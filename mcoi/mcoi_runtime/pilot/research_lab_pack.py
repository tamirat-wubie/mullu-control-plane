"""Phase 138 — Research / Lab Operations Pack."""
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

# Pack Definition (138A)
RESEARCH_LAB_CAPABILITIES = (
    "research_intake",
    "hypothesis_tracking",
    "experiment_coordination",
    "evidence_retrieval",
    "literature_review",
    "peer_review_approval",
    "result_synthesis",
    "compliance_overlay",
    "research_dashboard",
    "research_copilot",
)

RESEARCH_LAB_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-research-lab-v1",
    name="Research / Lab Operations",
    pack_domain="research_lab",
)

# Pack Bootstrap (138B)
class ResearchLabPackBootstrap:
    """One-call bootstrap for Research / Lab Operations pack."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {"tenant_id": tenant_id, "pack": "research_lab", "steps": []}

        # 1. Create pack
        pack_id = f"rl-pack-{tenant_id}"
        pack = self._pack_engine.register_pack(pack_id, tenant_id, "Research / Lab Operations", PackDomain.RESEARCH_LAB)

        # Add 10 capabilities
        for i, cap_name in enumerate(RESEARCH_LAB_CAPABILITIES):
            self._pack_engine.add_capability(
                f"rl-cap-{tenant_id}-{i}", tenant_id, pack_id,
                PackCapabilityKind.INTAKE if "intake" in cap_name else
                PackCapabilityKind.CASE_MANAGEMENT if "hypothesis" in cap_name or "experiment" in cap_name else
                PackCapabilityKind.EVIDENCE if "evidence" in cap_name or "literature" in cap_name else
                PackCapabilityKind.APPROVAL if "peer_review" in cap_name else
                PackCapabilityKind.OBSERVABILITY if "result_synthesis" in cap_name else
                PackCapabilityKind.GOVERNANCE if "compliance" in cap_name else
                PackCapabilityKind.DASHBOARD if "dashboard" in cap_name else
                PackCapabilityKind.COPILOT if "copilot" in cap_name else
                PackCapabilityKind.GOVERNANCE,
                target_runtime=cap_name,
            )
        results["capability_count"] = 10
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant
        bootstrap_id = f"rl-bootstrap-{tenant_id}"
        self._pilot_engine.bootstrap_tenant(bootstrap_id, tenant_id, pack_id)
        self._pilot_engine.start_bootstrap(bootstrap_id)
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"rl-conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors"] = activated
        results["steps"].append("connectors_activated")

        # 4. Personas (research-specific — 6 personas)
        personas = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Research Operator"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.AUTONOMOUS, "Principal Investigator"),
            (PersonaKind.REGULATORY, InteractionStyle.FORMAL, AuthorityMode.GUIDED, "Reviewer"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Lab Manager"),
            (PersonaKind.REGULATORY, InteractionStyle.FORMAL, AuthorityMode.READ_ONLY, "Compliance Reviewer"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.READ_ONLY, "Executive Research Viewer"),
        ]:
            pid = f"rl-persona-{tenant_id}-{name.lower().replace(' ', '_')}"
            self._persona_engine.register_persona(pid, tenant_id, name, kind, style, authority)
            personas.append(pid)
        results["personas"] = personas
        results["steps"].append("personas_created")

        # 5. Governance
        rules = []
        for rule_name, kind in [
            ("no_unauthorized_data_modification", ConstitutionRuleKind.HARD_DENY),
            ("require_evidence_for_publication", ConstitutionRuleKind.REQUIRE),
            ("restrict_unreviewed_conclusions", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"rl-rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*", target_action="*")
            rules.append(rid)
        results["governance_rules"] = rules
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"rl-pilot-{tenant_id}", tenant_id, pack_id)
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

# Demo Generator (138C)
class ResearchLabDemoGenerator:
    """Creates a seeded demo for Research / Lab Operations pack."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = ResearchLabPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "rl-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "research_lab"}

        # Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result

        # Seed research cases
        cases = [
            {"case_id": f"rl-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Phase III trial protocol review", "critical"),
                ("Cell line contamination investigation", "critical"),
                ("Reagent lot qualification failure", "high"),
                ("Publication retraction review", "high"),
                ("Lab safety audit finding", "critical"),
                ("Equipment calibration dispute", "medium"),
                ("Data integrity assessment", "high"),
                ("Cross-contamination root cause", "critical"),
                ("Regulatory submission gap", "high"),
                ("Reproducibility challenge", "medium"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}

        # Seed remediations linked to first 5 cases
        rems = [
            {"remediation_id": f"rl-rem-{i:03d}", "case_ref": f"rl-case-{i:03d}", "title": f"Remediate: {cases[i]['title']}"}
            for i in range(5)
        ]
        rem_result = self._importer.import_remediations(tenant_id, rems)
        result["remediations"] = {"imported": rem_result.accepted}

        # Seed evidence records
        records = [
            {"record_id": f"rl-rec-{i:03d}", "title": title}
            for i, title in enumerate([
                "Protocol document",
                "Lab notebook extract",
                "Calibration certificate",
                "Safety inspection report",
                "Literature review packet",
                "Statistical analysis report",
                "Peer review comments",
                "Regulatory correspondence",
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, records)
        result["records"] = {"imported": rec_result.accepted}

        result["status"] = "demo_ready"
        result["total_seeded"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> ResearchLabPackBootstrap:
        return self._bootstrap
