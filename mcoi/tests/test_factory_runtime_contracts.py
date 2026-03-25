"""Comprehensive tests for factory runtime contracts.

Tests cover: enum membership, dataclass construction, validation failures,
frozen immutability, metadata freezing, and to_dict() serialization.
"""

from __future__ import annotations

import dataclasses
import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.factory_runtime import *


# ===================================================================
# Helpers: valid kwargs for each dataclass
# ===================================================================


def _plant_kw(**overrides):
    base = dict(
        plant_id="p-1", tenant_id="t-1", display_name="Plant Alpha",
        status=FactoryStatus.ACTIVE, line_count=3,
        created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _line_kw(**overrides):
    base = dict(
        line_id="l-1", tenant_id="t-1", plant_id="p-1",
        display_name="Line A", station_count=5,
        created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _station_kw(**overrides):
    base = dict(
        station_id="s-1", tenant_id="t-1", line_id="l-1",
        display_name="Station 1", machine_ref="m-1",
        created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _work_order_kw(**overrides):
    base = dict(
        order_id="wo-1", tenant_id="t-1", plant_id="p-1",
        product_ref="prod-1", status=WorkOrderStatus.DRAFT,
        quantity=100, created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _batch_kw(**overrides):
    base = dict(
        batch_id="b-1", tenant_id="t-1", order_id="wo-1",
        status=BatchStatus.PLANNED, unit_count=50,
        yield_rate=0.95, created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _machine_kw(**overrides):
    base = dict(
        machine_id="m-1", tenant_id="t-1", station_ref="s-1",
        display_name="CNC Lathe", status=MachineStatus.OPERATIONAL,
        uptime_hours=1200, created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _quality_check_kw(**overrides):
    base = dict(
        check_id="qc-1", tenant_id="t-1", batch_id="b-1",
        verdict=QualityVerdict.PASS, defect_count=0,
        inspector_ref="insp-1", checked_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _downtime_event_kw(**overrides):
    base = dict(
        event_id="dt-1", tenant_id="t-1", machine_id="m-1",
        reason="Belt failure", duration_minutes=45,
        disposition=MaintenanceDisposition.UNSCHEDULED,
        recorded_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _snapshot_kw(**overrides):
    base = dict(
        snapshot_id="snap-1", tenant_id="t-1",
        total_plants=5, total_lines=20, total_orders=100,
        total_batches=200, total_checks=150,
        total_downtime_events=10, total_violations=2,
        captured_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


def _closure_report_kw(**overrides):
    base = dict(
        report_id="rpt-1", tenant_id="t-1",
        total_plants=5, total_orders=100,
        total_batches=200, total_checks=150, total_violations=2,
        created_at="2025-06-01T00:00:00", metadata={},
    )
    base.update(overrides)
    return base


# ===================================================================
# Enum tests
# ===================================================================


class TestFactoryStatusEnum:
    def test_members(self):
        assert set(FactoryStatus) == {
            FactoryStatus.ACTIVE, FactoryStatus.IDLE,
            FactoryStatus.MAINTENANCE, FactoryStatus.SHUTDOWN,
        }

    @pytest.mark.parametrize("member,value", [
        (FactoryStatus.ACTIVE, "active"),
        (FactoryStatus.IDLE, "idle"),
        (FactoryStatus.MAINTENANCE, "maintenance"),
        (FactoryStatus.SHUTDOWN, "shutdown"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(FactoryStatus) == 4


class TestWorkOrderStatusEnum:
    def test_members(self):
        assert set(WorkOrderStatus) == {
            WorkOrderStatus.DRAFT, WorkOrderStatus.RELEASED,
            WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED,
            WorkOrderStatus.CANCELLED,
        }

    @pytest.mark.parametrize("member,value", [
        (WorkOrderStatus.DRAFT, "draft"),
        (WorkOrderStatus.RELEASED, "released"),
        (WorkOrderStatus.IN_PROGRESS, "in_progress"),
        (WorkOrderStatus.COMPLETED, "completed"),
        (WorkOrderStatus.CANCELLED, "cancelled"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(WorkOrderStatus) == 5


class TestMachineStatusEnum:
    def test_members(self):
        assert set(MachineStatus) == {
            MachineStatus.OPERATIONAL, MachineStatus.DEGRADED,
            MachineStatus.DOWN, MachineStatus.MAINTENANCE,
            MachineStatus.DECOMMISSIONED,
        }

    @pytest.mark.parametrize("member,value", [
        (MachineStatus.OPERATIONAL, "operational"),
        (MachineStatus.DEGRADED, "degraded"),
        (MachineStatus.DOWN, "down"),
        (MachineStatus.MAINTENANCE, "maintenance"),
        (MachineStatus.DECOMMISSIONED, "decommissioned"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(MachineStatus) == 5


class TestBatchStatusEnum:
    def test_members(self):
        assert set(BatchStatus) == {
            BatchStatus.PLANNED, BatchStatus.IN_PROGRESS,
            BatchStatus.COMPLETED, BatchStatus.REJECTED,
            BatchStatus.SCRAPPED,
        }

    @pytest.mark.parametrize("member,value", [
        (BatchStatus.PLANNED, "planned"),
        (BatchStatus.IN_PROGRESS, "in_progress"),
        (BatchStatus.COMPLETED, "completed"),
        (BatchStatus.REJECTED, "rejected"),
        (BatchStatus.SCRAPPED, "scrapped"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(BatchStatus) == 5


class TestQualityVerdictEnum:
    def test_members(self):
        assert set(QualityVerdict) == {
            QualityVerdict.PASS, QualityVerdict.FAIL,
            QualityVerdict.CONDITIONAL, QualityVerdict.NOT_TESTED,
        }

    @pytest.mark.parametrize("member,value", [
        (QualityVerdict.PASS, "pass"),
        (QualityVerdict.FAIL, "fail"),
        (QualityVerdict.CONDITIONAL, "conditional"),
        (QualityVerdict.NOT_TESTED, "not_tested"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(QualityVerdict) == 4


class TestMaintenanceDispositionEnum:
    def test_members(self):
        assert set(MaintenanceDisposition) == {
            MaintenanceDisposition.SCHEDULED,
            MaintenanceDisposition.UNSCHEDULED,
            MaintenanceDisposition.EMERGENCY,
            MaintenanceDisposition.COMPLETED,
        }

    @pytest.mark.parametrize("member,value", [
        (MaintenanceDisposition.SCHEDULED, "scheduled"),
        (MaintenanceDisposition.UNSCHEDULED, "unscheduled"),
        (MaintenanceDisposition.EMERGENCY, "emergency"),
        (MaintenanceDisposition.COMPLETED, "completed"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(MaintenanceDisposition) == 4


# ===================================================================
# PlantRecord tests
# ===================================================================


class TestPlantRecord:
    def test_valid_construction(self):
        r = PlantRecord(**_plant_kw())
        assert r.plant_id == "p-1"
        assert r.tenant_id == "t-1"
        assert r.display_name == "Plant Alpha"
        assert r.status is FactoryStatus.ACTIVE
        assert r.line_count == 3

    def test_frozen(self):
        r = PlantRecord(**_plant_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.plant_id = "x"

    def test_metadata_frozen_to_mapping_proxy(self):
        r = PlantRecord(**_plant_kw(metadata={"k": "v"}))
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["k"] == "v"
        with pytest.raises(TypeError):
            r.metadata["k2"] = "v2"

    def test_to_dict_metadata_plain(self):
        r = PlantRecord(**_plant_kw(metadata={"a": 1}))
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"] == {"a": 1}

    def test_to_dict_keys(self):
        d = PlantRecord(**_plant_kw()).to_dict()
        expected = {"plant_id", "tenant_id", "display_name", "status",
                    "line_count", "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "plant_id", "tenant_id", "display_name",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "plant_id", "tenant_id", "display_name",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(**{field_name: "   "}))

    @pytest.mark.parametrize("bad", [-1, -100])
    def test_line_count_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(line_count=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_line_count_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(line_count=bad))

    @pytest.mark.parametrize("bad", [1.0, 2.5])
    def test_line_count_float_rejected(self, bad):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(line_count=bad))

    def test_line_count_zero_accepted(self):
        r = PlantRecord(**_plant_kw(line_count=0))
        assert r.line_count == 0

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(status="active"))

    @pytest.mark.parametrize("member", list(FactoryStatus))
    def test_all_status_members_accepted(self, member):
        r = PlantRecord(**_plant_kw(status=member))
        assert r.status is member

    def test_created_at_date_only_accepted(self):
        r = PlantRecord(**_plant_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_with_timezone(self):
        r = PlantRecord(**_plant_kw(created_at="2025-06-01T12:00:00Z"))
        assert r.created_at == "2025-06-01T12:00:00Z"

    def test_created_at_invalid_rejected(self):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(created_at="not-a-date"))

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            PlantRecord(**_plant_kw(created_at=""))

    def test_nested_metadata_frozen(self):
        r = PlantRecord(**_plant_kw(metadata={"inner": {"a": 1}}))
        assert isinstance(r.metadata["inner"], MappingProxyType)

    def test_to_dict_nested_metadata_thawed(self):
        r = PlantRecord(**_plant_kw(metadata={"inner": {"a": 1}}))
        d = r.to_dict()
        assert isinstance(d["metadata"]["inner"], dict)


# ===================================================================
# LineRecord tests
# ===================================================================


class TestLineRecord:
    def test_valid_construction(self):
        r = LineRecord(**_line_kw())
        assert r.line_id == "l-1"
        assert r.tenant_id == "t-1"
        assert r.plant_id == "p-1"
        assert r.display_name == "Line A"
        assert r.station_count == 5

    def test_frozen(self):
        r = LineRecord(**_line_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.line_id = "x"

    def test_metadata_frozen(self):
        r = LineRecord(**_line_kw(metadata={"x": 1}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        r = LineRecord(**_line_kw(metadata={"x": 1}))
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_keys(self):
        d = LineRecord(**_line_kw()).to_dict()
        expected = {"line_id", "tenant_id", "plant_id", "display_name",
                    "station_count", "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "line_id", "tenant_id", "plant_id", "display_name",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            LineRecord(**_line_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "line_id", "tenant_id", "plant_id", "display_name",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            LineRecord(**_line_kw(**{field_name: "\t\n"}))

    @pytest.mark.parametrize("bad", [-1, -99])
    def test_station_count_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            LineRecord(**_line_kw(station_count=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_station_count_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            LineRecord(**_line_kw(station_count=bad))

    @pytest.mark.parametrize("bad", [1.5, 0.0])
    def test_station_count_float_rejected(self, bad):
        with pytest.raises(ValueError):
            LineRecord(**_line_kw(station_count=bad))

    def test_station_count_zero(self):
        r = LineRecord(**_line_kw(station_count=0))
        assert r.station_count == 0

    def test_created_at_date_only(self):
        r = LineRecord(**_line_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            LineRecord(**_line_kw(created_at="xyz"))


# ===================================================================
# StationRecord tests
# ===================================================================


class TestStationRecord:
    def test_valid_construction(self):
        r = StationRecord(**_station_kw())
        assert r.station_id == "s-1"
        assert r.tenant_id == "t-1"
        assert r.line_id == "l-1"
        assert r.display_name == "Station 1"
        assert r.machine_ref == "m-1"

    def test_frozen(self):
        r = StationRecord(**_station_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.station_id = "x"

    def test_metadata_frozen(self):
        r = StationRecord(**_station_kw(metadata={"z": 9}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = StationRecord(**_station_kw()).to_dict()
        expected = {"station_id", "tenant_id", "line_id", "display_name",
                    "machine_ref", "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "station_id", "tenant_id", "line_id", "display_name", "machine_ref",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            StationRecord(**_station_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "station_id", "tenant_id", "line_id", "display_name", "machine_ref",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            StationRecord(**_station_kw(**{field_name: "   "}))

    def test_created_at_date_only(self):
        r = StationRecord(**_station_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            StationRecord(**_station_kw(created_at="nope"))

    def test_to_dict_metadata_thawed(self):
        r = StationRecord(**_station_kw(metadata={"a": [1, 2]}))
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# WorkOrder tests
# ===================================================================


class TestWorkOrder:
    def test_valid_construction(self):
        r = WorkOrder(**_work_order_kw())
        assert r.order_id == "wo-1"
        assert r.tenant_id == "t-1"
        assert r.plant_id == "p-1"
        assert r.product_ref == "prod-1"
        assert r.status is WorkOrderStatus.DRAFT
        assert r.quantity == 100

    def test_frozen(self):
        r = WorkOrder(**_work_order_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.order_id = "x"

    def test_metadata_frozen(self):
        r = WorkOrder(**_work_order_kw(metadata={"q": 1}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = WorkOrder(**_work_order_kw()).to_dict()
        expected = {"order_id", "tenant_id", "plant_id", "product_ref",
                    "status", "quantity", "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "order_id", "tenant_id", "plant_id", "product_ref",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "order_id", "tenant_id", "plant_id", "product_ref",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(**{field_name: " \t "}))

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(status="draft"))

    @pytest.mark.parametrize("member", list(WorkOrderStatus))
    def test_all_status_members_accepted(self, member):
        r = WorkOrder(**_work_order_kw(status=member))
        assert r.status is member

    @pytest.mark.parametrize("bad", [-1, -50])
    def test_quantity_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(quantity=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_quantity_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(quantity=bad))

    @pytest.mark.parametrize("bad", [1.0, 99.9])
    def test_quantity_float_rejected(self, bad):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(quantity=bad))

    def test_quantity_zero(self):
        r = WorkOrder(**_work_order_kw(quantity=0))
        assert r.quantity == 0

    def test_created_at_date_only(self):
        r = WorkOrder(**_work_order_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(created_at="bad"))

    def test_status_wrong_enum_type_rejected(self):
        with pytest.raises(ValueError):
            WorkOrder(**_work_order_kw(status=FactoryStatus.ACTIVE))


# ===================================================================
# BatchRecord tests
# ===================================================================


class TestBatchRecord:
    def test_valid_construction(self):
        r = BatchRecord(**_batch_kw())
        assert r.batch_id == "b-1"
        assert r.tenant_id == "t-1"
        assert r.order_id == "wo-1"
        assert r.status is BatchStatus.PLANNED
        assert r.unit_count == 50
        assert r.yield_rate == 0.95

    def test_frozen(self):
        r = BatchRecord(**_batch_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.batch_id = "x"

    def test_metadata_frozen(self):
        r = BatchRecord(**_batch_kw(metadata={"r": 2}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = BatchRecord(**_batch_kw()).to_dict()
        expected = {"batch_id", "tenant_id", "order_id", "status",
                    "unit_count", "yield_rate", "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "batch_id", "tenant_id", "order_id",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "batch_id", "tenant_id", "order_id",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(**{field_name: "  "}))

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(status="planned"))

    @pytest.mark.parametrize("member", list(BatchStatus))
    def test_all_status_members_accepted(self, member):
        r = BatchRecord(**_batch_kw(status=member))
        assert r.status is member

    @pytest.mark.parametrize("bad", [-1, -10])
    def test_unit_count_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(unit_count=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_unit_count_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(unit_count=bad))

    @pytest.mark.parametrize("bad", [1.0, 5.5])
    def test_unit_count_float_rejected(self, bad):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(unit_count=bad))

    def test_unit_count_zero(self):
        r = BatchRecord(**_batch_kw(unit_count=0))
        assert r.unit_count == 0

    # -- yield_rate (unit float) tests --

    def test_yield_rate_zero(self):
        r = BatchRecord(**_batch_kw(yield_rate=0.0))
        assert r.yield_rate == 0.0

    def test_yield_rate_one(self):
        r = BatchRecord(**_batch_kw(yield_rate=1.0))
        assert r.yield_rate == 1.0

    def test_yield_rate_midpoint(self):
        r = BatchRecord(**_batch_kw(yield_rate=0.5))
        assert r.yield_rate == 0.5

    @pytest.mark.parametrize("bad", [-0.01, -1.0])
    def test_yield_rate_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=bad))

    @pytest.mark.parametrize("bad", [1.01, 2.0, 100.0])
    def test_yield_rate_above_one_rejected(self, bad):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=bad))

    def test_yield_rate_nan_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=float("nan")))

    def test_yield_rate_inf_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=float("inf")))

    def test_yield_rate_neg_inf_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=float("-inf")))

    def test_yield_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=True))

    def test_yield_rate_string_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate="0.5"))

    def test_yield_rate_int_zero_accepted(self):
        r = BatchRecord(**_batch_kw(yield_rate=0))
        assert r.yield_rate == 0.0

    def test_yield_rate_int_one_accepted(self):
        r = BatchRecord(**_batch_kw(yield_rate=1))
        assert r.yield_rate == 1.0

    def test_created_at_date_only(self):
        r = BatchRecord(**_batch_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(created_at="nah"))

    def test_status_wrong_enum_type_rejected(self):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(status=WorkOrderStatus.DRAFT))


# ===================================================================
# MachineRecord tests
# ===================================================================


class TestMachineRecord:
    def test_valid_construction(self):
        r = MachineRecord(**_machine_kw())
        assert r.machine_id == "m-1"
        assert r.tenant_id == "t-1"
        assert r.station_ref == "s-1"
        assert r.display_name == "CNC Lathe"
        assert r.status is MachineStatus.OPERATIONAL
        assert r.uptime_hours == 1200

    def test_frozen(self):
        r = MachineRecord(**_machine_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.machine_id = "x"

    def test_metadata_frozen(self):
        r = MachineRecord(**_machine_kw(metadata={"fw": "v2"}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = MachineRecord(**_machine_kw()).to_dict()
        expected = {"machine_id", "tenant_id", "station_ref", "display_name",
                    "status", "uptime_hours", "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "machine_id", "tenant_id", "station_ref", "display_name",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "machine_id", "tenant_id", "station_ref", "display_name",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(**{field_name: "\n\t"}))

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(status="operational"))

    @pytest.mark.parametrize("member", list(MachineStatus))
    def test_all_status_members_accepted(self, member):
        r = MachineRecord(**_machine_kw(status=member))
        assert r.status is member

    @pytest.mark.parametrize("bad", [-1, -500])
    def test_uptime_hours_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(uptime_hours=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_uptime_hours_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(uptime_hours=bad))

    @pytest.mark.parametrize("bad", [1.0, 0.5])
    def test_uptime_hours_float_rejected(self, bad):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(uptime_hours=bad))

    def test_uptime_hours_zero(self):
        r = MachineRecord(**_machine_kw(uptime_hours=0))
        assert r.uptime_hours == 0

    def test_created_at_date_only(self):
        r = MachineRecord(**_machine_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(created_at="bad-date"))

    def test_status_wrong_enum_type_rejected(self):
        with pytest.raises(ValueError):
            MachineRecord(**_machine_kw(status=FactoryStatus.MAINTENANCE))


# ===================================================================
# QualityCheck tests
# ===================================================================


class TestQualityCheck:
    def test_valid_construction(self):
        r = QualityCheck(**_quality_check_kw())
        assert r.check_id == "qc-1"
        assert r.tenant_id == "t-1"
        assert r.batch_id == "b-1"
        assert r.verdict is QualityVerdict.PASS
        assert r.defect_count == 0
        assert r.inspector_ref == "insp-1"

    def test_frozen(self):
        r = QualityCheck(**_quality_check_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.check_id = "x"

    def test_metadata_frozen(self):
        r = QualityCheck(**_quality_check_kw(metadata={"t": 3}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = QualityCheck(**_quality_check_kw()).to_dict()
        expected = {"check_id", "tenant_id", "batch_id", "verdict",
                    "defect_count", "inspector_ref", "checked_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "check_id", "tenant_id", "batch_id", "inspector_ref",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "check_id", "tenant_id", "batch_id", "inspector_ref",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(**{field_name: "   "}))

    def test_verdict_string_rejected(self):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(verdict="pass"))

    @pytest.mark.parametrize("member", list(QualityVerdict))
    def test_all_verdict_members_accepted(self, member):
        r = QualityCheck(**_quality_check_kw(verdict=member))
        assert r.verdict is member

    @pytest.mark.parametrize("bad", [-1, -10])
    def test_defect_count_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(defect_count=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_defect_count_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(defect_count=bad))

    @pytest.mark.parametrize("bad", [1.0, 3.3])
    def test_defect_count_float_rejected(self, bad):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(defect_count=bad))

    def test_defect_count_zero(self):
        r = QualityCheck(**_quality_check_kw(defect_count=0))
        assert r.defect_count == 0

    def test_defect_count_positive(self):
        r = QualityCheck(**_quality_check_kw(defect_count=42))
        assert r.defect_count == 42

    def test_checked_at_date_only(self):
        r = QualityCheck(**_quality_check_kw(checked_at="2025-06-01"))
        assert r.checked_at == "2025-06-01"

    def test_checked_at_invalid(self):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(checked_at="invalid"))

    def test_verdict_wrong_enum_type_rejected(self):
        with pytest.raises(ValueError):
            QualityCheck(**_quality_check_kw(verdict=BatchStatus.COMPLETED))


# ===================================================================
# DowntimeEvent tests
# ===================================================================


class TestDowntimeEvent:
    def test_valid_construction(self):
        r = DowntimeEvent(**_downtime_event_kw())
        assert r.event_id == "dt-1"
        assert r.tenant_id == "t-1"
        assert r.machine_id == "m-1"
        assert r.reason == "Belt failure"
        assert r.duration_minutes == 45
        assert r.disposition is MaintenanceDisposition.UNSCHEDULED

    def test_frozen(self):
        r = DowntimeEvent(**_downtime_event_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.event_id = "x"

    def test_metadata_frozen(self):
        r = DowntimeEvent(**_downtime_event_kw(metadata={"sev": "high"}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = DowntimeEvent(**_downtime_event_kw()).to_dict()
        expected = {"event_id", "tenant_id", "machine_id", "reason",
                    "duration_minutes", "disposition", "recorded_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", [
        "event_id", "tenant_id", "machine_id", "reason",
    ])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", [
        "event_id", "tenant_id", "machine_id", "reason",
    ])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(**{field_name: " \t\n "}))

    def test_disposition_string_rejected(self):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(disposition="unscheduled"))

    @pytest.mark.parametrize("member", list(MaintenanceDisposition))
    def test_all_disposition_members_accepted(self, member):
        r = DowntimeEvent(**_downtime_event_kw(disposition=member))
        assert r.disposition is member

    @pytest.mark.parametrize("bad", [-1, -60])
    def test_duration_minutes_negative_rejected(self, bad):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(duration_minutes=bad))

    @pytest.mark.parametrize("bad", [True, False])
    def test_duration_minutes_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(duration_minutes=bad))

    @pytest.mark.parametrize("bad", [1.0, 30.5])
    def test_duration_minutes_float_rejected(self, bad):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(duration_minutes=bad))

    def test_duration_minutes_zero(self):
        r = DowntimeEvent(**_downtime_event_kw(duration_minutes=0))
        assert r.duration_minutes == 0

    def test_recorded_at_date_only(self):
        r = DowntimeEvent(**_downtime_event_kw(recorded_at="2025-06-01"))
        assert r.recorded_at == "2025-06-01"

    def test_recorded_at_invalid(self):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(recorded_at="nope"))

    def test_disposition_wrong_enum_type_rejected(self):
        with pytest.raises(ValueError):
            DowntimeEvent(**_downtime_event_kw(disposition=FactoryStatus.ACTIVE))


# ===================================================================
# FactorySnapshot tests
# ===================================================================


class TestFactorySnapshot:
    def test_valid_construction(self):
        r = FactorySnapshot(**_snapshot_kw())
        assert r.snapshot_id == "snap-1"
        assert r.tenant_id == "t-1"
        assert r.total_plants == 5
        assert r.total_lines == 20
        assert r.total_orders == 100
        assert r.total_batches == 200
        assert r.total_checks == 150
        assert r.total_downtime_events == 10
        assert r.total_violations == 2

    def test_frozen(self):
        r = FactorySnapshot(**_snapshot_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.snapshot_id = "x"

    def test_metadata_frozen(self):
        r = FactorySnapshot(**_snapshot_kw(metadata={"v": 1}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = FactorySnapshot(**_snapshot_kw()).to_dict()
        expected = {"snapshot_id", "tenant_id", "total_plants", "total_lines",
                    "total_orders", "total_batches", "total_checks",
                    "total_downtime_events", "total_violations",
                    "captured_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            FactorySnapshot(**_snapshot_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            FactorySnapshot(**_snapshot_kw(**{field_name: "   "}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_lines", "total_orders", "total_batches",
        "total_checks", "total_downtime_events", "total_violations",
    ])
    def test_int_field_negative_rejected(self, int_field):
        with pytest.raises(ValueError):
            FactorySnapshot(**_snapshot_kw(**{int_field: -1}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_lines", "total_orders", "total_batches",
        "total_checks", "total_downtime_events", "total_violations",
    ])
    def test_int_field_bool_rejected(self, int_field):
        with pytest.raises(ValueError):
            FactorySnapshot(**_snapshot_kw(**{int_field: True}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_lines", "total_orders", "total_batches",
        "total_checks", "total_downtime_events", "total_violations",
    ])
    def test_int_field_float_rejected(self, int_field):
        with pytest.raises(ValueError):
            FactorySnapshot(**_snapshot_kw(**{int_field: 1.0}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_lines", "total_orders", "total_batches",
        "total_checks", "total_downtime_events", "total_violations",
    ])
    def test_int_field_zero_accepted(self, int_field):
        r = FactorySnapshot(**_snapshot_kw(**{int_field: 0}))
        assert getattr(r, int_field) == 0

    def test_captured_at_date_only(self):
        r = FactorySnapshot(**_snapshot_kw(captured_at="2025-06-01"))
        assert r.captured_at == "2025-06-01"

    def test_captured_at_invalid(self):
        with pytest.raises(ValueError):
            FactorySnapshot(**_snapshot_kw(captured_at="xxx"))

    def test_captured_at_with_tz(self):
        r = FactorySnapshot(**_snapshot_kw(captured_at="2025-06-01T12:00:00+05:30"))
        assert r.captured_at == "2025-06-01T12:00:00+05:30"

    def test_to_dict_metadata_thawed(self):
        r = FactorySnapshot(**_snapshot_kw(metadata={"nested": {"a": 1}}))
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["nested"], dict)


# ===================================================================
# FactoryClosureReport tests
# ===================================================================


class TestFactoryClosureReport:
    def test_valid_construction(self):
        r = FactoryClosureReport(**_closure_report_kw())
        assert r.report_id == "rpt-1"
        assert r.tenant_id == "t-1"
        assert r.total_plants == 5
        assert r.total_orders == 100
        assert r.total_batches == 200
        assert r.total_checks == 150
        assert r.total_violations == 2

    def test_frozen(self):
        r = FactoryClosureReport(**_closure_report_kw())
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "x"

    def test_metadata_frozen(self):
        r = FactoryClosureReport(**_closure_report_kw(metadata={"x": 0}))
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_keys(self):
        d = FactoryClosureReport(**_closure_report_kw()).to_dict()
        expected = {"report_id", "tenant_id", "total_plants", "total_orders",
                    "total_batches", "total_checks", "total_violations",
                    "created_at", "metadata"}
        assert set(d.keys()) == expected

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            FactoryClosureReport(**_closure_report_kw(**{field_name: ""}))

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field_name):
        with pytest.raises(ValueError):
            FactoryClosureReport(**_closure_report_kw(**{field_name: "  "}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_orders", "total_batches",
        "total_checks", "total_violations",
    ])
    def test_int_field_negative_rejected(self, int_field):
        with pytest.raises(ValueError):
            FactoryClosureReport(**_closure_report_kw(**{int_field: -1}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_orders", "total_batches",
        "total_checks", "total_violations",
    ])
    def test_int_field_bool_rejected(self, int_field):
        with pytest.raises(ValueError):
            FactoryClosureReport(**_closure_report_kw(**{int_field: False}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_orders", "total_batches",
        "total_checks", "total_violations",
    ])
    def test_int_field_float_rejected(self, int_field):
        with pytest.raises(ValueError):
            FactoryClosureReport(**_closure_report_kw(**{int_field: 2.0}))

    @pytest.mark.parametrize("int_field", [
        "total_plants", "total_orders", "total_batches",
        "total_checks", "total_violations",
    ])
    def test_int_field_zero_accepted(self, int_field):
        r = FactoryClosureReport(**_closure_report_kw(**{int_field: 0}))
        assert getattr(r, int_field) == 0

    def test_created_at_date_only(self):
        r = FactoryClosureReport(**_closure_report_kw(created_at="2025-06-01"))
        assert r.created_at == "2025-06-01"

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            FactoryClosureReport(**_closure_report_kw(created_at="nope"))

    def test_to_dict_metadata_thawed(self):
        r = FactoryClosureReport(**_closure_report_kw(metadata={"n": {"v": 1}}))
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["n"], dict)


# ===================================================================
# Cross-cutting / parametrized tests
# ===================================================================

_ALL_FACTORIES = [
    ("PlantRecord", _plant_kw),
    ("LineRecord", _line_kw),
    ("StationRecord", _station_kw),
    ("WorkOrder", _work_order_kw),
    ("BatchRecord", _batch_kw),
    ("MachineRecord", _machine_kw),
    ("QualityCheck", _quality_check_kw),
    ("DowntimeEvent", _downtime_event_kw),
    ("FactorySnapshot", _snapshot_kw),
    ("FactoryClosureReport", _closure_report_kw),
]

_CLASSES = {
    "PlantRecord": PlantRecord,
    "LineRecord": LineRecord,
    "StationRecord": StationRecord,
    "WorkOrder": WorkOrder,
    "BatchRecord": BatchRecord,
    "MachineRecord": MachineRecord,
    "QualityCheck": QualityCheck,
    "DowntimeEvent": DowntimeEvent,
    "FactorySnapshot": FactorySnapshot,
    "FactoryClosureReport": FactoryClosureReport,
}


class TestCrossCutting:
    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_is_frozen_dataclass(self, name, factory):
        cls = _CLASSES[name]
        assert dataclasses.is_dataclass(cls)
        obj = cls(**factory())
        first_field = dataclasses.fields(obj)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, first_field, "CHANGED")

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_has_slots(self, name, factory):
        cls = _CLASSES[name]
        assert hasattr(cls, "__slots__")

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_to_dict_returns_dict(self, name, factory):
        obj = _CLASSES[name](**factory())
        d = obj.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_to_dict_metadata_is_plain_dict(self, name, factory):
        obj = _CLASSES[name](**factory(metadata={"k": "v"}))
        d = obj.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_metadata_input_dict_is_frozen(self, name, factory):
        obj = _CLASSES[name](**factory(metadata={"k": "v"}))
        assert isinstance(obj.metadata, MappingProxyType)

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_metadata_empty_dict(self, name, factory):
        obj = _CLASSES[name](**factory(metadata={}))
        assert isinstance(obj.metadata, MappingProxyType)
        assert len(obj.metadata) == 0

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_metadata_mutation_raises(self, name, factory):
        obj = _CLASSES[name](**factory(metadata={"a": 1}))
        with pytest.raises(TypeError):
            obj.metadata["b"] = 2

    @pytest.mark.parametrize("name,factory", _ALL_FACTORIES, ids=[n for n, _ in _ALL_FACTORIES])
    def test_to_dict_field_count_matches(self, name, factory):
        cls = _CLASSES[name]
        obj = cls(**factory())
        d = obj.to_dict()
        assert len(d) == len(dataclasses.fields(obj))


# ===================================================================
# Additional datetime format tests
# ===================================================================

_DATETIME_FIELD_MAP = [
    (PlantRecord, _plant_kw, "created_at"),
    (LineRecord, _line_kw, "created_at"),
    (StationRecord, _station_kw, "created_at"),
    (WorkOrder, _work_order_kw, "created_at"),
    (BatchRecord, _batch_kw, "created_at"),
    (MachineRecord, _machine_kw, "created_at"),
    (QualityCheck, _quality_check_kw, "checked_at"),
    (DowntimeEvent, _downtime_event_kw, "recorded_at"),
    (FactorySnapshot, _snapshot_kw, "captured_at"),
    (FactoryClosureReport, _closure_report_kw, "created_at"),
]


class TestDatetimeFormats:
    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FIELD_MAP,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FIELD_MAP])
    def test_iso_with_offset(self, cls, factory, dt_field):
        obj = cls(**factory(**{dt_field: "2025-06-01T10:30:00+02:00"}))
        assert getattr(obj, dt_field) == "2025-06-01T10:30:00+02:00"

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FIELD_MAP,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FIELD_MAP])
    def test_iso_with_z(self, cls, factory, dt_field):
        obj = cls(**factory(**{dt_field: "2025-06-01T00:00:00Z"}))
        assert getattr(obj, dt_field) == "2025-06-01T00:00:00Z"

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FIELD_MAP,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FIELD_MAP])
    def test_date_only(self, cls, factory, dt_field):
        obj = cls(**factory(**{dt_field: "2025-06-01"}))
        assert getattr(obj, dt_field) == "2025-06-01"

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FIELD_MAP,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FIELD_MAP])
    def test_garbage_rejected(self, cls, factory, dt_field):
        with pytest.raises(ValueError):
            cls(**factory(**{dt_field: "not-a-datetime"}))

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FIELD_MAP,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FIELD_MAP])
    def test_empty_rejected(self, cls, factory, dt_field):
        with pytest.raises(ValueError):
            cls(**factory(**{dt_field: ""}))

    @pytest.mark.parametrize("cls,factory,dt_field", _DATETIME_FIELD_MAP,
                             ids=[c.__name__ for c, _, _ in _DATETIME_FIELD_MAP])
    def test_whitespace_only_rejected(self, cls, factory, dt_field):
        with pytest.raises(ValueError):
            cls(**factory(**{dt_field: "   "}))


# ===================================================================
# Enum-field-rejects-string parametrized
# ===================================================================

_ENUM_FIELD_MAP = [
    (PlantRecord, _plant_kw, "status", "active"),
    (WorkOrder, _work_order_kw, "status", "draft"),
    (BatchRecord, _batch_kw, "status", "planned"),
    (MachineRecord, _machine_kw, "status", "operational"),
    (QualityCheck, _quality_check_kw, "verdict", "pass"),
    (DowntimeEvent, _downtime_event_kw, "disposition", "unscheduled"),
]


class TestEnumFieldRejectsStrings:
    @pytest.mark.parametrize("cls,factory,field,bad_str", _ENUM_FIELD_MAP,
                             ids=[c.__name__ for c, _, _, _ in _ENUM_FIELD_MAP])
    def test_string_rejected(self, cls, factory, field, bad_str):
        with pytest.raises(ValueError):
            cls(**factory(**{field: bad_str}))

    @pytest.mark.parametrize("cls,factory,field,bad_str", _ENUM_FIELD_MAP,
                             ids=[c.__name__ for c, _, _, _ in _ENUM_FIELD_MAP])
    def test_int_rejected(self, cls, factory, field, bad_str):
        with pytest.raises(ValueError):
            cls(**factory(**{field: 0}))

    @pytest.mark.parametrize("cls,factory,field,bad_str", _ENUM_FIELD_MAP,
                             ids=[c.__name__ for c, _, _, _ in _ENUM_FIELD_MAP])
    def test_none_rejected(self, cls, factory, field, bad_str):
        with pytest.raises(ValueError):
            cls(**factory(**{field: None}))


# ===================================================================
# to_dict preserves enum objects
# ===================================================================


class TestToDictPreservesEnums:
    def test_plant_status_in_dict(self):
        r = PlantRecord(**_plant_kw(status=FactoryStatus.IDLE))
        d = r.to_dict()
        assert d["status"] is FactoryStatus.IDLE

    def test_work_order_status_in_dict(self):
        r = WorkOrder(**_work_order_kw(status=WorkOrderStatus.RELEASED))
        d = r.to_dict()
        assert d["status"] is WorkOrderStatus.RELEASED

    def test_batch_status_in_dict(self):
        r = BatchRecord(**_batch_kw(status=BatchStatus.IN_PROGRESS))
        d = r.to_dict()
        assert d["status"] is BatchStatus.IN_PROGRESS

    def test_machine_status_in_dict(self):
        r = MachineRecord(**_machine_kw(status=MachineStatus.DEGRADED))
        d = r.to_dict()
        assert d["status"] is MachineStatus.DEGRADED

    def test_quality_verdict_in_dict(self):
        r = QualityCheck(**_quality_check_kw(verdict=QualityVerdict.FAIL))
        d = r.to_dict()
        assert d["verdict"] is QualityVerdict.FAIL

    def test_downtime_disposition_in_dict(self):
        r = DowntimeEvent(**_downtime_event_kw(disposition=MaintenanceDisposition.EMERGENCY))
        d = r.to_dict()
        assert d["disposition"] is MaintenanceDisposition.EMERGENCY


# ===================================================================
# Metadata edge-cases
# ===================================================================


class TestMetadataEdgeCases:
    def test_nested_list_frozen_to_tuple(self):
        r = PlantRecord(**_plant_kw(metadata={"items": [1, 2, 3]}))
        assert isinstance(r.metadata["items"], tuple)
        assert r.metadata["items"] == (1, 2, 3)

    def test_nested_list_thawed_to_list(self):
        r = PlantRecord(**_plant_kw(metadata={"items": [1, 2, 3]}))
        d = r.to_dict()
        assert isinstance(d["metadata"]["items"], list)

    def test_deeply_nested_metadata(self):
        md = {"a": {"b": {"c": {"d": "deep"}}}}
        r = LineRecord(**_line_kw(metadata=md))
        assert isinstance(r.metadata["a"], MappingProxyType)
        assert isinstance(r.metadata["a"]["b"], MappingProxyType)
        assert isinstance(r.metadata["a"]["b"]["c"], MappingProxyType)
        assert r.metadata["a"]["b"]["c"]["d"] == "deep"

    def test_deeply_nested_thawed(self):
        md = {"a": {"b": {"c": "val"}}}
        r = LineRecord(**_line_kw(metadata=md))
        d = r.to_dict()
        assert isinstance(d["metadata"]["a"]["b"], dict)

    def test_metadata_with_set_frozen_to_frozenset(self):
        r = PlantRecord(**_plant_kw(metadata={"tags": {"x", "y"}}))
        assert isinstance(r.metadata["tags"], frozenset)

    def test_metadata_with_bool_values(self):
        r = PlantRecord(**_plant_kw(metadata={"flag": True}))
        assert r.metadata["flag"] is True

    def test_metadata_with_none_value(self):
        r = PlantRecord(**_plant_kw(metadata={"nothing": None}))
        assert r.metadata["nothing"] is None

    def test_metadata_with_numeric_values(self):
        r = PlantRecord(**_plant_kw(metadata={"count": 42, "rate": 3.14}))
        assert r.metadata["count"] == 42
        assert r.metadata["rate"] == 3.14

    def test_source_dict_not_mutated_after_construction(self):
        md = {"k": "v"}
        r = PlantRecord(**_plant_kw(metadata=md))
        md["k2"] = "v2"
        assert "k2" not in r.metadata


# ===================================================================
# Large integer acceptance
# ===================================================================


class TestLargeIntegers:
    def test_plant_large_line_count(self):
        r = PlantRecord(**_plant_kw(line_count=999_999))
        assert r.line_count == 999_999

    def test_snapshot_large_totals(self):
        r = FactorySnapshot(**_snapshot_kw(total_plants=10**9))
        assert r.total_plants == 10**9

    def test_work_order_large_quantity(self):
        r = WorkOrder(**_work_order_kw(quantity=10**7))
        assert r.quantity == 10**7

    def test_machine_large_uptime(self):
        r = MachineRecord(**_machine_kw(uptime_hours=87_600))
        assert r.uptime_hours == 87_600

    def test_quality_check_large_defects(self):
        r = QualityCheck(**_quality_check_kw(defect_count=50_000))
        assert r.defect_count == 50_000

    def test_downtime_large_duration(self):
        r = DowntimeEvent(**_downtime_event_kw(duration_minutes=525_600))
        assert r.duration_minutes == 525_600


# ===================================================================
# Yield-rate boundary precision
# ===================================================================


class TestYieldRateBoundary:
    @pytest.mark.parametrize("val", [0.0, 0.001, 0.01, 0.1, 0.5, 0.9, 0.99, 0.999, 1.0])
    def test_valid_yield_rates(self, val):
        r = BatchRecord(**_batch_kw(yield_rate=val))
        assert r.yield_rate == pytest.approx(val)

    @pytest.mark.parametrize("val", [-0.001, 1.001, 2.0, -1.0, 10.0])
    def test_invalid_yield_rates(self, val):
        with pytest.raises(ValueError):
            BatchRecord(**_batch_kw(yield_rate=val))


# ===================================================================
# ContractRecord base behaviour
# ===================================================================


class TestContractRecordBase:
    def test_plant_is_contract_record(self):
        assert issubclass(PlantRecord, ContractRecord)

    def test_line_is_contract_record(self):
        assert issubclass(LineRecord, ContractRecord)

    def test_station_is_contract_record(self):
        assert issubclass(StationRecord, ContractRecord)

    def test_work_order_is_contract_record(self):
        assert issubclass(WorkOrder, ContractRecord)

    def test_batch_is_contract_record(self):
        assert issubclass(BatchRecord, ContractRecord)

    def test_machine_is_contract_record(self):
        assert issubclass(MachineRecord, ContractRecord)

    def test_quality_check_is_contract_record(self):
        assert issubclass(QualityCheck, ContractRecord)

    def test_downtime_event_is_contract_record(self):
        assert issubclass(DowntimeEvent, ContractRecord)

    def test_snapshot_is_contract_record(self):
        assert issubclass(FactorySnapshot, ContractRecord)

    def test_closure_report_is_contract_record(self):
        assert issubclass(FactoryClosureReport, ContractRecord)


# ===================================================================
# Text-field non-type values
# ===================================================================


class TestTextFieldTypeSafety:
    @pytest.mark.parametrize("cls,factory,field_name", [
        (PlantRecord, _plant_kw, "plant_id"),
        (PlantRecord, _plant_kw, "tenant_id"),
        (LineRecord, _line_kw, "line_id"),
        (StationRecord, _station_kw, "station_id"),
        (WorkOrder, _work_order_kw, "order_id"),
        (BatchRecord, _batch_kw, "batch_id"),
        (MachineRecord, _machine_kw, "machine_id"),
        (QualityCheck, _quality_check_kw, "check_id"),
        (DowntimeEvent, _downtime_event_kw, "event_id"),
        (FactorySnapshot, _snapshot_kw, "snapshot_id"),
        (FactoryClosureReport, _closure_report_kw, "report_id"),
    ])
    def test_int_as_text_rejected(self, cls, factory, field_name):
        with pytest.raises((ValueError, TypeError)):
            cls(**factory(**{field_name: 123}))

    @pytest.mark.parametrize("cls,factory,field_name", [
        (PlantRecord, _plant_kw, "plant_id"),
        (LineRecord, _line_kw, "line_id"),
        (WorkOrder, _work_order_kw, "order_id"),
        (BatchRecord, _batch_kw, "batch_id"),
        (MachineRecord, _machine_kw, "machine_id"),
        (QualityCheck, _quality_check_kw, "check_id"),
        (DowntimeEvent, _downtime_event_kw, "event_id"),
    ])
    def test_none_as_text_rejected(self, cls, factory, field_name):
        with pytest.raises((ValueError, TypeError)):
            cls(**factory(**{field_name: None}))


# ===================================================================
# Equality and identity
# ===================================================================


class TestEquality:
    def test_same_kwargs_equal(self):
        a = PlantRecord(**_plant_kw())
        b = PlantRecord(**_plant_kw())
        assert a == b

    def test_different_kwargs_not_equal(self):
        a = PlantRecord(**_plant_kw(plant_id="p-1"))
        b = PlantRecord(**_plant_kw(plant_id="p-2"))
        assert a != b

    def test_batch_same_equal(self):
        a = BatchRecord(**_batch_kw())
        b = BatchRecord(**_batch_kw())
        assert a == b

    def test_snapshot_same_equal(self):
        a = FactorySnapshot(**_snapshot_kw())
        b = FactorySnapshot(**_snapshot_kw())
        assert a == b


# ===================================================================
# to_dict round-trip identity (no enums -> no to_json)
# ===================================================================


class TestToDictRoundTrip:
    """Verify that to_dict() output can reconstruct an equivalent instance
    for classes WITHOUT enum fields (LineRecord, StationRecord, FactorySnapshot,
    FactoryClosureReport)."""

    def test_line_record_roundtrip(self):
        orig = LineRecord(**_line_kw())
        d = orig.to_dict()
        rebuilt = LineRecord(**d)
        assert orig == rebuilt

    def test_station_record_roundtrip(self):
        orig = StationRecord(**_station_kw())
        d = orig.to_dict()
        rebuilt = StationRecord(**d)
        assert orig == rebuilt

    def test_snapshot_roundtrip(self):
        orig = FactorySnapshot(**_snapshot_kw())
        d = orig.to_dict()
        rebuilt = FactorySnapshot(**d)
        assert orig == rebuilt

    def test_closure_report_roundtrip(self):
        orig = FactoryClosureReport(**_closure_report_kw())
        d = orig.to_dict()
        rebuilt = FactoryClosureReport(**d)
        assert orig == rebuilt
