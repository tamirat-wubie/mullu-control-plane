"""Prometheus dashboard metric projection.

Purpose: Project existing runtime read models into Prometheus dashboard metric
families.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: PrometheusExporter, GovernanceMetricsEngine-compatible metrics,
runtime health, tenant, provider, audit, agent, task, and memory read models.
Invariants:
  - Counter projections emit deltas only.
  - Gauge projections are bounded and deterministic.
  - Missing optional sources do not fabricate activity.
  - Source read errors raise contextual projection errors.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.core.prometheus_exporter import PrometheusExporter


class PrometheusMetricProjectionError(RuntimeError):
    """Raised when a registered projection source cannot be read."""


@dataclass(frozen=True, slots=True)
class PrometheusProjectionReceipt:
    """Receipt for one route-level Prometheus projection pass."""

    counter_deltas: dict[str, float]
    gauges: dict[str, float]
    source_totals: dict[str, float]

    def to_dict(self) -> dict[str, dict[str, float]]:
        return {
            "counter_deltas": dict(self.counter_deltas),
            "gauges": dict(self.gauges),
            "source_totals": dict(self.source_totals),
        }


class PrometheusMetricProjector:
    """Projects dashboard metric families from runtime read models."""

    def __init__(self, *, monotonic_clock: Callable[[], float] = time.monotonic) -> None:
        self._monotonic_clock = monotonic_clock
        self._started_at = monotonic_clock()
        self._last_counter_totals: dict[str, float] = {}

    def project(
        self,
        *,
        exporter: PrometheusExporter,
        metrics: Any | None = None,
        tenant_budget_mgr: Any | None = None,
        health_agg: Any | None = None,
        llm_bridge: Any | None = None,
        llm_circuit: Any | None = None,
        audit_trail: Any | None = None,
        agent_registry: Any | None = None,
        task_manager: Any | None = None,
        task_queue: Any | None = None,
        agent_memory: Any | None = None,
        circuit_dashboard: Any | None = None,
    ) -> PrometheusProjectionReceipt:
        """Project runtime totals into the dashboard Prometheus families.

        Input contract: every source is optional, but any supplied source that
        raises while being read produces a projection error.
        Output contract: exporter state is updated and a receipt names emitted
        counter deltas and gauge values.
        Error contract: invalid numeric values or source read failures raise
        PrometheusMetricProjectionError with causal source context.
        """

        counter_totals = {
            "requests_governed_total": self._metric_counter(metrics, "requests_governed"),
            "errors_total": self._metric_counter(metrics, "errors_total"),
            "llm_requests_total": max(
                self._metric_counter(metrics, "llm_calls_total"),
                self._object_number(llm_bridge, "invocation_count", "llm_bridge", default=0.0),
            ),
            "llm_tokens_total": max(
                self._histogram_stat(metrics, "tokens_per_call", "sum"),
                self._llm_history_token_total(llm_bridge),
            ),
            "policy_violations_total": max(
                self._metric_counter(metrics, "policy_decisions_denied"),
                self._metric_counter(metrics, "requests_rejected"),
            ),
            "audit_events_total": self._summary_number(
                audit_trail, "entry_count", "audit_trail", default=0.0
            ),
            "tasks_completed_total": max(
                self._summary_number(task_queue, "processed", "task_queue", default=0.0),
                self._object_number(task_manager, "completed_count", "task_manager", default=0.0),
            ),
            "memory_ops_total": self._summary_number(
                agent_memory, "total", "agent_memory", default=0.0
            ),
        }

        gauges = {
            "uptime_seconds": self._non_negative(
                max(
                    self._monotonic_clock() - self._started_at,
                    self._metric_gauge(metrics, "uptime_seconds"),
                ),
                "uptime_seconds",
            ),
            "health_score": self._unit_interval(
                max(self._health_score(health_agg), self._metric_gauge(metrics, "health_score")),
                "health_score",
            ),
            "active_tenants": self._non_negative(
                max(
                    self._object_number(
                        tenant_budget_mgr, "tenant_count", "tenant_budget_mgr", default=0.0
                    ),
                    self._metric_gauge(metrics, "active_tenants"),
                ),
                "active_tenants",
            ),
            "llm_latency_p99_seconds": self._non_negative(
                self._histogram_stat(metrics, "llm_latency_ms", "p99") / 1000.0,
                "llm_latency_p99_seconds",
            ),
            "llm_budget_utilization_ratio": self._unit_interval(
                max(
                    self._metric_gauge(metrics, "budget_utilization_pct") / 100.0,
                    self._tenant_budget_utilization_ratio(tenant_budget_mgr),
                    self._llm_budget_utilization_ratio(llm_bridge),
                ),
                "llm_budget_utilization_ratio",
            ),
            "circuit_breaker_open": self._unit_interval(
                max(
                    self._circuit_state_open(llm_circuit),
                    self._circuit_dashboard_open(circuit_dashboard),
                ),
                "circuit_breaker_open",
            ),
            "active_agents": self._non_negative(
                self._active_agent_count(agent_registry),
                "active_agents",
            ),
            "chain_success_rate": self._unit_interval(
                self._chain_success_rate(metrics),
                "chain_success_rate",
            ),
        }

        counter_deltas: dict[str, float] = {}
        source_totals: dict[str, float] = {}
        for name, current_total in counter_totals.items():
            source_totals[name] = self._non_negative(current_total, name)
            counter_deltas[name] = self._emit_counter_delta(
                exporter,
                name,
                source_totals[name],
            )

        for name, value in gauges.items():
            exporter.set_gauge(name, value)

        return PrometheusProjectionReceipt(
            counter_deltas=counter_deltas,
            gauges=gauges,
            source_totals=source_totals,
        )

    def _emit_counter_delta(
        self,
        exporter: PrometheusExporter,
        name: str,
        current_total: float,
    ) -> float:
        previous_total = self._last_counter_totals.get(name, 0.0)
        delta = current_total - previous_total if current_total >= previous_total else current_total
        self._last_counter_totals[name] = current_total
        if delta > 0.0:
            exporter.inc_counter(name, delta)
        return round(delta, 6)

    def _metric_counter(self, metrics: Any | None, name: str) -> float:
        if metrics is None:
            return 0.0
        return self._call_number(metrics, "counter", "metrics", name, default=0.0)

    def _metric_gauge(self, metrics: Any | None, name: str) -> float:
        if metrics is None:
            return 0.0
        return self._call_number(metrics, "gauge", "metrics", name, default=0.0)

    def _histogram_stat(self, metrics: Any | None, name: str, stat_name: str) -> float:
        if metrics is None:
            return 0.0
        try:
            stats = metrics.histogram_stats(name)
        except AttributeError:
            return 0.0
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"metrics histogram {name} projection failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(stats, dict):
            raise PrometheusMetricProjectionError(
                f"metrics histogram {name} projection returned non-dict stats"
            )
        return self._non_negative(stats.get(stat_name, 0.0), f"{name}.{stat_name}")

    def _summary_number(
        self,
        source: Any | None,
        key: str,
        source_name: str,
        *,
        default: float,
    ) -> float:
        if source is None:
            return default
        try:
            summary = source.summary()
        except AttributeError:
            return default
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"{source_name} summary projection failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(summary, dict):
            raise PrometheusMetricProjectionError(
                f"{source_name} summary projection returned non-dict summary"
            )
        return self._non_negative(summary.get(key, default), f"{source_name}.{key}")

    def _object_number(
        self,
        source: Any | None,
        attribute_name: str,
        source_name: str,
        *,
        default: float,
    ) -> float:
        if source is None:
            return default
        try:
            value = getattr(source, attribute_name)
        except AttributeError:
            return default
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"{source_name}.{attribute_name} projection failed: {type(exc).__name__}"
            ) from exc
        if callable(value):
            try:
                value = value()
            except Exception as exc:
                raise PrometheusMetricProjectionError(
                    f"{source_name}.{attribute_name} projection failed: {type(exc).__name__}"
                ) from exc
        return self._non_negative(value, f"{source_name}.{attribute_name}")

    def _call_number(
        self,
        source: Any,
        method_name: str,
        source_name: str,
        argument: str,
        *,
        default: float,
    ) -> float:
        try:
            method = getattr(source, method_name)
        except AttributeError:
            return default
        try:
            value = method(argument)
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"{source_name}.{method_name}({argument}) projection failed: {type(exc).__name__}"
            ) from exc
        return self._non_negative(value, f"{source_name}.{argument}")

    def _health_score(self, health_agg: Any | None) -> float:
        if health_agg is None:
            return 0.0
        try:
            health = health_agg.compute()
        except AttributeError:
            return 0.0
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"health_agg projection failed: {type(exc).__name__}"
            ) from exc
        return self._unit_interval(getattr(health, "overall_score", 0.0), "health_score")

    def _tenant_budget_utilization_ratio(self, tenant_budget_mgr: Any | None) -> float:
        if tenant_budget_mgr is None:
            return 0.0
        try:
            reports = tenant_budget_mgr.all_reports()
        except AttributeError:
            return 0.0
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"tenant_budget_mgr reports projection failed: {type(exc).__name__}"
            ) from exc
        ratios = []
        for report in reports:
            utilization_pct = self._non_negative(
                getattr(report, "utilization_pct", 0.0),
                "tenant_budget_mgr.utilization_pct",
            )
            ratios.append(utilization_pct / 100.0)
        return self._unit_interval(max(ratios, default=0.0), "llm_budget_utilization_ratio")

    def _llm_budget_utilization_ratio(self, llm_bridge: Any | None) -> float:
        if llm_bridge is None:
            return 0.0
        try:
            summary = llm_bridge.budget_summary()
        except AttributeError:
            return 0.0
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"llm_bridge budget projection failed: {type(exc).__name__}"
            ) from exc
        budgets = summary.get("budgets", []) if isinstance(summary, dict) else []
        ratios = []
        for budget in budgets if isinstance(budgets, list) else []:
            if not isinstance(budget, dict):
                continue
            max_cost = self._non_negative(budget.get("max_cost", 0.0), "llm_budget.max_cost")
            spent = self._non_negative(budget.get("spent", 0.0), "llm_budget.spent")
            ratios.append(0.0 if max_cost == 0.0 else spent / max_cost)
        return self._unit_interval(max(ratios, default=0.0), "llm_budget_utilization_ratio")

    def _llm_history_token_total(self, llm_bridge: Any | None) -> float:
        if llm_bridge is None:
            return 0.0
        try:
            history = llm_bridge.invocation_history(limit=10000)
        except AttributeError:
            return 0.0
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"llm_bridge invocation history projection failed: {type(exc).__name__}"
            ) from exc
        total = 0.0
        for record in history:
            if isinstance(record, dict):
                total += self._non_negative(record.get("tokens", 0.0), "llm_history.tokens")
        return total

    def _circuit_state_open(self, llm_circuit: Any | None) -> float:
        if llm_circuit is None:
            return 0.0
        try:
            state = getattr(llm_circuit, "state")
        except AttributeError:
            return 0.0
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"llm_circuit state projection failed: {type(exc).__name__}"
            ) from exc
        state_value = getattr(state, "value", state)
        return 1.0 if str(state_value).lower() == "open" else 0.0

    def _circuit_dashboard_open(self, circuit_dashboard: Any | None) -> float:
        if circuit_dashboard is None:
            return 0.0
        open_count = self._summary_number(circuit_dashboard, "open", "circuit_dashboard", default=0.0)
        return 1.0 if open_count > 0.0 else 0.0

    def _active_agent_count(self, agent_registry: Any | None) -> float:
        if agent_registry is None:
            return 0.0
        try:
            agents = agent_registry.list_agents()
        except AttributeError:
            agents = []
        except Exception as exc:
            raise PrometheusMetricProjectionError(
                f"agent_registry list projection failed: {type(exc).__name__}"
            ) from exc
        if isinstance(agents, (list, tuple)):
            return sum(1.0 for agent in agents if bool(getattr(agent, "enabled", True)))

        enabled_agents = self._summary_number(
            agent_registry, "enabled_agents", "agent_registry", default=0.0
        )
        if enabled_agents > 0.0:
            return enabled_agents
        return self._object_number(agent_registry, "count", "agent_registry", default=0.0)

    def _chain_success_rate(self, metrics: Any | None) -> float:
        policy_total = self._metric_counter(metrics, "policy_decisions_total")
        policy_denied = self._metric_counter(metrics, "policy_decisions_denied")
        if policy_total > 0.0:
            return max(policy_total - policy_denied, 0.0) / policy_total

        governed = self._metric_counter(metrics, "requests_governed")
        rejected = self._metric_counter(metrics, "requests_rejected")
        total = governed + rejected
        if total <= 0.0:
            return 0.0
        return governed / total

    @staticmethod
    def _non_negative(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise PrometheusMetricProjectionError(f"{field_name} must be numeric")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise PrometheusMetricProjectionError(f"{field_name} must be numeric") from exc
        if not math.isfinite(numeric) or numeric < 0.0:
            raise PrometheusMetricProjectionError(f"{field_name} must be non-negative finite")
        return round(numeric, 6)

    @classmethod
    def _unit_interval(cls, value: Any, field_name: str) -> float:
        numeric = cls._non_negative(value, field_name)
        if numeric > 1.0:
            raise PrometheusMetricProjectionError(f"{field_name} must be within [0.0, 1.0]")
        return numeric
