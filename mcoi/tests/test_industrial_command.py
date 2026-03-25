"""Phase 166 — Industrial Command Center Tests."""
import pytest
from mcoi_runtime.pilot.industrial_command import (
    INDUSTRIAL_COMMAND_CAPABILITIES, INDUSTRIAL_KPIS,
    IndustrialCommandConfig, IndustrialCommandDashboard,
)


class TestCapabilitiesAndKPIs:
    def test_8_capabilities(self):
        assert len(INDUSTRIAL_COMMAND_CAPABILITIES) == 8

    def test_10_kpis(self):
        assert len(INDUSTRIAL_KPIS) == 10

    def test_known_capabilities(self):
        assert "real_time_line_status" in INDUSTRIAL_COMMAND_CAPABILITIES
        assert "digital_twin_overview" in INDUSTRIAL_COMMAND_CAPABILITIES
        assert "process_deviation_alerts" in INDUSTRIAL_COMMAND_CAPABILITIES

    def test_known_kpis(self):
        assert "oee" in INDUSTRIAL_KPIS
        assert "throughput_rate" in INDUSTRIAL_KPIS
        assert "energy_per_unit" in INDUSTRIAL_KPIS


class TestConfig:
    def test_default_refresh(self):
        cfg = IndustrialCommandConfig(plant_count=2, line_count=4, station_count=8, machine_count=20)
        assert cfg.refresh_interval_seconds == 30

    def test_custom_refresh(self):
        cfg = IndustrialCommandConfig(plant_count=1, line_count=2, station_count=4, machine_count=10, refresh_interval_seconds=5)
        assert cfg.refresh_interval_seconds == 5


class TestDashboard:
    def _make_dashboard(self) -> IndustrialCommandDashboard:
        cfg = IndustrialCommandConfig(plant_count=2, line_count=4, station_count=8, machine_count=20)
        return IndustrialCommandDashboard(cfg)

    def test_register_plant(self):
        dash = self._make_dashboard()
        plant = dash.register_plant("P1", "Plant Alpha")
        assert plant["plant_id"] == "P1"
        assert plant["status"] == "online"
        assert len(plant["capabilities"]) == 8

    def test_add_kpi(self):
        dash = self._make_dashboard()
        dash.register_plant("P1", "Plant Alpha")
        kpi = dash.add_kpi("P1", "oee", 87.5)
        assert kpi["status"] == "recorded"
        assert kpi["value"] == 87.5

    def test_add_kpi_unknown_plant_raises(self):
        dash = self._make_dashboard()
        with pytest.raises(KeyError):
            dash.add_kpi("MISSING", "oee", 50.0)

    def test_add_kpi_unknown_kpi_raises(self):
        dash = self._make_dashboard()
        dash.register_plant("P1", "Plant Alpha")
        with pytest.raises(ValueError):
            dash.add_kpi("P1", "not_a_kpi", 0.0)

    def test_get_plant_status(self):
        dash = self._make_dashboard()
        dash.register_plant("P1", "Plant Alpha")
        dash.add_kpi("P1", "oee", 90.0)
        dash.add_kpi("P1", "yield_rate", 95.0)
        status = dash.get_plant_status("P1")
        assert status["kpi_count"] == 2
        assert status["kpis"]["oee"] == 90.0

    def test_aggregate_status(self):
        dash = self._make_dashboard()
        dash.register_plant("P1", "Plant Alpha")
        dash.register_plant("P2", "Plant Beta")
        dash.add_kpi("P1", "oee", 90.0)
        dash.add_kpi("P2", "throughput_rate", 120.0)
        agg = dash.aggregate_status()
        assert agg["plant_count"] == 2
        assert agg["total_kpis_recorded"] == 2
        assert set(agg["plants"]) == {"P1", "P2"}

    def test_command_summary_no_plants(self):
        dash = self._make_dashboard()
        summary = dash.command_summary()
        assert summary["status"] == "awaiting_plants"
        assert summary["capability_count"] == 8
        assert summary["kpi_count"] == 10

    def test_command_summary_with_plants(self):
        dash = self._make_dashboard()
        dash.register_plant("P1", "Plant Alpha")
        summary = dash.command_summary()
        assert summary["status"] == "command_center_active"
        assert summary["registered_plants"] == 1


class TestGoldenProof:
    def test_industrial_command_lifecycle(self):
        cfg = IndustrialCommandConfig(plant_count=3, line_count=6, station_count=12, machine_count=30)
        dash = IndustrialCommandDashboard(cfg)

        # 1. Register plants
        dash.register_plant("P1", "Plant Alpha")
        dash.register_plant("P2", "Plant Beta")
        dash.register_plant("P3", "Plant Gamma")

        # 2. Record KPIs
        for pid in ("P1", "P2", "P3"):
            dash.add_kpi(pid, "oee", 85.0)
            dash.add_kpi(pid, "throughput_rate", 100.0)

        # 3. Aggregate
        agg = dash.aggregate_status()
        assert agg["plant_count"] == 3
        assert agg["total_kpis_recorded"] == 6

        # 4. Summary
        summary = dash.command_summary()
        assert summary["status"] == "command_center_active"
        assert summary["capability_count"] == 8
        assert summary["kpi_count"] == 10
        assert summary["config"]["plant_count"] == 3
