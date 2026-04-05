"""Phase 145 — Channel / Partner Distribution Motion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 145A — Partner Model
@dataclass(frozen=True)
class PartnerType:
    name: str
    can_sell: bool
    can_deploy: bool
    can_support: bool
    revenue_share_pct: float
    certification_required: str

PARTNER_TYPES = {
    "referral": PartnerType("Referral Partner", False, False, False, 10.0, "none"),
    "reseller": PartnerType("Reseller", True, False, False, 20.0, "demo_certified"),
    "implementation": PartnerType("Implementation Partner", True, True, False, 30.0, "implementation_certified"),
    "managed_service": PartnerType("Managed Service Partner", True, True, True, 40.0, "support_certified"),
    "strategic": PartnerType("Strategic Ecosystem Partner", True, True, True, 35.0, "bundle_certified"),
}

# 145B — Enablement
ENABLEMENT_ASSETS = (
    "pack_training_materials", "deployment_playbooks", "demo_environments",
    "connector_setup_guides", "support_runbooks", "objection_handling",
    "architecture_briefs", "pricing_quoting_guides",
)

# 145C — Certification
@dataclass(frozen=True)
class CertificationLevel:
    level: str
    requirements: tuple[str, ...]

CERTIFICATIONS = {
    "demo_certified": CertificationLevel("demo_certified", ("product_knowledge_exam", "demo_delivery_observed", "security_overview")),
    "implementation_certified": CertificationLevel("implementation_certified", ("demo_certified", "deployment_success_x2", "governance_understanding", "connector_proficiency")),
    "support_certified": CertificationLevel("support_certified", ("implementation_certified", "support_handling_x5", "escalation_proficiency", "sla_understanding")),
    "bundle_certified": CertificationLevel("bundle_certified", ("support_certified", "multi_pack_deployment", "cross_pack_workflow_proficiency", "margin_awareness")),
}

# 145D — Economics
@dataclass
class PartnerEconomics:
    partner_id: str
    partner_type: str
    deals_sourced: int = 0
    deals_closed: int = 0
    total_revenue_influenced: float = 0.0
    referral_fees_earned: float = 0.0
    implementation_revenue: float = 0.0
    support_revenue: float = 0.0
    renewals_managed: int = 0
    expansions_sourced: int = 0

    @property
    def close_rate(self) -> float:
        return self.deals_closed / self.deals_sourced if self.deals_sourced else 0.0

    @property
    def total_earned(self) -> float:
        return self.referral_fees_earned + self.implementation_revenue + self.support_revenue

# 145E — Partner Pipeline & Governance
@dataclass
class PartnerRecord:
    partner_id: str
    company_name: str
    partner_type: str
    certification_level: str
    active: bool = True
    quality_score: float = 0.0  # 0-10

    @property
    def status(self) -> str:
        if not self.active: return "inactive"
        if self.quality_score >= 8: return "gold"
        if self.quality_score >= 6: return "silver"
        if self.quality_score >= 4: return "bronze"
        return "probation"

class PartnerEngine:
    """Manages partner lifecycle, economics, and governance."""

    def __init__(self):
        self._partners: dict[str, PartnerRecord] = {}
        self._economics: dict[str, PartnerEconomics] = {}

    def onboard_partner(self, partner_id: str, company_name: str, partner_type: str, certification: str = "none") -> PartnerRecord:
        if partner_id in self._partners:
            raise ValueError("partner already exists")
        record = PartnerRecord(partner_id, company_name, partner_type, certification)
        self._partners[partner_id] = record
        self._economics[partner_id] = PartnerEconomics(partner_id, partner_type)
        return record

    def certify_partner(self, partner_id: str, level: str) -> PartnerRecord:
        if partner_id not in self._partners:
            raise ValueError("unknown partner")
        p = self._partners[partner_id]
        self._partners[partner_id] = PartnerRecord(p.partner_id, p.company_name, p.partner_type, level, p.active, p.quality_score)
        return self._partners[partner_id]

    def record_deal(self, partner_id: str, revenue: float, closed: bool = False) -> PartnerEconomics:
        if partner_id not in self._economics:
            raise ValueError("unknown partner")
        econ = self._economics[partner_id]
        econ.deals_sourced += 1
        econ.total_revenue_influenced += revenue
        if closed:
            econ.deals_closed += 1
            ptype = PARTNER_TYPES.get(econ.partner_type)
            if ptype:
                econ.referral_fees_earned += revenue * (ptype.revenue_share_pct / 100)
        return econ

    def update_quality(self, partner_id: str, score: float) -> PartnerRecord:
        if partner_id not in self._partners:
            raise ValueError("unknown partner")
        p = self._partners[partner_id]
        self._partners[partner_id] = PartnerRecord(p.partner_id, p.company_name, p.partner_type, p.certification_level, p.active, score)
        return self._partners[partner_id]

    @property
    def partner_count(self) -> int:
        return len(self._partners)

    def gold_partners(self) -> list[PartnerRecord]:
        return [p for p in self._partners.values() if p.status == "gold"]

    def probation_partners(self) -> list[PartnerRecord]:
        return [p for p in self._partners.values() if p.status == "probation"]

    def dashboard(self) -> dict[str, Any]:
        total_influenced = sum(e.total_revenue_influenced for e in self._economics.values())
        total_earned = sum(e.total_earned for e in self._economics.values())
        return {
            "total_partners": self.partner_count,
            "gold": len(self.gold_partners()),
            "probation": len(self.probation_partners()),
            "total_revenue_influenced": total_influenced,
            "total_partner_earnings": total_earned,
            "avg_close_rate": sum(e.close_rate for e in self._economics.values()) / max(1, len(self._economics)),
        }
