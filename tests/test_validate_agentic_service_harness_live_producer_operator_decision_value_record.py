"""Tests for Agentic Service Harness operator decision value record.

Purpose: prove explicit operator approval is recorded without granting live
producer authority or satisfying remaining live-effect witnesses.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_record
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record.
Invariants:
  - The default approval record validates.
  - Remaining witnesses continue to block live producer implementation.
  - Mutation route, credential, raw input, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_value_record import (  # noqa: E402
    OPERATOR_DECISION_VALUE_RECORD_ID,
    project_record_path_to_operator_decision_value_record,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_record,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record_path import (  # noqa: E402
    validate_live_producer_operator_decision_value_record_path,
)


def _default_record() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_record_accepts_default_fixture() -> None:
    validation, produced_record = validate_live_producer_operator_decision_value_record()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.record_id == OPERATOR_DECISION_VALUE_RECORD_ID
    assert validation.decision_kind == "explicit_operator_approval"
    assert validation.approval_status == "Satisfied"
    assert validation.remaining_witness_count == 4
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_record["operator_approval_witness_satisfied"] is True
    assert produced_record["authority_granted"] is False


def test_live_producer_operator_decision_value_record_projects_record_path() -> None:
    path_validation, record_path = validate_live_producer_operator_decision_value_record_path()
    produced_record = project_record_path_to_operator_decision_value_record(
        record_path,
        operator_decision_value="approve",
    )

    assert path_validation.ok is True
    assert produced_record["record_id"] == OPERATOR_DECISION_VALUE_RECORD_ID
    assert produced_record["normalized_decision_value"] == "approve"
    assert produced_record["operator_value_record_created"] is True
    assert produced_record["operator_approval_witness_satisfied"] is True
    assert produced_record["remaining_live_witnesses_status"] == "AwaitingEvidence"
    assert all(witness["blocks_live_producer"] is True for witness in produced_record["remaining_witnesses"])


def test_live_producer_operator_decision_value_record_rejects_live_authority(tmp_path: Path) -> None:
    record = _default_record()
    record["authority_granted"] = True
    record["record_controls"]["grants_live_authority"] = True
    record["authority_denials"]["live_execution_authorized"] = True
    record_path = tmp_path / "operator-decision-value-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_value_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "authority_granted" in serialized_errors
    assert "record_controls.grants_live_authority" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_record["authority_granted"] is False
    assert produced_record["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_value_record_rejects_remaining_witness_satisfaction(
    tmp_path: Path,
) -> None:
    record = _default_record()
    record["remaining_witnesses"][0]["status"] = "Satisfied"
    record["remaining_witnesses"][0]["blocks_live_producer"] = False
    record_path = tmp_path / "operator-decision-value-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_value_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "effect_receipt status must be AwaitingEvidence" in serialized_errors
    assert "effect_receipt must block live producer" in serialized_errors
    assert produced_record["remaining_witnesses"][0]["status"] == "AwaitingEvidence"
    assert produced_record["remaining_witnesses"][0]["blocks_live_producer"] is True


def test_live_producer_operator_decision_value_record_rejects_raw_input_storage(tmp_path: Path) -> None:
    record = _default_record()
    record["raw_input_serialized"] = True
    record["record_controls"]["stores_raw_operator_input"] = True
    record_path = tmp_path / "operator-decision-value-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_value_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "raw_input_serialized" in serialized_errors
    assert "record_controls.stores_raw_operator_input" in serialized_errors
    assert produced_record["raw_input_serialized"] is False
    assert produced_record["record_controls"]["stores_raw_operator_input"] is False


def test_live_producer_operator_decision_value_record_rejects_mutation_route_ref(tmp_path: Path) -> None:
    record = _default_record()
    record["operator_input_ref"] = "POST /api/v1/harness/live-producer/operator-decision-value-record"
    record_path = tmp_path / "operator-decision-value-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_value_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_record["operator_input_ref"].startswith("codex-thread://")


def test_live_producer_operator_decision_value_record_rejects_secret_like_value(tmp_path: Path) -> None:
    record = _default_record()
    record["next_action"] = "Collect sk-forbiddencredential"
    record_path = tmp_path / "operator-decision-value-record.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")

    validation, produced_record = validate_live_producer_operator_decision_value_record(fixture_path=record_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors
    assert produced_record["record_controls"]["stores_secret_values"] is False


def test_live_producer_operator_decision_value_record_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["decision_kind"] == "explicit_operator_approval"
    assert payload["produced_record"]["operator_approval_witness_satisfied"] is True
    assert payload["produced_record"]["authority_granted"] is False
