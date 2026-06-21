"""Tests for signed approval generic continuation rejection.

Purpose: verify generic continuation never satisfies the signed approval
intake contract or runtime authorization gate.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: signed approval generic continuation rejection validator,
signed approval intake validator, and schema validation.
Invariants: rejection witness preserves absent approval, absent signature
verification, blocked authorization, and denied runtime authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import (
    validate_governed_planning_profile_runtime_authorization_signed_approval_generic_continuation_rejection
    as validator,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_witness() -> dict:
    return json.loads(validator.DEFAULT_WITNESS.read_text(encoding="utf-8"))


def test_signed_approval_generic_continuation_rejection_accepts_default_fixture() -> None:
    validation, produced_witness = validator.validate_signed_approval_generic_continuation_rejection()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == (
        "schemas/governed_planning_profile_runtime_authorization_signed_approval_generic_continuation_rejection.schema.json"
    )
    assert validation.witness_path == (
        "examples/governed_planning_profile_runtime_authorization_signed_approval_generic_continuation_rejection.local.json"
    )
    assert validation.rejection_control_count == len(validator.REJECTION_CONTROL_IDS)
    assert validation.required_witness_field_rejection_count == len(validator.WITNESS_FIELD_IDS)
    assert validation.scenario_rejection_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.signed_approval_present is False
    assert validation.runtime_authorization_gate_satisfied is False
    assert produced_witness["generic_continuation_rejected"] is True


def test_signed_approval_generic_continuation_rejection_schema_accepts_fixture_and_produced_witness() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_witness()
    _validation, produced_witness = validator.validate_signed_approval_generic_continuation_rejection()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_witness)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_witness
    assert len(fixture["witness_hash"]) == 64
    assert fixture["observed_input_kind"] == "generic_continuation"


def test_signed_approval_generic_continuation_rejection_binds_pr_and_intake_evidence() -> None:
    witness = _default_witness()
    source_intake = witness["source_signed_approval_intake"]
    pr_evidence = witness["source_pull_request_evidence"]
    controls = {control["control_id"]: control["status"] for control in witness["rejection_controls"]}

    assert source_intake["intake_status"] == "AwaitingSignedApproval"
    assert source_intake["signed_approval_witness_collected"] is False
    assert source_intake["signature_verified"] is False
    assert pr_evidence["pr_number"] == 2047
    assert pr_evidence["state"] == "CLOSED"
    assert pr_evidence["merged"] is False
    assert pr_evidence["checks_observed_green"] is True
    assert pr_evidence["operator_close_respected"] is True
    assert controls["closed_pr_2047_evidence_bound"] == "Pass"


def test_signed_approval_generic_continuation_rejection_records_field_and_scenario_rejections() -> None:
    witness = _default_witness()
    field_ids = tuple(field["field_id"] for field in witness["required_witness_field_rejections"])
    observed_classes = tuple(item["plan_class"] for item in witness["scenario_rejections"])
    boundary = witness["operator_response_boundary"]

    assert field_ids == validator.WITNESS_FIELD_IDS
    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert all(field["value_present"] is False for field in witness["required_witness_field_rejections"])
    assert all(field["verified"] is False for field in witness["required_witness_field_rejections"])
    assert all(item["generic_continuation_rejected"] is True for item in witness["scenario_rejections"])
    assert boundary["generic_continuation_satisfies_authorization"] is False
    assert boundary["future_signed_approval_still_allowed"] is True
    assert boundary["runtime_activation_requires_separate_gate"] is True


def test_signed_approval_generic_continuation_rejection_rejects_approval_and_signature_drift(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["operator_approval_collected"] = True
    witness["signed_approval_witness_collected"] = True
    witness["signed_approval_present"] = True
    witness["decision_value_present"] = True
    witness["decision_value_accepted"] = True
    witness["signature_present"] = True
    witness["signature_verified"] = True
    witness["runtime_authorization_gate_satisfied"] = True
    witness_path = tmp_path / "signed-approval-generic-continuation-approval-drift.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_signed_approval_generic_continuation_rejection(
        witness_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_approval_collected" in serialized_errors
    assert "signed_approval_witness_collected" in serialized_errors
    assert "signed_approval_present" in serialized_errors
    assert "decision_value_accepted" in serialized_errors
    assert "signature_verified" in serialized_errors
    assert "runtime_authorization_gate_satisfied" in serialized_errors
    assert produced_witness["signature_verified"] is False
    assert produced_witness["runtime_authorization_gate_satisfied"] is False


def test_signed_approval_generic_continuation_rejection_rejects_source_and_pr_drift(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["source_signed_approval_intake"]["signed_approval_present"] = True
    witness["source_signed_approval_intake"]["signature_verified"] = True
    witness["source_signed_approval_intake"]["runtime_authorization_gate_satisfied"] = True
    witness["source_pull_request_evidence"]["merged"] = True
    witness["source_pull_request_evidence"]["operator_close_respected"] = False
    witness_path = tmp_path / "signed-approval-generic-continuation-source-drift.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_signed_approval_generic_continuation_rejection(
        witness_path=witness_path
    )
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source_signed_approval_intake.signed_approval_present" in serialized_errors
    assert "source_signed_approval_intake.signature_verified" in serialized_errors
    assert "source_signed_approval_intake.runtime_authorization_gate_satisfied" in serialized_errors
    assert "source_pull_request_evidence.merged" in serialized_errors
    assert "source_pull_request_evidence.operator_close_respected" in serialized_errors
    assert produced_witness["source_pull_request_evidence"]["merged"] is False


def test_signed_approval_generic_continuation_rejection_rejects_runtime_authority(tmp_path: Path) -> None:
    witness = _default_witness()
    witness["runtime_promotion_authorized"] = True
    witness["execution_allowed"] = True
    witness["dispatch_allowed"] = True
    witness["terminal_closure"] = True
    witness["authority_denials"]["runtime_promotion_authorized"] = True
    witness["scenario_rejections"][0]["runtime_promotion_authorized"] = True
    witness["scenario_rejections"][0]["runtime_execution_performed"] = True
    witness_path = tmp_path / "signed-approval-generic-continuation-authority.json"
    witness_path.write_text(json.dumps(witness), encoding="utf-8")

    validation, produced_witness = validator.validate_signed_approval_generic_continuation_rejection(
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


def test_signed_approval_generic_continuation_rejection_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["rejection_control_count"] == len(validator.REJECTION_CONTROL_IDS)
    assert payload["required_witness_field_rejection_count"] == len(validator.WITNESS_FIELD_IDS)
    assert payload["scenario_rejection_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["signed_approval_present"] is False
    assert payload["runtime_authorization_gate_satisfied"] is False
    assert payload["produced_witness"]["generic_continuation_rejected"] is True
    assert payload["produced_witness"]["runtime_promotion_authorized"] is False
