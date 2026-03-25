"""Purpose: golden scenarios for team runtime integration — end-to-end flows
    that verify correct behavior across team engine, org directory, escalation,
    and conversation subsystems.
Governance scope: golden scenario tests only.
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
# Helpers
# ---------------------------------------------------------------------------

FIXED_CLOCK = "2026-03-19T10:00:00+00:00"


def _clock() -> str:
    return FIXED_CLOCK


def _make_org() -> OrgDirectory:
    return OrgDirectory(clock=_clock)


def _make_escalation(org: OrgDirectory) -> EscalationManager:
    return EscalationManager(directory=org, clock=_clock)


def _make_convo() -> ConversationEngine:
    return ConversationEngine(clock=_clock)


def _make_registry() -> WorkerRegistry:
    return WorkerRegistry(clock=_clock)


def _make_engine(registry: WorkerRegistry) -> TeamEngine:
    return TeamEngine(registry=registry, clock=_clock)


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
        created_at=FIXED_CLOCK,
        goal_id=goal_id,
        workflow_id=workflow_id,
    )


def _seed_team(
    org: OrgDirectory,
    team_id: str = "team-alpha",
    member_ids: tuple[str, ...] = ("p-alice",),
) -> None:
    """Register persons and team in org directory."""
    for pid in member_ids:
        try:
            org.register_person(Person(
                person_id=pid,
                name=pid.replace("p-", "").title(),
                email=f"{pid}@example.com",
                roles=(RoleType.OWNER,),
            ))
        except (ValueError, Exception):
            pass  # already registered
    try:
        org.register_team(Team(team_id=team_id, name=team_id, members=member_ids))
    except (ValueError, Exception):
        pass


# ===========================================================================
# Golden Scenario 1: Job assigned to correct role by ownership lookup
# ===========================================================================


class TestGoldenScenario1_OwnershipAssignment:
    """A job whose goal_id maps to a team via ownership should be assigned
    to a worker on that team with the correct role."""

    def test_ownership_maps_goal_to_team_and_assigns_worker(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-backend", ("p-dev1", "p-dev2"))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-api-fix",
            resource_type="goal",
            owner_team_id="team-backend",
        ))
        registry.register_role(_make_role("role-backend-dev", "Backend Dev"))
        registry.register_worker(_make_worker(
            "w-dev1", "Dev1", ("role-backend-dev",),
        ))
        registry.register_worker(_make_worker(
            "w-dev2", "Dev2", ("role-backend-dev",),
        ))

        job = _make_job("job-api", "Fix API", goal_id="goal-api-fix")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is not None
        assert decision.worker_id in ("w-dev1", "w-dev2")
        assert decision.role_id == "role-backend-dev"

    def test_ownership_lookup_returns_correct_worker(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-data", ("p-analyst",))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-report",
            resource_type="goal",
            owner_team_id="team-data",
        ))
        registry.register_role(_make_role("role-analyst", "Analyst"))
        registry.register_worker(_make_worker(
            "w-analyst", "Analyst", ("role-analyst",),
        ))

        job = _make_job("job-report", "Gen report", goal_id="goal-report")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is not None
        assert decision.worker_id == "w-analyst"

    def test_ownership_via_workflow_id_when_no_goal(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-ops", ("p-ops1",))
        org.register_ownership(OwnershipMapping(
            resource_id="wf-ci-cd",
            resource_type="workflow",
            owner_team_id="team-ops",
        ))
        registry.register_role(_make_role("role-ops", "Ops"))
        registry.register_worker(_make_worker(
            "w-ops1", "Ops1", ("role-ops",),
        ))

        job = _make_job("job-ci", "Run CI", workflow_id="wf-ci-cd")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is not None
        assert decision.worker_id == "w-ops1"


# ===========================================================================
# Golden Scenario 2: Overloaded worker triggers escalation
# ===========================================================================


class TestGoldenScenario2_OverloadEscalation:
    """An overloaded worker triggers an escalation chain via the bridge."""

    def test_overloaded_worker_triggers_escalation_chain(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        esc = _make_escalation(org)
        _seed_team(org, "team-alpha", ("p-alice",))
        step = EscalationStep(step_order=1, target_person_id="p-alice", timeout_minutes=15)
        org.register_escalation_chain(EscalationChain(
            chain_id="chain-overload", name="Overload", steps=(step,), created_at=FIXED_CLOCK,
        ))
        registry.register_worker(_make_worker("w-alice", "Alice", ("role-gen",)))

        state = TeamJobBridge.escalate_overloaded(engine, esc, "w-alice", "chain-overload")

        assert state.chain_id == "chain-overload"
        assert state.current_step == 1
        assert state.resolved is False

    def test_escalation_returns_unresolved_state(self) -> None:
        """The escalation just starts the chain; it does not resolve anything."""
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        esc = _make_escalation(org)
        _seed_team(org, "team-beta", ("p-bob",))
        step = EscalationStep(step_order=1, target_person_id="p-bob", timeout_minutes=30)
        org.register_escalation_chain(EscalationChain(
            chain_id="chain-beta", name="Beta Overload", steps=(step,), created_at=FIXED_CLOCK,
        ))
        registry.register_worker(_make_worker("w-bob", "Bob", ("role-gen",)))

        state = TeamJobBridge.escalate_overloaded(engine, esc, "w-bob", "chain-beta")

        assert state.resolved is False
        assert state.started_at == FIXED_CLOCK


# ===========================================================================
# Golden Scenario 3: Handoff preserves thread context
# ===========================================================================


class TestGoldenScenario3_HandoffThread:
    """A job handoff appends a status message to the conversation thread
    preserving all prior messages."""

    def test_handoff_appends_message_to_thread(self) -> None:
        registry = _make_registry()
        engine = _make_engine(registry)
        convo = _make_convo()
        registry.register_worker(_make_worker("w-1", "W1", ("role-gen",)))
        registry.register_worker(_make_worker("w-2", "W2", ("role-gen",)))
        thread = convo.create_thread("Important job")

        record, updated = TeamJobBridge.handoff_with_thread(
            engine, convo, "job-x", "w-1", "w-2",
            HandoffReason.ESCALATION, thread,
        )

        assert len(updated.messages) == 1
        assert "job-x" in updated.messages[0].content
        assert "w-1" in updated.messages[0].content
        assert "w-2" in updated.messages[0].content

    def test_handoff_preserves_prior_clarification(self) -> None:
        registry = _make_registry()
        engine = _make_engine(registry)
        convo = _make_convo()
        registry.register_worker(_make_worker("w-a", "A", ("role-gen",)))
        registry.register_worker(_make_worker("w-b", "B", ("role-gen",)))
        thread = convo.create_thread("Thread with history")
        thread, _ = convo.request_clarification(thread, "Need info", "w-a")

        _, updated = TeamJobBridge.handoff_with_thread(
            engine, convo, "job-y", "w-a", "w-b",
            HandoffReason.SHIFT_CHANGE, thread,
        )

        assert len(updated.messages) == 2
        assert updated.messages[0].content == "Need info"
        assert "handed off" in updated.messages[1].content

    def test_handoff_record_matches_parameters(self) -> None:
        registry = _make_registry()
        engine = _make_engine(registry)
        convo = _make_convo()
        registry.register_worker(_make_worker("w-src", "Src", ("role-gen",)))
        registry.register_worker(_make_worker("w-dst", "Dst", ("role-gen",)))
        thread = convo.create_thread("Handoff record test")

        record, _ = TeamJobBridge.handoff_with_thread(
            engine, convo, "job-z", "w-src", "w-dst",
            HandoffReason.ROLE_CHANGE, thread,
        )

        assert record.job_id == "job-z"
        assert record.from_worker_id == "w-src"
        assert record.to_worker_id == "w-dst"
        assert record.reason == HandoffReason.ROLE_CHANGE


# ===========================================================================
# Golden Scenario 4: Least-loaded assignment picks correct worker
# ===========================================================================


class TestGoldenScenario4_LeastLoaded:
    """When multiple workers are available, assignment picks the one with most
    available slots (least loaded)."""

    def test_picks_worker_with_lowest_load(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-lb", ("p-w1", "p-w2", "p-w3"))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-lb",
            resource_type="goal",
            owner_team_id="team-lb",
        ))
        registry.register_role(_make_role("role-lb", "LB"))
        registry.register_worker(_make_worker("w-busy", "Busy", ("role-lb",)))
        registry.register_worker(_make_worker("w-light", "Light", ("role-lb",)))
        registry.register_worker(_make_worker("w-heavy", "Heavy", ("role-lb",)))
        # Update capacities: w-light has lowest load (most available slots)
        registry.update_capacity("w-busy", 4)
        registry.update_capacity("w-light", 1)
        registry.update_capacity("w-heavy", 3)

        job = _make_job("job-lb", "Load balanced", goal_id="goal-lb")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is not None
        assert decision.worker_id == "w-light"

    def test_equal_load_picks_deterministically(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-eq", ("p-eq1", "p-eq2"))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-eq",
            resource_type="goal",
            owner_team_id="team-eq",
        ))
        registry.register_role(_make_role("role-eq", "EQ"))
        registry.register_worker(_make_worker("w-eq1", "EQ1", ("role-eq",)))
        registry.register_worker(_make_worker("w-eq2", "EQ2", ("role-eq",)))
        registry.update_capacity("w-eq1", 2)
        registry.update_capacity("w-eq2", 2)

        job = _make_job("job-eq", "Equal load", goal_id="goal-eq")
        d1 = TeamJobBridge.assign_job_by_ownership(engine, org, job)
        d2 = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        # Both calls should pick the same worker
        assert d1 is not None and d2 is not None
        assert d1.worker_id == d2.worker_id


# ===========================================================================
# Golden Scenario 5: No available worker returns None (escalation needed)
# ===========================================================================


class TestGoldenScenario5_NoAvailableWorker:
    """When no workers are available in the owning team, assign returns None."""

    def test_all_workers_offline_returns_none(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-ghost", ("p-ghost",))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-ghost",
            resource_type="goal",
            owner_team_id="team-ghost",
        ))
        registry.register_role(_make_role("role-ghost", "Ghost"))
        registry.register_worker(_make_worker(
            "w-ghost", "Ghost", ("role-ghost",),
            status=WorkerStatus.OFFLINE,
        ))

        job = _make_job("job-ghost", "Ghost job", goal_id="goal-ghost")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is None

    def test_all_workers_at_capacity_returns_none(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-full", ("p-full",))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-full",
            resource_type="goal",
            owner_team_id="team-full",
        ))
        registry.register_role(_make_role("role-full", "Full"))
        registry.register_worker(_make_worker(
            "w-full", "Full", ("role-full",), max_concurrent_jobs=2,
        ))
        # Fill capacity completely
        registry.update_capacity("w-full", 2)

        job = _make_job("job-full", "Full job", goal_id="goal-full")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is None

    def test_no_workers_registered_returns_none(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-empty", ("p-placeholder",))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-none",
            resource_type="goal",
            owner_team_id="team-empty",
        ))
        registry.register_role(_make_role("role-empty", "Empty"))
        # No workers registered at all

        job = _make_job("job-none", "No workers", goal_id="goal-none")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is None

    def test_no_resource_id_returns_none(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)

        job = _make_job("job-orphan", "Orphan")
        decision = TeamJobBridge.assign_job_by_ownership(engine, org, job)

        assert decision is None


# ===========================================================================
# Golden Scenario 6: Capacity update changes assignment routing
# ===========================================================================


class TestGoldenScenario6_CapacityRouting:
    """Updating a worker's capacity changes which worker gets assigned next."""

    def test_capacity_change_reroutes_assignment(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-cap", ("p-cap1", "p-cap2"))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-cap",
            resource_type="goal",
            owner_team_id="team-cap",
        ))
        registry.register_role(_make_role("role-cap", "Cap"))
        registry.register_worker(_make_worker("w-cap1", "Cap1", ("role-cap",)))
        registry.register_worker(_make_worker("w-cap2", "Cap2", ("role-cap",)))

        # Initially cap1 has lower load (more available slots)
        registry.update_capacity("w-cap1", 1)
        registry.update_capacity("w-cap2", 4)

        job = _make_job("job-cap1", "Cap test 1", goal_id="goal-cap")
        d1 = TeamJobBridge.assign_job_by_ownership(engine, org, job)
        assert d1 is not None
        assert d1.worker_id == "w-cap1"

        # Update capacities -- now cap2 is lighter
        registry.update_capacity("w-cap1", 4)
        registry.update_capacity("w-cap2", 0)

        job2 = _make_job("job-cap2", "Cap test 2", goal_id="goal-cap")
        d2 = TeamJobBridge.assign_job_by_ownership(engine, org, job2)
        assert d2 is not None
        assert d2.worker_id == "w-cap2"

    def test_filling_capacity_prevents_assignment(self) -> None:
        org = _make_org()
        registry = _make_registry()
        engine = _make_engine(registry)
        _seed_team(org, "team-block", ("p-block",))
        org.register_ownership(OwnershipMapping(
            resource_id="goal-block",
            resource_type="goal",
            owner_team_id="team-block",
        ))
        registry.register_role(_make_role("role-block", "Block"))
        registry.register_worker(_make_worker(
            "w-block", "Block", ("role-block",), max_concurrent_jobs=3,
        ))

        # First assignment works (worker has capacity)
        job1 = _make_job("job-b1", "Block1", goal_id="goal-block")
        d1 = TeamJobBridge.assign_job_by_ownership(engine, org, job1)
        assert d1 is not None

        # Fill worker to capacity
        registry.update_capacity("w-block", 3)

        # Second assignment should return None (escalation needed)
        job2 = _make_job("job-b2", "Block2", goal_id="goal-block")
        d2 = TeamJobBridge.assign_job_by_ownership(engine, org, job2)
        assert d2 is None


# ===========================================================================
# Additional golden: View model + console rendering end-to-end
# ===========================================================================


class TestGoldenViewModelRendering:
    """View model creation and console rendering are consistent."""

    def test_view_to_render_roundtrip(self) -> None:
        view = TeamSummaryView(
            team_id="team-golden",
            total_workers=10,
            available_workers=7,
            overloaded_workers=2,
            queued_jobs=15,
            assigned_jobs=8,
        )
        output = render_team_summary(view)

        assert "team-golden" in output
        assert "10" in output
        assert "7" in output
        assert "2" in output
        assert "15" in output
        assert "8" in output

    def test_zero_team_renders_cleanly(self) -> None:
        view = TeamSummaryView(
            team_id="team-zero",
            total_workers=0,
            available_workers=0,
            overloaded_workers=0,
            queued_jobs=0,
            assigned_jobs=0,
        )
        output = render_team_summary(view)

        assert "team-zero" in output
        assert "=== Team Summary ===" in output
