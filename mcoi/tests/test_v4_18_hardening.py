"""v4.18.0 — hardening from end-to-end audit.

The v4.x audit surfaced four unbounded-growth issues in long-lived state.
Two were patched as direct deque conversions
(``CorrelationManager._completed`` and ``ReplayRecorder._completed``) —
see test_request_correlation.py and test_execution_replay.py for those.

The two remaining required design choices and land here:

1. ``CorrelationManager._active`` — TTL sweep so crashed requests
   (which never call ``complete()``) cannot accumulate forever.
2. ``TenantedRegistryStore._tenants`` — optional cap on tenant count
   so deployments where tenant_id comes from arbitrary auth claims can
   bound blast radius.

Both fixes are additive: existing constructions preserve original
behavior. Tenants on the v4.17.x line that don't set the new
parameters see no change.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.substrate.registry_store import (
    TenantedRegistryStore,
    TenantQuotaExceeded,
)


# ============================================================
# TenantedRegistryStore.max_tenants
# ============================================================


def test_default_unbounded():
    """No cap by default — preserves v4.17.x behavior."""
    store = TenantedRegistryStore()
    assert store.max_tenants is None
    # Auto-provision 100 distinct tenants — none should fail
    for i in range(100):
        store.get_or_create(f"t{i}")
    assert len(store.list_tenants()) == 100


def test_cap_on_construction():
    store = TenantedRegistryStore(max_tenants=3)
    assert store.max_tenants == 3
    store.get_or_create("a")
    store.get_or_create("b")
    store.get_or_create("c")
    assert len(store.list_tenants()) == 3


def test_cap_rejects_new_tenant_past_limit():
    store = TenantedRegistryStore(max_tenants=2)
    store.get_or_create("a")
    store.get_or_create("b")
    with pytest.raises(TenantQuotaExceeded) as exc:
        store.get_or_create("c")
    # Error message names the cap and the rejected tenant for HTTP layers
    assert "max_tenants" in str(exc.value)
    assert "'c'" in str(exc.value)
    # Cap rejection does not register the tenant
    assert "c" not in store.list_tenants()


def test_cap_does_not_block_existing_tenant_repeat_access():
    """An already-provisioned tenant remains accessible even past the cap."""
    store = TenantedRegistryStore(max_tenants=2)
    a = store.get_or_create("a")
    store.get_or_create("b")
    # Re-access "a" — must NOT raise even though we're at the cap
    a_again = store.get_or_create("a")
    assert a_again is a


def test_set_max_tenants_at_runtime():
    store = TenantedRegistryStore()
    assert store.max_tenants is None
    store.set_max_tenants(5)
    assert store.max_tenants == 5
    store.set_max_tenants(None)
    assert store.max_tenants is None


def test_lower_cap_below_existing_count_does_not_evict():
    """Lowering the cap is a forward-looking policy — existing tenants
    keep their state. Eviction would lose data; the cap only blocks
    new auto-provisioning."""
    store = TenantedRegistryStore()
    for i in range(5):
        store.get_or_create(f"t{i}")
    store.set_max_tenants(2)  # below current count
    assert len(store.list_tenants()) == 5
    # But new tenants past the cap are blocked
    with pytest.raises(TenantQuotaExceeded):
        store.get_or_create("new-tenant")


def test_get_does_not_create_under_cap():
    """get() (vs get_or_create()) never creates and never raises."""
    store = TenantedRegistryStore(max_tenants=1)
    store.get_or_create("a")
    # get() for an unknown tenant returns None — not blocked by cap
    # because it's not creating.
    assert store.get("unknown") is None
    # And it's not double-counted: still room for "a", but no new
    # tenant has appeared.
    assert len(store.list_tenants()) == 1


def test_reset_tenant_frees_capacity():
    store = TenantedRegistryStore(max_tenants=2)
    store.get_or_create("a")
    store.get_or_create("b")
    store.reset_tenant("a")
    # Now there's room for one more
    store.get_or_create("c")
    assert set(store.list_tenants()) == {"b", "c"}


def test_empty_tenant_id_still_rejected_with_value_error():
    """The empty-tenant_id check runs before the cap check —
    bad input is still bad input regardless of capacity."""
    store = TenantedRegistryStore(max_tenants=10)
    with pytest.raises(ValueError, match="tenant_id"):
        store.get_or_create("")


def test_cap_thread_safety_via_lock():
    """Cap checks happen under the store's RLock — concurrent
    auto-provisions cannot race past the cap."""
    import threading
    store = TenantedRegistryStore(max_tenants=10)
    rejections = []

    def worker(name: str):
        try:
            store.get_or_create(name)
        except TenantQuotaExceeded:
            rejections.append(name)

    threads = [
        threading.Thread(target=worker, args=(f"t{i}",))
        for i in range(50)
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(store.list_tenants()) == 10
    assert len(rejections) == 40  # exactly 40 of 50 rejected


def test_tenant_quota_exceeded_is_subclass_of_exception():
    """Catchable as a generic Exception — for HTTP layers that don't
    want to import the specific class."""
    assert issubclass(TenantQuotaExceeded, Exception)
