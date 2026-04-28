"""Purpose: read-only HTTP access to software-change lifecycle receipts.
Governance scope: MUSIA read-gated receipt list/get/replay operations.
Dependencies: FastAPI, MUSIA auth dependencies, software receipt store.
Invariants:
  - All routes require musia.read.
  - Routes never mutate workspace or receipt store state.
  - Replay requires a terminally closed receipt chain.
  - Store errors are bounded at the HTTP boundary.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.musia_auth import require_read
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
    governed: bool = True


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


def _serialize_receipts(
    receipts: tuple[SoftwareChangeReceipt, ...],
) -> list[dict[str, Any]]:
    return [receipt.to_json_dict() for receipt in receipts]


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
