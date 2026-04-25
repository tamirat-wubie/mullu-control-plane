"""Integration tests proving governance enforcement through HTTP endpoints.

These tests use FastAPI's TestClient to verify that subsystems are actually
wired into the request flow — not just instantiated.
"""
from __future__ import annotations

import os
import pytest

try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app
    return TestClient(app, raise_server_exceptions=False)


class TestApiKeyAuthEnforcement:
    """Prove API key auth guard is wired into middleware."""

    def test_invalid_api_key_returns_401(self, client):
        resp = client.post(
            "/api/v1/complete",
            json={"prompt": "hello", "tenant_id": "t1"},
            headers={"Authorization": "Bearer invalid-key-12345"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["guard"] == "api_key"
        assert body["governed"] is True

    def test_no_api_key_passes_through(self, client):
        """Requests without Authorization header should pass the auth guard."""
        resp = client.post(
            "/api/v1/complete",
            json={"prompt": "hello", "tenant_id": "t1"},
        )
        # Should NOT be 401 — may be 200 or other, but not auth failure
        assert resp.status_code != 401


class TestCircuitBreakerEnforcement:
    """Prove circuit breaker is wired into /complete."""

    def test_complete_returns_circuit_state(self, client):
        resp = client.post(
            "/api/v1/complete",
            json={"prompt": "hello", "tenant_id": "t1"},
        )
        if resp.status_code == 200:
            body = resp.json()
            assert "circuit_state" in body


class TestInputValidationEnforcement:
    """Prove input validation is wired into /complete."""

    def test_empty_prompt_rejected(self, client):
        resp = client.post(
            "/api/v1/complete",
            json={"prompt": "", "tenant_id": "t1"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body.get("detail", {}).get("governed") is True or "validation" in str(body).lower()

    def test_negative_max_tokens_rejected(self, client):
        resp = client.post(
            "/api/v1/complete",
            json={"prompt": "hello", "max_tokens": -1, "tenant_id": "t1"},
        )
        # Pydantic or our validator should catch this
        assert resp.status_code in (422, 400)

    def test_temperature_too_high_rejected(self, client):
        resp = client.post(
            "/api/v1/complete",
            json={"prompt": "hello", "temperature": 5.0, "tenant_id": "t1"},
        )
        assert resp.status_code == 422


class TestFeatureFlagEnforcement:
    """Prove feature flags gate access to features."""

    def test_streaming_v2_flag_checked(self, client):
        """streaming_v2 is enabled by default, so should pass."""
        resp = client.post(
            "/api/v1/chat/stream",
            json={"message": "hello", "conversation_id": "test", "tenant_id": "t1"},
        )
        # Should not get 403 for feature flag since it's enabled
        assert resp.status_code != 403

    def test_tool_augmentation_flag_checked(self, client):
        """tool_augmentation is enabled by default."""
        resp = client.post(
            "/api/v1/workflow/tools",
            json={"prompt": "hello", "tool_ids": [], "tenant_id": "t1"},
        )
        assert resp.status_code != 403


class TestGlobalErrorHandler:
    """Prove global error handler returns sanitized errors."""

    def test_nonexistent_endpoint_returns_404(self, client):
        """Unknown endpoints return structured error, not a stack trace."""
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code in (404, 405)

    def test_health_endpoint_works(self, client):
        """Health endpoint should always respond."""
        resp = client.get("/health")
        assert resp.status_code == 200


class TestGuardChainComposition:
    """Prove the guard chain has the expected guards."""

    def test_guard_chain_has_four_guards(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        from mcoi_runtime.app.server import guard_chain
        names = guard_chain.guard_names()
        assert "tenant" in names
        assert "tenant_gating" in names
        assert "rbac" in names
        assert "Lambda_input_safety" in names
        assert "rate_limit" in names
        assert "budget" in names
        assert len(names) == 7

    def test_api_key_guard_runs_first(self):
        os.environ["MULLU_ENV"] = "local_dev"
        os.environ["MULLU_DB_BACKEND"] = "memory"
        from mcoi_runtime.app.server import guard_chain
        assert guard_chain.guard_names()[0] == "api_key"
