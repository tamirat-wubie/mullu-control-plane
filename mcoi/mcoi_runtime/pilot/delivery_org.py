"""Phase 135A+B — Delivery Operating Model and Support Tiering."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class DeliveryRole:
    role: str
    description: str
    phase: str  # "sales", "implementation", "support", "success"
    headcount_ratio: str  # e.g., "1:5 customers"

DELIVERY_ROLES = (
    DeliveryRole("Sales Engineer", "Pre-sales technical validation, demo execution", "sales", "1:20 prospects"),
    DeliveryRole("Implementation Lead", "Tenant bootstrap, connector activation, data migration", "implementation", "1:3 concurrent"),
    DeliveryRole("Deployment Engineer", "Technical deployment, integration, troubleshooting", "implementation", "1:5 concurrent"),
    DeliveryRole("Support Engineer", "Tier 1+2 incident response, break/fix", "support", "1:10 customers"),
    DeliveryRole("Platform Engineer", "Tier 3 escalation, engine/connector issues", "support", "1:20 customers"),
    DeliveryRole("Customer Success Manager", "Adoption, health, renewal, expansion", "success", "1:8 customers"),
    DeliveryRole("Executive Sponsor (internal)", "Strategic relationship, escalation backstop", "success", "1:15 customers"),
)

HANDOFF_CHAIN = (
    "1. Sales closes deal → Implementation Lead assigned within 24 hours",
    "2. Implementation Lead runs deployment playbook → Deployment Engineer assists",
    "3. Go-live → 30-day hypercare window (Implementation Lead + Support Engineer)",
    "4. Hypercare ends → CSM takes ownership, Support Engineer on-call",
    "5. Quarterly business review → CSM + Executive Sponsor",
    "6. Renewal (60 days out) → CSM drives, Sales assists if expansion",
)

@dataclass(frozen=True)
class SupportTier:
    name: str
    response_critical: str
    response_high: str
    response_medium: str
    response_low: str
    hours: str
    dedicated_csm: bool
    hypercare_days: int

SUPPORT_TIERS = {
    "pilot": SupportTier("Pilot", "8h", "24h", "48h", "5d", "Business hours", False, 14),
    "standard": SupportTier("Standard", "4h", "8h", "24h", "48h", "Business hours", False, 30),
    "premium": SupportTier("Premium", "1h", "4h", "8h", "24h", "24/7", True, 30),
    "enterprise": SupportTier("Enterprise", "30m", "2h", "4h", "8h", "24/7", True, 45),
}

ISSUE_CLASSIFICATION = {
    "break_fix": "System is not functioning as designed — fix required",
    "configuration": "System works but needs adjustment for customer environment",
    "product_gap": "Requested capability does not exist — roadmap consideration",
    "training": "Customer needs help understanding existing functionality",
    "connector": "Integration with external system is failing or degraded",
    "data": "Data quality, migration, or mapping issue",
}
