# OIDC discovery and JWKS refresh

v9 adds a discovery-backed identity verifier model.

```text
issuer
  → /.well-known/openid-configuration
  → jwks_uri
  → JWKS cache entry
  → verifier config
  → bearer JWT verification
  → VerifiedIdentity
  → Principal
```

The runtime currently reads discovery and JWKS documents from files. This keeps key material explicit and testable while preserving the adapter seam for live HTTP discovery.

## Kernel types

```text
OidcDiscoveryConfig
OidcDiscoveryDocument
OidcJwksRefreshRequest
OidcJwksCacheEntry
OidcDiscoveryRefreshReport
```

## API

```text
GET  /system/oidc-discovery
POST /system/oidc-verifier/refresh
POST /system/identity/verify-jwt
```

Refresh does not silently mutate authorization policy. It records the JWKS hash, key count, issuer, and `jwks_uri` as operational evidence.

## CLI

```bash
cargo run -p mind-cli -- oidc-discovery-refresh \
  ./config/openid-configuration.json \
  ./config/jwks.json \
  https://issuer.example \
  nested-mind-api \
  RS256
```

## Environment

```bash
MIND_OIDC_DISCOVERY_FILE=./config/openid-configuration.json
MIND_OIDC_JWKS_FILE=./config/jwks.json
MIND_OIDC_ISSUER=https://issuer.example
MIND_OIDC_AUDIENCES=nested-mind-api
MIND_OIDC_ALLOWED_ALGORITHMS=RS256
MIND_OIDC_REFRESH_TTL_SECONDS=3600
```

## Fracture boundary

```text
- live HTTP fetch is not implemented in the kernel
- automatic cache rotation is not implemented
- discovery files must be supplied by deployment automation or a future fetch adapter
```
