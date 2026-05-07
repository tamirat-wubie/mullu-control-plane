"""Gateway enterprise authority graph tests.

Purpose: verify human, agent, and service identities are governed by tenant
boundaries, expiring grants, credential leases, and separation of duty.
Governance scope: enterprise identity, service accounts, machine credentials,
agent permission expansion, approval authority, and schema compatibility.
Dependencies: gateway.enterprise_authority and schemas/enterprise_authority.schema.json.
Invariants:
  - Service identities require scoped active credential leases.
  - Agents cannot expand their own permissions.
  - Requesters cannot approve their own high-risk actions.
  - Expired grants fail closed.
"""

from __future__ import annotations

from pathlib import Path

from gateway.enterprise_authority import (
    AuthorityGrant,
    AuthorityRequest,
    CredentialLease,
    EnterpriseAuthorityGraph,
    EnterpriseIdentity,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "enterprise_authority.schema.json"
NOW = "2026-05-05T12:00:00+00:00"
FUTURE = "2026-05-05T13:00:00+00:00"
PAST = "2026-05-05T11:00:00+00:00"


def test_human_authority_grant_allows_schema_valid_decision() -> None:
    graph = EnterpriseAuthorityGraph()
    graph.register_identity(_identity("human-finance", "human", roles=("finance_admin",)))
    graph.grant(_grant("grant-pay", "human-finance", "payment.dispatch", max_amount=5000.0))

    decision = graph.evaluate(_request(actor_id="human-finance", action="payment.dispatch", amount=2500.0))
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), decision.to_json_dict())

    assert errors == []
    assert decision.verdict == "allow"
    assert decision.reason == "authority_grant_satisfied"
    assert decision.matched_grant_ids == ("grant-pay",)
    assert decision.metadata["decision_is_not_execution"] is True
    assert decision.decision_hash


def test_high_risk_self_approval_is_denied() -> None:
    graph = EnterpriseAuthorityGraph()
    graph.register_identity(_identity("human-finance", "human", roles=("finance_admin",)))
    graph.grant(_grant("grant-approval", "human-finance", "grant_approval", grant_type="approval_authority"))

    decision = graph.evaluate(
        _request(
            actor_id="human-finance",
            action="grant_approval",
            risk_tier="high",
            approval_target_actor_id="human-finance",
        ),
    )

    assert decision.verdict == "deny"
    assert decision.reason == "self_approval_forbidden"
    assert decision.metadata["separation_of_duty_checked"] is True
    assert decision.matched_grant_ids == ()


def test_agent_cannot_expand_own_permissions() -> None:
    graph = EnterpriseAuthorityGraph()
    graph.register_identity(_identity("agent-finance", "agent", roles=("finance_agent",)))
    graph.grant(_grant("grant-delegate", "agent-finance", "grant_permission", grant_type="delegation"))

    decision = graph.evaluate(
        _request(
            actor_id="agent-finance",
            action="grant_permission",
            approval_target_actor_id="agent-finance",
            requested_grant_value="payment.dispatch",
        ),
    )

    assert decision.verdict == "deny"
    assert decision.reason == "agent_cannot_expand_own_permissions"
    assert decision.evidence_refs == ("directory://agent-finance",)
    assert decision.decision_id.startswith("authority-decision-")


def test_service_identity_requires_active_scoped_credential_lease() -> None:
    graph = EnterpriseAuthorityGraph()
    graph.register_identity(_identity("svc-payments", "service", roles=("payment_service",)))
    graph.grant(_grant("grant-service-pay", "svc-payments", "payment.dispatch", max_amount=5000.0))

    missing = graph.evaluate(_request(actor_id="svc-payments", action="payment.dispatch", credential_scope="stripe.write"))
    graph.lease(_lease("lease-pay", "svc-payments", scopes=("stripe.read",)))
    wrong_scope = graph.evaluate(_request(actor_id="svc-payments", action="payment.dispatch", credential_scope="stripe.write"))
    graph.lease(_lease("lease-pay-write", "svc-payments", scopes=("stripe.write",)))
    allowed = graph.evaluate(_request(actor_id="svc-payments", action="payment.dispatch", credential_scope="stripe.write"))

    assert missing.verdict == "deny"
    assert missing.reason == "service_credential_lease_missing"
    assert wrong_scope.verdict == "deny"
    assert wrong_scope.reason == "service_credential_scope_denied"
    assert allowed.verdict == "allow"
    assert allowed.reason == "authority_grant_satisfied"
    assert allowed.metadata["credential_lease_checked"] is True


def test_expired_grant_and_tenant_boundary_fail_closed() -> None:
    graph = EnterpriseAuthorityGraph()
    graph.register_identity(_identity("human-finance", "human", roles=("finance_admin",)))
    graph.grant(_grant("grant-expired", "human-finance", "payment.dispatch", expires_at=PAST))

    expired = graph.evaluate(_request(actor_id="human-finance", action="payment.dispatch"))
    wrong_tenant = graph.evaluate(_request(actor_id="human-finance", tenant_id="tenant-b", action="payment.dispatch"))

    assert expired.verdict == "deny"
    assert expired.reason == "authority_grant_expired"
    assert expired.required_controls == ("fresh_grant",)
    assert wrong_tenant.verdict == "deny"
    assert wrong_tenant.reason == "tenant_boundary_denied"


def test_enterprise_authority_read_model_projects_all_identity_primitives() -> None:
    graph = EnterpriseAuthorityGraph()
    identity = graph.register_identity(_identity("human-finance", "human", roles=("finance_admin",)))
    grant = graph.grant(_grant("grant-pay", "human-finance", "payment.dispatch"))

    read_model = graph.read_model()

    assert read_model["identity_count"] == 1
    assert read_model["grant_count"] == 1
    assert read_model["lease_count"] == 0
    assert read_model["identities"][0]["identity_hash"] == identity.identity_hash
    assert read_model["grants"][0]["grant_hash"] == grant.grant_hash
    assert read_model["identities"][0]["metadata"]["tenant_bound_identity"] is True


def _identity(identity_id: str, identity_type: str, *, roles: tuple[str, ...]) -> EnterpriseIdentity:
    return EnterpriseIdentity(
        identity_id=identity_id,
        identity_type=identity_type,
        tenant_id="tenant-a",
        display_name=identity_id,
        status="active",
        source="scim",
        external_subject=f"scim://directory/{identity_id}",
        teams=("finance",),
        roles=roles,
        created_at=NOW,
        evidence_refs=(f"directory://{identity_id}",),
    )


def _grant(
    grant_id: str,
    identity_id: str,
    value: str,
    *,
    grant_type: str = "capability",
    max_amount: float = 0.0,
    expires_at: str = FUTURE,
) -> AuthorityGrant:
    return AuthorityGrant(
        grant_id=grant_id,
        identity_id=identity_id,
        tenant_id="tenant-a",
        grant_type=grant_type,
        value=value,
        resource="payment",
        issued_by="directory-admin",
        issued_at=NOW,
        expires_at=expires_at,
        evidence_refs=(f"grant://{grant_id}",),
        max_amount=max_amount,
        separation_of_duty=grant_type == "approval_authority",
    )


def _lease(lease_id: str, identity_id: str, *, scopes: tuple[str, ...]) -> CredentialLease:
    return CredentialLease(
        lease_id=lease_id,
        identity_id=identity_id,
        tenant_id="tenant-a",
        scopes=scopes,
        issued_at=NOW,
        expires_at=FUTURE,
        evidence_refs=(f"lease://{lease_id}",),
    )


def _request(
    *,
    actor_id: str,
    action: str,
    tenant_id: str = "tenant-a",
    risk_tier: str = "high",
    amount: float = 0.0,
    approval_target_actor_id: str = "",
    requested_grant_value: str = "",
    credential_scope: str = "",
) -> AuthorityRequest:
    return AuthorityRequest(
        request_id=f"req-{actor_id}-{action}",
        actor_id=actor_id,
        tenant_id=tenant_id,
        action=action,
        resource="payment",
        risk_tier=risk_tier,
        requested_at=NOW,
        amount=amount,
        approval_target_actor_id=approval_target_actor_id,
        requested_grant_value=requested_grant_value,
        credential_scope=credential_scope,
    )
