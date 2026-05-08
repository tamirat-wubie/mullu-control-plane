"""Purpose: verify explicit persistence and restore for team queue-state witnesses.
Governance scope: aggregate team queue-state persistence only.
Dependencies: team runtime, queue store, persistence errors.
Invariants:
  - Queue-state serialization is deterministic for the same engine state.
  - Restore preserves exact queue-state counts and timestamps.
  - Malformed payloads fail closed.
  - Restore rejects duplicate team identifiers before mutation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry
from mcoi_runtime.persistence.errors import CorruptedDataError
from mcoi_runtime.persistence.team_queue_store import TeamQueueStore


_T0 = "2026-05-01T12:00:00+00:00"
_T1 = "2026-05-01T12:00:01+00:00"


def _make_clock(times: list[str]):
    iterator = iter(times)

    def clock() -> str:
        return next(iterator)

    return clock


def _make_engine() -> TeamEngine:
    registry = WorkerRegistry(clock=_make_clock([_T0, _T1]))
    return TeamEngine(registry=registry, clock=_make_clock([_T0, _T1]))


def test_team_queue_store_round_trip_preserves_queue_states(tmp_path: Path) -> None:
    engine = _make_engine()
    first = engine.capture_queue_state("team-a", queued=5, assigned=3, waiting=2)
    second = engine.capture_queue_state("team-b", queued=1, assigned=1, waiting=0)
    store = TeamQueueStore(tmp_path / "coordination")

    saved = store.save_queue_states(engine)
    restored = _make_engine()
    states = store.restore_queue_states(restored)

    assert "\"queue_states\"" in saved
    assert tuple(state.team_id for state in states) == ("team-a", "team-b")
    assert restored.queue_state_count == 2
    assert restored.get_queue_state("team-a") == first
    assert restored.get_queue_state("team-b") == second
    assert restored.list_queue_states() == (first, second)


def test_team_queue_store_serialization_is_stable_for_same_input(tmp_path: Path) -> None:
    engine = _make_engine()
    engine.capture_queue_state("team-a", queued=5, assigned=3, waiting=2)
    engine.capture_queue_state("team-b", queued=1, assigned=1, waiting=0)
    store = TeamQueueStore(tmp_path / "coordination")

    first = store.save_queue_states(engine)
    second = store.save_queue_states(engine)
    persisted = (tmp_path / "coordination" / "team_queue_states.json").read_text(encoding="utf-8")

    assert first == second
    assert persisted == first
    assert store.exists() is True


def test_team_queue_store_fails_closed_on_malformed_payload(tmp_path: Path) -> None:
    base_path = tmp_path / "coordination"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "team_queue_states.json"
    payload_path.write_text(
        json.dumps({"queue_states": {}}),
        encoding="utf-8",
    )
    store = TeamQueueStore(base_path)

    assert payload_path.exists() is True
    with pytest.raises(CorruptedDataError, match="queue_states array"):
        store.load_queue_states()
    assert store.exists() is True


def test_restore_queue_states_rejects_duplicate_team_before_mutation(tmp_path: Path) -> None:
    base_path = tmp_path / "coordination"
    base_path.mkdir(parents=True, exist_ok=True)
    payload_path = base_path / "team_queue_states.json"
    payload_path.write_text(
        json.dumps(
            {
                "queue_states": [
                    {
                        "team_id": "team-a",
                        "queued_jobs": 5,
                        "assigned_jobs": 3,
                        "waiting_jobs": 2,
                        "overloaded_workers": 0,
                        "captured_at": _T0,
                    },
                    {
                        "team_id": "team-a",
                        "queued_jobs": 1,
                        "assigned_jobs": 1,
                        "waiting_jobs": 0,
                        "overloaded_workers": 0,
                        "captured_at": _T1,
                    },
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    store = TeamQueueStore(base_path)
    engine = _make_engine()

    assert payload_path.exists() is True
    with pytest.raises(CorruptedDataError, match="duplicate team_id"):
        store.restore_queue_states(engine)
    assert engine.queue_state_count == 0
    assert engine.list_queue_states() == ()


def test_restore_queue_states_rejects_existing_team_before_mutation(tmp_path: Path) -> None:
    engine = _make_engine()
    existing = engine.capture_queue_state("team-a", queued=2, assigned=1, waiting=1)
    store = TeamQueueStore(tmp_path / "coordination")

    fresh = _make_engine()
    fresh.capture_queue_state("team-a", queued=5, assigned=3, waiting=2)
    store.save_queue_states(fresh)

    assert existing.team_id == "team-a"
    with pytest.raises(RuntimeCoreInvariantError, match="queue state already restored"):
        store.restore_queue_states(engine)
    assert engine.queue_state_count == 1
    assert engine.get_queue_state("team-a") == existing
