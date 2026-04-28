"""v4.33.0 — JWT auth hardening (audit Part 3).

Pre-v4.33 the JWT validator authenticated tokens that were technically
well-formed but operationally unsafe:

  - Empty ``sub`` was accepted; audit attribution went blank.
  - Empty tenant claim was accepted; combined with X-Tenant-ID header
    handling in middleware, an empty-tenant JWT effectively trusted
    the header (defense bypass).
  - ``iat`` was not validated; tokens with bogus future ``iat``
    passed as long as ``exp > now``.
  - ``jwks_url`` accepted any scheme, including ``http://`` — enabling
    MITM key substitution on the JWKS fetch path.
  - The default JWKS fetcher used ``urlopen`` directly, following 3xx
    redirects. A compromised JWKS endpoint could redirect to a private
    IP / metadata endpoint and slip past upstream SSRF checks.

v4.33 closes all five gaps. The new posture is opt-out per flag
(``require_subject``, ``require_tenant_claim``, ``require_iat_not_in_future``,
``require_https_jwks``) so legacy deployments can roll forward without
breaking.
"""
from __future__ import annotations

import json
import time
import urllib.error

import pytest

from mcoi_runtime.governance.auth.jwt import JWTAuthenticator, OIDCConfig
# Private helper stays on the canonical core path; shim only
# re-exports public API.
from mcoi_runtime.core.jwt_auth import _default_jwks_fetcher


# ============================================================
# require_https_jwks
# ============================================================


class TestHttpsOnlyJwks:
    def test_http_jwks_url_rejected_by_default(self):
        with pytest.raises(ValueError, match="must use HTTPS"):
            OIDCConfig(
                issuer="iss", audience="aud",
                jwks_url="http://jwks.example.com/keys",
                allowed_algorithms=frozenset({"RS256"}),
            )

    def test_https_jwks_url_accepted(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            jwks_url="https://jwks.example.com/keys",
            allowed_algorithms=frozenset({"RS256"}),
        )
        assert cfg.jwks_url == "https://jwks.example.com/keys"

    def test_opt_out_allows_http(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            jwks_url="http://jwks.example.com/keys",
            allowed_algorithms=frozenset({"RS256"}),
            require_https_jwks=False,
        )
        assert cfg.jwks_url == "http://jwks.example.com/keys"

    def test_https_check_is_case_insensitive(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            jwks_url="HTTPS://jwks.example.com/keys",
            allowed_algorithms=frozenset({"RS256"}),
        )
        assert cfg.jwks_url.lower().startswith("https://")


# ============================================================
# require_subject
# ============================================================


def _make_token(authenticator: JWTAuthenticator, **claims) -> str:
    """Build a token via the public create_token path, then optionally
    blank specific claims by re-signing the payload manually.

    create_token always sets ``sub`` from its argument, so to produce a
    token with empty ``sub`` we need to round-trip through the encoded
    pieces. We use create_token for the heavy lifting and re-encode.
    """
    import base64
    import hmac
    import hashlib

    token = authenticator.create_token(subject=claims.pop("subject", "user"))
    header_b64, payload_b64, _ = token.split(".")

    payload_raw = base64.urlsafe_b64decode(payload_b64 + "==")
    payload = json.loads(payload_raw)
    payload.update(claims)
    new_payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()

    signing_input = f"{header_b64}.{new_payload_b64}".encode("ascii")
    sig = hmac.new(
        authenticator.config.signing_key, signing_input, hashlib.sha256
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{header_b64}.{new_payload_b64}.{sig_b64}"


class TestRequireSubject:
    def test_empty_sub_rejected_by_default(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
        )
        auth = JWTAuthenticator(cfg)
        token = _make_token(auth, sub="")
        result = auth.validate(token)
        assert result.authenticated is False
        assert "sub" in result.error.lower()

    def test_missing_sub_rejected_by_default(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
        )
        auth = JWTAuthenticator(cfg)
        token = auth.create_token(subject="alice")
        # Strip sub from the token entirely
        import base64
        import hmac
        import hashlib

        h_b64, p_b64, _ = token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(p_b64 + "=="))
        payload.pop("sub", None)
        new_p = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        signing = f"{h_b64}.{new_p}".encode("ascii")
        sig = hmac.new(b"x" * 32, signing, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        result = auth.validate(f"{h_b64}.{new_p}.{sig_b64}")
        assert result.authenticated is False
        assert "sub" in result.error.lower()

    def test_opt_out_allows_empty_sub(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_subject=False,
            require_tenant_claim=False,
        )
        auth = JWTAuthenticator(cfg)
        token = _make_token(auth, sub="")
        result = auth.validate(token)
        assert result.authenticated is True
        assert result.subject == ""


# ============================================================
# require_tenant_claim
# ============================================================


class TestRequireTenantClaim:
    def test_empty_tenant_rejected_by_default(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
        )
        auth = JWTAuthenticator(cfg)
        # create_token only sets tenant_claim when tenant_id is non-empty
        token = auth.create_token(subject="alice")
        result = auth.validate(token)
        assert result.authenticated is False
        assert "tenant" in result.error.lower()

    def test_non_empty_tenant_accepted(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
        )
        auth = JWTAuthenticator(cfg)
        token = auth.create_token(subject="alice", tenant_id="acme")
        result = auth.validate(token)
        assert result.authenticated is True
        assert result.tenant_id == "acme"

    def test_opt_out_allows_empty_tenant(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
        )
        auth = JWTAuthenticator(cfg)
        token = auth.create_token(subject="alice")
        result = auth.validate(token)
        assert result.authenticated is True
        assert result.tenant_id == ""

    def test_custom_tenant_claim_name_enforced(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            tenant_claim="org_id",
        )
        auth = JWTAuthenticator(cfg)
        # tenant_id arg routes through tenant_claim, so this sets org_id="acme"
        token = auth.create_token(subject="alice", tenant_id="acme")
        result = auth.validate(token)
        assert result.authenticated is True
        assert result.tenant_id == "acme"


# ============================================================
# require_iat_not_in_future
# ============================================================


class TestIatNotInFuture:
    def test_future_iat_rejected_by_default(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
            clock_skew_seconds=30,
        )
        auth = JWTAuthenticator(cfg)
        future_iat = int(time.time()) + 3600  # 1h in the future
        token = _make_token(auth, iat=future_iat)
        result = auth.validate(token)
        assert result.authenticated is False
        assert "future" in result.error.lower()

    def test_iat_within_skew_accepted(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
            clock_skew_seconds=30,
        )
        auth = JWTAuthenticator(cfg)
        # iat 10s in the future — within 30s skew window
        token = _make_token(auth, iat=int(time.time()) + 10)
        result = auth.validate(token)
        assert result.authenticated is True

    def test_past_iat_accepted(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
        )
        auth = JWTAuthenticator(cfg)
        token = _make_token(auth, iat=int(time.time()) - 60)
        result = auth.validate(token)
        assert result.authenticated is True

    def test_non_numeric_iat_rejected(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
        )
        auth = JWTAuthenticator(cfg)
        token = _make_token(auth, iat="not-a-number")
        result = auth.validate(token)
        assert result.authenticated is False
        assert "iat" in result.error.lower()

    def test_opt_out_allows_future_iat(self):
        cfg = OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
            require_tenant_claim=False,
            require_iat_not_in_future=False,
        )
        auth = JWTAuthenticator(cfg)
        token = _make_token(auth, iat=int(time.time()) + 3600)
        result = auth.validate(token)
        assert result.authenticated is True


# ============================================================
# JWKS fetcher: redirect blocking
# ============================================================


class TestJwksRedirectBlocking:
    """The default JWKS fetcher must NOT follow 3xx redirects.

    We test the handler directly because spinning up an HTTP server in
    a unit test is overkill and brittle on Windows.
    """

    def test_no_redirect_handler_raises_on_redirect(self):
        import urllib.request

        # Re-extract the handler class from the fetcher's module by
        # invoking it against a stub URL via an HTTP-mocking shim.
        # Easier: build a redirect handler by replicating the inline
        # class' contract, then verify the fetcher's behavior end-to-end.
        from unittest.mock import MagicMock, patch

        # Simulate an HTTP redirect response. urllib's redirect handler
        # is invoked when status is 301/302/303/307/308. We patch the
        # opener.open call to raise the redirect-blocked error directly,
        # confirming the fetcher surfaces it.
        with patch("urllib.request.OpenerDirector.open") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                "https://jwks.example.com/keys", 302,
                "jwks_redirect_blocked:302", {}, None,
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                _default_jwks_fetcher("https://jwks.example.com/keys")
            assert "jwks_redirect_blocked" in str(exc_info.value.msg)

    def test_no_redirect_handler_class_blocks_redirect_request(self):
        """Verify the inline _NoRedirectHandler raises HTTPError on redirect."""
        # Import the function and exercise it; then probe its handler
        # class by triggering the redirect path through a known interface.
        # We construct a minimal stand-in HTTPRedirectHandler subclass
        # that mirrors the module's inline class to validate behavior.
        import urllib.request
        from unittest.mock import MagicMock

        # Re-build the handler by re-running _default_jwks_fetcher on a
        # closure that captures the opener — instead, exercise the live
        # handler by intercepting the build_opener call.
        captured = {}
        real_build = urllib.request.build_opener

        def capture_opener(*handlers):
            captured["handlers"] = handlers
            return real_build(*handlers)

        from unittest.mock import patch

        with patch("urllib.request.build_opener", side_effect=capture_opener):
            # Force the fetcher to fail fast — patch the opener.open call
            # so we don't make a real network request.
            with patch("urllib.request.OpenerDirector.open") as mock_open:
                mock_open.side_effect = urllib.error.URLError("stop")
                with pytest.raises(urllib.error.URLError):
                    _default_jwks_fetcher("https://jwks.example.com/keys")

        # The handlers list must include a class whose redirect_request
        # raises HTTPError with "jwks_redirect_blocked" in the message.
        handlers = captured["handlers"]
        assert len(handlers) >= 1
        handler_class = handlers[0]
        handler = handler_class() if isinstance(handler_class, type) else handler_class
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            handler.redirect_request(
                MagicMock(), MagicMock(), 302, "Found", {},
                "https://attacker.example.com/keys",
            )
        assert "jwks_redirect_blocked" in str(exc_info.value.msg)
