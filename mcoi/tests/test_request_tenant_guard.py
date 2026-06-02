"""Persistence-layer tenant defense-in-depth (request_tenant_guard).

The router's ``enforce_tenant_scope`` is the primary tenant gate. This guard is a
SECOND line below it: a store refuses to return another tenant's record even if a
handler forgot to scope. It activates only when the middleware bound a concrete,
non-operator authenticated tenant for the request; operators, unauthenticated /
dev requests, and background / test contexts leave it a no-op.

Covered here: the guard semantics, the finance store's get_case under a bound
foreign tenant (the actual defense-in-depth), and the HTTP boundary mapping to a
bounded 403 (so a fire is a clean governed response, never a 500).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.server_http import install_global_exception_handler
from mcoi_runtime.contracts.finance_approval_packet import (
    FinancePacketRisk,
    FinancePacketState,
    InvoiceCase,
    InvoiceMoney,
)
from mcoi_runtime.core.request_tenant_guard import (
    CrossTenantRecordError,
    assert_owns,
    bind_request_tenant,
    current_request_tenant,
    reset_request_tenant,
)
from mcoi_runtime.persistence.finance_approval_store import FinanceApprovalPacketStore

NOW = "2026-06-02T00:00:00+00:00"


def _case(*, case_id: str, tenant_id: str) -> InvoiceCase:
    return InvoiceCase(
        case_id=case_id,
        tenant_id=tenant_id,
        actor_id="user-requester",
        vendor_id="vendor-acme",
        invoice_id="INV-001",
        amount=InvoiceMoney(currency="USD", minor_units=100_000),
        source_evidence_ref="evidence:invoice",
        state=FinancePacketState.REQUIRES_REVIEW,
        risk=FinancePacketRisk.HIGH,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture(autouse=True)
def _isolate_binding():
    # The binding lives in a process-wide ContextVar; make sure nothing a test
    # leaves bound bleeds into the next test.
    yield
    bind_request_tenant(None)


# --- guard semantics ---------------------------------------------------------


def test_unbound_is_noop():
    assert current_request_tenant() is None
    assert_owns("any-tenant")  # must not raise


def test_same_tenant_passes():
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        assert_owns("tenant-a")
    finally:
        reset_request_tenant(token)


def test_cross_tenant_raises():
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        with pytest.raises(CrossTenantRecordError):
            assert_owns("tenant-b")
    finally:
        reset_request_tenant(token)


def test_operator_scope_is_noop():
    token = bind_request_tenant("tenant-a", frozenset({"*"}))
    try:
        bound = current_request_tenant()
        assert bound is not None and bound.is_operator is True
        assert_owns("tenant-b")  # operator authority bypasses the guard
    finally:
        reset_request_tenant(token)


def test_record_without_tenant_passes():
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        assert_owns("")
        assert_owns(None)
    finally:
        reset_request_tenant(token)


def test_empty_authenticated_tenant_is_noop():
    token = bind_request_tenant("", frozenset())
    try:
        assert current_request_tenant() is None
        assert_owns("tenant-b")
    finally:
        reset_request_tenant(token)


def test_reset_restores_noop():
    token = bind_request_tenant("tenant-a", frozenset())
    reset_request_tenant(token)
    assert current_request_tenant() is None
    assert_owns("tenant-b")  # no raise after reset


def test_non_iterable_scopes_defaults_non_operator():
    # A malformed scopes value must fail safe to non-operator (still enforced),
    # not crash and not silently grant operator bypass.
    token = bind_request_tenant("tenant-a", object())
    try:
        with pytest.raises(CrossTenantRecordError):
            assert_owns("tenant-b")
    finally:
        reset_request_tenant(token)


# --- finance store defense-in-depth -----------------------------------------


def test_store_get_case_blocks_cross_tenant():
    store = FinanceApprovalPacketStore()
    store.save_case(_case(case_id="c1", tenant_id="tenant-b"))
    token = bind_request_tenant("tenant-a", frozenset())  # non-operator A
    try:
        with pytest.raises(CrossTenantRecordError):
            store.get_case("c1")  # B's case must not be handed to A
    finally:
        reset_request_tenant(token)


def test_store_get_case_allows_same_tenant():
    store = FinanceApprovalPacketStore()
    store.save_case(_case(case_id="c1", tenant_id="tenant-a"))
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        got = store.get_case("c1")
        assert got is not None and got.tenant_id == "tenant-a"
    finally:
        reset_request_tenant(token)


def test_store_get_case_operator_bypass():
    store = FinanceApprovalPacketStore()
    store.save_case(_case(case_id="c1", tenant_id="tenant-b"))
    token = bind_request_tenant("tenant-a", frozenset({"*"}))
    try:
        got = store.get_case("c1")
        assert got is not None and got.tenant_id == "tenant-b"
    finally:
        reset_request_tenant(token)


def test_store_get_case_unbound_returns_record():
    store = FinanceApprovalPacketStore()
    store.save_case(_case(case_id="c1", tenant_id="tenant-b"))
    # No binding -> default deployment posture (auth opt-in) -> pure no-op.
    got = store.get_case("c1")
    assert got is not None and got.tenant_id == "tenant-b"


def test_store_get_missing_case_returns_none():
    store = FinanceApprovalPacketStore()
    token = bind_request_tenant("tenant-a", frozenset())
    try:
        assert store.get_case("nope") is None  # no record -> guard never fires
    finally:
        reset_request_tenant(token)


# --- HTTP boundary mapping ---------------------------------------------------


class _Metrics:
    def inc(self, *args, **kwargs) -> None:
        pass


class _Logger:
    def log(self, *args, **kwargs) -> None:
        pass


class _LogLevels:
    ERROR = 40


def test_cross_tenant_record_error_maps_to_403():
    app = FastAPI()
    install_global_exception_handler(
        app=app, metrics=_Metrics(), platform_logger=_Logger(), log_levels=_LogLevels(),
    )

    @app.get("/raise/cross-tenant")
    def _raise():
        raise CrossTenantRecordError("finance approval packet belongs to another tenant")

    resp = TestClient(app, raise_server_exceptions=False).get("/raise/cross-tenant")
    assert resp.status_code == 403
    body = resp.json()
    assert body["error_code"] == "cross_tenant_denied"
    assert body["governed"] is True
