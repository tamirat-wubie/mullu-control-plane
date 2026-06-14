"""Tests for Agentic Service Harness operator decision pending status.

Purpose: prove the platform-facing status blocks live producer authority until
an explicit operator decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_pending_status
and scripts.validate_agentic_service_harness_live_producer_operator_decision_pending_status.
Invariants:
  - The default pending status validates.
  - Generic continuation is never accepted as a decision.
  - Mutation route, credential, status, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_pending_status import (  # noqa: E402
    OPERATOR_DECISION_PENDING_STATUS_ID,
    project_value_absence_to_pending_status,
)
from gateway.agentic_service_harness_live_producer_operator_decision_record import (  # noqa: E402
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_pending_status import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_pending_status,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_absence import (  # noqa: E402
    validate_live_producer_operator_decision_value_absence,
)


def _default_status() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_pending_status_accepts_default_fixture() -> None:
    validation, produced_status = validate_live_producer_operator_decision_pending_status()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_operator_decision_pending_status.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_operator_decision_pending_status.schema.json"
    assert validation.status_boundary_id == OPERATOR_DECISION_PENDING_STATUS_ID
    assert validation.pending_status == "blocked_pending_operator_decision_value"
    assert validation.pending_requirement_count == len(ACCEPTED_RECORD_KINDS)
    assert validation.block_reason_count == 3
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_status["decision_gate_state"] == "blocked"
    assert produced_status["operator_action_required"] is True
    assert produced_status["generic_continuation_accepted_as_decision"] is False
    assert produced_status["authority_granted"] is False


def test_live_producer_operator_decision_pending_status_projects_value_absence() -> None:
    absence_validation, value_absence = validate_live_producer_operator_decision_value_absence()
    produced_status = project_value_absence_to_pending_status(value_absence)
    pending_requirements = produced_status["pending_requirements"]

    assert absence_validation.ok is True
    assert produced_status["status_boundary_id"] == OPERATOR_DECISION_PENDING_STATUS_ID
    assert tuple(entry["decision_kind"] for entry in pending_requirements) == ACCEPTED_RECORD_KINDS
    assert all(tuple(entry["required_value_shape"]) == REQUIRED_DECISION_RECORD_FIELDS for entry in pending_requirements)
    assert all(entry["blocks_live_authority"] is True for entry in pending_requirements)
    assert produced_status["block_reasons"] == [
        "explicit_operator_approval_missing",
        "explicit_operator_rejection_missing",
        "generic_continuation_not_decision_value",
    ]
    assert produced_status["authority_denials"]["live_execution_authorized"] is False
    assert produced_status["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_pending_status_rejects_unblocked_gate(tmp_path: Path) -> None:
    status = _default_status()
    status["decision_gate_state"] = "open"
    status["authority_granted"] = True
    status_path = tmp_path / "operator-decision-pending-status.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")

    validation, produced_status = validate_live_producer_operator_decision_pending_status(fixture_path=status_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "decision_gate_state" in serialized_errors
    assert "authority_granted" in serialized_errors
    assert produced_status["decision_gate_state"] == "blocked"
    assert produced_status["authority_granted"] is False


def test_live_producer_operator_decision_pending_status_rejects_generic_continuation_acceptance(
    tmp_path: Path,
) -> None:
    status = _default_status()
    status["generic_continuation_accepted_as_decision"] = True
    status["explicit_operator_value_present"] = True
    status_path = tmp_path / "operator-decision-pending-status.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")

    validation, produced_status = validate_live_producer_operator_decision_pending_status(fixture_path=status_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "generic_continuation_accepted_as_decision" in serialized_errors
    assert "explicit_operator_value_present" in serialized_errors
    assert produced_status["generic_continuation_accepted_as_decision"] is False


def test_live_producer_operator_decision_pending_status_rejects_mutation_route_ref(tmp_path: Path) -> None:
    status = _default_status()
    status["source_value_absence_ref"] = "POST /api/v1/harness/live-producer/operator-decision"
    status_path = tmp_path / "operator-decision-pending-status.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")

    validation, produced_status = validate_live_producer_operator_decision_pending_status(fixture_path=status_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_status["source_value_absence_ref"].startswith("value-absence://")


def test_live_producer_operator_decision_pending_status_rejects_secret_like_value(tmp_path: Path) -> None:
    status = _default_status()
    status["next_action"] = "Use sk-forbiddencredential"
    status_path = tmp_path / "operator-decision-pending-status.json"
    status_path.write_text(json.dumps(status), encoding="utf-8")

    validation, produced_status = validate_live_producer_operator_decision_pending_status(fixture_path=status_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors
    assert produced_status["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_pending_status_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["pending_requirement_count"] == len(ACCEPTED_RECORD_KINDS)
    assert payload["produced_status"]["decision_gate_state"] == "blocked"
    assert payload["produced_status"]["authority_granted"] is False
