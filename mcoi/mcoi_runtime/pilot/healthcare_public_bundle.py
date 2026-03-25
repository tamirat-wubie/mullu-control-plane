"""Phase 171 — Healthcare + Public Sector Sovereign Bundle (7th bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.healthcare_pack import HealthcarePackBootstrap
from mcoi_runtime.pilot.public_sector_pack import PublicSectorPackBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Healthcare Public Sector Sovereign Suite"
BUNDLE_PACKS = ("healthcare", "public_sector")


@dataclass(frozen=True)
class HealthcarePublicSectorPricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 6500.0  # 4000 healthcare + 2500 public sector
    monthly_bundled: float = 5250.0
    annual_savings: float = 15000.0
    discount_percent: float = 19.2


HEALTHCARE_PUBLIC_SECTOR_PRICING = HealthcarePublicSectorPricing()


@dataclass(frozen=True)
class HealthcarePublicSectorStitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str


STITCHED_WORKFLOWS = (
    HealthcarePublicSectorStitchedWorkflow(
        "patient_case_triggers_public_health_review", "healthcare", "public_sector",
        "Patient case finding triggers public health review and reporting workflow"),
    HealthcarePublicSectorStitchedWorkflow(
        "public_service_request_opens_clinical_governance", "public_sector", "healthcare",
        "Public service request opens clinical governance review and care pathway assessment"),
    HealthcarePublicSectorStitchedWorkflow(
        "evidence_spans_clinical_and_public_records", "healthcare", "public_sector",
        "Evidence gathering spans both clinical records and public sector documentation"),
    HealthcarePublicSectorStitchedWorkflow(
        "executive_combined_health_public_posture", "healthcare", "public_sector",
        "Executive dashboard combines clinical quality posture with public sector service metrics"),
    HealthcarePublicSectorStitchedWorkflow(
        "copilot_cross_clinical_public_evidence", "healthcare", "public_sector",
        "Copilot explains a case using both clinical and public sector evidence sources"),
)

# 171D — Sovereign Configuration
SOVEREIGN_CONFIG: dict[str, Any] = {
    "profile_compatibility": (
        "sovereign_cloud",
        "restricted_network",
        "on_prem",
        "partner_operated",
    ),
    "restricted_connector_defaults": {
        "sovereign_cloud": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        "restricted_network": ("email", "identity_sso", "document_storage"),
        "on_prem": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
        "partner_operated": ("email", "identity_sso", "document_storage", "ticketing", "reporting_export"),
    },
    "copilot_mode_defaults": {
        "sovereign_cloud": "full",
        "restricted_network": "explain_only",
        "on_prem": "full",
        "partner_operated": "full",
        "restricted": "explain_only",
        "classified": "explain_only",
    },
    "procurement_package_included": True,
}


class HealthcarePublicSectorBundle:
    """One-call deployment for the bundled Healthcare + Public Sector suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._healthcare = HealthcarePackBootstrap(self._es)
        self._public_sector = PublicSectorPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy healthcare pack
        hc_result = self._healthcare.bootstrap(tenant_id)
        result["healthcare"] = hc_result
        result["packs_deployed"].append("healthcare")

        # 2. Deploy public sector pack
        ps_result = self._public_sector.bootstrap(f"{tenant_id}-ps")
        result["public_sector"] = ps_result
        result["packs_deployed"].append("public_sector")

        # 3. Stitched workflows
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        # 4. Sovereign config
        result["sovereign_profiles"] = len(SOVEREIGN_CONFIG["profile_compatibility"])

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            hc_result.get("capability_count", 10) +
            ps_result.get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Healthcare cases
        hc_cases = [
            {"case_id": f"hcps-hc-{i}", "title": t}
            for i, t in enumerate([
                "Patient readmission review - respiratory",
                "Clinical quality audit - emergency department",
                "Medication reconciliation gap - geriatric",
                "Care pathway deviation - maternal health",
                "Discharge planning compliance review - pediatric",
            ])
        ]
        hc_import = self._importer.import_cases(tenant_id, hc_cases)
        result["healthcare_cases"] = hc_import.accepted

        # Public sector cases
        ps_cases = [
            {"case_id": f"hcps-ps-{i}", "title": t}
            for i, t in enumerate([
                "Public health surveillance alert - infectious disease",
                "Community health program review",
                "Inter-agency coordination - emergency response",
                "Health department compliance audit",
                "Public health reporting - vaccination tracking",
            ])
        ]
        ps_import = self._importer.import_cases(f"{tenant_id}-ps", ps_cases)
        result["public_sector_cases"] = ps_import.accepted

        # Cross-domain evidence
        evidence = [
            {"record_id": f"hcps-ev-{i}", "title": t}
            for i, t in enumerate([
                "Clinical quality report",
                "Public health surveillance dashboard",
                "Combined compliance audit",
                "Community health impact assessment",
                "Cross-domain risk assessment",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = hc_import.accepted + ps_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_healthcare_to_public(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing healthcare customer to the full bundle."""
        ps_result = self._public_sector.bootstrap(f"{tenant_id}-ps-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "healthcare_to_public_sector_bundle",
            "public_sector_added": True,
            "public_sector_capabilities": ps_result.get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": HEALTHCARE_PUBLIC_SECTOR_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "healthcare": self._healthcare,
            "public_sector": self._public_sector,
            "importer": self._importer,
        }
