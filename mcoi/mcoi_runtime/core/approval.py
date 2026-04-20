"""Purpose: approval engine — manage approval lifecycle and validation.
Governance scope: approval request management, decision validation, override recording.
Dependencies: approval contracts, invariant helpers.
Invariants:
  - Pending approvals must be resolved before expiry.
  - Expired approvals fail closed (no silent reuse).
  - Scope mismatch between request and action fails closed.
  - Execution count is tracked per approval.
  - Overrides are fully attributed and recorded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from mcoi_runtime.contracts.approval import (
    ApprovalDecisionRecord,
    ApprovalRequest,
    ApprovalScope,
    ApprovalScopeType,
    ApprovalStatus,
    OverrideRecord,
    OverrideType,
)
from .invariants import ensure_non_empty_text, stable_identifier


class ApprovalEngine:
    """Manages the lifecycle of approval requests, decisions, and overrides.

    Rules:
    - Requests register with explicit scope and optional expiry
    - Decisions bind to requests and carry approver identity
    - Expired approvals cannot be used
    - Scope mismatch between approval and action fails closed
    - Execution count tracks how many times an approval has been consumed
    - Overrides are explicitly recorded
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._requests: dict[str, ApprovalRequest] = {}
        self._decisions: dict[str, ApprovalDecisionRecord] = {}
        self._overrides: list[OverrideRecord] = []
        self._execution_counts: dict[str, int] = {}

    # --- Request management ---

    def submit_request(self, request: ApprovalRequest) -> ApprovalRequest:
        """Register an approval request."""
        if request.request_id in self._requests:
            raise ValueError("approval request already exists")
        self._requests[request.request_id] = request
        return request

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        return self._requests.get(request_id)

    def list_pending(self) -> tuple[ApprovalRequest, ...]:
        """List requests that have no decision yet."""
        decided = {d.request_id for d in self._decisions.values()}
        return tuple(
            r for r in sorted(self._requests.values(), key=lambda x: x.request_id)
            if r.request_id not in decided
        )

    # --- Decision management ---

    def record_decision(
        self,
        *,
        request_id: str,
        approver_id: str,
        approved: bool,
        reason: str | None = None,
    ) -> ApprovalDecisionRecord:
        """Record an approval or rejection decision."""
        ensure_non_empty_text("request_id", request_id)
        ensure_non_empty_text("approver_id", approver_id)

        request = self._requests.get(request_id)
        if request is None:
            raise ValueError("approval request unavailable")

        # Check expiry
        if request.expires_at and self._is_expired(request.expires_at):
            decision = ApprovalDecisionRecord(
                decision_id=self._make_id("approval-decision"),
                request_id=request_id,
                approver_id=approver_id,
                status=ApprovalStatus.EXPIRED,
                decided_at=self._clock(),
                reason="request expired before decision",
            )
            self._decisions[decision.decision_id] = decision
            return decision

        if request.requester_id.strip() == approver_id.strip():
            raise ValueError("requester cannot approve own request")
        if request.allowed_approver_ids and approver_id.strip() not in request.allowed_approver_ids:
            raise ValueError("approver not authorized for request")

        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        decision = ApprovalDecisionRecord(
            decision_id=self._make_id("approval-decision"),
            request_id=request_id,
            approver_id=approver_id,
            status=status,
            decided_at=self._clock(),
            reason=reason,
        )
        self._decisions[decision.decision_id] = decision
        return decision

    def get_decision(self, decision_id: str) -> ApprovalDecisionRecord | None:
        return self._decisions.get(decision_id)

    # --- Validation ---

    def validate_approval(
        self,
        decision_id: str,
        *,
        target_id: str,
        action: str,
    ) -> tuple[bool, str]:
        """Validate an approval decision against scope and state.

        Returns (valid, reason).
        """
        decision = self._decisions.get(decision_id)
        if decision is None:
            return False, "decision not found"

        if decision.is_terminal:
            return False, f"decision is terminal: {decision.status.value}"

        if not decision.is_active:
            return False, f"decision not active: {decision.status.value}"

        request = self._requests.get(decision.request_id)
        if request is None:
            return False, "original request not found"

        # Check expiry at validation time
        if request.expires_at and self._is_expired(request.expires_at):
            return False, "approval expired"

        # Scope: target must match
        if request.scope.target_id != target_id:
            return False, f"scope mismatch: approved for {request.scope.target_id}, used for {target_id}"

        # Scope: action must be allowed (if actions specified)
        if request.scope.allowed_actions and action not in request.scope.allowed_actions:
            return False, f"action {action} not in allowed actions"

        # Execution count
        used = self._execution_counts.get(decision_id, 0)
        if used >= request.scope.max_executions:
            return False, f"execution limit reached ({request.scope.max_executions})"

        return True, "valid"

    def consume_approval(self, decision_id: str) -> None:
        """Mark one execution consumed against an approval."""
        self._execution_counts[decision_id] = self._execution_counts.get(decision_id, 0) + 1

    # --- Override ---

    def record_override(self, override: OverrideRecord) -> OverrideRecord:
        """Record a manual override."""
        self._overrides.append(override)
        return override

    def list_overrides(self) -> tuple[OverrideRecord, ...]:
        return tuple(self._overrides)

    # --- Revocation ---

    def revoke(self, decision_id: str, *, reason: str) -> ApprovalDecisionRecord | None:
        """Revoke an active approval. Returns the revoked record or None."""
        decision = self._decisions.get(decision_id)
        if decision is None or not decision.is_active:
            return None

        revoked = ApprovalDecisionRecord(
            decision_id=decision.decision_id,
            request_id=decision.request_id,
            approver_id=decision.approver_id,
            status=ApprovalStatus.REVOKED,
            decided_at=decision.decided_at,
            reason=reason,
            executions_used=self._execution_counts.get(decision_id, 0),
        )
        self._decisions[decision_id] = revoked
        return revoked

    # --- Helpers ---

    def _is_expired(self, expires_at: str) -> bool:
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            now = datetime.fromisoformat(self._clock().replace("Z", "+00:00"))
            return now >= expiry
        except ValueError:
            # Fail closed: unparseable expiry is treated as expired so that
            # a malformed timestamp can never grant perpetual validity.
            return True

    def _make_id(self, prefix: str) -> str:
        return stable_identifier(prefix, {
            "count": len(self._decisions) + len(self._overrides),
            "time": self._clock(),
        })
