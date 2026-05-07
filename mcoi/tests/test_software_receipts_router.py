"""Purpose: verify HTTP software receipt query/replay/review-sync routes.
Governance scope: MUSIA-gated receipt inspection and review request materialization.
Dependencies: FastAPI test client, software receipt persistence store, review queue.
Invariants:
  - Query routes require musia.read through dev/auth dependency flow.
  - Review sync requires musia.write through dev/auth dependency flow.
  - List/get/replay return typed receipt envelopes.
  - Review decisions close receipt chains with terminal receipt witnesses.
  - Replay fails closed when the request chain is missing or not terminal.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.musia_auth import (
    configure_musia_auth,
    configure_musia_dev_mode,
    configure_musia_jwt,
)
from mcoi_runtime.app.routers.software_receipts import router
from mcoi_runtime.app.software_receipt_review_queue import SoftwareReceiptReviewQueue
from mcoi_runtime.core.review import ReviewEngine
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
    configure_musia_auth(None)
    configure_musia_jwt(None)
    configure_musia_dev_mode(True)
    deps.set("software_receipt_store", store)
    deps.set(
        "software_receipt_review_queue",
        SoftwareReceiptReviewQueue(
            review_engine=ReviewEngine(clock=lambda: T1),
            receipt_store=store,
        ),
    )
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


def test_review_returns_open_request_signals() -> None:
    store = SoftwareChangeReceiptStore()
    terminal = _receipt(
        receipt_id="receipt-terminal",
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        created_at=T1,
    )
    open_receipt = _receipt(
        receipt_id="receipt-open",
        request_id="request-http-open",
        stage=SoftwareChangeReceiptStage.GATE_EVALUATED,
        created_at=T1,
    )
    store.append_many((
        _receipt(receipt_id="receipt-admitted"),
        terminal,
        open_receipt,
    ))
    client = _client(store)

    response = client.get("/software/receipts/review", params={"limit": 10})
    body = response.json()

    assert response.status_code == 200
    assert body["operation"] == "review"
    assert body["count"] == 1
    assert body["requires_operator_review"] is True
    assert body["review_signal_count"] == 1
    assert body["receipts"][0]["receipt_id"] == "receipt-open"
    assert body["review_signals"] == [
        {
            "request_id": "request-http-open",
            "latest_receipt_id": "receipt-open",
            "latest_stage": "gate_evaluated",
            "latest_outcome": "ok",
            "reason": "software_change_receipt_chain_open",
        }
    ]


def test_review_empty_store_has_no_review_required() -> None:
    client = _client(SoftwareChangeReceiptStore())

    response = client.get("/software/receipts/review")
    body = response.json()

    assert response.status_code == 200
    assert body["operation"] == "review"
    assert body["count"] == 0
    assert body["requires_operator_review"] is False
    assert body["review_signal_count"] == 0
    assert body["review_signals"] == []


def test_review_sync_materializes_open_receipt_reviews() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(
        receipt_id="receipt-open",
        request_id="request-http-open",
        stage=SoftwareChangeReceiptStage.GATE_EVALUATED,
        created_at=T1,
    ))
    client = _client(store)

    first = client.post("/software/receipts/review/sync", params={"limit": 10})
    second = client.post("/software/receipts/review/sync", params={"limit": 10})
    first_body = first.json()
    second_body = second.json()

    assert first.status_code == 200
    assert first_body["operation"] == "review_sync"
    assert first_body["count"] == 1
    assert first_body["review_request_count"] == 1
    assert first_body["pending_review_count"] == 1
    assert first_body["requires_operator_review"] is True
    assert first_body["review_requests"][0]["request_id"] == (
        "software-receipt-review:request-http-open"
    )
    assert first_body["review_requests"][0]["scope"]["scope_type"] == "software_receipt_chain"
    assert first_body["review_requests"][0]["metadata"]["latest_receipt_id"] == "receipt-open"
    assert second.status_code == 200
    assert second_body["count"] == 0
    assert second_body["review_request_count"] == 0
    assert second_body["pending_review_count"] == 1


def test_review_requests_list_and_decision_resolve_pending_request() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(
        receipt_id="receipt-open",
        request_id="request-http-open",
        stage=SoftwareChangeReceiptStage.GATE_EVALUATED,
        created_at=T1,
    ))
    client = _client(store)
    sync_body = client.post("/software/receipts/review/sync").json()
    request_id = sync_body["review_requests"][0]["request_id"]

    pending_response = client.get("/software/receipts/review/requests")
    decision_response = client.post(
        f"/software/receipts/review/requests/{request_id}/decision",
        json={
            "reviewer_id": "operator-http",
            "approved": True,
            "comment": "closure evidence accepted",
        },
    )
    final_pending = client.get("/software/receipts/review/requests")
    final_review = client.get("/software/receipts/review")
    replay = client.get("/software/receipts/replay/request-http-open")
    pending_body = pending_response.json()
    decision_body = decision_response.json()
    replay_body = replay.json()

    assert pending_response.status_code == 200
    assert pending_body["operation"] == "review_requests"
    assert pending_body["review_request_count"] == 1
    assert pending_body["review_requests"][0]["request_id"] == request_id
    assert decision_response.status_code == 200
    assert decision_body["operation"] == "review_decision"
    assert decision_body["review_decision"]["request_id"] == request_id
    assert decision_body["review_decision"]["reviewer_id"] == "operator-http"
    assert decision_body["review_decision"]["status"] == "approved"
    assert decision_body["gate_allowed"] is True
    assert decision_body["pending_review_count"] == 0
    assert final_pending.json()["review_request_count"] == 0
    assert final_review.json()["requires_operator_review"] is False
    assert replay.status_code == 200
    assert replay_body["terminal_closed"] is True
    assert replay_body["receipts"][-1]["stage"] == "terminal_closed"
    assert replay_body["receipts"][-1]["metadata"]["review_decision_id"] == (
        decision_body["review_decision"]["decision_id"]
    )


def test_review_decision_missing_request_returns_bounded_404() -> None:
    client = _client(SoftwareChangeReceiptStore())

    response = client.post(
        "/software/receipts/review/requests/missing-review/decision",
        json={"reviewer_id": "operator-http", "approved": False},
    )
    body = response.json()

    assert response.status_code == 404
    assert body["detail"]["error"] == "software receipt review decision unavailable"
    assert body["detail"]["type"] == "ValueError"


def test_review_decision_requires_reviewer_identity() -> None:
    client = _client(SoftwareChangeReceiptStore())

    response = client.post(
        "/software/receipts/review/requests/missing-review/decision",
        json={"reviewer_id": "", "approved": False},
    )
    body = response.json()

    assert response.status_code == 422
    assert body["detail"][0]["loc"] == ["body", "reviewer_id"]
    assert body["detail"][0]["type"] == "string_too_short"


def test_review_sync_requires_registered_review_queue() -> None:
    configure_musia_auth(None)
    configure_musia_jwt(None)
    configure_musia_dev_mode(True)
    deps.set("software_receipt_review_queue", None)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post("/software/receipts/review/sync")
    body = response.json()

    assert response.status_code == 503
    assert body["detail"]["error"] == "software_receipt_review_queue_unavailable"
