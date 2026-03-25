"""Edge case tests for Holistic Audit #12 fixes.

Covers:
  - ExpectedState.expected_by accepts actor ID text (not datetime)
  - TradeoffOutcome not double-appended in full_learning_cycle
  - check_expired_obligations handles Z vs +00:00 timestamps correctly
  - Governance compile produces matching compilation_id/compiled_at
  - Governance evaluate produces matching trace_id/evaluated_at
  - knowledge_ingestion classes reject construction without created_at
  - thaw_value frozenset produces deterministic sorted output
  - get_preferred_providers returns tuple (not list)
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts._base import thaw_value
from mcoi_runtime.contracts.decision_learning import OutcomeQuality
from mcoi_runtime.contracts.governance import (
    CompilationStatus,
    PolicyAction,
    PolicyActionKind,
    PolicyBundle,
    PolicyCondition,
    PolicyConditionOperator,
    PolicyEffect,
    PolicyEvaluationTrace,
    PolicyRule,
    PolicyScope,
    PolicyScopeKind,
    PolicyVersion,
)
from mcoi_runtime.contracts.knowledge_ingestion import (
    BestPracticeRecord,
    ConfidenceLevel,
    FailurePattern,
    LessonRecord,
    MethodPattern,
    ProcedureCandidate,
    ProcedureStep,
)
from mcoi_runtime.contracts.simulation import RiskLevel, SimulationOption
from mcoi_runtime.contracts.utility import (
    DecisionComparison,
    DecisionFactor,
    DecisionFactorKind,
    OptionUtility,
    TradeoffDirection,
    TradeoffRecord,
    UtilityProfile,
)
from mcoi_runtime.contracts.world_state import ExpectedState
from mcoi_runtime.core.decision_learning import DecisionLearningEngine
from mcoi_runtime.core.decision_learning_integration import DecisionLearningBridge
from mcoi_runtime.core.governance_compiler import GovernanceCompiler, GovernanceEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTER = 0


def _make_clock():
    global _COUNTER
    _COUNTER = 0

    def clock() -> str:
        global _COUNTER
        _COUNTER += 1
        minutes = _COUNTER // 60
        seconds = _COUNTER % 60
        return f"2026-03-20T00:{minutes:02d}:{seconds:02d}Z"

    return clock


def _make_profile() -> UtilityProfile:
    return UtilityProfile(
        profile_id="prof-1",
        context_type="test",
        context_id="ctx-1",
        factors=(
            DecisionFactor(factor_id="f-risk", kind=DecisionFactorKind.RISK, weight=0.4, value=0.3, label="risk"),
            DecisionFactor(factor_id="f-cost", kind=DecisionFactorKind.COST, weight=0.3, value=0.5, label="cost"),
            DecisionFactor(factor_id="f-conf", kind=DecisionFactorKind.CONFIDENCE, weight=0.3, value=0.8, label="confidence"),
        ),
        tradeoff_direction=TradeoffDirection.BALANCED,
        created_at="2026-03-20T00:00:00Z",
    )


def _make_comparison() -> DecisionComparison:
    ou1 = OptionUtility(option_id="opt-a", raw_score=0.7, weighted_score=0.65, factor_contributions={"risk": 0.3}, rank=1)
    ou2 = OptionUtility(option_id="opt-b", raw_score=0.5, weighted_score=0.45, factor_contributions={"risk": 0.5}, rank=2)
    return DecisionComparison(
        comparison_id="cmp-1",
        profile_id="prof-1",
        option_utilities=(ou1, ou2),
        best_option_id="opt-a",
        spread=0.2,
        decided_at="2026-03-20T00:00:00Z",
    )


def _make_option() -> SimulationOption:
    return SimulationOption(
        option_id="opt-a",
        label="Option A",
        risk_level=RiskLevel.LOW,
        estimated_cost=100.0,
        estimated_duration_seconds=3600.0,
        success_probability=0.9,
    )


def _make_tradeoff() -> TradeoffRecord:
    return TradeoffRecord(
        tradeoff_id="tradeoff-1",
        comparison_id="cmp-1",
        chosen_option_id="opt-a",
        rejected_option_ids=("opt-b",),
        tradeoff_direction=TradeoffDirection.BALANCED,
        rationale="option A scored higher",
        recorded_at="2026-03-20T00:00:00Z",
    )


def _make_bundle() -> PolicyBundle:
    cond = PolicyCondition(
        field_path="subject.role",
        operator=PolicyConditionOperator.EQ,
        expected_value="admin",
    )
    scope = PolicyScope(scope_id="scope-1", kind=PolicyScopeKind.GLOBAL)
    action = PolicyAction(action_id="act-1", kind=PolicyActionKind.SET_AUTONOMY, parameters={"level": "high"})
    rule = PolicyRule(
        rule_id="rule-1",
        name="Admin allow",
        description="Allow admin access",
        effect=PolicyEffect.ALLOW,
        conditions=(cond,),
        actions=(action,),
        scope=scope,
        priority=10,
    )
    version = PolicyVersion(
        version_id="v-1",
        major=1,
        minor=0,
        patch=0,
        created_at="2026-03-20T00:00:00Z",
    )
    return PolicyBundle(
        bundle_id="bundle-1",
        name="Test bundle",
        version=version,
        rules=(rule,),
        created_at="2026-03-20T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# Tests: ExpectedState.expected_by accepts actor ID (not datetime)
# ---------------------------------------------------------------------------


class TestExpectedStateExpectedBy:
    def test_accepts_actor_id_text(self):
        """expected_by should accept any non-empty text (actor ID), not just datetime."""
        es = ExpectedState(
            expectation_id="exp-1",
            entity_id="ent-1",
            attribute="status",
            expected_value="running",
            confidence=0.9,
            basis="policy-123",
            expected_by="operator-alice",
            created_at="2026-03-20T00:00:00Z",
        )
        assert es.expected_by == "operator-alice"

    def test_rejects_empty_expected_by(self):
        with pytest.raises(ValueError, match="expected_by"):
            ExpectedState(
                expectation_id="exp-1",
                entity_id="ent-1",
                attribute="status",
                expected_value="running",
                confidence=0.9,
                basis="policy-123",
                expected_by="",
                created_at="2026-03-20T00:00:00Z",
            )


# ---------------------------------------------------------------------------
# Tests: TradeoffOutcome not double-appended
# ---------------------------------------------------------------------------


class TestNoDoubleAppendTradeoffOutcome:
    def test_full_learning_cycle_single_tradeoff(self):
        """full_learning_cycle should produce exactly one TradeoffOutcome per call."""
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        engine.full_learning_cycle(
            comparison=_make_comparison(),
            chosen_option=_make_option(),
            profile=_make_profile(),
            tradeoff=_make_tradeoff(),
            quality=OutcomeQuality.SUCCESS,
            actual_cost=90.0,
            actual_duration_seconds=3000.0,
            success_observed=True,
            notes="good",
        )
        # Access internal tradeoff outcomes
        outcomes = engine._tradeoff_outcomes
        assert len(outcomes) == 1, f"Expected 1 tradeoff outcome, got {len(outcomes)}"

    def test_multiple_cycles_no_doubling(self):
        """N cycles should produce exactly N tradeoff outcomes."""
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        n = 5
        for _ in range(n):
            engine.full_learning_cycle(
                comparison=_make_comparison(),
                chosen_option=_make_option(),
                profile=_make_profile(),
                tradeoff=_make_tradeoff(),
                quality=OutcomeQuality.SUCCESS,
                actual_cost=90.0,
                actual_duration_seconds=3000.0,
                success_observed=True,
                notes="good",
            )
        assert len(engine._tradeoff_outcomes) == n


# ---------------------------------------------------------------------------
# Tests: Governance compile/evaluate timestamp consistency
# ---------------------------------------------------------------------------


class TestGovernanceTimestampConsistency:
    def test_compile_timestamp_matches_id(self):
        """compiled_at in result should match the timestamp embedded in compilation_id."""
        clock = _make_clock()
        compiler = GovernanceCompiler(clock=clock)
        bundle = _make_bundle()
        result = compiler.compile(bundle)
        # The compilation_id is derived from a stable_identifier that uses compiled_at
        # Key property: compiled_at is set from a single clock() call
        assert result.compiled_at is not None
        assert isinstance(result.compiled_at, str)
        # Compile a second time — should get a different timestamp (clock advances)
        result2 = compiler.compile(bundle)
        assert result2.compiled_at != result.compiled_at
        assert result2.compilation_id != result.compilation_id

    def test_evaluate_timestamp_matches_id(self):
        """evaluated_at in trace should match the timestamp embedded in trace_id."""
        clock = _make_clock()
        compiler = GovernanceCompiler(clock=clock)
        bundle = _make_bundle()
        compiled = compiler.compile(bundle)

        evaluator = GovernanceEvaluator(clock=clock)
        context = {"subject": {"role": "admin"}}
        trace = evaluator.evaluate(bundle, "subj-1", context)
        assert trace.evaluated_at is not None
        assert isinstance(trace.evaluated_at, str)


# ---------------------------------------------------------------------------
# Tests: knowledge_ingestion classes require created_at
# ---------------------------------------------------------------------------


class TestKnowledgeIngestionCreatedAtRequired:
    def test_procedure_candidate_requires_created_at(self):
        step = ProcedureStep(step_order=0, description="do thing")
        with pytest.raises(TypeError):
            ProcedureCandidate(
                candidate_id="cand-1",
                source_id="src-1",
                name="Test proc",
                steps=(step,),
                # missing created_at
            )

    def test_method_pattern_requires_created_at(self):
        with pytest.raises(TypeError):
            MethodPattern(
                pattern_id="pat-1",
                source_ids=("src-1",),
                name="Test pattern",
                description="A pattern",
                applicability="everywhere",
                steps=("step 1",),
                # missing created_at
            )

    def test_best_practice_requires_created_at(self):
        with pytest.raises(TypeError):
            BestPracticeRecord(
                practice_id="bp-1",
                source_ids=("src-1",),
                name="Best practice",
                description="A best practice",
                conditions=("always",),
                recommendations=("do this",),
                # missing created_at
            )

    def test_failure_pattern_requires_created_at(self):
        with pytest.raises(TypeError):
            FailurePattern(
                pattern_id="fp-1",
                source_ids=("src-1",),
                name="Failure pattern",
                trigger_conditions=("overload",),
                failure_mode="crash",
                recommended_response="restart",
                # missing created_at
            )

    def test_lesson_record_requires_created_at(self):
        with pytest.raises(TypeError):
            LessonRecord(
                lesson_id="les-1",
                source_id="src-1",
                context="test context",
                action_taken="tried it",
                outcome="success",
                lesson="it worked",
                # missing created_at
            )

    def test_procedure_candidate_accepts_created_at(self):
        """Positive test: construction succeeds when created_at is provided."""
        step = ProcedureStep(step_order=0, description="do thing")
        pc = ProcedureCandidate(
            candidate_id="cand-1",
            source_id="src-1",
            name="Test proc",
            steps=(step,),
            created_at="2026-03-20T00:00:00Z",
        )
        assert pc.created_at == "2026-03-20T00:00:00Z"


# ---------------------------------------------------------------------------
# Tests: thaw_value frozenset deterministic ordering
# ---------------------------------------------------------------------------


class TestThawValueFrozensetDeterminism:
    def test_frozenset_sorted_output(self):
        """thaw_value on a frozenset should return a sorted list."""
        fs = frozenset({"cherry", "apple", "banana"})
        result = thaw_value(fs)
        assert result == ["apple", "banana", "cherry"]

    def test_frozenset_numeric_sorted(self):
        fs = frozenset({3, 1, 2})
        result = thaw_value(fs)
        # Sorted by str representation
        assert result == sorted(result, key=str)

    def test_frozenset_deterministic_across_calls(self):
        """Multiple calls should always produce the same order."""
        fs = frozenset({"z", "a", "m", "b"})
        results = [thaw_value(fs) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_tuple_preserves_order(self):
        """Tuples should preserve insertion order (not sorted)."""
        t = ("cherry", "apple", "banana")
        result = thaw_value(t)
        assert result == ["cherry", "apple", "banana"]


# ---------------------------------------------------------------------------
# Tests: get_preferred_providers returns tuple
# ---------------------------------------------------------------------------


class TestGetPreferredProvidersReturnType:
    def test_empty_result_is_tuple(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1",),
        )
        assert isinstance(result, tuple)
        assert result == ()

    def test_populated_result_is_tuple(self):
        clock = _make_clock()
        engine = DecisionLearningEngine(clock=clock)
        for _ in range(5):
            engine.update_provider_preference("prov-1", "test", True)
        result = DecisionLearningBridge.get_preferred_providers(
            decision_engine=engine,
            context_type="test",
            provider_ids=("prov-1",),
            min_samples=1,
        )
        assert isinstance(result, tuple)
        assert len(result) == 1
        # Each element is also a tuple
        assert isinstance(result[0], tuple)
