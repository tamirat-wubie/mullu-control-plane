"""Tests for the product dashboard Prometheus scrape sample receipt.

Purpose: keep repository-local scrape evidence separate from public production
endpoint evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/product_dashboard_prometheus_scrape_sample_receipt.json,
    mcoi_runtime.app.server, and product dashboard Prometheus projection.
Invariants:
  - The scrape receipt names every default dashboard metric family.
  - The local `/metrics` route exposes the same required families.
  - Public production status remains AwaitingEvidence until endpoint evidence
    is attached.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


RECEIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "product_dashboard_prometheus_scrape_sample_receipt.json"
)


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def _metric_family_names_from_prometheus_text(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        match = re.match(r"# TYPE\s+([a-zA-Z_:][a-zA-Z0-9_:]*)\s+", line)
        if match:
            names.add(match.group(1))
    return names


def _metric_family_names_from_sample_lines(lines: list[str]) -> set[str]:
    return _metric_family_names_from_prometheus_text("\n".join(lines) + "\n")


def test_scrape_sample_receipt_hashes_exact_sample_lines() -> None:
    receipt = _receipt()
    scrape_sample = receipt["scrape_sample"]  # type: ignore[index]
    sample_lines = scrape_sample["sample_lines"]  # type: ignore[index]
    sample_text = "\n".join(sample_lines) + "\n"
    digest = "sha256:" + hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert scrape_sample["format"] == "prometheus_text_0_0_4"  # type: ignore[index]
    assert scrape_sample["sample_text_sha256"] == digest  # type: ignore[index]
    assert receipt["raw_reasoning_included"] is False


def test_scrape_sample_receipt_names_all_required_metric_families() -> None:
    receipt = _receipt()
    scrape_sample = receipt["scrape_sample"]  # type: ignore[index]
    required = set(scrape_sample["required_metric_families"])  # type: ignore[index]
    observed = _metric_family_names_from_sample_lines(scrape_sample["sample_lines"])  # type: ignore[index]

    assert len(required) == 16
    assert observed == required
    assert receipt["summary"]["required_family_count"] == 16  # type: ignore[index]
    assert receipt["summary"]["observed_family_count"] == 16  # type: ignore[index]
    assert receipt["summary"]["missing_family_count"] == 0  # type: ignore[index]
    assert receipt["summary"]["closure_state"] == "repository_local_scrape_verified"  # type: ignore[index]


def test_local_metrics_route_exposes_receipt_required_families() -> None:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app

    receipt = _receipt()
    required = set(receipt["scrape_sample"]["required_metric_families"])  # type: ignore[index]
    client = TestClient(app)
    client.post("/api/v1/tenant/budget", json={"tenant_id": "scrape-sample-tenant"})

    response = client.get("/metrics")
    observed = _metric_family_names_from_prometheus_text(response.text)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert required <= observed
    assert "mullu_requests_governed_total" in observed
    assert "mullu_health_score" in observed


def test_scrape_sample_receipt_preserves_public_production_boundary() -> None:
    receipt = _receipt()
    production_boundary = receipt["production_boundary"]  # type: ignore[index]

    assert production_boundary["public_production_claim"] == "not_claimed"
    assert production_boundary["production_endpoint"] == "https://api.mullusi.com/metrics"
    assert production_boundary["solver_outcome"] == "AwaitingEvidence"
    assert (
        production_boundary["latest_probe_receipt"]
        == "examples/product_dashboard_production_prometheus_scrape_probe_receipt.json"
    )
    assert "production_https_scrape_sample" in production_boundary["required_evidence"]
    assert "deployment_witness" in production_boundary["required_evidence"]
