"""Tests for personal-assistant ref absence closure review.

Purpose: prove blocked absence closure packets can be reviewed without becoming
terminal closure, value acceptance, verifier execution, or authority.
Governance scope: closure review, pending evidence obligations,
private-payload redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant closure review builders and schema validation
helpers.
Invariants:
  - Runtime envelope validates against the closure review schema.
  - Missing verification results remain pending evidence obligations.
  - No terminal closure, verifier execution, connector mutation, memory write,
    deployment mutation, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_ref_absence_closure_review,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet,
    build_personal_assistant_ref_absence_closure_review_envelope,
)
from scripts.validate_pa_ref_absence_closure_review import (
    EXPECTED_REQUIRED_VALUE_REFS,
    _validate_ref_absence_closure_review_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
CLOSURE_REVIEW_SCHEMA_PATH = ROOT / "schemas" / "pa_ref_absence_closure_review.schema.json"
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_ref_absence_closure_review_blocks_terminal_closure() -> None:
    envelope = build_default_personal_assistant_ref_absence_closure_review()
    schema = _load_schema(CLOSURE_REVIEW_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_ref_absence_closure_review_semantics(envelope, receipt_schema) == ()
    assert envelope["review_state"]["can_close_review"] is False
    assert envelope["review_state"]["can_close_source_packet"] is False
    assert envelope["review_state"]["can_close_verifier_execution"] is False
    assert envelope["review_state"]["can_close_authority_grant"] is False
    assert envelope["review_state"]["can_close_terminal_readiness"] is False
    assert envelope["summary"]["reviewed_obligation_count"] == 4
    assert envelope["summary"]["pending_evidence_obligation_count"] == 4
    assert envelope["summary"]["missing_verification_result_count"] == 4
    assert envelope["summary"]["verification_result_present_count"] == 0
    assert envelope["summary"]["verified_ref_count"] == 0
    assert envelope["summary"]["accepted_ref_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert tuple(item["ref_name"] for item in envelope["review_items"]) == EXPECTED_REQUIRED_VALUE_REFS
    assert all(item["required_next_evidence"] == "governed_verification_result" for item in envelope["review_items"])
    assert all(item["verification_result_present"] is False for item in envelope["review_items"])
    assert all(item["grants_authority"] is False for item in envelope["review_items"])
    assert envelope["effect_boundary"]["connector_mutation_allowed"] is False
    assert envelope["effect_boundary"]["memory_write_allowed"] is False
    assert envelope["effect_boundary"]["deployment_mutation_allowed"] is False
    assert envelope["receipt"]["metadata"]["review_only"] is True


def test_runtime_ref_absence_closure_review_rejects_source_terminal_closure_drift() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet()
    source["closure_state"]["can_close_terminal_readiness"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_ref_absence_closure_review_envelope(
            generated_at="2026-06-14T03:00:00+00:00",
            source_closure_packet=source,
        )

    assert "source closure_state.can_close_terminal_readiness must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_ref_absence_closure_review_rejects_accepted_obligation_drift() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet()
    source["pending_evidence_obligations"][0]["accepted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_ref_absence_closure_review_envelope(
            generated_at="2026-06-14T03:00:00+00:00",
            source_closure_packet=source,
        )

    assert "accepted must be false" in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_runtime_ref_absence_closure_review_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_ref_absence_closure_review()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["review_state"]["can_close_review"] = True
    envelope["review_items"][0]["grants_authority"] = True

    errors = _validate_ref_absence_closure_review_semantics(envelope, receipt_schema)

    assert errors
    assert any("review_state.can_close_review must be false" in error for error in errors)
    assert any("review_items[0].grants_authority must be False" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_ref_absence_closure_review_rejects_secret_values() -> None:
    source = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_closure_packet()
    source["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_ref_absence_closure_review_envelope(
            generated_at="2026-06-14T03:00:00+00:00",
            source_closure_packet=source,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
