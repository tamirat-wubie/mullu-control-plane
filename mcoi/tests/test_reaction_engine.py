"""Tests for the ReactionEngine — rule matching, condition evaluation,
gating, idempotency, backpressure, and decision recording."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
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
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.reaction_engine import ReactionEngine

NOW = "2026-03-20T12:00:00+00:00"
CLOCK = lambda: NOW  # noqa: E731


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event(
    eid: str = "e1",
    etype: EventType = EventType.APPROVAL_REQUESTED,
    payload: dict | None = None,
) -> EventRecord:
    return EventRecord(
        event_id=eid,
        event_type=etype,
        source=EventSource.APPROVAL_SYSTEM,
        correlation_id="cor-1",
        payload=payload or {"state": "active", "priority": "high"},
        emitted_at=NOW,
    )


def _cond(
    cid: str = "c1", path: str = "state", op: str = "eq", val: str = "active",
) -> ReactionCondition:
    return ReactionCondition(condition_id=cid, field_path=path, operator=op, expected_value=val)


def _target(
    tid: str = "t1",
    kind: ReactionTargetKind = ReactionTargetKind.CREATE_OBLIGATION,
) -> ReactionTarget:
    return ReactionTarget(target_id=tid, kind=kind, target_ref_id="ref-1", parameters={})


def _rule(
    rid: str = "r1",
    event_type: str = "approval_requested",
    conditions: tuple[ReactionCondition, ...] | None = None,
    target: ReactionTarget | None = None,
    priority: int = 0,
    enabled: bool = True,
) -> ReactionRule:
    return ReactionRule(
        rule_id=rid, name=f"rule-{rid}",
        event_type=event_type,
        conditions=conditions if conditions is not None else (_cond(),),
        target=target or _target(),
        priority=priority,
        enabled=enabled,
        created_at=NOW,
    )


def _engine(**kwargs) -> ReactionEngine:
    return ReactionEngine(clock=CLOCK, **kwargs)


# ---------------------------------------------------------------------------
# Rule management
# ---------------------------------------------------------------------------


class TestRuleManagement:
    def test_register_and_retrieve(self) -> None:
        eng = _engine()
        r = _rule()
        eng.register_rule(r)
        assert eng.get_rule("r1") is r
        assert eng.rule_count == 1

    def test_duplicate_rule_raises(self) -> None:
        eng = _engine()
        eng.register_rule(_rule())
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            eng.register_rule(_rule())
        assert str(excinfo.value) == "rule already exists"
        assert "r1" not in str(excinfo.value)

    def test_unregister(self) -> None:
        eng = _engine()
        eng.register_rule(_rule())
        eng.unregister_rule("r1")
        assert eng.get_rule("r1") is None
        assert eng.rule_count == 0

    def test_unregister_missing_raises(self) -> None:
        eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            eng.unregister_rule("nope")
        assert str(excinfo.value) == "rule not found"
        assert "nope" not in str(excinfo.value)

    def test_list_rules_sorted_by_priority(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r2", priority=5))
        eng.register_rule(_rule("r1", priority=1))
        eng.register_rule(_rule("r3", priority=3))
        rules = eng.list_rules()
        assert [r.rule_id for r in rules] == ["r1", "r3", "r2"]

    def test_list_rules_enabled_only(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", enabled=True))
        eng.register_rule(_rule("r2", enabled=False))
        assert len(eng.list_rules(enabled_only=True)) == 1
        assert len(eng.list_rules(enabled_only=False)) == 2


# ---------------------------------------------------------------------------
# Condition evaluation
# ---------------------------------------------------------------------------


class TestConditionEvaluation:
    def test_eq_match(self) -> None:
        assert ReactionEngine.evaluate_condition(
            _cond(op="eq", val="active"), {"state": "active"},
        ) is True

    def test_eq_no_match(self) -> None:
        assert ReactionEngine.evaluate_condition(
            _cond(op="eq", val="active"), {"state": "pending"},
        ) is False

    def test_neq(self) -> None:
        assert ReactionEngine.evaluate_condition(
            _cond(op="neq", val="active"), {"state": "pending"},
        ) is True

    def test_gt(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="count", operator="gt", expected_value=5),
            {"count": 10},
        ) is True

    def test_gte(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="count", operator="gte", expected_value=10),
            {"count": 10},
        ) is True

    def test_lt(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="count", operator="lt", expected_value=10),
            {"count": 5},
        ) is True

    def test_lte(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="count", operator="lte", expected_value=5),
            {"count": 5},
        ) is True

    def test_gt_incompatible_types_returns_false(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="name", operator="gt", expected_value=5),
            {"name": "alice"},
        ) is False

    def test_lt_incompatible_types_returns_false(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="count", operator="lt", expected_value="not_a_number"),
            {"count": 5},
        ) is False

    def test_contains(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="tags", operator="contains", expected_value="urgent"),
            {"tags": ["urgent", "low"]},
        ) is True

    def test_in_operator(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="status", operator="in", expected_value=("a", "b")),
            {"status": "a"},
        ) is True

    def test_exists_present(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="x", operator="exists", expected_value=None),
            {"x": 42},
        ) is True

    def test_exists_absent(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="y", operator="exists", expected_value=None),
            {"x": 42},
        ) is False

    def test_nested_path(self) -> None:
        assert ReactionEngine.evaluate_condition(
            ReactionCondition(condition_id="c", field_path="a.b.c", operator="eq", expected_value=99),
            {"a": {"b": {"c": 99}}},
        ) is True

    def test_missing_path_returns_false(self) -> None:
        assert ReactionEngine.evaluate_condition(
            _cond(path="missing"), {"state": "active"},
        ) is False


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------


class TestRuleMatching:
    def test_match_by_event_type(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", event_type="approval_requested"))
        eng.register_rule(_rule("r2", event_type="incident_opened"))
        matched = eng.match_rules(_event())
        assert len(matched) == 1
        assert matched[0].rule_id == "r1"

    def test_match_with_conditions(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", event_type="approval_requested", conditions=(_cond(),)))
        eng.register_rule(_rule("r2", event_type="approval_requested", conditions=(
            _cond("c2", "state", "eq", "pending"),
        )))
        matched = eng.match_rules(_event())
        assert len(matched) == 1
        assert matched[0].rule_id == "r1"

    def test_no_match(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", event_type="incident_opened"))
        assert eng.match_rules(_event()) == ()

    def test_disabled_rules_excluded(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", event_type="approval_requested", enabled=False))
        assert eng.match_rules(_event()) == ()


# ---------------------------------------------------------------------------
# React cycle
# ---------------------------------------------------------------------------


class TestReactCycle:
    def test_basic_react_proceeds(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", event_type="approval_requested"))
        decision = eng.react(_event())
        assert decision.rules_matched == 1
        assert decision.rules_executed == 1
        assert decision.rules_rejected == 0
        assert len(decision.executions) == 1
        assert decision.executions[0].executed is True

    def test_no_matching_rules(self) -> None:
        eng = _engine()
        decision = eng.react(_event())
        assert decision.rules_matched == 0
        assert decision.rules_executed == 0
        assert len(decision.executions) == 0

    def test_multiple_rules_matched(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1", event_type="approval_requested"))
        eng.register_rule(_rule("r2", event_type="approval_requested",
                                target=_target("t2", ReactionTargetKind.NOTIFY)))
        decision = eng.react(_event())
        assert decision.rules_matched == 2
        assert decision.rules_executed == 2

    def test_decision_recorded(self) -> None:
        eng = _engine()
        eng.register_rule(_rule())
        decision = eng.react(_event())
        assert eng.decision_count == 1
        retrieved = eng.list_decisions()
        assert retrieved[0].decision_id == decision.decision_id

    def test_execution_recorded(self) -> None:
        eng = _engine()
        eng.register_rule(_rule())
        eng.react(_event())
        execs = eng.list_executions(event_id="e1")
        assert len(execs) == 1
        assert execs[0].executed is True


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------


class TestGating:
    def test_custom_gate_reject(self) -> None:
        def rejecting_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-reject", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.REJECT,
                simulation_safe=False, utility_acceptable=True, meta_reasoning_clear=True,
                confidence=0.2, reason="simulation failed", gated_at=NOW,
            )
        eng = _engine(gate=rejecting_gate)
        eng.register_rule(_rule())
        decision = eng.react(_event())
        assert decision.rules_executed == 0
        assert decision.rules_rejected == 1
        assert decision.executions[0].executed is False

    def test_custom_gate_defer(self) -> None:
        def deferring_gate(event, rule):
            return ReactionGateResult(
                gate_id="g-defer", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.DEFER,
                simulation_safe=True, utility_acceptable=True, meta_reasoning_clear=True,
                confidence=0.6, reason="low confidence", gated_at=NOW,
            )
        eng = _engine(gate=deferring_gate)
        eng.register_rule(_rule())
        decision = eng.react(_event())
        assert decision.rules_executed == 0
        assert decision.rules_deferred == 1

    def test_gate_exception_produces_reject(self) -> None:
        def crashing_gate(event, rule):
            raise RuntimeError("gate crashed")
        eng = _engine(gate=crashing_gate)
        eng.register_rule(_rule())
        decision = eng.react(_event())
        assert decision.rules_executed == 0
        assert decision.rules_rejected == 1
        assert decision.executions[0].gate_result.reason == "gate callback error (RuntimeError)"
        assert "gate crashed" not in decision.executions[0].gate_result.reason
        assert decision.executions[0].gate_result.confidence == 0.0


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_duplicate_event_rejected(self) -> None:
        eng = _engine()
        eng.register_rule(_rule())
        d1 = eng.react(_event())
        assert d1.rules_executed == 1
        # Replay same event
        d2 = eng.react(_event())
        assert d2.rules_executed == 0
        assert d2.rules_rejected == 1
        assert "duplicate" in d2.executions[0].execution_notes

    def test_different_events_both_proceed(self) -> None:
        eng = _engine()
        eng.register_rule(_rule())
        eng.react(_event("e1"))
        d2 = eng.react(_event("e2"))
        assert d2.rules_executed == 1

    def test_is_duplicate_check(self) -> None:
        eng = _engine()
        assert eng.is_duplicate("e1", "r1") is False
        eng.register_rule(_rule())
        eng.react(_event())
        assert eng.is_duplicate("e1", "r1") is True


# ---------------------------------------------------------------------------
# Backpressure
# ---------------------------------------------------------------------------


class TestBackpressure:
    def test_backpressure_defers_when_full(self) -> None:
        eng = _engine()
        eng.set_backpressure(BackpressurePolicy(
            policy_id="bp1", max_concurrent=1, max_per_window=10,
            window_seconds=60, strategy=BackpressureStrategy.RATE_LIMIT,
        ))
        eng.register_rule(_rule())
        # First event proceeds
        d1 = eng.react(_event("e1"))
        assert d1.rules_executed == 1
        # Second event deferred (active_count still at 1)
        d2 = eng.react(_event("e2"))
        assert d2.rules_deferred == 1
        assert d2.rules_executed == 0

    def test_release_active_unblocks(self) -> None:
        eng = _engine()
        eng.set_backpressure(BackpressurePolicy(
            policy_id="bp1", max_concurrent=1, max_per_window=10,
            window_seconds=60, strategy=BackpressureStrategy.RATE_LIMIT,
        ))
        eng.register_rule(_rule())
        eng.react(_event("e1"))
        eng.release_active()
        d2 = eng.react(_event("e2"))
        assert d2.rules_executed == 1

    def test_window_limit(self) -> None:
        eng = _engine()
        eng.set_backpressure(BackpressurePolicy(
            policy_id="bp1", max_concurrent=100, max_per_window=2,
            window_seconds=60, strategy=BackpressureStrategy.RATE_LIMIT,
        ))
        eng.register_rule(_rule())
        eng.react(_event("e1"))
        eng.release_active()
        eng.react(_event("e2"))
        eng.release_active()
        d3 = eng.react(_event("e3"))
        assert d3.rules_deferred == 1

    def test_reset_window(self) -> None:
        eng = _engine()
        eng.set_backpressure(BackpressurePolicy(
            policy_id="bp1", max_concurrent=100, max_per_window=1,
            window_seconds=60, strategy=BackpressureStrategy.RATE_LIMIT,
        ))
        eng.register_rule(_rule())
        eng.react(_event("e1"))
        eng.release_active()
        eng.reset_window()
        d2 = eng.react(_event("e2"))
        assert d2.rules_executed == 1


# ---------------------------------------------------------------------------
# History queries
# ---------------------------------------------------------------------------


class TestHistory:
    def test_list_executions_by_rule(self) -> None:
        eng = _engine()
        eng.register_rule(_rule("r1"))
        eng.register_rule(_rule("r2", event_type="incident_opened"))
        eng.react(_event())
        assert len(eng.list_executions(rule_id="r1")) == 1
        assert len(eng.list_executions(rule_id="r2")) == 0

    def test_list_executions_executed_only(self) -> None:
        def deferring(event, rule):
            return ReactionGateResult(
                gate_id="g", rule_id=rule.rule_id, event_id=event.event_id,
                verdict=ReactionVerdict.DEFER,
                simulation_safe=True, utility_acceptable=True, meta_reasoning_clear=True,
                confidence=0.5, reason="test", gated_at=NOW,
            )
        eng = _engine(gate=deferring)
        eng.register_rule(_rule())
        eng.react(_event())
        assert len(eng.list_executions(executed_only=True)) == 0
        assert len(eng.list_executions(executed_only=False)) == 1


# ---------------------------------------------------------------------------
# Dispatch all
# ---------------------------------------------------------------------------


class TestDispatchAll:
    def test_dispatch_all_routes_by_kind(self) -> None:
        from mcoi_runtime.contracts.obligation import (
            ObligationDeadline,
            ObligationOwner,
        )
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
        from mcoi_runtime.core.reaction_integration import ReactionBridge

        spine = EventSpineEngine(clock=CLOCK)
        obl_eng = ObligationRuntimeEngine(clock=CLOCK)
        rxn_eng = _engine()

        # Two rules: one creates obligation, one notifies
        rxn_eng.register_rule(_rule(
            "r-obl", event_type="approval_requested",
            target=_target("t-obl", ReactionTargetKind.CREATE_OBLIGATION),
        ))
        rxn_eng.register_rule(_rule(
            "r-notify", event_type="approval_requested",
            target=_target("t-notify", ReactionTargetKind.NOTIFY),
        ))

        evt = _event()
        spine.emit(evt)
        decision = rxn_eng.react(evt)
        assert decision.rules_executed == 2

        owner = ObligationOwner(owner_id="o1", owner_type="human", display_name="Alice")
        deadline = ObligationDeadline(deadline_id="dl1", due_at="2026-12-31T00:00:00+00:00")

        results = ReactionBridge.dispatch_all(
            decision, spine, obl_eng,
            default_owner=owner, default_deadline=deadline,
        )
        assert "create_obligation" in results
        assert "notify" in results
        assert len(results["create_obligation"]) == 1
        assert len(results["notify"]) == 1


# ---------------------------------------------------------------------------
# Audit #10 — unknown operator and backpressure window auto-reset
# ---------------------------------------------------------------------------


class TestUnknownOperatorRaises:
    """Unknown condition operators should raise, not silently return False."""

    def test_unknown_operator_rejected_at_contract_level(self) -> None:
        """ReactionCondition contract itself rejects unknown operators."""
        with pytest.raises(ValueError, match="^operator has unsupported value$") as exc_info:
            ReactionCondition(
                condition_id="c-1",
                field_path="status",
                operator="MATCHES",
                expected_value="ok",
            )
        message = str(exc_info.value)
        assert "MATCHES" not in message
        assert "eq" not in message

    def test_known_operators_do_not_raise(self) -> None:
        for i, op in enumerate(("eq", "neq", "gt", "gte", "lt", "lte", "contains", "in", "exists")):
            cond = ReactionCondition(
                condition_id=f"c-{i}",
                field_path="val",
                operator=op,
                expected_value=5,
            )
            # Should not raise — result correctness varies by op/type
            ReactionEngine.evaluate_condition(cond, {"val": 5})


class TestBackpressureAutoReset:
    """Backpressure window should auto-reset after window_seconds elapse."""

    def test_window_resets_after_elapsed_time(self) -> None:
        times = iter([
            "2026-03-20T12:00:00+00:00",  # set_backpressure / first check
            "2026-03-20T12:00:01+00:00",  # _record_throughput
            "2026-03-20T12:00:02+00:00",  # second check (before window expires)
            "2026-03-20T12:01:01+00:00",  # third check (after 60s window expires)
            "2026-03-20T12:01:01+00:00",  # _record_throughput for reset window
        ])
        eng = ReactionEngine(clock=lambda: next(times))
        policy = BackpressurePolicy(
            policy_id="bp-1",
            max_concurrent=100,
            max_per_window=1,
            window_seconds=60,
            strategy=BackpressureStrategy.RATE_LIMIT,
        )
        eng.set_backpressure(policy)
        eng.reset_window()  # initializes _window_start

        # First check: can proceed
        assert eng._check_backpressure() is True
        eng._record_throughput()  # window_count = 1

        # Second check: at limit, window not expired
        assert eng._check_backpressure() is False

        # Third check: window expired (61s later), should auto-reset
        assert eng._check_backpressure() is True
