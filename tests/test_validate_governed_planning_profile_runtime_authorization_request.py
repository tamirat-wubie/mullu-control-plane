"""Tests for GovernedPlanningProfile runtime authorization request.

Purpose: verify the planning-profile runtime authorization request is
deterministic, terminal-certificate-bound, locally request-only, and
non-authorizing.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: runtime authorization request validator, terminal closure
certificate validator, and runtime authorization request schema.
Invariants: request evidence can be recorded locally, runtime promotion remains
unauthorized, and activation requires a separate signed response witness.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_governed_planning_profile_runtime_authorization_request as validator
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def _default_request() -> dict:
    return json.loads(validator.DEFAULT_REQUEST.read_text(encoding="utf-8"))


def test_runtime_authorization_request_accepts_default_fixture() -> None:
    validation, produced_request = validator.validate_runtime_authorization_request()

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.schema_path == "schemas/governed_planning_profile_runtime_authorization_request.schema.json"
    assert validation.request_path == "examples/governed_planning_profile_runtime_authorization_request.local.json"
    assert validation.authorization_control_count == len(validator.AUTHORIZATION_CONTROL_IDS)
    assert validation.scenario_authorization_request_count == len(validator.EXPECTED_PLAN_CLASSES)
    assert validation.remaining_promotion_gate_count == 0
    assert produced_request["runtime_authorization_request_submitted"] is True
    assert produced_request["runtime_promotion_authorized"] is False


def test_runtime_authorization_schema_accepts_fixture_and_produced_request() -> None:
    schema = _load_schema(validator.DEFAULT_SCHEMA)
    fixture = _default_request()
    _validation, produced_request = validator.validate_runtime_authorization_request()

    fixture_errors = _validate_schema_instance(schema, fixture)
    produced_errors = _validate_schema_instance(schema, produced_request)

    assert fixture_errors == []
    assert produced_errors == []
    assert fixture == produced_request
    assert fixture["source_terminal_closure_certificate"]["certificate_id"] == produced_request["source_terminal_closure_certificate"]["certificate_id"]
    assert len(fixture["request_hash"]) == 64


def test_runtime_authorization_request_binds_terminal_certificate_and_plan_classes() -> None:
    request = _default_request()
    observed_classes = tuple(item["plan_class"] for item in request["scenario_authorization_requests"])
    source_certificate = request["source_terminal_closure_certificate"]

    assert observed_classes == validator.EXPECTED_PLAN_CLASSES
    assert source_certificate["terminal_closure_certificate_status"] == "CollectedNoEffect"
    assert source_certificate["terminal_closure_gate_satisfied"] is True
    assert source_certificate["all_promotion_evidence_satisfied"] is True
    assert source_certificate["remaining_promotion_gate_count"] == 0
    assert request["request_boundary"]["source_terminal_closure_certificate_bound"] is True
    assert request["request_boundary"]["authorization_response_required"] is True


def test_runtime_authorization_request_records_awaiting_response_without_authority() -> None:
    request = _default_request()
    control_ids = tuple(control["control_id"] for control in request["authorization_controls"])
    control_statuses = {control["control_id"]: control["status"] for control in request["authorization_controls"]}
    operator_request = request["operator_authorization_request"]

    assert control_ids == validator.AUTHORIZATION_CONTROL_IDS
    assert control_statuses["runtime_authorization_response_required"] == "AwaitingEvidence"
    assert control_statuses["signed_response_absent"] == "AwaitingEvidence"
    assert tuple(operator_request["allowed_response_kinds"]) == validator.ALLOWED_RESPONSE_KINDS
    assert operator_request["default_response_kind"] == validator.ALLOWED_RESPONSE_KINDS[1]
    assert operator_request["response_record_collected"] is False
    assert request["runtime_authorization_gate_satisfied"] is False
    assert request["runtime_promotion_authorized"] is False


def test_runtime_authorization_request_rejects_runtime_authority(tmp_path: Path) -> None:
    request = _default_request()
    request["runtime_promotion_authorized"] = True
    request["execution_allowed"] = True
    request["dispatch_allowed"] = True
    request["terminal_closure"] = True
    request["authority_denials"]["runtime_promotion_authorized"] = True
    request["scenario_authorization_requests"][0]["runtime_promotion_authorized"] = True
    request["scenario_authorization_requests"][0]["runtime_execution_performed"] = True
    request_path = tmp_path / "runtime-authorization-authority.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validator.validate_runtime_authorization_request(request_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "runtime_promotion_authorized" in serialized_errors
    assert "execution_allowed" in serialized_errors
    assert "dispatch_allowed" in serialized_errors
    assert "terminal_closure" in serialized_errors
    assert "authority_denials.runtime_promotion_authorized" in serialized_errors
    assert "runtime_execution_performed" in serialized_errors
    assert produced_request["runtime_promotion_authorized"] is False
    assert produced_request["terminal_closure"] is False


def test_runtime_authorization_request_rejects_collected_response_drift(tmp_path: Path) -> None:
    request = _default_request()
    request["operator_response_collected"] = True
    request["runtime_authorization_response_ref"] = "approval://signed-response"
    request["runtime_authorization_gate_satisfied"] = True
    request["operator_authorization_request"]["response_record_collected"] = True
    request["operator_authorization_request"]["runtime_promotion_authorized_after_response"] = True
    request["request_boundary"]["authorization_response_collected"] = True
    request_path = tmp_path / "runtime-authorization-response-drift.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validator.validate_runtime_authorization_request(request_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "operator_response_collected" in serialized_errors
    assert "runtime_authorization_response_ref must remain unknown" in serialized_errors
    assert "runtime_authorization_gate_satisfied" in serialized_errors
    assert "response_record_collected" in serialized_errors
    assert "runtime_promotion_authorized_after_response" in serialized_errors
    assert "request_boundary.authorization_response_collected" in serialized_errors
    assert produced_request["operator_response_collected"] is False
    assert produced_request["runtime_authorization_gate_satisfied"] is False


def test_runtime_authorization_request_rejects_unsatisfied_source_certificate(tmp_path: Path) -> None:
    request = _default_request()
    request["source_terminal_closure_certificate"]["terminal_closure_certificate_status"] = "AwaitingEvidence"
    request["source_terminal_closure_certificate"]["terminal_closure_gate_satisfied"] = False
    request["source_terminal_closure_certificate"]["all_promotion_evidence_satisfied"] = False
    request["source_terminal_closure_certificate"]["remaining_promotion_gate_count"] = 1
    request["promotion_gate_summary"]["all_promotion_evidence_satisfied"] = False
    request_path = tmp_path / "runtime-authorization-unsatisfied-source.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validator.validate_runtime_authorization_request(request_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "source terminal closure certificate status" in serialized_errors
    assert "source terminal closure gate" in serialized_errors
    assert "source promotion evidence" in serialized_errors
    assert "source remaining promotion gate count" in serialized_errors
    assert "promotion_gate_summary.all_promotion_evidence_satisfied" in serialized_errors
    assert produced_request["source_terminal_closure_certificate"]["remaining_promotion_gate_count"] == 0
    assert produced_request["promotion_gate_summary"]["all_promotion_evidence_satisfied"] is True


def test_runtime_authorization_request_rejects_boundary_drift(tmp_path: Path) -> None:
    request = _default_request()
    request["request_boundary"]["source_terminal_closure_certificate_bound"] = False
    request["request_boundary"]["all_promotion_evidence_satisfied"] = False
    request["request_boundary"]["authorization_request_submitted"] = False
    request["request_boundary"]["authorization_response_required"] = False
    request["request_boundary"]["runtime_activation_performed"] = True
    request["request_boundary"]["terminal_closure_authority_granted"] = True
    request_path = tmp_path / "runtime-authorization-boundary-drift.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    validation, produced_request = validator.validate_runtime_authorization_request(request_path=request_path)
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "request_boundary.source_terminal_closure_certificate_bound" in serialized_errors
    assert "request_boundary.all_promotion_evidence_satisfied" in serialized_errors
    assert "request_boundary.authorization_request_submitted" in serialized_errors
    assert "request_boundary.authorization_response_required" in serialized_errors
    assert "request_boundary.runtime_activation_performed" in serialized_errors
    assert "request_boundary.terminal_closure_authority_granted" in serialized_errors
    assert produced_request["request_boundary"]["authorization_request_submitted"] is True
    assert produced_request["request_boundary"]["runtime_activation_performed"] is False


def test_runtime_authorization_request_cli_json_reports_valid(capsys) -> None:
    exit_code = validator.main(["--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["authorization_control_count"] == len(validator.AUTHORIZATION_CONTROL_IDS)
    assert payload["scenario_authorization_request_count"] == len(validator.EXPECTED_PLAN_CLASSES)
    assert payload["remaining_promotion_gate_count"] == 0
    assert payload["produced_request"]["runtime_authorization_request_submitted"] is True
    assert payload["produced_request"]["runtime_promotion_authorized"] is False
