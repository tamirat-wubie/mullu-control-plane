"""Tests for benchmark contracts — enums, scenarios, suites, metrics, results,
runs, adversarial cases, regression records, and capability scorecards."""

import pytest

from mcoi_runtime.contracts.benchmark import (
    AdversarialCase,
    AdversarialCategory,
    AdversarialSeverity,
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
    RegressionRecord,
    ScorecardStatus,
)


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnums:
    def test_benchmark_category_values(self):
        assert len(BenchmarkCategory) == 13
        assert BenchmarkCategory.GOVERNANCE == "governance"
        assert BenchmarkCategory.CROSS_PLANE == "cross_plane"

    def test_benchmark_outcome_values(self):
        assert len(BenchmarkOutcome) == 5
        assert BenchmarkOutcome.PASS == "pass"
        assert BenchmarkOutcome.TIMEOUT == "timeout"

    def test_adversarial_severity_values(self):
        assert len(AdversarialSeverity) == 4
        assert AdversarialSeverity.BENIGN == "benign"
        assert AdversarialSeverity.CATASTROPHIC == "catastrophic"

    def test_adversarial_category_values(self):
        assert len(AdversarialCategory) == 11
        assert AdversarialCategory.CONFLICTING_POLICIES == "conflicting_policies"
        assert AdversarialCategory.RESOURCE_EXHAUSTION == "resource_exhaustion"

    def test_metric_kind_values(self):
        assert len(MetricKind) == 10
        assert MetricKind.ACCURACY == "accuracy"
        assert MetricKind.CUSTOM == "custom"

    def test_regression_direction_values(self):
        assert len(RegressionDirection) == 3
        assert RegressionDirection.IMPROVED == "improved"

    def test_scorecard_status_values(self):
        assert len(ScorecardStatus) == 4
        assert ScorecardStatus.HEALTHY == "healthy"


# ---------------------------------------------------------------------------
# BenchmarkScenario
# ---------------------------------------------------------------------------


class TestBenchmarkScenario:
    def _valid(self, **overrides):
        defaults = dict(
            scenario_id="sc-001",
            name="test scenario",
            description="a test",
            category=BenchmarkCategory.GOVERNANCE,
            inputs={"key": "value"},
            expected_outcome=BenchmarkOutcome.PASS,
        )
        defaults.update(overrides)
        return BenchmarkScenario(**defaults)

    def test_valid_creation(self):
        s = self._valid()
        assert s.scenario_id == "sc-001"
        assert s.category == BenchmarkCategory.GOVERNANCE
        assert s.timeout_ms == 30000

    def test_inputs_frozen(self):
        s = self._valid(inputs={"a": [1, 2]})
        assert isinstance(s.inputs["a"], tuple)

    def test_tags_frozen(self):
        s = self._valid(tags=["fast", "gov"])
        assert isinstance(s.tags, tuple)
        assert s.tags == ("fast", "gov")

    def test_empty_scenario_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(scenario_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            self._valid(name="")

    def test_invalid_category_rejected(self):
        with pytest.raises(ValueError):
            self._valid(category="not_a_category")

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValueError):
            self._valid(timeout_ms=0)


# ---------------------------------------------------------------------------
# BenchmarkSuite
# ---------------------------------------------------------------------------


class TestBenchmarkSuite:
    def _scenario(self, sid="sc-001"):
        return BenchmarkScenario(
            scenario_id=sid,
            name="s",
            description="d",
            category=BenchmarkCategory.GOVERNANCE,
            inputs={},
            expected_outcome=BenchmarkOutcome.PASS,
        )

    def _valid(self, **overrides):
        defaults = dict(
            suite_id="suite-001",
            name="gov suite",
            category=BenchmarkCategory.GOVERNANCE,
            scenarios=(self._scenario(),),
            version="1.0.0",
            created_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return BenchmarkSuite(**defaults)

    def test_valid_creation(self):
        s = self._valid()
        assert s.suite_id == "suite-001"
        assert s.scenario_count == 1

    def test_duplicate_scenario_ids_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            self._valid(scenarios=(self._scenario("sc-x"), self._scenario("sc-x")))

    def test_empty_suite_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(suite_id="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            self._valid(created_at="not-a-date")


# ---------------------------------------------------------------------------
# BenchmarkMetric
# ---------------------------------------------------------------------------


class TestBenchmarkMetric:
    def _valid(self, **overrides):
        defaults = dict(
            metric_id="m-001",
            kind=MetricKind.ACCURACY,
            name="accuracy",
            value=0.95,
            threshold=0.90,
            passed=True,
        )
        defaults.update(overrides)
        return BenchmarkMetric(**defaults)

    def test_valid_creation(self):
        m = self._valid()
        assert m.passed is True
        assert m.value == 0.95

    def test_value_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            self._valid(value=1.5)

    def test_negative_value_rejected(self):
        with pytest.raises(ValueError):
            self._valid(value=-0.1)

    def test_passed_must_be_bool(self):
        with pytest.raises(ValueError):
            self._valid(passed="yes")

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValueError):
            self._valid(kind="invalid")


# ---------------------------------------------------------------------------
# BenchmarkResult
# ---------------------------------------------------------------------------


class TestBenchmarkResult:
    def _metric(self):
        return BenchmarkMetric(
            metric_id="m-001",
            kind=MetricKind.ACCURACY,
            name="acc",
            value=0.9,
            threshold=0.8,
            passed=True,
        )

    def _valid(self, **overrides):
        defaults = dict(
            result_id="r-001",
            scenario_id="sc-001",
            outcome=BenchmarkOutcome.PASS,
            metrics=(self._metric(),),
            actual_properties={"key": "val"},
            executed_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return BenchmarkResult(**defaults)

    def test_valid_creation(self):
        r = self._valid()
        assert r.passed is True
        assert r.metric_pass_rate == 1.0

    def test_failed_outcome(self):
        r = self._valid(outcome=BenchmarkOutcome.FAIL)
        assert r.passed is False

    def test_empty_metrics_pass_rate(self):
        r = self._valid(metrics=())
        assert r.metric_pass_rate == 1.0

    def test_mixed_metrics_rate(self):
        m_pass = BenchmarkMetric(
            metric_id="m-p", kind=MetricKind.ACCURACY, name="a", value=0.9, threshold=0.8, passed=True
        )
        m_fail = BenchmarkMetric(
            metric_id="m-f", kind=MetricKind.ACCURACY, name="b", value=0.5, threshold=0.8, passed=False
        )
        r = self._valid(metrics=(m_pass, m_fail))
        assert r.metric_pass_rate == 0.5

    def test_invalid_outcome_rejected(self):
        with pytest.raises(ValueError):
            self._valid(outcome="invalid")


# ---------------------------------------------------------------------------
# BenchmarkRun
# ---------------------------------------------------------------------------


class TestBenchmarkRun:
    def _result(self, rid="r-001", outcome=BenchmarkOutcome.PASS):
        return BenchmarkResult(
            result_id=rid,
            scenario_id="sc-001",
            outcome=outcome,
            metrics=(),
            actual_properties={},
            executed_at="2025-01-01T00:00:00Z",
        )

    def _valid(self, **overrides):
        defaults = dict(
            run_id="run-001",
            suite_id="suite-001",
            results=(self._result(),),
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:01:00Z",
        )
        defaults.update(overrides)
        return BenchmarkRun(**defaults)

    def test_valid_creation(self):
        run = self._valid()
        assert run.pass_count == 1
        assert run.fail_count == 0
        assert run.pass_rate == 1.0
        assert run.total == 1

    def test_mixed_results(self):
        run = self._valid(results=(
            self._result("r-1", BenchmarkOutcome.PASS),
            self._result("r-2", BenchmarkOutcome.FAIL),
        ))
        assert run.pass_count == 1
        assert run.fail_count == 1
        assert run.pass_rate == 0.5

    def test_empty_results(self):
        run = self._valid(results=())
        assert run.pass_rate == 1.0
        assert run.total == 0

    def test_metadata_frozen(self):
        run = self._valid(metadata={"env": "test"})
        from types import MappingProxyType
        assert isinstance(run.metadata, MappingProxyType)


# ---------------------------------------------------------------------------
# AdversarialCase
# ---------------------------------------------------------------------------


class TestAdversarialCase:
    def _valid(self, **overrides):
        defaults = dict(
            case_id="ac-001",
            name="test case",
            description="adversarial test",
            category=AdversarialCategory.MALFORMED_INPUT,
            severity=AdversarialSeverity.MODERATE,
            target_subsystem=BenchmarkCategory.GOVERNANCE,
            attack_vector="inject malformed data",
            inputs={"payload": "bad"},
            expected_behavior="validation rejects",
        )
        defaults.update(overrides)
        return AdversarialCase(**defaults)

    def test_valid_creation(self):
        c = self._valid()
        assert c.case_id == "ac-001"
        assert c.severity == AdversarialSeverity.MODERATE

    def test_inputs_frozen(self):
        c = self._valid(inputs={"a": [1]})
        assert isinstance(c.inputs["a"], tuple)

    def test_tags_frozen(self):
        c = self._valid(tags=["x", "y"])
        assert c.tags == ("x", "y")

    def test_empty_case_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(case_id="")

    def test_invalid_category_rejected(self):
        with pytest.raises(ValueError):
            self._valid(category="bad")

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            self._valid(severity="bad")


# ---------------------------------------------------------------------------
# RegressionRecord
# ---------------------------------------------------------------------------


class TestRegressionRecord:
    def _valid(self, **overrides):
        defaults = dict(
            regression_id="reg-001",
            metric_name="pass_rate",
            category=BenchmarkCategory.GOVERNANCE,
            baseline_value=0.95,
            current_value=0.85,
            direction=RegressionDirection.DEGRADED,
            delta=-0.10,
            baseline_run_id="run-001",
            current_run_id="run-002",
            detected_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return RegressionRecord(**defaults)

    def test_valid_creation(self):
        r = self._valid()
        assert r.is_regression is True

    def test_improved_not_regression(self):
        r = self._valid(direction=RegressionDirection.IMPROVED)
        assert r.is_regression is False

    def test_stable_not_regression(self):
        r = self._valid(direction=RegressionDirection.STABLE)
        assert r.is_regression is False

    def test_out_of_range_value_rejected(self):
        with pytest.raises(ValueError):
            self._valid(baseline_value=1.5)

    def test_empty_metric_name_rejected(self):
        with pytest.raises(ValueError):
            self._valid(metric_name="")


# ---------------------------------------------------------------------------
# CapabilityScorecard
# ---------------------------------------------------------------------------


class TestCapabilityScorecard:
    def _regression(self):
        return RegressionRecord(
            regression_id="reg-001",
            metric_name="pass_rate",
            category=BenchmarkCategory.GOVERNANCE,
            baseline_value=0.95,
            current_value=0.85,
            direction=RegressionDirection.DEGRADED,
            delta=-0.10,
            baseline_run_id="run-001",
            current_run_id="run-002",
            detected_at="2025-01-01T00:00:00Z",
        )

    def _valid(self, **overrides):
        defaults = dict(
            scorecard_id="sc-001",
            category=BenchmarkCategory.GOVERNANCE,
            status=ScorecardStatus.HEALTHY,
            pass_rate=0.98,
            metric_count=10,
            metrics_passing=9,
            adversarial_pass_rate=0.90,
            regressions=(),
            confidence_trend="stable-high",
            assessed_at="2025-01-01T00:00:00Z",
        )
        defaults.update(overrides)
        return CapabilityScorecard(**defaults)

    def test_valid_creation(self):
        s = self._valid()
        assert s.is_healthy is True
        assert s.regression_count == 0

    def test_with_regressions(self):
        s = self._valid(regressions=(self._regression(),))
        assert s.regression_count == 1

    def test_not_healthy(self):
        s = self._valid(status=ScorecardStatus.FAILING)
        assert s.is_healthy is False

    def test_pass_rate_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            self._valid(pass_rate=1.5)

    def test_negative_metric_count_rejected(self):
        with pytest.raises(ValueError):
            self._valid(metric_count=-1)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._valid(status="bad")
