"""Golden scenario tests for the benchmark subsystem — end-to-end pipeline
validation covering suite creation, evaluation, adversarial runs, scorecard
generation, regression detection, and dashboard summary extraction."""

import pytest

from mcoi_runtime.contracts.benchmark import (
    AdversarialCategory,
    BenchmarkCategory,
    BenchmarkMetric,
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkScenario,
    BenchmarkSuite,
    CapabilityScorecard,
    MetricKind,
    RegressionDirection,
    ScorecardStatus,
)
from mcoi_runtime.core.benchmark_engine import BenchmarkEngine
from mcoi_runtime.core.benchmark_integration import BenchmarkBridge
from mcoi_runtime.core.scorecard_engine import ScorecardEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_tick = 0


def _clock():
    global _tick
    _tick += 1
    return f"2025-06-01T00:00:{_tick:02d}Z"


def _reset():
    global _tick
    _tick = 0


def _pass_evaluator(scenario):
    m = BenchmarkMetric(
        metric_id="m-auto",
        kind=MetricKind.ACCURACY,
        name="accuracy",
        value=0.95,
        threshold=0.80,
        passed=True,
    )
    return BenchmarkOutcome.PASS, [m], {"validated": True}, None


def _fail_evaluator(scenario):
    m = BenchmarkMetric(
        metric_id="m-auto",
        kind=MetricKind.ACCURACY,
        name="accuracy",
        value=0.40,
        threshold=0.80,
        passed=False,
    )
    return BenchmarkOutcome.FAIL, [m], {}, "accuracy below threshold"


# ---------------------------------------------------------------------------
# Golden: full pipeline — create, evaluate, scorecard, summary
# ---------------------------------------------------------------------------


class TestGoldenFullPipeline:
    def setup_method(self):
        _reset()

    def test_governance_benchmark_healthy(self):
        """Full pipeline: governance suite passes → healthy scorecard."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _pass_evaluator)

        sc1 = BenchmarkBridge.create_scenario(
            "gov-policy-eval",
            "Policy evaluation correctness",
            BenchmarkCategory.GOVERNANCE,
            {"rule_count": 5},
            BenchmarkOutcome.PASS,
        )
        sc2 = BenchmarkBridge.create_scenario(
            "gov-scope-filter",
            "Scope filtering accuracy",
            BenchmarkCategory.GOVERNANCE,
            {"scope_kinds": 8},
            BenchmarkOutcome.PASS,
        )
        suite = BenchmarkBridge.create_suite(
            "governance-core",
            BenchmarkCategory.GOVERNANCE,
            (sc1, sc2),
            "1.0.0",
            "2025-01-01T00:00:00Z",
        )

        run = engine.run_suite(suite)
        assert run.pass_rate == 1.0
        assert run.total == 2

        scorecard_engine = ScorecardEngine(clock=_clock)
        sc = scorecard_engine.build_scorecard(BenchmarkCategory.GOVERNANCE, run)
        assert sc.status == ScorecardStatus.HEALTHY
        assert sc.pass_rate == 1.0
        assert sc.is_healthy is True

    def test_simulation_benchmark_failing(self):
        """Full pipeline: simulation suite fails → failing scorecard."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.SIMULATION, _fail_evaluator)

        sc1 = BenchmarkBridge.create_scenario(
            "sim-risk-scoring",
            "Risk scoring accuracy",
            BenchmarkCategory.SIMULATION,
            {"options": 3},
            BenchmarkOutcome.PASS,
        )
        suite = BenchmarkBridge.create_suite(
            "simulation-core",
            BenchmarkCategory.SIMULATION,
            (sc1,),
            "1.0.0",
            "2025-01-01T00:00:00Z",
        )

        run = engine.run_suite(suite)
        assert run.pass_rate == 0.0

        scorecard_engine = ScorecardEngine(clock=_clock)
        sc = scorecard_engine.build_scorecard(BenchmarkCategory.SIMULATION, run)
        assert sc.status == ScorecardStatus.FAILING
        assert sc.is_healthy is False


class TestGoldenRegression:
    def setup_method(self):
        _reset()

    def test_regression_detected_between_runs(self):
        """Two runs: baseline all-pass, current 50% fail → regression detected."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _pass_evaluator)

        scenarios = tuple(
            BenchmarkBridge.create_scenario(
                f"gov-check-{i}",
                f"Check {i}",
                BenchmarkCategory.GOVERNANCE,
                {"i": i},
                BenchmarkOutcome.PASS,
            )
            for i in range(4)
        )
        suite = BenchmarkBridge.create_suite(
            "gov-reg", BenchmarkCategory.GOVERNANCE, scenarios, "1.0.0", "2025-01-01T00:00:00Z"
        )

        baseline_run = engine.run_suite(suite)
        assert baseline_run.pass_rate == 1.0

        # Now switch to failing evaluator for current run
        call_count = 0
        def half_fail(scenario):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return BenchmarkOutcome.FAIL, [], {}, "fail"
            return BenchmarkOutcome.PASS, [], {}, None

        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, half_fail)
        current_run = engine.run_suite(suite)
        assert current_run.pass_rate == 0.5

        scorecard_engine = ScorecardEngine(clock=_clock)
        sc = scorecard_engine.build_scorecard(
            BenchmarkCategory.GOVERNANCE, current_run, baseline_run=baseline_run
        )
        assert len(sc.regressions) == 1
        assert sc.regressions[0].direction == RegressionDirection.DEGRADED
        assert sc.regressions[0].is_regression is True

    def test_improvement_detected(self):
        """Baseline poor, current improved → improvement recorded."""
        engine = BenchmarkEngine(clock=_clock)

        scenarios = tuple(
            BenchmarkBridge.create_scenario(
                f"check-{i}",
                f"Check {i}",
                BenchmarkCategory.UTILITY,
                {},
                BenchmarkOutcome.PASS,
            )
            for i in range(4)
        )
        suite = BenchmarkBridge.create_suite(
            "util-reg", BenchmarkCategory.UTILITY, scenarios, "1.0.0", "2025-01-01T00:00:00Z"
        )

        # Baseline: 50% fail
        call_count = 0
        def half_fail(scenario):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return BenchmarkOutcome.FAIL, [], {}, "fail"
            return BenchmarkOutcome.PASS, [], {}, None

        engine.register_evaluator(BenchmarkCategory.UTILITY, half_fail)
        baseline_run = engine.run_suite(suite)

        # Current: all pass
        engine.register_evaluator(BenchmarkCategory.UTILITY, _pass_evaluator)
        current_run = engine.run_suite(suite)

        scorecard_engine = ScorecardEngine(clock=_clock)
        sc = scorecard_engine.build_scorecard(
            BenchmarkCategory.UTILITY, current_run, baseline_run=baseline_run
        )
        assert sc.regressions[0].direction == RegressionDirection.IMPROVED


class TestGoldenAdversarial:
    def setup_method(self):
        _reset()

    def test_adversarial_evaluation_via_bridge(self):
        """Evaluate adversarial cases through the bridge."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _pass_evaluator)

        from mcoi_runtime.core.adversarial_packs import conflicting_policies_pack
        cases = conflicting_policies_pack()
        results = BenchmarkBridge.evaluate_adversarial_cases(
            engine, cases, BenchmarkCategory.GOVERNANCE
        )
        assert len(results) == 3
        assert all(r.outcome == BenchmarkOutcome.PASS for r in results)

    def test_adversarial_affects_scorecard(self):
        """Adversarial failures lower the adversarial_pass_rate on scorecard."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _pass_evaluator)

        sc = BenchmarkBridge.create_scenario(
            "gov-base", "base check", BenchmarkCategory.GOVERNANCE, {}, BenchmarkOutcome.PASS
        )
        suite = BenchmarkBridge.create_suite(
            "gov-adv", BenchmarkCategory.GOVERNANCE, (sc,), "1.0.0", "2025-01-01T00:00:00Z"
        )
        run = engine.run_suite(suite)

        # Simulate adversarial results — 1 pass, 1 fail
        adv_pass = BenchmarkResult(
            result_id="adv-p",
            scenario_id="adv-sc-p",
            outcome=BenchmarkOutcome.PASS,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )
        adv_fail = BenchmarkResult(
            result_id="adv-f",
            scenario_id="adv-sc-f",
            outcome=BenchmarkOutcome.FAIL,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )

        scorecard_engine = ScorecardEngine(clock=_clock)
        sc = scorecard_engine.build_scorecard(
            BenchmarkCategory.GOVERNANCE, run, adversarial_results=(adv_pass, adv_fail)
        )
        assert sc.adversarial_pass_rate == 0.5


class TestGoldenDashboardSummary:
    def setup_method(self):
        _reset()

    def test_extract_summary_from_scorecards(self):
        """Extract dashboard summary from multiple scorecards."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _pass_evaluator)
        engine.register_evaluator(BenchmarkCategory.SIMULATION, _fail_evaluator)

        gov_sc = BenchmarkBridge.create_scenario(
            "gov-s", "gov", BenchmarkCategory.GOVERNANCE, {}, BenchmarkOutcome.PASS
        )
        sim_sc = BenchmarkBridge.create_scenario(
            "sim-s", "sim", BenchmarkCategory.SIMULATION, {}, BenchmarkOutcome.PASS
        )

        gov_suite = BenchmarkBridge.create_suite(
            "gov", BenchmarkCategory.GOVERNANCE, (gov_sc,), "1.0.0", "2025-01-01T00:00:00Z"
        )
        sim_suite = BenchmarkBridge.create_suite(
            "sim", BenchmarkCategory.SIMULATION, (sim_sc,), "1.0.0", "2025-01-01T00:00:00Z"
        )

        gov_run = engine.run_suite(gov_suite)
        sim_run = engine.run_suite(sim_suite)

        scorecard_engine = ScorecardEngine(clock=_clock)
        scorecards = scorecard_engine.build_all_scorecards({
            BenchmarkCategory.GOVERNANCE: gov_run,
            BenchmarkCategory.SIMULATION: sim_run,
        })

        summary = BenchmarkBridge.extract_summary(scorecards)
        assert summary["total_categories"] == 2
        assert summary["healthy_count"] >= 0
        assert "governance" in summary["categories"] or "simulation" in summary["categories"]
        assert summary["overall_pass_rate"] >= 0.0

    def test_empty_summary(self):
        summary = BenchmarkBridge.extract_summary(())
        assert summary["total_categories"] == 0
        assert summary["overall_pass_rate"] == 1.0


class TestGoldenBridgeFactories:
    def test_create_scenario(self):
        sc = BenchmarkBridge.create_scenario(
            "test-sc", "Test scenario", BenchmarkCategory.GOVERNANCE, {"x": 1}, BenchmarkOutcome.PASS
        )
        assert sc.name == "test-sc"
        assert sc.scenario_id  # deterministic, non-empty

    def test_create_suite(self):
        sc = BenchmarkBridge.create_scenario(
            "sc-1", "s", BenchmarkCategory.GOVERNANCE, {}, BenchmarkOutcome.PASS
        )
        suite = BenchmarkBridge.create_suite(
            "suite-1", BenchmarkCategory.GOVERNANCE, (sc,), "2.0.0", "2025-01-01T00:00:00Z"
        )
        assert suite.name == "suite-1"
        assert suite.scenario_count == 1

    def test_create_metric(self):
        m = BenchmarkBridge.create_metric("acc", MetricKind.ACCURACY, 0.95, 0.80)
        assert m.passed is True
        assert m.value == 0.95

    def test_create_metric_failing(self):
        m = BenchmarkBridge.create_metric("acc", MetricKind.ACCURACY, 0.50, 0.80)
        assert m.passed is False


class TestGoldenFullPipelineMethod:
    def setup_method(self):
        _reset()

    def test_full_evaluation_pipeline(self):
        """Full pipeline method: suites → runs → scorecards."""
        engine = BenchmarkEngine(clock=_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _pass_evaluator)

        sc = BenchmarkBridge.create_scenario(
            "gov-full", "full check", BenchmarkCategory.GOVERNANCE, {}, BenchmarkOutcome.PASS
        )
        suite = BenchmarkBridge.create_suite(
            "gov-full", BenchmarkCategory.GOVERNANCE, (sc,), "1.0.0", "2025-01-01T00:00:00Z"
        )

        scorecard_engine = ScorecardEngine(clock=_clock)
        runs, scorecards = BenchmarkBridge.full_evaluation_pipeline(
            engine,
            scorecard_engine,
            {BenchmarkCategory.GOVERNANCE: suite},
            include_adversarial=True,
        )
        assert BenchmarkCategory.GOVERNANCE in runs
        assert len(scorecards) >= 1
