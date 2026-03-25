"""Phases 175-176 — EngineBase Adoption + International Partner Onboarding."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# Phase 175 — EngineBase Adoption
ENGINE_ADOPTION_TIERS = {
    "tier_1_critical": ["billing_runtime", "settlement_runtime", "customer_runtime", "marketplace_runtime", "public_api", "external_execution", "constitutional_governance", "meta_orchestration", "continuity_runtime"],
    "tier_2_important": ["llm_runtime", "copilot_runtime", "persona_runtime", "multimodal_runtime", "memory_consolidation", "self_tuning", "ledger_runtime", "identity_security", "distributed_runtime"],
    "tier_3_standard": ["factory_runtime", "research_runtime", "data_quality", "observability_runtime", "operator_workspace", "product_console", "policy_simulation", "knowledge_query", "workforce_runtime"],
    "tier_4_foundational": ["asset_runtime", "case_runtime", "change_runtime", "contract_runtime", "forecasting_runtime", "human_workflow", "partner_runtime", "procurement_runtime", "records_runtime", "remediation_runtime", "service_catalog", "tenant_runtime"],
}

@dataclass
class AdoptionTracker:
    adopted: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    def adopt(self, engine: str) -> None:
        if engine not in self.adopted:
            self.adopted.append(engine)
            if engine in self.pending:
                self.pending.remove(engine)

    def add_pending(self, engine: str) -> None:
        if engine not in self.pending and engine not in self.adopted:
            self.pending.append(engine)

    @property
    def adoption_rate(self) -> float:
        total = len(self.adopted) + len(self.pending)
        return len(self.adopted) / total if total else 0.0

    def summary(self) -> dict[str, Any]:
        return {"adopted": len(self.adopted), "pending": len(self.pending), "rate": round(self.adoption_rate, 3)}

# Phase 176 — International Partner Onboarding
@dataclass(frozen=True)
class RegionalPartnerOnboardingPlan:
    region: str
    partner_target_count: int
    certification_variant: str
    priority_bundles: tuple[str, ...]
    estimated_onboarding_weeks: int
    local_support_required: bool

REGIONAL_ONBOARDING_PLANS = {
    "us": RegionalPartnerOnboardingPlan("us", 10, "standard", ("regulated_financial", "service_governance", "industrial"), 4, False),
    "eu": RegionalPartnerOnboardingPlan("eu", 8, "eu_certified", ("regulated_financial", "public_sector_governance", "healthcare_financial"), 6, True),
    "uk": RegionalPartnerOnboardingPlan("uk", 5, "uk_certified", ("regulated_financial", "service_governance"), 5, True),
    "sg": RegionalPartnerOnboardingPlan("sg", 4, "apac_certified", ("service_governance", "financial_control"), 6, True),
    "ae": RegionalPartnerOnboardingPlan("ae", 3, "mena_certified", ("public_sector_governance", "regulated_ops"), 8, True),
}

class InternationalPartnerPipeline:
    def __init__(self):
        self._pipeline: dict[str, list[dict[str, Any]]] = {}

    def add_partner_prospect(self, region: str, partner_name: str, capability: str) -> None:
        self._pipeline.setdefault(region, []).append({"name": partner_name, "capability": capability, "status": "prospect"})

    def onboard_partner(self, region: str, partner_name: str) -> None:
        for p in self._pipeline.get(region, []):
            if p["name"] == partner_name:
                p["status"] = "onboarded"

    def by_region(self) -> dict[str, int]:
        return {r: len(ps) for r, ps in self._pipeline.items()}

    def onboarded_count(self) -> int:
        return sum(1 for ps in self._pipeline.values() for p in ps if p["status"] == "onboarded")

    def summary(self) -> dict[str, Any]:
        return {"regions": len(self._pipeline), "total_prospects": sum(len(ps) for ps in self._pipeline.values()), "onboarded": self.onboarded_count()}
