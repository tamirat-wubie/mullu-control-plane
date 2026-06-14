"""Purpose: dashboard projection for operational mathematics receipts.
Governance scope: read-only receipt projection and observability registration.
Dependencies: observability-compatible register_source, receipt stores, and JSON maps.
Invariants:
  - Projection never mutates the source receipt.
  - Missing or unresolved principles are surfaced as review signals.
  - Source name is stable for dashboard consumers.
  - Invalid wiring fails explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from mcoi_runtime.app.operational_math_integration import (
    OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV,
)
from mcoi_runtime.persistence.operational_math_receipt_store import (
    OperationalMathReceiptStore,
)


OPERATIONAL_MATH_OBSERVABILITY_SOURCE = "operational_math"


def summarize_operational_math_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Return a dashboard-safe summary for one operational math receipt."""

    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")
    status = _text_value(receipt.get("status"))
    solver_outcome = _text_value(receipt.get("solver_outcome"))
    target_id = _text_value(receipt.get("target_id"))
    unresolved_ids = _text_list(receipt.get("unresolved_principle_ids"))
    applied_ids = _text_list(receipt.get("applied_principle_ids"))
    iteration_count = _non_negative_int(receipt.get("iteration_count"), "iteration_count")
    event_count = _non_negative_int(receipt.get("event_count"), "event_count")

    review_signals: list[str] = []
    if status != "passed":
        review_signals.append("operational_math_status_not_passed")
    if unresolved_ids:
        review_signals.append("operational_math_unresolved_principles")
    if solver_outcome != "SolvedVerified":
        review_signals.append("operational_math_solver_not_verified")

    return {
        "source": OPERATIONAL_MATH_OBSERVABILITY_SOURCE,
        "governed": True,
        "target_id": target_id,
        "status": status,
        "solver_outcome": solver_outcome,
        "iteration_count": iteration_count,
        "event_count": event_count,
        "applied_principle_count": len(applied_ids),
        "unresolved_principle_count": len(unresolved_ids),
        "unresolved_principle_ids": unresolved_ids,
        "requires_operator_review": bool(review_signals),
        "review_signals": review_signals,
    }


def register_operational_math_observability(
    *,
    observability: Any,
    receipt_provider: Callable[[], Mapping[str, Any]] | None = None,
    receipt_store: OperationalMathReceiptStore | None = None,
    store_persistent: bool = False,
    store_path: str = "",
) -> None:
    """Register a read-only operational math receipt projection source."""

    register_source = getattr(observability, "register_source", None)
    if not callable(register_source):
        raise TypeError("observability must provide register_source")
    if receipt_store is not None:
        if not isinstance(receipt_store, OperationalMathReceiptStore):
            raise TypeError("receipt_store must be an OperationalMathReceiptStore")
        store_posture = _receipt_store_posture(
            store_persistent=store_persistent,
            store_path=store_path,
        )
        register_source(
            OPERATIONAL_MATH_OBSERVABILITY_SOURCE,
            lambda: _store_summary_with_posture(receipt_store, store_posture),
        )
        return
    if not callable(receipt_provider):
        raise TypeError("receipt_provider must be callable when receipt_store is absent")
    register_source(
        OPERATIONAL_MATH_OBSERVABILITY_SOURCE,
        lambda: summarize_operational_math_receipt(receipt_provider()),
    )


def _store_summary_with_posture(
    receipt_store: OperationalMathReceiptStore,
    store_posture: Mapping[str, Any],
) -> dict[str, Any]:
    summary = receipt_store.summary()
    summary["receipt_store"] = dict(store_posture)
    return summary


def _receipt_store_posture(*, store_persistent: bool, store_path: str) -> dict[str, Any]:
    if not isinstance(store_persistent, bool):
        raise TypeError("store_persistent must be a bool")
    if not isinstance(store_path, str):
        raise TypeError("store_path must be a string")

    path_configured = bool(store_path.strip())
    if store_persistent and not path_configured:
        raise ValueError("store_path must be configured when store_persistent is true")
    if path_configured and not store_persistent:
        raise ValueError("store_path requires store_persistent to be true")

    return {
        "kind": "file" if store_persistent else "memory",
        "persistent": store_persistent,
        "path_configured": path_configured,
        "path_env": OPERATIONAL_MATH_RECEIPT_STORE_PATH_ENV,
    }


def _text_value(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return value


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value
