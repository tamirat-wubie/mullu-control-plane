"""Phase 229C — Tenant Quota Enforcement Engine.

Purpose: Enforce resource quotas per tenant — API calls, storage, compute,
    tokens — with configurable limits, grace periods, and overage tracking.
Dependencies: None (stdlib only).
Invariants:
  - Quota checks are O(1).
  - Grace overage allows burst within configured percentage.
  - All quota events are auditable.
  - Quotas reset on configured intervals.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any


@unique
class QuotaDecision(Enum):
    ALLOWED = "allowed"
    GRACE = "grace"         # allowed but in overage window
    DENIED = "denied"       # hard limit exceeded
    NO_QUOTA = "no_quota"   # no quota configured


@dataclass
class QuotaLimit:
    """A quota limit for a specific resource."""
    resource: str
    limit: int
    grace_percent: float = 10.0   # allow 10% overage
    reset_interval_seconds: float = 3600.0  # hourly reset

    @property
    def hard_limit(self) -> int:
        return int(self.limit * (1.0 + self.grace_percent / 100.0))


@dataclass
class QuotaUsage:
    """Tracks usage against a quota limit."""
    resource: str
    current: int = 0
    total_allowed: int = 0
    total_denied: int = 0
    total_grace: int = 0
    last_reset_at: float = field(default_factory=time.time)

    def reset(self) -> None:
        self.current = 0
        self.last_reset_at = time.time()


@dataclass(frozen=True)
class QuotaCheckResult:
    """Result of a quota check."""
    tenant_id: str
    resource: str
    decision: QuotaDecision
    current: int
    limit: int
    remaining: int


class TenantQuotaEngine:
    """Enforces per-tenant resource quotas."""

    def __init__(self):
        self._quotas: dict[str, dict[str, QuotaLimit]] = {}  # tenant -> resource -> limit
        self._usage: dict[str, dict[str, QuotaUsage]] = {}   # tenant -> resource -> usage
        self._total_checks = 0
        self._total_denials = 0

    def set_quota(self, tenant_id: str, resource: str, limit: int,
                  grace_percent: float = 10.0,
                  reset_interval: float = 3600.0) -> QuotaLimit:
        if tenant_id not in self._quotas:
            self._quotas[tenant_id] = {}
            self._usage[tenant_id] = {}
        quota = QuotaLimit(
            resource=resource, limit=limit,
            grace_percent=grace_percent,
            reset_interval_seconds=reset_interval,
        )
        self._quotas[tenant_id][resource] = quota
        if resource not in self._usage[tenant_id]:
            self._usage[tenant_id][resource] = QuotaUsage(resource=resource)
        return quota

    def check_and_consume(self, tenant_id: str, resource: str,
                          amount: int = 1) -> QuotaCheckResult:
        """Check quota and consume if allowed."""
        self._total_checks += 1

        quotas = self._quotas.get(tenant_id, {})
        quota = quotas.get(resource)
        if not quota:
            return QuotaCheckResult(
                tenant_id=tenant_id, resource=resource,
                decision=QuotaDecision.NO_QUOTA,
                current=0, limit=0, remaining=0,
            )

        usage = self._usage[tenant_id][resource]

        # Check if reset is needed
        elapsed = time.time() - usage.last_reset_at
        if elapsed >= quota.reset_interval_seconds:
            usage.reset()

        new_total = usage.current + amount

        if new_total <= quota.limit:
            usage.current = new_total
            usage.total_allowed += amount
            return QuotaCheckResult(
                tenant_id=tenant_id, resource=resource,
                decision=QuotaDecision.ALLOWED,
                current=new_total, limit=quota.limit,
                remaining=quota.limit - new_total,
            )
        elif new_total <= quota.hard_limit:
            usage.current = new_total
            usage.total_grace += amount
            return QuotaCheckResult(
                tenant_id=tenant_id, resource=resource,
                decision=QuotaDecision.GRACE,
                current=new_total, limit=quota.limit,
                remaining=quota.hard_limit - new_total,
            )
        else:
            usage.total_denied += amount
            self._total_denials += 1
            return QuotaCheckResult(
                tenant_id=tenant_id, resource=resource,
                decision=QuotaDecision.DENIED,
                current=usage.current, limit=quota.limit,
                remaining=0,
            )

    def get_usage(self, tenant_id: str) -> dict[str, Any]:
        usage = self._usage.get(tenant_id, {})
        return {
            r: {
                "current": u.current,
                "limit": self._quotas[tenant_id][r].limit,
                "total_allowed": u.total_allowed,
                "total_denied": u.total_denied,
                "total_grace": u.total_grace,
            }
            for r, u in usage.items()
        }

    def summary(self) -> dict[str, Any]:
        return {
            "tenants_with_quotas": len(self._quotas),
            "total_checks": self._total_checks,
            "total_denials": self._total_denials,
            "denial_rate": (
                round(self._total_denials / self._total_checks, 4)
                if self._total_checks else 0.0
            ),
        }
