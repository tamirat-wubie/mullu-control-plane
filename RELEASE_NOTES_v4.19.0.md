# Mullu Platform v4.19.0 — RSA + JWKS for JWT Authentication

**Release date:** TBD
**Codename:** Keys
**Migration required:** No (additive — HS* paths unchanged; RS* is opt-in)

---

## What this release is

Closes a long-standing production gap: pre-v4.19 the JWT authenticator
([`mcoi/mcoi_runtime/core/jwt_auth.py`](mullu-control-plane/mcoi/mcoi_runtime/core/jwt_auth.py))
supported HS256/384/512 only. Real OIDC providers (Auth0, Okta, Azure
AD, Keycloak, Google) sign with RSA and distribute public keys via a
JWKS endpoint. Without RSA support, integration with those providers
required a sidecar token-translator or a forked authenticator. v4.19
ships native support.

This was deferred since v4.5 because the `cryptography` library wasn't
yet wired through. The dependency was already declared as the
`encryption` extra in `pyproject.toml`; v4.19 just lights it up.

---

## What is new in v4.19.0

### RS256 / RS384 / RS512

`OIDCConfig.allowed_algorithms` now accepts `RS256`, `RS384`, `RS512`
in addition to the existing HS variants. Verification uses
PKCS#1 v1.5 padding (the standard for OIDC) with the matching SHA hash.

```python
from mcoi_runtime.core.jwt_auth import OIDCConfig, JWTAuthenticator

cfg = OIDCConfig(
    issuer="https://your-tenant.auth0.com/",
    audience="mullu-api",
    public_keys={"kid-1": pem_public_key_bytes},
    allowed_algorithms=frozenset({"RS256"}),
)
auth = JWTAuthenticator(cfg)
result = auth.validate(token)
```

### JWKS-based key resolution

For deployments that rotate keys, `OIDCConfig.jwks_url` lets the
authenticator fetch the JWKS document on demand. The `JWKSFetcher` class:

- Caches keys for `jwks_cache_ttl_seconds` (default: 1 hour)
- Refreshes on cache miss for an unknown `kid` (handles steady-state rotation)
- Rate-limits unknown-kid refreshes to one per 5 seconds (bounds storms from bad-kid token floods)
- Keeps stale cache on network failure (don't reject all tokens because the JWKS endpoint is briefly down)
- Skips non-RSA keys silently (interoperates with mixed-content JWKS)
- Thread-safe (RLock on cache mutations)

```python
cfg = OIDCConfig(
    issuer="https://your-tenant.auth0.com/",
    audience="mullu-api",
    jwks_url="https://your-tenant.auth0.com/.well-known/jwks.json",
    allowed_algorithms=frozenset({"RS256"}),
    jwks_cache_ttl_seconds=3600,
)
auth = JWTAuthenticator(cfg)
```

A custom fetcher can be injected for tests, certificate pinning, or a
circuit breaker around your HTTP client:

```python
from mcoi_runtime.core.jwt_auth import JWKSFetcher
fetcher = JWKSFetcher(
    "https://your-tenant.auth0.com/.well-known/jwks.json",
    cache_ttl_seconds=900,
    fetcher=my_governed_https_client,
)
auth = JWTAuthenticator(cfg, jwks_fetcher=fetcher)
```

### Mixed-mode authenticators

A single `OIDCConfig` may allow HS* AND RS* simultaneously, useful
during rolling cutover from a legacy HMAC-signed system to OIDC:

```python
cfg = OIDCConfig(
    issuer="...", audience="...",
    signing_key=b"legacy-hmac-secret",       # HS path
    public_keys={"k1": pem_bytes},           # RS path
    allowed_algorithms=frozenset({"HS256", "RS256"}),
)
```

Algorithm-confusion attacks remain blocked: a token with `alg: HS256`
goes through `_verify_hmac`; a token with `alg: RS256` goes through
`_verify_rsa`. The two paths never share a key.

### Algorithm-confusion guard preserved

Cross-family alg-confusion is explicitly tested:

- HS256-signed token + RS-only auth → rejected (`algorithm not allowed`)
- RS256 token signed with the wrong private key → rejected (`signature verification failed`)
- RS256 token without `kid` → rejected (`RSA token missing kid in header`)
- RS256 token with unknown `kid` → rejected (`signing key not found`)
- `alg: none` → still rejected (existing v3 behavior preserved)

### Static public keys vs JWKS — exclusive

`public_keys` and `jwks_url` cannot both be set. Use static keys for
air-gapped deployments and tests; use JWKS for production deployments
that rotate. `__post_init__` raises if both are provided.

### Lazy `cryptography` import

The HS-only path doesn't need the `cryptography` extra. v4.19 imports
`cryptography` lazily inside the RSA helpers — configs that don't
allow RS* algs continue to work without the extra installed. If RSA
is requested without `cryptography`:

```
RuntimeError: RS* algorithms require the 'cryptography' package;
install via mcoi-runtime[encryption]
```

This is a deliberate "fail at first RSA use" semantic so deployments
can't accidentally ship an RSA-allowed config without the dependency.

---

## Test counts

| Suite                                    | v4.18.0 | v4.19.0 |
| ---------------------------------------- | ------- | ------- |
| jwt_auth tests (existing HS-only)        | 46      | 46      |
| RSA + JWKS tests (new)                   | n/a     | 22      |

The 22 new tests in [`test_v4_19_jwks_rsa.py`](mullu-control-plane/mcoi/tests/test_v4_19_jwks_rsa.py) cover:

**OIDCConfig validation (6)**
- RS256 + static public_keys accepted
- RS256 + jwks_url accepted
- RS256 without keys/jwks → ValueError
- public_keys + jwks_url mutually exclusive
- Mixed HS+RS: requires both signing_key and keys
- jwks_cache_ttl_seconds must be positive

**RSA round-trip + rejection (8)**
- RS256/RS384/RS512 round-trip pass
- Token signed with wrong private key → reject
- Token with unknown kid → reject
- Token without kid → ValueError on create_token
- alg outside allowed list → reject (e.g., RS256 token, RS384-only auth)
- Cross-family alg-confusion (HS256 token vs RS-only auth) → reject

**Mixed mode (1)**
- HS256 and RS256 tokens both validated by same authenticator

**JWKSFetcher (5)**
- Caches keys (no re-fetch within TTL)
- Refreshes on unknown kid (handles rotation)
- Cache expires after TTL
- Network failure preserves stale cache (no wipe-on-error)
- Non-RSA keys skipped silently

**JWKS end-to-end (2)**
- RS256 token validated through fetcher path
- Token with unknown kid rejected even after JWKS refresh

Two pre-existing tests in `test_jwt_auth.py` (asserted "RS256 is unsupported") were updated to use `ES256` — same intent (genuinely-unsupported algorithm message format), still passes.

---

## Compatibility

- **All v4.18.x JWT auth code works unchanged.** Default `allowed_algorithms = {"HS256"}`; default `signing_key=b""` is now allowed only when no HS* algs are requested
- **One observable behavior change**: `OIDCConfig` constructor errors differently on missing keys. v4.18 raised "signing_key must not be empty" unconditionally; v4.19 only raises that when an HS* alg is allowed (which is still the default). Configs that were previously valid stay valid.
- The two `test_jwt_auth.py` tests updated (RS256 → ES256) are semantic-equivalent — they still test that an unsupported algorithm raises with a bounded error
- `cryptography>=41.0` is still an optional extra (install via `pip install mcoi-runtime[encryption]`). HS-only deployments don't need it.

---

## Production deployment guidance

### Migrating from HS256 to OIDC RS256

Typical rolling cutover:

1. **Phase 1:** Deploy v4.19 with mixed-mode config:
   ```python
   allowed_algorithms=frozenset({"HS256", "RS256"})
   signing_key=b"<existing-hmac-secret>"
   jwks_url="https://provider/.well-known/jwks.json"
   ```
2. **Phase 2:** Issue new tokens via OIDC (RS256). Old HS256 tokens still work.
3. **Phase 3:** Wait for HS256 tokens to expire (typically 1–24 hours with `ttl_seconds`).
4. **Phase 4:** Tighten config to RS256 only:
   ```python
   allowed_algorithms=frozenset({"RS256"})
   signing_key=b""  # no longer needed
   ```

### JWKS endpoint hardening

The default fetcher (`urllib`) is intentionally minimal. For
production, inject a custom fetcher with:

- Certificate pinning to the OIDC provider
- Retry with exponential backoff
- Circuit breaker on repeated failures
- Outbound proxy support if the runtime is behind one

```python
from mcoi_runtime.core.jwt_auth import JWKSFetcher
fetcher = JWKSFetcher(jwks_url, fetcher=my_pinned_https_client)
auth = JWTAuthenticator(cfg, jwks_fetcher=fetcher)
```

### Cache TTL tuning

- **Stable keys (rotated quarterly+):** `jwks_cache_ttl_seconds=86400` (1 day) — minimizes JWKS endpoint load
- **Frequent rotation (daily or more):** `jwks_cache_ttl_seconds=3600` (default, 1 hour)
- **Test environment:** any value — use `force_refresh()` to invalidate manually

The unknown-kid refresh is rate-limited at 5 seconds regardless of TTL, so a flood of bad-kid tokens cannot DoS the JWKS endpoint.

---

## What v4.19.0 still does NOT include

- **ES256 / ES384 / ES512 (ECDSA)** — Some OIDC providers default to
  ECDSA; we don't support it yet. Adding it is straightforward (mirror
  the RS path with `ec.ECDSA(hash)` instead of `padding.PKCS1v15()`)
  but no current customer has asked. Future workstream.
- **PS256 / PS384 / PS512 (RSA-PSS)** — Same shape as RS but with PSS
  padding. Similar to ES — implementable, no demand yet.
- **Encrypted JWTs (JWE)** — We verify signed tokens (JWS); we don't
  decrypt encrypted tokens (JWE). OIDC providers rarely use JWE.
- **JWKS HTTPS certificate pinning by default** — The default `urllib`
  fetcher uses system trust. Production deployments should inject a
  pinned client (see deployment guidance above).
- **Distributed JWKS cache** — Each process maintains its own cache.
  At fleet scale, a Redis-backed cache could deduplicate JWKS fetches
  across processes; not in scope for v4.19.

---

## Cumulative MUSIA progress

```
v4.0.0   substrate (Mfidel + Tier 1)
v4.1.0   full 25 constructs + cascade + Φ_gov + cognition + UCJA
v4.2.0   HTTP surface + governed writes + business_process adapter
...
v4.18.0  end-to-end audit + bounded-state hardening
v4.19.0  RSA + JWKS for JWT authentication (closes v4.5 deferred item)
```

47,800+ MUSIA tests + 46 HS-only JWT tests + 22 new RSA/JWKS tests; OIDC-ready for Auth0, Okta, Azure AD, Keycloak, Google, and any other RS256 provider.

---

## Honest assessment

v4.19 is small (~280 lines of source + 380 lines of tests including
fixtures). The smallness is the same story as previous releases —
the existing `JWTAuthenticator` was designed with `_verify_hmac` already
isolated, so adding `_verify_rsa` next to it didn't require structural
changes. The `JWKSFetcher` is a clean stand-alone class with an
injectable HTTP fetcher; tests use a stub function and never hit the
network.

What it is not, yet: full OIDC discovery. Real OIDC clients fetch
`.well-known/openid-configuration` and discover the `jwks_uri`,
`token_endpoint`, and `userinfo_endpoint` automatically. We require the
operator to pre-populate `jwks_url` directly. Discovery is a clean
addition for v4.20 if anyone needs it.

**We recommend:**
- Upgrade in place. v4.19.0 is additive; HS-only deployments see no change.
- Plan an HS256 → RS256 migration if you're on legacy HMAC tokens. Use mixed-mode allowed_algorithms during the cutover window.
- For production OIDC integration, inject a pinned HTTPS client into `JWKSFetcher` rather than relying on default `urllib`.
- Keep `cryptography>=41.0` in your install only if you actually use RS* — HS-only deployments stay zero-extra-dep.

---

## Contributors

Same single architect, same Mullusi project. v4.19 closes the v4.5
deferred "JWKS-with-RSA" item, fourteen minor releases later.
