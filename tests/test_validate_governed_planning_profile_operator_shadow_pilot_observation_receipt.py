"""Tests for GovernedPlanningProfile operator shadow-pilot observation receipt.

Purpose: verify the planning-profile operator shadow-pilot observation receipt
is explicit, deterministic, collected locally, and non-authorizing.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: governed planning profile shadow dossier reporter, evidence
request validator, observation receipt validator, and observation schema.
Invariants: local observations can be collected, runtime promotion remains
blocked, and every expected plan class retains no-effect authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_planning_profile_operator_shadow_pilot_observation_receipt as validator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_receipt() -> dict:
    return json.loads(validator.DEFAULT_RECEIPT.read_text(encoding="utf-8"))


def test_operator_shadow_pilot_observation_receipt_accepts_default_fixture() -> None:
    validation, produced_receipt = validator.validate_operator_shadow_pilot_observation_receipt()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == (
        "schemas/governed_planning_profile_operator_shadow_pilot_observation_receipt.schema.json"
    )
    assert validation.receipt_path == (
        "examples/governed_planning_profile_operator_shadow_pilot_observation_receipt.local.json"
    )
    assert validation.scenario_observation_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.remaining_promotion_gate_count == 3
    assert produced_receipt["operator_observation_status"] == "Collected"
    assert produced_receipt["operator_observation_collected"] is True
    assert produced_receipt["runtime_promotion_authorized"] is False


def test_operator_shadow_pilot_observation_schema_accepts_fixture_and_produced_receipt() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_receipt()
    _validation, produced_receipt = validator.validate_operator_shadow_pilot_observation_receipt()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_receipt)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_receipt
    assert fixture["source_evidence_request"]["evidence_id"] == produced_receipt["source_evidence_request"]["evidence_id"]
    assert len(fixture["receipt_hash"]) == 64


def test_operator_shadow_pilot_observation_binds_all_expected_plan_classes() -> None:
    receipt = _default_receipt()
    observed_classes = tuple(observation["plan_class"] for observation in receipt["scenario_observations"])
    observed_refs = tuple(observation["operator_observation_ref"] for observation in receipt["scenario_observations"])

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert all(ref.startswith("receipt://governed-planning-profile/operator-shadow-pilot/") for ref in observed_refs)
    assert all(observation["operator_observation_status"] == "Collected" for observation in receipt["scenario_observations"])
    assert all(observation["parity_confirmed"] is True for observation in receipt["scenario_observations"])
    assert all(observation["observed_behavior_matches_projection"] is True for observation in receipt["scenario_observations"])
    assert all(observation["runtime_promotion_ready"] is False for observation in receipt["scenario_observations"])


def test_operator_shadow_pilot_observation_rejects_runtime_authority(tmp_path: Path) -> None:
    receipt = _default_receipt()
    receipt["runtime_promotion_authorized"] = True
    receipt["execution_allowed"] = True
    receipt["authority_denials"]["runtime_promotion_authorized"] = True
    receipt["scenario_observations"][0]["runtime_promotion_ready"] = True
    receipt_path = tmp_path / "operator-shadow-pilot-observation-authority.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation, produced_receipt = validator.validate_operator_shadow_pilot_observation_receipt(
        receipt_path=receipt_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "scenario runtime_promotion_ready" in serialized_errors
    assert produced_receipt["runtime_promotion_authorized"] is False
    assert produced_receipt["scenario_observations"][0]["runtime_promotion_ready"] is False


def test_operator_shadow_pilot_observation_rejects_uncollected_receipt(tmp_path: Path) -> None:
    receipt = _default_receipt()
    receipt["operator_observation_collected"] = False
    receipt["operator_observation_status"] = "AwaitingEvidence"
    receipt["scenario_observations"][0]["operator_observation_status"] = "AwaitingEvidence"
    receipt_path = tmp_path / "operator-shadow-pilot-observation-uncollected.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation, produced_receipt = validator.validate_operator_shadow_pilot_observation_receipt(
        receipt_path=receipt_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_observation_collected" in serialized_errors
    assert "operator_observation_status" in serialized_errors
    assert "scenario operator_observation_status" in serialized_errors
    assert produced_receipt["operator_observation_collected"] is True
    assert produced_receipt["scenario_observations"][0]["operator_observation_status"] == "Collected"


def test_operator_shadow_pilot_observation_rejects_missing_remaining_gate(tmp_path: Path) -> None:
    receipt = _default_receipt()
    receipt["remaining_promotion_gates"] = receipt["remaining_promotion_gates"][:-1]
    receipt["observation_summary"]["remaining_promotion_gate_count"] = 2
    receipt_path = tmp_path / "operator-shadow-pilot-observation-missing-gate.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    validation, produced_receipt = validator.validate_operator_shadow_pilot_observation_receipt(
        receipt_path=receipt_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "remaining_promotion_gates" in serialized_errors
    assert "remaining promotion gate ids mismatch" in serialized_errors
    assert "remaining_promotion_gate_count mismatch" in serialized_errors
    assert len(produced_receipt["remaining_promotion_gates"]) == 3
    assert produced_receipt["remaining_promotion_gates"][-1]["gate_id"] == "terminal_closure_certificate"


def test_operator_shadow_pilot_observation_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["scenario_observation_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["remaining_promotion_gate_count"] == 3
    assert payload["produced_receipt"]["runtime_promotion_authorized"] is False
