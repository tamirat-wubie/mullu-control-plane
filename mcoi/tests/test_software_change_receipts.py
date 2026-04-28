"""Purpose: verify governed software-change receipts.
Governance scope: lifecycle receipt typing and causal ordering for the
software-dev autonomy loop.
Dependencies: pytest, local code adapter, software-dev loop contracts.
Invariants:
  - Every receipt binds request, stage, target, constraint, evidence, and time.
  - Plan validation receipts precede patch receipts.
  - Terminal closure is always the final receipt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.command_spine import CommandLedger, InMemoryCommandLedgerStore
from mcoi_runtime.adapters.code_adapter import CommandPolicy, LocalCodeAdapter
from mcoi_runtime.contracts.code import PatchProposal
from mcoi_runtime.contracts.software_dev_loop import (
    QualityGateResult,
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
    WorkPlan,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.software_dev_loop import (
    UCJAOutcomeShape,
    governed_software_change,
)
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
)
from mcoi_runtime.mcp.server import MulluMCPServer, SoftwareDevRunnerConfig


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _clock_factory():
    times = iter((T0, T1, T1, T1, T1, T1, T1, T1))
    return lambda: next(times)


def _clock() -> str:
    return T0


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    return ws


def _adapter(ws: Path) -> LocalCodeAdapter:
    return LocalCodeAdapter(
        root_path=str(ws),
        clock=lambda: T0,
        command_policy=CommandPolicy.permissive_for_testing(),
    )


def _accept_ucja(payload: dict[str, Any]) -> UCJAOutcomeShape:
    return UCJAOutcomeShape(
        accepted=True,
        rejected=False,
        job_id="job-receipt-accept",
        halted_at_layer=None,
        reason="",
    )


def _request(**overrides: Any) -> SoftwareRequest:
    values = {
        "kind": SoftwareWorkKind.BUG_FIX,
        "summary": "rename hello to greet",
        "repository": "repo-receipts",
        "affected_files": ("main.py",),
        "acceptance_criteria": ("function renamed",),
        "quality_gates": (SoftwareQualityGate.UNIT_TESTS,),
        "max_self_debug_iterations": 0,
    }
    values.update(overrides)
    return SoftwareRequest(**values)


def _plan(req: SoftwareRequest, snapshot: object) -> WorkPlan:
    return WorkPlan(
        plan_id="plan-receipts",
        summary="rename function",
        steps=("rewrite function definition",),
        target_files=("main.py",),
    )


def _patch(
    req: SoftwareRequest,
    snapshot: object,
    plan: WorkPlan,
    attempt: int,
    prior_failures: tuple[QualityGateResult, ...],
) -> PatchProposal:
    return PatchProposal(
        patch_id=f"patch-receipts-{attempt}",
        target_file="main.py",
        description="rename function",
        unified_diff=(
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-def hello():\n"
            "+def greet():\n"
            "     return 'world'\n"
        ),
    )


def _passing_gate(
    adapter: LocalCodeAdapter,
    request: SoftwareRequest,
    attempt: int,
) -> QualityGateResult:
    return QualityGateResult(
        gate=SoftwareQualityGate.UNIT_TESTS.value,
        passed=True,
        evidence_id=f"gate-receipts-{attempt}",
        summary="ok",
    )


class _PlatformStub:
    def __init__(self) -> None:
        self._session = type("Session", (), {"close": lambda self: None})()

    def connect(self, **kwargs: Any) -> object:
        return self._session


def _ledger() -> CommandLedger:
    return CommandLedger(clock=_clock, store=InMemoryCommandLedgerStore())


def _runner_config(tmp_path: Path) -> SoftwareDevRunnerConfig:
    adapter = _adapter(_workspace(tmp_path))
    return SoftwareDevRunnerConfig(
        adapter=adapter,
        plan_generator=_plan,
        patch_generator=_patch,
        gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate},
        clock=_clock,
        ucja_runner=_accept_ucja,
    )


def test_successful_loop_emits_ordered_lifecycle_receipts(tmp_path: Path) -> None:
    adapter = _adapter(_workspace(tmp_path))
    outcome = governed_software_change(
        _request(),
        adapter=adapter,
        plan_generator=_plan,
        patch_generator=_patch,
        gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate},
        clock=_clock_factory(),
        ucja_runner=_accept_ucja,
    )

    stages = tuple(receipt.stage for receipt in outcome.receipts)

    assert outcome.certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert stages[0] is SoftwareChangeReceiptStage.REQUEST_ADMITTED
    assert stages.index(SoftwareChangeReceiptStage.PLAN_VALIDATED) < stages.index(
        SoftwareChangeReceiptStage.PATCH_APPLIED,
    )
    assert stages[-1] is SoftwareChangeReceiptStage.TERMINAL_CLOSED
    assert all(receipt.request_id == outcome.evidence.request_id for receipt in outcome.receipts)
    assert all(receipt.target_refs and receipt.evidence_refs for receipt in outcome.receipts)


def test_receipt_contract_rejects_incomplete_witness_fields() -> None:
    try:
        SoftwareChangeReceipt(
            receipt_id="receipt-1",
            request_id="request-1",
            stage=SoftwareChangeReceiptStage.REQUEST_ADMITTED,
            cause="request received",
            outcome="accepted",
            target_refs=(),
            constraint_refs=("constraint:software_change_lifecycle_v1",),
            evidence_refs=("request:request-1",),
            created_at=T0,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message
    assert "must contain at least one item" in message
    assert "receipt-1" not in message


def test_mcp_payload_surfaces_json_receipts(tmp_path: Path) -> None:
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(tmp_path),
    )

    result = server.call_tool("mullu_software_change", {
        "kind": "bug_fix",
        "summary": "rename hello",
        "repository": "repo-receipts",
        "affected_files": ["main.py"],
        "quality_gates": ["unit_tests"],
        "max_self_debug_iterations": 0,
    })
    body = json.loads(result.content)
    receipt_stages = [receipt["stage"] for receipt in body["receipts"]]

    assert not result.is_error
    assert body["outcome"] == "solved"
    assert receipt_stages[0] == "request_admitted"
    assert "gate_evaluated" in receipt_stages
    assert receipt_stages[-1] == "terminal_closed"
    assert body["receipts"][-1]["metadata"]["certificate_id"] == body["certificate"]["certificate_id"]
