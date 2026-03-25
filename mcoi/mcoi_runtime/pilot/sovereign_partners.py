"""Phase 154 — Sovereign Partner Scale-Out."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# 154A — SovereignPartnerType Variants (5 types)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SovereignPartnerType:
    name: str
    can_sell: bool
    can_deploy_sovereign: bool
    can_support_sovereign: bool
    clearance_required: str  # "none", "confidential", "secret", "top_secret"
    base_revenue_share_pct: float

SOVEREIGN_PARTNER_TYPES: dict[str, SovereignPartnerType] = {
    "referral_sovereign": SovereignPartnerType(
        "Sovereign Referral Partner", False, False, False,
        "none", 10.0,
    ),
    "reseller_sovereign": SovereignPartnerType(
        "Sovereign Reseller", True, False, False,
        "confidential", 20.0,
    ),
    "implementation_sovereign": SovereignPartnerType(
        "Sovereign Implementation Partner", True, True, False,
        "secret", 30.0,
    ),
    "managed_sovereign": SovereignPartnerType(
        "Sovereign Managed Service Partner", True, True, True,
        "secret", 40.0,
    ),
    "strategic_sovereign": SovereignPartnerType(
        "Strategic Sovereign Ecosystem Partner", True, True, True,
        "top_secret", 35.0,
    ),
}


# ---------------------------------------------------------------------------
# 154B — SovereignCertification Overlay (5 levels)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SovereignCertification:
    level: str
    requirements: tuple[str, ...]
    sovereign_overlay: tuple[str, ...]

SOVEREIGN_CERTIFICATIONS: dict[str, SovereignCertification] = {
    "sovereign_aware": SovereignCertification(
        "sovereign_aware",
        ("security_overview", "data_residency_training"),
        ("sovereign_policy_awareness",),
    ),
    "sovereign_demo_certified": SovereignCertification(
        "sovereign_demo_certified",
        ("sovereign_aware", "product_knowledge_exam", "demo_delivery_observed"),
        ("restricted_connector_demo", "trust_bundle_walkthrough"),
    ),
    "sovereign_implementation_certified": SovereignCertification(
        "sovereign_implementation_certified",
        ("sovereign_demo_certified", "deployment_success_x2", "governance_understanding"),
        ("sovereign_profile_deployment", "air_gap_proficiency", "break_glass_drill"),
    ),
    "sovereign_support_certified": SovereignCertification(
        "sovereign_support_certified",
        ("sovereign_implementation_certified", "support_handling_x5", "escalation_proficiency"),
        ("restricted_support_ops", "on_site_support_readiness", "legal_hold_handling"),
    ),
    "sovereign_bundle_certified": SovereignCertification(
        "sovereign_bundle_certified",
        ("sovereign_support_certified", "multi_pack_deployment", "cross_pack_proficiency"),
        ("classified_adjacent_handling", "sovereign_audit_export", "continuous_monitoring_ops"),
    ),
}


# ---------------------------------------------------------------------------
# 154C — Sovereign Deployment Playbooks per Profile
# ---------------------------------------------------------------------------
SOVEREIGN_DEPLOYMENT_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "sovereign_cloud": {
        "title": "Sovereign Cloud Deployment Playbook",
        "steps": (
            "provision_sovereign_tenant",
            "configure_data_residency_boundary",
            "restrict_connectors_to_allowed",
            "apply_trust_bundle",
            "enable_audit_export_signed",
            "validate_copilot_restrictions",
            "run_acceptance_suite",
        ),
        "partner_clearance_min": "confidential",
        "estimated_days": 14,
    },
    "restricted_network": {
        "title": "Restricted Network Deployment Playbook",
        "steps": (
            "prepare_air_gap_package",
            "deploy_to_restricted_network",
            "configure_offline_connectors",
            "apply_high_security_trust_bundle",
            "disable_external_copilot",
            "validate_data_boundary_isolation",
            "run_restricted_acceptance_suite",
        ),
        "partner_clearance_min": "secret",
        "estimated_days": 30,
    },
    "on_prem": {
        "title": "On-Premises Deployment Playbook",
        "steps": (
            "ship_deployment_artifact",
            "install_on_customer_hardware",
            "configure_customer_identity",
            "restrict_cloud_connectors",
            "apply_customer_trust_bundle",
            "validate_local_data_residency",
            "run_on_prem_acceptance_suite",
        ),
        "partner_clearance_min": "secret",
        "estimated_days": 21,
    },
    "partner_operated": {
        "title": "Partner-Operated Sovereign Playbook",
        "steps": (
            "provision_partner_managed_tenant",
            "configure_partner_data_boundary",
            "restrict_to_partner_connectors",
            "apply_partner_gov_trust_bundle",
            "set_copilot_restricted_mode",
            "validate_partner_audit_trail",
            "run_partner_acceptance_suite",
        ),
        "partner_clearance_min": "confidential",
        "estimated_days": 14,
    },
    "air_gapped": {
        "title": "Air-Gapped Deployment Playbook",
        "steps": (
            "prepare_offline_media",
            "deploy_via_secure_transfer",
            "configure_certificate_identity",
            "disable_all_external_connectors",
            "apply_classified_trust_bundle",
            "disable_copilot_entirely",
            "run_offline_acceptance_suite",
        ),
        "partner_clearance_min": "top_secret",
        "estimated_days": 45,
    },
}


# ---------------------------------------------------------------------------
# 154D — Partner Pipeline & Reference Tracking
# ---------------------------------------------------------------------------
@dataclass
class SovereignPartnerRecord:
    partner_id: str
    company_name: str
    partner_type: str  # key into SOVEREIGN_PARTNER_TYPES
    certification_level: str  # key into SOVEREIGN_CERTIFICATIONS
    clearance_level: str  # "none", "confidential", "secret", "top_secret"
    active: bool = True
    quality_score: float = 0.0  # 0-10
    references_delivered: int = 0

    @property
    def status(self) -> str:
        if not self.active:
            return "inactive"
        if self.quality_score >= 8:
            return "gold"
        if self.quality_score >= 6:
            return "silver"
        if self.quality_score >= 4:
            return "bronze"
        return "probation"


@dataclass
class SovereignPartnerReference:
    reference_id: str
    partner_id: str
    account_name: str
    sector: str
    deployment_profile: str
    success: bool = False


class SovereignPartnerPipeline:
    """Manages sovereign partner lifecycle, references, and governance."""

    def __init__(self) -> None:
        self._partners: dict[str, SovereignPartnerRecord] = {}
        self._references: list[SovereignPartnerReference] = []

    def onboard(self, record: SovereignPartnerRecord) -> SovereignPartnerRecord:
        if record.partner_id in self._partners:
            raise ValueError(f"Partner {record.partner_id} already exists")
        self._partners[record.partner_id] = record
        return record

    def certify(self, partner_id: str, level: str) -> SovereignPartnerRecord:
        if partner_id not in self._partners:
            raise ValueError(f"Unknown partner: {partner_id}")
        p = self._partners[partner_id]
        p_new = SovereignPartnerRecord(
            p.partner_id, p.company_name, p.partner_type, level,
            p.clearance_level, p.active, p.quality_score, p.references_delivered,
        )
        self._partners[partner_id] = p_new
        return p_new

    def update_quality(self, partner_id: str, score: float) -> SovereignPartnerRecord:
        if partner_id not in self._partners:
            raise ValueError(f"Unknown partner: {partner_id}")
        p = self._partners[partner_id]
        p_new = SovereignPartnerRecord(
            p.partner_id, p.company_name, p.partner_type, p.certification_level,
            p.clearance_level, p.active, score, p.references_delivered,
        )
        self._partners[partner_id] = p_new
        return p_new

    def add_reference(self, ref: SovereignPartnerReference) -> None:
        self._references.append(ref)
        if ref.success and ref.partner_id in self._partners:
            p = self._partners[ref.partner_id]
            self._partners[ref.partner_id] = SovereignPartnerRecord(
                p.partner_id, p.company_name, p.partner_type, p.certification_level,
                p.clearance_level, p.active, p.quality_score, p.references_delivered + 1,
            )

    def get_partner(self, partner_id: str) -> SovereignPartnerRecord:
        if partner_id not in self._partners:
            raise ValueError(f"Unknown partner: {partner_id}")
        return self._partners[partner_id]

    @property
    def partner_count(self) -> int:
        return len(self._partners)

    def gold_partners(self) -> list[SovereignPartnerRecord]:
        return [p for p in self._partners.values() if p.status == "gold"]

    def references_for_partner(self, partner_id: str) -> list[SovereignPartnerReference]:
        return [r for r in self._references if r.partner_id == partner_id]

    def dashboard(self) -> dict[str, Any]:
        successful_refs = [r for r in self._references if r.success]
        return {
            "total_partners": self.partner_count,
            "gold": len(self.gold_partners()),
            "active": len([p for p in self._partners.values() if p.active]),
            "total_references": len(self._references),
            "successful_references": len(successful_refs),
            "sectors_covered": list({r.sector for r in self._references}),
        }


# ---------------------------------------------------------------------------
# 154E — Sovereign Economics with Premium Logic
# ---------------------------------------------------------------------------
CLEARANCE_PREMIUM: dict[str, float] = {
    "none": 1.0,
    "confidential": 1.15,
    "secret": 1.30,
    "top_secret": 1.50,
}

DEPLOYMENT_PREMIUM: dict[str, float] = {
    "sovereign_cloud": 1.0,
    "restricted_network": 1.25,
    "on_prem": 1.20,
    "partner_operated": 1.10,
    "air_gapped": 1.50,
}


@dataclass
class SovereignPartnerEconomics:
    partner_id: str
    partner_type: str
    clearance_level: str
    deals_sourced: int = 0
    deals_closed: int = 0
    total_revenue_influenced: float = 0.0
    partner_earnings: float = 0.0

    @property
    def close_rate(self) -> float:
        return self.deals_closed / self.deals_sourced if self.deals_sourced else 0.0

    def record_deal(self, revenue: float, deployment_model: str, closed: bool = False) -> float:
        """Record a deal and return the partner payout for this deal (0 if not closed)."""
        self.deals_sourced += 1
        self.total_revenue_influenced += revenue
        if not closed:
            return 0.0
        self.deals_closed += 1
        ptype = SOVEREIGN_PARTNER_TYPES.get(self.partner_type)
        base_share = ptype.base_revenue_share_pct / 100 if ptype else 0.0
        clearance_mult = CLEARANCE_PREMIUM.get(self.clearance_level, 1.0)
        deploy_mult = DEPLOYMENT_PREMIUM.get(deployment_model, 1.0)
        payout = round(revenue * base_share * clearance_mult * deploy_mult, 2)
        self.partner_earnings += payout
        return payout


# ---------------------------------------------------------------------------
# 154F — Golden Proof Function
# ---------------------------------------------------------------------------
def golden_proof_sovereign_partners() -> dict[str, Any]:
    """Exercises the full sovereign partner scale-out flow end-to-end."""
    results: dict[str, Any] = {"steps": []}

    # 1. Partner types
    assert len(SOVEREIGN_PARTNER_TYPES) == 5
    strat = SOVEREIGN_PARTNER_TYPES["strategic_sovereign"]
    assert strat.can_sell and strat.can_deploy_sovereign and strat.can_support_sovereign
    assert strat.clearance_required == "top_secret"
    results["steps"].append("partner_types_validated")

    # 2. Certifications
    assert len(SOVEREIGN_CERTIFICATIONS) == 5
    bundle_cert = SOVEREIGN_CERTIFICATIONS["sovereign_bundle_certified"]
    assert "sovereign_audit_export" in bundle_cert.sovereign_overlay
    results["steps"].append("certifications_validated")

    # 3. Playbooks
    assert len(SOVEREIGN_DEPLOYMENT_PLAYBOOKS) == 5
    for pb in SOVEREIGN_DEPLOYMENT_PLAYBOOKS.values():
        assert pb["title"]
        assert len(pb["steps"]) >= 7
        assert pb["estimated_days"] > 0
    results["steps"].append("playbooks_validated")

    # 4. Pipeline
    pipeline = SovereignPartnerPipeline()
    rec = SovereignPartnerRecord(
        "sp-001", "GovSecure Corp", "managed_sovereign",
        "sovereign_implementation_certified", "secret", True, 8.5, 0,
    )
    pipeline.onboard(rec)
    assert pipeline.partner_count == 1
    assert pipeline.get_partner("sp-001").status == "gold"

    ref = SovereignPartnerReference(
        "ref-001", "sp-001", "Dept of Finance", "civilian",
        "sovereign_cloud", True,
    )
    pipeline.add_reference(ref)
    assert pipeline.get_partner("sp-001").references_delivered == 1
    results["steps"].append("pipeline_validated")

    # 5. Economics
    econ = SovereignPartnerEconomics(
        "sp-001", "managed_sovereign", "secret",
    )
    payout = econ.record_deal(100_000, "sovereign_cloud", closed=True)
    assert payout > 0
    assert econ.deals_closed == 1
    assert econ.partner_earnings == payout
    # Premium: base 40% * clearance 1.30 * deploy 1.0 = 52000
    expected = round(100_000 * 0.40 * 1.30 * 1.0, 2)
    assert payout == expected
    results["steps"].append("economics_validated")

    # 6. Dashboard
    dash = pipeline.dashboard()
    assert dash["total_partners"] == 1
    assert dash["gold"] == 1
    assert dash["successful_references"] == 1
    results["steps"].append("dashboard_validated")

    results["status"] = "PASS"
    results["subsections"] = ("154A", "154B", "154C", "154D", "154E", "154F")
    return results
