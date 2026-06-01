"""Cross-tenant scoping for finance-approval and temporal write-by-id endpoints.

Two mutation endpoints addressed a tenant-owned record by id with no tenant check:
- finance_approval.approve_finance_approval_packet(case_id): records an approval
  decision and closes a packet -- a caller could forge approvals on / close another
  tenant's finance packet.
- temporal_scheduler.cancel_temporal_schedule(schedule_id): cancels another
  tenant's scheduled action.

Both now enforce_tenant_scope on the fetched record's tenant before mutating; the
cross-tenant request is rejected (403) before the write. No-op for operators
(wildcard scope) and unauthenticated dev requests.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import finance_approval, temporal_scheduler


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.write"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


class _Owned:
    tenant_id = "tenant-b"


class _Body:
    """Placeholder body -- the tenant check fires before it is read."""


# -- finance approval write ------------------------------------------------

class _FinanceStore:
    def get_case(self, case_id):
        return _Owned()


def test_approve_finance_packet_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(finance_approval, "_store", lambda: _FinanceStore())
    with pytest.raises(HTTPException) as exc:
        finance_approval.approve_finance_approval_packet("case-1", _Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403


# -- temporal cancel write -------------------------------------------------

class _TemporalStore:
    def get_action(self, schedule_id):
        return _Owned()


def test_cancel_temporal_schedule_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(temporal_scheduler.deps, "temporal_scheduler_store", _TemporalStore())
    with pytest.raises(HTTPException) as exc:
        temporal_scheduler.cancel_temporal_schedule("sched-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_cancel_temporal_schedule_missing_is_404(monkeypatch):
    class _Empty:
        def get_action(self, schedule_id):
            return None

    monkeypatch.setattr(temporal_scheduler.deps, "temporal_scheduler_store", _Empty())
    with pytest.raises(HTTPException) as exc:
        temporal_scheduler.cancel_temporal_schedule("missing", _authed("tenant-a"))
    assert exc.value.status_code == 404
