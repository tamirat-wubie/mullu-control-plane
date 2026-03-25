"""Tests for pilot deployment contracts.

Governance scope: comprehensive coverage for all enums, dataclasses,
validation rules, immutability invariants, metadata freezing, and
serialization in the pilot_deployment contract module.
"""

from types import MappingProxyType

import pytest

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
    PilotRiskLevel,
    PilotViolation,
    RunbookEntry,
    SloDefinition,
    TenantBootstrap,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = "2026-03-24T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_bootstrap_status_members(self):
        assert len(BootstrapStatus) == 5
        assert BootstrapStatus.PENDING.value == "pending"
        assert BootstrapStatus.IN_PROGRESS.value == "in_progress"
        assert BootstrapStatus.COMPLETED.value == "completed"
        assert BootstrapStatus.FAILED.value == "failed"
        assert BootstrapStatus.ROLLED_BACK.value == "rolled_back"

    def test_connector_activation_status_members(self):
        assert len(ConnectorActivationStatus) == 5
        assert ConnectorActivationStatus.INACTIVE.value == "inactive"
        assert ConnectorActivationStatus.ACTIVATING.value == "activating"
        assert ConnectorActivationStatus.ACTIVE.value == "active"
        assert ConnectorActivationStatus.DEGRADED.value == "degraded"
        assert ConnectorActivationStatus.FAILED.value == "failed"

    def test_migration_status_members(self):
        assert len(MigrationStatus) == 5
        assert MigrationStatus.PENDING.value == "pending"
        assert MigrationStatus.VALIDATING.value == "validating"
        assert MigrationStatus.IMPORTING.value == "importing"
        assert MigrationStatus.COMPLETED.value == "completed"
        assert MigrationStatus.FAILED.value == "failed"

    def test_pilot_phase_members(self):
        assert len(PilotPhase) == 5
        assert PilotPhase.SETUP.value == "setup"
        assert PilotPhase.ONBOARDING.value == "onboarding"
        assert PilotPhase.ACTIVE_USE.value == "active_use"
        assert PilotPhase.EVALUATION.value == "evaluation"
        assert PilotPhase.GRADUATED.value == "graduated"

    def test_go_live_readiness_members(self):
        assert len(GoLiveReadiness) == 4
        assert GoLiveReadiness.NOT_READY.value == "not_ready"
        assert GoLiveReadiness.PARTIAL.value == "partial"
        assert GoLiveReadiness.READY.value == "ready"
        assert GoLiveReadiness.LIVE.value == "live"

    def test_pilot_risk_level_members(self):
        assert len(PilotRiskLevel) == 4
        assert PilotRiskLevel.LOW.value == "low"
        assert PilotRiskLevel.MEDIUM.value == "medium"
        assert PilotRiskLevel.HIGH.value == "high"
        assert PilotRiskLevel.CRITICAL.value == "critical"


# ---------------------------------------------------------------------------
# TenantBootstrap
# ---------------------------------------------------------------------------


class TestTenantBootstrap:
    def test_valid(self):
        b = TenantBootstrap(
            bootstrap_id="b1", tenant_id="t1", pack_ref="p1",
            status=BootstrapStatus.PENDING, workspace_count=0,
            connector_count=0, created_at=_NOW,
        )
        assert b.bootstrap_id == "b1"
        assert b.status == BootstrapStatus.PENDING
        assert b.workspace_count == 0
        assert b.connector_count == 0

    def test_empty_bootstrap_id_rejected(self):
        with pytest.raises(ValueError):
            TenantBootstrap(
                bootstrap_id="", tenant_id="t1", pack_ref="p1",
                status=BootstrapStatus.PENDING, created_at=_NOW,
            )

    def test_negative_workspace_count_rejected(self):
        with pytest.raises(ValueError):
            TenantBootstrap(
                bootstrap_id="b1", tenant_id="t1", pack_ref="p1",
                status=BootstrapStatus.PENDING, workspace_count=-1,
                created_at=_NOW,
            )

    def test_metadata_frozen(self):
        b = TenantBootstrap(
            bootstrap_id="b1", tenant_id="t1", pack_ref="p1",
            status=BootstrapStatus.PENDING, created_at=_NOW,
            metadata={"key": "val"},
        )
        assert isinstance(b.metadata, MappingProxyType)

    def test_serialization(self):
        b = TenantBootstrap(
            bootstrap_id="b1", tenant_id="t1", pack_ref="p1",
            status=BootstrapStatus.PENDING, created_at=_NOW,
        )
        d = b.to_json_dict()
        assert d["status"] == "pending"
        assert isinstance(b.to_json(), str)

    def test_immutability(self):
        b = TenantBootstrap(
            bootstrap_id="b1", tenant_id="t1", pack_ref="p1",
            status=BootstrapStatus.PENDING, created_at=_NOW,
        )
        with pytest.raises(AttributeError):
            b.status = BootstrapStatus.COMPLETED  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ConnectorActivation
# ---------------------------------------------------------------------------


class TestConnectorActivation:
    def test_valid(self):
        c = ConnectorActivation(
            activation_id="a1", tenant_id="t1", connector_type="http",
            target_url="https://x.com",
            status=ConnectorActivationStatus.ACTIVATING,
            health_check_passed=False, activated_at=_NOW,
        )
        assert c.activation_id == "a1"
        assert c.health_check_passed is False

    def test_health_check_non_bool_rejected(self):
        with pytest.raises(ValueError):
            ConnectorActivation(
                activation_id="a1", tenant_id="t1", connector_type="http",
                target_url="https://x.com",
                status=ConnectorActivationStatus.ACTIVE,
                health_check_passed=1, activated_at=_NOW,
            )

    def test_empty_target_url_rejected(self):
        with pytest.raises(ValueError):
            ConnectorActivation(
                activation_id="a1", tenant_id="t1", connector_type="http",
                target_url="",
                status=ConnectorActivationStatus.ACTIVE,
                health_check_passed=True, activated_at=_NOW,
            )

    def test_serialization(self):
        c = ConnectorActivation(
            activation_id="a1", tenant_id="t1", connector_type="http",
            target_url="https://x.com",
            status=ConnectorActivationStatus.ACTIVE,
            health_check_passed=True, activated_at=_NOW,
        )
        d = c.to_json_dict()
        assert d["status"] == "active"
        assert d["health_check_passed"] is True


# ---------------------------------------------------------------------------
# DataMigration
# ---------------------------------------------------------------------------


class TestDataMigration:
    def test_valid(self):
        m = DataMigration(
            migration_id="m1", tenant_id="t1", source_system="legacy",
            record_count=100, imported_count=0, failed_count=0,
            status=MigrationStatus.PENDING, created_at=_NOW,
        )
        assert m.record_count == 100

    def test_negative_record_count_rejected(self):
        with pytest.raises(ValueError):
            DataMigration(
                migration_id="m1", tenant_id="t1", source_system="legacy",
                record_count=-1, status=MigrationStatus.PENDING, created_at=_NOW,
            )

    def test_serialization(self):
        m = DataMigration(
            migration_id="m1", tenant_id="t1", source_system="legacy",
            record_count=50, status=MigrationStatus.IMPORTING, created_at=_NOW,
        )
        d = m.to_json_dict()
        assert d["status"] == "importing"


# ---------------------------------------------------------------------------
# PilotRecord
# ---------------------------------------------------------------------------


class TestPilotRecord:
    def test_valid(self):
        p = PilotRecord(
            pilot_id="p1", tenant_id="t1", pack_ref="pk1",
            phase=PilotPhase.SETUP, started_at=_NOW,
        )
        assert p.phase == PilotPhase.SETUP

    def test_empty_pilot_id_rejected(self):
        with pytest.raises(ValueError):
            PilotRecord(
                pilot_id="", tenant_id="t1", pack_ref="pk1",
                phase=PilotPhase.SETUP, started_at=_NOW,
            )

    def test_invalid_phase_rejected(self):
        with pytest.raises(ValueError):
            PilotRecord(
                pilot_id="p1", tenant_id="t1", pack_ref="pk1",
                phase="setup", started_at=_NOW,
            )


# ---------------------------------------------------------------------------
# GoLiveChecklist
# ---------------------------------------------------------------------------


class TestGoLiveChecklist:
    def test_valid(self):
        gl = GoLiveChecklist(
            checklist_id="cl1", tenant_id="t1", pilot_ref="p1",
            total_items=5, passed_items=3,
            readiness=GoLiveReadiness.PARTIAL, assessed_at=_NOW,
        )
        assert gl.readiness == GoLiveReadiness.PARTIAL

    def test_negative_items_rejected(self):
        with pytest.raises(ValueError):
            GoLiveChecklist(
                checklist_id="cl1", tenant_id="t1", pilot_ref="p1",
                total_items=-1, readiness=GoLiveReadiness.NOT_READY,
                assessed_at=_NOW,
            )


# ---------------------------------------------------------------------------
# RunbookEntry
# ---------------------------------------------------------------------------


class TestRunbookEntry:
    def test_valid(self):
        rb = RunbookEntry(
            entry_id="rb1", tenant_id="t1", title="Restart",
            category="ops", procedure="Step 1", created_at=_NOW,
        )
        assert rb.title == "Restart"

    def test_empty_procedure_rejected(self):
        with pytest.raises(ValueError):
            RunbookEntry(
                entry_id="rb1", tenant_id="t1", title="Restart",
                category="ops", procedure="", created_at=_NOW,
            )


# ---------------------------------------------------------------------------
# SloDefinition
# ---------------------------------------------------------------------------


class TestSloDefinition:
    def test_valid(self):
        slo = SloDefinition(
            slo_id="s1", tenant_id="t1", metric_name="uptime",
            target_value=99.9, current_value=99.5, unit="percent",
            created_at=_NOW,
        )
        assert slo.target_value == 99.9

    def test_negative_target_rejected(self):
        with pytest.raises(ValueError):
            SloDefinition(
                slo_id="s1", tenant_id="t1", metric_name="uptime",
                target_value=-1.0, current_value=0.0, unit="percent",
                created_at=_NOW,
            )


# ---------------------------------------------------------------------------
# PilotAssessment
# ---------------------------------------------------------------------------


class TestPilotAssessment:
    def test_valid(self):
        pa = PilotAssessment(
            assessment_id="pa1", tenant_id="t1", pilot_ref="p1",
            total_connectors=5, active_connectors=3,
            migration_completeness=0.8, readiness_score=0.7,
            assessed_at=_NOW,
        )
        assert pa.readiness_score == 0.7

    def test_migration_completeness_over_1_rejected(self):
        with pytest.raises(ValueError):
            PilotAssessment(
                assessment_id="pa1", tenant_id="t1", pilot_ref="p1",
                total_connectors=5, active_connectors=3,
                migration_completeness=1.5, readiness_score=0.7,
                assessed_at=_NOW,
            )

    def test_readiness_score_negative_rejected(self):
        with pytest.raises(ValueError):
            PilotAssessment(
                assessment_id="pa1", tenant_id="t1", pilot_ref="p1",
                total_connectors=5, active_connectors=3,
                migration_completeness=0.5, readiness_score=-0.1,
                assessed_at=_NOW,
            )


# ---------------------------------------------------------------------------
# PilotViolation
# ---------------------------------------------------------------------------


class TestPilotViolation:
    def test_valid(self):
        pv = PilotViolation(
            violation_id="v1", tenant_id="t1",
            operation="connector_activation",
            reason="failed in live pilot", detected_at=_NOW,
        )
        assert pv.operation == "connector_activation"

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            PilotViolation(
                violation_id="v1", tenant_id="t1",
                operation="op", reason="", detected_at=_NOW,
            )


# ---------------------------------------------------------------------------
# PilotClosureReport
# ---------------------------------------------------------------------------


class TestPilotClosureReport:
    def test_valid(self):
        pcr = PilotClosureReport(
            report_id="r1", tenant_id="t1",
            total_bootstraps=1, total_connectors=3,
            total_migrations=2, total_violations=1,
            created_at=_NOW,
        )
        assert pcr.total_bootstraps == 1

    def test_negative_total_rejected(self):
        with pytest.raises(ValueError):
            PilotClosureReport(
                report_id="r1", tenant_id="t1",
                total_bootstraps=-1, created_at=_NOW,
            )

    def test_serialization(self):
        pcr = PilotClosureReport(
            report_id="r1", tenant_id="t1",
            total_bootstraps=1, total_connectors=3,
            total_migrations=2, total_violations=0,
            created_at=_NOW,
        )
        j = pcr.to_json()
        assert '"report_id":"r1"' in j
