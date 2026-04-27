"""v4.19.0 — RSA / JWKS support in JWTAuthenticator.

Pre-v4.19 the authenticator was HMAC-only (HS256/384/512). Real OIDC
deployments (Auth0, Okta, Azure AD, Keycloak, Google) sign with RSA and
distribute public keys via a JWKS endpoint. This release adds:

- RS256/RS384/RS512 verification via the ``cryptography`` library
- Static public-key configuration for tests and air-gapped deployments
- JWKS-based key resolution with TTL-bounded cache + lazy refresh on
  unknown ``kid`` (rate-limited so a stream of bad-kid tokens cannot
  storm the JWKS endpoint)
- Mixed-mode configs (HS* + RS* allowed simultaneously)

All HS* paths are unchanged — see test_jwt_auth.py for those (46 tests
still pass without the ``cryptography`` extra).
"""
from __future__ import annotations

from typing import Any

import pytest

# Skip the entire module when ``cryptography`` is not installed.
# The lazy-import design in jwt_auth.py promises HS-only deployments
# don't need this extra; this skip keeps that contract honest while
# letting CI matrices that DO install it exercise the RSA path.
pytest.importorskip("cryptography")

from mcoi_runtime.core.jwt_auth import (
    JWKSFetcher,
    JWTAuthenticator,
    OIDCConfig,
)


# ---- Test fixtures: ephemeral RSA key pairs ----


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[Any, bytes]:
    """Generate a fresh 2048-bit RSA key pair for testing.

    Returns (private_key, public_pem_bytes). Module-scoped so we don't
    pay key generation on every test (~100ms).
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_pem


@pytest.fixture(scope="module")
def rsa_keypair_alt() -> tuple[Any, bytes]:
    """Second key pair for rotation/mismatch tests."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_pem


def _public_key_to_jwk(public_key, kid: str) -> dict[str, Any]:
    """Convert a cryptography RSAPublicKey into a JWKS-format dict."""
    import base64
    numbers = public_key.public_numbers()
    n_bytes = numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
    e_bytes = numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode("ascii"),
        "e": base64.urlsafe_b64encode(e_bytes).rstrip(b"=").decode("ascii"),
    }


# ============================================================
# OIDCConfig: validation of new RSA/JWKS fields
# ============================================================


def test_rs256_config_with_static_public_keys(rsa_keypair):
    _, pub_pem = rsa_keypair
    cfg = OIDCConfig(
        issuer="iss", audience="aud",
        public_keys={"k1": pub_pem},
        allowed_algorithms=frozenset({"RS256"}),
    )
    assert cfg.public_keys == {"k1": pub_pem}
    # signing_key may be empty when only RS* allowed
    assert cfg.signing_key == b""


def test_rs256_config_with_jwks_url():
    cfg = OIDCConfig(
        issuer="iss", audience="aud",
        jwks_url="https://example.com/.well-known/jwks.json",
        allowed_algorithms=frozenset({"RS256"}),
    )
    assert cfg.jwks_url == "https://example.com/.well-known/jwks.json"


def test_rs256_requires_keys_or_jwks():
    with pytest.raises(ValueError, match="public_keys or jwks_url"):
        OIDCConfig(
            issuer="iss", audience="aud",
            allowed_algorithms=frozenset({"RS256"}),
        )


def test_public_keys_and_jwks_url_mutually_exclusive(rsa_keypair):
    _, pub_pem = rsa_keypair
    with pytest.raises(ValueError, match="mutually exclusive"):
        OIDCConfig(
            issuer="iss", audience="aud",
            public_keys={"k1": pub_pem},
            jwks_url="https://example.com/jwks.json",
            allowed_algorithms=frozenset({"RS256"}),
        )


def test_mixed_hmac_and_rsa_requires_both(rsa_keypair):
    """If HS* AND RS* are both allowed, both signing_key AND keys are required."""
    _, pub_pem = rsa_keypair
    cfg = OIDCConfig(
        issuer="iss", audience="aud",
        signing_key=b"hmac-secret",
        public_keys={"k1": pub_pem},
        allowed_algorithms=frozenset({"HS256", "RS256"}),
    )
    assert cfg.signing_key == b"hmac-secret"
    assert cfg.public_keys is not None

    # Missing signing_key when HS* requested
    with pytest.raises(ValueError, match="signing_key"):
        OIDCConfig(
            issuer="iss", audience="aud",
            public_keys={"k1": pub_pem},
            allowed_algorithms=frozenset({"HS256", "RS256"}),
        )


def test_jwks_cache_ttl_must_be_positive():
    with pytest.raises(ValueError, match="jwks_cache_ttl_seconds"):
        OIDCConfig(
            issuer="iss", audience="aud",
            jwks_url="https://example.com/jwks.json",
            allowed_algorithms=frozenset({"RS256"}),
            jwks_cache_ttl_seconds=0,
        )


# ============================================================
# JWTAuthenticator: RS256 with static public keys
# ============================================================


def _config_with_static_keys(public_keys: dict[str, bytes]) -> OIDCConfig:
    return OIDCConfig(
        issuer="iss", audience="aud",
        public_keys=public_keys,
        allowed_algorithms=frozenset({"RS256", "RS384", "RS512"}),
        require_tenant_claim=False,
    )


def test_rs256_token_round_trip(rsa_keypair):
    private_key, pub_pem = rsa_keypair
    auth = JWTAuthenticator(_config_with_static_keys({"k1": pub_pem}))

    token = auth.create_token(
        subject="alice",
        tenant_id="acme",
        algorithm="RS256",
        rsa_private_key=private_key,
        kid="k1",
    )
    result = auth.validate(token)
    assert result.authenticated is True
    assert result.subject == "alice"
    assert result.tenant_id == "acme"


def test_rs384_token_round_trip(rsa_keypair):
    private_key, pub_pem = rsa_keypair
    auth = JWTAuthenticator(_config_with_static_keys({"k1": pub_pem}))

    token = auth.create_token(
        subject="bob", algorithm="RS384",
        rsa_private_key=private_key, kid="k1",
    )
    result = auth.validate(token)
    assert result.authenticated is True
    assert result.subject == "bob"


def test_rs512_token_round_trip(rsa_keypair):
    private_key, pub_pem = rsa_keypair
    auth = JWTAuthenticator(_config_with_static_keys({"k1": pub_pem}))

    token = auth.create_token(
        subject="carol", algorithm="RS512",
        rsa_private_key=private_key, kid="k1",
    )
    result = auth.validate(token)
    assert result.authenticated is True


def test_rs256_token_signed_by_wrong_key_rejected(rsa_keypair, rsa_keypair_alt):
    """A token signed with a different private key must NOT verify
    even if the kid matches a configured key."""
    _, pub_pem = rsa_keypair  # k1's public key
    wrong_private, _ = rsa_keypair_alt  # different keypair

    auth = JWTAuthenticator(_config_with_static_keys({"k1": pub_pem}))
    token = auth.create_token(
        subject="x", algorithm="RS256",
        rsa_private_key=wrong_private,  # signs with WRONG private key
        kid="k1",
    )
    result = auth.validate(token)
    assert result.authenticated is False
    assert "signature" in result.error


def test_rs256_token_with_unknown_kid_rejected(rsa_keypair):
    private_key, pub_pem = rsa_keypair
    auth = JWTAuthenticator(_config_with_static_keys({"k1": pub_pem}))
    token = auth.create_token(
        subject="x", algorithm="RS256",
        rsa_private_key=private_key, kid="unknown-kid",
    )
    result = auth.validate(token)
    assert result.authenticated is False
    assert "key not found" in result.error


def test_rs256_token_without_kid_rejected(rsa_keypair):
    """RFC 7517: kid is critical for multi-key JWKS. We require it."""
    private_key, pub_pem = rsa_keypair
    auth = JWTAuthenticator(
        OIDCConfig(
            issuer="iss", audience="aud",
            public_keys={"k1": pub_pem},
            allowed_algorithms=frozenset({"RS256"}),
        )
    )
    # create_token rejects empty kid for RS* algorithms
    with pytest.raises(ValueError, match="kid"):
        auth.create_token(
            subject="x", algorithm="RS256",
            rsa_private_key=private_key, kid="",
        )


def test_rs256_alg_not_allowed_rejected(rsa_keypair):
    """allowed_algorithms gates RS256 just like HS256 (alg confusion guard)."""
    private_key, pub_pem = rsa_keypair
    # Auth allows RS384 only — RS256 token must be rejected
    auth = JWTAuthenticator(OIDCConfig(
        issuer="iss", audience="aud",
        public_keys={"k1": pub_pem},
        allowed_algorithms=frozenset({"RS384"}),
    ))
    token = auth.create_token(
        subject="x", algorithm="RS256",
        rsa_private_key=private_key, kid="k1",
    )
    result = auth.validate(token)
    assert result.authenticated is False
    assert "algorithm not allowed" in result.error


def test_hmac_token_rejected_when_only_rsa_allowed(rsa_keypair):
    """Cross-family alg-confusion: HS256 token must NOT pass RS-only auth."""
    _, pub_pem = rsa_keypair
    rsa_auth = JWTAuthenticator(_config_with_static_keys({"k1": pub_pem}))

    # Create an HS256 token using a separate HMAC config
    hmac_auth = JWTAuthenticator(OIDCConfig(
        issuer="iss", audience="aud", signing_key=b"shared",
        allowed_algorithms=frozenset({"HS256"}),
    ))
    token = hmac_auth.create_token(subject="x")

    # Verify with RSA-only auth — must reject
    result = rsa_auth.validate(token)
    assert result.authenticated is False
    assert "algorithm not allowed" in result.error


# ============================================================
# Mixed mode: HS* + RS* in same authenticator
# ============================================================


def test_mixed_mode_accepts_both_families(rsa_keypair):
    """A config that allows HS256 AND RS256 must verify tokens of either."""
    private_key, pub_pem = rsa_keypair
    auth = JWTAuthenticator(OIDCConfig(
        issuer="iss", audience="aud",
        signing_key=b"hmac-secret",
        public_keys={"k1": pub_pem},
        allowed_algorithms=frozenset({"HS256", "RS256"}),
        require_tenant_claim=False,
    ))

    hs_token = auth.create_token(subject="hmac-user", algorithm="HS256")
    rs_token = auth.create_token(
        subject="rsa-user", algorithm="RS256",
        rsa_private_key=private_key, kid="k1",
    )

    hs_result = auth.validate(hs_token)
    rs_result = auth.validate(rs_token)
    assert hs_result.authenticated is True
    assert hs_result.subject == "hmac-user"
    assert rs_result.authenticated is True
    assert rs_result.subject == "rsa-user"


# ============================================================
# JWKSFetcher
# ============================================================


def test_jwks_fetcher_caches_keys(rsa_keypair):
    private_key, _ = rsa_keypair
    public_key = private_key.public_key()
    jwk = _public_key_to_jwk(public_key, "k1")
    call_count = [0]

    def stub_fetch(url: str) -> dict[str, Any]:
        call_count[0] += 1
        return {"keys": [jwk]}

    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        cache_ttl_seconds=60,
        fetcher=stub_fetch,
    )
    # First call hits the fetcher
    k1 = fetcher.get_key("k1")
    assert k1 is not None
    assert call_count[0] == 1
    # Second call is cached
    k2 = fetcher.get_key("k1")
    assert k2 is k1
    assert call_count[0] == 1


def test_jwks_fetcher_refreshes_on_unknown_kid(rsa_keypair, rsa_keypair_alt):
    """Unknown kid triggers a refresh in case keys rotated. After refresh,
    if still unknown, returns None — but the rotated key becomes available."""
    pk1, _ = rsa_keypair
    pk2, _ = rsa_keypair_alt

    fetch_responses = [
        {"keys": [_public_key_to_jwk(pk1.public_key(), "k1")]},
        {"keys": [_public_key_to_jwk(pk2.public_key(), "k2")]},  # rotated
    ]
    call_count = [0]

    def stub_fetch(url: str) -> dict[str, Any]:
        idx = min(call_count[0], len(fetch_responses) - 1)
        call_count[0] += 1
        return fetch_responses[idx]

    clock_value = [1000.0]
    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        cache_ttl_seconds=3600,
        fetcher=stub_fetch,
        clock=lambda: clock_value[0],
    )
    # Initial fetch — k1 only
    assert fetcher.get_key("k1") is not None
    assert call_count[0] == 1

    # Asking for k2 (unknown) triggers a refresh; k2 now available
    # (advance clock past the 5s rate-limit on refresh-on-miss)
    clock_value[0] = 1010.0
    assert fetcher.get_key("k2") is not None
    assert call_count[0] == 2


def test_jwks_fetcher_cache_expires(rsa_keypair):
    pk, _ = rsa_keypair
    jwk = _public_key_to_jwk(pk.public_key(), "k1")
    call_count = [0]

    def stub_fetch(url: str) -> dict[str, Any]:
        call_count[0] += 1
        return {"keys": [jwk]}

    clock_value = [1000.0]
    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        cache_ttl_seconds=60,
        fetcher=stub_fetch,
        clock=lambda: clock_value[0],
    )
    fetcher.get_key("k1")
    assert call_count[0] == 1

    # Advance clock past TTL
    clock_value[0] = 1100.0
    fetcher.get_key("k1")
    assert call_count[0] == 2


def test_jwks_fetcher_network_failure_keeps_stale_cache(rsa_keypair):
    """A failed refresh must not wipe a valid stale cache —
    bad upstream != reject all tokens."""
    pk, _ = rsa_keypair
    jwk = _public_key_to_jwk(pk.public_key(), "k1")
    fetch_count = [0]

    def stub_fetch(url: str) -> dict[str, Any]:
        fetch_count[0] += 1
        if fetch_count[0] == 1:
            return {"keys": [jwk]}
        raise ConnectionError("upstream JWKS unreachable")

    clock_value = [1000.0]
    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        cache_ttl_seconds=60,
        fetcher=stub_fetch,
        clock=lambda: clock_value[0],
    )
    assert fetcher.get_key("k1") is not None

    # TTL expires; refresh fails
    clock_value[0] = 1100.0
    # Existing key still resolvable from stale cache (defense against
    # JWKS endpoint flakiness)
    # Note: behavior is "best-effort" — refresh attempt fires but the
    # old cache stays. The fetcher does NOT wipe on failure.
    key = fetcher.get_key("k1")
    assert key is not None  # stale-but-functional


def test_jwks_fetcher_skips_non_rsa_keys():
    """A JWKS document containing EC or oct keys alongside RSA must
    parse the RSA ones and silently ignore others."""
    rsa_jwk_partial = {
        "kty": "RSA", "kid": "k1", "use": "sig", "alg": "RS256",
        # n, e omitted intentionally — should also be skipped
    }
    ec_jwk = {"kty": "EC", "kid": "k2", "crv": "P-256"}

    def stub_fetch(url: str) -> dict[str, Any]:
        return {"keys": [rsa_jwk_partial, ec_jwk]}

    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        fetcher=stub_fetch,
    )
    # Both keys are non-resolvable (EC unsupported, RSA missing n/e)
    assert fetcher.get_key("k1") is None
    assert fetcher.get_key("k2") is None


# ============================================================
# JWTAuthenticator + JWKS end-to-end
# ============================================================


def test_jwks_auth_validates_rs256_token(rsa_keypair):
    private_key, _ = rsa_keypair
    public_key = private_key.public_key()
    jwk = _public_key_to_jwk(public_key, "production-key-1")

    def stub_fetch(url: str) -> dict[str, Any]:
        return {"keys": [jwk]}

    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        fetcher=stub_fetch,
    )
    cfg = OIDCConfig(
        issuer="iss", audience="aud",
        jwks_url="https://example.com/jwks.json",
        allowed_algorithms=frozenset({"RS256"}),
    )
    auth = JWTAuthenticator(cfg, jwks_fetcher=fetcher)

    # Sign a token with our private key, kid matches JWKS
    token = auth.create_token(
        subject="alice", tenant_id="acme", algorithm="RS256",
        rsa_private_key=private_key, kid="production-key-1",
    )
    result = auth.validate(token)
    assert result.authenticated is True
    assert result.subject == "alice"
    assert result.tenant_id == "acme"


def test_jwks_auth_rejects_token_with_unknown_kid(rsa_keypair):
    private_key, _ = rsa_keypair

    def stub_fetch(url: str) -> dict[str, Any]:
        return {"keys": [_public_key_to_jwk(private_key.public_key(), "k1")]}

    fetcher = JWKSFetcher(
        "https://example.com/jwks.json",
        fetcher=stub_fetch,
    )
    auth = JWTAuthenticator(
        OIDCConfig(
            issuer="iss", audience="aud",
            jwks_url="https://example.com/jwks.json",
            allowed_algorithms=frozenset({"RS256"}),
        ),
        jwks_fetcher=fetcher,
    )
    # Token signed with kid="k99" — not in JWKS
    token = auth.create_token(
        subject="x", algorithm="RS256",
        rsa_private_key=private_key, kid="k99",
    )
    result = auth.validate(token)
    assert result.authenticated is False
    assert "key not found" in result.error
