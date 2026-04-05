"""Purpose: persistence for goal execution state, plans, and replan records.
Governance scope: persistence layer goal record storage only.
Dependencies: persistence errors, serialization helpers, goal contracts.
Invariants: one file per goal/plan, atomic writes, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mcoi_runtime.contracts.goal import (
    GoalExecutionState,
    GoalPlan,
    GoalReplanRecord,
)

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
)


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
        raise PersistenceWriteError(_bounded_store_error("goal store write failed", exc)) from exc


class GoalStore:
    """Persistence for goal execution state, plans, and replan records.

    Directory layout:
      {base_path}/
        goals/{goal_id}.json          — GoalExecutionState
        plans/{plan_id}.json          — GoalPlan
        replans/{goal_id}_{timestamp}.json — GoalReplanRecord
    """

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _safe_path(self, subdir: str, id_value: str, suffix: str = ".json") -> Path:
        """Construct a path from *id_value* and validate it stays inside _base_path."""
        if "\0" in id_value:
            raise PathTraversalError("identifier contains null byte")
        if "/" in id_value or "\\" in id_value or ".." in id_value:
            raise PathTraversalError("identifier contains forbidden characters")
        candidate = (self._base_path / subdir / f"{id_value}{suffix}").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError("path escapes base directory")
        return candidate

    # --- Goal execution state ---

    def save_goal_state(self, state: GoalExecutionState) -> None:
        """Persist goal execution state."""
        if not isinstance(state, GoalExecutionState):
            raise PersistenceError("state must be a GoalExecutionState instance")
        path = self._safe_path("goals", state.goal_id)
        content = serialize_record(state)
        _atomic_write(path, content)

    def load_goal_state(self, goal_id: str) -> GoalExecutionState:
        """Load goal execution state by goal ID."""
        if not isinstance(goal_id, str) or not goal_id.strip():
            raise PersistenceError("goal_id must be a non-empty string")
        path = self._safe_path("goals", goal_id)
        if not path.exists():
            raise PersistenceError("goal state not found")
        return _load_file(path, GoalExecutionState)

    # --- Plans ---

    def save_plan(self, plan: GoalPlan) -> None:
        """Persist a goal plan."""
        if not isinstance(plan, GoalPlan):
            raise PersistenceError("plan must be a GoalPlan instance")
        path = self._safe_path("plans", plan.plan_id)
        content = serialize_record(plan)
        _atomic_write(path, content)

    def load_plan(self, plan_id: str) -> GoalPlan:
        """Load a goal plan by plan ID."""
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise PersistenceError("plan_id must be a non-empty string")
        path = self._safe_path("plans", plan_id)
        if not path.exists():
            raise PersistenceError("plan not found")
        return _load_file(path, GoalPlan)

    # --- Replan records ---

    def save_replan_record(self, record: GoalReplanRecord) -> None:
        """Persist a replan audit record."""
        if not isinstance(record, GoalReplanRecord):
            raise PersistenceError("record must be a GoalReplanRecord instance")
        # Use goal_id + new_plan_id as the unique key
        record_key = f"{record.goal_id}_{record.new_plan_id}"
        path = self._safe_path("replans", record_key)
        content = serialize_record(record)
        _atomic_write(path, content)

    # --- Listing ---

    def list_goals(self) -> tuple[str, ...]:
        """List all persisted goal IDs in sorted order."""
        goals_dir = self._base_path / "goals"
        if not goals_dir.exists():
            return ()
        return tuple(
            entry.stem
            for entry in sorted(goals_dir.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )


def _load_file(path: Path, record_type: type) -> object:
    """Load and validate a single JSON file into a typed record."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptedDataError(_bounded_store_error("goal store read failed", exc)) from exc

    try:
        return deserialize_record(content, record_type)
    except CorruptedDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid goal record", exc)) from exc
