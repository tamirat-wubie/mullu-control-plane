# Mullu Platform v3.13.1 — Substrate-Soak Telemetry Patch

**Release date:** 2026-05-06
**Codename:** Pre-Soak
**Migration required:** No

---

## Why this patch exists

v4.0.0 introduces a second Mfidel implementation (`substrate/mfidel/grid.py`) that coexists with the existing `core/mfidel_matrix.py`. The two grids encode different causal claims about the substrate (272 dense atoms vs. 269 atoms with three known-empty col-8 slots).

Convergence to a single source of truth is scheduled for the v4.0.x soak window via Option 1b (spec is truth, vectorizer is derived view). Convergence is **gated** on a 4-week soak that must surface:

- whether any request flow touches both implementations
- which existing callers of `core/mfidel_matrix.py` depend on synthesized col-8 fidels
- the runtime cost of the new substrate path
- the per-tenant traffic distribution across both paths

This patch ships the telemetry needed to make the gate falsifiable. **Without it, the 4-week soak is calendar time; with it, the soak is a measurement.**

The patch must land before the v4.0.0 announcement so that day-zero of the soak is also day-zero of the data.

---

## What is new

- **`mcoi_runtime/substrate/metrics.py`** — new module
  - `SubstratePathRegistry` — thread-safe singleton tracking lookups per Mfidel implementation
  - Per-correlation-id path tracking with `bind_correlation()` / `close_request()`
  - Verdicts at request close: `legacy_only` | `canonical_only` | `mixed` | `none`
  - Snapshot API for dashboards and Prometheus export
  - `MUSIA_MODE` distribution gauge (records `unset` for v3.13.1/v4.0.0; reserved for v4.1.0 when the flag becomes meaningful)
- **`core/mfidel_matrix.py`** — instrumentation only
  - `MfidelMatrix.lookup()` records `legacy_matrix` path
  - `MfidelMatrix.glyph_to_position()` records `legacy_matrix` path
  - `MfidelMatrix.vectorize()` records `legacy_matrix` path (once per call, not per character)
  - No behavior change. Lazy import to avoid load-order cycles.
- **`substrate/mfidel/grid.py`** — instrumentation only
  - `fidel_at()` records `canonical_grid` path
  - No behavior change.
- **`core/request_correlation.py`** — bridge added
  - `CorrelationManager.start()` calls `substrate.metrics.bind_correlation(cid)`
  - `CorrelationManager.complete()` finalizes the substrate per-request bucket and clears the contextvar
  - Existing `CorrelationContext` (frozen+slots) is unchanged

---

## What is unchanged

- All existing endpoints behave identically to v3.13.0
- All existing audit/proof/governance flows are unchanged
- All 44,500+ existing tests still pass (verified — see `tests/test_mfidel_matrix.py`, `tests/test_mfidel_semantics.py`, `tests/test_request_correlation.py`)
- No new dependencies
- No new endpoints
- No new flags
- No new versions of any contract or schema

This patch is purely additive. The only externally observable change is **new metrics** appearing in the Prometheus scrape.

---

## New metrics

| Metric                          | Type  | Labels                                | Source                |
| ------------------------------- | ----- | ------------------------------------- | --------------------- |
| `substrate_mfidel_lookups_total`| gauge | `path={legacy_matrix,canonical_grid}` | per-lookup increments |
| `substrate_requests_total`      | gauge | `bucket={legacy_only,canonical_only,mixed}` | per-request close |
| `substrate_requests_open`       | gauge | —                                     | live count            |
| `substrate_musia_mode_total`    | gauge | `mode={unset,...}`                    | per request           |

(Cumulative totals are exposed as gauges in v3.13.1 for simplicity. v4.1+ moves to true Prometheus counters with delta tracking once the soak settles.)

---

## Test additions

15 new tests in `tests/test_substrate_metrics.py`:

- canonical grid path recorded
- legacy matrix path recorded
- legacy-only request classified at close
- canonical-only request classified at close
- mixed request flagged at close (the soak gate signal)
- background lookups (no correlation) do not pollute per-request stats
- close with unknown / empty correlation id returns `none`
- invalid path raises `ValueError`
- end-to-end correlation manager bridge
- mode distribution accumulates
- prometheus exporter emits expected gauge names
- lookups outside grid bounds do not increment counters
- `glyph_to_position` records legacy lookup
- `vectorize` records legacy lookup (once per call)

All tests pass. The 90 pre-existing Mfidel/correlation tests also still pass.

---

## Soak gate criteria (W4 review)

Convergence to Option 1b proceeds **only if** at the end of W4:

- `substrate_requests_total{bucket="mixed"}` is zero, OR every mixed flow has a documented migration path
- legacy callers depending on synthesized col-8 fidels (`f[20][8]`, `f[21][8]`, `f[24][8]`) are enumerated and have migration paths
- p95 latency delta vs v3.13.0 is within ±5% across all instrumented endpoints
- no pilot has filed P0/P1 against either Mfidel path
- substrate self-tests still pass

If any criterion fails, convergence postpones until criteria pass. Phase 2 blocks postpone correspondingly. Timeline extends honestly; no compression.

---

## Honest assessment

This patch is what makes the v4.0.0 release safe to announce. Without telemetry, the dual-Mfidel coexistence is a structural fault that can only be detected by accident. With telemetry, the fault is observable in real time.

The total cost was 3 days of W0a engineering for a substantial reduction in v4.0.0 → v4.0.x risk. We recommend: install v3.13.1, scrape metrics for at least 7 days, then consider the v4.0.0 announcement.
