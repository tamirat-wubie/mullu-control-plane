# Identity boundary

v7 separates authentication evidence from authorization decisions.

```text
upstream OIDC/mTLS gateway
  → verified claims / certificate digest
  → trusted identity headers
  → IdentityBindingPolicy
  → Principal
  → AuthorizationPolicy
```

The API does not trust identity headers unless:

```bash
MIND_TRUSTED_IDENTITY_HEADERS=true
```

When enabled, the API accepts these headers from a trusted reverse proxy only:

```text
x-mind-subject                 required
x-mind-issuer                  optional unless policy requires issuer
x-mind-audience                comma-separated
x-mind-roles                   comma-separated: observer,operator,auditor,maintainer,admin
x-mind-client-cert-sha256      optional unless policy requires certificate binding
x-mind-identity-source         oidc_jwt | mtls_client_certificate | trusted_proxy_header
```

Policy controls:

```bash
MIND_IDENTITY_ALLOWED_ISSUERS="https://issuer.example"
MIND_IDENTITY_REQUIRED_AUDIENCES="nested-mind-api"
MIND_IDENTITY_REQUIRED_CLIENT_CERT_SHA256="<sha256>"
```

Security boundary:

```text
- Direct client traffic must not be allowed to set trusted identity headers.
- The proxy must strip incoming identity headers before injecting verified values.
- OIDC/JWKS validation belongs at the gateway layer in this scaffold.
- mTLS client certificate verification belongs at the gateway layer in this scaffold.
- The API verifies policy binding over already-verified claims.
```

Protected inspection endpoint:

```text
GET /system/identity-policy
```

Requires `ReadIdentityPolicy` under the current authorization policy.

## v8 direct OIDC/JWKS verifier

v8 adds a direct bearer-JWT path. When `MIND_OIDC_JWKS_FILE`, `MIND_OIDC_ISSUER`, and `MIND_OIDC_AUDIENCES` are configured, the API can verify JWT signatures and registered claims before binding the identity to a principal. Trusted proxy headers remain available but are no longer the only production identity route.
