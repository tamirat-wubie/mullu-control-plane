# Mullu Platform v4.5.0 — MUSIA Runtime (Hardening)

**Release date:** TBD
**Codename:** Hardening
**Migration required:** No (additive — dev mode preserves v4.4 behavior)

---

## What this release is

Three production hardening features land together: auto-snapshot-on-write
(closes the v4.4 gap of "explicit save calls only"), JWT auth (parallel
to API-key, lets deployments migrate auth schemes), and scope enforcement
(read/write/admin separation per endpoint).

Each is a structural step toward a deployable service: persistent state
that doesn't require write-path discipline, auth flexibility for OIDC-style
deployments, and least-privilege enforcement at the API surface.

---

## What is new in v4.5.0

### Auto-snapshot-on-write

Opt-in, off by default. With `configure_persistence(dir, auto_snapshot=True)`,
every successful write through `/constructs/*` triggers `snapshot_tenant`
on the same tenant. Cross-tenant writes only persist their own tenant.

```python
configure_persistence("/var/lib/mullu/musia", auto_snapshot=True)
# Now POST /constructs/state writes both in-memory AND to disk
```

Save failures are silent on the write path: a successful in-memory write
must not roll back because disk is full. Production wiring should monitor
backend health separately.

### JWT auth integration

[musia_auth.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_auth.py) now supports two authenticators in priority order:

1. `APIKeyManager` (since v4.3.1) — raw API key
2. `JWTAuthenticator` (v4.5.0) — signed JWT

```python
from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    configure_musia_jwt,
)
from mcoi_runtime.core.api_key_auth import APIKeyManager
from mcoi_runtime.core.jwt_auth import JWTAuthenticator, OIDCConfig

configure_musia_auth(APIKeyManager())
configure_musia_jwt(JWTAuthenticator(OIDCConfig(
    issuer="https://accounts.example.com",
    audience="musia",
    signing_key=os.environ["JWT_HMAC_SECRET"].encode(),
)))
```

When both are configured, API-keys are tried first (cheaper validation
— single hashtable lookup), JWTs are the fallback. A deployment can run
both simultaneously during a migration without a flag day.

### Scope enforcement

Three scopes now mapped onto the MUSIA API surface:

| Scope          | Endpoints                                                |
| -------------- | -------------------------------------------------------- |
| `musia.read`   | `GET /constructs`, `GET /constructs/{id}`, `GET /constructs/{id}/dependents`, `GET /cognition/tension`, `GET /cognition/symbol-field` |
| `musia.write`  | `POST /constructs/*`, `DELETE /constructs/{id}`, `POST /cognition/run` |
| `musia.admin`  | All `/musia/tenants/*` endpoints (list, get, delete, snapshot, load) |
| `*` (wildcard) | Grants all of the above                                  |

Scopes are enforced at the dependency layer. The auth context flows from
`resolve_musia_auth → require_scope(...) → handler` via FastAPI's Depends
chain. **Auth context is passed by return value, not ContextVar**, because
FastAPI evaluates each Depends in its own task context (an early
implementation that used ContextVar broke between resolver and scope
check).

The `/ucja/*` and `/mfidel/*` endpoints are not scope-gated — they are
stateless and computational, with no per-tenant resources to protect.

---

## What changed structurally

### Auth context as a value, not a side effect

The first attempt at scope enforcement used a `ContextVar[MusiaAuthContext]`
written by the resolver and read by `require_scope`. Tests revealed the
ContextVar was empty by the time the scope check ran. FastAPI runs each
`Depends` in its own task context (via `asyncio.create_task` or equivalent),
which isolates ContextVar state.

The fix: have `resolve_musia_auth` return the full `MusiaAuthContext`,
and have `require_scope` depend on it directly. Each handler that needs
the tenant_id uses `Depends(require_X)`; each handler that just needs
authentication (no scope) uses `Depends(resolve_musia_tenant)` which is
a thin wrapper that pulls `tenant_id` from the same context.

This is recorded here because it's the kind of subtle dependency-graph
gotcha that only surfaces in tests, and the lesson generalizes: **don't
use ContextVar for FastAPI dependency-chain communication**.

### Dev mode treats scopes as wildcard

When no auth is configured (dev mode), `resolve_musia_auth` returns a
context with `scopes=frozenset({"*"})`. Scope checks become no-ops. This
preserves v4.4 dev behavior: existing tests that POST without auth keep
working.

---

## Test counts

| Suite                                    | v4.4.0  | v4.5.0  |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 416     | 435     |
| Hardening tests (new)                    | n/a     | 19      |

The 19 new tests cover:
- Auto-snapshot writes after create + delete + per-tenant isolation
- Auto-snapshot disabled does not write
- Auto-snapshot save-failure does not roll back the in-memory write
- JWT valid token authenticates with tenant + scopes from claims
- JWT invalid signature / expired / wrong issuer / missing tenant claim → 401
- JWT spoofing X-Tenant-ID → 403
- API-key + JWT both configured: API-key takes priority for matching keys, JWT for unrecognized
- Read-only key can GET but cannot POST (403 with `musia.write` named)
- Write key cannot access admin endpoints
- Admin key can access admin endpoints
- Wildcard `*` scope passes everything
- Dev mode bypasses scope enforcement
- 403 detail names subject + lists granted scopes (so the caller can debug)

Doc/code consistency check passes.

---

## Compatibility

- All v4.4.0 endpoints unchanged in URL or shape
- Default behavior in v4.5.0 is dev mode — identical to v4.4.0
- Existing tests (97 across `test_routers_musia`, `test_multi_tenant`, `test_musia_auth`, `test_persistence`) all pass without modification
- `_REGISTRY` backward-compat shim preserved
- Library API unchanged

---

## Production deployment guidance

```python
# Startup, in order:

# 1. Auth (pick one or both)
configure_musia_auth(api_key_manager)
configure_musia_jwt(jwt_authenticator)

# 2. Persistence with auto-snapshot
configure_persistence("/var/lib/mullu/musia", auto_snapshot=True)
loaded_tenants = STORE.load_all()

# 3. Re-install per-tenant Φ_agent filters (still not persisted)
for tid, filter_obj in your_filter_config.items():
    install_phi_agent_filter(filter_obj, tenant_id=tid)
```

Provision API keys with explicit scopes (not wildcard) for least-privilege
deployments:

```python
api_key_manager.create_key(
    tenant_id="acme-corp",
    scopes=frozenset({"musia.read", "musia.write"}),  # no admin
)
```

For JWT: claim `tenant_id` in the token payload, claim `scope` as a
space-separated string (or array). The `scope_claim` and `tenant_claim`
names are configurable via `OIDCConfig`.

---

## What v4.5.0 still does NOT include

- **Multi-process backend** — `FileBackedPersistence` is single-process. S3/postgres backends slot into the same interface.
- **Tenant onboarding/quotas/rate limits**
- **Domain adapters scoped per tenant** (Python `run_with_ucja()` is still tenant-naive)
- **Φ_gov ↔ existing `governance_guard.py`** integration
- **More domain adapters** (`scientific_research`, `manufacturing`, `healthcare`, `education`)
- **Rust port**
- **Bulk proof migration tool binary**
- **JWKS-based JWT key rotation** — `OIDCConfig.signing_key` is a single symmetric secret; production might want JWKS or asymmetric keys

---

## Honest assessment

v4.5.0 is a hardening release. No new conceptual ground; three
production prerequisites that the v4.4 release notes called out as
gaps. The codebase is now closer to "deployable" than at any prior point:
multi-tenant + auth + persistence + scope enforcement all working
together end to end.

What it is not, yet: validated under load. The framework's tests cover
correctness, not throughput. Auto-snapshot in particular adds a disk
write per governed write — fine for write rates measured in
ops/second/tenant, problematic at higher rates. A deployment running
hot should benchmark and consider a periodic-flush pattern instead.

**We recommend:**
- Upgrade in place. v4.5.0 is additive; default behavior unchanged.
- Provision keys with explicit scopes; reserve `*` for admin tooling.
- Enable auto-snapshot in dev/staging first; benchmark before enabling in production at high write rates.
- For OIDC deployments, prefer JWT over API-key (tokens have built-in
  expiry; keys don't unless you set `ttl_seconds`).

---

## Contributors

Same single architect, same Mullusi project. v4.5.0 closes three
specific gaps without adding scope creep.
