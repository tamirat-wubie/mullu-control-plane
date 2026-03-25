"""Phase 165 — Scientific Governance Suite (Research Lab + Regulated Ops Bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.research_lab_pack import ResearchLabPackBootstrap
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Scientific Governance Suite"
BUNDLE_PACKS = ("research_lab", "regulated_ops")

@dataclass(frozen=True)
class ScientificGovernanceBundlePricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 5000.0
    monthly_bundled: float = 4250.0
    annual_savings: float = 9000.0  # (5000-4250)*12
    discount_percent: float = 15.0

SCIENTIFIC_GOVERNANCE_PRICING = ScientificGovernanceBundlePricing()

@dataclass(frozen=True)
class ScientificGovernanceStitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str

STITCHED_WORKFLOWS = (
    ScientificGovernanceStitchedWorkflow(
        "research_finding_triggers_compliance_review", "research_lab", "regulated_ops",
        "Research finding triggers a compliance review in regulated operations"),
    ScientificGovernanceStitchedWorkflow(
        "regulatory_requirement_opens_study", "regulated_ops", "research_lab",
        "Regulatory requirement opens a new study or investigation in the research lab"),
    ScientificGovernanceStitchedWorkflow(
        "evidence_spans_research_and_compliance", "research_lab", "regulated_ops",
        "Evidence gathered in research is shared with compliance tracking in regulated ops"),
    ScientificGovernanceStitchedWorkflow(
        "executive_combined_research_compliance", "research_lab", "regulated_ops",
        "Executive dashboard combines research posture with regulatory compliance status"),
    ScientificGovernanceStitchedWorkflow(
        "copilot_cross_scientific_regulatory", "research_lab", "regulated_ops",
        "Copilot explains a case using both research lab and regulated operations evidence"),
)


class ScientificGovernanceBundle:
    """One-call deployment for the bundled Research Lab + Regulated Ops suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._research_lab = ResearchLabPackBootstrap(self._es)
        self._regulated_ops = PilotTenantBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy research lab pack
        res_result = self._research_lab.bootstrap(f"{tenant_id}-res")
        result["research_lab"] = res_result
        result["packs_deployed"].append("research_lab")

        # 2. Deploy regulated ops pack
        reg_result = self._regulated_ops.bootstrap(f"{tenant_id}-reg")
        result["regulated_ops"] = reg_result
        result["packs_deployed"].append("regulated_ops")

        # 3. Stitched workflows
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            res_result.get("capability_count", 10) +
            reg_result.get("pack", {}).get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Research cases
        res_cases = [
            {"case_id": f"scg-res-{i}", "title": t}
            for i, t in enumerate([
                "Clinical trial data integrity review",
                "Biomarker discovery validation study",
                "Environmental impact assessment protocol",
                "Drug interaction modeling experiment",
                "Genomic sequencing quality assurance",
            ])
        ]
        res_import = self._importer.import_cases(f"{tenant_id}-res", res_cases)
        result["research_cases"] = res_import.accepted

        # Regulated ops cases
        reg_cases = [
            {"case_id": f"scg-reg-{i}", "title": t}
            for i, t in enumerate([
                "GLP compliance audit - Q1",
                "FDA submission readiness assessment",
                "Data governance policy update - research",
                "Institutional review board renewal",
                "Laboratory accreditation maintenance",
            ])
        ]
        reg_import = self._importer.import_cases(f"{tenant_id}-reg", reg_cases)
        result["regulated_cases"] = reg_import.accepted

        # Cross-domain evidence
        evidence = [
            {"record_id": f"scg-ev-{i}", "title": t}
            for i, t in enumerate([
                "Research finding compliance escalation report",
                "Regulatory requirement study initiation record",
                "Cross-domain research governance evidence bundle",
                "Executive combined research compliance summary",
                "Copilot scientific regulatory audit trail",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = res_import.accepted + reg_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_research_customer(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing research lab customer to the full bundle."""
        reg_result = self._regulated_ops.bootstrap(f"{tenant_id}-reg-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "research_lab_to_bundle",
            "regulated_ops_added": True,
            "regulated_capabilities": reg_result.get("pack", {}).get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": SCIENTIFIC_GOVERNANCE_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "research_lab": self._research_lab,
            "regulated_ops": self._regulated_ops,
            "importer": self._importer,
        }
