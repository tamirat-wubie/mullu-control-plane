"""v4.35.0 — env + tenant binding hardening (audit F5 + F6).

Two contained gaps:

F5 (env binding): Pre-v4.35 every site that read ``MULLU_ENV`` did
``runtime_env.get("MULLU_ENV", "local_dev")`` directly. An operator
deploying without setting the env var silently got the most permissive
policies (local_dev shell, looser tenant validation, X-Tenant-ID trust).
v4.35 routes reads through ``resolve_env`` which logs CRITICAL on
implicit fallback and supports fail-closed via ``MULLU_ENV_REQUIRED``.

F6 (tenant binding): Pre-v4.35 the JWT and API-key guards rejected
header/JWT tenant mismatch only when ``require_auth=True``. With
``require_auth=False`` a JWT with tenant=A combined with header
X-Tenant-ID=B silently overwrote ctx[tenant_id] to A. v4.35 introduces
``ctx["tenant_id_explicit"]`` set by the middleware when the caller
*explicitly* supplied a tenant. Mismatch is then rejected regardless of
``require_auth`` whenever the request explicitly supplied a different
tenant. Implicit defaults (e.g. middleware "system" fallback) are not
treated as explicit so legitimate dev requests keep passing.
"""
from __future__ import annotations

import logging

import pytest

from mcoi_runtime.app.server_context import (
    EnvBindingError,
    KNOWN_ENVS,
    resolve_env,
)
from mcoi_runtime.core.api_key_auth import APIKeyManager
from mcoi_runtime.core.governance_guard import (
    GovernanceGuardChain,
    create_api_key_guard,
    create_jwt_guard,
)
from mcoi_runtime.core.jwt_auth import JWTAuthenticator, OIDCConfig


# ============================================================
# F5: resolve_env
# ============================================================


class TestResolveEnv:
    def test_known_value_returned_unchanged(self):
        for env in KNOWN_ENVS:
            assert resolve_env({"MULLU_ENV": env}) == env

    def test_empty_falls_back_to_local_dev_with_warning(self, caplog):
        with caplog.at_level(logging.CRITICAL):
            result = resolve_env({})
        assert result == "local_dev"
        assert any("MULLU_ENV is not set" in rec.message for rec in caplog.records)

    def test_whitespace_only_treated_as_empty(self, caplog):
        with caplog.at_level(logging.CRITICAL):
            result = resolve_env({"MULLU_ENV": "   "})
        assert result == "local_dev"

    def test_unknown_value_returned_with_error_log(self, caplog):
        with caplog.at_level(logging.ERROR):
            result = resolve_env({"MULLU_ENV": "wonderland"})
        assert result == "wonderland"
        assert any("not a known environment" in rec.message for rec in caplog.records)

    def test_required_flag_blocks_implicit_default(self):
        with pytest.raises(EnvBindingError, match="MULLU_ENV_REQUIRED"):
            resolve_env({"MULLU_ENV_REQUIRED": "true"})

    def test_required_flag_blocks_empty_value(self):
        with pytest.raises(EnvBindingError):
            resolve_env({"MULLU_ENV": "", "MULLU_ENV_REQUIRED": "true"})

    def test_required_flag_passes_when_env_set(self):
        result = resolve_env(
            {"MULLU_ENV": "production", "MULLU_ENV_REQUIRED": "true"}
        )
        assert result == "production"

    @pytest.mark.parametrize("flag", ["1", "yes", "on", "TRUE", "True"])
    def test_required_flag_truthy_variants(self, flag):
        with pytest.raises(EnvBindingError):
            resolve_env({"MULLU_ENV_REQUIRED": flag})

    @pytest.mark.parametrize("flag", ["0", "no", "off", "false", ""])
    def test_required_flag_falsy_variants(self, flag, caplog):
        with caplog.at_level(logging.CRITICAL):
            result = resolve_env({"MULLU_ENV_REQUIRED": flag})
        assert result == "local_dev"


# ============================================================
# F6: tenant binding — JWT guard
# ============================================================


def _jwt_auth() -> JWTAuthenticator:
    return JWTAuthenticator(
        OIDCConfig(
            issuer="iss", audience="aud",
            signing_key=b"x" * 32,
            allowed_algorithms=frozenset({"HS256"}),
        )
    )


class TestJwtGuardTenantBindingF6:
    """Mismatch must be rejected when the request *explicitly* supplied
    a different tenant, regardless of ``require_auth``."""

    def test_explicit_mismatch_rejected_without_require_auth(self):
        auth = _jwt_auth()
        token = auth.create_token(subject="u1", tenant_id="t1")
        guard = create_jwt_guard(auth)  # require_auth=False (default)
        ctx = {
            "authorization": f"Bearer {token}",
            "tenant_id": "t2",                 # explicit header value
            "tenant_id_explicit": True,        # marked by middleware
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is False
        assert "tenant" in result.reason.lower()

    def test_implicit_default_does_not_trigger_mismatch(self):
        """When the middleware's implicit "system" default reaches the
        guard, the JWT tenant should win silently (legacy behavior)."""
        auth = _jwt_auth()
        token = auth.create_token(subject="u1", tenant_id="t1")
        guard = create_jwt_guard(auth)
        ctx = {
            "authorization": f"Bearer {token}",
            "tenant_id": "system",             # implicit fallback
            "tenant_id_explicit": False,       # NOT explicit
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is True
        assert ctx["tenant_id"] == "t1"

    def test_explicit_match_passes(self):
        auth = _jwt_auth()
        token = auth.create_token(subject="u1", tenant_id="acme")
        guard = create_jwt_guard(auth)
        ctx = {
            "authorization": f"Bearer {token}",
            "tenant_id": "acme",
            "tenant_id_explicit": True,
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is True

    def test_require_auth_still_rejects_implicit_mismatch(self):
        """``require_auth=True`` keeps the legacy strict behavior even
        when the request didn't mark tenant as explicit."""
        auth = _jwt_auth()
        token = auth.create_token(subject="u1", tenant_id="t1")
        guard = create_jwt_guard(auth, require_auth=True)
        ctx = {
            "authorization": f"Bearer {token}",
            "tenant_id": "t2",
            # tenant_id_explicit not set — pre-v4.35 callers wouldn't set it
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is False


# ============================================================
# F6: tenant binding — API key guard
# ============================================================


class TestApiKeyGuardTenantBindingF6:
    def _make_key(self, tenant: str = "acme") -> tuple[APIKeyManager, str]:
        mgr = APIKeyManager()
        raw, _ = mgr.create_key(tenant_id=tenant, scopes=frozenset({"*"}))
        return mgr, raw

    def test_explicit_mismatch_rejected_without_require_auth(self):
        mgr, raw = self._make_key(tenant="acme")
        guard = create_api_key_guard(mgr)  # require_auth=False
        ctx = {
            "authorization": f"Bearer {raw}",
            "tenant_id": "evil",
            "tenant_id_explicit": True,
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is False
        assert "tenant" in result.reason.lower()

    def test_implicit_default_passes_silently(self):
        mgr, raw = self._make_key(tenant="acme")
        guard = create_api_key_guard(mgr)
        ctx = {
            "authorization": f"Bearer {raw}",
            "tenant_id": "system",          # implicit
            "tenant_id_explicit": False,
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is True
        assert ctx["tenant_id"] == "acme"

    def test_require_auth_still_rejects_pre_v4_34_callers(self):
        """Old callers that don't set tenant_id_explicit still get the
        require_auth=True legacy strict path."""
        mgr, raw = self._make_key(tenant="acme")
        guard = create_api_key_guard(mgr, require_auth=True)
        ctx = {
            "authorization": f"Bearer {raw}",
            "tenant_id": "evil",
            "endpoint": "/api/test",
        }
        result = guard.check(ctx)
        assert result.allowed is False


# ============================================================
# F6: middleware sets tenant_id_explicit
# ============================================================


class TestMiddlewareTenantExplicit:
    """Verify the FastAPI middleware sets tenant_id_explicit correctly."""

    def _make_app(self):
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi not installed")

        from mcoi_runtime.app.middleware import GovernanceMiddleware
        from mcoi_runtime.core.governance_guard import (
            GovernanceGuard, GovernanceGuardChain, GuardResult,
        )

        captured: dict = {}

        def spy_check(ctx):
            captured["tenant_id"] = ctx.get("tenant_id")
            captured["tenant_id_explicit"] = ctx.get("tenant_id_explicit")
            return GuardResult(allowed=True, guard_name="spy")

        chain = GovernanceGuardChain()
        chain.add(GovernanceGuard("spy", spy_check))

        app = FastAPI()
        app.add_middleware(GovernanceMiddleware, guard_chain=chain)

        @app.get("/api/v1/probe")
        def probe():
            return {"ok": True}

        return TestClient(app), captured

    def test_no_header_marks_tenant_implicit(self):
        client, captured = self._make_app()
        client.get("/api/v1/probe")
        assert captured["tenant_id"] == "system"
        assert captured["tenant_id_explicit"] is False

    def test_header_marks_tenant_explicit(self):
        client, captured = self._make_app()
        client.get("/api/v1/probe", headers={"x-tenant-id": "acme"})
        assert captured["tenant_id"] == "acme"
        assert captured["tenant_id_explicit"] is True

    def test_query_marks_tenant_explicit(self):
        client, captured = self._make_app()
        client.get("/api/v1/probe?tenant_id=beta")
        assert captured["tenant_id"] == "beta"
        assert captured["tenant_id_explicit"] is True
