"""Purpose: god-mode capability registry and registration-agreement ledger.

Governance scope: holds the static catalog of god capabilities plus the
append-only ledger of registration agreements that promote them to ARMED.
The registry alone NEVER permits invocation — that requires the engine
plus an `ActivationAgreement`.

Dependencies: god_mode contracts.

Invariants:
  - A capability cannot be registered twice with conflicting descriptors.
  - A capability is invocable only if it has at least one active registration
    agreement (i.e. recorded and not withdrawn).
  - All agreements are append-only — withdrawal is a new event, not a delete.
  - Registry mutations are thread-safe via a single lock.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Iterator

from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityState,
    RegistrationAgreement,
)


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


class GodModeRegistryError(RuntimeError):
    """Raised on registry contract violations (duplicate, unknown, etc.)."""


class GodModeRegistry:
    """In-memory registry of god capabilities and their registration agreements."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._capabilities: dict[tuple[str, str], GodCapability] = {}
        self._agreements: dict[str, RegistrationAgreement] = {}
        # capability_key → ordered list of agreement_ids (history)
        self._capability_agreements: dict[tuple[str, str], list[str]] = {}
        self._suspended: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------
    # Catalog management
    # ------------------------------------------------------------------

    def register_capability(self, capability: GodCapability) -> GodCapability:
        """Add a capability to the catalog. Idempotent on identical descriptors."""
        with self._lock:
            existing = self._capabilities.get(capability.key)
            if existing is None:
                self._capabilities[capability.key] = capability
                self._capability_agreements.setdefault(capability.key, [])
                return capability
            if existing != capability:
                raise GodModeRegistryError(
                    f"capability {capability.fqn} already registered with a different descriptor"
                )
            return existing

    def unregister_capability(self, module: str, name: str) -> bool:
        """Remove a capability and all of its registration history. Test-only.

        Returns True if removed, False if not present.
        """
        with self._lock:
            key = (module, name)
            if key not in self._capabilities:
                return False
            del self._capabilities[key]
            for aid in self._capability_agreements.pop(key, []):
                self._agreements.pop(aid, None)
            self._suspended.discard(key)
            return True

    def reset(self) -> None:
        """Clear all state — test fixture support."""
        with self._lock:
            self._capabilities.clear()
            self._agreements.clear()
            self._capability_agreements.clear()
            self._suspended.clear()

    def get_capability(self, module: str, name: str) -> GodCapability:
        with self._lock:
            cap = self._capabilities.get((module, name))
            if cap is None:
                raise GodModeRegistryError(f"capability {module}.{name} is not registered")
            return cap

    def has_capability(self, module: str, name: str) -> bool:
        with self._lock:
            return (module, name) in self._capabilities

    def list_capabilities(self) -> tuple[GodCapability, ...]:
        with self._lock:
            return tuple(
                sorted(self._capabilities.values(), key=lambda c: (c.module, c.name))
            )

    def list_modules(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted({cap.module for cap in self._capabilities.values()}))

    # ------------------------------------------------------------------
    # Registration agreements
    # ------------------------------------------------------------------

    def agree_to_register(
        self,
        *,
        module: str,
        name: str,
        actor_id: str,
        justification: str,
    ) -> RegistrationAgreement:
        """Record an operator's consent that arms the capability.

        For dual-control capabilities, the same actor cannot record two
        agreements that both count toward the dual-control quorum — distinct
        actors are required.
        """
        with self._lock:
            cap = self.get_capability(module, name)
            if len(justification.strip()) < cap.min_justification_chars:
                raise GodModeRegistryError(
                    f"justification must be at least {cap.min_justification_chars} chars"
                )
            if cap.requires_dual_control:
                active_actors = {
                    a.actor_id
                    for a in self.list_agreements(module, name)
                    if a.is_active
                }
                if actor_id in active_actors:
                    raise GodModeRegistryError(
                        f"{cap.fqn} requires dual control: actor {actor_id} already has "
                        "an active agreement; a distinct actor must record the second"
                    )
            agreement = RegistrationAgreement(
                agreement_id=f"god-reg-{uuid.uuid4().hex[:16]}",
                capability_module=module,
                capability_name=name,
                actor_id=actor_id,
                justification=justification,
                recorded_at=_utc_now_iso(),
            )
            self._agreements[agreement.agreement_id] = agreement
            self._capability_agreements.setdefault((module, name), []).append(
                agreement.agreement_id
            )
            # Re-arming clears suspension.
            self._suspended.discard((module, name))
            return agreement

    def withdraw_registration(
        self,
        *,
        agreement_id: str,
        actor_id: str,
        reason: str,
    ) -> RegistrationAgreement:
        """Withdraw an active registration agreement."""
        with self._lock:
            current = self._agreements.get(agreement_id)
            if current is None:
                raise GodModeRegistryError(f"agreement {agreement_id} not found")
            if not current.is_active:
                raise GodModeRegistryError(f"agreement {agreement_id} already withdrawn")
            if not reason.strip():
                raise GodModeRegistryError("withdrawal reason required")
            withdrawn = RegistrationAgreement(
                agreement_id=current.agreement_id,
                capability_module=current.capability_module,
                capability_name=current.capability_name,
                actor_id=current.actor_id,
                justification=current.justification,
                recorded_at=current.recorded_at,
                withdrawn_at=_utc_now_iso(),
                withdrawn_reason=f"{actor_id}: {reason.strip()}",
            )
            self._agreements[agreement_id] = withdrawn
            return withdrawn

    def get_agreement(self, agreement_id: str) -> RegistrationAgreement:
        with self._lock:
            agreement = self._agreements.get(agreement_id)
            if agreement is None:
                raise GodModeRegistryError(f"agreement {agreement_id} not found")
            return agreement

    def list_agreements(
        self, module: str, name: str
    ) -> tuple[RegistrationAgreement, ...]:
        with self._lock:
            return tuple(
                self._agreements[aid]
                for aid in self._capability_agreements.get((module, name), ())
            )

    def iter_active_agreements(
        self, module: str, name: str
    ) -> Iterator[RegistrationAgreement]:
        for agreement in self.list_agreements(module, name):
            if agreement.is_active:
                yield agreement

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def state_of(self, module: str, name: str) -> GodCapabilityState:
        with self._lock:
            cap = self._capabilities.get((module, name))
            if cap is None:
                raise GodModeRegistryError(f"capability {module}.{name} is not registered")
            if (module, name) in self._suspended:
                return GodCapabilityState.SUSPENDED
            active = [
                a for a in self.list_agreements(module, name) if a.is_active
            ]
            if not active:
                # Has there ever been one that was withdrawn?
                if self.list_agreements(module, name):
                    return GodCapabilityState.WITHDRAWN
                return GodCapabilityState.DORMANT
            if cap.requires_dual_control:
                distinct_actors = {a.actor_id for a in active}
                if len(distinct_actors) < cap.dual_control_min_actors:
                    return GodCapabilityState.PENDING_DUAL
            return GodCapabilityState.ARMED

    def is_armed(self, module: str, name: str) -> bool:
        return self.state_of(module, name) == GodCapabilityState.ARMED

    def pending_required_actors(self, module: str, name: str) -> int:
        """Return how many additional distinct actors are needed to ARM.

        Returns 0 if the capability is already ARMED, or if it doesn't
        require dual control. Returns the deficit otherwise.
        """
        with self._lock:
            cap = self.get_capability(module, name)
            if not cap.requires_dual_control:
                return 0
            active = [
                a for a in self.list_agreements(module, name) if a.is_active
            ]
            distinct_actors = {a.actor_id for a in active}
            deficit = cap.dual_control_min_actors - len(distinct_actors)
            return max(0, deficit)

    def suspend(self, module: str, name: str) -> None:
        with self._lock:
            if (module, name) not in self._capabilities:
                raise GodModeRegistryError(f"capability {module}.{name} is not registered")
            self._suspended.add((module, name))

    def resume(self, module: str, name: str) -> None:
        with self._lock:
            self._suspended.discard((module, name))


_REGISTRY: GodModeRegistry | None = None


def get_registry() -> GodModeRegistry:
    """Return the process-wide god-mode registry, lazily initialized."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = GodModeRegistry()
    return _REGISTRY


def set_registry(registry: GodModeRegistry | None) -> None:
    """Replace the process-wide registry. Test fixture only."""
    global _REGISTRY
    _REGISTRY = registry


__all__ = [
    "GodModeRegistry",
    "GodModeRegistryError",
    "get_registry",
    "set_registry",
]
