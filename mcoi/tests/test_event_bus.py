"""Phase 205D — Event bus tests."""

import pytest
from mcoi_runtime.core.event_bus import EventBus, GovernedEvent

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestEventBus:
    def test_publish(self):
        bus = EventBus(clock=FIXED_CLOCK)
        event = bus.publish("task.completed", tenant_id="t1", source="workflow", payload={"task_id": "t1"})
        assert event.event_type == "task.completed"
        assert event.tenant_id == "t1"
        assert event.event_hash

    def test_subscribe_receives(self):
        bus = EventBus(clock=FIXED_CLOCK)
        received = []
        bus.subscribe("task.completed", lambda e: received.append(e))
        bus.publish("task.completed", payload={"x": 1})
        assert len(received) == 1
        assert received[0].payload["x"] == 1

    def test_subscribe_filters_type(self):
        bus = EventBus(clock=FIXED_CLOCK)
        received = []
        bus.subscribe("task.completed", lambda e: received.append(e))
        bus.publish("task.failed", payload={})
        assert len(received) == 0

    def test_multiple_subscribers(self):
        bus = EventBus(clock=FIXED_CLOCK)
        log1, log2 = [], []
        bus.subscribe("x", lambda e: log1.append(e))
        bus.subscribe("x", lambda e: log2.append(e))
        bus.publish("x", payload={})
        assert len(log1) == 1
        assert len(log2) == 1

    def test_subscribe_all(self):
        bus = EventBus(clock=FIXED_CLOCK)
        received = []
        bus.subscribe_all(lambda e: received.append(e))
        bus.publish("a", payload={})
        bus.publish("b", payload={})
        assert len(received) == 2

    def test_error_isolation(self):
        bus = EventBus(clock=FIXED_CLOCK)
        good_log = []
        bus.subscribe("x", lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
        bus.subscribe("x", lambda e: good_log.append(e))
        bus.publish("x", payload={})
        assert len(good_log) == 1  # Good subscriber still called
        assert bus.error_count == 1

    def test_history(self):
        bus = EventBus(clock=FIXED_CLOCK)
        bus.publish("a", payload={})
        bus.publish("b", payload={})
        bus.publish("a", payload={})
        assert len(bus.history()) == 3
        assert len(bus.history(event_type="a")) == 2

    def test_event_count(self):
        bus = EventBus(clock=FIXED_CLOCK)
        assert bus.event_count == 0
        bus.publish("x", payload={})
        bus.publish("y", payload={})
        assert bus.event_count == 2

    def test_subscriber_count(self):
        bus = EventBus(clock=FIXED_CLOCK)
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        bus.subscribe_all(lambda e: None)
        assert bus.subscriber_count == 3

    def test_subscribed_types(self):
        bus = EventBus(clock=FIXED_CLOCK)
        bus.subscribe("b", lambda e: None)
        bus.subscribe("a", lambda e: None)
        assert bus.subscribed_types() == ["a", "b"]

    def test_summary(self):
        bus = EventBus(clock=FIXED_CLOCK)
        bus.publish("task.completed", payload={})
        bus.publish("task.completed", payload={})
        bus.publish("task.failed", payload={})
        summary = bus.summary()
        assert summary["total_events"] == 3
        assert summary["event_types"]["task.completed"] == 2

    def test_event_immutable(self):
        bus = EventBus(clock=FIXED_CLOCK)
        event = bus.publish("x", payload={"k": "v"})
        with pytest.raises(AttributeError):
            event.event_type = "y"
