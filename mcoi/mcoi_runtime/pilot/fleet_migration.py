"""Phases 173-174 — Clock Injection + Snapshot/Restore Fleet Migration Tooling."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# Phase 173 — Engines still using _now_iso() that need clock injection
ENGINES_NEEDING_CLOCK = (
    "mcoi_runtime/engines/billing_engine.py",
    "mcoi_runtime/engines/settlement_engine.py",
    "mcoi_runtime/engines/customer_engine.py",
    "mcoi_runtime/engines/marketplace_engine.py",
    "mcoi_runtime/engines/invoice_engine.py",
    "mcoi_runtime/engines/payment_engine.py",
    "mcoi_runtime/engines/subscription_engine.py",
    "mcoi_runtime/engines/usage_engine.py",
    "mcoi_runtime/engines/metering_engine.py",
    "mcoi_runtime/engines/pricing_engine.py",
    "mcoi_runtime/engines/discount_engine.py",
    "mcoi_runtime/engines/tax_engine.py",
    "mcoi_runtime/engines/refund_engine.py",
    "mcoi_runtime/engines/credit_engine.py",
    "mcoi_runtime/engines/ledger_engine.py",
    "mcoi_runtime/engines/reconciliation_engine.py",
    "mcoi_runtime/engines/dunning_engine.py",
    "mcoi_runtime/engines/collection_engine.py",
    "mcoi_runtime/engines/revenue_engine.py",
    "mcoi_runtime/engines/forecast_engine.py",
    "mcoi_runtime/engines/quota_engine.py",
    "mcoi_runtime/engines/entitlement_engine.py",
    "mcoi_runtime/engines/provisioning_engine.py",
    "mcoi_runtime/engines/onboarding_engine.py",
    "mcoi_runtime/engines/activation_engine.py",
    "mcoi_runtime/engines/retention_engine.py",
    "mcoi_runtime/engines/churn_engine.py",
    "mcoi_runtime/engines/renewal_engine.py",
    "mcoi_runtime/engines/upsell_engine.py",
    "mcoi_runtime/engines/cross_sell_engine.py",
    "mcoi_runtime/engines/trial_engine.py",
    "mcoi_runtime/engines/freemium_engine.py",
    "mcoi_runtime/engines/conversion_engine.py",
    "mcoi_runtime/engines/nurture_engine.py",
    "mcoi_runtime/engines/campaign_engine.py",
    "mcoi_runtime/engines/attribution_engine.py",
    "mcoi_runtime/engines/funnel_engine.py",
    "mcoi_runtime/engines/lead_engine.py",
    "mcoi_runtime/engines/opportunity_engine.py",
    "mcoi_runtime/engines/deal_engine.py",
    "mcoi_runtime/engines/contract_engine.py",
    "mcoi_runtime/engines/sla_engine.py",
    "mcoi_runtime/engines/escalation_engine.py",
    "mcoi_runtime/engines/incident_engine.py",
    "mcoi_runtime/engines/notification_engine.py",
    "mcoi_runtime/engines/alert_engine.py",
    "mcoi_runtime/engines/scheduling_engine.py",
    "mcoi_runtime/engines/calendar_engine.py",
    "mcoi_runtime/engines/task_engine.py",
    "mcoi_runtime/engines/queue_engine.py",
    "mcoi_runtime/engines/routing_engine.py",
    "mcoi_runtime/engines/assignment_engine.py",
    "mcoi_runtime/engines/priority_engine.py",
    "mcoi_runtime/engines/triage_engine.py",
    "mcoi_runtime/engines/classification_engine.py",
)

# Phase 174 — Engines missing snapshot()/_collections() for restore
ENGINES_NEEDING_SNAPSHOT = (
    "mcoi_runtime/engines/billing_engine.py",
    "mcoi_runtime/engines/settlement_engine.py",
    "mcoi_runtime/engines/customer_engine.py",
    "mcoi_runtime/engines/marketplace_engine.py",
    "mcoi_runtime/engines/invoice_engine.py",
    "mcoi_runtime/engines/payment_engine.py",
    "mcoi_runtime/engines/subscription_engine.py",
    "mcoi_runtime/engines/usage_engine.py",
    "mcoi_runtime/engines/metering_engine.py",
    "mcoi_runtime/engines/pricing_engine.py",
    "mcoi_runtime/engines/discount_engine.py",
    "mcoi_runtime/engines/tax_engine.py",
    "mcoi_runtime/engines/refund_engine.py",
    "mcoi_runtime/engines/credit_engine.py",
    "mcoi_runtime/engines/ledger_engine.py",
    "mcoi_runtime/engines/reconciliation_engine.py",
    "mcoi_runtime/engines/dunning_engine.py",
    "mcoi_runtime/engines/collection_engine.py",
    "mcoi_runtime/engines/revenue_engine.py",
    "mcoi_runtime/engines/forecast_engine.py",
    "mcoi_runtime/engines/quota_engine.py",
    "mcoi_runtime/engines/entitlement_engine.py",
    "mcoi_runtime/engines/provisioning_engine.py",
    "mcoi_runtime/engines/onboarding_engine.py",
    "mcoi_runtime/engines/activation_engine.py",
    "mcoi_runtime/engines/retention_engine.py",
    "mcoi_runtime/engines/churn_engine.py",
    "mcoi_runtime/engines/renewal_engine.py",
    "mcoi_runtime/engines/upsell_engine.py",
    "mcoi_runtime/engines/cross_sell_engine.py",
    "mcoi_runtime/engines/trial_engine.py",
    "mcoi_runtime/engines/freemium_engine.py",
    "mcoi_runtime/engines/conversion_engine.py",
    "mcoi_runtime/engines/nurture_engine.py",
    "mcoi_runtime/engines/campaign_engine.py",
    "mcoi_runtime/engines/attribution_engine.py",
    "mcoi_runtime/engines/funnel_engine.py",
    "mcoi_runtime/engines/lead_engine.py",
    "mcoi_runtime/engines/opportunity_engine.py",
    "mcoi_runtime/engines/deal_engine.py",
    "mcoi_runtime/engines/contract_engine.py",
    "mcoi_runtime/engines/sla_engine.py",
    "mcoi_runtime/engines/escalation_engine.py",
    "mcoi_runtime/engines/incident_engine.py",
    "mcoi_runtime/engines/notification_engine.py",
    "mcoi_runtime/engines/alert_engine.py",
)

# Critical engines that must be migrated first
_CRITICAL_ENGINES = frozenset({
    "billing_engine", "settlement_engine", "customer_engine",
    "marketplace_engine", "invoice_engine", "payment_engine",
})
_HIGH_ENGINES = frozenset({
    "subscription_engine", "usage_engine", "metering_engine",
    "pricing_engine", "ledger_engine", "reconciliation_engine",
    "revenue_engine", "contract_engine", "sla_engine",
})


class MigrationTracker:
    """Track migration progress for clock injection and snapshot/restore."""

    def __init__(self):
        self._tracked: dict[str, dict[str, Any]] = {}

    def track_engine(self, name: str, migration_type: str) -> dict[str, Any]:
        """Register an engine for migration tracking.

        Args:
            name: Engine name (e.g. "billing_engine")
            migration_type: "clock" or "snapshot"
        """
        if migration_type not in ("clock", "snapshot"):
            raise ValueError(f"migration_type must be 'clock' or 'snapshot', got {migration_type!r}")
        key = f"{name}:{migration_type}"
        entry = {
            "name": name,
            "migration_type": migration_type,
            "status": "pending",
        }
        self._tracked[key] = entry
        return entry

    def mark_complete(self, name: str, migration_type: str | None = None) -> dict[str, Any]:
        """Mark an engine migration as complete.

        If migration_type is None, marks all tracked migrations for that engine.
        """
        completed = []
        for key, entry in self._tracked.items():
            if entry["name"] == name:
                if migration_type is None or entry["migration_type"] == migration_type:
                    entry["status"] = "complete"
                    completed.append(key)
        if not completed:
            raise KeyError(f"No tracked migration for {name!r}" +
                           (f" type={migration_type!r}" if migration_type else ""))
        return {"name": name, "completed": len(completed), "status": "complete"}

    def progress(self) -> dict[str, Any]:
        """Return migration progress summary."""
        total = len(self._tracked)
        done = sum(1 for e in self._tracked.values() if e["status"] == "complete")
        pending = total - done
        return {
            "total": total,
            "complete": done,
            "pending": pending,
            "percent_complete": round(done / total * 100, 1) if total else 0.0,
        }

    def summary(self) -> dict[str, Any]:
        """Return detailed migration summary by type."""
        clock_total = sum(1 for e in self._tracked.values() if e["migration_type"] == "clock")
        clock_done = sum(1 for e in self._tracked.values()
                         if e["migration_type"] == "clock" and e["status"] == "complete")
        snap_total = sum(1 for e in self._tracked.values() if e["migration_type"] == "snapshot")
        snap_done = sum(1 for e in self._tracked.values()
                        if e["migration_type"] == "snapshot" and e["status"] == "complete")
        return {
            "clock": {"total": clock_total, "complete": clock_done, "pending": clock_total - clock_done},
            "snapshot": {"total": snap_total, "complete": snap_done, "pending": snap_total - snap_done},
            "overall": self.progress(),
        }


@dataclass(frozen=True)
class MigrationPlan:
    engine_name: str
    migration_type: str  # "clock" or "snapshot"
    priority: str  # "critical", "high", "medium", "low"
    estimated_hours: float


def _priority_for_engine(engine_path: str) -> str:
    """Determine priority based on engine name."""
    name = engine_path.rsplit("/", 1)[-1].replace(".py", "")
    if name in _CRITICAL_ENGINES:
        return "critical"
    if name in _HIGH_ENGINES:
        return "high"
    return "medium"


_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_HOURS_BY_PRIORITY = {"critical": 8.0, "high": 4.0, "medium": 2.0, "low": 1.0}


def generate_migration_plan() -> list[MigrationPlan]:
    """Generate a sorted migration plan for all engines needing clock or snapshot migration.

    Returns plans sorted by priority (critical first), then by engine name.
    """
    plans: list[MigrationPlan] = []

    # Clock injection plans
    for engine_path in ENGINES_NEEDING_CLOCK:
        priority = _priority_for_engine(engine_path)
        name = engine_path.rsplit("/", 1)[-1].replace(".py", "")
        plans.append(MigrationPlan(
            engine_name=name,
            migration_type="clock",
            priority=priority,
            estimated_hours=_HOURS_BY_PRIORITY[priority],
        ))

    # Snapshot/restore plans
    for engine_path in ENGINES_NEEDING_SNAPSHOT:
        priority = _priority_for_engine(engine_path)
        name = engine_path.rsplit("/", 1)[-1].replace(".py", "")
        plans.append(MigrationPlan(
            engine_name=name,
            migration_type="snapshot",
            priority=priority,
            estimated_hours=_HOURS_BY_PRIORITY[priority],
        ))

    plans.sort(key=lambda p: (_PRIORITY_ORDER[p.priority], p.engine_name, p.migration_type))
    return plans
