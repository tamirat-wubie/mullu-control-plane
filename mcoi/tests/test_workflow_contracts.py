"""Tests for cross-plane workflow runtime contracts."""

import pytest

NOW = "2025-01-01T00:00:00+00:00"

from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    TransitionType,
    WorkflowBinding,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStage,
    WorkflowStatus,
    WorkflowTransition,
    WorkflowVerificationRecord,
)


# --- Helpers ---


def _stage(stage_id: str = "s1", **overrides):
    defaults = dict(
        stage_id=stage_id,
        stage_type=StageType.SKILL_EXECUTION,
        description="test stage",
    )
    defaults.update(overrides)
    return WorkflowStage(**defaults)


def _descriptor(**overrides):
    stages = overrides.pop("stages", (_stage("s1"),))
    defaults = dict(
        workflow_id="wf-001",
        name="test-workflow",
        description="a test workflow",
        stages=stages,
        created_at=NOW,
    )
    defaults.update(overrides)
    return WorkflowDescriptor(**defaults)


# --- WorkflowStage ---


class TestWorkflowStage:
    def test_valid(self):
        s = _stage()
        assert s.stage_id == "s1"
        assert s.stage_type is StageType.SKILL_EXECUTION
        assert s.predecessors == ()
        assert s.skill_id is None

    def test_with_skill_id(self):
        s = _stage(skill_id="skill-001")
        assert s.skill_id == "skill-001"

    def test_with_predecessors(self):
        s = _stage(stage_id="s2", predecessors=("s1",))
        assert s.predecessors == ("s1",)

    def test_with_timeout(self):
        s = _stage(timeout_seconds=60)
        assert s.timeout_seconds == 60

    def test_empty_stage_id_rejected(self):
        with pytest.raises(ValueError, match="stage_id"):
            _stage(stage_id="")

    def test_invalid_stage_type_rejected(self):
        with pytest.raises(ValueError, match="stage_type"):
            WorkflowStage(stage_id="s1", stage_type="bad")

    def test_empty_predecessor_rejected(self):
        with pytest.raises(ValueError, match="predecessors"):
            _stage(predecessors=("",))

    def test_empty_skill_id_rejected(self):
        with pytest.raises(ValueError, match="skill_id"):
            _stage(skill_id="")

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValueError, match="timeout_seconds"):
            _stage(timeout_seconds=0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValueError, match="timeout_seconds"):
            _stage(timeout_seconds=-5)

    def test_all_stage_types(self):
        for st in StageType:
            s = _stage(stage_type=st)
            assert s.stage_type is st

    def test_frozen(self):
        s = _stage()
        with pytest.raises(AttributeError):
            s.stage_id = "changed"


# --- WorkflowBinding ---


class TestWorkflowBinding:
    def test_valid(self):
        b = WorkflowBinding(
            binding_id="b1",
            source_stage_id="s1",
            source_output_key="result",
            target_stage_id="s2",
            target_input_key="input",
        )
        assert b.binding_id == "b1"
        assert b.source_stage_id == "s1"
        assert b.target_input_key == "input"

    def test_empty_binding_id_rejected(self):
        with pytest.raises(ValueError, match="binding_id"):
            WorkflowBinding(
                binding_id="",
                source_stage_id="s1",
                source_output_key="r",
                target_stage_id="s2",
                target_input_key="i",
            )

    def test_empty_source_stage_rejected(self):
        with pytest.raises(ValueError, match="source_stage_id"):
            WorkflowBinding(
                binding_id="b1",
                source_stage_id="",
                source_output_key="r",
                target_stage_id="s2",
                target_input_key="i",
            )

    def test_frozen(self):
        b = WorkflowBinding(
            binding_id="b1",
            source_stage_id="s1",
            source_output_key="r",
            target_stage_id="s2",
            target_input_key="i",
        )
        with pytest.raises(AttributeError):
            b.binding_id = "changed"


# --- WorkflowDescriptor ---


class TestWorkflowDescriptor:
    def test_valid(self):
        d = _descriptor()
        assert d.workflow_id == "wf-001"
        assert d.name == "test-workflow"
        assert len(d.stages) == 1

    def test_multi_stage(self):
        d = _descriptor(stages=(
            _stage("s1"),
            _stage("s2", predecessors=("s1",)),
        ))
        assert len(d.stages) == 2

    def test_with_bindings(self):
        binding = WorkflowBinding(
            binding_id="b1",
            source_stage_id="s1",
            source_output_key="out",
            target_stage_id="s2",
            target_input_key="in",
        )
        d = _descriptor(
            stages=(_stage("s1"), _stage("s2", predecessors=("s1",))),
            bindings=(binding,),
        )
        assert len(d.bindings) == 1

    def test_empty_workflow_id_rejected(self):
        with pytest.raises(ValueError, match="workflow_id"):
            _descriptor(workflow_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _descriptor(name="")

    def test_empty_stages_rejected(self):
        with pytest.raises(ValueError, match="stages"):
            _descriptor(stages=())

    def test_frozen(self):
        d = _descriptor()
        with pytest.raises(AttributeError):
            d.workflow_id = "changed"

    def test_serialization_round_trip(self):
        d = _descriptor()
        data = d.to_dict()
        assert data["workflow_id"] == "wf-001"
        assert isinstance(data["stages"], list)


# --- WorkflowTransition ---


class TestWorkflowTransition:
    def test_valid_sequential(self):
        t = WorkflowTransition(
            from_stage_id="s1",
            to_stage_id="s2",
            transition_type=TransitionType.SEQUENTIAL,
        )
        assert t.transition_type is TransitionType.SEQUENTIAL
        assert t.condition is None

    def test_conditional(self):
        t = WorkflowTransition(
            from_stage_id="s1",
            to_stage_id="s2",
            transition_type=TransitionType.CONDITIONAL,
            condition="output.success == true",
        )
        assert t.condition == "output.success == true"

    def test_on_failure(self):
        t = WorkflowTransition(
            from_stage_id="s1",
            to_stage_id="s3",
            transition_type=TransitionType.ON_FAILURE,
        )
        assert t.transition_type is TransitionType.ON_FAILURE

    def test_empty_from_stage_rejected(self):
        with pytest.raises(ValueError, match="from_stage_id"):
            WorkflowTransition(
                from_stage_id="",
                to_stage_id="s2",
                transition_type=TransitionType.SEQUENTIAL,
            )

    def test_invalid_transition_type_rejected(self):
        with pytest.raises(ValueError, match="transition_type"):
            WorkflowTransition(
                from_stage_id="s1",
                to_stage_id="s2",
                transition_type="bad",
            )


# --- StageExecutionResult ---


class TestStageExecutionResult:
    def test_valid(self):
        r = StageExecutionResult(
            stage_id="s1",
            status=StageStatus.COMPLETED,
            output={"result": "ok"},
            started_at=NOW,
            completed_at=NOW,
        )
        assert r.stage_id == "s1"
        assert r.status is StageStatus.COMPLETED
        assert r.output["result"] == "ok"

    def test_with_error(self):
        r = StageExecutionResult(
            stage_id="s1",
            status=StageStatus.FAILED,
            error="something broke",
            started_at=NOW,
            completed_at=NOW,
        )
        assert r.error == "something broke"

    def test_empty_stage_id_rejected(self):
        with pytest.raises(ValueError, match="stage_id"):
            StageExecutionResult(stage_id="", status=StageStatus.COMPLETED, started_at=NOW, completed_at=NOW)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            StageExecutionResult(stage_id="s1", status="bad", started_at=NOW, completed_at=NOW)

    def test_output_frozen(self):
        r = StageExecutionResult(
            stage_id="s1",
            status=StageStatus.COMPLETED,
            output={"key": "val"},
            started_at=NOW,
            completed_at=NOW,
        )
        with pytest.raises(TypeError):
            r.output["new_key"] = "new_val"


# --- WorkflowExecutionRecord ---


class TestWorkflowExecutionRecord:
    def test_valid(self):
        rec = WorkflowExecutionRecord(
            workflow_id="wf-001",
            execution_id="exec-001",
            status=WorkflowStatus.RUNNING,
            started_at="2025-01-01T00:00:00Z",
        )
        assert rec.workflow_id == "wf-001"
        assert rec.status is WorkflowStatus.RUNNING
        assert rec.completed_at is None

    def test_with_stage_results(self):
        result = StageExecutionResult(
            stage_id="s1",
            status=StageStatus.COMPLETED,
            started_at=NOW,
            completed_at=NOW,
        )
        rec = WorkflowExecutionRecord(
            workflow_id="wf-001",
            execution_id="exec-001",
            status=WorkflowStatus.COMPLETED,
            stage_results=(result,),
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:01:00Z",
        )
        assert len(rec.stage_results) == 1

    def test_empty_workflow_id_rejected(self):
        with pytest.raises(ValueError, match="workflow_id"):
            WorkflowExecutionRecord(
                workflow_id="",
                execution_id="exec-001",
                status=WorkflowStatus.RUNNING,
            )

    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            WorkflowExecutionRecord(
                workflow_id="wf-001",
                execution_id="",
                status=WorkflowStatus.RUNNING,
            )

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError, match="status"):
            WorkflowExecutionRecord(
                workflow_id="wf-001",
                execution_id="exec-001",
                status="bad",
            )


# --- WorkflowVerificationRecord ---


class TestWorkflowVerificationRecord:
    def test_verified(self):
        v = WorkflowVerificationRecord(
            execution_id="exec-001",
            verified=True,
            verified_at="2025-01-01T00:02:00Z",
        )
        assert v.verified is True
        assert v.mismatch_reasons == ()

    def test_not_verified_with_reasons(self):
        v = WorkflowVerificationRecord(
            execution_id="exec-001",
            verified=False,
            mismatch_reasons=("output mismatch on stage s2",),
            verified_at=NOW,
        )
        assert v.verified is False
        assert len(v.mismatch_reasons) == 1

    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            WorkflowVerificationRecord(
                execution_id="",
                verified=True,
                verified_at=NOW,
            )

    def test_non_bool_verified_rejected(self):
        with pytest.raises(ValueError, match="verified"):
            WorkflowVerificationRecord(
                execution_id="exec-001",
                verified="yes",
                verified_at=NOW,
            )
