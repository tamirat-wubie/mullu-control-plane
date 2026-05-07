# Mullu Platform v4.23.0 — Cursor Pagination on /constructs

**Release date:** TBD
**Codename:** Cursor
**Migration required:** No (additive — offset pagination unchanged)

---

## What this release is

Closes the cursor-pagination gap noted in v4.14 release notes. Offset
pagination via `page=` + `page_size=` (v4.14.0) drifts under
concurrent inserts/deletes — items can appear twice or be skipped
during long iterations. v4.23 adds cursor pagination via `cursor=` +
`limit=` as an **additive** option on `GET /constructs`. Existing
offset callers see no change.

---

## What is new in v4.23.0

### Cursor pagination on `GET /constructs`

[`constructs.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/constructs.py).

```bash
# First page
curl -H "X-Tenant-ID: acme" \
  "https://mullu.example/constructs?limit=100"
# Response includes `next_cursor` if more items exist

# Next page
curl -H "X-Tenant-ID: acme" \
  "https://mullu.example/constructs?limit=100&cursor=<token>"

# Exhausted — `next_cursor` is null
```

Three pagination modes on `/constructs` (mutually exclusive):

| Mode | Trigger | Stable under inserts/deletes? |
|---|---|---|
| Unpaginated (v4.13.x default) | no params | n/a |
| Offset (v4.14.0+) | `page_size=N`, `page=K` | ❌ |
| **Cursor (v4.23.0+)** | `limit=N`, `cursor=...` | ✅ |

When both modes' params are passed, **cursor takes precedence** and
offset response fields stay null. This makes it safe for clients to
upgrade gradually — pass `limit=` alongside existing `page_size=` and
the new behavior activates immediately.

### Stable iteration semantics

Cursor mode sorts items by UUID lexicographically and uses
"items strictly greater than cursor" as the page boundary:

- **Insert with `id < cursor`** → invisible to subsequent pages (correct: it's "behind" us)
- **Insert with `id > cursor`** → appears in a future page when we reach it (correct)
- **Delete an already-paginated item** → no effect on subsequent pages (correct)
- **Delete a future item** → no longer appears (correct)

Trade-off: items are not returned in insertion order. The contract
doesn't promise insertion order anyway, but if a client relies on it
(implicitly), they should stay on offset pagination.

### Opaque cursor format

The cursor is a base64-urlsafe-encoded JSON `{"after_id": "<uuid>"}`.
Format is implementation-private — we may switch to a different
encoding (e.g., binary, signed) in a future release. Clients should
treat the cursor as opaque: pass back exactly what the server emitted,
no parsing.

```python
# Internal — not part of the API contract:
import base64, json
cursor_str = base64.urlsafe_b64encode(
    json.dumps({"after_id": "abc-123"}, separators=(",", ":")).encode()
).rstrip(b"=").decode()
```

### Validation

- `limit < 1` or `limit > PAGE_SIZE_MAX` (1000) → `400 invalid_limit`
- Malformed cursor → `400 invalid_cursor`
- `cursor` without `limit` → defaults to `PAGE_SIZE_MAX` (returns up to 1000 items)
- `limit` without `cursor` → first page

### `next_cursor` semantics

`next_cursor` in the response is **non-null only when more items exist
beyond the page**. The walking pattern is:

```python
cursor = None
while True:
    resp = GET /constructs?limit=100&cursor={cursor}
    process(resp.constructs)
    cursor = resp.next_cursor
    if cursor is None:
        break
```

A page that exactly fills `limit` may still return `next_cursor=None` if
no more items exist — the server checks past the last returned item.
This avoids the "one extra empty request" pattern common in poorly
designed cursor APIs.

---

## Why only `/constructs` and not other listed endpoints

`/constructs` is the most-likely-to-be-large endpoint in production
(MUSIA tenants accumulate constructs continuously). Other listed
endpoints (`/musia/tenants/<id>/runs`, `/constructs/by-run/<id>`) are
naturally bounded by run count or run size and rarely cross the
thousand-item threshold where offset pagination starts to drift.

The pattern is established by this release; extending to those
endpoints is mechanical follow-up if any deployment hits scale issues
on them.

---

## Test counts

| Suite                                    | v4.22.0 | v4.23.0 |
| ---------------------------------------- | ------- | ------- |
| v4.14 offset pagination (regression)     | 22      | 22      |
| v4.23 cursor pagination (new)            | n/a     | 20      |

The 20 new tests in [`test_v4_23_cursor_pagination.py`](mullu-control-plane/mcoi/tests/test_v4_23_cursor_pagination.py) cover:

**Cursor encoding (3)**
- Encode/decode round-trip
- URL-safe (no `+`, `/`, `=`)
- Opaque to clients (not the raw id)

**`_paginate_cursor` semantics (6)**
- No cursor → first `limit` items, sorted by UUID
- With cursor → strictly after the cursor's id
- Last page returns `next_cursor=None`
- Exact-`limit` page with no remaining items returns `next_cursor=None`
- Stable after delete between pages
- Stable after insert between pages

**HTTP endpoint (11)**
- Sequential cursor walk visits every item exactly once
- Cursor mode excludes offset response fields (page/page_size/total_pages stay null)
- Cursor takes precedence when both modes' params are passed
- `cursor=...` alone (no `limit`) defaults to PAGE_SIZE_MAX
- Invalid cursor → 400 invalid_cursor
- Invalid limit (0 or >max) → 400 invalid_limit with detail
- Total reflects unfiltered match count, not page size
- Empty registry returns no pages cleanly
- Tier/type filters compose with cursor pagination
- Offset and cursor paths report the same `total`

All 22 v4.14 offset pagination tests still pass — additive, no behavior change for existing callers.

---

## Compatibility

- **All v4.22.x callers work unchanged.** Cursor params are optional;
  omitting them preserves v4.22 behavior exactly
- `ConstructListResponse` adds a `next_cursor: str | None = None` field —
  Pydantic deserializers ignore unknown fields by default, so existing
  parsers that don't know about it stay happy
- The two pagination modes are explicitly mutually exclusive — when
  cursor is active, offset response fields are null. Clients that
  null-check (recommended) work in both modes

---

## Production deployment guidance

### When to use which mode

- **Offset pagination**: small, mostly-static lists where order
  matters (insertion order, by_type counts). Comfortable for
  dashboards. Don't use for large lists with concurrent writers.
- **Cursor pagination**: large lists, long-running iteration, any
  pagination that may take more than a few seconds end-to-end.
  Stable under writers; immune to drift.
- **Unpaginated**: small lists known to fit in one response. Watch
  out — a tenant that grows past your assumption silently exceeds
  response size limits.

### Choosing `limit`

- **100–500**: typical for interactive UIs (dashboards, admin pages)
- **1000 (PAGE_SIZE_MAX)**: typical for batch jobs and exports
- Above 1000: not allowed — split into multiple cursors

### Migration from offset

If you already paginate with offset, the cleanest cutover:

```python
# Before (v4.14 offset)
page = 1
while True:
    resp = GET /constructs?page={page}&page_size=100
    process(resp.constructs)
    if not resp.has_more:
        break
    page += 1

# After (v4.23 cursor)
cursor = None
while True:
    params = {"limit": 100}
    if cursor: params["cursor"] = cursor
    resp = GET /constructs (params)
    process(resp.constructs)
    cursor = resp.next_cursor
    if cursor is None:
        break
```

The cursor walk is 1 line shorter and stable under writers — no reason
not to switch for new code.

---

## What v4.23.0 still does NOT include

- **Cursor pagination on `/musia/tenants/<id>/runs`** — naturally bounded
  by run count; rarely large enough to need it. Mechanical follow-up if
  any deployment hits scale issues
- **Cursor pagination on `/constructs/by-run/<run_id>`** — bounded by
  per-run construct count; same reasoning
- **Reverse cursor (cursor=before)** — only forward iteration today.
  Most paginating clients walk forward; backward only matters for
  "previous page" UI buttons
- **Signed cursors** — cursor format is opaque but unsigned. A
  malicious client can craft a bogus cursor — but the worst case is
  `400 invalid_cursor`, no data leak. Signing matters when cursors
  encode privileged data; ours don't

---

## Production-readiness gap status

```
✅ #3 JWKS/RSA                       — v4.19.0
✅ "in-process counters only"         — v4.20.0
✅ "no latency histograms"            — v4.21.0
✅ CI Node.js 20 deprecation         — v4.22.0
✅ "cursor pagination missing"       — v4.23.0
⏳ #1 Live deployment evidence        — needs real production environment
⏳ #2 Single-process state            — needs Redis + Postgres
⏳ #4 DB schema migrations            — could be done locally; bigger surface
⏳ Per-tenant scrape redaction       — small, contained, planned next
```

---

## Honest assessment

v4.23 is small (~95 lines source + ~270 lines tests). The cursor
implementation does the boring-correct thing: sort by UUID, "strictly
greater than cursor" boundary, opaque base64-JSON cursor. No clever
tricks. Stability under inserts/deletes is the whole point — the
mechanism is straightforward; the tests prove it works.

What it is not, yet: cursor pagination on every listed endpoint.
v4.23 establishes the pattern on `/constructs`; extending to other
endpoints is mechanical when scale demands it.

**We recommend:**
- Upgrade in place. v4.23 is additive; offset behavior unchanged.
- For new pagination code, use cursor mode. For existing offset code,
  migrate when you hit drift symptoms (duplicates or skipped items
  during long walks).
- If a deployment relies on insertion order from `/constructs`, stay
  on offset — cursor mode sorts by UUID, not insertion time.
