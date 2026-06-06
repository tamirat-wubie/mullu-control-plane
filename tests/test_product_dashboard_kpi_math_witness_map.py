"""Tests for the product dashboard KPI math witness map.

Purpose: keep dashboard KPI math lineage explicit and auditable.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: docs/product_dashboard_kpi_math_witness_map.md.
Invariants:
  - Executable KPI surfaces name their code witnesses.
  - Grafana panel expressions remain bound to exact metric emitters and route projections.
  - Verification lanes are named for the mapped surfaces.
"""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "product_dashboard_kpi_math_witness_map.md"


def _doc_text() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def test_witness_map_names_executable_dashboard_math_surfaces() -> None:
    doc = _doc_text()

    required_sources = (
        "gateway/commercial_metering.py",
        "gateway/economic_intelligence.py",
        "gateway/workflow_mining.py",
        "gateway/temporal_resolution.py",
        "mcoi/mcoi_runtime/core/dashboard.py",
        "mcoi/mcoi_runtime/core/executive_reporting.py",
        "mcoi/mcoi_runtime/core/cost_analytics.py",
        "mcoi/mcoi_runtime/core/tenant_analytics.py",
        "gateway/operator_control_tower.py",
    )

    for source in required_sources:
        assert source in doc
    assert "success_count / routing_count" in doc
    assert "completion rate, success rate, burn rate, cost per completion" in doc


def test_witness_map_preserves_grafana_external_evidence_boundary() -> None:
    doc = _doc_text()

    grafana_expressions = (
        "mullu_health_score * 100",
        "mullu_llm_budget_utilization_ratio * 100",
        "mullu_chain_success_rate * 100",
        "mullu_llm_latency_p99_seconds",
    )

    for expression in grafana_expressions:
        assert expression in doc
    assert "| Grafana dashboard panel config |" in doc
    assert "| `mullu_health_score * 100` | exact collector + route projection |" in doc
    assert "SolvedVerified" in doc
    assert "registers exact metric families for all default Grafana panel expressions" in doc
    assert "PrometheusMetricProjector" in doc
    assert "examples/product_dashboard_grafana_metric_emitter_receipt.json" in doc
    assert "examples/product_dashboard_prometheus_scrape_sample_receipt.json" in doc
    assert "examples/product_dashboard_production_prometheus_scrape_probe_receipt.json" in doc
    assert "Public production scrape outcome: `AwaitingEvidence`" in doc
    assert "api.mullusi.com` did not resolve" in doc
    assert "scripts/collect_product_dashboard_production_prometheus_scrape_probe.py" in doc
    assert "scripts/validate_product_dashboard_production_prometheus_scrape_probe_receipt.py" in doc
    assert "--gateway-url https://api.mullusi.com --host api.mullusi.com" in doc
    assert "--output .change_assurance/product_dashboard_production_prometheus_scrape_probe_validation.json" in doc


def test_witness_map_names_verification_lanes_and_status_block() -> None:
    doc = _doc_text()

    required_tests = (
        "mcoi/tests/test_dashboard_engine.py",
        "mcoi/tests/test_dashboard_contracts.py",
        "mcoi/tests/test_executive_reporting_engine.py",
        "mcoi/tests/test_cost_analytics.py",
        "mcoi/tests/test_tenant_analytics.py",
        "mcoi/tests/test_grafana_dashboard.py",
        "mcoi/tests/test_platform_metrics.py",
        "mcoi/tests/test_prometheus_metric_projection.py",
        "mcoi/tests/test_server_phase202.py",
        "tests/test_gateway/test_operator_control_tower.py",
        "tests/test_product_dashboard_grafana_metric_emitter_receipt.py",
        "tests/test_product_dashboard_prometheus_scrape_sample_receipt.py",
        "tests/test_product_dashboard_production_prometheus_scrape_probe_receipt.py",
        "tests/test_collect_product_dashboard_production_prometheus_scrape_probe.py",
        "tests/test_validate_product_dashboard_production_prometheus_scrape_probe_receipt.py",
        "tests/test_validate_streaming_budget_enforcement.py",
    )

    for test_ref in required_tests:
        assert test_ref in doc
    assert "STATUS:" in doc
    assert "Completeness: 100% repository-local / AwaitingEvidence public production" in doc
    assert "production DNS blocker receipt" in doc
    assert "repeatable production scrape probe" in doc
    assert "schema-backed production scrape validation" in doc
    assert "Open issues: external production Prometheus scrape samples remain blocked" in doc
