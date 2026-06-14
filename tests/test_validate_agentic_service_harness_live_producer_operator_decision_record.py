"""Tests for Agentic Service Harness live producer operator decision record.

Purpose: prove generic continuation records no operator decision and no live
producer authority is granted by the decision record boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_record
and scripts.validate_agentic_service_harness_live_producer_operator_decision_record.
Invariants:
  - The default decision record validates.
  - Generic continuation never records approval or rejection.
  - Mutation route, credential, decision, and authority drift fail closed.
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
    OPERATOR_DECISION_RECORD_ID,
    REQUIRED_DECISION_RECORD_FIELDS,
    project_decision_evidence_to_decision_record,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_evidence import (  # noqa: E402
    validate_live_producer_operator_decision_evidence,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_record import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_record,
)


def _default_record() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_record_accept_default_fixture() -> None:
    validation, produced_record = validate_live_producer_operator_decision_record()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.fixture_path == "examples/agentic_service_harness_live_producer_operator_decision_record.local.json"
    assert validation.schema_path == "schemas/agentic_service_harness_live_producer_operator_decision_record.schema.json"
    assert validation.record_boundary_id == OPERATOR_DECISION_RECORD_ID
    assert validation.record_status == "AwaitingEvidence"
    assert validation.accepted_record_count == len(ACCEPTED_RECORD_KINDS)
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_record["current_input_kind"] == "generic_continuation"
    assert produced_record["generic_continuation_records_decision"] is False
    assert produced_record["approval_recorded"] is False
    assert produced_record["rejection_recorded"] is False


def test_live_producer_operator_decision_record_projects_decision_evidence() -> None:
    evidence_validation, decision_evidence = validate_live_producer_operator_decision_evidence()
    produced_record = project_decision_evidence_to_decision_record(decision_evidence)
    accepted = produced_record["accepted_record_shapes"]

    assert evidence_validation.ok is True
    assert produced_record["record_boundary_id"] == OPERATOR_DECISION_RECORD_ID
    assert tuple(entry["decision_kind"] for entry in accepted) == ACCEPTED_RECORD_KINDS
    assert all(tuple(entry["required_fields"]) == REQUIRED_DECISION_RECORD_FIELDS for entry in accepted)
    assert all(entry["status"] == "AwaitingEvidence" for entry in accepted)
    assert produced_record["generic_continuation_records_decision"] is False
    assert produced_record["authority_denials"]["live_execution_authorized"] is False
    assert produced_record["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_record_rejects_generic_decision(tmp_path: Path) -> None:
    record = _default_record()
    record["generic_continuation_records_decision"] = True
    record["approval_recorded"] = True
    record["current_decision_kind"] = "explicit_operator_approval"
    record_path = tmp_path / "operator-decision-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "generic_continuation_records_decision" in serialized_errors
    assert "approval_recorded" in serialized_errors
    assert "current_decision_kind" in serialized_errors
    assert produced_record["approval_recorded"] is False


def test_live_producer_operator_decision_record_rejects_live_authority(tmp_path: Path) -> None:
    record = _default_record()
    record["authority_denials"]["live_execution_authorized"] = True
    record_path = tmp_path / "operator-decision-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "live execution authority" in serialized_errors
    assert produced_record["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_record_rejects_mutation_route_ref(tmp_path: Path) -> None:
    record = _default_record()
    record["source_decision_evidence_ref"] = "POST /api/v1/harness/live-producer/decision-record"
    record_path = tmp_path / "operator-decision-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_record["source_decision_evidence_ref"].startswith("decision-evidence://")


def test_live_producer_operator_decision_record_rejects_secret_like_value(tmp_path: Path) -> None:
    record = _default_record()
    record["next_action"] = "Record sk-forbiddencredential"
    record_path = tmp_path / "operator-decision-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors
    assert produced_record["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_record_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["accepted_record_count"] == len(ACCEPTED_RECORD_KINDS)
    assert payload["produced_record"]["approval_recorded"] is False
