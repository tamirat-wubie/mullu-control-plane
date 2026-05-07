"""Gateway enterprise identity and authority graph.

Purpose: bind human, agent, and service identities to tenant-scoped authority
    grants, credential leases, delegation expiry, and separation-of-duty checks.
Governance scope: enterprise identity, non-human identity, service accounts,
    directory sync evidence, role grants, capability grants, approval authority,
    credential leases, and break-glass controls.
Dependencies: dataclasses, datetime, and command-spine canonical hashing.
Invariants:
  - Every identity is tenant-bound and typed.
  - Service identities require scoped credential leases.
  - Agents cannot expand their own permissions.
  - Requesters cannot approve their own high-risk action.
  - Expired grants, delegations, and credential leases fail closed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable

from gateway.command_spine import canonical_hash


IDENTITY_TYPES = ("human", "agent", "service")
IDENTITY_STATUSES = ("active", "suspended", "revoked")
GRANT_TYPES = ("role", "permission", "capability", "approval_authority", "delegation")
DECISION_VERDICTS = ("allow", "deny", "escalate")
RISK_TIERS = ("low", "medium", "high", "critical")


@dataclass(frozen=True, slots=True)
class EnterpriseIdentity:
    """Canonical identity for humans, agents, and services."""

    identity_id: str
    identity_type: str
    tenant_id: str
    display_name: str
    status: str
    source: str
    external_subject: str
    teams: tuple[str, ...]
    roles: tuple[str, ...]
    created_at: str
    expires_at: str = ""
    evidence_refs: tuple[str, ...] = ()
    identity_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.identity_id, "identity_id")
        if self.identity_type not in IDENTITY_TYPES:
            raise ValueError("identity_type_invalid")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.display_name, "display_name")
        if self.status not in IDENTITY_STATUSES:
            raise ValueError("identity_status_invalid")
        _require_text(self.source, "source")
        _require_text(self.external_subject, "external_subject")
        _require_text(self.created_at, "created_at")
        object.__setattr__(self, "teams", _normalize_text_tuple(self.teams, "teams", allow_empty=True))
        object.__setattr__(self, "roles", _normalize_text_tuple(self.roles, "roles", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _identity_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    """Tenant-scoped authority assigned to one identity."""

    grant_id: str
    identity_id: str
    tenant_id: str
    grant_type: str
    value: str
    resource: str
    issued_by: str
    issued_at: str
    expires_at: str
    evidence_refs: tuple[str, ...]
    max_amount: float = 0.0
    separation_of_duty: bool = False
    grant_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.grant_id, "grant_id")
        _require_text(self.identity_id, "identity_id")
        _require_text(self.tenant_id, "tenant_id")
        if self.grant_type not in GRANT_TYPES:
            raise ValueError("grant_type_invalid")
        _require_text(self.value, "value")
        _require_text(self.resource, "resource")
        _require_text(self.issued_by, "issued_by")
        _require_text(self.issued_at, "issued_at")
        _require_text(self.expires_at, "expires_at")
        if self.max_amount < 0:
            raise ValueError("max_amount_nonnegative_required")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _grant_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class CredentialLease:
    """Short-lived credential lease for service or machine-style execution."""

    lease_id: str
    identity_id: str
    tenant_id: str
    scopes: tuple[str, ...]
    issued_at: str
    expires_at: str
    evidence_refs: tuple[str, ...]
    revoked_at: str = ""
    lease_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.lease_id, "lease_id")
        _require_text(self.identity_id, "identity_id")
        _require_text(self.tenant_id, "tenant_id")
        object.__setattr__(self, "scopes", _normalize_text_tuple(self.scopes, "scopes"))
        _require_text(self.issued_at, "issued_at")
        _require_text(self.expires_at, "expires_at")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AuthorityRequest:
    """One authority evaluation request."""

    request_id: str
    actor_id: str
    tenant_id: str
    action: str
    resource: str
    risk_tier: str
    requested_at: str
    amount: float = 0.0
    approval_target_actor_id: str = ""
    requested_grant_value: str = ""
    credential_scope: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.actor_id, "actor_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.action, "action")
        _require_text(self.resource, "resource")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        _require_text(self.requested_at, "requested_at")
        if self.amount < 0:
            raise ValueError("amount_nonnegative_required")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    """Deterministic authority decision."""

    decision_id: str
    request_id: str
    actor_id: str
    tenant_id: str
    verdict: str
    reason: str
    required_controls: tuple[str, ...]
    matched_grant_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        _require_text(self.request_id, "request_id")
        _require_text(self.actor_id, "actor_id")
        _require_text(self.tenant_id, "tenant_id")
        if self.verdict not in DECISION_VERDICTS:
            raise ValueError("authority_verdict_invalid")
        _require_text(self.reason, "reason")
        object.__setattr__(self, "required_controls", _normalize_text_tuple(self.required_controls, "required_controls", allow_empty=True))
        object.__setattr__(self, "matched_grant_ids", _normalize_text_tuple(self.matched_grant_ids, "matched_grant_ids", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", _decision_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class EnterpriseAuthorityGraph:
    """In-memory enterprise authority graph for gateway admission checks."""

    def __init__(self, *, identities: Iterable[EnterpriseIdentity] = (), grants: Iterable[AuthorityGrant] = (), leases: Iterable[CredentialLease] = ()) -> None:
        self._identities = {identity.identity_id: _stamp_identity(identity) for identity in identities}
        self._grants = {grant.grant_id: _stamp_grant(grant) for grant in grants}
        self._leases = {lease.lease_id: _stamp_lease(lease) for lease in leases}

    def register_identity(self, identity: EnterpriseIdentity) -> EnterpriseIdentity:
        """Register one identity and return its stamped copy."""
        stamped = _stamp_identity(identity)
        self._identities[stamped.identity_id] = stamped
        return stamped

    def grant(self, grant: AuthorityGrant) -> AuthorityGrant:
        """Register one authority grant and return its stamped copy."""
        if grant.identity_id not in self._identities:
            raise ValueError("grant_identity_unknown")
        stamped = _stamp_grant(grant)
        self._grants[stamped.grant_id] = stamped
        return stamped

    def lease(self, lease: CredentialLease) -> CredentialLease:
        """Register one credential lease and return its stamped copy."""
        if lease.identity_id not in self._identities:
            raise ValueError("lease_identity_unknown")
        stamped = _stamp_lease(lease)
        self._leases[stamped.lease_id] = stamped
        return stamped

    def evaluate(self, request: AuthorityRequest) -> AuthorityDecision:
        """Evaluate one authority request against identities, grants, and leases."""
        identity = self._identities.get(request.actor_id)
        if identity is None:
            return _decision(request, "deny", "identity_unknown", (), (), request.evidence_refs)
        if identity.status != "active":
            return _decision(request, "deny", "identity_not_active", (), (), (*request.evidence_refs, *identity.evidence_refs))
        if identity.tenant_id != request.tenant_id:
            return _decision(request, "deny", "tenant_boundary_denied", (), (), (*request.evidence_refs, *identity.evidence_refs))
        if identity.expires_at and _expired(identity.expires_at, request.requested_at):
            return _decision(request, "deny", "identity_expired", (), (), (*request.evidence_refs, *identity.evidence_refs))
        if identity.identity_type == "agent" and request.action == "grant_permission" and request.actor_id == request.approval_target_actor_id:
            return _decision(request, "deny", "agent_cannot_expand_own_permissions", (), (), (*request.evidence_refs, *identity.evidence_refs))
        if request.action == "grant_approval" and request.risk_tier in {"high", "critical"} and request.actor_id == request.approval_target_actor_id:
            return _decision(request, "deny", "self_approval_forbidden", (), (), (*request.evidence_refs, *identity.evidence_refs))
        if identity.identity_type == "service":
            lease_decision = _service_lease_decision(identity, request, self._leases.values())
            if lease_decision is not None:
                return lease_decision

        grants = tuple(grant for grant in self._grants.values() if _grant_matches(grant, request))
        active_grants = tuple(grant for grant in grants if not _expired(grant.expires_at, request.requested_at))
        if not grants:
            return _decision(request, "deny", "authority_grant_missing", ("directory_sync",), (), (*request.evidence_refs, *identity.evidence_refs))
        if not active_grants:
            return _decision(request, "deny", "authority_grant_expired", ("fresh_grant",), tuple(grant.grant_id for grant in grants), _refs(request, identity, grants))
        if any(grant.max_amount and request.amount > grant.max_amount for grant in active_grants):
            return _decision(request, "deny", "authority_amount_limit_exceeded", (), tuple(grant.grant_id for grant in active_grants), _refs(request, identity, active_grants))
        if any(grant.separation_of_duty for grant in active_grants) and request.actor_id == request.approval_target_actor_id:
            return _decision(request, "deny", "separation_of_duty_denied", (), tuple(grant.grant_id for grant in active_grants), _refs(request, identity, active_grants))
        return _decision(
            request,
            "allow",
            "authority_grant_satisfied",
            ("terminal_closure",),
            tuple(grant.grant_id for grant in active_grants),
            _refs(request, identity, active_grants),
        )

    def read_model(self) -> dict[str, Any]:
        """Return a bounded operator read model."""
        return {
            "identity_count": len(self._identities),
            "grant_count": len(self._grants),
            "lease_count": len(self._leases),
            "identities": [identity.to_json_dict() for identity in sorted(self._identities.values(), key=lambda item: item.identity_id)],
            "grants": [grant.to_json_dict() for grant in sorted(self._grants.values(), key=lambda item: item.grant_id)],
            "leases": [lease.to_json_dict() for lease in sorted(self._leases.values(), key=lambda item: item.lease_id)],
        }


def _service_lease_decision(identity: EnterpriseIdentity, request: AuthorityRequest, leases: Iterable[CredentialLease]) -> AuthorityDecision | None:
    matching = tuple(lease for lease in leases if lease.identity_id == identity.identity_id and lease.tenant_id == request.tenant_id)
    if not matching:
        return _decision(request, "deny", "service_credential_lease_missing", ("credential_lease",), (), (*request.evidence_refs, *identity.evidence_refs))
    active = tuple(lease for lease in matching if not lease.revoked_at and not _expired(lease.expires_at, request.requested_at))
    if not active:
        return _decision(request, "deny", "service_credential_lease_expired", ("fresh_credential_lease",), (), (*request.evidence_refs, *identity.evidence_refs, *(ref for lease in matching for ref in lease.evidence_refs)))
    if request.credential_scope and not any(request.credential_scope in lease.scopes for lease in active):
        return _decision(request, "deny", "service_credential_scope_denied", ("scoped_credential_lease",), (), (*request.evidence_refs, *identity.evidence_refs, *(ref for lease in active for ref in lease.evidence_refs)))
    return None


def _grant_matches(grant: AuthorityGrant, request: AuthorityRequest) -> bool:
    if grant.identity_id != request.actor_id or grant.tenant_id != request.tenant_id:
        return False
    if grant.resource != "*" and grant.resource != request.resource:
        return False
    return grant.value in {request.action, request.requested_grant_value, "*"}


def _decision(
    request: AuthorityRequest,
    verdict: str,
    reason: str,
    required_controls: tuple[str, ...],
    matched_grant_ids: tuple[str, ...],
    evidence_refs: tuple[str, ...],
) -> AuthorityDecision:
    decision = AuthorityDecision(
        decision_id="pending",
        request_id=request.request_id,
        actor_id=request.actor_id,
        tenant_id=request.tenant_id,
        verdict=verdict,
        reason=reason,
        required_controls=required_controls,
        matched_grant_ids=matched_grant_ids,
        evidence_refs=evidence_refs or ("authority:evaluation",),
    )
    payload = decision.to_json_dict()
    payload["decision_hash"] = ""
    decision_hash = canonical_hash(payload)
    return replace(decision, decision_id=f"authority-decision-{decision_hash[:16]}", decision_hash=decision_hash)


def _refs(request: AuthorityRequest, identity: EnterpriseIdentity, grants: Iterable[AuthorityGrant]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*request.evidence_refs, *identity.evidence_refs, *(ref for grant in grants for ref in grant.evidence_refs))))


def _stamp_identity(identity: EnterpriseIdentity) -> EnterpriseIdentity:
    payload = identity.to_json_dict()
    payload["identity_hash"] = ""
    return replace(identity, identity_hash=canonical_hash(payload))


def _stamp_grant(grant: AuthorityGrant) -> AuthorityGrant:
    payload = grant.to_json_dict()
    payload["grant_hash"] = ""
    return replace(grant, grant_hash=canonical_hash(payload))


def _stamp_lease(lease: CredentialLease) -> CredentialLease:
    payload = lease.to_json_dict()
    payload["lease_hash"] = ""
    return replace(lease, lease_hash=canonical_hash(payload))


def _expired(expires_at: str, now: str) -> bool:
    return _parse_time(expires_at) <= _parse_time(now)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _identity_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["tenant_bound_identity"] = True
    payload["identity_type_explicit"] = True
    payload["directory_evidence_required"] = True
    return payload


def _grant_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["grant_is_expiring"] = True
    payload["grant_is_tenant_scoped"] = True
    return payload


def _decision_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["decision_is_not_execution"] = True
    payload["separation_of_duty_checked"] = True
    payload["credential_lease_checked"] = True
    return payload


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
