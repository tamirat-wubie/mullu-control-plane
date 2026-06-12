"""Purpose: verify job integration bridges -- conversation, learning, escalation, views, console.
Governance scope: job integration tests only.
Dependencies: job_integration bridges, conversation engine, learning engine, escalation manager,
    view models, console renderers, and real job contracts/engine.
Invariants:
  - All tests are deterministic with injected clocks.
  - No network. No real persistence.
  - Uses real contract types and real JobEngine (no stubs).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from mcoi_runtime.adapters.executor_base import ExecutionRequest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.goal import GoalDescriptor, GoalPriority
from mcoi_runtime.contracts.job import (
    JobDescriptor,
    JobPriority,
    JobState,
    JobStatus,
    PauseReason,
    SlaStatus,
)
from mcoi_runtime.contracts.organization import (
    EscalationChain,
    EscalationStep,
    Person,
    RoleType,
    Team,
)
from mcoi_runtime.contracts.conversation import ThreadStatus
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.contracts.whqr import EvidenceGate, GateResult, NormGate, TruthGate, WHQRNode, WHRole
from mcoi_runtime.core.dispatcher import Dispatcher
from mcoi_runtime.core.governed_dispatcher import GovernedDispatcher
from mcoi_runtime.core.conversation import ConversationEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.jobs import JobEngine
from mcoi_runtime.core.job_integration import (
    JobConversationBridge,
    JobEscalationBridge,
    JobLearningBridge,
    JobWHQROrchestrationBridge,
)
from mcoi_runtime.core.learning import LearningEngine
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.organization import EscalationManager, OrgDirectory
from mcoi_runtime.core.system_stabilization import EquilibriumEngine
from mcoi_runtime.core.template_validator import TemplateValidator
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.whqr.binding_preflight import validate_binding_preflight
from mcoi_runtime.whqr.clarification import (
    build_binding_clarification_requests,
    build_binding_map_from_clarification_responses,
)
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.app.view_models import JobSummaryView
from mcoi_runtime.app.console import render_job_summary

# ---------------------------------------------------------------------------
# Deterministic clock helpers
# ---------------------------------------------------------------------------

_T0 = "2026-03-19T00:00:00+00:00"
_T1 = "2026-03-19T01:00:00+00:00"
_T2 = "2026-03-19T02:00:00+00:00"
_T3 = "2026-03-19T03:00:00+00:00"
_T4 = "2026-03-19T04:00:00+00:00"
_T5 = "2026-03-19T05:00:00+00:00"
_T6 = "2026-03-19T06:00:00+00:00"
_T7 = "2026-03-19T07:00:00+00:00"
_T8 = "2026-03-19T08:00:00+00:00"
_T9 = "2026-03-19T09:00:00+00:00"
_T10 = "2026-03-19T10:00:00+00:00"
_T11 = "2026-03-19T11:00:00+00:00"
_T12 = "2026-03-19T12:00:00+00:00"
_T13 = "2026-03-19T13:00:00+00:00"
_T14 = "2026-03-19T14:00:00+00:00"
_T15 = "2026-03-19T15:00:00+00:00"
_T16 = "2026-03-19T16:00:00+00:00"
_T17 = "2026-03-19T17:00:00+00:00"
_T18 = "2026-03-19T18:00:00+00:00"
_T19 = "2026-03-19T19:00:00+00:00"
_T20 = "2026-03-19T20:00:00+00:00"

VALID_TEMPLATE = {
    "template_id": "tpl-gov",
    "action_type": "shell_command",
    "command_argv": ("echo", "{msg}"),
    "required_parameters": ("msg",),
}


def _stepping_clock(times: list[str] | None = None):
    """Return a callable that yields successive timestamps from a list."""
    times = times or [
        _T0, _T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10,
        _T11, _T12, _T13, _T14, _T15, _T16, _T17, _T18, _T19, _T20,
    ]
    it = iter(times)
    return lambda: next(it)


@dataclass
class FakeExecutor:
    """Executor test double that records deterministic successful calls."""

    calls: int = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(
            request.execution_id,
            request.goal_id,
            ExecutionOutcome.SUCCEEDED,
            (EffectRecord("process_completed", {"argv": list(request.argv)}),),
            (),
            _T12,
            _T12,
        )


# ---------------------------------------------------------------------------
# Helpers: create a real job and advance it to IN_PROGRESS
# ---------------------------------------------------------------------------


def _create_and_start_job(
    engine: JobEngine,
    *,
    name: str = "Deploy staging",
    description: str = "Deploy the staging environment",
    priority: JobPriority = JobPriority.NORMAL,
    goal_id: str | None = "goal-42",
    deadline: str | None = "2026-03-20T00:00:00+00:00",
    sla_target_minutes: int | None = None,
) -> tuple[JobDescriptor, JobState]:
    """Create a job via the real JobEngine and start it (transition to IN_PROGRESS)."""
    descriptor, _created_state = engine.create_job(
        name,
        description,
        priority,
        goal_id=goal_id,
        deadline=deadline,
        sla_target_minutes=sla_target_minutes,
    )
    started_state = engine.start_job(descriptor.job_id)
    return descriptor, started_state


def _make_escalation_fixtures(clock):
    """Build org directory with people, team, and escalation chain."""
    org = OrgDirectory(clock=clock)
    p1 = Person(
        person_id="person-1", name="Alice", email="alice@test.com",
        roles=(RoleType.ESCALATION_TARGET,),
    )
    p2 = Person(
        person_id="person-2", name="Bob", email="bob@test.com",
        roles=(RoleType.ESCALATION_TARGET,),
    )
    org.register_person(p1)
    org.register_person(p2)
    team = Team(team_id="team-1", name="Ops", members=("person-1", "person-2"))
    org.register_team(team)
    chain = EscalationChain(
        chain_id="chain-1",
        name="Overdue Job",
        steps=(
            EscalationStep(step_order=1, target_person_id="person-1", timeout_minutes=30),
            EscalationStep(step_order=2, target_person_id="person-2", timeout_minutes=60),
        ),
        created_at=_T0,
    )
    org.register_escalation_chain(chain)
    esc_mgr = EscalationManager(directory=org, clock=clock)
    return org, esc_mgr


def _whqr_binding_request(thread_id: str):
    report = validate_binding_preflight(
        WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor")
    )
    return build_binding_clarification_requests(
        report,
        thread_id=thread_id,
        requested_from_id="op-1",
        requested_at=_T8,
    ).requests[0]


def _governed_dispatcher() -> tuple[GovernedDispatcher, FakeExecutor]:
    executor = FakeExecutor()
    equilibrium = EquilibriumEngine()
    equilibrium.register_agent("operator")
    dispatcher = Dispatcher(TemplateValidator(), {"shell_command": executor}, lambda: _T12)
    return GovernedDispatcher(dispatcher, equilibrium=equilibrium, clock=lambda: _T12), executor


def _whqr_goal() -> GoalDescriptor:
    return GoalDescriptor("goal-42", "Govern vendor command", GoalPriority.NORMAL, _T7)


def _vendor_context() -> WHQREvaluationContext:
    return WHQREvaluationContext(
        node_results={
            "vendor": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.PROVEN),
        }
    )


# ===================================================================
# TEST: JobConversationBridge -- thread creation
# ===================================================================


class TestJobThreadCreation:
    def test_create_job_thread_returns_thread(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _state = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        assert thread.subject == "Deploy staging"
        assert thread.goal_id == "goal-42"
        assert thread.status == ThreadStatus.OPEN

    def test_create_job_thread_without_goal(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _state = _create_and_start_job(engine, goal_id=None)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        assert thread.goal_id is None
        assert thread.subject == "Deploy staging"

    def test_create_job_thread_uses_job_name_as_subject(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _state = _create_and_start_job(engine, name="Run backups")
        thread = JobConversationBridge.create_job_thread(desc, conv)
        assert thread.subject == "Run backups"

    def test_create_job_thread_has_nonempty_thread_id(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _state = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        assert thread.thread_id
        assert len(thread.thread_id) > 0


# ===================================================================
# TEST: JobConversationBridge -- pause with clarification
# ===================================================================


class TestPauseWithClarification:
    def test_pause_returns_paused_state(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)

        state, updated_thread, clarif = JobConversationBridge.pause_job_with_clarification(
            engine, conv, desc.job_id, "What environment?", "operator-1", thread=thread,
        )
        assert state.status == JobStatus.PAUSED
        assert state.pause_reason == PauseReason.AWAITING_RESPONSE

    def test_pause_creates_clarification_request(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)

        _state, _thread, clarif = JobConversationBridge.pause_job_with_clarification(
            engine, conv, desc.job_id, "What environment?", "operator-1", thread=thread,
        )
        assert clarif.question == "What environment?"
        assert clarif.requested_from_id == "operator-1"

    def test_pause_transitions_thread_to_waiting(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)

        _state, updated_thread, _clarif = JobConversationBridge.pause_job_with_clarification(
            engine, conv, desc.job_id, "What environment?", "operator-1", thread=thread,
        )
        assert updated_thread.status == ThreadStatus.WAITING


# ===================================================================
# TEST: JobConversationBridge -- resume on response
# ===================================================================


class TestResumeOnResponse:
    def test_resume_returns_in_progress(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)

        _state, paused_thread, clarif = JobConversationBridge.pause_job_with_clarification(
            engine, conv, desc.job_id, "Which branch?", "op-1", thread=thread,
        )
        state, _t, _r = JobConversationBridge.resume_on_response(
            engine, conv, desc.job_id, "main branch", "op-1",
            thread=paused_thread, clarification_request=clarif,
        )
        assert state.status == JobStatus.IN_PROGRESS

    def test_resume_creates_clarification_response(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)

        _s, paused_thread, clarif = JobConversationBridge.pause_job_with_clarification(
            engine, conv, desc.job_id, "Which branch?", "op-1", thread=thread,
        )
        _s2, _t2, response = JobConversationBridge.resume_on_response(
            engine, conv, desc.job_id, "main branch", "op-1",
            thread=paused_thread, clarification_request=clarif,
        )
        assert response.answer == "main branch"
        assert response.responded_by_id == "op-1"

    def test_resume_transitions_thread_to_active(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)

        _s, paused_thread, clarif = JobConversationBridge.pause_job_with_clarification(
            engine, conv, desc.job_id, "Which branch?", "op-1", thread=thread,
        )
        _s2, resumed_thread, _r = JobConversationBridge.resume_on_response(
            engine, conv, desc.job_id, "main branch", "op-1",
            thread=paused_thread, clarification_request=clarif,
        )
        assert resumed_thread.status == ThreadStatus.ACTIVE


class TestWHQRBindingClarificationBridge:
    def test_persist_whqr_binding_clarification_requests_are_replayable(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        request = _whqr_binding_request(thread.thread_id)

        updated_thread = JobConversationBridge.persist_whqr_binding_clarification_requests(
            thread,
            (request,),
        )
        replay = JobConversationBridge.replay_whqr_binding_clarifications(updated_thread)

        assert updated_thread.status == ThreadStatus.WAITING
        assert len(updated_thread.messages) == 1
        assert updated_thread.messages[0].metadata["whqr_binding"] is True
        assert updated_thread.messages[0].metadata["clarification_request_id"] == request.request_id
        assert replay.requests == (request,)
        assert replay.responses == ()
        assert replay.ready_for_binding_map is False

    def test_persist_whqr_binding_clarification_response_feeds_binding_map(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        request = _whqr_binding_request(thread.thread_id)
        waiting_thread = JobConversationBridge.persist_whqr_binding_clarification_requests(
            thread,
            (request,),
        )

        active_thread, response = JobConversationBridge.persist_whqr_binding_clarification_response(
            conv,
            waiting_thread,
            request,
            "entity_ref=vendor:acme;evidence_ref=evidence:vendor-doc-1",
            "op-1",
        )
        replay = JobConversationBridge.replay_whqr_binding_clarifications(active_thread)
        binding_map = build_binding_map_from_clarification_responses(replay.requests, replay.responses)

        assert active_thread.status == ThreadStatus.ACTIVE
        assert response.request_id == request.request_id
        assert replay.ready_for_binding_map is True
        assert replay.requests == (request,)
        assert replay.responses == (response,)
        assert binding_map.passed is True
        assert binding_map.accepted_count == 1
        assert binding_map.as_binding_candidates()["vendor"].entity_ref == "vendor:acme"

    def test_whqr_binding_bridge_rejects_non_whqr_clarification_context(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        _waiting_thread, general_request = conv.request_clarification(
            thread,
            "Which branch?",
            "op-1",
        )

        with pytest.raises(RuntimeCoreInvariantError, match="WHQR binding context"):
            JobConversationBridge.persist_whqr_binding_clarification_requests(
                thread,
                (general_request,),
            )

    def test_whqr_binding_replay_rejects_malformed_metadata(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        request = _whqr_binding_request(thread.thread_id)
        waiting_thread = JobConversationBridge.persist_whqr_binding_clarification_requests(
            thread,
            (request,),
        )
        malformed_message = replace(waiting_thread.messages[0], metadata={"whqr_binding": True})
        malformed_thread = replace(waiting_thread, messages=(malformed_message,))

        with pytest.raises(RuntimeCoreInvariantError, match="clarification_request_id"):
            JobConversationBridge.replay_whqr_binding_clarifications(malformed_thread)


class TestJobWHQROrchestrationBridge:
    def test_run_from_thread_replay_completes_after_binding_response(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        expr = WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor")
        request = _whqr_binding_request(thread.thread_id)
        waiting_thread = JobConversationBridge.persist_whqr_binding_clarification_requests(thread, (request,))
        active_thread, _response = JobConversationBridge.persist_whqr_binding_clarification_response(
            conv,
            waiting_thread,
            request,
            "entity_ref=vendor:acme;evidence_ref=evidence:vendor-doc-1",
            "op-1",
        )
        governed, executor = _governed_dispatcher()
        memory = EpisodicMemory()

        result = JobWHQROrchestrationBridge.run_from_thread_replay(
            thread=active_thread,
            expr=expr,
            goal=_whqr_goal(),
            subject_id="operator",
            issued_at=_T13,
            governed=governed,
            certifier=TerminalClosureCertifier(clock=lambda: _T12),
            episodic=memory,
            actor_id="operator",
            intent_id="intent",
            template=VALID_TEMPLATE,
            bindings={"msg": "hi"},
            context=_vendor_context(),
            capability="shell_command",
        )

        assert result.completed is True
        assert result.next_step == "complete"
        assert result.clarification_binding_map is not None
        assert result.clarification_binding_map.accepted_count == 1
        assert isinstance(result.whqr_document.root, WHQRNode)
        assert result.whqr_document.root.entity_ref == "vendor:acme"
        assert result.whqr_document.root.evidence_ref == "evidence:vendor-doc-1"
        assert result.terminal_bundle is not None
        assert result.terminal_bundle.certificate.disposition is TerminalClosureDisposition.COMMITTED
        assert memory.size == 1
        assert executor.calls == 1

    def test_run_from_thread_replay_rejects_goal_mismatch(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        conv = ConversationEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)
        thread = JobConversationBridge.create_job_thread(desc, conv)
        governed, _executor = _governed_dispatcher()

        with pytest.raises(RuntimeCoreInvariantError, match="goal_id"):
            JobWHQROrchestrationBridge.run_from_thread_replay(
                thread=thread,
                expr=WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor"),
                goal=GoalDescriptor("other-goal", "Govern vendor command", GoalPriority.NORMAL, _T7),
                subject_id="operator",
                issued_at=_T13,
                governed=governed,
                certifier=TerminalClosureCertifier(clock=lambda: _T12),
                episodic=EpisodicMemory(),
                actor_id="operator",
                intent_id="intent",
                template=VALID_TEMPLATE,
                bindings={"msg": "hi"},
                context=_vendor_context(),
                capability="shell_command",
            )


# ===================================================================
# TEST: JobLearningBridge -- record job outcome
# ===================================================================


class TestJobOutcomeLessonRecording:
    def test_record_success_lesson(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        lesson = JobLearningBridge.record_job_outcome(
            learning, "job-1", outcome_success=True, context="staging deployment",
        )
        assert "succeeded" in lesson.outcome
        assert lesson.source_id == "job-1"
        assert "staging deployment" in lesson.context

    def test_record_failure_lesson(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        lesson = JobLearningBridge.record_job_outcome(
            learning, "job-2", outcome_success=False, context="prod rollback",
        )
        assert "failed" in lesson.outcome
        assert lesson.source_id == "job-2"

    def test_lesson_is_retrievable(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        JobLearningBridge.record_job_outcome(
            learning, "job-1", outcome_success=True, context="staging deploy",
        )
        found = learning.find_relevant_lessons(("staging",))
        assert len(found) == 1
        assert found[0].source_id == "job-1"

    def test_lesson_has_non_empty_id(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        lesson = JobLearningBridge.record_job_outcome(
            learning, "job-x", outcome_success=True, context="test context",
        )
        assert lesson.lesson_id
        assert len(lesson.lesson_id) > 0


# ===================================================================
# TEST: JobLearningBridge -- workflow confidence update
# ===================================================================


class TestWorkflowConfidenceUpdate:
    def test_success_increases_confidence(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        # Default confidence is 0.5
        result = JobLearningBridge.update_workflow_confidence(
            learning, "workflow-1", success=True,
        )
        assert result.value > 0.5

    def test_failure_decreases_confidence(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        result = JobLearningBridge.update_workflow_confidence(
            learning, "workflow-1", success=False,
        )
        assert result.value < 0.5

    def test_confidence_has_reason(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        result = JobLearningBridge.update_workflow_confidence(
            learning, "workflow-1", success=True,
        )
        assert "increase" in result.reason

    def test_consecutive_successes_increase_further(self):
        clock = _stepping_clock()
        learning = LearningEngine(clock=clock)
        r1 = JobLearningBridge.update_workflow_confidence(learning, "wf-1", success=True)
        r2 = JobLearningBridge.update_workflow_confidence(learning, "wf-1", success=True)
        assert r2.value > r1.value


# ===================================================================
# TEST: JobEscalationBridge
# ===================================================================


class TestJobEscalationBridge:
    def test_escalate_overdue_pauses_job(self):
        clock = _stepping_clock()
        org, esc_mgr = _make_escalation_fixtures(clock)
        engine = JobEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)

        _esc_state = JobEscalationBridge.escalate_overdue_job(
            engine, esc_mgr, org, desc.job_id, "chain-1",
        )
        # Job should now be paused -- access internal state for verification
        job_state = engine._states[desc.job_id]
        assert job_state.status == JobStatus.PAUSED
        assert job_state.pause_reason == PauseReason.OPERATOR_HOLD

    def test_escalate_overdue_returns_escalation_state(self):
        clock = _stepping_clock()
        org, esc_mgr = _make_escalation_fixtures(clock)
        engine = JobEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)

        esc_state = JobEscalationBridge.escalate_overdue_job(
            engine, esc_mgr, org, desc.job_id, "chain-1",
        )
        assert esc_state.chain_id == "chain-1"
        assert esc_state.current_step == 1
        assert esc_state.resolved is False

    def test_check_and_advance_after_timeout(self):
        clock = _stepping_clock()
        org, esc_mgr = _make_escalation_fixtures(clock)
        engine = JobEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)

        esc_state = JobEscalationBridge.escalate_overdue_job(
            engine, esc_mgr, org, desc.job_id, "chain-1",
        )
        # Check at 1 hour later (> 30 min step-1 timeout)
        should_escalate, next_step = JobEscalationBridge.check_and_advance_escalation(
            esc_mgr, esc_state, _T8,  # well past timeout
        )
        assert should_escalate is True
        assert next_step is not None
        assert next_step.target_person_id == "person-2"

    def test_check_and_advance_within_timeout(self):
        clock = _stepping_clock()
        org, esc_mgr = _make_escalation_fixtures(clock)
        engine = JobEngine(clock=clock)
        desc, _started = _create_and_start_job(engine)

        esc_state = JobEscalationBridge.escalate_overdue_job(
            engine, esc_mgr, org, desc.job_id, "chain-1",
        )
        # The escalation started_at is the 4th clock tick (_T3 = 03:00).
        # Check at only 10 minutes after that: 03:10 (well within 30-min timeout).
        ten_min_later = "2026-03-19T03:10:00+00:00"
        should_escalate, next_step = JobEscalationBridge.check_and_advance_escalation(
            esc_mgr, esc_state, ten_min_later,
        )
        assert should_escalate is False
        assert next_step is None


# ===================================================================
# TEST: JobSummaryView
# ===================================================================


class TestJobSummaryView:
    def test_from_state_basic(self):
        """Build a view from real JobState and JobDescriptor."""
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        desc, started = _create_and_start_job(engine)
        view = JobSummaryView.from_state(started, desc)
        assert view.job_id == desc.job_id
        assert view.name == "Deploy staging"
        assert view.status == "in_progress"
        assert view.priority == "normal"
        assert view.sla_status == "not_applicable"
        # Real JobState has current_assignment_id not assigned_to;
        # from_state uses hasattr(state, "assigned_to") which returns False
        assert view.assigned_to is None
        assert view.deadline == "2026-03-20T00:00:00+00:00"

    def test_from_state_no_deadline(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        desc, started = _create_and_start_job(engine, deadline=None)
        view = JobSummaryView.from_state(started, desc)
        assert view.deadline is None

    def test_from_state_high_priority(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        desc, started = _create_and_start_job(engine, priority=JobPriority.HIGH)
        view = JobSummaryView.from_state(started, desc)
        assert view.priority == "high"

    def test_view_is_frozen(self):
        clock = _stepping_clock()
        engine = JobEngine(clock=clock)
        desc, started = _create_and_start_job(engine)
        view = JobSummaryView.from_state(started, desc)
        with pytest.raises(AttributeError):
            view.name = "changed"  # type: ignore[misc]


# ===================================================================
# TEST: Console rendering
# ===================================================================


class TestConsoleJobRendering:
    def test_render_job_summary_basic(self):
        view = JobSummaryView(
            job_id="job-1",
            name="Deploy staging",
            status="in_progress",
            priority="normal",
            sla_status="on_track",
            assigned_to="agent-1",
            thread_id="thread-abc",
            deadline="2026-03-20T00:00:00+00:00",
        )
        text = render_job_summary(view)
        assert "=== Job Summary ===" in text
        assert "job-1" in text
        assert "Deploy staging" in text
        assert "in_progress" in text
        assert "normal" in text
        assert "on_track" in text
        assert "agent-1" in text
        assert "thread-abc" in text
        assert "2026-03-20" in text

    def test_render_job_summary_unassigned(self):
        view = JobSummaryView(
            job_id="job-2",
            name="Cleanup logs",
            status="queued",
            priority="low",
            sla_status="unknown",
            assigned_to=None,
            thread_id=None,
            deadline=None,
        )
        text = render_job_summary(view)
        assert "(unassigned)" in text
        assert "(none)" in text

    def test_render_is_deterministic(self):
        view = JobSummaryView(
            job_id="job-3",
            name="Test job",
            status="completed",
            priority="high",
            sla_status="on_track",
            assigned_to="op-1",
            thread_id="t-1",
            deadline="2026-04-01T00:00:00+00:00",
        )
        assert render_job_summary(view) == render_job_summary(view)
