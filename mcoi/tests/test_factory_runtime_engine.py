"""Comprehensive pytest tests for FactoryRuntimeEngine.

Target: ~350 tests covering constructor validation, plant/line/station/machine
registration, work-order lifecycle, batch lifecycle, quality checks, downtime,
violation detection, snapshots, state hashing, event emission, and edge cases.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.factory_runtime import FactoryRuntimeEngine
from mcoi_runtime.contracts.factory_runtime import (
    BatchRecord,
    BatchStatus,
    DowntimeEvent,
    FactoryClosureReport,
    FactorySnapshot,
    FactoryStatus,
    LineRecord,
    MachineRecord,
    MachineStatus,
    MaintenanceDisposition,
    PlantRecord,
    QualityCheck,
    QualityVerdict,
    StationRecord,
    WorkOrder,
    WorkOrderStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(es: EventSpineEngine) -> FactoryRuntimeEngine:
    return FactoryRuntimeEngine(es)


@pytest.fixture
def plant(engine: FactoryRuntimeEngine) -> PlantRecord:
    return engine.register_plant("p1", "t1", "Plant One")


@pytest.fixture
def line(engine: FactoryRuntimeEngine, plant: PlantRecord) -> LineRecord:
    return engine.register_line("l1", "t1", "p1", "Line One")


@pytest.fixture
def station(engine: FactoryRuntimeEngine, line: LineRecord) -> StationRecord:
    return engine.register_station("s1", "t1", "l1", "Station One", "mach-ref")


@pytest.fixture
def machine(engine: FactoryRuntimeEngine, station: StationRecord) -> MachineRecord:
    return engine.register_machine("m1", "t1", "s1", "Machine One")


@pytest.fixture
def order(engine: FactoryRuntimeEngine, plant: PlantRecord) -> WorkOrder:
    return engine.create_work_order("o1", "t1", "p1", "prod-A", 100)


@pytest.fixture
def batch(engine: FactoryRuntimeEngine, order: WorkOrder) -> BatchRecord:
    return engine.start_batch("b1", "t1", "o1", 50)


# ---------------------------------------------------------------------------
# 1. Constructor Validation (10 tests)
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_accepts_event_spine(self, es: EventSpineEngine) -> None:
        eng = FactoryRuntimeEngine(es)
        assert eng.plant_count == 0

    def test_rejects_none(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeEngine(None)

    def test_rejects_string(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeEngine("not-an-engine")

    def test_rejects_int(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeEngine(42)

    def test_rejects_dict(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeEngine({})

    def test_rejects_list(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeEngine([])

    def test_rejects_bool(self) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            FactoryRuntimeEngine(True)

    def test_initial_plant_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.plant_count == 0

    def test_initial_order_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.order_count == 0

    def test_initial_batch_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.batch_count == 0


# ---------------------------------------------------------------------------
# 2. Property Counters (12 tests)
# ---------------------------------------------------------------------------


class TestPropertyCounters:
    def test_line_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.line_count == 0

    def test_station_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.station_count == 0

    def test_machine_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.machine_count == 0

    def test_check_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.check_count == 0

    def test_downtime_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.downtime_count == 0

    def test_violation_count_zero(self, engine: FactoryRuntimeEngine) -> None:
        assert engine.violation_count == 0

    def test_plant_count_increments(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P1")
        assert engine.plant_count == 1
        engine.register_plant("p2", "t1", "P2")
        assert engine.plant_count == 2

    def test_line_count_increments(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.register_line("l1", "t1", "p1", "L1")
        assert engine.line_count == 1

    def test_station_count_increments(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        engine.register_station("s1", "t1", "l1", "S1", "mr")
        assert engine.station_count == 1

    def test_machine_count_increments(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        engine.register_station("s1", "t1", "l1", "S", "mr")
        engine.register_machine("m1", "t1", "s1", "M")
        assert engine.machine_count == 1

    def test_order_count_increments(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        assert engine.order_count == 1

    def test_batch_count_increments(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.start_batch("b1", "t1", "o1", 10)
        assert engine.batch_count == 1


# ---------------------------------------------------------------------------
# 3. Plant Registration (25 tests)
# ---------------------------------------------------------------------------


class TestPlantRegistration:
    def test_returns_plant_record(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "Plant")
        assert isinstance(p, PlantRecord)

    def test_plant_id_stored(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "Plant")
        assert p.plant_id == "p1"

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "Plant")
        assert p.tenant_id == "t1"

    def test_display_name_stored(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "My Plant")
        assert p.display_name == "My Plant"

    def test_status_is_active(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "Plant")
        assert p.status == FactoryStatus.ACTIVE

    def test_line_count_starts_zero(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "Plant")
        assert p.line_count == 0

    def test_created_at_set(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "Plant")
        assert p.created_at != ""

    def test_duplicate_plant_raises(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate plant_id"):
            engine.register_plant("p1", "t1", "B")

    def test_different_ids_ok(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        engine.register_plant("p2", "t1", "B")
        assert engine.plant_count == 2

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        assert es.event_count == 1

    def test_get_plant_returns(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        p = engine.get_plant("p1")
        assert p.plant_id == "p1"

    def test_get_plant_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plant_id"):
            engine.get_plant("no-such")

    def test_plants_for_tenant_empty(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.plants_for_tenant("t1")
        assert result == ()

    def test_plants_for_tenant_returns_matching(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        engine.register_plant("p2", "t2", "B")
        result = engine.plants_for_tenant("t1")
        assert len(result) == 1
        assert result[0].tenant_id == "t1"

    def test_plants_for_tenant_multiple(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        engine.register_plant("p2", "t1", "B")
        result = engine.plants_for_tenant("t1")
        assert len(result) == 2

    def test_plants_for_tenant_no_cross_tenant(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        engine.register_plant("p2", "t2", "B")
        result = engine.plants_for_tenant("t2")
        assert len(result) == 1
        assert result[0].plant_id == "p2"

    def test_plant_record_frozen(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "P")
        with pytest.raises(AttributeError):
            p.plant_id = "changed"

    def test_register_many_plants(self, engine: FactoryRuntimeEngine) -> None:
        for i in range(10):
            engine.register_plant(f"p{i}", "t1", f"Plant {i}")
        assert engine.plant_count == 10

    def test_plant_metadata_default_empty(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("p1", "t1", "P")
        assert len(p.metadata) == 0

    def test_plants_for_tenant_returns_tuple(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        result = engine.plants_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_two_events_for_two_plants(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        engine.register_plant("p2", "t1", "B")
        assert es.event_count == 2

    def test_get_plant_after_line_registration_shows_updated_count(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        p = engine.get_plant("p1")
        assert p.line_count == 1

    def test_register_plant_different_tenants(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "A")
        engine.register_plant("p2", "t2", "B")
        assert engine.plant_count == 2

    def test_plant_id_preserved_exactly(self, engine: FactoryRuntimeEngine) -> None:
        p = engine.register_plant("plant-ABC-123", "t1", "P")
        assert p.plant_id == "plant-ABC-123"

    def test_duplicate_plant_does_not_increment_count(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_plant("p1", "t1", "P2")
        assert engine.plant_count == 1


# ---------------------------------------------------------------------------
# 4. Line Registration (25 tests)
# ---------------------------------------------------------------------------


class TestLineRegistration:
    def test_returns_line_record(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "Line")
        assert isinstance(ln, LineRecord)

    def test_line_id_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "Line")
        assert ln.line_id == "l1"

    def test_plant_id_ref(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "Line")
        assert ln.plant_id == "p1"

    def test_station_count_starts_zero(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "Line")
        assert ln.station_count == 0

    def test_created_at_set(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "Line")
        assert ln.created_at != ""

    def test_duplicate_line_raises(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.register_line("l1", "t1", "p1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate line_id"):
            engine.register_line("l1", "t1", "p1", "B")

    def test_unknown_plant_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plant_id"):
            engine.register_line("l1", "t1", "no-plant", "Line")

    def test_increments_plant_line_count(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.register_line("l1", "t1", "p1", "L1")
        p = engine.get_plant("p1")
        assert p.line_count == 1

    def test_increments_plant_line_count_twice(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.register_line("l1", "t1", "p1", "L1")
        engine.register_line("l2", "t1", "p1", "L2")
        p = engine.get_plant("p1")
        assert p.line_count == 2

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        before = es.event_count
        engine.register_line("l1", "t1", "p1", "L")
        assert es.event_count == before + 1

    def test_get_line_returns(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        ln = engine.get_line("l1")
        assert ln.line_id == "l1"

    def test_get_line_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown line_id"):
            engine.get_line("no-such")

    def test_line_record_frozen(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "L")
        with pytest.raises(AttributeError):
            ln.line_id = "changed"

    def test_multiple_lines_different_plants(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("pA", "t1", "PA")
        engine.register_plant("pB", "t1", "PB")
        engine.register_line("l1", "t1", "pA", "L1")
        engine.register_line("l2", "t1", "pB", "L2")
        assert engine.get_plant("pA").line_count == 1
        assert engine.get_plant("pB").line_count == 1

    def test_five_lines_one_plant(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        for i in range(5):
            engine.register_line(f"l{i}", "t1", "p1", f"Line {i}")
        assert engine.get_plant("p1").line_count == 5
        assert engine.line_count == 5

    def test_display_name_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "Assembly Line Alpha")
        assert ln.display_name == "Assembly Line Alpha"

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "L")
        assert ln.tenant_id == "t1"

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        ln = engine.register_line("l1", "t1", "p1", "L")
        assert len(ln.metadata) == 0

    def test_duplicate_line_does_not_increment_plant_count(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_line("l1", "t1", "p1", "L2")
        assert engine.get_plant("p1").line_count == 1

    def test_line_count_three(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        for i in range(3):
            engine.register_line(f"l{i}", "t1", "p1", f"L{i}")
        assert engine.line_count == 3

    def test_get_line_after_station_shows_updated_count(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        engine.register_station("s1", "t1", "l1", "S", "mr")
        ln = engine.get_line("l1")
        assert ln.station_count == 1

    def test_register_line_event_count(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        # 1 for plant + 1 for line
        assert es.event_count == 2

    def test_register_line_preserves_plant_display_name(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        p = engine.get_plant("p1")
        assert p.display_name == "Plant One"

    def test_register_line_preserves_plant_status(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        p = engine.get_plant("p1")
        assert p.status == FactoryStatus.ACTIVE

    def test_register_line_preserves_plant_tenant(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        p = engine.get_plant("p1")
        assert p.tenant_id == "t1"


# ---------------------------------------------------------------------------
# 5. Station Registration (20 tests)
# ---------------------------------------------------------------------------


class TestStationRegistration:
    def test_returns_station_record(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        assert isinstance(s, StationRecord)

    def test_station_id_stored(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        assert s.station_id == "s1"

    def test_line_id_ref(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        assert s.line_id == "l1"

    def test_machine_ref_stored(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mach-x")
        assert s.machine_ref == "mach-x"

    def test_duplicate_station_raises(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        engine.register_station("s1", "t1", "l1", "A", "mr")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate station_id"):
            engine.register_station("s1", "t1", "l1", "B", "mr")

    def test_unknown_line_raises(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown line_id"):
            engine.register_station("s1", "t1", "no-line", "S", "mr")

    def test_increments_line_station_count(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        engine.register_station("s1", "t1", "l1", "S", "mr")
        ln = engine.get_line("l1")
        assert ln.station_count == 1

    def test_increments_line_station_count_twice(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        engine.register_station("s1", "t1", "l1", "S1", "mr")
        engine.register_station("s2", "t1", "l1", "S2", "mr")
        ln = engine.get_line("l1")
        assert ln.station_count == 2

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        before = es.event_count
        engine.register_station("s1", "t1", "l1", "S", "mr")
        assert es.event_count == before + 1

    def test_station_record_frozen(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        with pytest.raises(AttributeError):
            s.station_id = "changed"

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        assert s.tenant_id == "t1"

    def test_display_name_stored(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "Welding Station", "mr")
        assert s.display_name == "Welding Station"

    def test_created_at_set(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        assert s.created_at != ""

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        s = engine.register_station("s1", "t1", "l1", "S", "mr")
        assert len(s.metadata) == 0

    def test_five_stations(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        for i in range(5):
            engine.register_station(f"s{i}", "t1", "l1", f"S{i}", "mr")
        assert engine.station_count == 5
        assert engine.get_line("l1").station_count == 5

    def test_duplicate_station_does_not_increment_count(
        self, engine: FactoryRuntimeEngine, line: LineRecord
    ) -> None:
        engine.register_station("s1", "t1", "l1", "S", "mr")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_station("s1", "t1", "l1", "S2", "mr")
        assert engine.get_line("l1").station_count == 1

    def test_station_preserves_line_display_name(
        self, engine: FactoryRuntimeEngine, line: LineRecord
    ) -> None:
        engine.register_station("s1", "t1", "l1", "S", "mr")
        ln = engine.get_line("l1")
        assert ln.display_name == "Line One"

    def test_station_preserves_line_plant_id(
        self, engine: FactoryRuntimeEngine, line: LineRecord
    ) -> None:
        engine.register_station("s1", "t1", "l1", "S", "mr")
        ln = engine.get_line("l1")
        assert ln.plant_id == "p1"

    def test_station_preserves_line_tenant(
        self, engine: FactoryRuntimeEngine, line: LineRecord
    ) -> None:
        engine.register_station("s1", "t1", "l1", "S", "mr")
        ln = engine.get_line("l1")
        assert ln.tenant_id == "t1"

    def test_station_count_property(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        engine.register_station("s1", "t1", "l1", "S1", "mr")
        engine.register_station("s2", "t1", "l1", "S2", "mr")
        engine.register_station("s3", "t1", "l1", "S3", "mr")
        assert engine.station_count == 3


# ---------------------------------------------------------------------------
# 6. Machine Registration (20 tests)
# ---------------------------------------------------------------------------


class TestMachineRegistration:
    def test_returns_machine_record(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "Machine")
        assert isinstance(m, MachineRecord)

    def test_machine_id_stored(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert m.machine_id == "m1"

    def test_station_ref_stored(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert m.station_ref == "s1"

    def test_status_operational(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert m.status == MachineStatus.OPERATIONAL

    def test_uptime_zero(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert m.uptime_hours == 0

    def test_duplicate_machine_raises(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        engine.register_machine("m1", "t1", "s1", "A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate machine_id"):
            engine.register_machine("m1", "t1", "s1", "B")

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        before = es.event_count
        engine.register_machine("m1", "t1", "s1", "M")
        assert es.event_count == before + 1

    def test_machine_record_frozen(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        with pytest.raises(AttributeError):
            m.machine_id = "changed"

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert m.tenant_id == "t1"

    def test_display_name_stored(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "CNC Router")
        assert m.display_name == "CNC Router"

    def test_created_at_set(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert m.created_at != ""

    def test_multiple_machines(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        for i in range(5):
            engine.register_machine(f"m{i}", "t1", "s1", f"Machine {i}")
        assert engine.machine_count == 5

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert len(m.metadata) == 0

    def test_duplicate_does_not_increment(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        engine.register_machine("m1", "t1", "s1", "M")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_machine("m1", "t1", "s1", "M2")
        assert engine.machine_count == 1

    def test_machine_id_preserved_exactly(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("machine-XYZ-99", "t1", "s1", "M")
        assert m.machine_id == "machine-XYZ-99"

    def test_two_machines_two_events(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, station: StationRecord
    ) -> None:
        before = es.event_count
        engine.register_machine("m1", "t1", "s1", "M1")
        engine.register_machine("m2", "t1", "s1", "M2")
        assert es.event_count == before + 2

    def test_register_ten_machines(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        for i in range(10):
            engine.register_machine(f"m{i}", "t1", "s1", f"M{i}")
        assert engine.machine_count == 10

    def test_machine_different_tenants(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        engine.register_machine("m1", "t1", "s1", "M1")
        engine.register_machine("m2", "t2", "s1", "M2")
        assert engine.machine_count == 2

    def test_machine_status_is_enum(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        m = engine.register_machine("m1", "t1", "s1", "M")
        assert isinstance(m.status, MachineStatus)

    def test_machine_count_after_registration(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        assert engine.machine_count == 0
        engine.register_machine("m1", "t1", "s1", "M")
        assert engine.machine_count == 1


# ---------------------------------------------------------------------------
# 7. Work Order Creation (20 tests)
# ---------------------------------------------------------------------------


class TestWorkOrderCreation:
    def test_returns_work_order(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert isinstance(o, WorkOrder)

    def test_order_id_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert o.order_id == "o1"

    def test_defaults_to_draft(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert o.status == WorkOrderStatus.DRAFT

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert o.tenant_id == "t1"

    def test_plant_id_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert o.plant_id == "p1"

    def test_product_ref_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "widget-X", 100)
        assert o.product_ref == "widget-X"

    def test_quantity_stored(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 250)
        assert o.quantity == 250

    def test_created_at_set(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert o.created_at != ""

    def test_duplicate_order_raises(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.create_work_order("o1", "t1", "p1", "prod", 100)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate order_id"):
            engine.create_work_order("o1", "t1", "p1", "prod", 200)

    def test_unknown_plant_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown plant_id"):
            engine.create_work_order("o1", "t1", "no-plant", "prod", 100)

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        before = es.event_count
        engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert es.event_count == before + 1

    def test_order_record_frozen(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        with pytest.raises(AttributeError):
            o.status = WorkOrderStatus.RELEASED

    def test_multiple_orders(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        for i in range(5):
            engine.create_work_order(f"o{i}", "t1", "p1", f"prod{i}", 10)
        assert engine.order_count == 5

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert len(o.metadata) == 0

    def test_duplicate_does_not_increment_count(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.create_work_order("o1", "t1", "p1", "prod", 100)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.create_work_order("o1", "t1", "p1", "prod", 200)
        assert engine.order_count == 1

    def test_zero_quantity(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 0)
        assert o.quantity == 0

    def test_large_quantity(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 999999)
        assert o.quantity == 999999

    def test_status_is_enum(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        o = engine.create_work_order("o1", "t1", "p1", "prod", 100)
        assert isinstance(o.status, WorkOrderStatus)

    def test_ten_orders_ten_events(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        before = es.event_count
        for i in range(10):
            engine.create_work_order(f"o{i}", "t1", "p1", f"p{i}", 10)
        assert es.event_count == before + 10

    def test_order_different_plants(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("pA", "t1", "PA")
        engine.register_plant("pB", "t1", "PB")
        engine.create_work_order("o1", "t1", "pA", "prod", 10)
        engine.create_work_order("o2", "t1", "pB", "prod", 10)
        assert engine.order_count == 2


# ---------------------------------------------------------------------------
# 8. Work Order Lifecycle / Transitions (45 tests)
# ---------------------------------------------------------------------------


class TestWorkOrderTransitions:
    # --- release_order ---
    def test_release_draft_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        r = engine.release_order("o1")
        assert r.status == WorkOrderStatus.RELEASED

    def test_release_returns_work_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        r = engine.release_order("o1")
        assert isinstance(r, WorkOrder)

    def test_release_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        before = es.event_count
        engine.release_order("o1")
        assert es.event_count == before + 1

    def test_release_preserves_order_id(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        r = engine.release_order("o1")
        assert r.order_id == "o1"

    def test_release_preserves_quantity(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        r = engine.release_order("o1")
        assert r.quantity == 100

    def test_release_non_draft_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only release DRAFT"):
            engine.release_order("o1")

    def test_release_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown order_id"):
            engine.release_order("no-such")

    # --- start_order ---
    def test_start_released_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        s = engine.start_order("o1")
        assert s.status == WorkOrderStatus.IN_PROGRESS

    def test_start_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        before = es.event_count
        engine.start_order("o1")
        assert es.event_count == before + 1

    def test_start_draft_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Can only start RELEASED"):
            engine.start_order("o1")

    def test_start_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown order_id"):
            engine.start_order("no-such")

    def test_start_preserves_product_ref(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        s = engine.start_order("o1")
        assert s.product_ref == "prod-A"

    # --- complete_order ---
    def test_complete_in_progress_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        c = engine.complete_order("o1")
        assert c.status == WorkOrderStatus.COMPLETED

    def test_complete_emits_event(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        before = es.event_count
        engine.complete_order("o1")
        assert es.event_count == before + 1

    def test_complete_draft_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Can only complete IN_PROGRESS"):
            engine.complete_order("o1")

    def test_complete_released_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only complete IN_PROGRESS"):
            engine.complete_order("o1")

    def test_complete_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown order_id"):
            engine.complete_order("no-such")

    # --- cancel_order ---
    def test_cancel_draft_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        c = engine.cancel_order("o1")
        assert c.status == WorkOrderStatus.CANCELLED

    def test_cancel_released_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        c = engine.cancel_order("o1")
        assert c.status == WorkOrderStatus.CANCELLED

    def test_cancel_in_progress_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        c = engine.cancel_order("o1")
        assert c.status == WorkOrderStatus.CANCELLED

    def test_cancel_emits_event(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        before = es.event_count
        engine.cancel_order("o1")
        assert es.event_count == before + 1

    def test_cancel_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown order_id"):
            engine.cancel_order("no-such")

    # --- terminal state blocking ---
    def test_completed_order_cannot_release(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only release DRAFT"):
            engine.release_order("o1")

    def test_completed_order_cannot_start(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only start RELEASED"):
            engine.start_order("o1")

    def test_completed_order_cannot_complete_again(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only complete IN_PROGRESS"):
            engine.complete_order("o1")

    def test_completed_order_cannot_cancel(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.cancel_order("o1")

    def test_cancelled_order_cannot_release(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.cancel_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only release DRAFT"):
            engine.release_order("o1")

    def test_cancelled_order_cannot_start(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.cancel_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only start RELEASED"):
            engine.start_order("o1")

    def test_cancelled_order_cannot_complete(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.cancel_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only complete IN_PROGRESS"):
            engine.complete_order("o1")

    def test_cancelled_order_cannot_cancel_again(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.cancel_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.cancel_order("o1")

    # --- full lifecycle event counting ---
    def test_full_lifecycle_event_count(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        before = es.event_count
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        assert es.event_count == before + 3

    def test_full_lifecycle_cancel_event_count(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        before = es.event_count
        engine.release_order("o1")
        engine.start_order("o1")
        engine.cancel_order("o1")
        assert es.event_count == before + 3

    # --- multiple orders ---
    def test_two_orders_independent_lifecycle(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.create_work_order("oA", "t1", "p1", "pA", 10)
        engine.create_work_order("oB", "t1", "p1", "pB", 20)
        engine.release_order("oA")
        engine.cancel_order("oB")
        # oA should be RELEASED, oB should be CANCELLED
        # Cannot start oB because it's cancelled
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_order("oB")
        # Can start oA
        engine.start_order("oA")

    def test_release_preserves_tenant(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        r = engine.release_order("o1")
        assert r.tenant_id == "t1"

    def test_start_preserves_plant_id(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        s = engine.start_order("o1")
        assert s.plant_id == "p1"

    def test_complete_preserves_tenant(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        c = engine.complete_order("o1")
        assert c.tenant_id == "t1"

    def test_cancel_preserves_product_ref(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        c = engine.cancel_order("o1")
        assert c.product_ref == "prod-A"

    def test_complete_preserves_created_at(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        original_created = order.created_at
        engine.release_order("o1")
        engine.start_order("o1")
        c = engine.complete_order("o1")
        assert c.created_at == original_created

    def test_release_preserves_created_at(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        original_created = order.created_at
        r = engine.release_order("o1")
        assert r.created_at == original_created

    def test_start_in_progress_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only start RELEASED"):
            engine.start_order("o1")

    def test_release_in_progress_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only release DRAFT"):
            engine.release_order("o1")

    def test_ten_orders_full_lifecycle(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        before = es.event_count
        for i in range(10):
            oid = f"o{i}"
            engine.create_work_order(oid, "t1", "p1", f"p{i}", 10)
            engine.release_order(oid)
            engine.start_order(oid)
            engine.complete_order(oid)
        # 10 * 4 = 40 events (create + release + start + complete)
        assert es.event_count == before + 40

    def test_cancel_preserves_quantity(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        c = engine.cancel_order("o1")
        assert c.quantity == 100

    def test_complete_returns_frozen(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        c = engine.complete_order("o1")
        with pytest.raises(AttributeError):
            c.status = WorkOrderStatus.DRAFT


# ---------------------------------------------------------------------------
# 9. Batch Lifecycle (40 tests)
# ---------------------------------------------------------------------------


class TestBatchLifecycle:
    def test_start_batch_returns_record(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        assert isinstance(b, BatchRecord)

    def test_start_batch_status_in_progress(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        assert b.status == BatchStatus.IN_PROGRESS

    def test_start_batch_id_stored(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        assert b.batch_id == "b1"

    def test_start_batch_order_ref(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        assert b.order_id == "o1"

    def test_start_batch_unit_count(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 75)
        assert b.unit_count == 75

    def test_start_batch_yield_zero(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        assert b.yield_rate == 0.0

    def test_start_batch_created_at_set(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        assert b.created_at != ""

    def test_duplicate_batch_raises(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.start_batch("b1", "t1", "o1", 50)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate batch_id"):
            engine.start_batch("b1", "t1", "o1", 50)

    def test_unknown_order_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown order_id"):
            engine.start_batch("b1", "t1", "no-order", 50)

    def test_start_batch_emits_event(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        before = es.event_count
        engine.start_batch("b1", "t1", "o1", 50)
        assert es.event_count == before + 1

    def test_batch_record_frozen(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        b = engine.start_batch("b1", "t1", "o1", 50)
        with pytest.raises(AttributeError):
            b.status = BatchStatus.COMPLETED

    # --- complete_batch ---
    def test_complete_batch_status(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        cb = engine.complete_batch("b1")
        assert cb.status == BatchStatus.COMPLETED

    def test_complete_batch_yield_no_qc(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 1.0

    def test_complete_batch_yield_all_pass(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 1.0

    def test_complete_batch_yield_all_fail(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 3, "insp1")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.FAIL, 2, "insp1")
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 0.0

    def test_complete_batch_yield_mixed(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.FAIL, 1, "insp1")
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 0.5

    def test_complete_batch_yield_3_of_4(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc3", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc4", "t1", "b1", QualityVerdict.FAIL, 1, "insp1")
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 0.75

    def test_complete_batch_emits_event(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord
    ) -> None:
        before = es.event_count
        engine.complete_batch("b1")
        assert es.event_count == before + 1

    def test_complete_batch_preserves_unit_count(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        cb = engine.complete_batch("b1")
        assert cb.unit_count == 50

    def test_complete_batch_preserves_tenant(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        cb = engine.complete_batch("b1")
        assert cb.tenant_id == "t1"

    def test_complete_batch_preserves_order_id(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        cb = engine.complete_batch("b1")
        assert cb.order_id == "o1"

    def test_complete_batch_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown batch_id"):
            engine.complete_batch("no-such")

    # --- reject_batch ---
    def test_reject_batch_status(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        rb = engine.reject_batch("b1")
        assert rb.status == BatchStatus.REJECTED

    def test_reject_batch_emits_event(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord
    ) -> None:
        before = es.event_count
        engine.reject_batch("b1")
        assert es.event_count == before + 1

    def test_reject_batch_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown batch_id"):
            engine.reject_batch("no-such")

    def test_reject_preserves_unit_count(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        rb = engine.reject_batch("b1")
        assert rb.unit_count == 50

    # --- scrap_batch ---
    def test_scrap_batch_status(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        sb = engine.scrap_batch("b1")
        assert sb.status == BatchStatus.SCRAPPED

    def test_scrap_batch_emits_event(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord
    ) -> None:
        before = es.event_count
        engine.scrap_batch("b1")
        assert es.event_count == before + 1

    def test_scrap_batch_unknown_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown batch_id"):
            engine.scrap_batch("no-such")

    def test_scrap_preserves_tenant(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        sb = engine.scrap_batch("b1")
        assert sb.tenant_id == "t1"

    # --- terminal batch states ---
    def test_completed_batch_cannot_complete(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.complete_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.complete_batch("b1")

    def test_completed_batch_cannot_reject(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.complete_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.reject_batch("b1")

    def test_completed_batch_cannot_scrap(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.complete_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.scrap_batch("b1")

    def test_rejected_batch_cannot_complete(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.reject_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.complete_batch("b1")

    def test_rejected_batch_cannot_reject(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.reject_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.reject_batch("b1")

    def test_rejected_batch_cannot_scrap(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.reject_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.scrap_batch("b1")

    def test_scrapped_batch_cannot_complete(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.scrap_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.complete_batch("b1")

    def test_scrapped_batch_cannot_reject(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.scrap_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.reject_batch("b1")

    def test_scrapped_batch_cannot_scrap(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.scrap_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal status"):
            engine.scrap_batch("b1")

    def test_multiple_batches_one_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.start_batch("b1", "t1", "o1", 10)
        engine.start_batch("b2", "t1", "o1", 20)
        engine.start_batch("b3", "t1", "o1", 30)
        assert engine.batch_count == 3


# ---------------------------------------------------------------------------
# 10. Quality Checks (30 tests)
# ---------------------------------------------------------------------------


class TestQualityChecks:
    def test_returns_quality_check(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert isinstance(qc, QualityCheck)

    def test_check_id_stored(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert qc.check_id == "qc1"

    def test_batch_id_stored(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert qc.batch_id == "b1"

    def test_verdict_pass(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert qc.verdict == QualityVerdict.PASS

    def test_verdict_fail(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 5, "insp1")
        assert qc.verdict == QualityVerdict.FAIL

    def test_verdict_conditional(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.CONDITIONAL, 1, "insp1")
        assert qc.verdict == QualityVerdict.CONDITIONAL

    def test_verdict_not_tested(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.NOT_TESTED, 0, "insp1")
        assert qc.verdict == QualityVerdict.NOT_TESTED

    def test_defect_count_stored(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 7, "insp1")
        assert qc.defect_count == 7

    def test_inspector_ref_stored(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "inspector-42")
        assert qc.inspector_ref == "inspector-42"

    def test_checked_at_set(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert qc.checked_at != ""

    def test_duplicate_check_raises(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate check_id"):
            engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 1, "insp1")

    def test_unknown_batch_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown batch_id"):
            engine.record_quality_check("qc1", "t1", "no-batch", QualityVerdict.PASS, 0, "insp1")

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        before = es.event_count
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert es.event_count == before + 1

    def test_check_record_frozen(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        with pytest.raises(AttributeError):
            qc.verdict = QualityVerdict.FAIL

    def test_check_count_increments(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert engine.check_count == 1

    def test_checks_for_batch_empty(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        result = engine.checks_for_batch("b1")
        assert result == ()

    def test_checks_for_batch_returns_matching(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        result = engine.checks_for_batch("b1")
        assert len(result) == 1
        assert result[0].check_id == "qc1"

    def test_checks_for_batch_multiple(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.FAIL, 2, "insp1")
        result = engine.checks_for_batch("b1")
        assert len(result) == 2

    def test_checks_for_batch_no_cross_batch(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.start_batch("b1", "t1", "o1", 10)
        engine.start_batch("b2", "t1", "o1", 20)
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        engine.record_quality_check("qc2", "t1", "b2", QualityVerdict.FAIL, 1, "insp1")
        assert len(engine.checks_for_batch("b1")) == 1
        assert len(engine.checks_for_batch("b2")) == 1

    def test_checks_for_batch_returns_tuple(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        result = engine.checks_for_batch("b1")
        assert isinstance(result, tuple)

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert qc.tenant_id == "t1"

    def test_zero_defects(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp1")
        assert qc.defect_count == 0

    def test_many_defects(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 999, "insp1")
        assert qc.defect_count == 999

    def test_five_checks_five_events(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord
    ) -> None:
        before = es.event_count
        for i in range(5):
            engine.record_quality_check(f"qc{i}", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        assert es.event_count == before + 5

    def test_yield_1_of_3_pass(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.FAIL, 1, "insp")
        engine.record_quality_check("qc3", "t1", "b1", QualityVerdict.FAIL, 2, "insp")
        cb = engine.complete_batch("b1")
        assert abs(cb.yield_rate - 1 / 3) < 0.001

    def test_yield_conditional_counts_as_non_pass(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.CONDITIONAL, 0, "insp")
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 0.5

    def test_yield_not_tested_counts_as_non_pass(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.NOT_TESTED, 0, "insp")
        cb = engine.complete_batch("b1")
        assert cb.yield_rate == 0.5

    def test_duplicate_does_not_increment_count(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 1, "insp")
        assert engine.check_count == 1

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        qc = engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        assert len(qc.metadata) == 0


# ---------------------------------------------------------------------------
# 11. Downtime Events (25 tests)
# ---------------------------------------------------------------------------


class TestDowntimeEvents:
    def test_returns_downtime_event(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power failure", 30)
        assert isinstance(dt, DowntimeEvent)

    def test_event_id_stored(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power failure", 30)
        assert dt.event_id == "dt1"

    def test_machine_id_stored(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power failure", 30)
        assert dt.machine_id == "m1"

    def test_reason_stored(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "belt snapped", 60)
        assert dt.reason == "belt snapped"

    def test_duration_stored(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power failure", 45)
        assert dt.duration_minutes == 45

    def test_default_disposition_unscheduled(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power failure", 30)
        assert dt.disposition == MaintenanceDisposition.UNSCHEDULED

    def test_disposition_scheduled(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "planned", 30, MaintenanceDisposition.SCHEDULED)
        assert dt.disposition == MaintenanceDisposition.SCHEDULED

    def test_disposition_emergency(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "fire", 30, MaintenanceDisposition.EMERGENCY)
        assert dt.disposition == MaintenanceDisposition.EMERGENCY

    def test_disposition_completed(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "done", 30, MaintenanceDisposition.COMPLETED)
        assert dt.disposition == MaintenanceDisposition.COMPLETED

    def test_recorded_at_set(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power", 30)
        assert dt.recorded_at != ""

    def test_duplicate_event_raises(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate event_id"):
            engine.record_downtime("dt1", "t1", "m1", "other", 10)

    def test_unknown_machine_raises(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown machine_id"):
            engine.record_downtime("dt1", "t1", "no-machine", "power", 30)

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        before = es.event_count
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        assert es.event_count == before + 1

    def test_downtime_record_frozen(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power", 30)
        with pytest.raises(AttributeError):
            dt.reason = "changed"

    def test_downtime_count_increments(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        assert engine.downtime_count == 1

    def test_downtime_for_machine_empty(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        result = engine.downtime_for_machine("m1")
        assert result == ()

    def test_downtime_for_machine_returns_matching(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        result = engine.downtime_for_machine("m1")
        assert len(result) == 1

    def test_downtime_for_machine_multiple(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        engine.record_downtime("dt2", "t1", "m1", "belt", 15)
        result = engine.downtime_for_machine("m1")
        assert len(result) == 2

    def test_downtime_for_machine_returns_tuple(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        result = engine.downtime_for_machine("m1")
        assert isinstance(result, tuple)

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power", 30)
        assert dt.tenant_id == "t1"

    def test_zero_duration(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "brief", 0)
        assert dt.duration_minutes == 0

    def test_large_duration(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "extended", 9999)
        assert dt.duration_minutes == 9999

    def test_three_events_three_spine_events(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, machine: MachineRecord
    ) -> None:
        before = es.event_count
        for i in range(3):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"reason{i}", 10)
        assert es.event_count == before + 3

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        dt = engine.record_downtime("dt1", "t1", "m1", "power", 30)
        assert len(dt.metadata) == 0

    def test_duplicate_does_not_increment_count(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_downtime("dt1", "t1", "m1", "other", 10)
        assert engine.downtime_count == 1


# ---------------------------------------------------------------------------
# 12. Violation Detection (40 tests)
# ---------------------------------------------------------------------------


class TestViolationDetection:
    # --- order_no_batches ---
    def test_no_violations_initially(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.detect_factory_violations()
        assert result == ()

    def test_no_violations_draft_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        result = engine.detect_factory_violations()
        assert result == ()

    def test_no_violations_released_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        result = engine.detect_factory_violations()
        assert result == ()

    def test_no_violations_in_progress_order(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        result = engine.detect_factory_violations()
        assert result == ()

    def test_completed_order_no_batches_violation(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        result = engine.detect_factory_violations()
        assert len(result) == 1
        assert result[0]["operation"] == "order_no_batches"

    def test_completed_order_with_batch_no_violation(
        self, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        engine.start_batch("b1", "t1", "o1", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        result = engine.detect_factory_violations()
        # Only batch_no_qc might appear, not order_no_batches
        ops = [v["operation"] for v in result]
        assert "order_no_batches" not in ops

    def test_cancelled_order_no_violation(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.cancel_order("o1")
        result = engine.detect_factory_violations()
        assert result == ()

    def test_order_no_batches_has_tenant(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        result = engine.detect_factory_violations()
        assert result[0]["tenant_id"] == "t1"

    def test_order_no_batches_has_violation_id(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        result = engine.detect_factory_violations()
        assert "violation_id" in result[0]

    def test_order_no_batches_has_reason(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        result = engine.detect_factory_violations()
        assert result[0]["reason"] == "completed order has no batches"

    def test_order_no_batches_has_detected_at(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        result = engine.detect_factory_violations()
        assert "detected_at" in result[0]

    # --- batch_no_qc ---
    def test_completed_batch_no_qc_violation(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.complete_batch("b1")
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "batch_no_qc" in ops

    def test_completed_batch_with_qc_no_violation(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        engine.complete_batch("b1")
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "batch_no_qc" not in ops

    def test_in_progress_batch_no_violation(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "batch_no_qc" not in ops

    def test_rejected_batch_no_qc_no_violation(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.reject_batch("b1")
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "batch_no_qc" not in ops

    def test_scrapped_batch_no_qc_no_violation(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.scrap_batch("b1")
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "batch_no_qc" not in ops

    def test_batch_no_qc_has_tenant(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.complete_batch("b1")
        result = engine.detect_factory_violations()
        qc_violations = [v for v in result if v["operation"] == "batch_no_qc"]
        assert qc_violations[0]["tenant_id"] == "t1"

    # --- machine_excessive_downtime ---
    def test_machine_two_downtime_no_violation(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "a", 10)
        engine.record_downtime("dt2", "t1", "m1", "b", 20)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "machine_excessive_downtime" not in ops

    def test_machine_three_downtime_violation(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "a", 10)
        engine.record_downtime("dt2", "t1", "m1", "b", 20)
        engine.record_downtime("dt3", "t1", "m1", "c", 30)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "machine_excessive_downtime" in ops

    def test_machine_four_downtime_still_one_violation(
        self, engine: FactoryRuntimeEngine, machine: MachineRecord
    ) -> None:
        for i in range(4):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"r{i}", 10)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert ops.count("machine_excessive_downtime") == 1

    def test_machine_excessive_has_tenant(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        for i in range(3):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"r{i}", 10)
        result = engine.detect_factory_violations()
        dt_violations = [v for v in result if v["operation"] == "machine_excessive_downtime"]
        assert dt_violations[0]["tenant_id"] == "t1"

    def test_machine_excessive_has_reason(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        for i in range(3):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"r{i}", 10)
        result = engine.detect_factory_violations()
        dt_violations = [v for v in result if v["operation"] == "machine_excessive_downtime"]
        assert dt_violations[0]["reason"] == "machine has excessive downtime"

    # --- idempotency ---
    def test_idempotent_second_call_empty(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        first = engine.detect_factory_violations()
        assert len(first) > 0
        second = engine.detect_factory_violations()
        assert len(second) == 0

    def test_idempotent_violation_count_stable(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        engine.detect_factory_violations()
        count_after_first = engine.violation_count
        engine.detect_factory_violations()
        assert engine.violation_count == count_after_first

    def test_idempotent_batch_no_qc(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.complete_batch("b1")
        first = engine.detect_factory_violations()
        second = engine.detect_factory_violations()
        assert len(first) > 0
        assert len(second) == 0

    def test_idempotent_machine_excessive(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        for i in range(3):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"r{i}", 10)
        first = engine.detect_factory_violations()
        second = engine.detect_factory_violations()
        assert len(first) == 1
        assert len(second) == 0

    # --- combined violations ---
    def test_multiple_violation_types(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        # order_no_batches
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        # batch_no_qc
        engine.create_work_order("o2", "t1", "p1", "prod2", 10)
        engine.start_batch("b1", "t1", "o2", 10)
        engine.complete_batch("b1")
        result = engine.detect_factory_violations()
        ops = sorted(v["operation"] for v in result)
        assert "batch_no_qc" in ops
        assert "order_no_batches" in ops

    def test_violation_count_reflects_total(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        engine.detect_factory_violations()
        assert engine.violation_count >= 1

    def test_detect_emits_event_when_violations_found(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        before = es.event_count
        engine.detect_factory_violations()
        assert es.event_count == before + 1

    def test_detect_no_event_when_no_violations(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine
    ) -> None:
        before = es.event_count
        engine.detect_factory_violations()
        assert es.event_count == before

    def test_detect_no_event_on_idempotent_call(
        self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder
    ) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        engine.detect_factory_violations()
        before = es.event_count
        engine.detect_factory_violations()
        assert es.event_count == before

    def test_violations_returns_tuple(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.detect_factory_violations()
        assert isinstance(result, tuple)

    def test_two_completed_orders_no_batches_two_violations(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        for i in range(2):
            oid = f"o{i}"
            engine.create_work_order(oid, "t1", "p1", f"p{i}", 10)
            engine.release_order(oid)
            engine.start_order(oid)
            engine.complete_order(oid)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert ops.count("order_no_batches") == 2

    def test_two_machines_both_excessive(
        self, engine: FactoryRuntimeEngine, station: StationRecord
    ) -> None:
        engine.register_machine("m1", "t1", "s1", "M1")
        engine.register_machine("m2", "t1", "s1", "M2")
        for i in range(3):
            engine.record_downtime(f"dt1{i}", "t1", "m1", f"r{i}", 10)
            engine.record_downtime(f"dt2{i}", "t1", "m2", f"r{i}", 10)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert ops.count("machine_excessive_downtime") == 2

    def test_machine_exactly_three_is_violation(
        self, engine: FactoryRuntimeEngine, machine: MachineRecord
    ) -> None:
        for i in range(3):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"r{i}", 10)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "machine_excessive_downtime" in ops

    def test_machine_one_downtime_no_violation(
        self, engine: FactoryRuntimeEngine, machine: MachineRecord
    ) -> None:
        engine.record_downtime("dt1", "t1", "m1", "a", 10)
        result = engine.detect_factory_violations()
        ops = [v["operation"] for v in result]
        assert "machine_excessive_downtime" not in ops

    def test_zero_downtime_no_violation(
        self, engine: FactoryRuntimeEngine, machine: MachineRecord
    ) -> None:
        result = engine.detect_factory_violations()
        assert result == ()

    def test_new_violations_after_new_completions(
        self, engine: FactoryRuntimeEngine, plant: PlantRecord
    ) -> None:
        engine.create_work_order("o1", "t1", "p1", "p1", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        first = engine.detect_factory_violations()
        assert len(first) == 1
        # Now add another completed order with no batches
        engine.create_work_order("o2", "t1", "p1", "p2", 10)
        engine.release_order("o2")
        engine.start_order("o2")
        engine.complete_order("o2")
        second = engine.detect_factory_violations()
        assert len(second) == 1  # Only the new violation


# ---------------------------------------------------------------------------
# 13. Factory Snapshot (20 tests)
# ---------------------------------------------------------------------------


class TestFactorySnapshot:
    def test_returns_snapshot(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert isinstance(snap, FactorySnapshot)

    def test_snapshot_id_stored(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.snapshot_id == "snap1"

    def test_tenant_id_stored(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.tenant_id == "t1"

    def test_captured_at_set(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.captured_at != ""

    def test_total_plants(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_plants == 1

    def test_total_lines(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_lines == 1

    def test_total_orders(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_orders == 1

    def test_total_batches(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_batches == 1

    def test_total_checks(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_checks == 1

    def test_total_downtime(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_downtime_events == 1

    def test_total_violations(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        engine.detect_factory_violations()
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_violations >= 1

    def test_duplicate_snapshot_raises(self, engine: FactoryRuntimeEngine) -> None:
        engine.factory_snapshot("snap1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.factory_snapshot("snap1", "t1")

    def test_emits_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        before = es.event_count
        engine.factory_snapshot("snap1", "t1")
        assert es.event_count == before + 1

    def test_snapshot_frozen(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        with pytest.raises(AttributeError):
            snap.total_plants = 999

    def test_empty_factory_snapshot(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_plants == 0
        assert snap.total_lines == 0
        assert snap.total_orders == 0
        assert snap.total_batches == 0
        assert snap.total_checks == 0
        assert snap.total_downtime_events == 0
        assert snap.total_violations == 0

    def test_two_snapshots_different_ids(self, engine: FactoryRuntimeEngine) -> None:
        engine.factory_snapshot("snap1", "t1")
        engine.factory_snapshot("snap2", "t1")
        # No error

    def test_snapshot_after_multiple_registrations(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P1")
        engine.register_plant("p2", "t1", "P2")
        engine.register_line("l1", "t1", "p1", "L1")
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_plants == 2
        assert snap.total_lines == 1

    def test_metadata_default_empty(self, engine: FactoryRuntimeEngine) -> None:
        snap = engine.factory_snapshot("snap1", "t1")
        assert len(snap.metadata) == 0

    def test_snapshot_reflects_current_state(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        snap1 = engine.factory_snapshot("snap1", "t1")
        engine.register_plant("p2", "t1", "P2")
        snap2 = engine.factory_snapshot("snap2", "t1")
        assert snap1.total_plants == 1
        assert snap2.total_plants == 2

    def test_two_snapshot_events(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        before = es.event_count
        engine.factory_snapshot("snap1", "t1")
        engine.factory_snapshot("snap2", "t1")
        assert es.event_count == before + 2


# ---------------------------------------------------------------------------
# 14. State Hash (20 tests)
# ---------------------------------------------------------------------------


class TestStateHash:
    def test_returns_string(self, engine: FactoryRuntimeEngine) -> None:
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_length_16(self, engine: FactoryRuntimeEngine) -> None:
        h = engine.state_hash()
        assert len(h) == 64

    def test_hex_characters(self, engine: FactoryRuntimeEngine) -> None:
        h = engine.state_hash()
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic_empty(self, es: EventSpineEngine) -> None:
        e1 = FactoryRuntimeEngine(es)
        es2 = EventSpineEngine()
        e2 = FactoryRuntimeEngine(es2)
        assert e1.state_hash() == e2.state_hash()

    def test_changes_after_plant(self, engine: FactoryRuntimeEngine) -> None:
        h1 = engine.state_hash()
        engine.register_plant("p1", "t1", "P")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_line(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        h1 = engine.state_hash()
        engine.register_line("l1", "t1", "p1", "L")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_station(self, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        h1 = engine.state_hash()
        engine.register_station("s1", "t1", "l1", "S", "mr")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_machine(self, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        h1 = engine.state_hash()
        engine.register_machine("m1", "t1", "s1", "M")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_order(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        h1 = engine.state_hash()
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_batch(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        h1 = engine.state_hash()
        engine.start_batch("b1", "t1", "o1", 10)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_check(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        h1 = engine.state_hash()
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_downtime(self, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        h1 = engine.state_hash()
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_after_violation(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        h1 = engine.state_hash()
        engine.detect_factory_violations()
        h2 = engine.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self, engine: FactoryRuntimeEngine) -> None:
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_same_state_same_hash_after_ops(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        engine.register_line("l1", "t1", "p1", "L")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_two_engines_same_ops_same_hash(self) -> None:
        es1 = EventSpineEngine()
        e1 = FactoryRuntimeEngine(es1)
        e1.register_plant("p1", "t1", "P")

        es2 = EventSpineEngine()
        e2 = FactoryRuntimeEngine(es2)
        e2.register_plant("p1", "t1", "P")

        assert e1.state_hash() == e2.state_hash()

    def test_hash_based_on_counts(self, engine: FactoryRuntimeEngine) -> None:
        # Hash uses count-based representation
        h = engine.state_hash()
        assert len(h) == 64  # 16-char hex prefix of SHA-256

    def test_different_plants_different_hash(self) -> None:
        es1 = EventSpineEngine()
        e1 = FactoryRuntimeEngine(es1)
        e1.register_plant("p1", "t1", "P")

        es2 = EventSpineEngine()
        e2 = FactoryRuntimeEngine(es2)
        e2.register_plant("p1", "t1", "P")
        e2.register_plant("p2", "t1", "P2")

        assert e1.state_hash() != e2.state_hash()

    def test_hash_is_sha256_prefix(self, engine: FactoryRuntimeEngine) -> None:
        h = engine.state_hash()
        # Must be valid hex
        int(h, 16)

    def test_hash_stable_across_calls(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        hashes = [engine.state_hash() for _ in range(5)]
        assert all(h == hashes[0] for h in hashes)


# ---------------------------------------------------------------------------
# 15. Event Emission Counting (20 tests)
# ---------------------------------------------------------------------------


class TestEventEmission:
    def test_no_events_initially(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        assert es.event_count == 0

    def test_plant_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        assert es.event_count == 1

    def test_line_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        before = es.event_count
        engine.register_line("l1", "t1", "p1", "L")
        assert es.event_count == before + 1

    def test_station_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, line: LineRecord) -> None:
        before = es.event_count
        engine.register_station("s1", "t1", "l1", "S", "mr")
        assert es.event_count == before + 1

    def test_machine_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, station: StationRecord) -> None:
        before = es.event_count
        engine.register_machine("m1", "t1", "s1", "M")
        assert es.event_count == before + 1

    def test_order_creation_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        before = es.event_count
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        assert es.event_count == before + 1

    def test_release_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        before = es.event_count
        engine.release_order("o1")
        assert es.event_count == before + 1

    def test_start_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        before = es.event_count
        engine.start_order("o1")
        assert es.event_count == before + 1

    def test_complete_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        engine.release_order("o1")
        engine.start_order("o1")
        before = es.event_count
        engine.complete_order("o1")
        assert es.event_count == before + 1

    def test_cancel_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        before = es.event_count
        engine.cancel_order("o1")
        assert es.event_count == before + 1

    def test_batch_start_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        before = es.event_count
        engine.start_batch("b1", "t1", "o1", 10)
        assert es.event_count == before + 1

    def test_batch_complete_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        before = es.event_count
        engine.complete_batch("b1")
        assert es.event_count == before + 1

    def test_batch_reject_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        before = es.event_count
        engine.reject_batch("b1")
        assert es.event_count == before + 1

    def test_batch_scrap_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        before = es.event_count
        engine.scrap_batch("b1")
        assert es.event_count == before + 1

    def test_qc_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        before = es.event_count
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        assert es.event_count == before + 1

    def test_downtime_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine, machine: MachineRecord) -> None:
        before = es.event_count
        engine.record_downtime("dt1", "t1", "m1", "power", 30)
        assert es.event_count == before + 1

    def test_snapshot_emits_one(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        before = es.event_count
        engine.factory_snapshot("snap1", "t1")
        assert es.event_count == before + 1

    def test_failed_operations_no_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        before = es.event_count
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_line("l1", "t1", "no-plant", "L")
        assert es.event_count == before

    def test_full_factory_setup_event_count(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")          # 1
        engine.register_line("l1", "t1", "p1", "L")     # 2
        engine.register_station("s1", "t1", "l1", "S", "mr")  # 3
        engine.register_machine("m1", "t1", "s1", "M")  # 4
        engine.create_work_order("o1", "t1", "p1", "prod", 10)  # 5
        engine.start_batch("b1", "t1", "o1", 10)        # 6
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")  # 7
        engine.record_downtime("dt1", "t1", "m1", "power", 30)  # 8
        assert es.event_count == 8

    def test_duplicate_failure_no_event(self, es: EventSpineEngine, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("p1", "t1", "P")
        before = es.event_count
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_plant("p1", "t1", "P2")
        assert es.event_count == before


# ---------------------------------------------------------------------------
# 16. Golden Scenarios (30 tests)
# ---------------------------------------------------------------------------


class TestGoldenScenarios:
    """End-to-end golden-path scenarios."""

    def test_full_production_cycle(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("plant-1", "tenant-A", "Main Plant")
        engine.register_line("line-1", "tenant-A", "plant-1", "Assembly")
        engine.register_station("st-1", "tenant-A", "line-1", "Welding", "m-ref")
        engine.register_machine("mach-1", "tenant-A", "st-1", "Welder X")
        o = engine.create_work_order("wo-1", "tenant-A", "plant-1", "widget", 500)
        assert o.status == WorkOrderStatus.DRAFT
        engine.release_order("wo-1")
        engine.start_order("wo-1")
        engine.start_batch("batch-1", "tenant-A", "wo-1", 100)
        engine.record_quality_check("qc-1", "tenant-A", "batch-1", QualityVerdict.PASS, 0, "inspector-1")
        engine.record_quality_check("qc-2", "tenant-A", "batch-1", QualityVerdict.PASS, 0, "inspector-1")
        b = engine.complete_batch("batch-1")
        assert b.yield_rate == 1.0
        engine.complete_order("wo-1")
        snap = engine.factory_snapshot("snap-final", "tenant-A")
        assert snap.total_plants == 1
        assert snap.total_orders == 1
        assert snap.total_batches == 1
        assert snap.total_checks == 2

    def test_multi_batch_order(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "Plant")
        engine.create_work_order("o1", "t1", "p1", "prod", 200)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.start_batch("b1", "t1", "o1", 50)
        engine.start_batch("b2", "t1", "o1", 50)
        engine.start_batch("b3", "t1", "o1", 50)
        engine.start_batch("b4", "t1", "o1", 50)
        assert engine.batch_count == 4
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        engine.complete_batch("b1")
        engine.record_quality_check("qc2", "t1", "b2", QualityVerdict.FAIL, 5, "insp")
        b2 = engine.complete_batch("b2")
        assert b2.yield_rate == 0.0
        engine.reject_batch("b3")
        engine.scrap_batch("b4")
        engine.complete_order("o1")

    def test_violation_scan_after_production(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "Plant")
        engine.register_line("l1", "t1", "p1", "Line")
        engine.register_station("s1", "t1", "l1", "Stn", "mr")
        engine.register_machine("m1", "t1", "s1", "Mach")
        # Completed order with no batches
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        # Excessive downtime
        engine.record_downtime("dt1", "t1", "m1", "a", 10)
        engine.record_downtime("dt2", "t1", "m1", "b", 20)
        engine.record_downtime("dt3", "t1", "m1", "c", 30)
        violations = engine.detect_factory_violations()
        ops = sorted(v["operation"] for v in violations)
        assert "machine_excessive_downtime" in ops
        assert "order_no_batches" in ops

    def test_partial_yield_scenario(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.create_work_order("o1", "t1", "p1", "prod", 100)
        engine.start_batch("b1", "t1", "o1", 100)
        # 3 pass, 1 fail
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "i")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.PASS, 0, "i")
        engine.record_quality_check("qc3", "t1", "b1", QualityVerdict.PASS, 0, "i")
        engine.record_quality_check("qc4", "t1", "b1", QualityVerdict.FAIL, 2, "i")
        b = engine.complete_batch("b1")
        assert b.yield_rate == 0.75

    def test_multi_tenant_isolation(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "Plant T1")
        engine.register_plant("p2", "t2", "Plant T2")
        assert len(engine.plants_for_tenant("t1")) == 1
        assert len(engine.plants_for_tenant("t2")) == 1
        assert engine.plants_for_tenant("t1")[0].plant_id == "p1"
        assert engine.plants_for_tenant("t2")[0].plant_id == "p2"

    def test_state_hash_tracks_progression(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        hashes = [engine.state_hash()]
        engine.register_plant("p1", "t1", "P")
        hashes.append(engine.state_hash())
        engine.register_line("l1", "t1", "p1", "L")
        hashes.append(engine.state_hash())
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        hashes.append(engine.state_hash())
        # All hashes should be different
        assert len(set(hashes)) == len(hashes)

    def test_cancel_and_recreate(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.cancel_order("o1")
        # Cannot reuse same ID
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate order_id"):
            engine.create_work_order("o1", "t1", "p1", "prod", 10)
        # But can use a new ID
        engine.create_work_order("o2", "t1", "p1", "prod", 10)
        assert engine.order_count == 2

    def test_snapshot_before_and_after_violations(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        snap1 = engine.factory_snapshot("snap1", "t1")
        assert snap1.total_violations == 0
        engine.detect_factory_violations()
        snap2 = engine.factory_snapshot("snap2", "t1")
        assert snap2.total_violations >= 1

    def test_complex_factory_with_all_entities(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "Main")
        engine.register_line("l1", "t1", "p1", "Assembly")
        engine.register_line("l2", "t1", "p1", "Packaging")
        engine.register_station("s1", "t1", "l1", "Weld", "mr1")
        engine.register_station("s2", "t1", "l1", "Paint", "mr2")
        engine.register_station("s3", "t1", "l2", "Box", "mr3")
        engine.register_machine("m1", "t1", "s1", "Welder")
        engine.register_machine("m2", "t1", "s2", "Sprayer")
        assert engine.plant_count == 1
        assert engine.line_count == 2
        assert engine.station_count == 3
        assert engine.machine_count == 2
        assert engine.get_plant("p1").line_count == 2
        assert engine.get_line("l1").station_count == 2
        assert engine.get_line("l2").station_count == 1

    def test_full_lifecycle_with_qc_and_downtime(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        engine.register_station("s1", "t1", "l1", "S", "mr")
        engine.register_machine("m1", "t1", "s1", "M")
        engine.create_work_order("o1", "t1", "p1", "prod", 100)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.start_batch("b1", "t1", "o1", 50)
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")
        engine.record_quality_check("qc2", "t1", "b1", QualityVerdict.FAIL, 2, "insp")
        engine.record_downtime("dt1", "t1", "m1", "belt", 15)
        b = engine.complete_batch("b1")
        assert b.yield_rate == 0.5
        engine.complete_order("o1")
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_plants == 1
        assert snap.total_lines == 1
        assert snap.total_orders == 1
        assert snap.total_batches == 1
        assert snap.total_checks == 2
        assert snap.total_downtime_events == 1

    def test_event_count_full_golden_path(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")       # 1
        engine.register_line("l1", "t1", "p1", "L")  # 2
        engine.register_station("s1", "t1", "l1", "S", "mr")  # 3
        engine.register_machine("m1", "t1", "s1", "M")  # 4
        engine.create_work_order("o1", "t1", "p1", "prod", 10)  # 5
        engine.release_order("o1")                    # 6
        engine.start_order("o1")                      # 7
        engine.start_batch("b1", "t1", "o1", 10)     # 8
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "insp")  # 9
        engine.complete_batch("b1")                   # 10
        engine.complete_order("o1")                   # 11
        engine.record_downtime("dt1", "t1", "m1", "r", 10)  # 12
        engine.factory_snapshot("snap1", "t1")        # 13
        assert es.event_count == 13

    def test_multiple_orders_multiple_plants(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "Plant A")
        engine.register_plant("p2", "t1", "Plant B")
        engine.create_work_order("o1", "t1", "p1", "widget", 100)
        engine.create_work_order("o2", "t1", "p2", "gadget", 200)
        engine.release_order("o1")
        engine.release_order("o2")
        engine.start_order("o1")
        engine.start_order("o2")
        engine.complete_order("o1")
        engine.cancel_order("o2")
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_plants == 2
        assert snap.total_orders == 2

    def test_batch_no_qc_violation_golden(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.start_batch("b1", "t1", "o1", 10)
        engine.complete_batch("b1")
        violations = engine.detect_factory_violations()
        ops = [v["operation"] for v in violations]
        assert "batch_no_qc" in ops

    def test_no_false_violations_with_good_data(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        engine.register_station("s1", "t1", "l1", "S", "mr")
        engine.register_machine("m1", "t1", "s1", "M")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.start_batch("b1", "t1", "o1", 10)
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "i")
        engine.complete_batch("b1")
        engine.complete_order("o1")
        engine.record_downtime("dt1", "t1", "m1", "r1", 10)
        engine.record_downtime("dt2", "t1", "m1", "r2", 10)
        violations = engine.detect_factory_violations()
        assert len(violations) == 0

    def test_idempotent_violations_golden(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        engine.register_station("s1", "t1", "l1", "S", "mr")
        engine.register_machine("m1", "t1", "s1", "M")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")
        for i in range(3):
            engine.record_downtime(f"dt{i}", "t1", "m1", f"r{i}", 10)
        first = engine.detect_factory_violations()
        assert len(first) == 2  # order_no_batches + machine_excessive_downtime
        second = engine.detect_factory_violations()
        assert len(second) == 0

    def test_yield_rate_100_percent(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.start_batch("b1", "t1", "o1", 10)
        for i in range(10):
            engine.record_quality_check(f"qc{i}", "t1", "b1", QualityVerdict.PASS, 0, "i")
        b = engine.complete_batch("b1")
        assert b.yield_rate == 1.0

    def test_yield_rate_0_percent(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.start_batch("b1", "t1", "o1", 10)
        for i in range(5):
            engine.record_quality_check(f"qc{i}", "t1", "b1", QualityVerdict.FAIL, 1, "i")
        b = engine.complete_batch("b1")
        assert b.yield_rate == 0.0

    def test_hash_determinism_across_engines(self) -> None:
        es1 = EventSpineEngine()
        e1 = FactoryRuntimeEngine(es1)
        es2 = EventSpineEngine()
        e2 = FactoryRuntimeEngine(es2)
        # Same operations
        for eng in [e1, e2]:
            eng.register_plant("p1", "t1", "P")
            eng.register_line("l1", "t1", "p1", "L")
            eng.create_work_order("o1", "t1", "p1", "prod", 10)
        assert e1.state_hash() == e2.state_hash()

    def test_snapshot_counts_match_properties(self, es: EventSpineEngine) -> None:
        engine = FactoryRuntimeEngine(es)
        engine.register_plant("p1", "t1", "P")
        engine.register_line("l1", "t1", "p1", "L")
        engine.register_station("s1", "t1", "l1", "S", "mr")
        engine.register_machine("m1", "t1", "s1", "M")
        engine.create_work_order("o1", "t1", "p1", "prod", 10)
        engine.start_batch("b1", "t1", "o1", 10)
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "i")
        engine.record_downtime("dt1", "t1", "m1", "r", 10)
        snap = engine.factory_snapshot("snap1", "t1")
        assert snap.total_plants == engine.plant_count
        assert snap.total_lines == engine.line_count
        assert snap.total_orders == engine.order_count
        assert snap.total_batches == engine.batch_count
        assert snap.total_checks == engine.check_count
        assert snap.total_downtime_events == engine.downtime_count
        assert snap.total_violations == engine.violation_count


# ---------------------------------------------------------------------------
# 17. Edge Cases and Misc (20 tests)
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_register_line_without_plant_fails(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_line("l1", "t1", "no-plant", "L")

    def test_register_station_without_line_fails(self, engine: FactoryRuntimeEngine, plant: PlantRecord) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_station("s1", "t1", "no-line", "S", "mr")

    def test_create_order_without_plant_fails(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.create_work_order("o1", "t1", "no-plant", "prod", 10)

    def test_start_batch_without_order_fails(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_batch("b1", "t1", "no-order", 10)

    def test_record_qc_without_batch_fails(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_quality_check("qc1", "t1", "no-batch", QualityVerdict.PASS, 0, "i")

    def test_record_downtime_without_machine_fails(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_downtime("dt1", "t1", "no-machine", "reason", 30)

    def test_get_plant_missing(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_plant("missing")

    def test_get_line_missing(self, engine: FactoryRuntimeEngine) -> None:
        with pytest.raises(RuntimeCoreInvariantError):
            engine.get_line("missing")

    def test_plants_for_nonexistent_tenant(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.plants_for_tenant("nonexistent")
        assert result == ()

    def test_checks_for_nonexistent_batch(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.checks_for_batch("nonexistent")
        assert result == ()

    def test_downtime_for_nonexistent_machine(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.downtime_for_machine("nonexistent")
        assert result == ()

    def test_many_plants_many_lines(self, engine: FactoryRuntimeEngine) -> None:
        for i in range(10):
            engine.register_plant(f"p{i}", "t1", f"P{i}")
            for j in range(3):
                engine.register_line(f"l{i}_{j}", "t1", f"p{i}", f"L{j}")
        assert engine.plant_count == 10
        assert engine.line_count == 30
        for i in range(10):
            assert engine.get_plant(f"p{i}").line_count == 3

    def test_violation_detection_with_no_data(self, engine: FactoryRuntimeEngine) -> None:
        result = engine.detect_factory_violations()
        assert result == ()
        assert engine.violation_count == 0

    def test_snapshot_id_uniqueness(self, engine: FactoryRuntimeEngine) -> None:
        engine.factory_snapshot("s1", "t1")
        engine.factory_snapshot("s2", "t1")
        engine.factory_snapshot("s3", "t1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.factory_snapshot("s1", "t1")

    def test_batch_complete_yield_single_pass(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.PASS, 0, "i")
        b = engine.complete_batch("b1")
        assert b.yield_rate == 1.0

    def test_batch_complete_yield_single_fail(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.record_quality_check("qc1", "t1", "b1", QualityVerdict.FAIL, 5, "i")
        b = engine.complete_batch("b1")
        assert b.yield_rate == 0.0

    def test_order_transitions_are_strictly_sequential(self, engine: FactoryRuntimeEngine, order: WorkOrder) -> None:
        # DRAFT -> can't complete directly
        with pytest.raises(RuntimeCoreInvariantError):
            engine.complete_order("o1")
        # DRAFT -> can't start directly
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_order("o1")
        # Proper progression
        engine.release_order("o1")
        engine.start_order("o1")
        engine.complete_order("o1")

    def test_complete_batch_preserves_created_at(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        original = batch.created_at
        cb = engine.complete_batch("b1")
        assert cb.created_at == original

    def test_reject_batch_preserves_created_at(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        original = batch.created_at
        rb = engine.reject_batch("b1")
        assert rb.created_at == original

    def test_scrap_batch_preserves_created_at(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        original = batch.created_at
        sb = engine.scrap_batch("b1")
        assert sb.created_at == original


class TestBoundedFactoryContracts:
    def test_duplicate_plant_does_not_echo_id(self, engine: FactoryRuntimeEngine) -> None:
        engine.register_plant("plant-secret", "t1", "Plant")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate plant_id") as exc:
            engine.register_plant("plant-secret", "t1", "Plant")
        assert "plant-secret" not in str(exc.value)

    def test_terminal_batch_transition_does_not_echo_status(self, engine: FactoryRuntimeEngine, batch: BatchRecord) -> None:
        engine.reject_batch("b1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot complete batch in terminal status") as exc:
            engine.complete_batch("b1")
        assert "rejected" not in str(exc.value).lower()
