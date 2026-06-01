"""Cross-tenant scoping for lineage resolution (per-node tenant enforcement).

Lineage resolves by trace/output/command/artifact id with NO tenant input, so a
caller could resolve another tenant's causal graph by naming its id. Each resolved
node carries its owning tenant. `_resolve` (the chokepoint for all five lineage
handlers) now rejects a non-operator whose authenticated tenant differs from any
resolved node's tenant; the "unknown" sentinel (unresolved nodes) is skipped, and
operators (wildcard scope) / unauthenticated dev requests are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import lineage


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


def _doc(*tenant_ids):
    return {"nodes": [{"node_id": f"n{i}", "tenant_id": t} for i, t in enumerate(tenant_ids)]}


@pytest.fixture
def fake_resolver(monkeypatch):
    holder = {"doc": _doc("tenant-b")}
    monkeypatch.setattr(lineage, "resolve_lineage_uri", lambda *a, **k: holder["doc"])
    return holder


def test_trace_lineage_rejects_cross_tenant(fake_resolver):
    with pytest.raises(HTTPException) as exc:
        lineage.get_trace_lineage("trace-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_output_lineage_rejects_cross_tenant(fake_resolver):
    with pytest.raises(HTTPException) as exc:
        lineage.get_output_lineage("out-1", _authed("tenant-a"))
    assert exc.value.status_code == 403


def test_lineage_operator_passthrough(fake_resolver):
    doc = lineage.get_trace_lineage("trace-1", _authed("tenant-a", operator=True))
    assert doc is fake_resolver["doc"]


def test_lineage_unauthenticated_passthrough(fake_resolver):
    doc = lineage.get_trace_lineage("trace-1", _unauth())
    assert doc is fake_resolver["doc"]


def test_lineage_own_tenant_allowed(fake_resolver):
    fake_resolver["doc"] = _doc("tenant-a", "tenant-a")
    doc = lineage.get_trace_lineage("trace-1", _authed("tenant-a"))
    assert doc is fake_resolver["doc"]


def test_lineage_unknown_nodes_skipped(fake_resolver):
    # Unresolved nodes carry the "unknown" sentinel and must not trip the check.
    fake_resolver["doc"] = _doc("unknown", "unknown")
    doc = lineage.get_trace_lineage("trace-1", _authed("tenant-a"))
    assert doc is fake_resolver["doc"]


def test_lineage_mixed_own_and_unknown_allowed(fake_resolver):
    fake_resolver["doc"] = _doc("tenant-a", "unknown")
    doc = lineage.get_trace_lineage("trace-1", _authed("tenant-a"))
    assert doc is fake_resolver["doc"]


def test_resolve_lineage_post_rejects_cross_tenant(fake_resolver):
    class _Body:
        uri = "lineage://trace/trace-1"
    with pytest.raises(HTTPException) as exc:
        lineage.resolve_lineage(_Body(), _authed("tenant-a"))
    assert exc.value.status_code == 403
