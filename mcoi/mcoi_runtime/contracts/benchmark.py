"""Purpose: canonical benchmark and adversarial evaluation contracts for
measuring capability quality, decision reliability, governance correctness,
and failure behavior under stress.
Governance scope: benchmark plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Benchmarks are reproducible — same scenario, same inputs, same expected behavior.
  - Adversarial cases are explicit — no hidden malice.
  - Scorecards aggregate measured evidence, not estimates.
  - Regression records link current run to previous baseline.
  - All metrics are bounded and validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BenchmarkCategory(StrEnum):
    """What subsystem a benchmark targets."""

    GOVERNANCE = "governance"
    SIMULATION = "simulation"
    UTILITY = "utility"
    REACTION = "reaction"
    JOB_RUNTIME = "job_runtime"
    TEAM_FUNCTION = "team_function"
    PROVIDER_ROUTING = "provider_routing"
    RECOVERY_PLAYBOOK = "recovery_playbook"
    WORLD_STATE = "world_state"
    META_REASONING = "meta_reasoning"
    OBLIGATION = "obligation"
    EVENT_SPINE = "event_spine"
    CROSS_PLANE = "cross_plane"


class BenchmarkOutcome(StrEnum):
    """Result of a single benchmark scenario execution."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"
    TIMEOUT = "timeout"


class AdversarialSeverity(StrEnum):
    """How hostile the adversarial case is."""

    BENIGN = "benign"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CATASTROPHIC = "catastrophic"


class AdversarialCategory(StrEnum):
    """Classification of adversarial attack vectors."""

    CONFLICTING_POLICIES = "conflicting_policies"
    MALFORMED_INPUT = "malformed_input"
    DECEPTIVE_PAYLOAD = "deceptive_payload"
    AMBIGUOUS_APPROVAL = "ambiguous_approval"
    STALE_WORLD_STATE = "stale_world_state"
    HIGH_EVENT_CHURN = "high_event_churn"
    OVERLOADED_WORKERS = "overloaded_workers"
    PROVIDER_VOLATILITY = "provider_volatility"
    SIMULATION_UTILITY_DISAGREEMENT = "simulation_utility_disagreement"
    REPLAY_IDEMPOTENCY = "replay_idempotency"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class MetricKind(StrEnum):
    """What a benchmark metric measures."""

    ACCURACY = "accuracy"
    CORRECTNESS = "correctness"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RECOVERY_RATE = "recovery_rate"
    FALSE_POSITIVE_RATE = "false_positive_rate"
    FALSE_NEGATIVE_RATE = "false_negative_rate"
    COVERAGE = "coverage"
    STABILITY = "stability"
    CUSTOM = "custom"


class RegressionDirection(StrEnum):
    """Whether a metric change is an improvement or degradation."""

    IMPROVED = "improved"
    DEGRADED = "degraded"
    STABLE = "stable"


class ScorecardStatus(StrEnum):
    """Overall health of a subsystem scorecard."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Benchmark scenario and suite
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BenchmarkScenario(ContractRecord):
    """A single reproducible benchmark scenario with inputs and expected behavior."""

    scenario_id: str
    name: str
    description: str
    category: BenchmarkCategory
    inputs: Mapping[str, Any]
    expected_outcome: BenchmarkOutcome
    expected_properties: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    timeout_ms: int = 30000

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.category, BenchmarkCategory):
            raise ValueError("category must be a BenchmarkCategory value")
        object.__setattr__(self, "inputs", freeze_value(self.inputs))
        if not isinstance(self.expected_outcome, BenchmarkOutcome):
            raise ValueError("expected_outcome must be a BenchmarkOutcome value")
        object.__setattr__(self, "expected_properties", freeze_value(self.expected_properties))
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        object.__setattr__(self, "timeout_ms", require_positive_int(self.timeout_ms, "timeout_ms"))


@dataclass(frozen=True, slots=True)
class BenchmarkSuite(ContractRecord):
    """A versioned collection of benchmark scenarios for a subsystem."""

    suite_id: str
    name: str
    category: BenchmarkCategory
    scenarios: tuple[BenchmarkScenario, ...]
    version: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "suite_id", require_non_empty_text(self.suite_id, "suite_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.category, BenchmarkCategory):
            raise ValueError("category must be a BenchmarkCategory value")
        object.__setattr__(self, "scenarios", freeze_value(list(self.scenarios)))
        if not self.scenarios:
            raise ValueError("scenarios must contain at least one BenchmarkScenario")
        for s in self.scenarios:
            if not isinstance(s, BenchmarkScenario):
                raise ValueError("each scenario must be a BenchmarkScenario instance")
        # Unique scenario IDs
        ids = [s.scenario_id for s in self.scenarios]
        if len(ids) != len(set(ids)):
            raise ValueError("scenario_id values must be unique within a suite")
        object.__setattr__(self, "version", require_non_empty_text(self.version, "version"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))

    @property
    def scenario_count(self) -> int:
        return len(self.scenarios)


# ---------------------------------------------------------------------------
# Metrics and results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BenchmarkMetric(ContractRecord):
    """A single measured metric from a benchmark run."""

    metric_id: str
    kind: MetricKind
    name: str
    value: float
    threshold: float
    passed: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_id", require_non_empty_text(self.metric_id, "metric_id"))
        if not isinstance(self.kind, MetricKind):
            raise ValueError("kind must be a MetricKind value")
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "value", require_unit_float(self.value, "value"))
        object.__setattr__(self, "threshold", require_unit_float(self.threshold, "threshold"))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        if (self.value >= self.threshold) != self.passed:
            raise ValueError("passed must be True iff value >= threshold")


@dataclass(frozen=True, slots=True)
class BenchmarkResult(ContractRecord):
    """Result of executing a single benchmark scenario."""

    result_id: str
    scenario_id: str
    outcome: BenchmarkOutcome
    metrics: tuple[BenchmarkMetric, ...]
    actual_properties: Mapping[str, Any]
    error_message: str | None = None
    duration_ms: int = 0
    executed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        if not isinstance(self.outcome, BenchmarkOutcome):
            raise ValueError("outcome must be a BenchmarkOutcome value")
        object.__setattr__(self, "metrics", freeze_value(list(self.metrics)))
        for m in self.metrics:
            if not isinstance(m, BenchmarkMetric):
                raise ValueError("each metric must be a BenchmarkMetric instance")
        object.__setattr__(self, "actual_properties", freeze_value(self.actual_properties))
        object.__setattr__(self, "duration_ms", require_non_negative_int(self.duration_ms, "duration_ms"))
        object.__setattr__(self, "executed_at", require_datetime_text(self.executed_at, "executed_at"))

    @property
    def passed(self) -> bool:
        return self.outcome == BenchmarkOutcome.PASS

    @property
    def metric_pass_rate(self) -> float:
        if not self.metrics:
            return 1.0
        return sum(1 for m in self.metrics if m.passed) / len(self.metrics)


@dataclass(frozen=True, slots=True)
class BenchmarkRun(ContractRecord):
    """A complete benchmark run — a suite executed against the runtime."""

    run_id: str
    suite_id: str
    results: tuple[BenchmarkResult, ...]
    started_at: str
    finished_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_non_empty_text(self.run_id, "run_id"))
        object.__setattr__(self, "suite_id", require_non_empty_text(self.suite_id, "suite_id"))
        object.__setattr__(self, "results", freeze_value(list(self.results)))
        for r in self.results:
            if not isinstance(r, BenchmarkResult):
                raise ValueError("each result must be a BenchmarkResult instance")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 1.0
        return self.pass_count / len(self.results)

    @property
    def total(self) -> int:
        return len(self.results)


# ---------------------------------------------------------------------------
# Adversarial cases
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdversarialCase(ContractRecord):
    """An explicit adversarial test case designed to stress-test a subsystem."""

    case_id: str
    name: str
    description: str
    category: AdversarialCategory
    severity: AdversarialSeverity
    target_subsystem: BenchmarkCategory
    attack_vector: str
    inputs: Mapping[str, Any]
    expected_behavior: str
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        if not isinstance(self.category, AdversarialCategory):
            raise ValueError("category must be an AdversarialCategory value")
        if not isinstance(self.severity, AdversarialSeverity):
            raise ValueError("severity must be an AdversarialSeverity value")
        if not isinstance(self.target_subsystem, BenchmarkCategory):
            raise ValueError("target_subsystem must be a BenchmarkCategory value")
        object.__setattr__(self, "attack_vector", require_non_empty_text(self.attack_vector, "attack_vector"))
        object.__setattr__(self, "inputs", freeze_value(self.inputs))
        object.__setattr__(self, "expected_behavior", require_non_empty_text(self.expected_behavior, "expected_behavior"))
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))


# ---------------------------------------------------------------------------
# Regression tracking
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegressionRecord(ContractRecord):
    """Tracks metric changes between benchmark runs to detect regressions."""

    regression_id: str
    metric_name: str
    category: BenchmarkCategory
    baseline_value: float
    current_value: float
    direction: RegressionDirection
    delta: float
    baseline_run_id: str
    current_run_id: str
    detected_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "regression_id", require_non_empty_text(self.regression_id, "regression_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        if not isinstance(self.category, BenchmarkCategory):
            raise ValueError("category must be a BenchmarkCategory value")
        object.__setattr__(self, "baseline_value", require_unit_float(self.baseline_value, "baseline_value"))
        object.__setattr__(self, "current_value", require_unit_float(self.current_value, "current_value"))
        if not isinstance(self.direction, RegressionDirection):
            raise ValueError("direction must be a RegressionDirection value")
        object.__setattr__(self, "baseline_run_id", require_non_empty_text(self.baseline_run_id, "baseline_run_id"))
        object.__setattr__(self, "current_run_id", require_non_empty_text(self.current_run_id, "current_run_id"))
        object.__setattr__(self, "detected_at", require_datetime_text(self.detected_at, "detected_at"))

    @property
    def is_regression(self) -> bool:
        return self.direction == RegressionDirection.DEGRADED


# ---------------------------------------------------------------------------
# Scorecards
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CapabilityScorecard(ContractRecord):
    """Aggregated health/quality assessment for one subsystem."""

    scorecard_id: str
    category: BenchmarkCategory
    status: ScorecardStatus
    pass_rate: float
    metric_count: int
    metrics_passing: int
    adversarial_pass_rate: float
    regressions: tuple[RegressionRecord, ...]
    confidence_trend: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "scorecard_id", require_non_empty_text(self.scorecard_id, "scorecard_id"))
        if not isinstance(self.category, BenchmarkCategory):
            raise ValueError("category must be a BenchmarkCategory value")
        if not isinstance(self.status, ScorecardStatus):
            raise ValueError("status must be a ScorecardStatus value")
        object.__setattr__(self, "pass_rate", require_unit_float(self.pass_rate, "pass_rate"))
        object.__setattr__(self, "metric_count", require_non_negative_int(self.metric_count, "metric_count"))
        object.__setattr__(self, "metrics_passing", require_non_negative_int(self.metrics_passing, "metrics_passing"))
        if self.metrics_passing > self.metric_count:
            raise ValueError("metrics_passing cannot exceed metric_count")
        object.__setattr__(self, "adversarial_pass_rate", require_unit_float(self.adversarial_pass_rate, "adversarial_pass_rate"))
        object.__setattr__(self, "regressions", freeze_value(list(self.regressions)))
        for r in self.regressions:
            if not isinstance(r, RegressionRecord):
                raise ValueError("each regression must be a RegressionRecord instance")
        object.__setattr__(self, "confidence_trend", require_non_empty_text(self.confidence_trend, "confidence_trend"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))

    @property
    def regression_count(self) -> int:
        return sum(1 for r in self.regressions if r.is_regression)

    @property
    def is_healthy(self) -> bool:
        return self.status == ScorecardStatus.HEALTHY
