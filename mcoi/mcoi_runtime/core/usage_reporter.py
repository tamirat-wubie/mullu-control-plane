"""Phase 217B — Usage Reporter.

Purpose: Per-tenant usage reports combining LLM calls, costs, budgets,
    and activity metrics into a single exportable report.
Governance scope: report generation only — read-only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Any, Callable


_MAX_ID_LENGTH = 256


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Complete usage report for a tenant."""

    tenant_id: str
    llm_calls: int
    total_cost: float
    budget_remaining: float
    conversations: int
    workflows: int
    tool_invocations: int
    events_published: int
    report_period: str
    generated_at: str


class UsageReporter:
    """Generates per-tenant usage reports."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._data_fns: dict[str, Callable[[str], Any]] = {}
        self._source_error_counts: dict[str, int] = {}
        self._last_source_errors: dict[str, str] = {}

    def register_source(self, name: str, fn: Callable[[str], Any]) -> None:
        name = _validate_identity(name, field_name="source")
        if not callable(fn):
            raise ValueError("usage source must be callable")
        self._data_fns[name] = fn

    def generate(self, tenant_id: str, period: str = "current") -> UsageReport:
        tenant_id = _validate_identity(tenant_id, field_name="tenant_id")
        data: dict[str, Any] = {}
        for name, fn in self._data_fns.items():
            try:
                data[name] = _coerce_source_value(name, fn(tenant_id))
                self._last_source_errors.pop(name, None)
            except Exception as exc:
                self._source_error_counts[name] = self._source_error_counts.get(name, 0) + 1
                self._last_source_errors[name] = _bounded_usage_source_error(exc)
                data[name] = 0

        return UsageReport(
            tenant_id=tenant_id,
            llm_calls=data.get("llm_calls", 0),
            total_cost=data.get("total_cost", 0.0),
            budget_remaining=data.get("budget_remaining", 0.0),
            conversations=data.get("conversations", 0),
            workflows=data.get("workflows", 0),
            tool_invocations=data.get("tool_invocations", 0),
            events_published=data.get("events_published", 0),
            report_period=period,
            generated_at=_validate_timestamp(self._clock()),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "sources": list(self._data_fns.keys()),
            "source_error_count": sum(self._source_error_counts.values()),
            "source_errors": dict(sorted(self._last_source_errors.items())),
        }


def _bounded_usage_source_error(exc: Exception) -> str:
    return f"usage source error ({type(exc).__name__})"


def _validate_identity(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    if len(normalized) > _MAX_ID_LENGTH:
        raise ValueError(f"{field_name} exceeds maximum length")
    return normalized


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("generated_at must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("generated_at must be non-empty")
    return normalized


def _coerce_source_value(name: str, value: Any) -> int | float | Any:
    if name in {
        "llm_calls",
        "conversations",
        "workflows",
        "tool_invocations",
        "events_published",
    }:
        return _coerce_non_negative_int(value)
    if name in {"total_cost", "budget_remaining"}:
        return _coerce_non_negative_float(value)
    return value


def _coerce_non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("usage source value must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0 or not numeric.is_integer():
        raise ValueError("usage source value must be a non-negative integer")
    return int(numeric)


def _coerce_non_negative_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("usage source value must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0:
        raise ValueError("usage source value must be a finite non-negative number")
    return numeric
