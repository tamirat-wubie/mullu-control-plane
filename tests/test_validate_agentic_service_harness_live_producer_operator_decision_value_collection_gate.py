"""Tests for Agentic Service Harness operator decision value collection gate.

Purpose: prove collection remains blocked until an actual explicit operator
decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_collection_gate
and scripts.validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.
Invariants:
  - The default collection gate validates.
  - Collection route admission and value capture fail closed.
  - Mutation route, credential, and authority drift fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gateway.agentic_service_harness_live_producer_operator_decision_value_collection_gate import (  # noqa: E402
    OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID,
    project_value_template_to_collection_gate,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS  # noqa: E402
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate import (  # noqa: E402
    DEFAULT_FIXTURE,
    main,
    validate_live_producer_operator_decision_value_collection_gate,
)
from scripts.validate_agentic_service_harness_live_producer_operator_decision_value_template import (  # noqa: E402
    validate_live_producer_operator_decision_value_template,
)


def _default_gate() -> dict:
    return json.loads(DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_live_producer_operator_decision_value_collection_gate_accepts_default_fixture() -> None:
    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.collection_gate_id == OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID
    assert validation.gate_status == "blocked_awaiting_explicit_operator_value"
    assert validation.accepted_input_kind_count == 2
    assert validation.rejected_input_kind_count == 2
    assert validation.authority_denial_count == len(FALSE_AUTHORITY_FLAGS) + 1
    assert produced_gate["collection_route_admitted"] is False
    assert produced_gate["operator_value_collected"] is False
    assert produced_gate["authority_granted"] is False


def test_live_producer_operator_decision_value_collection_gate_projects_template() -> None:
    template_validation, template_packet = validate_live_producer_operator_decision_value_template()
    produced_gate = project_value_template_to_collection_gate(template_packet)

    assert template_validation.ok is True
    assert produced_gate["collection_gate_id"] == OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID
    assert produced_gate["accepted_input_kinds"] == ["explicit_operator_approval", "explicit_operator_rejection"]
    assert produced_gate["rejected_input_kinds"] == ["generic_continuation", "template_packet"]
    assert produced_gate["gate_controls"]["requires_actual_operator_value"] is True
    assert produced_gate["gate_controls"]["admits_mutation_route"] is False
    assert produced_gate["effect_boundary"]["network_policy"] == "none"


def test_live_producer_operator_decision_value_collection_gate_rejects_collection_route(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["collection_route_admitted"] = True
    gate["gate_controls"]["admits_mutation_route"] = True
    gate_path = tmp_path / "operator-decision-value-collection-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "collection_route_admitted" in serialized_errors
    assert "gate_controls.admits_mutation_route" in serialized_errors
    assert produced_gate["collection_route_admitted"] is False
    assert produced_gate["gate_controls"]["admits_mutation_route"] is False


def test_live_producer_operator_decision_value_collection_gate_rejects_collected_value(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["operator_value_collected"] = True
    gate["explicit_operator_value_present"] = True
    gate_path = tmp_path / "operator-decision-value-collection-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_value_collected" in serialized_errors
    assert "explicit_operator_value_present" in serialized_errors
    assert produced_gate["operator_value_collected"] is False
    assert produced_gate["explicit_operator_value_present"] is False


def test_live_producer_operator_decision_value_collection_gate_rejects_live_authority(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["gate_controls"]["grants_live_authority"] = True
    gate["authority_denials"]["live_execution_authorized"] = True
    gate_path = tmp_path / "operator-decision-value-collection-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "gate_controls.grants_live_authority" in serialized_errors
    assert "live execution authority" in serialized_errors
    assert produced_gate["authority_denials"]["live_execution_authorized"] is False


def test_live_producer_operator_decision_value_collection_gate_rejects_mutation_route_ref(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["source_template_ref"] = "POST /api/v1/harness/live-producer/operator-decision-value"
    gate_path = tmp_path / "operator-decision-value-collection-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "mutation route string" in serialized_errors
    assert produced_gate["source_template_ref"].startswith("value-template://")


def test_live_producer_operator_decision_value_collection_gate_rejects_secret_like_value(tmp_path: Path) -> None:
    gate = _default_gate()
    gate["next_action"] = "Provide xoxb-forbiddencredential"
    gate_path = tmp_path / "operator-decision-value-collection-gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")

    validation, produced_gate = validate_live_producer_operator_decision_value_collection_gate(fixture_path=gate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "credential-like value" in serialized_errors
    assert "xoxb-forbiddencredential" not in serialized_errors
    assert produced_gate["effect_boundary"]["secret_mutation_enabled"] is False


def test_live_producer_operator_decision_value_collection_gate_cli_json_reports_valid(capsys) -> None:
    exit_code = main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["accepted_input_kind_count"] == 2
    assert payload["produced_gate"]["collection_route_admitted"] is False
    assert payload["produced_gate"]["authority_granted"] is False
