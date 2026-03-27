"""Tests for Phase 231A — Governed Event Sourcing Engine."""
from __future__ import annotations
import pytest
from mcoi_runtime.core.event_sourcing import EventStore


class TestEventStore:
    def test_append_event(self):
        store = EventStore()
        event = store.append("order-1", "OrderCreated", {"amount": 100})
        assert event.stream_id == "order-1"
        assert event.sequence == 1
        assert event.data["amount"] == 100

    def test_sequence_increments(self):
        store = EventStore()
        e1 = store.append("s1", "A", {})
        e2 = store.append("s1", "B", {})
        assert e1.sequence == 1
        assert e2.sequence == 2

    def test_get_events(self):
        store = EventStore()
        store.append("s1", "A", {"v": 1})
        store.append("s1", "B", {"v": 2})
        events = store.get_events("s1")
        assert len(events) == 2

    def test_get_events_from_sequence(self):
        store = EventStore()
        store.append("s1", "A", {})
        store.append("s1", "B", {})
        store.append("s1", "C", {})
        events = store.get_events("s1", from_seq=1)
        assert len(events) == 2

    def test_stream_isolation(self):
        store = EventStore()
        store.append("s1", "A", {})
        store.append("s2", "B", {})
        assert store.get_stream_length("s1") == 1
        assert store.get_stream_length("s2") == 1

    def test_projection(self):
        store = EventStore()
        def counter_proj(state, event):
            state["count"] = state.get("count", 0) + 1
            return state
        store.register_projection("counter", counter_proj)
        store.append("s1", "A", {})
        store.append("s1", "B", {})
        proj = store.get_projection("counter", "s1")
        assert proj["count"] == 2

    def test_replay(self):
        store = EventStore()
        store.append("s1", "Add", {"amount": 10})
        store.append("s1", "Add", {"amount": 20})
        store.append("s1", "Sub", {"amount": 5})
        def reducer(state, event):
            total = state.get("total", 0)
            if event.event_type == "Add":
                total += event.data["amount"]
            elif event.event_type == "Sub":
                total -= event.data["amount"]
            return {"total": total}
        result = store.replay("s1", reducer)
        assert result["total"] == 25

    def test_empty_stream(self):
        store = EventStore()
        assert store.get_events("nonexistent") == []
        assert store.get_stream_length("nonexistent") == 0

    def test_summary(self):
        store = EventStore()
        store.append("s1", "A", {})
        store.append("s2", "B", {})
        s = store.summary()
        assert s["total_events"] == 2
        assert s["total_streams"] == 2
