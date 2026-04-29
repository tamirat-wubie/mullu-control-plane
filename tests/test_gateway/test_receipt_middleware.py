"""Tests for gateway/receipt_middleware.py — G10.1 entry-point certification.

Verifies that every gateway webhook/authority POST emits a
TransitionReceipt via the platform's ProofBridge. Closes the High-
severity gap documented in docs/MAF_RECEIPT_COVERAGE.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from gateway.receipt_middleware import (  # noqa: E402
    GatewayReceiptMiddleware,
    _channel_from_path,
    _outcome_from_status,
    install_gateway_receipt_middleware,
)


# ── Test doubles ─────────────────────────────────────────────────────


class _RecordingProofBridge:
    """Captures every certify_governance_decision call for inspection."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def certify_governance_decision(self, **kwargs):
        self.calls.append(kwargs)
        return None


class _ExplodingProofBridge:
    """Raises on certify — proves middleware cannot break the gateway."""

    def certify_governance_decision(self, **kwargs):
        raise RuntimeError("simulated proof_bridge failure")


# ── _channel_from_path ──────────────────────────────────────────────


class TestChannelFromPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/webhook/whatsapp", "whatsapp"),
            ("/webhook/telegram", "telegram"),
            ("/webhook/slack", "slack"),
            ("/webhook/discord", "discord"),
            ("/webhook/web", "web"),
            ("/webhook/approve/req-123", "approve"),
            ("/authority/approval-chains/expire-overdue", "authority"),
            ("/authority/obligations/abc/satisfy", "authority"),
            ("/authority/obligations/escalate-overdue", "authority"),
            ("/capability-plans/plan-1/recover", "capability-plans"),
            ("/random/path", "other"),
            ("/webhook/", "webhook"),
            ("/", "other"),
        ],
    )
    def test_paths_map_to_documented_channels(self, path: str, expected: str):
        assert _channel_from_path(path) == expected


# ── _outcome_from_status ────────────────────────────────────────────


class TestOutcomeFromStatus:
    @pytest.mark.parametrize(
        "code,decision,outcome",
        [
            (200, "allowed", "success"),
            (201, "allowed", "success"),
            (299, "allowed", "success"),
            (400, "denied", "denied"),
            (401, "denied", "denied"),
            (403, "denied", "denied"),
            (404, "denied", "denied"),
            (499, "denied", "denied"),
            (500, "denied", "error"),
            (502, "denied", "error"),
            (599, "denied", "error"),
        ],
    )
    def test_status_maps_to_documented_outcome(
        self, code: int, decision: str, outcome: str,
    ):
        assert _outcome_from_status(code) == (decision, outcome)

    def test_unusual_status_codes_default_to_denied(self):
        # 1xx and 3xx fall through to the "denied" branch (intentional —
        # gateway entry-points never legitimately return these).
        assert _outcome_from_status(100) == ("denied", "error")
        assert _outcome_from_status(301) == ("denied", "error")


# ── Middleware end-to-end ───────────────────────────────────────────


def _make_app(proof_bridge):
    app = FastAPI()
    app.add_middleware(GatewayReceiptMiddleware, proof_bridge=proof_bridge)

    @app.post("/webhook/whatsapp")
    async def whatsapp():
        return {"ok": True}

    @app.post("/webhook/telegram")
    async def telegram():
        return {"ok": True}

    @app.post("/webhook/slack")
    async def slack_handler():
        raise HTTPException(403, detail="bad signature")

    @app.post("/webhook/discord")
    async def discord_handler():
        raise HTTPException(401, detail="unauthorized")

    @app.post("/webhook/web")
    async def web():
        return {"ok": True}

    @app.post("/webhook/approve/{rid}")
    async def approve(rid: str):
        return {"resolved": rid}

    @app.post("/authority/approval-chains/expire-overdue")
    async def expire():
        return {"expired": 0}

    @app.post("/authority/obligations/{oid}/satisfy")
    async def satisfy(oid: str):
        return {"satisfied": oid}

    @app.post("/authority/obligations/escalate-overdue")
    async def escalate():
        raise RuntimeError("simulated handler crash")

    @app.post("/capability-plans/{plan_id}/recover")
    async def recover_plan(plan_id: str):
        return {"recovered": plan_id}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


class TestMiddlewareCertifies:
    def test_successful_webhook_emits_allowed_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        resp = client.post("/webhook/whatsapp", json={})
        assert resp.status_code == 200
        assert len(bridge.calls) == 1
        call = bridge.calls[0]
        assert call["decision"] == "allowed"
        assert call["endpoint"] == "/webhook/whatsapp"
        assert call["tenant_id"] == "gateway:whatsapp"
        assert call["actor_id"] == "gateway:whatsapp"
        assert call["guard_results"][0]["allowed"] is True
        assert call["guard_results"][0]["reason"].startswith("http_200")

    def test_403_response_emits_denied_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        resp = client.post("/webhook/slack", json={})
        assert resp.status_code == 403
        assert len(bridge.calls) == 1
        call = bridge.calls[0]
        assert call["decision"] == "denied"
        assert call["guard_results"][0]["allowed"] is False
        assert call["guard_results"][0]["reason"].startswith("http_403")

    def test_401_response_emits_denied_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        resp = client.post("/webhook/discord", json={})
        assert resp.status_code == 401
        assert len(bridge.calls) == 1
        assert bridge.calls[0]["decision"] == "denied"

    def test_500_response_emits_denied_receipt_with_error_outcome(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        resp = client.post("/authority/obligations/escalate-overdue", json={})
        assert resp.status_code == 500
        assert len(bridge.calls) == 1
        call = bridge.calls[0]
        assert call["decision"] == "denied"
        assert "http_500" in call["guard_results"][0]["reason"]

    def test_all_certified_paths_emit_receipts(self):
        """Coverage matrix from receipt_middleware.py docstring."""
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        certified_paths = [
            "/webhook/whatsapp",
            "/webhook/telegram",
            "/webhook/slack",
            "/webhook/discord",
            "/webhook/web",
            "/webhook/approve/abc",
            "/authority/approval-chains/expire-overdue",
            "/authority/obligations/xyz/satisfy",
            "/authority/obligations/escalate-overdue",
            "/capability-plans/plan-1/recover",
        ]
        for p in certified_paths:
            client.post(p, json={})
        # Every certified path emitted exactly one receipt
        assert len(bridge.calls) == len(certified_paths)
        emitted_paths = [c["endpoint"] for c in bridge.calls]
        assert set(emitted_paths) == set(certified_paths)


class TestMiddlewareDoesNotCertify:
    def test_get_request_not_certified(self):
        """Only POSTs cross the trust boundary; GETs are read-only."""
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge))
        resp = client.get("/health")
        assert resp.status_code == 200
        assert bridge.calls == []

    def test_unknown_path_not_certified(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        # No /random/* in certified_prefixes
        client.post("/random/path", json={})
        assert bridge.calls == []


class TestMiddlewareIsObservabilityNotGate:
    """The gateway must NEVER fail because of receipt emission failure.
    Receipts are observability, not authorization."""

    def test_proof_bridge_exception_does_not_break_gateway(self):
        bridge = _ExplodingProofBridge()
        client = TestClient(_make_app(bridge), raise_server_exceptions=False)
        resp = client.post("/webhook/whatsapp", json={})
        # Handler still returns 200 even though proof_bridge crashes
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_no_proof_bridge_is_safe_noop(self):
        """If platform/proof_bridge unavailable, middleware silently skips."""
        app = FastAPI()
        app.add_middleware(GatewayReceiptMiddleware, proof_bridge=None)

        @app.post("/webhook/whatsapp")
        async def whatsapp():
            return {"ok": True}

        client = TestClient(app)
        resp = client.post("/webhook/whatsapp", json={})
        assert resp.status_code == 200


class TestInstallHelper:
    def test_install_returns_true_when_platform_has_proof_bridge(self):
        class _Platform:
            proof_bridge = _RecordingProofBridge()

        app = FastAPI()
        installed = install_gateway_receipt_middleware(app, _Platform())
        assert installed is True

    def test_install_returns_false_when_platform_is_none(self):
        app = FastAPI()
        installed = install_gateway_receipt_middleware(app, None)
        assert installed is False

    def test_install_returns_false_when_proof_bridge_is_none(self):
        class _Platform:
            proof_bridge = None

        app = FastAPI()
        installed = install_gateway_receipt_middleware(app, _Platform())
        assert installed is False
