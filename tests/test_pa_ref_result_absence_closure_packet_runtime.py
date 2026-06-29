"""Tests for explicit decision value-ref result absence closure packet.

Purpose: prove absent verification result statuses can be summarized as a
closure packet without becoming terminal closure, value acceptance, execution,
or authority.
Governance scope: closure packet, pending evidence obligations, private-payload
redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant absence closure packet builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the closure packet schema.
  - Missing verification results remain pending evidence obligations.
  - No terminal closure, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_explicit_decision_value_ref_verification_result_absence_status_closure_packet_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_explicit_decision_value_ref_verification_result_absence_closure_packet_blocks_terminal_closure() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet()
    schema = _load_schema(VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_CLOSURE_PACKET_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_value_ref_verification_result_absence_status_closure_packet_semantics(envelope, receipt_schema) == ()
    assert envelope["closure_state"]["can_close_verifier_execution"] is False
    assert envelope["closure_state"]["can_close_value_binding"] is False
    assert envelope["closure_state"]["can_close_authority_grant"] is False
    assert envelope["closure_state"]["can_close_terminal_readiness"] is False
    assert envelope["summary"]["pending_evidence_obligation_count"] == 4
    assert envelope["summary"]["missing_verification_result_count"] == 4
    assert envelope["summary"]["verification_result_present_count"] == 0
    assert envelope["summary"]["submitted_ref_only_count"] == 4
    assert envelope["summary"]["verified_ref_count"] == 0
    assert envelope["summary"]["accepted_ref_count"] == 0
    assert envelope["summary"]["bound_ref_count"] == 0
    assert envelope["summary"]["stored_ref_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert tuple(obligation["ref_name"] for obligation in envelope["pending_evidence_obligations"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(obligation["required_evidence"] == "governed_verification_result" for obligation in envelope["pending_evidence_obligations"])
    assert all(obligation["verification_result_present"] is False for obligation in envelope["pending_evidence_obligations"])
    assert all(obligation["grants_authority"] is False for obligation in envelope["pending_evidence_obligations"])
    assert envelope["receipt"]["metadata"]["closure_packet_only"] is True
    assert envelope["receipt"]["metadata"]["terminal_closure_claimed"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False


def test_runtime_explicit_decision_value_ref_verification_result_absence_closure_packet_rejects_source_ready_drift() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger()
    source["effect_boundary"]["verifier_execution_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_envelope(
            generated_at="2026-06-14T02:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger=source,
        )

    assert "effect_boundary.verifier_execution_allowed must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_explicit_decision_value_ref_verification_result_absence_closure_packet_rejects_verified_obligation_drift() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger()
    source["absence_statuses"][0]["verified"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_envelope(
            generated_at="2026-06-14T02:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger=source,
        )

    assert "verified must be false" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_runtime_explicit_decision_value_ref_verification_result_absence_closure_packet_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["closure_state"]["can_close_terminal_readiness"] = True
    envelope["pending_evidence_obligations"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_value_ref_verification_result_absence_status_closure_packet_semantics(envelope, receipt_schema)

    assert errors
    assert any("closure_state.can_close_terminal_readiness must be false" in error for error in errors)
    assert any("pending_evidence_obligations[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_explicit_decision_value_ref_verification_result_absence_closure_packet_rejects_secret_values() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger()
    source["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet_envelope(
            generated_at="2026-06-14T02:45:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger=source,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
