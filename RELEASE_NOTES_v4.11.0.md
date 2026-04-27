# Mullu Platform v4.11.0 — MUSIA Runtime (Audit Trail Completion)

**Release date:** TBD
**Codename:** Lineage
**Migration required:** No (additive — `persist_run` defaults to false)

---

## What this release is

Closes the audit-trail gap from v4.8 release notes: `/domains/<name>/process`
calls now optionally persist the cycle's constructs into the tenant's
registry. Each persisted run gets a `run_id` that lets callers query
the constructs back later.

Before v4.11.0, every domain run discarded its construct graph after
producing the result. After v4.11.0, an opt-in `?persist_run=true` query
param keeps the constructs as queryable audit artifacts. The cycle's
~12 constructs become tenant-scoped registry entries with
`metadata["run_id"] = "run-<uuid>"`.

---

## What is new in v4.11.0

### `?persist_run=true` query param on every `/domains/<name>/process` endpoint

[domains.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/domains.py).

```http
POST /domains/software-dev/process?persist_run=true HTTP/1.1
X-Tenant-ID: acme-corp
{...}

200 OK
{
  "domain": "software_dev",
  "governance_status": "approved",
  "audit_trail_id": "<uuid>",
  "run_id": "run-abc123def456",   ← new in v4.11.0
  ...
}
```

Default is false; existing callers see no change. When true, the run's
~12 cycle constructs (State, Change, Causation, Boundary, Pattern,
Transformation, Validation, Observation, Inference, Decision, Execution)
are merged into the tenant's registry under a freshly-generated run_id.

### `?run_id=X` filter on `GET /constructs`

[constructs.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/constructs.py).

```http
GET /constructs?run_id=run-abc123def456 HTTP/1.1
X-Tenant-ID: acme-corp

200 OK
{
  "total": 12,
  "by_type": {"state": 2, "change": 1, "causation": 1, ...},
  "constructs": [...]
}
```

Combinable with existing `tier` and `type_filter` query params.

### `TenantState.merge_run(run_id, constructs)` — atomic, quota-checked

[registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py).

```python
def merge_run(self, run_id: str, constructs: list) -> tuple[bool, str]:
    """Atomically merge a domain-cycle's audit constructs into the registry."""
```

Behaviors:
- **Atomic**: if the merge would push over `quota.max_constructs`, none of the constructs are inserted (vs. partial insert)
- **Stamps `metadata["run_id"]`** on each construct in place before insert
- **Skips Φ_gov re-evaluation**: cycle constructs are derived from an already-UCJA-passed input; re-evaluation would be redundant
- **Skips rate limit check**: a single domain run is one user-facing operation regardless of internal construct count

The lifetime construct quota IS still checked because it bounds tenant
blast radius. A merge that would exceed the quota is rejected with a
risk_flag attached to the response (no HTTP error — the cycle itself
ran fine; only persistence was rejected).

### `capture: list | None` parameter on every adapter's `run_with_ucja`

Each adapter (`software_dev`, `business_process`, `scientific_research`,
`manufacturing`, `healthcare`, `education`) and the cycle helper
(`run_default_cycle`) accept an optional `capture` list. When provided,
the cycle's constructs are appended after the run completes.

Default is None — no capture, no overhead. Existing callers see no
behavior change.

### Auto-snapshot still applies

If the deployment has `configure_persistence(dir, auto_snapshot=True)`,
a successful `merge_run` does NOT trigger an auto-snapshot. Reasoning:
auto-snapshot is wired into `_governed_write` (the path for individual
construct API writes), not into bulk merges. A multi-construct merge
followed by a single snapshot would race the persistence layer; the
single-construct write path is the safe place for auto-snapshot.

Operators who want domain runs persisted to disk should call
`STORE.snapshot_tenant(tenant_id)` after a `persist_run=true` request,
or set up a periodic flush.

---

## Test counts

| Suite                                    | v4.10.0 | v4.11.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 610     | 627     |
| persist_run + run_id query tests (new)   | n/a     | 17      |

The 17 new tests cover:
- `merge_run` stamps metadata on each construct
- `merge_run` inserts into graph
- `merge_run` blocked by lifetime quota
- `merge_run` atomic — no partial inserts on block
- `merge_run` succeeds with unlimited quota
- `merge_run` does not consume rate-limit slot
- `?persist_run=false` (default) yields null run_id
- `?persist_run=true` returns a run_id
- Persisted run constructs appear in the registry
- `?run_id=X` filter isolates runs (two distinct runs queryable separately)
- Per-tenant isolation: tenant A's run not visible to tenant B
- Quota rejection produces risk flag, not HTTP error; constructs unchanged
- All six domain endpoints accept `?persist_run=true`
- `?run_id=unknown` returns total=0
- `?run_id=X&tier=1` filter combination
- `capture` parameter default works (no capture)
- `capture=[]` collects constructs (Tier 1 + Tier 5 verified)

Doc/code consistency check passes.

---

## Compatibility

- All v4.10.0 endpoints unchanged in URL or shape
- New `run_id` field added to `DomainOutcome` envelope (existing tests of envelope shape updated to acknowledge it)
- `capture` is keyword-only on all adapter functions; positional callers unaffected
- `?persist_run` defaults to false — existing requests behave identically
- `?run_id` filter is optional; default = no filter
- `merge_run` is a new method on `TenantState`; existing callers don't need it

---

## Production deployment guidance

### When to use `persist_run=true`

- **Audit-grade workflows** where every domain run must produce a queryable trail
- **Replay/debugging** — when a run looks wrong, persist it to inspect the cycle's intermediate constructs
- **Compliance** — domain runs that must produce a "what was reasoned" record alongside the result

### When NOT to use it

- **High-volume domain runs** — 12 constructs per call adds up; budget against `max_constructs` quota
- **Cheap reads** — no point persisting a request that just qualified L0 and produced trivial output

### Combining with quotas

`max_constructs` should be sized for the expected ratio of persisted
runs to direct construct writes. A tenant doing 100 persisted runs/day
adds ~1200 audit constructs/day; quota should reflect that plus
direct-write headroom.

---

## What v4.11.0 still does NOT include

- **Run-level metadata richness**: only `run_id` is stamped. Future releases may add domain, request summary, audit_trail_id, timestamp.
- **TTL on run-stamped constructs**: persisted runs accumulate forever. Manual cleanup via `DELETE /constructs/{id}` only.
- **Run-level batch delete** (e.g., `DELETE /constructs?run_id=X`).
- **Auto-snapshot on merge_run**: explicit snapshots only.
- **Distributed rate limits**, **JWKS-with-RSA**, **multi-process backend**, **Φ_gov ↔ governance_guard**, **Rust port** — separate workstreams.

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
```

627 MUSIA tests; 103 docs; six domains over HTTP with optional audit-trail persistence; multi-tenant + multi-auth-with-rotation + persistent-with-quota + scope-enforced + size-and-rate-bounded + run-traceable.

---

## Honest assessment

v4.11.0 closes a structural loop. Before this release, the framework
ran governed cycles but discarded the cycle's intermediate state — the
"how did we get here" was implicit in the response envelope.
v4.11.0 makes it queryable: `?persist_run=true` produces a `run_id`
that points to the 12 constructs the cycle generated.

What it is not, yet: a full reconstruction of the cycle's decision
process. The constructs are stamped with `run_id` but not with their
position in the cycle (which step produced them, what their dependencies
were). Future releases may add this richness; for v4.11.0, the trail
is "these constructs came from this run" — enough for audit, not enough
for full replay.

**We recommend:**
- Upgrade in place. v4.11.0 is additive; default behavior unchanged.
- Use `?persist_run=true` for runs that need audit trails. Skip it for high-volume calls.
- Size quotas to budget for persisted runs (~12 constructs per persisted run).

---

## Contributors

Same single architect, same Mullusi project. v4.11.0 closes the
audit-trail gap that was deferred from v4.8.0.
