"""Phase 142 — Regulated Financial Control Suite (Flagship Bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.financial_control_pack import FinancialControlPackBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Regulated Financial Control Suite"
BUNDLE_PACKS = ("regulated_ops", "financial_control")

@dataclass(frozen=True)
class BundlePricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 5500.0  # 2500 + 3000 if bought separately
    monthly_bundled: float = 4500.0  # bundle discount
    annual_savings: float = 12000.0  # (5500-4500)*12
    discount_percent: float = 18.2

BUNDLE_PRICING = BundlePricing()

@dataclass(frozen=True)
class StitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str

STITCHED_WORKFLOWS = (
    StitchedWorkflow("case_triggers_financial_review", "regulated_ops", "financial_control",
                     "Regulated case finding triggers financial control review of related transactions"),
    StitchedWorkflow("dispute_triggers_remediation", "financial_control", "regulated_ops",
                     "Financial dispute triggers evidence gathering and remediation workflow"),
    StitchedWorkflow("reporting_includes_settlement", "regulated_ops", "financial_control",
                     "Regulatory reporting packet includes financial settlement evidence"),
    StitchedWorkflow("executive_combined_posture", "regulated_ops", "financial_control",
                     "Executive dashboard combines compliance posture with cash/risk posture"),
    StitchedWorkflow("copilot_cross_evidence", "regulated_ops", "financial_control",
                     "Copilot explains a case using both regulatory and financial evidence"),
)

class RegulatedFinancialBundle:
    """One-call deployment for the bundled Regulated + Financial suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._reg_bootstrap = PilotTenantBootstrap(self._es)
        self._fin_bootstrap = FinancialControlPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy regulated ops pack
        reg_result = self._reg_bootstrap.bootstrap(tenant_id)
        result["regulated_ops"] = reg_result
        result["packs_deployed"].append("regulated_ops")

        # 2. Deploy financial control pack (uses separate engine instances but same tenant)
        fin_result = self._fin_bootstrap.bootstrap(f"{tenant_id}-fin")
        result["financial_control"] = fin_result
        result["packs_deployed"].append("financial_control")

        # 3. Stitched workflow verification
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            reg_result.get("pack", {}).get("capability_count", 10) +
            fin_result.get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Regulatory cases
        reg_cases = [
            {"case_id": f"bundle-reg-{i}", "title": title}
            for i, title in enumerate([
                "Annual compliance review - Q4", "Vendor security assessment",
                "Policy update - new regulation", "Internal control gap - AP",
                "Board reporting preparation",
            ])
        ]
        reg_import = self._importer.import_cases(tenant_id, reg_cases)
        result["regulatory_cases"] = reg_import.accepted

        # Financial cases
        fin_cases = [
            {"case_id": f"bundle-fin-{i}", "title": title}
            for i, title in enumerate([
                "Invoice dispute - vendor overcharge", "Settlement reconciliation gap",
                "Overdue collection - 90 days", "Credit approval pending",
                "Revenue recognition variance",
            ])
        ]
        fin_import = self._importer.import_cases(f"{tenant_id}-fin", fin_cases)
        result["financial_cases"] = fin_import.accepted

        # Cross-pack evidence
        evidence = [
            {"record_id": f"bundle-ev-{i}", "title": title}
            for i, title in enumerate([
                "Compliance audit report", "Financial settlement proof",
                "Combined risk assessment", "Cross-department evidence bundle",
                "Executive compliance + finance summary",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = reg_import.accepted + fin_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_existing_customer(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing regulated ops customer to the bundle."""
        # Financial pack is added on top of existing regulated tenant
        fin_result = self._fin_bootstrap.bootstrap(f"{tenant_id}-fin-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "regulated_to_bundle",
            "financial_pack_added": True,
            "financial_capabilities": fin_result.get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": BUNDLE_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "regulated_bootstrap": self._reg_bootstrap,
            "financial_bootstrap": self._fin_bootstrap,
            "importer": self._importer,
        }
