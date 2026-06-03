"""Phase 2D — Tenant Gating Guard.

Purpose: Enforce tenant lifecycle states at the governance guard layer.
    Suspended/terminated tenants are hard-blocked before any business logic
    executes. Onboarding tenants may have restricted access.
Governance scope: tenant lifecycle enforcement only.
Dependencies: none (pure data structures).
Invariants:
  - Tenant status transitions are validated (no backward transitions).
  - Suspended/terminated tenants are always rejected.
  - Unknown-tenant admission is explicit and governed by registry policy.
  - Status changes are auditable via the returned TenantGate record.
"""

from __future__ import annotations

import threading
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


class TenantGatingError(ValueError):
    """Base governed error for tenant lifecycle operations."""

    error_code = "tenant_lifecycle_error"
    public_error = "tenant lifecycle request failed"
    http_status_code = 400


class TenantAlreadyRegisteredError(TenantGatingError):
    """Raised when a tenant registration collides with an existing entry."""

    error_code = "tenant_exists"
    public_error = "tenant already registered"
    http_status_code = 409

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"tenant {tenant_id} already registered")


class TenantNotRegisteredError(TenantGatingError):
    """Raised when a tenant lifecycle operation targets an unknown tenant."""

    error_code = "tenant_not_found"
    public_error = "tenant not registered"
    http_status_code = 404

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        super().__init__(f"tenant {tenant_id} not registered")


class InvalidTenantStatusTransitionError(TenantGatingError):
    """Raised when a lifecycle transition violates the allowed state graph."""

    error_code = "invalid_status_transition"
    public_error = "invalid status transition"
    http_status_code = 409

    def __init__(self, tenant_id: str, current_status: TenantStatus, new_status: TenantStatus) -> None:
        self.tenant_id = tenant_id
        self.current_status = current_status
        self.new_status = new_status
        super().__init__(
            f"invalid transition: {current_status.value} -> {new_status.value} for tenant {tenant_id}"
        )


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

    Atomic Store Doctrine (audit follow-up): ``try_transition`` is the
    optional cross-replica conditional-state-change primitive. The
    registry's ``update_status`` reads the current status, validates
    the transition, then writes — a read-validate-write race. Under
    ``self._lock`` that is single-process safe, but ``save`` is an
    unconditional UPSERT, so two replicas can both read ``active``,
    both validate (one to ``terminated``, one to ``suspended``), and
    last-write-wins — silently *un-terminating* a tenant and defeating
    the ``TERMINATED`` terminal-state invariant. When a store overrides
    ``try_transition``, the registry delegates the compare-and-set to
    it; detection uses the same MRO override-sentinel as the other
    atomic stores. See docs/ATOMIC_STORE_DOCTRINE.md.
    """

    def load(self, tenant_id: str) -> TenantGate | None:
        return None

    def save(self, gate: TenantGate) -> None:
        pass

    def load_all(self) -> list[TenantGate]:
        return []

    def try_transition(
        self,
        tenant_id: str,
        allowed_from: "frozenset[TenantStatus]",
        new_status: "TenantStatus",
        reason: str,
        gated_at: str,
    ) -> "TenantGate | None":
        """Atomic conditional status transition (cross-replica).

        Atomically set the tenant's status to ``new_status`` **iff** the
        tenant exists and its current (committed) status is in
        ``allowed_from``. Returns the updated ``TenantGate`` on success.

        Returns ``None`` for either "transition rejected" (tenant
        absent, or current status not in ``allowed_from`` — e.g. another
        replica already moved it, or it is ``TERMINATED``) **or** "this
        base class has no atomic path." The registry disambiguates via
        MRO override-detection: when the store overrides this method,
        ``None`` means *rejected* and the registry re-reads to raise the
        correct error; when it does not, the registry falls through to
        the legacy in-process read-validate-write path. This overload of
        ``None`` matches the established convention of
        ``BudgetStore.try_record_spend`` and ``RateLimitStore.try_consume``.
        """
        return None


class TenantGatingRegistry:
    """Manages tenant lifecycle states for gating decisions.

    Each tenant has a status (active, onboarding, suspended, terminated).
    Status transitions are validated — invalid transitions are rejected.
    Unknown-tenant admission is explicit and configurable.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        store: TenantGatingStore | None = None,
        default_status: TenantStatus = TenantStatus.ACTIVE,
        allow_unknown_tenants: bool = True,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._gates: dict[str, TenantGate] = {}
        self._store = store
        self._default_status = default_status
        self._allow_unknown_tenants = allow_unknown_tenants
        self._lock = threading.RLock()

    def _load_gate_locked(self, tenant_id: str) -> TenantGate | None:
        gate = self._gates.get(tenant_id)
        if gate is None and self._store is not None:
            gate = self._store.load(tenant_id)
            if gate is not None:
                self._gates[tenant_id] = gate
        return gate

    def _load_all_gates_locked(self) -> None:
        if self._store is None:
            return
        for gate in self._store.load_all():
            self._gates[gate.tenant_id] = gate

    def register(self, tenant_id: str, status: TenantStatus = TenantStatus.ONBOARDING, reason: str = "") -> TenantGate:
        """Register a new tenant with initial status."""
        with self._lock:
            if self._load_gate_locked(tenant_id) is not None:
                raise TenantAlreadyRegisteredError(tenant_id)
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

        When the backing store provides an atomic ``try_transition``
        (cross-replica conditional compare-and-set), the transition is
        delegated to it — closing the read-validate-write race where two
        replicas could both validate against a stale ``active`` read and
        last-write-wins (e.g. un-terminating a tenant). Stores without
        the override fall through to the legacy in-process path, which
        is single-process safe under ``self._lock``.
        """
        with self._lock:
            store_owned = (
                self._store is not None
                and getattr(type(self._store), "try_transition", TenantGatingStore.try_transition)
                is not TenantGatingStore.try_transition
            )
            if store_owned:
                # Compute the set of current-states from which new_status
                # is reachable, then let the store enforce the predicate
                # atomically against the committed row.
                allowed_from = frozenset(
                    s for s, targets in _VALID_TRANSITIONS.items() if new_status in targets
                )
                gate = self._store.try_transition(
                    tenant_id, allowed_from, new_status, reason, self._clock()
                )
                if gate is None:
                    # Rejected: tenant absent, or current status not in
                    # allowed_from (invalid transition, or another replica
                    # already moved it). Re-read the authoritative store
                    # row to raise the precise error.
                    current = self._store.load(tenant_id)
                    if current is not None:
                        self._gates[tenant_id] = current
                        raise InvalidTenantStatusTransitionError(
                            tenant_id, current.status, new_status
                        )
                    self._gates.pop(tenant_id, None)
                    raise TenantNotRegisteredError(tenant_id)
                self._gates[tenant_id] = gate  # refresh cache from authoritative result
                return gate

            # Legacy in-process path (no atomic store): unchanged.
            current = self._load_gate_locked(tenant_id)
            if current is None:
                raise TenantNotRegisteredError(tenant_id)

            allowed = _VALID_TRANSITIONS.get(current.status, frozenset())
            if new_status not in allowed:
                raise InvalidTenantStatusTransitionError(tenant_id, current.status, new_status)

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
        with self._lock:
            return self._load_gate_locked(tenant_id)

    def is_allowed(self, tenant_id: str) -> bool:
        """Check if a tenant is allowed to make requests.

        Unknown-tenant admission depends on registry policy.
        """
        gate = self.get_status(tenant_id)
        if gate is None:
            return self._allow_unknown_tenants
        return gate.status not in _BLOCKED_STATES

    def denial_reason(self, tenant_id: str) -> str | None:
        """Return a stable denial reason for the current tenant posture."""
        gate = self.get_status(tenant_id)
        if gate is None:
            if self._allow_unknown_tenants:
                return None
            return f"tenant {tenant_id} is not registered"

        if gate.status in _BLOCKED_STATES:
            if gate.reason:
                return f"tenant {tenant_id} is {gate.status.value}: {gate.reason}"
            return f"tenant {tenant_id} is {gate.status.value}"
        return None

    @property
    def allow_unknown_tenants(self) -> bool:
        return self._allow_unknown_tenants

    def all_gates(self) -> list[TenantGate]:
        """All registered tenant gates, sorted by tenant_id."""
        with self._lock:
            self._load_all_gates_locked()
            return sorted(self._gates.values(), key=lambda g: g.tenant_id)

    @property
    def tenant_count(self) -> int:
        with self._lock:
            self._load_all_gates_locked()
            return len(self._gates)

    def summary(self) -> dict[str, Any]:
        """Gating summary for health endpoint."""
        with self._lock:
            self._load_all_gates_locked()
            status_counts: dict[str, int] = {}
            for gate in self._gates.values():
                status_counts[gate.status.value] = status_counts.get(gate.status.value, 0) + 1
            return {
                "total_tenants": len(self._gates),
                "status_counts": status_counts,
                "blocked_states": [s.value for s in _BLOCKED_STATES],
                "allow_unknown_tenants": self._allow_unknown_tenants,
            }


def create_tenant_gating_guard(
    registry: TenantGatingRegistry,
) -> "GovernanceGuard":
    """Create a tenant gating guard for the governance guard chain.

    Blocks requests from suspended, terminated, or strict-mode unknown tenants.
    """
    from mcoi_runtime.governance.guards.chain import GovernanceGuard, GuardResult

    def check(ctx: dict[str, Any]) -> GuardResult:
        tenant_id = ctx.get("tenant_id", "")
        if not tenant_id or tenant_id == "system":
            return GuardResult(allowed=True, guard_name="tenant_gating")

        reason = registry.denial_reason(tenant_id)
        if reason is not None:
            return GuardResult(
                allowed=False, guard_name="tenant_gating",
                reason=reason,
            )

        return GuardResult(allowed=True, guard_name="tenant_gating")
    return GovernanceGuard("tenant_gating", check)
