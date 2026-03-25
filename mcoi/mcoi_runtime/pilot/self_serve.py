"""Phase 146 — Self-Serve Customer Onboarding / Trial-to-Pilot Automation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

# 146A — Signup and Qualification
@dataclass
class SignupRecord:
    account_id: str
    company_name: str
    email: str
    industry: str
    team_size: int
    pain_points: tuple[str, ...] = ()
    selected_pack: str = ""
    fit_score: float = 0.0
    recommended_path: str = ""  # "demo_only", "trial", "pilot", "sales_assisted"
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            object.__setattr__(self, "created_at", datetime.now(timezone.utc).isoformat())

def qualify_signup(signup: SignupRecord) -> SignupRecord:
    score = 0.0
    if signup.team_size >= 10: score += 0.3
    elif signup.team_size >= 5: score += 0.2
    else: score += 0.1
    if len(signup.pain_points) >= 3: score += 0.3
    elif len(signup.pain_points) >= 1: score += 0.15
    if signup.industry in ("financial_services", "healthcare", "energy", "government", "insurance", "technology", "manufacturing"):
        score += 0.2
    if signup.selected_pack: score += 0.2

    score = min(1.0, score)
    if score >= 0.7: path = "pilot"
    elif score >= 0.5: path = "trial"
    elif score >= 0.3: path = "demo_only"
    else: path = "sales_assisted"

    object.__setattr__(signup, "fit_score", round(score, 3))
    object.__setattr__(signup, "recommended_path", path)
    return signup

# 146B — Trial Tenant
@dataclass
class TrialConfig:
    max_connectors: int = 2
    max_users: int = 5
    max_records: int = 100
    trial_days: int = 14
    governance_bundle: str = "trial_safe"
    auto_expire: bool = True

TRIAL_CONFIGS = {
    "demo": TrialConfig(max_connectors=0, max_users=1, max_records=50, trial_days=7),
    "trial": TrialConfig(max_connectors=2, max_users=5, max_records=100, trial_days=14),
    "pilot_ready": TrialConfig(max_connectors=5, max_users=25, max_records=500, trial_days=42, auto_expire=False),
}

class TrialTenantManager:
    def __init__(self):
        self._tenants: dict[str, dict[str, Any]] = {}

    def create_trial(self, account_id: str, pack: str, tier: str = "trial") -> dict[str, Any]:
        config = TRIAL_CONFIGS.get(tier, TRIAL_CONFIGS["trial"])
        tenant = {
            "account_id": account_id,
            "pack": pack,
            "tier": tier,
            "config": config,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "seeded": True,
        }
        self._tenants[account_id] = tenant
        return tenant

    def get_tenant(self, account_id: str) -> dict[str, Any] | None:
        return self._tenants.get(account_id)

    @property
    def active_trials(self) -> int:
        return sum(1 for t in self._tenants.values() if t["status"] == "active")

# 146C — Guided Onboarding
ONBOARDING_STEPS = (
    {"step": 1, "name": "create_workspace", "category": "setup"},
    {"step": 2, "name": "invite_users", "category": "setup"},
    {"step": 3, "name": "assign_personas", "category": "configure"},
    {"step": 4, "name": "connect_first_system", "category": "connect"},
    {"step": 5, "name": "load_sample_data", "category": "import"},
    {"step": 6, "name": "activate_dashboard", "category": "activate"},
    {"step": 7, "name": "run_first_workflow", "category": "verify"},
    {"step": 8, "name": "try_copilot", "category": "verify"},
)

@dataclass
class OnboardingProgress:
    account_id: str
    completed_steps: list[int] = field(default_factory=list)

    def complete_step(self, step: int) -> None:
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    @property
    def completion_rate(self) -> float:
        return len(self.completed_steps) / len(ONBOARDING_STEPS) if ONBOARDING_STEPS else 0.0

    @property
    def first_value_reached(self) -> bool:
        return 7 in self.completed_steps  # "run_first_workflow"

    @property
    def next_step(self) -> str:
        for s in ONBOARDING_STEPS:
            if s["step"] not in self.completed_steps:
                return s["name"]
        return "all_complete"

# 146D — Trial-to-Pilot Conversion
@dataclass
class TrialMetrics:
    account_id: str
    onboarding_completion: float = 0.0
    workflows_completed: int = 0
    dashboard_views: int = 0
    copilot_queries: int = 0
    connectors_activated: int = 0
    evidence_generated: int = 0
    reports_generated: int = 0
    days_active: int = 0

def recommend_conversion(metrics: TrialMetrics) -> dict[str, Any]:
    score = 0.0
    reasons = []

    if metrics.onboarding_completion >= 0.75:
        score += 0.25; reasons.append("strong_onboarding")
    if metrics.workflows_completed >= 3:
        score += 0.2; reasons.append("workflow_engagement")
    if metrics.dashboard_views >= 10:
        score += 0.15; reasons.append("dashboard_usage")
    if metrics.copilot_queries >= 5:
        score += 0.15; reasons.append("copilot_adoption")
    if metrics.connectors_activated >= 2:
        score += 0.15; reasons.append("connector_activation")
    if metrics.days_active >= 7:
        score += 0.1; reasons.append("sustained_usage")

    score = min(1.0, score)
    if score >= 0.7: action = "convert_to_paid"
    elif score >= 0.5: action = "promote_to_pilot"
    elif score >= 0.3: action = "extend_trial"
    else: action = "route_to_sales"

    return {"account_id": metrics.account_id, "score": round(score, 3), "action": action, "reasons": reasons}

# 146E — Friction Analytics
@dataclass
class FrictionEvent:
    account_id: str
    step: str
    event_type: str  # "drop_off", "failure", "slow", "skip"

class FrictionTracker:
    def __init__(self):
        self._events: list[FrictionEvent] = []

    def record(self, account_id: str, step: str, event_type: str) -> None:
        self._events.append(FrictionEvent(account_id, step, event_type))

    def drop_off_rate(self, step: str) -> float:
        total = sum(1 for e in self._events if e.step == step)
        drops = sum(1 for e in self._events if e.step == step and e.event_type == "drop_off")
        return drops / total if total else 0.0

    def worst_step(self) -> str | None:
        if not self._events:
            return None
        step_rates = {}
        for s in set(e.step for e in self._events):
            step_rates[s] = self.drop_off_rate(s)
        return max(step_rates, key=step_rates.get) if step_rates else None

    def summary(self) -> dict[str, Any]:
        return {
            "total_events": len(self._events),
            "drop_offs": sum(1 for e in self._events if e.event_type == "drop_off"),
            "failures": sum(1 for e in self._events if e.event_type == "failure"),
            "worst_step": self.worst_step(),
        }
