# Mullu Platform v4.26.0 — Audit P0: MUSIA Auth Wiring + Route Coverage Gate

**Release date:** TBD
**Codename:** Closed
**Migration required:** Yes for `pilot`/`production` deployments — see "Compatibility" below

---

## What this release is

Closes three audit-found authorization fractures in the MUSIA layer
that an external review surfaced. All three were mine — added in
v4.5.0–v4.16.0 and missed by the unit-test-scoped audit I ran in
v4.18.

| Fracture | Source | Fix |
|---|---|---|
| **F16** `musia_auth` resolver short-circuited to wildcard scope when no authenticator was configured. The bootstrap path never called `configure_musia_auth(...)`, so every MUSIA endpoint accepted unauthenticated wildcard-scope requests in production. | Mine, v4.5.0 | Bootstrap now wires `configure_musia_auth(api_key_mgr)` and `configure_musia_jwt(jwt_authenticator)` from `OperationalBootstrap`. Resolver fail-closes (503) when no auth is configured AND `MULLU_ENV != "local_dev"`. |
| **F13** All six `POST /domains/*/process` endpoints declared `Depends(require_read)` but accept `?persist_run=true` which calls `state.merge_run(...)` to write captured constructs. Read-scope credential, write side-effect. | Mine, v4.11.0 | Each endpoint now uses `_resolve_domain_auth(persist_run, auth)` which requires `musia.write` when `persist_run=True`, `musia.read` otherwise. |
| **F14** `POST /ucja/qualify` and `POST /ucja/define-job` had no `Depends(...)` at all. Anonymous CPU-burning DoS surface; ruleset behavior leaked to anyone probing. | Mine, v4.5.0 | `qualify` now requires `musia.read`, `define-job` requires `musia.write` (it produces a JobDraft artifact). |

Plus the structural fix that should have existed before:

- **A pytest collector that walks every router in `include_default_routers` and asserts each non-GET route is either gated by `/api/` middleware or declares a `Depends(require_*)` dependency.** New routers added without proper gating fail this test on the PR.

---

## What is new in v4.26.0

### `configure_musia_dev_mode(allowed: bool)` + fail-closed resolver

[`musia_auth.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_auth.py).

Pre-v4.26: `resolve_musia_auth` short-circuited to dev wildcard whenever
`is_auth_configured()` returned False. v4.26 splits that into two
explicit conditions:

```python
if not is_auth_configured():
    if not _DEV_MODE_ALLOWED:
        raise HTTPException(503, detail={
            "error": "musia_auth_not_configured",
            "remedy": "Wire configure_musia_auth(...) at startup, "
                      "or set MULLU_ENV=local_dev to enable dev mode.",
        })
    # else: legacy dev-wildcard branch
```

`configure_musia_dev_mode(True)` is set explicitly by:
1. `bootstrap_server_lifecycle` when `env in ("local_dev", "test")` AND no real authenticator is wired
2. The pytest `conftest.py` autouse fixture (preserves existing test fixtures that called `configure_musia_auth(None)`)

In `pilot`/`production` envs with no authenticator wired, the resolver
now returns a clear 503 instead of silently passing.

### `bootstrap_server_lifecycle` wires `configure_musia_*`

[`server_lifecycle.py`](mullu-control-plane/mcoi/mcoi_runtime/app/server_lifecycle.py) +
[`server.py`](mullu-control-plane/mcoi/mcoi_runtime/app/server.py).

The function now takes `api_key_mgr`, `jwt_authenticator`, and `env`,
and calls `configure_musia_auth(...)` + `configure_musia_jwt(...)`
**before** `include_default_routers(app)`. This guarantees the
resolver state is configured before any route can serve.

```python
# server.py — new lines passed through:
_lifecycle_bootstrap = bootstrap_server_lifecycle(
    ...
    api_key_mgr=_operational_bootstrap.api_key_mgr,
    jwt_authenticator=_jwt_authenticator,
    env=os.environ.get("MULLU_ENV", "local_dev"),
)
```

The `OperationalBootstrap` already constructed `api_key_mgr`; it just
wasn't propagated through. Same for `_jwt_authenticator`.

### Domain endpoint scope split

[`domains.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/domains.py).

```python
def _resolve_domain_auth(persist_run: bool, auth: MusiaAuthContext) -> str:
    required = "musia.write" if persist_run else "musia.read"
    if "*" not in auth.scopes and required not in auth.scopes:
        raise HTTPException(403, ...)
    return auth.tenant_id

@router.post("/software-dev/process", response_model=DomainOutcome)
def process_software_dev(
    payload: SoftwareDevPayload,
    persist_run: bool = False,
    auth: MusiaAuthContext = Depends(resolve_musia_auth),
) -> DomainOutcome:
    tenant_id = _resolve_domain_auth(persist_run, auth)
    ...
```

All six `/domains/*/process` endpoints use this pattern. A read-scoped
credential can no longer flip `?persist_run=true` to write into the
registry.

### UCJA endpoints gated

[`ucja.py`](mullu-control-plane/mcoi/mcoi_runtime/app/routers/ucja.py).

- `POST /ucja/qualify` → `Depends(require_read)`. L0 pipeline; no artifact produced; read scope sufficient.
- `POST /ucja/define-job` → `Depends(require_write)`. Full L0–L9 pipeline producing a `JobDraft`; write scope required.

### Route-coverage CI gate

New test file [`test_v4_26_route_governance_coverage.py`](mullu-control-plane/mcoi/tests/test_v4_26_route_governance_coverage.py).

Walks every `APIRoute` mounted by `include_default_routers` and asserts:

1. Every non-GET route is either:
   - Under `/api/` (middleware-gated), OR
   - Has `Depends(require_read | require_write | require_admin | resolve_musia_auth)` in its handler signature, OR
   - Listed in `_INTENTIONALLY_OPEN` with a written justification

2. Every GET route is either gated, or appears in `_INTENTIONALLY_OPEN`
   (operational probes, public Mfidel grid, domain index — each annotated)

This is the structural fix. New routers added without proper gating
fail this test before merge. Pre-v4.26, this test would have caught
F14 (UCJA POSTs unauth) and the pre-fix F1-style bypass class.

---

## Compatibility

### Breaking change for `pilot`/`production` deployments

**If your deployment runs with `MULLU_ENV=pilot` or `MULLU_ENV=production`
AND has not been wiring `api_key_mgr` / `jwt_authenticator` to the MUSIA
routers** (which, per F16, is every default-bootstrap deployment), the
MUSIA endpoints will now return 503 instead of silently passing
unauthenticated wildcard requests.

This is the correct behavior — those deployments were running an
unauthenticated MUSIA surface — but it surfaces as a 503 in production
on first deploy.

**To preserve existing behavior intentionally** (only do this if you
genuinely want the MUSIA layer open):
```bash
export MULLU_ENV=local_dev   # NOT recommended for prod
```

**To fix it properly** — which is what v4.26 makes possible — your
existing `APIKeyManager` and `JWTAuthenticator` are now wired
automatically through `bootstrap_server_lifecycle`. No additional
configuration needed.

### Test fixtures unchanged

All existing test fixtures that call `configure_musia_auth(None)` to
reset state continue to work. The `conftest.py` autouse fixture sets
`configure_musia_dev_mode(True)` for the test session.

Tests that want to verify the fail-closed behavior call
`configure_musia_dev_mode(False)` explicitly inside their body — see
[`test_v4_26_musia_auth_fail_closed.py`](mullu-control-plane/mcoi/tests/test_v4_26_musia_auth_fail_closed.py).

### README + MAF documentation

- The README's MAF line is now explicit: "Receipt-shape parity with
  Python contracts. NOT currently in the request path: Python does not
  call into Rust today (no PyO3 bindings, maf-cli is a scaffold)."
  Pre-v4.26 the line described the protocol without calling out the
  disconnect. The honest baseline already lived in
  [`docs/MAF_RECEIPT_COVERAGE.md`](mullu-control-plane/docs/MAF_RECEIPT_COVERAGE.md);
  v4.26 just makes the README link to it more explicit.
- Release-notes pointer bumped from v4.18.0 → v4.26.0.

---

## Test counts

| Suite                                    | v4.25.0 | v4.26.0 |
| ---------------------------------------- | ------- | ------- |
| Existing MUSIA suites (regression)       | many    | unchanged |
| `test_v4_26_route_governance_coverage`   | n/a     | 4 |
| `test_v4_26_musia_auth_fail_closed`      | n/a     | 6 |

The 4 route-coverage tests:
- Every non-GET route is gated (catches F14-style regressions)
- Every GET route is either gated or annotated as intentionally open
- `_INTENTIONALLY_OPEN` table has documented justifications for every entry
- Auth-dependency name allow-list contains the standard `require_*` factories

The 6 fail-closed tests:
- Default initial state of `dev_mode_allowed` is False (production-style)
- Unauthed request returns 503 in fail-closed mode
- 503 response includes a remedy hint pointing to the fix
- GETs also fail closed (consistent with POSTs)
- Re-enabling dev mode at runtime restores legacy behavior
- A configured authenticator overrides the dev-mode check (auth path runs)

All v4.15–v4.25 governance tests still pass (regression-clean).

---

## What v4.26.0 still does NOT include

The audit identified other fractures that are NOT closed by this PR.
These need their own dedicated changes with careful test design:

| Fracture | Why deferred |
|---|---|
| **F1** routers without `/api/` prefix bypass middleware | Architectural restructure; the route-coverage gate prevents new bypasses but doesn't move existing routes under `/api/`. The musia_auth wiring closes the practical gap (F1 + F16 combined; with auth wired, the bypass ceases to be a bypass). Moving prefixes is a separate cleanup. |
| **F2** budget UPSERT TOCTOU | Requires `UPDATE budgets SET spent = spent + $1 WHERE tenant_id = $2 AND spent + $1 <= max_cost RETURNING …` plus invalidating the in-memory cache. ~80 LoC + careful concurrency tests. Own PR. |
| **F3** audit chain `verify_chain` invalid after first prune | Needs `governance_audit_checkpoints` table + verifier change. Own PR. |
| **F4** audit chain forks per worker | Needs DB-side sequence + DB-side `previous_hash` chain. Multi-worker coordination is a design surface. Own PR. |
| **F8** MAF disconnect | This release makes the README explicit about the disconnect. Actually wiring PyO3 bindings is weeks of Rust work and a separate decision (build vs. mark-as-research). |
| **F9** webhook SSRF gaps + **F10** DNS rebinding | Unify `webhook_system._is_private_url` with `http_connector._is_private_host`; pin resolved IP across DNS lookups. Own PR. |
| **F11** per-process rate limiter + **F12** DB write ceiling | Needs Redis or DB-backed token bucket; needs connection pooling. Multi-replica work. |
| **F15** `HashChainStore` filesystem TOCTOU | Add `flock` or move to SQLite-backed chain. Own PR. |
| **JWT empty-claim** + **HTTPS-only `jwks_url`** + **`iat` validation** | Hardening on the JWT module itself. Own PR. |

---

## Audit response posture

The audit caught what my own v4.18 audit didn't: the **wiring step**
between the auth resolver and the bootstrap path. The MUSIA-layer
tests pass because each fixture explicitly configures auth — the
production-bootstrap path was never tested for "did we configure
the resolver?"

The route-coverage CI gate is the structural fix to that class of
miss. Going forward, any router added to `include_default_routers`
must either be `/api/`-prefixed or carry a `Depends(require_*)`
declaration, and the test will refuse a PR that doesn't.

The audit is ongoing (Part 4 is open: Φ_gov semantics, agent execution
path, MCP surface). v4.27.0+ will address the F2/F3/F4/F15-class
fractures one at a time.

---

## Honest assessment

This is the most consequential release of the v4.x line. Pre-v4.26,
my "production-ready" framing was wrong because the most foundational
authorization invariant — "MUSIA endpoints require authentication"
— wasn't enforced in the deployed surface. The unit tests passed,
the audit passed, the CI was green. None of that mattered because
production runtime resolution short-circuited to wildcard.

The fix is small (~150 LoC source + ~250 LoC tests). The fix being
small makes the bug worse: this should have been caught in code review
of v4.5.0, in the v4.18 audit I ran, in any of the seven minor releases
shipped on top. It wasn't, until an external auditor ran the
"who-calls-this" check that mine didn't.

**We recommend:**
- Upgrade in place. If you're in `pilot`/`production` env, expect 503s
  from MUSIA endpoints on first deploy — this is the system telling
  you the bug existed and is now visible. The fix is automatic via
  the `bootstrap_server_lifecycle` wiring; no operator action needed.
- If you've been running with `MULLU_ENV=staging` or any non-canonical
  value, consider this a wake-up call to read F5 carefully: the HTTP
  middleware also fails open in that case.
- Read the audit reports if you can. Independent eyes catch the
  wiring-step bugs that internal tests can't.
