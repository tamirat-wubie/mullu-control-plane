"""Tests for dashboard Prometheus metric projection.

Purpose: verify route-level dashboard metric projection from runtime read
models into Prometheus families.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: prometheus metric projector, PrometheusExporter, and governance
metrics engine.
Invariants:
  - Counter projection emits deltas only.
  - Counter source resets do not emit negative values.
  - Dashboard gauges are bounded read-model projections.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from mcoi_runtime.core.prometheus_exporter import PrometheusExporter
from mcoi_runtime.core.prometheus_metric_projection import (
    PrometheusMetricProjectionError,
    PrometheusMetricProjector,
)
from mcoi_runtime.governance.metrics import GovernanceMetricsEngine


def _metrics() -> GovernanceMetricsEngine:
    return GovernanceMetricsEngine(clock=lambda: "2026-06-02T00:00:00Z")


def _sample_value(exported: str, name: str) -> float:
    match = re.search(rf"^{re.escape(name)}(?:\{{[^}}]*\}})?\s+([0-9.]+)$", exported, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing Prometheus sample: {name}")
    return float(match.group(1))


def test_counter_projection_emits_only_deltas() -> None:
    metrics = _metrics()
    exporter = PrometheusExporter(prefix="mullu")
    projector = PrometheusMetricProjector(monotonic_clock=lambda: 1.0)

    metrics.inc("requests_governed", 3)
    first = projector.project(exporter=exporter, metrics=metrics)
    second = projector.project(exporter=exporter, metrics=metrics)
    metrics.inc("requests_governed", 2)
    third = projector.project(exporter=exporter, metrics=metrics)

    assert first.counter_deltas["requests_governed_total"] == 3.0
    assert second.counter_deltas["requests_governed_total"] == 0.0
    assert third.counter_deltas["requests_governed_total"] == 2.0
    assert _sample_value(exporter.export(), "mullu_requests_governed_total") == 5.0


def test_counter_projection_handles_source_reset_without_negative_delta() -> None:
    metrics = _metrics()
    exporter = PrometheusExporter(prefix="mullu")
    projector = PrometheusMetricProjector(monotonic_clock=lambda: 1.0)

    metrics.inc("requests_governed", 5)
    projector.project(exporter=exporter, metrics=metrics)
    metrics.reset()
    metrics.inc("requests_governed", 2)
    receipt = projector.project(exporter=exporter, metrics=metrics)

    assert receipt.source_totals["requests_governed_total"] == 2.0
    assert receipt.counter_deltas["requests_governed_total"] == 2.0
    assert receipt.counter_deltas["errors_total"] == 0.0
    assert _sample_value(exporter.export(), "mullu_requests_governed_total") == 7.0


class _HealthAggregator:
    def compute(self):
        return SimpleNamespace(overall_score=0.75)


class _TenantBudgetManager:
    def tenant_count(self) -> int:
        return 3

    def all_reports(self):
        return [SimpleNamespace(utilization_pct=60.0)]


class _LLMBridge:
    def __init__(self) -> None:
        self.history_limits: list[int] = []

    @property
    def invocation_count(self) -> int:
        return 2

    def invocation_history(self, limit: int = 50):
        self.history_limits.append(limit)
        return [{"tokens": 7}, {"tokens": 5}]

    def budget_summary(self):
        return {"budgets": [{"spent": 1.0, "max_cost": 4.0}]}


class _AuditTrail:
    def summary(self):
        return {"entry_count": 8}


class _AgentRegistry:
    @property
    def count(self) -> int:
        return 99

    def list_agents(self):
        return [
            SimpleNamespace(enabled=True),
            SimpleNamespace(enabled=False),
            SimpleNamespace(enabled=True),
        ]


class _TaskManager:
    @property
    def completed_count(self) -> int:
        return 4


class _TaskQueue:
    def summary(self):
        return {"processed": 5, "succeeded": 5, "failed": 0}


class _AgentMemory:
    def summary(self):
        return {"total": 6}


class _CircuitDashboard:
    def summary(self):
        return {"open": 0}


def test_projection_maps_runtime_read_models_to_dashboard_families() -> None:
    metrics = _metrics()
    exporter = PrometheusExporter(prefix="mullu")
    projector = PrometheusMetricProjector(monotonic_clock=lambda: 2.0)

    metrics.inc("requests_governed", 10)
    metrics.inc("errors_total", 1)
    metrics.inc("llm_calls_total", 2)
    metrics.inc("policy_decisions_total", 10)
    metrics.inc("policy_decisions_denied", 2)
    metrics.observe("tokens_per_call", 10)
    metrics.observe("tokens_per_call", 15)
    metrics.observe("llm_latency_ms", 250)
    metrics.observe("llm_latency_ms", 500)
    llm_bridge = _LLMBridge()

    receipt = projector.project(
        exporter=exporter,
        metrics=metrics,
        tenant_budget_mgr=_TenantBudgetManager(),
        health_agg=_HealthAggregator(),
        llm_bridge=llm_bridge,
        llm_circuit=SimpleNamespace(state=SimpleNamespace(value="open")),
        audit_trail=_AuditTrail(),
        agent_registry=_AgentRegistry(),
        task_manager=_TaskManager(),
        task_queue=_TaskQueue(),
        agent_memory=_AgentMemory(),
        circuit_dashboard=_CircuitDashboard(),
    )
    exported = exporter.export()

    assert receipt.counter_deltas["requests_governed_total"] == 10.0
    assert receipt.counter_deltas["llm_tokens_total"] == 25.0
    assert receipt.gauges["health_score"] == 0.75
    assert receipt.gauges["active_tenants"] == 3.0
    assert receipt.gauges["llm_latency_p99_seconds"] == 0.5
    assert receipt.gauges["llm_budget_utilization_ratio"] == 0.6
    assert receipt.gauges["circuit_breaker_open"] == 1.0
    assert receipt.gauges["active_agents"] == 2.0
    assert receipt.gauges["chain_success_rate"] == 0.8
    assert llm_bridge.history_limits == [500]
    assert _sample_value(exported, "mullu_audit_events_total") == 8.0
    assert _sample_value(exported, "mullu_tasks_completed_total") == 5.0
    assert _sample_value(exported, "mullu_memory_ops_total") == 6.0


class _InvalidTenantBudgetManager:
    def all_reports(self):
        return [SimpleNamespace(utilization_pct=150.0)]


def test_projection_rejects_invalid_bounded_gauge_values() -> None:
    exporter = PrometheusExporter(prefix="mullu")
    projector = PrometheusMetricProjector(monotonic_clock=lambda: 1.0)

    with pytest.raises(PrometheusMetricProjectionError, match="within"):
        projector.project(
            exporter=exporter,
            metrics=_metrics(),
            tenant_budget_mgr=_InvalidTenantBudgetManager(),
        )
