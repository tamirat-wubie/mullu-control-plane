# Mullu Platform v4.12.0 — MUSIA Runtime (Run Metadata + Bulk Operations)

**Release date:** TBD
**Codename:** Ledger
**Migration required:** No (additive — old run-stamped constructs work fine)

---

## What this release is

Closes the v4.11.0 honest gaps:

1. **Persisted runs now carry richer metadata** — `run_domain`, `run_summary`, `run_timestamp` join the `run_id` stamp. A run is self-describing without re-reading the original request.
2. **Bulk delete by run** — `DELETE /constructs/by-run/{run_id}` removes all constructs from a single run in one call, atomically.
3. **Runs listing endpoint** — `GET /musia/tenants/{tenant_id}/runs` returns every persisted run on a tenant in newest-first order, with full metadata.

---

## What is new in v4.12.0

### Enriched run metadata

[registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py).

`TenantState.merge_run()` extended with three new optional keyword args:

```python
def merge_run(
    self,
    run_id: str,
    constructs: list,
    *,
    domain: str | None = None,         # v4.12.0
    summary: str | None = None,        # v4.12.0
    timestamp_iso: str | None = None,  # v4.12.0 (auto-generated if omitted)
) -> tuple[bool, str]:
```

Each construct gets the following metadata stamped in place:
- `run_id` (v4.11.0)
- `run_timestamp` (v4.12.0; auto-set to merge time if not supplied)
- `run_domain` (v4.12.0; only stamped when supplied)
- `run_summary` (v4.12.0; only stamped when supplied)

The domain router passes `domain` and `summary` through automatically — every persisted run via `/domains/<name>/process?persist_run=true` gets the full enrichment.

### `GET /musia/tenants/{tenant_id}/runs`

[musia_tenants.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_tenants.py).

Admin scope. Returns:

```json
{
  "tenant_id": "acme-corp",
  "total_runs": 47,
  "runs": [
    {
      "run_id": "run-abc123",
      "domain": "software_dev",
      "summary": "fix budget enforcement leak",
      "timestamp": "2026-04-26T10:23:45.123456+00:00",
      "construct_count": 12
    },
    ...
  ]
}
```

Newest-first by timestamp. Constructs without `run_id` metadata (i.e. direct API writes) are skipped.

### `DELETE /constructs/by-run/{run_id}`

[constructs.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/constructs.py).

Admin scope. Removes every construct stamped with `run_id` for the requesting tenant. Returns 200 with a count summary:

```json
{
  "tenant_id": "acme-corp",
  "run_id": "run-abc123",
  "deleted": 12,
  "skipped": 0,
  "skipped_ids": []
}
```

Skip behavior: constructs that have **live dependents** (other constructs referencing them) are skipped to avoid orphaning. Their UUIDs land in `skipped_ids`. The caller can decide whether to retry after addressing the dependency, force-delete the dependents first, or accept the partial delete.

This endpoint is admin-scoped (not write-scoped) because bulk operations have larger blast radius than individual deletes — an accidental wildcard match would be much worse than an accidental single delete.

### `TenantState.list_runs()` and `TenantState.delete_run()`

Direct Python API for the same operations:

```python
state = STORE.get("acme-corp")
runs = state.list_runs()
# [{"run_id": "...", "domain": "...", "summary": "...", "timestamp": "...", "construct_count": N}, ...]

result = state.delete_run("run-abc123")
# {"deleted": 12, "skipped": 0, "skipped_ids": []}
```

Both run a single linear scan of `state.graph.constructs.values()`. For tenants with hundreds of thousands of constructs, indexing by `run_id` would be a separate optimization workstream.

---

## Test counts

| Suite                                           | v4.11.0 | v4.12.0 |
| ----------------------------------------------- | ------- | ------- |
| MUSIA-specific suites                           | 627     | 651     |
| run metadata + bulk delete + runs listing (new) | n/a     | 24      |

The 24 new tests cover:
- `merge_run` stamps default ISO timestamp when omitted
- `merge_run` uses provided timestamp_iso verbatim
- `merge_run` stamps `run_domain` and `run_summary` when supplied
- `merge_run` omits optional fields when not supplied (only `run_id` and `run_timestamp` are mandatory)
- `list_runs` groups by `run_id`
- `list_runs` skips constructs without `run_id` (direct API writes)
- `list_runs` orders newest-first by timestamp
- `list_runs` empty when no runs
- `delete_run` removes all matching constructs
- `delete_run` skips unrelated constructs (no run_id metadata)
- `delete_run` skips constructs with live dependents (no orphaning)
- `delete_run` unknown run_id returns zero counts (no error)
- HTTP: persisted run stamps domain + summary on every construct
- HTTP: each of the six domains stamps the correct domain string
- `GET /musia/tenants/{id}/runs` returns runs with metadata
- `GET /runs` 404 for unknown tenant
- `GET /runs` excludes direct writes
- `DELETE /constructs/by-run/{id}` removes all matching constructs
- bulk-delete unknown run_id returns 200 with zero counts
- bulk-delete only touches the requested run (other runs unaffected)
- bulk-delete per-tenant isolated (tenant A can't delete tenant B's runs)
- bulk-delete does not remove direct-write constructs
- runs listing post-delete omits the deleted run

Doc/code consistency check passes.

---

## Compatibility

- All v4.11.0 endpoints unchanged in URL or shape
- `merge_run`'s new kwargs are optional — existing callers see no change
- Existing run-stamped constructs (created with v4.11.0) continue to work; they simply lack the new metadata fields, which is gracefully handled by `list_runs` (returns `null` for absent fields)
- New `/by-run/{run_id}` and `/runs` endpoints are purely additive
- All 610 v4.11.0 tests pass without modification

---

## Production deployment guidance

### Audit dashboard backed by `/musia/tenants/{id}/runs`

```python
runs = client.get(f"/musia/tenants/{tenant}/runs").json()["runs"]
# Render in newest-first order; each run has its self-describing metadata
```

### Run-level cleanup runbook

```bash
# Inspect what runs exist
GET /musia/tenants/acme-corp/runs

# Delete a specific run's audit trail (admin auth required)
DELETE /constructs/by-run/run-abc123def456
# Returns count + any skipped UUIDs (constructs that other constructs depend on)

# If skipped IDs were returned, decide:
# (a) Find dependents via GET /constructs/{skipped_id}/dependents
# (b) Force-delete each dependent first
# (c) Accept the partial cleanup
```

### Quota interaction

Each run's ~12 constructs count against `quota.max_constructs`. A
deployment doing 100 runs/day per tenant adds ~1200 constructs/day. The
runs listing makes the rate observable; pair with `/quota` to keep
projection vs. cap visible.

---

## What v4.12.0 still does NOT include

- **Indexed run lookup** — `list_runs()` scans every construct. Future releases may add a secondary index on `run_id` for tenants with millions of constructs.
- **TTL or auto-prune** — runs accumulate forever. Operators handle their own retention via the new bulk-delete endpoint.
- **Run replay** — the audit trail records constructs but not the cycle's step ordering or per-step decisions. Replaying a run from its persisted constructs alone is not sufficient.
- **Run-level export** — no batch download endpoint. Use `GET /constructs?run_id=X` with pagination (when added).
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
```

651 MUSIA tests; 104 docs; six domains over HTTP with self-describing
audit-trail persistence; multi-tenant + multi-auth-with-rotation +
persistent-with-quota + scope-enforced + size-and-rate-bounded +
run-traceable + run-cleanable.

---

## Honest assessment

v4.12.0 closes the v4.11 audit-trail loop. A persisted run is now
self-describing (every construct knows what domain it came from, what
the request summary was, when the run happened), discoverable
(`/runs`), and disposable (`/by-run/{id}` cleanup). The audit trail
graduates from "exists" to "operationally usable."

What it is not, yet: ergonomic at scale. Tenants with 100k+ constructs
will see linear scans on `list_runs` and `delete_run`. For most
production deployments this is fine — runs are typically in the
thousands per tenant per month, and a linear scan over 100k is
sub-second. For workloads at higher scale, indexing run_id is the
next workstream.

**We recommend:**
- Upgrade in place. v4.12.0 is additive.
- Use `/runs` for audit dashboards.
- Use `/by-run/{run_id}` for retention cleanup (not `/constructs/{id}`).
- Quota-budget for ~12 constructs per persisted run.

---

## Contributors

Same single architect, same Mullusi project. v4.12.0 closes both honest
gaps from v4.11.0: metadata enrichment + bulk operations.
