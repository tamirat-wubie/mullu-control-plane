"""Purpose: HTTP access to software-change lifecycle receipts and review sync.
Governance scope: MUSIA-gated receipt list/get/replay and review request materialization.
Dependencies: FastAPI, MUSIA auth dependencies, software receipt store, review queue.
Invariants:
  - Receipt query routes require musia.read.
  - Review synchronization requires musia.write.
  - Routes never mutate workspace or receipt store state.
  - Replay requires a terminally closed receipt chain.
  - Store errors are bounded at the HTTP boundary.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.musia_auth import require_read, require_write
from mcoi_runtime.app.software_receipt_review_queue import SoftwareReceiptReviewQueue
from mcoi_runtime.contracts.review import ReviewDecision, ReviewRequest
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.errors import PersistenceError
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


router = APIRouter(prefix="/software/receipts", tags=["software-receipts"])
_FALLBACK_STORE = SoftwareChangeReceiptStore()


class SoftwareReceiptEnvelope(BaseModel):
    """HTTP response envelope for software lifecycle receipts."""

    operation: str
    tenant_id: str
    count: int
    receipts: list[dict[str, Any]]
    request_id: str | None = None
    receipt_id: str | None = None
    stage: str | None = None
    found: bool | None = None
    terminal_closed: bool | None = None
    requires_operator_review: bool | None = None
    review_signal_count: int | None = None
    review_signals: list[dict[str, Any]] | None = None
    review_request_count: int | None = None
    review_requests: list[dict[str, Any]] | None = None
    pending_review_count: int | None = None
    review_decision: dict[str, Any] | None = None
    gate_allowed: bool | None = None
    gate_reason: str | None = None
    governed: bool = True


class SoftwareReceiptReviewDecisionBody(BaseModel):
    """HTTP request body for deciding a software receipt review."""

    reviewer_id: str = Field(..., min_length=1)
    approved: bool
    comment: str | None = None


def _bounded_http_error(summary: str, exc: Exception) -> dict[str, str]:
    return {"error": summary, "type": type(exc).__name__}


def _receipt_store() -> SoftwareChangeReceiptStore:
    try:
        store = deps.get("software_receipt_store")
    except RuntimeError:
        return _FALLBACK_STORE
    if not isinstance(store, SoftwareChangeReceiptStore):
        raise HTTPException(
            status_code=503,
            detail={"error": "software_receipt_store_invalid"},
        )
    return store


def _review_queue() -> SoftwareReceiptReviewQueue:
    try:
        queue = deps.get("software_receipt_review_queue")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "software_receipt_review_queue_unavailable"},
        ) from exc
    if not isinstance(queue, SoftwareReceiptReviewQueue):
        raise HTTPException(
            status_code=503,
            detail={"error": "software_receipt_review_queue_invalid"},
        )
    return queue


def _serialize_receipts(
    receipts: tuple[SoftwareChangeReceipt, ...],
) -> list[dict[str, Any]]:
    return [receipt.to_json_dict() for receipt in receipts]


def _serialize_review_requests(
    requests: tuple[ReviewRequest, ...],
) -> list[dict[str, Any]]:
    return [request.to_json_dict() for request in requests]


def _serialize_review_decision(decision: ReviewDecision) -> dict[str, Any]:
    return decision.to_json_dict()


def _review_signals(receipts: tuple[SoftwareChangeReceipt, ...]) -> list[dict[str, str]]:
    return [
        {
            "request_id": receipt.request_id,
            "latest_receipt_id": receipt.receipt_id,
            "latest_stage": receipt.stage.value,
            "latest_outcome": receipt.outcome,
            "reason": "software_change_receipt_chain_open",
        }
        for receipt in receipts
    ]


@router.get("", response_model=SoftwareReceiptEnvelope)
def list_software_receipts(
    request_id: str | None = None,
    stage: str | None = None,
    limit: int = Query(default=50, ge=1),
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """List stored lifecycle receipts with optional request/stage filters."""
    stage_filter = None
    try:
        if stage:
            stage_filter = SoftwareChangeReceiptStage(stage)
        receipts = _receipt_store().list_receipts(
            request_id=request_id,
            stage=stage_filter,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("invalid receipt stage", exc),
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt query rejected", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="list",
        tenant_id=tenant_id,
        request_id=request_id,
        stage=stage_filter.value if stage_filter is not None else None,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
    )


@router.get("/replay/{request_id}", response_model=SoftwareReceiptEnvelope)
def replay_software_receipts(
    request_id: str,
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """Replay a terminally closed receipt chain for one request."""
    try:
        receipts = _receipt_store().replay_request(request_id)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=404,
            detail=_bounded_http_error("receipt replay unavailable", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="replay",
        tenant_id=tenant_id,
        request_id=request_id,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
        terminal_closed=True,
    )


@router.post("/review/sync", response_model=SoftwareReceiptEnvelope)
def sync_software_receipt_reviews(
    limit: int = Query(default=10, ge=1),
    tenant_id: str = Depends(require_write),
) -> SoftwareReceiptEnvelope:
    """Materialize open receipt-chain signals as canonical review requests."""
    try:
        queue = _review_queue()
        submitted = queue.sync(limit=limit)
        pending = queue.pending()
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt review sync rejected", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="review_sync",
        tenant_id=tenant_id,
        count=len(submitted),
        receipts=[],
        review_request_count=len(submitted),
        review_requests=_serialize_review_requests(submitted),
        pending_review_count=len(pending),
        requires_operator_review=bool(pending),
    )


@router.get("/review/requests", response_model=SoftwareReceiptEnvelope)
def list_software_receipt_review_requests(
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """List pending canonical review requests for software receipt chains."""
    queue = _review_queue()
    pending = queue.pending()
    return SoftwareReceiptEnvelope(
        operation="review_requests",
        tenant_id=tenant_id,
        count=len(pending),
        receipts=[],
        review_request_count=len(pending),
        review_requests=_serialize_review_requests(pending),
        pending_review_count=len(pending),
        requires_operator_review=bool(pending),
    )


@router.post("/review/requests/{request_id}/decision", response_model=SoftwareReceiptEnvelope)
def decide_software_receipt_review_request(
    request_id: str,
    body: SoftwareReceiptReviewDecisionBody,
    tenant_id: str = Depends(require_write),
) -> SoftwareReceiptEnvelope:
    """Approve or reject a software receipt review request."""
    queue = _review_queue()
    try:
        decision = queue.decide(
            request_id=request_id,
            reviewer_id=body.reviewer_id,
            approved=body.approved,
            comment=body.comment,
        )
        gate_allowed = decision.is_approved
        gate_reason = "review approved" if decision.is_approved else "review not approved"
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=_bounded_http_error("software receipt review decision unavailable", exc),
        ) from exc
    pending = queue.pending()
    return SoftwareReceiptEnvelope(
        operation="review_decision",
        tenant_id=tenant_id,
        request_id=request_id,
        count=1,
        receipts=[],
        review_decision=_serialize_review_decision(decision),
        pending_review_count=len(pending),
        requires_operator_review=bool(pending),
        gate_allowed=gate_allowed,
        gate_reason=gate_reason,
    )


@router.get("/review", response_model=SoftwareReceiptEnvelope)
def review_software_receipts(
    limit: int = Query(default=10, ge=1),
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """List latest receipt for each request chain needing operator review."""
    try:
        receipts = _receipt_store().review_receipts(limit=limit)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt review query rejected", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="review",
        tenant_id=tenant_id,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
        requires_operator_review=bool(receipts),
        review_signal_count=len(receipts),
        review_signals=_review_signals(receipts),
    )


@router.get("/{receipt_id}", response_model=SoftwareReceiptEnvelope)
def get_software_receipt(
    receipt_id: str,
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """Fetch a single software lifecycle receipt by id."""
    receipt = _receipt_store().get(receipt_id)
    receipts = tuple() if receipt is None else (receipt,)
    return SoftwareReceiptEnvelope(
        operation="get",
        tenant_id=tenant_id,
        receipt_id=receipt_id,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
        found=receipt is not None,
    )
