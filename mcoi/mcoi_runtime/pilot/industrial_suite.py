"""Phase 143 — Industrial Operations Suite (Factory + Supply Chain Bundle)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.factory_quality_pack import FactoryQualityPackBootstrap
from mcoi_runtime.pilot.supply_chain_pack import SupplyChainPackBootstrap
from mcoi_runtime.pilot.data_import import PilotDataImporter

BUNDLE_NAME = "Industrial Operations Suite"
BUNDLE_PACKS = ("factory_quality", "supply_chain")

@dataclass(frozen=True)
class IndustrialBundlePricing:
    name: str = BUNDLE_NAME
    monthly_individual: float = 8000.0  # 4000 factory + 4000 supply (with industrial premium)
    monthly_bundled: float = 6500.0
    annual_savings: float = 18000.0
    discount_percent: float = 18.75

INDUSTRIAL_PRICING = IndustrialBundlePricing()

@dataclass(frozen=True)
class IndustrialStitchedWorkflow:
    name: str
    trigger_pack: str
    target_pack: str
    description: str

STITCHED_WORKFLOWS = (
    IndustrialStitchedWorkflow("downtime_triggers_procurement", "factory_quality", "supply_chain",
        "Machine downtime triggers supply/parts procurement review for replacement components"),
    IndustrialStitchedWorkflow("supplier_delay_impacts_production", "supply_chain", "factory_quality",
        "Supplier delivery delay triggers production risk assessment and throughput impact visibility"),
    IndustrialStitchedWorkflow("quality_failure_traces_vendor", "factory_quality", "supply_chain",
        "Quality failure triggers vendor and material trace review across supply chain"),
    IndustrialStitchedWorkflow("replenishment_affects_scheduling", "supply_chain", "factory_quality",
        "Replenishment exception affects batch scheduling and line utilization planning"),
    IndustrialStitchedWorkflow("twin_reflects_supply_constraint", "factory_quality", "supply_chain",
        "Digital twin reflects both plant degradation state and supply constraint impact"),
    IndustrialStitchedWorkflow("copilot_cross_industrial", "factory_quality", "supply_chain",
        "Copilot explains industrial issue using both factory and supply chain evidence"),
)

class IndustrialSuiteBundle:
    """One-call deployment for Factory + Supply Chain industrial suite."""

    def __init__(self):
        self._es = EventSpineEngine()
        self._factory = FactoryQualityPackBootstrap(self._es)
        self._supply = SupplyChainPackBootstrap(self._es)
        self._importer = PilotDataImporter(self._es)

    def deploy_bundle(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id, "bundle": BUNDLE_NAME, "packs_deployed": []}

        # 1. Deploy factory quality pack
        fac_result = self._factory.bootstrap(tenant_id)
        result["factory_quality"] = fac_result
        result["packs_deployed"].append("factory_quality")

        # 2. Deploy supply chain pack
        sc_result = self._supply.bootstrap(f"{tenant_id}-sc")
        result["supply_chain"] = sc_result
        result["packs_deployed"].append("supply_chain")

        # 3. Stitched workflows
        result["stitched_workflows"] = len(STITCHED_WORKFLOWS)
        result["cross_pack_active"] = True

        result["status"] = "bundle_ready"
        result["total_capabilities"] = (
            fac_result.get("capability_count", 11) +
            sc_result.get("capability_count", 10)
        )
        return result

    def seed_bundle_demo(self, tenant_id: str) -> dict[str, Any]:
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Factory cases
        fac_cases = [
            {"case_id": f"ind-fac-{i}", "title": t}
            for i, t in enumerate([
                "CNC machine breakdown - Line 2", "Quality failure batch 7891",
                "Unplanned downtime Station C", "Yield drop below threshold",
                "Calibration overdue - press 4",
            ])
        ]
        fac_import = self._importer.import_cases(tenant_id, fac_cases)
        result["factory_cases"] = fac_import.accepted

        # Supply chain cases
        sc_cases = [
            {"case_id": f"ind-sc-{i}", "title": t}
            for i, t in enumerate([
                "Vendor delivery delay - raw materials", "PO approval backlog",
                "Supplier quality audit overdue", "Inventory stockout alert",
                "Replenishment threshold breach",
            ])
        ]
        sc_import = self._importer.import_cases(f"{tenant_id}-sc", sc_cases)
        result["supply_chain_cases"] = sc_import.accepted

        # Cross-domain evidence
        evidence = [
            {"record_id": f"ind-ev-{i}", "title": t}
            for i, t in enumerate([
                "Machine maintenance log", "Vendor scorecard",
                "Batch genealogy trace", "PO confirmation document",
                "Process parameter chart", "Delivery receipt",
                "Quality inspection report", "Supply risk assessment",
            ])
        ]
        ev_import = self._importer.import_records(tenant_id, evidence)
        result["evidence_records"] = ev_import.accepted

        result["total_seeded"] = fac_import.accepted + sc_import.accepted + ev_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_factory_customer(self, tenant_id: str) -> dict[str, Any]:
        sc_result = self._supply.bootstrap(f"{tenant_id}-sc-upgrade")
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "factory_to_industrial_suite",
            "supply_chain_added": True,
            "supply_chain_capabilities": sc_result.get("capability_count", 10),
            "stitched_workflows": len(STITCHED_WORKFLOWS),
            "new_monthly_price": INDUSTRIAL_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            "event_spine": self._es,
            "factory": self._factory,
            "supply_chain": self._supply,
            "importer": self._importer,
        }
