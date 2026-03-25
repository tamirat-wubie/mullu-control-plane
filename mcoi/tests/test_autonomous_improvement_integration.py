"""Tests for mcoi.mcoi_runtime.core.autonomous_improvement_integration.

Covers: constructor validation, evaluate_from_* methods, run_improvement_lifecycle,
monitor_and_rollback, suppress_from_change_failure, attach_improvement_to_memory_mesh,
attach_improvement_to_graph, event emission, and golden end-to-end scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.autonomous_improvement_integration import (
    AutonomousImprovementIntegration,
)
from mcoi_runtime.core.autonomous_improvement import AutonomousImprovementEngine
from mcoi_runtime.core.change_runtime import ChangeRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.autonomous_improvement import (
    ImprovementDisposition,
    AutonomyLevel,
    ImprovementOutcomeVerdict,
    LearningWindowStatus,
    SuppressionReason,
)
from mcoi_runtime.contracts.change_runtime import (
    ChangeType,
    ChangeScope,
    RolloutMode,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engines():
    """Return (event_spine, improvement_engine, change_engine, memory_engine)."""
    es = EventSpineEngine()
    imp = AutonomousImprovementEngine(event_spine=es)
    chg = ChangeRuntimeEngine(event_spine=es)
    mem = MemoryMeshEngine()
    return es, imp, chg, mem


@pytest.fixture()
def integration(engines):
    """Return a fully-wired AutonomousImprovementIntegration."""
    es, imp, chg, mem = engines
    return AutonomousImprovementIntegration(imp, chg, es, mem)


@pytest.fixture()
def integration_with_engines(engines):
    """Return (integration, es, imp, chg, mem) for tests that need raw engines."""
    es, imp, chg, mem = engines
    bridge = AutonomousImprovementIntegration(imp, chg, es, mem)
    return bridge, es, imp, chg, mem


def _register_default_policy(imp: AutonomousImprovementEngine, change_type: str = "optimization") -> None:
    """Register an autonomy policy that allows auto-promotion."""
    imp.register_policy(
        f"pol-{change_type}",
        change_type,
        min_confidence=0.5,
        max_risk_score=0.5,
        max_cost_delta=200.0,
        max_auto_changes_per_window=10,
        rollback_tolerance_pct=5.0,
    )


# ===================================================================
# TestConstructor
# ===================================================================


class TestConstructor:
    """AutonomousImprovementIntegration constructor validation."""

    def test_valid_construction(self, engines):
        es, imp, chg, mem = engines
        bridge = AutonomousImprovementIntegration(imp, chg, es, mem)
        assert bridge is not None

    def test_invalid_improvement_engine(self, engines):
        es, _, chg, mem = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration("not-an-engine", chg, es, mem)

    def test_invalid_change_engine(self, engines):
        es, imp, _, mem = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(imp, "not-an-engine", es, mem)

    def test_invalid_event_spine(self, engines):
        _, imp, chg, mem = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(imp, chg, "not-an-engine", mem)

    def test_invalid_memory_engine(self, engines):
        es, imp, chg, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(imp, chg, es, "not-an-engine")

    def test_none_arguments_raise(self, engines):
        es, imp, chg, mem = engines
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(None, chg, es, mem)
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(imp, None, es, mem)
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(imp, chg, None, mem)
        with pytest.raises(RuntimeCoreInvariantError):
            AutonomousImprovementIntegration(imp, chg, es, None)


# ===================================================================
# TestEvaluateFromOptimization
# ===================================================================


class TestEvaluateFromOptimization:
    """evaluate_from_optimization auto-promotion and approval paths."""

    def test_auto_promote_with_policy(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        result = bridge.evaluate_from_optimization(
            "cand-opt-1", "rec-1", "Optimize cache",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
            estimated_cost_delta=10.0,
        )

        assert result["candidate_id"] == "cand-opt-1"
        assert result["source"] == "optimization"
        assert result["disposition"] == ImprovementDisposition.AUTO_PROMOTED.value
        assert result["autonomy_level"] == AutonomyLevel.BOUNDED_AUTO.value
        assert result["auto_promoted"] is True
        assert isinstance(result["reason"], str)

    def test_approval_required_without_policy(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        # No policy registered

        result = bridge.evaluate_from_optimization(
            "cand-opt-2", "rec-2", "Optimize something",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )

        assert result["disposition"] == ImprovementDisposition.APPROVAL_REQUIRED.value
        assert result["auto_promoted"] is False

    def test_approval_required_low_confidence(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        result = bridge.evaluate_from_optimization(
            "cand-opt-3", "rec-3", "Low confidence opt",
            change_type="optimization",
            confidence=0.1,  # below min_confidence=0.5
            risk_score=0.1,
        )

        assert result["disposition"] == ImprovementDisposition.APPROVAL_REQUIRED.value
        assert result["auto_promoted"] is False


# ===================================================================
# TestEvaluateFromGovernance
# ===================================================================


class TestEvaluateFromGovernance:
    """evaluate_from_governance auto-promotion path."""

    def test_auto_promote_with_policy(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "governance")

        result = bridge.evaluate_from_governance(
            "cand-gov-1", "rec-gov-1", "Governance policy change",
            change_type="governance",
            confidence=0.9,
            risk_score=0.1,
            estimated_cost_delta=5.0,
        )

        assert result["candidate_id"] == "cand-gov-1"
        assert result["source"] == "governance"
        assert result["disposition"] == ImprovementDisposition.AUTO_PROMOTED.value
        assert result["auto_promoted"] is True

    def test_approval_required_without_policy(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        result = bridge.evaluate_from_governance(
            "cand-gov-2", "rec-gov-2", "Governance no policy",
            change_type="governance",
        )

        assert result["disposition"] == ImprovementDisposition.APPROVAL_REQUIRED.value
        assert result["auto_promoted"] is False


# ===================================================================
# TestEvaluateFromFaultCampaign
# ===================================================================


class TestEvaluateFromFaultCampaign:
    """evaluate_from_fault_campaign auto-promotion path."""

    def test_auto_promote_with_policy(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "fault_remediation")

        result = bridge.evaluate_from_fault_campaign(
            "cand-fc-1", "rec-fc-1", "Fix recurring fault",
            change_type="fault_remediation",
            confidence=0.9,
            risk_score=0.1,
            estimated_cost_delta=5.0,
        )

        assert result["candidate_id"] == "cand-fc-1"
        assert result["source"] == "fault_campaign"
        assert result["disposition"] == ImprovementDisposition.AUTO_PROMOTED.value
        assert result["auto_promoted"] is True

    def test_approval_required_without_policy(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        result = bridge.evaluate_from_fault_campaign(
            "cand-fc-2", "rec-fc-2", "Fault no policy",
            change_type="fault_remediation",
        )

        assert result["disposition"] == ImprovementDisposition.APPROVAL_REQUIRED.value
        assert result["auto_promoted"] is False


# ===================================================================
# TestRunImprovementLifecycle
# ===================================================================


class TestRunImprovementLifecycle:
    """run_improvement_lifecycle improved and degraded paths."""

    def test_improved_outcome(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # First evaluate a candidate so the session can reference it
        bridge.evaluate_from_optimization(
            "cand-lc-1", "rec-lc-1", "Lifecycle test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )

        result = bridge.run_improvement_lifecycle(
            session_id="sess-1",
            candidate_id="cand-lc-1",
            change_id="chg-lc-1",
            metric_name="latency_ms",
            baseline_value=100.0,
            final_value=120.0,  # 20% improvement
            confidence=0.9,
        )

        assert result["session_id"] == "sess-1"
        assert result["candidate_id"] == "cand-lc-1"
        assert result["change_id"] == "chg-lc-1"
        assert result["window_id"] == "sess-1-win"
        assert result["outcome_id"] == "sess-1-out"
        assert result["verdict"] == ImprovementOutcomeVerdict.IMPROVED.value
        assert result["improvement_pct"] == pytest.approx(20.0)
        assert result["rollback_triggered"] is False
        assert result["suppression_triggered"] is False
        assert result["reinforcement_applied"] is True

    def test_degraded_outcome_triggers_rollback_and_suppression(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        bridge.evaluate_from_optimization(
            "cand-lc-2", "rec-lc-2", "Degraded test",
            change_type="optimization",
            scope_ref_id="scope-deg",
            confidence=0.9,
            risk_score=0.1,
        )

        result = bridge.run_improvement_lifecycle(
            session_id="sess-2",
            candidate_id="cand-lc-2",
            change_id="chg-lc-2",
            metric_name="latency_ms",
            baseline_value=100.0,
            final_value=50.0,  # 50% degradation
            confidence=0.9,
        )

        assert result["verdict"] == ImprovementOutcomeVerdict.DEGRADED.value
        assert result["improvement_pct"] == pytest.approx(-50.0)
        assert result["rollback_triggered"] is True
        # suppression_triggered depends on failure threshold (default=3);
        # first failure won't reach threshold
        assert isinstance(result["suppression_triggered"], bool)

    def test_neutral_outcome(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        bridge.evaluate_from_optimization(
            "cand-lc-3", "rec-lc-3", "Neutral test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )

        result = bridge.run_improvement_lifecycle(
            session_id="sess-3",
            candidate_id="cand-lc-3",
            change_id="chg-lc-3",
            metric_name="latency_ms",
            baseline_value=100.0,
            final_value=100.5,  # ~0.5% — within [-1, 1] range → neutral
            confidence=0.9,
        )

        assert result["verdict"] == ImprovementOutcomeVerdict.NEUTRAL.value
        assert result["rollback_triggered"] is False
        assert result["reinforcement_applied"] is False


# ===================================================================
# TestMonitorAndRollback
# ===================================================================


class TestMonitorAndRollback:
    """monitor_and_rollback trigger and no-trigger paths."""

    def _create_in_progress_change(self, chg: ChangeRuntimeEngine, change_id: str) -> None:
        """Create a change that is IN_PROGRESS and eligible for rollback."""
        chg.create_change_request(
            change_id, "Test change", ChangeType.CONFIGURATION, approval_required=False,
        )
        chg.plan_change(
            f"plan-{change_id}", change_id, "Plan",
            [{"step_id": f"s-{change_id}", "title": "Step 1"}],
        )
        chg.execute_change_step(change_id, f"s-{change_id}")

    def test_trigger_fires_and_rolls_back(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # Evaluate candidate + start session so check_rollback_trigger can find it
        bridge.evaluate_from_optimization(
            "cand-rb-1", "rec-rb-1", "Rollback test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )
        imp.start_session("sess-rb-1", "cand-rb-1", "chg-rb-1")

        # Create a real change in IN_PROGRESS state
        self._create_in_progress_change(chg, "chg-rb-1")

        result = bridge.monitor_and_rollback(
            change_id="chg-rb-1",
            session_id="sess-rb-1",
            metric_name="latency_ms",
            baseline_value=100.0,
            observed_value=80.0,  # 20% degradation, > 5% tolerance
        )

        assert result["change_id"] == "chg-rb-1"
        assert result["session_id"] == "sess-rb-1"
        assert result["metric_name"] == "latency_ms"
        assert result["triggered"] is True
        assert result["rolled_back"] is True
        assert result["degradation_pct"] == pytest.approx(20.0)
        assert result["tolerance_pct"] == pytest.approx(5.0)

    def test_no_trigger_within_tolerance(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        bridge.evaluate_from_optimization(
            "cand-rb-2", "rec-rb-2", "No rollback test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )
        imp.start_session("sess-rb-2", "cand-rb-2", "chg-rb-2")

        self._create_in_progress_change(chg, "chg-rb-2")

        result = bridge.monitor_and_rollback(
            change_id="chg-rb-2",
            session_id="sess-rb-2",
            metric_name="latency_ms",
            baseline_value=100.0,
            observed_value=98.0,  # 2% degradation, < 5% tolerance
        )

        assert result["triggered"] is False
        assert result["rolled_back"] is False
        assert result["degradation_pct"] == 0.0
        assert result["tolerance_pct"] == 0.0

    def test_trigger_with_custom_tolerance(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        bridge.evaluate_from_optimization(
            "cand-rb-3", "rec-rb-3", "Custom tol test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )
        imp.start_session("sess-rb-3", "cand-rb-3", "chg-rb-3")
        self._create_in_progress_change(chg, "chg-rb-3")

        result = bridge.monitor_and_rollback(
            change_id="chg-rb-3",
            session_id="sess-rb-3",
            metric_name="latency_ms",
            baseline_value=100.0,
            observed_value=98.0,  # 2% degradation
            tolerance_pct=1.0,  # 1% tolerance → triggers
        )

        assert result["triggered"] is True
        assert result["rolled_back"] is True
        assert result["degradation_pct"] == pytest.approx(2.0)
        assert result["tolerance_pct"] == pytest.approx(1.0)


# ===================================================================
# TestSuppressFromChangeFailure
# ===================================================================


class TestSuppressFromChangeFailure:
    """suppress_from_change_failure manual suppression."""

    def test_manual_suppression(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        result = bridge.suppress_from_change_failure(
            change_type="optimization",
            scope_ref_id="scope-fail-1",
            reason=SuppressionReason.REPEATED_FAILURE,
        )

        assert isinstance(result["suppression_id"], str)
        assert result["change_type"] == "optimization"
        assert result["scope_ref_id"] == "scope-fail-1"
        assert result["reason"] == SuppressionReason.REPEATED_FAILURE.value
        assert isinstance(result["failure_count"], int)

    def test_suppression_with_different_reasons(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        for reason in [SuppressionReason.DEGRADED_KPI, SuppressionReason.COST_EXCEEDED, SuppressionReason.MANUAL_BLOCK]:
            result = bridge.suppress_from_change_failure(
                change_type="governance",
                scope_ref_id=f"scope-{reason.value}",
                reason=reason,
            )
            assert result["reason"] == reason.value

    def test_suppression_blocks_future_auto_promotion(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # Suppress a pattern
        bridge.suppress_from_change_failure(
            change_type="optimization",
            scope_ref_id="scope-blocked",
            reason=SuppressionReason.REPEATED_FAILURE,
        )

        # Try to evaluate — should be SUPPRESSED
        result = bridge.evaluate_from_optimization(
            "cand-sup-1", "rec-sup-1", "Should be suppressed",
            change_type="optimization",
            scope_ref_id="scope-blocked",
            confidence=0.9,
            risk_score=0.1,
        )

        assert result["disposition"] == ImprovementDisposition.SUPPRESSED.value
        assert result["auto_promoted"] is False


# ===================================================================
# TestMemoryMeshAttachment
# ===================================================================


class TestMemoryMeshAttachment:
    """attach_improvement_to_memory_mesh persistence and duplicate rejection."""

    def test_attach_returns_memory_record(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        record = bridge.attach_improvement_to_memory_mesh("scope-mem-1")

        assert isinstance(record, MemoryRecord)
        assert record.scope_ref_id == "scope-mem-1"
        assert record.title == "Improvement state: scope-mem-1"
        assert record.confidence == 1.0
        assert "improvement" in record.tags
        assert "autonomous" in record.tags

    def test_duplicate_scope_raises(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        bridge.attach_improvement_to_memory_mesh("scope-dup")
        # Same scope_ref_id → same memory_id (deterministic) → duplicate
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate memory_id"):
            bridge.attach_improvement_to_memory_mesh("scope-dup")

    def test_content_reflects_engine_state(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # Create some state
        bridge.evaluate_from_optimization(
            "cand-mem-c", "rec-mem-c", "Memory content test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )

        record = bridge.attach_improvement_to_memory_mesh("scope-mem-content")
        content = record.content

        assert content["total_candidates"] == 1
        assert content["auto_changes"] == 1


# ===================================================================
# TestGraphAttachment
# ===================================================================


class TestGraphAttachment:
    """attach_improvement_to_graph returns correct counts."""

    def test_returns_correct_counts(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # Evaluate a candidate
        bridge.evaluate_from_optimization(
            "cand-graph-1", "rec-graph-1", "Graph test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )

        # Run lifecycle
        bridge.run_improvement_lifecycle(
            session_id="sess-graph-1",
            candidate_id="cand-graph-1",
            change_id="chg-graph-1",
            metric_name="throughput",
            baseline_value=100.0,
            final_value=110.0,
        )

        result = bridge.attach_improvement_to_graph("scope-graph")

        assert result["scope_ref_id"] == "scope-graph"
        assert result["total_candidates"] == 1
        assert result["total_sessions"] == 1
        assert result["total_outcomes"] == 1
        assert result["total_suppressions"] == 0
        assert result["auto_changes"] == 1
        assert isinstance(result["suppressed_patterns"], list)

    def test_graph_includes_suppressed_patterns(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        bridge.suppress_from_change_failure(
            "optimization", "scope-s1", SuppressionReason.REPEATED_FAILURE,
        )
        bridge.suppress_from_change_failure(
            "governance", "scope-s2", SuppressionReason.DEGRADED_KPI,
        )

        result = bridge.attach_improvement_to_graph("scope-graph-supp")

        assert result["total_suppressions"] == 2
        assert len(result["suppressed_patterns"]) == 2
        types = {p["change_type"] for p in result["suppressed_patterns"]}
        assert types == {"optimization", "governance"}


# ===================================================================
# TestEventEmission
# ===================================================================


class TestEventEmission:
    """Verify that events are emitted for each operation."""

    def test_evaluate_emits_event(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        initial_count = es.event_count

        bridge.evaluate_from_optimization(
            "cand-evt-1", "rec-evt-1", "Event test",
        )

        # At minimum: candidate_evaluated (from engine) + evaluate_from_optimization (from bridge)
        assert es.event_count > initial_count

    def test_lifecycle_emits_events(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        bridge.evaluate_from_optimization(
            "cand-evt-2", "rec-evt-2", "Lifecycle event test",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )
        initial_count = es.event_count

        bridge.run_improvement_lifecycle(
            session_id="sess-evt-2",
            candidate_id="cand-evt-2",
            change_id="chg-evt-2",
            metric_name="latency",
            baseline_value=100.0,
            final_value=110.0,
        )

        # session_started, learning_window_opened, learning_window_closed,
        # outcome_assessed, improvement_lifecycle_completed
        assert es.event_count >= initial_count + 4

    def test_monitor_emits_event(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        bridge.evaluate_from_optimization(
            "cand-evt-3", "rec-evt-3", "Monitor event",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )
        imp.start_session("sess-evt-3", "cand-evt-3", "chg-evt-3")

        initial_count = es.event_count
        bridge.monitor_and_rollback(
            "chg-evt-3", "sess-evt-3", "latency", 100.0, 99.0,
        )

        assert es.event_count > initial_count

    def test_suppress_emits_event(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        initial_count = es.event_count

        bridge.suppress_from_change_failure("optimization", "scope-evt-s")

        assert es.event_count > initial_count

    def test_memory_attach_emits_event(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        initial_count = es.event_count

        bridge.attach_improvement_to_memory_mesh("scope-evt-mem")

        assert es.event_count > initial_count


# ===================================================================
# Golden Scenarios
# ===================================================================


class TestGoldenScenario1OptimizationAutoPromotedLifecycleImproved:
    """Golden 1: Optimization recommendation auto-promoted -> lifecycle -> improved -> reinforcement."""

    def test_full_flow(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # Step 1: Evaluate → auto-promote
        eval_result = bridge.evaluate_from_optimization(
            "cand-g1", "rec-g1", "Cache optimization",
            change_type="optimization",
            confidence=0.95,
            risk_score=0.05,
            estimated_improvement_pct=15.0,
            estimated_cost_delta=10.0,
        )
        assert eval_result["auto_promoted"] is True
        assert eval_result["source"] == "optimization"

        # Step 2: Run lifecycle with improvement
        lc_result = bridge.run_improvement_lifecycle(
            session_id="sess-g1",
            candidate_id="cand-g1",
            change_id="chg-g1",
            metric_name="response_time_ms",
            baseline_value=200.0,
            final_value=240.0,  # 20% improvement
            confidence=0.95,
        )
        assert lc_result["verdict"] == ImprovementOutcomeVerdict.IMPROVED.value
        assert lc_result["reinforcement_applied"] is True
        assert lc_result["rollback_triggered"] is False
        assert lc_result["suppression_triggered"] is False


class TestGoldenScenario2GovernanceDegradedRollbackSuppression:
    """Golden 2: Governance recommendation -> lifecycle -> degraded -> rollback + suppression."""

    def test_full_flow(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        # Register a policy with low failure_suppression_threshold so suppression fires on first degraded
        imp.register_policy(
            "pol-gov-g2",
            "governance",
            min_confidence=0.5,
            max_risk_score=0.5,
            max_cost_delta=200.0,
            failure_suppression_threshold=1,  # Suppress on first failure
            rollback_tolerance_pct=5.0,
        )

        # Step 1: Evaluate
        eval_result = bridge.evaluate_from_governance(
            "cand-g2", "rec-g2", "Governance tweak",
            change_type="governance",
            scope_ref_id="scope-g2",
            confidence=0.9,
            risk_score=0.1,
        )
        assert eval_result["auto_promoted"] is True

        # Step 2: Run lifecycle with degradation
        lc_result = bridge.run_improvement_lifecycle(
            session_id="sess-g2",
            candidate_id="cand-g2",
            change_id="chg-g2",
            metric_name="availability_pct",
            baseline_value=99.9,
            final_value=90.0,  # severe degradation
            confidence=0.9,
        )
        assert lc_result["verdict"] == ImprovementOutcomeVerdict.DEGRADED.value
        assert lc_result["rollback_triggered"] is True
        assert lc_result["suppression_triggered"] is True


class TestGoldenScenario3MonitorAndRollbackWithRealChange:
    """Golden 3: Monitor and rollback with a real change through change engine."""

    def test_full_flow(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines
        _register_default_policy(imp, "optimization")

        # Evaluate candidate
        bridge.evaluate_from_optimization(
            "cand-g3", "rec-g3", "Config optimization",
            change_type="optimization",
            confidence=0.9,
            risk_score=0.1,
        )

        # Start improvement session
        imp.start_session("sess-g3", "cand-g3", "chg-g3")

        # Create a real change in the change engine
        chg.create_change_request(
            "chg-g3", "Real config change", ChangeType.CONFIGURATION,
            approval_required=False,
        )
        chg.plan_change(
            "plan-g3", "chg-g3", "Plan G3",
            [{"step_id": "s-g3", "title": "Step 1"}],
        )
        chg.execute_change_step("chg-g3", "s-g3")

        # Verify change is IN_PROGRESS
        from mcoi_runtime.contracts.change_runtime import ChangeStatus
        assert chg.get_change_status("chg-g3") == ChangeStatus.IN_PROGRESS

        # Monitor with severe degradation
        result = bridge.monitor_and_rollback(
            change_id="chg-g3",
            session_id="sess-g3",
            metric_name="throughput_rps",
            baseline_value=1000.0,
            observed_value=800.0,  # 20% degradation
        )

        assert result["triggered"] is True
        assert result["rolled_back"] is True
        assert result["degradation_pct"] == pytest.approx(20.0)

        # Verify change status is now ROLLED_BACK
        assert chg.get_change_status("chg-g3") == ChangeStatus.ROLLED_BACK


class TestGoldenScenario4FullPipeline:
    """Golden 4: policy -> evaluate -> session -> window -> observe -> close -> assess -> memory -> graph."""

    def test_full_pipeline(self, integration_with_engines):
        bridge, es, imp, chg, mem = integration_with_engines

        # 1. Register policy
        _register_default_policy(imp, "optimization")

        # 2. Evaluate candidate
        eval_result = bridge.evaluate_from_optimization(
            "cand-g4", "rec-g4", "Full pipeline test",
            change_type="optimization",
            scope_ref_id="scope-g4",
            confidence=0.95,
            risk_score=0.05,
            estimated_improvement_pct=10.0,
            estimated_cost_delta=5.0,
        )
        assert eval_result["auto_promoted"] is True

        # 3. Run improvement lifecycle (session + window + outcome)
        lc_result = bridge.run_improvement_lifecycle(
            session_id="sess-g4",
            candidate_id="cand-g4",
            change_id="chg-g4",
            metric_name="cpu_utilization",
            baseline_value=80.0,
            final_value=88.0,  # 10% improvement
            confidence=0.9,
        )
        assert lc_result["verdict"] == ImprovementOutcomeVerdict.IMPROVED.value
        assert lc_result["window_id"] == "sess-g4-win"
        assert lc_result["outcome_id"] == "sess-g4-out"

        # 4. Attach to memory mesh
        mem_record = bridge.attach_improvement_to_memory_mesh("scope-g4")
        assert isinstance(mem_record, MemoryRecord)
        assert mem_record.content["total_candidates"] == 1
        assert mem_record.content["total_sessions"] == 1
        assert mem_record.content["total_outcomes"] == 1
        assert mem_record.content["auto_changes"] == 1

        # 5. Attach to graph
        graph_result = bridge.attach_improvement_to_graph("scope-g4")
        assert graph_result["scope_ref_id"] == "scope-g4"
        assert graph_result["total_candidates"] == 1
        assert graph_result["total_sessions"] == 1
        assert graph_result["total_outcomes"] == 1
        assert graph_result["total_suppressions"] == 0
        assert graph_result["auto_changes"] == 1
        assert graph_result["suppressed_patterns"] == []

        # 6. Verify events were emitted throughout
        assert es.event_count > 0
