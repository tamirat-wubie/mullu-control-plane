"""Persistence-layer tenant defense-in-depth -- temporal scheduler store.

Second store wired to request_tenant_guard.assert_owns (the guard semantics and
the HTTP 403 mapping are covered in test_request_tenant_guard.py). Here we prove
TemporalSchedulerStore.get_action refuses to hand a schedule to a bound foreign
tenant while staying a no-op for same-tenant / operator / unbound callers.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.temporal_runtime import TemporalActionRequest
from mcoi_runtime.core.request_tenant_guard import (
    CrossTenantRecordError,
    bind_request_tenant,
    reset_request_tenant,
)
from mcoi_runtime.core.temporal_scheduler import ScheduledTemporalAction
from mcoi_runtime.persistence.temporal_scheduler_store import TemporalSchedulerStore

NOW = "2026-06-02T00:00:00+00:00"


def _scheduled(*, schedule_id: str, tenant_id: str) -> ScheduledTemporalAction:
    request = TemporalActionRequest(
        action_id="act-1",
        tenant_id=tenant_id,
        actor_id="user-a",
        action_type="reminder",
        requested_at=NOW,
        execute_at=NOW,
    )
    return ScheduledTemporalAction(
        schedule_id=schedule_id,
        tenant_id=tenant_id,
        action=request,
        execute_at=NOW,
    )


@pytest.fixture(autouse=True)
def _isolate_binding():
    yield
    bind_request_tenant(None)


def test_get_action_blocks_cross_tenant():
    store = TemporalSchedulerStore()
    store.save_action(_scheduled(schedule_id="sched-1", tenant_id="tenant-b"))
    token = bind_request_tenant("tenant-a", frozenset())  # non-operator A
    try:
        with pytest.raises(CrossTenantRecordError):
            store.get_action("sched-1")  # B's schedule must not reach A
    finally:
        reset_request_tenant(token)


def test_get_action_allows_same_tenant():
    store = TemporalSchedulerStore()
    store.save_action(_scheduled(schedule_id="sched-1", tenant_id="tenant-a"))
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        got = store.get_action("sched-1")
        assert got is not None and got.tenant_id == "tenant-a"
    finally:
        reset_request_tenant(token)


def test_get_action_operator_bypass():
    store = TemporalSchedulerStore()
    store.save_action(_scheduled(schedule_id="sched-1", tenant_id="tenant-b"))
    token = bind_request_tenant("tenant-a", frozenset({"*"}))
    try:
        got = store.get_action("sched-1")
        assert got is not None and got.tenant_id == "tenant-b"
    finally:
        reset_request_tenant(token)


def test_get_action_unbound_returns_record():
    store = TemporalSchedulerStore()
    store.save_action(_scheduled(schedule_id="sched-1", tenant_id="tenant-b"))
    got = store.get_action("sched-1")  # default posture -> no-op
    assert got is not None and got.tenant_id == "tenant-b"
