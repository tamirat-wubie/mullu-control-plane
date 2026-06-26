"""Tests for operator value-binding evidence acceptance preflight.

Purpose: prove submitted evidence refs can be checked without accepting
evidence, binding values, admitting records, or granting execution authority.
Governance scope: submitted-evidence refs, acceptance preflight denial,
private-payload redaction, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant evidence acceptance preflight builders and
schema validation helpers.
Invariants:
  - Runtime envelope validates against the evidence acceptance preflight schema.
  - Submitted refs remain unverified and unaccepted.
  - Dispatch and live connector execution remain blocked.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    PersonalAssistantInvariantError,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake,
    build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_envelope,
)
from scripts.validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight import (
    _validate_evidence_acceptance_preflight_semantics,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_ACCEPTANCE_PREFLIGHT_SCHEMA_PATH = (
    ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight.schema.json"
)
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_blocks_acceptance() -> None:
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight()
    schema = _load_schema(EVIDENCE_ACCEPTANCE_PREFLIGHT_SCHEMA_PATH)
    receipt_schema = _load_schema(RECEIPT_SCHEMA_PATH)
    evidence_kinds = {record["evidence_kind"] for record in envelope["acceptance_preflights"]}

    assert _validate_schema_instance(schema, envelope) == []
    assert _validate_evidence_acceptance_preflight_semantics(envelope, receipt_schema) == ()
    assert envelope["acceptance_preflight_count"] == 4
    assert envelope["summary"]["submitted_evidence_count"] == 4
    assert envelope["summary"]["verified_evidence_count"] == 0
    assert envelope["summary"]["accepted_evidence_count"] == 0
    assert envelope["summary"]["authority_grant_count"] == 0
    assert envelope["acceptance_state"] == "submitted_refs_checked_not_verified_not_accepted"
    assert envelope["outcome"] == "AwaitingEvidence"
    assert evidence_kinds == {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
    assert envelope["effect_boundary"]["submitted_evidence_ref_presence_check_allowed"] is True
    assert envelope["effect_boundary"]["evidence_verified"] is False
    assert envelope["effect_boundary"]["evidence_accepted"] is False
    assert envelope["effect_boundary"]["binding_record_created"] is False
    assert envelope["effect_boundary"]["authority_granted"] is False
    assert envelope["effect_boundary"]["dispatch_allowed"] is False


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_rejects_empty_records() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake()
    intake["submission_records"] = []

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_envelope(
            generated_at="2026-06-14T00:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake=intake,
        )

    assert "requires at least one submitted evidence ref" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_rejects_source_acceptance_drift() -> None:
    intake = copy.deepcopy(
        build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake()
    )
    intake["effect_boundary"]["evidence_accepted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_envelope(
            generated_at="2026-06-14T00:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake=intake,
        )

    assert "submitted evidence ref intake effect_boundary.evidence_accepted must be false" in str(exc_info.value)
    assert "approved" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_rejects_record_verification_drift() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake()
    intake["submission_records"][0]["submitted_evidence"]["evidence_accepted"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_envelope(
            generated_at="2026-06-14T00:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake=intake,
        )

    assert "submitted_evidence.evidence_accepted must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_rejects_authority_drift() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake()
    intake["submission_records"][0]["authority_status"]["dispatch_allowed"] = True

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_envelope(
            generated_at="2026-06-14T00:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake=intake,
        )

    assert "submitted evidence ref intake authority_status.dispatch_allowed must be false" in str(exc_info.value)
    assert "external_message" not in str(exc_info.value)


def test_runtime_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_rejects_secret_values() -> None:
    intake = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake()
    intake["submission_records"][0]["receipt"]["actions_taken"].append("reuse Bearer secret-worker-token")

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        build_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight_envelope(
            generated_at="2026-06-14T00:25:00+00:00",
            operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake=intake,
        )

    assert "secret-like value must not be serialized" in str(secret_exc.value)
    assert "secret-worker-token" not in str(secret_exc.value)
