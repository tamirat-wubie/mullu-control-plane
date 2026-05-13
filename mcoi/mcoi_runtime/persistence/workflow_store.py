"""Purpose: persistence for workflow descriptors and execution records.
Governance scope: persistence layer workflow storage only.
Dependencies: persistence errors, serialization helpers, workflow contracts.
Invariants:
  - Workflow descriptors and execution records are stored explicitly.
  - Artifact types do not collide on disk.
  - Reads fail closed on malformed data.
"""

from __future__ import annotations

import os
import tempfile
import json
from dataclasses import dataclass
from pathlib import Path

from mcoi_runtime.contracts.workflow import WorkflowDescriptor, WorkflowExecutionRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.workflow import WorkflowEngine

from ._serialization import deserialize_record, serialize_record
from .errors import (
    CorruptedDataError,
    PathTraversalError,
    PersistenceError,
    PersistenceWriteError,
)


_DESCRIPTOR_PREFIX = "workflow-descriptor--"


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
        raise PersistenceWriteError(_bounded_store_error("workflow store write failed", exc)) from exc


class WorkflowStore:
    """Persistence for WorkflowDescriptor and WorkflowExecutionRecord artifacts."""

    def __init__(self, base_path: Path) -> None:
        if not isinstance(base_path, Path):
            raise PersistenceError("base_path must be a Path instance")
        self._base_path = base_path

    def _safe_path(self, id_value: str, suffix: str = ".json") -> Path:
        """Construct a path from *id_value* and validate it stays inside _base_path."""
        if "\0" in id_value:
            raise PathTraversalError("identifier contains null byte")
        if "/" in id_value or "\\" in id_value or ".." in id_value:
            raise PathTraversalError("identifier contains forbidden characters")
        candidate = (self._base_path / f"{id_value}{suffix}").resolve()
        base_resolved = self._base_path.resolve()
        if not candidate.is_relative_to(base_resolved):
            raise PathTraversalError("path escapes base directory")
        return candidate

    def save_execution_record(self, record: WorkflowExecutionRecord) -> None:
        """Persist a workflow execution record."""
        if not isinstance(record, WorkflowExecutionRecord):
            raise PersistenceError("record must be a WorkflowExecutionRecord instance")
        path = self._safe_path(record.execution_id)
        content = serialize_record(record)
        _atomic_write(path, content)

    def save_descriptor(self, descriptor: WorkflowDescriptor) -> None:
        """Persist a workflow descriptor."""
        if not isinstance(descriptor, WorkflowDescriptor):
            raise PersistenceError("descriptor must be a WorkflowDescriptor instance")
        path = self._descriptor_path(descriptor.workflow_id)
        content = serialize_record(descriptor)
        _atomic_write(path, content)

    def load_execution_record(self, execution_id: str) -> WorkflowExecutionRecord:
        """Load a workflow execution record by execution ID."""
        if not isinstance(execution_id, str) or not execution_id.strip():
            raise PersistenceError("execution_id must be a non-empty string")
        path = self._safe_path(execution_id)
        if not path.exists():
            raise PersistenceError("workflow execution record not found")
        record = _load_workflow_file(path, WorkflowExecutionRecord, "workflow record")
        if record.execution_id != execution_id:
            raise CorruptedDataError("workflow execution id mismatch")
        return record

    def load_descriptor(self, workflow_id: str) -> WorkflowDescriptor:
        """Load a workflow descriptor by workflow ID."""
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise PersistenceError("workflow_id must be a non-empty string")
        path = self._descriptor_path(workflow_id)
        if not path.exists():
            raise PersistenceError("workflow descriptor not found")
        descriptor = _load_workflow_file(path, WorkflowDescriptor, "workflow descriptor")
        if descriptor.workflow_id != workflow_id:
            raise CorruptedDataError("workflow descriptor id mismatch")
        return descriptor

    def list_executions(self) -> tuple[str, ...]:
        """List all persisted workflow execution IDs in sorted order."""
        if not self._base_path.exists():
            return ()
        return tuple(
            self._listed_execution_id(entry)
            for entry in sorted(self._base_path.iterdir())
            if (
                entry.is_file()
                and entry.suffix == ".json"
                and not entry.name.startswith(_DESCRIPTOR_PREFIX)
                and entry.stem != "workflow_runtime"
            )
        )

    def list_descriptors(self) -> tuple[str, ...]:
        """List all persisted workflow descriptor IDs in sorted order."""
        if not self._base_path.exists():
            return ()
        return tuple(
            self._listed_descriptor_id(entry)
            for entry in sorted(self._base_path.iterdir())
            if entry.is_file() and entry.suffix == ".json" and entry.name.startswith(_DESCRIPTOR_PREFIX)
        )

    def _descriptor_path(self, workflow_id: str) -> Path:
        return self._safe_path(f"{_DESCRIPTOR_PREFIX}{workflow_id}")

    def _listed_execution_id(self, file_path: Path) -> str:
        execution_id = file_path.stem
        try:
            self._safe_path(execution_id)
        except PathTraversalError as exc:
            raise CorruptedDataError("workflow execution filename is invalid") from exc
        return execution_id

    def _listed_descriptor_id(self, file_path: Path) -> str:
        workflow_id = file_path.name[len(_DESCRIPTOR_PREFIX):-len(".json")]
        try:
            self._descriptor_path(workflow_id)
        except PathTraversalError as exc:
            raise CorruptedDataError("workflow descriptor filename is invalid") from exc
        return workflow_id

    def save_state(self, engine: WorkflowEngine) -> str:
        """Persist exact workflow descriptors and execution records as one witness."""
        if not isinstance(engine, WorkflowEngine):
            raise PersistenceError("engine must be a WorkflowEngine instance")
        descriptors = engine.list_workflow_descriptors()
        execution_records = engine.list_execution_records()
        for descriptor in descriptors:
            self.save_descriptor(descriptor)
        for record in execution_records:
            self.save_execution_record(record)
        payload = {
            "descriptors": [
                json.loads(serialize_record(descriptor))
                for descriptor in descriptors
            ],
            "execution_records": [
                json.loads(serialize_record(record))
                for record in execution_records
            ],
        }
        content = _deterministic_json(payload)
        _atomic_write(self._base_path / "workflow_runtime.json", content)
        return content

    def load_state(self) -> "WorkflowRuntimeState":
        """Load a deterministic workflow runtime witness."""
        descriptor_ids = self.list_descriptors()
        execution_ids = self.list_executions()
        if descriptor_ids or execution_ids:
            descriptors = tuple(
                self.load_descriptor(workflow_id) for workflow_id in descriptor_ids
            )
            execution_records = tuple(
                self.load_execution_record(execution_id)
                for execution_id in execution_ids
            )
            self._validate_pairing(descriptors, execution_records)
            return WorkflowRuntimeState(
                descriptors=descriptors,
                execution_records=execution_records,
            )

        path = self._base_path / "workflow_runtime.json"
        if not path.exists():
            raise CorruptedDataError(f"workflow runtime file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(f"malformed workflow runtime file: {exc}") from exc
        if not isinstance(payload, dict):
            raise CorruptedDataError("workflow runtime payload must be a JSON object")

        descriptors_raw = payload.get("descriptors")
        records_raw = payload.get("execution_records")
        if not isinstance(descriptors_raw, list):
            raise CorruptedDataError("workflow runtime descriptors must be a JSON array")
        if not isinstance(records_raw, list):
            raise CorruptedDataError("workflow runtime execution_records must be a JSON array")

        descriptors = tuple(
            self._deserialize_descriptor(raw) for raw in descriptors_raw
        )
        execution_records = tuple(
            self._deserialize_record(raw) for raw in records_raw
        )
        self._validate_pairing(descriptors, execution_records)
        return WorkflowRuntimeState(
            descriptors=descriptors,
            execution_records=execution_records,
        )

    def restore_state(self, engine: WorkflowEngine) -> "WorkflowRuntimeState":
        """Restore exact persisted workflow runtime state without replay."""
        if not isinstance(engine, WorkflowEngine):
            raise PersistenceError("engine must be a WorkflowEngine instance")
        state = self.load_state()
        self._validate_restore_preconditions(engine, state)
        for descriptor in state.descriptors:
            engine.restore_descriptor(descriptor)
        for record in state.execution_records:
            engine.restore_execution_record(record)
        return state

    def exists(self) -> bool:
        return (
            (self._base_path / "workflow_runtime.json").exists()
            or bool(self.list_descriptors())
            or bool(self.list_executions())
        )

    @staticmethod
    def _deserialize_descriptor(raw: object) -> WorkflowDescriptor:
        if not isinstance(raw, dict):
            raise CorruptedDataError("workflow descriptor entry must be a JSON object")
        return deserialize_record(_deterministic_json(raw), WorkflowDescriptor)

    @staticmethod
    def _deserialize_record(raw: object) -> WorkflowExecutionRecord:
        if not isinstance(raw, dict):
            raise CorruptedDataError("workflow execution entry must be a JSON object")
        return deserialize_record(_deterministic_json(raw), WorkflowExecutionRecord)

    @staticmethod
    def _validate_pairing(
        descriptors: tuple[WorkflowDescriptor, ...],
        execution_records: tuple[WorkflowExecutionRecord, ...],
    ) -> None:
        descriptor_ids = tuple(descriptor.workflow_id for descriptor in descriptors)
        execution_ids = tuple(record.execution_id for record in execution_records)
        WorkflowStore._require_unique(descriptor_ids, label="workflow descriptor")
        WorkflowStore._require_unique(execution_ids, label="workflow execution")
        available_workflow_ids = set(descriptor_ids)
        missing_workflow_ids = tuple(
            sorted(
                {
                    record.workflow_id
                    for record in execution_records
                    if record.workflow_id not in available_workflow_ids
                }
            )
        )
        if missing_workflow_ids:
            raise CorruptedDataError(
                "workflow runtime execution records reference missing workflow descriptors: "
                + ", ".join(missing_workflow_ids)
            )

    @staticmethod
    def _validate_restore_preconditions(
        engine: WorkflowEngine,
        state: "WorkflowRuntimeState",
    ) -> None:
        for descriptor in state.descriptors:
            if engine.get_workflow_descriptor(descriptor.workflow_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"workflow descriptor already restored: {descriptor.workflow_id}"
                )
        for record in state.execution_records:
            if engine.get_execution_record(record.execution_id) is not None:
                raise RuntimeCoreInvariantError(
                    f"workflow execution already restored: {record.execution_id}"
                )

    @staticmethod
    def _require_unique(ids: tuple[str, ...], *, label: str) -> None:
        if len(ids) != len(set(ids)):
            raise CorruptedDataError(
                f"duplicate {label} identifier in workflow runtime payload"
            )


@dataclass(frozen=True, slots=True)
class WorkflowRuntimeState:
    """Explicit snapshot of live workflow descriptors and execution records."""

    descriptors: tuple[WorkflowDescriptor, ...]
    execution_records: tuple[WorkflowExecutionRecord, ...]

    def __post_init__(self) -> None:
        if any(
            not isinstance(descriptor, WorkflowDescriptor)
            for descriptor in self.descriptors
        ):
            raise PersistenceError(
                "descriptors must contain WorkflowDescriptor instances only"
            )
        if any(
            not isinstance(record, WorkflowExecutionRecord)
            for record in self.execution_records
        ):
            raise PersistenceError(
                "execution_records must contain WorkflowExecutionRecord instances only"
            )


def _load_workflow_file(path: Path, record_type: type, label: str):
    """Load and validate a single persisted workflow artifact JSON file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptedDataError(_bounded_store_error("workflow artifact read failed", exc)) from exc

    try:
        return deserialize_record(content, record_type)
    except CorruptedDataError:
        raise
    except (TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid workflow artifact", exc)) from exc
