"""Purpose: event-obligation integration bridge — connects the event spine
and obligation runtime for end-to-end event-driven obligation lifecycle.
Governance scope: cross-plane integration for events and obligations.
Dependencies: event spine engine, obligation runtime engine, contracts.
Invariants:
  - Bridge methods are stateless static helpers.
  - Events create obligations, obligations emit events.
  - No silent side effects — all changes are auditable.
  - Subscription matching is deterministic.
"""

from __future__ import annotations

from datetime import datetime

from mcoi_runtime.contracts.event import (
    EventReaction,
    EventRecord,
    EventSource,
    EventSubscription,
    EventType,
)
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationRecord,
    ObligationState,
    ObligationTrigger,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .obligation_runtime import ObligationRuntimeEngine


class EventObligationBridge:
    """Static methods bridging the event spine and obligation runtime.

    Provides convenience methods for:
    - Processing an event through subscriptions to create obligations
    - Emitting obligation lifecycle events back into the spine
    - Checking for expired obligations and triggering escalation chains
    - Reconstructing causal timelines for a correlation
    """

    @staticmethod
    def process_event(
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        event: EventRecord,
        *,
        owner: ObligationOwner,
        deadline: ObligationDeadline,
        trigger: ObligationTrigger,
        description: str,
    ) -> tuple[ObligationRecord, EventRecord]:
        """Process an event: create obligation and emit obligation-created event.

        Returns (obligation, obligation_created_event).
        """
        # 1. Create obligation from event
        obl = obligation_engine.create_from_event(
            event,
            trigger=trigger,
            owner=owner,
            deadline=deadline,
            description=description,
        )

        # 2. Generate and emit obligation-created event
        obl_event = obligation_engine.obligation_event(obl, EventType.OBLIGATION_CREATED)
        spine.emit(obl_event)

        return (obl, obl_event)

    @staticmethod
    def close_and_emit(
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        obligation_id: str,
        *,
        final_state: ObligationState,
        reason: str,
        closed_by: str,
    ) -> tuple[ObligationRecord, EventRecord]:
        """Close an obligation and emit the closure event.

        Returns (updated_obligation, obligation_closed_event).
        """
        obligation_engine.close(
            obligation_id,
            final_state=final_state,
            reason=reason,
            closed_by=closed_by,
        )
        obl = obligation_engine.get_obligation(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError(f"obligation {obligation_id} not found after close")
        if obl.state != final_state:
            raise RuntimeCoreInvariantError(
                f"obligation {obligation_id} state is {obl.state}, expected {final_state}"
            )

        event_type = (
            EventType.OBLIGATION_EXPIRED
            if final_state == ObligationState.EXPIRED
            else EventType.OBLIGATION_CLOSED
        )
        evt = obligation_engine.obligation_event(obl, event_type)
        spine.emit(evt)
        return (obl, evt)

    @staticmethod
    def transfer_and_emit(
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        obligation_id: str,
        *,
        to_owner: ObligationOwner,
        reason: str,
    ) -> tuple[ObligationRecord, EventRecord]:
        """Transfer an obligation and emit the transfer event.

        Returns (updated_obligation, obligation_transferred_event).
        """
        obligation_engine.transfer(obligation_id, to_owner=to_owner, reason=reason)
        obl = obligation_engine.get_obligation(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError(f"obligation {obligation_id} not found after transfer")
        if obl.owner != to_owner:
            raise RuntimeCoreInvariantError(
                f"obligation {obligation_id} owner is {obl.owner.owner_id}, expected {to_owner.owner_id}"
            )
        evt = obligation_engine.obligation_event(obl, EventType.OBLIGATION_TRANSFERRED)
        spine.emit(evt)
        return (obl, evt)

    @staticmethod
    def escalate_and_emit(
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        obligation_id: str,
        *,
        escalated_to: ObligationOwner,
        reason: str,
        severity: str = "high",
    ) -> tuple[ObligationRecord, EventRecord]:
        """Escalate an obligation and emit the escalation event.

        Returns (updated_obligation, obligation_escalated_event).
        """
        obligation_engine.escalate(
            obligation_id,
            escalated_to=escalated_to,
            reason=reason,
            severity=severity,
        )
        obl = obligation_engine.get_obligation(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError(f"obligation {obligation_id} not found after escalate")
        if obl.state != ObligationState.ESCALATED:
            raise RuntimeCoreInvariantError(
                f"obligation {obligation_id} state is {obl.state}, expected escalated"
            )
        evt = obligation_engine.obligation_event(obl, EventType.OBLIGATION_ESCALATED)
        spine.emit(evt)
        return (obl, evt)

    @staticmethod
    def reconstruct_timeline(
        spine: EventSpineEngine,
        correlation_id: str,
    ) -> tuple[EventRecord, ...]:
        """Reconstruct the full causal timeline for a correlation ID."""
        return spine.list_events(correlation_id=correlation_id)

    @staticmethod
    def check_expired_obligations(
        obligation_engine: ObligationRuntimeEngine,
        *,
        current_time: str,
    ) -> tuple[ObligationRecord, ...]:
        """Find active/pending obligations whose deadline has passed.

        Returns obligations that should be expired or escalated.
        The caller decides the action (expire vs escalate).
        """
        open_obls = obligation_engine.list_obligations(state=ObligationState.ACTIVE)
        open_obls += obligation_engine.list_obligations(state=ObligationState.PENDING)
        expired: list[ObligationRecord] = []
        for obl in open_obls:
            due = datetime.fromisoformat(obl.deadline.due_at.replace("Z", "+00:00"))
            now = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
            if due <= now:
                expired.append(obl)
        return tuple(expired)
