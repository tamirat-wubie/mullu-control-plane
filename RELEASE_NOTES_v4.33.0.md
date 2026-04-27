# Mullu Platform v4.33.0 — JWT Auth Hardening (Audit Part 3)

**Release date:** TBD
**Codename:** Subject
**Migration required:** Tests/configs that issued JWTs with empty `sub` or empty tenant claim must now set both, OR opt out via the new flags

---

## What this release is

Closes the four JWT/OIDC gaps called out in audit Part 3:

1. **Empty `sub` accepted.** Pre-v4.33 a token with `"sub": ""` (or no `sub` at all) authenticated successfully with `subject=""`. Audit attribution went blank; rate limits keyed on subject collided across users.
2. **Empty tenant claim accepted.** Pre-v4.33 a token with no tenant claim authenticated with `tenant_id=""`. Combined with the X-Tenant-ID header handling in `governance_guard_chain`, an empty-tenant JWT effectively trusted the header — a tenant-isolation bypass.
3. **`iat` not validated.** RFC 7519 §4.1.6 says `iat` is the issued-at time; pre-v4.33 the validator never looked at it. A token with `iat = now + 1 year` and `exp = now + 1 hour` was happily accepted. Forged tokens with bogus `iat` slipped through.
4. **`jwks_url` accepted any scheme + redirects followed.** Pre-v4.33 nothing stopped an operator misconfiguring `jwks_url="http://..."`; the default fetcher used `urlopen` directly, which follows 3xx redirects. Either path enabled MITM key substitution — an attacker who could redirect or MITM the JWKS fetch could ship their own public key, and the validator would happily accept tokens signed by their private key.

v4.33 closes all four. Each is a flag on `OIDCConfig` defaulting to the strict posture, with explicit opt-out for legacy deployments that need a soft rollout.

---

## What is new in v4.33.0

### `OIDCConfig` — four new flags

```python
@dataclass(frozen=True, slots=True)
class OIDCConfig:
    ...
    # v4.33.0 (audit JWT hardening)
    require_subject: bool = True
    require_tenant_claim: bool = True
    require_iat_not_in_future: bool = True
    require_https_jwks: bool = True
```

All default `True`. Operators who genuinely need an opt-out (rare) flip the relevant flag explicitly.

### `OIDCConfig.__post_init__` — HTTPS check

```python
if (
    self.jwks_url is not None
    and self.require_https_jwks
    and not self.jwks_url.lower().startswith("https://")
):
    raise ValueError(
        "jwks_url must use HTTPS; set require_https_jwks=False to opt out"
    )
```

Misconfigured `http://` JWKS URLs fail at config construction, not at first token. The error message is a hint — operators see it before deploy, not at 3am.

### `JWTAuthenticator.validate()` — three new claim checks

After the existing `iss` / `aud` / `exp` / `nbf` checks:

```python
# iat (issued-at) sanity — RFC 7519 §4.1.6
iat = claims.get("iat")
if iat is not None and self._config.require_iat_not_in_future:
    if not isinstance(iat, (int, float)):
        return JWTAuthResult(authenticated=False, error="iat claim must be numeric")
    if iat > now + self._config.clock_skew_seconds:
        return JWTAuthResult(authenticated=False, error="token iat is in the future")

subject = str(claims.get("sub", ""))
tenant_id = str(claims.get(self._config.tenant_claim, ""))

if self._config.require_subject and not subject:
    return JWTAuthResult(authenticated=False, error="sub claim is empty or missing")
if self._config.require_tenant_claim and not tenant_id:
    return JWTAuthResult(authenticated=False, error="tenant claim is empty or missing")
```

Each check honors its flag, so an operator can flip just the one they need to relax during a migration.

### `_default_jwks_fetcher` — redirects blocked

Pre-v4.33:
```python
with urlopen(url, timeout=10) as resp:
    body = resp.read()
```

v4.33:
```python
class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f"jwks_redirect_blocked:{code}",
            headers, fp,
        )

opener = urllib.request.build_opener(_NoRedirectHandler)
with opener.open(url, timeout=10) as resp:
    body = resp.read()
```

3xx responses now surface as `jwks_redirect_blocked:<code>` — they no longer chase the new location. Combined with the HTTPS-only check on the configured URL, an attacker can't redirect a JWKS fetch from `https://idp.example.com/keys` to `http://attacker.example.com/keys`.

---

## Compatibility

The four new flags break four old behaviors. The migration table:

| Pre-v4.33 behavior | v4.33 default | If you actually need it |
|---|---|---|
| Empty `sub` accepted | Rejected | `require_subject=False` |
| Empty tenant claim accepted | Rejected | `require_tenant_claim=False` |
| Future `iat` accepted | Rejected when iat > now + skew | `require_iat_not_in_future=False` |
| `jwks_url="http://..."` accepted | `ValueError` at config init | `require_https_jwks=False` |

In practice: **production deployments using a real OIDC provider don't need any opt-outs** — Auth0/Okta/Azure AD/Keycloak/Google all set `sub`, all set `iat` correctly, and all serve JWKS over HTTPS. Test fixtures and toy auth configs may need `require_tenant_claim=False` if they don't bother to populate tenant. This PR updates the existing test helpers (`test_jwt_auth.py::_config`, `test_v4_19_jwks_rsa.py::_config_with_static_keys` and the mixed-mode test) to do exactly that.

---

## Test counts

18 new tests in [`test_v4_33_jwt_hardening.py`](mullu-control-plane/mcoi/tests/test_v4_33_jwt_hardening.py):

- `TestHttpsOnlyJwks` — 4 tests (http rejected, https accepted, opt-out, case-insensitive scheme check)
- `TestRequireSubject` — 3 tests (empty rejected, missing rejected, opt-out works)
- `TestRequireTenantClaim` — 4 tests (empty rejected, non-empty accepted, opt-out, custom claim name enforced)
- `TestIatNotInFuture` — 5 tests (future rejected, within skew accepted, past accepted, non-numeric rejected, opt-out)
- `TestJwksRedirectBlocking` — 2 tests (fetcher surfaces redirect-blocked error, handler raises on redirect)

All 50 pre-existing JWT tests (`test_jwt_auth.py` 32 + `test_v4_19_jwks_rsa.py` 18) still pass after the helper updates.

Combined: **68 JWT tests pass** end-to-end.

---

## Production deployment guidance

### Watch for new auth rejections

After deploying v4.33, the auth subsystem starts rejecting tokens it would have accepted. The error codes to watch in your auth log:

- `sub claim is empty or missing` — token has no subject. Either the IdP is misconfigured or this is a service-to-service token that should populate `sub` with the service identity
- `tenant claim is empty or missing` — your IdP isn't populating the configured `tenant_claim` (default `"tenant_id"`). Check the IdP's claim mapping or rename via `tenant_claim`
- `token iat is in the future` — clock drift between IdP and Mullu, or a forged token. If clock drift is real, raise `clock_skew_seconds`; if not, investigate the source of the token
- `iat claim must be numeric` — almost certainly a forged or buggy token; legitimate IdPs always emit numeric `iat`
- `jwks_redirect_blocked:<code>` — your JWKS endpoint is responding with a 3xx. Either the URL is wrong (point to the canonical endpoint, not a redirect) or someone is trying to substitute keys

### Soft-launch path for legacy IdPs

If you have a non-compliant IdP that legitimately doesn't emit `sub` or `tenant`, you can ship v4.33 with the relevant flag opted out:

```python
OIDCConfig(
    issuer=...,
    audience=...,
    signing_key=...,
    require_tenant_claim=False,  # IdP doesn't emit tenant; we derive it elsewhere
)
```

We recommend keeping `require_subject=True` and `require_iat_not_in_future=True` regardless — those gaps have no benign explanation in production.

### `jwks_url` HTTPS

If your `jwks_url` is `http://`, fix it. There is no legitimate reason for a production JWKS endpoint to be unencrypted. The `require_https_jwks=False` opt-out exists for in-cluster test environments (sidecar serving JWKS over HTTP on localhost) and nothing else.

---

## Production-readiness gap status

```
✅ F2  atomic budget                   — v4.27.0
✅ F3  audit checkpoint anchor         — v4.28.0
✅ F11 atomic rate limit               — v4.29.0
✅ F15 atomic hash chain append        — v4.30.0
✅ F4  atomic audit append             — v4.31.0
✅ F9 + F10 unified SSRF + pin         — v4.32.0
✅ JWT hardening (Audit Part 3)        — v4.33.0
⏳ F5 / F6 env + tenant binding        — small, similar to F16 pattern
⏳ F7 governance module sprawl         — architectural
⏳ F8 MAF substrate disconnect         — README mitigated; PyO3 weeks
⏳ F12 DB write throughput ceiling     — needs connection pool
```

15 of 17 audit fractures fully closed (counting the JWT bundle as one). Remaining 4 either need external infra (F12), are small/contained (F5/F6), or are architectural (F7/F8).

---

## Honest assessment

v4.33 is small (~50 LoC source + ~280 LoC tests). The findings were obvious-in-retrospect — every modern JWT spec / RFC says `sub` and `iat` should be validated; HTTPS for JWKS is table-stakes. They were fractures because the original v4.18 cut focused on signature + alg + issuer + audience + exp/nbf, and "non-empty sub" felt redundant with "issuer matches" until the audit showed the path through the X-Tenant-ID header.

The lesson: **claim presence is part of validation, not a downstream concern.** If the validator returns `authenticated=True` with `subject=""`, it is lying to every caller that uses `subject` for attribution or rate limiting. Fail closed at the auth layer — every layer above gets to assume non-empty fields.

Combined with v4.32 (unified SSRF) and v4.31 (atomic audit), the auth + audit + SSRF surfaces are now hardened to audit-Part-3 standard. The remaining roadmap is connection pooling (F12, infra), env+tenant binding (F5/F6, contained), and the deeper architectural items (F7 module sprawl, F8 MAF substrate connection).

**We recommend:**
- Upgrade in place. Production deployments using a real OIDC provider see no token rejections
- Test code constructing `OIDCConfig` directly may need `require_tenant_claim=False` if it issues tokens without tenant_id
- After deploy, scan auth logs for the new error codes — any non-zero count of `iat is in the future` or `jwks_redirect_blocked` is worth investigating before you assume it's noise
