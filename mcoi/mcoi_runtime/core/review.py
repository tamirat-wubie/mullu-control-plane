"""Purpose: review workflow engine — manage review lifecycle and gating.
Governance scope: review request management, decision recording, gating checks.
Dependencies: review contracts, invariant helpers.
Invariants:
  - Review-gated actions MUST NOT proceed while review is pending.
  - Expired reviews fail closed.
  - All decisions are attributed and auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from mcoi_runtime.contracts.review import (
    ReviewDecision,
    ReviewRequest,
    ReviewScope,
    ReviewScopeType,
    ReviewStatus,
)
from .invariants import ensure_non_empty_text, stable_identifier


class ReviewEngine:
    """Manages review lifecycle: submit, decide, gate, expire."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._requests: dict[str, ReviewRequest] = {}
        self._decisions: dict[str, ReviewDecision] = {}

    def submit(self, request: ReviewRequest) -> ReviewRequest:
        if request.request_id in self._requests:
            raise ValueError(f"review request already exists: {request.request_id}")
        self._requests[request.request_id] = request
        return request

    def get_request(self, request_id: str) -> ReviewRequest | None:
        return self._requests.get(request_id)

    def list_pending(self) -> tuple[ReviewRequest, ...]:
        decided = {d.request_id for d in self._decisions.values()}
        return tuple(
            r for r in sorted(self._requests.values(), key=lambda x: x.request_id)
            if r.request_id not in decided
        )

    def decide(
        self,
        *,
        request_id: str,
        reviewer_id: str,
        approved: bool,
        comment: str | None = None,
    ) -> ReviewDecision:
        ensure_non_empty_text("request_id", request_id)
        request = self._requests.get(request_id)
        if request is None:
            raise ValueError(f"review request not found: {request_id}")

        # Check expiry
        if request.expires_at and self._is_expired(request.expires_at):
            decision = ReviewDecision(
                decision_id=self._make_id(),
                request_id=request_id,
                reviewer_id=reviewer_id,
                status=ReviewStatus.EXPIRED,
                decided_at=self._clock(),
                comment="review expired before decision",
            )
            self._decisions[decision.decision_id] = decision
            return decision

        status = ReviewStatus.APPROVED if approved else ReviewStatus.REJECTED
        decision = ReviewDecision(
            decision_id=self._make_id(),
            request_id=request_id,
            reviewer_id=reviewer_id,
            status=status,
            decided_at=self._clock(),
            comment=comment,
        )
        self._decisions[decision.decision_id] = decision
        return decision

    def is_review_resolved(self, request_id: str) -> bool:
        """Check if a review request has been resolved (approved, rejected, or expired)."""
        for d in self._decisions.values():
            if d.request_id == request_id and d.is_resolved:
                return True
        return False

    def is_review_approved(self, request_id: str) -> bool:
        """Check if a review request has been approved."""
        for d in self._decisions.values():
            if d.request_id == request_id and d.is_approved:
                return True
        return False

    def check_gate(self, request_id: str) -> tuple[bool, str]:
        """Check if a review-gated action can proceed. Returns (allowed, reason)."""
        request = self._requests.get(request_id)
        if request is None:
            return False, "review request not found"

        if not self.is_review_resolved(request_id):
            return False, "review pending"

        if self.is_review_approved(request_id):
            return True, "review approved"

        return False, "review not approved"

    def _is_expired(self, expires_at: str) -> bool:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            now = datetime.fromisoformat(self._clock().replace("Z", "+00:00"))
            return now >= expiry
        except ValueError:
            return False

    def _make_id(self) -> str:
        return stable_identifier("review-decision", {
            "count": len(self._decisions),
            "time": self._clock(),
        })
