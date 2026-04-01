"""Phase 2D — Tenant Gating Guard.

Purpose: Enforce tenant lifecycle states at the governance guard layer.
    Suspended/terminated tenants are hard-blocked before any business logic
    executes. Onboarding tenants may have restricted access.
Governance scope: tenant lifecycle enforcement only.
Dependencies: none (pure data structures).
Invariants:
  - Tenant status transitions are validated (no backward transitions).
  - Suspended/terminated tenants are always rejected.
  - Unknown tenants are allowed through (auto-provisioning compatible).
  - Status changes are auditable via the returned TenantGate record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class TenantStatus(str, Enum):
    """Tenant lifecycle states."""

    ACTIVE = "active"
    ONBOARDING = "onboarding"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


# Valid transitions: current -> set of allowed next states
_VALID_TRANSITIONS: dict[TenantStatus, frozenset[TenantStatus]] = {
    TenantStatus.ONBOARDING: frozenset({TenantStatus.ACTIVE, TenantStatus.TERMINATED}),
    TenantStatus.ACTIVE: frozenset({TenantStatus.SUSPENDED, TenantStatus.TERMINATED}),
    TenantStatus.SUSPENDED: frozenset({TenantStatus.ACTIVE, TenantStatus.TERMINATED}),
    TenantStatus.TERMINATED: frozenset(),  # Terminal state — no transitions
}

# States that block request processing
_BLOCKED_STATES = frozenset({TenantStatus.SUSPENDED, TenantStatus.TERMINATED})


@dataclass(frozen=True, slots=True)
class TenantGate:
    """Record of a tenant's gating state."""

    tenant_id: str
    status: TenantStatus
    reason: str = ""
    gated_at: str = ""


class TenantGatingStore:
    """Optional persistent backend for tenant gating state.

    When provided to TenantGatingRegistry, tenant lifecycle state
    is written through for cross-replica consistency.
    """

    def load(self, tenant_id: str) -> TenantGate | None:
        return None

    def save(self, gate: TenantGate) -> None:
        pass

    def load_all(self) -> list[TenantGate]:
        return []


class TenantGatingRegistry:
    """Manages tenant lifecycle states for gating decisions.

    Each tenant has a status (active, onboarding, suspended, terminated).
    Status transitions are validated — invalid transitions are rejected.
    Unknown tenants default to allowed (auto-provisioning compatible).
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        store: TenantGatingStore | None = None,
        default_status: TenantStatus = TenantStatus.ACTIVE,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._gates: dict[str, TenantGate] = {}
        self._store = store
        self._default_status = default_status

    def register(self, tenant_id: str, status: TenantStatus = TenantStatus.ONBOARDING, reason: str = "") -> TenantGate:
        """Register a new tenant with initial status."""
        if tenant_id in self._gates:
            raise ValueError(f"tenant {tenant_id} already registered")
        gate = TenantGate(
            tenant_id=tenant_id,
            status=status,
            reason=reason,
            gated_at=self._clock(),
        )
        self._gates[tenant_id] = gate
        if self._store is not None:
            self._store.save(gate)
        return gate

    def update_status(self, tenant_id: str, new_status: TenantStatus, reason: str = "") -> TenantGate:
        """Update a tenant's lifecycle status.

        Validates that the transition is allowed. Raises ValueError for
        invalid transitions or unknown tenants.
        """
        current = self._gates.get(tenant_id)
        if current is None:
            # Check persistent store
            if self._store is not None:
                current = self._store.load(tenant_id)
                if current is not None:
                    self._gates[tenant_id] = current
        if current is None:
            raise ValueError(f"tenant {tenant_id} not registered")

        allowed = _VALID_TRANSITIONS.get(current.status, frozenset())
        if new_status not in allowed:
            raise ValueError(
                f"invalid transition: {current.status.value} -> {new_status.value} "
                f"for tenant {tenant_id}"
            )

        gate = TenantGate(
            tenant_id=tenant_id,
            status=new_status,
            reason=reason,
            gated_at=self._clock(),
        )
        self._gates[tenant_id] = gate
        if self._store is not None:
            self._store.save(gate)
        return gate

    def get_status(self, tenant_id: str) -> TenantGate | None:
        """Get a tenant's current gating state."""
        gate = self._gates.get(tenant_id)
        if gate is None and self._store is not None:
            gate = self._store.load(tenant_id)
            if gate is not None:
                self._gates[tenant_id] = gate
        return gate

    def is_allowed(self, tenant_id: str) -> bool:
        """Check if a tenant is allowed to make requests.

        Unknown tenants are allowed (auto-provisioning compatible).
        """
        gate = self.get_status(tenant_id)
        if gate is None:
            return True  # Unknown tenants allowed through
        return gate.status not in _BLOCKED_STATES

    def all_gates(self) -> list[TenantGate]:
        """All registered tenant gates, sorted by tenant_id."""
        return sorted(self._gates.values(), key=lambda g: g.tenant_id)

    @property
    def tenant_count(self) -> int:
        return len(self._gates)

    def summary(self) -> dict[str, Any]:
        """Gating summary for health endpoint."""
        status_counts: dict[str, int] = {}
        for gate in self._gates.values():
            status_counts[gate.status.value] = status_counts.get(gate.status.value, 0) + 1
        return {
            "total_tenants": self.tenant_count,
            "status_counts": status_counts,
            "blocked_states": [s.value for s in _BLOCKED_STATES],
        }


def create_tenant_gating_guard(
    registry: TenantGatingRegistry,
) -> "GovernanceGuard":
    """Create a tenant gating guard for the governance guard chain.

    Blocks requests from suspended or terminated tenants.
    Unknown tenants are allowed through.
    """
    from mcoi_runtime.core.governance_guard import GovernanceGuard, GuardResult

    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "")
        if not tenant_id or tenant_id == "system":
            return GuardResult(allowed=True, guard_name="tenant_gating")

        gate = registry.get_status(tenant_id)
        if gate is None:
            # Unknown tenant — allow through (auto-provisioning compatible)
            return GuardResult(allowed=True, guard_name="tenant_gating")

        if gate.status in _BLOCKED_STATES:
            return GuardResult(
                allowed=False, guard_name="tenant_gating",
                reason=f"tenant {tenant_id} is {gate.status.value}: {gate.reason}",
            )

        return GuardResult(allowed=True, guard_name="tenant_gating")
    return GovernanceGuard("tenant_gating", check)
