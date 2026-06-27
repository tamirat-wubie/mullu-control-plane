"""Tests for verifier execution record value explicit decision candidate projection.

Purpose: prove explicit operator decision candidates are class-only projections
until a governed value with required refs exists.
Governance scope: explicit candidate projection, private-payload redaction, and
Foundation Mode no-effect boundaries.
Dependencies: personal-assistant explicit-decision candidate builders and schema
validation helpers.
Invariants:
  - Runtime envelope validates against the explicit-decision candidate schema.
  - Candidate classes do not become admitted operator values.
  - No value record, verifier execution, or authority is admitted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate import (
    EXPECTED_CANDIDATE_KINDS,
    _validate_explicit_decision_candidate_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
EXPLICIT_DECISION_CANDIDATE_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_verifier_execution_record_value_explicit_decision_candidate_projects_classes_without_authority() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate()
    schema = _load_schema(EXPLICIT_DECISION_CANDIDATE_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    first_candidate = envelope["explicit_decision_candidates"][0]["explicit_decision_candidate"]

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_explicit_decision_candidate_semantics(envelope, receipt_schema) == ()
    assert envelope["explicit_decision_candidate_count"] == 20
    assert envelope["summary"]["explicit_decision_candidate_class_count"] == 80
    assert envelope["summary"]["explicit_decision_candidate_detectable_count"] == 80
    assert envelope["summary"]["explicit_decision_candidate_admission_count"] == 0
    assert envelope["summary"]["explicit_decision_candidate_execution_count"] == 0
    assert envelope["summary"]["explicit_operator_decision_value_bound_count"] == 0
    assert envelope["summary"]["actual_operator_decision_value_absent_count"] == 20
    assert envelope["summary"]["operator_value_record_creation_count"] == 0
    assert envelope["summary"]["verifier_execution_allowed_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["explicit_decision_candidate_state"] == "explicit_operator_decision_candidate_projected_not_admitted"
    assert envelope["effect_boundary"]["explicit_decision_candidate_classes_projected"] is True
    assert envelope["effect_boundary"]["explicit_decision_candidate_admitted"] is False
    assert envelope["effect_boundary"]["operator_decision_value_present"] is False
    assert envelope["effect_boundary"]["operator_value_record_created"] is False
    assert envelope["effect_boundary"]["verifier_execution_started"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert tuple(candidate["candidate_kind"] for candidate in first_candidate["candidate_kinds"]) == EXPECTED_CANDIDATE_KINDS
    assert all(candidate["candidate_detectable"] is True for candidate in first_candidate["candidate_kinds"])
    assert all(candidate["candidate_admitted"] is False for candidate in first_candidate["candidate_kinds"])
    assert all(candidate["grants_authority"] is False for candidate in first_candidate["candidate_kinds"])


def test_runtime_verifier_execution_record_value_explicit_decision_candidate_rejects_empty_source_records() -> None:
    rejection = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection()
    rejection["generic_continuation_rejections"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_envelope(
            generated_at="2026-06-14T01:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection=rejection,
        )

    assert "requires at least one generic continuation rejection" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_verifier_execution_record_value_explicit_decision_candidate_rejects_source_rejection_drift() -> None:
    rejection = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection()
    rejection["generic_continuation_rejections"][0]["generic_continuation_rejection"]["generic_continuation_rejected"] = False

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_envelope(
            generated_at="2026-06-14T01:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection=rejection,
        )

    assert "generic_continuation_rejected must be true" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_verifier_execution_record_value_explicit_decision_candidate_detects_validator_tamper() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate()
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    envelope["explicit_decision_candidates"][0]["explicit_decision_candidate"]["candidate_kinds"][0]["candidate_admitted"] = True
    envelope["explicit_decision_candidates"][0]["explicit_decision_candidate"]["candidate_kinds"][0]["grants_authority"] = True

    errors = _validate_explicit_decision_candidate_semantics(envelope, receipt_schema)

    assert errors
    assert any("candidate_kinds[0].candidate_admitted must be false" in error for error in errors)
    assert any("candidate_kinds[0].grants_authority must be false" in error for error in errors)
    assert not any("secret-worker-token" in error for error in errors)


def test_runtime_verifier_execution_record_value_explicit_decision_candidate_rejects_secret_values() -> None:
    rejection = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection()
    rejection["generic_continuation_rejections"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_candidate_envelope(
            generated_at="2026-06-14T01:50:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection=rejection,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
