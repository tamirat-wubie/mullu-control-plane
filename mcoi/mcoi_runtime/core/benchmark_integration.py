"""Purpose: benchmark integration bridge — connects benchmark engine, scorecard
engine, and adversarial packs into a unified evaluation pipeline.
Governance scope: benchmark plane orchestration only.
Dependencies: benchmark engine, scorecard engine, adversarial packs, benchmark contracts.
Invariants:
  - Bridge methods are stateless orchestrators.
  - All results flow through typed contracts.
  - No direct subsystem access — evaluators are injected.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from mcoi_runtime.contracts.benchmark import (
    AdversarialCase,
    BenchmarkCategory,
    BenchmarkMetric,
    BenchmarkOutcome,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkScenario,
    BenchmarkSuite,
    CapabilityScorecard,
    MetricKind,
    RegressionRecord,
    ScorecardStatus,
)
from .adversarial_packs import (
    adversarial_cases_for_subsystem,
    all_adversarial_cases,
    all_adversarial_packs,
)
from .benchmark_engine import BenchmarkEngine, EvaluatorCallback
from .invariants import stable_identifier
from .scorecard_engine import ScorecardEngine


class BenchmarkBridge:
    """Static integration bridge for the benchmark subsystem.

    Orchestrates:
    - Suite creation from scenarios
    - Full benchmark evaluation pipeline
    - Adversarial evaluation
    - Scorecard generation with regression tracking
    - Summary extraction for dashboard integration
    """

    @staticmethod
    def create_scenario(
        name: str,
        description: str,
        category: BenchmarkCategory,
        inputs: Mapping[str, Any],
        expected_outcome: BenchmarkOutcome,
        *,
        expected_properties: Mapping[str, Any] | None = None,
        tags: tuple[str, ...] = (),
        timeout_ms: int = 30000,
    ) -> BenchmarkScenario:
        """Factory for creating a benchmark scenario with deterministic ID."""
        scenario_id = stable_identifier("scenario", {"name": name, "category": category.value})
        return BenchmarkScenario(
            scenario_id=scenario_id,
            name=name,
            description=description,
            category=category,
            inputs=inputs,
            expected_outcome=expected_outcome,
            expected_properties=expected_properties or {},
            tags=tags,
            timeout_ms=timeout_ms,
        )

    @staticmethod
    def create_suite(
        name: str,
        category: BenchmarkCategory,
        scenarios: tuple[BenchmarkScenario, ...],
        version: str,
        created_at: str,
    ) -> BenchmarkSuite:
        """Factory for creating a benchmark suite with deterministic ID."""
        suite_id = stable_identifier("suite", {"name": name, "category": category.value, "version": version})
        return BenchmarkSuite(
            suite_id=suite_id,
            name=name,
            category=category,
            scenarios=scenarios,
            version=version,
            created_at=created_at,
        )

    @staticmethod
    def create_metric(
        name: str,
        kind: MetricKind,
        value: float,
        threshold: float,
    ) -> BenchmarkMetric:
        """Factory for creating a benchmark metric with deterministic ID."""
        passed = value >= threshold
        metric_id = stable_identifier("metric", {"name": name, "kind": kind.value})
        return BenchmarkMetric(
            metric_id=metric_id,
            kind=kind,
            name=name,
            value=value,
            threshold=threshold,
            passed=passed,
        )

    @staticmethod
    def run_evaluation(
        engine: BenchmarkEngine,
        suite: BenchmarkSuite,
    ) -> BenchmarkRun:
        """Execute a benchmark suite through the engine."""
        return engine.run_suite(suite)

    @staticmethod
    def evaluate_adversarial_cases(
        engine: BenchmarkEngine,
        cases: tuple[AdversarialCase, ...],
        category: BenchmarkCategory,
    ) -> tuple[BenchmarkResult, ...]:
        """Evaluate adversarial cases by converting them to scenarios and running.

        Each adversarial case is wrapped as a BenchmarkScenario and evaluated
        through the engine's registered evaluator for the target subsystem.
        """
        results: list[BenchmarkResult] = []

        for case in cases:
            scenario = BenchmarkScenario(
                scenario_id=case.case_id,
                name=f"adversarial:{case.name}",
                description=case.description,
                category=case.target_subsystem,
                inputs=case.inputs,
                expected_outcome=BenchmarkOutcome.PASS,
                expected_properties={"expected_behavior": case.expected_behavior},
                tags=case.tags,
                timeout_ms=30000,
            )
            result = engine.evaluate_scenario(scenario)
            results.append(result)

        return tuple(results)

    @staticmethod
    def build_scorecard(
        scorecard_engine: ScorecardEngine,
        category: BenchmarkCategory,
        current_run: BenchmarkRun,
        *,
        baseline_run: BenchmarkRun | None = None,
        adversarial_results: tuple[BenchmarkResult, ...] = (),
    ) -> CapabilityScorecard:
        """Build a capability scorecard for a category."""
        return scorecard_engine.build_scorecard(
            category,
            current_run,
            baseline_run=baseline_run,
            adversarial_results=adversarial_results,
        )

    @staticmethod
    def full_evaluation_pipeline(
        benchmark_engine: BenchmarkEngine,
        scorecard_engine: ScorecardEngine,
        suites: dict[BenchmarkCategory, BenchmarkSuite],
        *,
        baselines: dict[BenchmarkCategory, BenchmarkRun] | None = None,
        include_adversarial: bool = True,
    ) -> tuple[Mapping[BenchmarkCategory, BenchmarkRun], tuple[CapabilityScorecard, ...]]:
        """Run the full evaluation pipeline: execute suites, run adversarial
        cases, and build scorecards.

        Returns (runs_by_category, scorecards).
        """
        baselines = baselines or {}
        runs: dict[BenchmarkCategory, BenchmarkRun] = {}
        adversarial_results: dict[BenchmarkCategory, tuple[BenchmarkResult, ...]] = {}

        # Execute each suite
        for category, suite in suites.items():
            run = benchmark_engine.run_suite(suite)
            runs[category] = run

            # Run adversarial cases for this category
            if include_adversarial:
                cases = adversarial_cases_for_subsystem(category)
                if cases:
                    adv_results = BenchmarkBridge.evaluate_adversarial_cases(
                        benchmark_engine, cases, category
                    )
                    adversarial_results[category] = adv_results

        # Build scorecards
        scorecards = scorecard_engine.build_all_scorecards(
            runs,
            baselines_by_category=baselines,
            adversarial_by_category=adversarial_results,
        )

        return MappingProxyType(runs), scorecards

    @staticmethod
    def extract_summary(
        scorecards: tuple[CapabilityScorecard, ...],
    ) -> Mapping[str, Any]:
        """Extract a dashboard-friendly summary from scorecards.

        Returns an immutable mapping with:
        - total_categories: number of scored categories
        - healthy_count: categories with HEALTHY status
        - degraded_count: categories with DEGRADED status
        - failing_count: categories with FAILING status
        - overall_pass_rate: average pass rate across categories
        - overall_adversarial_rate: average adversarial pass rate
        - total_regressions: total regression count
        - categories: per-category summary dicts
        """
        if not scorecards:
            return MappingProxyType({
                "total_categories": 0,
                "healthy_count": 0,
                "degraded_count": 0,
                "failing_count": 0,
                "overall_pass_rate": 1.0,
                "overall_adversarial_rate": 1.0,
                "total_regressions": 0,
                "categories": MappingProxyType({}),
            })

        healthy = sum(1 for s in scorecards if s.status == ScorecardStatus.HEALTHY)
        degraded = sum(1 for s in scorecards if s.status == ScorecardStatus.DEGRADED)
        failing = sum(1 for s in scorecards if s.status == ScorecardStatus.FAILING)
        avg_pass = sum(s.pass_rate for s in scorecards) / len(scorecards)
        avg_adv = sum(s.adversarial_pass_rate for s in scorecards) / len(scorecards)
        total_reg = sum(s.regression_count for s in scorecards)

        categories = {}
        for s in scorecards:
            categories[s.category.value] = {
                "status": s.status.value,
                "pass_rate": s.pass_rate,
                "adversarial_pass_rate": s.adversarial_pass_rate,
                "metric_count": s.metric_count,
                "metrics_passing": s.metrics_passing,
                "regression_count": s.regression_count,
                "confidence_trend": s.confidence_trend,
            }

        return MappingProxyType({
            "total_categories": len(scorecards),
            "healthy_count": healthy,
            "degraded_count": degraded,
            "failing_count": failing,
            "overall_pass_rate": round(avg_pass, 4),
            "overall_adversarial_rate": round(avg_adv, 4),
            "total_regressions": total_reg,
            "categories": MappingProxyType(categories),
        })
