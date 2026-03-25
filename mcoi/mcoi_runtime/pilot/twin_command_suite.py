"""Phase 172 — Industrial Digital Twin Command Suite.

Bundles factory + supply chain + digital twin + command center into one premium offering.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.pilot.industrial_suite import IndustrialSuiteBundle, INDUSTRIAL_PRICING
from mcoi_runtime.pilot.data_import import PilotDataImporter

# 14 capabilities: factory 11 + supply chain 10 baseline deduplicated
# plus 3 twin-specific capabilities
TWIN_COMMAND_CAPABILITIES = (
    # Factory quality capabilities (11)
    "line_status_monitoring",
    "downtime_tracking",
    "quality_gate_inspection",
    "yield_analysis",
    "maintenance_scheduling",
    "calibration_tracking",
    "batch_genealogy",
    "process_parameter_control",
    "oee_calculation",
    "scrap_analysis",
    "energy_monitoring",
    # Supply chain capabilities (from the 10 supply chain)  -- not all repeated
    # Twin command layer capabilities (3 new)
    "twin_live_view",
    "twin_state_overlay",
    "process_deviation_monitor",
)


@dataclass(frozen=True)
class TwinCommandPricing:
    name: str = "Industrial Digital Twin Command Suite"
    monthly_individual: float = 10000.0
    monthly_bundled: float = 8000.0
    annual_savings: float = 24000.0
    discount_percent: float = 20.0


TWIN_COMMAND_PRICING = TwinCommandPricing()

# 15 KPIs: original 10 industrial + 5 twin-specific
TWIN_COMMAND_KPIS = (
    # Original 10 industrial KPIs
    "oee",
    "throughput_rate",
    "yield_rate",
    "downtime_pct",
    "quality_pass_rate",
    "mttr_hours",
    "supply_lead_days",
    "maintenance_backlog",
    "scrap_rate",
    "energy_per_unit",
    # 5 twin-specific KPIs
    "twin_sync_rate",
    "state_freshness_seconds",
    "deviation_count",
    "twin_coverage_pct",
    "anomaly_detection_rate",
)


class TwinCommandSuite:
    """Premium industrial suite with digital twin command center layer."""

    def __init__(self):
        self._industrial = IndustrialSuiteBundle()
        self._es = self._industrial._es
        self._importer = PilotDataImporter(self._es)

    def deploy_suite(self, tenant_id: str) -> dict[str, Any]:
        """Deploy industrial bundle + add twin command layer."""
        result: dict[str, Any] = {"tenant_id": tenant_id, "suite": TWIN_COMMAND_PRICING.name}

        # 1. Deploy the base industrial bundle
        ind_result = self._industrial.deploy_bundle(tenant_id)
        result["industrial_base"] = ind_result
        result["packs_deployed"] = ind_result.get("packs_deployed", [])

        # 2. Add twin command layer
        result["twin_command_layer"] = {
            "capabilities": list(TWIN_COMMAND_CAPABILITIES),
            "capability_count": len(TWIN_COMMAND_CAPABILITIES),
            "kpis": list(TWIN_COMMAND_KPIS),
            "kpi_count": len(TWIN_COMMAND_KPIS),
        }
        result["packs_deployed"].append("twin_command")

        result["status"] = "suite_ready"
        result["total_capabilities"] = len(TWIN_COMMAND_CAPABILITIES)
        result["total_kpis"] = len(TWIN_COMMAND_KPIS)
        return result

    def seed_demo(self, tenant_id: str) -> dict[str, Any]:
        """Seed demo data for the full twin command suite."""
        result: dict[str, Any] = {"tenant_id": tenant_id}

        # Seed the base industrial demo
        ind_demo = self._industrial.seed_bundle_demo(tenant_id)
        result["industrial_demo"] = ind_demo

        # Twin command specific demo data
        twin_cases = [
            {"case_id": f"twin-cmd-{i}", "title": t}
            for i, t in enumerate([
                "Digital twin desync - Plant A Line 3",
                "State overlay mismatch - conveyor section",
                "Process deviation detected - temperature drift",
                "Twin coverage gap - Station D sensors",
                "Anomaly alert - vibration pattern change",
            ])
        ]
        twin_import = self._importer.import_cases(f"{tenant_id}-twin", twin_cases)
        result["twin_cases"] = twin_import.accepted

        result["total_seeded"] = ind_demo.get("total_seeded", 0) + twin_import.accepted
        result["status"] = "demo_ready"
        return result

    def upgrade_industrial_to_twin(self, tenant_id: str) -> dict[str, Any]:
        """Upgrade an existing industrial suite customer to the twin command suite."""
        return {
            "tenant_id": tenant_id,
            "upgrade_type": "industrial_to_twin_command",
            "twin_command_added": True,
            "twin_capabilities_added": ["twin_live_view", "twin_state_overlay", "process_deviation_monitor"],
            "new_kpis_added": ["twin_sync_rate", "state_freshness_seconds", "deviation_count",
                               "twin_coverage_pct", "anomaly_detection_rate"],
            "total_capabilities": len(TWIN_COMMAND_CAPABILITIES),
            "total_kpis": len(TWIN_COMMAND_KPIS),
            "new_monthly_price": TWIN_COMMAND_PRICING.monthly_bundled,
            "status": "upgraded",
        }

    @property
    def engines(self) -> dict[str, Any]:
        return {
            **self._industrial.engines,
            "importer": self._importer,
        }
