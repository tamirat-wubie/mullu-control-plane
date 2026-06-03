"""Tests for Stage-A shadow mode wired into the live OperatorLoop.

Proves the end-to-end wiring: (1) default-OFF leaves OperatorLoop byte-identical
(no shadow_loop, nothing observed); (2) attaching a shadow observer makes a
dispatched run ALSO produce a ShadowObservation without changing the live result;
(3) a failing shadow path never breaks the real request (error captured, report
returned); (4) malformed flag is a hard validation error; (5) the env selector is
default-OFF. Reuses the proven dispatched-request fixture from test_operator_loop.
>=3 assertions per test.
"""
from __future__ import annotations

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.cognitive_loop_integration import (
    COGNITIVE_LOOP_SHADOW_ENV,
    attach_shadow_observer,
    validate_cognitive_loop_shadow_config,
)
from mcoi_runtime.app.operator_loop import ObservationDirective, OperatorLoop, OperatorRequest
from mcoi_runtime.adapters.filesystem_observer import (
    FilesystemObservationMode,
    FilesystemObservationRequest,
)
from mcoi_runtime.contracts.execution import ExecutionOutcome
from mcoi_runtime.core.cognitive_loop import ShadowObservation
from mcoi_runtime.core.evidence_merger import EvidenceInput, EvidenceStateCategory
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge

from test_operator_loop import FakeExecutor, FakeObserver


def _runtime():
    return bootstrap_runtime(
        clock=lambda: "2026-03-18T12:00:00+00:00",
        executors={"shell_command": FakeExecutor()},
        observers={"filesystem": FakeObserver()},
    )


def _dispatched_request() -> OperatorRequest:
    return OperatorRequest(
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


# --------------------------------------------------------------------------
# Default-OFF: live path byte-identical
# --------------------------------------------------------------------------


def test_default_off_attaches_nothing_and_observes_nothing():
    runtime = _runtime()
    loop = OperatorLoop(runtime)

    attached = attach_shadow_observer({}, runtime, loop)  # no flag => off

    assert attached is False
    assert loop.shadow_loop is None

    report = loop.run_step(_dispatched_request())
    assert report.dispatched is True
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    assert loop.shadow_observations == []  # nothing observed when off
    assert loop.shadow_errors == []


def test_validate_shadow_disabled_by_default():
    report = validate_cognitive_loop_shadow_config({})
    assert report.enabled is False
    assert report.error is None


def test_validate_shadow_rejects_unknown_value():
    report = validate_cognitive_loop_shadow_config({COGNITIVE_LOOP_SHADOW_ENV: "perhaps"})
    assert report.enabled is False
    assert report.error is not None
    assert COGNITIVE_LOOP_SHADOW_ENV in report.error


def test_attach_malformed_flag_raises():
    runtime = _runtime()
    loop = OperatorLoop(runtime)
    try:
        attach_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "maybe"}, runtime, loop)
        raised = False
    except ValueError:
        raised = True
    assert raised is True
    assert loop.shadow_loop is None  # not enabled on malformed flag


# --------------------------------------------------------------------------
# Enabled: observes without perturbing the live result
# --------------------------------------------------------------------------


def test_enabled_shadow_observes_dispatched_run_without_changing_result():
    runtime = _runtime()
    loop = OperatorLoop(runtime)

    attached = attach_shadow_observer({COGNITIVE_LOOP_SHADOW_ENV: "1"}, runtime, loop)
    assert attached is True
    assert loop.shadow_loop is not None

    report = loop.run_step(_dispatched_request())

    # Live result identical to the default-off path.
    assert report.dispatched is True
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    assert report.completed is False  # verification still open, unchanged
    # Shadow produced exactly one observation, and no errors.
    assert len(loop.shadow_observations) == 1
    assert isinstance(loop.shadow_observations[0], ShadowObservation)
    assert loop.shadow_errors == []
    obs = loop.shadow_observations[0]
    assert obs.goal_id == "goal-1"
    assert obs.execution_id == report.execution_result.execution_id


def test_shadow_failure_never_breaks_the_live_request():
    runtime = _runtime()

    class _BoomShadow:
        def shadow_observe(self, *args, **kwargs):
            raise RuntimeError("boom")

    loop = OperatorLoop(runtime, shadow_loop=_BoomShadow())

    report = loop.run_step(_dispatched_request())

    # The live request still succeeds despite the shadow blowing up.
    assert report.dispatched is True
    assert report.execution_result.status is ExecutionOutcome.SUCCEEDED
    # The failure is recorded (no silent failure), not raised.
    assert len(loop.shadow_errors) == 1
    assert "boom" in loop.shadow_errors[0]
    assert loop.shadow_observations == []
