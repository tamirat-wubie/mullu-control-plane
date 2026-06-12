# Direct OIDC/JWKS verification

v8 adds an in-process OIDC/JWKS verifier path.

```text
Authorization: Bearer <JWT>
  → decode JWT header
  → require allowed algorithm
  → locate kid in JWKS
  → verify signature and registered claims
  → bind issuer/audience/subject into VerifiedIdentity
  → map VerifiedIdentity into Principal
  → authorize action
```

The trusted gateway header path remains available, but direct verification is now possible when the following settings are present:

```bash
MIND_OIDC_JWKS_FILE=./config/jwks.json
MIND_OIDC_ISSUER=https://issuer.example
MIND_OIDC_AUDIENCES=nested-mind-api
MIND_OIDC_ALLOWED_ALGORITHMS=RS256
MIND_OIDC_DEFAULT_ROLE=observer
```

Protected API endpoints:

```text
GET  /system/oidc-verifier
POST /system/identity/verify-jwt
```

CLI verification:

```bash
cargo run -p mind-cli -- verify-oidc-jwt \
  ./config/jwks.json \
  ./config/token.jwt \
  https://issuer.example \
  nested-mind-api
```

## Invariants

```text
- issuer must match configured issuer
- audience must intersect configured audience set
- algorithm must be explicitly allowed
- kid must exist in the configured JWKS
- token signature must verify before identity binding
- default role is applied only when no usable role claim exists
```

## Remaining work

```text
- JWKS refresh/caching is not automated yet
- OIDC discovery is not implemented yet
- mTLS direct certificate-chain verification remains delegated to gateway/runtime infrastructure
```
