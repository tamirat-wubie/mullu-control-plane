# Mullu Platform v4.9.0 — MUSIA Runtime (JWT Rotation + Tenant Quotas)

**Release date:** TBD
**Codename:** Bound
**Migration required:** No (additive — single-authenticator JWT and unbounded quota are still defaults)

---

## What this release is

Two production hardening features:

1. **Multi-authenticator JWT** — `configure_musia_jwt()` now accepts a list of authenticators, enabling key rotation without downtime. During the rotation window, both old and new keys validate; afterwards, the old is removed.

2. **Per-tenant construct count quotas** — `TenantQuota.max_constructs` caps how many constructs a tenant can hold in its registry. Exceeded → HTTP 429 with structured detail naming the quota.

Both are opt-in. Default behavior is unchanged from v4.8.0: single-authenticator JWT (or none), unlimited construct count per tenant.

---

## What is new in v4.9.0

### `configure_musia_jwt(authenticators)` accepts a list

[musia_auth.py](mullu-control-plane/mcoi/mcoi_runtime/app/routers/musia_auth.py).

```python
from mcoi_runtime.app.routers.musia_auth import configure_musia_jwt
from mcoi_runtime.core.jwt_auth import JWTAuthenticator, OIDCConfig

# Old usage still works (back-compat)
configure_musia_jwt(JWTAuthenticator(cfg_v1))

# New: rotation
configure_musia_jwt([
    JWTAuthenticator(cfg_v1_old_key),  # accepting old tokens still in flight
    JWTAuthenticator(cfg_v2_new_key),  # accepting new tokens going forward
])

# After all old tokens have expired, drop the old authenticator
configure_musia_jwt([JWTAuthenticator(cfg_v2_new_key)])
```

Authenticators are tried in declared order. First match wins. A token signed by any active key passes; one signed by no active key fails with HTTP 401.

`configured_jwt_authenticators()` returns a copy of the current list for inspection.

### `TenantQuota` + HTTP enforcement

[registry_store.py](mullu-control-plane/mcoi/mcoi_runtime/substrate/registry_store.py) gains a `TenantQuota` dataclass and a `TenantState.check_quota_for_write()` method. The constructs router calls it before Φ_gov on every write.

Order of write-path checks (constructs.py):
1. **Quota** — HTTP 429 on violation (`{"error": "tenant quota exceeded", "reason": "...", "tenant_id": "..."}` + `Retry-After: 0` header)
2. **Φ_gov / Φ_agent** — HTTP 403 on rejection
3. Register the construct

Quota is checked first because "you're at capacity" is a clearer signal than "Φ_gov rejected for some reason."

### Quota HTTP endpoints

```
GET  /musia/tenants/{tenant_id}/quota   → QuotaSnapshot (admin scope)
PUT  /musia/tenants/{tenant_id}/quota   → set quota, returns updated snapshot
```

`QuotaSnapshot` shape:
```json
{
  "tenant_id": "acme-corp",
  "max_constructs": 10000,
  "current_constructs": 4321,
  "headroom": 5679
}
```

Setting `max_constructs` to `null` makes the quota unlimited. Setting it below the current count is permitted (no eviction); subsequent writes will 429 until the count drops below the new limit. `headroom` may be negative in this case.

PUT auto-creates the tenant state if absent — operators can pre-provision quotas before the tenant ever submits a write.

---

## What v4.9.0 still does NOT include

- **Sliding-window rate limits** — only lifetime construct count cap. Hourly/daily write rates need a time-windowed counter with TTL eviction; that's a separate workstream.
- **JWKS URL fetching** — multi-authenticator works for symmetric secret rotation; OIDC deployments wanting JWKS-with-RSA need to extend `JWTAuthenticator` to support RSA verification (separate workstream).
- **Quota enforcement on `/cognition/run` or `/domains/*/process`** — these endpoints don't grow the registry directly; the underlying writes (if any) are already gated.
- **Quota persistence across restarts** — `TenantQuota` lives on `TenantState` which is process-local. v4.4.0's persistence covers the construct graph but not the quota field. Production deployments that want durable quotas should set them at startup from external config.

---

## Test counts

| Suite                                    | v4.8.0  | v4.9.0  |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 566     | 585     |
| JWT rotation tests (new)                 | n/a     | 5       |
| Tenant quota tests (new)                 | n/a     | 14      |

The 5 JWT rotation tests cover:
- Single authenticator (back-compat)
- List of authenticators
- None disables JWT
- Both old and new accepted during rotation window
- After rotation, old token rejected
- First-matching authenticator wins

The 14 quota tests cover:
- Default unlimited
- Negative max_constructs rejected
- Zero blocks all writes
- At-limit blocks next write
- HTTP 429 with structured detail on violation
- Per-tenant isolation (one tenant's quota does not affect another)
- GET/PUT endpoint behavior
- Setting to unlimited via PUT
- Negative max via PUT rejected at Pydantic layer (422)
- Lowering quota below current count permitted, no eviction, blocks next write
- 404 on GET for unknown tenant
- PUT auto-creates tenant state

Doc/code consistency check passes.

---

## Compatibility

- All v4.8.0 endpoints unchanged
- `configure_musia_jwt(single_authenticator)` still accepted as in v4.5.0+
- Tenant default quota is unlimited; existing deployments see no change
- All v4.8.0 tests (549) still pass without modification

---

## Production deployment guidance

### JWT rotation procedure

1. Generate the new signing key.
2. Add a new `JWTAuthenticator(OIDCConfig(signing_key=new_key, ...))` to the existing list. Both old and new active.
3. Deploy. Existing tokens (signed with old key) continue to work; newly issued tokens use the new key.
4. Wait for the maximum token lifetime to elapse (typically 1 hour for short-lived OIDC tokens).
5. Remove the old authenticator from the list.
6. Deploy. Old tokens now reject; only new key is recognized.

### Quota provisioning

```python
from mcoi_runtime.substrate.registry_store import STORE, TenantQuota

# At startup, provision per-tenant quotas from external config
for tenant_id, max_constructs in your_quota_config.items():
    STORE.get_or_create(tenant_id).quota = TenantQuota(max_constructs=max_constructs)
```

Or via HTTP at runtime:

```bash
curl -X PUT https://api/musia/tenants/acme-corp/quota \
     -H "Authorization: Bearer <admin-key>" \
     -H "Content-Type: application/json" \
     -d '{"max_constructs": 10000}'
```

---

## Honest assessment

v4.9.0 is "production hardening continued." Each of the two features
addresses a specific deployment need: rotation lets OIDC keys roll
without flag days; quotas let multi-tenant deployments cap blast
radius per tenant.

What it is not, yet: full rate-limiting. A tenant with `max_constructs=10000`
who hits 10000 in one second will hit the 429 on the 10001th write;
they can also burst to 10000 writes in under a second if they're fast
enough. Real rate limits need a time-windowed counter; that work
remains.

**We recommend:**
- Upgrade in place. v4.9.0 is additive.
- Provision quotas at tenant onboarding time, not when problems surface.
- Plan rotation runbooks before they're urgent.

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
v4.9.0   JWT rotation + tenant quotas
```

585 MUSIA tests; 101 docs; six domains over HTTP; multi-tenant +
multi-auth-with-rotation + persistent + scope-enforced + quota-bounded.

---

## Contributors

Same single architect, same Mullusi project. v4.9.0 closes two specific
production gaps without scope creep.
