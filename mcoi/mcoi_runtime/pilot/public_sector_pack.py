"""Phase 149 — Public Sector / Case Governance Pack."""
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

# Pack Definition (149A)
PUBLIC_SECTOR_CAPABILITIES = (
    "citizen_request_intake",
    "case_lifecycle",
    "review_approval",
    "evidence_retrieval",
    "audit_reporting",
    "sla_deadline_visibility",
    "operator_case_dashboard",
    "executive_public_service",
    "governed_copilot",
    "compliance_bundle",
)

PUBLIC_SECTOR_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-public-sector-v1",
    name="Public Sector / Case Governance",
    pack_domain="public_sector",
)

# Pack Bootstrap (149B)
class PublicSectorPackBootstrap:
    """One-call bootstrap for Public Sector / Case Governance pack."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {"tenant_id": tenant_id, "pack": "public_sector", "steps": []}

        # 1. Create pack
        pack_id = f"ps-pack-{tenant_id}"
        pack = self._pack_engine.register_pack(pack_id, tenant_id, "Public Sector / Case Governance", PackDomain.CUSTOM)

        # Add 10 capabilities
        for i, cap_name in enumerate(PUBLIC_SECTOR_CAPABILITIES):
            self._pack_engine.add_capability(
                f"ps-cap-{tenant_id}-{i}", tenant_id, pack_id,
                PackCapabilityKind.INTAKE if "intake" in cap_name else
                PackCapabilityKind.CASE_MANAGEMENT if "case_lifecycle" in cap_name else
                PackCapabilityKind.APPROVAL if "review_approval" in cap_name else
                PackCapabilityKind.EVIDENCE if "evidence" in cap_name else
                PackCapabilityKind.REPORTING if "audit_reporting" in cap_name else
                PackCapabilityKind.OBSERVABILITY if "sla_deadline" in cap_name else
                PackCapabilityKind.DASHBOARD if "dashboard" in cap_name or "executive" in cap_name else
                PackCapabilityKind.COPILOT if "copilot" in cap_name else
                PackCapabilityKind.GOVERNANCE,
                target_runtime=cap_name,
            )
        results["capability_count"] = 10
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant
        bootstrap_id = f"ps-bootstrap-{tenant_id}"
        self._pilot_engine.bootstrap_tenant(bootstrap_id, tenant_id, pack_id)
        self._pilot_engine.start_bootstrap(bootstrap_id)
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"ps-conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors"] = activated
        results["steps"].append("connectors_activated")

        # 4. Personas (public-sector-specific — 6 personas)
        personas = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Case Operator"),
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS, "Supervisor"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Reviewer"),
            (PersonaKind.REGULATORY, InteractionStyle.FORMAL, AuthorityMode.READ_ONLY, "Compliance Officer"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.READ_ONLY, "Executive Public-Service Viewer"),
            (PersonaKind.CUSTOMER_SUPPORT, InteractionStyle.CONVERSATIONAL, AuthorityMode.RESTRICTED, "Citizen Liaison"),
        ]:
            pid = f"ps-persona-{tenant_id}-{name.lower().replace(' ', '_').replace('-', '_')}"
            self._persona_engine.register_persona(pid, tenant_id, name, kind, style, authority)
            personas.append(pid)
        results["personas"] = personas
        results["steps"].append("personas_created")

        # 5. Governance
        rules = []
        for rule_name, kind in [
            ("no_unauthorized_citizen_data_access", ConstitutionRuleKind.HARD_DENY),
            ("require_evidence_for_case_closure", ConstitutionRuleKind.REQUIRE),
            ("restrict_bulk_case_operations", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"ps-rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*", target_action="*")
            rules.append(rid)
        results["governance_rules"] = rules
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"ps-pilot-{tenant_id}", tenant_id, pack_id)
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

# Demo Generator (149C)
class PublicSectorDemoGenerator:
    """Creates a seeded demo for Public Sector / Case Governance pack."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = PublicSectorPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "ps-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "public_sector"}

        # Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result

        # Seed public sector cases
        cases = [
            {"case_id": f"ps-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Building permit application", "high"),
                ("Zoning variance request", "high"),
                ("Public records FOIA request", "critical"),
                ("Environmental compliance review", "critical"),
                ("Business license renewal", "medium"),
                ("Citizen complaint investigation", "high"),
                ("Code enforcement follow-up", "medium"),
                ("Budget allocation review", "high"),
                ("Public hearing scheduling", "medium"),
                ("Inter-agency coordination request", "high"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}

        # Seed remediations linked to first 5 cases
        rems = [
            {"remediation_id": f"ps-rem-{i:03d}", "case_ref": f"ps-case-{i:03d}", "title": "Public sector remediation"}
            for i in range(5)
        ]
        rem_result = self._importer.import_remediations(tenant_id, rems)
        result["remediations"] = {"imported": rem_result.accepted}

        # Seed evidence records
        records = [
            {"record_id": f"ps-rec-{i:03d}", "title": title}
            for i, title in enumerate([
                "Permit application form",
                "Zoning ordinance excerpt",
                "FOIA response draft",
                "Environmental assessment",
                "License verification",
                "Complaint intake form",
                "Enforcement notice",
                "Budget justification memo",
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, records)
        result["records"] = {"imported": rec_result.accepted}

        result["status"] = "demo_ready"
        result["total_seeded"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> PublicSectorPackBootstrap:
        return self._bootstrap
