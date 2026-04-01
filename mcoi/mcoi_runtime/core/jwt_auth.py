"""Phase 2A — JWT/OIDC Authentication.

Purpose: Validate JWT tokens from external OIDC providers (Azure AD, Okta,
    Auth0, Keycloak). Extracts claims, verifies signatures and expiry,
    and propagates tenant identity into the governance guard context.
Governance scope: authentication only — never modifies business state.
Dependencies: stdlib (hmac, hashlib, base64, json, time).
Invariants:
  - JWT validation is stateless — no server-side session state.
  - Expired tokens are hard-rejected (no grace period).
  - Algorithm confusion attacks are prevented (explicit allowlist).
  - Tenant claim extraction is configurable (claim name mapping).
  - Signature verification is mandatory — unsigned tokens rejected.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JWTAlgorithm(str, Enum):
    """Supported JWT signing algorithms."""

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"


# Mapping of algorithm names to hashlib constructors
_HMAC_HASH_MAP: dict[str, str] = {
    "HS256": "sha256",
    "HS384": "sha384",
    "HS512": "sha512",
}


@dataclass(frozen=True, slots=True)
class OIDCConfig:
    """Configuration for OIDC/JWT authentication.

    issuer: Expected 'iss' claim value (e.g., "https://accounts.google.com")
    audience: Expected 'aud' claim value (e.g., "mullu-api")
    signing_key: Shared secret for HMAC algorithms (bytes)
    allowed_algorithms: Which algorithms to accept (prevents alg confusion)
    tenant_claim: JWT claim name containing tenant_id (default: "tenant_id")
    scope_claim: JWT claim name containing scopes (default: "scope")
    clock_skew_seconds: Tolerance for clock drift (default: 30s)
    require_expiry: If True, reject tokens without 'exp' claim
    """

    issuer: str
    audience: str
    signing_key: bytes
    allowed_algorithms: frozenset[str] = frozenset({"HS256"})
    tenant_claim: str = "tenant_id"
    scope_claim: str = "scope"
    clock_skew_seconds: int = 30
    require_expiry: bool = True

    def __post_init__(self) -> None:
        if not self.issuer:
            raise ValueError("issuer must not be empty")
        if not self.audience:
            raise ValueError("audience must not be empty")
        if not self.signing_key:
            raise ValueError("signing_key must not be empty")
        if not self.allowed_algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        for alg in self.allowed_algorithms:
            if alg not in _HMAC_HASH_MAP:
                raise ValueError(f"unsupported algorithm: {alg}")


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

    def __init__(self, config: OIDCConfig) -> None:
        self._config = config

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
                error=f"algorithm not allowed: {alg}",
            )
        if alg == "none":
            return JWTAuthResult(authenticated=False, error="unsigned tokens are rejected")

        # Step 4: Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        try:
            signature = _b64url_decode(signature_b64)
        except Exception:
            return JWTAuthResult(authenticated=False, error="invalid signature encoding")

        if not self._verify_hmac(alg, signing_input, signature):
            return JWTAuthResult(authenticated=False, error="signature verification failed")

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
                error=f"issuer mismatch: expected {self._config.issuer}, got {iss}",
            )

        # Audience
        aud = claims.get("aud", "")
        if isinstance(aud, list):
            if self._config.audience not in aud:
                return JWTAuthResult(
                    authenticated=False,
                    error=f"audience mismatch: {self._config.audience} not in {aud}",
                )
        elif aud != self._config.audience:
            return JWTAuthResult(
                authenticated=False,
                error=f"audience mismatch: expected {self._config.audience}, got {aud}",
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

        # Step 7: Extract identity claims
        subject = str(claims.get("sub", ""))
        tenant_id = str(claims.get(self._config.tenant_claim, ""))

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

    def create_token(
        self,
        *,
        subject: str,
        tenant_id: str = "",
        scopes: list[str] | None = None,
        extra_claims: dict[str, Any] | None = None,
        ttl_seconds: int = 3600,
        algorithm: str = "HS256",
    ) -> str:
        """Create a signed JWT token (useful for testing).

        NOT for production token issuance — use an OIDC provider for that.
        """
        if algorithm not in _HMAC_HASH_MAP:
            raise ValueError(f"unsupported algorithm: {algorithm}")

        now = int(time.time())
        header = {"alg": algorithm, "typ": "JWT"}
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
        hash_name = _HMAC_HASH_MAP[algorithm]
        signature = hmac.new(self._config.signing_key, signing_input, hash_name).digest()
        signature_b64 = _b64url_encode(signature)

        return f"{header_b64}.{payload_b64}.{signature_b64}"
