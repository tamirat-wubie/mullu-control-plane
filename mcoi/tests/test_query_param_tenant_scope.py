"""Cross-tenant scoping for handlers that take a scalar `tenant_id` query param.

Before this change the tenant-scope linter only inspected `{tenant_id}` path
segments and request-body models, so handlers that read stored state keyed by a
caller-supplied `tenant_id` *query parameter* (e.g. `GET /api/v1/ledger?tenant_id=`)
were never flagged. `GovernanceMiddleware` binds the *context* tenant but does
not force such a parameter to match the authenticated tenant, so an authenticated
caller for tenant A could read tenant B's ledger / finance approval packets by
naming B (or omitting the id to read all tenants).

These tests pin two things:
  1. The verified high-severity handlers now apply a scope helper -- a
     non-operator naming a different tenant is rejected with 403, an operator
     (wildcard scope) is unaffected, and a non-operator's empty claim is forced
     to its own tenant (not "all tenants").
  2. The linter's new scalar-`tenant_id` detection actually fires (and is
     satisfied by a scope helper), so the blind spot cannot silently reopen.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import finance_approval, workflow


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


# --------------------------------------------------------------------------
# get_ledger -- full semantic matrix via a tenant-capturing fake store
# --------------------------------------------------------------------------

class _CapturingStore:
    def __init__(self) -> None:
        self.seen: list[str | None] = []

    def query_ledger(self, tenant_id, limit: int = 100):
        self.seen.append(tenant_id)
        return []


def test_get_ledger_rejects_cross_tenant(monkeypatch):
    store = _CapturingStore()
    monkeypatch.setattr(workflow.deps, "store", store)
    with pytest.raises(HTTPException) as exc:
        workflow.get_ledger(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403
    assert store.seen == []  # rejected before the store is touched


def test_get_ledger_forces_own_tenant_when_unspecified(monkeypatch):
    store = _CapturingStore()
    monkeypatch.setattr(workflow.deps, "store", store)
    workflow.get_ledger(_authed("tenant-a"), tenant_id="")
    assert store.seen == ["tenant-a"]  # not "" (which would read all tenants)


def test_get_ledger_operator_passthrough(monkeypatch):
    store = _CapturingStore()
    monkeypatch.setattr(workflow.deps, "store", store)
    workflow.get_ledger(_authed("tenant-a", operator=True), tenant_id="tenant-b")
    assert store.seen == ["tenant-b"]


def test_get_ledger_unauthenticated_passthrough(monkeypatch):
    store = _CapturingStore()
    monkeypatch.setattr(workflow.deps, "store", store)
    workflow.get_ledger(_unauth(), tenant_id="tenant-b")
    assert store.seen == ["tenant-b"]  # dev / no-auth profile unaffected


# --------------------------------------------------------------------------
# create_session (write) -- cross-tenant session forgery is rejected
# --------------------------------------------------------------------------

def test_create_session_rejects_cross_tenant():
    with pytest.raises(HTTPException) as exc:
        workflow.create_session("actor-x", "tenant-b", _authed("tenant-a"))
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------
# finance approval reads -- list + operator-read-model + by-id
# --------------------------------------------------------------------------

class _FakeCase:
    tenant_id = "tenant-b"


class _FakeFinanceStore:
    def list_cases(self, *, tenant_id="", state=None):
        return ()

    def get_case(self, case_id):
        return _FakeCase()


def test_list_finance_packets_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(finance_approval, "_store", lambda: _FakeFinanceStore())
    with pytest.raises(HTTPException) as exc:
        finance_approval.list_finance_approval_packets(_authed("tenant-a"), tenant_id="tenant-b")
    assert exc.value.status_code == 403


def test_finance_operator_read_model_rejects_cross_tenant(monkeypatch):
    monkeypatch.setattr(finance_approval, "_store", lambda: _FakeFinanceStore())
    with pytest.raises(HTTPException) as exc:
        finance_approval.finance_approval_operator_read_model(
            _authed("tenant-a"), tenant_id="tenant-b",
        )
    assert exc.value.status_code == 403


def test_get_finance_packet_by_id_rejects_cross_tenant(monkeypatch):
    # Case belongs to tenant-b; a tenant-a caller must not read it by id.
    monkeypatch.setattr(finance_approval, "_store", lambda: _FakeFinanceStore())
    with pytest.raises(HTTPException) as exc:
        finance_approval.get_finance_approval_packet("case-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------
# Linter: the scalar-`tenant_id` detection fires and is satisfied by a helper
# --------------------------------------------------------------------------

def _load_linter():
    path = Path(__file__).resolve().parents[2] / "scripts" / "validate_tenant_scope_coverage.py"
    spec = importlib.util.spec_from_file_location("tenant_scope_linter", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _fn(src: str) -> ast.FunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef)
    return node


def test_linter_detects_scalar_tenant_id_param():
    mod = _load_linter()
    assert mod._has_tenant_id_param(_fn("def h(tenant_id: str = ''):\n    return 1")) is True
    assert mod._has_tenant_id_param(_fn("def h(tenant_id: str | None = None):\n    return 1")) is True
    assert mod._has_tenant_id_param(_fn("def h(other: int = 0):\n    return 1")) is False


def test_linter_scope_helper_satisfies_detection():
    mod = _load_linter()
    scoped = _fn(
        "def h(request, tenant_id: str = ''):\n"
        "    tenant_id = scoped_listing_tenant(request, tenant_id)\n"
        "    return tenant_id"
    )
    assert mod._has_tenant_id_param(scoped) is True
    assert mod._is_scoped(scoped) is True
