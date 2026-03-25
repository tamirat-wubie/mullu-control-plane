"""Golden scenario tests for the reactive orchestration runtime.

Each scenario exercises the full reactive pipeline: event spine → reaction
engine → decision gating → obligation/escalation dispatch → audit trail.
"""

from __future__ import annotations

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
)
from mcoi_runtime.contracts.reaction import (
    BackpressurePolicy,
    BackpressureStrategy,
    ReactionCondition,
    ReactionGateResult,
    ReactionRule,
    ReactionTarget,
    ReactionTargetKind,
    ReactionVerdict,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.reaction_engine import ReactionEngine
from mcoi_runtime.core.reaction_integration import ReactionBridge

NOW = "2026-03-20T12:00:00+00:00"
FUTURE = "2026-03-21T12:00:00+00:00"
PAST = "2026-03-19T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


def _owner(oid: str = "owner-1", name: str = "Alice") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type="human", display_name=name)


def _deadline(due: str = FUTURE) -> ObligationDeadline:
    return ObligationDeadline(deadline_id="dl-1", due_at=due)


def _event(
    eid: str = "evt-1",
    etype: EventType = EventType.APPROVAL_REQUESTED,
    source: EventSource = EventSource.APPROVAL_SYSTEM,
    payload: dict | None = None,
    corr: str = "cor-1",
) -> EventRecord:
    return EventRecord(
        event_id=eid, event_type=etype, source=source,
        correlation_id=corr,
        payload=payload or {"state": "active"},
        emitted_at=NOW,
    )


def _cond(
    cid: str = "c1", path: str = "state", op: str = "eq", val: str = "active",
) -> ReactionCondition:
    return ReactionCondition(condition_id=cid, field_path=path, operator=op, expected_value=val)


def _setup():
    spine = EventSpineEngine(clock=CLOCK)
    obl_engine = ObligationRuntimeEngine(clock=CLOCK)
    rxn_engine = ReactionEngine(clock=CLOCK)
    return spine, obl_engine, rxn_engine


# ---------------------------------------------------------------------------
# Scenario 1: Approval request event → obligation → follow-up job
# ---------------------------------------------------------------------------


class TestScenario1ApprovalToObligation:
    def test_approval_event_creates_obligation(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        # Register rule: approval_requested → create obligation
        rule = ReactionRule(
            rule_id="rule-approval-obl",
            name="create approval obligation",
            event_type="approval_requested",
            conditions=(_cond(),),
            target=ReactionTarget(
                target_id="tgt-1",
                kind=ReactionTargetKind.CREATE_OBLIGATION,
                target_ref_id="approval-ref",
                parameters={"type": "approval"},
            ),
            created_at=NOW,
        )
        rxn_engine.register_rule(rule)

        # Emit event
        evt = _event()
        spine.emit(evt)

        # Process through reaction engine
        decision = ReactionBridge.process_event(rxn_engine, spine, evt)
        assert decision.rules_executed == 1

        # Dispatch obligation creation
        created = ReactionBridge.dispatch_obligation_reactions(
            decision, spine, obl_engine,
            default_owner=_owner(), default_deadline=_deadline(),
        )
        assert len(created) == 1
        assert created[0].state == ObligationState.PENDING
        assert obl_engine.obligation_count == 1

        # Verify event trail in spine (original + obligation_created)
        events = spine.list_events(correlation_id="cor-1")
        assert len(events) == 2
        assert events[1].event_type == EventType.OBLIGATION_CREATED


# ---------------------------------------------------------------------------
# Scenario 2: Unanswered communication → escalation path
# ---------------------------------------------------------------------------


class TestScenario2CommunicationEscalation:
    def test_timed_out_communication_escalates(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        # Register rule: communication_timed_out → escalate
        rule = ReactionRule(
            rule_id="rule-comm-esc",
            name="escalate timed out communication",
            event_type="communication_timed_out",
            conditions=(_cond(),),
            target=ReactionTarget(
                target_id="tgt-esc",
                kind=ReactionTargetKind.ESCALATE,
                target_ref_id="obl-comm",
                parameters={},
            ),
            created_at=NOW,
        )
        rxn_engine.register_rule(rule)

        # Create the obligation that will be escalated
        obl = obl_engine.create_obligation(
            obligation_id="obl-comm",
            trigger=__import__("mcoi_runtime.contracts.obligation", fromlist=["ObligationTrigger"]).ObligationTrigger.COMMUNICATION_FOLLOW_UP,
            trigger_ref_id="msg-1",
            owner=_owner(),
            deadline=_deadline(),
            description="follow up on unanswered message",
            correlation_id="cor-comm",
        )
        obl_engine.activate("obl-comm")

        # Emit timeout event
        evt = _event(
            "evt-timeout",
            EventType.COMMUNICATION_TIMED_OUT,
            EventSource.COMMUNICATION_SYSTEM,
            corr="cor-comm",
        )
        spine.emit(evt)

        decision = rxn_engine.react(evt)
        assert decision.rules_executed == 1

        # Dispatch escalation
        manager = _owner("mgr-1", "Manager Bob")
        escalated = ReactionBridge.dispatch_escalation_reactions(
            decision, spine, obl_engine, escalation_owner=manager,
        )
        assert len(escalated) == 1
        assert escalated[0].state == ObligationState.ESCALATED
        assert escalated[0].owner.owner_id == "mgr-1"


# ---------------------------------------------------------------------------
# Scenario 3: Incident opened → function playbook activation
# ---------------------------------------------------------------------------


class TestScenario3IncidentPlaybook:
    def test_incident_triggers_notification(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        rule = ReactionRule(
            rule_id="rule-incident-notify",
            name="notify on incident",
            event_type="incident_opened",
            conditions=(_cond(),),
            target=ReactionTarget(
                target_id="tgt-notify",
                kind=ReactionTargetKind.NOTIFY,
                target_ref_id="oncall-channel",
                parameters={"channel": "ops"},
            ),
            created_at=NOW,
        )
        rxn_engine.register_rule(rule)

        evt = _event("evt-inc", EventType.INCIDENT_OPENED, EventSource.INCIDENT_SYSTEM)
        spine.emit(evt)

        decision = rxn_engine.react(evt)
        assert decision.rules_executed == 1
        assert decision.executions[0].target.kind == ReactionTargetKind.NOTIFY
        assert decision.executions[0].executed is True


# ---------------------------------------------------------------------------
# Scenario 4: Workflow stage failure → recovery decision path
# ---------------------------------------------------------------------------


class TestScenario4WorkflowFailureRecovery:
    def test_workflow_failure_gates_through_simulation(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        # Gate rejects because simulation says unsafe
        def unsafe_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-unsafe",
                rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.REJECT,
                simulation_safe=False,
                utility_acceptable=True,
                meta_reasoning_clear=True,
                confidence=0.1,
                reason="simulation predicts cascading failure",
                gated_at=NOW,
            )

        rxn_engine = ReactionEngine(clock=CLOCK, gate=unsafe_gate)
        rule = ReactionRule(
            rule_id="rule-wf-recovery",
            name="auto-retry workflow stage",
            event_type="workflow_stage_transition",
            conditions=(
                ReactionCondition(
                    condition_id="c-failed",
                    field_path="state",
                    operator="eq",
                    expected_value="failed",
                ),
            ),
            target=ReactionTarget(
                target_id="tgt-retry",
                kind=ReactionTargetKind.RESUME_JOB,
                target_ref_id="job-wf-1",
                parameters={"action": "retry"},
            ),
            created_at=NOW,
        )
        rxn_engine.register_rule(rule)

        evt = _event(
            "evt-wf-fail",
            EventType.WORKFLOW_STAGE_TRANSITION,
            EventSource.WORKFLOW_RUNTIME,
            payload={"state": "failed", "stage": "deploy"},
        )
        spine.emit(evt)

        decision = rxn_engine.react(evt)
        assert decision.rules_matched == 1
        assert decision.rules_executed == 0
        assert decision.rules_rejected == 1
        assert "simulation" in decision.executions[0].gate_result.reason


# ---------------------------------------------------------------------------
# Scenario 5: Obligation expiration → reactive escalation
# ---------------------------------------------------------------------------


class TestScenario5ObligationExpiry:
    def test_expired_obligation_triggers_escalation(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        # Create an obligation with past deadline
        obl = obl_engine.create_obligation(
            obligation_id="obl-expired",
            trigger=__import__("mcoi_runtime.contracts.obligation", fromlist=["ObligationTrigger"]).ObligationTrigger.INCIDENT_SLA,
            trigger_ref_id="inc-1",
            owner=_owner(),
            deadline=ObligationDeadline(deadline_id="dl-past", due_at=PAST),
            description="resolve incident within SLA",
            correlation_id="cor-sla",
        )
        obl_engine.activate("obl-expired")

        # Run expiry sweep — no rules registered, so direct escalation
        manager = _owner("mgr-1", "Manager Bob")
        escalated = ReactionBridge.reactive_expiry_sweep(
            rxn_engine, spine, obl_engine,
            current_time=NOW, escalation_owner=manager,
        )
        assert len(escalated) == 1
        assert escalated[0].state == ObligationState.ESCALATED
        assert escalated[0].owner.owner_id == "mgr-1"

        # Verify expiry event was emitted into spine
        events = spine.list_events(event_type=EventType.OBLIGATION_EXPIRED)
        assert len(events) == 1


# ---------------------------------------------------------------------------
# Scenario 6: Event replay / idempotency does not duplicate work
# ---------------------------------------------------------------------------


class TestScenario6ReplayIdempotency:
    def test_replayed_event_does_not_duplicate(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        rule = ReactionRule(
            rule_id="rule-idem",
            name="idempotent rule",
            event_type="approval_requested",
            conditions=(_cond(),),
            target=ReactionTarget(
                target_id="tgt-idem",
                kind=ReactionTargetKind.CREATE_OBLIGATION,
                target_ref_id="ref-idem",
                parameters={},
            ),
            created_at=NOW,
        )
        rxn_engine.register_rule(rule)

        evt = _event("evt-replay")
        spine.emit(evt)

        # First pass — executes
        d1 = rxn_engine.react(evt)
        assert d1.rules_executed == 1

        obligations_1 = ReactionBridge.dispatch_obligation_reactions(
            d1, spine, obl_engine,
            default_owner=_owner(), default_deadline=_deadline(),
        )
        assert len(obligations_1) == 1

        # Replay same event — idempotency rejects
        d2 = rxn_engine.react(evt)
        assert d2.rules_executed == 0
        assert d2.rules_rejected == 1
        assert "duplicate" in d2.executions[0].execution_notes

        # No new obligations created
        obligations_2 = ReactionBridge.dispatch_obligation_reactions(
            d2, spine, obl_engine,
            default_owner=_owner(), default_deadline=_deadline(),
        )
        assert len(obligations_2) == 0
        assert obl_engine.obligation_count == 1  # still just 1


# ---------------------------------------------------------------------------
# Scenario 7: Reaction decisions emit events back into spine
# ---------------------------------------------------------------------------


class TestScenario7DecisionEventEmission:
    def test_emit_decision_events_closes_loop(self) -> None:
        spine, obl_engine, rxn_engine = _setup()

        rule = ReactionRule(
            rule_id="rule-loop",
            name="loop test rule",
            event_type="approval_requested",
            conditions=(_cond(),),
            target=ReactionTarget(
                target_id="tgt-loop",
                kind=ReactionTargetKind.NOTIFY,
                target_ref_id="channel-1",
                parameters={},
            ),
            created_at=NOW,
        )
        rxn_engine.register_rule(rule)

        evt = _event("evt-loop")
        spine.emit(evt)

        decision = rxn_engine.react(evt)
        assert decision.rules_executed == 1

        # Emit decision events back into spine
        emitted = ReactionBridge.emit_decision_events(spine, decision)
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.REACTION_EXECUTED
        assert emitted[0].payload["rule_id"] == "rule-loop"
        assert emitted[0].payload["verdict"] == "proceed"

        # Verify the event is in the spine
        all_events = spine.list_events(correlation_id="cor-1")
        reaction_events = [e for e in all_events if e.event_type == EventType.REACTION_EXECUTED]
        assert len(reaction_events) == 1
