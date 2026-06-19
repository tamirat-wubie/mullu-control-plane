"""Tests for GovernedPlanningProfile replay/recovery witness.

Purpose: verify the planning-profile replay/recovery witness is explicit,
deterministic, locally witness-bound, and non-authorizing.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: replay/recovery witness validator, runtime-promotion approval
validator, and replay/recovery witness schema.
Invariants: replay/recovery evidence can be recorded locally, runtime promotion
remains unauthorized, and terminal closure remains AwaitingEvidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_planning_profile_replay_recovery_witness as validator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_witness() -> dict:
    return json.loads(validator.DEFAULT_WITNESS.read_text(encoding="utf-8"))


def test_replay_recovery_witness_accepts_default_fixture() -> None:
    validation, produced_witness = validator.validate_replay_recovery_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == "schemas/governed_planning_profile_replay_recovery_witness.schema.json"
    assert validation.witness_path == "examples/governed_planning_profile_replay_recovery_witness.local.json"
    assert validation.replay_recovery_control_count == len(validator.REPLAY_RECOVERY_CONTROL_IDS)
    assert validation.scenario_witness_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.remaining_promotion_gate_count == 1
    assert produced_witness["replay_recovery_gate_satisfied"] is True
    assert produced_witness["runtime_promotion_authorized"] is False


def test_replay_recovery_schema_accepts_fixture_and_produced_witness() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_witness()
    _validation, produced_witness = validator.validate_replay_recovery_witness()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_witness)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_witness
    assert fixture["source_runtime_promotion_approval_packet"]["packet_id"] == produced_witness["source_runtime_promotion_approval_packet"]["packet_id"]
    assert len(fixture["witness_hash"]) == 64


def test_replay_recovery_witness_binds_source_approval_and_plan_classes() -> None:
    witness = _default_witness()
    observed_classes = tuple(item["plan_class"] for item in witness["scenario_replay_witnesses"])
    observed_refs = tuple(item["operator_observation_ref"] for item in witness["scenario_replay_witnesses"])
    replay_probe_refs = tuple(item["replay_probe_ref"] for item in witness["scenario_replay_witnesses"])

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert all(ref.startswith("receipt://governed-planning-profile/operator-shadow-pilot/") for ref in observed_refs)
    assert all(ref.startswith("hash://sha256/") for ref in replay_probe_refs)
    assert witness["source_runtime_promotion_approval_packet"]["runtime_promotion_approval_status"] == "ConditionallyApprovedNoEffect"
    assert witness["source_runtime_promotion_approval_packet"]["runtime_promotion_approval_collected"] is True
    assert witness["source_runtime_promotion_approval_packet"]["scenario_approval_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert all(item["replay_probe_status"] == "WitnessBound" for item in witness["scenario_replay_witnesses"])
    assert all(item["runtime_promotion_ready"] is False for item in witness["scenario_replay_witnesses"])


def test_replay_recovery_witness_records_controls_without_authority() -> None:
    witness = _default_witness()
    control_ids = tuple(control["control_id"] for control in witness["replay_recovery_controls"])
    control_statuses = tuple(control["status"] for control in witness["replay_recovery_controls"])
    gate_summary = witness["promotion_gate_summary"]

    assert control_ids == validator.REPLAY_RECOVERY_CONTROL_IDS
    assert all(status == "Pass" for status in control_statuses)
    assert all(control["blocks_runtime_promotion"] is False for control in witness["replay_recovery_controls"])
    assert tuple(gate_summary["satisfied_promotion_gate_ids"]) == validator.SATISFIED_PROMOTION_GATE_IDS
    assert tuple(gate_summary["remaining_promotion_gate_ids"]) == validator.REMAINING_PROMOTION_GATE_IDS
    assert gate_summary["runtime_promotion_authorized"] is False


def test_replay_recovery_witness_rejects_runtime_and_replay_authority(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["runtime_promotion_authorized"] = True
    witness["execution_allowed"] = True
    witness["replay_execution_performed"] = True
    witness["rollback_execution_performed"] = True
    witness["authority_denials"]["runtime_promotion_authorized"] = True
    witness["scenario_replay_witnesses"][0]["runtime_promotion_ready"] = True
    witness["scenario_replay_witnesses"][0]["replay_execution_performed"] = True
    witness_path = tmp_path / "replay-recovery-authority.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_replay_recovery_witness(witness_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "replay_execution_performed" in serialized_errors
    assert "rollback_execution_performed" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "scenario runtime_promotion_ready" in serialized_errors
    assert produced_witness["runtime_promotion_authorized"] is False
    assert produced_witness["replay_execution_performed"] is False


def test_replay_recovery_witness_rejects_uncollected_source_approval(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["replay_recovery_gate_satisfied"] = False
    witness["replay_recovery_witness_status"] = "AwaitingEvidence"
    witness["source_runtime_promotion_approval_packet"]["runtime_promotion_approval_status"] = "AwaitingEvidence"
    witness["source_runtime_promotion_approval_packet"]["runtime_promotion_approval_collected"] = False
    witness["source_runtime_promotion_approval_packet"]["runtime_promotion_gate_satisfied"] = False
    witness_path = tmp_path / "replay-recovery-uncollected.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_replay_recovery_witness(witness_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "replay_recovery_gate_satisfied" in serialized_errors
    assert "replay_recovery_witness_status" in serialized_errors
    assert "source approval status" in serialized_errors
    assert "source approval must be collected" in serialized_errors
    assert "source runtime promotion approval gate" in serialized_errors
    assert produced_witness["replay_recovery_gate_satisfied"] is True
    assert produced_witness["source_runtime_promotion_approval_packet"]["runtime_promotion_approval_collected"] is True


def test_replay_recovery_witness_rejects_missing_terminal_gate(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["remaining_promotion_gates"] = []
    witness["promotion_gate_summary"]["remaining_promotion_gate_ids"] = []
    witness_path = tmp_path / "replay-recovery-missing-terminal-gate.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_replay_recovery_witness(witness_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "remaining_promotion_gates" in serialized_errors
    assert "remaining promotion gate ids mismatch" in serialized_errors
    assert len(produced_witness["remaining_promotion_gates"]) == 1
    assert produced_witness["remaining_promotion_gates"][0]["gate_id"] == "terminal_closure_certificate"


def test_replay_recovery_witness_rejects_recovery_boundary_drift(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["recovery_boundary"]["rollback_plan_documented"] = False
    witness["recovery_boundary"]["recovery_handoff_documented"] = False
    witness["recovery_boundary"]["incident_handoff_required_if_drift"] = False
    witness["recovery_boundary"]["terminal_closure_required"] = False
    witness["scenario_replay_witnesses"][0]["replay_mismatch_count"] = 1
    witness["scenario_replay_witnesses"][0]["replay_probe_ref"] = "probe://raw"
    witness_path = tmp_path / "replay-recovery-boundary-drift.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_replay_recovery_witness(witness_path=witness_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "recovery_boundary.rollback_plan_documented" in serialized_errors
    assert "recovery_boundary.recovery_handoff_documented" in serialized_errors
    assert "recovery_boundary.incident_handoff_required_if_drift" in serialized_errors
    assert "recovery_boundary.terminal_closure_required" in serialized_errors
    assert "scenario replay_mismatch_count" in serialized_errors
    assert "scenario replay_probe_ref" in serialized_errors
    assert produced_witness["recovery_boundary"]["terminal_closure_required"] is True


def test_replay_recovery_witness_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["replay_recovery_control_count"] == len(validator.REPLAY_RECOVERY_CONTROL_IDS)
    assert payload["scenario_witness_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["remaining_promotion_gate_count"] == 1
    assert payload["produced_witness"]["runtime_promotion_authorized"] is False
