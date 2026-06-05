# Product Dashboard KPI Math Witness Map

Purpose: bind product-facing dashboard and operator KPIs to executable math
witnesses.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway read models, MCOI dashboard contracts, executive
reporting, cost analytics, tenant analytics, platform metrics, and Grafana
dashboard generation.
Invariants:
- KPI values must be either computed by named code or marked as external input.
- Unit scores and rates must remain bounded.
- Cost and count fields must remain non-negative.
- Grafana panels must not be treated as runtime evidence unless a metric emitter
  or Prometheus source is named.

## Architecture

| KPI surface | Math witness | Verification witness | Proof state |
| --- | --- | --- | --- |
| Commercial invoice readiness | `gateway/commercial_metering.py` computes plan-limit review, overage revenue, provider cost, total revenue, gross margin, and invoice readiness. | `tests/test_gateway/test_commercial_metering.py` | Pass |
| Economic route selection | `gateway/economic_intelligence.py` computes utility as expected value minus model/tool/latency/risk/review/failure cost, with risk multipliers. | `tests/test_gateway/test_economic_intelligence.py` | Pass |
| Workflow mining confidence | `gateway/workflow_mining.py` computes occurrence count, confidence `min(1.0, len(traces) / 5)`, and risk-tier approval rules. | `tests/test_gateway/test_workflow_mining.py` | Pass |
| Temporal readiness | `gateway/temporal_resolution.py` computes tenant timezone conversion, business-day resolution, future-window limits, and high-risk ambiguity blocking. | `tests/test_gateway/test_temporal_resolution.py` | Pass |
| World-state dashboard summary | `mcoi/mcoi_runtime/core/dashboard.py` projects entity, relation, derived fact, contradiction, expected-state, violation, and confidence counts from world-state snapshots. | `mcoi/tests/test_world_state_integration.py`, `mcoi/tests/test_dashboard_contracts.py` | Pass |
| Provider routing dashboard | `mcoi/mcoi_runtime/core/dashboard.py` aggregates routing, success, and failure counts; `mcoi/mcoi_runtime/contracts/dashboard.py` computes success rate as `success_count / routing_count` or `0.0`. | `mcoi/tests/test_dashboard_engine.py`, `mcoi/tests/test_dashboard_contracts.py`, `mcoi/tests/test_dashboard_integration.py` | Pass |
| Learning insight direction | `mcoi/mcoi_runtime/core/dashboard.py` classifies cumulative delta as improving, declining, or stable with bounded thresholds. | `mcoi/tests/test_dashboard_engine.py`, `mcoi/tests/test_dashboard_contracts.py` | Pass |
| Executive KPI rollup | `mcoi/mcoi_runtime/core/executive_reporting.py` computes count, total, average, minimum, and maximum over recorded KPI samples. | `mcoi/tests/test_executive_reporting_engine.py` | Pass |
| Executive KPI trend | `mcoi/mcoi_runtime/core/executive_reporting.py` computes percent change from the last two samples and classifies direction using `higher_is_better`. | `mcoi/tests/test_executive_reporting_engine.py` | Pass |
| Executive outcome, efficiency, cost, and reliability reports | `mcoi/mcoi_runtime/core/executive_reporting.py` computes completion rate, success rate, burn rate, cost per completion, ROI, operation success rate, and drill success rate. | `mcoi/tests/test_executive_reporting_engine.py`, `mcoi/tests/test_executive_reporting_integration.py` | Pass |
| Executive dashboard snapshot | `mcoi/mcoi_runtime/core/executive_reporting.py` counts KPI status buckets and bounds budget utilization and connector health percentages. | `mcoi/tests/test_executive_reporting_engine.py` | Pass |
| Cost analytics dashboard | `mcoi/mcoi_runtime/core/cost_analytics.py` computes tenant cost totals, token totals, average cost per call, model cost splits, daily rate, projected monthly cost, budget remaining, and days to exhaustion. | `mcoi/tests/test_cost_analytics.py` | Pass |
| Tenant analytics dashboard | `mcoi/mcoi_runtime/core/tenant_analytics.py` aggregates registered collectors into tenant-level counts and cost fields; collector failures resolve to `0`. | `mcoi/tests/test_tenant_analytics.py` | Pass |
| Operator control tower | `gateway/operator_control_tower.py` computes missing, degraded, critical signal, blocked, and review counts from panel read models. | `tests/test_gateway/test_operator_control_tower.py` | Pass |
| Operational health read models | health routes and dashboard routes expose bounded health score, component weights, readiness counts, error rate, uptime, and idempotency hit rate. | `mcoi/tests/test_operational_health_read_models.py` | Pass |
| Operational math loop dashboard projection | `mcoi/mcoi_runtime/core/operational_math_loop.py` computes unresolved principles and tension; CLI projection exposes operator review posture. | `mcoi/tests/test_operational_math_loop.py`, `mcoi/tests/test_operational_math_cli.py`, `mcoi/tests/test_operational_math_observability.py` | Pass |
| Finance approval and streaming budget | finance approval and streaming budget validators enforce packet proof, provider binding, closure receipt, predictive debit, cutoff, and settlement arithmetic. | `tests/test_validate_streaming_budget_enforcement.py`, `mcoi/tests/test_finance_approval_packet.py`, `mcoi/tests/test_finance_approval_router.py` | Pass |
| Grafana dashboard panel config | `mcoi/mcoi_runtime/core/grafana_dashboard.py` generates rows, panels, thresholds, units, and PromQL expressions; `mcoi/mcoi_runtime/core/platform_metrics.py` registers exact collector families for every default panel expression. | `mcoi/tests/test_grafana_dashboard.py`, `mcoi/tests/test_platform_metrics.py`, `tests/test_product_dashboard_grafana_metric_emitter_receipt.py` | Pass |

## Grafana Metric Source Classification

The Grafana dashboard is a projection surface. The following panel expressions
are configured and schema-tested, but the panel config is not by itself a live
metric receipt.

Emitter receipt:
`examples/product_dashboard_grafana_metric_emitter_receipt.json`

Repository-local scrape sample receipt:
`examples/product_dashboard_prometheus_scrape_sample_receipt.json`

Public production scrape probe receipt:
`examples/product_dashboard_production_prometheus_scrape_probe_receipt.json`

Current receipt outcome: `SolvedVerified`. `PlatformMetricsCollector` now
registers exact metric families for all default Grafana panel expressions, and
the app-level Prometheus scrape bootstrap registers the same dashboard family
names. `/metrics` projects existing runtime read models into those families
through `PrometheusMetricProjector` with counter delta guards. Unit-ratio gauges
such as health, budget utilization, and chain success are multiplied by `100` in
the dashboard expression, not in the emitted metric.

Public production scrape outcome: `AwaitingEvidence`.
`api.mullusi.com` did not resolve during the non-mutating scrape probe on
2026-06-04, so no production `/metrics` or `/health` sample can be claimed from
this repository state.

Production probe command:

```powershell
python scripts/collect_product_dashboard_production_prometheus_scrape_probe.py --gateway-url https://api.mullusi.com --host api.mullusi.com --output examples/product_dashboard_production_prometheus_scrape_probe_receipt.json --json
```

Production probe validation command:

```powershell
python scripts/validate_product_dashboard_production_prometheus_scrape_probe_receipt.py --receipt examples/product_dashboard_production_prometheus_scrape_probe_receipt.json --output .change_assurance/product_dashboard_production_prometheus_scrape_probe_validation.json --json
```

| Grafana expression | Source status | Required closure evidence |
| --- | --- | --- |
| `mullu_uptime_seconds` | exact collector + route projection | `mullu_uptime_seconds` gauge registered and projected |
| `mullu_health_score * 100` | exact collector + route projection | `mullu_health_score` unit-ratio gauge registered and projected |
| `mullu_active_tenants` | exact collector + route projection | `mullu_active_tenants` gauge registered and projected |
| `rate(mullu_errors_total[5m])` | exact collector + route projection | `mullu_errors_total` counter registered and delta-projected |
| `rate(mullu_llm_requests_total[5m])` | exact collector + route projection | `mullu_llm_requests_total` counter registered and delta-projected |
| `mullu_llm_latency_p99_seconds` | exact collector + route projection | `mullu_llm_latency_p99_seconds` gauge registered and projected |
| `rate(mullu_llm_tokens_total[5m])` | exact collector + route projection | `mullu_llm_tokens_total` counter registered and delta-projected |
| `mullu_llm_budget_utilization_ratio * 100` | exact collector + route projection | `mullu_llm_budget_utilization_ratio` unit-ratio gauge registered and projected |
| `mullu_requests_governed_total` | exact collector + route projection | `mullu_requests_governed_total` counter registered and delta-projected |
| `mullu_policy_violations_total` | exact collector + route projection | `mullu_policy_violations_total` counter registered and delta-projected |
| `rate(mullu_audit_events_total[5m])` | exact collector + route projection | `mullu_audit_events_total` counter registered and delta-projected |
| `mullu_circuit_breaker_open` | exact collector + route projection | `mullu_circuit_breaker_open` gauge registered and projected |
| `mullu_active_agents` | exact collector + route projection | `mullu_active_agents` gauge registered and projected |
| `rate(mullu_tasks_completed_total[5m])` | exact collector + route projection | `mullu_tasks_completed_total` counter registered and delta-projected |
| `mullu_chain_success_rate * 100` | exact collector + route projection | `mullu_chain_success_rate` unit-ratio gauge registered and projected |
| `rate(mullu_memory_ops_total[5m])` | exact collector + route projection | `mullu_memory_ops_total` counter registered and delta-projected |

## Algorithm

1. Classify each product-facing KPI as executable, read-model input, or external
   metric input.
2. For executable KPIs, name the exact code surface that computes the value.
3. For read-model inputs, name the upstream contract and its bound validation.
4. For external metrics, require a collector family or scrape receipt before the
   panel is treated as closed.
5. Treat every dashboard value without a witness as non-closed.

## Verification

Focused witness command:

```powershell
python -m pytest tests/test_product_dashboard_kpi_math_witness_map.py tests/test_product_dashboard_grafana_metric_emitter_receipt.py tests/test_product_dashboard_prometheus_scrape_sample_receipt.py tests/test_product_dashboard_production_prometheus_scrape_probe_receipt.py tests/test_collect_product_dashboard_production_prometheus_scrape_probe.py tests/test_validate_product_dashboard_production_prometheus_scrape_probe_receipt.py mcoi/tests/test_prometheus_metric_projection.py mcoi/tests/test_server_phase202.py mcoi/tests/test_dashboard_engine.py mcoi/tests/test_dashboard_contracts.py mcoi/tests/test_executive_reporting_engine.py mcoi/tests/test_cost_analytics.py mcoi/tests/test_tenant_analytics.py mcoi/tests/test_grafana_dashboard.py tests/test_gateway/test_operator_control_tower.py -q
```

STATUS:
  Completeness: 100% repository-local / AwaitingEvidence public production
  Invariants verified: executable KPI source mapping, bounded score/rate mapping, non-negative cost/count mapping, Grafana exact-emitter boundary, route-level Prometheus projection, counter delta projection, repository-local scrape sample, production DNS blocker receipt, repeatable production scrape probe, schema-backed production scrape validation
  Open issues: external production Prometheus scrape samples remain blocked until api.mullusi.com resolves and deployment witness evidence is published
  Next action: repair/publish api.mullusi.com DNS target, then rerun the production Prometheus scrape probe
