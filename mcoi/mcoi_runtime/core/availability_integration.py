"""Purpose: availability integration bridge.
Governance scope: composing human availability, calendar, meeting, and SLA
    decisions with work campaigns, portfolio scheduling, contact identity,
    communication surface, memory mesh, and operational graph.
Dependencies: availability engine, portfolio engine, work_campaign engine,
    event_spine, memory_mesh, core invariants.
Invariants:
  - Every availability operation emits events.
  - Availability state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..contracts.availability import (
    AvailabilityResolution,
    AvailabilityRoutingDecision,
    AvailabilityWindow,
    ResponseExpectation,
    WindowType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .availability import AvailabilityEngine
from .event_spine import EventSpineEngine
from .memory_mesh import MemoryMeshEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-aint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class AvailabilityIntegration:
    """Integration bridge for availability with all platform layers."""

    def __init__(
        self,
        availability_engine: AvailabilityEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(availability_engine, AvailabilityEngine):
            raise RuntimeCoreInvariantError(
                "availability_engine must be an AvailabilityEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError(
                "memory_engine must be a MemoryMeshEngine"
            )
        self._availability = availability_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Contact resolution
    # ------------------------------------------------------------------

    def resolve_contact_window_for_identity(
        self,
        identity_ref: str,
        *,
        priority: str = "normal",
        channel: str = "",
        at_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Resolve whether and when to contact an identity.

        Returns the routing decision plus the next available window
        if contact is not allowed now.
        """
        decision = self._availability.contact_allowed_now(
            identity_ref, priority=priority, channel=channel, at_time=at_time,
        )

        allowed_now = decision.resolution in (
            AvailabilityResolution.AVAILABLE_NOW,
            AvailabilityResolution.EMERGENCY_OVERRIDE,
        )

        result: dict[str, Any] = {
            "identity_ref": identity_ref,
            "decision": decision,
            "resolution": decision.resolution.value,
            "allowed_now": allowed_now,
            "reason": decision.reason,
            "next_window": None,
            "contact_at": (at_time or datetime.now(timezone.utc)).isoformat() if allowed_now else "",
        }

        if not allowed_now:
            window = self._availability.next_contact_window(
                identity_ref, after=at_time,
            )
            result["next_window"] = window
            result["contact_at"] = window.starts_at if window else ""

        _emit(self._events, "contact_window_resolved", {
            "identity_ref": identity_ref,
            "resolution": decision.resolution.value,
            "allowed_now": result["allowed_now"],
        }, identity_ref)

        return result

    def resolve_escalation_window_for_obligation(
        self,
        identity_ref: str,
        obligation_id: str,
        *,
        priority: str = "urgent",
        at_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Resolve contact window for an obligation escalation.

        Escalations use higher priority (urgent by default) and always
        compute a fallback window if not available now.
        """
        decision = self._availability.contact_allowed_now(
            identity_ref, priority=priority, at_time=at_time,
        )

        result: dict[str, Any] = {
            "identity_ref": identity_ref,
            "obligation_id": obligation_id,
            "decision": decision,
            "resolution": decision.resolution.value,
            "escalation_allowed": decision.resolution in (
                AvailabilityResolution.AVAILABLE_NOW,
                AvailabilityResolution.EMERGENCY_OVERRIDE,
            ),
            "reason": decision.reason,
        }

        # Always compute SLA deadline
        sla_info = self._availability.resolve_response_deadline(
            identity_ref, sent_at=at_time,
        )
        result["sla"] = sla_info

        if not result["escalation_allowed"]:
            window = self._availability.next_contact_window(
                identity_ref, after=at_time,
            )
            result["next_window"] = window
            result["contact_at"] = window.starts_at if window else ""
        else:
            result["next_window"] = None
            result["contact_at"] = (at_time or datetime.now(timezone.utc)).isoformat()

        _emit(self._events, "escalation_window_resolved", {
            "identity_ref": identity_ref,
            "obligation_id": obligation_id,
            "resolution": decision.resolution.value,
        }, obligation_id)

        return result

    def resolve_campaign_wait_until(
        self,
        identity_ref: str,
        campaign_id: str,
        *,
        priority: str = "normal",
        at_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Resolve when a campaign waiting on a human can proceed.

        Checks availability and returns a wait-until timestamp.
        """
        decision = self._availability.contact_allowed_now(
            identity_ref, priority=priority, at_time=at_time,
        )

        can_proceed = decision.resolution in (
            AvailabilityResolution.AVAILABLE_NOW,
            AvailabilityResolution.EMERGENCY_OVERRIDE,
        )

        result: dict[str, Any] = {
            "identity_ref": identity_ref,
            "campaign_id": campaign_id,
            "can_proceed_now": can_proceed,
            "resolution": decision.resolution.value,
            "reason": decision.reason,
        }

        if can_proceed:
            result["wait_until"] = ""
            result["next_window"] = None
        else:
            window = self._availability.next_contact_window(
                identity_ref, after=at_time,
            )
            result["wait_until"] = window.starts_at if window else ""
            result["next_window"] = window

        _emit(self._events, "campaign_wait_resolved", {
            "identity_ref": identity_ref,
            "campaign_id": campaign_id,
            "can_proceed": can_proceed,
        }, campaign_id)

        return result

    # ------------------------------------------------------------------
    # Portfolio + availability integration
    # ------------------------------------------------------------------

    def resolve_portfolio_schedule_with_availability(
        self,
        portfolio_id: str,
        campaign_id: str,
        participant_refs: list[str],
        *,
        priority: str = "normal",
        at_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Check availability of all participants before scheduling a campaign.

        Returns availability status per participant and an overall go/no-go.
        """
        now = at_time or datetime.now(timezone.utc)
        participant_results: list[dict[str, Any]] = []
        all_available = True
        blocking_participants: list[str] = []

        for pid in participant_refs:
            decision = self._availability.contact_allowed_now(
                pid, priority=priority, at_time=now,
            )
            available = decision.resolution in (
                AvailabilityResolution.AVAILABLE_NOW,
                AvailabilityResolution.EMERGENCY_OVERRIDE,
            )
            entry: dict[str, Any] = {
                "identity_ref": pid,
                "available": available,
                "resolution": decision.resolution.value,
                "reason": decision.reason,
            }
            if not available:
                all_available = False
                blocking_participants.append(pid)
                window = self._availability.next_contact_window(pid, after=now)
                entry["next_window"] = window
                entry["available_at"] = window.starts_at if window else ""
            else:
                entry["next_window"] = None
                entry["available_at"] = ""
            participant_results.append(entry)

        # Find earliest time all are available
        earliest_all = ""
        if not all_available:
            latest_available_at = ""
            for pr in participant_results:
                if not pr["available"]:
                    avail_at = pr.get("available_at", "")
                    if avail_at and (not latest_available_at or avail_at > latest_available_at):
                        latest_available_at = avail_at
            earliest_all = latest_available_at

        result: dict[str, Any] = {
            "portfolio_id": portfolio_id,
            "campaign_id": campaign_id,
            "all_available": all_available,
            "blocking_participants": blocking_participants,
            "participant_results": participant_results,
            "earliest_all_available": earliest_all,
        }

        _emit(self._events, "portfolio_availability_check", {
            "portfolio_id": portfolio_id,
            "campaign_id": campaign_id,
            "all_available": all_available,
            "blocking_count": len(blocking_participants),
        }, portfolio_id)

        return result

    # ------------------------------------------------------------------
    # Channel choice
    # ------------------------------------------------------------------

    def resolve_channel_choice_by_time(
        self,
        identity_ref: str,
        available_channels: list[str],
        *,
        priority: str = "normal",
        at_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Choose the best channel based on time-of-day and availability.

        Tests each channel against the identity's availability and
        returns the first allowed one, or defers if none are allowed.
        """
        now = at_time or datetime.now(timezone.utc)
        channel_results: list[dict[str, Any]] = []
        chosen_channel = ""

        for ch in available_channels:
            decision = self._availability.contact_allowed_now(
                identity_ref, priority=priority, channel=ch, at_time=now,
            )
            allowed = decision.resolution in (
                AvailabilityResolution.AVAILABLE_NOW,
                AvailabilityResolution.EMERGENCY_OVERRIDE,
            )
            channel_results.append({
                "channel": ch,
                "allowed": allowed,
                "resolution": decision.resolution.value,
                "reason": decision.reason,
            })
            if allowed and not chosen_channel:
                chosen_channel = ch

        deferred = not bool(chosen_channel)
        result: dict[str, Any] = {
            "identity_ref": identity_ref,
            "chosen_channel": chosen_channel,
            "channel_results": channel_results,
            "deferred": deferred,
            "next_window": None,
            "contact_at": "",
        }

        if deferred:
            window = self._availability.next_contact_window(
                identity_ref, after=now,
            )
            result["next_window"] = window
            result["contact_at"] = window.starts_at if window else ""

        _emit(self._events, "channel_choice_resolved", {
            "identity_ref": identity_ref,
            "chosen_channel": chosen_channel,
            "deferred": result["deferred"],
        }, identity_ref)

        return result

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_availability_to_memory_mesh(
        self, identity_ref: str,
    ) -> MemoryRecord:
        """Persist availability state to memory mesh."""
        now = _now_iso()
        bh = self._availability.get_business_hours(identity_ref)
        records = self._availability.get_availability(identity_ref)
        meetings = self._availability.get_meetings_for_identity(identity_ref)
        sla = self._availability.get_response_sla(identity_ref)

        content: dict[str, Any] = {
            "identity_ref": identity_ref,
            "has_business_hours": bh is not None,
            "availability_record_count": len(records),
            "meeting_count": len(meetings),
            "has_sla": sla is not None,
        }
        if bh:
            content["business_hours"] = {
                "weekday_start": bh.weekday_start_hour,
                "weekday_end": bh.weekday_end_hour,
                "weekend_available": bh.weekend_available,
                "quiet_start": bh.quiet_start_hour,
                "quiet_end": bh.quiet_end_hour,
                "timezone": bh.timezone,
            }
        if sla:
            content["sla"] = {
                "expectation": sla.expectation.value,
                "max_response_seconds": sla.max_response_seconds,
                "escalation_after_seconds": sla.escalation_after_seconds,
            }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-avail", {
                "id": identity_ref,
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=identity_ref,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Availability state: {identity_ref}",
            content=content,
            source_ids=(identity_ref,),
            tags=("availability", "state"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "availability_attached_to_memory", {
            "identity_ref": identity_ref,
            "memory_id": mem.memory_id,
        }, identity_ref)

        return mem

    def attach_availability_to_graph(
        self, identity_ref: str,
    ) -> dict[str, Any]:
        """Return availability state suitable for operational graph consumption."""
        bh = self._availability.get_business_hours(identity_ref)
        records = self._availability.get_availability(identity_ref)
        meetings = self._availability.get_meetings_for_identity(identity_ref)
        sla = self._availability.get_response_sla(identity_ref)
        windows = self._availability.get_windows(identity_ref)
        conflicts = self._availability.find_conflicts(identity_ref)
        decisions = self._availability.get_routing_decisions(identity_ref)

        result: dict[str, Any] = {
            "identity_ref": identity_ref,
            "business_hours": None,
            "availability_records": len(records),
            "meetings": len(meetings),
            "windows": len(windows),
            "conflicts": len(conflicts),
            "routing_decisions": len(decisions),
            "has_sla": sla is not None,
        }

        if bh:
            result["business_hours"] = {
                "weekday_start": bh.weekday_start_hour,
                "weekday_end": bh.weekday_end_hour,
                "weekend_available": bh.weekend_available,
                "quiet_start": bh.quiet_start_hour,
                "quiet_end": bh.quiet_end_hour,
                "emergency_override": bh.emergency_override,
                "timezone": bh.timezone,
            }

        if sla:
            result["sla"] = {
                "expectation": sla.expectation.value,
                "max_response_seconds": sla.max_response_seconds,
                "escalation_after_seconds": sla.escalation_after_seconds,
                "escalation_target": sla.escalation_target,
            }

        return result
