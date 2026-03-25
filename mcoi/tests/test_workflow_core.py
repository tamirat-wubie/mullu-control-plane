"""Tests for cross-plane workflow runtime core engine."""

import pytest

NOW = "2025-01-01T00:00:00+00:00"

from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowBinding,
    WorkflowDescriptor,
    WorkflowStage,
    WorkflowStatus,
)
from mcoi_runtime.core.workflow import (
    WorkflowEngine,
    WorkflowValidator,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# --- Helpers ---


def _stage(stage_id: str, predecessors: tuple[str, ...] = (), **kw):
    defaults = dict(
        stage_id=stage_id,
        stage_type=StageType.SKILL_EXECUTION,
        description=f"stage {stage_id}",
    )
    defaults["predecessors"] = predecessors
    defaults.update(kw)
    return WorkflowStage(**defaults)


def _descriptor(stages, bindings=(), **kw):
    defaults = dict(
        workflow_id="wf-test",
        name="test-workflow",
        created_at=NOW,
    )
    defaults.update(kw)
    return WorkflowDescriptor(stages=stages, bindings=bindings, **defaults)


class FakeStageExecutor:
    """Stage executor that succeeds by default, with configurable failures."""

    def __init__(self, *, fail_stages: set[str] | None = None, outputs: dict | None = None):
        self._fail_stages = fail_stages or set()
        self._outputs = outputs or {}
        self.executed: list[str] = []
        self.inputs_by_stage: dict[str, dict] = {}

    def execute_stage(self, stage_id, stage_type, skill_id, inputs):
        self.executed.append(stage_id)
        self.inputs_by_stage[stage_id] = dict(inputs)
        if stage_id in self._fail_stages:
            return StageExecutionResult(
                stage_id=stage_id,
                status=StageStatus.FAILED,
                error="simulated failure",
                started_at=NOW,
                completed_at=NOW,
            )
        output = self._outputs.get(stage_id, {"done": True})
        return StageExecutionResult(
            stage_id=stage_id,
            status=StageStatus.COMPLETED,
            output=output,
            started_at=NOW,
            completed_at=NOW,
        )


def _make_clock(times: list[str]):
    """Return a clock function that yields successive timestamps."""
    idx = [0]

    def clock() -> str:
        ts = times[idx[0] % len(times)]
        idx[0] += 1
        return ts

    return clock


# --- WorkflowValidator ---


class TestWorkflowValidator:
    def test_valid_linear(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
            _stage("C", predecessors=("B",)),
        ))
        v = WorkflowValidator()
        assert v.validate(d) == []

    def test_valid_parallel(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B"),
            _stage("C", predecessors=("A", "B")),
        ))
        v = WorkflowValidator()
        assert v.validate(d) == []

    def test_missing_predecessor(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("missing",)),
        ))
        v = WorkflowValidator()
        errors = v.validate(d)
        assert len(errors) == 1
        assert "unknown predecessor" in errors[0]

    def test_cycle_detected(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("B",)),
            _stage("B", predecessors=("A",)),
        ))
        v = WorkflowValidator()
        errors = v.validate(d)
        assert len(errors) == 1
        assert "cycle" in errors[0]

    def test_self_cycle_detected(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("A",)),
        ))
        v = WorkflowValidator()
        errors = v.validate(d)
        assert len(errors) == 1
        assert "cycle" in errors[0]

    def test_three_node_cycle(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("C",)),
            _stage("B", predecessors=("A",)),
            _stage("C", predecessors=("B",)),
        ))
        v = WorkflowValidator()
        errors = v.validate(d)
        assert any("cycle" in e for e in errors)

    def test_invalid_binding_source(self):
        binding = WorkflowBinding(
            binding_id="b1",
            source_stage_id="missing",
            source_output_key="out",
            target_stage_id="A",
            target_input_key="in",
        )
        d = _descriptor(stages=(_stage("A"),), bindings=(binding,))
        v = WorkflowValidator()
        errors = v.validate(d)
        assert any("unknown source stage" in e for e in errors)

    def test_invalid_binding_target(self):
        binding = WorkflowBinding(
            binding_id="b1",
            source_stage_id="A",
            source_output_key="out",
            target_stage_id="missing",
            target_input_key="in",
        )
        d = _descriptor(stages=(_stage("A"),), bindings=(binding,))
        v = WorkflowValidator()
        errors = v.validate(d)
        assert any("unknown target stage" in e for e in errors)


# --- WorkflowEngine ---


class TestWorkflowEngineLinear:
    """Linear workflow (A -> B -> C) executes in order."""

    def test_linear_workflow_executes_in_order(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
            _stage("C", predecessors=("B",)),
        ))
        clock = _make_clock(["t0", "t1", "t2", "t3", "t4", "t5", "t6"])
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor()

        record = engine.start_workflow(d)
        assert record.status is WorkflowStatus.RUNNING

        # Execute A
        record = engine.execute_next_stage(d, record, executor)
        assert len(record.stage_results) == 1
        assert record.stage_results[0].stage_id == "A"
        assert record.status is WorkflowStatus.RUNNING

        # Execute B
        record = engine.execute_next_stage(d, record, executor)
        assert len(record.stage_results) == 2
        assert record.stage_results[1].stage_id == "B"

        # Execute C (final)
        record = engine.execute_next_stage(d, record, executor)
        assert len(record.stage_results) == 3
        assert record.stage_results[2].stage_id == "C"
        assert record.status is WorkflowStatus.COMPLETED

        assert executor.executed == ["A", "B", "C"]


class TestWorkflowEngineParallel:
    """Parallel-capable workflow executes respecting dependencies."""

    def test_parallel_roots_then_join(self):
        # A and B are independent roots; C depends on both
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B"),
            _stage("C", predecessors=("A", "B")),
        ))
        clock = _make_clock(["t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7"])
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor()

        record = engine.start_workflow(d)

        # First call executes A (deterministic: sorted by stage_id)
        record = engine.execute_next_stage(d, record, executor)
        assert record.stage_results[-1].stage_id == "A"

        # Second call executes B
        record = engine.execute_next_stage(d, record, executor)
        assert record.stage_results[-1].stage_id == "B"

        # Third call executes C (both predecessors done)
        record = engine.execute_next_stage(d, record, executor)
        assert record.stage_results[-1].stage_id == "C"
        assert record.status is WorkflowStatus.COMPLETED

    def test_c_not_eligible_until_both_predecessors_done(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B"),
            _stage("C", predecessors=("A", "B")),
        ))
        clock = _make_clock(["t0"] * 20)
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor()

        record = engine.start_workflow(d)
        # Execute only A
        record = engine.execute_next_stage(d, record, executor)
        completed_ids = {r.stage_id for r in record.stage_results}
        assert "C" not in completed_ids

    def test_explicit_bindings_flow_to_target_stage_inputs(self):
        binding = WorkflowBinding(
            binding_id="b1",
            source_stage_id="A",
            source_output_key="payload",
            target_stage_id="B",
            target_input_key="message",
        )
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
        ), bindings=(binding,))
        clock = _make_clock(["t0"] * 10)
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor(outputs={"A": {"payload": "hello"}})

        record = engine.start_workflow(d, context={"template_id": "tpl-1"})
        record = engine.execute_next_stage(d, record, executor, context={"template_id": "tpl-1"})
        record = engine.execute_next_stage(d, record, executor, context={"template_id": "tpl-1"})

        assert record.status is WorkflowStatus.COMPLETED
        assert executor.inputs_by_stage["B"]["message"] == "hello"
        assert executor.inputs_by_stage["B"]["template_id"] == "tpl-1"

    def test_predecessor_outputs_are_not_implicitly_injected(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
        ))
        clock = _make_clock(["t0"] * 10)
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor(outputs={"A": {"payload": "hello"}})

        record = engine.start_workflow(d, context={"template_id": "tpl-2"})
        record = engine.execute_next_stage(d, record, executor, context={"template_id": "tpl-2"})
        record = engine.execute_next_stage(d, record, executor, context={"template_id": "tpl-2"})

        assert record.status is WorkflowStatus.COMPLETED
        assert "payload" not in executor.inputs_by_stage["B"]
        assert "A.payload" not in executor.inputs_by_stage["B"]


class TestWorkflowEngineCycleDetection:
    """Cycle detection raises validation error."""

    def test_start_with_cycle_raises(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("B",)),
            _stage("B", predecessors=("A",)),
        ))
        clock = _make_clock(["t0"])
        engine = WorkflowEngine(clock=clock)
        with pytest.raises(RuntimeCoreInvariantError, match="cycle"):
            engine.start_workflow(d)

    def test_validate_returns_cycle_error(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("B",)),
            _stage("B", predecessors=("A",)),
        ))
        clock = _make_clock(["t0"])
        engine = WorkflowEngine(clock=clock)
        errors = engine.validate_workflow(d)
        assert any("cycle" in e for e in errors)


class TestWorkflowEngineMissingPredecessor:
    """Missing predecessor raises validation error."""

    def test_start_with_missing_predecessor_raises(self):
        d = _descriptor(stages=(
            _stage("A", predecessors=("nonexistent",)),
        ))
        clock = _make_clock(["t0"])
        engine = WorkflowEngine(clock=clock)
        with pytest.raises(RuntimeCoreInvariantError, match="validation failed"):
            engine.start_workflow(d)


class TestWorkflowEngineFailure:
    """Failed stage stops workflow."""

    def test_failed_stage_stops_workflow(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
            _stage("C", predecessors=("B",)),
        ))
        clock = _make_clock(["t0", "t1", "t2", "t3", "t4", "t5"])
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor(fail_stages={"B"})

        record = engine.start_workflow(d)
        record = engine.execute_next_stage(d, record, executor)  # A succeeds
        record = engine.execute_next_stage(d, record, executor)  # B fails

        assert record.status is WorkflowStatus.FAILED
        assert len(record.stage_results) == 2
        assert record.stage_results[1].status is StageStatus.FAILED
        # C was never executed
        assert "C" not in {r.stage_id for r in record.stage_results}

    def test_first_stage_failure(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
        ))
        clock = _make_clock(["t0"] * 10)
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor(fail_stages={"A"})

        record = engine.start_workflow(d)
        record = engine.execute_next_stage(d, record, executor)
        assert record.status is WorkflowStatus.FAILED
        assert len(record.stage_results) == 1


class TestWorkflowEngineSuspend:
    """Suspended workflow preserves partial results."""

    def test_suspend_preserves_results(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
            _stage("C", predecessors=("B",)),
        ))
        clock = _make_clock(["t0", "t1", "t2", "t3", "t4"])
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor()

        record = engine.start_workflow(d)
        record = engine.execute_next_stage(d, record, executor)  # A
        assert len(record.stage_results) == 1

        record = engine.suspend_workflow(record, reason="operator pause")
        assert record.status is WorkflowStatus.SUSPENDED
        assert len(record.stage_results) == 1
        assert record.stage_results[0].stage_id == "A"
        assert record.completed_at is not None

    def test_suspend_non_running_raises(self):
        clock = _make_clock(["t0", "t1", "t2", "t3"])
        engine = WorkflowEngine(clock=clock)

        d = _descriptor(stages=(_stage("A"),))
        executor = FakeStageExecutor()
        record = engine.start_workflow(d)
        record = engine.execute_next_stage(d, record, executor)
        assert record.status is WorkflowStatus.COMPLETED

        with pytest.raises(RuntimeCoreInvariantError, match="cannot suspend"):
            engine.suspend_workflow(record, reason="too late")


class TestWorkflowEngineClockDeterminism:
    """Clock injection produces deterministic timestamps."""

    def test_deterministic_timestamps(self):
        d = _descriptor(stages=(_stage("A"),))
        timestamps = ["2025-06-01T10:00:00Z", "2025-06-01T10:00:01Z", "2025-06-01T10:00:02Z"]
        clock = _make_clock(timestamps)
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor()

        record = engine.start_workflow(d)
        assert record.started_at in timestamps

        record = engine.execute_next_stage(d, record, executor)
        assert record.status is WorkflowStatus.COMPLETED
        assert record.completed_at in timestamps

    def test_same_clock_same_results(self):
        d = _descriptor(stages=(
            _stage("A"),
            _stage("B", predecessors=("A",)),
        ))
        timestamps = ["t0", "t1", "t2", "t3", "t4", "t5"]

        # Run 1
        engine1 = WorkflowEngine(clock=_make_clock(list(timestamps)))
        exec1 = FakeStageExecutor()
        r1 = engine1.start_workflow(d)
        r1 = engine1.execute_next_stage(d, r1, exec1)
        r1 = engine1.execute_next_stage(d, r1, exec1)

        # Run 2
        engine2 = WorkflowEngine(clock=_make_clock(list(timestamps)))
        exec2 = FakeStageExecutor()
        r2 = engine2.start_workflow(d)
        r2 = engine2.execute_next_stage(d, r2, exec2)
        r2 = engine2.execute_next_stage(d, r2, exec2)

        assert r1.execution_id == r2.execution_id
        assert r1.started_at == r2.started_at
        assert r1.completed_at == r2.completed_at
        assert exec1.executed == exec2.executed


class TestWorkflowEngineNoOpOnNonRunning:
    """Calling execute_next_stage on a non-running record is a no-op."""

    def test_no_op_on_completed(self):
        d = _descriptor(stages=(_stage("A"),))
        clock = _make_clock(["t0", "t1", "t2", "t3"])
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor()

        record = engine.start_workflow(d)
        record = engine.execute_next_stage(d, record, executor)
        assert record.status is WorkflowStatus.COMPLETED

        record2 = engine.execute_next_stage(d, record, executor)
        assert record2 is record  # unchanged

    def test_no_op_on_failed(self):
        d = _descriptor(stages=(_stage("A"),))
        clock = _make_clock(["t0"] * 10)
        engine = WorkflowEngine(clock=clock)
        executor = FakeStageExecutor(fail_stages={"A"})

        record = engine.start_workflow(d)
        record = engine.execute_next_stage(d, record, executor)
        assert record.status is WorkflowStatus.FAILED

        record2 = engine.execute_next_stage(d, record, executor)
        assert record2 is record
