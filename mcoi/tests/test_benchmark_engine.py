"""Tests for benchmark engine, scorecard engine, and adversarial packs."""

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
from mcoi_runtime.core.scorecard_engine import ScorecardEngine, detect_regressions
from mcoi_runtime.core.adversarial_packs import (
    all_adversarial_cases,
    all_adversarial_packs,
    adversarial_cases_for_subsystem,
    conflicting_policies_pack,
    malformed_input_pack,
    deceptive_payload_pack,
    ambiguous_approval_pack,
    stale_world_state_pack,
    high_event_churn_pack,
    overloaded_workers_pack,
    provider_volatility_pack,
    simulation_utility_disagreement_pack,
    replay_idempotency_pack,
    resource_exhaustion_pack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_tick = 0


def _test_clock():
    global _tick
    _tick += 1
    return f"2025-01-01T00:00:{_tick:02d}Z"


def _reset_clock():
    global _tick
    _tick = 0


@pytest.fixture(autouse=True)
def _auto_reset_clock():
    """Reset the module-level clock before each test for isolation."""
    _reset_clock()
    yield
    _reset_clock()


def _make_scenario(sid="sc-001", category=BenchmarkCategory.GOVERNANCE):
    return BenchmarkScenario(
        scenario_id=sid,
        name=f"scenario-{sid}",
        description="test scenario",
        category=category,
        inputs={"key": "value"},
        expected_outcome=BenchmarkOutcome.PASS,
    )


def _make_suite(scenarios=None, category=BenchmarkCategory.GOVERNANCE):
    if scenarios is None:
        scenarios = (_make_scenario(),)
    return BenchmarkSuite(
        suite_id="suite-001",
        name="test suite",
        category=category,
        scenarios=scenarios,
        version="1.0.0",
        created_at="2025-01-01T00:00:00Z",
    )


def _passing_evaluator(scenario):
    metric = BenchmarkMetric(
        metric_id="m-001",
        kind=MetricKind.ACCURACY,
        name="accuracy",
        value=0.95,
        threshold=0.90,
        passed=True,
    )
    return BenchmarkOutcome.PASS, [metric], {"checked": True}, None


def _failing_evaluator(scenario):
    metric = BenchmarkMetric(
        metric_id="m-001",
        kind=MetricKind.ACCURACY,
        name="accuracy",
        value=0.50,
        threshold=0.90,
        passed=False,
    )
    return BenchmarkOutcome.FAIL, [metric], {}, "below threshold"


def _error_evaluator(scenario):
    raise RuntimeError("evaluator crash")


# ---------------------------------------------------------------------------
# BenchmarkEngine tests
# ---------------------------------------------------------------------------


class TestBenchmarkEngine:
    def setup_method(self):
        _reset_clock()

    def test_register_and_check_evaluator(self):
        engine = BenchmarkEngine(clock=_test_clock)
        assert engine.has_evaluator(BenchmarkCategory.GOVERNANCE) is False
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _passing_evaluator)
        assert engine.has_evaluator(BenchmarkCategory.GOVERNANCE) is True

    def test_invalid_category_rejected(self):
        engine = BenchmarkEngine(clock=_test_clock)
        with pytest.raises(ValueError):
            engine.register_evaluator("bad", _passing_evaluator)

    def test_non_callable_rejected(self):
        engine = BenchmarkEngine(clock=_test_clock)
        with pytest.raises(ValueError):
            engine.register_evaluator(BenchmarkCategory.GOVERNANCE, "not_callable")

    def test_evaluate_scenario_pass(self):
        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _passing_evaluator)
        result = engine.evaluate_scenario(_make_scenario())
        assert result.outcome == BenchmarkOutcome.PASS
        assert len(result.metrics) == 1
        assert result.passed is True

    def test_evaluate_scenario_fail(self):
        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _failing_evaluator)
        result = engine.evaluate_scenario(_make_scenario())
        assert result.outcome == BenchmarkOutcome.FAIL
        assert result.error_message == "below threshold"

    def test_evaluate_scenario_no_evaluator(self):
        engine = BenchmarkEngine(clock=_test_clock)
        result = engine.evaluate_scenario(_make_scenario())
        assert result.outcome == BenchmarkOutcome.SKIP
        assert "No evaluator" in result.error_message

    def test_evaluate_scenario_evaluator_error(self):
        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _error_evaluator)
        result = engine.evaluate_scenario(_make_scenario())
        assert result.outcome == BenchmarkOutcome.ERROR
        assert "evaluator crash" in result.error_message

    def test_invalid_scenario_rejected(self):
        engine = BenchmarkEngine(clock=_test_clock)
        with pytest.raises(ValueError):
            engine.evaluate_scenario("not a scenario")

    def test_run_suite(self):
        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _passing_evaluator)
        suite = _make_suite()
        run = engine.run_suite(suite)
        assert run.suite_id == "suite-001"
        assert run.total == 1
        assert run.pass_rate == 1.0

    def test_run_suite_multiple_scenarios(self):
        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _passing_evaluator)
        scenarios = (_make_scenario("sc-1"), _make_scenario("sc-2"), _make_scenario("sc-3"))
        suite = _make_suite(scenarios=scenarios)
        run = engine.run_suite(suite)
        assert run.total == 3
        assert run.pass_count == 3

    def test_run_tracking(self):
        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, _passing_evaluator)
        suite = _make_suite()
        engine.run_suite(suite)
        assert engine.run_count() == 1
        runs = engine.list_runs()
        assert len(runs) == 1
        engine.clear_runs()
        assert engine.run_count() == 0

    def test_invalid_suite_rejected(self):
        engine = BenchmarkEngine(clock=_test_clock)
        with pytest.raises(ValueError):
            engine.run_suite("not a suite")

    def test_mixed_pass_fail_suite(self):
        call_count = 0
        def alternating_evaluator(scenario):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return BenchmarkOutcome.FAIL, [], {}, "fail"
            return BenchmarkOutcome.PASS, [], {}, None

        engine = BenchmarkEngine(clock=_test_clock)
        engine.register_evaluator(BenchmarkCategory.GOVERNANCE, alternating_evaluator)
        scenarios = (_make_scenario("s1"), _make_scenario("s2"), _make_scenario("s3"), _make_scenario("s4"))
        suite = _make_suite(scenarios=scenarios)
        run = engine.run_suite(suite)
        assert run.pass_count == 2
        assert run.fail_count == 2
        assert run.pass_rate == 0.5


# ---------------------------------------------------------------------------
# ScorecardEngine tests
# ---------------------------------------------------------------------------


class TestScorecardEngine:
    def _make_run(self, results, run_id="run-001"):
        return BenchmarkRun(
            run_id=run_id,
            suite_id="suite-001",
            results=tuple(results),
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:01:00Z",
        )

    def _pass_result(self, rid="r-001"):
        return BenchmarkResult(
            result_id=rid,
            scenario_id="sc-001",
            outcome=BenchmarkOutcome.PASS,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )

    def _fail_result(self, rid="r-002"):
        return BenchmarkResult(
            result_id=rid,
            scenario_id="sc-002",
            outcome=BenchmarkOutcome.FAIL,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )

    def test_healthy_scorecard(self):
        engine = ScorecardEngine(clock=_test_clock)
        _reset_clock()
        run = self._make_run([self._pass_result(f"r-{i}") for i in range(20)])
        sc = engine.build_scorecard(BenchmarkCategory.GOVERNANCE, run)
        assert sc.status == ScorecardStatus.HEALTHY
        assert sc.pass_rate == 1.0
        assert sc.is_healthy is True

    def test_failing_scorecard(self):
        engine = ScorecardEngine(clock=_test_clock)
        _reset_clock()
        results = [self._fail_result(f"r-{i}") for i in range(10)]
        run = self._make_run(results)
        sc = engine.build_scorecard(BenchmarkCategory.GOVERNANCE, run)
        assert sc.status == ScorecardStatus.FAILING
        assert sc.pass_rate == 0.0

    def test_degraded_scorecard(self):
        engine = ScorecardEngine(clock=_test_clock)
        _reset_clock()
        results = [self._pass_result(f"r-{i}") for i in range(8)]
        results.extend([self._fail_result(f"r-f{i}") for i in range(2)])
        run = self._make_run(results)
        sc = engine.build_scorecard(BenchmarkCategory.GOVERNANCE, run)
        assert sc.status == ScorecardStatus.DEGRADED
        assert 0.70 <= sc.pass_rate <= 0.90

    def test_scorecard_with_regression(self):
        engine = ScorecardEngine(clock=_test_clock)
        _reset_clock()
        baseline = self._make_run(
            [self._pass_result(f"r-{i}") for i in range(10)], run_id="baseline"
        )
        current = self._make_run(
            [self._pass_result(f"r-{i}") for i in range(5)]
            + [self._fail_result(f"r-f{i}") for i in range(5)],
            run_id="current",
        )
        sc = engine.build_scorecard(
            BenchmarkCategory.GOVERNANCE, current, baseline_run=baseline
        )
        assert len(sc.regressions) == 1
        assert sc.regressions[0].direction == RegressionDirection.DEGRADED

    def test_scorecard_with_adversarial(self):
        engine = ScorecardEngine(clock=_test_clock)
        _reset_clock()
        run = self._make_run([self._pass_result()])
        adv_pass = BenchmarkResult(
            result_id="adv-1",
            scenario_id="adv-sc-1",
            outcome=BenchmarkOutcome.PASS,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )
        adv_fail = BenchmarkResult(
            result_id="adv-2",
            scenario_id="adv-sc-2",
            outcome=BenchmarkOutcome.FAIL,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )
        sc = engine.build_scorecard(
            BenchmarkCategory.GOVERNANCE, run, adversarial_results=(adv_pass, adv_fail)
        )
        assert sc.adversarial_pass_rate == 0.5

    def test_build_all_scorecards(self):
        engine = ScorecardEngine(clock=_test_clock)
        _reset_clock()
        runs = {
            BenchmarkCategory.GOVERNANCE: self._make_run([self._pass_result()], "run-gov"),
            BenchmarkCategory.SIMULATION: self._make_run([self._pass_result("r-sim")], "run-sim"),
        }
        scorecards = engine.build_all_scorecards(runs)
        assert len(scorecards) == 2


# ---------------------------------------------------------------------------
# Regression detection tests
# ---------------------------------------------------------------------------


class TestRegressionDetection:
    def _make_run(self, pass_count, fail_count, run_id="run-001"):
        results = []
        for i in range(pass_count):
            results.append(BenchmarkResult(
                result_id=f"p-{i}",
                scenario_id=f"sc-{i}",
                outcome=BenchmarkOutcome.PASS,
                metrics=(),
                actual_properties={},
                executed_at="2025-01-01T00:00:00Z",
            ))
        for i in range(fail_count):
            results.append(BenchmarkResult(
                result_id=f"f-{i}",
                scenario_id=f"sc-f-{i}",
                outcome=BenchmarkOutcome.FAIL,
                metrics=(),
                actual_properties={},
                executed_at="2025-01-01T00:00:00Z",
            ))
        return BenchmarkRun(
            run_id=run_id,
            suite_id="suite-001",
            results=tuple(results),
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:01:00Z",
        )

    def test_stable_when_identical(self):
        baseline = self._make_run(10, 0, "baseline")
        current = self._make_run(10, 0, "current")
        regs = detect_regressions(baseline, current, BenchmarkCategory.GOVERNANCE, clock=_test_clock)
        _reset_clock()
        assert regs[0].direction == RegressionDirection.STABLE

    def test_degraded_detected(self):
        baseline = self._make_run(10, 0, "baseline")
        current = self._make_run(5, 5, "current")
        _reset_clock()
        regs = detect_regressions(baseline, current, BenchmarkCategory.GOVERNANCE, clock=_test_clock)
        assert regs[0].direction == RegressionDirection.DEGRADED
        assert regs[0].is_regression is True

    def test_improved_detected(self):
        baseline = self._make_run(5, 5, "baseline")
        current = self._make_run(10, 0, "current")
        _reset_clock()
        regs = detect_regressions(baseline, current, BenchmarkCategory.GOVERNANCE, clock=_test_clock)
        assert regs[0].direction == RegressionDirection.IMPROVED

    def test_small_change_within_threshold(self):
        baseline = self._make_run(100, 0, "baseline")
        current = self._make_run(97, 3, "current")
        _reset_clock()
        regs = detect_regressions(
            baseline, current, BenchmarkCategory.GOVERNANCE, clock=_test_clock, threshold=0.05
        )
        assert regs[0].direction == RegressionDirection.STABLE


# ---------------------------------------------------------------------------
# Adversarial pack tests
# ---------------------------------------------------------------------------


class TestAdversarialPacks:
    def test_conflicting_policies_pack(self):
        cases = conflicting_policies_pack()
        assert len(cases) == 3
        assert all(c.category == AdversarialCategory.CONFLICTING_POLICIES for c in cases)

    def test_malformed_input_pack(self):
        cases = malformed_input_pack()
        assert len(cases) == 3
        assert all(c.category == AdversarialCategory.MALFORMED_INPUT for c in cases)

    def test_deceptive_payload_pack(self):
        cases = deceptive_payload_pack()
        assert len(cases) == 2

    def test_ambiguous_approval_pack(self):
        cases = ambiguous_approval_pack()
        assert len(cases) == 2

    def test_stale_world_state_pack(self):
        cases = stale_world_state_pack()
        assert len(cases) == 2

    def test_high_event_churn_pack(self):
        cases = high_event_churn_pack()
        assert len(cases) == 2

    def test_overloaded_workers_pack(self):
        cases = overloaded_workers_pack()
        assert len(cases) == 2

    def test_provider_volatility_pack(self):
        cases = provider_volatility_pack()
        assert len(cases) == 2

    def test_simulation_utility_disagreement_pack(self):
        cases = simulation_utility_disagreement_pack()
        assert len(cases) == 2

    def test_replay_idempotency_pack(self):
        cases = replay_idempotency_pack()
        assert len(cases) == 2

    def test_resource_exhaustion_pack(self):
        cases = resource_exhaustion_pack()
        assert len(cases) == 2

    def test_all_packs_indexed(self):
        packs = all_adversarial_packs()
        assert len(packs) == 11
        for category, cases in packs.items():
            assert isinstance(category, AdversarialCategory)
            assert len(cases) >= 2

    def test_all_cases_flat(self):
        cases = all_adversarial_cases()
        assert len(cases) == 24  # 3+3+2+2+2+2+2+2+2+2+2 = 24

    def test_cases_for_subsystem(self):
        gov_cases = adversarial_cases_for_subsystem(BenchmarkCategory.GOVERNANCE)
        assert len(gov_cases) >= 5  # conflicting_policies(3) + malformed(1) + deceptive(2) + ambiguous(2)
        assert all(c.target_subsystem == BenchmarkCategory.GOVERNANCE for c in gov_cases)

    def test_all_cases_have_unique_ids(self):
        cases = all_adversarial_cases()
        ids = [c.case_id for c in cases]
        assert len(ids) == len(set(ids))

    def test_all_cases_are_valid_contracts(self):
        """Every adversarial case is a valid frozen dataclass — construction itself validates."""
        cases = all_adversarial_cases()
        for c in cases:
            assert c.case_id
            assert c.name
            assert c.description
            assert c.attack_vector
            assert c.expected_behavior
