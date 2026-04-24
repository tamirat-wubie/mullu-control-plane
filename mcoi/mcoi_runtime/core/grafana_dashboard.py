"""Phase 222A — Grafana Monitoring Dashboard Configuration.

Purpose: Generate Grafana dashboard JSON for Mullu Platform monitoring.
    Produces provisioned dashboard configs for Prometheus/Grafana stacks.
Dependencies: None (pure config generation).
Invariants:
  - Dashboard JSON is valid Grafana 10.x schema.
  - All panels reference governed metrics (prefixed `mullu_`).
  - Row layout groups: health, LLM, tenants, agents, governance.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PanelConfig:
    """Single Grafana panel definition."""
    title: str
    panel_type: str  # "graph", "stat", "table", "gauge", "heatmap"
    metric_expr: str  # PromQL expression
    description: str = ""
    thresholds: tuple[float, ...] = ()
    unit: str = ""
    grid_pos: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "w": 12, "h": 8})


@dataclass(frozen=True)
class RowConfig:
    """Dashboard row grouping panels."""
    title: str
    panels: tuple[PanelConfig, ...]
    collapsed: bool = False


class GrafanaDashboardGenerator:
    """Generates Grafana dashboard JSON from row/panel definitions."""

    def __init__(self, title: str = "Mullu Control Plane - Governed Symbolic Intelligence Operating System",
                 uid: str = "mullu-control-plane-main",
                 refresh: str = "30s"):
        self._title = title
        self._uid = uid
        self._refresh = refresh
        self._rows: list[RowConfig] = []

    def add_row(self, row: RowConfig) -> None:
        self._rows.append(row)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def panel_count(self) -> int:
        return sum(len(r.panels) for r in self._rows)

    def generate(self) -> dict[str, Any]:
        """Generate complete Grafana dashboard JSON."""
        panels: list[dict[str, Any]] = []
        panel_id = 1
        y_offset = 0

        for row in self._rows:
            # Row header
            panels.append({
                "id": panel_id,
                "type": "row",
                "title": row.title,
                "collapsed": row.collapsed,
                "gridPos": {"x": 0, "y": y_offset, "w": 24, "h": 1},
                "panels": [],
            })
            panel_id += 1
            y_offset += 1

            for i, p in enumerate(row.panels):
                gp = dict(p.grid_pos)
                gp["y"] = y_offset + (i // 2) * gp.get("h", 8)
                gp["x"] = (i % 2) * 12

                panel_def: dict[str, Any] = {
                    "id": panel_id,
                    "type": p.panel_type,
                    "title": p.title,
                    "description": p.description,
                    "gridPos": gp,
                    "targets": [{"expr": p.metric_expr, "refId": "A"}],
                    "fieldConfig": {"defaults": {}},
                }
                if p.unit:
                    panel_def["fieldConfig"]["defaults"]["unit"] = p.unit
                if p.thresholds:
                    panel_def["fieldConfig"]["defaults"]["thresholds"] = {
                        "mode": "absolute",
                        "steps": [
                            {"value": None, "color": "green"},
                            *[{"value": t, "color": "red"} for t in p.thresholds],
                        ],
                    }
                panels.append(panel_def)
                panel_id += 1

            y_offset += ((len(row.panels) + 1) // 2) * 8

        return {
            "dashboard": {
                "uid": self._uid,
                "title": self._title,
                "tags": ["mullu", "governed", "ai"],
                "timezone": "utc",
                "refresh": self._refresh,
                "schemaVersion": 39,
                "panels": panels,
                "templating": {"list": []},
                "time": {"from": "now-6h", "to": "now"},
            },
            "overwrite": True,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.generate(), indent=indent)


def build_default_dashboard() -> GrafanaDashboardGenerator:
    """Build the default Mullu Platform monitoring dashboard."""
    gen = GrafanaDashboardGenerator()

    # Health row
    gen.add_row(RowConfig(
        title="Platform Health",
        panels=(
            PanelConfig("Uptime", "stat", 'mullu_uptime_seconds', unit="s"),
            PanelConfig("Health Score", "gauge", 'mullu_health_score',
                        thresholds=(50.0, 80.0), unit="percent"),
            PanelConfig("Active Tenants", "stat", 'mullu_active_tenants'),
            PanelConfig("Error Rate (5m)", "graph",
                        'rate(mullu_errors_total[5m])', unit="ops"),
        ),
    ))

    # LLM row
    gen.add_row(RowConfig(
        title="LLM Operations",
        panels=(
            PanelConfig("LLM Requests/s", "graph",
                        'rate(mullu_llm_requests_total[5m])', unit="reqps"),
            PanelConfig("LLM Latency p99", "graph",
                        'histogram_quantile(0.99, mullu_llm_duration_seconds_bucket)',
                        unit="s"),
            PanelConfig("Token Usage", "graph",
                        'rate(mullu_llm_tokens_total[5m])', unit="ops"),
            PanelConfig("LLM Budget Utilization", "gauge",
                        'mullu_llm_budget_utilization_ratio * 100',
                        thresholds=(60.0, 80.0), unit="percent"),
        ),
    ))

    # Governance row
    gen.add_row(RowConfig(
        title="Governance & Compliance",
        panels=(
            PanelConfig("Governed Requests", "stat", 'mullu_requests_governed_total'),
            PanelConfig("Policy Violations", "stat",
                        'mullu_policy_violations_total',
                        thresholds=(1.0,)),
            PanelConfig("Audit Events/s", "graph",
                        'rate(mullu_audit_events_total[5m])', unit="ops"),
            PanelConfig("Circuit Breaker State", "stat",
                        'mullu_circuit_breaker_open'),
        ),
    ))

    # Agent row
    gen.add_row(RowConfig(
        title="Agent Operations",
        panels=(
            PanelConfig("Active Agents", "stat", 'mullu_active_agents'),
            PanelConfig("Task Throughput", "graph",
                        'rate(mullu_tasks_completed_total[5m])', unit="ops"),
            PanelConfig("Chain Success Rate", "gauge",
                        'mullu_chain_success_rate * 100',
                        thresholds=(70.0, 90.0), unit="percent"),
            PanelConfig("Memory Operations", "graph",
                        'rate(mullu_memory_ops_total[5m])', unit="ops"),
        ),
    ))

    return gen
