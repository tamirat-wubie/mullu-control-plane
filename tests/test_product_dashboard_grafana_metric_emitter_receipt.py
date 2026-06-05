"""Tests for the product dashboard Grafana metric emitter receipt.

Purpose: keep Grafana panel metric closure explicit and bounded.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/product_dashboard_grafana_metric_emitter_receipt.json,
    mcoi_runtime.core.grafana_dashboard, mcoi_runtime.core.platform_metrics.
Invariants:
  - Every default Grafana panel expression has a receipt binding.
  - Receipt status confirms exact emitted metric families.
  - Alias candidates and missing emitters cannot be reported as closure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mcoi_runtime.core.grafana_dashboard import build_default_dashboard
from mcoi_runtime.core.platform_metrics import PlatformMetricsCollector


RECEIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "product_dashboard_grafana_metric_emitter_receipt.json"
)


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def _dashboard_panel_expressions() -> dict[str, str]:
    dashboard = build_default_dashboard().generate()["dashboard"]
    expressions: dict[str, str] = {}
    for panel in dashboard["panels"]:
        targets = panel.get("targets", ())
        if panel.get("type") != "row" and targets:
            expressions[str(panel["title"])] = str(targets[0]["expr"])
    return expressions


def _metric_family_names(exported: str) -> set[str]:
    names: set[str] = set()
    for line in exported.splitlines():
        match = re.match(r"# TYPE\s+([a-zA-Z_:][a-zA-Z0-9_:]*)\s+", line)
        if match:
            names.add(match.group(1))
    return names


def test_receipt_covers_every_default_grafana_panel_expression() -> None:
    receipt = _receipt()
    dashboard_expressions = _dashboard_panel_expressions()
    bindings = {str(item["panel_title"]): item for item in receipt["bindings"]}  # type: ignore[index]

    assert receipt["solver_outcome"] == "SolvedVerified"
    assert receipt["summary"]["grafana_expression_count"] == len(dashboard_expressions)  # type: ignore[index]
    assert set(bindings) == set(dashboard_expressions)
    for title, expression in dashboard_expressions.items():
        assert bindings[title]["expression"] == expression


def test_receipt_claims_only_exact_collector_families() -> None:
    receipt = _receipt()
    emitted_families = _metric_family_names(PlatformMetricsCollector().export())

    confirmed_exact = 0
    for binding in receipt["bindings"]:  # type: ignore[index]
        status = binding["emitter_status"]
        assert status == "confirmed_exact"
        for metric_name in binding["metric_names"]:
            assert metric_name in emitted_families
            confirmed_exact += 1

    assert confirmed_exact == receipt["summary"]["confirmed_exact_emitter_count"]  # type: ignore[index]
    assert receipt["summary"]["confirmed_exact_emitter_count"] == 16  # type: ignore[index]
    assert receipt["summary"]["closure_state"] == "collector_and_route_projected"  # type: ignore[index]


def test_receipt_rejects_alias_candidates_and_missing_emitters() -> None:
    receipt = _receipt()
    bindings = receipt["bindings"]  # type: ignore[index]

    alias_count = sum(1 for binding in bindings if binding["emitter_status"] == "alias_candidate")
    missing_count = sum(1 for binding in bindings if binding["emitter_status"] == "missing")

    assert alias_count == receipt["summary"]["alias_candidate_count"]  # type: ignore[index]
    assert missing_count == receipt["summary"]["missing_emitter_count"]  # type: ignore[index]
    assert alias_count == 0
    assert missing_count == 0
