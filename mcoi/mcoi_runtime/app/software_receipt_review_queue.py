"""Purpose: convert open software receipt chains into canonical review requests.
Governance scope: read-only receipt inspection and ReviewEngine submission only.
Dependencies: review engine, review contracts, and software receipt persistence.
Invariants:
  - Receipt state is never mutated by review queue synchronization.
  - One open software request chain maps to one stable review request id.
  - Review metadata binds latest receipt, stage, constraints, and evidence.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.review import ReviewRequest, ReviewScope, ReviewScopeType
from mcoi_runtime.contracts.software_dev_loop import SoftwareChangeReceipt
from mcoi_runtime.core.review import ReviewEngine
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


SOFTWARE_RECEIPT_REVIEW_REASON = "software_change_receipt_chain_open"
SOFTWARE_RECEIPT_REVIEW_SOURCE = "software_receipts"
SOFTWARE_RECEIPT_REVIEW_REQUESTER = "software_receipt_monitor"


def software_receipt_review_request_id(receipt: SoftwareChangeReceipt) -> str:
    """Return the stable review request id for a software receipt chain."""
    if not isinstance(receipt, SoftwareChangeReceipt):
        raise TypeError("receipt must be a SoftwareChangeReceipt")
    return f"software-receipt-review:{receipt.request_id}"


class SoftwareReceiptReviewQueue:
    """Idempotently submits open software receipt chains to ReviewEngine."""

    def __init__(
        self,
        *,
        review_engine: ReviewEngine,
        receipt_store: SoftwareChangeReceiptStore,
        requester_id: str = SOFTWARE_RECEIPT_REVIEW_REQUESTER,
    ) -> None:
        if not isinstance(review_engine, ReviewEngine):
            raise TypeError("review_engine must be a ReviewEngine")
        if not isinstance(receipt_store, SoftwareChangeReceiptStore):
            raise TypeError("receipt_store must be a SoftwareChangeReceiptStore")
        requester = requester_id.strip()
        if not requester:
            raise ValueError("requester_id must be non-empty")
        self._review_engine = review_engine
        self._receipt_store = receipt_store
        self._requester_id = requester

    def sync(self, *, limit: int | None = 10) -> tuple[ReviewRequest, ...]:
        """Submit missing review requests for latest open software receipt chains."""
        submitted: list[ReviewRequest] = []
        for receipt in self._receipt_store.review_receipts(limit=limit):
            request_id = software_receipt_review_request_id(receipt)
            if self._review_engine.get_request(request_id) is not None:
                continue
            request = self._request_from_receipt(receipt, request_id=request_id)
            submitted.append(self._review_engine.submit(request))
        return tuple(submitted)

    def pending(self) -> tuple[ReviewRequest, ...]:
        """Return pending review requests produced from software receipt chains."""
        return tuple(
            request
            for request in self._review_engine.list_pending()
            if request.metadata.get("source") == SOFTWARE_RECEIPT_REVIEW_SOURCE
        )

    def summary(self) -> dict[str, Any]:
        """Return a dashboard-safe summary of pending software receipt reviews."""
        pending = self.pending()
        return {
            "pending_review_count": len(pending),
            "request_ids": [request.request_id for request in pending],
            "target_request_ids": [request.scope.target_id for request in pending],
            "source": SOFTWARE_RECEIPT_REVIEW_SOURCE,
            "governed": True,
        }

    def _request_from_receipt(
        self,
        receipt: SoftwareChangeReceipt,
        *,
        request_id: str,
    ) -> ReviewRequest:
        return ReviewRequest(
            request_id=request_id,
            requester_id=self._requester_id,
            scope=ReviewScope(
                scope_type=ReviewScopeType.SOFTWARE_RECEIPT_CHAIN,
                target_id=receipt.request_id,
                description="Software change receipt chain requires terminal closure review",
            ),
            reason=SOFTWARE_RECEIPT_REVIEW_REASON,
            requested_at=receipt.created_at,
            metadata={
                "source": SOFTWARE_RECEIPT_REVIEW_SOURCE,
                "latest_receipt_id": receipt.receipt_id,
                "latest_stage": receipt.stage.value,
                "latest_outcome": receipt.outcome,
                "target_refs": receipt.target_refs,
                "constraint_refs": receipt.constraint_refs,
                "evidence_refs": receipt.evidence_refs,
            },
        )
