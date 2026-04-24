"""Phase 152 — Sovereign / Public-Sector Market Entry & Reference Program."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# 152A — Sovereign Target Account Scoring & Engine
# ---------------------------------------------------------------------------
@dataclass
class SovereignTargetAccount:
    account_id: str
    agency_name: str
    sector: str  # "defense", "civilian", "intelligence", "state_local", "health", "justice"
    trust_fit: float = 0.0           # 0-10
    residency_fit: float = 0.0       # 0-10
    connector_feasibility: float = 0.0  # 0-10
    procurement_complexity: float = 0.0  # 0-10 (lower = easier)
    buyer_urgency: float = 0.0       # 0-10
    reference_value: float = 0.0     # 0-10

    @property
    def composite_score(self) -> float:
        return round(
            self.trust_fit * 0.20 +
            self.residency_fit * 0.15 +
            self.connector_feasibility * 0.15 +
            (10 - self.procurement_complexity) * 0.15 +
            self.buyer_urgency * 0.20 +
            self.reference_value * 0.15,
            3,
        )

    @property
    def tier(self) -> str:
        s = self.composite_score
        if s >= 7.0:
            return "tier_1"
        if s >= 5.0:
            return "tier_2"
        return "tier_3"


class SovereignTargetEngine:
    def __init__(self) -> None:
        self._accounts: list[SovereignTargetAccount] = []

    def add_account(self, account: SovereignTargetAccount) -> None:
        self._accounts.append(account)

    def rank(self) -> list[SovereignTargetAccount]:
        return sorted(self._accounts, key=lambda a: a.composite_score, reverse=True)

    def by_sector(self, sector: str) -> list[SovereignTargetAccount]:
        return [a for a in self._accounts if a.sector == sector]

    def tier_1_accounts(self) -> list[SovereignTargetAccount]:
        return [a for a in self._accounts if a.tier == "tier_1"]

    @property
    def total(self) -> int:
        return len(self._accounts)


# ---------------------------------------------------------------------------
# 152B — Procurement / Compliance Package
# ---------------------------------------------------------------------------
PROCUREMENT_PACKAGE: dict[str, dict[str, Any]] = {
    "security_matrix": {
        "title": "Security and Access Control Matrix",
        "sections": ("identity_management", "access_control", "audit_logging", "encryption", "data_residency", "incident_response"),
    },
    "residency_statement": {
        "title": "Data Residency and Sovereignty Statement",
        "sections": ("storage_locations", "processing_boundaries", "cross_border_restrictions", "retention_policy", "deletion_guarantees"),
    },
    "deployment_comparison": {
        "title": "Deployment Model Comparison",
        "sections": ("sovereign_cloud", "restricted_network", "on_premises", "partner_operated", "hybrid_options"),
    },
    "connector_matrix": {
        "title": "Connector Compatibility and Restriction Matrix",
        "sections": ("allowed_connectors", "restricted_connectors", "blocked_connectors", "offline_alternatives", "approval_process"),
    },
    "copilot_restrictions": {
        "title": "Symbolic Intelligence Copilot Governance and Restrictions",
        "sections": ("copilot_modes", "generation_restrictions", "explain_only_mode", "disabled_mode", "override_tracking"),
    },
    "support_model": {
        "title": "Support Model for Sovereign Deployments",
        "sections": ("support_tiers", "response_times", "escalation_path", "on_site_support", "partner_support"),
    },
    "audit_package": {
        "title": "Audit and Evidence Export Package",
        "sections": ("export_formats", "signing_verification", "chain_of_custody", "retention_compliance", "legal_hold"),
    },
    "pilot_checklist": {
        "title": "Sovereign Pilot Readiness Checklist",
        "sections": ("qualification", "profile_selection", "trust_bundle", "bootstrap", "connector_verification", "go_live"),
    },
}


# ---------------------------------------------------------------------------
# 152C — Sovereign Partner Profile & Requirements
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SovereignPartnerProfile:
    partner_id: str
    company_name: str
    sovereign_certified: bool
    clearance_level: str  # "none", "confidential", "secret", "top_secret"
    deployment_capability: tuple[str, ...]  # ("sovereign_cloud", "on_prem", ...)

    @property
    def can_deploy_restricted(self) -> bool:
        return self.sovereign_certified and self.clearance_level in ("secret", "top_secret")


SOVEREIGN_PARTNER_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "basic_sovereign": {
        "title": "Basic Sovereign Partner",
        "sovereign_certified": True,
        "min_clearance": "confidential",
        "deployment_capabilities": ("sovereign_cloud",),
        "certifications": ("demo_certified", "implementation_certified"),
        "audit_requirements": ("annual_security_review",),
    },
    "advanced_sovereign": {
        "title": "Advanced Sovereign Partner",
        "sovereign_certified": True,
        "min_clearance": "secret",
        "deployment_capabilities": ("sovereign_cloud", "on_prem", "restricted_network"),
        "certifications": ("demo_certified", "implementation_certified", "support_certified"),
        "audit_requirements": ("annual_security_review", "penetration_test", "compliance_attestation"),
    },
    "strategic_sovereign": {
        "title": "Strategic Sovereign Partner",
        "sovereign_certified": True,
        "min_clearance": "top_secret",
        "deployment_capabilities": ("sovereign_cloud", "on_prem", "restricted_network", "air_gapped"),
        "certifications": ("demo_certified", "implementation_certified", "support_certified", "bundle_certified"),
        "audit_requirements": ("annual_security_review", "penetration_test", "compliance_attestation", "continuous_monitoring"),
    },
}


# ---------------------------------------------------------------------------
# 152D — Sovereign Reference Account & Program
# ---------------------------------------------------------------------------
@dataclass
class SovereignReferenceAccount:
    account_id: str
    agency_name: str
    sector: str
    profile_used: str  # sovereign profile id
    trust_bundle: str  # trust bundle id
    procurement_hurdles_cleared: int = 0
    rollout_milestones: int = 0
    time_to_approval_days: int = 0
    reference_ready: bool = False

    @property
    def maturity(self) -> str:
        if self.reference_ready and self.rollout_milestones >= 5:
            return "champion"
        if self.rollout_milestones >= 3:
            return "mature"
        if self.rollout_milestones >= 1:
            return "growing"
        return "early"


class SovereignReferenceProgram:
    def __init__(self) -> None:
        self._accounts: list[SovereignReferenceAccount] = []

    def add_account(self, account: SovereignReferenceAccount) -> None:
        self._accounts.append(account)

    @property
    def total(self) -> int:
        return len(self._accounts)

    def reference_ready_accounts(self) -> list[SovereignReferenceAccount]:
        return [a for a in self._accounts if a.reference_ready]

    def by_sector(self, sector: str) -> list[SovereignReferenceAccount]:
        return [a for a in self._accounts if a.sector == sector]

    def summary(self) -> dict[str, Any]:
        return {
            "total_accounts": self.total,
            "reference_ready": len(self.reference_ready_accounts()),
            "champions": len([a for a in self._accounts if a.maturity == "champion"]),
            "avg_approval_days": (
                round(sum(a.time_to_approval_days for a in self._accounts) / self.total)
                if self.total else 0
            ),
            "sectors": list({a.sector for a in self._accounts}),
        }


# ---------------------------------------------------------------------------
# 152E — Sovereign Pilot Motion (8 steps)
# ---------------------------------------------------------------------------
SOVEREIGN_PILOT_MOTION: tuple[dict[str, Any], ...] = (
    {"step": 1, "name": "qualify", "description": "Qualify sovereign account against target criteria"},
    {"step": 2, "name": "profile", "description": "Select sovereign deployment profile and trust bundle"},
    {"step": 3, "name": "package", "description": "Assemble procurement and compliance package"},
    {"step": 4, "name": "deploy", "description": "Bootstrap tenant in sovereign deployment model"},
    {"step": 5, "name": "validate", "description": "Validate data residency, connectors, and security controls"},
    {"step": 6, "name": "workflow", "description": "Run end-to-end case workflow in restricted mode"},
    {"step": 7, "name": "metrics", "description": "Capture pilot success metrics and ROI evidence"},
    {"step": 8, "name": "promote", "description": "Promote account to reference-ready status"},
)


# ---------------------------------------------------------------------------
# 152F — Golden Proof
# ---------------------------------------------------------------------------
def golden_proof_sovereign_market() -> dict[str, Any]:
    """Exercises the full sovereign market entry flow end-to-end."""
    results: dict[str, Any] = {"steps": []}

    # 1. Build target engine and score accounts
    engine = SovereignTargetEngine()
    acct_a = SovereignTargetAccount(
        "sov-acct-001", "Dept of Finance", "civilian",
        trust_fit=9, residency_fit=8, connector_feasibility=7,
        procurement_complexity=4, buyer_urgency=8, reference_value=9,
    )
    acct_b = SovereignTargetAccount(
        "sov-acct-002", "State Health Agency", "health",
        trust_fit=6, residency_fit=7, connector_feasibility=8,
        procurement_complexity=6, buyer_urgency=5, reference_value=6,
    )
    engine.add_account(acct_a)
    engine.add_account(acct_b)
    ranked = engine.rank()
    assert ranked[0].account_id == "sov-acct-001"
    assert engine.total == 2
    results["steps"].append("target_engine_ranked")

    # 2. Validate procurement package
    assert len(PROCUREMENT_PACKAGE) == 8
    for artifact in PROCUREMENT_PACKAGE.values():
        assert artifact["title"]
        assert len(artifact["sections"]) >= 4
    results["steps"].append("procurement_package_validated")

    # 3. Partner profile
    partner = SovereignPartnerProfile(
        "sp-001", "GovTech Partners", True, "secret", ("sovereign_cloud", "on_prem"),
    )
    assert partner.can_deploy_restricted
    assert len(SOVEREIGN_PARTNER_REQUIREMENTS) == 3
    results["steps"].append("partner_profile_validated")

    # 4. Reference program
    ref_prog = SovereignReferenceProgram()
    ref_acct = SovereignReferenceAccount(
        "sov-acct-001", "Dept of Finance", "civilian",
        "sov-cloud", "trust-std-gov",
        procurement_hurdles_cleared=5, rollout_milestones=6,
        time_to_approval_days=45, reference_ready=True,
    )
    ref_prog.add_account(ref_acct)
    assert ref_prog.total == 1
    assert ref_acct.maturity == "champion"
    assert len(ref_prog.reference_ready_accounts()) == 1
    results["steps"].append("reference_program_validated")

    # 5. Pilot motion
    assert len(SOVEREIGN_PILOT_MOTION) == 8
    step_names = tuple(s["name"] for s in SOVEREIGN_PILOT_MOTION)
    assert step_names == ("qualify", "profile", "package", "deploy", "validate", "workflow", "metrics", "promote")
    results["steps"].append("pilot_motion_validated")

    # 6. Summary
    summary = ref_prog.summary()
    assert summary["total_accounts"] == 1
    assert summary["champions"] == 1
    results["steps"].append("summary_validated")

    results["status"] = "PASS"
    results["subsections"] = ("152A", "152B", "152C", "152D", "152E", "152F")
    return results
