"""Purpose: verify team integration bridges — assignment by ownership, escalation,
    handoff with thread, view models, and console rendering.
Governance scope: team integration tests only.
Dependencies: team_integration bridges, conversation engine, escalation manager,
    org directory, view models, console renderers, and real team contracts/engine.
Invariants:
  - All tests are deterministic with injected clocks.
  - No network. No real persistence.
  - Uses real contract types and engine implementations.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.job import JobDescriptor, JobPriority
from mcoi_runtime.contracts.roles import (
    AssignmentDecision,
    AssignmentStrategy,
    HandoffReason,
    HandoffRecord,
    RoleDescriptor,
    WorkerCapacity,
    WorkerProfile,
    WorkerStatus,
    WorkloadSnapshot,
    TeamQueueState,
)
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry
from mcoi_runtime.core.team_integration import TeamJobBridge
from mcoi_runtime.core.conversation import ConversationEngine
from mcoi_runtime.core.organization import EscalationManager, OrgDirectory
from mcoi_runtime.contracts.organization import (
    EscalationChain,
    EscalationStep,
    OwnershipMapping,
    Person,
    RoleType,
    Team,
)
from mcoi_runtime.app.view_models import TeamSummaryView
from mcoi_runtime.app.console import render_team_summary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXED_CLOCK_VALUE = "2026-03-19T10:00:00+00:00"


def _fixed_clock() -> str:
    return FIXED_CLOCK_VALUE


@pytest.fixture()
def org_directory() -> OrgDirectory:
    return OrgDirectory(clock=_fixed_clock)


@pytest.fixture()
def escalation_manager(org_directory: OrgDirectory) -> EscalationManager:
    return EscalationManager(directory=org_directory, clock=_fixed_clock)


@pytest.fixture()
def conversation_engine() -> ConversationEngine:
    return ConversationEngine(clock=_fixed_clock)


@pytest.fixture()
def registry() -> WorkerRegistry:
    return WorkerRegistry(clock=_fixed_clock)


@pytest.fixture()
def team_engine(registry: WorkerRegistry) -> TeamEngine:
    return TeamEngine(registry=registry, clock=_fixed_clock)


def _setup_org_with_team(org_directory: OrgDirectory) -> tuple[str, str]:
    """Register a person, team, and ownership mapping. Returns (team_id, person_id)."""
    person = Person(
        person_id="p-alice",
        name="Alice",
        email="alice@example.com",
        roles=(RoleType.OWNER,),
    )
    org_directory.register_person(person)
    team = Team(team_id="team-alpha", name="Alpha Team", members=("p-alice",))
    org_directory.register_team(team)
    return "team-alpha", "p-alice"


def _setup_escalation_chain(org_directory: OrgDirectory) -> str:
    """Register an escalation chain. Returns chain_id."""
    step = EscalationStep(
        step_order=1,
        target_person_id="p-alice",
        timeout_minutes=30,
    )
    chain = EscalationChain(
        chain_id="chain-overload",
        name="Overload Escalation",
        steps=(step,),
        created_at=FIXED_CLOCK_VALUE,
    )
    org_directory.register_escalation_chain(chain)
    return "chain-overload"


def _make_role(role_id: str, name: str) -> RoleDescriptor:
    """Create a RoleDescriptor with required fields."""
    return RoleDescriptor(
        role_id=role_id,
        name=name,
        description=f"Role for {name}",
        required_skills=("general",),
    )


def _make_worker(
    worker_id: str,
    name: str,
    roles: tuple[str, ...],
    *,
    status: WorkerStatus = WorkerStatus.AVAILABLE,
    max_concurrent_jobs: int = 5,
) -> WorkerProfile:
    """Create a WorkerProfile with required fields."""
    return WorkerProfile(
        worker_id=worker_id,
        name=name,
        roles=roles,
        status=status,
        max_concurrent_jobs=max_concurrent_jobs,
    )


def _make_job(
    job_id: str,
    name: str,
    *,
    goal_id: str | None = None,
    workflow_id: str | None = None,
) -> JobDescriptor:
    """Create a JobDescriptor with required fields."""
    return JobDescriptor(
        job_id=job_id,
        name=name,
        description="test job",
        priority=JobPriority.NORMAL,
        created_at=FIXED_CLOCK_VALUE,
        goal_id=goal_id,
        workflow_id=workflow_id,
    )


# ---------------------------------------------------------------------------
# Tests: assign_job_by_ownership
# ---------------------------------------------------------------------------

class TestAssignJobByOwnership:
    """Tests for TeamJobBridge.assign_job_by_ownership."""

    def test_assigns_via_goal_ownership(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        org_directory: OrgDirectory,
    ) -> None:
        team_id, person_id = _setup_org_with_team(org_directory)
        org_directory.register_ownership(OwnershipMapping(
            resource_id="goal-1",
            resource_type="goal",
            owner_team_id=team_id,
        ))
        registry.register_role(_make_role("role-dev", "Developer"))
        registry.register_worker(_make_worker("w-alice", "Alice", ("role-dev",)))

        job = _make_job("job-1", "Fix bug", goal_id="goal-1")
        decision = TeamJobBridge.assign_job_by_ownership(team_engine, org_directory, job)

        assert decision is not None
        assert decision.job_id == "job-1"
        assert decision.worker_id == "w-alice"
        assert decision.role_id == "role-dev"

    def test_assigns_via_workflow_ownership(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        org_directory: OrgDirectory,
    ) -> None:
        team_id, _ = _setup_org_with_team(org_directory)
        org_directory.register_ownership(OwnershipMapping(
            resource_id="wf-deploy",
            resource_type="workflow",
            owner_team_id=team_id,
        ))
        registry.register_role(_make_role("role-ops", "Ops"))
        registry.register_worker(_make_worker("w-alice", "Alice", ("role-ops",)))

        job = _make_job("job-2", "Deploy", workflow_id="wf-deploy")
        decision = TeamJobBridge.assign_job_by_ownership(team_engine, org_directory, job)

        assert decision is not None
        assert decision.job_id == "job-2"
        assert decision.worker_id == "w-alice"

    def test_returns_none_when_no_ownership(
        self,
        team_engine: TeamEngine,
        org_directory: OrgDirectory,
    ) -> None:
        """No goal_id or workflow_id means no resource to look up ownership."""
        job = _make_job("job-3", "Orphan task")
        decision = TeamJobBridge.assign_job_by_ownership(team_engine, org_directory, job)

        assert decision is None

    def test_returns_none_when_no_workers_available(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        org_directory: OrgDirectory,
    ) -> None:
        team_id, _ = _setup_org_with_team(org_directory)
        org_directory.register_ownership(OwnershipMapping(
            resource_id="goal-empty",
            resource_type="goal",
            owner_team_id=team_id,
        ))
        registry.register_role(_make_role("role-x", "X"))
        # Register a worker that is OFFLINE so no available workers
        registry.register_worker(_make_worker(
            "w-offline", "Offline", ("role-x",),
            status=WorkerStatus.OFFLINE,
        ))

        job = _make_job("job-4", "No workers", goal_id="goal-empty")
        decision = TeamJobBridge.assign_job_by_ownership(team_engine, org_directory, job)

        assert decision is None


# ---------------------------------------------------------------------------
# Tests: escalate_overloaded
# ---------------------------------------------------------------------------

class TestEscalateOverloaded:
    """Tests for TeamJobBridge.escalate_overloaded."""

    def test_starts_escalation_chain(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        escalation_manager: EscalationManager,
        org_directory: OrgDirectory,
    ) -> None:
        _setup_org_with_team(org_directory)
        chain_id = _setup_escalation_chain(org_directory)
        registry.register_worker(_make_worker("w-bob", "Bob", ("role-gen",)))

        state = TeamJobBridge.escalate_overloaded(
            team_engine, escalation_manager, "w-bob", chain_id,
        )

        assert state.chain_id == chain_id
        assert state.current_step == 1
        assert state.resolved is False

    def test_escalation_uses_correct_chain(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        escalation_manager: EscalationManager,
        org_directory: OrgDirectory,
    ) -> None:
        _setup_org_with_team(org_directory)
        chain_id = _setup_escalation_chain(org_directory)
        registry.register_worker(_make_worker("w-charlie", "Charlie", ("role-gen",)))

        state = TeamJobBridge.escalate_overloaded(
            team_engine, escalation_manager, "w-charlie", chain_id,
        )

        assert state.chain_id == "chain-overload"
        assert state.started_at == FIXED_CLOCK_VALUE


# ---------------------------------------------------------------------------
# Tests: handoff_with_thread
# ---------------------------------------------------------------------------

class TestHandoffWithThread:
    """Tests for TeamJobBridge.handoff_with_thread."""

    def test_handoff_creates_record_and_updates_thread(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        conversation_engine: ConversationEngine,
    ) -> None:
        registry.register_worker(_make_worker("w-from", "From", ("role-gen",)))
        registry.register_worker(_make_worker("w-to", "To", ("role-gen",)))
        thread = conversation_engine.create_thread("Test job thread")

        record, updated_thread = TeamJobBridge.handoff_with_thread(
            team_engine, conversation_engine,
            job_id="job-h1",
            from_id="w-from",
            to_id="w-to",
            reason=HandoffReason.CAPACITY_EXCEEDED,
            thread=thread,
        )

        assert record.job_id == "job-h1"
        assert record.from_worker_id == "w-from"
        assert record.to_worker_id == "w-to"
        assert record.reason == HandoffReason.CAPACITY_EXCEEDED
        # Thread should have a new message about the handoff
        assert len(updated_thread.messages) == 1
        msg = updated_thread.messages[0]
        assert "handed off" in msg.content
        assert "w-from" in msg.content
        assert "w-to" in msg.content

    def test_handoff_message_contains_reason(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        conversation_engine: ConversationEngine,
    ) -> None:
        registry.register_worker(_make_worker("w-a", "A", ("role-gen",)))
        registry.register_worker(_make_worker("w-b", "B", ("role-gen",)))
        thread = conversation_engine.create_thread("Handoff reason test")

        _, updated_thread = TeamJobBridge.handoff_with_thread(
            team_engine, conversation_engine,
            job_id="job-h2",
            from_id="w-a",
            to_id="w-b",
            reason=HandoffReason.ROLE_CHANGE,
            thread=thread,
        )

        msg = updated_thread.messages[-1]
        assert "role_change" in msg.content

    def test_handoff_preserves_existing_messages(
        self,
        registry: WorkerRegistry,
        team_engine: TeamEngine,
        conversation_engine: ConversationEngine,
    ) -> None:
        registry.register_worker(_make_worker("w-x", "X", ("role-gen",)))
        registry.register_worker(_make_worker("w-y", "Y", ("role-gen",)))
        thread = conversation_engine.create_thread("Pre-existing messages")
        # Add a prior message via clarification
        thread, _ = conversation_engine.request_clarification(
            thread, "What is the scope?", "w-x",
        )
        original_count = len(thread.messages)

        _, updated_thread = TeamJobBridge.handoff_with_thread(
            team_engine, conversation_engine,
            job_id="job-h3",
            from_id="w-x",
            to_id="w-y",
            reason=HandoffReason.ESCALATION,
            thread=thread,
        )

        assert len(updated_thread.messages) == original_count + 1


# ---------------------------------------------------------------------------
# Tests: TeamSummaryView (direct construction — real WorkloadSnapshot has
# worker_capacities not total_workers/available_workers)
# ---------------------------------------------------------------------------

class TestTeamSummaryView:
    """Tests for TeamSummaryView direct construction."""

    def test_direct_construction_basic(self) -> None:
        view = TeamSummaryView(
            team_id="team-alpha",
            total_workers=5,
            available_workers=3,
            overloaded_workers=1,
            queued_jobs=4,
            assigned_jobs=2,
        )

        assert view.team_id == "team-alpha"
        assert view.total_workers == 5
        assert view.available_workers == 3
        assert view.overloaded_workers == 1
        assert view.queued_jobs == 4
        assert view.assigned_jobs == 2

    def test_zero_values(self) -> None:
        view = TeamSummaryView(
            team_id="empty-team",
            total_workers=0,
            available_workers=0,
            overloaded_workers=0,
            queued_jobs=0,
            assigned_jobs=0,
        )

        assert view.total_workers == 0
        assert view.available_workers == 0
        assert view.overloaded_workers == 0
        assert view.queued_jobs == 0
        assert view.assigned_jobs == 0


# ---------------------------------------------------------------------------
# Tests: render_team_summary
# ---------------------------------------------------------------------------

class TestRenderTeamSummary:
    """Tests for render_team_summary console function."""

    def test_render_contains_all_fields(self) -> None:
        view = TeamSummaryView(
            team_id="team-render",
            total_workers=8,
            available_workers=5,
            overloaded_workers=2,
            queued_jobs=10,
            assigned_jobs=6,
        )
        output = render_team_summary(view)

        assert "=== Team Summary ===" in output
        assert "team-render" in output
        assert "8" in output
        assert "5" in output
        assert "2" in output
        assert "10" in output
        assert "6" in output

    def test_render_deterministic(self) -> None:
        view = TeamSummaryView(
            team_id="team-det",
            total_workers=3,
            available_workers=2,
            overloaded_workers=0,
            queued_jobs=1,
            assigned_jobs=1,
        )
        assert render_team_summary(view) == render_team_summary(view)
