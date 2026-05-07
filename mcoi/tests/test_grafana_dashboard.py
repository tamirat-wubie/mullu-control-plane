"""Tests for Phase 222A — Grafana Dashboard Configuration.

Governance scope: validate dashboard JSON generation, panel/row structure,
    PromQL expressions, and default dashboard completeness.
"""
from __future__ import annotations

import json
import pytest

from mcoi_runtime.core.grafana_dashboard import (
    GrafanaDashboardGenerator,
    PanelConfig,
    RowConfig,
    build_default_dashboard,
)


class TestPanelConfig:
    def test_frozen(self):
        p = PanelConfig(title="T", panel_type="stat", metric_expr="up")
        with pytest.raises(AttributeError):
            p.title = "X"  # type: ignore[misc]

    def test_defaults(self):
        p = PanelConfig(title="T", panel_type="graph", metric_expr="up")
        assert p.description == ""
        assert p.thresholds == ()
        assert p.unit == ""
        assert "x" in p.grid_pos


class TestRowConfig:
    def test_frozen(self):
        r = RowConfig(title="R", panels=())
        with pytest.raises(AttributeError):
            r.title = "X"  # type: ignore[misc]

    def test_panels_tuple(self):
        p = PanelConfig(title="T", panel_type="stat", metric_expr="up")
        r = RowConfig(title="R", panels=(p,))
        assert len(r.panels) == 1


class TestGrafanaDashboardGenerator:
    def test_empty_dashboard(self):
        gen = GrafanaDashboardGenerator(title="Test")
        result = gen.generate()
        assert result["dashboard"]["title"] == "Test"
        assert result["dashboard"]["panels"] == []
        assert gen.row_count == 0
        assert gen.panel_count == 0

    def test_add_row_with_panels(self):
        gen = GrafanaDashboardGenerator()
        gen.add_row(RowConfig(
            title="Health",
            panels=(
                PanelConfig("Uptime", "stat", "up"),
                PanelConfig("Errors", "graph", "errors_total"),
            ),
        ))
        assert gen.row_count == 1
        assert gen.panel_count == 2
        result = gen.generate()
        panels = result["dashboard"]["panels"]
        # 1 row header + 2 panels = 3
        assert len(panels) == 3
        assert panels[0]["type"] == "row"
        assert panels[1]["title"] == "Uptime"
        assert panels[2]["title"] == "Errors"

    def test_panel_ids_unique(self):
        gen = GrafanaDashboardGenerator()
        gen.add_row(RowConfig("R1", panels=(
            PanelConfig("A", "stat", "a"),
            PanelConfig("B", "stat", "b"),
        )))
        gen.add_row(RowConfig("R2", panels=(
            PanelConfig("C", "stat", "c"),
        )))
        result = gen.generate()
        ids = [p["id"] for p in result["dashboard"]["panels"]]
        assert len(ids) == len(set(ids))

    def test_thresholds_in_panel(self):
        gen = GrafanaDashboardGenerator()
        gen.add_row(RowConfig("R", panels=(
            PanelConfig("G", "gauge", "metric", thresholds=(50.0, 80.0)),
        )))
        result = gen.generate()
        panel = result["dashboard"]["panels"][1]
        steps = panel["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert len(steps) == 3  # green + 2 thresholds

    def test_unit_in_panel(self):
        gen = GrafanaDashboardGenerator()
        gen.add_row(RowConfig("R", panels=(
            PanelConfig("U", "graph", "metric", unit="s"),
        )))
        result = gen.generate()
        panel = result["dashboard"]["panels"][1]
        assert panel["fieldConfig"]["defaults"]["unit"] == "s"

    def test_to_json_valid(self):
        gen = GrafanaDashboardGenerator()
        gen.add_row(RowConfig("R", panels=(
            PanelConfig("P", "stat", "up"),
        )))
        j = gen.to_json()
        parsed = json.loads(j)
        assert parsed["dashboard"]["uid"] == "mullu-control-plane-main"

    def test_schema_version(self):
        gen = GrafanaDashboardGenerator()
        result = gen.generate()
        assert result["dashboard"]["schemaVersion"] == 39

    def test_overwrite_flag(self):
        gen = GrafanaDashboardGenerator()
        result = gen.generate()
        assert result["overwrite"] is True


class TestDefaultDashboard:
    def test_build_default(self):
        gen = build_default_dashboard()
        assert gen.row_count == 4
        assert gen.panel_count == 16

    def test_default_rows(self):
        gen = build_default_dashboard()
        result = gen.generate()
        row_titles = [p["title"] for p in result["dashboard"]["panels"] if p["type"] == "row"]
        assert "Platform Health" in row_titles
        assert "LLM Operations" in row_titles
        assert "Governance & Compliance" in row_titles
        assert "Agent Operations" in row_titles

    def test_all_metrics_prefixed(self):
        gen = build_default_dashboard()
        result = gen.generate()
        for panel in result["dashboard"]["panels"]:
            if panel["type"] != "row" and "targets" in panel:
                expr = panel["targets"][0]["expr"]
                assert "mullu_" in expr, f"Panel '{panel['title']}' metric not prefixed: {expr}"

    def test_default_json_roundtrip(self):
        gen = build_default_dashboard()
        j = gen.to_json()
        parsed = json.loads(j)
        assert parsed["dashboard"]["tags"] == ["mullu", "governed", "ai"]
