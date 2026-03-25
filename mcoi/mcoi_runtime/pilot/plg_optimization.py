"""Phase 147 — Product-Led Growth Optimization / Trial Economics."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 147A — Funnel Instrumentation
FUNNEL_STAGES = ("signup", "qualify", "tenant_launch", "onboarding", "first_workflow", "trial_value", "pilot", "paid", "expanded")

@dataclass
class FunnelEntry:
    account_id: str
    pack: str
    channel: str  # "direct", "partner", "self_serve"
    stage: str

class FunnelInstrumentation:
    def __init__(self):
        self._entries: list[FunnelEntry] = []

    def record(self, account_id: str, pack: str, channel: str, stage: str) -> None:
        self._entries.append(FunnelEntry(account_id, pack, channel, stage))

    def conversion_rate(self, pack: str, channel: str, from_stage: str, to_stage: str) -> float:
        from_count = sum(1 for e in self._entries if e.pack == pack and e.channel == channel and e.stage == from_stage)
        to_count = sum(1 for e in self._entries if e.pack == pack and e.channel == channel and e.stage == to_stage)
        return to_count / from_count if from_count else 0.0

    def by_pack_channel(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for e in self._entries:
            key = f"{e.pack}:{e.channel}"
            result.setdefault(key, {})
            result[key][e.stage] = result[key].get(e.stage, 0) + 1
        return result

    @property
    def total_entries(self) -> int:
        return len(self._entries)

# 147B — Activation Milestones
ACTIVATION_MILESTONES = (
    "tenant_created", "first_user_invited", "first_connector",
    "first_data_loaded", "first_dashboard", "first_workflow",
    "first_copilot", "first_evidence_report",
)

@dataclass
class ActivationScore:
    account_id: str
    milestones_hit: int = 0
    total_milestones: int = len(ACTIVATION_MILESTONES)

    @property
    def rate(self) -> float:
        return self.milestones_hit / self.total_milestones if self.total_milestones else 0.0

    @property
    def status(self) -> str:
        r = self.rate
        if r >= 0.875: return "activated"
        if r >= 0.5: return "partially_activated"
        if r >= 0.25: return "stalled"
        if self.milestones_hit >= 1: return "high_potential"
        return "low_likelihood"

class ActivationEngine:
    def __init__(self):
        self._scores: dict[str, ActivationScore] = {}

    def track(self, account_id: str, milestones_hit: int) -> ActivationScore:
        score = ActivationScore(account_id, milestones_hit)
        self._scores[account_id] = score
        return score

    def stalled_accounts(self) -> list[str]:
        return [k for k, v in self._scores.items() if v.status == "stalled"]

    def activated_accounts(self) -> list[str]:
        return [k for k, v in self._scores.items() if v.status == "activated"]

    @property
    def total_tracked(self) -> int:
        return len(self._scores)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for v in self._scores.values():
            counts[v.status] = counts.get(v.status, 0) + 1
        return counts

# 147C — Guided Conversion
@dataclass(frozen=True)
class ConversionNudge:
    trigger: str
    message: str
    route_to: str  # "self_serve", "sales_assist", "partner_assist", "pilot", "disqualify"

NUDGES = (
    ConversionNudge("onboarding_incomplete", "Complete your setup to unlock full features", "self_serve"),
    ConversionNudge("no_connector", "Connect your first system to see real data", "self_serve"),
    ConversionNudge("no_workflow", "Run your first workflow to experience the value", "self_serve"),
    ConversionNudge("no_dashboard", "Open your dashboard to see your operational posture", "self_serve"),
    ConversionNudge("no_copilot", "Ask the copilot a question about your data", "self_serve"),
    ConversionNudge("stalled_7_days", "Need help getting started? We can assist", "sales_assist"),
    ConversionNudge("high_engagement_no_convert", "Ready to upgrade? Talk to our team", "pilot"),
    ConversionNudge("low_fit_score", "This may not be the right fit — let us help evaluate", "disqualify"),
)

def recommend_nudge(activation: ActivationScore, days_since_signup: int) -> ConversionNudge | None:
    if activation.status == "stalled" and days_since_signup >= 7:
        return next(n for n in NUDGES if n.trigger == "stalled_7_days")
    if activation.status == "low_likelihood":
        return next(n for n in NUDGES if n.trigger == "low_fit_score")
    if activation.milestones_hit >= 6 and activation.status != "activated":
        return next(n for n in NUDGES if n.trigger == "high_engagement_no_convert")
    if activation.milestones_hit < 3:
        return next(n for n in NUDGES if n.trigger == "onboarding_incomplete")
    return None

# 147D — Trial Economics
@dataclass
class TrialEconomics:
    account_id: str
    infrastructure_cost: float = 0.0
    connector_cost: float = 0.0
    support_cost: float = 0.0
    conversion_likelihood: float = 0.0  # 0-1
    expected_acv: float = 0.0
    expected_margin: float = 0.0

    @property
    def trial_cost(self) -> float:
        return self.infrastructure_cost + self.connector_cost + self.support_cost

    @property
    def expected_return(self) -> float:
        return self.expected_acv * self.conversion_likelihood - self.trial_cost

    @property
    def flag(self) -> str:
        if self.expected_return >= 5000: return "high_return"
        if self.expected_return >= 0: return "marginal"
        if self.conversion_likelihood < 0.2: return "expensive_low_likelihood"
        return "needs_review"

# 147E — Friction Analytics (extends Phase 146)
def pack_activation_ranking(funnel: FunnelInstrumentation) -> list[tuple[str, float]]:
    """Rank packs by self-serve activation rate."""
    packs = set(e.pack for e in funnel._entries)
    rates = []
    for p in packs:
        signups = sum(1 for e in funnel._entries if e.pack == p and e.stage == "signup")
        activated = sum(1 for e in funnel._entries if e.pack == p and e.stage == "first_workflow")
        rate = activated / signups if signups else 0.0
        rates.append((p, round(rate, 3)))
    return sorted(rates, key=lambda x: x[1], reverse=True)

# 147F — Executive Growth Dashboard
def growth_dashboard(funnel: FunnelInstrumentation, activation: ActivationEngine, economics: list[TrialEconomics]) -> dict[str, Any]:
    act_summary = activation.summary()
    high_return = sum(1 for e in economics if e.flag == "high_return")
    expensive = sum(1 for e in economics if e.flag == "expensive_low_likelihood")
    return {
        "total_funnel_entries": funnel.total_entries,
        "total_tracked_accounts": activation.total_tracked,
        "activation_summary": act_summary,
        "activated": act_summary.get("activated", 0),
        "stalled": act_summary.get("stalled", 0),
        "pack_ranking": pack_activation_ranking(funnel),
        "high_return_trials": high_return,
        "expensive_trials": expensive,
        "nudges_available": len(NUDGES),
    }
