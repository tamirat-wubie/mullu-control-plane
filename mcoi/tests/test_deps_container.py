"""Purpose: pin the shared router dependency container's attribute contract.
Governance scope: dependency-injection container semantics only.
Dependencies: pytest monkeypatch, mcoi_runtime.app.routers.deps.
Invariants:
  - Public attribute writes route into the backing store (not a shadowing
    instance attribute), so ``deps.x = v``, ``deps.set("x", v)`` and
    ``monkeypatch.setattr(deps, "x", v)`` are equivalent.
  - monkeypatch.setattr/teardown round-trips cleanly: after a patched test,
    ``set()`` for that key works again (no permanent ``__getattr__`` shadow).
    This is the cross-test pollution regression — a tenant-scope test patching
    ``deps.temporal_scheduler_store`` previously poisoned later router tests.
  - Private attributes (``_store``) remain real instance state.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.app.routers.deps import _Deps


def test_set_then_attribute_read() -> None:
    d = _Deps()
    sentinel = object()
    d.set("thing", sentinel)
    assert d.thing is sentinel
    assert d.get("thing") is sentinel


def test_public_attribute_write_routes_into_store_not_instance_dict() -> None:
    d = _Deps()
    sentinel = object()
    d.thing = sentinel
    # Routed into the backing store, NOT a shadowing instance attribute.
    assert d.get("thing") is sentinel
    assert "thing" not in d.__dict__
    assert d.thing is sentinel


def test_private_attribute_stays_real_instance_state() -> None:
    d = _Deps()
    new_store: dict = {}
    d._store = new_store
    assert d.__dict__["_store"] is new_store


def test_missing_dependency_raises() -> None:
    d = _Deps()
    with pytest.raises(RuntimeError):
        d.get("absent")
    with pytest.raises(RuntimeError):
        _ = d.absent


def test_delattr_clears_store_entry() -> None:
    d = _Deps()
    d.set("thing", object())
    del d.thing
    with pytest.raises(RuntimeError):
        d.get("thing")


def test_monkeypatch_setattr_round_trip_does_not_shadow() -> None:
    """The pollution regression: a monkeypatch.setattr on a deps key must not
    leave a permanent shadow that breaks set() after teardown.

    Reproduces the mechanism that made test_finance_temporal_write_tenant_scope
    poison test_temporal_scheduler_router in the full suite.
    """
    d = _Deps()
    original = object()
    d.set("temporal_scheduler_store", original)

    with pytest.MonkeyPatch.context() as mp:
        patched = object()
        mp.setattr(d, "temporal_scheduler_store", patched)
        assert d.temporal_scheduler_store is patched

    # After teardown, the original is restored AND set() still works — no
    # shadowing instance attribute intercepts the backing store.
    assert d.temporal_scheduler_store is original
    fresh = object()
    d.set("temporal_scheduler_store", fresh)
    assert d.temporal_scheduler_store is fresh
    assert "temporal_scheduler_store" not in d.__dict__
