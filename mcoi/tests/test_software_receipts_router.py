"""Purpose: verify HTTP software receipt query/replay routes.
Governance scope: read-only MUSIA-gated receipt inspection.
Dependencies: FastAPI test client and software receipt persistence store.
Invariants:
  - Routes require musia.read through dev/auth dependency flow.
  - List/get/replay return typed receipt envelopes.
  - Replay fails closed when the request chain is missing or not terminal.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.musia_auth import configure_musia_dev_mode
from mcoi_runtime.app.routers.software_receipts import router
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _receipt(
    *,
    receipt_id: str,
    request_id: str = "request-http-1",
    stage: SoftwareChangeReceiptStage = SoftwareChangeReceiptStage.REQUEST_ADMITTED,
    created_at: str = T0,
) -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id=receipt_id,
        request_id=request_id,
        stage=stage,
        cause=f"{stage.value} cause",
        outcome="ok",
        target_refs=(f"target:{stage.value}",),
        constraint_refs=("constraint:software_change_lifecycle_v1",),
        evidence_refs=(f"evidence:{stage.value}",),
        created_at=created_at,
    )


def _client(store: SoftwareChangeReceiptStore) -> TestClient:
    configure_musia_dev_mode(True)
    deps.set("software_receipt_store", store)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_filters_by_request_and_stage() -> None:
    store = SoftwareChangeReceiptStore()
    admitted = _receipt(receipt_id="receipt-admitted")
    terminal = _receipt(
        receipt_id="receipt-terminal",
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        created_at=T1,
    )
    other = _receipt(receipt_id="receipt-other", request_id="request-http-2")
    store.append_many((admitted, terminal, other))
    client = _client(store)

    response = client.get(
        "/software/receipts",
        params={
            "request_id": "request-http-1",
            "stage": "terminal_closed",
            "limit": 10,
        },
        headers={"X-Tenant-ID": "tenant-http"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["operation"] == "list"
    assert body["tenant_id"] == "tenant-http"
    assert body["count"] == 1
    assert body["receipts"][0]["receipt_id"] == terminal.receipt_id
    assert body["receipts"][0]["stage"] == "terminal_closed"


def test_get_receipt_by_id_returns_found_flag() -> None:
    store = SoftwareChangeReceiptStore()
    receipt = _receipt(receipt_id="receipt-get")
    store.append(receipt)
    client = _client(store)

    found = client.get("/software/receipts/receipt-get")
    missing = client.get("/software/receipts/missing-receipt")

    assert found.status_code == 200
    assert found.json()["found"] is True
    assert found.json()["receipts"][0]["receipt_id"] == "receipt-get"
    assert missing.status_code == 200
    assert missing.json()["found"] is False
    assert missing.json()["receipts"] == []


def test_replay_returns_terminal_chain() -> None:
    store = SoftwareChangeReceiptStore()
    admitted = _receipt(receipt_id="receipt-admitted")
    terminal = _receipt(
        receipt_id="receipt-terminal",
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        created_at=T1,
    )
    store.append_many((admitted, terminal))
    client = _client(store)

    response = client.get("/software/receipts/replay/request-http-1")
    body = response.json()

    assert response.status_code == 200
    assert body["operation"] == "replay"
    assert body["terminal_closed"] is True
    assert body["count"] == 2
    assert [receipt["receipt_id"] for receipt in body["receipts"]] == [
        "receipt-admitted",
        "receipt-terminal",
    ]


def test_replay_missing_request_returns_bounded_404() -> None:
    client = _client(SoftwareChangeReceiptStore())

    response = client.get("/software/receipts/replay/missing-request")
    body = response.json()

    assert response.status_code == 404
    assert body["detail"]["error"] == "receipt replay unavailable"
    assert body["detail"]["type"] == "PersistenceError"
