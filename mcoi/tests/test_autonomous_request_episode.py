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
    AutonomousRequestEpisode,
    AutonomousRequestExecutor,
    RequestActionBoundary,
)
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.contracts.autonomy import AutonomyDecisionStatus
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.solver_outcome import SolverOutcome
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge


@dataclass
class FakeExecutor:
    calls: int = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
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
                    OperatorRequest(
                        request_id="request-external-repair",
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
                    ),
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
                OperatorRequest(
                    request_id="request-send-1",
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
                ),
            ),
        )
    )

    assert executor.calls == 0
    assert receipt.solver_outcome == SolverOutcome.AWAITING_EVIDENCE.value
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


def test_autonomous_request_episode_rejects_empty_request_tuple() -> None:
    with pytest.raises(Exception, match="requests must be a non-empty tuple"):
        AutonomousRequestEpisode(
            episode_id="episode-empty",
            subject_id="operator-1",
            goal_id="goal-autonomous-request",
            requests=(),
        )
