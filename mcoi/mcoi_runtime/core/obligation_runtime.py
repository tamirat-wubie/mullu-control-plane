"""Purpose: obligation runtime — creates, tracks, transfers, escalates, and
closes obligations with full audit trail.
Governance scope: obligation plane core logic only.
Dependencies: obligation contracts, event contracts, invariant helpers.
Invariants:
  - Obligations are created from events, jobs, approvals, etc.
  - Ownership and deadlines are always tracked.
  - Transfers preserve history.
  - Closures are explicit — never silent.
  - Escalations produce typed events back into the spine.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts._base import freeze_value
from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventType,
)
from mcoi_runtime.contracts.obligation import (
    ObligationClosure,
    ObligationDeadline,
    ObligationEscalation,
    ObligationOwner,
    ObligationRecord,
    ObligationState,
    ObligationTransfer,
    ObligationTrigger,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier

_TERMINAL_STATES = (
    ObligationState.COMPLETED,
    ObligationState.EXPIRED,
    ObligationState.CANCELLED,
)


class ObligationRuntimeEngine:
    """Creates, tracks, transfers, escalates, and closes obligations.

    This engine:
    - Creates obligations from events or direct calls
    - Tracks ownership and deadlines
    - Transfers obligations between owners
    - Escalates on deadline breach or explicit request
    - Marks closure explicitly (completed, expired, cancelled)
    - Produces typed event records for spine emission
    - Maintains full transfer and escalation history
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._obligations: dict[str, ObligationRecord] = {}
        self._closures: dict[str, ObligationClosure] = {}
        self._transfers: dict[str, ObligationTransfer] = {}
        self._escalations: dict[str, ObligationEscalation] = {}
        self._event_seq: int = 0
        self._clock = clock or self._default_clock

    @staticmethod
    def _default_clock() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _now(self) -> str:
        return self._clock()

    # --- Creation ---

    def create_obligation(
        self,
        *,
        obligation_id: str | None = None,
        trigger: ObligationTrigger,
        trigger_ref_id: str,
        owner: ObligationOwner,
        deadline: ObligationDeadline,
        description: str,
        correlation_id: str,
        metadata: dict[str, object] | None = None,
    ) -> ObligationRecord:
        """Create a new obligation in PENDING state."""
        now = self._now()
        oid = obligation_id or stable_identifier("obl", {
            "trigger": trigger.value,
            "ref": trigger_ref_id,
        })
        if oid in self._obligations:
            raise RuntimeCoreInvariantError("obligation already exists")

        record = ObligationRecord(
            obligation_id=oid,
            trigger=trigger,
            trigger_ref_id=trigger_ref_id,
            state=ObligationState.PENDING,
            owner=owner,
            deadline=deadline,
            description=description,
            correlation_id=correlation_id,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._obligations[oid] = record
        return record

    def create_from_event(
        self,
        event: EventRecord,
        *,
        trigger: ObligationTrigger,
        owner: ObligationOwner,
        deadline: ObligationDeadline,
        description: str,
    ) -> ObligationRecord:
        """Create an obligation triggered by an event."""
        return self.create_obligation(
            trigger=trigger,
            trigger_ref_id=event.event_id,
            owner=owner,
            deadline=deadline,
            description=description,
            correlation_id=event.correlation_id,
            metadata={"source_event_type": event.event_type.value},
        )

    # --- Retrieval ---

    def get_obligation(self, obligation_id: str) -> ObligationRecord | None:
        ensure_non_empty_text("obligation_id", obligation_id)
        return self._obligations.get(obligation_id)

    def list_obligations(
        self,
        *,
        state: ObligationState | None = None,
        owner_id: str | None = None,
        trigger: ObligationTrigger | None = None,
    ) -> tuple[ObligationRecord, ...]:
        obls = sorted(self._obligations.values(), key=lambda o: o.obligation_id)
        if state is not None:
            obls = [o for o in obls if o.state == state]
        if owner_id is not None:
            ensure_non_empty_text("owner_id", owner_id)
            obls = [o for o in obls if o.owner.owner_id == owner_id]
        if trigger is not None:
            obls = [o for o in obls if o.trigger == trigger]
        return tuple(obls)

    # --- State transitions ---

    def activate(self, obligation_id: str) -> ObligationRecord:
        """Transition from PENDING to ACTIVE."""
        return self._transition(obligation_id, ObligationState.PENDING, ObligationState.ACTIVE)

    def _transition(
        self,
        obligation_id: str,
        expected_from: ObligationState,
        to_state: ObligationState,
    ) -> ObligationRecord:
        ensure_non_empty_text("obligation_id", obligation_id)
        obl = self._obligations.get(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError("obligation not found")
        if obl.state != expected_from:
            raise RuntimeCoreInvariantError("obligation state mismatch")
        now = self._now()
        updated = ObligationRecord(
            obligation_id=obl.obligation_id,
            trigger=obl.trigger,
            trigger_ref_id=obl.trigger_ref_id,
            state=to_state,
            owner=obl.owner,
            deadline=obl.deadline,
            description=obl.description,
            correlation_id=obl.correlation_id,
            metadata=freeze_value(dict(obl.metadata)),
            created_at=obl.created_at,
            updated_at=now,
        )
        self._obligations[obligation_id] = updated
        return updated

    # --- Closure ---

    def close(
        self,
        obligation_id: str,
        *,
        final_state: ObligationState,
        reason: str,
        closed_by: str,
    ) -> ObligationClosure:
        """Explicitly close an obligation."""
        ensure_non_empty_text("obligation_id", obligation_id)
        if final_state not in _TERMINAL_STATES:
            raise RuntimeCoreInvariantError("final_state must be terminal")
        obl = self._obligations.get(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError("obligation not found")
        if obl.state in _TERMINAL_STATES:
            raise RuntimeCoreInvariantError("obligation already closed")

        now = self._now()
        closure_id = stable_identifier("cls", {
            "obligation_id": obligation_id,
            "final_state": final_state.value,
        })

        closure = ObligationClosure(
            closure_id=closure_id,
            obligation_id=obligation_id,
            final_state=final_state,
            reason=reason,
            closed_by=closed_by,
            closed_at=now,
        )

        # Build updated obligation before writing either — atomic commit
        updated = ObligationRecord(
            obligation_id=obl.obligation_id,
            trigger=obl.trigger,
            trigger_ref_id=obl.trigger_ref_id,
            state=final_state,
            owner=obl.owner,
            deadline=obl.deadline,
            description=obl.description,
            correlation_id=obl.correlation_id,
            metadata=freeze_value(dict(obl.metadata)),
            created_at=obl.created_at,
            updated_at=now,
        )

        # Commit both atomically — both objects already constructed successfully
        self._closures[closure_id] = closure
        self._obligations[obligation_id] = updated
        return closure

    # --- Transfer ---

    def transfer(
        self,
        obligation_id: str,
        *,
        to_owner: ObligationOwner,
        reason: str,
    ) -> ObligationTransfer:
        """Transfer an obligation to a new owner."""
        ensure_non_empty_text("obligation_id", obligation_id)
        obl = self._obligations.get(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError("obligation not found")
        if obl.state in _TERMINAL_STATES:
            raise RuntimeCoreInvariantError("cannot transfer closed obligation")

        now = self._now()
        transfer_id = stable_identifier("xfr", {
            "obligation_id": obligation_id,
            "to": to_owner.owner_id,
        })

        xfr = ObligationTransfer(
            transfer_id=transfer_id,
            obligation_id=obligation_id,
            from_owner=obl.owner,
            to_owner=to_owner,
            reason=reason,
            transferred_at=now,
        )

        # Construct updated obligation BEFORE any writes (construct-then-commit)
        updated = ObligationRecord(
            obligation_id=obl.obligation_id,
            trigger=obl.trigger,
            trigger_ref_id=obl.trigger_ref_id,
            state=obl.state,
            owner=to_owner,
            deadline=obl.deadline,
            description=obl.description,
            correlation_id=obl.correlation_id,
            metadata=freeze_value(dict(obl.metadata)),
            created_at=obl.created_at,
            updated_at=now,
        )

        # Both constructed successfully — commit atomically
        self._transfers[transfer_id] = xfr
        self._obligations[obligation_id] = updated
        return xfr

    # --- Escalation ---

    def escalate(
        self,
        obligation_id: str,
        *,
        escalated_to: ObligationOwner,
        reason: str,
        severity: str = "high",
    ) -> ObligationEscalation:
        """Escalate an obligation to a new owner with severity."""
        ensure_non_empty_text("obligation_id", obligation_id)
        obl = self._obligations.get(obligation_id)
        if obl is None:
            raise RuntimeCoreInvariantError("obligation not found")
        if obl.state in _TERMINAL_STATES:
            raise RuntimeCoreInvariantError("cannot escalate closed obligation")

        now = self._now()
        esc_id = stable_identifier("esc", {
            "obligation_id": obligation_id,
            "to": escalated_to.owner_id,
        })

        esc = ObligationEscalation(
            escalation_id=esc_id,
            obligation_id=obligation_id,
            escalated_to=escalated_to,
            reason=reason,
            severity=severity,
            escalated_at=now,
        )

        # Construct updated obligation BEFORE any writes (construct-then-commit)
        updated = ObligationRecord(
            obligation_id=obl.obligation_id,
            trigger=obl.trigger,
            trigger_ref_id=obl.trigger_ref_id,
            state=ObligationState.ESCALATED,
            owner=escalated_to,
            deadline=obl.deadline,
            description=obl.description,
            correlation_id=obl.correlation_id,
            metadata=freeze_value(dict(obl.metadata)),
            created_at=obl.created_at,
            updated_at=now,
        )

        # Both constructed successfully — commit atomically
        self._escalations[esc_id] = esc
        self._obligations[obligation_id] = updated
        return esc

    # --- Event generation ---

    def obligation_event(
        self,
        obligation: ObligationRecord,
        event_type: EventType,
    ) -> EventRecord:
        """Generate a typed event for an obligation lifecycle change."""
        self._event_seq += 1
        event_id = stable_identifier("evt", {
            "obligation_id": obligation.obligation_id,
            "type": event_type.value,
            "seq": self._event_seq,
        })
        return EventRecord(
            event_id=event_id,
            event_type=event_type,
            source=EventSource.OBLIGATION_RUNTIME,
            correlation_id=obligation.correlation_id,
            payload={
                "obligation_id": obligation.obligation_id,
                "state": obligation.state.value,
                "owner_id": obligation.owner.owner_id,
                "trigger": obligation.trigger.value,
            },
            emitted_at=self._now(),
        )

    # --- History ---

    def transfer_history(self, obligation_id: str) -> tuple[ObligationTransfer, ...]:
        ensure_non_empty_text("obligation_id", obligation_id)
        return tuple(
            t for t in sorted(self._transfers.values(), key=lambda t: t.transferred_at)
            if t.obligation_id == obligation_id
        )

    def escalation_history(self, obligation_id: str) -> tuple[ObligationEscalation, ...]:
        ensure_non_empty_text("obligation_id", obligation_id)
        return tuple(
            e for e in sorted(self._escalations.values(), key=lambda e: e.escalated_at)
            if e.obligation_id == obligation_id
        )

    def closure_for(self, obligation_id: str) -> ObligationClosure | None:
        ensure_non_empty_text("obligation_id", obligation_id)
        for c in self._closures.values():
            if c.obligation_id == obligation_id:
                return c
        return None

    # --- Properties ---

    @property
    def obligation_count(self) -> int:
        return len(self._obligations)

    @property
    def open_count(self) -> int:
        return sum(
            1 for o in self._obligations.values()
            if o.state in (ObligationState.PENDING, ObligationState.ACTIVE, ObligationState.ESCALATED)
        )

    @property
    def transfer_count(self) -> int:
        return len(self._transfers)

    @property
    def escalation_count(self) -> int:
        return len(self._escalations)

    @property
    def closure_count(self) -> int:
        return len(self._closures)

    # --- Snapshot / restore ---

    def state_hash(self) -> str:
        """Compute a deterministic SHA-256 hash of all obligation state.

        Includes obligations, closures, transfers, and escalations to ensure
        checkpoint verification catches inconsistencies in any collection.
        """
        state_map = {
            "obligations": {
                oid: o.state.value
                for oid, o in sorted(self._obligations.items())
            },
            "closures": sorted(self._closures.keys()),
            "transfers": sorted(self._transfers.keys()),
            "escalations": sorted(self._escalations.keys()),
        }
        digest_input = json.dumps(state_map, sort_keys=True).encode()
        return hashlib.sha256(digest_input).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Capture the complete obligation runtime state as a serializable dictionary."""
        return {
            "obligations": {oid: o.to_dict() for oid, o in self._obligations.items()},
            "closures": {cid: c.to_dict() for cid, c in self._closures.items()},
            "transfers": {tid: t.to_dict() for tid, t in self._transfers.items()},
            "escalations": {eid: e.to_dict() for eid, e in self._escalations.items()},
            "event_seq": self._event_seq,
            "state_hash": self.state_hash(),
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Restore obligation runtime state from a snapshot dictionary.

        Clears all current state and rebuilds from the snapshot.
        Atomic: on any reconstruction error, pre-restore state is rolled back.
        """
        # Capture pre-restore state for rollback
        pre_obligations = dict(self._obligations)
        pre_closures = dict(self._closures)
        pre_transfers = dict(self._transfers)
        pre_escalations = dict(self._escalations)
        pre_event_seq = self._event_seq

        self._obligations.clear()
        self._closures.clear()
        self._transfers.clear()
        self._escalations.clear()

        try:
            for oid, odict in snapshot.get("obligations", {}).items():
                # Rebuild nested contract objects
                odict = dict(odict)
                odict["state"] = ObligationState(odict["state"])
                odict["trigger"] = ObligationTrigger(odict["trigger"])
                odict["owner"] = ObligationOwner(**odict["owner"])
                odict["deadline"] = ObligationDeadline(**odict["deadline"])
                self._obligations[oid] = ObligationRecord(**odict)

            for cid, cdict in snapshot.get("closures", {}).items():
                cdict = dict(cdict)
                cdict["final_state"] = ObligationState(cdict["final_state"])
                self._closures[cid] = ObligationClosure(**cdict)

            for tid, tdict in snapshot.get("transfers", {}).items():
                tdict = dict(tdict)
                tdict["from_owner"] = ObligationOwner(**tdict["from_owner"])
                tdict["to_owner"] = ObligationOwner(**tdict["to_owner"])
                self._transfers[tid] = ObligationTransfer(**tdict)

            for eid, edict in snapshot.get("escalations", {}).items():
                edict = dict(edict)
                edict["escalated_to"] = ObligationOwner(**edict["escalated_to"])
                self._escalations[eid] = ObligationEscalation(**edict)

            if "event_seq" not in snapshot:
                raise RuntimeCoreInvariantError(
                    "snapshot missing required field 'event_seq' — "
                    "cannot restore without event sequence counter"
                )
            self._event_seq = snapshot["event_seq"]
        except Exception:
            # Rollback to pre-restore state
            self._obligations.clear()
            self._obligations.update(pre_obligations)
            self._closures.clear()
            self._closures.update(pre_closures)
            self._transfers.clear()
            self._transfers.update(pre_transfers)
            self._escalations.clear()
            self._escalations.update(pre_escalations)
            self._event_seq = pre_event_seq
            raise
