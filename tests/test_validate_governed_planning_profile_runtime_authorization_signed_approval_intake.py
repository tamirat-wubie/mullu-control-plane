"""Tests for GovernedPlanningProfile signed approval intake.

Purpose: verify the signed approval intake contract defines future approval
values without collecting approval, verifying a signature, or granting runtime
authority.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: signed approval intake validator, approval template validator,
and schema validation.
Invariants: the intake contract never authorizes runtime promotion, activation,
execution, dispatch, replanning, success, or terminal closure authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_governed_planning_profile_runtime_authorization_signed_approval_intake
    as validator,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_intake() -> dict:
    return json.loads(validator.DEFAULT_INTAKE.read_text(encoding="utf-8"))


def test_signed_approval_intake_accepts_default_fixture() -> None:
    validation, produced_intake = validator.validate_signed_approval_intake()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == (
        "schemas/governed_planning_profile_runtime_authorization_signed_approval_intake.schema.json"
    )
    assert validation.intake_path == (
        "examples/governed_planning_profile_runtime_authorization_signed_approval_intake.local.json"
    )
    assert validation.intake_control_count == len(validator.INTAKE_CONTROL_IDS)
    assert validation.required_witness_field_count == len(validator.WITNESS_FIELD_IDS)
    assert validation.scenario_intake_requirement_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.signed_approval_present is False
    assert validation.runtime_authorization_gate_satisfied is False
    assert produced_intake["intake_accepted_as_approval"] is False


def test_signed_approval_intake_schema_accepts_fixture_and_produced_intake() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_intake()
    _validation, produced_intake = validator.validate_signed_approval_intake()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_intake)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_intake
    assert len(fixture["intake_hash"]) == 64
    assert fixture["runtime_authorization_response_kind"] == validator.APPROVAL_RESPONSE_KIND


def test_signed_approval_intake_binds_template_sources_and_plan_classes() -> None:
    intake = _default_intake()
    observed_classes = tuple(item["plan_class"] for item in intake["scenario_intake_requirements"])
    template = intake["source_approval_witness_template"]
    source_request = intake["source_runtime_authorization_request"]
    source_rejection = intake["source_generic_continuation_rejection"]

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert template["template_status"] == "TemplateNoEffect"
    assert template["approval_witness_collected"] is False
    assert source_request["runtime_authorization_request_status"] == "SubmittedNoEffect"
    assert source_request["operator_response_collected"] is False
    assert source_rejection["runtime_authorization_response_status"] == "RejectedNoEffect"
    assert source_rejection["generic_continuation_rejected"] is True
    assert source_rejection["signed_approval_present"] is False


def test_signed_approval_intake_records_missing_required_witness_values() -> None:
    intake = _default_intake()
    field_ids = tuple(field["field_id"] for field in intake["required_witness_fields"])
    controls = {control["control_id"]: control["status"] for control in intake["intake_controls"]}
    boundary = intake["operator_signature_boundary"]

    assert field_ids == validator.WITNESS_FIELD_IDS
    assert controls["explicit_decision_value_absent"] == "AwaitingEvidence"
    assert controls["operator_identity_absent"] == "AwaitingEvidence"
    assert controls["source_hash_acknowledgements_absent"] == "AwaitingEvidence"
    assert controls["signature_absent"] == "AwaitingEvidence"
    assert all(field["required"] is True for field in intake["required_witness_fields"])
    assert all(field["value_present"] is False for field in intake["required_witness_fields"])
    assert all(field["verified"] is False for field in intake["required_witness_fields"])
    assert boundary["signature_ref_required"] is True
    assert boundary["signature_verified"] is False


def test_signed_approval_intake_rejects_runtime_authority(tmp_path: Path) -> None:
    intake = _default_intake()
    intake["runtime_promotion_authorized"] = True
    intake["execution_allowed"] = True
    intake["dispatch_allowed"] = True
    intake["terminal_closure"] = True
    intake["authority_denials"]["runtime_promotion_authorized"] = True
    intake["scenario_intake_requirements"][0]["runtime_promotion_authorized"] = True
    intake["scenario_intake_requirements"][0]["runtime_execution_performed"] = True
    intake_path = tmp_path / "signed-approval-intake-authority.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")

    validation, produced_intake = validator.validate_signed_approval_intake(intake_path=intake_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "dispatch_allowed" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "runtime_execution_performed" in serialized_errors
    assert produced_intake["runtime_promotion_authorized"] is False
    assert produced_intake["terminal_closure"] is False


def test_signed_approval_intake_rejects_approval_collection_drift(tmp_path: Path) -> None:
    intake = _default_intake()
    intake["intake_accepted_as_approval"] = True
    intake["signed_approval_witness_collected"] = True
    intake["operator_response_recorded"] = True
    intake["operator_approval_collected"] = True
    intake["signed_approval_present"] = True
    intake["decision_value_present"] = True
    intake["decision_value_accepted"] = True
    intake["runtime_authorization_gate_satisfied"] = True
    intake["runtime_activation_allowed"] = True
    intake_path = tmp_path / "signed-approval-intake-approval-drift.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")

    validation, produced_intake = validator.validate_signed_approval_intake(intake_path=intake_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "intake_accepted_as_approval" in serialized_errors
    assert "signed_approval_witness_collected" in serialized_errors
    assert "operator_response_recorded" in serialized_errors
    assert "operator_approval_collected" in serialized_errors
    assert "signed_approval_present" in serialized_errors
    assert "decision_value_accepted" in serialized_errors
    assert "runtime_authorization_gate_satisfied" in serialized_errors
    assert "runtime_activation_allowed" in serialized_errors
    assert produced_intake["signed_approval_present"] is False


def test_signed_approval_intake_rejects_signature_and_field_drift(tmp_path: Path) -> None:
    intake = _default_intake()
    intake["signature_present"] = True
    intake["signature_verified"] = True
    intake["required_witness_fields"][0]["value_present"] = True
    intake["required_witness_fields"][0]["verified"] = True
    intake["required_witness_fields"][1]["accepted_from_generic_continuation"] = True
    intake["operator_signature_boundary"]["signature_ref_present"] = True
    intake["operator_signature_boundary"]["signature_verified"] = True
    intake_path = tmp_path / "signed-approval-intake-signature-drift.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")

    validation, produced_intake = validator.validate_signed_approval_intake(intake_path=intake_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "signature_present" in serialized_errors
    assert "signature_verified" in serialized_errors
    assert "value_present" in serialized_errors
    assert "verified" in serialized_errors
    assert "accepted_from_generic_continuation" in serialized_errors
    assert "operator_signature_boundary.signature_ref_present" in serialized_errors
    assert produced_intake["signature_verified"] is False


def test_signed_approval_intake_rejects_source_template_drift(tmp_path: Path) -> None:
    intake = _default_intake()
    intake["source_approval_witness_template"]["template_accepted_as_approval"] = True
    intake["source_approval_witness_template"]["approval_witness_collected"] = True
    intake["source_approval_witness_template"]["signed_approval_present"] = True
    intake["source_approval_witness_template"]["runtime_authorization_gate_satisfied"] = True
    intake["source_generic_continuation_rejection"]["generic_continuation_rejected"] = False
    intake_path = tmp_path / "signed-approval-intake-source-drift.json"
    intake_path.write_text(json.dumps(intake), encoding="utf-8")

    validation, produced_intake = validator.validate_signed_approval_intake(intake_path=intake_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_approval_witness_template.template_accepted_as_approval" in serialized_errors
    assert "source_approval_witness_template.approval_witness_collected" in serialized_errors
    assert "source_approval_witness_template.signed_approval_present" in serialized_errors
    assert "source_approval_witness_template.runtime_authorization_gate_satisfied" in serialized_errors
    assert "source_generic_continuation_rejection.generic_continuation_rejected" in serialized_errors
    assert produced_intake["source_approval_witness_template"]["signed_approval_present"] is False


def test_signed_approval_intake_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["intake_control_count"] == len(validator.INTAKE_CONTROL_IDS)
    assert payload["required_witness_field_count"] == len(validator.WITNESS_FIELD_IDS)
    assert payload["scenario_intake_requirement_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["signed_approval_present"] is False
    assert payload["runtime_authorization_gate_satisfied"] is False
    assert payload["produced_intake"]["signed_approval_witness_collected"] is False
    assert payload["produced_intake"]["runtime_promotion_authorized"] is False
