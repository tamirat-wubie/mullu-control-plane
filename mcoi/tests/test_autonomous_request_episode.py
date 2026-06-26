"""Purpose: verify autonomous request episode orchestration and receipt emission.
Governance scope: MCOI app-layer request episodes only.
Dependencies: local bootstrap, operator loop, autonomy contracts, and execution contracts.
Invariants: local reversible execution runs without prompts; external boundaries block before dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.app.autonomous_request import (
    AutonomousRequestAutomationState,
    AutonomousRequestCapabilityMetadata,
    AutonomousRequestEpisode,
    AutonomousRequestExecutor,
    AutonomousRequestIntent,
    AutonomousRequestPlan,
    AutonomousRequestPlanCompiler,
    AutonomousRequestPlanStep,
    RequestActionBoundary,
)
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.app.view_models import AutonomousRequestEpisodeSummaryView
from mcoi_runtime.contracts.autonomy import AutonomyDecisionStatus
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.contracts.workflow import StageType
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge


@dataclass
class FakeExecutor:
    calls: int = 0
    argv_history: tuple[tuple[str, ...], ...] = ()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        self.argv_history = self.argv_history + (tuple(request.argv),)
        return ExecutionResult(
            execution_id=request.execution_id,
            goal_id=request.goal_id,
            status=ExecutionOutcome.SUCCEEDED,
            actual_effects=(EffectRecord(name="local_change_completed", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at="2026-06-25T12:00:00+00:00",
            finished_at="2026-06-25T12:00:01+00:00",
            metadata={"adapter": "fake"},
        )


def _loop(executor: FakeExecutor) -> OperatorLoop:
    runtime = bootstrap_runtime(
        clock=lambda: "2026-06-25T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={},
    )
    return OperatorLoop(runtime)


def _local_request(
    request_id: str = "request-local-1",
    *,
    bindings: dict[str, str] | None = None,
) -> OperatorRequest:
    return OperatorRequest(
        request_id=request_id,
        subject_id="operator-1",
        goal_id="goal-autonomous-request",
        template={
            "template_id": "template-local",
            "action_type": "shell_command",
            "action_class": "execute_write",
            "command_argv": ("python", "-c", "print('{message}')"),
            "required_parameters": ("message",),
        },
        bindings={"message": "ok"} if bindings is None else bindings,
        knowledge_entries=(
            PlanningKnowledge("knowledge-local", "constraint", KnowledgeLifecycle.ADMITTED),
        ),
    )


def _external_request(request_id: str = "request-send-1") -> OperatorRequest:
    return OperatorRequest(
        request_id=request_id,
        subject_id="operator-1",
        goal_id="goal-autonomous-request",
        template={
            "template_id": "template-send",
            "action_type": "smtp_send",
            "action_class": "communicate",
            "command_argv": ("send", "{message}"),
            "required_parameters": ("message",),
        },
        bindings={"message": "hello"},
        knowledge_entries=(
            PlanningKnowledge("knowledge-send", "constraint", KnowledgeLifecycle.ADMITTED),
        ),
    )


def _capability_metadata(
    capability_id: str,
    *,
    message_parameter: str = "message",
    default_bindings: dict[str, str] | None = None,
    predecessor_capability_ids: tuple[str, ...] = (),
) -> AutonomousRequestCapabilityMetadata:
    return AutonomousRequestCapabilityMetadata(
        capability_id=capability_id,
        template={
            "template_id": f"template-{capability_id}",
            "action_type": "shell_command",
            "action_class": "execute_write",
            "command_argv": ("python", "-c", f"print('{{{message_parameter}}}')"),
            "required_parameters": (message_parameter,),
        },
        default_bindings={} if default_bindings is None else default_bindings,
        predecessor_capability_ids=predecessor_capability_ids,
        knowledge_entries=(
            PlanningKnowledge(f"knowledge-{capability_id}", "constraint", KnowledgeLifecycle.ADMITTED),
        ),
    )


def test_autonomous_request_episode_runs_local_step_without_prompt() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)

    receipt = AutonomousRequestExecutor(loop).run_episode(
        AutonomousRequestEpisode(
            episode_id="episode-local",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(_local_request(),),
        )
    )

    assert executor.calls == 1
    assert receipt.solver_outcome == SolverOutcome.SOLVED_UNVERIFIED.value
    assert receipt.automation_state == AutonomousRequestAutomationState.SETTLED_WITHOUT_PROMPT.value
    assert receipt.prompt_count == 0
    assert receipt.pending_approval_count == 0
    assert receipt.dispatched_count == 1
    assert receipt.action_count == 1
    assert receipt.no_bypass is True
    assert receipt.rollback_ref.endswith("/local-effects")
    assert len(receipt.receipt_refs) == 1
    assert receipt.step_receipts[0].boundary == RequestActionBoundary.LOCAL_REVERSIBLE.value
    assert receipt.step_receipts[0].autonomy_status == AutonomyDecisionStatus.ALLOWED.value
    assert receipt.step_receipts[0].execution_id in receipt.execution_ids
    assert receipt.repair_attempt_count == 0
    assert receipt.repaired_step_count == 0
    assert receipt.repair_receipt_refs == ()
    assert receipt.workflow_descriptor_ref is not None
    assert receipt.workflow_descriptor_ref.startswith("workflow://")
    assert receipt.workflow_stage_count == 1
    assert receipt.workflow_approval_stage_count == 0
    assert receipt.workflow_external_stage_count == 0

    summary = AutonomousRequestEpisodeSummaryView.from_receipt(receipt)
    assert summary.episode_id == "episode-local"
    assert summary.workflow_descriptor_ref == receipt.workflow_descriptor_ref
    assert summary.workflow_stage_count == 1
    assert summary.workflow_approval_stage_count == 0
    assert summary.workflow_external_stage_count == 0


def test_autonomous_request_episode_records_local_retry_repair() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)

    receipt = AutonomousRequestExecutor(loop).run_episode(
        AutonomousRequestEpisode(
            episode_id="episode-repair",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(_local_request(request_id="request-bad", bindings={}),),
            max_local_retries=1,
            retry_requests={
                "request-bad": (
                    _local_request(request_id="request-repair", bindings={"message": "fixed"}),
                ),
            },
        )
    )

    assert executor.calls == 1
    assert receipt.solver_outcome == SolverOutcome.SOLVED_UNVERIFIED.value
    assert receipt.dispatched_count == 1
    assert receipt.validation_errors == ()
    assert receipt.repair_attempt_count == 1
    assert receipt.repaired_step_count == 1
    assert len(receipt.repair_receipt_refs) == 1
    assert receipt.step_receipts[0].attempt_count == 2
    assert receipt.step_receipts[0].retry_count == 1
    assert receipt.step_receipts[0].validation_error is None
    assert receipt.step_receipts[0].repair_receipts[0].request_id == "request-repair"
    assert receipt.step_receipts[0].repair_receipts[0].trigger.startswith("missing_parameter")


def test_autonomous_request_episode_runs_validated_plan_in_dependency_order() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)
    analyze_request = _local_request(
        request_id="request-analyze",
        bindings={"message": "analyze"},
    )
    apply_request = _local_request(
        request_id="request-apply",
        bindings={"message": "apply"},
    )
    plan = AutonomousRequestPlan(
        plan_id="plan-two-step",
        steps=(
            AutonomousRequestPlanStep(
                stage_id="stage-apply",
                request=apply_request,
                predecessors=("stage-analyze",),
            ),
            AutonomousRequestPlanStep(
                stage_id="stage-analyze",
                request=analyze_request,
            ),
        ),
    )

    receipt = AutonomousRequestExecutor(loop).run_episode(
        AutonomousRequestEpisode.from_plan(
            episode_id="episode-plan",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            plan=plan,
        )
    )

    assert executor.calls == 2
    assert executor.argv_history[0][-1] == "print('analyze')"
    assert executor.argv_history[1][-1] == "print('apply')"
    assert receipt.solver_outcome == SolverOutcome.SOLVED_UNVERIFIED.value
    assert receipt.plan_id == "plan-two-step"
    assert receipt.planned_stage_count == 2
    assert receipt.blocked_dependency_count == 0
    assert receipt.plan_receipt_ref is not None
    assert tuple(step.plan_stage_id for step in receipt.step_receipts) == (
        "stage-analyze",
        "stage-apply",
    )
    assert receipt.step_receipts[1].plan_predecessors == ("stage-analyze",)
    assert len(receipt.receipt_refs) == 2


def test_autonomous_request_plan_compiles_to_workflow_descriptor_without_prompt_gate() -> None:
    plan = AutonomousRequestPlan(
        plan_id="plan-local-workflow",
        steps=(
            AutonomousRequestPlanStep(
                stage_id="stage-inspect",
                request=_local_request("request-inspect", bindings={"message": "inspect"}),
            ),
            AutonomousRequestPlanStep(
                stage_id="stage-apply",
                request=_local_request("request-apply", bindings={"message": "apply"}),
                predecessors=("stage-inspect",),
            ),
        ),
    )

    descriptor = plan.to_workflow_descriptor(
        workflow_id="workflow-local",
        created_at="2026-06-25T12:00:00+00:00",
    )

    assert descriptor.workflow_id == "workflow-local"
    assert descriptor.name == "autonomous-request-continuation"
    assert tuple(stage.stage_id for stage in descriptor.stages) == ("stage-inspect", "stage-apply")
    assert tuple(stage.stage_type for stage in descriptor.stages) == (
        StageType.SKILL_EXECUTION,
        StageType.SKILL_EXECUTION,
    )
    assert tuple(stage.predecessors for stage in descriptor.stages) == ((), ("stage-inspect",))
    assert tuple(stage.skill_id for stage in descriptor.stages) == ("template-local", "template-local")


def test_autonomous_request_plan_adds_approval_gate_for_external_boundary() -> None:
    plan = AutonomousRequestPlan(
        plan_id="plan-external-workflow",
        steps=(
            AutonomousRequestPlanStep(stage_id="stage-plan", request=_local_request()),
            AutonomousRequestPlanStep(
                stage_id="stage-send",
                request=_external_request(),
                predecessors=("stage-plan",),
            ),
        ),
    )

    descriptor = plan.to_workflow_descriptor(
        workflow_id="workflow-external",
        created_at="2026-06-25T12:00:00+00:00",
        has_approval=False,
    )

    assert tuple(stage.stage_id for stage in descriptor.stages) == (
        "stage-plan",
        "approval-stage-send",
        "stage-send",
    )
    assert tuple(stage.stage_type for stage in descriptor.stages) == (
        StageType.SKILL_EXECUTION,
        StageType.APPROVAL_GATE,
        StageType.COMMUNICATION,
    )
    assert descriptor.stages[1].predecessors == ("stage-plan",)
    assert descriptor.stages[2].predecessors == ("stage-plan", "approval-stage-send")
    assert descriptor.stages[2].skill_id == "template-send"


def test_autonomous_request_plan_omits_external_gate_when_approval_exists() -> None:
    plan = AutonomousRequestPlan(
        plan_id="plan-approved-external-workflow",
        steps=(
            AutonomousRequestPlanStep(
                stage_id="stage-send",
                request=_external_request(),
            ),
        ),
    )

    descriptor = plan.to_workflow_descriptor(
        created_at="2026-06-25T12:00:00+00:00",
        has_approval=True,
    )

    assert descriptor.workflow_id == "workflow-plan-approved-external-workflow"
    assert len(descriptor.stages) == 1
    assert descriptor.stages[0].stage_id == "stage-send"
    assert descriptor.stages[0].stage_type is StageType.COMMUNICATION
    assert descriptor.stages[0].predecessors == ()


def test_autonomous_request_episode_compiles_raw_requests_to_workflow_descriptor() -> None:
    episode = AutonomousRequestEpisode(
        episode_id="episode-raw-external",
        subject_id="operator-1",
        goal_id="goal-autonomous-request",
        requests=(_external_request("request-send-raw"),),
        has_approval=False,
    )

    descriptor = episode.to_workflow_descriptor(
        workflow_id="workflow-raw-external",
        created_at="2026-06-25T12:00:00+00:00",
    )

    assert descriptor.workflow_id == "workflow-raw-external"
    assert tuple(stage.stage_id for stage in descriptor.stages) == (
        "approval-request-send-raw",
        "request-send-raw",
    )
    assert tuple(stage.stage_type for stage in descriptor.stages) == (
        StageType.APPROVAL_GATE,
        StageType.COMMUNICATION,
    )
    assert descriptor.stages[0].predecessors == ()
    assert descriptor.stages[1].predecessors == ("approval-request-send-raw",)


def test_autonomous_request_episode_blocks_plan_dependent_stage_after_failed_predecessor() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)
    failing_request = _local_request(request_id="request-fail", bindings={})
    dependent_request = _local_request(request_id="request-dependent", bindings={"message": "unused"})
    plan = AutonomousRequestPlan(
        plan_id="plan-block-dependent",
        steps=(
            AutonomousRequestPlanStep(stage_id="stage-fail", request=failing_request),
            AutonomousRequestPlanStep(
                stage_id="stage-dependent",
                request=dependent_request,
                predecessors=("stage-fail",),
            ),
        ),
    )

    receipt = AutonomousRequestExecutor(loop).run_episode(
        AutonomousRequestEpisode.from_plan(
            episode_id="episode-plan-blocked",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            plan=plan,
        )
    )

    assert executor.calls == 0
    assert receipt.solver_outcome == SolverOutcome.GOVERNANCE_BLOCKED.value
    assert receipt.automation_state == AutonomousRequestAutomationState.GOVERNANCE_BLOCKED.value
    assert receipt.plan_id == "plan-block-dependent"
    assert receipt.planned_stage_count == 2
    assert receipt.blocked_dependency_count == 1
    assert receipt.dispatched_count == 0
    assert receipt.validation_errors[0].startswith("missing_parameter")
    assert receipt.validation_errors[1] == "dependency_blocked:stage-fail"
    assert receipt.step_receipts[1].autonomy_status == AutonomyDecisionStatus.REJECTED.value
    assert receipt.step_receipts[1].autonomy_reason == "predecessor stage did not settle"
    assert receipt.step_receipts[1].structured_error_codes == ("dependency_blocked",)
    assert receipt.step_receipts[1].plan_predecessors == ("stage-fail",)


def test_autonomous_request_plan_rejects_cycles_before_execution() -> None:
    first_request = _local_request(request_id="request-cycle-a", bindings={"message": "a"})
    second_request = _local_request(request_id="request-cycle-b", bindings={"message": "b"})

    with pytest.raises(Exception, match="plan stage graph must not contain cycles"):
        AutonomousRequestPlan(
            plan_id="plan-cycle",
            steps=(
                AutonomousRequestPlanStep(
                    stage_id="stage-a",
                    request=first_request,
                    predecessors=("stage-b",),
                ),
                AutonomousRequestPlanStep(
                    stage_id="stage-b",
                    request=second_request,
                    predecessors=("stage-a",),
                ),
            ),
        )


def test_autonomous_request_plan_compiler_expands_capability_dependencies() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)
    compiler = AutonomousRequestPlanCompiler(
        {
            "capability-analyze": _capability_metadata(
                "capability-analyze",
                message_parameter="source",
            ),
            "capability-apply": _capability_metadata(
                "capability-apply",
                message_parameter="target",
                default_bindings={"target": "apply"},
                predecessor_capability_ids=("capability-analyze",),
            ),
        }
    )

    episode = compiler.compile_episode(
        AutonomousRequestIntent(
            episode_id="episode-compiled-plan",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            capability_ids=("capability-apply",),
            bindings={"source": "inspect"},
        )
    )
    receipt = AutonomousRequestExecutor(loop).run_episode(episode)

    assert tuple(step.stage_id for step in episode.plan.steps) == (
        "stage-capability-analyze",
        "stage-capability-apply",
    )
    assert tuple(request.bindings for request in episode.requests) == (
        {"source": "inspect"},
        {"target": "apply"},
    )
    assert executor.calls == 2
    assert executor.argv_history[0][-1] == "print('inspect')"
    assert executor.argv_history[1][-1] == "print('apply')"
    assert receipt.solver_outcome == SolverOutcome.SOLVED_UNVERIFIED.value
    assert receipt.plan_id == episode.plan.plan_id
    assert receipt.planned_stage_count == 2
    assert receipt.blocked_dependency_count == 0


def test_autonomous_request_plan_compiler_rejects_missing_required_bindings() -> None:
    compiler = AutonomousRequestPlanCompiler(
        {
            "capability-analyze": _capability_metadata(
                "capability-analyze",
                message_parameter="source",
            ),
        }
    )

    with pytest.raises(Exception, match="capability required bindings are missing"):
        compiler.compile_episode(
            AutonomousRequestIntent(
                episode_id="episode-missing-binding",
                subject_id="operator-1",
                goal_id="goal-autonomous-request",
                capability_ids=("capability-analyze",),
                bindings={},
            )
        )


def test_autonomous_request_plan_compiler_rejects_dependency_cycles() -> None:
    compiler = AutonomousRequestPlanCompiler(
        {
            "capability-a": _capability_metadata(
                "capability-a",
                predecessor_capability_ids=("capability-b",),
            ),
            "capability-b": _capability_metadata(
                "capability-b",
                predecessor_capability_ids=("capability-a",),
            ),
        }
    )

    with pytest.raises(Exception, match="capability dependency graph must not contain cycles"):
        compiler.compile_episode(
            AutonomousRequestIntent(
                episode_id="episode-cycle",
                subject_id="operator-1",
                goal_id="goal-autonomous-request",
                capability_ids=("capability-a",),
                bindings={"message": "loop"},
            )
        )


def test_autonomous_request_episode_respects_retry_ceiling() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)

    receipt = AutonomousRequestExecutor(loop).run_episode(
        AutonomousRequestEpisode(
            episode_id="episode-repair-ceiling",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(_local_request(request_id="request-bad", bindings={}),),
            max_local_retries=0,
            retry_requests={
                "request-bad": (
                    _local_request(request_id="request-repair", bindings={"message": "fixed"}),
                ),
            },
        )
    )

    assert executor.calls == 0
    assert receipt.solver_outcome == SolverOutcome.GOVERNANCE_BLOCKED.value
    assert receipt.dispatched_count == 0
    assert receipt.repair_attempt_count == 0
    assert receipt.repaired_step_count == 0
    assert receipt.step_receipts[0].attempt_count == 1
    assert receipt.step_receipts[0].retry_count == 0
    assert receipt.step_receipts[0].validation_error is not None


def test_autonomous_request_episode_blocks_external_retry_candidate() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)

    receipt = AutonomousRequestExecutor(loop).run_episode(
        AutonomousRequestEpisode(
            episode_id="episode-external-retry",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(_local_request(request_id="request-bad", bindings={}),),
            max_local_retries=1,
            retry_requests={
                "request-bad": (
                    _external_request("request-external-repair"),
                ),
            },
        )
    )

    assert executor.calls == 0
    assert receipt.solver_outcome == SolverOutcome.GOVERNANCE_BLOCKED.value
    assert receipt.dispatched_count == 0
    assert receipt.repair_attempt_count == 1
    assert receipt.repaired_step_count == 0
    assert receipt.step_receipts[0].retry_count == 1
    assert receipt.step_receipts[0].repair_receipts[0].autonomy_status == (
        AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL.value
    )
    assert receipt.step_receipts[0].repair_receipts[0].dispatched is False


def test_autonomous_request_episode_blocks_external_communication_without_approval() -> None:
    executor = FakeExecutor()
    loop = _loop(executor)

    receipt = loop.run_autonomous_request_episode(
        AutonomousRequestEpisode(
            episode_id="episode-external",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(
                _external_request(),
            ),
        )
    )

    assert executor.calls == 0
    assert receipt.solver_outcome == SolverOutcome.AWAITING_EVIDENCE.value
    assert receipt.automation_state == AutonomousRequestAutomationState.AWAITING_APPROVAL.value
    assert receipt.prompt_count == 1
    assert receipt.pending_approval_count == 1
    assert receipt.dispatched_count == 0
    assert receipt.blocked_count == 1
    assert receipt.execution_ids == ()
    assert receipt.rollback_ref.endswith("/no-effects")
    assert receipt.step_receipts[0].boundary == RequestActionBoundary.EXTERNAL_COMMUNICATION.value
    assert receipt.step_receipts[0].autonomy_status == AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL.value
    assert receipt.repair_attempt_count == 0
    assert receipt.repaired_step_count == 0
    assert receipt.workflow_descriptor_ref is not None
    assert receipt.workflow_stage_count == 2
    assert receipt.workflow_approval_stage_count == 1
    assert receipt.workflow_external_stage_count == 1


def test_autonomous_request_episode_rejects_empty_request_tuple() -> None:
    with pytest.raises(Exception, match="requests must be a non-empty tuple"):
        AutonomousRequestEpisode(
            episode_id="episode-empty",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(),
        )
