"""Phase 153 — Healthcare / Clinical Governance Pack."""
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

# Pack Definition (153A)
HEALTHCARE_CAPABILITIES = (
    "patient_service_intake",
    "case_review_workflow",
    "approval_routing",
    "evidence_document_retrieval",
    "incident_remediation",
    "records_retention_audit",
    "compliance_dashboard",
    "executive_healthcare",
    "governed_copilot",
    "sovereign_compatibility",
)

HEALTHCARE_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-healthcare-v1",
    name="Healthcare / Clinical Governance",
    pack_domain="healthcare",
)

# Pack Bootstrap (153B)
class HealthcarePackBootstrap:
    """One-call bootstrap for Healthcare / Clinical Governance pack."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {"tenant_id": tenant_id, "pack": "healthcare", "steps": []}

        # 1. Create pack
        pack_id = f"hc-pack-{tenant_id}"
        pack = self._pack_engine.register_pack(pack_id, tenant_id, "Healthcare / Clinical Governance", PackDomain.CUSTOM)

        # Add 10 capabilities
        for i, cap_name in enumerate(HEALTHCARE_CAPABILITIES):
            self._pack_engine.add_capability(
                f"hc-cap-{tenant_id}-{i}", tenant_id, pack_id,
                PackCapabilityKind.INTAKE if "intake" in cap_name else
                PackCapabilityKind.CASE_MANAGEMENT if "case_review" in cap_name else
                PackCapabilityKind.APPROVAL if "approval" in cap_name else
                PackCapabilityKind.EVIDENCE if "evidence" in cap_name else
                PackCapabilityKind.REPORTING if "records_retention" in cap_name else
                PackCapabilityKind.OBSERVABILITY if "incident" in cap_name else
                PackCapabilityKind.DASHBOARD if "dashboard" in cap_name or "executive" in cap_name else
                PackCapabilityKind.COPILOT if "copilot" in cap_name else
                PackCapabilityKind.GOVERNANCE,
                target_runtime=cap_name,
            )
        results["capability_count"] = 10
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant
        bootstrap_id = f"hc-bootstrap-{tenant_id}"
        self._pilot_engine.bootstrap_tenant(bootstrap_id, tenant_id, pack_id)
        self._pilot_engine.start_bootstrap(bootstrap_id)
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"hc-conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors"] = activated
        results["steps"].append("connectors_activated")

        # 4. Personas (healthcare-specific — 6 personas)
        personas = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Care Operations Coordinator"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Clinical Reviewer"),
            (PersonaKind.REGULATORY, InteractionStyle.FORMAL, AuthorityMode.READ_ONLY, "Compliance Officer"),
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS, "Incident Manager"),
            (PersonaKind.TECHNICAL, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Records Administrator"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.READ_ONLY, "Executive Healthcare Viewer"),
        ]:
            pid = f"hc-persona-{tenant_id}-{name.lower().replace(' ', '_').replace('-', '_')}"
            self._persona_engine.register_persona(pid, tenant_id, name, kind, style, authority)
            personas.append(pid)
        results["personas"] = personas
        results["steps"].append("personas_created")

        # 5. Governance
        rules = []
        for rule_name, kind in [
            ("no_unauthorized_patient_data_access", ConstitutionRuleKind.HARD_DENY),
            ("require_evidence_for_case_closure", ConstitutionRuleKind.REQUIRE),
            ("restrict_autonomous_clinical_decisions", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"hc-rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*", target_action="*")
            rules.append(rid)
        results["governance_rules"] = rules
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"hc-pilot-{tenant_id}", tenant_id, pack_id)
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

# Demo Generator (153C)
class HealthcareDemoGenerator:
    """Creates a seeded demo for Healthcare / Clinical Governance pack."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = HealthcarePackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "hc-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "healthcare"}

        # Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result

        # Seed healthcare cases
        cases = [
            {"case_id": f"hc-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Patient referral processing", "high"),
                ("Clinical review backlog", "high"),
                ("Medication incident investigation", "critical"),
                ("Compliance audit finding", "critical"),
                ("Care coordination gap", "medium"),
                ("Adverse event follow-up", "high"),
                ("Credentialing verification overdue", "medium"),
                ("Quality metric review", "high"),
                ("Regulatory submission preparation", "medium"),
                ("Patient safety escalation", "high"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}

        # Seed remediations linked to first 5 cases
        rems = [
            {"remediation_id": f"hc-rem-{i:03d}", "case_ref": f"hc-case-{i:03d}", "title": f"Remediate: {cases[i]['title']}"}
            for i in range(5)
        ]
        rem_result = self._importer.import_remediations(tenant_id, rems)
        result["remediations"] = {"imported": rem_result.accepted}

        # Seed evidence records
        records = [
            {"record_id": f"hc-rec-{i:03d}", "title": title}
            for i, title in enumerate([
                "Referral form",
                "Clinical assessment",
                "Incident report",
                "Compliance checklist",
                "Care plan document",
                "Adverse event timeline",
                "Credential verification",
                "Quality scorecard",
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, records)
        result["records"] = {"imported": rec_result.accepted}

        result["status"] = "demo_ready"
        result["total_seeded"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> HealthcarePackBootstrap:
        return self._bootstrap
