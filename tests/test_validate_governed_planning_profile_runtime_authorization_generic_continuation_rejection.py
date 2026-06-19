"""Tests for GovernedPlanningProfile generic continuation rejection witness.

Purpose: verify generic continuation is rejected as a non-authorization input
while preserving the runtime authorization request evidence chain.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: generic continuation rejection validator, runtime authorization
request validator, and schema validation.
Invariants: generic continuation never authorizes runtime promotion, execution,
dispatch, replanning, success, or terminal closure authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection
    as validator,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_witness() -> dict:
    return json.loads(validator.DEFAULT_WITNESS.read_text(encoding="utf-8"))


def test_generic_continuation_rejection_accepts_default_fixture() -> None:
    validation, produced_witness = validator.validate_generic_continuation_rejection_witness()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == (
        "schemas/governed_planning_profile_runtime_authorization_generic_continuation_rejection.schema.json"
    )
    assert validation.witness_path == (
        "examples/governed_planning_profile_runtime_authorization_generic_continuation_rejection.local.json"
    )
    assert validation.rejection_control_count == len(validator.REJECTION_CONTROL_IDS)
    assert validation.scenario_rejection_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.runtime_authorization_gate_satisfied is False
    assert produced_witness["generic_continuation_rejected"] is True
    assert produced_witness["runtime_promotion_authorized"] is False


def test_generic_continuation_schema_accepts_fixture_and_produced_witness() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_witness()
    _validation, produced_witness = validator.validate_generic_continuation_rejection_witness()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_witness)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_witness
    assert len(fixture["witness_hash"]) == 64
    assert fixture["runtime_authorization_response_kind"] == validator.REJECTION_RESPONSE_KIND


def test_generic_continuation_rejection_binds_source_request_and_plan_classes() -> None:
    witness = _default_witness()
    observed_classes = tuple(item["plan_class"] for item in witness["scenario_rejections"])
    source_request = witness["source_runtime_authorization_request"]

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert source_request["runtime_authorization_request_status"] == "SubmittedNoEffect"
    assert source_request["runtime_authorization_request_submitted"] is True
    assert source_request["operator_response_required"] is True
    assert source_request["operator_response_collected"] is False
    assert source_request["runtime_authorization_gate_satisfied"] is False
    assert witness["promotion_gate_summary"]["remaining_promotion_gate_ids"] == [
        "signed_runtime_authorization_approval_witness"
    ]


def test_generic_continuation_rejection_records_blocked_response_without_authority() -> None:
    witness = _default_witness()
    control_ids = tuple(control["control_id"] for control in witness["rejection_controls"])
    blocked_controls = [
        control for control in witness["rejection_controls"] if control["blocks_runtime_authorization"]
    ]
    boundary = witness["operator_response_boundary"]

    assert control_ids == validator.REJECTION_CONTROL_IDS
    assert len(blocked_controls) == len(validator.REJECTION_CONTROL_IDS) - 1
    assert witness["solver_outcome"] == "GovernanceBlocked"
    assert witness["runtime_authorization_response_status"] == "RejectedNoEffect"
    assert witness["operator_response_recorded"] is True
    assert witness["operator_approval_collected"] is False
    assert boundary["observed_input"] == "continue"
    assert boundary["generic_continuation_satisfies_authorization"] is False


def test_generic_continuation_rejection_rejects_runtime_authority(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["runtime_promotion_authorized"] = True
    witness["execution_allowed"] = True
    witness["dispatch_allowed"] = True
    witness["terminal_closure"] = True
    witness["authority_denials"]["runtime_promotion_authorized"] = True
    witness["scenario_rejections"][0]["runtime_promotion_authorized"] = True
    witness["scenario_rejections"][0]["runtime_execution_performed"] = True
    witness_path = tmp_path / "generic-continuation-authority.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_generic_continuation_rejection_witness(
        witness_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "dispatch_allowed" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "runtime_execution_performed" in serialized_errors
    assert produced_witness["runtime_promotion_authorized"] is False
    assert produced_witness["terminal_closure"] is False


def test_generic_continuation_rejection_rejects_signed_approval_drift(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["operator_approval_collected"] = True
    witness["signed_approval_present"] = True
    witness["runtime_authorization_gate_satisfied"] = True
    witness["runtime_activation_allowed"] = True
    witness["promotion_gate_summary"]["runtime_authorization_response_approved"] = True
    witness_path = tmp_path / "generic-continuation-signed-approval-drift.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_generic_continuation_rejection_witness(
        witness_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_approval_collected" in serialized_errors
    assert "signed_approval_present" in serialized_errors
    assert "runtime_authorization_gate_satisfied" in serialized_errors
    assert "runtime_activation_allowed" in serialized_errors
    assert "runtime_authorization_response_approved" in serialized_errors
    assert produced_witness["operator_approval_collected"] is False
    assert produced_witness["runtime_authorization_gate_satisfied"] is False


def test_generic_continuation_rejection_rejects_unsatisfied_source_request(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["source_runtime_authorization_request"]["runtime_authorization_request_status"] = "Missing"
    witness["source_runtime_authorization_request"]["runtime_authorization_request_submitted"] = False
    witness["source_runtime_authorization_request"]["operator_response_required"] = False
    witness["source_runtime_authorization_request"]["operator_response_collected"] = True
    witness["source_runtime_authorization_request"]["runtime_authorization_gate_satisfied"] = True
    witness_path = tmp_path / "generic-continuation-unsatisfied-source.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_generic_continuation_rejection_witness(
        witness_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_runtime_authorization_request.runtime_authorization_request_status" in serialized_errors
    assert "source_runtime_authorization_request.runtime_authorization_request_submitted" in serialized_errors
    assert "source_runtime_authorization_request.operator_response_required" in serialized_errors
    assert "source_runtime_authorization_request.operator_response_collected" in serialized_errors
    assert "source_runtime_authorization_request.runtime_authorization_gate_satisfied" in serialized_errors
    assert produced_witness["source_runtime_authorization_request"]["operator_response_collected"] is False


def test_generic_continuation_rejection_rejects_boundary_drift(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["operator_response_boundary"]["observed_input"] = "approve"
    witness["operator_response_boundary"]["observed_input_kind"] = "signed_authorization"
    witness["operator_response_boundary"]["explicit_signed_authorization_required"] = False
    witness["operator_response_boundary"]["generic_continuation_satisfies_authorization"] = True
    witness["operator_response_boundary"]["future_signed_approval_still_allowed"] = False
    witness["operator_response_boundary"]["runtime_activation_performed"] = True
    witness_path = tmp_path / "generic-continuation-boundary-drift.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_generic_continuation_rejection_witness(
        witness_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_response_boundary.observed_input" in serialized_errors
    assert "operator_response_boundary.observed_input_kind" in serialized_errors
    assert "operator_response_boundary.explicit_signed_authorization_required" in serialized_errors
    assert "operator_response_boundary.generic_continuation_satisfies_authorization" in serialized_errors
    assert "operator_response_boundary.future_signed_approval_still_allowed" in serialized_errors
    assert "operator_response_boundary.runtime_activation_performed" in serialized_errors
    assert produced_witness["operator_response_boundary"]["observed_input"] == "continue"
    assert produced_witness["operator_response_boundary"]["runtime_activation_performed"] is False


def test_generic_continuation_rejection_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["rejection_control_count"] == len(validator.REJECTION_CONTROL_IDS)
    assert payload["scenario_rejection_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["runtime_authorization_gate_satisfied"] is False
    assert payload["produced_witness"]["generic_continuation_rejected"] is True
    assert payload["produced_witness"]["runtime_promotion_authorized"] is False
