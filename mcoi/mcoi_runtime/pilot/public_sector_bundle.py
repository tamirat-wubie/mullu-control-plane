"""Phase 157 — Public Sector Governance Suite (Public Sector + Regulated Ops Bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.public_sector_pack import PublicSectorPackBootstrap
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Public Sector Governance Suite"
BUNDLE_PACKS = ("public_sector", "regulated_ops")

@dataclass(frozen=True)
class PublicSectorBundlePricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 5000.0  # 2500 public sector + 2500 regulated ops
    monthly_bundled: float = 4000.0
    annual_savings: float = 12000.0  # (5000-4000)*12
    discount_percent: float = 20.0

PUBLIC_SECTOR_BUNDLE_PRICING = PublicSectorBundlePricing()

@dataclass(frozen=True)
class PublicSectorStitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str

STITCHED_WORKFLOWS = (
    PublicSectorStitchedWorkflow(
        "case_escalates_to_regulated_remediation", "public_sector", "regulated_ops",
        "Public sector case escalation triggers regulated remediation workflow"),
    PublicSectorStitchedWorkflow(
        "sla_breach_opens_governance_review", "public_sector", "regulated_ops",
        "SLA breach on a public sector case opens a governance review in regulated ops"),
    PublicSectorStitchedWorkflow(
        "evidence_supports_case_and_compliance", "public_sector", "regulated_ops",
        "Evidence gathered for a case is shared with compliance tracking in regulated ops"),
    PublicSectorStitchedWorkflow(
        "approval_spans_service_and_regulation", "public_sector", "regulated_ops",
        "Approval workflow spans both public service delivery and regulatory sign-off"),
    PublicSectorStitchedWorkflow(
        "executive_combined_posture", "public_sector", "regulated_ops",
        "Executive dashboard combines public service posture with regulatory compliance status"),
    PublicSectorStitchedWorkflow(
        "copilot_cross_evidence", "public_sector", "regulated_ops",
        "Copilot explains a case using both public sector and regulated operations evidence"),
)

# 157D — Sovereign Packaging
SOVEREIGN_BUNDLE_CONFIG: dict[str, Any] = {
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


class PublicSectorGovernanceBundle:
    """One-call deployment for the bundled Public Sector + Regulated Ops suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._public_sector = PublicSectorPackBootstrap(self._es)
        self._regulated_ops = PilotTenantBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy public sector pack
        ps_result = self._public_sector.bootstrap(tenant_id)
        result["public_sector"] = ps_result
        result["packs_deployed"].append("public_sector")

        # 2. Deploy regulated ops pack
        reg_result = self._regulated_ops.bootstrap(f"{tenant_id}-reg")
        result["regulated_ops"] = reg_result
        result["packs_deployed"].append("regulated_ops")

        # 3. Stitched workflows
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            ps_result.get("capability_count", 10) +
            reg_result.get("pack", {}).get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Public sector cases
        ps_cases = [
            {"case_id": f"psgov-ps-{i}", "title": t}
            for i, t in enumerate([
                "Building permit application backlog",
                "Citizen complaint - zoning violation",
                "FOIA request - environmental records",
                "Inter-agency coordination - public safety",
                "Budget allocation review - infrastructure",
            ])
        ]
        ps_import = self._importer.import_cases(tenant_id, ps_cases)
        result["public_sector_cases"] = ps_import.accepted

        # Regulated ops cases
        reg_cases = [
            {"case_id": f"psgov-reg-{i}", "title": t}
            for i, t in enumerate([
                "Annual compliance review - data governance",
                "Vendor security assessment - cloud services",
                "Policy update - accessibility regulation",
                "Internal control gap - procurement",
                "Board reporting preparation - Q4",
            ])
        ]
        reg_import = self._importer.import_cases(f"{tenant_id}-reg", reg_cases)
        result["regulated_cases"] = reg_import.accepted

        # Cross-domain evidence
        evidence = [
            {"record_id": f"psgov-ev-{i}", "title": t}
            for i, t in enumerate([
                "Case escalation compliance report",
                "SLA governance review documentation",
                "Cross-domain evidence bundle",
                "Service-regulation approval chain",
                "Executive combined posture summary",
                "Copilot cross-evidence audit trail",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = ps_import.accepted + reg_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_public_sector_customer(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing public sector customer to the full bundle."""
        reg_result = self._regulated_ops.bootstrap(f"{tenant_id}-reg-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "public_sector_to_bundle",
            "regulated_ops_added": True,
            "regulated_capabilities": reg_result.get("pack", {}).get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": PUBLIC_SECTOR_BUNDLE_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "public_sector": self._public_sector,
            "regulated_ops": self._regulated_ops,
            "importer": self._importer,
        }
