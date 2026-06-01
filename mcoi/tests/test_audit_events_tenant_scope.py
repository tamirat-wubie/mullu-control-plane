"""Cross-tenant scoping for the governed event-bus history listing.

audit.list_events returned event_bus.history() -- every tenant's GovernedEvents
(each carries tenant_id) with no filter, so any caller could read other tenants'
governance event stream. It now filters to the caller's tenant via
scoped_listing_tenant (operators with wildcard scope and unauthenticated dev
requests still see all), mirroring the scheduler list_jobs fix.
"""

from __future__ import annotations

from mcoi_runtime.app.routers import audit


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.read"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


def _unauth() -> _Req:
    return _Req({})


class _Event:
    def __init__(self, tenant_id, event_id):
        self.tenant_id = tenant_id
        self.event_id = event_id
        self.event_type = "t"
        self.source = "s"
        self.published_at = "now"


class _Bus:
    def history(self, event_type=None, limit=50):
        return [_Event("tenant-a", "ea"), _Event("tenant-b", "eb")]


def test_list_events_filters_to_own_tenant(monkeypatch):
    monkeypatch.setattr(audit.deps, "event_bus", _Bus())
    result = audit.list_events(_authed("tenant-a"))
    assert result["count"] == 1
    assert [e["id"] for e in result["events"]] == ["ea"]


def test_list_events_operator_sees_all(monkeypatch):
    monkeypatch.setattr(audit.deps, "event_bus", _Bus())
    result = audit.list_events(_authed("tenant-a", operator=True))
    assert result["count"] == 2


def test_list_events_unauthenticated_sees_all(monkeypatch):
    monkeypatch.setattr(audit.deps, "event_bus", _Bus())
    result = audit.list_events(_unauth())
    assert result["count"] == 2
