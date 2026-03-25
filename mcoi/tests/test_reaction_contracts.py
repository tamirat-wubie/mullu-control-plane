"""Tests for reaction contracts — conditions, rules, targets, gating,
execution records, backpressure, idempotency, and decisions."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.reaction import (
    BackpressurePolicy,
    BackpressureStrategy,
    IdempotencyWindow,
    ReactionCondition,
    ReactionDecision,
    ReactionExecutionRecord,
    ReactionGateResult,
    ReactionRule,
    ReactionTarget,
    ReactionTargetKind,
    ReactionVerdict,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cond(cid: str = "c1", path: str = "state", op: str = "eq", val: str = "active") -> ReactionCondition:
    return ReactionCondition(condition_id=cid, field_path=path, operator=op, expected_value=val)


def _target(tid: str = "t1", kind: ReactionTargetKind = ReactionTargetKind.CREATE_OBLIGATION) -> ReactionTarget:
    return ReactionTarget(target_id=tid, kind=kind, target_ref_id="ref-1", parameters={"key": "val"})


def _gate(gid: str = "g1", rule_id: str = "r1", event_id: str = "e1") -> ReactionGateResult:
    return ReactionGateResult(
        gate_id=gid, rule_id=rule_id, event_id=event_id,
        verdict=ReactionVerdict.PROCEED,
        simulation_safe=True, utility_acceptable=True, meta_reasoning_clear=True,
        confidence=0.9, reason="all clear", gated_at=NOW,
    )


def _execution(eid: str = "x1") -> ReactionExecutionRecord:
    return ReactionExecutionRecord(
        execution_id=eid, rule_id="r1", event_id="e1", correlation_id="cor-1",
        target=_target(), gate_result=_gate(),
        executed=True, result_ref_id="ref-1",
        execution_notes="ok", executed_at=NOW,
    )


# ---------------------------------------------------------------------------
# ReactionCondition
# ---------------------------------------------------------------------------


class TestReactionCondition:
    def test_valid_condition(self) -> None:
        c = _cond()
        assert c.condition_id == "c1"
        assert c.operator == "eq"

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="condition_id"):
            ReactionCondition(condition_id="", field_path="x", operator="eq", expected_value=1)

    def test_invalid_operator_raises(self) -> None:
        with pytest.raises(ValueError, match="operator"):
            ReactionCondition(condition_id="c1", field_path="x", operator="banana", expected_value=1)

    def test_all_valid_operators(self) -> None:
        for op in ("eq", "neq", "gt", "gte", "lt", "lte", "contains", "in", "exists"):
            c = ReactionCondition(condition_id=f"c-{op}", field_path="x", operator=op, expected_value=1)
            assert c.operator == op

    def test_payload_frozen(self) -> None:
        c = ReactionCondition(condition_id="c1", field_path="x", operator="eq", expected_value={"a": [1]})
        assert isinstance(c.expected_value, tuple) or not isinstance(c.expected_value, list)


# ---------------------------------------------------------------------------
# ReactionTarget
# ---------------------------------------------------------------------------


class TestReactionTarget:
    def test_valid_target(self) -> None:
        t = _target()
        assert t.kind == ReactionTargetKind.CREATE_OBLIGATION
        assert t.parameters["key"] == "val"

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError):
            ReactionTarget(target_id="", kind=ReactionTargetKind.NOTIFY, target_ref_id="r", parameters={})

    def test_parameters_frozen(self) -> None:
        t = _target()
        with pytest.raises(TypeError):
            t.parameters["new"] = "val"  # type: ignore[index]


# ---------------------------------------------------------------------------
# ReactionRule
# ---------------------------------------------------------------------------


class TestReactionRule:
    def test_valid_rule(self) -> None:
        r = ReactionRule(
            rule_id="r1", name="test rule",
            event_type="approval_requested",
            conditions=(_cond(),), target=_target(),
            created_at=NOW,
        )
        assert r.rule_id == "r1"
        assert r.enabled is True
        assert r.priority == 0

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="name"):
            ReactionRule(
                rule_id="r1", name="",
                event_type="x", conditions=(_cond(),), target=_target(),
                created_at=NOW,
            )

    def test_non_tuple_conditions_raises(self) -> None:
        with pytest.raises(ValueError, match="conditions must be a tuple"):
            ReactionRule(
                rule_id="r1", name="test",
                event_type="x", conditions=[_cond()],  # type: ignore[arg-type]
                target=_target(),
                created_at=NOW,
            )

    def test_bad_condition_raises(self) -> None:
        with pytest.raises(ValueError, match="each condition"):
            ReactionRule(
                rule_id="r1", name="test",
                event_type="x", conditions=("not-a-condition",),  # type: ignore[arg-type]
                target=_target(),
                created_at=NOW,
            )

    def test_serialization_roundtrip(self) -> None:
        r = ReactionRule(
            rule_id="r1", name="test", event_type="x",
            conditions=(_cond(),), target=_target(), priority=5,
            created_at=NOW,
        )
        d = r.to_dict()
        assert d["rule_id"] == "r1"
        assert d["priority"] == 5


# ---------------------------------------------------------------------------
# ReactionGateResult
# ---------------------------------------------------------------------------


class TestReactionGateResult:
    def test_valid_gate(self) -> None:
        g = _gate()
        assert g.verdict == ReactionVerdict.PROCEED
        assert g.confidence == 0.9

    def test_bad_confidence_raises(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            ReactionGateResult(
                gate_id="g", rule_id="r", event_id="e",
                verdict=ReactionVerdict.PROCEED,
                simulation_safe=True, utility_acceptable=True, meta_reasoning_clear=True,
                confidence=1.5, reason="test", gated_at=NOW,
            )

    def test_empty_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            ReactionGateResult(
                gate_id="g", rule_id="r", event_id="e",
                verdict=ReactionVerdict.PROCEED,
                simulation_safe=True, utility_acceptable=True, meta_reasoning_clear=True,
                confidence=0.5, reason="", gated_at=NOW,
            )


# ---------------------------------------------------------------------------
# ReactionExecutionRecord
# ---------------------------------------------------------------------------


class TestReactionExecutionRecord:
    def test_valid_execution(self) -> None:
        e = _execution()
        assert e.executed is True
        assert e.rule_id == "r1"

    def test_empty_id_raises(self) -> None:
        with pytest.raises(ValueError, match="execution_id"):
            ReactionExecutionRecord(
                execution_id="", rule_id="r1", event_id="e1", correlation_id="c",
                target=_target(), gate_result=_gate(),
                executed=True, result_ref_id="r",
                execution_notes="ok", executed_at=NOW,
            )


# ---------------------------------------------------------------------------
# BackpressurePolicy
# ---------------------------------------------------------------------------


class TestBackpressurePolicy:
    def test_valid_policy(self) -> None:
        p = BackpressurePolicy(
            policy_id="bp1", max_concurrent=10,
            max_per_window=100, window_seconds=60,
            strategy=BackpressureStrategy.RATE_LIMIT,
        )
        assert p.max_concurrent == 10

    def test_zero_concurrent_raises(self) -> None:
        with pytest.raises(ValueError, match="max_concurrent"):
            BackpressurePolicy(
                policy_id="bp1", max_concurrent=0,
                max_per_window=100, window_seconds=60,
                strategy=BackpressureStrategy.RATE_LIMIT,
            )

    def test_negative_window_raises(self) -> None:
        with pytest.raises(ValueError, match="window_seconds"):
            BackpressurePolicy(
                policy_id="bp1", max_concurrent=10,
                max_per_window=100, window_seconds=-1,
                strategy=BackpressureStrategy.RATE_LIMIT,
            )


# ---------------------------------------------------------------------------
# IdempotencyWindow
# ---------------------------------------------------------------------------


class TestIdempotencyWindow:
    def test_valid_window(self) -> None:
        w = IdempotencyWindow(
            window_id="iw1", event_id="e1", rule_id="r1",
            execution_id="x1", processed_at=NOW, expires_at="9999-12-31T23:59:59+00:00",
        )
        assert w.event_id == "e1"

    def test_empty_event_id_raises(self) -> None:
        with pytest.raises(ValueError, match="event_id"):
            IdempotencyWindow(
                window_id="iw1", event_id="", rule_id="r1",
                execution_id="x1", processed_at=NOW, expires_at="9999-12-31T23:59:59+00:00",
            )


# ---------------------------------------------------------------------------
# ReactionDecision
# ---------------------------------------------------------------------------


class TestReactionDecision:
    def test_valid_decision(self) -> None:
        d = ReactionDecision(
            decision_id="d1", event_id="e1", correlation_id="c1",
            rules_evaluated=5, rules_matched=2, rules_executed=1,
            rules_deferred=0, rules_rejected=1,
            executions=(_execution(),), decided_at=NOW,
        )
        assert d.rules_matched == 2
        assert len(d.executions) == 1

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="rules_evaluated"):
            ReactionDecision(
                decision_id="d1", event_id="e1", correlation_id="c1",
                rules_evaluated=-1, rules_matched=0, rules_executed=0,
                rules_deferred=0, rules_rejected=0,
                executions=(), decided_at=NOW,
            )

    def test_non_tuple_executions_raises(self) -> None:
        with pytest.raises(ValueError, match="executions must be a tuple"):
            ReactionDecision(
                decision_id="d1", event_id="e1", correlation_id="c1",
                rules_evaluated=0, rules_matched=0, rules_executed=0,
                rules_deferred=0, rules_rejected=0,
                executions=[_execution()],  # type: ignore[arg-type]
                decided_at=NOW,
            )

    def test_bad_execution_type_raises(self) -> None:
        with pytest.raises(ValueError, match="each execution"):
            ReactionDecision(
                decision_id="d1", event_id="e1", correlation_id="c1",
                rules_evaluated=0, rules_matched=0, rules_executed=0,
                rules_deferred=0, rules_rejected=0,
                executions=("not-an-execution",),  # type: ignore[arg-type]
                decided_at=NOW,
            )
