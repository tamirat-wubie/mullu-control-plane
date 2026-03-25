"""Purpose: reactive orchestration integration bridge — connects the reaction
engine to the event spine, obligation runtime, and decision gating subsystems.
Governance scope: cross-plane integration for reactive orchestration.
Dependencies: reaction engine, event spine, obligation runtime, contracts.
Invariants:
  - Bridge methods are stateless static helpers.
  - Every reaction target is dispatched through existing engines.
  - No silent side effects — all changes are auditable.
  - Decision gating is mandatory for all reactions.
"""

from __future__ import annotations

from typing import Callable

from mcoi_runtime.contracts.event import (
    EventRecord,
    EventSource,
    EventType,
)
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationRecord,
    ObligationState,
    ObligationTrigger,
)
from mcoi_runtime.contracts.reaction import (
    ReactionDecision,
    ReactionExecutionRecord,
    ReactionGateResult,
    ReactionRule,
    ReactionTargetKind,
    ReactionVerdict,
)
from .event_obligation_integration import EventObligationBridge
from .event_spine import EventSpineEngine
from .invariants import stable_identifier
from .obligation_runtime import ObligationRuntimeEngine
from .reaction_engine import ReactionEngine


class ReactionBridge:
    """Static methods bridging the reaction engine to the wider runtime.

    Provides convenience methods for:
    - Processing an event through the full reactive pipeline
    - Dispatching executed reactions to target engines
    - Building gating callbacks that compose simulation/utility/meta checks
    - Checking for expired obligations and triggering reactive escalation
    """

    @staticmethod
    def process_event(
        reaction_engine: ReactionEngine,
        spine: EventSpineEngine,
        event: EventRecord,
    ) -> ReactionDecision:
        """Feed an event through the reaction engine.

        The event should already be in the spine.  This method runs the
        full reaction cycle: match rules → gate → record decisions.
        """
        return reaction_engine.react(event)

    @staticmethod
    def dispatch_obligation_reactions(
        decision: ReactionDecision,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        *,
        default_owner: ObligationOwner,
        default_deadline: ObligationDeadline,
    ) -> tuple[ObligationRecord, ...]:
        """Dispatch all executed CREATE_OBLIGATION reactions from a decision.

        Returns the obligations that were created.
        """
        created: list[ObligationRecord] = []
        for exe in decision.executions:
            if not exe.executed:
                continue
            if exe.target.kind != ReactionTargetKind.CREATE_OBLIGATION:
                continue
            # Determine trigger from event type
            trigger = _infer_trigger(exe.event_id, exe.target)
            event = spine.get_event(exe.event_id)
            if event is None:
                continue

            obl, _evt = EventObligationBridge.process_event(
                spine,
                obligation_engine,
                event,
                owner=default_owner,
                deadline=default_deadline,
                trigger=trigger,
                description=f"reactive obligation from rule {exe.rule_id}",
            )
            created.append(obl)
        return tuple(created)

    @staticmethod
    def dispatch_escalation_reactions(
        decision: ReactionDecision,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        *,
        escalation_owner: ObligationOwner,
    ) -> tuple[ObligationRecord, ...]:
        """Dispatch all executed ESCALATE reactions from a decision.

        Finds obligations referenced in the target and escalates them.
        """
        escalated: list[ObligationRecord] = []
        for exe in decision.executions:
            if not exe.executed:
                continue
            if exe.target.kind != ReactionTargetKind.ESCALATE:
                continue
            obl_id = exe.target.target_ref_id
            obl = obligation_engine.get_obligation(obl_id)
            if obl is None:
                continue
            updated, _evt = EventObligationBridge.escalate_and_emit(
                spine,
                obligation_engine,
                obl_id,
                escalated_to=escalation_owner,
                reason=f"reactive escalation from rule {exe.rule_id}",
                severity="high",
            )
            escalated.append(updated)
        return tuple(escalated)

    @staticmethod
    def dispatch_close_reactions(
        decision: ReactionDecision,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
    ) -> tuple[ObligationRecord, ...]:
        """Dispatch all executed CLOSE_OBLIGATION reactions from a decision."""
        closed: list[ObligationRecord] = []
        for exe in decision.executions:
            if not exe.executed:
                continue
            if exe.target.kind != ReactionTargetKind.CLOSE_OBLIGATION:
                continue
            obl_id = exe.target.target_ref_id
            obl = obligation_engine.get_obligation(obl_id)
            if obl is None:
                continue
            updated, _evt = EventObligationBridge.close_and_emit(
                spine,
                obligation_engine,
                obl_id,
                final_state=ObligationState.COMPLETED,
                reason=f"reactive closure from rule {exe.rule_id}",
                closed_by="reaction_engine",
            )
            closed.append(updated)
        return tuple(closed)

    @staticmethod
    def dispatch_transfer_reactions(
        decision: ReactionDecision,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        *,
        transfer_to: ObligationOwner,
    ) -> tuple[ObligationRecord, ...]:
        """Dispatch all executed TRANSFER_OBLIGATION reactions from a decision."""
        transferred: list[ObligationRecord] = []
        for exe in decision.executions:
            if not exe.executed:
                continue
            if exe.target.kind != ReactionTargetKind.TRANSFER_OBLIGATION:
                continue
            obl_id = exe.target.target_ref_id
            obl = obligation_engine.get_obligation(obl_id)
            if obl is None:
                continue
            updated, _evt = EventObligationBridge.transfer_and_emit(
                spine,
                obligation_engine,
                obl_id,
                to_owner=transfer_to,
                reason=f"reactive transfer from rule {exe.rule_id}",
            )
            transferred.append(updated)
        return tuple(transferred)

    @staticmethod
    def dispatch_all(
        decision: ReactionDecision,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        *,
        default_owner: ObligationOwner,
        default_deadline: ObligationDeadline,
        escalation_owner: ObligationOwner | None = None,
        transfer_to: ObligationOwner | None = None,
    ) -> dict[str, tuple[object, ...]]:
        """Dispatch all executed reactions from a decision by target kind.

        Returns a dict keyed by target kind with tuples of results.
        This is the unified dispatcher that routes to kind-specific handlers.
        Unhandled kinds (NOTIFY, RESUME_JOB, ACTIVATE_WORKFLOW, CREATE_INCIDENT,
        REQUEST_APPROVAL, CUSTOM) are collected but not dispatched — the caller
        must handle them via the returned dict.
        """
        results: dict[str, list[object]] = {}
        for exe in decision.executions:
            if not exe.executed:
                continue
            kind = exe.target.kind.value
            if kind not in results:
                results[kind] = []

        # Dispatch obligation-creation reactions
        created = ReactionBridge.dispatch_obligation_reactions(
            decision, spine, obligation_engine,
            default_owner=default_owner, default_deadline=default_deadline,
        )
        results.setdefault(ReactionTargetKind.CREATE_OBLIGATION.value, []).extend(created)

        # Dispatch escalation reactions
        if escalation_owner is not None:
            escalated = ReactionBridge.dispatch_escalation_reactions(
                decision, spine, obligation_engine,
                escalation_owner=escalation_owner,
            )
            results.setdefault(ReactionTargetKind.ESCALATE.value, []).extend(escalated)

        # Dispatch close reactions
        closed = ReactionBridge.dispatch_close_reactions(
            decision, spine, obligation_engine,
        )
        results.setdefault(ReactionTargetKind.CLOSE_OBLIGATION.value, []).extend(closed)

        # Dispatch transfer reactions
        if transfer_to is not None:
            transferred = ReactionBridge.dispatch_transfer_reactions(
                decision, spine, obligation_engine,
                transfer_to=transfer_to,
            )
            results.setdefault(ReactionTargetKind.TRANSFER_OBLIGATION.value, []).extend(transferred)

        # Collect passthrough kinds (caller dispatches these)
        passthrough_kinds = {
            ReactionTargetKind.NOTIFY,
            ReactionTargetKind.RESUME_JOB,
            ReactionTargetKind.ACTIVATE_WORKFLOW,
            ReactionTargetKind.CREATE_INCIDENT,
            ReactionTargetKind.REQUEST_APPROVAL,
            ReactionTargetKind.CUSTOM,
        }
        for exe in decision.executions:
            if exe.executed and exe.target.kind in passthrough_kinds:
                results.setdefault(exe.target.kind.value, []).append(exe)

        return {k: tuple(v) for k, v in results.items()}

    @staticmethod
    def reactive_expiry_sweep(
        reaction_engine: ReactionEngine,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        *,
        current_time: str,
        escalation_owner: ObligationOwner,
    ) -> tuple[ObligationRecord, ...]:
        """Sweep for expired obligations and reactively escalate them.

        For each expired obligation:
        1. Emit an expiry event into the spine
        2. Feed the event through the reaction engine
        3. If no escalation rule fires, escalate directly
        """
        expired = EventObligationBridge.check_expired_obligations(
            obligation_engine, current_time=current_time,
        )
        escalated: list[ObligationRecord] = []
        for obl in expired:
            # Emit expiry event
            evt = obligation_engine.obligation_event(obl, EventType.OBLIGATION_EXPIRED)
            spine.emit(evt)

            # Feed through reaction engine
            decision = reaction_engine.react(evt)

            # If no rules executed, escalate directly
            if decision.rules_executed == 0:
                updated, _esc_evt = EventObligationBridge.escalate_and_emit(
                    spine,
                    obligation_engine,
                    obl.obligation_id,
                    escalated_to=escalation_owner,
                    reason="obligation expired — reactive escalation",
                    severity="high",
                )
                escalated.append(updated)
            else:
                # Rules handled it — re-fetch for updated state
                updated = obligation_engine.get_obligation(obl.obligation_id)
                if updated is not None:
                    escalated.append(updated)
        return tuple(escalated)

    @staticmethod
    def build_gate_callback(
        *,
        simulation_check: bool = True,
        utility_check: bool = True,
        meta_reasoning_check: bool = True,
        confidence_threshold: float = 0.5,
    ) -> Callable[[EventRecord, ReactionRule], ReactionGateResult]:
        """Build a gate callback that composes checks with a confidence threshold.

        This is a convenience factory for creating gate functions.
        In a real deployment, the checks would call actual engines.
        This factory creates a configurable gate for testing and wiring.
        """
        def gate(event: EventRecord, rule: ReactionRule) -> ReactionGateResult:
            verdict = ReactionVerdict.PROCEED
            reasons: list[str] = []
            confidence = 1.0

            if not simulation_check:
                verdict = ReactionVerdict.REJECT
                reasons.append("simulation unsafe")
                confidence = min(confidence, 0.2)
            if not utility_check:
                verdict = ReactionVerdict.REJECT
                reasons.append("utility unacceptable")
                confidence = min(confidence, 0.3)
            if not meta_reasoning_check:
                verdict = ReactionVerdict.ESCALATE
                reasons.append("meta-reasoning unclear")
                confidence = min(confidence, 0.4)

            if confidence < confidence_threshold and verdict == ReactionVerdict.PROCEED:
                verdict = ReactionVerdict.DEFER
                reasons.append(f"confidence {confidence:.2f} below threshold {confidence_threshold:.2f}")

            reason = "; ".join(reasons) if reasons else "all checks passed"

            return ReactionGateResult(
                gate_id=stable_identifier("gate", {
                    "event_id": event.event_id,
                    "rule_id": rule.rule_id,
                }),
                rule_id=rule.rule_id,
                event_id=event.event_id,
                verdict=verdict,
                simulation_safe=simulation_check,
                utility_acceptable=utility_check,
                meta_reasoning_clear=meta_reasoning_check,
                confidence=confidence,
                reason=reason,
                gated_at=event.emitted_at,
            )
        return gate

    @staticmethod
    def emit_decision_events(
        spine: EventSpineEngine,
        decision: ReactionDecision,
    ) -> tuple[EventRecord, ...]:
        """Emit reaction outcome events back into the spine.

        For each execution in the decision, emits a REACTION_EXECUTED,
        REACTION_DEFERRED, or REACTION_REJECTED event so downstream
        subscribers can observe the reactive layer's decisions.
        """
        emitted: list[EventRecord] = []
        for exe in decision.executions:
            if exe.executed:
                etype = EventType.REACTION_EXECUTED
            elif exe.gate_result.verdict == ReactionVerdict.DEFER:
                etype = EventType.REACTION_DEFERRED
            else:
                etype = EventType.REACTION_REJECTED

            evt = EventRecord(
                event_id=stable_identifier("rxn-evt", {
                    "execution_id": exe.execution_id,
                }),
                event_type=etype,
                source=EventSource.REACTION_ENGINE,
                correlation_id=exe.correlation_id,
                payload={
                    "execution_id": exe.execution_id,
                    "rule_id": exe.rule_id,
                    "target_kind": exe.target.kind.value,
                    "verdict": exe.gate_result.verdict.value,
                    "confidence": exe.gate_result.confidence,
                },
                emitted_at=decision.decided_at,
            )
            spine.emit(evt)
            emitted.append(evt)
        return tuple(emitted)

    @staticmethod
    def executed_targets(decision: ReactionDecision) -> tuple[ReactionExecutionRecord, ...]:
        """Extract only the executed reactions from a decision."""
        return tuple(e for e in decision.executions if e.executed)

    @staticmethod
    def deferred_targets(decision: ReactionDecision) -> tuple[ReactionExecutionRecord, ...]:
        """Extract only deferred reactions from a decision."""
        return tuple(
            e for e in decision.executions
            if not e.executed and e.gate_result.verdict == ReactionVerdict.DEFER
        )

    @staticmethod
    def rejected_targets(decision: ReactionDecision) -> tuple[ReactionExecutionRecord, ...]:
        """Extract only rejected reactions from a decision."""
        return tuple(
            e for e in decision.executions
            if not e.executed and e.gate_result.verdict in (
                ReactionVerdict.REJECT, ReactionVerdict.ESCALATE,
                ReactionVerdict.REQUIRES_APPROVAL,
            )
        )


def _infer_trigger(event_id: str, target: object) -> ObligationTrigger:
    """Infer an obligation trigger from the reaction context."""
    return ObligationTrigger.CUSTOM
