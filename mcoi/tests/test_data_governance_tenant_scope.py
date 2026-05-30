"""Cross-tenant access enforcement for the data-governance read/eval routes.

Regression test for the residual IDOR gaps left after #868/#871 (which bound the
six body-tenant *write* routes): the ``GET /summary`` read model and the
``POST /evaluate`` route were still unscoped, so an authenticated caller for
tenant A could read tenant B's governance posture.

Uses the in-repo direct-handler-call idiom (see test_route_auth_context.py):
build a fake Request carrying ``governance_context`` and invoke the route
function directly. The scope helpers are no-ops without an authenticated tenant,
so the existing no-auth suites are unaffected.
"""
from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.fixture(scope="module")
def gov():
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    import mcoi_runtime.app.server  # noqa: F401 — bootstraps deps
    from mcoi_runtime.app.routers.data import governance as g

    # Seed a record owned by tenant-a (string->enum conversion happens in the
    # classify handler), via an authenticated tenant-a request.
    g.classify_data_record(
        g.DataClassifyRequest(
            data_id="rec-scope-a", tenant_id="tenant-a", classification="pii",
            residency="us", privacy_basis="consent",
        ),
        _req({"authenticated_tenant_id": "tenant-a"}),
    )
    return g


def _req(ctx):
    return SimpleNamespace(state=SimpleNamespace(governance_context=ctx))


def _A():
    return _req({"authenticated_tenant_id": "tenant-a"})


def _B():
    return _req({"authenticated_tenant_id": "tenant-b"})


def _OP():
    return _req({"authenticated_tenant_id": "op", "jwt_scopes": frozenset({"*"})})


# ── GET /summary ────────────────────────────────────────────────────────────

def test_summary_denies_cross_tenant_read(gov):
    with pytest.raises(HTTPException) as exc:
        gov.data_governance_summary(_B(), tenant_id="tenant-a")
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_summary_same_tenant_allowed(gov):
    resp = gov.data_governance_summary(_A(), tenant_id="tenant-a")
    assert resp["tenant"]["tenant_id"] == "tenant-a"


def test_summary_none_forced_to_authenticated_tenant(gov):
    # tenant_id omitted must NOT widen to all tenants; forced to the caller.
    resp = gov.data_governance_summary(_A(), tenant_id=None)
    assert resp["tenant"]["tenant_id"] == "tenant-a"


def test_summary_operator_wildcard_may_read_cross_tenant(gov):
    resp = gov.data_governance_summary(_OP(), tenant_id="tenant-a")
    assert resp["tenant"]["tenant_id"] == "tenant-a"


def test_summary_unauthenticated_is_noop(gov):
    # Empty context (dev / no-auth) -> no enforcement, existing suites unaffected.
    resp = gov.data_governance_summary(_req({}), tenant_id="tenant-a")
    assert resp["tenant"]["tenant_id"] == "tenant-a"


# ── POST /evaluate ──────────────────────────────────────────────────────────

def test_evaluate_denies_cross_tenant(gov):
    # tenant-b evaluates tenant-a's data_id -> decision's tenant is tenant-a -> denied.
    with pytest.raises(HTTPException) as exc:
        gov.evaluate_data_handling(
            gov.DataHandlingEvaluationRequest(
                data_id="rec-scope-a", operation="external_response", target_region="us",
            ),
            _B(),
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "cross_tenant_denied"


def test_evaluate_same_tenant_allowed(gov):
    resp = gov.evaluate_data_handling(
        gov.DataHandlingEvaluationRequest(
            data_id="rec-scope-a", operation="external_response", target_region="us",
        ),
        _A(),
    )
    assert resp["governed"] is True


def test_evaluate_unauthenticated_is_noop(gov):
    resp = gov.evaluate_data_handling(
        gov.DataHandlingEvaluationRequest(
            data_id="rec-scope-a", operation="external_response", target_region="us",
        ),
        _req({}),
    )
    assert resp["governed"] is True
