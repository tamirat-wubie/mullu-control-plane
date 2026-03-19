"""Purpose: verify operator loop produces structured errors at each failure point.
Governance scope: operator-loop error reporting tests only.
Dependencies: operator loop, bootstrap, error taxonomy.
Invariants: every failure path produces typed StructuredError in the report.
"""

from __future__ import annotations

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.operator_loop import OperatorLoop, OperatorRequest
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.core.errors import ErrorFamily, Recoverability
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge


_VALID_TEMPLATE = {
    "template_id": "test-tpl",
    "action_type": "shell_command",
    "command_argv": ["echo", "hello"],
}
_CLOCK_VALUE = "2026-03-19T00:00:00+00:00"


def _make_loop() -> OperatorLoop:
    runtime = bootstrap_runtime(
        config=AppConfig(
            allowed_planning_classes=("constraint",),
            enabled_executor_routes=("shell_command",),
            enabled_observer_routes=("filesystem",),
        ),
        clock=lambda: _CLOCK_VALUE,
    )
    return OperatorLoop(runtime=runtime)


def test_admissibility_failure_produces_structured_error() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
            knowledge_entries=(
                PlanningKnowledge("k-1", "constraint", KnowledgeLifecycle.BLOCKED),
            ),
        )
    )

    assert not report.completed
    assert len(report.structured_errors) == 1
    err = report.structured_errors[0]
    assert err.family is ErrorFamily.ADMISSIBILITY
    assert err.error_code == "planning_rejected_inadmissible_knowledge"
    assert err.recoverability is Recoverability.APPROVAL_REQUIRED
    assert "k-1" in err.related_ids


def test_policy_denial_produces_structured_error() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
            blocked_knowledge_ids=("blocked-1",),
        )
    )

    assert not report.completed
    assert len(report.structured_errors) == 1
    err = report.structured_errors[0]
    assert err.family is ErrorFamily.POLICY
    assert "deny" in err.error_code
    assert err.recoverability is Recoverability.FATAL_FOR_RUN


def test_policy_escalation_produces_structured_error() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
            requires_operator_review=True,
        )
    )

    assert not report.completed
    assert len(report.structured_errors) == 1
    err = report.structured_errors[0]
    assert err.family is ErrorFamily.POLICY
    assert "escalate" in err.error_code
    assert err.recoverability is Recoverability.APPROVAL_REQUIRED


def test_validation_failure_produces_structured_error() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template={"template_id": "bad", "action_type": "invalid_type", "command_argv": ["x"]},
            bindings={},
        )
    )

    assert not report.completed
    assert len(report.structured_errors) == 1
    err = report.structured_errors[0]
    assert err.family is ErrorFamily.VALIDATION


def test_successful_dispatch_with_open_verification_has_no_errors() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
        )
    )

    assert report.dispatched
    assert report.structured_errors == ()


def test_verification_mismatch_produces_structured_error() -> None:
    loop = _make_loop()
    report = loop.run_step(
        OperatorRequest(
            request_id="req-1",
            subject_id="subject-1",
            goal_id="goal-1",
            template=_VALID_TEMPLATE,
            bindings={},
            verification_result=VerificationResult(
                verification_id="ver-wrong",
                execution_id="wrong-execution-id",
                status=VerificationStatus.PASS,
                checks=(
                    VerificationCheck(
                        name="test check",
                        status=VerificationStatus.PASS,
                    ),
                ),
                evidence=(EvidenceRecord(description="test evidence"),),
                closed_at="2026-03-19T00:00:00+00:00",
            ),
        )
    )

    assert report.dispatched
    assert report.verification_error is not None
    assert len(report.structured_errors) == 1
    err = report.structured_errors[0]
    assert err.family is ErrorFamily.VERIFICATION
    assert err.error_code == "verification_closure_error"
