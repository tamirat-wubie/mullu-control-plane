"""Phase 156 — Sovereign Multi-Region Channel Scaling."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# 156A — REGION_BUNDLE_MATRIX
# ---------------------------------------------------------------------------

REGION_BUNDLE_MATRIX: dict[str, dict[str, Any]] = {
    "us": {
        "allowed_bundles": ("regulated_ops", "enterprise_service", "financial_control", "factory_quality"),
        "sovereign_profiles": ("fedramp_moderate", "fedramp_high", "itar"),
        "partner_types": ("var", "msp", "si", "co_sell"),
        "compliance_bundle": "soc2_hipaa_fedramp",
        "connector_set": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export", "gov_cloud"),
    },
    "eu": {
        "allowed_bundles": ("regulated_ops", "enterprise_service", "financial_control"),
        "sovereign_profiles": ("gdpr_standard", "gdpr_strict", "eu_sovereign_cloud"),
        "partner_types": ("var", "msp", "si"),
        "compliance_bundle": "gdpr_iso27001",
        "connector_set": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export", "eu_data_residency"),
    },
    "uk": {
        "allowed_bundles": ("regulated_ops", "enterprise_service", "financial_control"),
        "sovereign_profiles": ("uk_gdpr", "cyber_essentials_plus", "nhs_dspt"),
        "partner_types": ("var", "msp", "si", "co_sell"),
        "compliance_bundle": "uk_gdpr_ce_plus",
        "connector_set": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export", "uk_gov_cloud"),
    },
    "sg": {
        "allowed_bundles": ("regulated_ops", "enterprise_service"),
        "sovereign_profiles": ("pdpa_standard", "mas_regulated"),
        "partner_types": ("var", "msp"),
        "compliance_bundle": "pdpa_mas",
        "connector_set": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export", "apac_relay"),
    },
    "ae": {
        "allowed_bundles": ("regulated_ops",),
        "sovereign_profiles": ("uae_ias", "difc_regulated"),
        "partner_types": ("msp", "si"),
        "compliance_bundle": "uae_ias_difc",
        "connector_set": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export", "me_data_residency"),
    },
}


# ---------------------------------------------------------------------------
# 156B — route_sovereign_opportunity
# ---------------------------------------------------------------------------

_ROUTING_RULES: list[tuple[Any, str]] = [
    # (predicate, routing_decision)
]


def route_sovereign_opportunity(
    region: str,
    buyer_type: str,
    trust_requirement: str,
    bundle: str,
) -> str:
    """Return routing decision for a sovereign opportunity."""
    matrix = REGION_BUNDLE_MATRIX.get(region)
    if matrix is None:
        return "restricted_specialist"

    if bundle not in matrix["allowed_bundles"]:
        return "restricted_specialist"

    # High-trust sovereign profiles always need managed sovereign
    high_trust = {
        "fedramp_high", "itar", "eu_sovereign_cloud",
        "nhs_dspt", "mas_regulated", "difc_regulated",
    }
    if trust_requirement in high_trust:
        return "managed_sovereign"

    # Government / public-sector buyers route to partner-led
    if buyer_type == "government":
        return "partner_led"

    # Co-sell available and enterprise buyer
    if buyer_type == "enterprise" and "co_sell" in matrix["partner_types"]:
        return "co_sell"

    # Default for standard commercial
    if buyer_type in ("smb", "commercial"):
        return "direct"

    return "partner_led"


# ---------------------------------------------------------------------------
# 156C — REGIONAL_PARTNER_PLAYBOOKS
# ---------------------------------------------------------------------------

REGIONAL_PARTNER_PLAYBOOKS: dict[str, dict[str, dict[str, Any]]] = {
    "regulated_ops": {
        "us": {"deployment_model": "private_cloud", "trust_bundle": "fedramp_moderate", "pricing_multiplier": 1.25, "estimated_days": 45},
        "eu": {"deployment_model": "eu_sovereign", "trust_bundle": "gdpr_standard", "pricing_multiplier": 1.30, "estimated_days": 50},
        "uk": {"deployment_model": "uk_gov_cloud", "trust_bundle": "cyber_essentials_plus", "pricing_multiplier": 1.20, "estimated_days": 40},
        "sg": {"deployment_model": "apac_managed", "trust_bundle": "pdpa_standard", "pricing_multiplier": 1.15, "estimated_days": 35},
        "ae": {"deployment_model": "me_sovereign", "trust_bundle": "uae_ias", "pricing_multiplier": 1.40, "estimated_days": 60},
    },
    "enterprise_service": {
        "us": {"deployment_model": "hybrid_cloud", "trust_bundle": "soc2_hipaa", "pricing_multiplier": 1.15, "estimated_days": 30},
        "eu": {"deployment_model": "eu_hybrid", "trust_bundle": "gdpr_strict", "pricing_multiplier": 1.25, "estimated_days": 40},
        "uk": {"deployment_model": "uk_hybrid", "trust_bundle": "uk_gdpr", "pricing_multiplier": 1.15, "estimated_days": 35},
        "sg": {"deployment_model": "apac_hybrid", "trust_bundle": "mas_regulated", "pricing_multiplier": 1.20, "estimated_days": 35},
    },
    "financial_control": {
        "us": {"deployment_model": "private_cloud", "trust_bundle": "fedramp_high", "pricing_multiplier": 1.35, "estimated_days": 55},
        "eu": {"deployment_model": "eu_sovereign", "trust_bundle": "gdpr_strict", "pricing_multiplier": 1.40, "estimated_days": 60},
        "uk": {"deployment_model": "uk_gov_cloud", "trust_bundle": "nhs_dspt", "pricing_multiplier": 1.30, "estimated_days": 50},
    },
    "factory_quality": {
        "us": {"deployment_model": "edge_hybrid", "trust_bundle": "itar", "pricing_multiplier": 1.50, "estimated_days": 70},
    },
}


# ---------------------------------------------------------------------------
# 156D — compute_sovereign_economics
# ---------------------------------------------------------------------------

_PARTNER_SHARE_RATES: dict[str, float] = {
    "var": 0.20,
    "msp": 0.25,
    "si": 0.30,
    "co_sell": 0.15,
}

_SOVEREIGN_PREMIUM_RATES: dict[str, float] = {
    "us": 0.10,
    "eu": 0.15,
    "uk": 0.12,
    "sg": 0.08,
    "ae": 0.20,
}


def compute_sovereign_economics(
    base_revenue: float,
    region: str,
    profile: str,
    bundle: str,
    partner_type: str,
) -> dict[str, float]:
    """Return economics breakdown for a sovereign deal."""
    playbook = REGIONAL_PARTNER_PLAYBOOKS.get(bundle, {}).get(region, {})
    multiplier = playbook.get("pricing_multiplier", 1.0)
    adjusted_revenue = base_revenue * multiplier

    sovereign_premium = adjusted_revenue * _SOVEREIGN_PREMIUM_RATES.get(region, 0.10)
    partner_share = adjusted_revenue * _PARTNER_SHARE_RATES.get(partner_type, 0.20)
    margin_after_share = adjusted_revenue - partner_share + sovereign_premium
    total_cost = adjusted_revenue - margin_after_share

    return {
        "adjusted_revenue": round(adjusted_revenue, 2),
        "partner_share": round(partner_share, 2),
        "sovereign_premium": round(sovereign_premium, 2),
        "margin_after_share": round(margin_after_share, 2),
        "total_cost": round(total_cost, 2),
    }


# ---------------------------------------------------------------------------
# 156E — SovereignGlobalDashboard
# ---------------------------------------------------------------------------

@dataclass
class SovereignGlobalDashboard:
    """Tracks sovereign pipeline by region, partner opportunities, deployment mix, and margin."""

    pipeline_by_region: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    partner_opportunities: list[dict[str, Any]] = field(default_factory=list)
    deployment_mix: dict[str, int] = field(default_factory=dict)
    margin_by_region: dict[str, float] = field(default_factory=dict)

    def add_opportunity(
        self, region: str, bundle: str, partner_type: str,
        base_revenue: float, profile: str,
    ) -> dict[str, Any]:
        routing = route_sovereign_opportunity(region, "enterprise", profile, bundle)
        economics = compute_sovereign_economics(base_revenue, region, profile, bundle, partner_type)

        entry: dict[str, Any] = {
            "region": region,
            "bundle": bundle,
            "partner_type": partner_type,
            "routing": routing,
            **economics,
        }

        self.pipeline_by_region.setdefault(region, []).append(entry)
        self.partner_opportunities.append(entry)

        playbook = REGIONAL_PARTNER_PLAYBOOKS.get(bundle, {}).get(region, {})
        model = playbook.get("deployment_model", "standard")
        self.deployment_mix[model] = self.deployment_mix.get(model, 0) + 1

        self.margin_by_region[region] = (
            self.margin_by_region.get(region, 0.0) + economics["margin_after_share"]
        )
        return entry

    def summary(self) -> dict[str, Any]:
        return {
            "total_opportunities": len(self.partner_opportunities),
            "regions_active": list(self.pipeline_by_region.keys()),
            "deployment_mix": dict(self.deployment_mix),
            "margin_by_region": {k: round(v, 2) for k, v in self.margin_by_region.items()},
        }


# ---------------------------------------------------------------------------
# 156F — golden_proof_sovereign_scaling
# ---------------------------------------------------------------------------

def golden_proof_sovereign_scaling() -> dict[str, Any]:
    """Exercise all 156 subsections and return proof artefact."""
    proof: dict[str, Any] = {}

    # 156A — matrix coverage
    proof["matrix_regions"] = list(REGION_BUNDLE_MATRIX.keys())
    assert len(proof["matrix_regions"]) == 5

    # 156B — routing decisions
    proof["routing_samples"] = {
        "us_enterprise": route_sovereign_opportunity("us", "enterprise", "fedramp_moderate", "regulated_ops"),
        "eu_government": route_sovereign_opportunity("eu", "government", "gdpr_standard", "regulated_ops"),
        "ae_high_trust": route_sovereign_opportunity("ae", "enterprise", "difc_regulated", "regulated_ops"),
        "unknown_region": route_sovereign_opportunity("xx", "enterprise", "none", "regulated_ops"),
    }

    # 156C — playbook coverage
    proof["playbook_bundles"] = list(REGIONAL_PARTNER_PLAYBOOKS.keys())

    # 156D — economics sample
    proof["economics_sample"] = compute_sovereign_economics(
        10000.0, "us", "fedramp_moderate", "regulated_ops", "var",
    )

    # 156E — dashboard
    dashboard = SovereignGlobalDashboard()
    for region in ("us", "eu", "uk"):
        dashboard.add_opportunity(region, "regulated_ops", "msp", 10000.0, "fedramp_moderate")
    dashboard.add_opportunity("sg", "enterprise_service", "var", 8000.0, "pdpa_standard")
    dashboard.add_opportunity("ae", "regulated_ops", "si", 15000.0, "uae_ias")
    proof["dashboard_summary"] = dashboard.summary()

    assert proof["dashboard_summary"]["total_opportunities"] == 5
    assert len(proof["dashboard_summary"]["regions_active"]) == 5

    proof["status"] = "pass"
    return proof
