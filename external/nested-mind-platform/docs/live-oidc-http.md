# Live OIDC HTTPS discovery and JWKS refresh

v10 adds a live connector boundary for OIDC discovery:

```text
OidcDiscoveryConfig
  → LiveOidcRefreshRequest
  → HTTPS GET /.well-known/openid-configuration
  → validate issuer / algorithms
  → HTTPS GET jwks_uri
  → OidcJwksCacheEntry
  → LiveOidcRefreshReport
  → SQLite ledger
```

The kernel remains deterministic. Network I/O lives in `crates/mind-connectors`; the resulting evidence object is passed back into the API/store layer.

API:

```text
POST /system/oidc-verifier/refresh-live
```

Environment:

```bash
MIND_OIDC_ISSUER=https://issuer.example
MIND_OIDC_AUDIENCES=nested-mind-api
MIND_OIDC_ALLOWED_ALGORITHMS=RS256
MIND_OIDC_REFRESH_TTL_SECONDS=3600
```

CLI:

```bash
cargo run -p mind-cli -- oidc-live-refresh \
  https://issuer.example \
  nested-mind-api \
  RS256
```

The live refresh records `jwks_hash`, `discovery_hash`, `key_count`, and verifier config. Runtime hot-swap of the active verifier is intentionally separate and should be added only with a clear rotation policy.
