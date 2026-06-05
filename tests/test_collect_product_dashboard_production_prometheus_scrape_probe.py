"""Tests for production Prometheus scrape probe collection.

Purpose: prove public dashboard metric evidence can be collected without
mutating deployment state.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.collect_product_dashboard_production_prometheus_scrape_probe.
Invariants:
  - DNS failures preserve AwaitingEvidence.
  - Production closure requires DNS, health, and all metric families.
  - CLI writes a bounded receipt and returns non-zero when evidence is open.
"""

from __future__ import annotations

import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_product_dashboard_production_prometheus_scrape_probe import (  # noqa: E402
    HttpProbeResult,
    REQUIRED_METRIC_FAMILIES,
    collect_production_prometheus_scrape_probe,
    main,
)


FIXED_NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _prometheus_text(families: tuple[str, ...] = REQUIRED_METRIC_FAMILIES) -> bytes:
    lines: list[str] = []
    for family in families:
        lines.append(f"# HELP {family} test metric")
        lines.append(f"# TYPE {family} gauge")
        lines.append(f"{family} 1.0")
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_probe_records_dns_unresolved_without_calling_http() -> None:
    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        raise socket.gaierror("private resolver detail")

    def http_getter(url: str) -> HttpProbeResult:
        raise AssertionError(f"HTTP getter should not run while DNS is unresolved: {url}")

    receipt = collect_production_prometheus_scrape_probe(
        resolver=resolver,
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    dns_resolution = receipt["probe"]["dns_resolution"]  # type: ignore[index]
    metrics_probe = receipt["probe"]["metrics_http_probe"]  # type: ignore[index]

    assert receipt["proof_state"] == "Fail"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert dns_resolution["status"] == "unresolved"
    assert metrics_probe["request_reached_endpoint"] is False
    assert receipt["summary"]["production_claim_closed"] is False  # type: ignore[index]
    assert "private resolver detail" not in json.dumps(receipt)


def test_probe_closes_only_when_dns_health_and_metric_families_pass() -> None:
    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        return ("203.0.113.10",)

    def http_getter(url: str) -> HttpProbeResult:
        if url.endswith("/metrics"):
            return HttpProbeResult(200, {"content-type": "text/plain"}, _prometheus_text(), True, "")
        if url.endswith("/health"):
            return HttpProbeResult(200, {"content-type": "application/json"}, b'{"status":"healthy"}', True, "")
        raise AssertionError(url)

    receipt = collect_production_prometheus_scrape_probe(
        resolver=resolver,
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    summary = receipt["summary"]  # type: ignore[index]
    metrics_probe = receipt["probe"]["metrics_http_probe"]  # type: ignore[index]

    assert receipt["proof_state"] == "Pass"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["closure_state"] == "production_scrape_verified"
    assert summary["production_claim_closed"] is True
    assert summary["observed_family_count"] == len(REQUIRED_METRIC_FAMILIES)
    assert metrics_probe["missing_metric_families"] == []
    assert receipt["blockers"] == []


def test_probe_closes_with_extra_non_required_prometheus_families() -> None:
    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        return ("203.0.113.10",)

    def http_getter(url: str) -> HttpProbeResult:
        if url.endswith("/metrics"):
            families = (*REQUIRED_METRIC_FAMILIES, "python_gc_objects_collected_total")
            return HttpProbeResult(200, {"content-type": "text/plain"}, _prometheus_text(families), True, "")
        if url.endswith("/health"):
            return HttpProbeResult(200, {"content-type": "application/json"}, b'{"status":"healthy"}', True, "")
        raise AssertionError(url)

    receipt = collect_production_prometheus_scrape_probe(
        resolver=resolver,
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    summary = receipt["summary"]  # type: ignore[index]
    metrics_probe = receipt["probe"]["metrics_http_probe"]  # type: ignore[index]

    assert receipt["solver_outcome"] == "SolvedVerified"
    assert summary["production_claim_closed"] is True
    assert summary["observed_family_count"] == len(REQUIRED_METRIC_FAMILIES) + 1
    assert "python_gc_objects_collected_total" in metrics_probe["observed_metric_families"]
    assert metrics_probe["missing_metric_families"] == []


def test_probe_blocks_when_metrics_endpoint_omits_required_family() -> None:
    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        return ("203.0.113.10",)

    families = tuple(family for family in REQUIRED_METRIC_FAMILIES if family != "mullu_chain_success_rate")

    def http_getter(url: str) -> HttpProbeResult:
        if url.endswith("/metrics"):
            return HttpProbeResult(200, {"content-type": "text/plain"}, _prometheus_text(families), True, "")
        if url.endswith("/health"):
            return HttpProbeResult(200, {"content-type": "application/json"}, b'{"status":"healthy"}', True, "")
        raise AssertionError(url)

    receipt = collect_production_prometheus_scrape_probe(
        resolver=resolver,
        http_getter=http_getter,
        now_utc=FIXED_NOW,
    )
    blockers = receipt["blockers"]  # type: ignore[index]
    metrics_probe = receipt["probe"]["metrics_http_probe"]  # type: ignore[index]

    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["summary"]["production_claim_closed"] is False  # type: ignore[index]
    assert "mullu_chain_success_rate" in metrics_probe["missing_metric_families"]
    assert {blocker["kind"] for blocker in blockers} == {"missing_metric_families"}
    assert "deploy the dashboard metric projection" in blockers[0]["required_next_action"]


def test_probe_cli_writes_unresolved_receipt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def resolver(host: str) -> tuple[str, ...]:
        assert host == "api.mullusi.com"
        return ()

    output_path = tmp_path / "production_probe.json"
    exit_code = main(
        ["--output", str(output_path), "--json"],
        resolver=resolver,
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["summary"]["production_claim_closed"] is False
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""
