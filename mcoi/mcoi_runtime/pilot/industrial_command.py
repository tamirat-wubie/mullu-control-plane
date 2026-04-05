"""Phase 166 — Industrial Command Center (deepens the industrial lane)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

INDUSTRIAL_COMMAND_CAPABILITIES = (
    "real_time_line_status",
    "downtime_impact_view",
    "quality_gate_board",
    "supply_chain_risk_feed",
    "maintenance_priority_queue",
    "throughput_yield_dashboard",
    "digital_twin_overview",
    "process_deviation_alerts",
)

INDUSTRIAL_KPIS = (
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
)


@dataclass
class IndustrialCommandConfig:
    plant_count: int
    line_count: int
    station_count: int
    machine_count: int
    refresh_interval_seconds: int = 30


class IndustrialCommandDashboard:
    """Command-center dashboard for industrial operations."""

    def __init__(self, config: IndustrialCommandConfig):
        self._config = config
        self._plants: dict[str, dict[str, Any]] = {}
        self._kpis: dict[str, dict[str, float]] = {}  # plant_id -> {kpi_name: value}

    @property
    def config(self) -> IndustrialCommandConfig:
        return self._config

    def register_plant(self, plant_id: str, name: str, **metadata: Any) -> dict[str, Any]:
        """Register a plant in the command center."""
        entry: dict[str, Any] = {
            "plant_id": plant_id,
            "name": name,
            "status": "online",
            "capabilities": list(INDUSTRIAL_COMMAND_CAPABILITIES),
            **metadata,
        }
        self._plants[plant_id] = entry
        self._kpis[plant_id] = {}
        return entry

    def add_kpi(self, plant_id: str, kpi_name: str, value: float) -> dict[str, Any]:
        """Add or update a KPI value for a plant."""
        if plant_id not in self._plants:
            raise KeyError("plant not registered")
        if kpi_name not in INDUSTRIAL_KPIS:
            raise ValueError("unknown KPI")
        self._kpis[plant_id][kpi_name] = value
        return {"plant_id": plant_id, "kpi": kpi_name, "value": value, "status": "recorded"}

    def get_plant_status(self, plant_id: str) -> dict[str, Any]:
        """Return status and KPIs for a single plant."""
        if plant_id not in self._plants:
            raise KeyError("plant not registered")
        plant = self._plants[plant_id]
        kpis = self._kpis.get(plant_id, {})
        return {
            **plant,
            "kpis": dict(kpis),
            "kpi_count": len(kpis),
        }

    def aggregate_status(self) -> dict[str, Any]:
        """Aggregate status across all registered plants."""
        total_kpis = sum(len(v) for v in self._kpis.values())
        return {
            "plant_count": len(self._plants),
            "total_kpis_recorded": total_kpis,
            "plants": list(self._plants.keys()),
            "capabilities": list(INDUSTRIAL_COMMAND_CAPABILITIES),
            "refresh_interval_seconds": self._config.refresh_interval_seconds,
        }

    def command_summary(self) -> dict[str, Any]:
        """High-level command-center summary."""
        return {
            "config": {
                "plant_count": self._config.plant_count,
                "line_count": self._config.line_count,
                "station_count": self._config.station_count,
                "machine_count": self._config.machine_count,
                "refresh_interval_seconds": self._config.refresh_interval_seconds,
            },
            "registered_plants": len(self._plants),
            "capability_count": len(INDUSTRIAL_COMMAND_CAPABILITIES),
            "kpi_count": len(INDUSTRIAL_KPIS),
            "status": "command_center_active" if self._plants else "awaiting_plants",
        }
