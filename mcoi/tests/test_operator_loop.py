"""Purpose: verify single-step operator-loop orchestration for the MCOI runtime.
Governance scope: operator-loop tests only.
Dependencies: local bootstrap and operator-loop modules, runtime-core boundaries, and canonical contracts.
Invariants: boundary order is explicit, dispatch is gated, and execution is never marked complete without verification closure.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.adapters.executor_base import ExecutionRequest, derive_execution_id
from mcoi_runtime.adapters.filesystem_observer import FilesystemObservationMode, FilesystemObservationRequest
from mcoi_runtime.adapters.observer_base import ObservationResult, ObservationStatus
from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.operator_loop import ObservationDirective, OperatorLoop, OperatorRequest
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceStateCategory
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
            actual_effects=(EffectRecord(name="process_completed", details={"argv": list(request.argv)}),),
            assumed_effects=(),
            started_at="2026-03-18T12:00:00+00:00",
            finished_at="2026-03-18T12:00:01+00:00",
            metadata={"adapter": "fake"},
        )


@dataclass
class FakeObserver:
    calls: int = 0

    def observe(self, request: object) -> ObservationResult:
        self.calls += 1
        return ObservationResult(
            status=ObservationStatus.SUCCEEDED,
            evidence=(
                EvidenceRecord(
                    description="observer.workspace",
                    details={"count": 3},
                ),
            ),
        )


def test_operator_loop_processes_one_request_and_keeps_verification_open() -> None:
    executor = FakeExecutor()
    observer = FakeObserver()
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={"filesystem": observer},
    )
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template={
                "template_id": "template-1",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={"message": "hello"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            evidence_entries=(
                EvidenceInput(
                    evidence_id="evidence-1",
                    state_key="workspace.seed",
                    value={"ready": True},
                    category=EvidenceStateCategory.OBSERVED,
                ),
            ),
            observation_requests=(
                ObservationDirective(
                    observer_route="filesystem",
                    request=FilesystemObservationRequest(
                        path="C:/unused",
                        mode=FilesystemObservationMode.EXISTS,
                    ),
                    state_key="workspace.observed",
                ),
            ),
        )
    )

    assert executor.calls == 1
    assert observer.calls == 1
    assert report.dispatched is True
    assert report.execution_result is not None
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    assert report.validation_passed is True
    assert report.verification_closed is False
    assert report.completed is False


def test_operator_loop_stops_before_dispatch_on_policy_denial() -> None:
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={},
    )
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-2",
            subject_id="subject-1",
            goal_id="goal-1",
            template={
                "template_id": "template-2",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={"message": "hello"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            blocked_knowledge_ids=("knowledge-9",),
        )
    )

    assert executor.calls == 0
    assert report.dispatched is False
    assert report.execution_result is None
    assert report.policy_decision.status.value == "deny"
    assert report.validation_error == "policy_denied_or_escalated"


def test_operator_loop_stops_before_dispatch_on_validation_failure() -> None:
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={},
    )
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-3",
            subject_id="subject-1",
            goal_id="goal-1",
            template={
                "template_id": "template-3",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
        )
    )

    assert executor.calls == 0
    assert report.dispatched is False
    assert report.execution_result is None
    assert report.validation_passed is False
    assert report.validation_error is not None
    assert report.validation_error.startswith("missing_parameter:")


def test_operator_loop_stops_before_dispatch_on_admissibility_failure() -> None:
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={},
    )
    loop = OperatorLoop(runtime)

    report = loop.run_step(
        OperatorRequest(
            request_id="request-4",
            subject_id="subject-1",
            goal_id="goal-1",
            template={
                "template_id": "template-4",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={"message": "hello"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.CANDIDATE),
            ),
        )
    )

    assert executor.calls == 0
    assert report.dispatched is False
    assert report.execution_result is None
    assert len(report.planning_result.rejected) == 1
    assert report.validation_error == "planning_rejected_inadmissible_knowledge"


def test_operator_loop_marks_completion_only_with_explicit_verification() -> None:
    executor = FakeExecutor()
    runtime = bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        executors={"shell_command": executor},
        observers={},
    )
    loop = OperatorLoop(runtime)
    expected_execution_id = derive_execution_id(
        "goal-1",
        "shell_command",
        "template-5",
        {"message": "hello"},
    )
    verification = VerificationResult(
        verification_id="verification-1",
        execution_id=expected_execution_id,
        status=VerificationStatus.PASS,
        checks=(VerificationCheck(name="stdout_present", status=VerificationStatus.PASS),),
        evidence=(EvidenceRecord(description="verification.evidence", details={"ok": True}),),
        closed_at="2026-03-18T12:00:02+00:00",
    )

    report = loop.run_step(
        OperatorRequest(
            request_id="request-5",
            subject_id="subject-1",
            goal_id="goal-1",
            template={
                "template_id": "template-5",
                "action_type": "shell_command",
                "command_argv": ("python", "-c", "print('{message}')"),
                "required_parameters": ("message",),
            },
            bindings={"message": "hello"},
            knowledge_entries=(
                PlanningKnowledge("knowledge-1", "constraint", KnowledgeLifecycle.ADMITTED),
            ),
            verification_result=verification,
        )
    )

    assert report.execution_result is not None
    assert report.execution_result.execution_id == expected_execution_id
    assert report.verification_closed is True
    assert report.completed is True
