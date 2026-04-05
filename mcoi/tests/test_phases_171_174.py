"""Phases 171-174 — Healthcare Public Bundle, Twin Command Suite, Fleet Migration Tests."""
import pytest
from mcoi_runtime.pilot.healthcare_public_bundle import (
    BUNDLE_NAME as HPS_BUNDLE_NAME,
    BUNDLE_PACKS as HPS_BUNDLE_PACKS,
    HEALTHCARE_PUBLIC_SECTOR_PRICING,
    STITCHED_WORKFLOWS as HPS_STITCHED_WORKFLOWS,
    SOVEREIGN_CONFIG,
    HealthcarePublicSectorBundle,
)
from mcoi_runtime.pilot.twin_command_suite import (
    TWIN_COMMAND_CAPABILITIES,
    TWIN_COMMAND_KPIS,
    TWIN_COMMAND_PRICING,
    TwinCommandSuite,
)
from mcoi_runtime.pilot.fleet_migration import (
    ENGINES_NEEDING_CLOCK,
    ENGINES_NEEDING_SNAPSHOT,
    MigrationTracker,
    MigrationPlan,
    generate_migration_plan,
)


# ---------------------------------------------------------------------------
# Phase 171 — Healthcare + Public Sector Sovereign Bundle
# ---------------------------------------------------------------------------

class TestHealthcarePublicBundle:
    def test_bundle_definition(self):
        assert HPS_BUNDLE_NAME == "Healthcare Public Sector Sovereign Suite"
        assert len(HPS_BUNDLE_PACKS) == 2
        assert "healthcare" in HPS_BUNDLE_PACKS
        assert "public_sector" in HPS_BUNDLE_PACKS
        assert HEALTHCARE_PUBLIC_SECTOR_PRICING.monthly_individual == 6500.0
        assert HEALTHCARE_PUBLIC_SECTOR_PRICING.monthly_bundled == 5250.0
        assert HEALTHCARE_PUBLIC_SECTOR_PRICING.annual_savings == 15000.0

    def test_deploy_bundle(self):
        bundle = HealthcarePublicSectorBundle()
        result = bundle.deploy_bundle("hcps-test-001")
        assert result["status"] == "bundle_ready"
        assert len(result["packs_deployed"]) == 2
        assert result["total_capabilities"] >= 20
        assert result["stitched_workflows"] == 5
        assert result["cross_pack_active"]
        assert result["sovereign_profiles"] == 4

    def test_upgrade_healthcare_to_public(self):
        bundle = HealthcarePublicSectorBundle()
        bundle.deploy_bundle("hcps-upgrade")
        upgrade = bundle.upgrade_healthcare_to_public("hcps-upgrade")
        assert upgrade["status"] == "upgraded"
        assert upgrade["public_sector_added"]
        assert upgrade["new_monthly_price"] == 5250.0
        assert upgrade["stitched_workflows"] == 5

    def test_stitched_workflows(self):
        assert len(HPS_STITCHED_WORKFLOWS) == 5
        names = {wf.name for wf in HPS_STITCHED_WORKFLOWS}
        assert "patient_case_triggers_public_health_review" in names
        assert "public_service_request_opens_clinical_governance" in names
        assert "copilot_cross_clinical_public_evidence" in names
        # All cross-pack
        for wf in HPS_STITCHED_WORKFLOWS:
            assert wf.trigger_pack != wf.target_pack


# ---------------------------------------------------------------------------
# Phase 172 — Industrial Digital Twin Command Suite
# ---------------------------------------------------------------------------

class TestTwinCommandSuite:
    def test_capabilities(self):
        assert len(TWIN_COMMAND_CAPABILITIES) == 14
        assert "twin_live_view" in TWIN_COMMAND_CAPABILITIES
        assert "twin_state_overlay" in TWIN_COMMAND_CAPABILITIES
        assert "process_deviation_monitor" in TWIN_COMMAND_CAPABILITIES

    def test_pricing(self):
        assert TWIN_COMMAND_PRICING.monthly_individual == 10000.0
        assert TWIN_COMMAND_PRICING.monthly_bundled == 8000.0
        assert TWIN_COMMAND_PRICING.annual_savings == 24000.0
        assert TWIN_COMMAND_PRICING.monthly_bundled < TWIN_COMMAND_PRICING.monthly_individual

    def test_deploy_suite(self):
        suite = TwinCommandSuite()
        result = suite.deploy_suite("twin-test-001")
        assert result["status"] == "suite_ready"
        assert "twin_command" in result["packs_deployed"]
        assert result["total_capabilities"] == 14
        assert result["total_kpis"] == 15

    def test_kpis(self):
        assert len(TWIN_COMMAND_KPIS) == 15
        # Original 10 industrial KPIs present
        for kpi in ("oee", "throughput_rate", "yield_rate", "downtime_pct",
                     "quality_pass_rate", "mttr_hours", "supply_lead_days",
                     "maintenance_backlog", "scrap_rate", "energy_per_unit"):
            assert kpi in TWIN_COMMAND_KPIS
        # 5 twin-specific KPIs
        for kpi in ("twin_sync_rate", "state_freshness_seconds", "deviation_count",
                     "twin_coverage_pct", "anomaly_detection_rate"):
            assert kpi in TWIN_COMMAND_KPIS


# ---------------------------------------------------------------------------
# Phases 173-174 — Fleet Migration
# ---------------------------------------------------------------------------

class TestFleetMigration:
    def test_tracker(self):
        tracker = MigrationTracker()
        tracker.track_engine("billing_engine", "clock")
        tracker.track_engine("billing_engine", "snapshot")
        tracker.track_engine("customer_engine", "clock")

        prog = tracker.progress()
        assert prog["total"] == 3
        assert prog["complete"] == 0
        assert prog["pending"] == 3

        tracker.mark_complete("billing_engine", "clock")
        prog = tracker.progress()
        assert prog["complete"] == 1
        assert prog["pending"] == 2

        tracker.mark_complete("billing_engine")  # completes remaining (snapshot)
        prog = tracker.progress()
        assert prog["complete"] == 2

    def test_invalid_migration_type_error_is_bounded(self):
        tracker = MigrationTracker()
        with pytest.raises(ValueError, match="migration_type") as excinfo:
            tracker.track_engine("billing_engine", "full")
        assert str(excinfo.value) == "migration_type must be 'clock' or 'snapshot'"
        assert "full" not in str(excinfo.value)

    def test_missing_tracked_migration_error_is_bounded(self):
        tracker = MigrationTracker()
        with pytest.raises(KeyError) as excinfo:
            tracker.mark_complete("billing_engine", "clock")
        assert excinfo.value.args[0] == "no tracked migration"
        assert "billing_engine" not in excinfo.value.args[0]
        assert "clock" not in excinfo.value.args[0]

    def test_plan_generation(self):
        plans = generate_migration_plan()
        assert len(plans) > 0
        # All plans are MigrationPlan instances
        for p in plans:
            assert isinstance(p, MigrationPlan)
            assert p.migration_type in ("clock", "snapshot")
            assert p.priority in ("critical", "high", "medium", "low")
            assert p.estimated_hours > 0

    def test_priority_ordering(self):
        plans = generate_migration_plan()
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for i in range(len(plans) - 1):
            assert priority_order[plans[i].priority] <= priority_order[plans[i + 1].priority]

    def test_progress_summary(self):
        tracker = MigrationTracker()
        for path in ENGINES_NEEDING_CLOCK[:5]:
            name = path.rsplit("/", 1)[-1].replace(".py", "")
            tracker.track_engine(name, "clock")

        summary = tracker.summary()
        assert summary["clock"]["total"] == 5
        assert summary["snapshot"]["total"] == 0
        assert summary["overall"]["total"] == 5
        assert summary["overall"]["percent_complete"] == 0.0

        # Complete one
        first_name = ENGINES_NEEDING_CLOCK[0].rsplit("/", 1)[-1].replace(".py", "")
        tracker.mark_complete(first_name, "clock")
        summary = tracker.summary()
        assert summary["clock"]["complete"] == 1
        assert summary["overall"]["percent_complete"] == 20.0


# ---------------------------------------------------------------------------
# Golden Proof
# ---------------------------------------------------------------------------

class TestGoldenProof:
    def test_bundle_lifecycle(self):
        """End-to-end lifecycle: deploy, seed, upgrade for healthcare public bundle."""
        bundle = HealthcarePublicSectorBundle()

        # Deploy
        deploy = bundle.deploy_bundle("golden-hcps")
        assert deploy["status"] == "bundle_ready"
        assert deploy["total_capabilities"] >= 20
        assert len(deploy["packs_deployed"]) == 2

        # Seed demo (5 + 5 + 5 = 15 seeded)
        demo = bundle.seed_bundle_demo("golden-hcps")
        assert demo["status"] == "demo_ready"
        assert demo["healthcare_cases"] == 5
        assert demo["public_sector_cases"] == 5
        assert demo["evidence_records"] == 5
        assert demo["total_seeded"] == 15

        # Upgrade path
        upgrade = bundle.upgrade_healthcare_to_public("golden-hcps")
        assert upgrade["status"] == "upgraded"
        assert upgrade["new_monthly_price"] == 5250.0

        # Sovereign config completeness
        assert len(SOVEREIGN_CONFIG["profile_compatibility"]) == 4
        assert SOVEREIGN_CONFIG["copilot_mode_defaults"]["restricted"] == "explain_only"
        assert SOVEREIGN_CONFIG["copilot_mode_defaults"]["classified"] == "explain_only"

    def test_migration_plan_completeness(self):
        """Migration plan covers all engines in both lists."""
        plans = generate_migration_plan()

        clock_engines = {p.engine_name for p in plans if p.migration_type == "clock"}
        snapshot_engines = {p.engine_name for p in plans if p.migration_type == "snapshot"}

        expected_clock = {p.rsplit("/", 1)[-1].replace(".py", "") for p in ENGINES_NEEDING_CLOCK}
        expected_snapshot = {p.rsplit("/", 1)[-1].replace(".py", "") for p in ENGINES_NEEDING_SNAPSHOT}

        assert clock_engines == expected_clock
        assert snapshot_engines == expected_snapshot

        # Critical engines are first
        critical_plans = [p for p in plans if p.priority == "critical"]
        assert len(critical_plans) > 0
        assert all(p.engine_name in ("billing_engine", "settlement_engine", "customer_engine",
                                      "marketplace_engine", "invoice_engine", "payment_engine")
                   for p in critical_plans)
