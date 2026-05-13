"""Purpose: explicit local persistence for team queue-state witnesses.
Governance scope: persistence layer aggregate team queue-state storage only.
Dependencies: team runtime contracts, deterministic JSON helpers, persistence errors.
Invariants:
  - Queue-state serialization is deterministic and team-id sorted.
  - Load fails closed on malformed content or duplicate team IDs.
  - Restore is explicit and never recomputes queue-state counts.
  - This store persists queue-state witnesses, not live queue-item orchestration.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mcoi_runtime.contracts.roles import TeamQueueState
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.team_runtime import TeamEngine

from ._serialization import deserialize_record, serialize_record
from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _deterministic_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _atomic_write(path: Path, content: str) -> None:
    """Write content to a file atomically via temp-file-then-rename."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(_bounded_store_error("team queue store write failed", exc)) from exc


def _queue_state_payload(state: TeamQueueState) -> dict[str, object]:
    payload = json.loads(serialize_record(state))
    if not isinstance(payload, dict):
        raise PersistenceError("serialized team queue state must be a JSON object")
    return payload


class TeamQueueStore:
    """Persist explicit team queue-state witnesses as deterministic JSON."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _queue_path(self) -> Path:
        return self._base_path / "team_queue_states.json"

    def save_queue_states(self, engine: TeamEngine) -> str:
        if not isinstance(engine, TeamEngine):
            raise PersistenceError("engine must be a TeamEngine instance")
        payload = {
            "queue_states": [
                _queue_state_payload(state)
                for state in engine.list_queue_states()
            ]
        }
        content = _deterministic_json(payload)
        _atomic_write(self._queue_path(), content)
        return content

    def load_queue_states(self) -> tuple[TeamQueueState, ...]:
        path = self._queue_path()
        if not path.exists():
            raise CorruptedDataError("team queue state file not found")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(_bounded_store_error("malformed team queue state file", exc)) from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("team queue state payload must be a JSON object")
        states_raw = payload.get("queue_states")
        if not isinstance(states_raw, list):
            raise CorruptedDataError("team queue state payload must contain a queue_states array")

        states: list[TeamQueueState] = []
        seen_team_ids: set[str] = set()
        for raw in states_raw:
            if not isinstance(raw, dict):
                raise CorruptedDataError("team queue state entry must be a JSON object")
            state = deserialize_record(_deterministic_json(raw), TeamQueueState)
            if state.team_id in seen_team_ids:
                raise CorruptedDataError("duplicate team_id in team queue state payload")
            seen_team_ids.add(state.team_id)
            states.append(state)
        return tuple(states)

    def restore_queue_states(self, engine: TeamEngine) -> tuple[TeamQueueState, ...]:
        if not isinstance(engine, TeamEngine):
            raise PersistenceError("engine must be a TeamEngine instance")
        states = self.load_queue_states()
        for state in states:
            if engine.get_queue_state(state.team_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"queue state already restored: {state.team_id}"
                )
        for state in states:
            engine.restore_queue_state(state)
        return states

    def exists(self) -> bool:
        return self._queue_path().exists()
