"""Gateway benchmark harness for governed provider comparisons.

Purpose: compare Mullusi gateway overhead against LiteLLM and Portkey-style baselines.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: dataclasses, hashlib, json, statistics.
Invariants: benchmark reports are deterministic, explicit about proof cost, and free of live network calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class GatewayBenchmarkSample:
    """One benchmark observation for a gateway profile."""

    latency_ms: float
    audit_cost_usd: float
    success: bool

    def __post_init__(self) -> None:
        if self.latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        if self.audit_cost_usd < 0:
            raise ValueError("audit_cost_usd must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "audit_cost_usd": self.audit_cost_usd,
            "success": self.success,
        }


@dataclass(frozen=True)
class GatewayBenchmarkProfile:
    """A benchmarked gateway profile with proof-mode metadata."""

    gateway: str
    proof_mode: str
    window_seconds: float
    samples: tuple[GatewayBenchmarkSample, ...]

    def __post_init__(self) -> None:
        if not self.gateway:
            raise ValueError("gateway is required")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if not self.samples:
            raise ValueError("at least one benchmark sample is required")


class GatewayBenchmarkHarness:
    """Compute deterministic gateway benchmark reports."""

    def __init__(self, profiles: tuple[GatewayBenchmarkProfile, ...] | None = None) -> None:
        self._profiles = profiles or default_gateway_benchmark_profiles()

    def run(self) -> dict[str, Any]:
        profile_reports = [self._profile_report(profile) for profile in self._profiles]
        baseline_reports = [report for report in profile_reports if report["gateway"] != "mullusi"]
        mullusi_report = _find_report(profile_reports, "mullusi")
        fastest_baseline = min(baseline_reports, key=lambda report: report["p95_latency_ms"])
        cheapest_baseline = min(baseline_reports, key=lambda report: report["audit_cost_per_request_usd"])
        comparison = {
            "latency_overhead_vs_fastest_baseline_pct": _percent_delta(
                mullusi_report["p95_latency_ms"],
                fastest_baseline["p95_latency_ms"],
            ),
            "audit_cost_delta_vs_cheapest_baseline_usd": round(
                mullusi_report["audit_cost_per_request_usd"]
                - cheapest_baseline["audit_cost_per_request_usd"],
                6,
            ),
            "throughput_delta_vs_fastest_baseline_pct": _percent_delta(
                mullusi_report["throughput_rps"],
                fastest_baseline["throughput_rps"],
            ),
            "proof_tradeoff": "Mullusi records causal proof, audit cost, and policy witness fields; baseline gateways are measured as unproven routing paths.",
        }
        report = {
            "suite_id": "gateway-overhead-offline-v1",
            "mode": "offline_deterministic",
            "profiles": profile_reports,
            "comparison": comparison,
            "invariants": [
                "no_live_network_calls",
                "explicit_audit_cost_per_request",
                "p95_latency_reported",
                "throughput_reported",
                "proof_tradeoff_declared",
            ],
        }
        return {
            **report,
            "report_hash": _stable_hash(report),
        }

    @staticmethod
    def _profile_report(profile: GatewayBenchmarkProfile) -> dict[str, Any]:
        successful_samples = [sample for sample in profile.samples if sample.success]
        latencies = [sample.latency_ms for sample in successful_samples]
        audit_costs = [sample.audit_cost_usd for sample in profile.samples]
        return {
            "gateway": profile.gateway,
            "proof_mode": profile.proof_mode,
            "sample_count": len(profile.samples),
            "success_count": len(successful_samples),
            "success_rate": round(len(successful_samples) / len(profile.samples), 4),
            "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
            "p50_latency_ms": _percentile(latencies, 50),
            "p95_latency_ms": _percentile(latencies, 95),
            "p99_latency_ms": _percentile(latencies, 99),
            "throughput_rps": round(len(successful_samples) / profile.window_seconds, 4),
            "audit_cost_per_request_usd": round(mean(audit_costs), 6),
        }


def default_gateway_benchmark_profiles() -> tuple[GatewayBenchmarkProfile, ...]:
    """Return deterministic seeded gateway profiles for offline CI runs."""
    return (
        GatewayBenchmarkProfile(
            gateway="litellm",
            proof_mode="routing_only",
            window_seconds=10.0,
            samples=(
                GatewayBenchmarkSample(142.0, 0.0, True),
                GatewayBenchmarkSample(148.0, 0.0, True),
                GatewayBenchmarkSample(151.0, 0.0, True),
                GatewayBenchmarkSample(158.0, 0.0, True),
                GatewayBenchmarkSample(164.0, 0.0, True),
            ),
        ),
        GatewayBenchmarkProfile(
            gateway="portkey",
            proof_mode="observability_only",
            window_seconds=10.0,
            samples=(
                GatewayBenchmarkSample(149.0, 0.000004, True),
                GatewayBenchmarkSample(154.0, 0.000004, True),
                GatewayBenchmarkSample(160.0, 0.000004, True),
                GatewayBenchmarkSample(168.0, 0.000004, True),
                GatewayBenchmarkSample(173.0, 0.000004, True),
            ),
        ),
        GatewayBenchmarkProfile(
            gateway="mullusi",
            proof_mode="causal_proof_and_audit",
            window_seconds=10.0,
            samples=(
                GatewayBenchmarkSample(172.0, 0.000013, True),
                GatewayBenchmarkSample(181.0, 0.000013, True),
                GatewayBenchmarkSample(188.0, 0.000013, True),
                GatewayBenchmarkSample(195.0, 0.000013, True),
                GatewayBenchmarkSample(207.0, 0.000013, True),
            ),
        ),
    )


def _find_report(reports: list[dict[str, Any]], gateway: str) -> dict[str, Any]:
    for report in reports:
        if report["gateway"] == gateway:
            return report
    raise ValueError(f"gateway report not found: {gateway}")


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = round((percentile / 100) * (len(sorted_values) - 1))
    return round(sorted_values[index], 2)


def _percent_delta(candidate: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return round(((candidate - baseline) / baseline) * 100, 2)


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"
