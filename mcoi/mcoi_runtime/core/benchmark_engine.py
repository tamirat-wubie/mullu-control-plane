"""Purpose: benchmark evaluation engine — executes benchmark scenarios against
subsystem evaluators, produces measured results, and tracks runs.
Governance scope: benchmark plane core logic only.
Dependencies: benchmark contracts, invariant helpers.
Invariants:
  - Evaluation is deterministic for the same inputs.
  - Every scenario produces a measured result with metrics.
  - Runs aggregate results faithfully — no estimation.
  - Clock is injected for deterministic timestamps.
  - Evaluator callbacks are injected — engine owns orchestration, not logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.benchmark import (
    BenchmarkCategory,
    BenchmarkMetric,
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkScenario,
    BenchmarkSuite,
    MetricKind,
)
from .invariants import stable_identifier


# ---------------------------------------------------------------------------
# Evaluator callback protocol
# ---------------------------------------------------------------------------

# An evaluator receives a scenario and returns (outcome, metrics, actual_properties, error_message_or_none).
# The engine does NOT own subsystem logic — evaluators are injected by the bridge.
EvaluatorCallback = Callable[
    [BenchmarkScenario],
    tuple[BenchmarkOutcome, list[BenchmarkMetric], Mapping[str, Any], str | None],
]


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


class BenchmarkEngine:
    """Benchmark execution engine — runs scenarios, collects metrics, produces runs.

    This engine:
    - Registers evaluator callbacks per BenchmarkCategory
    - Executes individual scenarios through the appropriate evaluator
    - Produces BenchmarkResult records with measured metrics
    - Aggregates results into BenchmarkRun records
    - Tracks all runs for audit
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _default_clock
        self._evaluators: dict[BenchmarkCategory, EvaluatorCallback] = {}
        self._runs: list[BenchmarkRun] = []

    def register_evaluator(self, category: BenchmarkCategory, evaluator: EvaluatorCallback) -> None:
        """Register an evaluator callback for a benchmark category."""
        if not isinstance(category, BenchmarkCategory):
            raise ValueError("category must be a BenchmarkCategory value")
        if not callable(evaluator):
            raise ValueError("evaluator must be callable")
        self._evaluators[category] = evaluator

    def has_evaluator(self, category: BenchmarkCategory) -> bool:
        """Check if an evaluator is registered for a category."""
        return category in self._evaluators

    def evaluate_scenario(self, scenario: BenchmarkScenario) -> BenchmarkResult:
        """Execute a single benchmark scenario and produce a result.

        If no evaluator is registered for the scenario's category, the result
        outcome is SKIP with an appropriate error message.
        """
        if not isinstance(scenario, BenchmarkScenario):
            raise ValueError("scenario must be a BenchmarkScenario instance")

        now = self._clock()
        result_id = stable_identifier("bench-result", {"scenario_id": scenario.scenario_id, "ts": now})

        evaluator = self._evaluators.get(scenario.category)
        if evaluator is None:
            return BenchmarkResult(
                result_id=result_id,
                scenario_id=scenario.scenario_id,
                outcome=BenchmarkOutcome.SKIP,
                metrics=(),
                actual_properties={},
                error_message=f"No evaluator registered for category {scenario.category.value}",
                duration_ms=0,
                executed_at=now,
            )

        try:
            outcome, metrics, actual_properties, error_message = evaluator(scenario)
            return BenchmarkResult(
                result_id=result_id,
                scenario_id=scenario.scenario_id,
                outcome=outcome,
                metrics=tuple(metrics),
                actual_properties=actual_properties,
                error_message=error_message,
                duration_ms=0,
                executed_at=now,
            )
        except Exception as exc:
            return BenchmarkResult(
                result_id=result_id,
                scenario_id=scenario.scenario_id,
                outcome=BenchmarkOutcome.ERROR,
                metrics=(),
                actual_properties={},
                error_message=f"Evaluator raised: {exc!s}",
                duration_ms=0,
                executed_at=now,
            )

    def run_suite(self, suite: BenchmarkSuite) -> BenchmarkRun:
        """Execute all scenarios in a suite and produce a BenchmarkRun.

        Scenarios are executed in order. Results are collected even if
        individual scenarios fail or error.
        """
        if not isinstance(suite, BenchmarkSuite):
            raise ValueError("suite must be a BenchmarkSuite instance")

        started = self._clock()
        results: list[BenchmarkResult] = []

        for scenario in suite.scenarios:
            result = self.evaluate_scenario(scenario)
            results.append(result)

        finished = self._clock()
        run_id = stable_identifier("bench-run", {"suite_id": suite.suite_id, "ts": started})

        run = BenchmarkRun(
            run_id=run_id,
            suite_id=suite.suite_id,
            results=tuple(results),
            started_at=started,
            finished_at=finished,
            metadata={"suite_name": suite.name, "suite_version": suite.version},
        )
        self._runs.append(run)
        return run

    def list_runs(self) -> tuple[BenchmarkRun, ...]:
        """Return all recorded benchmark runs."""
        return tuple(self._runs)

    def clear_runs(self) -> None:
        """Clear the run history."""
        self._runs.clear()

    def run_count(self) -> int:
        """Return the number of recorded runs."""
        return len(self._runs)
