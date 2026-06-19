"""Tests for GovernedPlanningProfile terminal closure certificate.

Purpose: verify the planning-profile terminal closure certificate is explicit,
deterministic, locally evidence-bound, and non-authorizing.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: terminal closure certificate validator, replay/recovery witness
validator, and terminal closure certificate schema.
Invariants: terminal closure certificate evidence can be recorded locally,
runtime promotion remains unauthorized, and activation remains a separate
authority-changing action.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_planning_profile_terminal_closure_certificate as validator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_certificate() -> dict:
    return json.loads(validator.DEFAULT_CERTIFICATE.read_text(encoding="utf-8"))


def test_terminal_closure_certificate_accepts_default_fixture() -> None:
    validation, produced_certificate = validator.validate_terminal_closure_certificate()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == "schemas/governed_planning_profile_terminal_closure_certificate.schema.json"
    assert validation.certificate_path == "examples/governed_planning_profile_terminal_closure_certificate.local.json"
    assert validation.terminal_closure_control_count == len(validator.TERMINAL_CLOSURE_CONTROL_IDS)
    assert validation.scenario_closure_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.remaining_promotion_gate_count == 0
    assert produced_certificate["terminal_closure_gate_satisfied"] is True
    assert produced_certificate["runtime_promotion_authorized"] is False


def test_terminal_closure_schema_accepts_fixture_and_produced_certificate() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_certificate()
    _validation, produced_certificate = validator.validate_terminal_closure_certificate()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_certificate)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_certificate
    assert fixture["source_replay_recovery_witness"]["witness_id"] == produced_certificate["source_replay_recovery_witness"]["witness_id"]
    assert len(fixture["certificate_hash"]) == 64


def test_terminal_closure_certificate_binds_source_witness_and_plan_classes() -> None:
    certificate = _default_certificate()
    observed_classes = tuple(item["plan_class"] for item in certificate["scenario_terminal_closures"])
    replay_refs = tuple(item["source_replay_probe_ref"] for item in certificate["scenario_terminal_closures"])
    recovery_refs = tuple(item["source_recovery_path_ref"] for item in certificate["scenario_terminal_closures"])

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert all(ref.startswith("hash://sha256/") for ref in replay_refs)
    assert all(ref.startswith("recovery://governed-planning-profile/") for ref in recovery_refs)
    assert certificate["source_replay_recovery_witness"]["replay_recovery_witness_status"] == "CollectedNoEffect"
    assert certificate["source_replay_recovery_witness"]["replay_recovery_gate_satisfied"] is True
    assert certificate["source_replay_recovery_witness"]["scenario_witness_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert certificate["source_replay_recovery_witness"]["remaining_promotion_gate_count"] == 1
    assert all(item["terminal_closure_status"] == "ClosedNoEffect" for item in certificate["scenario_terminal_closures"])


def test_terminal_closure_certificate_records_all_gates_without_authority() -> None:
    certificate = _default_certificate()
    control_ids = tuple(control["control_id"] for control in certificate["terminal_closure_controls"])
    gate_summary = certificate["promotion_gate_summary"]

    assert control_ids == validator.TERMINAL_CLOSURE_CONTROL_IDS
    assert all(control["status"] == "Pass" for control in certificate["terminal_closure_controls"])
    assert all(control["blocks_runtime_promotion_evidence"] is False for control in certificate["terminal_closure_controls"])
    assert tuple(gate_summary["satisfied_promotion_gate_ids"]) == validator.SATISFIED_PROMOTION_GATE_IDS
    assert gate_summary["remaining_promotion_gate_ids"] == []
    assert certificate["remaining_promotion_gates"] == []
    assert gate_summary["all_promotion_evidence_satisfied"] is True
    assert gate_summary["runtime_promotion_authorized"] is False


def test_terminal_closure_certificate_rejects_runtime_authority(tmp_path: Path) -> None:
    certificate = _default_certificate()
    certificate["runtime_promotion_authorized"] = True
    certificate["execution_allowed"] = True
    certificate["dispatch_allowed"] = True
    certificate["terminal_closure"] = True
    certificate["authority_denials"]["runtime_promotion_authorized"] = True
    certificate["scenario_terminal_closures"][0]["runtime_promotion_authorized"] = True
    certificate["scenario_terminal_closures"][0]["runtime_execution_performed"] = True
    certificate_path = tmp_path / "terminal-closure-authority.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation, produced_certificate = validator.validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "dispatch_allowed" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "runtime_execution_performed" in serialized_errors
    assert produced_certificate["runtime_promotion_authorized"] is False
    assert produced_certificate["terminal_closure"] is False


def test_terminal_closure_certificate_rejects_unsatisfied_source_witness(tmp_path: Path) -> None:
    certificate = _default_certificate()
    certificate["terminal_closure_certificate_status"] = "AwaitingEvidence"
    certificate["terminal_closure_gate_satisfied"] = False
    certificate["all_promotion_evidence_satisfied"] = False
    certificate["source_replay_recovery_witness"]["replay_recovery_witness_status"] = "AwaitingEvidence"
    certificate["source_replay_recovery_witness"]["replay_recovery_gate_satisfied"] = False
    certificate_path = tmp_path / "terminal-closure-unsatisfied-source.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation, produced_certificate = validator.validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "terminal_closure_certificate_status" in serialized_errors
    assert "terminal_closure_gate_satisfied" in serialized_errors
    assert "all_promotion_evidence_satisfied" in serialized_errors
    assert "source replay/recovery witness status" in serialized_errors
    assert "source replay/recovery gate" in serialized_errors
    assert produced_certificate["terminal_closure_gate_satisfied"] is True
    assert produced_certificate["all_promotion_evidence_satisfied"] is True


def test_terminal_closure_certificate_rejects_remaining_gate_drift(tmp_path: Path) -> None:
    certificate = _default_certificate()
    certificate["remaining_promotion_gates"] = [
        {
            "gate_id": "terminal_closure_certificate",
            "status": "AwaitingEvidence",
            "blocks_runtime_promotion": True,
        }
    ]
    certificate["promotion_gate_summary"]["remaining_promotion_gate_ids"] = ["terminal_closure_certificate"]
    certificate_path = tmp_path / "terminal-closure-remaining-gate.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation, produced_certificate = validator.validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "remaining_promotion_gates" in serialized_errors
    assert "remaining promotion gate ids must be empty" in serialized_errors
    assert produced_certificate["remaining_promotion_gates"] == []
    assert produced_certificate["promotion_gate_summary"]["remaining_promotion_gate_ids"] == []


def test_terminal_closure_certificate_rejects_boundary_drift(tmp_path: Path) -> None:
    certificate = _default_certificate()
    certificate["certificate_boundary"]["source_replay_recovery_witness_bound"] = False
    certificate["certificate_boundary"]["all_prior_gates_satisfied"] = False
    certificate["certificate_boundary"]["terminal_certificate_collected"] = False
    certificate["certificate_boundary"]["runtime_promotion_authorization_required"] = False
    certificate["certificate_boundary"]["runtime_promotion_authorization_performed"] = True
    certificate["certificate_boundary"]["terminal_closure_authority_granted"] = True
    certificate["scenario_terminal_closures"][0]["replay_mismatch_count"] = 1
    certificate["scenario_terminal_closures"][0]["source_replay_probe_ref"] = "probe://raw"
    certificate_path = tmp_path / "terminal-closure-boundary-drift.json"
    certificate_path.write_text(json.dumps(certificate), encoding="utf-8")

    validation, produced_certificate = validator.validate_terminal_closure_certificate(certificate_path=certificate_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "certificate_boundary.source_replay_recovery_witness_bound" in serialized_errors
    assert "certificate_boundary.all_prior_gates_satisfied" in serialized_errors
    assert "certificate_boundary.terminal_certificate_collected" in serialized_errors
    assert "certificate_boundary.runtime_promotion_authorization_required" in serialized_errors
    assert "certificate_boundary.runtime_promotion_authorization_performed" in serialized_errors
    assert "certificate_boundary.terminal_closure_authority_granted" in serialized_errors
    assert "scenario replay_mismatch_count" in serialized_errors
    assert "scenario source_replay_probe_ref" in serialized_errors
    assert produced_certificate["certificate_boundary"]["terminal_certificate_collected"] is True


def test_terminal_closure_certificate_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["terminal_closure_control_count"] == len(validator.TERMINAL_CLOSURE_CONTROL_IDS)
    assert payload["scenario_closure_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["remaining_promotion_gate_count"] == 0
    assert payload["produced_certificate"]["all_promotion_evidence_satisfied"] is True
    assert payload["produced_certificate"]["runtime_promotion_authorized"] is False
