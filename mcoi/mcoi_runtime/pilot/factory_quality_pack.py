"""Phase 132 — Factory Quality / Downtime / Throughput Pack."""
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

# Pack Definition (132A)
FACTORY_QUALITY_CAPABILITIES = (
    "work_order_intake",
    "batch_station_tracking",
    "downtime_tracking",
    "quality_inspection",
    "nonconformance_flow",
    "rework_scrap_yield",
    "maintenance_escalation",
    "digital_twin_view",
    "process_deviation",
    "factory_dashboard",
    "factory_copilot",
)

FACTORY_QUALITY_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-factory-quality-v1",
    name="Factory Quality / Downtime / Throughput",
    pack_domain="factory_quality",
)

# Pack Bootstrap (132B)
class FactoryQualityPackBootstrap:
    """One-call bootstrap for Factory Quality / Downtime / Throughput pack."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {"tenant_id": tenant_id, "pack": "factory_quality", "steps": []}

        # 1. Create pack
        pack_id = f"fq-pack-{tenant_id}"
        pack = self._pack_engine.register_pack(pack_id, tenant_id, "Factory Quality / Downtime / Throughput", PackDomain.FACTORY_QUALITY)

        # Add 11 capabilities
        for i, cap_name in enumerate(FACTORY_QUALITY_CAPABILITIES):
            self._pack_engine.add_capability(
                f"fq-cap-{tenant_id}-{i}", tenant_id, pack_id,
                PackCapabilityKind.INTAKE if "intake" in cap_name else
                PackCapabilityKind.CASE_MANAGEMENT if "tracking" in cap_name or "nonconformance" in cap_name else
                PackCapabilityKind.EVIDENCE if "inspection" in cap_name or "quality" in cap_name else
                PackCapabilityKind.APPROVAL if "escalation" in cap_name else
                PackCapabilityKind.OBSERVABILITY if "rework" in cap_name or "scrap" in cap_name or "yield" in cap_name or "deviation" in cap_name else
                PackCapabilityKind.CONTINUITY if "digital_twin" in cap_name else
                PackCapabilityKind.DASHBOARD if "dashboard" in cap_name else
                PackCapabilityKind.COPILOT if "copilot" in cap_name else
                PackCapabilityKind.GOVERNANCE,
                target_runtime=cap_name,
            )
        results["capability_count"] = 11
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant
        bootstrap_id = f"fq-bootstrap-{tenant_id}"
        self._pilot_engine.bootstrap_tenant(bootstrap_id, tenant_id, pack_id)
        self._pilot_engine.start_bootstrap(bootstrap_id)
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"fq-conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors"] = activated
        results["steps"].append("connectors_activated")

        # 4. Personas (factory-specific — 6 personas)
        personas = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Line Operator"),
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS, "Shift Supervisor"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Quality Engineer"),
            (PersonaKind.TECHNICAL, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Maintenance Lead"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Plant Manager"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.READ_ONLY, "Executive Operations Viewer"),
        ]:
            pid = f"fq-persona-{tenant_id}-{name.lower().replace(' ', '_')}"
            self._persona_engine.register_persona(pid, tenant_id, name, kind, style, authority)
            personas.append(pid)
        results["personas"] = personas
        results["steps"].append("personas_created")

        # 5. Governance
        rules = []
        for rule_name, kind in [
            ("no_unauthorized_production_changes", ConstitutionRuleKind.HARD_DENY),
            ("require_quality_evidence_for_release", ConstitutionRuleKind.REQUIRE),
            ("restrict_batch_override", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"fq-rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*", target_action="*")
            rules.append(rid)
        results["governance_rules"] = rules
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"fq-pilot-{tenant_id}", tenant_id, pack_id)
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

# Demo Generator (132C)
class FactoryQualityDemoGenerator:
    """Creates a seeded demo for Factory Quality pack."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = FactoryQualityPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "fq-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "factory_quality"}

        # Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result

        # Seed factory cases
        cases = [
            {"case_id": f"fq-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Machine breakdown - press line 2", "critical"),
                ("Quality failure batch 4472", "critical"),
                ("Yield drop on Line 3", "high"),
                ("Unplanned downtime Station A", "critical"),
                ("Rework queue overflow", "high"),
                ("Calibration overdue - torque wrench set", "medium"),
                ("Process deviation CNC-7", "high"),
                ("Scrap rate spike - injection mold bay", "critical"),
                ("Maintenance backlog critical", "high"),
                ("Shift handover gap - night to day", "medium"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}

        # Seed remediations linked to first 5 cases
        rems = [
            {"remediation_id": f"fq-rem-{i:03d}", "case_ref": f"fq-case-{i:03d}", "title": f"Remediate: {cases[i]['title']}"}
            for i in range(5)
        ]
        rem_result = self._importer.import_remediations(tenant_id, rems)
        result["remediations"] = {"imported": rem_result.accepted}

        # Seed evidence records
        records = [
            {"record_id": f"fq-rec-{i:03d}", "title": title}
            for i, title in enumerate([
                "Machine log extract",
                "Quality inspection report",
                "Downtime timeline",
                "Batch genealogy trace",
                "Process parameter chart",
                "Maintenance work order",
                "Calibration certificate",
                "Yield analysis report",
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, records)
        result["records"] = {"imported": rec_result.accepted}

        result["status"] = "demo_ready"
        result["total_seeded"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> FactoryQualityPackBootstrap:
        return self._bootstrap
