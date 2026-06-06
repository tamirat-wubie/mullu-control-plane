"""Phase 221B — Tenant Analytics Dashboard.

Purpose: Per-tenant analytics combining all subsystem data into
    a single dashboard view. Provides operational intelligence
    for tenant management.
Governance scope: analytics computation only — read-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, Callable


_MAX_ID_LENGTH = 256
_COUNT_METRICS = {
    "llm_calls",
    "conversations",
    "workflows",
    "tool_invocations",
    "memories",
    "active_sessions",
}
_FLOAT_METRICS = {"total_cost", "budget_utilization_pct"}


@dataclass(frozen=True, slots=True)
class TenantAnalytics:
    """Complete analytics for a single tenant."""

    tenant_id: str
    llm_calls: int
    total_cost: float
    conversations: int
    workflows: int
    tool_invocations: int
    memories: int
    budget_utilization_pct: float
    active_sessions: int
    generated_at: str


class TenantAnalyticsEngine:
    """Computes per-tenant analytics from all subsystems."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._collectors: dict[str, Callable[[str], Any]] = {}

    def register_collector(self, metric: str, fn: Callable[[str], Any]) -> None:
        metric = _validate_identity(metric, field_name="metric")
        if not callable(fn):
            raise ValueError("collector must be callable")
        self._collectors[metric] = fn

    def compute(self, tenant_id: str) -> TenantAnalytics:
        tenant_id = _validate_identity(tenant_id, field_name="tenant_id")
        data: dict[str, Any] = {}
        for metric, fn in self._collectors.items():
            try:
                data[metric] = _coerce_metric_value(metric, fn(tenant_id))
            except Exception:
                data[metric] = 0

        return TenantAnalytics(
            tenant_id=tenant_id,
            llm_calls=data.get("llm_calls", 0),
            total_cost=data.get("total_cost", 0.0),
            conversations=data.get("conversations", 0),
            workflows=data.get("workflows", 0),
            tool_invocations=data.get("tool_invocations", 0),
            memories=data.get("memories", 0),
            budget_utilization_pct=data.get("budget_utilization_pct", 0.0),
            active_sessions=data.get("active_sessions", 0),
            generated_at=_validate_timestamp(self._clock()),
        )

    def compute_all(self, tenant_ids: list[str]) -> list[TenantAnalytics]:
        return [self.compute(tid) for tid in tenant_ids]

    def summary(self) -> dict[str, Any]:
        return {"collectors": list(self._collectors.keys())}


def _validate_identity(value: str, *, field_name: str) -> str:
    """Validate identity values before they become analytics keys."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if len(normalized) > _MAX_ID_LENGTH:
        raise ValueError(f"{field_name} exceeds maximum length")
    return normalized


def _validate_timestamp(value: Any) -> str:
    """Validate clock output for analytics read models."""
    if not isinstance(value, str):
        raise ValueError("generated_at must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("generated_at must be non-empty")
    return normalized


def _coerce_metric_value(metric: str, value: Any) -> int | float | Any:
    """Normalize known tenant analytics fields; leave unknown fields unchanged."""
    if metric in _COUNT_METRICS:
        return _coerce_non_negative_int(value, field_name=metric)
    if metric in _FLOAT_METRICS:
        return _coerce_non_negative_float(value, field_name=metric)
    return value


def _coerce_non_negative_int(value: Any, *, field_name: str) -> int:
    """Validate finite non-negative integer-like collector values."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be an integer")
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0 or not numeric_value.is_integer():
        raise ValueError(f"{field_name} must be a finite non-negative integer")
    return int(value)


def _coerce_non_negative_float(value: Any, *, field_name: str) -> float:
    """Validate finite non-negative floating collector values."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field_name} must be a number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{field_name} must be a finite non-negative number")
    return numeric_value
