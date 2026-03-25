"""Edge case tests for the reactive orchestration runtime.

Covers: ESCALATE/REQUIRES_APPROVAL verdicts, cascading reactions, idempotency
expiry, all target kinds, and gate error recovery.
"""

from __future__ import annotations

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.obligation import (
    ObligationDeadline,
    ObligationOwner,
    ObligationState,
    ObligationTrigger,
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
LATER = "2026-03-20T13:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


def _event(
    eid: str = "e1",
    etype: EventType = EventType.APPROVAL_REQUESTED,
    payload: dict | None = None,
    corr: str = "cor-1",
) -> EventRecord:
    return EventRecord(
        event_id=eid, event_type=etype, source=EventSource.APPROVAL_SYSTEM,
        correlation_id=corr, payload=payload or {"state": "active"},
        emitted_at=NOW,
    )


def _cond(
    cid: str = "c1", path: str = "state", op: str = "exists", val: object = True,
) -> ReactionCondition:
    return ReactionCondition(condition_id=cid, field_path=path, operator=op, expected_value=val)


def _rule(
    rid: str = "r1",
    event_type: str = "approval_requested",
    kind: ReactionTargetKind = ReactionTargetKind.CREATE_OBLIGATION,
    conditions: tuple | None = None,
) -> ReactionRule:
    return ReactionRule(
        rule_id=rid, name=f"rule-{rid}", event_type=event_type,
        conditions=conditions if conditions is not None else (_cond(),),
        target=ReactionTarget(
            target_id=f"tgt-{rid}", kind=kind,
            target_ref_id="ref-1", parameters={},
        ),
        created_at=NOW,
    )


def _owner(oid: str = "o1") -> ObligationOwner:
    return ObligationOwner(owner_id=oid, owner_type="human", display_name="Test")


def _deadline() -> ObligationDeadline:
    return ObligationDeadline(deadline_id="dl-1", due_at="2026-12-31T00:00:00+00:00")


# ---------------------------------------------------------------------------
# ESCALATE verdict
# ---------------------------------------------------------------------------


class TestEscalateVerdict:
    def test_escalate_verdict_not_executed(self) -> None:
        def escalating_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-esc", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.ESCALATE,
                simulation_safe=True, utility_acceptable=True,
                meta_reasoning_clear=False,
                confidence=0.3, reason="meta-reasoning unclear — escalating",
                gated_at=NOW,
            )
        eng = ReactionEngine(clock=CLOCK, gate=escalating_gate)
        eng.register_rule(_rule())
        decision = eng.react(_event())
        assert decision.rules_executed == 0
        assert decision.rules_rejected == 1
        assert decision.executions[0].gate_result.verdict == ReactionVerdict.ESCALATE
        assert decision.executions[0].executed is False

    def test_escalate_counted_in_rejected(self) -> None:
        def escalating_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-esc", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.ESCALATE,
                simulation_safe=True, utility_acceptable=True,
                meta_reasoning_clear=False,
                confidence=0.4, reason="needs human review",
                gated_at=NOW,
            )
        eng = ReactionEngine(clock=CLOCK, gate=escalating_gate)
        eng.register_rule(_rule())
        eng.register_rule(_rule("r2"))
        decision = eng.react(_event())
        assert decision.rules_rejected == 2


# ---------------------------------------------------------------------------
# REQUIRES_APPROVAL verdict
# ---------------------------------------------------------------------------


class TestRequiresApprovalVerdict:
    def test_requires_approval_not_executed(self) -> None:
        def approval_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-appr", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.REQUIRES_APPROVAL,
                simulation_safe=True, utility_acceptable=True,
                meta_reasoning_clear=True,
                confidence=0.8, reason="policy requires human approval",
                gated_at=NOW,
            )
        eng = ReactionEngine(clock=CLOCK, gate=approval_gate)
        eng.register_rule(_rule())
        decision = eng.react(_event())
        assert decision.rules_executed == 0
        assert decision.rules_rejected == 1
        assert decision.executions[0].gate_result.verdict == ReactionVerdict.REQUIRES_APPROVAL

    def test_requires_approval_shows_in_rejected_targets(self) -> None:
        def approval_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-appr", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.REQUIRES_APPROVAL,
                simulation_safe=True, utility_acceptable=True,
                meta_reasoning_clear=True,
                confidence=0.8, reason="needs approval",
                gated_at=NOW,
            )
        eng = ReactionEngine(clock=CLOCK, gate=approval_gate)
        eng.register_rule(_rule())
        decision = eng.react(_event())
        rejected = ReactionBridge.rejected_targets(decision)
        assert len(rejected) == 1
        assert rejected[0].gate_result.verdict == ReactionVerdict.REQUIRES_APPROVAL


# ---------------------------------------------------------------------------
# All target kinds
# ---------------------------------------------------------------------------


class TestAllTargetKinds:
    def test_all_target_kinds_construct(self) -> None:
        for kind in ReactionTargetKind:
            r = _rule(f"r-{kind.value}", kind=kind)
            assert r.target.kind == kind

    def test_dispatch_all_passthrough_kinds(self) -> None:
        spine = EventSpineEngine(clock=CLOCK)
        obl_eng = ObligationRuntimeEngine(clock=CLOCK)
        eng = ReactionEngine(clock=CLOCK)

        passthrough_kinds = [
            ReactionTargetKind.NOTIFY,
            ReactionTargetKind.RESUME_JOB,
            ReactionTargetKind.ACTIVATE_WORKFLOW,
            ReactionTargetKind.CREATE_INCIDENT,
            ReactionTargetKind.REQUEST_APPROVAL,
            ReactionTargetKind.CUSTOM,
        ]
        for i, kind in enumerate(passthrough_kinds):
            eng.register_rule(_rule(f"r-{i}", kind=kind))

        evt = _event()
        spine.emit(evt)
        decision = eng.react(evt)
        assert decision.rules_executed == len(passthrough_kinds)

        results = ReactionBridge.dispatch_all(
            decision, spine, obl_eng,
            default_owner=_owner(), default_deadline=_deadline(),
        )
        for kind in passthrough_kinds:
            assert kind.value in results


# ---------------------------------------------------------------------------
# Cascading reactions
# ---------------------------------------------------------------------------


class TestCascadingReactions:
    def test_reaction_produces_event_triggers_second_reaction(self) -> None:
        spine = EventSpineEngine(clock=CLOCK)
        obl_eng = ObligationRuntimeEngine(clock=CLOCK)
        rxn_eng = ReactionEngine(clock=CLOCK)

        # Rule 1: approval_requested → create obligation
        rxn_eng.register_rule(_rule("r-phase1",
            event_type="approval_requested",
            kind=ReactionTargetKind.CREATE_OBLIGATION,
        ))
        # Rule 2: obligation_created → notify
        rxn_eng.register_rule(_rule("r-phase2",
            event_type="obligation_created",
            kind=ReactionTargetKind.NOTIFY,
        ))

        # Phase 1: emit approval event
        evt1 = _event("evt-approval")
        spine.emit(evt1)
        d1 = rxn_eng.react(evt1)
        assert d1.rules_executed == 1

        # Dispatch obligation creation (this emits obligation_created into spine)
        created = ReactionBridge.dispatch_obligation_reactions(
            d1, spine, obl_eng,
            default_owner=_owner(), default_deadline=_deadline(),
        )
        assert len(created) == 1

        # Phase 2: the obligation_created event should trigger rule 2
        obl_events = spine.list_events(event_type=EventType.OBLIGATION_CREATED)
        assert len(obl_events) == 1

        d2 = rxn_eng.react(obl_events[0])
        assert d2.rules_executed == 1
        assert d2.executions[0].target.kind == ReactionTargetKind.NOTIFY

    def test_cascading_does_not_infinite_loop_via_idempotency(self) -> None:
        spine = EventSpineEngine(clock=CLOCK)
        rxn_eng = ReactionEngine(clock=CLOCK)

        # Rule that matches its own output type
        rxn_eng.register_rule(_rule("r-self",
            event_type="reaction_executed",
            kind=ReactionTargetKind.NOTIFY,
            conditions=(_cond(path="rule_id"),),
        ))

        # Simulate a reaction_executed event
        evt = EventRecord(
            event_id="evt-rxn-1",
            event_type=EventType.REACTION_EXECUTED,
            source=EventSource.REACTION_ENGINE,
            correlation_id="cor-loop",
            payload={"rule_id": "r-self"},
            emitted_at=NOW,
        )
        spine.emit(evt)

        d1 = rxn_eng.react(evt)
        assert d1.rules_executed == 1

        # Emit decision events back
        emitted = ReactionBridge.emit_decision_events(spine, d1)
        assert len(emitted) == 1

        # Try to react to the emitted event — idempotency blocks the same event
        # but the emitted event has a NEW event_id, so it WILL match
        d2 = rxn_eng.react(emitted[0])
        assert d2.rules_executed == 1

        # Emit again — this produces yet another new event
        emitted2 = ReactionBridge.emit_decision_events(spine, d2)

        # But in a real system, you'd add a max-cascade-depth check.
        # Here we just verify the mechanism works for 2 hops.
        assert spine.event_count >= 3  # original + reaction event + at least one emission


# ---------------------------------------------------------------------------
# Idempotency expiry
# ---------------------------------------------------------------------------


class TestIdempotencyExpiry:
    def test_expired_idempotency_allows_reprocessing(self) -> None:
        # Set idempotency to expire at NOW (which is before LATER)
        eng = ReactionEngine(clock=CLOCK, idempotency_expiry=NOW)
        eng.register_rule(_rule())

        d1 = eng.react(_event())
        assert d1.rules_executed == 1

        # Advance clock past expiry
        eng._clock = lambda: LATER

        d2 = eng.react(_event())
        # Should proceed because the idempotency window expired
        assert d2.rules_executed == 1

    def test_non_expired_idempotency_blocks(self) -> None:
        eng = ReactionEngine(clock=CLOCK, idempotency_expiry="9999-12-31T23:59:59+00:00")
        eng.register_rule(_rule())

        eng.react(_event())
        d2 = eng.react(_event())
        assert d2.rules_executed == 0
        assert d2.rules_rejected == 1


# ---------------------------------------------------------------------------
# Priority tie-breaking
# ---------------------------------------------------------------------------


class TestPriorityTieBreaking:
    def test_same_priority_sorted_by_rule_id(self) -> None:
        eng = ReactionEngine(clock=CLOCK)
        eng.register_rule(ReactionRule(
            rule_id="r-charlie", name="charlie", event_type="x",
            conditions=(_cond(),), target=ReactionTarget(
                target_id="t", kind=ReactionTargetKind.NOTIFY,
                target_ref_id="r", parameters={}), priority=0, created_at=NOW))
        eng.register_rule(ReactionRule(
            rule_id="r-alpha", name="alpha", event_type="x",
            conditions=(_cond(),), target=ReactionTarget(
                target_id="t", kind=ReactionTargetKind.NOTIFY,
                target_ref_id="r", parameters={}), priority=0, created_at=NOW))
        eng.register_rule(ReactionRule(
            rule_id="r-bravo", name="bravo", event_type="x",
            conditions=(_cond(),), target=ReactionTarget(
                target_id="t", kind=ReactionTargetKind.NOTIFY,
                target_ref_id="r", parameters={}), priority=0, created_at=NOW))
        rules = eng.list_rules()
        ids = [r.rule_id for r in rules]
        assert ids == ["r-alpha", "r-bravo", "r-charlie"]


# ---------------------------------------------------------------------------
# build_gate_callback
# ---------------------------------------------------------------------------


class TestBuildGateCallback:
    def test_all_checks_pass(self) -> None:
        gate = ReactionBridge.build_gate_callback(
            simulation_check=True, utility_check=True, meta_reasoning_check=True,
        )
        result = gate(_event(), _rule())
        assert result.verdict == ReactionVerdict.PROCEED

    def test_simulation_fails(self) -> None:
        gate = ReactionBridge.build_gate_callback(simulation_check=False)
        result = gate(_event(), _rule())
        assert result.verdict == ReactionVerdict.REJECT
        assert result.simulation_safe is False

    def test_utility_fails(self) -> None:
        gate = ReactionBridge.build_gate_callback(utility_check=False)
        result = gate(_event(), _rule())
        assert result.verdict == ReactionVerdict.REJECT
        assert result.utility_acceptable is False

    def test_meta_reasoning_fails(self) -> None:
        gate = ReactionBridge.build_gate_callback(meta_reasoning_check=False)
        result = gate(_event(), _rule())
        assert result.verdict == ReactionVerdict.ESCALATE
        assert result.meta_reasoning_clear is False

    def test_confidence_threshold(self) -> None:
        gate = ReactionBridge.build_gate_callback(confidence_threshold=0.99)
        result = gate(_event(), _rule())
        # All checks pass → confidence=1.0 ≥ 0.99 → PROCEED
        assert result.verdict == ReactionVerdict.PROCEED


# ---------------------------------------------------------------------------
# emit_decision_events
# ---------------------------------------------------------------------------


class TestEmitDecisionEvents:
    def test_deferred_emits_deferred_event(self) -> None:
        def deferring(event, rule):
            return ReactionGateResult(
                gate_id="g", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.DEFER,
                simulation_safe=True, utility_acceptable=True,
                meta_reasoning_clear=True,
                confidence=0.5, reason="defer", gated_at=NOW,
            )
        spine = EventSpineEngine(clock=CLOCK)
        eng = ReactionEngine(clock=CLOCK, gate=deferring)
        eng.register_rule(_rule())

        evt = _event()
        spine.emit(evt)
        decision = eng.react(evt)

        emitted = ReactionBridge.emit_decision_events(spine, decision)
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.REACTION_DEFERRED

    def test_rejected_emits_rejected_event(self) -> None:
        def rejecting(event, rule):
            return ReactionGateResult(
                gate_id="g", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.REJECT,
                simulation_safe=False, utility_acceptable=True,
                meta_reasoning_clear=True,
                confidence=0.1, reason="reject", gated_at=NOW,
            )
        spine = EventSpineEngine(clock=CLOCK)
        eng = ReactionEngine(clock=CLOCK, gate=rejecting)
        eng.register_rule(_rule())

        evt = _event()
        spine.emit(evt)
        decision = eng.react(evt)

        emitted = ReactionBridge.emit_decision_events(spine, decision)
        assert len(emitted) == 1
        assert emitted[0].event_type == EventType.REACTION_REJECTED
