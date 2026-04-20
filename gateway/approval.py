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


import re as _re

# Precompiled word-boundary patterns for risk classification
_HIGH_RISK_RE = _re.compile(
    r"\b(?:" + "|".join(_re.escape(k) for k in _HIGH_RISK_KEYWORDS) + r")\b",
    _re.IGNORECASE,
)
_MEDIUM_RISK_RE = _re.compile(
    r"\b(?:" + "|".join(_re.escape(k) for k in _MEDIUM_RISK_KEYWORDS) + r")\b",
    _re.IGNORECASE,
)


def classify_risk(action: str, body: str) -> RiskTier:
    """Classify the risk tier of an action based on word-boundary keyword matching.

    Uses regex word boundaries to avoid false positives on substrings
    (e.g., "deleted_at" won't match "delete").
    """
    text = f"{action} {body}"

    if _HIGH_RISK_RE.search(text):
        return RiskTier.HIGH

    if _MEDIUM_RISK_RE.search(text):
        return RiskTier.MEDIUM

    return RiskTier.LOW


class ApprovalRouter:
    """Routes operations through risk-appropriate approval paths.

    Low-risk: auto-approve immediately (audit recorded).
    Medium-risk: send approval prompt to user, wait for response.
    High-risk: block and require explicit confirmation before proceeding.
    """

    MAX_PENDING = 10_000
    MAX_HISTORY = 100_000

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

    def _parse_timestamp(self, value: str) -> datetime | None:
        """Parse an ISO timestamp, returning None when parsing fails."""
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _is_expired(self, request: ApprovalRequest, now: datetime) -> bool:
        """Return True when a pending request is past its timeout window."""
        requested_at = self._parse_timestamp(request.requested_at)
        if requested_at is None:
            return True
        return (now - requested_at).total_seconds() >= self._timeout_seconds

    def _append_history(self, request: ApprovalRequest) -> None:
        """Append a resolved request while preserving bounded history size."""
        self._history.append(request)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]

    def _expire_pending(self, request_id: str, pending: ApprovalRequest, now_text: str) -> ApprovalRequest:
        """Expire a pending request and record it in history."""
        expired = ApprovalRequest(
            request_id=pending.request_id,
            tenant_id=pending.tenant_id,
            identity_id=pending.identity_id,
            channel=pending.channel,
            action_description=pending.action_description,
            risk_tier=pending.risk_tier,
            status=ApprovalStatus.EXPIRED,
            requested_at=pending.requested_at,
            resolved_at=now_text,
            resolved_by="timeout",
        )
        self._append_history(expired)
        return expired

    def _prune_expired_pending(self, now_text: str | None = None) -> None:
        """Expire all stale pending requests."""
        current_text = now_text or self._clock()
        now = self._parse_timestamp(current_text)
        if now is None:
            now = datetime.now(timezone.utc)
            current_text = now.isoformat()

        expired_ids = [
            request_id
            for request_id, pending in self._pending.items()
            if self._is_expired(pending, now)
        ]
        for request_id in expired_ids:
            pending = self._pending.pop(request_id, None)
            if pending is not None:
                self._expire_pending(request_id, pending, current_text)

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
        self._prune_expired_pending(now)
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
            self._append_history(request)
            return request

        # Evict oldest pending if at capacity
        if len(self._pending) >= self.MAX_PENDING:
            oldest_id = next(iter(self._pending))
            self._pending.pop(oldest_id)

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
        now_text = self._clock()
        now = self._parse_timestamp(now_text)
        if now is None:
            now = datetime.now(timezone.utc)
            now_text = now.isoformat()
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return None
        if self._is_expired(pending, now):
            return self._expire_pending(request_id, pending, now_text)

        resolved = ApprovalRequest(
            request_id=pending.request_id,
            tenant_id=pending.tenant_id,
            identity_id=pending.identity_id,
            channel=pending.channel,
            action_description=pending.action_description,
            risk_tier=pending.risk_tier,
            status=ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED,
            requested_at=pending.requested_at,
            resolved_at=now_text,
            resolved_by=resolved_by,
        )
        self._append_history(resolved)
        return resolved

    def get_pending(self, tenant_id: str = "") -> list[ApprovalRequest]:
        """Get pending approval requests, optionally filtered by tenant."""
        self._prune_expired_pending()
        if tenant_id:
            return [r for r in self._pending.values() if r.tenant_id == tenant_id]
        return list(self._pending.values())

    @property
    def pending_count(self) -> int:
        self._prune_expired_pending()
        return len(self._pending)

    @property
    def total_requests(self) -> int:
        self._prune_expired_pending()
        return len(self._history) + len(self._pending)

    def summary(self) -> dict[str, Any]:
        return {
            "pending": self.pending_count,
            "total": self.total_requests,
            "history_count": len(self._history),
        }
