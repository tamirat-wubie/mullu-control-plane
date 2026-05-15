"""Purpose: persistence for goal execution state, plans, and replan records.
Governance scope: persistence layer goal record storage only.
Dependencies: persistence errors, serialization helpers, goal contracts.
Invariants: one file per goal/plan, atomic writes, fail closed on malformed data.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from mcoi_runtime.contracts.goal import (
    GoalDescriptor,
    GoalExecutionState,
    GoalPlan,
    GoalReplanRecord,
)
from mcoi_runtime.core.goal_reasoning import GoalReasoningEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

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
        descriptors/{goal_id}.json    — GoalDescriptor
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

    def save_goal_descriptor(self, descriptor: GoalDescriptor) -> None:
        """Persist goal descriptor metadata."""
        if not isinstance(descriptor, GoalDescriptor):
            raise PersistenceError("descriptor must be a GoalDescriptor instance")
        path = self._safe_path("descriptors", descriptor.goal_id)
        content = serialize_record(descriptor)
        _atomic_write(path, content)

    def load_goal_descriptor(self, goal_id: str) -> GoalDescriptor:
        """Load goal descriptor metadata by goal ID."""
        if not isinstance(goal_id, str) or not goal_id.strip():
            raise PersistenceError("goal_id must be a non-empty string")
        path = self._safe_path("descriptors", goal_id)
        if not path.exists():
            raise PersistenceError(f"goal descriptor not found: {goal_id}")
        descriptor = _load_file(path, GoalDescriptor)
        if descriptor.goal_id != goal_id:
            raise CorruptedDataError("goal descriptor id mismatch")
        return descriptor

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
        state = _load_file(path, GoalExecutionState)
        if state.goal_id != goal_id:
            raise CorruptedDataError("goal state id mismatch")
        return state

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
        plan = _load_file(path, GoalPlan)
        if plan.plan_id != plan_id:
            raise CorruptedDataError("goal plan id mismatch")
        return plan

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

    def load_replan_record(self, record_key: str) -> GoalReplanRecord:
        """Load a goal replan record by its persisted key."""
        if not isinstance(record_key, str) or not record_key.strip():
            raise PersistenceError("record_key must be a non-empty string")
        path = self._safe_path("replans", record_key)
        if not path.exists():
            raise PersistenceError(f"replan record not found: {record_key}")
        record = _load_file(path, GoalReplanRecord)
        if f"{record.goal_id}_{record.new_plan_id}" != record_key:
            raise CorruptedDataError("goal replan record id mismatch")
        return record

    # --- Listing ---

    def list_goal_descriptors(self) -> tuple[str, ...]:
        """List all persisted goal descriptor IDs in sorted order."""
        descriptors_dir = self._base_path / "descriptors"
        if not descriptors_dir.exists():
            return ()
        return tuple(
            self._listed_artifact_id("descriptors", entry, label="goal descriptor")
            for entry in sorted(descriptors_dir.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def list_goals(self) -> tuple[str, ...]:
        """List all persisted goal IDs in sorted order."""
        goals_dir = self._base_path / "goals"
        if not goals_dir.exists():
            return ()
        return tuple(
            self._listed_artifact_id("goals", entry, label="goal state")
            for entry in sorted(goals_dir.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def list_plans(self) -> tuple[str, ...]:
        """List all persisted plan IDs in sorted order."""
        plans_dir = self._base_path / "plans"
        if not plans_dir.exists():
            return ()
        return tuple(
            self._listed_artifact_id("plans", entry, label="goal plan")
            for entry in sorted(plans_dir.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def list_replans(self) -> tuple[str, ...]:
        """List all persisted replan record keys in sorted order."""
        replans_dir = self._base_path / "replans"
        if not replans_dir.exists():
            return ()
        return tuple(
            self._listed_artifact_id("replans", entry, label="goal replan record")
            for entry in sorted(replans_dir.iterdir())
            if entry.is_file() and entry.suffix == ".json"
        )

    def _listed_artifact_id(self, subdir: str, file_path: Path, *, label: str) -> str:
        artifact_id = file_path.stem
        try:
            self._safe_path(subdir, artifact_id)
        except PathTraversalError as exc:
            raise CorruptedDataError(f"{label} filename is invalid") from exc
        return artifact_id

    def save_state(self, engine: GoalReasoningEngine) -> str:
        """Persist exact goal runtime descriptors, states, plans, and replans."""
        if not isinstance(engine, GoalReasoningEngine):
            raise PersistenceError("engine must be a GoalReasoningEngine instance")
        descriptors = engine.list_goal_descriptors()
        states = engine.list_goal_states()
        plans = engine.list_plans()
        replans = engine.list_replan_records()
        for descriptor in descriptors:
            self.save_goal_descriptor(descriptor)
        for state in states:
            self.save_goal_state(state)
        for plan in plans:
            self.save_plan(plan)
        for record in replans:
            self.save_replan_record(record)
        payload = {
            "descriptors": [descriptor.to_json_dict() for descriptor in descriptors],
            "states": [state.to_json_dict() for state in states],
            "plans": [plan.to_json_dict() for plan in plans],
            "replans": [record.to_json_dict() for record in replans],
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)

    def load_state(self) -> "GoalRuntimeState":
        """Load persisted goal runtime records from deterministic artifact directories."""
        descriptor_ids = self.list_goal_descriptors()
        goal_ids = self.list_goals()
        plan_ids = self.list_plans()
        replan_ids = self.list_replans()

        descriptors = tuple(
            self.load_goal_descriptor(goal_id) for goal_id in descriptor_ids
        )
        states = tuple(self.load_goal_state(goal_id) for goal_id in goal_ids)
        plans = tuple(self.load_plan(plan_id) for plan_id in plan_ids)
        replans = tuple(self.load_replan_record(record_key) for record_key in replan_ids)
        self._validate_runtime_state(descriptors, states, plans, replans)
        return GoalRuntimeState(
            descriptors=descriptors,
            states=states,
            plans=plans,
            replans=replans,
        )

    def restore_state(self, engine: GoalReasoningEngine) -> "GoalRuntimeState":
        """Restore exact persisted goal runtime state without replay."""
        if not isinstance(engine, GoalReasoningEngine):
            raise PersistenceError("engine must be a GoalReasoningEngine instance")
        state = self.load_state()
        self._validate_restore_preconditions(engine, state)
        for descriptor in state.descriptors:
            matching_state = next(
                goal_state for goal_state in state.states if goal_state.goal_id == descriptor.goal_id
            )
            engine.restore_goal(descriptor, matching_state)
        for plan in state.plans:
            engine.restore_plan(plan)
        for record in state.replans:
            engine.restore_replan_record(record)
        return state

    def exists(self) -> bool:
        return any(
            (
                bool(self.list_goal_descriptors()),
                bool(self.list_goals()),
                bool(self.list_plans()),
                bool(self.list_replans()),
            )
        )

    @staticmethod
    def _validate_runtime_state(
        descriptors: tuple[GoalDescriptor, ...],
        states: tuple[GoalExecutionState, ...],
        plans: tuple[GoalPlan, ...],
        replans: tuple[GoalReplanRecord, ...],
    ) -> None:
        descriptor_ids = tuple(descriptor.goal_id for descriptor in descriptors)
        state_ids = tuple(state.goal_id for state in states)
        plan_ids = tuple(plan.plan_id for plan in plans)
        replan_keys = tuple(f"{record.goal_id}_{record.new_plan_id}" for record in replans)
        GoalStore._require_unique(descriptor_ids, label="goal descriptor")
        GoalStore._require_unique(state_ids, label="goal state")
        GoalStore._require_unique(plan_ids, label="goal plan")
        GoalStore._require_unique(replan_keys, label="goal replan record")
        if set(descriptor_ids) != set(state_ids):
            raise CorruptedDataError(
                "goal descriptors and states must cover the same goal_ids"
            )
        available_goal_ids = set(descriptor_ids)
        available_plan_ids = set(plan_ids)
        for plan in plans:
            if plan.goal_id not in available_goal_ids:
                raise CorruptedDataError(
                    f"goal plan references missing goal descriptor: {plan.goal_id}"
                )
        plans_by_id = {plan.plan_id: plan for plan in plans}
        for state in states:
            if state.current_plan_id is None:
                continue
            if state.current_plan_id not in available_plan_ids:
                raise CorruptedDataError(
                    f"goal state references missing current plan: {state.current_plan_id}"
                )
            current_plan = plans_by_id[state.current_plan_id]
            if current_plan.goal_id != state.goal_id:
                raise CorruptedDataError(
                    "goal state current plan does not belong to the same goal"
                )
            available_sub_goals = {sub_goal.sub_goal_id for sub_goal in current_plan.sub_goals}
            missing_sub_goals = tuple(
                sorted(
                    (set(state.completed_sub_goals) | set(state.failed_sub_goals))
                    - available_sub_goals
                )
            )
            if missing_sub_goals:
                raise CorruptedDataError(
                    "goal state references sub-goals missing from current plan: "
                    + ", ".join(missing_sub_goals)
                )
        for record in replans:
            if record.goal_id not in available_goal_ids:
                raise CorruptedDataError(
                    f"goal replan record references missing goal descriptor: {record.goal_id}"
                )
            if record.previous_plan_id not in available_plan_ids or record.new_plan_id not in available_plan_ids:
                raise CorruptedDataError(
                    "goal replan record references missing plan artifacts"
                )

    @staticmethod
    def _validate_restore_preconditions(
        engine: GoalReasoningEngine,
        state: "GoalRuntimeState",
    ) -> None:
        for descriptor in state.descriptors:
            if engine.get_goal_descriptor(descriptor.goal_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"goal already restored: {descriptor.goal_id}"
                )
        for goal_state in state.states:
            if engine.get_goal_state(goal_state.goal_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"goal state already restored: {goal_state.goal_id}"
                )
        for plan in state.plans:
            if engine.get_plan(plan.plan_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"goal plan already restored: {plan.plan_id}"
                )

    @staticmethod
    def _require_unique(ids: tuple[str, ...], *, label: str) -> None:
        if len(ids) != len(set(ids)):
            raise CorruptedDataError(
                f"duplicate {label} identifier in goal runtime payload"
            )


@dataclass(frozen=True, slots=True)
class GoalRuntimeState:
    """Explicit snapshot of live goal descriptors, states, plans, and replans."""

    descriptors: tuple[GoalDescriptor, ...]
    states: tuple[GoalExecutionState, ...]
    plans: tuple[GoalPlan, ...]
    replans: tuple[GoalReplanRecord, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(descriptor, GoalDescriptor) for descriptor in self.descriptors):
            raise PersistenceError("descriptors must contain GoalDescriptor instances only")
        if any(not isinstance(state, GoalExecutionState) for state in self.states):
            raise PersistenceError("states must contain GoalExecutionState instances only")
        if any(not isinstance(plan, GoalPlan) for plan in self.plans):
            raise PersistenceError("plans must contain GoalPlan instances only")
        if any(not isinstance(record, GoalReplanRecord) for record in self.replans):
            raise PersistenceError("replans must contain GoalReplanRecord instances only")


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
