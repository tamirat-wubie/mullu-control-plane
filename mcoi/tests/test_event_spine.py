"""Purpose: verify event spine engine — emit, subscribe, react, correlate, window.
Governance scope: event plane engine tests only.
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
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


_CLOCK = "2026-03-20T00:00:00+00:00"
_CLOCK_FN = lambda: _CLOCK  # noqa: E731


def _spine() -> EventSpineEngine:
    return EventSpineEngine(clock=_CLOCK_FN)


def _event(
    eid: str = "evt-1",
    etype: EventType = EventType.JOB_STATE_TRANSITION,
    source: EventSource = EventSource.JOB_RUNTIME,
    corr: str = "corr-1",
) -> EventRecord:
    return EventRecord(
        event_id=eid, event_type=etype, source=source,
        correlation_id=corr,
        payload={"detail": "test"},
        emitted_at=_CLOCK,
    )


def _subscription(
    sid: str = "sub-1",
    etype: EventType = EventType.JOB_STATE_TRANSITION,
    filter_source: EventSource | None = None,
) -> EventSubscription:
    return EventSubscription(
        subscription_id=sid,
        event_type=etype,
        subscriber_id="obligation-runtime",
        reaction_id="create-obligation",
        filter_source=filter_source,
        created_at=_CLOCK,
    )


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

class TestEmit:
    def test_emit(self) -> None:
        s = _spine()
        e = s.emit(_event())
        assert s.event_count == 1
        assert s.get_event("evt-1") is not None

    def test_duplicate_rejected(self) -> None:
        s = _spine()
        s.emit(_event())
        with pytest.raises(RuntimeCoreInvariantError, match="^event already exists$") as excinfo:
            s.emit(_event())
        assert "evt-1" not in str(excinfo.value)

    def test_emit_and_envelope(self) -> None:
        s = _spine()
        env = s.emit_and_envelope(_event(), ("dashboard", "obligation_runtime"))
        assert isinstance(env, EventEnvelope)
        assert s.event_count == 1
        assert len(env.target_subsystems) == 2


# ---------------------------------------------------------------------------
# List / Filter
# ---------------------------------------------------------------------------

class TestListEvents:
    def test_list_all(self) -> None:
        s = _spine()
        s.emit(_event("e-1"))
        s.emit(_event("e-2", etype=EventType.APPROVAL_REQUESTED, source=EventSource.APPROVAL_SYSTEM))
        assert len(s.list_events()) == 2

    def test_filter_by_type(self) -> None:
        s = _spine()
        s.emit(_event("e-1", etype=EventType.JOB_STATE_TRANSITION))
        s.emit(_event("e-2", etype=EventType.APPROVAL_REQUESTED))
        result = s.list_events(event_type=EventType.JOB_STATE_TRANSITION)
        assert len(result) == 1

    def test_filter_by_correlation(self) -> None:
        s = _spine()
        s.emit(_event("e-1", corr="c-1"))
        s.emit(_event("e-2", corr="c-2"))
        result = s.list_events(correlation_id="c-1")
        assert len(result) == 1

    def test_filter_by_source(self) -> None:
        s = _spine()
        s.emit(_event("e-1", source=EventSource.JOB_RUNTIME))
        s.emit(_event("e-2", source=EventSource.APPROVAL_SYSTEM))
        result = s.list_events(source=EventSource.JOB_RUNTIME)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

class TestSubscriptions:
    def test_subscribe(self) -> None:
        s = _spine()
        s.subscribe(_subscription())
        assert s.subscription_count == 1

    def test_duplicate_rejected(self) -> None:
        s = _spine()
        s.subscribe(_subscription())
        with pytest.raises(RuntimeCoreInvariantError, match="^subscription already exists$") as excinfo:
            s.subscribe(_subscription())
        assert "sub-1" not in str(excinfo.value)

    def test_unsubscribe(self) -> None:
        s = _spine()
        s.subscribe(_subscription())
        s.unsubscribe("sub-1")
        assert s.subscription_count == 0

    def test_unsubscribe_not_found(self) -> None:
        s = _spine()
        with pytest.raises(RuntimeCoreInvariantError, match="^subscription not found$") as excinfo:
            s.unsubscribe("sub-missing")
        assert "sub-missing" not in str(excinfo.value)

    def test_matching_subscriptions(self) -> None:
        s = _spine()
        s.subscribe(_subscription("sub-1", EventType.JOB_STATE_TRANSITION))
        s.subscribe(_subscription("sub-2", EventType.APPROVAL_REQUESTED))
        evt = _event("e-1", etype=EventType.JOB_STATE_TRANSITION)
        matches = s.matching_subscriptions(evt)
        assert len(matches) == 1
        assert matches[0].subscription_id == "sub-1"

    def test_matching_with_source_filter(self) -> None:
        s = _spine()
        s.subscribe(_subscription("sub-1", EventType.JOB_STATE_TRANSITION,
                                  filter_source=EventSource.JOB_RUNTIME))
        s.subscribe(_subscription("sub-2", EventType.JOB_STATE_TRANSITION,
                                  filter_source=EventSource.WORKFLOW_RUNTIME))
        evt = _event("e-1", source=EventSource.JOB_RUNTIME)
        matches = s.matching_subscriptions(evt)
        assert len(matches) == 1
        assert matches[0].subscription_id == "sub-1"

    def test_list_by_type(self) -> None:
        s = _spine()
        s.subscribe(_subscription("sub-1", EventType.JOB_STATE_TRANSITION))
        s.subscribe(_subscription("sub-2", EventType.APPROVAL_REQUESTED))
        result = s.list_subscriptions(event_type=EventType.APPROVAL_REQUESTED)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------

class TestReactions:
    def test_record_reaction(self) -> None:
        s = _spine()
        s.emit(_event("evt-1"))
        rx = EventReaction(
            reaction_id="rx-1", event_id="evt-1",
            subscription_id="sub-1",
            action_taken="created obligation",
            result="success", reacted_at=_CLOCK,
        )
        s.record_reaction(rx)
        assert s.reaction_count == 1

    def test_reaction_requires_event(self) -> None:
        s = _spine()
        rx = EventReaction(
            reaction_id="rx-1", event_id="evt-missing",
            subscription_id="sub-1",
            action_taken="test", result="ok", reacted_at=_CLOCK,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="^event not found$") as excinfo:
            s.record_reaction(rx)
        assert "evt-missing" not in str(excinfo.value)

    def test_list_reactions_by_event(self) -> None:
        s = _spine()
        s.emit(_event("evt-1"))
        s.emit(_event("evt-2"))
        s.record_reaction(EventReaction(
            reaction_id="rx-1", event_id="evt-1",
            subscription_id="sub-1",
            action_taken="a", result="ok", reacted_at=_CLOCK,
        ))
        s.record_reaction(EventReaction(
            reaction_id="rx-2", event_id="evt-2",
            subscription_id="sub-1",
            action_taken="b", result="ok", reacted_at=_CLOCK,
        ))
        assert len(s.list_reactions(event_id="evt-1")) == 1


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

class TestCorrelation:
    def test_correlate(self) -> None:
        s = _spine()
        s.emit(_event("e-1", corr="job-1"))
        s.emit(_event("e-2", corr="job-1"))
        s.emit(_event("e-3", corr="job-2"))
        corr = s.correlate("job-1")
        assert corr is not None
        assert len(corr.event_ids) == 2
        assert corr.root_event_id == "e-1"
        assert corr.description == "correlated event group"
        assert "job-1" not in corr.description

    def test_correlate_not_found(self) -> None:
        s = _spine()
        assert s.correlate("missing") is None


# ---------------------------------------------------------------------------
# Event Windows
# ---------------------------------------------------------------------------

class TestEventWindow:
    def test_build_window(self) -> None:
        s = _spine()
        s.emit(EventRecord(
            event_id="e-1", event_type=EventType.JOB_STATE_TRANSITION,
            source=EventSource.JOB_RUNTIME, correlation_id="job-1",
            payload={}, emitted_at="2026-03-20T00:00:00+00:00",
        ))
        s.emit(EventRecord(
            event_id="e-2", event_type=EventType.JOB_STATE_TRANSITION,
            source=EventSource.JOB_RUNTIME, correlation_id="job-1",
            payload={}, emitted_at="2026-03-20T01:00:00+00:00",
        ))
        win = s.build_window("job-1")
        assert win is not None
        assert win.event_count == 2
        assert win.window_start == "2026-03-20T00:00:00+00:00"
        assert win.window_end == "2026-03-20T01:00:00+00:00"

    def test_window_not_found(self) -> None:
        s = _spine()
        assert s.build_window("missing") is None
