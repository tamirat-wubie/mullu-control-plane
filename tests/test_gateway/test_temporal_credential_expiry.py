"""Gateway temporal credential expiry tests.

Purpose: verify credential expiry receipts are runtime-owned, scope-aware,
rotation-aware, source-bound, secret-free, and schema-backed before dispatch.
Governance scope: credential lifecycle, expiry, provider and scope binding,
rotation windows, evidence refs, high-risk source receipt binding, and
non-terminal credential expiry receipts.
Dependencies: gateway.temporal_credential_expiry and temporal credential
expiry receipt schema.
Invariants:
  - Active scoped credentials may authorize dispatch only before expiry.
  - Expired or revoked credentials cannot authorize dispatch.
  - Rotation-pending credentials warn without serializing credential values.
  - High-risk credentialed dispatch binds temporal, reapproval, and binding receipts.
  - Low-risk policies may mark credential expiry control not required.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from gateway.temporal_credential_expiry import (
    CredentialDescriptor,
    TemporalCredentialExpiry,
    TemporalCredentialPolicy,
    TemporalCredentialRequest,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "temporal_credential_expiry_receipt.schema.json"
NOW = "2026-05-05T14:30:00+00:00"


class FixedClock:
    """Deterministic wall-clock provider for credential expiry tests."""

    def now_utc(self) -> str:
        return NOW


def test_credential_expiry_allows_high_risk_active_scoped_unexpired_credential() -> None:
    receipt = TemporalCredentialExpiry(FixedClock()).evaluate(_request())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "credential_valid"
    assert receipt.credential_state == "active"
    assert receipt.credential_id == "credential-1"
    assert receipt.provider_id == "gmail"
    assert receipt.credential_scope_id == "email.send"
    assert receipt.seconds_until_expiry == 86400
    assert receipt.seconds_until_rotation_due == 79200
    assert receipt.credential_age_seconds == 345600
    assert receipt.credential_evidence_refs == ["proof://credential/evidence-1"]
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["secret_value_absent"] is True
    assert receipt.metadata["high_risk_source_receipts_checked"] is True


def test_credential_expiry_marks_near_expiry_as_rotation_pending() -> None:
    receipt = TemporalCredentialExpiry(FixedClock()).evaluate(
        _request(
            credential=replace(
                _credential(),
                expires_at="2026-05-05T15:00:00+00:00",
                rotation_due_at="2026-05-05T14:45:00+00:00",
            )
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "rotation_pending"
    assert receipt.credential_state == "rotation_pending"
    assert receipt.seconds_until_expiry == 1800
    assert receipt.seconds_until_rotation_due == 900
    assert "credential_expiry_near" in receipt.warning_reasons
    assert "credential_rotation_due_soon" in receipt.warning_reasons
    assert receipt.blocked_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["rotation_warning_checked"] is True


def test_credential_expiry_blocks_expired_credential() -> None:
    receipt = TemporalCredentialExpiry(FixedClock()).evaluate(
        _request(credential=replace(_credential(), expires_at="2026-05-05T14:00:00+00:00"))
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "expired"
    assert receipt.credential_state == "expired"
    assert receipt.seconds_until_expiry == 0
    assert "credential_expired" in receipt.blocked_reasons
    assert "credential_dispatch_block" in receipt.required_controls
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["expiry_checked"] is True


def test_credential_expiry_blocks_wrong_scope_revoked_missing_evidence_and_sources() -> None:
    receipt = TemporalCredentialExpiry(FixedClock()).evaluate(
        _request(
            credential=replace(
                _credential(),
                tenant_id="tenant-other",
                provider_id="slack",
                credential_scope_id="chat.write",
                disposition="revoked",
                evidence_refs=[],
                source_binding_receipt_id="",
            ),
            evidence_refs=[],
            source_temporal_receipt_id="",
            source_reapproval_receipt_id="",
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "blocked"
    assert receipt.credential_state == "revoked"
    assert "credential_tenant_mismatch" in receipt.blocked_reasons
    assert "credential_provider_mismatch" in receipt.blocked_reasons
    assert "credential_scope_mismatch" in receipt.blocked_reasons
    assert "credential_provider_not_allowed" in receipt.blocked_reasons
    assert "credential_scope_not_allowed" in receipt.blocked_reasons
    assert "credential_revoked" in receipt.blocked_reasons
    assert "credential_evidence_refs_required" in receipt.blocked_reasons
    assert "source_binding_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "evidence_refs_required" in receipt.blocked_reasons
    assert "source_temporal_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert "source_reapproval_receipt_required_for_high_risk" in receipt.blocked_reasons
    assert receipt.metadata["dispatch_allowed"] is False
    assert receipt.metadata["high_risk_source_receipts_checked"] is False


def test_credential_expiry_blocks_future_or_rotation_overdue_credential() -> None:
    future_receipt = TemporalCredentialExpiry(FixedClock()).evaluate(
        _request(
            credential=replace(
                _credential(),
                issued_at="2026-05-05T15:00:00+00:00",
                observed_at="2026-05-05T15:00:00+00:00",
            )
        )
    )
    overdue_receipt = TemporalCredentialExpiry(FixedClock()).evaluate(
        _request(credential=replace(_credential(), rotation_due_at="2026-05-05T14:00:00+00:00"))
    )

    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(future_receipt)) == []
    assert _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(overdue_receipt)) == []
    assert future_receipt.status == "blocked"
    assert future_receipt.credential_state == "future"
    assert future_receipt.credential_age_seconds == 0
    assert "credential_future" in future_receipt.blocked_reasons
    assert "credential_observed_in_future" in future_receipt.blocked_reasons
    assert overdue_receipt.status == "blocked"
    assert overdue_receipt.credential_state == "invalid"
    assert "credential_rotation_overdue" in overdue_receipt.blocked_reasons
    assert overdue_receipt.metadata["dispatch_allowed"] is False


def test_credential_expiry_marks_low_risk_action_not_required() -> None:
    receipt = TemporalCredentialExpiry(FixedClock()).evaluate(
        TemporalCredentialRequest(
            request_id="credential-low-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_reminder",
            risk_level="low",
            provider_id="reminder",
            credential_scope_id="reminder.write",
            policy=replace(_policy(), requires_credential_check=False),
            evidence_refs=[],
            credential=None,
        )
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), asdict(receipt))

    assert errors == []
    assert receipt.status == "not_required"
    assert receipt.credential_state == "not_required"
    assert receipt.credential_check_required is False
    assert receipt.credential_id == ""
    assert receipt.seconds_until_expiry == 0
    assert receipt.credential_age_seconds == 0
    assert receipt.blocked_reasons == []
    assert receipt.warning_reasons == []
    assert receipt.metadata["dispatch_allowed"] is True
    assert receipt.metadata["credential_checked"] is False


def test_credential_expiry_rejects_secret_material_in_metadata() -> None:
    with pytest.raises(ValueError, match="secret_metadata_keys_forbidden"):
        replace(_credential(), metadata={"token": "must-not-serialize"})

    with pytest.raises(ValueError, match="secret_metadata_keys_forbidden"):
        TemporalCredentialRequest(
            request_id="credential-secret-1",
            tenant_id="tenant-1",
            actor_id="operator-1",
            command_id="command-1",
            action_type="send_email",
            risk_level="high",
            provider_id="gmail",
            credential_scope_id="email.send",
            policy=_policy(),
            evidence_refs=["proof://credential/policy-1"],
            credential=_credential(),
            metadata={"api_key": "must-not-serialize"},
        )


def _request(
    *,
    credential: CredentialDescriptor | None = None,
    policy: TemporalCredentialPolicy | None = None,
    evidence_refs: list[str] | None = None,
    source_temporal_receipt_id: str = "temporal-receipt-0123456789abcdef",
    source_reapproval_receipt_id: str = "temporal-reapproval-receipt-0123456789abcdef",
) -> TemporalCredentialRequest:
    return TemporalCredentialRequest(
        request_id="credential-expiry-1",
        tenant_id="tenant-1",
        actor_id="operator-1",
        command_id="command-1",
        action_type="send_email",
        risk_level="high",
        provider_id="gmail",
        credential_scope_id="email.send",
        policy=policy or _policy(),
        evidence_refs=evidence_refs if evidence_refs is not None else ["proof://credential/policy-1"],
        credential=credential if credential is not None else _credential(),
        source_temporal_receipt_id=source_temporal_receipt_id,
        source_reapproval_receipt_id=source_reapproval_receipt_id,
    )


def _policy() -> TemporalCredentialPolicy:
    return TemporalCredentialPolicy(
        policy_id="credential-policy-1",
        tenant_id="tenant-1",
        allowed_provider_ids=["gmail"],
        allowed_credential_scope_ids=["email.send"],
        rotation_warning_seconds=3600,
        max_credential_age_seconds=604800,
        requires_credential_check=True,
        high_risk_requires_credential_check=True,
    )


def _credential() -> CredentialDescriptor:
    return CredentialDescriptor(
        credential_id="credential-1",
        tenant_id="tenant-1",
        provider_id="gmail",
        credential_scope_id="email.send",
        source_kind="vault",
        disposition="active",
        issued_at="2026-05-01T14:30:00+00:00",
        observed_at="2026-05-05T14:00:00+00:00",
        expires_at="2026-05-06T14:30:00+00:00",
        rotation_due_at="2026-05-06T12:30:00+00:00",
        owner_id="credential-owner-1",
        evidence_refs=["proof://credential/evidence-1"],
        source_binding_receipt_id="credential-binding-receipt-0123456789abcdef",
    )
