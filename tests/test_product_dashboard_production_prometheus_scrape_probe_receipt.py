"""Tests for product dashboard production Prometheus scrape probe receipt.

Purpose: prove failed public scrape probes preserve the production evidence
boundary without claiming public runtime health.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/product_dashboard_production_prometheus_scrape_probe_receipt.json.
Invariants:
  - DNS-unresolved probes remain AwaitingEvidence.
  - Production scrape closure cannot be claimed without observed metric families.
  - Probe receipts must not serialize secret values.
"""

from __future__ import annotations

import json
from pathlib import Path


RECEIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "product_dashboard_production_prometheus_scrape_probe_receipt.json"
)


def _receipt() -> dict[str, object]:
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


def test_production_probe_receipt_records_dns_unresolved_boundary() -> None:
    receipt = _receipt()
    probe = receipt["probe"]  # type: ignore[index]
    dns_resolution = probe["dns_resolution"]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert probe["metrics_endpoint"] == "https://api.mullusi.com/metrics"  # type: ignore[index]
    assert probe["health_endpoint"] == "https://api.mullusi.com/health"  # type: ignore[index]
    assert dns_resolution["status"] == "unresolved"
    assert dns_resolution["resolver_result_count"] == 0


def test_production_probe_receipt_does_not_claim_scrape_closure() -> None:
    receipt = _receipt()
    summary = receipt["summary"]  # type: ignore[index]
    metrics_probe = receipt["probe"]["metrics_http_probe"]  # type: ignore[index]
    health_probe = receipt["probe"]["health_http_probe"]  # type: ignore[index]

    assert summary["closure_state"] == "production_scrape_awaiting_dns"
    assert summary["production_claim_closed"] is False
    assert summary["observed_family_count"] == 0
    assert summary["missing_family_count"] == summary["required_family_count"]
    assert metrics_probe["request_reached_endpoint"] is False
    assert health_probe["request_reached_endpoint"] is False


def test_production_probe_receipt_names_actionable_blockers() -> None:
    receipt = _receipt()
    blockers = receipt["blockers"]  # type: ignore[index]
    blocker_kinds = {blocker["kind"] for blocker in blockers}

    assert blocker_kinds == {"dns_unresolved", "endpoint_unreachable"}
    assert all(blocker["required_next_action"] for blocker in blockers)
    assert any("rerun the production Prometheus scrape probe" in blocker["required_next_action"] for blocker in blockers)
    assert receipt["production_boundary"]["gateway_target_state"] == "AwaitingEvidence"  # type: ignore[index]


def test_production_probe_receipt_does_not_serialize_secrets() -> None:
    serialized = json.dumps(_receipt(), sort_keys=True).lower()

    assert "secret" not in serialized
    assert "access_token" not in serialized
    assert "bearer" not in serialized
    assert "authorization" not in serialized
    assert "password" not in serialized
