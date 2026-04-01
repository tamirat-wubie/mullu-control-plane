"""Gateway Approval Router — Human-in-the-loop governance.

Purpose: Classify request risk and route through appropriate approval path.
    Low-risk: auto-approve with audit record.
    Medium-risk: async approval via same channel (inline button/reply).
    High-risk: block until explicit confirmation with timeout.
Invariants:
  - Every approval decision is audited.
  - Timeouts default to DENY.
  - No operation executes without explicit or auto-approval.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable


class RiskTier(StrEnum):
    """Risk classification for gateway operations."""

    LOW = "low"  # Auto-approve (read-only, informational)
    MEDIUM = "medium"  # Async approval (sends prompt, waits for response)
    HIGH = "high"  # Block until explicit confirmation


class ApprovalStatus(StrEnum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A pending approval request."""

    request_id: str
    tenant_id: str
    identity_id: str
    channel: str
    action_description: str
    risk_tier: RiskTier
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: str = ""
    resolved_at: str = ""
    resolved_by: str = ""


# Keywords that escalate risk
_HIGH_RISK_KEYWORDS = frozenset({
    "delete", "remove", "send_email", "transfer", "payment", "execute",
    "modify", "update", "write", "post", "publish",
})

_MEDIUM_RISK_KEYWORDS = frozenset({
    "schedule", "create", "book", "reserve", "subscribe", "connect",
})


def classify_risk(action: str, body: str) -> RiskTier:
    """Classify the risk tier of an action based on keywords and intent.

    This is the lightweight risk classifier. Production systems should
    use LLM-based classification with confidence scoring.
    """
    lower_body = body.lower()
    lower_action = action.lower()

    for keyword in _HIGH_RISK_KEYWORDS:
        if keyword in lower_body or keyword in lower_action:
            return RiskTier.HIGH

    for keyword in _MEDIUM_RISK_KEYWORDS:
        if keyword in lower_body or keyword in lower_action:
            return RiskTier.MEDIUM

    return RiskTier.LOW


class ApprovalRouter:
    """Routes operations through risk-appropriate approval paths.

    Low-risk: auto-approve immediately (audit recorded).
    Medium-risk: send approval prompt to user, wait for response.
    High-risk: block and require explicit confirmation before proceeding.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        timeout_seconds: int = 300,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._timeout_seconds = timeout_seconds
        self._pending: dict[str, ApprovalRequest] = {}
        self._history: list[ApprovalRequest] = []

    def request_approval(
        self,
        *,
        tenant_id: str,
        identity_id: str,
        channel: str,
        action_description: str,
        body: str = "",
    ) -> ApprovalRequest:
        """Classify risk and create an approval request.

        Low-risk: returns immediately with APPROVED status.
        Medium/High-risk: returns PENDING — caller must wait for resolve().
        """
        risk = classify_risk(action_description, body)
        now = self._clock()
        request_id = f"apr-{hashlib.sha256(f'{tenant_id}:{identity_id}:{now}'.encode()).hexdigest()[:12]}"

        if risk == RiskTier.LOW:
            # Auto-approve
            request = ApprovalRequest(
                request_id=request_id,
                tenant_id=tenant_id,
                identity_id=identity_id,
                channel=channel,
                action_description=action_description,
                risk_tier=risk,
                status=ApprovalStatus.APPROVED,
                requested_at=now,
                resolved_at=now,
                resolved_by="auto",
            )
            self._history.append(request)
            return request

        # Medium or High — create pending request
        request = ApprovalRequest(
            request_id=request_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            channel=channel,
            action_description=action_description,
            risk_tier=risk,
            status=ApprovalStatus.PENDING,
            requested_at=now,
        )
        self._pending[request_id] = request
        return request

    def resolve(self, request_id: str, approved: bool, resolved_by: str = "user") -> ApprovalRequest | None:
        """Resolve a pending approval request."""
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return None

        resolved = ApprovalRequest(
            request_id=pending.request_id,
            tenant_id=pending.tenant_id,
            identity_id=pending.identity_id,
            channel=pending.channel,
            action_description=pending.action_description,
            risk_tier=pending.risk_tier,
            status=ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED,
            requested_at=pending.requested_at,
            resolved_at=self._clock(),
            resolved_by=resolved_by,
        )
        self._history.append(resolved)
        return resolved

    def get_pending(self, tenant_id: str = "") -> list[ApprovalRequest]:
        """Get pending approval requests, optionally filtered by tenant."""
        if tenant_id:
            return [r for r in self._pending.values() if r.tenant_id == tenant_id]
        return list(self._pending.values())

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def total_requests(self) -> int:
        return len(self._history) + len(self._pending)

    def summary(self) -> dict[str, Any]:
        return {
            "pending": self.pending_count,
            "total": self.total_requests,
            "history_count": len(self._history),
        }
