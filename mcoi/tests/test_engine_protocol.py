"""Tests for the engine protocol, base classes, and clock implementations."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from mcoi_runtime.core.engine_protocol import (
    Clock,
    EngineBase,
    EngineProtocol,
    FixedClock,
    IntegrationBase,
    MonotonicClock,
    WallClock,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ===================================================================
# Clock tests
# ===================================================================


class TestWallClock:
    def test_returns_string(self):
        c = WallClock()
        assert isinstance(c.now_iso(), str)

    def test_is_iso_format(self):
        c = WallClock()
        t = c.now_iso()
        datetime.fromisoformat(t)  # should not raise

    def test_successive_calls_advance(self):
        c = WallClock()
        t1 = c.now_iso()
        t2 = c.now_iso()
        # Could be equal in fast execution, but should not go backward
        assert t2 >= t1

    def test_implements_clock_protocol(self):
        c = WallClock()
        assert isinstance(c, Clock)


class TestFixedClock:
    def test_returns_fixed_time(self):
        c = FixedClock("2026-06-15T12:00:00+00:00")
        assert c.now_iso() == "2026-06-15T12:00:00+00:00"

    def test_successive_calls_return_same(self):
        c = FixedClock("2026-06-15T12:00:00+00:00")
        t1 = c.now_iso()
        t2 = c.now_iso()
        assert t1 == t2

    def test_advance_changes_time(self):
        c = FixedClock("2026-01-01T00:00:00+00:00")
        c.advance("2026-12-31T23:59:59+00:00")
        assert c.now_iso() == "2026-12-31T23:59:59+00:00"

    def test_default_time(self):
        c = FixedClock()
        assert "2026-01-01" in c.now_iso()

    def test_implements_clock_protocol(self):
        c = FixedClock()
        assert isinstance(c, Clock)


class TestMonotonicClock:
    def test_advances_each_call(self):
        c = MonotonicClock("2026-01-01T00:00:00+00:00")
        t1 = c.now_iso()
        t2 = c.now_iso()
        assert t1 != t2
        assert t2 > t1

    def test_first_call_is_base_plus_one_second(self):
        c = MonotonicClock("2026-01-01T00:00:00+00:00")
        t = c.now_iso()
        assert "2026-01-01T00:00:01" in t

    def test_tenth_call_is_base_plus_ten_seconds(self):
        c = MonotonicClock("2026-01-01T00:00:00+00:00")
        for _ in range(10):
            t = c.now_iso()
        assert "2026-01-01T00:00:10" in t

    def test_implements_clock_protocol(self):
        c = MonotonicClock()
        assert isinstance(c, Clock)


# ===================================================================
# EngineBase tests
# ===================================================================


class ConcreteEngine(EngineBase):
    """Minimal concrete engine for testing."""

    def __init__(self, event_spine, clock=None):
        super().__init__(event_spine, clock)
        self._items: dict[str, str] = {}
        self._records: dict[str, str] = {}

    def _collections(self):
        return {"items": self._items, "records": self._records}

    def add_item(self, key: str, value: str) -> None:
        self._items[key] = value

    def add_record(self, key: str, value: str) -> None:
        self._records[key] = value


class TestEngineBase:
    def test_rejects_non_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ConcreteEngine("not_an_engine")

    def test_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ConcreteEngine(None)

    def test_accepts_event_spine(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        assert eng is not None

    def test_default_wall_clock(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        assert isinstance(eng._clock, WallClock)

    def test_injected_fixed_clock(self):
        es = EventSpineEngine()
        fc = FixedClock("2026-06-01T00:00:00+00:00")
        eng = ConcreteEngine(es, clock=fc)
        assert eng._now() == "2026-06-01T00:00:00+00:00"

    def test_injected_monotonic_clock(self):
        es = EventSpineEngine()
        mc = MonotonicClock("2026-01-01T00:00:00+00:00")
        eng = ConcreteEngine(es, clock=mc)
        t1 = eng._now()
        t2 = eng._now()
        assert t1 != t2

    def test_state_hash_empty(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_state_hash_deterministic(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        eng.add_item("a", "1")
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_mutation(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        h1 = eng.state_hash()
        eng.add_item("a", "1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_state_hash_changes_on_different_collection(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        eng.add_item("a", "1")
        h1 = eng.state_hash()
        eng.add_record("b", "2")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_snapshot_empty(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        snap = eng.snapshot()
        assert isinstance(snap, dict)
        assert snap["items"] == {}
        assert snap["records"] == {}
        assert "_state_hash" in snap

    def test_snapshot_with_data(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        eng.add_item("a", "1")
        eng.add_record("b", "2")
        snap = eng.snapshot()
        assert snap["items"] == {"a": "1"}
        assert snap["records"] == {"b": "2"}

    def test_snapshot_hash_matches_state_hash(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        eng.add_item("a", "1")
        snap = eng.snapshot()
        assert snap["_state_hash"] == eng.state_hash()

    def test_event_spine_property(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        assert eng.event_spine is es

    def test_collections_returns_all(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        cols = eng._collections()
        assert "items" in cols
        assert "records" in cols


# ===================================================================
# IntegrationBase tests
# ===================================================================


class TestIntegrationBase:
    def test_rejects_wrong_engine_type(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            IntegrationBase("bad", ConcreteEngine, es, mm)

    def test_rejects_wrong_event_spine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = ConcreteEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            IntegrationBase(eng, ConcreteEngine, "bad", mm)

    def test_rejects_wrong_memory_engine(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            IntegrationBase(eng, ConcreteEngine, es, "bad")

    def test_accepts_valid_args(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = ConcreteEngine(es)
        bridge = IntegrationBase(eng, ConcreteEngine, es, mm)
        assert bridge._engine is eng
        assert bridge._events is es
        assert bridge._memory is mm

    def test_rejects_none_engine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            IntegrationBase(None, ConcreteEngine, es, mm)

    def test_rejects_none_event_spine(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        eng = ConcreteEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            IntegrationBase(eng, ConcreteEngine, None, mm)

    def test_rejects_none_memory(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            IntegrationBase(eng, ConcreteEngine, es, None)


# ===================================================================
# EngineProtocol tests
# ===================================================================


class TestEngineProtocol:
    def test_concrete_engine_has_state_hash(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        assert hasattr(eng, "state_hash")
        assert callable(eng.state_hash)

    def test_concrete_engine_has_snapshot(self):
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        assert hasattr(eng, "snapshot")
        assert callable(eng.snapshot)

    def test_raw_dict_does_not_implement(self):
        assert not isinstance({}, EngineProtocol)

    def test_string_does_not_implement(self):
        assert not isinstance("hello", EngineProtocol)


# ===================================================================
# Replay determinism with clocks
# ===================================================================


class TestReplayDeterminism:
    def test_two_engines_same_clock_same_hash(self):
        """Two engines with the same fixed clock produce the same state hash."""
        es1 = EventSpineEngine()
        es2 = EventSpineEngine()
        fc1 = FixedClock("2026-01-01T00:00:00+00:00")
        fc2 = FixedClock("2026-01-01T00:00:00+00:00")
        eng1 = ConcreteEngine(es1, clock=fc1)
        eng2 = ConcreteEngine(es2, clock=fc2)

        eng1.add_item("x", "1")
        eng2.add_item("x", "1")

        assert eng1.state_hash() == eng2.state_hash()

    def test_snapshot_roundtrip_preserves_hash(self):
        """Snapshot captures hash that can be verified after restore."""
        es = EventSpineEngine()
        eng = ConcreteEngine(es)
        eng.add_item("a", "1")
        eng.add_record("b", "2")
        snap = eng.snapshot()
        original_hash = snap["_state_hash"]

        # Create new engine, add same data
        es2 = EventSpineEngine()
        eng2 = ConcreteEngine(es2)
        eng2.add_item("a", "1")
        eng2.add_record("b", "2")

        assert eng2.state_hash() == original_hash
