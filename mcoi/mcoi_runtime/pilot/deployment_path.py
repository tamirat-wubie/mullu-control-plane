"""Phase 128D — Paid Deployment Path (Pilot-to-Production)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

@dataclass
class DeploymentMilestone:
    step: int
    name: str
    description: str
    owner: str  # "customer", "platform", "joint"
    estimated_days: int
    completed: bool = False
    completed_at: str = ""

    def complete(self) -> None:
        self.completed = True
        self.completed_at = datetime.now(timezone.utc).isoformat()

class PaidDeploymentPath:
    """Manages the pilot-to-production conversion flow."""

    def __init__(self, customer_id: str, offer_id: str):
        self.customer_id = customer_id
        self.offer_id = offer_id
        self._milestones = [
            DeploymentMilestone(1, "contract_signed", "Commercial agreement executed", "joint", 5),
            DeploymentMilestone(2, "tenant_created", "Production tenant bootstrapped", "platform", 1),
            DeploymentMilestone(3, "connectors_activated", "All required connectors authenticated and health-checked", "joint", 3),
            DeploymentMilestone(4, "data_loaded", "Historical data imported with audit report", "joint", 5),
            DeploymentMilestone(5, "operators_trained", "All operators completed enablement checklist", "joint", 5),
            DeploymentMilestone(6, "go_live_approved", "Go-live checklist signed off by both parties", "joint", 1),
            DeploymentMilestone(7, "hypercare_opened", "30-day hypercare window with elevated support", "platform", 0),
        ]

    def complete_milestone(self, step: int) -> DeploymentMilestone:
        for m in self._milestones:
            if m.step == step:
                m.complete()
                return m
        raise ValueError(f"No milestone with step {step}")

    @property
    def milestones(self) -> tuple[DeploymentMilestone, ...]:
        return tuple(self._milestones)

    @property
    def progress(self) -> dict[str, Any]:
        completed = sum(1 for m in self._milestones if m.completed)
        total = len(self._milestones)
        return {
            "customer_id": self.customer_id,
            "completed": completed,
            "total": total,
            "percent": round(completed / total * 100, 1) if total else 0,
            "next_step": next((m.name for m in self._milestones if not m.completed), "all_complete"),
            "estimated_days_remaining": sum(m.estimated_days for m in self._milestones if not m.completed),
            "is_live": completed == total,
        }

@dataclass(frozen=True)
class ReferenceDeployment:
    """Phase 128E — Canonical reference deployment pattern."""
    target_profile: str = "Regulated operations / compliance team, 5-25 operators"
    connector_set: tuple[str, ...] = ("email", "identity_sso", "document_storage", "ticketing", "reporting_export")
    data_load_shape: str = "50-500 historical cases, 20-200 remediations, 50-300 evidence records"
    timeline_weeks: int = 3
    hypercare_days: int = 30
    common_issues: tuple[str, ...] = (
        "SSO configuration delays (SAML metadata exchange)",
        "Document storage permission scoping",
        "Historical data mapping conflicts",
        "Operator workflow adoption curve (week 1-2)",
        "Executive dashboard KPI calibration",
    )
    kpi_baseline: dict[str, str] = field(default_factory=lambda: {
        "cases_per_week": "10-30",
        "remediation_cycle_days": "15-45 → target 10-20",
        "evidence_completeness": "60-70% → target 90%+",
        "reporting_turnaround_days": "5-10 → target 1-2",
        "operator_satisfaction": "target 7+/10 by week 4",
    })
