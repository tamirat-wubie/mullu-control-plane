"""Purpose: verify foundational contract constructors match schema shape.

Governance scope: old shared plan, environment, and execution contracts.
Dependencies: mcoi_runtime.contracts foundational modules and pytest.
Invariants: runtime constructors reject shapes that shared JSON schemas reject.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.environment import (
    EnvironmentFingerprint,
    PlatformDescriptor,
    RuntimeDescriptor,
)
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.plan import Plan, PlanItem
from mcoi_runtime.contracts.replay import ReplayEffect, ReplayMode, ReplayRecord
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.contracts.workflow import (
    StageExecutionResult,
    StageStatus,
    StageType,
    WorkflowBinding,
    WorkflowDescriptor,
    WorkflowExecutionRecord,
    WorkflowStage,
    WorkflowStatus,
    WorkflowVerificationRecord,
)


NOW = "2026-05-13T12:00:00+00:00"


def test_plan_item_dependencies_reject_scalar_shape() -> None:
    item = PlanItem(item_id="step-2", description="child", depends_on=["step-1"])  # type: ignore[arg-type]

    assert item.depends_on == ("step-1",)
    assert isinstance(item.depends_on, tuple)
    assert item.to_json_dict()["depends_on"] == ["step-1"]

    with pytest.raises(ValueError, match="depends_on must be an array"):
        PlanItem(item_id="step-2", description="child", depends_on="step-1")  # type: ignore[arg-type]


def test_plan_dependency_graph_rejects_invalid_edges() -> None:
    base = PlanItem(item_id="step-1", description="root")
    child = PlanItem(item_id="step-2", description="child", depends_on=("step-1",))

    plan = Plan(
        plan_id="plan-1",
        goal_id="goal-1",
        state_hash="state",
        registry_hash="registry",
        items=(base, child),
    )

    assert len(plan.items) == 2
    assert plan.items[1].depends_on == ("step-1",)
    assert plan.to_json_dict()["items"][1]["depends_on"] == ["step-1"]

    with pytest.raises(ValueError, match="unique item_id"):
        Plan(
            plan_id="plan-1",
            goal_id="goal-1",
            state_hash="state",
            registry_hash="registry",
            items=(base, PlanItem(item_id="step-1", description="duplicate")),
        )
    with pytest.raises(ValueError, match="declared item_id"):
        Plan(
            plan_id="plan-1",
            goal_id="goal-1",
            state_hash="state",
            registry_hash="registry",
            items=(PlanItem(item_id="step-2", description="child", depends_on=("missing",)),),
        )
    with pytest.raises(ValueError, match="dependency cycles"):
        Plan(
            plan_id="plan-1",
            goal_id="goal-1",
            state_hash="state",
            registry_hash="registry",
            items=(
                PlanItem(item_id="step-1", description="root", depends_on=("step-2",)),
                PlanItem(item_id="step-2", description="child", depends_on=("step-1",)),
            ),
        )


def test_environment_fingerprint_rejects_descriptor_shape_drift() -> None:
    fingerprint = EnvironmentFingerprint(
        fingerprint_id="env-1",
        captured_at="2026-05-13T12:00:00+00:00",
        digest="sha256:abc",
        platform=PlatformDescriptor(os="windows", architecture="x64"),
        runtime=RuntimeDescriptor(name="python", version="3.13"),
    )

    assert fingerprint.platform is not None
    assert fingerprint.runtime is not None
    assert fingerprint.to_json_dict()["platform"]["os"] == "windows"

    with pytest.raises(ValueError, match="PlatformDescriptor"):
        EnvironmentFingerprint(
            fingerprint_id="env-1",
            captured_at="2026-05-13T12:00:00+00:00",
            digest="sha256:abc",
            platform={"os": "windows"},  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="RuntimeDescriptor"):
        EnvironmentFingerprint(
            fingerprint_id="env-1",
            captured_at="2026-05-13T12:00:00+00:00",
            digest="sha256:abc",
            runtime={"name": "python"},  # type: ignore[arg-type]
        )


def test_execution_result_rejects_effect_shape_drift() -> None:
    result = ExecutionResult(
        execution_id="exec-1",
        goal_id="goal-1",
        status=ExecutionOutcome.SUCCEEDED,
        actual_effects=[EffectRecord(name="witness")],  # type: ignore[arg-type]
        assumed_effects=[],
        started_at="2026-05-13T12:00:00+00:00",
        finished_at="2026-05-13T12:00:01+00:00",
    )

    assert result.actual_effects == (EffectRecord(name="witness"),)
    assert result.assumed_effects == ()
    assert result.to_json_dict()["actual_effects"][0]["name"] == "witness"

    with pytest.raises(ValueError, match="actual_effects must be an array"):
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects="witness",  # type: ignore[arg-type]
            assumed_effects=(),
            started_at="2026-05-13T12:00:00+00:00",
            finished_at="2026-05-13T12:00:01+00:00",
        )
    with pytest.raises(ValueError, match=r"actual_effects\[0\] must be an EffectRecord"):
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=("witness",),  # type: ignore[arg-type]
            assumed_effects=(),
            started_at="2026-05-13T12:00:00+00:00",
            finished_at="2026-05-13T12:00:01+00:00",
        )
    with pytest.raises(ValueError, match=r"assumed_effects\[0\] must be an EffectRecord"):
        ExecutionResult(
            execution_id="exec-1",
            goal_id="goal-1",
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(),
            assumed_effects=("witness",),  # type: ignore[arg-type]
            started_at="2026-05-13T12:00:00+00:00",
            finished_at="2026-05-13T12:00:01+00:00",
        )


def test_workflow_descriptor_rejects_graph_shape_drift() -> None:
    root = WorkflowStage(stage_id="stage-1", stage_type=StageType.SKILL_EXECUTION)
    child = WorkflowStage(stage_id="stage-2", stage_type=StageType.OBSERVATION, predecessors=["stage-1"])  # type: ignore[arg-type]
    binding = WorkflowBinding(
        binding_id="binding-1",
        source_stage_id="stage-1",
        source_output_key="result",
        target_stage_id="stage-2",
        target_input_key="input",
    )

    descriptor = WorkflowDescriptor(
        workflow_id="workflow-1",
        name="workflow",
        stages=[root, child],  # type: ignore[arg-type]
        bindings=[binding],  # type: ignore[arg-type]
        created_at=NOW,
    )

    assert descriptor.stages == (root, child)
    assert descriptor.bindings == (binding,)
    assert descriptor.to_json_dict()["stages"][1]["predecessors"] == ["stage-1"]

    with pytest.raises(ValueError, match="predecessors must be an array"):
        WorkflowStage(stage_id="stage-2", stage_type=StageType.OBSERVATION, predecessors="stage-1")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unique stage_id"):
        WorkflowDescriptor(
            workflow_id="workflow-1",
            name="workflow",
            stages=(root, WorkflowStage(stage_id="stage-1", stage_type=StageType.OBSERVATION)),
            bindings=(),
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="declared stage_id"):
        WorkflowDescriptor(
            workflow_id="workflow-1",
            name="workflow",
            stages=(WorkflowStage(stage_id="stage-2", stage_type=StageType.OBSERVATION, predecessors=("missing",)),),
            bindings=(),
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="predecessor cycles"):
        WorkflowDescriptor(
            workflow_id="workflow-1",
            name="workflow",
            stages=(
                WorkflowStage(stage_id="stage-1", stage_type=StageType.SKILL_EXECUTION, predecessors=("stage-2",)),
                WorkflowStage(stage_id="stage-2", stage_type=StageType.OBSERVATION, predecessors=("stage-1",)),
            ),
            bindings=(),
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="bindings must reference declared stage_id"):
        WorkflowDescriptor(
            workflow_id="workflow-1",
            name="workflow",
            stages=(root,),
            bindings=(binding,),
            created_at=NOW,
        )
    with pytest.raises(ValueError, match="bindings must be an array"):
        WorkflowDescriptor(
            workflow_id="workflow-1",
            name="workflow",
            stages=(root,),
            bindings="binding-1",  # type: ignore[arg-type]
            created_at=NOW,
        )


def test_workflow_execution_and_verification_reject_sequence_shape_drift() -> None:
    stage_result = StageExecutionResult(
        stage_id="stage-1",
        status=StageStatus.COMPLETED,
        started_at=NOW,
        completed_at=NOW,
    )

    record = WorkflowExecutionRecord(
        workflow_id="workflow-1",
        execution_id="execution-1",
        status=WorkflowStatus.COMPLETED,
        stage_results=[stage_result],  # type: ignore[arg-type]
        started_at=NOW,
        completed_at=NOW,
    )
    verification = WorkflowVerificationRecord(
        execution_id="execution-1",
        verified=False,
        mismatch_reasons=["stage output changed"],  # type: ignore[arg-type]
        verified_at=NOW,
    )

    assert record.stage_results == (stage_result,)
    assert verification.mismatch_reasons == ("stage output changed",)
    assert record.to_json_dict()["stage_results"][0]["status"] == "completed"

    with pytest.raises(ValueError, match="stage_results must be an array"):
        WorkflowExecutionRecord(
            workflow_id="workflow-1",
            execution_id="execution-1",
            status=WorkflowStatus.COMPLETED,
            stage_results="stage-1",  # type: ignore[arg-type]
            started_at=NOW,
            completed_at=NOW,
        )
    with pytest.raises(ValueError, match=r"stage_results\[0\] must be a StageExecutionResult"):
        WorkflowExecutionRecord(
            workflow_id="workflow-1",
            execution_id="execution-1",
            status=WorkflowStatus.COMPLETED,
            stage_results=("stage-1",),  # type: ignore[arg-type]
            started_at=NOW,
            completed_at=NOW,
        )
    with pytest.raises(ValueError, match="mismatch_reasons must be an array"):
        WorkflowVerificationRecord(
            execution_id="execution-1",
            verified=False,
            mismatch_reasons="stage output changed",  # type: ignore[arg-type]
            verified_at=NOW,
        )


def test_replay_record_rejects_effect_sequence_shape_drift() -> None:
    effect = ReplayEffect(effect_id="effect-1", description="observed output")
    record = ReplayRecord(
        replay_id="replay-1",
        trace_id="trace-1",
        source_hash="sha256:abc",
        approved_effects=[effect],  # type: ignore[arg-type]
        blocked_effects=[],
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at=NOW,
    )

    assert record.approved_effects == (effect,)
    assert record.blocked_effects == ()
    assert record.to_json_dict()["approved_effects"][0]["effect_id"] == "effect-1"

    with pytest.raises(ValueError, match="approved_effects must be an array"):
        ReplayRecord(
            replay_id="replay-1",
            trace_id="trace-1",
            source_hash="sha256:abc",
            approved_effects="effect-1",  # type: ignore[arg-type]
            blocked_effects=(),
            mode=ReplayMode.OBSERVATION_ONLY,
            recorded_at=NOW,
        )
    with pytest.raises(ValueError, match=r"approved_effects\[0\] must be a ReplayEffect"):
        ReplayRecord(
            replay_id="replay-1",
            trace_id="trace-1",
            source_hash="sha256:abc",
            approved_effects=("effect-1",),  # type: ignore[arg-type]
            blocked_effects=(),
            mode=ReplayMode.OBSERVATION_ONLY,
            recorded_at=NOW,
        )
    with pytest.raises(ValueError, match=r"blocked_effects\[0\] must be a ReplayEffect"):
        ReplayRecord(
            replay_id="replay-1",
            trace_id="trace-1",
            source_hash="sha256:abc",
            approved_effects=(),
            blocked_effects=("effect-1",),  # type: ignore[arg-type]
            mode=ReplayMode.OBSERVATION_ONLY,
            recorded_at=NOW,
        )


def test_verification_result_rejects_record_sequence_shape_drift() -> None:
    check = VerificationCheck(name="effect observed", status=VerificationStatus.PASS)
    evidence = EvidenceRecord(description="observer capture")
    result = VerificationResult(
        verification_id="verification-1",
        execution_id="execution-1",
        status=VerificationStatus.PASS,
        checks=[check],  # type: ignore[arg-type]
        evidence=[evidence],  # type: ignore[arg-type]
        closed_at=NOW,
    )

    assert result.checks == (check,)
    assert result.evidence == (evidence,)
    assert result.to_json_dict()["checks"][0]["status"] == "pass"

    with pytest.raises(ValueError, match="checks must be an array"):
        VerificationResult(
            verification_id="verification-1",
            execution_id="execution-1",
            status=VerificationStatus.PASS,
            checks="effect observed",  # type: ignore[arg-type]
            evidence=(evidence,),
            closed_at=NOW,
        )
    with pytest.raises(ValueError, match=r"checks\[0\] must be a VerificationCheck"):
        VerificationResult(
            verification_id="verification-1",
            execution_id="execution-1",
            status=VerificationStatus.PASS,
            checks=("effect observed",),  # type: ignore[arg-type]
            evidence=(evidence,),
            closed_at=NOW,
        )
    with pytest.raises(ValueError, match=r"evidence\[0\] must be an EvidenceRecord"):
        VerificationResult(
            verification_id="verification-1",
            execution_id="execution-1",
            status=VerificationStatus.PASS,
            checks=(check,),
            evidence=("observer capture",),  # type: ignore[arg-type]
            closed_at=NOW,
        )
