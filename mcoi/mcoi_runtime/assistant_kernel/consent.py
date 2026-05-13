"""Purpose: assistant consent ledger for external-effect authorization.
Governance scope: owner consent, expiry, revocation, evidence binding, and
    explicit denial before external writes.
Dependencies: dataclasses, datetime, and runtime invariant helpers.
Test contract: tests/test_assistant_kernel.py.
Invariants:
  - Consent grants require evidence.
  - Expired or revoked consent cannot authorize an external effect.
  - Authorization returns a typed decision instead of a bare boolean.
  - Ledger lineage is append-only for grant and revoke events.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


@dataclass(frozen=True, slots=True)
class ConsentGrant:
    """One evidence-backed consent grant for an assistant capability."""

    consent_id: str
    tenant_id: str
    owner_id: str
    capability_id: str
    scope: str
    granted_by: str
    granted_at: str
    expires_at: str
    evidence_refs: tuple[str, ...]
    revoked_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "consent_id", ensure_non_empty_text("consent_id", self.consent_id))
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "owner_id", ensure_non_empty_text("owner_id", self.owner_id))
        object.__setattr__(self, "capability_id", ensure_non_empty_text("capability_id", self.capability_id))
        object.__setattr__(self, "scope", ensure_non_empty_text("scope", self.scope))
        object.__setattr__(self, "granted_by", ensure_non_empty_text("granted_by", self.granted_by))
        object.__setattr__(self, "granted_at", ensure_non_empty_text("granted_at", self.granted_at))
        object.__setattr__(self, "expires_at", ensure_non_empty_text("expires_at", self.expires_at))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def active_at(self, now: str) -> bool:
        """Return whether this grant is active at the supplied timestamp."""
        if self.revoked_at:
            return False
        if self.expires_at == "never":
            return True
        return _parse_timestamp(self.expires_at) > _parse_timestamp(now)


@dataclass(frozen=True, slots=True)
class ConsentDecision:
    """Authorization decision for one capability against the consent ledger."""

    allowed: bool
    reason: str
    consent_id: str = ""
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


class ConsentLedger:
    """In-memory consent ledger with append-only lineage records."""

    def __init__(self) -> None:
        self._grants: dict[str, ConsentGrant] = {}
        self._lineage: list[str] = []

    def grant(self, grant: ConsentGrant) -> ConsentGrant:
        """Persist one consent grant."""
        if grant.consent_id in self._grants:
            raise RuntimeCoreInvariantError("duplicate consent_id")
        self._grants[grant.consent_id] = grant
        self._lineage.append(f"grant:{grant.consent_id}")
        return grant

    def revoke(self, *, consent_id: str, revoked_at: str, evidence_ref: str) -> ConsentGrant:
        """Revoke an existing consent grant with evidence."""
        consent = self._grants.get(ensure_non_empty_text("consent_id", consent_id))
        if consent is None:
            raise RuntimeCoreInvariantError("unknown consent_id")
        evidence = ensure_non_empty_text("evidence_ref", evidence_ref)
        updated = replace(
            consent,
            revoked_at=ensure_non_empty_text("revoked_at", revoked_at),
            metadata={**consent.metadata, "revocation_evidence_ref": evidence},
        )
        self._grants[consent_id] = updated
        self._lineage.append(f"revoke:{consent_id}:{evidence}")
        return updated

    def authorize(
        self,
        *,
        tenant_id: str,
        owner_id: str,
        capability_id: str,
        now: str,
    ) -> ConsentDecision:
        """Authorize one capability if an active matching consent grant exists."""
        tenant = ensure_non_empty_text("tenant_id", tenant_id)
        owner = ensure_non_empty_text("owner_id", owner_id)
        capability = ensure_non_empty_text("capability_id", capability_id)
        active = [
            grant
            for grant in self._grants.values()
            if grant.tenant_id == tenant
            and grant.owner_id == owner
            and grant.capability_id == capability
            and grant.active_at(now)
        ]
        if not active:
            return ConsentDecision(False, "active_consent_required")
        grant = sorted(active, key=lambda item: item.consent_id)[0]
        return ConsentDecision(True, "consent_authorized", grant.consent_id, grant.evidence_refs)

    def lineage(self) -> tuple[str, ...]:
        """Return append-only ledger lineage."""
        return tuple(self._lineage)


def consent_grant_id(
    *,
    tenant_id: str,
    owner_id: str,
    capability_id: str,
    scope: str,
    granted_at: str,
) -> str:
    """Build a stable consent identifier from grant identity fields."""
    return stable_identifier(
        "consent",
        {
            "tenant_id": tenant_id,
            "owner_id": owner_id,
            "capability_id": capability_id,
            "scope": scope,
            "granted_at": granted_at,
        },
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized:
        raise RuntimeCoreInvariantError(f"{field_name} must contain at least one item")
    return normalized


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeCoreInvariantError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
