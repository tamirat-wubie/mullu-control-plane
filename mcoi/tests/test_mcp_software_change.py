"""Tests for the mullu_software_change MCP tool.

Verifies:
  - Tool is hidden from list_tools when no runner is configured
  - Tool appears with correct schema when a runner is configured
  - Schema declares all expected properties (kind, summary, repository,
    mode, quality_gates, etc.)
  - Tool is tagged as high risk_tier
  - Schema-level rejections (bad kind, bad mode, missing required) come
    back as is_error=True without invoking the loop
  - Successful run delegates to governed_software_change and returns
    a JSON payload with outcome, certificate, and evidence
  - Loop exceptions are bounded — no backend detail leaks
"""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gateway.command_spine import CommandLedger, InMemoryCommandLedgerStore
from mcoi_runtime.adapters.code_adapter import CommandPolicy, LocalCodeAdapter
from mcoi_runtime.contracts.code import PatchProposal
from mcoi_runtime.contracts.software_dev_loop import (
    QualityGateResult,
    WorkPlan,
)
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.governed_session import Platform
from mcoi_runtime.core.proof_bridge import ProofBridge
from mcoi_runtime.core.software_dev_loop import UCJAOutcomeShape
from mcoi_runtime.domain_adapters.software_dev import SoftwareQualityGate
from mcoi_runtime.mcp.server import (
    MulluMCPServer,
    SoftwareDevRunnerConfig,
)


T0 = "2025-01-15T10:00:00+00:00"


def _clock():
    return T0


def _platform():
    return Platform(
        clock=_clock,
        audit_trail=AuditTrail(clock=_clock),
        proof_bridge=ProofBridge(clock=_clock),
    )


def _ledger() -> CommandLedger:
    return CommandLedger(
        clock=_clock,
        store=InMemoryCommandLedgerStore(),
    )


class _PlatformStub:
    def __init__(self):
        self._session = SimpleNamespace(close=lambda: None)

    def connect(self, **kwargs):
        return self._session


def _setup_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    return ws


def _accept_ucja(payload: dict[str, Any]) -> UCJAOutcomeShape:
    return UCJAOutcomeShape(
        accepted=True, rejected=False,
        job_id="job-mcp-accept",
        halted_at_layer=None, reason="",
    )


def _basic_plan(req, snap) -> WorkPlan:
    return WorkPlan(
        plan_id="plan-mcp",
        summary="rename hello",
        steps=("rewrite",),
        target_files=("main.py",),
    )


def _basic_patch(req, snap, plan, attempt, prior_failures) -> PatchProposal:
    return PatchProposal(
        patch_id="patch-mcp",
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


def _passing_gate(adapter, request, attempt) -> QualityGateResult:
    return QualityGateResult(
        gate=SoftwareQualityGate.UNIT_TESTS.value,
        passed=True,
        evidence_id=f"gate-attempt-{attempt}",
        summary="ok",
    )


def _runner_config(tmp_path: Path) -> SoftwareDevRunnerConfig:
    ws = _setup_workspace(tmp_path)
    adapter = LocalCodeAdapter(
        root_path=str(ws),
        clock=_clock,
        command_policy=CommandPolicy.permissive_for_testing(),
    )
    return SoftwareDevRunnerConfig(
        adapter=adapter,
        plan_generator=_basic_plan,
        patch_generator=_basic_patch,
        gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate},
        clock=_clock,
        ucja_runner=_accept_ucja,
    )


# ---- Tool listing ----


class TestMCPSoftwareChangeListing:
    def test_omitted_when_runner_not_configured(self):
        server = MulluMCPServer(platform=_PlatformStub())
        names = [t.name for t in server.list_tools()]
        assert "mullu_software_change" not in names

    def test_present_when_runner_configured(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            software_dev_runner=_runner_config(tmp_path),
        )
        names = [t.name for t in server.list_tools()]
        assert "mullu_software_change" in names

    def test_schema_declares_required_and_enums(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            software_dev_runner=_runner_config(tmp_path),
        )
        tool = next(t for t in server.list_tools() if t.name == "mullu_software_change")
        schema = tool.input_schema
        assert "kind" in schema["properties"]
        assert "summary" in schema["properties"]
        assert "repository" in schema["properties"]
        assert set(schema["required"]) == {"kind", "summary", "repository"}
        # Mode enum surfaces all six work modes
        modes = schema["properties"]["mode"]["enum"]
        for required_mode in ("plan_only", "dry_run", "patch_only",
                              "patch_and_test", "patch_test_review",
                              "commit_candidate"):
            assert required_mode in modes
        # Quality gate enum surfaces all seven gates
        gates = schema["properties"]["quality_gates"]["items"]["enum"]
        for required_gate in ("unit_tests", "integration_tests", "lint",
                              "typecheck", "security_scan", "build", "review"):
            assert required_gate in gates


# ---- Schema-level rejection ----


class TestMCPSoftwareChangeSchemaRejection:
    def test_missing_required_summary_yields_error(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            software_dev_runner=_runner_config(tmp_path),
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "repository": "r",
        })
        assert result.is_error
        assert "summary" in result.content.lower()

    def test_invalid_kind_rejected(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            software_dev_runner=_runner_config(tmp_path),
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "definitely_not_a_kind",
            "summary": "x",
            "repository": "r",
        })
        assert result.is_error
        assert "kind" in result.content.lower()

    def test_invalid_mode_rejected(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            software_dev_runner=_runner_config(tmp_path),
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "summary": "x",
            "repository": "r",
            "mode": "definitely_not_a_mode",
        })
        assert result.is_error
        assert "mode" in result.content.lower()

    def test_invalid_quality_gate_rejected(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            software_dev_runner=_runner_config(tmp_path),
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "summary": "x",
            "repository": "r",
            "quality_gates": ["unit_tests", "definitely_not_a_gate"],
        })
        assert result.is_error
        assert "quality_gates" in result.content.lower() or "gate" in result.content.lower()


# ---- Successful invocation ----


class TestMCPSoftwareChangeSuccess:
    def test_happy_path_returns_solved_payload(self, tmp_path):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            software_dev_runner=_runner_config(tmp_path),
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "summary": "rename hello",
            "repository": "r",
            "affected_files": ["main.py"],
            "quality_gates": ["unit_tests"],
            "max_self_debug_iterations": 0,
        })
        assert not result.is_error
        body = json.loads(result.content)
        assert body["outcome"] == "solved"
        assert body["solved"] is True
        assert body["certificate"]["disposition"] == "committed"
        assert body["evidence"]["ucja_accepted"] is True
        assert len(body["evidence"]["attempts"]) == 1
        attempt = body["evidence"]["attempts"][0]
        assert attempt["status"] == "gates_passed"
        assert attempt["rolled_back"] is False

    def test_high_risk_tier_recorded(self, tmp_path):
        ledger = _ledger()
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=ledger,
            software_dev_runner=_runner_config(tmp_path),
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "summary": "rename",
            "repository": "r",
            "affected_files": ["main.py"],
            "quality_gates": ["unit_tests"],
            "max_self_debug_iterations": 0,
        })
        # The metadata records the tool's risk_tier; underlying ledger
        # transitions also surface "high" on every tagged event (RECEIVED
        # is created before risk classification, so it carries no tier).
        assert result.metadata["risk_tier"] == "high"
        command_id = result.metadata["command_id"]
        events = ledger.events_for(command_id)
        tagged = [event.risk_tier for event in events if event.risk_tier]
        assert tagged, "no events were risk-tier tagged"
        assert all(tier == "high" for tier in tagged)


# ---- Runner not configured ----


class TestMCPSoftwareChangeNoRunner:
    def test_runner_missing_yields_service_error(self):
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            # software_dev_runner intentionally omitted
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "summary": "x",
            "repository": "r",
        })
        assert result.is_error
        assert "not configured" in result.content


# ---- Loop exception bounded ----


class TestMCPSoftwareChangeBoundedError:
    def test_plan_generator_raising_yields_review_disposition(self, tmp_path):
        ws = _setup_workspace(tmp_path)
        adapter = LocalCodeAdapter(
            root_path=str(ws),
            clock=_clock,
            command_policy=CommandPolicy.permissive_for_testing(),
        )

        def raising_plan(req, snap):
            raise ValueError("secret detail about how plan generation broke")

        config = SoftwareDevRunnerConfig(
            adapter=adapter,
            plan_generator=raising_plan,
            patch_generator=_basic_patch,
            gate_runners={SoftwareQualityGate.UNIT_TESTS: _passing_gate},
            clock=_clock,
            ucja_runner=_accept_ucja,
        )
        server = MulluMCPServer(
            platform=_PlatformStub(),
            command_ledger=_ledger(),
            software_dev_runner=config,
        )
        result = server.call_tool("mullu_software_change", {
            "kind": "bug_fix",
            "summary": "x",
            "repository": "r",
            "affected_files": ["main.py"],
            "quality_gates": ["unit_tests"],
        })
        # The loop catches ValueError from plan_generator and returns a
        # REQUIRES_REVIEW certificate; not an MCP error
        assert not result.is_error
        body = json.loads(result.content)
        assert body["outcome"] == "requires_review"
        assert body["certificate"]["disposition"] == "requires_review"
        # Secret detail does not leak
        assert "secret detail" not in result.content
