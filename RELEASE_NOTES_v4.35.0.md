# Mullu Platform v4.35.0 — Env + Tenant Binding (Audit F5 + F6)

**Release date:** TBD
**Codename:** Bind
**Migration required:** Production deployments should set `MULLU_ENV` explicitly and add `MULLU_ENV_REQUIRED=true` to fail-closed on misconfiguration

---

## What this release is

Closes audit fractures **F5** (env binding) and **F6** (tenant binding). Both are small, surgical defense-in-depth fixes on paths that were "almost right" but had a fail-open corner.

### F5 — env binding silently defaulted to `local_dev`

Pre-v4.35 every site that read `MULLU_ENV` did `runtime_env.get("MULLU_ENV", "local_dev")` directly. An operator deploying a container without setting the env var silently got the most permissive policies — local_dev shell execution, looser tenant validation, X-Tenant-ID trust, weakened policy posture. The deployment looked healthy because routes returned 200, but the policy was dev mode.

### F6 — tenant mismatch only checked when `require_auth=True`

The JWT and API-key guards rejected header/JWT tenant mismatch only when constructed with `require_auth=True`. With `require_auth=False` (the default), a JWT carrying tenant=A combined with header `X-Tenant-ID: B` silently overwrote `ctx[tenant_id]` to A. Downstream guards saw the corrected value, but any code branching on `require_auth` lost the spoof signal — and the moment-before state was observable to attribution + logging that ran before the JWT guard.

---

## What is new in v4.35.0

### `mcoi_runtime/app/server_context.py` — `resolve_env`

```python
KNOWN_ENVS = frozenset({"local_dev", "test", "pilot", "production"})

class EnvBindingError(RuntimeError):
    """Raised when MULLU_ENV is unset and MULLU_ENV_REQUIRED is set."""

def resolve_env(runtime_env: Mapping[str, str]) -> str:
    raw = runtime_env.get("MULLU_ENV", "").strip()
    required = runtime_env.get("MULLU_ENV_REQUIRED", "").strip().lower() in _TRUTHY
    if not raw:
        if required:
            raise EnvBindingError(...)
        _log.critical("MULLU_ENV is not set; falling back to 'local_dev'. ...")
        return "local_dev"
    if raw not in KNOWN_ENVS:
        _log.error("MULLU_ENV=%r is not a known environment ...", raw)
    return raw
```

Behavior table:

| `MULLU_ENV` | `MULLU_ENV_REQUIRED` | Result |
|---|---|---|
| `production` | any | returns `"production"` |
| `local_dev` | any | returns `"local_dev"` |
| unset / empty | unset / falsy | logs CRITICAL, returns `"local_dev"` (legacy) |
| unset / empty | `true` / `1` / `yes` / `on` | raises `EnvBindingError` |
| `wonderland` | any | logs ERROR, returns `"wonderland"` (downstream falls to sandboxed) |

`server.py`'s bootstrap call now goes through `resolve_env(os.environ)` instead of `os.environ.get("MULLU_ENV", "local_dev")`. `bootstrap_server_context` does the same internally.

### `mcoi_runtime/core/governance_guard.py` — explicit-tenant mismatch check

Both `create_jwt_guard` and `create_api_key_guard` had:

```python
# pre-v4.35
if require_auth and request_tenant and request_tenant != result.tenant_id:
    return GuardResult(allowed=False, ..., reason="tenant mismatch")
```

v4.35 introduces `ctx["tenant_id_explicit"]` (set by middleware when the caller explicitly supplied a tenant via header or query) and uses it as an additional trigger:

```python
# v4.35
request_tenant_explicit = bool(ctx.get("tenant_id_explicit", False))
if (
    request_tenant
    and request_tenant != result.tenant_id
    and (require_auth or request_tenant_explicit)
):
    return GuardResult(allowed=False, ..., reason="tenant mismatch")
```

### `mcoi_runtime/app/middleware.py` — sets `tenant_id_explicit`

```python
explicit_tenant = False
tenant_id = request.query_params.get("tenant_id", "")
if tenant_id:
    explicit_tenant = True
else:
    header_tenant = request.headers.get("x-tenant-id", "")
    if header_tenant:
        tenant_id = header_tenant
        explicit_tenant = True
    else:
        tenant_id = "system"   # implicit fallback (legacy)

context = {
    "tenant_id": tenant_id,
    "tenant_id_explicit": explicit_tenant,
    ...
}
```

The "system" implicit fallback is preserved for backward compat — but it's now distinguishable from a real header value, so the spoof check fires only on real (explicit) mismatches.

---

## Compatibility

- **F5 is opt-in stricter.** Existing deployments that didn't set `MULLU_ENV` keep working (CRITICAL warning in logs). To gain fail-closed behavior, add `MULLU_ENV_REQUIRED=true` to your container manifest.
- **F6 is strictly tightening.** A request that explicitly supplies an `X-Tenant-ID` header that disagrees with the JWT or API-key tenant is now rejected with `tenant mismatch` even when the guard was constructed with `require_auth=False`. This was always an attack surface; v4.35 closes it. Implicit middleware defaults ("system") are not treated as explicit, so dev-mode requests without auth keep passing.
- The `require_auth=True` legacy strict path is unchanged for backward compat with callers that pre-date `tenant_id_explicit`.

---

## Test counts

27 new tests in [`test_v4_35_env_tenant_binding.py`](mullu-control-plane/mcoi/tests/test_v4_35_env_tenant_binding.py):

- `TestResolveEnv` — 17 tests (parametrized truthy/falsy variants, known/unknown values, REQUIRED flag, whitespace handling)
- `TestJwtGuardTenantBindingF6` — 4 tests (explicit mismatch rejected, implicit fallback passes, explicit match, legacy require_auth path)
- `TestApiKeyGuardTenantBindingF6` — 3 tests (same pattern for API-key guard)
- `TestMiddlewareTenantExplicit` — 3 tests (no-header → implicit, header → explicit, query → explicit)

Full mcoi suite: **48,617 passed, 26 skipped, 0 failures** (+27 over v4.33.0 baseline of 48,580).

---

## Production deployment guidance

### Add `MULLU_ENV_REQUIRED=true` to production manifests

```yaml
env:
  - MULLU_ENV: production
  - MULLU_ENV_REQUIRED: "true"
```

If somebody removes `MULLU_ENV` from the manifest by mistake, the platform now refuses to start instead of silently running with dev policies. The startup error is `EnvBindingError`.

### Watch for new auth log signals

After deploying v4.35, expect:

- `tenant mismatch` (403) — caller supplied `X-Tenant-ID: B` (or `?tenant_id=B`) on a request authenticated as tenant=A. Either the caller is buggy (cross-tenant API call from a logged-in session) or this is a spoofing attempt
- `MULLU_ENV is not set; falling back to 'local_dev'` (CRITICAL log) — operator forgot to set `MULLU_ENV`. In production this is a misconfiguration
- `MULLU_ENV=... is not a known environment` (ERROR log) — typo in deployment manifest. Downstream policies fall to sandboxed defaults
- `EnvBindingError` at boot — `MULLU_ENV_REQUIRED=true` is set but `MULLU_ENV` is missing. Boot refused

### Soft rollout for legacy clients

If you have legacy clients that send `X-Tenant-ID` for routing reasons but never match the authenticated tenant (rare), they will now get 403s. Either update the client to drop the header, or document that `X-Tenant-ID` is now strictly a tenant *assertion*, not routing metadata.

---

## Production-readiness gap status

```
✅ F2  atomic budget                   — v4.27.0
✅ F3  audit checkpoint anchor         — v4.28.0
✅ F11 atomic rate limit (tenant)      — v4.29.0
✅ F15 atomic hash chain append        — v4.30.0
✅ F4  atomic audit append             — v4.31.0
✅ F9 + F10 unified SSRF + pin         — v4.32.0
✅ JWT hardening (Audit Part 3)        — v4.33.0
✅ F11 atomic rate limit (identity)    — v4.34.0  (parallel track)
✅ F5 + F6 env + tenant binding        — v4.35.0  ← this PR
⏳ F7 governance module sprawl         — architectural
⏳ F8 MAF substrate disconnect         — README mitigated; PyO3 weeks
⏳ F12 DB write throughput ceiling     — needs connection pool
```

16 of 17 audit fractures fully closed. Remaining 3 are: F7 (architectural — module sprawl), F8 (MAF substrate connection — needs PyO3 work), F12 (DB connection pool — needs infra). Each is a multi-week effort, not a contained patch.

---

## Honest assessment

v4.35 is small (~80 LoC source + ~250 LoC tests). The findings were the kind of "almost right" that audits exist to catch:

- **F5** had `local_dev` as a default that *felt* sensible (fail-soft for dev) until you imagined a deploy without the env var (fail-open in prod)
- **F6** had `require_auth and ...` as a guard that *felt* defensive (only enforce mismatch in strict mode) until you realized the only path that exercises it is the path that already enforces the rest of the binding

The lesson: **the failure modes that audits surface are the ones where the "correct" behavior under expected configuration masks a fail-open under misconfiguration.** A deploy that always sets `MULLU_ENV=production` never sees F5; a deploy that always sets `require_auth=True` never sees F6. Fix both at the source so misconfiguration costs a hard error, not a silent permission grant.

**We recommend:**
- Upgrade in place. F5 is opt-in stricter; F6 is strict-only-when-mismatch. Production deployments using a real OIDC provider see no token rejections
- Add `MULLU_ENV_REQUIRED=true` to your production deployment manifests
- After deploy, scan for `tenant mismatch` error counts in your auth log — non-zero counts deserve investigation
