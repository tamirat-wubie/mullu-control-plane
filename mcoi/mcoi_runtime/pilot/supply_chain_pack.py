"""Phase 139 — Supply Chain / Procurement Operations Pack."""
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

# Pack Definition (139A)
SUPPLY_CHAIN_CAPABILITIES = (
    "procurement_intake",
    "vendor_management",
    "purchase_order_lifecycle",
    "delivery_receiving",
    "inventory_replenishment",
    "lead_time_tracking",
    "supplier_risk_compliance",
    "supply_dashboard",
    "executive_supply",
    "supply_copilot",
)

SUPPLY_CHAIN_TEMPLATE = DeploymentTemplate(
    template_id="tmpl-supply-chain-v1",
    name="Supply Chain / Procurement Operations",
    pack_domain="supply_chain",
)

# Pack Bootstrap (139B)
class SupplyChainPackBootstrap:
    """One-call bootstrap for Supply Chain / Procurement Operations pack."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        results: dict[str, Any] = {"tenant_id": tenant_id, "pack": "supply_chain", "steps": []}

        # 1. Create pack
        pack_id = f"sc-pack-{tenant_id}"
        pack = self._pack_engine.register_pack(pack_id, tenant_id, "Supply Chain / Procurement Operations", PackDomain.CUSTOM)

        # Add 10 capabilities
        for i, cap_name in enumerate(SUPPLY_CHAIN_CAPABILITIES):
            self._pack_engine.add_capability(
                f"sc-cap-{tenant_id}-{i}", tenant_id, pack_id,
                PackCapabilityKind.INTAKE if "intake" in cap_name else
                PackCapabilityKind.CASE_MANAGEMENT if "vendor_management" in cap_name or "purchase_order" in cap_name else
                PackCapabilityKind.EVIDENCE if "delivery" in cap_name or "inventory" in cap_name else
                PackCapabilityKind.OBSERVABILITY if "lead_time" in cap_name else
                PackCapabilityKind.GOVERNANCE if "supplier_risk" in cap_name or "compliance" in cap_name else
                PackCapabilityKind.DASHBOARD if "dashboard" in cap_name or "executive" in cap_name else
                PackCapabilityKind.COPILOT if "copilot" in cap_name else
                PackCapabilityKind.GOVERNANCE,
                target_runtime=cap_name,
            )
        results["capability_count"] = 10
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant
        bootstrap_id = f"sc-bootstrap-{tenant_id}"
        self._pilot_engine.bootstrap_tenant(bootstrap_id, tenant_id, pack_id)
        self._pilot_engine.start_bootstrap(bootstrap_id)
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"sc-conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors"] = activated
        results["steps"].append("connectors_activated")

        # 4. Personas (supply-chain-specific — 6 personas)
        personas = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Procurement Operator"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Supply Chain Analyst"),
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.AUTONOMOUS, "Vendor Manager"),
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Receiving Coordinator"),
            (PersonaKind.TECHNICAL, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Inventory Planner"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.READ_ONLY, "Executive Supply Viewer"),
        ]:
            pid = f"sc-persona-{tenant_id}-{name.lower().replace(' ', '_')}"
            self._persona_engine.register_persona(pid, tenant_id, name, kind, style, authority)
            personas.append(pid)
        results["personas"] = personas
        results["steps"].append("personas_created")

        # 5. Governance
        rules = []
        for rule_name, kind in [
            ("no_unauthorized_vendor_changes", ConstitutionRuleKind.HARD_DENY),
            ("require_evidence_for_procurement", ConstitutionRuleKind.REQUIRE),
            ("restrict_bulk_purchase_orders", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"sc-rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*", target_action="*")
            rules.append(rid)
        results["governance_rules"] = rules
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"sc-pilot-{tenant_id}", tenant_id, pack_id)
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

# Demo Generator (139C)
class SupplyChainDemoGenerator:
    """Creates a seeded demo for Supply Chain / Procurement Operations pack."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._bootstrap = SupplyChainPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def generate(self, tenant_id: str = "sc-demo-001") -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "pack": "supply_chain"}

        # Bootstrap
        bootstrap_result = self._bootstrap.bootstrap(tenant_id)
        result["bootstrap"] = bootstrap_result

        # Seed supply chain cases
        cases = [
            {"case_id": f"sc-case-{i:03d}", "title": title, "priority": pri}
            for i, (title, pri) in enumerate([
                ("Vendor delivery delay - critical component", "critical"),
                ("Inventory stockout alert - warehouse B", "critical"),
                ("PO approval pending - bulk order 9921", "high"),
                ("Supplier quality audit - tier 1 vendor", "high"),
                ("Receiving discrepancy - shipment 4408", "critical"),
                ("Lead time variance - raw materials", "medium"),
                ("Contract renewal overdue - logistics partner", "high"),
                ("Replenishment threshold breach - SKU 7743", "critical"),
                ("Vendor risk escalation - geopolitical exposure", "high"),
                ("Procurement compliance gap - approval bypass", "medium"),
            ])
        ]
        case_result = self._importer.import_cases(tenant_id, cases)
        result["cases"] = {"imported": case_result.accepted, "total": case_result.total_records}

        # Seed remediations linked to first 5 cases
        rems = [
            {"remediation_id": f"sc-rem-{i:03d}", "case_ref": f"sc-case-{i:03d}", "title": f"Remediate: {cases[i]['title']}"}
            for i in range(5)
        ]
        rem_result = self._importer.import_remediations(tenant_id, rems)
        result["remediations"] = {"imported": rem_result.accepted}

        # Seed evidence records
        records = [
            {"record_id": f"sc-rec-{i:03d}", "title": title}
            for i, title in enumerate([
                "Vendor scorecard",
                "PO confirmation",
                "Delivery receipt",
                "Inventory report",
                "Supplier certificate",
                "Lead time analysis",
                "Contract terms",
                "Compliance audit trail",
            ])
        ]
        rec_result = self._importer.import_records(tenant_id, records)
        result["records"] = {"imported": rec_result.accepted}

        result["status"] = "demo_ready"
        result["total_seeded"] = case_result.accepted + rem_result.accepted + rec_result.accepted
        return result

    @property
    def bootstrap(self) -> SupplyChainPackBootstrap:
        return self._bootstrap
