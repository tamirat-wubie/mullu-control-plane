"""Tests for PilotDeploymentEngine.

Governance scope: comprehensive coverage for bootstrap lifecycle, connector
activation, data migration, pilot phases, go-live assessment, runbook/SLO
registration, pilot assessment, violation detection, snapshots, and closure.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.pilot_deployment import PilotDeploymentEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.pilot_deployment import (
    BootstrapStatus,
    ConnectorActivation,
    ConnectorActivationStatus,
    DataMigration,
    GoLiveChecklist,
    GoLiveReadiness,
    MigrationStatus,
    PilotAssessment,
    PilotClosureReport,
    PilotPhase,
    PilotRecord,
    PilotViolation,
    RunbookEntry,
    SloDefinition,
    TenantBootstrap,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture()
def engine(spine: EventSpineEngine, clock: FixedClock) -> PilotDeploymentEngine:
    return PilotDeploymentEngine(spine, clock=clock)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_rejects_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PilotDeploymentEngine("not_an_engine")

    def test_valid(self, engine: PilotDeploymentEngine):
        assert engine.bootstrap_count == 0
        assert engine.connector_count == 0
        assert engine.migration_count == 0
        assert engine.pilot_count == 0
        assert engine.checklist_count == 0
        assert engine.runbook_count == 0
        assert engine.slo_count == 0
        assert engine.violation_count == 0


# ---------------------------------------------------------------------------
# Bootstrap lifecycle
# ---------------------------------------------------------------------------


class TestBootstrapLifecycle:
    def test_bootstrap_tenant(self, engine: PilotDeploymentEngine):
        b = engine.bootstrap_tenant("b1", "t1", "pack-1")
        assert isinstance(b, TenantBootstrap)
        assert b.status == BootstrapStatus.PENDING
        assert b.workspace_count == 0
        assert b.connector_count == 0
        assert engine.bootstrap_count == 1

    def test_duplicate_rejected(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.bootstrap_tenant("b1", "t1", "pack-2")

    def test_start_bootstrap(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        b = engine.start_bootstrap("b1")
        assert b.status == BootstrapStatus.IN_PROGRESS

    def test_complete_bootstrap(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.start_bootstrap("b1")
        b = engine.complete_bootstrap("b1")
        assert b.status == BootstrapStatus.COMPLETED

    def test_complete_bootstrap_requires_in_progress(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot transition"):
            engine.complete_bootstrap("b1")

    def test_fail_bootstrap(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        b = engine.fail_bootstrap("b1")
        assert b.status == BootstrapStatus.FAILED

    def test_rollback_from_failed(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.fail_bootstrap("b1")
        b = engine.rollback_bootstrap("b1")
        assert b.status == BootstrapStatus.ROLLED_BACK

    def test_rollback_from_in_progress(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.start_bootstrap("b1")
        b = engine.rollback_bootstrap("b1")
        assert b.status == BootstrapStatus.ROLLED_BACK

    def test_rollback_from_pending_rejected(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot transition"):
            engine.rollback_bootstrap("b1")

    def test_unknown_bootstrap_rejected(self, engine: PilotDeploymentEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.start_bootstrap("nope")


# ---------------------------------------------------------------------------
# Connector activation
# ---------------------------------------------------------------------------


class TestConnectorActivation:
    def test_activate_connector(self, engine: PilotDeploymentEngine):
        c = engine.activate_connector("a1", "t1", "http", "https://x.com")
        assert isinstance(c, ConnectorActivation)
        assert c.status == ConnectorActivationStatus.ACTIVATING
        assert c.health_check_passed is False
        assert engine.connector_count == 1

    def test_duplicate_rejected(self, engine: PilotDeploymentEngine):
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.activate_connector("a1", "t1", "grpc", "https://y.com")

    def test_complete_activation_passed(self, engine: PilotDeploymentEngine):
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        c = engine.complete_connector_activation("a1", True)
        assert c.status == ConnectorActivationStatus.ACTIVE
        assert c.health_check_passed is True

    def test_complete_activation_failed(self, engine: PilotDeploymentEngine):
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        c = engine.complete_connector_activation("a1", False)
        assert c.status == ConnectorActivationStatus.FAILED
        assert c.health_check_passed is False

    def test_degrade_connector(self, engine: PilotDeploymentEngine):
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        c = engine.degrade_connector("a1")
        assert c.status == ConnectorActivationStatus.DEGRADED

    def test_unknown_connector_rejected(self, engine: PilotDeploymentEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.complete_connector_activation("nope", True)


# ---------------------------------------------------------------------------
# Data migration
# ---------------------------------------------------------------------------


class TestDataMigration:
    def test_start_migration(self, engine: PilotDeploymentEngine):
        m = engine.start_migration("m1", "t1", "legacy", 100)
        assert isinstance(m, DataMigration)
        assert m.status == MigrationStatus.PENDING
        assert m.record_count == 100
        assert engine.migration_count == 1

    def test_duplicate_rejected(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.start_migration("m1", "t1", "other", 50)

    def test_validate_migration(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        m = engine.validate_migration("m1")
        assert m.status == MigrationStatus.VALIDATING

    def test_import_migration(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        engine.validate_migration("m1")
        m = engine.import_migration("m1")
        assert m.status == MigrationStatus.IMPORTING

    def test_complete_migration(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        engine.validate_migration("m1")
        engine.import_migration("m1")
        m = engine.complete_migration("m1", 95, 5)
        assert m.status == MigrationStatus.COMPLETED
        assert m.imported_count == 95
        assert m.failed_count == 5

    def test_fail_migration(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        m = engine.fail_migration("m1")
        assert m.status == MigrationStatus.FAILED


# ---------------------------------------------------------------------------
# Pilot lifecycle
# ---------------------------------------------------------------------------


class TestPilotLifecycle:
    def test_register_pilot(self, engine: PilotDeploymentEngine):
        p = engine.register_pilot("p1", "t1", "pack-1")
        assert isinstance(p, PilotRecord)
        assert p.phase == PilotPhase.SETUP
        assert engine.pilot_count == 1

    def test_duplicate_rejected(self, engine: PilotDeploymentEngine):
        engine.register_pilot("p1", "t1", "pack-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_pilot("p1", "t1", "pack-2")

    def test_advance_pilot_full_cycle(self, engine: PilotDeploymentEngine):
        engine.register_pilot("p1", "t1", "pack-1")
        p = engine.advance_pilot("p1")
        assert p.phase == PilotPhase.ONBOARDING
        p = engine.advance_pilot("p1")
        assert p.phase == PilotPhase.ACTIVE_USE
        p = engine.advance_pilot("p1")
        assert p.phase == PilotPhase.EVALUATION
        p = engine.advance_pilot("p1")
        assert p.phase == PilotPhase.GRADUATED

    def test_advance_past_graduated_rejected(self, engine: PilotDeploymentEngine):
        engine.register_pilot("p1", "t1", "pack-1")
        for _ in range(4):
            engine.advance_pilot("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.advance_pilot("p1")

    def test_unknown_pilot_rejected(self, engine: PilotDeploymentEngine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.advance_pilot("nope")


# ---------------------------------------------------------------------------
# Go-live assessment
# ---------------------------------------------------------------------------


class TestGoLiveAssessment:
    def test_empty_tenant(self, engine: PilotDeploymentEngine):
        gl = engine.assess_go_live("cl1", "t1", "p1")
        assert isinstance(gl, GoLiveChecklist)
        assert gl.total_items == 0
        assert gl.readiness == GoLiveReadiness.NOT_READY

    def test_all_completed(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.start_bootstrap("b1")
        engine.complete_bootstrap("b1")
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        engine.complete_connector_activation("a1", True)
        engine.start_migration("m1", "t1", "legacy", 100)
        engine.complete_migration("m1", 100, 0)

        gl = engine.assess_go_live("cl1", "t1", "p1")
        assert gl.total_items == 3
        assert gl.passed_items == 3
        assert gl.readiness == GoLiveReadiness.READY

    def test_partial_readiness(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.start_bootstrap("b1")
        engine.complete_bootstrap("b1")
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        engine.complete_connector_activation("a1", True)
        engine.start_migration("m1", "t1", "legacy", 100)
        # migration not completed

        gl = engine.assess_go_live("cl1", "t1", "p1")
        assert gl.total_items == 3
        assert gl.passed_items == 2
        # 2/3 = 0.667 < 0.7 -> NOT_READY
        assert gl.readiness == GoLiveReadiness.NOT_READY

    def test_seventy_percent_partial(self, engine: PilotDeploymentEngine):
        # Create 10 items, 7 completed -> 70% -> PARTIAL
        for i in range(7):
            engine.bootstrap_tenant(f"b{i}", "t1", "pack-1")
            engine.start_bootstrap(f"b{i}")
            engine.complete_bootstrap(f"b{i}")
        for i in range(3):
            engine.activate_connector(f"a{i}", "t1", "http", f"https://x{i}.com")
            # not completed

        gl = engine.assess_go_live("cl1", "t1", "p1")
        assert gl.total_items == 10
        assert gl.passed_items == 7
        assert gl.readiness == GoLiveReadiness.PARTIAL

    def test_duplicate_checklist_rejected(self, engine: PilotDeploymentEngine):
        engine.assess_go_live("cl1", "t1", "p1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.assess_go_live("cl1", "t1", "p1")


# ---------------------------------------------------------------------------
# Runbook & SLO
# ---------------------------------------------------------------------------


class TestRunbookAndSlo:
    def test_register_runbook(self, engine: PilotDeploymentEngine):
        rb = engine.register_runbook("rb1", "t1", "Restart", "ops", "Step 1")
        assert isinstance(rb, RunbookEntry)
        assert rb.title == "Restart"
        assert engine.runbook_count == 1

    def test_duplicate_runbook_rejected(self, engine: PilotDeploymentEngine):
        engine.register_runbook("rb1", "t1", "Restart", "ops", "Step 1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_runbook("rb1", "t1", "Other", "ops", "Step 2")

    def test_register_slo(self, engine: PilotDeploymentEngine):
        slo = engine.register_slo("s1", "t1", "uptime", 99.9, 99.5, "percent")
        assert isinstance(slo, SloDefinition)
        assert slo.target_value == 99.9
        assert engine.slo_count == 1

    def test_duplicate_slo_rejected(self, engine: PilotDeploymentEngine):
        engine.register_slo("s1", "t1", "uptime", 99.9, 99.5, "percent")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_slo("s1", "t1", "latency", 100.0, 50.0, "ms")


# ---------------------------------------------------------------------------
# Pilot assessment
# ---------------------------------------------------------------------------


class TestPilotAssessment:
    def test_empty_assessment(self, engine: PilotDeploymentEngine):
        pa = engine.pilot_assessment("pa1", "t1", "p1")
        assert isinstance(pa, PilotAssessment)
        assert pa.total_connectors == 0
        assert pa.readiness_score == 0.0

    def test_assessment_with_data(self, engine: PilotDeploymentEngine):
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        engine.complete_connector_activation("a1", True)
        engine.activate_connector("a2", "t1", "grpc", "https://y.com")
        engine.start_migration("m1", "t1", "legacy", 100)
        engine.complete_migration("m1", 100, 0)

        pa = engine.pilot_assessment("pa1", "t1", "p1")
        assert pa.total_connectors == 2
        assert pa.active_connectors == 1
        assert pa.migration_completeness == 1.0
        # connector_ratio = 0.5, migration = 1.0 -> avg = 0.75
        assert pa.readiness_score == 0.75


# ---------------------------------------------------------------------------
# Violation detection
# ---------------------------------------------------------------------------


class TestViolationDetection:
    def test_no_violations_empty(self, engine: PilotDeploymentEngine):
        violations = engine.detect_pilot_violations("t1")
        assert violations == ()

    def test_failed_connector_in_live_pilot(self, engine: PilotDeploymentEngine):
        engine.register_pilot("p1", "t1", "pack-1")
        # Advance to ACTIVE_USE (SETUP -> ONBOARDING -> ACTIVE_USE)
        engine.advance_pilot("p1")
        engine.advance_pilot("p1")
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        engine.complete_connector_activation("a1", False)  # FAILED

        violations = engine.detect_pilot_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "failed_connector_in_live_pilot"

    def test_incomplete_migration(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        engine.fail_migration("m1")

        violations = engine.detect_pilot_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "incomplete_migration"

    def test_slo_breach(self, engine: PilotDeploymentEngine):
        # target=100, current=80 -> 80 < 100*0.9=90 -> breach
        engine.register_slo("s1", "t1", "uptime", 100.0, 80.0, "percent")
        violations = engine.detect_pilot_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "slo_breach"

    def test_slo_no_breach(self, engine: PilotDeploymentEngine):
        # target=100, current=95 -> 95 >= 90 -> no breach
        engine.register_slo("s1", "t1", "uptime", 100.0, 95.0, "percent")
        violations = engine.detect_pilot_violations("t1")
        assert len(violations) == 0

    def test_idempotent(self, engine: PilotDeploymentEngine):
        engine.start_migration("m1", "t1", "legacy", 100)
        engine.fail_migration("m1")

        v1 = engine.detect_pilot_violations("t1")
        assert len(v1) == 1
        v2 = engine.detect_pilot_violations("t1")
        assert len(v2) == 0  # no new violations
        assert engine.violation_count == 1


# ---------------------------------------------------------------------------
# Snapshot and state hash
# ---------------------------------------------------------------------------


class TestSnapshotAndStateHash:
    def test_empty_state_hash(self, engine: PilotDeploymentEngine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_state_hash_changes(self, engine: PilotDeploymentEngine):
        h1 = engine.state_hash()
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        snap = engine.snapshot()
        assert "bootstraps" in snap
        assert "connectors" in snap
        assert "_state_hash" in snap
        assert len(snap["_state_hash"]) == 64

    def test_pilot_snapshot(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        snap = engine.pilot_snapshot("t1")
        assert snap["tenant_id"] == "t1"
        assert snap["bootstraps"] == 1

    def test_pilot_closure_report(self, engine: PilotDeploymentEngine):
        engine.bootstrap_tenant("b1", "t1", "pack-1")
        engine.activate_connector("a1", "t1", "http", "https://x.com")
        report = engine.pilot_closure_report("r1", "t1")
        assert isinstance(report, PilotClosureReport)
        assert report.total_bootstraps == 1
        assert report.total_connectors == 1

    def test_collections(self, engine: PilotDeploymentEngine):
        cols = engine._collections()
        assert "bootstraps" in cols
        assert "connectors" in cols
        assert "migrations" in cols
        assert "pilots" in cols
        assert "checklists" in cols
        assert "runbooks" in cols
        assert "slos" in cols
        assert "violations" in cols
