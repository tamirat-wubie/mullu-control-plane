"""Phase 124C — Single Pilot Tenant Bootstrap."""
from __future__ import annotations
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.industry_pack import IndustryPackEngine
from mcoi_runtime.core.pilot_deployment import PilotDeploymentEngine
from mcoi_runtime.core.product_console import ProductConsoleEngine
from mcoi_runtime.core.persona_runtime import PersonaRuntimeEngine
from mcoi_runtime.core.copilot_runtime import CopilotRuntimeEngine
from mcoi_runtime.core.constitutional_governance import ConstitutionalGovernanceEngine
from mcoi_runtime.contracts.persona_runtime import PersonaKind, InteractionStyle, AuthorityMode
from mcoi_runtime.contracts.constitutional_governance import ConstitutionRuleKind, PrecedenceLevel
from mcoi_runtime.pilot.scope_config import PILOT_CAPABILITIES, PILOT_CONNECTORS
from mcoi_runtime.pilot.connector_profiles import ALL_REQUIRED_PROFILES

class PilotTenantBootstrap:
    """Bootstraps a complete pilot tenant for Regulated Operations Control Tower."""

    def __init__(self, event_spine: EventSpineEngine):
        self._es = event_spine
        self._mm = MemoryMeshEngine()
        self._pack_engine = IndustryPackEngine(event_spine)
        self._pilot_engine = PilotDeploymentEngine(event_spine)
        self._console_engine = ProductConsoleEngine(event_spine)
        self._persona_engine = PersonaRuntimeEngine(event_spine)
        self._copilot_engine = CopilotRuntimeEngine(event_spine)
        self._governance_engine = ConstitutionalGovernanceEngine(event_spine)

    def bootstrap(self, tenant_id: str) -> dict[str, Any]:
        """Execute complete tenant bootstrap. Returns summary."""
        results: dict[str, Any] = {"tenant_id": tenant_id, "steps": []}

        # 1. Create regulated ops pack
        pack_result = self._pack_engine.bootstrap_regulated_ops_pack(f"pack-{tenant_id}", tenant_id)
        results["pack"] = pack_result
        results["steps"].append("pack_created")

        # 2. Bootstrap tenant deployment
        self._pilot_engine.bootstrap_tenant(f"bootstrap-{tenant_id}", tenant_id, f"pack-{tenant_id}")
        self._pilot_engine.start_bootstrap(f"bootstrap-{tenant_id}")
        results["steps"].append("tenant_bootstrapped")

        # 3. Activate connectors
        activated = []
        for i, profile in enumerate(ALL_REQUIRED_PROFILES):
            act_id = f"conn-{tenant_id}-{i}"
            self._pilot_engine.activate_connector(act_id, tenant_id, profile.connector_type, profile.endpoint_url)
            activated.append(profile.connector_type)
        results["connectors_activated"] = activated
        results["steps"].append("connectors_activated")

        # 4. Create personas
        personas_created = []
        for kind, style, authority, name in [
            (PersonaKind.OPERATOR, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Operator"),
            (PersonaKind.EXECUTIVE, InteractionStyle.CONCISE, AuthorityMode.GUIDED, "Executive"),
            (PersonaKind.INVESTIGATOR, InteractionStyle.DETAILED, AuthorityMode.GUIDED, "Investigator"),
            (PersonaKind.REGULATORY, InteractionStyle.FORMAL, AuthorityMode.READ_ONLY, "Compliance"),
        ]:
            pid = f"persona-{tenant_id}-{name.lower()}"
            self._persona_engine.register_persona(pid, tenant_id, f"{name} Assistant", kind, style, authority)
            personas_created.append(pid)
        results["personas"] = personas_created
        results["steps"].append("personas_created")

        # 5. Create constitutional rules
        rules_created = []
        for rule_name, kind in [
            ("no_unauthorized_data_access", ConstitutionRuleKind.HARD_DENY),
            ("require_evidence_for_closure", ConstitutionRuleKind.REQUIRE),
            ("restrict_external_execution", ConstitutionRuleKind.RESTRICT),
        ]:
            rid = f"rule-{tenant_id}-{rule_name}"
            self._governance_engine.register_rule(rid, tenant_id, rule_name, kind, PrecedenceLevel.TENANT, target_runtime="*")
            rules_created.append(rid)
        results["governance_rules"] = rules_created
        results["steps"].append("governance_configured")

        # 6. Register pilot
        self._pilot_engine.register_pilot(f"pilot-{tenant_id}", tenant_id, f"pack-{tenant_id}")
        results["steps"].append("pilot_registered")

        # 7. Complete bootstrap
        self._pilot_engine.complete_bootstrap(f"bootstrap-{tenant_id}")
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
            "console": self._console_engine,
            "persona": self._persona_engine,
            "copilot": self._copilot_engine,
            "governance": self._governance_engine,
        }
