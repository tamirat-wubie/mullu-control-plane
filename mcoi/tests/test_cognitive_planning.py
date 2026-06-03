"""Tests for the read-only plan-time cognitive context reader (#3a read-back).

Verifies the reader maps learned organ state to per-capability advisory context,
flags caution capabilities (non-PROCEED verdicts), de-duplicates capabilities, and
writes nothing back to any engine.
"""

from __future__ import annotations

from mcoi_runtime.core.cognitive_loop import DecisionVerdict
from mcoi_runtime.core.cognitive_planning import (
    CognitivePlanningContext,
    CognitivePlanningReader,
)


class _FakeConfidence:
    def __init__(self, overall: float) -> None:
        self.overall_confidence = overall


class _FakeMeta:
    def __init__(self, table: dict) -> None:
        # capability_id -> (confidence_or_None, degraded)
        self._table = table
        self.update_calls = 0

    def get_confidence(self, capability_id: str):
        conf, _degraded = self._table.get(capability_id, (None, False))
        return _FakeConfidence(conf) if conf is not None else None

    def is_degraded(self, capability_id: str) -> bool:
        _conf, degraded = self._table.get(capability_id, (None, False))
        return degraded

    def update_confidence(self, confidence) -> None:  # must never be called
        self.update_calls += 1


class _FakeWorldState:
    def __init__(self, n: int = 0) -> None:
        self._entities = tuple(range(n))

    def list_entities(self):
        return self._entities


class _FakeEntry:
    def __init__(self, content: dict) -> None:
        self.content = content


class _FakeEpisodic:
    def __init__(self, entries=()) -> None:
        self._entries = tuple(entries)
        self.admit_calls = 0

    def list_entries(self):
        return self._entries

    def admit(self, entry):  # must never be called
        self.admit_calls += 1
        return entry


def _reader(table, *, entities=0, entries=()):
    return CognitivePlanningReader(
        meta_reasoning=_FakeMeta(table),
        world_state=_FakeWorldState(entities),
        episodic_memory=_FakeEpisodic(entries),
    )


def test_confident_capability_proceeds_no_caution():
    ctx = _reader({"pay": (0.9, False)}).read(("pay",))
    assert isinstance(ctx, CognitivePlanningContext)
    assert len(ctx.capabilities) == 1
    assert ctx.capabilities[0].decision_verdict is DecisionVerdict.PROCEED
    assert ctx.caution_capabilities == ()
    assert ctx.has_caution is False


def test_degraded_low_confidence_is_caution():
    ctx = _reader({"flaky": (0.1, True)}).read(("flaky",))
    assert ctx.capabilities[0].decision_verdict is DecisionVerdict.DEFER_TO_REVIEW
    assert ctx.caution_capabilities == ("flaky",)
    assert ctx.has_caution is True


def test_unseen_capability_is_neutral_and_proceeds():
    ctx = _reader({}).read(("never_seen",))
    assert ctx.capabilities[0].confidence == 0.5
    assert ctx.capabilities[0].decision_verdict is DecisionVerdict.PROCEED


def test_capabilities_are_deduplicated_order_preserving():
    ctx = _reader({"a": (0.9, False), "b": (0.9, False)}).read(("a", "b", "a"))
    assert [c.capability_id for c in ctx.capabilities] == ["a", "b"]


def test_prior_outcomes_and_entities_counted():
    entries = (
        _FakeEntry({"capability_id": "pay"}),
        _FakeEntry({"route": "pay"}),
        _FakeEntry({"capability_id": "other"}),
    )
    ctx = _reader({"pay": (0.9, False)}, entities=4, entries=entries).read(("pay",))
    assert ctx.capabilities[0].prior_outcomes == 2
    assert ctx.planning_entity_count == 4


def test_reader_writes_nothing_back():
    meta = _FakeMeta({"pay": (0.1, True)})
    episodic = _FakeEpisodic()
    reader = CognitivePlanningReader(
        meta_reasoning=meta, world_state=_FakeWorldState(1), episodic_memory=episodic
    )
    reader.read(("pay",))
    assert meta.update_calls == 0
    assert episodic.admit_calls == 0


def test_to_dict_shape():
    ctx = _reader({"pay": (0.1, True), "ok": (0.9, False)}).read(("pay", "ok"))
    data = ctx.to_dict()
    assert data["has_caution"] is True
    assert "pay" in data["caution_capabilities"]
    assert {c["capability_id"] for c in data["capabilities"]} == {"pay", "ok"}
    pay = next(c for c in data["capabilities"] if c["capability_id"] == "pay")
    assert pay["verdict"] == DecisionVerdict.DEFER_TO_REVIEW.value
