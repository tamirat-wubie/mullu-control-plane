"""Connector self-healing receipt tests.

Purpose: verify provider failures become bounded recovery receipts instead of
implicit connector success.
Governance scope: retry bounds, write-operation review, receipt restoration,
fallback provider certification, read-only degradation, and schema anchoring.
Dependencies: gateway.connector_self_healing and connector self-healing schema.
Invariants:
  - Provider success is never assumed after failure.
  - Write failures require operator review.
  - Missing receipts can revoke capability use.
  - Fallback providers require certification and fresh receipts.
"""

from __future__ import annotations

from pathlib import Path

from gateway.connector_self_healing import ConnectorFailure, ConnectorFailureType, ConnectorHealingStatus, ConnectorRecoveryAction, ConnectorRecoveryPolicy, ConnectorSelfHealingEngine
from scripts.validate_schemas import _load_schema, _validate_schema_instance

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "connector_self_healing_receipt.schema.json"


def test_retryable_provider_failure_emits_retry_receipt_not_success() -> None:
    receipt = ConnectorSelfHealingEngine().evaluate(_failure(), _policy(), attempt_count=0)
    assert receipt.status == ConnectorHealingStatus.RETRY_SCHEDULED
    assert receipt.safe_to_continue is False
    assert "verification_after_retry" in receipt.required_controls
    assert receipt.metadata["provider_success_not_assumed"] is True


def test_write_operation_failure_requires_operator_review() -> None:
    receipt = ConnectorSelfHealingEngine().evaluate(_failure(), _policy(), write_operation=True)
    assert receipt.status == ConnectorHealingStatus.REQUIRES_REVIEW
    assert receipt.action == ConnectorRecoveryAction.REQUIRE_REVIEW
    assert "operator_review" in receipt.required_controls
    assert receipt.safe_to_continue is False


def test_missing_receipt_revokes_capability_until_proof_restored() -> None:
    receipt = ConnectorSelfHealingEngine().evaluate(_failure(failure_type=ConnectorFailureType.RECEIPT_MISSING, retryable=False), _policy())
    assert receipt.status == ConnectorHealingStatus.CAPABILITY_REVOKED
    assert receipt.action == ConnectorRecoveryAction.REVOKE_CAPABILITY
    assert "receipt_restoration" in receipt.required_controls
    assert receipt.metadata["revoked_until_receipt_restored"] is True


def test_fallback_provider_switch_requires_certification_and_fresh_receipt() -> None:
    policy = _policy(allowed_actions=(ConnectorRecoveryAction.SWITCH_PROVIDER, ConnectorRecoveryAction.OPEN_INCIDENT), fallback_providers=("gmail-backup",))
    receipt = ConnectorSelfHealingEngine().evaluate(_failure(retryable=False), policy)
    assert receipt.status == ConnectorHealingStatus.PROVIDER_SWITCH_REQUIRED
    assert receipt.fallback_provider == "gmail-backup"
    assert "fallback_provider_certification" in receipt.required_controls
    assert "fresh_connector_receipt" in receipt.required_controls


def test_read_only_degradation_is_bounded_for_non_write_failure() -> None:
    policy = _policy(allowed_actions=(ConnectorRecoveryAction.DEGRADE_READ_ONLY, ConnectorRecoveryAction.OPEN_INCIDENT))
    receipt = ConnectorSelfHealingEngine().evaluate(_failure(retryable=False), policy)
    assert receipt.status == ConnectorHealingStatus.DEGRADED_READ_ONLY
    assert receipt.safe_to_continue is True
    assert "read_only_scope" in receipt.required_controls
    assert receipt.metadata["degraded_mode"] == "read_only"


def test_connector_self_healing_receipt_schema_validates() -> None:
    receipt = ConnectorSelfHealingEngine().evaluate(_failure(), _policy())
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), receipt.to_json_dict())
    assert errors == []
    assert receipt.receipt_hash
    assert receipt.receipt_is_terminal_closure is False
    assert receipt.metadata["healing_receipt_is_not_terminal_closure"] is True


def _failure(*, failure_type: ConnectorFailureType = ConnectorFailureType.PROVIDER_ERROR, retryable: bool = True) -> ConnectorFailure:
    return ConnectorFailure(failure_id="failure-gmail-1", connector_id="gmail.send_draft", provider="gmail", operation="send_draft", tenant_id="tenant-a", failure_type=failure_type, observed_at="2026-05-06T12:00:00Z", retryable=retryable, evidence_refs=("proof://connector/failure-1",))


def _policy(*, allowed_actions: tuple[ConnectorRecoveryAction, ...] = (ConnectorRecoveryAction.RETRY, ConnectorRecoveryAction.SWITCH_PROVIDER, ConnectorRecoveryAction.DEGRADE_READ_ONLY, ConnectorRecoveryAction.OPEN_INCIDENT, ConnectorRecoveryAction.REVOKE_CAPABILITY, ConnectorRecoveryAction.REQUIRE_REVIEW), fallback_providers: tuple[str, ...] = ("gmail-backup",)) -> ConnectorRecoveryPolicy:
    return ConnectorRecoveryPolicy(connector_id="gmail.send_draft", allowed_actions=allowed_actions, max_retry_attempts=2, fallback_providers=fallback_providers, requires_receipt=True)
