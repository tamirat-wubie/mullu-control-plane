"""Purpose: verify software receipt review queue synchronization.
Governance scope: conversion of open receipt chains into canonical ReviewRequest records.
Dependencies: ReviewEngine, receipt store, and software receipt review queue adapter.
Invariants:
  - Open receipt chains produce stable review requests.
  - Closed receipt chains do not produce review requests.
  - Synchronization is idempotent and does not mutate receipt state.
  - Review decisions append terminal receipt witnesses and close review signals.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.app.software_receipt_review_queue import (
    SOFTWARE_RECEIPT_REVIEW_REASON,
    SOFTWARE_RECEIPT_REVIEW_SOURCE,
    SoftwareReceiptReviewQueue,
    software_receipt_review_request_id,
)
from mcoi_runtime.contracts.review import ReviewScopeType
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.core.review import ReviewEngine
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _receipt(
    *,
    receipt_id: str,
    request_id: str = "request-open",
    stage: SoftwareChangeReceiptStage = SoftwareChangeReceiptStage.REQUEST_ADMITTED,
    created_at: str = T0,
) -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id=receipt_id,
        request_id=request_id,
        stage=stage,
        cause=f"{stage.value} cause",
        outcome="ok",
        target_refs=(f"target:{request_id}",),
        constraint_refs=("constraint:software_change_lifecycle_v1",),
        evidence_refs=(f"evidence:{receipt_id}",),
        created_at=created_at,
        metadata={"stage": stage.value},
    )


def _terminal(
    *,
    receipt_id: str = "receipt-terminal",
    request_id: str = "request-closed",
) -> SoftwareChangeReceipt:
    return _receipt(
        receipt_id=receipt_id,
        request_id=request_id,
        stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
        created_at=T1,
    )


def _queue(store: SoftwareChangeReceiptStore) -> SoftwareReceiptReviewQueue:
    return SoftwareReceiptReviewQueue(
        review_engine=ReviewEngine(clock=lambda: T1),
        receipt_store=store,
    )


def test_sync_submits_review_request_for_latest_open_receipt_chain() -> None:
    store = SoftwareChangeReceiptStore()
    open_receipt = _receipt(receipt_id="receipt-open")
    store.append_many((_terminal(), open_receipt))
    queue = _queue(store)

    submitted = queue.sync()
    request = submitted[0]

    assert len(submitted) == 1
    assert request.request_id == "software-receipt-review:request-open"
    assert request.scope.scope_type is ReviewScopeType.SOFTWARE_RECEIPT_CHAIN
    assert request.scope.target_id == "request-open"
    assert request.reason == SOFTWARE_RECEIPT_REVIEW_REASON
    assert request.metadata["source"] == SOFTWARE_RECEIPT_REVIEW_SOURCE
    assert request.metadata["latest_receipt_id"] == "receipt-open"
    assert request.metadata["latest_stage"] == "request_admitted"
    assert request.metadata["constraint_refs"] == ("constraint:software_change_lifecycle_v1",)


def test_sync_is_idempotent_for_existing_review_request() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(receipt_id="receipt-open"))
    queue = _queue(store)

    first = queue.sync()
    second = queue.sync()
    pending = queue.pending()

    assert len(first) == 1
    assert second == ()
    assert pending == first
    assert pending[0].request_id == software_receipt_review_request_id(store.list_receipts()[0])


def test_sync_respects_limit_and_does_not_mutate_receipts() -> None:
    store = SoftwareChangeReceiptStore()
    first = _receipt(receipt_id="receipt-open-1", request_id="request-open-1")
    second = _receipt(receipt_id="receipt-open-2", request_id="request-open-2")
    store.append_many((first, second))
    before = store.list_receipts()
    queue = _queue(store)

    submitted = queue.sync(limit=1)
    after = store.list_receipts()

    assert len(submitted) == 1
    assert submitted[0].scope.target_id == "request-open-1"
    assert after == before
    assert store.review_receipts(limit=None) == (first, second)


def test_closed_receipt_chain_does_not_submit_review_request() -> None:
    store = SoftwareChangeReceiptStore()
    store.append_many((
        _receipt(receipt_id="receipt-admitted", request_id="request-closed"),
        _terminal(request_id="request-closed"),
    ))
    queue = _queue(store)

    submitted = queue.sync()
    summary = queue.summary()

    assert submitted == ()
    assert queue.pending() == ()
    assert summary["pending_review_count"] == 0
    assert summary["request_ids"] == []
    assert summary["governed"] is True


def test_summary_reports_pending_software_receipt_reviews() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(receipt_id="receipt-open", request_id="request-open"))
    queue = _queue(store)
    queue.sync()

    summary = queue.summary()

    assert summary["pending_review_count"] == 1
    assert summary["request_ids"] == ["software-receipt-review:request-open"]
    assert summary["target_request_ids"] == ["request-open"]
    assert summary["source"] == SOFTWARE_RECEIPT_REVIEW_SOURCE
    assert summary["governed"] is True


def test_decide_records_attributed_review_decision() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(receipt_id="receipt-open", request_id="request-open"))
    queue = _queue(store)
    request = queue.sync()[0]

    decision = queue.decide(
        request_id=request.request_id,
        reviewer_id="operator-1",
        approved=True,
        comment="terminal closure accepted",
    )
    pending = queue.pending()
    replay = store.replay_request("request-open")
    terminal_receipt = replay[-1]

    assert decision.request_id == "software-receipt-review:request-open"
    assert decision.reviewer_id == "operator-1"
    assert decision.is_approved is True
    assert decision.comment == "terminal closure accepted"
    assert pending == ()
    assert store.review_receipts() == ()
    assert terminal_receipt.stage is SoftwareChangeReceiptStage.TERMINAL_CLOSED
    assert terminal_receipt.outcome == "review_approved"
    assert terminal_receipt.metadata["review_decision_id"] == decision.decision_id
    assert terminal_receipt.metadata["gate_allowed"] is True
    assert f"review_decision:{decision.decision_id}" in terminal_receipt.evidence_refs


def test_decide_rejects_already_resolved_software_receipt_review() -> None:
    store = SoftwareChangeReceiptStore()
    store.append(_receipt(receipt_id="receipt-open", request_id="request-open"))
    queue = _queue(store)
    request = queue.sync()[0]
    queue.decide(
        request_id=request.request_id,
        reviewer_id="operator-1",
        approved=False,
        comment="closure evidence rejected",
    )

    with pytest.raises(ValueError, match="^software receipt review request already resolved$"):
        queue.decide(
            request_id=request.request_id,
            reviewer_id="operator-2",
            approved=True,
        )

    replay = store.replay_request("request-open")
    assert replay[-1].outcome == "review_rejected"
    assert replay[-1].metadata["gate_allowed"] is False


def test_decide_rejects_non_software_receipt_review_request() -> None:
    store = SoftwareChangeReceiptStore()
    queue = _queue(store)

    with pytest.raises(ValueError):
        queue.decide(
            request_id="missing-review",
            reviewer_id="operator-1",
            approved=False,
        )


def test_invalid_wiring_fails_explicitly() -> None:
    with pytest.raises(TypeError):
        SoftwareReceiptReviewQueue(
            review_engine=object(),  # type: ignore[arg-type]
            receipt_store=SoftwareChangeReceiptStore(),
        )
    with pytest.raises(TypeError):
        SoftwareReceiptReviewQueue(
            review_engine=ReviewEngine(clock=lambda: T1),
            receipt_store=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        SoftwareReceiptReviewQueue(
            review_engine=ReviewEngine(clock=lambda: T1),
            receipt_store=SoftwareChangeReceiptStore(),
            requester_id=" ",
        )
