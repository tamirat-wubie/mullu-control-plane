"""Tests for GovernedPlanningProfile runtime authorization approval template.

Purpose: verify the approval witness template defines future signed approval
requirements without collecting approval or granting runtime authority.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: approval witness template validator, source authorization request
validator, source generic continuation rejection validator, and schema
validation.
Invariants: the template never authorizes runtime promotion, activation,
execution, dispatch, replanning, success, or terminal closure authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_governed_planning_profile_runtime_authorization_approval_witness_template
    as validator,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_template() -> dict:
    return json.loads(validator.DEFAULT_TEMPLATE.read_text(encoding="utf-8"))


def test_approval_witness_template_accepts_default_fixture() -> None:
    validation, produced_template = validator.validate_approval_witness_template()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == (
        "schemas/governed_planning_profile_runtime_authorization_approval_witness_template.schema.json"
    )
    assert validation.template_path == (
        "examples/governed_planning_profile_runtime_authorization_approval_witness_template.local.json"
    )
    assert validation.approval_template_control_count == len(validator.APPROVAL_TEMPLATE_CONTROL_IDS)
    assert validation.required_approval_field_count == len(validator.APPROVAL_FIELD_IDS)
    assert validation.scenario_approval_requirement_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.runtime_authorization_gate_satisfied is False
    assert produced_template["template_accepted_as_approval"] is False
    assert produced_template["runtime_promotion_authorized"] is False


def test_approval_witness_template_schema_accepts_fixture_and_produced_template() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_template()
    _validation, produced_template = validator.validate_approval_witness_template()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_template)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_template
    assert len(fixture["template_hash"]) == 64
    assert fixture["runtime_authorization_response_kind"] == validator.APPROVAL_RESPONSE_KIND


def test_approval_witness_template_binds_sources_and_plan_classes() -> None:
    template = _default_template()
    observed_classes = tuple(item["plan_class"] for item in template["scenario_approval_requirements"])
    source_request = template["source_runtime_authorization_request"]
    source_rejection = template["source_generic_continuation_rejection"]

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert source_request["runtime_authorization_request_status"] == "SubmittedNoEffect"
    assert source_request["operator_response_required"] is True
    assert source_request["operator_response_collected"] is False
    assert source_rejection["runtime_authorization_response_status"] == "RejectedNoEffect"
    assert source_rejection["generic_continuation_rejected"] is True
    assert source_rejection["signed_approval_present"] is False
    assert template["promotion_gate_summary"]["remaining_promotion_gate_ids"] == [
        "explicit_signed_runtime_authorization_approval_witness",
        "separate_runtime_activation_gate",
    ]


def test_approval_witness_template_records_required_fields_without_collection() -> None:
    template = _default_template()
    field_ids = tuple(field["field_id"] for field in template["required_approval_fields"])
    controls = {control["control_id"]: control["status"] for control in template["approval_template_controls"]}
    boundary = template["operator_approval_boundary"]

    assert field_ids == validator.APPROVAL_FIELD_IDS
    assert controls["explicit_signed_approval_required"] == "AwaitingEvidence"
    assert all(field["required"] is True for field in template["required_approval_fields"])
    assert all(field["collected"] is False for field in template["required_approval_fields"])
    assert all(
        field["accepted_from_generic_continuation"] is False
        for field in template["required_approval_fields"]
    )
    assert boundary["template_only"] is True
    assert boundary["approval_witness_collected"] is False
    assert boundary["runtime_activation_requires_separate_gate"] is True


def test_approval_witness_template_rejects_runtime_authority(tmp_path: Path) -> None:
    template = _default_template()
    template["runtime_promotion_authorized"] = True
    template["execution_allowed"] = True
    template["dispatch_allowed"] = True
    template["terminal_closure"] = True
    template["authority_denials"]["runtime_promotion_authorized"] = True
    template["scenario_approval_requirements"][0]["runtime_promotion_authorized"] = True
    template["scenario_approval_requirements"][0]["runtime_execution_performed"] = True
    template_path = tmp_path / "approval-template-authority.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validator.validate_approval_witness_template(
        template_path=template_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "dispatch_allowed" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "runtime_execution_performed" in serialized_errors
    assert produced_template["runtime_promotion_authorized"] is False
    assert produced_template["terminal_closure"] is False


def test_approval_witness_template_rejects_approval_collection_drift(tmp_path: Path) -> None:
    template = _default_template()
    template["template_accepted_as_approval"] = True
    template["approval_witness_collected"] = True
    template["operator_response_recorded"] = True
    template["operator_approval_collected"] = True
    template["signed_approval_present"] = True
    template["runtime_authorization_gate_satisfied"] = True
    template["runtime_activation_allowed"] = True
    template["required_approval_fields"][0]["collected"] = True
    template_path = tmp_path / "approval-template-collection-drift.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validator.validate_approval_witness_template(
        template_path=template_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "template_accepted_as_approval" in serialized_errors
    assert "approval_witness_collected" in serialized_errors
    assert "operator_response_recorded" in serialized_errors
    assert "operator_approval_collected" in serialized_errors
    assert "signed_approval_present" in serialized_errors
    assert "runtime_authorization_gate_satisfied" in serialized_errors
    assert "runtime_activation_allowed" in serialized_errors
    assert "collected must be false" in serialized_errors
    assert produced_template["signed_approval_present"] is False


def test_approval_witness_template_rejects_generic_continuation_acceptance(tmp_path: Path) -> None:
    template = _default_template()
    template["required_approval_fields"][1]["accepted_from_generic_continuation"] = True
    template["operator_approval_boundary"]["generic_continuation_satisfies_authorization"] = True
    template["source_generic_continuation_rejection"]["generic_continuation_rejected"] = False
    template_path = tmp_path / "approval-template-generic-continuation-drift.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validator.validate_approval_witness_template(
        template_path=template_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "accepted_from_generic_continuation must be false" in serialized_errors
    assert "operator_approval_boundary.generic_continuation_satisfies_authorization" in serialized_errors
    assert "source_generic_continuation_rejection.generic_continuation_rejected" in serialized_errors
    assert produced_template["operator_approval_boundary"]["generic_continuation_satisfies_authorization"] is False


def test_approval_witness_template_rejects_source_boundary_drift(tmp_path: Path) -> None:
    template = _default_template()
    template["source_runtime_authorization_request"]["operator_response_collected"] = True
    template["source_runtime_authorization_request"]["runtime_authorization_gate_satisfied"] = True
    template["source_generic_continuation_rejection"]["signed_approval_present"] = True
    template["source_generic_continuation_rejection"]["runtime_authorization_gate_satisfied"] = True
    template_path = tmp_path / "approval-template-source-drift.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")

    validation, produced_template = validator.validate_approval_witness_template(
        template_path=template_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_runtime_authorization_request.operator_response_collected" in serialized_errors
    assert "source_runtime_authorization_request.runtime_authorization_gate_satisfied" in serialized_errors
    assert "source_generic_continuation_rejection.signed_approval_present" in serialized_errors
    assert "source_generic_continuation_rejection.runtime_authorization_gate_satisfied" in serialized_errors
    assert produced_template["source_runtime_authorization_request"]["operator_response_collected"] is False
    assert produced_template["source_generic_continuation_rejection"]["signed_approval_present"] is False


def test_approval_witness_template_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["approval_template_control_count"] == len(validator.APPROVAL_TEMPLATE_CONTROL_IDS)
    assert payload["required_approval_field_count"] == len(validator.APPROVAL_FIELD_IDS)
    assert payload["scenario_approval_requirement_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["runtime_authorization_gate_satisfied"] is False
    assert payload["produced_template"]["approval_witness_collected"] is False
    assert payload["produced_template"]["runtime_promotion_authorized"] is False
