"""Tests for Agentic Service Harness live producer admission gate.

Purpose: prove the live producer admission gate stays blocked, read-only, and
free of live execution authority after local rehearsal evidence exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_admission and
scripts.validate_agentic_service_harness_live_producer_admission_gate.
Invariants:
  - The default admission gate validates.
  - Live execution, mutation route, and secret drift fail closed.
  - Invalid local rehearsal input produces a blocked invalid gate.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_admission import (  # noqa: E402
    ADMISSION_GATE_ID,
    DEFAULT_BLOCKED_REASONS,
    FALSE_AUTHORITY_FLAGS,
    project_rehearsal_to_live_producer_admission_gate,
)
from scripts.validate_agentic_service_harness_live_producer_admission_gate import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_admission_gate,
)
from scripts.validate_agentic_service_harness_live_task_run_producer_rehearsal import (  # noqa: E402
    validate_live_task_run_producer_rehearsal,
)


def _default_gate() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_admission_gate_accepts_default_fixture() -> None:
    validation, produced_gate = validate_live_producer_admission_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_admission_gate.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_admission_gate.schema.json"
    assert validation.gate_id == ADMISSION_GATE_ID
    assert validation.gate_state == "blocked_pending_live_authority"
    assert validation.blocked_reason_count == len(DEFAULT_BLOCKED_REASONS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_gate["admission_decision"] == "blocked"
    assert produced_gate["live_producer_implemented"] is False
    assert produced_gate["terminal_closure"] is False


def test_live_producer_admission_gate_projects_rehearsal_without_live_authority() -> None:
    rehearsal_validation, rehearsal_report = validate_live_task_run_producer_rehearsal()
    produced_gate = project_rehearsal_to_live_producer_admission_gate(rehearsal_report)

    assert rehearsal_validation.ok is True
    assert produced_gate["source_rehearsal_report_id"] == rehearsal_report["report_id"]
    assert produced_gate["scope"]["tenant_id"] == rehearsal_report["scope"]["tenant_id"]
    assert produced_gate["required_evidence"]["read_only_status_route_ref"] == "GET:/api/v1/harness/status"
    assert produced_gate["admission_decision"] == "blocked"
    assert produced_gate["solver_outcome"] == "AwaitingEvidence"
    assert produced_gate["effect_boundary"]["network_policy"] == "none"
    assert produced_gate["authority_denials"]["live_execution_authorized"] is False
    assert all(produced_gate["effect_boundary"][flag_name] is False for flag_name in FALSE_AUTHORITY_FLAGS)


def test_live_producer_admission_gate_rejects_live_execution_authority(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["authority_denials"]["live_execution_authorized"] = True
    gate_path = tmp_path / "admission-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_admission_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live_execution_authorized" in serialized_errors or "live execution authority" in serialized_errors
    assert produced_gate["authority_denials"]["live_execution_authorized"] is False
    assert produced_gate["admission_decision"] == "blocked"


def test_live_producer_admission_gate_rejects_mutation_route_ref(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["required_evidence"]["read_only_status_route_ref"] = "POST /api/v1/harness/tasks"
    gate_path = tmp_path / "admission-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_admission_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_gate["required_evidence"]["read_only_status_route_ref"] == "GET:/api/v1/harness/status"
    assert produced_gate["terminal_closure"] is False


def test_live_producer_admission_gate_rejects_secret_like_value(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["required_evidence"]["effect_receipt_ref"] = "receipt://ghp_forbiddencredential"
    gate_path = tmp_path / "admission-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_admission_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "ghp_forbiddencredential" not in serialized_errors
    assert produced_gate["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_admission_gate_blocks_invalid_rehearsal() -> None:
    rehearsal_validation, rehearsal_report = validate_live_task_run_producer_rehearsal()
    unsafe_report = dict(rehearsal_report)
    unsafe_report["live_producer_implemented"] = True

    produced_gate = project_rehearsal_to_live_producer_admission_gate(unsafe_report)

    assert rehearsal_validation.ok is True
    assert produced_gate["gate_state"] == "blocked_invalid_rehearsal"
    assert produced_gate["solver_outcome"] == "GovernanceBlocked"
    assert "invalid_local_rehearsal" in produced_gate["blocked_reasons"]
    assert produced_gate["live_producer_implemented"] is False
    assert produced_gate["effect_boundary"]["runtime_state_written"] is False


def test_live_producer_admission_gate_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["gate_state"] == "blocked_pending_live_authority"
    assert payload["produced_gate"]["admission_decision"] == "blocked"
