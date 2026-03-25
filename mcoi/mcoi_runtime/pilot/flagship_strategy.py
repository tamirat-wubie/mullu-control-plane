"""Phase 141 — Flagship Pack Dominance / Reference Expansion."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

FLAGSHIP_PACK = "regulated_ops"
FLAGSHIP_NAME = "Regulated Operations Control Tower"

# 141A — Flagship concentration
@dataclass(frozen=True)
class FlagshipFocus:
    pack_domain: str = FLAGSHIP_PACK
    product_name: str = FLAGSHIP_NAME
    investment_priority: str = "maximum"
    gtm_priority: str = "primary"
    delivery_priority: str = "first_class"
    support_priority: str = "premium"
    engineering_focus: tuple[str, ...] = (
        "evidence_workflow_improvements",
        "remediation_approval_flow",
        "reporting_ux",
        "executive_summaries",
        "copilot_explanations",
        "connector_reliability",
        "deployment_speed",
    )

FLAGSHIP = FlagshipFocus()

# 141B — Reference account program
@dataclass
class ReferenceAccount:
    account_id: str
    company_name: str
    industry: str
    deployment_date: str
    operator_count: int
    executive_sponsor: str
    roi_captured: bool = False
    case_study_published: bool = False
    reference_willing: bool = False
    maturity: str = "early"  # "early", "growing", "mature", "champion"

    @property
    def reference_ready(self) -> bool:
        return self.roi_captured and self.reference_willing and self.maturity in ("mature", "champion")

class ReferenceProgram:
    """Manages flagship reference accounts."""

    def __init__(self):
        self._accounts: list[ReferenceAccount] = []

    def add_account(self, account: ReferenceAccount) -> None:
        self._accounts.append(account)

    def reference_ready_accounts(self) -> list[ReferenceAccount]:
        return [a for a in self._accounts if a.reference_ready]

    def by_maturity(self, maturity: str) -> list[ReferenceAccount]:
        return [a for a in self._accounts if a.maturity == maturity]

    @property
    def total(self) -> int:
        return len(self._accounts)

    def summary(self) -> dict[str, Any]:
        return {
            "total_accounts": self.total,
            "reference_ready": len(self.reference_ready_accounts()),
            "champions": len(self.by_maturity("champion")),
            "mature": len(self.by_maturity("mature")),
            "growing": len(self.by_maturity("growing")),
            "early": len(self.by_maturity("early")),
            "roi_captured": sum(1 for a in self._accounts if a.roi_captured),
            "case_studies": sum(1 for a in self._accounts if a.case_study_published),
        }

# 141C — Flagship roadmap (improvements only for regulated ops)
FLAGSHIP_ROADMAP = (
    {"area": "evidence", "improvement": "Faster evidence bundle assembly with parallel retrieval", "priority": 1},
    {"area": "remediation", "improvement": "Streamlined remediation approval with one-click quorum", "priority": 2},
    {"area": "reporting", "improvement": "Template-based regulatory packet generation", "priority": 3},
    {"area": "executive", "improvement": "Real-time compliance posture dashboard", "priority": 4},
    {"area": "copilot", "improvement": "Evidence-grounded explanation with citation links", "priority": 5},
    {"area": "connectors", "improvement": "Pre-built GRC tool integration bundle", "priority": 6},
    {"area": "deployment", "improvement": "Sub-2-week deployment profile", "priority": 7},
)

# 141D — Expansion playbooks
EXPANSION_PLAYBOOKS = {
    "regulated_to_financial": {
        "land": "regulated_ops",
        "expand_to": "financial_control",
        "trigger": "Customer mentions audit prep burden, SOX compliance, or financial controls",
        "timing": "After 60 days of regulated ops adoption",
        "pitch": "Your compliance team already trusts the evidence and reporting. Extend that to financial controls and settlement tracking.",
        "expected_acv_increase": 1.8,
    },
    "regulated_to_service": {
        "land": "regulated_ops",
        "expand_to": "enterprise_service",
        "trigger": "Customer mentions IT governance gaps or service desk integration needs",
        "timing": "After 90 days or when service-related compliance issues surface",
        "pitch": "The same governance and evidence framework now powers your service operations.",
        "expected_acv_increase": 1.5,
    },
    "factory_to_supply_chain": {
        "land": "factory_quality",
        "expand_to": "supply_chain",
        "trigger": "Customer mentions vendor delays, procurement gaps, or inventory issues",
        "timing": "After 45 days or when supply-related quality issues surface",
        "pitch": "Your plant quality system now extends to procurement and supply chain visibility.",
        "expected_acv_increase": 2.0,
    },
}

# 141E — Incubation lane
INCUBATION_PACKS = {
    "research_lab": {
        "status": "incubated",
        "investment": "minimal",
        "criteria_to_promote": "3+ pilot requests, positive pilot outcomes, margin-positive unit economics",
        "allowed_activities": ("selective_pilots", "product_gap_fixes", "partner_evaluation"),
        "blocked_activities": ("major_gtm_push", "large_engineering_allocation", "new_feature_development"),
    },
}

# 141F — Executive action dashboard
class FlagshipActionDashboard:
    """Executive dashboard for flagship strategy execution."""

    def __init__(self, reference_program: ReferenceProgram):
        self._ref = reference_program

    def generate(self) -> dict[str, Any]:
        ref_summary = self._ref.summary()
        return {
            "flagship": {
                "pack": FLAGSHIP_PACK,
                "name": FLAGSHIP_NAME,
                "focus_areas": len(FLAGSHIP.engineering_focus),
                "roadmap_items": len(FLAGSHIP_ROADMAP),
            },
            "references": ref_summary,
            "expansion_playbooks": len(EXPANSION_PLAYBOOKS),
            "incubation": {pack: info["status"] for pack, info in INCUBATION_PACKS.items()},
            "action_items": [
                f"Capture ROI from {ref_summary['total_accounts'] - ref_summary['roi_captured']} accounts" if ref_summary['total_accounts'] > ref_summary['roi_captured'] else "All ROI captured",
                f"Publish {ref_summary['total_accounts'] - ref_summary['case_studies']} case studies" if ref_summary['total_accounts'] > ref_summary['case_studies'] else "All case studies published",
                f"Promote {ref_summary['growing']} growing accounts to mature" if ref_summary['growing'] > 0 else "No accounts to promote",
            ],
        }
