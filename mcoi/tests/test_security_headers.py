"""Security Headers Middleware Tests — OWASP-recommended response headers."""

import pytest
from mcoi_runtime.app.security_headers import (
    SecurityHeadersConfig,
    SecurityHeadersMiddleware,
    build_security_headers,
)


# ── build_security_headers ─────────────────────────────────────

class TestBuildSecurityHeaders:
    def test_default_production_headers(self):
        headers = build_security_headers()
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "0"
        assert headers["Cache-Control"] == "no-store"
        assert headers["Pragma"] == "no-cache"
        assert headers["Server"] == "mullu"
        assert "Content-Security-Policy" in headers
        assert "Referrer-Policy" in headers
        assert "Permissions-Policy" in headers
        assert "Strict-Transport-Security" in headers

    def test_production_hsts(self):
        headers = build_security_headers(SecurityHeadersConfig(environment="production"))
        hsts = headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_development_no_hsts(self):
        headers = build_security_headers(SecurityHeadersConfig(environment="development"))
        assert "Strict-Transport-Security" not in headers

    def test_production_strict_csp(self):
        headers = build_security_headers(SecurityHeadersConfig(environment="production"))
        csp = headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "'unsafe-eval'" not in csp

    def test_development_relaxed_csp(self):
        headers = build_security_headers(SecurityHeadersConfig(environment="development"))
        csp = headers["Content-Security-Policy"]
        assert "'unsafe-inline'" in csp
        assert "'unsafe-eval'" in csp

    def test_custom_csp_overrides_default(self):
        cfg = SecurityHeadersConfig(csp="default-src 'none'")
        headers = build_security_headers(cfg)
        assert headers["Content-Security-Policy"] == "default-src 'none'"

    def test_custom_headers(self):
        cfg = SecurityHeadersConfig(custom_headers={"X-Custom": "test-value"})
        headers = build_security_headers(cfg)
        assert headers["X-Custom"] == "test-value"

    def test_custom_headers_override_defaults(self):
        cfg = SecurityHeadersConfig(custom_headers={"X-Frame-Options": "SAMEORIGIN"})
        headers = build_security_headers(cfg)
        assert headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_referrer_policy(self):
        headers = build_security_headers()
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        headers = build_security_headers()
        pp = headers["Permissions-Policy"]
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp

    def test_server_header_hides_version(self):
        headers = build_security_headers()
        assert headers["Server"] == "mullu"
        assert "python" not in headers["Server"].lower()
        assert "uvicorn" not in headers["Server"].lower()


# ── SecurityHeadersConfig ──────────────────────────────────────

class TestSecurityHeadersConfig:
    def test_production_detection(self):
        assert SecurityHeadersConfig(environment="production").is_production is True
        assert SecurityHeadersConfig(environment="staging").is_production is True
        assert SecurityHeadersConfig(environment="development").is_production is False
        assert SecurityHeadersConfig(environment="local_dev").is_production is False
        assert SecurityHeadersConfig(environment="test").is_production is False

    def test_hsts_with_preload(self):
        cfg = SecurityHeadersConfig(hsts_preload=True)
        assert "preload" in cfg.effective_hsts

    def test_hsts_without_subdomains(self):
        cfg = SecurityHeadersConfig(hsts_include_subdomains=False)
        assert "includeSubDomains" not in cfg.effective_hsts

    def test_custom_hsts_max_age(self):
        cfg = SecurityHeadersConfig(hsts_max_age=86400)
        assert "max-age=86400" in cfg.effective_hsts

    def test_custom_referrer_policy(self):
        cfg = SecurityHeadersConfig(referrer_policy="no-referrer")
        headers = build_security_headers(cfg)
        assert headers["Referrer-Policy"] == "no-referrer"


# ── Middleware integration ─────────────────────────────────────

class TestMiddlewareIntegration:
    def test_middleware_adds_headers(self):
        """Test that middleware injects headers into response."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        def homepage(request):
            return PlainTextResponse("OK")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(SecurityHeadersMiddleware, config=SecurityHeadersConfig())

        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Content-Security-Policy"] != ""
        assert resp.headers["Server"] == "mullu"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_middleware_on_error_response(self):
        """Headers are applied even on error responses."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        def error_endpoint(request):
            return PlainTextResponse("Not Found", status_code=404)

        app = Starlette(routes=[Route("/missing", error_endpoint)])
        app.add_middleware(SecurityHeadersMiddleware, config=SecurityHeadersConfig())

        client = TestClient(app)
        resp = client.get("/missing")
        assert resp.status_code == 404
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_middleware_dev_config(self):
        """Development config applies relaxed headers."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        def homepage(request):
            return PlainTextResponse("OK")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(
            SecurityHeadersMiddleware,
            config=SecurityHeadersConfig(environment="development"),
        )

        client = TestClient(app)
        resp = client.get("/")
        assert "Strict-Transport-Security" not in resp.headers
        assert "'unsafe-eval'" in resp.headers["Content-Security-Policy"]

    def test_middleware_production_config(self):
        """Production config applies strict headers."""
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        def homepage(request):
            return PlainTextResponse("OK")

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(
            SecurityHeadersMiddleware,
            config=SecurityHeadersConfig(environment="production"),
        )

        client = TestClient(app)
        resp = client.get("/")
        assert "Strict-Transport-Security" in resp.headers
        assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]
        csp = resp.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp
        assert "'unsafe-eval'" not in csp


# ── Edge cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_custom_headers(self):
        cfg = SecurityHeadersConfig(custom_headers={})
        headers = build_security_headers(cfg)
        assert "X-Content-Type-Options" in headers  # Defaults preserved

    def test_all_environments(self):
        """All environment strings produce valid headers."""
        for env in ("production", "staging", "development", "local_dev", "test"):
            headers = build_security_headers(SecurityHeadersConfig(environment=env))
            assert "X-Content-Type-Options" in headers
            assert "Content-Security-Policy" in headers
