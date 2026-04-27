# Mullu Platform v4.13.0 — MUSIA Runtime (Indexed Run Lookup + Run Export)

**Release date:** TBD
**Codename:** Index
**Migration required:** No (additive — index reconstructs on load for old snapshots)

---

## What this release is

Closes both v4.12.0 honest gaps:

1. **Indexed run lookup** — adds a secondary `_runs_index: dict[run_id, set[UUID]]` to each `TenantState`. `list_runs`, `delete_run`, `constructs_in_run`, and the `/constructs?run_id=X` filter now operate at O(M) where M is constructs in that run, instead of O(N) over the full registry. Tenants with thousands of unrelated direct writes plus a few hundred persisted runs see a measurable speedup.

2. **Run export endpoint** — `GET /constructs/by-run/{run_id}` returns a self-describing run export envelope (run metadata + full construct payloads). Suitable for archival, replay analysis, or hand-off to downstream audit consumers.

---

## What is new in v4.13.0

### `TenantState._runs_index` — secondary index

[registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py).

```python
@dataclass
class TenantState:
    ...
    _runs_index: dict[str, set] = field(default_factory=dict)
```

Maps `run_id` → set of construct UUIDs in that run.

Maintained automatically:
- `merge_run` adds new IDs to the appropriate bucket
- `delete_run` removes deleted IDs and drops empty buckets
- `_rebuild_runs_index` (called after persistence load) reconstructs from `graph.constructs` metadata

**Not persisted.** The index is derivable from `graph.constructs.values()` metadata, so persistence stays graph-only and rebuild happens once at load time. This avoids paying snapshot disk overhead for derived state.

### New `TenantState.constructs_in_run(run_id)` method

```python
state.constructs_in_run("run-abc123")
# → list[ConstructBase] — the constructs in that run
# Returns [] for unknown run_id (no error)
```

Used by both the existing `?run_id=X` filter on `GET /constructs` and the new export endpoint.

### `GET /constructs/by-run/{run_id}` — run export endpoint

[constructs.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/constructs.py).

Admin scope. Returns:

```json
{
  "tenant_id": "acme-corp",
  "run_id": "run-abc123def456",
  "domain": "software_dev",
  "summary": "fix budget enforcement leak",
  "timestamp": "2026-04-26T10:23:45.123456+00:00",
  "construct_count": 12,
  "constructs": [
    {"id": "...", "type": "state", "tier": 1, "fields": {...}, ...},
    ...
  ]
}
```

Unknown run_id returns 200 with `construct_count=0` and empty `constructs`, not 404. Reasoning: callers iterating runs from `/musia/tenants/{id}/runs` may race with concurrent deletes, and a 200-with-empty is more ergonomic than a 404 in that race.

For lighter-weight read-scoped queries that just need the construct list, use `GET /constructs?run_id=X` (read scope, lighter envelope, same data).

### Index-aware `?run_id=X` filter

The existing `GET /constructs?run_id=X` filter (v4.11.0) now uses the index for O(M) lookup instead of O(N) scan when run_id is supplied.

```python
if run_id is not None:
    items = state.constructs_in_run(run_id)  # indexed
else:
    items = list(state.graph.constructs.values())  # full scan
```

---

## Performance characteristics

For a tenant with N total constructs and M constructs in a target run:

| Operation                              | v4.12.0 | v4.13.0 |
| -------------------------------------- | ------- | ------- |
| `list_runs()`                          | O(N)    | O(R) where R = distinct runs |
| `delete_run(run_id)`                   | O(N)    | O(M)    |
| `GET /constructs?run_id=X`             | O(N)    | O(M)    |
| `constructs_in_run(run_id)` (new)      | n/a     | O(M)    |
| `merge_run(run_id, constructs)`        | O(K)    | O(K) — unchanged |
| Snapshot load (`_rebuild_runs_index`)  | n/a     | O(N) once |

Concrete example: 5000 direct writes + 1 run with 5 constructs. Pre-v4.13, querying that run scans all 5005 constructs. Post-v4.13, the lookup touches only the 5 in the index.

---

## Test counts

| Suite                                    | v4.12.0 | v4.13.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 651     | 671     |
| index correctness + export (new)         | n/a     | 20      |

The 20 new tests cover:
- Index populated on `merge_run`
- Disjoint membership across runs
- Empty when no runs persisted
- Scrubbed completely on `delete_run`
- Partial state preserved when delete skips constructs (live dependents)
- `constructs_in_run` returns members; `[]` for unknown
- `list_runs` reads metadata from any member
- `list_runs` after delete omits deleted runs
- Index rebuilt after persistence snapshot/load round-trip
- `_rebuild_runs_index` idempotent
- `_rebuild_runs_index` handles graphs with no runs
- HTTP export endpoint returns full run with metadata + constructs
- Export endpoint unknown run returns 200 with empty bundle
- Export endpoint per-tenant isolated
- Export endpoint after delete returns empty
- Exported constructs share consistent run metadata
- Existing `?run_id=X` filter still works (regression check)
- Filter combined with `?tier=N`
- Performance smoke: 5000 unrelated writes + 1 run → index has only the 5 run members

Doc/code consistency check passes.

---

## Compatibility

- All v4.12.0 endpoints unchanged in URL or shape
- New endpoint `GET /constructs/by-run/{run_id}` is additive
- Index is internal state — old snapshot files (no index) load cleanly; the index reconstructs in `load_tenant`
- All 634 v4.12.0 tests pass without modification

---

## Production deployment guidance

### When to use export vs. filter

- **`GET /constructs?run_id=X`** (read scope) — tenant inspecting their own audit trail; lighter envelope; combines with `tier`/`type_filter`
- **`GET /constructs/by-run/{run_id}`** (admin scope) — operational tooling, archival, replay; richer envelope with run metadata; one canonical bundle per run

### Index rebuild on startup

If your deployment uses persistence and serves traffic immediately on startup, the first `load_all()` does an O(N) scan per tenant to rebuild the index. For tenants with millions of constructs, this is the right one-time cost — subsequent operations are O(M) per run.

If startup-time matters more than per-request latency, consider lazy index construction (build on first run-id query). Not implemented in v4.13.0; `_rebuild_runs_index` runs eagerly on load.

---

## What v4.13.0 still does NOT include

- **Persisted index** — the index is derived; we accept the load-time rebuild cost.
- **Pagination on export** — for runs with thousands of constructs, the export envelope can be large. No streaming or page param yet.
- **Index for non-run metadata** — only `run_id` is indexed. Other metadata fields require a scan.
- **Distributed rate limits, JWKS-with-RSA, multi-process backend, Φ_gov ↔ governance_guard, Rust port** — still ahead.

---

## Cumulative MUSIA progress

```
v4.0.0   substrate (Mfidel + Tier 1)
v4.1.0   full 25 constructs + cascade + Φ_gov + cognition + UCJA
v4.2.0   HTTP surface + governed writes + business_process adapter
v4.3.0   multi-tenant registry isolation
v4.3.1   auth-derived tenant resolution
v4.4.0   persistent tenant state
v4.5.0   auto-snapshot + JWT + scope enforcement
v4.6.0   scientific_research + bulk migration runner
v4.7.0   manufacturing + healthcare + education adapters
v4.8.0   /domains HTTP surface + adapter cleanup
v4.9.0   JWT rotation + tenant construct count quotas
v4.10.0  sliding-window rate limits + quota persistence
v4.11.0  persist_run audit trail + run_id queries
v4.12.0  run metadata enrichment + bulk delete + runs listing
v4.13.0  indexed run lookup + run export endpoint
```

671 MUSIA tests; 105 docs; six domains over HTTP with self-describing
indexed audit-trail persistence; multi-tenant + multi-auth-with-rotation
+ persistent-with-quota + scope-enforced + size-and-rate-bounded +
run-traceable + run-cleanable + run-exportable.

---

## Honest assessment

v4.13.0 is the "make it scale" release for the audit-trail story. v4.12
shipped the operational surface (list, delete, metadata); v4.13 makes
those operations not-O(N). For most current deployments this is
invisible — they have hundreds of runs, not millions. For tenants that
will scale to high run counts, the index is the difference between
"works fine" and "starts costing real seconds per query."

What it is not, yet: a proper audit-trail database. The index lives
in-process, alongside the registry. A multi-process deployment would
have each process maintain its own copy. Distributed indexing would
require a shared store; that's separate work.

**We recommend:**
- Upgrade in place. v4.13.0 is additive.
- Use `GET /constructs/by-run/{id}` (admin) for archival exports.
- Use `GET /constructs?run_id=X` (read) for routine tenant queries.
- Old snapshot files load cleanly — no migration needed.

---

## Contributors

Same single architect, same Mullusi project. v4.13.0 closes both
honest gaps from v4.12.0: indexed lookup + run export.
