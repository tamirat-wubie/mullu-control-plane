"""Middleware and governance-guard safety tests."""

from __future__ import annotations

import pytest

try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - environment-dependent
    FASTAPI_AVAILABLE = False

from mcoi_runtime.app.middleware import (
    GovernanceMiddleware,
    _extract_content_safety_fields,
)
from mcoi_runtime.core.governance_guard import (
    GuardResult,
    GovernanceGuard,
    GovernanceGuardChain,
)


def _client_with_chain(
    chain: GovernanceGuardChain,
    **middleware_kwargs: object,
) -> TestClient:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    app = FastAPI()

    @app.post("/api/v1/echo")
    def echo():
        return {"ok": True}

    app.add_middleware(GovernanceMiddleware, guard_chain=chain, **middleware_kwargs)
    return TestClient(app)


def test_guard_exception_is_sanitized_at_http_boundary() -> None:
    chain = GovernanceGuardChain()

    def boom(_context: dict[str, object]) -> GuardResult:
        raise RuntimeError("guard-secret-detail")

    chain.add(GovernanceGuard("boom", boom))
    client = _client_with_chain(chain)

    resp = client.post("/api/v1/echo", json={"prompt": "hello"})

    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "guard error (RuntimeError)"
    assert body["guard"] == "boom"
    assert body["governed"] is True
    assert "guard-secret-detail" not in str(body)


def test_middleware_skips_malformed_json_content_extraction() -> None:
    chain = GovernanceGuardChain()

    def verify_context(context: dict[str, object]) -> GuardResult:
        assert context.get("prompt") is None
        assert context.get("content") is None
        return GuardResult(allowed=True, guard_name="verify")

    chain.add(GovernanceGuard("verify", verify_context))
    client = _client_with_chain(chain)

    resp = client.post(
        "/api/v1/echo",
        content=b"{",
        headers={"content-type": "application/json"},
    )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_extract_content_safety_fields_rejects_malformed_json() -> None:
    assert _extract_content_safety_fields(b"{") == {}


def test_extract_content_safety_fields_only_keeps_strings() -> None:
    extracted = _extract_content_safety_fields(
        b'{"prompt":"safe","content":["not-text"],"ignored":true}'
    )

    assert extracted == {"prompt": "safe"}


def test_middleware_witnesses_proof_bridge_failures() -> None:
    chain = GovernanceGuardChain()
    metric_calls: list[tuple[str, int]] = []

    class BrokenProofBridge:
        def certify_governance_decision(self, **_kwargs: object) -> None:
            raise RuntimeError("secret-proof-failure")

    def allow(_context: dict[str, object]) -> GuardResult:
        return GuardResult(allowed=True, guard_name="allow")

    chain.add(GovernanceGuard("allow", allow))
    client = _client_with_chain(
        chain,
        metrics_fn=lambda name, value: metric_calls.append((name, value)),
        proof_bridge=BrokenProofBridge(),
    )

    resp = client.post("/api/v1/echo", json={"prompt": "hello"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert ("proof_bridge_certification_failures", 1) in metric_calls


def test_middleware_witnesses_decision_log_failures() -> None:
    chain = GovernanceGuardChain()
    metric_calls: list[tuple[str, int]] = []

    class BrokenDecisionLog:
        def record(self, **_kwargs: object) -> None:
            raise RuntimeError("secret-decision-log-failure")

    def allow(_context: dict[str, object]) -> GuardResult:
        return GuardResult(allowed=True, guard_name="allow")

    chain.add(GovernanceGuard("allow", allow))
    client = _client_with_chain(
        chain,
        metrics_fn=lambda name, value: metric_calls.append((name, value)),
        decision_log=BrokenDecisionLog(),
    )

    resp = client.post("/api/v1/echo", json={"prompt": "hello"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert ("decision_log_record_failures", 1) in metric_calls
    assert "secret-decision-log-failure" not in str(resp.json())


def test_middleware_witnesses_request_analytics_failures() -> None:
    chain = GovernanceGuardChain()
    metric_calls: list[tuple[str, int]] = []

    class BrokenRequestAnalytics:
        def record(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("secret-analytics-failure")

    def allow(_context: dict[str, object]) -> GuardResult:
        return GuardResult(allowed=True, guard_name="allow")

    chain.add(GovernanceGuard("allow", allow))
    client = _client_with_chain(
        chain,
        metrics_fn=lambda name, value: metric_calls.append((name, value)),
        request_analytics=BrokenRequestAnalytics(),
    )

    resp = client.post("/api/v1/echo", json={"prompt": "hello"})

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert ("request_analytics_record_failures", 1) in metric_calls
    assert "secret-analytics-failure" not in str(resp.json())
