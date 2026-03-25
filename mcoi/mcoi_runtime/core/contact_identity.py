"""Purpose: contact / identity graph engine.
Governance scope: identity registry, channel handle management,
    identity linking, contact preferences, availability tracking,
    escalation chain management, identity resolution, and routing.
Dependencies: contact_identity contracts, core invariants.
Invariants:
  - No duplicate IDs in any store.
  - Handles must reference existing identities.
  - Escalation targets must exist.
  - Routing decisions are immutable audit records.
  - Deterministic routing order (preference level → creation order).
  - State hash includes all stores.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.contact_identity import (
    AvailabilityState,
    AvailabilityWindow,
    ChannelHandle,
    ChannelPreferenceLevel,
    ContactPreferenceRecord,
    EscalationChainRecord,
    EscalationMode,
    IdentityLink,
    IdentityRecord,
    IdentityResolutionRecord,
    IdentityRoutingDecision,
    IdentityType,
)
from ..contracts.communication_surface import ChannelType
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Preference level ordering for routing (lower = more preferred)
_PREF_ORDER = {
    ChannelPreferenceLevel.PRIMARY: 0,
    ChannelPreferenceLevel.SECONDARY: 1,
    ChannelPreferenceLevel.EMERGENCY_ONLY: 2,
    ChannelPreferenceLevel.DISABLED: 99,
}


class ContactIdentityEngine:
    """Contact and identity graph substrate.

    Manages identities, channel handles, links, preferences,
    availability, escalation chains, resolution, and routing.
    """

    def __init__(self) -> None:
        self._identities: dict[str, IdentityRecord] = {}
        self._handles: dict[str, ChannelHandle] = {}
        self._links: dict[str, IdentityLink] = {}
        self._preferences: dict[str, ContactPreferenceRecord] = {}  # keyed by identity_id
        self._availability: dict[str, AvailabilityWindow] = {}  # keyed by identity_id
        self._escalation_chains: dict[str, EscalationChainRecord] = {}
        self._resolutions: dict[str, IdentityResolutionRecord] = {}
        self._routing_history: list[IdentityRoutingDecision] = []

    # ------------------------------------------------------------------
    # Identity CRUD
    # ------------------------------------------------------------------

    def add_identity(self, record: IdentityRecord) -> IdentityRecord:
        """Register an identity. Rejects duplicates."""
        if not isinstance(record, IdentityRecord):
            raise RuntimeCoreInvariantError("record must be an IdentityRecord")
        if record.identity_id in self._identities:
            raise RuntimeCoreInvariantError(f"duplicate identity_id: {record.identity_id}")
        self._identities[record.identity_id] = record
        return record

    def get_identity(self, identity_id: str) -> IdentityRecord | None:
        return self._identities.get(identity_id)

    def list_identities(
        self,
        *,
        identity_type: IdentityType | None = None,
        organization_id: str | None = None,
        team_id: str | None = None,
    ) -> tuple[IdentityRecord, ...]:
        """List identities with optional filters."""
        results = list(self._identities.values())
        if identity_type is not None:
            results = [r for r in results if r.identity_type == identity_type]
        if organization_id is not None:
            results = [r for r in results if r.organization_id == organization_id]
        if team_id is not None:
            results = [r for r in results if r.team_id == team_id]
        return tuple(results)

    # ------------------------------------------------------------------
    # Channel handle management
    # ------------------------------------------------------------------

    def add_channel_handle(self, handle: ChannelHandle) -> ChannelHandle:
        """Add a channel handle. Identity must exist. Rejects duplicate handle_id."""
        if not isinstance(handle, ChannelHandle):
            raise RuntimeCoreInvariantError("handle must be a ChannelHandle")
        if handle.handle_id in self._handles:
            raise RuntimeCoreInvariantError(f"duplicate handle_id: {handle.handle_id}")
        if handle.identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"identity not found: {handle.identity_id}")
        self._handles[handle.handle_id] = handle
        return handle

    def get_handle(self, handle_id: str) -> ChannelHandle | None:
        return self._handles.get(handle_id)

    def list_handles_for_identity(
        self,
        identity_id: str,
        *,
        channel_type: ChannelType | None = None,
        exclude_disabled: bool = False,
    ) -> tuple[ChannelHandle, ...]:
        """List handles for an identity, optionally filtered."""
        results = [h for h in self._handles.values() if h.identity_id == identity_id]
        if channel_type is not None:
            results = [h for h in results if h.channel_type == channel_type]
        if exclude_disabled:
            results = [h for h in results if h.preference_level != ChannelPreferenceLevel.DISABLED]
        # Sort by preference level then handle_id for determinism
        results.sort(key=lambda h: (_PREF_ORDER.get(h.preference_level, 50), h.handle_id))
        return tuple(results)

    # ------------------------------------------------------------------
    # Identity linking
    # ------------------------------------------------------------------

    def link_identities(self, link: IdentityLink) -> IdentityLink:
        """Create an explicit link between two identities. Both must exist."""
        if not isinstance(link, IdentityLink):
            raise RuntimeCoreInvariantError("link must be an IdentityLink")
        if link.link_id in self._links:
            raise RuntimeCoreInvariantError(f"duplicate link_id: {link.link_id}")
        if link.from_identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"from_identity not found: {link.from_identity_id}")
        if link.to_identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"to_identity not found: {link.to_identity_id}")
        self._links[link.link_id] = link
        return link

    def get_links_for(self, identity_id: str) -> tuple[IdentityLink, ...]:
        """Get all links involving an identity (from or to)."""
        return tuple(
            lk for lk in self._links.values()
            if lk.from_identity_id == identity_id or lk.to_identity_id == identity_id
        )

    # ------------------------------------------------------------------
    # Contact preferences
    # ------------------------------------------------------------------

    def set_contact_preference(self, pref: ContactPreferenceRecord) -> ContactPreferenceRecord:
        """Set contact preference for an identity. Replaces any existing."""
        if not isinstance(pref, ContactPreferenceRecord):
            raise RuntimeCoreInvariantError("pref must be a ContactPreferenceRecord")
        if pref.identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"identity not found: {pref.identity_id}")
        self._preferences[pref.identity_id] = pref
        return pref

    def get_contact_preference(self, identity_id: str) -> ContactPreferenceRecord | None:
        return self._preferences.get(identity_id)

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def set_availability(self, window: AvailabilityWindow) -> AvailabilityWindow:
        """Set current availability for an identity. Replaces any existing."""
        if not isinstance(window, AvailabilityWindow):
            raise RuntimeCoreInvariantError("window must be an AvailabilityWindow")
        if window.identity_id not in self._identities:
            raise RuntimeCoreInvariantError(f"identity not found: {window.identity_id}")
        self._availability[window.identity_id] = window
        return window

    def get_availability(self, identity_id: str) -> AvailabilityWindow | None:
        return self._availability.get(identity_id)

    # ------------------------------------------------------------------
    # Escalation chains
    # ------------------------------------------------------------------

    def add_escalation_chain(self, chain: EscalationChainRecord) -> EscalationChainRecord:
        """Register an escalation chain. All targets must exist."""
        if not isinstance(chain, EscalationChainRecord):
            raise RuntimeCoreInvariantError("chain must be an EscalationChainRecord")
        if chain.chain_id in self._escalation_chains:
            raise RuntimeCoreInvariantError(f"duplicate chain_id: {chain.chain_id}")
        for tid in chain.target_identity_ids:
            if tid not in self._identities:
                raise RuntimeCoreInvariantError(f"escalation target not found: {tid}")
        self._escalation_chains[chain.chain_id] = chain
        return chain

    def get_escalation_chain(self, chain_id: str) -> EscalationChainRecord | None:
        return self._escalation_chains.get(chain_id)

    def list_escalation_chains(self) -> tuple[EscalationChainRecord, ...]:
        return tuple(self._escalation_chains.values())

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    def resolve_identity(
        self,
        source_ref: str,
        source_type: str,
    ) -> IdentityResolutionRecord | None:
        """Resolve an external reference to a canonical identity.

        Searches handles by address, then returns the highest-confidence
        match. Returns None if no match found.
        """
        # Search handles for matching address
        matching_handles = [
            h for h in self._handles.values()
            if h.address == source_ref
        ]
        if not matching_handles:
            return None

        # Pick the first match (deterministic by handle_id sort)
        matching_handles.sort(key=lambda h: h.handle_id)
        best = matching_handles[0]

        now = _now_iso()
        resolution = IdentityResolutionRecord(
            resolution_id=stable_identifier("res", {"ref": source_ref, "type": source_type}),
            resolved_identity_id=best.identity_id,
            source_ref=source_ref,
            source_type=source_type,
            confidence=1.0 if best.verified else 0.7,
            resolved_at=now,
        )
        self._resolutions[resolution.resolution_id] = resolution
        return resolution

    def get_resolution(self, resolution_id: str) -> IdentityResolutionRecord | None:
        return self._resolutions.get(resolution_id)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_contact(
        self,
        identity_id: str,
        *,
        urgency: str = "normal",
    ) -> IdentityRoutingDecision | None:
        """Route to the best channel handle for an identity.

        Considers: preference level, availability, blocked channels.
        Returns None if no routable handle exists.
        """
        if identity_id not in self._identities:
            return None

        handles = list(self.list_handles_for_identity(identity_id, exclude_disabled=True))
        if not handles:
            return None

        # Filter by blocked channels
        pref = self._preferences.get(identity_id)
        blocked = set(pref.blocked_channels) if pref else set()
        handles = [h for h in handles if h.channel_type not in blocked]
        if not handles:
            return None

        # For urgent/emergency, include emergency-only handles; otherwise exclude them
        if urgency != "emergency":
            non_emergency = [h for h in handles if h.preference_level != ChannelPreferenceLevel.EMERGENCY_ONLY]
            if non_emergency:
                handles = non_emergency

        # Check availability — if unavailable, skip to emergency-only or return None
        avail = self._availability.get(identity_id)
        if avail and avail.state == AvailabilityState.UNAVAILABLE and urgency != "emergency":
            return None

        # Already sorted by preference level
        selected = handles[0]
        fallbacks = tuple(h.handle_id for h in handles[1:])

        now = _now_iso()
        reason = f"Best available handle for {urgency} contact"
        decision = IdentityRoutingDecision(
            decision_id=stable_identifier("route", {"iid": identity_id, "ts": now}),
            target_identity_id=identity_id,
            selected_handle_id=selected.handle_id,
            reason=reason,
            fallback_handle_ids=fallbacks,
            created_at=now,
        )
        self._routing_history.append(decision)
        return decision

    def route_escalation(
        self,
        chain_id: str,
    ) -> tuple[IdentityRoutingDecision, ...]:
        """Route escalation through a chain, producing routing decisions.

        For SEQUENTIAL: routes to each available target in order.
        For PARALLEL/EMERGENCY_BROADCAST: routes to all targets.
        Skips unavailable targets in SEQUENTIAL mode.
        """
        chain = self._escalation_chains.get(chain_id)
        if chain is None:
            return ()

        decisions: list[IdentityRoutingDecision] = []
        now = _now_iso()

        for idx, tid in enumerate(chain.target_identity_ids):
            # Check availability for sequential mode
            if chain.mode == EscalationMode.SEQUENTIAL:
                avail = self._availability.get(tid)
                if avail and avail.state == AvailabilityState.UNAVAILABLE:
                    continue

            # Find best handle for this target
            handles = list(self.list_handles_for_identity(tid, exclude_disabled=True))
            if not handles:
                continue

            selected = handles[0]
            fallbacks = tuple(h.handle_id for h in handles[1:])

            decision = IdentityRoutingDecision(
                decision_id=stable_identifier("esc-route", {"chain": chain_id, "idx": idx, "ts": now}),
                target_identity_id=tid,
                selected_handle_id=selected.handle_id,
                reason=f"Escalation chain '{chain.name}' step {idx + 1} ({chain.mode.value})",
                fallback_handle_ids=fallbacks,
                created_at=now,
            )
            decisions.append(decision)
            self._routing_history.append(decision)

            # For sequential, stop at first available
            if chain.mode == EscalationMode.SEQUENTIAL:
                break

        return tuple(decisions)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def identity_count(self) -> int:
        return len(self._identities)

    @property
    def handle_count(self) -> int:
        return len(self._handles)

    @property
    def link_count(self) -> int:
        return len(self._links)

    @property
    def chain_count(self) -> int:
        return len(self._escalation_chains)

    @property
    def resolution_count(self) -> int:
        return len(self._resolutions)

    @property
    def routing_decision_count(self) -> int:
        return len(self._routing_history)

    def state_hash(self) -> str:
        """Deterministic hash over all stores."""
        parts = []
        parts.extend(f"id:{k}" for k in sorted(self._identities))
        parts.extend(f"hd:{k}" for k in sorted(self._handles))
        parts.extend(f"lk:{k}" for k in sorted(self._links))
        parts.extend(f"pf:{k}" for k in sorted(self._preferences))
        parts.extend(f"av:{k}" for k in sorted(self._availability))
        parts.extend(f"ec:{k}" for k in sorted(self._escalation_chains))
        parts.extend(f"rs:{k}" for k in sorted(self._resolutions))
        parts.append(f"rt:{len(self._routing_history)}")
        return sha256("|".join(parts).encode()).hexdigest()
