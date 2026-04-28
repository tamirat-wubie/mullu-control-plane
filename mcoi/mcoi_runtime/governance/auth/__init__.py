"""Authentication primitives — JWT/OIDC validation + API-key auth.

Modules:
  - ``jwt`` — :class:`JWTAuthenticator`, :class:`OIDCConfig`,
    JWKS fetcher, RS*/HS* signature verification
  - ``api_key`` — :class:`APIKeyManager`, hashed-secret storage,
    constant-time comparison, scope-bounded keys

Both modules default to the fail-closed posture (audit Part 3,
v4.33). See ``docs/GOVERNANCE_ARCHITECTURE.md``.
"""
