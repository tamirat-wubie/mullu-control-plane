"""Purpose: scorecard engine — aggregates benchmark results and adversarial
evaluations into per-subsystem capability scorecards with regression tracking.
Governance scope: benchmark plane scorecard computation only.
Dependencies: benchmark contracts, invariant helpers.
Invariants:
  - Scorecards aggregate measured evidence, not estimates.
  - Regression records link current run to previous baseline.
  - All metrics are bounded and validated.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from mcoi_runtime.contracts.benchmark import (
    BenchmarkCategory,
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkRun,
    CapabilityScorecard,
    RegressionDirection,
    RegressionRecord,
    ScorecardStatus,
)
from .invariants import stable_identifier


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


# ---------------------------------------------------------------------------
# Regression detection
# ---------------------------------------------------------------------------


def detect_regressions(
    baseline_run: BenchmarkRun,
    current_run: BenchmarkRun,
    category: BenchmarkCategory,
    *,
    clock: Callable[[], str] | None = None,
    threshold: float = 0.05,
) -> tuple[RegressionRecord, ...]:
    """Compare two runs and detect metric regressions.

    A regression is detected when the current pass rate drops below the
    baseline by more than *threshold*.
    """
    clk = clock or _default_clock
    now = clk()

    baseline_rate = baseline_run.pass_rate
    current_rate = current_run.pass_rate
    delta = current_rate - baseline_rate

    if abs(delta) < 1e-9:
        direction = RegressionDirection.STABLE
    elif delta < 0:
        direction = RegressionDirection.DEGRADED
    else:
        direction = RegressionDirection.IMPROVED

    # Only report if the change exceeds the threshold
    if abs(delta) < threshold and direction != RegressionDirection.STABLE:
        direction = RegressionDirection.STABLE

    reg_id = stable_identifier(
        "regression", {"category": category.value, "baseline": baseline_run.run_id, "current": current_run.run_id}
    )

    record = RegressionRecord(
        regression_id=reg_id,
        metric_name="pass_rate",
        category=category,
        baseline_value=_clamp(baseline_rate),
        current_value=_clamp(current_rate),
        direction=direction,
        delta=round(delta, 6),
        baseline_run_id=baseline_run.run_id,
        current_run_id=current_run.run_id,
        detected_at=now,
    )
    return (record,)


# ---------------------------------------------------------------------------
# Scorecard computation
# ---------------------------------------------------------------------------


def _compute_status(pass_rate: float, adversarial_pass_rate: float) -> ScorecardStatus:
    """Derive scorecard status from pass rates."""
    if pass_rate >= 0.95 and adversarial_pass_rate >= 0.80:
        return ScorecardStatus.HEALTHY
    if pass_rate >= 0.70 and adversarial_pass_rate >= 0.50:
        return ScorecardStatus.DEGRADED
    if pass_rate < 0.70 or adversarial_pass_rate < 0.30:
        return ScorecardStatus.FAILING
    return ScorecardStatus.DEGRADED


def _compute_confidence_trend(
    regressions: tuple[RegressionRecord, ...],
    pass_rate: float,
) -> str:
    """Derive a confidence trend label from regressions and pass rate."""
    degraded_count = sum(1 for r in regressions if r.is_regression)
    improved_count = sum(
        1 for r in regressions if r.direction == RegressionDirection.IMPROVED
    )

    if degraded_count > improved_count:
        return "declining"
    if improved_count > degraded_count:
        return "improving"
    if pass_rate >= 0.95:
        return "stable-high"
    if pass_rate >= 0.70:
        return "stable"
    return "stable-low"


class ScorecardEngine:
    """Aggregates benchmark results into per-subsystem capability scorecards.

    This engine:
    - Filters results by category
    - Computes pass rates and metric counts
    - Detects regressions against a baseline run
    - Produces CapabilityScorecard records
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _default_clock

    def build_scorecard(
        self,
        category: BenchmarkCategory,
        current_run: BenchmarkRun,
        *,
        baseline_run: BenchmarkRun | None = None,
        adversarial_results: tuple[BenchmarkResult, ...] = (),
        regression_threshold: float = 0.05,
    ) -> CapabilityScorecard:
        """Build a capability scorecard for a specific category.

        Args:
            category: The subsystem being scored.
            current_run: The benchmark run to score.
            baseline_run: Optional prior run for regression detection.
            adversarial_results: Results from adversarial case evaluation.
            regression_threshold: Minimum delta to count as regression.
        """
        now = self._clock()

        # Filter results for this category (by checking scenario_id prefix convention
        # or counting all results if category cannot be determined from result alone)
        results = current_run.results
        total_metrics = 0
        metrics_passing = 0

        for r in results:
            for m in r.metrics:
                total_metrics += 1
                if m.passed:
                    metrics_passing += 1

        pass_rate = current_run.pass_rate

        # Adversarial pass rate
        if adversarial_results:
            adv_passing = sum(1 for r in adversarial_results if r.outcome == BenchmarkOutcome.PASS)
            adversarial_pass_rate = _clamp(adv_passing / len(adversarial_results))
        else:
            adversarial_pass_rate = 1.0  # No adversarial tests = no adversarial failures

        # Regression detection
        regressions: tuple[RegressionRecord, ...] = ()
        if baseline_run is not None:
            regressions = detect_regressions(
                baseline_run,
                current_run,
                category,
                clock=lambda: now,
                threshold=regression_threshold,
            )

        status = _compute_status(pass_rate, adversarial_pass_rate)
        confidence_trend = _compute_confidence_trend(regressions, pass_rate)

        scorecard_id = stable_identifier("scorecard", {"category": category.value, "run_id": current_run.run_id})

        return CapabilityScorecard(
            scorecard_id=scorecard_id,
            category=category,
            status=status,
            pass_rate=_clamp(pass_rate),
            metric_count=total_metrics,
            metrics_passing=metrics_passing,
            adversarial_pass_rate=adversarial_pass_rate,
            regressions=regressions,
            confidence_trend=confidence_trend,
            assessed_at=now,
        )

    def build_all_scorecards(
        self,
        runs_by_category: dict[BenchmarkCategory, BenchmarkRun],
        *,
        baselines_by_category: dict[BenchmarkCategory, BenchmarkRun] | None = None,
        adversarial_by_category: dict[BenchmarkCategory, tuple[BenchmarkResult, ...]] | None = None,
    ) -> tuple[CapabilityScorecard, ...]:
        """Build scorecards for all categories that have runs."""
        baselines = baselines_by_category or {}
        adversarial = adversarial_by_category or {}
        scorecards: list[CapabilityScorecard] = []

        for category, run in runs_by_category.items():
            scorecard = self.build_scorecard(
                category,
                run,
                baseline_run=baselines.get(category),
                adversarial_results=adversarial.get(category, ()),
            )
            scorecards.append(scorecard)

        return tuple(scorecards)
