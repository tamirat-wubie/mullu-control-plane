"""v4.10.0 — sliding-window rate limits + quota persistence."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.musia_tenants import router as musia_tenants_router
from mcoi_runtime.substrate.constructs import State
from mcoi_runtime.substrate.persistence import (
    FileBackedPersistence,
    restore_quota_from_payload,
    snapshot_graph,
)
from mcoi_runtime.substrate.registry_store import (
    STORE,
    TenantQuota,
    TenantState,
    configure_persistence,
)


# ============================================================
# TenantQuota dataclass — rate limit fields
# ============================================================


def test_quota_default_max_writes_is_none():
    q = TenantQuota()
    assert q.max_writes_per_window is None
    assert q.window_seconds == 3600


def test_quota_rejects_negative_max_writes():
    with pytest.raises(ValueError, match="max_writes_per_window"):
        TenantQuota(max_writes_per_window=-1)


def test_quota_rejects_zero_window():
    with pytest.raises(ValueError, match="window_seconds"):
        TenantQuota(window_seconds=0)


def test_quota_rejects_negative_window():
    with pytest.raises(ValueError, match="window_seconds"):
        TenantQuota(window_seconds=-100)


# ============================================================
# Sliding window rate limit — unit
# ============================================================


def test_rate_limit_unlimited_when_max_is_none():
    state = TenantState(tenant_id="x")
    for _ in range(10):
        ok, retry, reason = state.check_rate_limit_for_write()
        assert ok
        state.record_write()


def test_rate_limit_blocks_at_threshold():
    state = TenantState(
        tenant_id="x",
        quota=TenantQuota(max_writes_per_window=3, window_seconds=60),
    )
    now = 1000.0
    for i in range(3):
        ok, _, _ = state.check_rate_limit_for_write(now=now + i)
        assert ok
        state.record_write(now=now + i)
    ok, retry, reason = state.check_rate_limit_for_write(now=now + 3)
    assert not ok
    assert "max_writes_per_window quota reached" in reason


def test_rate_limit_retry_after_calculated_from_oldest():
    state = TenantState(
        tenant_id="x",
        quota=TenantQuota(max_writes_per_window=2, window_seconds=60),
    )
    state.record_write(now=1000.0)  # oldest
    state.record_write(now=1010.0)
    ok, retry, _ = state.check_rate_limit_for_write(now=1020.0)
    assert not ok
    # oldest at 1000.0, window 60s → expires at 1060. now=1020. retry = 40s
    assert retry == 40


def test_rate_limit_evicts_expired_timestamps():
    state = TenantState(
        tenant_id="x",
        quota=TenantQuota(max_writes_per_window=2, window_seconds=60),
    )
    state.record_write(now=1000.0)
    state.record_write(now=1010.0)
    # 70s later — both expired
    ok, _, _ = state.check_rate_limit_for_write(now=1080.0)
    assert ok
    assert len(state._recent_writes) == 0


def test_rate_limit_partial_eviction():
    """Old timestamp evicted, recent one kept; allows one more write."""
    state = TenantState(
        tenant_id="x",
        quota=TenantQuota(max_writes_per_window=2, window_seconds=60),
    )
    state.record_write(now=1000.0)  # will expire
    state.record_write(now=1050.0)
    # 65s after the first → first evicted, second still in window
    ok, _, _ = state.check_rate_limit_for_write(now=1065.0)
    assert ok  # one slot freed
    assert len(state._recent_writes) == 1


def test_rate_limit_rejected_writes_do_not_consume_slot():
    """A 429'd write doesn't add to the deque (only successful writes do)."""
    state = TenantState(
        tenant_id="x",
        quota=TenantQuota(max_writes_per_window=2, window_seconds=60),
    )
    state.record_write(now=1000.0)
    state.record_write(now=1001.0)
    # third attempt at t=1002, rejected; we don't call record_write
    ok, _, _ = state.check_rate_limit_for_write(now=1002.0)
    assert not ok
    # deque still has 2, not 3
    assert len(state._recent_writes) == 2


# ============================================================
# HTTP rate limit enforcement
# ============================================================


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(musia_tenants_router)
    yield TestClient(app)
    reset_registry()


def test_http_429_when_rate_limit_exceeded(client):
    client.put(
        "/musia/tenants/acme/quota",
        json={"max_writes_per_window": 2, "window_seconds": 3600},
    )
    # Two writes succeed
    for _ in range(2):
        r = client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )
        assert r.status_code == 201
    # Third → 429
    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 429
    detail = r.json()["detail"]
    assert "rate limit" in detail["error"]
    assert detail["retry_after_seconds"] >= 1
    assert "Retry-After" in r.headers
    assert int(r.headers["Retry-After"]) >= 1


def test_rate_limit_distinct_from_construct_quota(client):
    """A tenant can hit rate limit while having construct headroom."""
    client.put(
        "/musia/tenants/acme/quota",
        json={
            "max_constructs": 100,           # plenty of headroom
            "max_writes_per_window": 2,      # but tight rate
            "window_seconds": 3600,
        },
    )
    for _ in range(2):
        client.post(
            "/constructs/state",
            headers={"X-Tenant-ID": "acme"},
            json={"configuration": {}},
        )
    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 429
    assert "rate limit" in r.json()["detail"]["error"]


def test_construct_quota_takes_priority_over_rate(client):
    """When BOTH limits would block, the construct quota is reported (cheaper check first)."""
    client.put(
        "/musia/tenants/acme/quota",
        json={
            "max_constructs": 1,             # very tight
            "max_writes_per_window": 1,      # also tight
            "window_seconds": 3600,
        },
    )
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # Both would block. Construct quota is checked first → that's the error.
    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 429
    assert "quota exceeded" in r.json()["detail"]["error"]


def test_rate_limit_per_tenant_isolated(client):
    client.put(
        "/musia/tenants/acme/quota",
        json={"max_writes_per_window": 1, "window_seconds": 3600},
    )
    # acme: write succeeds, then 429
    r = client.post("/constructs/state",
                    headers={"X-Tenant-ID": "acme"},
                    json={"configuration": {}})
    assert r.status_code == 201
    r = client.post("/constructs/state",
                    headers={"X-Tenant-ID": "acme"},
                    json={"configuration": {}})
    assert r.status_code == 429
    # foo-llc: no quota set → unlimited
    for _ in range(5):
        r = client.post("/constructs/state",
                        headers={"X-Tenant-ID": "foo-llc"},
                        json={"configuration": {}})
        assert r.status_code == 201


def test_quota_snapshot_includes_rate_fields(client):
    client.put(
        "/musia/tenants/acme/quota",
        json={
            "max_constructs": 100,
            "max_writes_per_window": 50,
            "window_seconds": 7200,
        },
    )
    client.post("/constructs/state",
                headers={"X-Tenant-ID": "acme"},
                json={"configuration": {}})
    r = client.get("/musia/tenants/acme/quota")
    body = r.json()
    assert body["max_constructs"] == 100
    assert body["max_writes_per_window"] == 50
    assert body["window_seconds"] == 7200
    assert body["writes_in_current_window"] == 1


def test_quota_endpoint_validates_rate_fields(client):
    """Pydantic enforces non-negative max_writes and positive window."""
    r = client.put(
        "/musia/tenants/acme/quota",
        json={"max_writes_per_window": -1},
    )
    assert r.status_code == 422

    r = client.put(
        "/musia/tenants/acme/quota",
        json={"window_seconds": 0},
    )
    assert r.status_code == 422


# ============================================================
# Quota persistence (round-trip with the existing snapshot machinery)
# ============================================================


def test_snapshot_omits_quota_when_none():
    from mcoi_runtime.substrate.cascade import DependencyGraph
    g = DependencyGraph()
    payload = snapshot_graph("acme", g)
    assert "quota" not in payload


def test_snapshot_includes_quota_when_supplied():
    from mcoi_runtime.substrate.cascade import DependencyGraph
    g = DependencyGraph()
    quota = TenantQuota(
        max_constructs=100,
        max_writes_per_window=50,
        window_seconds=7200,
    )
    payload = snapshot_graph("acme", g, quota=quota)
    assert payload["quota"]["max_constructs"] == 100
    assert payload["quota"]["max_writes_per_window"] == 50
    assert payload["quota"]["window_seconds"] == 7200


def test_restore_quota_returns_none_when_absent():
    payload = {"schema_version": "1", "tenant_id": "x"}
    assert restore_quota_from_payload(payload) is None


def test_restore_quota_round_trip():
    quota = TenantQuota(
        max_constructs=200,
        max_writes_per_window=10,
        window_seconds=300,
    )
    from mcoi_runtime.substrate.cascade import DependencyGraph
    g = DependencyGraph()
    payload = snapshot_graph("x", g, quota=quota)
    restored = restore_quota_from_payload(payload)
    assert restored is not None
    assert restored.max_constructs == 200
    assert restored.max_writes_per_window == 10
    assert restored.window_seconds == 300


def test_file_backend_load_with_quota(tmp_path: Path):
    """Round-trip a tenant graph + quota through the file backend."""
    backend = FileBackedPersistence(tmp_path)
    from mcoi_runtime.substrate.cascade import DependencyGraph
    g = DependencyGraph()
    g.register(State(configuration={"x": 1}))
    quota = TenantQuota(max_constructs=99, max_writes_per_window=33)

    backend.save("acme", g, quota=quota)
    result = backend.load_with_quota("acme")
    assert result is not None
    restored_g, restored_q = result
    assert len(restored_g.constructs) == 1
    assert restored_q is not None
    assert restored_q.max_constructs == 99
    assert restored_q.max_writes_per_window == 33


def test_file_backend_legacy_load_without_quota(tmp_path: Path):
    """Old `load()` still works and ignores any quota in the file."""
    backend = FileBackedPersistence(tmp_path)
    from mcoi_runtime.substrate.cascade import DependencyGraph
    g = DependencyGraph()
    g.register(State(configuration={}))
    backend.save("acme", g, quota=TenantQuota(max_constructs=10))

    # Old API: just the graph
    g_only = backend.load("acme")
    assert g_only is not None
    assert len(g_only.constructs) == 1


def test_store_snapshot_load_round_trips_quota(tmp_path: Path):
    configure_persistence(str(tmp_path))
    try:
        STORE.reset_all()
        state = STORE.get_or_create("acme")
        state.quota = TenantQuota(
            max_constructs=42,
            max_writes_per_window=7,
            window_seconds=600,
        )
        state.graph.register(State(configuration={}))

        STORE.snapshot_tenant("acme")

        # Drop, reload, verify quota came back
        STORE.reset_all()
        STORE.load_tenant("acme")
        reloaded = STORE.get("acme")
        assert reloaded is not None
        assert reloaded.quota.max_constructs == 42
        assert reloaded.quota.max_writes_per_window == 7
        assert reloaded.quota.window_seconds == 600
    finally:
        configure_persistence(None)
        STORE.reset_all()


def test_store_load_handles_old_snapshot_without_quota(tmp_path: Path):
    """A v4.4–v4.9 snapshot (no quota field) loads cleanly with default quota."""
    backend = FileBackedPersistence(tmp_path)
    from mcoi_runtime.substrate.cascade import DependencyGraph
    g = DependencyGraph()
    g.register(State(configuration={}))
    # Save WITHOUT the quota kwarg — simulates an older snapshot
    backend.save("acme", g)

    configure_persistence(str(tmp_path))
    try:
        STORE.reset_all()
        STORE.load_tenant("acme")
        state = STORE.get("acme")
        assert state is not None
        # Default unlimited quota
        assert state.quota.max_constructs is None
        assert state.quota.max_writes_per_window is None
        assert state.quota.window_seconds == 3600
    finally:
        configure_persistence(None)
        STORE.reset_all()


def test_recent_writes_not_persisted(tmp_path: Path):
    """Rate-limit timestamps are transient — they don't survive snapshot/load."""
    configure_persistence(str(tmp_path))
    try:
        STORE.reset_all()
        state = STORE.get_or_create("acme")
        state.quota = TenantQuota(max_writes_per_window=10)
        # Simulate some writes
        state.record_write(now=1000.0)
        state.record_write(now=1001.0)
        assert len(state._recent_writes) == 2

        STORE.snapshot_tenant("acme")
        STORE.reset_all()
        STORE.load_tenant("acme")
        reloaded = STORE.get("acme")
        assert reloaded is not None
        # Quota persisted, but recent writes did not
        assert reloaded.quota.max_writes_per_window == 10
        assert len(reloaded._recent_writes) == 0
    finally:
        configure_persistence(None)
        STORE.reset_all()
