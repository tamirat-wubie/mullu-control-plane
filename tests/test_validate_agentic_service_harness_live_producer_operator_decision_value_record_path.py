"""Tests for Agentic Service Harness operator decision value record path.

Purpose: prove the future value-record path is defined but remains blocked
until an actual explicit operator decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_record_path
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record_path.
Invariants:
  - The default record path validates.
  - Record creation, value presence, and route admission fail closed.
  - Mutation route, credential, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_value_record_path import (  # noqa: E402
    OPERATOR_DECISION_VALUE_RECORD_PATH_ID,
    project_collection_gate_to_value_record_path,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate import (  # noqa: E402
    validate_live_producer_operator_decision_value_collection_gate,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_record_path import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_record_path,
)


def _default_path() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_record_path_accepts_default_fixture() -> None:
    validation, produced_path = validate_live_producer_operator_decision_value_record_path()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.record_path_id == OPERATOR_DECISION_VALUE_RECORD_PATH_ID
    assert validation.path_status == "ready_blocked_awaiting_explicit_operator_value"
    assert validation.accepted_record_kind_count == 2
    assert validation.rejected_input_kind_count == 2
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_path["record_contract_ready"] is True
    assert produced_path["operator_value_record_created"] is False
    assert produced_path["authority_granted"] is False


def test_live_producer_operator_decision_value_record_path_projects_collection_gate() -> None:
    gate_validation, collection_gate = validate_live_producer_operator_decision_value_collection_gate()
    produced_path = project_collection_gate_to_value_record_path(collection_gate)

    assert gate_validation.ok is True
    assert produced_path["record_path_id"] == OPERATOR_DECISION_VALUE_RECORD_PATH_ID
    assert produced_path["accepted_record_kinds"] == ["explicit_operator_approval", "explicit_operator_rejection"]
    assert produced_path["rejected_input_kinds"] == ["generic_continuation", "template_packet"]
    assert produced_path["record_controls"]["requires_actual_operator_value"] is True
    assert produced_path["record_controls"]["creates_operator_value_record"] is False
    assert produced_path["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_value_record_path_rejects_record_creation(tmp_path: Path) -> None:
    path = _default_path()
    path["operator_value_record_created"] = True
    path["record_controls"]["creates_operator_value_record"] = True
    path_path = tmp_path / "operator-decision-value-record-path.json"
    path_path.write_text(json.dumps(path), encoding="utf-8")

    validation, produced_path = validate_live_producer_operator_decision_value_record_path(fixture_path=path_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_value_record_created" in serialized_errors
    assert "record_controls.creates_operator_value_record" in serialized_errors
    assert produced_path["operator_value_record_created"] is False
    assert produced_path["record_controls"]["creates_operator_value_record"] is False


def test_live_producer_operator_decision_value_record_path_rejects_actual_value_presence(tmp_path: Path) -> None:
    path = _default_path()
    path["actual_operator_decision_value_present"] = True
    path["collection_gate_satisfied"] = True
    path_path = tmp_path / "operator-decision-value-record-path.json"
    path_path.write_text(json.dumps(path), encoding="utf-8")

    validation, produced_path = validate_live_producer_operator_decision_value_record_path(fixture_path=path_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "actual_operator_decision_value_present" in serialized_errors
    assert "collection_gate_satisfied" in serialized_errors
    assert produced_path["actual_operator_decision_value_present"] is False
    assert produced_path["collection_gate_satisfied"] is False


def test_live_producer_operator_decision_value_record_path_rejects_live_authority(tmp_path: Path) -> None:
    path = _default_path()
    path["record_controls"]["grants_live_authority"] = True
    path["authority_denials"]["live_execution_authorized"] = True
    path_path = tmp_path / "operator-decision-value-record-path.json"
    path_path.write_text(json.dumps(path), encoding="utf-8")

    validation, produced_path = validate_live_producer_operator_decision_value_record_path(fixture_path=path_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "record_controls.grants_live_authority" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_path["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_value_record_path_rejects_mutation_route_ref(tmp_path: Path) -> None:
    path = _default_path()
    path["source_collection_gate_ref"] = "POST /api/v1/harness/live-producer/operator-decision-value-record"
    path_path = tmp_path / "operator-decision-value-record-path.json"
    path_path.write_text(json.dumps(path), encoding="utf-8")

    validation, produced_path = validate_live_producer_operator_decision_value_record_path(fixture_path=path_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_path["source_collection_gate_ref"].startswith("collection-gate://")


def test_live_producer_operator_decision_value_record_path_rejects_secret_like_value(tmp_path: Path) -> None:
    path = _default_path()
    path["next_action"] = "Collect sk-forbiddencredential"
    path_path = tmp_path / "operator-decision-value-record-path.json"
    path_path.write_text(json.dumps(path), encoding="utf-8")

    validation, produced_path = validate_live_producer_operator_decision_value_record_path(fixture_path=path_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "sk-forbiddencredential" not in serialized_errors
    assert produced_path["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_value_record_path_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["accepted_record_kind_count"] == 2
    assert payload["produced_path"]["record_path_admitted"] is False
    assert payload["produced_path"]["authority_granted"] is False
