"""Phase 2A — JWT/OIDC Authentication.

Purpose: Validate JWT tokens from external OIDC providers (Azure AD, Okta,
    Auth0, Keycloak). Extracts claims, verifies signatures and expiry,
    and propagates tenant identity into the governance guard context.
Governance scope: authentication only — never modifies business state.
Dependencies: stdlib (hmac, hashlib, base64, json, time, threading,
  urllib for JWKS); ``cryptography`` (optional — required only when RS*
  algorithms are enabled).
Invariants:
  - JWT validation is stateless — no server-side session state.
  - Expired tokens are hard-rejected (no grace period).
  - Algorithm confusion attacks are prevented (explicit allowlist).
  - Tenant claim extraction is configurable (claim name mapping).
  - Signature verification is mandatory — unsigned tokens rejected.

v4.19.0+: RS256/RS384/RS512 + JWKS-based key resolution. HS* paths are
unchanged. RSA support is opt-in: configs that don't reference RS* algs
or JWKS keep working without the ``cryptography`` extra installed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any, Callable


class JWTAlgorithm(str, Enum):
    """Supported JWT signing algorithms."""

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"


# Mapping of algorithm names to hashlib constructors
_HMAC_HASH_MAP: dict[str, str] = {
    "HS256": "sha256",
    "HS384": "sha384",
    "HS512": "sha512",
}

# Mapping of RS* algorithm names to cryptography hash classes.
# Resolved lazily so the module imports without ``cryptography`` installed
# when only HS* algorithms are used.
_RSA_HASH_NAMES: dict[str, str] = {
    "RS256": "SHA256",
    "RS384": "SHA384",
    "RS512": "SHA512",
}


def _is_rsa_alg(alg: str) -> bool:
    return alg in _RSA_HASH_NAMES


def _is_hmac_alg(alg: str) -> bool:
    return alg in _HMAC_HASH_MAP


@dataclass(frozen=True, slots=True)
class OIDCConfig:
    """Configuration for OIDC/JWT authentication.

    issuer: Expected 'iss' claim value (e.g., "https://accounts.google.com")
    audience: Expected 'aud' claim value (e.g., "mullu-api")
    signing_key: Shared secret for HMAC algorithms (bytes). Required when
        any HS* algorithm is allowed; ignored otherwise. Pass an empty
        bytes (b"") if only RS* algs are enabled.
    public_keys: Static map of ``kid -> PEM-encoded RSA public key`` for
        RS* algorithms (v4.19.0+). Used when ``jwks_url`` is not set.
        Either this or ``jwks_url`` is required when any RS* alg is
        allowed; otherwise both should be None.
    jwks_url: HTTPS URL serving a JWKS document (RFC 7517). Fetched on
        first RSA verification, cached for ``jwks_cache_ttl_seconds``.
        Mutually exclusive with ``public_keys``. v4.19.0+.
    jwks_cache_ttl_seconds: How long to cache the JWKS document before
        re-fetching. Refresh also happens lazily on cache miss for an
        unknown ``kid``. Default: 1 hour.
    allowed_algorithms: Which algorithms to accept (prevents alg confusion)
    tenant_claim: JWT claim name containing tenant_id (default: "tenant_id")
    scope_claim: JWT claim name containing scopes (default: "scope")
    clock_skew_seconds: Tolerance for clock drift (default: 30s)
    require_expiry: If True, reject tokens without 'exp' claim
    """

    issuer: str
    audience: str
    signing_key: bytes = b""
    public_keys: dict[str, bytes] | None = None
    jwks_url: str | None = None
    jwks_cache_ttl_seconds: int = 3600
    allowed_algorithms: frozenset[str] = frozenset({"HS256"})
    tenant_claim: str = "tenant_id"
    scope_claim: str = "scope"
    clock_skew_seconds: int = 30
    require_expiry: bool = True
    # v4.33.0 (audit JWT hardening): claim-presence enforcement.
    require_subject: bool = True
    """If True, reject tokens with empty/missing ``sub`` claim. Pre-v4.33
    such tokens authenticated successfully with empty ``subject``,
    leaving audit attribution blank. Default True for production
    correctness; set False for OIDC providers that legitimately omit
    sub (rare)."""

    require_tenant_claim: bool = True
    """If True, reject tokens with empty/missing tenant claim (the
    claim named by ``tenant_claim``). Pre-v4.33 such tokens
    authenticated; combined with ``X-Tenant-ID`` header handling,
    an empty-tenant JWT effectively trusted the header. Default True;
    set False only in deployments that don't use multi-tenancy."""

    require_iat_not_in_future: bool = True
    """If True, reject tokens whose ``iat`` claim is more than
    ``clock_skew_seconds`` in the future. Pre-v4.33 ``iat`` was
    not validated; tokens with bogus future ``iat`` were accepted as
    long as ``exp > now``. RFC 7519 §4.1.6."""

    require_https_jwks: bool = True
    """If True (default), ``jwks_url`` must be ``https://``. Set False
    only for test environments serving JWKS over HTTP. Pre-v4.33
    accepted any scheme; an operator misconfiguring ``http://``
    enabled a MITM key-substitution attack on the JWKS path."""

    def __post_init__(self) -> None:
        if not self.issuer:
            raise ValueError("issuer must not be empty")
        if not self.audience:
            raise ValueError("audience must not be empty")
        if not self.allowed_algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        for alg in self.allowed_algorithms:
            if not (_is_hmac_alg(alg) or _is_rsa_alg(alg)):
                raise ValueError(_unsupported_algorithm_error())

        any_hmac = any(_is_hmac_alg(a) for a in self.allowed_algorithms)
        any_rsa = any(_is_rsa_alg(a) for a in self.allowed_algorithms)

        if any_hmac and not self.signing_key:
            raise ValueError("signing_key required when HS* algorithms are allowed")
        if any_rsa and not (self.public_keys or self.jwks_url):
            raise ValueError(
                "public_keys or jwks_url required when RS* algorithms are allowed"
            )
        if self.public_keys is not None and self.jwks_url is not None:
            raise ValueError("public_keys and jwks_url are mutually exclusive")
        if self.jwks_cache_ttl_seconds <= 0:
            raise ValueError("jwks_cache_ttl_seconds must be positive")
        # v4.33.0 (audit JWT hardening): jwks_url must be HTTPS unless
        # the operator explicitly opts out via ``require_https_jwks=False``.
        # Pre-v4.33 the fetcher accepted any scheme; an operator
        # misconfiguring ``http://`` enabled MITM key substitution on
        # the JWKS path (attacker forges any token).
        if (
            self.jwks_url is not None
            and self.require_https_jwks
            and not self.jwks_url.lower().startswith("https://")
        ):
            raise ValueError(
                "jwks_url must use HTTPS; set require_https_jwks=False to opt out"
            )


@dataclass(frozen=True, slots=True)
class JWTAuthResult:
    """Result of JWT authentication."""

    authenticated: bool
    subject: str = ""
    tenant_id: str = ""
    scopes: frozenset[str] = field(default_factory=frozenset)
    claims: dict[str, Any] = field(default_factory=dict)
    error: str = ""


def _b64url_decode(data: str) -> bytes:
    """Decode base64url-encoded data (RFC 7515)."""
    # Add padding if needed
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _b64url_encode(data: bytes) -> str:
    """Encode bytes as base64url (no padding)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _bounded_algorithm_rejection() -> str:
    """Return a bounded algorithm rejection error."""
    return "algorithm not allowed"


def _unsupported_algorithm_error() -> str:
    """Return a bounded unsupported algorithm error."""
    return "unsupported algorithm"


def _bounded_claim_mismatch(claim_name: str) -> str:
    """Return a bounded claim mismatch error."""
    return f"{claim_name} mismatch"


# ---- RSA / JWKS support (v4.19.0+) ----
#
# These helpers are isolated so the module imports cleanly when only
# HS* algorithms are used and the ``cryptography`` extra is not installed.


def _import_cryptography() -> Any:
    """Import the ``cryptography`` package on demand.

    Raises a clear error when the extra isn't installed but RS* is
    being used. Lazy import keeps the HS*-only path zero-dependency.
    """
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        return {
            "hashes": hashes,
            "serialization": serialization,
            "padding": padding,
            "rsa": rsa,
        }
    except ImportError as exc:
        raise RuntimeError(
            "RS* algorithms require the 'cryptography' package; "
            "install via mcoi-runtime[encryption]"
        ) from exc


def _hash_class_for_rsa_alg(alg: str) -> Any:
    """Return the cryptography hash class for an RS* algorithm."""
    crypto = _import_cryptography()
    name = _RSA_HASH_NAMES.get(alg)
    if name is None:
        raise ValueError(_unsupported_algorithm_error())
    return getattr(crypto["hashes"], name)()


def _load_pem_public_key(pem_bytes: bytes) -> Any:
    """Parse a PEM-encoded RSA public key into a cryptography object."""
    crypto = _import_cryptography()
    return crypto["serialization"].load_pem_public_key(pem_bytes)


def _jwk_to_public_key(jwk: dict[str, Any]) -> Any:
    """Convert a JWKS-format RSA public key (n, e) into a public key object.

    Per RFC 7517/7518: ``n`` and ``e`` are base64url-encoded big-endian
    unsigned integers. This is the format JWKS endpoints serve. Only
    ``kty == "RSA"`` keys are supported; others return None so the
    caller can skip them.
    """
    if jwk.get("kty") != "RSA":
        return None
    n = jwk.get("n")
    e = jwk.get("e")
    if not isinstance(n, str) or not isinstance(e, str):
        return None
    try:
        n_bytes = _b64url_decode(n)
        e_bytes = _b64url_decode(e)
    except Exception:
        return None
    n_int = int.from_bytes(n_bytes, "big")
    e_int = int.from_bytes(e_bytes, "big")
    crypto = _import_cryptography()
    return crypto["rsa"].RSAPublicNumbers(e=e_int, n=n_int).public_key()


def _default_jwks_fetcher(url: str) -> dict[str, Any]:
    """Default JWKS fetcher — uses urllib (stdlib only, no extra deps).

    Production deployments often inject a custom fetcher with retries,
    HTTPS certificate pinning, or a circuit breaker. The default is
    intentionally minimal so tests can swap it out cleanly.

    v4.33.0 (audit JWT hardening): redirects are blocked. Pre-v4.33
    the fetcher used ``urlopen`` directly, which followed 3xx by
    default. A compromised JWKS endpoint could redirect to a
    private-IP / metadata endpoint and slip past upstream SSRF
    checks.

    Returns the decoded JWKS document (dict). Raises on network/parse
    errors so the caller can surface them in error reasons.
    """
    import urllib.request
    import urllib.error

    class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise urllib.error.HTTPError(
                newurl, code, f"jwks_redirect_blocked:{code}",
                headers, fp,
            )

    opener = urllib.request.build_opener(_NoRedirectHandler)
    with opener.open(url, timeout=10) as resp:  # nosec B310 - URL is operator-supplied
        body = resp.read()
    return json.loads(body)


class JWKSFetcher:
    """Fetch and cache a JWKS document for RSA key resolution.

    Thread-safe. Cache TTL bounds how long stale keys stay valid; on
    cache miss for an unknown ``kid`` the fetcher refreshes once before
    giving up. This handles the steady-state "you rotated keys" case
    without unbounded refresh storms.

    Inject ``fetcher`` for tests — a callable that takes a URL and
    returns the decoded JWKS dict.
    """

    def __init__(
        self,
        url: str,
        *,
        cache_ttl_seconds: int = 3600,
        fetcher: Callable[[str], dict[str, Any]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not url:
            raise ValueError("url must not be empty")
        self._url = url
        self._ttl = cache_ttl_seconds
        self._fetcher = fetcher or _default_jwks_fetcher
        self._clock = clock or time.monotonic
        self._lock = RLock()
        self._cache: dict[str, Any] = {}  # kid -> RSA public key object
        self._cache_expiry: float = 0.0
        self._last_refresh_attempt: float = 0.0

    def get_key(self, kid: str) -> Any | None:
        """Return the public key for ``kid`` or None.

        Refreshes the cache if expired or if the kid is unknown
        (rate-limited to one refresh per 5 seconds to bound bursts on
        a stream of bad-kid tokens).
        """
        with self._lock:
            now = self._clock()
            if now > self._cache_expiry:
                self._refresh(now)
            key = self._cache.get(kid)
            if key is None and (now - self._last_refresh_attempt) > 5.0:
                # Unknown kid — try one refresh in case keys rotated
                self._refresh(now)
                key = self._cache.get(kid)
            return key

    def _refresh(self, now: float) -> None:
        """Fetch and parse the JWKS document. Updates cache + expiry."""
        self._last_refresh_attempt = now
        try:
            jwks = self._fetcher(self._url)
        except Exception:
            # Network/parse failure — keep stale cache, retry later.
            # Don't crash the chain; verification of unknown kid will
            # fail naturally with a "key not found" error.
            return
        keys: dict[str, Any] = {}
        for jwk in jwks.get("keys", []):
            kid = jwk.get("kid")
            if not isinstance(kid, str):
                continue
            try:
                key = _jwk_to_public_key(jwk)
            except Exception:
                continue
            if key is not None:
                keys[kid] = key
        self._cache = keys
        self._cache_expiry = now + self._ttl

    def force_refresh(self) -> None:
        """Test-only: force a refresh on next get_key() call."""
        with self._lock:
            self._cache_expiry = 0.0
            self._last_refresh_attempt = 0.0


class JWTAuthenticator:
    """Validates JWT tokens using HMAC signatures.

    Supports HS256, HS384, HS512 algorithms. Verifies:
    - Signature integrity (HMAC)
    - Token structure (3-part dotted format)
    - Algorithm allowlist (prevents alg confusion)
    - Issuer (iss) and audience (aud) claims
    - Expiry (exp) with configurable clock skew
    - Not-before (nbf) with clock skew

    Extracts tenant_id and scopes from configurable claim names.
    """

    def __init__(
        self,
        config: OIDCConfig,
        *,
        jwks_fetcher: JWKSFetcher | None = None,
    ) -> None:
        self._config = config
        # Pre-parse static public keys so RSA verification is hot-path-free
        # of PEM parsing. None when only HS* is configured.
        self._static_public_keys: dict[str, Any] | None = None
        if config.public_keys:
            self._static_public_keys = {
                kid: _load_pem_public_key(pem)
                for kid, pem in config.public_keys.items()
            }
        # JWKS fetcher: caller-injected, or constructed from config when
        # jwks_url is set. None when only HS* is configured.
        if jwks_fetcher is not None:
            self._jwks_fetcher = jwks_fetcher
        elif config.jwks_url:
            self._jwks_fetcher = JWKSFetcher(
                config.jwks_url,
                cache_ttl_seconds=config.jwks_cache_ttl_seconds,
            )
        else:
            self._jwks_fetcher = None

    @property
    def config(self) -> OIDCConfig:
        return self._config

    def validate(self, token: str) -> JWTAuthResult:
        """Validate a JWT token and extract claims.

        Returns JWTAuthResult with authenticated=True on success,
        or authenticated=False with error message on failure.
        """
        # Step 1: Split token into parts
        parts = token.split(".")
        if len(parts) != 3:
            return JWTAuthResult(authenticated=False, error="invalid token format: expected 3 parts")

        header_b64, payload_b64, signature_b64 = parts

        # Step 2: Decode and parse header
        try:
            header_bytes = _b64url_decode(header_b64)
            header = json.loads(header_bytes)
        except Exception:
            return JWTAuthResult(authenticated=False, error="invalid token header")

        # Step 3: Verify algorithm
        alg = header.get("alg", "")
        if alg not in self._config.allowed_algorithms:
            return JWTAuthResult(
                authenticated=False,
                error=_bounded_algorithm_rejection(),
            )
        if alg == "none":
            return JWTAuthResult(authenticated=False, error="unsigned tokens are rejected")

        # Step 4: Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        try:
            signature = _b64url_decode(signature_b64)
        except Exception:
            return JWTAuthResult(authenticated=False, error="invalid signature encoding")

        if _is_hmac_alg(alg):
            if not self._verify_hmac(alg, signing_input, signature):
                return JWTAuthResult(
                    authenticated=False, error="signature verification failed"
                )
        elif _is_rsa_alg(alg):
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                return JWTAuthResult(
                    authenticated=False, error="RSA token missing kid in header"
                )
            public_key = self._resolve_rsa_key(kid)
            if public_key is None:
                return JWTAuthResult(
                    authenticated=False, error="signing key not found"
                )
            if not self._verify_rsa(alg, signing_input, signature, public_key):
                return JWTAuthResult(
                    authenticated=False, error="signature verification failed"
                )
        else:
            # Reachable only if allowed_algorithms changed underneath.
            return JWTAuthResult(
                authenticated=False, error=_unsupported_algorithm_error()
            )

        # Step 5: Decode and parse payload
        try:
            payload_bytes = _b64url_decode(payload_b64)
            claims = json.loads(payload_bytes)
        except Exception:
            return JWTAuthResult(authenticated=False, error="invalid token payload")

        if not isinstance(claims, dict):
            return JWTAuthResult(authenticated=False, error="payload must be a JSON object")

        # Step 6: Verify standard claims
        now = time.time()

        # Issuer
        iss = claims.get("iss", "")
        if iss != self._config.issuer:
            return JWTAuthResult(
                authenticated=False,
                error=_bounded_claim_mismatch("issuer"),
            )

        # Audience
        aud = claims.get("aud", "")
        if isinstance(aud, list):
            if self._config.audience not in aud:
                return JWTAuthResult(
                    authenticated=False,
                    error=_bounded_claim_mismatch("audience"),
                )
        elif aud != self._config.audience:
            return JWTAuthResult(
                authenticated=False,
                error=_bounded_claim_mismatch("audience"),
            )

        # Expiry
        exp = claims.get("exp")
        if exp is None and self._config.require_expiry:
            return JWTAuthResult(authenticated=False, error="token has no expiry (exp claim)")
        if exp is not None:
            if not isinstance(exp, (int, float)):
                return JWTAuthResult(authenticated=False, error="exp claim must be numeric")
            if now > exp + self._config.clock_skew_seconds:
                return JWTAuthResult(authenticated=False, error="token has expired")

        # Not-before
        nbf = claims.get("nbf")
        if nbf is not None:
            if not isinstance(nbf, (int, float)):
                return JWTAuthResult(authenticated=False, error="nbf claim must be numeric")
            if now < nbf - self._config.clock_skew_seconds:
                return JWTAuthResult(authenticated=False, error="token is not yet valid (nbf)")

        # v4.33.0 (audit JWT hardening): iat (issued-at) sanity.
        # RFC 7519 §4.1.6. Reject tokens issued in the future
        # (beyond clock_skew); they're either misclocked or forged.
        # Pre-v4.33 ``iat`` was not validated; tokens with bogus
        # ``iat`` passed as long as ``exp > now``.
        iat = claims.get("iat")
        if iat is not None and self._config.require_iat_not_in_future:
            if not isinstance(iat, (int, float)):
                return JWTAuthResult(authenticated=False, error="iat claim must be numeric")
            if iat > now + self._config.clock_skew_seconds:
                return JWTAuthResult(authenticated=False, error="token iat is in the future")

        # Step 7: Extract identity claims
        subject = str(claims.get("sub", ""))
        tenant_id = str(claims.get(self._config.tenant_claim, ""))

        # v4.33.0 (audit JWT hardening): require non-empty subject.
        # Pre-v4.33 tokens with empty ``sub`` authenticated successfully
        # with empty ``subject``, leaving audit attribution blank.
        if self._config.require_subject and not subject:
            return JWTAuthResult(
                authenticated=False, error="sub claim is empty or missing"
            )

        # v4.33.0 (audit JWT hardening): require non-empty tenant claim.
        # Pre-v4.33 tokens with empty tenant claim authenticated; combined
        # with X-Tenant-ID header handling in middleware, an empty-tenant
        # JWT effectively trusted the header (defense bypass).
        if self._config.require_tenant_claim and not tenant_id:
            return JWTAuthResult(
                authenticated=False, error="tenant claim is empty or missing"
            )

        # Scopes: support both space-separated string and list
        raw_scopes = claims.get(self._config.scope_claim, "")
        if isinstance(raw_scopes, str):
            scope_list = raw_scopes.split() if raw_scopes else []
        elif isinstance(raw_scopes, list):
            scope_list = [str(s) for s in raw_scopes]
        else:
            scope_list = []

        return JWTAuthResult(
            authenticated=True,
            subject=subject,
            tenant_id=tenant_id,
            scopes=frozenset(scope_list),
            claims=claims,
        )

    def _verify_hmac(self, alg: str, signing_input: bytes, signature: bytes) -> bool:
        """Verify HMAC signature."""
        hash_name = _HMAC_HASH_MAP.get(alg)
        if hash_name is None:
            return False
        expected = hmac.new(self._config.signing_key, signing_input, hash_name).digest()
        return hmac.compare_digest(expected, signature)

    def _resolve_rsa_key(self, kid: str) -> Any | None:
        """Resolve an RSA public key by kid. Static map first, JWKS second."""
        if self._static_public_keys is not None:
            return self._static_public_keys.get(kid)
        if self._jwks_fetcher is not None:
            return self._jwks_fetcher.get_key(kid)
        return None

    def _verify_rsa(
        self,
        alg: str,
        signing_input: bytes,
        signature: bytes,
        public_key: Any,
    ) -> bool:
        """Verify an RSA-PKCS1v1.5 signature.

        Returns False on any verification failure (bad signature, wrong
        algorithm, malformed key) — exceptions are caught and treated as
        rejection so the caller's static-string error path stays consistent.
        """
        crypto = _import_cryptography()
        hash_obj = _hash_class_for_rsa_alg(alg)
        try:
            public_key.verify(
                signature,
                signing_input,
                crypto["padding"].PKCS1v15(),
                hash_obj,
            )
            return True
        except Exception:
            return False

    def create_token(
        self,
        *,
        subject: str,
        tenant_id: str = "",
        scopes: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
        ttl_seconds: int = 3600,
        algorithm: str = "HS256",
        rsa_private_key: Any = None,
        kid: str = "",
    ) -> str:
        """Create a signed JWT token (useful for testing).

        NOT for production token issuance — use an OIDC provider for that.

        For HS* algorithms: signs with ``self._config.signing_key``.
        For RS* algorithms: requires ``rsa_private_key`` (a cryptography
        RSAPrivateKey) and ``kid`` (the key ID, included in the header
        so the verifier can look up the matching public key).
        """
        if not (_is_hmac_alg(algorithm) or _is_rsa_alg(algorithm)):
            raise ValueError(_unsupported_algorithm_error())
        if _is_rsa_alg(algorithm) and rsa_private_key is None:
            raise ValueError("RS* algorithms require rsa_private_key")
        if _is_rsa_alg(algorithm) and not kid:
            raise ValueError("RS* algorithms require kid")

        now = int(time.time())
        header: dict[str, Any] = {"alg": algorithm, "typ": "JWT"}
        if kid:
            header["kid"] = kid
        payload: dict[str, Any] = {
            "iss": self._config.issuer,
            "aud": self._config.audience,
            "sub": subject,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        if tenant_id:
            payload[self._config.tenant_claim] = tenant_id
        if scopes:
            payload[self._config.scope_claim] = " ".join(scopes)
        if extra_claims:
            payload.update(extra_claims)

        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        if _is_hmac_alg(algorithm):
            hash_name = _HMAC_HASH_MAP[algorithm]
            signature = hmac.new(
                self._config.signing_key, signing_input, hash_name
            ).digest()
        else:
            crypto = _import_cryptography()
            hash_obj = _hash_class_for_rsa_alg(algorithm)
            signature = rsa_private_key.sign(
                signing_input,
                crypto["padding"].PKCS1v15(),
                hash_obj,
            )
        signature_b64 = _b64url_encode(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"
