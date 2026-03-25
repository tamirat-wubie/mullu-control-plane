"""Comprehensive tests for the DigitalTwinRuntimeEngine.

Tests cover: construction, twin model lifecycle, object registration, assembly
registration, state binding, state updates, telemetry binding, sync records,
health assessment, snapshots, closure reports, violation detection,
state_hash, and replay determinism.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.digital_twin_runtime import (
    TwinAssembly,
    TwinAssessment,
    TwinClosureReport,
    TwinModel,
    TwinObject,
    TwinObjectKind,
    TwinSnapshot,
    TwinStateDisposition,
    TwinStateRecord,
    TwinStatus,
    TwinSyncRecord,
    TwinSyncStatus,
    TwinTelemetryBinding,
    TwinViolation,
)
from mcoi_runtime.core.digital_twin_runtime import DigitalTwinRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es, clock):
    return DigitalTwinRuntimeEngine(es, clock=clock)


def _register_model(engine, model_id="m-1", tenant_id="t-1"):
    return engine.register_twin_model(model_id=model_id, tenant_id=tenant_id, display_name=f"Model {model_id}")


def _register_object(engine, object_id="o-1", tenant_id="t-1", model_ref="m-1",
                      kind=TwinObjectKind.MACHINE, parent_ref="root"):
    return engine.register_twin_object(
        object_id=object_id, tenant_id=tenant_id, model_ref=model_ref,
        kind=kind, display_name=f"Object {object_id}", parent_ref=parent_ref,
    )


# ===================================================================
# Construction Tests
# ===================================================================


class TestEngineConstruction:
    def test_valid_construction(self, es, clock):
        eng = DigitalTwinRuntimeEngine(es, clock=clock)
        assert eng.model_count == 0
        assert eng.object_count == 0

    def test_construction_without_clock(self, es):
        eng = DigitalTwinRuntimeEngine(es)
        assert eng.model_count == 0

    def test_invalid_event_spine_rejected(self, clock):
        with pytest.raises(RuntimeCoreInvariantError):
            DigitalTwinRuntimeEngine("not_es", clock=clock)

    def test_none_event_spine_rejected(self, clock):
        with pytest.raises(RuntimeCoreInvariantError):
            DigitalTwinRuntimeEngine(None, clock=clock)


# ===================================================================
# Twin Model Tests
# ===================================================================


class TestTwinModels:
    def test_register_model(self, engine):
        m = _register_model(engine)
        assert isinstance(m, TwinModel)
        assert m.status == TwinStatus.ACTIVE
        assert m.object_count == 0
        assert engine.model_count == 1

    def test_duplicate_model_rejected(self, engine):
        _register_model(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate model_id"):
            _register_model(engine)

    def test_multiple_models(self, engine):
        _register_model(engine, model_id="m-1")
        _register_model(engine, model_id="m-2")
        assert engine.model_count == 2


# ===================================================================
# Twin Object Tests
# ===================================================================


class TestTwinObjects:
    def test_register_object(self, engine):
        _register_model(engine)
        o = _register_object(engine)
        assert isinstance(o, TwinObject)
        assert o.state == TwinStateDisposition.NOMINAL
        assert engine.object_count == 1

    def test_register_object_increments_model_count(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        _register_object(engine, object_id="o-2")
        m = engine._get_model("m-1")
        assert m.object_count == 2

    def test_register_object_unknown_model_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown model_id"):
            _register_object(engine, model_ref="nonexistent")

    def test_duplicate_object_rejected(self, engine):
        _register_model(engine)
        _register_object(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate object_id"):
            _register_object(engine)

    def test_object_default_parent_ref(self, engine):
        _register_model(engine)
        o = _register_object(engine)
        assert o.parent_ref == "root"

    def test_object_custom_parent_ref(self, engine):
        _register_model(engine)
        o = _register_object(engine, parent_ref="site-1")
        assert o.parent_ref == "site-1"


# ===================================================================
# Twin Assembly Tests
# ===================================================================


class TestTwinAssemblies:
    def test_register_assembly(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        _register_object(engine, object_id="o-2")
        a = engine.register_twin_assembly(
            assembly_id="a-1", tenant_id="t-1",
            parent_object_ref="o-1", child_object_ref="o-2",
        )
        assert isinstance(a, TwinAssembly)
        assert a.depth >= 1
        assert engine.assembly_count == 1

    def test_duplicate_assembly_rejected(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        _register_object(engine, object_id="o-2")
        engine.register_twin_assembly(
            assembly_id="a-1", tenant_id="t-1",
            parent_object_ref="o-1", child_object_ref="o-2",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate assembly_id"):
            engine.register_twin_assembly(
                assembly_id="a-1", tenant_id="t-1",
                parent_object_ref="o-1", child_object_ref="o-2",
            )

    def test_assembly_unknown_parent_rejected(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-2")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown object_id"):
            engine.register_twin_assembly(
                assembly_id="a-1", tenant_id="t-1",
                parent_object_ref="nonexistent", child_object_ref="o-2",
            )

    def test_assembly_unknown_child_rejected(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown object_id"):
            engine.register_twin_assembly(
                assembly_id="a-1", tenant_id="t-1",
                parent_object_ref="o-1", child_object_ref="nonexistent",
            )


# ===================================================================
# State Binding Tests
# ===================================================================


class TestStateBinding:
    def test_bind_runtime_state(self, engine):
        _register_model(engine)
        _register_object(engine)
        rec = engine.bind_runtime_state(
            state_id="s-1", tenant_id="t-1", object_ref="o-1",
            disposition=TwinStateDisposition.WARNING, source_runtime="factory",
        )
        assert isinstance(rec, TwinStateRecord)
        assert rec.disposition == TwinStateDisposition.WARNING
        assert engine.state_count == 1

    def test_bind_state_updates_object(self, engine):
        _register_model(engine)
        _register_object(engine)
        engine.bind_runtime_state(
            state_id="s-1", tenant_id="t-1", object_ref="o-1",
            disposition=TwinStateDisposition.DEGRADED, source_runtime="factory",
        )
        obj = engine._get_object("o-1")
        assert obj.state == TwinStateDisposition.DEGRADED

    def test_bind_state_unknown_object_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown object_id"):
            engine.bind_runtime_state(
                state_id="s-1", tenant_id="t-1", object_ref="nonexistent",
                disposition=TwinStateDisposition.NOMINAL, source_runtime="factory",
            )

    def test_duplicate_state_rejected(self, engine):
        _register_model(engine)
        _register_object(engine)
        engine.bind_runtime_state(
            state_id="s-1", tenant_id="t-1", object_ref="o-1",
            disposition=TwinStateDisposition.NOMINAL, source_runtime="factory",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate state_id"):
            engine.bind_runtime_state(
                state_id="s-1", tenant_id="t-1", object_ref="o-1",
                disposition=TwinStateDisposition.NOMINAL, source_runtime="factory",
            )


# ===================================================================
# Update Twin State Tests
# ===================================================================


class TestUpdateTwinState:
    def test_update_state(self, engine):
        _register_model(engine)
        _register_object(engine)
        updated = engine.update_twin_state("o-1", TwinStateDisposition.CRITICAL)
        assert updated.state == TwinStateDisposition.CRITICAL

    def test_update_state_unknown_object_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown object_id"):
            engine.update_twin_state("nonexistent", TwinStateDisposition.NOMINAL)


# ===================================================================
# Telemetry Binding Tests
# ===================================================================


class TestTelemetryBinding:
    def test_bind_telemetry(self, engine):
        b = engine.bind_telemetry(
            binding_id="b-1", tenant_id="t-1", object_ref="o-1",
            telemetry_ref="tel-1", source_runtime="obs",
        )
        assert isinstance(b, TwinTelemetryBinding)
        assert engine.binding_count == 1

    def test_duplicate_binding_rejected(self, engine):
        engine.bind_telemetry(
            binding_id="b-1", tenant_id="t-1", object_ref="o-1",
            telemetry_ref="tel-1", source_runtime="obs",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate binding_id"):
            engine.bind_telemetry(
                binding_id="b-1", tenant_id="t-1", object_ref="o-1",
                telemetry_ref="tel-1", source_runtime="obs",
            )


# ===================================================================
# Sync Record Tests
# ===================================================================


class TestSyncRecords:
    def test_record_sync(self, engine):
        rec = engine.record_sync(
            sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
        )
        assert isinstance(rec, TwinSyncRecord)
        assert rec.status == TwinSyncStatus.SYNCED
        assert engine.sync_count == 1

    def test_record_sync_stale(self, engine):
        rec = engine.record_sync(
            sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
            status=TwinSyncStatus.STALE,
        )
        assert rec.status == TwinSyncStatus.STALE

    def test_duplicate_sync_rejected(self, engine):
        engine.record_sync(sync_id="sy-1", tenant_id="t-1", object_ref="o-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate sync_id"):
            engine.record_sync(sync_id="sy-1", tenant_id="t-1", object_ref="o-1")


# ===================================================================
# Assessment Tests
# ===================================================================


class TestAssessment:
    def test_assess_empty_tenant(self, engine):
        a = engine.assess_twin_health("as-1", "t-1")
        assert a.health_score == 1.0
        assert a.total_objects == 0

    def test_assess_all_nominal(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        _register_object(engine, object_id="o-2")
        a = engine.assess_twin_health("as-1", "t-1")
        assert a.health_score == 1.0
        assert a.total_nominal == 2
        assert a.total_degraded == 0

    def test_assess_partial_degraded(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        _register_object(engine, object_id="o-2")
        engine.update_twin_state("o-1", TwinStateDisposition.DEGRADED)
        a = engine.assess_twin_health("as-1", "t-1")
        assert a.health_score == 0.5
        assert a.total_nominal == 1
        assert a.total_degraded == 1

    def test_assess_multi_tenant_isolation(self, engine):
        _register_model(engine, model_id="m-1", tenant_id="t-1")
        _register_object(engine, object_id="o-1", tenant_id="t-1", model_ref="m-1")
        _register_model(engine, model_id="m-2", tenant_id="t-2")
        _register_object(engine, object_id="o-2", tenant_id="t-2", model_ref="m-2")
        a = engine.assess_twin_health("as-1", "t-1")
        assert a.total_objects == 1


# ===================================================================
# Snapshot Tests
# ===================================================================


class TestSnapshot:
    def test_snapshot_empty(self, engine):
        s = engine.twin_snapshot("snap-1", "t-1")
        assert s.total_models == 0
        assert s.total_objects == 0

    def test_snapshot_after_operations(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        _register_object(engine, object_id="o-2")
        engine.register_twin_assembly(
            assembly_id="a-1", tenant_id="t-1",
            parent_object_ref="o-1", child_object_ref="o-2",
        )
        s = engine.twin_snapshot("snap-1", "t-1")
        assert s.total_models == 1
        assert s.total_objects == 2
        assert s.total_assemblies == 1


# ===================================================================
# Closure Report Tests
# ===================================================================


class TestClosureReport:
    def test_closure_report(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        r = engine.twin_closure_report("r-1", "t-1")
        assert isinstance(r, TwinClosureReport)
        assert r.total_models == 1
        assert r.total_objects == 1


# ===================================================================
# Violation Detection Tests
# ===================================================================


class TestViolationDetection:
    def test_stale_sync_violation(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        engine.record_sync(
            sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
            status=TwinSyncStatus.STALE,
        )
        viols = engine.detect_twin_violations("t-1")
        assert len(viols) >= 1
        ops = [v.operation for v in viols]
        assert "stale_sync" in ops

    def test_diverged_sync_violation(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        engine.record_sync(
            sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
            status=TwinSyncStatus.DIVERGED,
        )
        viols = engine.detect_twin_violations("t-1")
        ops = [v.operation for v in viols]
        assert "stale_sync" in ops

    def test_missing_assembly_violation(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1", parent_ref="site-1")
        viols = engine.detect_twin_violations("t-1")
        ops = [v.operation for v in viols]
        assert "missing_assembly" in ops

    def test_degraded_no_state_violation(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        engine.update_twin_state("o-1", TwinStateDisposition.DEGRADED)
        viols = engine.detect_twin_violations("t-1")
        ops = [v.operation for v in viols]
        assert "degraded_no_state" in ops

    def test_no_violation_when_state_exists(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        engine.bind_runtime_state(
            state_id="s-1", tenant_id="t-1", object_ref="o-1",
            disposition=TwinStateDisposition.DEGRADED, source_runtime="factory",
        )
        viols = engine.detect_twin_violations("t-1")
        ops = [v.operation for v in viols]
        assert "degraded_no_state" not in ops

    def test_violations_idempotent(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        engine.record_sync(
            sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
            status=TwinSyncStatus.STALE,
        )
        viols1 = engine.detect_twin_violations("t-1")
        viols2 = engine.detect_twin_violations("t-1")
        assert len(viols1) >= 1
        assert len(viols2) == 0  # idempotent: already recorded

    def test_no_violations_clean_state(self, engine):
        _register_model(engine)
        _register_object(engine, object_id="o-1")
        engine.record_sync(
            sync_id="sy-1", tenant_id="t-1", object_ref="o-1",
            status=TwinSyncStatus.SYNCED,
        )
        viols = engine.detect_twin_violations("t-1")
        assert len(viols) == 0


# ===================================================================
# State Hash Tests
# ===================================================================


class TestStateHash:
    def test_state_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_mutation(self, engine):
        h1 = engine.state_hash()
        _register_model(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_length(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_full_snapshot(self, engine):
        _register_model(engine)
        snap = engine.snapshot()
        assert "_state_hash" in snap
        assert "models" in snap
        assert "objects" in snap


# ===================================================================
# Collections Tests
# ===================================================================


class TestCollections:
    def test_collections_empty(self, engine):
        c = engine._collections()
        assert "models" in c
        assert "objects" in c
        assert "assemblies" in c
        assert "states" in c
        assert "bindings" in c
        assert "syncs" in c
        assert "violations" in c

    def test_collections_sorted_keys(self, engine):
        c = engine._collections()
        keys = list(c.keys())
        assert keys == sorted(keys)


# ===================================================================
# Event Emission Tests
# ===================================================================


class TestEventEmission:
    def test_events_emitted_on_model_registration(self, es, engine):
        before = es.event_count
        _register_model(engine)
        assert es.event_count > before

    def test_events_emitted_on_object_registration(self, es, engine):
        _register_model(engine)
        before = es.event_count
        _register_object(engine)
        assert es.event_count > before

    def test_events_emitted_on_state_binding(self, es, engine):
        _register_model(engine)
        _register_object(engine)
        before = es.event_count
        engine.bind_runtime_state(
            state_id="s-1", tenant_id="t-1", object_ref="o-1",
            disposition=TwinStateDisposition.NOMINAL, source_runtime="factory",
        )
        assert es.event_count > before


# ===================================================================
# Replay Determinism Tests
# ===================================================================


class TestReplayDeterminism:
    def test_deterministic_replay(self, clock):
        es1 = EventSpineEngine()
        eng1 = DigitalTwinRuntimeEngine(es1, clock=clock)
        es2 = EventSpineEngine()
        eng2 = DigitalTwinRuntimeEngine(es2, clock=clock)

        for eng in (eng1, eng2):
            _register_model(eng, model_id="m-1")
            _register_object(eng, object_id="o-1", model_ref="m-1")
            _register_object(eng, object_id="o-2", model_ref="m-1")
            eng.register_twin_assembly(
                assembly_id="a-1", tenant_id="t-1",
                parent_object_ref="o-1", child_object_ref="o-2",
            )
            eng.bind_runtime_state(
                state_id="s-1", tenant_id="t-1", object_ref="o-1",
                disposition=TwinStateDisposition.WARNING, source_runtime="factory",
            )

        assert eng1.state_hash() == eng2.state_hash()
