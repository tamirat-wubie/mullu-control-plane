"""Tests for GovernedPlanningProfile operator shadow-pilot evidence.

Purpose: verify the planning-profile operator shadow-pilot evidence request is
explicit, deterministic, uncollected, and non-authorizing.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: governed planning profile shadow dossier reporter, evidence
validator, and evidence schema.
Invariants: evidence remains AwaitingEvidence, no runtime promotion authority
is granted, and every expected plan class has a blocked observation placeholder.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_planning_profile_operator_shadow_pilot_evidence as validator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_packet() -> dict:
    return json.loads(validator.DEFAULT_FIXTURE.read_text(encoding="utf-8"))


def test_operator_shadow_pilot_evidence_accepts_default_fixture() -> None:
    validation, produced_request = validator.validate_operator_shadow_pilot_evidence()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == "schemas/governed_planning_profile_operator_shadow_pilot_evidence.schema.json"
    assert validation.fixture_path == "examples/governed_planning_profile_operator_shadow_pilot_evidence.awaiting_evidence.json"
    assert validation.scenario_observation_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.promotion_gate_count == 4
    assert produced_request["operator_evidence_status"] == "AwaitingEvidence"
    assert produced_request["operator_observation_collected"] is False
    assert produced_request["runtime_promotion_authorized"] is False


def test_operator_shadow_pilot_evidence_schema_accepts_fixture_and_produced_packet() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_packet()
    _validation, produced_request = validator.validate_operator_shadow_pilot_evidence()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_request)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_request
    assert fixture["source_dossier"]["dossier_hash"] == produced_request["source_dossier"]["dossier_hash"]
    assert len(fixture["evidence_hash"]) == 64


def test_operator_shadow_pilot_evidence_binds_all_expected_plan_classes() -> None:
    packet = _default_packet()
    observed_classes = tuple(observation["plan_class"] for observation in packet["scenario_observations"])
    observed_refs = tuple(observation["operator_observation_ref"] for observation in packet["scenario_observations"])

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert all(ref.startswith("unknown://governed-planning-profile/operator-shadow-pilot/") for ref in observed_refs)
    assert all(observation["operator_observation_status"] == "AwaitingEvidence" for observation in packet["scenario_observations"])
    assert all(observation["parity_confirmed"] is False for observation in packet["scenario_observations"])
    assert all(observation["runtime_promotion_ready"] is False for observation in packet["scenario_observations"])


def test_operator_shadow_pilot_evidence_rejects_collected_observation(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["operator_observation_collected"] = True
    packet["operator_evidence_status"] = "Collected"
    packet["scenario_observations"][0]["operator_observation_status"] = "Collected"
    packet_path = tmp_path / "operator-shadow-pilot-evidence.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, produced_request = validator.validate_operator_shadow_pilot_evidence(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_observation_collected" in serialized_errors
    assert "operator_evidence_status" in serialized_errors
    assert "scenario operator_observation_status" in serialized_errors
    assert produced_request["operator_observation_collected"] is False
    assert produced_request["scenario_observations"][0]["operator_observation_status"] == "AwaitingEvidence"


def test_operator_shadow_pilot_evidence_rejects_runtime_authority(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["runtime_promotion_authorized"] = True
    packet["execution_allowed"] = True
    packet["authority_denials"]["runtime_promotion_authorized"] = True
    packet["promotion_gates"][0]["blocks_runtime_promotion"] = False
    packet_path = tmp_path / "operator-shadow-pilot-authority.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, produced_request = validator.validate_operator_shadow_pilot_evidence(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "promotion gate must block runtime promotion" in serialized_errors
    assert produced_request["runtime_promotion_authorized"] is False
    assert produced_request["authority_denials"]["runtime_promotion_authorized"] is False


def test_operator_shadow_pilot_evidence_rejects_missing_plan_class(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["scenario_observations"] = packet["scenario_observations"][:-1]
    packet_path = tmp_path / "operator-shadow-pilot-missing-class.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, produced_request = validator.validate_operator_shadow_pilot_evidence(fixture_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "scenario_observations" in serialized_errors
    assert "must cover all expected plan classes" in serialized_errors
    assert len(produced_request["scenario_observations"]) == len(validator.EXPECTED_PLAN_CLASSES)
    assert produced_request["scenario_observations"][-1]["plan_class"] == "world_contradiction_search"


def test_operator_shadow_pilot_evidence_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["scenario_observation_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["promotion_gate_count"] == 4
    assert payload["produced_request"]["runtime_promotion_authorized"] is False
