"""Phase 158 — Enterprise Service Governance Suite (Enterprise Service + Regulated Ops Bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.tenant_bootstrap import PilotTenantBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Enterprise Service Governance Suite"
BUNDLE_PACKS = ("enterprise_service", "regulated_ops")

@dataclass(frozen=True)
class ServiceRegulatedBundlePricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 5000.0  # 2500 enterprise service + 2500 regulated ops
    monthly_bundled: float = 4000.0
    annual_savings: float = 12000.0  # (5000-4000)*12
    discount_percent: float = 20.0

SERVICE_REGULATED_BUNDLE_PRICING = ServiceRegulatedBundlePricing()

@dataclass(frozen=True)
class ServiceRegulatedStitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str

STITCHED_WORKFLOWS = (
    ServiceRegulatedStitchedWorkflow(
        "service_incident_escalates_to_compliance", "enterprise_service", "regulated_ops",
        "Service incident escalation triggers compliance review workflow"),
    ServiceRegulatedStitchedWorkflow(
        "sla_breach_opens_regulatory_review", "enterprise_service", "regulated_ops",
        "SLA breach on a service case opens a regulatory review in regulated ops"),
    ServiceRegulatedStitchedWorkflow(
        "evidence_spans_service_and_governance", "enterprise_service", "regulated_ops",
        "Evidence gathered for a service case is shared with governance tracking in regulated ops"),
    ServiceRegulatedStitchedWorkflow(
        "approval_bridges_it_and_compliance", "enterprise_service", "regulated_ops",
        "Approval workflow bridges both IT service delivery and compliance sign-off"),
    ServiceRegulatedStitchedWorkflow(
        "executive_combined_service_compliance", "enterprise_service", "regulated_ops",
        "Executive dashboard combines service posture with regulatory compliance status"),
    ServiceRegulatedStitchedWorkflow(
        "copilot_cross_domain_evidence", "enterprise_service", "regulated_ops",
        "Copilot explains a case using both enterprise service and regulated operations evidence"),
)


class ServiceRegulatedBundle:
    """One-call deployment for the bundled Enterprise Service + Regulated Ops suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._enterprise_service = PilotTenantBootstrap(self._es)
        self._regulated_ops = PilotTenantBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy enterprise service pack
        svc_result = self._enterprise_service.bootstrap(f"{tenant_id}-svc")
        result["enterprise_service"] = svc_result
        result["packs_deployed"].append("enterprise_service")

        # 2. Deploy regulated ops pack
        reg_result = self._regulated_ops.bootstrap(f"{tenant_id}-reg")
        result["regulated_ops"] = reg_result
        result["packs_deployed"].append("regulated_ops")

        # 3. Stitched workflows
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            svc_result.get("pack", {}).get("capability_count", 10) +
            reg_result.get("pack", {}).get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Service cases
        svc_cases = [
            {"case_id": f"srg-svc-{i}", "title": t}
            for i, t in enumerate([
                "Critical SLA breach - enterprise ticketing platform",
                "Service outage escalation - authentication service",
                "Capacity planning review - API gateway",
                "Vendor integration failure - CRM connector",
                "Change management approval - infrastructure upgrade",
            ])
        ]
        svc_import = self._importer.import_cases(f"{tenant_id}-svc", svc_cases)
        result["service_cases"] = svc_import.accepted

        # Regulated ops cases
        reg_cases = [
            {"case_id": f"srg-reg-{i}", "title": t}
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
            {"record_id": f"srg-ev-{i}", "title": t}
            for i, t in enumerate([
                "Service incident compliance escalation report",
                "SLA regulatory review documentation",
                "Cross-domain service governance evidence bundle",
                "IT-compliance approval chain record",
                "Executive combined service compliance summary",
                "Copilot cross-domain evidence audit trail",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = svc_import.accepted + reg_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_service_customer(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing enterprise service customer to the full bundle."""
        reg_result = self._regulated_ops.bootstrap(f"{tenant_id}-reg-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "enterprise_service_to_bundle",
            "regulated_ops_added": True,
            "regulated_capabilities": reg_result.get("pack", {}).get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": SERVICE_REGULATED_BUNDLE_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "enterprise_service": self._enterprise_service,
            "regulated_ops": self._regulated_ops,
            "importer": self._importer,
        }
