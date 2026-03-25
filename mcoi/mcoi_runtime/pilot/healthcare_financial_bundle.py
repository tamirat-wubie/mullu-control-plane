"""Phase 155 — Healthcare Financial Governance Suite (Healthcare + Financial Control Bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.healthcare_pack import HealthcarePackBootstrap
from mcoi_runtime.pilot.financial_control_pack import FinancialControlPackBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Healthcare Financial Governance Suite"
BUNDLE_PACKS = ("healthcare", "financial_control")

@dataclass(frozen=True)
class HealthcareFinancialPricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 7000.0  # 4000 healthcare + 3000 financial
    monthly_bundled: float = 5750.0
    annual_savings: float = 15000.0
    discount_percent: float = 17.9

HEALTHCARE_FINANCIAL_PRICING = HealthcareFinancialPricing()

@dataclass(frozen=True)
class HealthcareFinancialStitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str

STITCHED_WORKFLOWS = (
    HealthcareFinancialStitchedWorkflow("healthcare_triggers_financial_review", "healthcare", "financial_control",
        "Clinical case finding triggers financial control review of related billing transactions"),
    HealthcareFinancialStitchedWorkflow("financial_exception_triggers_remediation", "financial_control", "healthcare",
        "Financial exception triggers clinical remediation and care pathway review"),
    HealthcareFinancialStitchedWorkflow("audit_includes_clinical_and_financial", "healthcare", "financial_control",
        "Compliance audit packet includes both clinical quality evidence and financial controls"),
    HealthcareFinancialStitchedWorkflow("executive_combined_posture", "healthcare", "financial_control",
        "Executive dashboard combines clinical quality posture with revenue cycle health"),
    HealthcareFinancialStitchedWorkflow("copilot_cross_evidence", "healthcare", "financial_control",
        "Copilot explains a case using both clinical and financial evidence sources"),
    HealthcareFinancialStitchedWorkflow("settlement_impacts_care_operations", "financial_control", "healthcare",
        "Financial settlement or denial impacts care operations scheduling and resource allocation"),
)

class HealthcareFinancialBundle:
    """One-call deployment for the bundled Healthcare + Financial Control suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._healthcare = HealthcarePackBootstrap(self._es)
        self._financial = FinancialControlPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy healthcare pack
        hc_result = self._healthcare.bootstrap(tenant_id)
        result["healthcare"] = hc_result
        result["packs_deployed"].append("healthcare")

        # 2. Deploy financial control pack
        fin_result = self._financial.bootstrap(f"{tenant_id}-fin")
        result["financial_control"] = fin_result
        result["packs_deployed"].append("financial_control")

        # 3. Stitched workflows
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            hc_result.get("capability_count", 10) +
            fin_result.get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Healthcare cases
        hc_cases = [
            {"case_id": f"hcfin-hc-{i}", "title": t}
            for i, t in enumerate([
                "Patient readmission review - cardiac", "Clinical quality audit - surgical",
                "Medication reconciliation gap", "Care pathway deviation - oncology",
                "Discharge planning compliance review",
            ])
        ]
        hc_import = self._importer.import_cases(tenant_id, hc_cases)
        result["healthcare_cases"] = hc_import.accepted

        # Financial cases
        fin_cases = [
            {"case_id": f"hcfin-fin-{i}", "title": t}
            for i, t in enumerate([
                "Claim denial - coding discrepancy", "Revenue cycle variance - Q4",
                "Settlement reconciliation gap", "Payer contract underpayment",
                "Charge capture audit finding",
            ])
        ]
        fin_import = self._importer.import_cases(f"{tenant_id}-fin", fin_cases)
        result["financial_cases"] = fin_import.accepted

        # Cross-domain evidence
        evidence = [
            {"record_id": f"hcfin-ev-{i}", "title": t}
            for i, t in enumerate([
                "Clinical quality report", "Revenue cycle dashboard",
                "Combined compliance audit", "Payer settlement documentation",
                "Care operations financial impact", "Cross-domain risk assessment",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = hc_import.accepted + fin_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_healthcare_customer(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing healthcare customer to the full bundle."""
        fin_result = self._financial.bootstrap(f"{tenant_id}-fin-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "healthcare_to_bundle",
            "financial_pack_added": True,
            "financial_capabilities": fin_result.get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": HEALTHCARE_FINANCIAL_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "healthcare": self._healthcare,
            "financial": self._financial,
            "importer": self._importer,
        }
