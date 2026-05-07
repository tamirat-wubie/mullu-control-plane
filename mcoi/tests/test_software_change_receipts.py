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
from mcoi_runtime.app.software_receipt_review_queue import SoftwareReceiptReviewQueue
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
from mcoi_runtime.core.review import ReviewEngine
from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareQualityGate,
    SoftwareRequest,
    SoftwareWorkKind,
)
from mcoi_runtime.mcp.server import MulluMCPServer, SoftwareDevRunnerConfig
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


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


def _runner_config(
    tmp_path: Path,
    *,
    receipt_store: SoftwareChangeReceiptStore | None = None,
    receipt_review_queue: SoftwareReceiptReviewQueue | None = None,
) -> SoftwareDevRunnerConfig:
    adapter = _adapter(_workspace(tmp_path))
    return SoftwareDevRunnerConfig(
        adapter=adapter,
        plan_generator=_plan,
        patch_generator=_patch,
        gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate},
        clock=_clock,
        ucja_runner=_accept_ucja,
        receipt_store=receipt_store,
        receipt_review_queue=receipt_review_queue,
    )


def _open_receipt() -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id="receipt-open-mcp-review",
        request_id="request-open-mcp-review",
        stage=SoftwareChangeReceiptStage.REVIEW_REQUIRED,
        cause="software change requires operator review",
        outcome="requires_review",
        target_refs=("case:request-open-mcp-review",),
        constraint_refs=("constraint:software_change_lifecycle_v1",),
        evidence_refs=("certificate:request-open-mcp-review",),
        created_at=T0,
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
    assert body["receipt_persistence"]["configured"] is False
    assert body["receipt_persistence"]["persisted"] is False


def test_mcp_persists_receipts_when_store_configured(tmp_path: Path) -> None:
    store = SoftwareChangeReceiptStore()
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(tmp_path, receipt_store=store),
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
    request_id = body["evidence"]["request_id"]
    replayed = store.replay_request(request_id)

    assert not result.is_error
    assert body["receipt_persistence"]["configured"] is True
    assert body["receipt_persistence"]["persisted"] is True
    assert body["receipt_persistence"]["count"] == len(body["receipts"])
    assert [receipt.receipt_id for receipt in replayed] == [
        receipt["receipt_id"] for receipt in body["receipts"]
    ]


def test_mcp_receipt_query_tool_hidden_without_store(tmp_path: Path) -> None:
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(tmp_path),
    )
    names = [tool.name for tool in server.list_tools()]

    assert "mullu_software_change" in names
    assert "mullu_software_receipts" not in names


def test_mcp_receipt_query_tool_lists_gets_and_replays(tmp_path: Path) -> None:
    store = SoftwareChangeReceiptStore()
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(tmp_path, receipt_store=store),
    )

    change_result = server.call_tool("mullu_software_change", {
        "kind": "bug_fix",
        "summary": "rename hello",
        "repository": "repo-receipts",
        "affected_files": ["main.py"],
        "quality_gates": ["unit_tests"],
        "max_self_debug_iterations": 0,
    })
    change_body = json.loads(change_result.content)
    request_id = change_body["evidence"]["request_id"]
    terminal_receipt_id = change_body["receipts"][-1]["receipt_id"]

    names = [tool.name for tool in server.list_tools()]
    list_result = server.call_tool("mullu_software_receipts", {
        "operation": "list",
        "request_id": request_id,
        "stage": "terminal_closed",
        "limit": 5,
    })
    get_result = server.call_tool("mullu_software_receipts", {
        "operation": "get",
        "receipt_id": terminal_receipt_id,
    })
    replay_result = server.call_tool("mullu_software_receipts", {
        "operation": "replay",
        "request_id": request_id,
    })

    list_body = json.loads(list_result.content)
    get_body = json.loads(get_result.content)
    replay_body = json.loads(replay_result.content)

    assert "mullu_software_receipts" in names
    assert not list_result.is_error
    assert not get_result.is_error
    assert not replay_result.is_error
    assert list_body["count"] == 1
    assert list_body["receipts"][0]["stage"] == "terminal_closed"
    assert get_body["found"] is True
    assert get_body["receipts"][0]["receipt_id"] == terminal_receipt_id
    assert replay_body["terminal_closed"] is True
    assert replay_body["count"] == len(change_body["receipts"])


def test_mcp_receipt_query_rejects_missing_replay_request_id(tmp_path: Path) -> None:
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(
            tmp_path,
            receipt_store=SoftwareChangeReceiptStore(),
        ),
    )

    result = server.call_tool("mullu_software_receipts", {"operation": "replay"})

    assert result.is_error
    assert "request_id" in result.content


def test_mcp_receipt_query_materializes_and_decides_review_requests(tmp_path: Path) -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_open_receipt())
    review_queue = SoftwareReceiptReviewQueue(
        review_engine=ReviewEngine(clock=_clock),
        receipt_store=store,
    )
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(
            tmp_path,
            receipt_store=store,
            receipt_review_queue=review_queue,
        ),
    )

    review_result = server.call_tool("mullu_software_receipts", {
        "operation": "review",
        "limit": 10,
    })
    sync_result = server.call_tool("mullu_software_receipts", {
        "operation": "review_sync",
        "limit": 10,
    })
    request_id = json.loads(sync_result.content)["review_requests"][0]["request_id"]
    pending_result = server.call_tool("mullu_software_receipts", {
        "operation": "review_requests",
    })
    decision_result = server.call_tool("mullu_software_receipts", {
        "operation": "review_decide",
        "request_id": request_id,
        "reviewer_id": "operator-mcp",
        "approved": True,
        "comment": "approved through MCP",
    })
    replay_result = server.call_tool("mullu_software_receipts", {
        "operation": "replay",
        "request_id": "request-open-mcp-review",
    })

    review_body = json.loads(review_result.content)
    sync_body = json.loads(sync_result.content)
    pending_body = json.loads(pending_result.content)
    decision_body = json.loads(decision_result.content)
    replay_body = json.loads(replay_result.content)

    assert not review_result.is_error
    assert not sync_result.is_error
    assert not pending_result.is_error
    assert not decision_result.is_error
    assert review_body["requires_operator_review"] is True
    assert review_body["review_signals"][0]["latest_receipt_id"] == "receipt-open-mcp-review"
    assert sync_body["review_request_count"] == 1
    assert pending_body["pending_review_count"] == 1
    assert decision_body["gate_allowed"] is True
    assert decision_body["review_decision"]["reviewer_id"] == "operator-mcp"
    assert replay_body["terminal_closed"] is True
    assert replay_body["receipts"][-1]["metadata"]["review_decision_id"] == (
        decision_body["review_decision"]["decision_id"]
    )


def test_mcp_receipt_review_sync_requires_review_queue(tmp_path: Path) -> None:
    server = MulluMCPServer(
        platform=_PlatformStub(),
        command_ledger=_ledger(),
        software_dev_runner=_runner_config(
            tmp_path,
            receipt_store=SoftwareChangeReceiptStore(),
        ),
    )

    result = server.call_tool("mullu_software_receipts", {"operation": "review_sync"})

    assert result.is_error
    assert "review queue not configured" in result.content
