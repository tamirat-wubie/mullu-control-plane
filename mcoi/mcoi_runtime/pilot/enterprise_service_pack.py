"""Phase 130 — Enterprise Service / IT Control Tower Pack."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.industry_pack import IndustryPackEngine
from mcoi_runtime.core.pilot_deployment import PilotDeploymentEngine
from mcoi_runtime.core.product_console import ProductConsoleEngine
from mcoi_runtime.core.persona_runtime import PersonaRuntimeEngine
from mcoi_runtime.core.copilot_runtime import CopilotRuntimeEngine
from mcoi_runtime.core.constitutional_governance import ConstitutionalGovernanceEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.contracts.industry_pack import PackDomain, PackCapabilityKind
from mcoi_runtime.contracts.persona_runtime import PersonaKind, InteractionStyle, AuthorityMode
from mcoi_runtime.contracts.constitutional_governance import ConstitutionRuleKind, PrecedenceLevel
from mcoi_runtime.pilot.connector_profiles import ALL_REQUIRED_PROFILES
from mcoi_runtime.pilot.data_import import PilotDataImporter
from mcoi_runtime.pilot.deployment_factory import DeploymentFactory, DeploymentTemplate

# Pack Definition (130A)
ENTERPRISE_SERVICE_CAPABILITIES = (
    "service_intake",
    "incident_case_handling",
    "remediation",
    "approvals",
    "evidence_retrieval",
    "service_dashboards",
    "observability_hooks",
    "continuity_escalation",
    "customer_impact_view",
    "service_copilot",
)

ENTERPRISE_SERVICE_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-enterprise-service-v1",
    name="Enterprise Service / IT Control Tower",
    pack_domain="enterprise_service",
)

# Pack Bootstrap (130B)
class EnterpriseServicePackBootstrap:
    """One-call bootstrap for Enterprise Service / IT Control Tower."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {"tenant_id": tenant_id, "pack": "enterprise_service", "steps": []}

        # 1. Create pack
        pack_id = f"es-pack-{tenant_id}"
        pack = self._pack_engine.register_pack(pack_id, tenant_id, "Enterprise Service / IT Control Tower", PackDomain.ENTERPRISE_SERVICE)

        # Add 10 capabilities
        for i, cap_name in enumerate(ENTERPRISE_SERVICE_CAPABILITIES):
            self._pack_engine.add_capability(
                f"es-cap-{tenant_id}-{i}", tenant_id, pack_id,
                PackCapabilityKind.INTAKE if "intake" in cap_name else
                PackCapabilityKind.CASE_MANAGEMENT if "case" in cap_name or "remediation" in cap_name else
                PackCapabilityKind.APPROVAL if "approval" in cap_name else
                PackCapabilityKind.EVIDENCE if "evidence" in cap_name else
                PackCapabilityKind.DASHBOARD if "dashboard" in cap_name else
                PackCapabilityKind.OBSERVABILITY if "observability" in cap_name else
                PackCapabilityKind.CONTINUITY if "continuity" in cap_name else
                PackCapabilityKind.COPILOT if "copilot" in cap_name else
                PackCapabilityKind.GOVERNANCE,
                target_runtime=cap_name,
            )
        results["capability_count"] = 10
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant
        bootstrap_id = f"es-bootstrap-{tenant_id}"
        self._pilot_engine.bootstrap_tenant(bootstrap_id, tenant_id, pack_id)
        self._pilot_engine.start_bootstrap(bootstrap_id)
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"es-conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors"] = activated
        results["steps"].append("connectors_activated")

        # 4. Personas (service-specific)
        personas = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Service Operator"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Service Manager"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Incident Investigator"),
            (PersonaKind.CUSTOMER_SUPPORT, InteractionStyle.CONVERSATIONAL, AuthorityMode.RESTRICTED, "Customer Liaison"),
        ]:
            pid = f"es-persona-{tenant_id}-{name.lower().replace(' ', '_')}"
            self._persona_engine.register_persona(pid, tenant_id, name, kind, style, authority)
            personas.append(pid)
        results["personas"] = personas
        results["steps"].append("personas_created")

        # 5. Governance
        rules = []
        for rule_name, kind in [
            ("service_data_protection", ConstitutionRuleKind.HARD_DENY),
            ("require_evidence_for_resolution", ConstitutionRuleKind.REQUIRE),
            ("restrict_customer_data_access", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"es-rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*", target_action="*")
            rules.append(rid)
        results["governance_rules"] = rules
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"es-pilot-{tenant_id}", tenant_id, pack_id)
        results["steps"].append("pilot_registered")

        # 7. Complete bootstrap
        self._pilot_engine.complete_bootstrap(bootstrap_id)
        results["steps"].append("bootstrap_completed")

        results["status"] = "ready"
        results["total_steps"] = len(results["steps"])
        return results

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "memory_mesh": self._mm,
            "pack": self._pack_engine,
            "pilot": self._pilot_engine,
            "persona": self._persona_engine,
            "copilot": self._copilot_engine,
            "governance": self._governance_engine,
        }

# Demo Generator (130C)
class EnterpriseServiceDemoGenerator:
    """Creates a seeded demo for Enterprise Service pack."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = EnterpriseServicePackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "es-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "enterprise_service"}

        # Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result

        # Seed service cases
        cases = [
            {"case_id": f"es-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Email service degradation - Outlook", "high"),
                ("VPN connectivity issues - remote workers", "critical"),
                ("Database performance degradation", "high"),
                ("Software license expiration approaching", "medium"),
                ("Security patch deployment - critical CVE", "critical"),
                ("Printer fleet management review", "low"),
                ("Cloud migration readiness assessment", "medium"),
                ("Helpdesk SLA breach investigation", "high"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}

        # Seed remediations
        rems = [
            {"remediation_id": f"es-rem-{i:03d}", "case_ref": f"es-case-{i:03d}", "title": f"Remediate: {cases[i]['title']}"}
            for i in range(4)
        ]
        rem_result = self._importer.import_remediations(tenant_id, rems)
        result["remediations"] = {"imported": rem_result.accepted}

        # Seed evidence
        records = [
            {"record_id": f"es-rec-{i:03d}", "title": title}
            for i, title in enumerate([
                "Network topology diagram", "Incident timeline", "Root cause analysis",
                "Vendor SLA document", "Change request log", "Performance benchmark report",
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, records)
        result["records"] = {"imported": rec_result.accepted}

        result["status"] = "demo_ready"
        result["total_seeded"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> EnterpriseServicePackBootstrap:
        return self._bootstrap
