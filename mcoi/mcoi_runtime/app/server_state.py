"""Server state lifecycle helpers.

Purpose: isolate startup restore and shutdown persistence logic from HTTP bootstrap.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: bounded warning appender, state persistence, budget/audit stores, platform logger.
Invariants: warning text stays bounded, restore/flush results remain deterministic, no silent failures.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

WarningAppender = Callable[[list[str], str, Exception], None]


def _snapshot_mapping_data(snapshot: Any) -> Mapping[str, Any] | None:
    """Return snapshot data only when it has the expected mapping shape."""
    data = getattr(snapshot, "data", None)
    if isinstance(data, Mapping):
        return data
    return None


def flush_state_on_shutdown(
    *,
    tenant_budget_mgr: Any,
    state_persistence: Any,
    audit_trail: Any,
    cost_analytics: Any,
    platform_logger: Any,
    log_levels: Any,
    append_bounded_warning: WarningAppender,
) -> dict[str, Any]:
    """Flush critical in-memory state to file-backed snapshots before exit."""
    flushed: dict[str, Any] = {}
    warnings: list[str] = []

    budget_data: dict[str, dict[str, Any]] = {}
    raw_budgets = getattr(tenant_budget_mgr, "_budgets", {})
    if isinstance(raw_budgets, Mapping):
        for tenant_id, budget in raw_budgets.items():
            try:
                budget_data[str(tenant_id)] = {
                    "spent": budget.spent,
                    "calls_made": budget.calls_made,
                    "max_cost": budget.max_cost,
                    "max_calls": budget.max_calls,
                }
            except Exception as exc:
                append_bounded_warning(warnings, "shutdown budget snapshot", exc)
    else:
        append_bounded_warning(warnings, "shutdown budgets snapshot", TypeError())
    try:
        state_persistence.save("budgets", budget_data)
        flushed["budgets"] = len(budget_data)
    except Exception as exc:
        append_bounded_warning(warnings, "shutdown budgets flush", exc)

    try:
        audit_summary_data = {
            "entry_count": getattr(audit_trail, "entry_count", 0),
            "last_hash": getattr(audit_trail, "_last_hash", ""),
            "sequence": getattr(audit_trail, "_sequence", 0),
        }
        state_persistence.save("audit_summary", audit_summary_data)
        flushed["audit_sequence"] = audit_summary_data["sequence"]
    except Exception as exc:
        append_bounded_warning(warnings, "shutdown audit summary flush", exc)

    try:
        cost_data = {
            "summary": cost_analytics.summary() if hasattr(cost_analytics, "summary") else {}
        }
        state_persistence.save("cost_analytics", cost_data)
        flushed["cost_analytics"] = True
    except Exception as exc:
        append_bounded_warning(warnings, "shutdown cost analytics flush", exc)

    if flushed:
        platform_logger.log(log_levels.INFO, f"Shutdown state flush: {flushed}")
    if warnings:
        platform_logger.log(log_levels.WARNING, f"Shutdown state flush warnings: {warnings}")
    return {"flushed": not warnings, **flushed, "warnings": tuple(warnings)}


def restore_state_on_startup(
    *,
    tenant_budget_mgr: Any,
    state_persistence: Any,
    platform_logger: Any,
    log_levels: Any,
    append_bounded_warning: WarningAppender,
) -> dict[str, Any]:
    """Restore persisted state snapshots during startup."""
    restored: dict[str, Any] = {}
    warnings: list[str] = []

    budget_snapshot = None
    try:
        budget_snapshot = state_persistence.load("budgets")
    except Exception as exc:
        append_bounded_warning(warnings, "startup budgets load", exc)
    budget_snapshot_data = _snapshot_mapping_data(budget_snapshot)
    if budget_snapshot and budget_snapshot_data is None:
        append_bounded_warning(warnings, "startup budgets payload", TypeError())
    if budget_snapshot_data:
        skipped = 0
        for tenant_id, budget_data in budget_snapshot_data.items():
            try:
                if not isinstance(budget_data, Mapping):
                    raise TypeError("budget snapshot entry must be a mapping")
                tenant_budget_mgr.ensure_budget(tenant_id)
                if budget_data.get("spent", 0) > 0:
                    tenant_budget_mgr.record_spend(tenant_id, cost=budget_data["spent"])
            except Exception as exc:
                skipped += 1
                append_bounded_warning(warnings, "startup budget restore", exc)
        restored["budgets"] = len(budget_snapshot_data)
        if skipped:
            restored["budget_restore_skipped"] = skipped

    audit_snapshot = None
    try:
        audit_snapshot = state_persistence.load("audit_summary")
    except Exception as exc:
        append_bounded_warning(warnings, "startup audit summary load", exc)
    audit_snapshot_data = _snapshot_mapping_data(audit_snapshot)
    if audit_snapshot and audit_snapshot_data is None:
        append_bounded_warning(warnings, "startup audit summary payload", TypeError())
    if audit_snapshot_data:
        restored["audit_sequence"] = audit_snapshot_data.get("sequence", 0)

    if restored:
        platform_logger.log(log_levels.INFO, f"Startup state restore: {restored}")
    if warnings:
        platform_logger.log(log_levels.WARNING, f"Startup state restore warnings: {warnings}")
        restored["warnings"] = tuple(warnings)
    return restored


def close_governance_stores(
    *,
    governance_stores: Any,
    primary_store: Any,
    platform_logger: Any,
    log_levels: Any,
    append_bounded_warning: WarningAppender,
) -> dict[str, Any]:
    """Close governance and primary store connections during shutdown."""
    warnings: list[str] = []
    governance_stores_closed = True
    primary_store_closed = True

    try:
        governance_stores.close()
    except Exception as exc:
        governance_stores_closed = False
        append_bounded_warning(warnings, "shutdown governance store close", exc)
    if hasattr(primary_store, "close"):
        try:
            primary_store.close()
        except Exception as exc:
            primary_store_closed = False
            append_bounded_warning(warnings, "shutdown primary store close", exc)

    if warnings:
        platform_logger.log(log_levels.WARNING, f"Shutdown store close warnings: {warnings}")
    return {
        "closed": governance_stores_closed and primary_store_closed,
        "governance_stores_closed": governance_stores_closed,
        "store_closed": primary_store_closed,
        "warnings": tuple(warnings),
    }
