# Mullu Platform v4.3.1 — MUSIA Runtime (Auth-Derived Tenant Resolution)

**Release date:** TBD
**Codename:** Bearer
**Migration required:** No (additive — dev mode preserves v4.3.0 behavior)
**Severity:** Security patch (closes the v4.3.0 known gap)

---

## What this release is

v4.3.0 shipped multi-tenant isolation but trusted client-supplied
`X-Tenant-ID` headers. v4.3.0's release notes called this out as a
must-fix-before-production gap.

v4.3.1 closes that gap. When an `APIKeyManager` is configured, the
authenticated tenant from `Authorization: Bearer <api-key>` is
authoritative. A client cannot impersonate another tenant by setting
`X-Tenant-ID`, and any attempt is rejected with HTTP 403 and logged.

When no `APIKeyManager` is configured (dev mode), v4.3.0 behavior is
preserved: `X-Tenant-ID` is accepted as-is.

---

## What is new in v4.3.1

### `mcoi_runtime.app.routers.musia_auth`

New module: [musia_auth.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_auth.py).

- `configure_musia_auth(manager: APIKeyManager | None)` — install/uninstall
- `is_auth_configured() -> bool` — runtime check
- `resolve_musia_tenant(...)` — FastAPI dependency used by all MUSIA routers

### Two-mode tenant resolution

| Mode | Trigger | Behavior |
|------|---------|----------|
| Dev | `_AUTH_MANAGER is None` | `X-Tenant-ID` header trusted, defaults to `default` |
| Prod | `configure_musia_auth(manager)` called | `Authorization` required; auth-derived tenant authoritative; spoof attempts → 403 |

### Spoofing rejection

```
POST /constructs/state HTTP/1.1
Authorization: Bearer <key-bound-to-acme-corp>
X-Tenant-ID: foo-llc       ← spoofing attempt
{"configuration": {}}

403 Forbidden
{
  "detail": {
    "error": "X-Tenant-ID does not match authenticated tenant",
    "authenticated_tenant": "acme-corp",
    "claimed_tenant": "foo-llc"
  }
}
```

The mismatch is logged at WARNING level with both tenant IDs and the
key_id, so spoof attempts produce a forensic trail.

### MUSIA routers refactored to use the dependency

[constructs.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/constructs.py) and [cognition.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/cognition.py) replaced their per-route `Header` parameters with `Depends(resolve_musia_tenant)`. All 12 endpoints now route through the same auth-aware resolver.

---

## Test counts

| Suite                                    | v4.3.0  | v4.3.1  |
| ---------------------------------------- | ------- | ------- |
| MCOI Python tests (existing, untouched)  | 44,500+ | 44,500+ |
| MUSIA-specific suites                    | 365     | 378     |
| MUSIA auth tests (new)                   | n/a     | 13      |

Doc/code consistency check passes.

The 13 new auth tests verify:
- `configure_musia_auth(None)` toggle
- Dev-mode default tenant when no header
- Dev-mode arbitrary X-Tenant-ID accepted
- Auth mode missing/malformed/invalid Authorization → 401
- Auth mode authenticated request uses key's tenant
- Auth mode matching X-Tenant-ID is accepted (idempotent)
- Auth mode spoofing X-Tenant-ID rejected with 403
- Spoof attempt does not create a construct in either tenant
- Two valid keys → two tenants → fully isolated
- Revoked key → 401
- Cognition endpoints scope to authenticated tenant

---

## Compatibility

- All v4.3.0 endpoints unchanged in URL or shape
- Default behavior in v4.3.1 is dev mode (no auth) — identical to v4.3.0
- Existing tests run against the same headers
- `_REGISTRY` backward-compat shim preserved
- Library API (Python, no HTTP) unchanged

---

## Production deployment guidance

To switch to auth mode, install your `APIKeyManager` once at startup:

```python
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.core.api_key_auth import APIKeyManager

manager = APIKeyManager()
# … create keys for each tenant via manager.create_key(tenant_id, scopes) …
configure_musia_auth(manager)
```

Then every MUSIA endpoint will require `Authorization: Bearer <api-key>`.
The tenant will be derived from the authenticated key. Clients that
include `X-Tenant-ID` may continue to do so (it is ignored if it matches,
rejected if it doesn't), so existing client code does not break.

---

## What v4.3.1 still does NOT include

Remaining items from the v4.3.0 list that did not land in this patch:

- **JWT auth** — only API-key auth is wired; JWT integration parallels but isn't done
- **Per-route scope enforcement** — auth is required, but `required_scope` isn't checked per endpoint (the framework supports it; production wiring needs to declare scopes)
- **Persistent tenant state** — store is still in-memory
- **Tenant onboarding/quotas/rate limits**
- **Domain adapters scoped per tenant**
- **Φ_gov ↔ existing `governance_guard.py`**
- **More domain adapters**
- **Rust port**
- **Bulk proof migration tool binary**

---

## Honest assessment

v4.3.1 is the smallest possible release that addresses the security gap
v4.3.0 left open. It does one thing: when auth is configured, the
authenticated tenant is authoritative. Everything else from v4.3.0 is
preserved exactly.

This is the right shape for a security patch. The next round of work
goes back to feature breadth: more domain adapters, persistence, scope
enforcement, JWT.

**We recommend:**
- Upgrade in place. v4.3.1 is additive; dev mode preserves v4.3.0 behavior.
- Before going to production, call `configure_musia_auth(manager)` and
  provision API keys per tenant.
- Clients can continue to include `X-Tenant-ID` (it's ignored when
  matching) — no client-side migration required.

---

## Contributors

Same single architect, same Mullusi project. v4.3.1 is the clearest
example so far of the discipline the audit work surfaced earlier:
shipping a release that explicitly documented its known gaps, then
shipping the fix as a focused follow-up rather than bundling it with
unrelated work.
