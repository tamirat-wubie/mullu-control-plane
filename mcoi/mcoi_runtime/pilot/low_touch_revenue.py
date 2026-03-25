"""Phase 148 — Self-Serve Expansion / Low-Touch Revenue Engine."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 148A — Trial-to-Paid Automation
@dataclass
class UpgradeDecision:
    account_id: str
    current_tier: str  # "trial", "starter", "standard", "enterprise"
    recommended_tier: str
    reason: str
    auto_eligible: bool  # can upgrade without human intervention
    action: str  # "auto_upgrade", "prompt_upgrade", "sales_handoff", "extend_trial", "expire"

def evaluate_upgrade(account_id: str, trial_days_remaining: int, activation_rate: float, fit_score: float, workflows_completed: int) -> UpgradeDecision:
    if activation_rate >= 0.75 and fit_score >= 0.7 and workflows_completed >= 5:
        return UpgradeDecision(account_id, "trial", "standard", "High activation + strong fit", True, "auto_upgrade")
    if activation_rate >= 0.5 and fit_score >= 0.5:
        return UpgradeDecision(account_id, "trial", "starter", "Good activation, moderate fit", True, "prompt_upgrade")
    if trial_days_remaining <= 3 and activation_rate >= 0.25:
        return UpgradeDecision(account_id, "trial", "starter", "Trial expiring, some engagement", False, "sales_handoff")
    if trial_days_remaining <= 0 and activation_rate < 0.25:
        return UpgradeDecision(account_id, "trial", "none", "Trial expired, low engagement", False, "expire")
    return UpgradeDecision(account_id, "trial", "trial", "Still evaluating", False, "extend_trial")

# 148B — Low-Touch Packaging
@dataclass(frozen=True)
class SelfServeOffer:
    offer_id: str
    name: str
    tier: str
    monthly_price: float
    max_users: int
    max_connectors: int
    copilot_included: bool
    bundle_eligible: bool

SELF_SERVE_OFFERS = {
    "starter_regulated": SelfServeOffer("ss-reg-starter", "Regulated Ops Starter", "starter", 999.0, 5, 3, True, False),
    "starter_service": SelfServeOffer("ss-svc-starter", "Service Ops Starter", "starter", 999.0, 5, 3, True, False),
    "standard_regulated": SelfServeOffer("ss-reg-std", "Regulated Ops Standard", "standard", 2500.0, 25, 5, True, True),
    "standard_service": SelfServeOffer("ss-svc-std", "Service Ops Standard", "standard", 2500.0, 25, 5, True, True),
    "bundle_regulated_financial": SelfServeOffer("ss-reg-fin", "Regulated Financial Suite", "bundle", 4500.0, 50, 5, True, True),
}

# 148C — In-Product Expansion
@dataclass
class ExpansionRecommendation:
    account_id: str
    current_pack: str
    recommendation: str  # "add_on", "pack_upgrade", "bundle_upgrade", "support_upgrade", "partner_onboarding"
    target: str
    reason: str
    estimated_acv_increase: float

def recommend_expansion(account_id: str, pack: str, users: int, connectors: int, copilot_queries: int, satisfaction: float) -> list[ExpansionRecommendation]:
    recs = []
    if users > 20 and pack.endswith("starter"):
        recs.append(ExpansionRecommendation(account_id, pack, "pack_upgrade", "standard", "User count exceeds starter limit", 1500.0))
    if connectors >= 4 and "bundle" not in pack:
        recs.append(ExpansionRecommendation(account_id, pack, "bundle_upgrade", f"{pack}_bundle", "High connector usage suggests bundle value", 2000.0))
    if copilot_queries > 50 and satisfaction >= 8.0:
        recs.append(ExpansionRecommendation(account_id, pack, "add_on", "multimodal_voice", "High copilot engagement, ready for voice", 1000.0))
    if satisfaction < 6.0:
        recs.append(ExpansionRecommendation(account_id, pack, "partner_onboarding", "implementation_partner", "Low satisfaction, needs assisted onboarding", 0.0))
    return recs

# 148D — Assisted-Routing Intelligence
def route_account(activation_rate: float, fit_score: float, support_tickets: int, trial_cost: float, conversion_likelihood: float) -> str:
    if activation_rate >= 0.75 and fit_score >= 0.7 and support_tickets <= 1:
        return "self_serve"
    if fit_score >= 0.6 and support_tickets <= 3:
        return "sales_assisted"
    if support_tickets > 5 or trial_cost > 500:
        return "partner_assisted"
    if fit_score < 0.3 or conversion_likelihood < 0.1:
        return "disqualify"
    return "pilot_driven"

# 148E — Low-Touch Margin Guard
@dataclass
class MarginFlag:
    account_id: str
    flag_type: str
    severity: str
    detail: str

def check_self_serve_margin(account_id: str, support_tickets: int, connector_count: int, monthly_price: float, trial_cost: float) -> list[MarginFlag]:
    flags = []
    if support_tickets > 3:
        flags.append(MarginFlag(account_id, "high_support", "medium" if support_tickets <= 5 else "high", f"{support_tickets} support tickets"))
    if connector_count > 5:
        flags.append(MarginFlag(account_id, "connector_heavy", "medium", f"{connector_count} connectors"))
    if monthly_price < 999 and trial_cost > 200:
        flags.append(MarginFlag(account_id, "underpriced", "high", f"Price ${monthly_price} vs trial cost ${trial_cost}"))
    return flags

# 148F — Executive Dashboard
def low_touch_dashboard(upgrades: list[UpgradeDecision], expansions: list[ExpansionRecommendation], flags: list[MarginFlag]) -> dict[str, Any]:
    auto_upgrades = sum(1 for u in upgrades if u.action == "auto_upgrade")
    prompted = sum(1 for u in upgrades if u.action == "prompt_upgrade")
    handoffs = sum(1 for u in upgrades if u.action == "sales_handoff")
    expired = sum(1 for u in upgrades if u.action == "expire")
    total_expansion_acv = sum(e.estimated_acv_increase for e in expansions)
    high_flags = sum(1 for f in flags if f.severity == "high")
    return {
        "auto_upgrades": auto_upgrades,
        "prompted_upgrades": prompted,
        "sales_handoffs": handoffs,
        "expired_trials": expired,
        "expansion_recommendations": len(expansions),
        "expansion_acv_potential": total_expansion_acv,
        "margin_flags_total": len(flags),
        "margin_flags_high": high_flags,
        "self_serve_offers": len(SELF_SERVE_OFFERS),
    }
