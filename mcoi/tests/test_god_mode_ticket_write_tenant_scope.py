"""Cross-tenant scoping for god-mode ticket consume/revoke.

god-mode tickets are tenant-bound (GodModeTicket.tenant_id). consume_ticket fed
the engine's tenant gate from a *request-body* field (req.expected_tenant_id),
which the caller controls -- so the gate was effectively absent. revoke_ticket
bound the claimed actor but never checked the ticket's tenant. Both now fetch the
ticket and enforce_tenant_scope on its tenant before the mutation, so a caller
acting on another tenant's ticket is rejected (403). No-op for operators (wildcard
scope) and unauthenticated dev requests.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import god_mode
from mcoi_runtime.core.god_mode_engine import GodModeEngineError


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(tenant_id: str, *, operator: bool = False) -> _Req:
    scopes = frozenset({"*"}) if operator else frozenset({"musia.write"})
    return _Req({"authenticated_tenant_id": tenant_id, "jwt_scopes": scopes})


class _Ticket:
    tenant_id = "tenant-b"


class _Engine:
    def get_ticket(self, ticket_id):
        return _Ticket()


class _MissingEngine:
    def get_ticket(self, ticket_id):
        raise GodModeEngineError("not found")


class _ConsumeReq:
    outcome = "success"
    pre_state: dict = {}
    post_state: dict = {}
    detail: dict = {}
    failure_reason = ""
    expected_tenant_id = "tenant-b"  # caller-supplied -- must not be trusted


class _RevokeReq:
    actor_id = ""
    reason = "test"


def test_consume_ticket_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(god_mode, "get_engine", lambda: _Engine())
    with pytest.raises(HTTPException) as exc:
        god_mode.consume_ticket("t-1", _ConsumeReq(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_revoke_ticket_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(god_mode, "get_engine", lambda: _Engine())
    with pytest.raises(HTTPException) as exc:
        god_mode.revoke_ticket("t-1", _RevokeReq(), _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_consume_ticket_missing_is_404(monkeypatch):
    monkeypatch.setattr(god_mode, "get_engine", lambda: _MissingEngine())
    with pytest.raises(HTTPException) as exc:
        god_mode.consume_ticket("missing", _ConsumeReq(), _authed("tenant-a"))
    assert exc.value.status_code == 404


def test_revoke_ticket_missing_is_404(monkeypatch):
    monkeypatch.setattr(god_mode, "get_engine", lambda: _MissingEngine())
    with pytest.raises(HTTPException) as exc:
        god_mode.revoke_ticket("missing", _RevokeReq(), _authed("tenant-a"))
    assert exc.value.status_code == 404
