"""Gateway connector certification tests.

Purpose: verify connector certification levels, evidence requirements, and
production invocation gates.
Governance scope: OAuth scope bounds, approval, idempotency, receipt evidence,
tenant binding, eval coverage, revocation, and public schema anchoring.
Dependencies: gateway.connector_certification and connector certification schema.
Invariants:
  - Write connectors require approval, idempotency, and receipts.
  - Production certification requires live evidence and governance evals.
  - Invocation cannot exceed manifest scopes.
  - Revoked connectors fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.connector_certification import (
    ConnectorCertificationLevel,
    ConnectorCertificationRegistry,
    ConnectorCertificationVerdict,
    ConnectorEvidence,
    ConnectorManifest,
    ConnectorRisk,
    connector_certification_snapshot_to_json_dict,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "connector_certification_registry.schema.json"


def test_write_connector_manifest_requires_approval_receipt_and_idempotency() -> None:
    with pytest.raises(ValueError, match="write_connector_requires_approval"):
        ConnectorManifest(
            connector_id="quickbooks.create_bill",
            provider="quickbooks",
            action="create_bill",
            version="1.0.0",
            risk=ConnectorRisk.HIGH,
            side_effects=("financial_record_create",),
            oauth_scopes=("accounting",),
            requires_approval=False,
            requires_receipt=True,
            requires_idempotency=True,
            requires_tenant_binding=True,
            eval_suites=("tenant_isolation", "approval_required"),
            evidence_required=("mock_test",),
            owner_team="finance-ops",
        )


def test_production_certification_requires_live_evidence_and_eval_coverage() -> None:
    registry = ConnectorCertificationRegistry()
    registry.register_manifest(_quickbooks_manifest(eval_suites=("tenant_isolation",)))
    registry.add_evidence(_evidence("ev-mock", "mock_test"))
    registry.add_evidence(_evidence("ev-sandbox", "sandbox_receipt"))

    certification, decision = registry.certify(
        connector_id="quickbooks.create_bill",
        requested_level=ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED,
        certified_by="operator-1",
        certified_at="2026-05-05T12:00:00Z",
        requested_oauth_scopes=("accounting",),
    )

    assert certification is None
    assert decision.verdict == ConnectorCertificationVerdict.DENY
    assert decision.reason == "connector_certification_requirements_missing"
    assert "approval_required" in decision.missing_evals
    assert "live_receipt" in decision.missing_evidence
    assert "deployment_witness" in decision.missing_evidence


def test_quickbooks_connector_can_be_production_certified_with_full_evidence() -> None:
    registry = _certified_quickbooks_registry()
    snapshot = registry.snapshot()
    payload = connector_certification_snapshot_to_json_dict(snapshot)

    assert len(snapshot.certifications) == 1
    assert snapshot.certifications[0].level == ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED
    assert snapshot.certifications[0].certification_hash
    assert snapshot.decisions[-1].verdict == ConnectorCertificationVerdict.ALLOW
    assert payload["certifications"][0]["level"] == "L5_production_certified"
    assert payload["snapshot_hash"]


def test_invocation_requires_scope_tenant_idempotency_and_receipt() -> None:
    registry = _certified_quickbooks_registry()

    denied_scope = registry.evaluate_invocation(
        connector_id="quickbooks.create_bill",
        requested_oauth_scopes=("accounting", "admin"),
        requires_write=True,
        tenant_bound=True,
        idempotency_key="idem-001",
        receipt_ref="receipt://quickbooks/001",
    )
    denied_idempotency = registry.evaluate_invocation(
        connector_id="quickbooks.create_bill",
        requested_oauth_scopes=("accounting",),
        requires_write=True,
        tenant_bound=True,
        receipt_ref="receipt://quickbooks/001",
    )
    allowed = registry.evaluate_invocation(
        connector_id="quickbooks.create_bill",
        requested_oauth_scopes=("accounting",),
        requires_write=True,
        tenant_bound=True,
        idempotency_key="idem-001",
        receipt_ref="receipt://quickbooks/001",
    )

    assert denied_scope.verdict == ConnectorCertificationVerdict.DENY
    assert denied_scope.reason == "oauth_scope_exceeds_manifest"
    assert denied_idempotency.verdict == ConnectorCertificationVerdict.DENY
    assert denied_idempotency.reason == "idempotency_key_required"
    assert allowed.verdict == ConnectorCertificationVerdict.ALLOW
    assert allowed.reason == "connector_invocation_certified"
    assert "receipt://quickbooks/001" in allowed.evidence_refs


def test_revoked_connector_fails_closed() -> None:
    registry = _certified_quickbooks_registry()
    revoked = registry.revoke(
        connector_id="quickbooks.create_bill",
        revoked_at="2026-05-05T13:00:00Z",
        reason="provider_scope_rotated",
    )
    decision = registry.evaluate_invocation(
        connector_id="quickbooks.create_bill",
        requested_oauth_scopes=("accounting",),
        requires_write=True,
        tenant_bound=True,
        idempotency_key="idem-001",
        receipt_ref="receipt://quickbooks/001",
    )

    assert revoked.revocation_reason == "provider_scope_rotated"
    assert decision.verdict == ConnectorCertificationVerdict.DENY
    assert decision.reason == "connector_certification_revoked"


def test_read_only_google_workspace_connector_can_stop_at_live_read_level() -> None:
    registry = ConnectorCertificationRegistry()
    registry.register_manifest(ConnectorManifest(
        connector_id="google.drive.read_file",
        provider="google_workspace",
        action="read_file",
        version="1.0.0",
        risk=ConnectorRisk.MEDIUM,
        side_effects=(),
        oauth_scopes=("drive.readonly",),
        requires_approval=False,
        requires_receipt=True,
        requires_idempotency=False,
        requires_tenant_binding=True,
        eval_suites=("tenant_isolation",),
        evidence_required=("mock_test", "sandbox_receipt", "live_read_receipt"),
        owner_team="knowledge-ops",
    ))
    for evidence_id, evidence_type in (
        ("ev-mock", "mock_test"),
        ("ev-sandbox", "sandbox_receipt"),
        ("ev-live-read", "live_read_receipt"),
    ):
        registry.add_evidence(_evidence(evidence_id, evidence_type, connector_id="google.drive.read_file"))

    certification, decision = registry.certify(
        connector_id="google.drive.read_file",
        requested_level=ConnectorCertificationLevel.L3_LIVE_READ_ONLY_TESTED,
        certified_by="operator-1",
        certified_at="2026-05-05T12:00:00Z",
        requested_oauth_scopes=("drive.readonly",),
    )

    assert certification is not None
    assert certification.level == ConnectorCertificationLevel.L3_LIVE_READ_ONLY_TESTED
    assert decision.verdict == ConnectorCertificationVerdict.ALLOW
    assert decision.required_controls == ("tenant_binding", "credential_scope", "connector_receipt")


def test_connector_certification_schema_exposes_registry_contract() -> None:
    registry = _certified_quickbooks_registry()
    payload = connector_certification_snapshot_to_json_dict(registry.snapshot())
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:connector-certification-registry:1"
    assert "L5_production_certified" in schema["$defs"]["level"]["enum"]
    assert schema["$defs"]["manifest"]["properties"]["requires_tenant_binding"]["const"] is True
    assert payload["manifests"][0]["manifest_hash"]


def _quickbooks_manifest(*, eval_suites: tuple[str, ...] = ("tenant_isolation", "approval_required")) -> ConnectorManifest:
    return ConnectorManifest(
        connector_id="quickbooks.create_bill",
        provider="quickbooks",
        action="create_bill",
        version="1.0.0",
        risk=ConnectorRisk.HIGH,
        side_effects=("financial_record_create",),
        oauth_scopes=("accounting",),
        requires_approval=True,
        requires_receipt=True,
        requires_idempotency=True,
        requires_tenant_binding=True,
        eval_suites=eval_suites,
        evidence_required=("mock_test", "sandbox_receipt", "live_receipt", "deployment_witness"),
        owner_team="finance-ops",
    )


def _evidence(evidence_id: str, evidence_type: str, *, connector_id: str = "quickbooks.create_bill") -> ConnectorEvidence:
    return ConnectorEvidence(
        evidence_id=evidence_id,
        connector_id=connector_id,
        evidence_type=evidence_type,
        evidence_ref=f"evidence://{connector_id}/{evidence_type}",
        observed_at="2026-05-05T12:00:00Z",
        passed=True,
    )


def _certified_quickbooks_registry() -> ConnectorCertificationRegistry:
    registry = ConnectorCertificationRegistry()
    registry.register_manifest(_quickbooks_manifest())
    for evidence_id, evidence_type in (
        ("ev-mock", "mock_test"),
        ("ev-sandbox", "sandbox_receipt"),
        ("ev-live-read", "live_read_receipt"),
        ("ev-live-write", "live_write_receipt"),
        ("ev-live", "live_receipt"),
        ("ev-deploy", "deployment_witness"),
    ):
        registry.add_evidence(_evidence(evidence_id, evidence_type))
    certification, decision = registry.certify(
        connector_id="quickbooks.create_bill",
        requested_level=ConnectorCertificationLevel.L5_PRODUCTION_CERTIFIED,
        certified_by="operator-1",
        certified_at="2026-05-05T12:00:00Z",
        requested_oauth_scopes=("accounting",),
    )
    assert certification is not None
    assert decision.verdict == ConnectorCertificationVerdict.ALLOW
    return registry
