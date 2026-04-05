"""Tests for workflow persistence: round-trip, listing, and error handling.

Proves that workflow execution records survive save/load cycles.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import mcoi_runtime.persistence.workflow_store as workflow_store_module
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStage,
    WorkflowStatus,
)
from mcoi_runtime.persistence.workflow_store import WorkflowStore
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


# --- Helpers ---


def _make_stage_result(stage_id="s1", status=StageStatus.COMPLETED, **kw):
    defaults = dict(
        stage_id=stage_id,
        status=status,
        output={"result": "ok"},
        started_at=FIXED_CLOCK,
        completed_at=FIXED_CLOCK,
    )
    defaults.update(kw)
    return StageExecutionResult(**defaults)


def _make_record(execution_id="exec-001", workflow_id="wf-1", **kw):
    defaults = dict(
        workflow_id=workflow_id,
        execution_id=execution_id,
        status=WorkflowStatus.COMPLETED,
        stage_results=(_make_stage_result(),),
        started_at=FIXED_CLOCK,
        completed_at=FIXED_CLOCK,
    )
    defaults.update(kw)
    return WorkflowExecutionRecord(**defaults)


def _make_descriptor(workflow_id="wf-1", **kw):
    defaults = dict(
        workflow_id=workflow_id,
        name=f"workflow-{workflow_id}",
        stages=(
            WorkflowStage(stage_id="s1", stage_type=StageType.OBSERVATION),
        ),
        created_at=FIXED_CLOCK,
    )
    defaults.update(kw)
    return WorkflowDescriptor(**defaults)


# --- WorkflowStore ---


class TestWorkflowStore:
    def test_save_and_load_round_trip(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        record = _make_record()
        store.save_execution_record(record)
        loaded = store.load_execution_record("exec-001")

        assert loaded.execution_id == record.execution_id
        assert loaded.workflow_id == record.workflow_id
        assert loaded.status is WorkflowStatus.COMPLETED

    def test_stage_results_preserved(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        stages = (
            _make_stage_result("s1", StageStatus.COMPLETED),
            _make_stage_result("s2", StageStatus.FAILED),
        )
        record = _make_record(stage_results=stages)
        store.save_execution_record(record)
        loaded = store.load_execution_record("exec-001")

        assert len(loaded.stage_results) == 2
        assert loaded.stage_results[0].stage_id == "s1"
        assert loaded.stage_results[0].status is StageStatus.COMPLETED
        assert loaded.stage_results[1].stage_id == "s2"
        assert loaded.stage_results[1].status is StageStatus.FAILED

    def test_stage_output_preserved(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        stage = _make_stage_result(output={"key": "value", "count": 42})
        record = _make_record(stage_results=(stage,))
        store.save_execution_record(record)
        loaded = store.load_execution_record("exec-001")

        assert loaded.stage_results[0].output["key"] == "value"
        assert loaded.stage_results[0].output["count"] == 42

    def test_timestamps_preserved(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        record = _make_record()
        store.save_execution_record(record)
        loaded = store.load_execution_record("exec-001")

        assert loaded.started_at == FIXED_CLOCK
        assert loaded.completed_at == FIXED_CLOCK

    def test_list_executions(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save_execution_record(_make_record("exec-b"))
        store.save_execution_record(_make_record("exec-a"))
        store.save_execution_record(_make_record("exec-c"))

        ids = store.list_executions()
        assert ids == ("exec-a", "exec-b", "exec-c")

    def test_list_executions_empty(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        assert store.list_executions() == ()

    def test_load_nonexistent_raises(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        with pytest.raises(PersistenceError, match=r"^workflow execution record not found$") as excinfo:
            store.load_execution_record("missing")
        assert "missing" not in str(excinfo.value)

    def test_malformed_file_fails_closed(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        (tmp_path / "workflows").mkdir(parents=True, exist_ok=True)
        (tmp_path / "workflows" / "bad.json").write_text("not json!!")
        with pytest.raises(CorruptedDataError, match=r"^malformed JSON \(JSONDecodeError\)$"):
            store.load_execution_record("bad")

    def test_invalid_type_rejected(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        with pytest.raises(PersistenceError, match="WorkflowExecutionRecord"):
            store.save_execution_record("not a record")

    def test_overwrite_same_id(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        record1 = _make_record(status=WorkflowStatus.RUNNING)
        record2 = _make_record(status=WorkflowStatus.COMPLETED)
        store.save_execution_record(record1)
        store.save_execution_record(record2)
        loaded = store.load_execution_record("exec-001")
        assert loaded.status is WorkflowStatus.COMPLETED

    def test_failed_workflow_status_preserved(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        record = _make_record(status=WorkflowStatus.FAILED, completed_at=FIXED_CLOCK)
        store.save_execution_record(record)
        loaded = store.load_execution_record("exec-001")
        assert loaded.status is WorkflowStatus.FAILED

    def test_save_and_load_descriptor_round_trip(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        descriptor = _make_descriptor()
        store.save_descriptor(descriptor)
        loaded = store.load_descriptor("wf-1")

        assert loaded.workflow_id == descriptor.workflow_id
        assert loaded.name == descriptor.name
        assert loaded.stages[0].stage_id == "s1"

    def test_list_descriptors(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save_descriptor(_make_descriptor("wf-b"))
        store.save_descriptor(_make_descriptor("wf-a"))

        assert store.list_descriptors() == ("wf-a", "wf-b")

    def test_list_executions_ignores_descriptors(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save_execution_record(_make_record("exec-1"))
        store.save_descriptor(_make_descriptor("wf-1"))

        assert store.list_executions() == ("exec-1",)

    def test_load_missing_descriptor_raises(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        with pytest.raises(PersistenceError, match=r"^workflow descriptor not found$") as excinfo:
            store.load_descriptor("missing")
        assert "missing" not in str(excinfo.value)

    def test_malformed_descriptor_fails_closed(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        (tmp_path / "workflows").mkdir(parents=True, exist_ok=True)
        (tmp_path / "workflows" / "workflow-descriptor--bad.json").write_text("not json!!")

        with pytest.raises(CorruptedDataError, match=r"^malformed JSON \(JSONDecodeError\)$"):
            store.load_descriptor("bad")

    def test_invalid_descriptor_type_rejected(self, tmp_path: Path):
        store = WorkflowStore(tmp_path / "workflows")
        with pytest.raises(PersistenceError, match="WorkflowDescriptor"):
            store.save_descriptor("not a descriptor")

    def test_descriptor_load_bounds_invalid_artifact_errors(
        self, tmp_path: Path, monkeypatch
    ):
        store = WorkflowStore(tmp_path / "workflows")
        descriptor = _make_descriptor()
        store.save_descriptor(descriptor)

        def _raise_value_error(_content, _record_type):
            raise ValueError("workflow descriptor internal detail")

        monkeypatch.setattr(workflow_store_module, "deserialize_record", _raise_value_error)

        with pytest.raises(
            CorruptedDataError,
            match=r"^invalid workflow artifact \(ValueError\)$",
        ) as excinfo:
            store.load_descriptor("wf-1")
        assert "workflow descriptor" not in str(excinfo.value)
        assert "internal detail" not in str(excinfo.value)
