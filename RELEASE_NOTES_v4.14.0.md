# Mullu Platform v4.14.0 — MUSIA Runtime (Pagination)

**Release date:** TBD
**Codename:** Page
**Migration required:** No (additive — pagination is strictly opt-in)

---

## What this release is

Adds opt-in pagination to the three list endpoints that could return large
result sets:

- `GET /constructs`
- `GET /constructs/by-run/{run_id}` (run export)
- `GET /musia/tenants/{tenant_id}/runs`

When `page` and/or `page_size` are absent (default), behavior is unchanged
from v4.13.0 — all matching items returned in one envelope. When supplied,
results are paginated with full metadata (`page`, `page_size`,
`total_pages`, `has_more`).

This is a "make existing endpoints scale" release, not a feature release.
No new functionality, just better behavior at scale.

---

## What is new in v4.14.0

### Opt-in `?page=&page_size=` query params

[constructs.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/constructs.py) and [musia_tenants.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_tenants.py).

```http
GET /constructs?page=2&page_size=100 HTTP/1.1
X-Tenant-ID: acme-corp

200 OK
{
  "total": 4321,
  "by_type": { ... },
  "constructs": [ ...100 items... ],
  "tenant_id": "acme-corp",
  "page": 2,
  "page_size": 100,
  "total_pages": 44,
  "has_more": true
}
```

Same pattern applies to `/constructs/by-run/{run_id}` and
`/musia/tenants/{id}/runs`.

### Validation

- `page_size` must be in `[1, 1000]` (rejected with 400 otherwise)
- `page` defaults to `1` if `page_size` is supplied without `page`
- `page` must be `>= 1` (rejected with 400 otherwise)
- Pagination beyond the total returns an empty `items` array with
  `has_more: false` (not an error)

### `total` semantics

The `total` (or `construct_count` / `total_runs`) field always reports the
**full** match count, independent of pagination. The `constructs` /
`runs` array is the page slice. Filters (`tier`, `type_filter`, `run_id`)
apply BEFORE pagination, so `total` reflects the filtered set.

For `GET /constructs`, the `by_type` breakdown also uses the full filtered
set, not just the current page.

### Backward compatibility

When neither `page` nor `page_size` is supplied (default), the response
shape matches v4.13.0 exactly except for four new pagination fields, all
`null`. v4.13 callers that read by-key see no behavior change.

The `total_pages` and `has_more` fields are only meaningful when
pagination is active; they are `null` when not.

---

## Test counts

| Suite                                    | v4.13.0 | v4.14.0 |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 671     | 693     |
| pagination tests (new)                   | n/a     | 22      |

The 22 new tests cover:
- `GET /constructs` default behavior (no pagination) returns all
- Paginated returns slice with full `total` and computed `total_pages`
- Last partial page returns remainder
- `page_size` without `page` defaults `page=1`
- Page beyond total returns empty + `has_more=false`
- Pagination combines with filters (`tier`, `type_filter`, `run_id`)
- Invalid `page_size` (>1000, 0, negative) returns 400
- Invalid `page` (negative, zero) returns 400
- `by_type` breakdown reflects full match, not just page
- `GET /constructs/by-run/{run_id}` default vs. paginated
- Export pagination on unknown run returns valid empty bundle
- Export rejects `page_size > 1000`
- `GET /musia/tenants/{id}/runs` default vs. paginated
- Newest-first sort order preserved across pages
- 404 still returned for unknown tenant in paginated runs list
- `total` independent of `page_size`
- Default response envelope preserves v4.13 shape (new pagination fields `null`)

Doc/code consistency check passes.

---

## Compatibility

- All v4.13.0 endpoints unchanged in URL or shape
- New `page` / `page_size` query params are opt-in
- Response envelopes have four new optional pagination fields, all `null` when not paginated
- All 654 v4.13.0 tests pass without modification
- The Pydantic models accept the new fields with defaults; clients that read by-key are unaffected

---

## Production deployment guidance

### When to paginate

- **Tenants with thousands of constructs** — default unbounded list endpoints become slow + memory-heavy. Use `?page_size=100` (or larger) to chunk.
- **Long-running run exports** — cycles produce ~12 constructs each, but a tenant might persist thousands of runs. Use `?page_size=500` on `/by-run/{id}` to avoid huge response bodies.
- **Tenant onboarding dashboards** — `/musia/tenants/{id}/runs` paginated to 50 per view fits typical UI patterns.

### Default page_size

There is no default. If you want server-imposed default pagination
(automatically chunk all responses), the v4.14.0 implementation does NOT
do that — pagination must be explicitly requested. Tenants with small
registries should not be forced to page.

If a deployment wants forced pagination, a middleware can rewrite
requests to inject `page_size` server-side. Future releases may add a
config flag for this.

---

## What v4.14.0 still does NOT include

- **Cursor-based pagination** — only offset+page. Cursor pagination is more efficient for very large datasets but adds complexity (deletes change positions). Future work.
- **Streaming response format** (NDJSON, etc.) — pagination chunks the data; streaming would emit it incrementally. Not yet.
- **Server-imposed default page size** — pagination is opt-in by design.
- **Sort param** — fixed sort orders (insertion order for constructs, newest-first for runs). Future releases may add `?sort=` for explicit control.
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
v4.14.0  opt-in pagination across list endpoints
```

693 MUSIA tests; 106 docs; six domains over HTTP with self-describing
indexed paginated audit-trail persistence.

---

## Honest assessment

v4.14.0 is the smallest possible response to a real scaling concern.
Tenants with hundreds of constructs see no change. Tenants with tens of
thousands no longer get a megabyte of JSON when they query the registry.
The implementation is ~50 lines of pagination logic plus tests.

What it is not, yet: cursor-based pagination. Offset+page is fine for
read-heavy workloads where the underlying set is stable. For
high-write-rate tenants, pages can shift between requests (a delete
moves everything up by one). Cursor pagination fixes this but the
complexity isn't yet justified by observed traffic patterns.

**We recommend:**
- Upgrade in place. v4.14.0 is additive; no client migration needed.
- Set `page_size=100` (or whatever fits your UI) on dashboards.
- Use `has_more` to drive "load more" buttons; ignore `total_pages` unless your UI shows page counts.

---

## Contributors

Same single architect, same Mullusi project. v4.14.0 closes a v4.13
honest gap (no pagination on potentially-large list endpoints) without
new external dependencies.
