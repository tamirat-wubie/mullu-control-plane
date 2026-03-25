"""Purpose: verify event spine contracts — EventRecord, EventEnvelope, EventSubscription,
EventReaction, EventWindow, EventCorrelation.
Governance scope: event plane contract tests only.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.event import (
    EventCorrelation,
    EventEnvelope,
    EventReaction,
    EventRecord,
    EventSource,
    EventSubscription,
    EventType,
    EventWindow,
)


_CLOCK = "2026-03-20T00:00:00+00:00"


def _event(eid: str = "evt-1") -> EventRecord:
    return EventRecord(
        event_id=eid,
        event_type=EventType.JOB_STATE_TRANSITION,
        source=EventSource.JOB_RUNTIME,
        correlation_id="corr-1",
        payload={"job_id": "j-1", "from": "pending", "to": "running"},
        emitted_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# EventRecord
# ---------------------------------------------------------------------------

class TestEventRecord:
    def test_valid(self) -> None:
        e = _event()
        assert e.event_id == "evt-1"
        assert e.event_type == EventType.JOB_STATE_TRANSITION
        assert e.source == EventSource.JOB_RUNTIME

    def test_payload_frozen(self) -> None:
        e = _event()
        with pytest.raises(TypeError):
            e.payload["new_key"] = "val"  # type: ignore[index]

    def test_empty_event_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="event_id"):
            EventRecord(
                event_id="", event_type=EventType.CUSTOM,
                source=EventSource.EXTERNAL, correlation_id="c-1",
                payload={}, emitted_at=_CLOCK,
            )

    def test_invalid_event_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="event_type"):
            EventRecord(
                event_id="e-1", event_type="not_valid",  # type: ignore[arg-type]
                source=EventSource.EXTERNAL, correlation_id="c-1",
                payload={}, emitted_at=_CLOCK,
            )

    def test_frozen(self) -> None:
        e = _event()
        with pytest.raises(AttributeError):
            e.event_id = "changed"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        d = _event().to_dict()
        assert d["event_id"] == "evt-1"
        assert isinstance(d["payload"], dict)


# ---------------------------------------------------------------------------
# EventEnvelope
# ---------------------------------------------------------------------------

class TestEventEnvelope:
    def test_valid(self) -> None:
        env = EventEnvelope(
            envelope_id="env-1", event=_event(),
            target_subsystems=("job_runtime", "dashboard"),
            priority=1,
        )
        assert env.delivered is False
        assert len(env.target_subsystems) == 2

    def test_empty_targets_rejected(self) -> None:
        with pytest.raises(ValueError, match="target_subsystems"):
            EventEnvelope(
                envelope_id="env-1", event=_event(),
                target_subsystems=(), priority=0,
            )

    def test_negative_priority_rejected(self) -> None:
        with pytest.raises(ValueError, match="priority"):
            EventEnvelope(
                envelope_id="env-1", event=_event(),
                target_subsystems=("x",), priority=-1,
            )

    def test_delivered_at_validated(self) -> None:
        env = EventEnvelope(
            envelope_id="env-1", event=_event(),
            target_subsystems=("x",), priority=0,
            delivered=True, delivered_at=_CLOCK,
        )
        assert env.delivered_at == _CLOCK


# ---------------------------------------------------------------------------
# EventSubscription
# ---------------------------------------------------------------------------

class TestEventSubscription:
    def test_valid(self) -> None:
        sub = EventSubscription(
            subscription_id="sub-1",
            event_type=EventType.APPROVAL_REQUESTED,
            subscriber_id="obligation-runtime",
            reaction_id="create-obligation",
            created_at=_CLOCK,
        )
        assert sub.active is True
        assert sub.filter_source is None

    def test_with_filter_source(self) -> None:
        sub = EventSubscription(
            subscription_id="sub-1",
            event_type=EventType.INCIDENT_OPENED,
            subscriber_id="obligation-runtime",
            reaction_id="create-sla-obligation",
            filter_source=EventSource.INCIDENT_SYSTEM,
            created_at=_CLOCK,
        )
        assert sub.filter_source == EventSource.INCIDENT_SYSTEM

    def test_invalid_filter_source_rejected(self) -> None:
        with pytest.raises(ValueError, match="filter_source"):
            EventSubscription(
                subscription_id="sub-1",
                event_type=EventType.CUSTOM,
                subscriber_id="x",
                reaction_id="y",
                filter_source="bad",  # type: ignore[arg-type]
                created_at=_CLOCK,
            )


# ---------------------------------------------------------------------------
# EventReaction
# ---------------------------------------------------------------------------

class TestEventReaction:
    def test_valid(self) -> None:
        r = EventReaction(
            reaction_id="rx-1", event_id="evt-1",
            subscription_id="sub-1",
            action_taken="created obligation obl-1",
            result="success",
            reacted_at=_CLOCK,
        )
        assert r.reaction_id == "rx-1"

    def test_empty_action_rejected(self) -> None:
        with pytest.raises(ValueError, match="action_taken"):
            EventReaction(
                reaction_id="rx-1", event_id="evt-1",
                subscription_id="sub-1",
                action_taken="", result="ok",
                reacted_at=_CLOCK,
            )


# ---------------------------------------------------------------------------
# EventWindow
# ---------------------------------------------------------------------------

class TestEventWindow:
    def test_valid(self) -> None:
        w = EventWindow(
            window_id="win-1", correlation_id="corr-1",
            window_start=_CLOCK, window_end="2026-03-20T01:00:00+00:00",
            event_count=5,
        )
        assert w.event_count == 5

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="event_count"):
            EventWindow(
                window_id="win-1", correlation_id="corr-1",
                window_start=_CLOCK, window_end=_CLOCK,
                event_count=-1,
            )


# ---------------------------------------------------------------------------
# EventCorrelation
# ---------------------------------------------------------------------------

class TestEventCorrelation:
    def test_valid(self) -> None:
        c = EventCorrelation(
            correlation_id="corr-1",
            event_ids=("evt-1", "evt-2", "evt-3"),
            root_event_id="evt-1",
            description="job j-1 lifecycle",
            created_at=_CLOCK,
        )
        assert len(c.event_ids) == 3

    def test_empty_event_ids_rejected(self) -> None:
        with pytest.raises(ValueError, match="event_ids"):
            EventCorrelation(
                correlation_id="corr-1", event_ids=(),
                root_event_id="evt-1",
                description="test", created_at=_CLOCK,
            )

    def test_frozen(self) -> None:
        c = EventCorrelation(
            correlation_id="corr-1",
            event_ids=("evt-1",),
            root_event_id="evt-1",
            description="test", created_at=_CLOCK,
        )
        with pytest.raises(AttributeError):
            c.correlation_id = "changed"  # type: ignore[misc]
