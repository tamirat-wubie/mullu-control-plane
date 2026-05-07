# Mullu Platform v4.25.0 — `mcoi migrate` CLI Subcommand

**Release date:** TBD
**Codename:** Migrate
**Migration required:** No (additive — new CLI subcommand, existing startup migration unchanged)

---

## What this release is

Closes the "DB schema migrations" gap from the v4.18 audit. The
[`MigrationEngine`](mullu-control-plane/mcoi/mcoi_runtime/persistence/migrations.py)
+ 4 platform migrations have existed since earlier releases and run
automatically at server startup for SQLite. What was missing was an
out-of-band CLI for operators to inspect and apply migrations
without booting the full server — needed for SQLite maintenance
windows and (future) Postgres deployments where multi-instance
race-prevention requires manual application.

v4.25 adds `mcoi migrate {status,history,up}` subcommands.

---

## What is new in v4.25.0

### New CLI subcommand: `mcoi migrate`

[`cli.py`](mullu-control-plane/mcoi/mcoi_runtime/app/cli.py).

```bash
# Show current schema version and pending migrations
mcoi migrate status --db sqlite:///./mullu.db

# Show applied migration history
mcoi migrate history --db sqlite:///./mullu.db

# Apply pending migrations
mcoi migrate up --db sqlite:///./mullu.db

# Preview what would be applied without changing the DB
mcoi migrate up --db sqlite:///./mullu.db --dry-run
```

All three subcommands wrap the existing `MigrationEngine` and use the
same 4 platform migrations that run at startup
(`PLATFORM_MIGRATIONS`). No new schema, no new dialect support —
v4.25 just exposes what was already there.

### Output shapes

`status`:
```
current_version: 0
registered: 4
pending: 4
  v1 initial_schema
  v2 add_ledger_actor_index
  v3 add_audit_trail_table
  v4 add_cost_events_table
```

`up`:
```
applied 4 migration(s):
  v1 initial_schema
  v2 add_ledger_actor_index
  v3 add_audit_trail_table
  v4 add_cost_events_table
```

`history` (after `up`):
```
v  1 initial_schema                           applied=2026-04-27T03:50:00+00:00 checksum=ab12cd34ef567890
v  2 add_ledger_actor_index                   applied=2026-04-27T03:50:00+00:00 checksum=...
...
```

### SQLite only — postgres unchanged

v4.25 supports `sqlite:///<path>` URLs. Postgres deployments continue
to apply migrations out-of-band via SQL files (the existing
production model) — wrapping psycopg2 in the
`MigrationEngine.DBConnection` protocol shape is intentionally
deferred until a customer asks for it. The startup wiring
([`server_platform.py`](mullu-control-plane/mcoi/mcoi_runtime/app/server_platform.py))
has always only auto-migrated for SQLite for the same reason
(multi-instance Postgres races on automatic startup migrations).

`mcoi migrate status --db postgresql://...` returns a clear error
explaining the SQLite-only scope.

### `--dry-run`

`mcoi migrate up --dry-run` lists the pending migrations without
applying them. Useful for ops review:

```
$ mcoi migrate up --db sqlite:///./prod.db --dry-run
would apply 1 migration(s):
  v5 add_construct_provenance_columns
```

---

## Why this isn't "DB schema migrations" the way the audit framed it

The v4.18 audit listed "no automated DB schema migrations" as a
critical gap. That was a misdiagnosis: the engine + 4 migrations
existed; what was missing was operator visibility. v4.25 fixes the
visibility gap; the engine itself didn't need changes.

The remaining piece — Postgres connection wrapping for `mcoi migrate
up --db postgresql://...` — is a small follow-up, but it requires
the optional `[persistence]` extra (`psycopg2-binary`) to be
installed. In the absence of a deployment that actually uses Postgres
through the Mullu Postgres backend (vs. operators applying SQL files
directly), there's no demand to ship it. v4.25 is the actionable
piece; future work picks up Postgres if needed.

---

## Test counts

| Suite                                    | v4.24.0 | v4.25.0 |
| ---------------------------------------- | ------- | ------- |
| existing migration engine tests          | 23      | 23      |
| `mcoi migrate` CLI subcommand (new)      | n/a     | 13      |

The 13 new tests in [`test_v4_25_migrate_cli.py`](mullu-control-plane/mcoi/tests/test_v4_25_migrate_cli.py) cover:

**`status` (2)**
- Fresh database: 4 platform migrations show as pending
- After `up`: `current_version=4`, `pending=0`

**`up` (3)**
- Applies all 4 pending migrations
- Idempotent: second `up` is a no-op
- `--dry-run` lists pending without mutating

**`history` (2)**
- Empty on fresh DB
- Shows version + name + checksum after `up`

**Error paths (3)**
- Postgres URL rejected with clear error
- Unknown URL scheme rejected
- `migrate` with no subcommand returns 1 + usage hint

**Functional (2)**
- After `up`, all expected tables exist (ledger, sessions, requests, audit_trail, cost_events, schema_version)
- `schema_version` table records every applied migration

**Workflow (1)**
- Full operator sequence: status → up → status → history

All 23 existing migration engine tests still pass — additive design.

---

## Compatibility

- **All v4.24.x callers work unchanged.** New CLI subcommand is purely
  additive
- Existing server startup migration logic in
  `server_platform.py:bootstrap_primary_store()` unchanged — sqlite
  deployments still get auto-migration at boot
- The `MigrationEngine` and `PLATFORM_MIGRATIONS` aren't touched —
  this PR only wraps them in CLI scaffolding

---

## Production deployment guidance

### Pre-deploy migration check

Add to your CI/CD pipeline before rolling new code:

```bash
# Check pending migrations before deploy
mcoi migrate status --db $MULLU_DB_URL
mcoi migrate up --db $MULLU_DB_URL --dry-run
```

### SQLite operator workflow

Most useful for local dev or single-box deployments:

```bash
# After git pull, before restarting the server
mcoi migrate status --db sqlite:///./mullu.db
mcoi migrate up --db sqlite:///./mullu.db
# Now restart the server — startup migration will be a no-op
```

### Postgres deployment

The `mcoi migrate` CLI doesn't support postgres yet. For postgres:
- Continue applying migrations from SQL files in your deployment pipeline
- The `PLATFORM_MIGRATIONS` constant in
  `mcoi_runtime/persistence/migrations.py` is the canonical source —
  copy the `sql_pg` text into your migration runner
- Rate-limit application: only one instance should run migrations
  during a maintenance window

If postgres CLI support becomes a real ask, v4.26 can wrap psycopg2
in the `DBConnection` protocol — straightforward but waiting on demand.

---

## What v4.25.0 still does NOT include

- **Postgres CLI support** — `--db postgresql://...` returns a clear
  error explaining sqlite-only. Operators apply postgres migrations
  via SQL files (the existing pre-v4.25 model)
- **`migrate down` / rollback** — the engine is forward-only by
  design (immutable history with checksums). Rollback would require
  reversing-migration files; not in this release
- **Schema diff validation** — `mcoi migrate status` reports versions
  but doesn't validate the actual table shape against the migrations.
  A "verify schema matches" subcommand could land in a future release

---

## Production-readiness gap status

```
✅ #3 JWKS/RSA                       — v4.19.0
✅ "in-process counters only"         — v4.20.0
✅ "no latency histograms"            — v4.21.0
✅ CI Node.js 20 deprecation         — v4.22.0
✅ "cursor pagination missing"       — v4.23.0
✅ "per-tenant scrape redaction"     — v4.24.0
✅ #4 DB schema migrations CLI       — v4.25.0
⏳ #1 Live deployment evidence        — needs real production environment
⏳ #2 Single-process state            — needs Redis + Postgres
```

7 of the 9 audited gaps are now closed. The remaining 2 (live
deployment + distributed state) require external infrastructure
(real cloud + Redis/Postgres) and can't be closed from inside the
codebase alone.

---

## Honest assessment

v4.25 is small (~95 lines source + ~210 lines tests). The actual fix
was operator-surface, not engine work — the engine + migrations have
been there for releases. What the v4.18 audit called "DB schema
migrations missing" was really "DB schema migrations are invisible
to operators outside server boot."

The intentional sqlite-only scope is the design decision worth
flagging. Postgres deployments treat migrations as pipeline artifacts
(SQL files in source control, applied during deploy windows) — auto-
applying via a CLI is convenient for sqlite but raises real questions
for postgres (which instance applies it? does the CLI lock?). Holding
on postgres support until a customer asks lets us design it for their
actual workflow rather than guessing.

**We recommend:**
- Upgrade in place. v4.25 is additive.
- Wire `mcoi migrate up --dry-run` into your CD pipeline as a sanity
  check before rolling new server code.
- For postgres deployments, no change to your existing migration
  workflow — keep applying SQL files manually.
