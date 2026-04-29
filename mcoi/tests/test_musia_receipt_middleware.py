"""Tests for mcoi/mcoi_runtime/app/musia_receipt_middleware.py — closes the
High-severity MUSIA-coverage gap documented in
docs/MAF_RECEIPT_COVERAGE.md.

Verifies that every state-mutating request on a MUSIA-prefixed path
(/cognition, /constructs, /domains, /musia/*, /software/receipts/*, /ucja) produces a
TransitionReceipt via the platform's ProofBridge, while non-MUSIA paths
and read-only methods are left alone. The middleware is the inverse
pattern of GovernanceMiddleware: receipt-only, no guard enforcement.

Mirrors tests/test_gateway/test_receipt_middleware.py for the gateway
counterpart.
"""

from __future__ import annotations

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.musia_receipt_middleware import (
    MusiaReceiptMiddleware,
    _outcome_from_status,
    _surface_from_path,
    get_musia_receipt_middleware_status,
    install_musia_receipt_middleware,
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
    """Raises on certify — proves middleware cannot break MUSIA."""

    def certify_governance_decision(self, **kwargs):
        raise RuntimeError("simulated proof_bridge failure")


# ── _surface_from_path ──────────────────────────────────────────────


class TestSurfaceFromPath:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("/cognition/run", "cognition"),
            ("/constructs/boundary", "constructs"),
            ("/constructs/by-run/abc", "constructs"),
            ("/domains/finance/process", "domains"),
            ("/domains/cybersecurity/process", "domains"),
            ("/musia/tenants/t1/snapshot", "musia"),
            ("/musia/governance/stats/reset", "musia"),
            ("/software/receipts/review/sync", "software_receipts"),
            ("/ucja/define-job", "ucja"),
            ("/ucja/qualify", "ucja"),
            ("/api/v1/something", "other"),
            ("/random", "other"),
            ("/", "other"),
        ],
    )
    def test_paths_map_to_documented_surfaces(self, path: str, expected: str):
        assert _surface_from_path(path) == expected


# ── _outcome_from_status ────────────────────────────────────────────


class TestOutcomeFromStatus:
    @pytest.mark.parametrize(
        "code,decision,outcome",
        [
            (200, "allowed", "success"),
            (201, "allowed", "success"),
            (299, "allowed", "success"),
            (400, "denied", "denied"),
            (404, "denied", "denied"),
            (499, "denied", "denied"),
            (500, "denied", "error"),
            (502, "denied", "error"),
            (599, "denied", "error"),
        ],
    )
    def test_status_maps_to_documented_outcome(
        self, code: int, decision: str, outcome: str
    ):
        assert _outcome_from_status(code) == (decision, outcome)


# ── Middleware behavior ─────────────────────────────────────────────


def _build_app(bridge):
    app = FastAPI()
    app.add_middleware(MusiaReceiptMiddleware, proof_bridge=bridge)

    @app.post("/cognition/run")
    async def cognition_run():
        return {"ok": True}

    @app.post("/domains/finance/process")
    async def domains_finance():
        return {"ok": True}

    @app.delete("/constructs/{cid}")
    async def delete_construct(cid: str):
        return {"ok": True, "deleted": cid}

    @app.put("/musia/tenants/{tid}/quota")
    async def put_quota(tid: str):
        return {"ok": True, "tid": tid}

    @app.post("/cognition/denied-route")
    async def cognition_denied():
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="forbidden")

    @app.post("/cognition/crash")
    async def cognition_crash():
        raise RuntimeError("kaboom")

    @app.get("/cognition/status")
    async def cognition_status():
        return {"ok": True}

    @app.post("/api/v1/something")
    async def non_musia():
        return {"ok": True}

    @app.post("/software/receipts/review/sync")
    async def software_receipt_review_sync():
        return {"ok": True}

    return app


class TestMiddlewareBehavior:
    def test_post_to_musia_path_emits_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.post("/cognition/run", json={})
        assert r.status_code == 200
        assert len(bridge.calls) == 1
        call = bridge.calls[0]
        assert call["tenant_id"] == "musia:cognition"
        assert call["endpoint"] == "/cognition/run"
        assert call["decision"] == "allowed"
        assert call["guard_results"][0]["guard_name"] == "musia.entry_admission"
        assert call["guard_results"][0]["allowed"] is True

    def test_delete_on_musia_path_emits_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.delete("/constructs/abc-123")
        assert r.status_code == 200
        assert len(bridge.calls) == 1
        assert bridge.calls[0]["tenant_id"] == "musia:constructs"
        assert bridge.calls[0]["endpoint"] == "/constructs/abc-123"

    def test_put_on_musia_path_emits_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.put("/musia/tenants/t1/quota")
        assert r.status_code == 200
        assert len(bridge.calls) == 1
        assert bridge.calls[0]["tenant_id"] == "musia:musia"

    def test_post_on_software_receipt_path_emits_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.post("/software/receipts/review/sync", json={})
        assert r.status_code == 200
        assert len(bridge.calls) == 1
        assert bridge.calls[0]["tenant_id"] == "musia:software_receipts"
        assert bridge.calls[0]["endpoint"] == "/software/receipts/review/sync"

    def test_get_on_musia_path_does_not_emit_receipt(self):
        """Read-only methods produce no governed transition."""
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.get("/cognition/status")
        assert r.status_code == 200
        assert bridge.calls == []

    def test_non_musia_path_does_not_emit_receipt(self):
        """Paths outside MUSIA prefixes are left alone (the main app's
        GovernanceMiddleware covers /api/ separately)."""
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.post("/api/v1/something", json={})
        assert r.status_code == 200
        assert bridge.calls == []

    def test_4xx_response_emits_denied_receipt(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.post("/cognition/denied-route", json={})
        assert r.status_code == 403
        assert len(bridge.calls) == 1
        call = bridge.calls[0]
        assert call["decision"] == "denied"
        assert call["guard_results"][0]["allowed"] is False
        # Reason is bounded to a status-code class — full status code is
        # recoverable from the audit trail entry. v4.43.0 contract guard.
        assert call["guard_results"][0]["reason"] == "http_4xx_response"

    def test_5xx_from_handler_exception_emits_receipt_then_reraises(self):
        bridge = _RecordingProofBridge()
        client = TestClient(_build_app(bridge))
        with pytest.raises(RuntimeError, match="kaboom"):
            client.post("/cognition/crash", json={})
        # Receipt was still emitted for the boundary decision.
        assert len(bridge.calls) == 1
        call = bridge.calls[0]
        assert call["decision"] == "denied"
        assert call["guard_results"][0]["reason"] == "http_5xx_exception"

    def test_exploding_proof_bridge_does_not_break_musia(self):
        """Receipt emission is observability, not a gate. If the bridge
        raises, the MUSIA endpoint MUST still return its response."""
        bridge = _ExplodingProofBridge()
        client = TestClient(_build_app(bridge))
        r = client.post("/cognition/run", json={})
        assert r.status_code == 200  # endpoint succeeds despite bridge failure

    def test_none_proof_bridge_is_no_op(self):
        """Constructed with proof_bridge=None: middleware skips emission
        but still passes the request through."""
        client = TestClient(_build_app(None))
        r = client.post("/cognition/run", json={})
        assert r.status_code == 200


# ── install_musia_receipt_middleware ────────────────────────────────


class TestInstall:
    def test_install_with_bridge_returns_true_and_marks_status(self):
        bridge = _RecordingProofBridge()
        app = FastAPI()
        ok = install_musia_receipt_middleware(app, proof_bridge=bridge)
        assert ok is True
        status = get_musia_receipt_middleware_status()
        assert status["installed"] is True
        assert "/cognition/" in status["certified_prefixes"]
        assert "/software/receipts/" in status["certified_prefixes"]

    def test_install_without_bridge_returns_false(self):
        app = FastAPI()
        ok = install_musia_receipt_middleware(app, proof_bridge=None)
        assert ok is False
        status = get_musia_receipt_middleware_status()
        assert status["installed"] is False
        assert status["reason"] == "proof_bridge is None"
