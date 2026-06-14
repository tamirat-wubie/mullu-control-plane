"""Tests for Agentic Service Harness operator decision value absence.

Purpose: prove generic continuation provides no explicit operator decision
value and grants no live producer authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_absence
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_absence.
Invariants:
  - The default absence witness validates.
  - Generic continuation never provides approval or rejection values.
  - Mutation route, credential, value, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_record import (  # noqa: E402
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_absence import (  # noqa: E402
    OPERATOR_DECISION_VALUE_ABSENCE_ID,
    project_decision_record_to_value_absence,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_record import (  # noqa: E402
    validate_live_producer_operator_decision_record,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_absence import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_absence,
)


def _default_absence() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_absence_accept_default_fixture() -> None:
    validation, produced_absence = validate_live_producer_operator_decision_value_absence()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_operator_decision_value_absence.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_operator_decision_value_absence.schema.json"
    assert validation.absence_boundary_id == OPERATOR_DECISION_VALUE_ABSENCE_ID
    assert validation.absence_status == "AwaitingEvidence"
    assert validation.missing_value_count == len(ACCEPTED_RECORD_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_absence["observed_input_kind"] == "generic_continuation"
    assert produced_absence["explicit_operator_value_present"] is False
    assert produced_absence["approval_value_present"] is False
    assert produced_absence["rejection_value_present"] is False


def test_live_producer_operator_decision_value_absence_projects_decision_record() -> None:
    record_validation, decision_record = validate_live_producer_operator_decision_record()
    produced_absence = project_decision_record_to_value_absence(decision_record)
    missing_values = produced_absence["missing_value_requirements"]

    assert record_validation.ok is True
    assert produced_absence["absence_boundary_id"] == OPERATOR_DECISION_VALUE_ABSENCE_ID
    assert tuple(entry["decision_kind"] for entry in missing_values) == ACCEPTED_RECORD_KINDS
    assert all(tuple(entry["required_value_shape"]) == REQUIRED_DECISION_RECORD_FIELDS for entry in missing_values)
    assert all(entry["status"] == "AwaitingEvidence" for entry in missing_values)
    assert produced_absence["decision_value_text_present"] is False
    assert produced_absence["authority_denials"]["live_execution_authorized"] is False
    assert produced_absence["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_value_absence_rejects_present_value(tmp_path: Path) -> None:
    absence = _default_absence()
    absence["explicit_operator_value_present"] = True
    absence["approval_value_present"] = True
    absence["decision_value_text_present"] = True
    absence_path = tmp_path / "operator-decision-value-absence.json"
    absence_path.write_text(json.dumps(absence), encoding="utf-8")

    validation, produced_absence = validate_live_producer_operator_decision_value_absence(fixture_path=absence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "explicit_operator_value_present" in serialized_errors
    assert "approval_value_present" in serialized_errors
    assert "decision_value_text_present" in serialized_errors
    assert produced_absence["explicit_operator_value_present"] is False


def test_live_producer_operator_decision_value_absence_rejects_live_authority(tmp_path: Path) -> None:
    absence = _default_absence()
    absence["authority_denials"]["live_execution_authorized"] = True
    absence_path = tmp_path / "operator-decision-value-absence.json"
    absence_path.write_text(json.dumps(absence), encoding="utf-8")

    validation, produced_absence = validate_live_producer_operator_decision_value_absence(fixture_path=absence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live execution authority" in serialized_errors
    assert produced_absence["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_value_absence_rejects_mutation_route_ref(tmp_path: Path) -> None:
    absence = _default_absence()
    absence["source_decision_record_ref"] = "POST /api/v1/harness/live-producer/decision-value"
    absence_path = tmp_path / "operator-decision-value-absence.json"
    absence_path.write_text(json.dumps(absence), encoding="utf-8")

    validation, produced_absence = validate_live_producer_operator_decision_value_absence(fixture_path=absence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_absence["source_decision_record_ref"].startswith("decision-record://")


def test_live_producer_operator_decision_value_absence_rejects_secret_like_value(tmp_path: Path) -> None:
    absence = _default_absence()
    absence["next_action"] = "Provide github_pat_forbiddencredential"
    absence_path = tmp_path / "operator-decision-value-absence.json"
    absence_path.write_text(json.dumps(absence), encoding="utf-8")

    validation, produced_absence = validate_live_producer_operator_decision_value_absence(fixture_path=absence_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "github_pat_forbiddencredential" not in serialized_errors
    assert produced_absence["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_value_absence_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["missing_value_count"] == len(ACCEPTED_RECORD_KINDS)
    assert payload["produced_absence"]["explicit_operator_value_present"] is False
