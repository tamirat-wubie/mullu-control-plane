"""Tests for deterministic gateway benchmark harness.

Purpose: verify offline gateway comparison metrics and proof tradeoff reporting.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: pytest, gateway benchmark harness.
Invariants: reports are deterministic, bounded, and explicit about proof cost.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.core.gateway_benchmark_harness import (
    GatewayBenchmarkHarness,
    GatewayBenchmarkProfile,
    GatewayBenchmarkSample,
)


def test_default_gateway_benchmark_report_is_deterministic() -> None:
    first_report = GatewayBenchmarkHarness().run()
    second_report = GatewayBenchmarkHarness().run()

    assert first_report == second_report
    assert first_report["suite_id"] == "gateway-overhead-offline-v1"
    assert first_report["mode"] == "offline_deterministic"
    assert first_report["report_hash"].startswith("sha256:")
    assert len(first_report["profiles"]) == 3
    assert "proof_tradeoff_declared" in first_report["invariants"]


def test_gateway_benchmark_report_declares_cost_and_throughput_tradeoff() -> None:
    report = GatewayBenchmarkHarness().run()
    mullusi_profile = next(profile for profile in report["profiles"] if profile["gateway"] == "mullusi")
    comparison = report["comparison"]

    assert mullusi_profile["proof_mode"] == "causal_proof_and_audit"
    assert mullusi_profile["audit_cost_per_request_usd"] > 0
    assert mullusi_profile["throughput_rps"] == 0.5
    assert comparison["latency_overhead_vs_fastest_baseline_pct"] > 0
    assert comparison["audit_cost_delta_vs_cheapest_baseline_usd"] > 0
    assert "causal proof" in comparison["proof_tradeoff"]


def test_gateway_benchmark_rejects_invalid_samples() -> None:
    with pytest.raises(ValueError, match="latency_ms must be non-negative"):
        GatewayBenchmarkSample(latency_ms=-1.0, audit_cost_usd=0.0, success=True)

    with pytest.raises(ValueError, match="audit_cost_usd must be non-negative"):
        GatewayBenchmarkSample(latency_ms=1.0, audit_cost_usd=-0.1, success=True)

    with pytest.raises(ValueError, match="window_seconds must be positive"):
        GatewayBenchmarkProfile(
            gateway="invalid",
            proof_mode="routing_only",
            window_seconds=0.0,
            samples=(GatewayBenchmarkSample(1.0, 0.0, True),),
        )


def test_gateway_benchmark_handles_failed_samples_explicitly() -> None:
    profile = GatewayBenchmarkProfile(
        gateway="mullusi",
        proof_mode="causal_proof_and_audit",
        window_seconds=4.0,
        samples=(
            GatewayBenchmarkSample(100.0, 0.1, True),
            GatewayBenchmarkSample(200.0, 0.1, False),
        ),
    )
    baseline = GatewayBenchmarkProfile(
        gateway="litellm",
        proof_mode="routing_only",
        window_seconds=4.0,
        samples=(GatewayBenchmarkSample(100.0, 0.0, True),),
    )
    portkey = GatewayBenchmarkProfile(
        gateway="portkey",
        proof_mode="observability_only",
        window_seconds=4.0,
        samples=(GatewayBenchmarkSample(100.0, 0.0, True),),
    )

    report = GatewayBenchmarkHarness((baseline, portkey, profile)).run()
    mullusi_profile = next(item for item in report["profiles"] if item["gateway"] == "mullusi")

    assert mullusi_profile["sample_count"] == 2
    assert mullusi_profile["success_count"] == 1
    assert mullusi_profile["success_rate"] == 0.5
    assert mullusi_profile["throughput_rps"] == 0.25
