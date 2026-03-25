"""Phase 125C — Pricing and Packaging Model."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class PricingTier:
    name: str
    description: str
    base_price_monthly: float
    included_workspaces: int
    included_operator_seats: int
    included_connectors: int
    copilot_included: bool
    multimodal_included: bool
    self_tuning_included: bool
    support_level: str  # "community", "standard", "premium", "dedicated"

PILOT_TIER = PricingTier(
    name="Pilot",
    description="Limited pilot for evaluation — up to 3 months, 1 workspace, 5 operators",
    base_price_monthly=0.0,
    included_workspaces=1,
    included_operator_seats=5,
    included_connectors=5,
    copilot_included=True,
    multimodal_included=False,
    self_tuning_included=False,
    support_level="standard",
)

STANDARD_TIER = PricingTier(
    name="Standard",
    description="Production deployment — multi-workspace, full connector suite, governed copilot",
    base_price_monthly=2500.0,
    included_workspaces=3,
    included_operator_seats=25,
    included_connectors=5,
    copilot_included=True,
    multimodal_included=False,
    self_tuning_included=False,
    support_level="standard",
)

ENTERPRISE_TIER = PricingTier(
    name="Enterprise",
    description="Full platform — unlimited workspaces, all add-ons, dedicated support",
    base_price_monthly=7500.0,
    included_workspaces=999,
    included_operator_seats=999,
    included_connectors=999,
    copilot_included=True,
    multimodal_included=True,
    self_tuning_included=True,
    support_level="dedicated",
)

ALL_TIERS = (PILOT_TIER, STANDARD_TIER, ENTERPRISE_TIER)

ADD_ONS = {
    "additional_workspace": {"price_monthly": 500.0, "description": "Extra workspace"},
    "additional_operator_seat": {"price_monthly": 50.0, "description": "Extra operator seat"},
    "multimodal_voice": {"price_monthly": 1000.0, "description": "Voice/streaming copilot interaction"},
    "self_tuning": {"price_monthly": 750.0, "description": "Automated improvement proposals"},
    "blockchain_settlement": {"price_monthly": 500.0, "description": "Verifiable settlement proofs"},
}
