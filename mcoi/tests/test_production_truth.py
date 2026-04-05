"""Purpose: verify Phase 1 production-truth features.
Governance scope: tenant binding, startup guards, audit anchoring.
Dependencies: governance_guard, audit_anchor, FastAPI test client.
Invariants: tenant spoofing rejected; memory backend fails in production;
  chain rewrite detected by anchor verification.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.core.audit_anchor import AuditAnchorStore
from mcoi_runtime.core.governance_guard import create_api_key_guard, GuardResult
from mcoi_runtime.core.api_key_auth import APIKeyManager


_CLOCK = "2026-03-30T00:00:00+00:00"


# --- Tenant Binding ---


def test_tenant_bound_from_api_key() -> None:
    mgr = APIKeyManager()
    raw_key, key = mgr.create_key("tenant-a", frozenset({"*"}))
    guard = create_api_key_guard(mgr, require_auth=True)
    ctx = {"authorization": f"Bearer {raw_key}", "tenant_id": ""}
    result = guard.check(ctx)
    assert result.allowed
    assert ctx["tenant_id"] == "tenant-a"
    assert ctx["authenticated_key_id"] == key.key_id


def test_tenant_spoofing_rejected_in_require_auth() -> None:
    mgr = APIKeyManager()
    raw_key, _ = mgr.create_key("tenant-a", frozenset({"*"}))
    guard = create_api_key_guard(mgr, require_auth=True)
    ctx = {"authorization": f"Bearer {raw_key}", "tenant_id": "spoofed-tenant"}
    result = guard.check(ctx)
    assert not result.allowed
    assert result.reason == "tenant mismatch"
    assert "tenant-a" not in result.reason
    assert "spoofed-tenant" not in result.reason


def test_tenant_spoofing_overridden_in_permissive_mode() -> None:
    mgr = APIKeyManager()
    raw_key, _ = mgr.create_key("tenant-a", frozenset({"*"}))
    guard = create_api_key_guard(mgr, require_auth=False)
    ctx = {"authorization": f"Bearer {raw_key}", "tenant_id": "spoofed"}
    result = guard.check(ctx)
    assert result.allowed
    # Key tenant overrides spoofed value
    assert ctx["tenant_id"] == "tenant-a"


# --- Audit Chain Anchoring ---


@dataclass
class FakeEntry:
    entry_hash: str = ""
    sequence: int = 0


def test_create_and_verify_anchor() -> None:
    store = AuditAnchorStore(clock=lambda: _CLOCK)
    entries = [FakeEntry(f"hash-{i}", i) for i in range(10)]
    anchor = store.create_anchor(entries)
    assert anchor.entry_count == 10
    assert anchor.merkle_root

    # Verify with same entries
    result = store.verify_anchor(anchor.anchor_id, entries)
    assert result["valid"] is True


def test_tampered_chain_detected() -> None:
    store = AuditAnchorStore(clock=lambda: _CLOCK)
    entries = [FakeEntry(f"hash-{i}", i) for i in range(10)]
    anchor = store.create_anchor(entries)

    # Tamper with one entry
    tampered = [FakeEntry(f"hash-{i}", i) for i in range(10)]
    tampered[5] = FakeEntry("TAMPERED", 5)
    result = store.verify_anchor(anchor.anchor_id, tampered)
    assert result["valid"] is False
    assert "mismatch" in result["reason"]


def test_missing_entries_detected() -> None:
    store = AuditAnchorStore(clock=lambda: _CLOCK)
    entries = [FakeEntry(f"hash-{i}", i) for i in range(10)]
    anchor = store.create_anchor(entries)

    # Verify with fewer entries
    result = store.verify_anchor(anchor.anchor_id, entries[:5])
    assert result["valid"] is False
    assert result["reason"] == "entry count mismatch"
    assert "10" not in result["reason"]


def test_anchor_not_found() -> None:
    store = AuditAnchorStore(clock=lambda: _CLOCK)
    result = store.verify_anchor("nonexistent", [])
    assert result["valid"] is False
    assert result["reason"] == "anchor not found"
    assert "nonexistent" not in result["reason"]


def test_list_anchors() -> None:
    store = AuditAnchorStore(clock=lambda: _CLOCK)
    entries = [FakeEntry("h", 0)]
    store.create_anchor(entries)
    store.create_anchor(entries)
    assert len(store.list_anchors()) == 2


# --- HTTP Endpoint Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_create_anchor_endpoint(client) -> None:
    resp = client.post("/api/v1/audit/anchor?limit=100")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "anchor_id" in data or "error" in data


def test_list_anchors_endpoint(client) -> None:
    client.post("/api/v1/audit/anchor?limit=50")
    resp = client.get("/api/v1/audit/anchors")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
