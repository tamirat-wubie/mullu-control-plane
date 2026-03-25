"""Phase 136 — Internal Service Delivery Automation. The company runs on its own platform."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

# 136A — Internal Delivery Pack
INTERNAL_PACK_CAPABILITIES = (
    "customer_onboarding", "implementation_milestones", "connector_activation_tasks",
    "import_backfill_tasks", "training_tasks", "go_live_approvals",
    "hypercare_tracking", "renewal_reviews", "expansion_reviews", "internal_dashboard",
)

# 136B — Implementation Workflow
@dataclass
class ImplementationProject:
    project_id: str
    customer_id: str
    pack: str
    status: str = "deal_closed"  # deal_closed → tenant_created → deploying → training → go_live_pending → live → hypercare → steady_state
    tasks_total: int = 0
    tasks_completed: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())

    @property
    def progress(self) -> float:
        return self.tasks_completed / self.tasks_total if self.tasks_total else 0.0

    @property
    def is_delayed(self) -> bool:
        return self.progress < 0.5 and self.status not in ("deal_closed", "steady_state", "live")

IMPLEMENTATION_STAGES = ("deal_closed", "tenant_created", "deploying", "training", "go_live_pending", "live", "hypercare", "steady_state")

# 136C — Support Operations
@dataclass
class SupportCase:
    case_id: str
    customer_id: str
    severity: str  # "critical", "high", "medium", "low"
    category: str
    status: str = "open"
    assigned_to: str = ""
    sla_deadline_hours: float = 0.0
    escalated: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())
        if not self.sla_deadline_hours:
            defaults = {"critical": 4.0, "high": 8.0, "medium": 24.0, "low": 48.0}
            object.__setattr__(self, "sla_deadline_hours", defaults.get(self.severity, 48.0))

# 136D — Customer Success Automation
@dataclass
class SuccessMilestone:
    milestone_id: str
    customer_id: str
    name: str
    target_day: int  # days after go-live
    completed: bool = False
    completed_at: str = ""

STANDARD_MILESTONES = (
    ("first_case_completed", 7),
    ("evidence_retrieval_used", 14),
    ("report_generated", 21),
    ("copilot_adopted", 30),
    ("executive_dashboard_reviewed", 45),
    ("value_realization_check", 60),
    ("renewal_readiness_review", 90),
    ("expansion_assessment", 120),
)

# 136E — Internal Executive Dashboard
@dataclass
class CompanyOperatingState:
    active_implementations: int = 0
    delayed_implementations: int = 0
    live_customers: int = 0
    open_support_cases: int = 0
    critical_cases: int = 0
    at_risk_renewals: int = 0
    expansion_pipeline: int = 0
    delivery_capacity_used: float = 0.0  # 0-1

    @property
    def operating_health(self) -> str:
        if self.critical_cases > 2 or self.delayed_implementations > 2:
            return "strained"
        if self.delivery_capacity_used > 0.85:
            return "near_capacity"
        if self.at_risk_renewals > 0:
            return "attention"
        return "healthy"

class InternalOpsEngine:
    """Runs the company's own delivery operations on the platform."""

    def __init__(self):
        self._projects: dict[str, ImplementationProject] = {}
        self._support_cases: list[SupportCase] = []
        self._milestones: list[SuccessMilestone] = []

    # Implementation
    def create_project(self, project_id: str, customer_id: str, pack: str) -> ImplementationProject:
        proj = ImplementationProject(project_id, customer_id, pack, tasks_total=8)
        self._projects[project_id] = proj
        return proj

    def advance_project(self, project_id: str) -> ImplementationProject:
        proj = self._projects[project_id]
        idx = IMPLEMENTATION_STAGES.index(proj.status)
        if idx < len(IMPLEMENTATION_STAGES) - 1:
            proj.status = IMPLEMENTATION_STAGES[idx + 1]
            proj.tasks_completed += 1
        return proj

    def complete_project_task(self, project_id: str) -> ImplementationProject:
        proj = self._projects[project_id]
        proj.tasks_completed = min(proj.tasks_completed + 1, proj.tasks_total)
        return proj

    # Support
    def create_support_case(self, case_id: str, customer_id: str, severity: str, category: str) -> SupportCase:
        case = SupportCase(case_id, customer_id, severity, category)
        self._support_cases.append(case)
        return case

    def assign_case(self, case_id: str, assignee: str) -> SupportCase:
        for c in self._support_cases:
            if c.case_id == case_id:
                c.assigned_to = assignee
                c.status = "in_progress"
                return c
        raise ValueError(f"Unknown case: {case_id}")

    def resolve_case(self, case_id: str) -> SupportCase:
        for c in self._support_cases:
            if c.case_id == case_id:
                c.status = "resolved"
                return c
        raise ValueError(f"Unknown case: {case_id}")

    def escalate_case(self, case_id: str) -> SupportCase:
        for c in self._support_cases:
            if c.case_id == case_id:
                c.escalated = True
                return c
        raise ValueError(f"Unknown case: {case_id}")

    # Success milestones
    def create_milestones(self, customer_id: str) -> list[SuccessMilestone]:
        created = []
        for name, target_day in STANDARD_MILESTONES:
            mid = f"ms-{customer_id}-{name}"
            ms = SuccessMilestone(mid, customer_id, name, target_day)
            self._milestones.append(ms)
            created.append(ms)
        return created

    def complete_milestone(self, milestone_id: str) -> SuccessMilestone:
        for ms in self._milestones:
            if ms.milestone_id == milestone_id:
                ms.completed = True
                ms.completed_at = datetime.now(timezone.utc).isoformat()
                return ms
        raise ValueError(f"Unknown milestone: {milestone_id}")

    # Dashboard
    def operating_state(self) -> CompanyOperatingState:
        active = sum(1 for p in self._projects.values() if p.status not in ("steady_state",))
        delayed = sum(1 for p in self._projects.values() if p.is_delayed)
        live = sum(1 for p in self._projects.values() if p.status in ("live", "hypercare", "steady_state"))
        open_cases = sum(1 for c in self._support_cases if c.status == "open")
        critical = sum(1 for c in self._support_cases if c.severity == "critical" and c.status != "resolved")
        capacity = min(1.0, active / 10.0) if active else 0.0

        return CompanyOperatingState(
            active_implementations=active,
            delayed_implementations=delayed,
            live_customers=live,
            open_support_cases=open_cases,
            critical_cases=critical,
            delivery_capacity_used=capacity,
        )

    @property
    def project_count(self) -> int:
        return len(self._projects)

    @property
    def case_count(self) -> int:
        return len(self._support_cases)

    @property
    def milestone_count(self) -> int:
        return len(self._milestones)
