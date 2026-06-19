"""Tests for GovernedPlanningProfile runtime promotion approval packet.

Purpose: verify the planning-profile runtime promotion approval packet is
explicit, deterministic, locally approval-bound, and non-authorizing.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: runtime promotion approval validator, observation receipt
validator, and runtime promotion approval schema.
Invariants: approval evidence can be recorded locally, runtime promotion
remains unauthorized, and replay/recovery plus terminal closure gates remain
AwaitingEvidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_planning_profile_runtime_promotion_approval_packet as validator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_packet() -> dict:
    return json.loads(validator.DEFAULT_PACKET.read_text(encoding="utf-8"))


def test_runtime_promotion_approval_packet_accepts_default_fixture() -> None:
    validation, produced_packet = validator.validate_runtime_promotion_approval_packet()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == "schemas/governed_planning_profile_runtime_promotion_approval_packet.schema.json"
    assert validation.packet_path == "examples/governed_planning_profile_runtime_promotion_approval_packet.local.json"
    assert validation.approval_criterion_count == len(validator.APPROVAL_CRITERION_IDS)
    assert validation.scenario_approval_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.remaining_promotion_gate_count == 2
    assert produced_packet["runtime_promotion_approval_collected"] is True
    assert produced_packet["runtime_promotion_authorized"] is False


def test_runtime_promotion_approval_schema_accepts_fixture_and_produced_packet() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_packet()
    _validation, produced_packet = validator.validate_runtime_promotion_approval_packet()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_packet)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_packet
    assert fixture["source_observation_receipt"]["receipt_id"] == produced_packet["source_observation_receipt"]["receipt_id"]
    assert len(fixture["packet_hash"]) == 64


def test_runtime_promotion_approval_binds_source_observation_and_plan_classes() -> None:
    packet = _default_packet()
    observed_classes = tuple(approval["plan_class"] for approval in packet["scenario_approvals"])
    observed_refs = tuple(approval["operator_observation_ref"] for approval in packet["scenario_approvals"])

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert all(ref.startswith("receipt://governed-planning-profile/operator-shadow-pilot/") for ref in observed_refs)
    assert packet["source_observation_receipt"]["operator_observation_status"] == "Collected"
    assert packet["source_observation_receipt"]["operator_observation_collected"] is True
    assert packet["source_observation_receipt"]["scenario_observation_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert all(approval["approval_status"] == "ConditionallyApprovedNoEffect" for approval in packet["scenario_approvals"])
    assert all(approval["runtime_promotion_ready"] is False for approval in packet["scenario_approvals"])


def test_runtime_promotion_approval_records_passed_criteria_without_authority() -> None:
    packet = _default_packet()
    criterion_ids = tuple(criterion["criterion_id"] for criterion in packet["approval_criteria"])
    criterion_statuses = tuple(criterion["status"] for criterion in packet["approval_criteria"])
    gate_summary = packet["promotion_gate_summary"]

    assert criterion_ids == validator.APPROVAL_CRITERION_IDS
    assert all(status == "Pass" for status in criterion_statuses)
    assert all(criterion["blocks_runtime_promotion"] is False for criterion in packet["approval_criteria"])
    assert tuple(gate_summary["satisfied_promotion_gate_ids"]) == validator.SATISFIED_PROMOTION_GATE_IDS
    assert tuple(gate_summary["remaining_promotion_gate_ids"]) == validator.REMAINING_PROMOTION_GATE_IDS
    assert gate_summary["runtime_promotion_authorized"] is False


def test_runtime_promotion_approval_rejects_runtime_authority(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["runtime_promotion_authorized"] = True
    packet["execution_allowed"] = True
    packet["authority_denials"]["runtime_promotion_authorized"] = True
    packet["scenario_approvals"][0]["runtime_promotion_ready"] = True
    packet_path = tmp_path / "runtime-promotion-approval-authority.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, produced_packet = validator.validate_runtime_promotion_approval_packet(packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "scenario runtime_promotion_ready" in serialized_errors
    assert produced_packet["runtime_promotion_authorized"] is False
    assert produced_packet["scenario_approvals"][0]["runtime_promotion_ready"] is False


def test_runtime_promotion_approval_rejects_uncollected_source_receipt(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["runtime_promotion_approval_collected"] = False
    packet["runtime_promotion_approval_status"] = "AwaitingEvidence"
    packet["source_observation_receipt"]["operator_observation_status"] = "AwaitingEvidence"
    packet["source_observation_receipt"]["operator_observation_collected"] = False
    packet_path = tmp_path / "runtime-promotion-approval-uncollected.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, produced_packet = validator.validate_runtime_promotion_approval_packet(packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_approval_collected" in serialized_errors
    assert "runtime_promotion_approval_status" in serialized_errors
    assert "source observation receipt status" in serialized_errors
    assert "source observation receipt must be collected" in serialized_errors
    assert produced_packet["runtime_promotion_approval_collected"] is True
    assert produced_packet["source_observation_receipt"]["operator_observation_collected"] is True


def test_runtime_promotion_approval_rejects_missing_remaining_gate(tmp_path: Path) -> None:
    packet = _default_packet()
    packet["remaining_promotion_gates"] = packet["remaining_promotion_gates"][:-1]
    packet["promotion_gate_summary"]["remaining_promotion_gate_ids"] = ["replay_recovery_witness"]
    packet_path = tmp_path / "runtime-promotion-approval-missing-gate.json"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")

    validation, produced_packet = validator.validate_runtime_promotion_approval_packet(packet_path=packet_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "remaining_promotion_gates" in serialized_errors
    assert "remaining promotion gate ids mismatch" in serialized_errors
    assert len(produced_packet["remaining_promotion_gates"]) == 2
    assert produced_packet["remaining_promotion_gates"][-1]["gate_id"] == "terminal_closure_certificate"


def test_runtime_promotion_approval_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["approval_criterion_count"] == len(validator.APPROVAL_CRITERION_IDS)
    assert payload["scenario_approval_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["remaining_promotion_gate_count"] == 2
    assert payload["produced_packet"]["runtime_promotion_authorized"] is False
