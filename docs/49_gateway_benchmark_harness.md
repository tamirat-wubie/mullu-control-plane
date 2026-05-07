# Gateway Benchmark Harness

Purpose: define the deterministic benchmark harness for comparing Mullusi gateway overhead against LiteLLM and Portkey-style baselines.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: `mcoi_runtime.core.gateway_benchmark_harness`, `scripts/benchmark_gateway_overhead.py`.
Invariants: no live network calls in default mode, explicit proof tradeoff, stable report hash.

## Architecture

| Component | Responsibility | Mutation |
|---|---|---:|
| `GatewayBenchmarkSample` | One latency, audit-cost, and success observation | no |
| `GatewayBenchmarkProfile` | Gateway identity, proof mode, measurement window, samples | no |
| `GatewayBenchmarkHarness` | Computes deterministic latency, throughput, cost, and comparison report | no |
| `scripts/benchmark_gateway_overhead.py` | Emits JSON report for CI or release notes | optional file output only |

## Metrics

| Metric | Meaning |
|---|---|
| `p95_latency_ms` | Published latency overhead comparison point |
| `throughput_rps` | Successful requests divided by benchmark window |
| `audit_cost_per_request_usd` | Mean audit/proof storage cost per request |
| `latency_overhead_vs_fastest_baseline_pct` | Mullusi p95 latency delta against fastest baseline |
| `audit_cost_delta_vs_cheapest_baseline_usd` | Mullusi audit cost delta against cheapest baseline |

## Procedure

1. Run `python scripts/benchmark_gateway_overhead.py`.
2. Save the JSON report with `--output artifacts/gateway_benchmark_report.json` when publishing.
3. Publish latency overhead and audit cost together. Proof has a cost; the benchmark must show it.

STATUS:
  Completeness: 100%
  Invariants verified: deterministic seeded samples, no live network calls, stable report hash, latency metric, throughput metric, audit cost metric, proof tradeoff declaration
  Open issues: none
  Next action: wire the harness into release CI once the artifact directory is standardized
