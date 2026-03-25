"""Tests for OrgDirectory and EscalationManager core logic."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.organization import (
    ContactChannel,
    EscalationChain,
    EscalationStep,
    OwnershipMapping,
    Person,
    RoleType,
    Team,
)
from mcoi_runtime.core.organization import EscalationManager, OrgDirectory


T0 = "2025-06-01T09:00:00+00:00"
T1 = "2025-06-01T09:10:00+00:00"
T2 = "2025-06-01T09:20:00+00:00"
T3 = "2025-06-01T09:40:00+00:00"
T4 = "2025-06-01T10:15:00+00:00"


def _clock(time=T0):
    return lambda: time


def _person(pid="p-1", name="Alice", email="alice@example.com", roles=()):
    return Person(person_id=pid, name=name, email=email, roles=roles)


def _team(tid="t-1", name="Platform", members=("p-1",), lead_id=None):
    return Team(team_id=tid, name=name, members=members, lead_id=lead_id)


def _ownership(resource_id="repo/mullu", resource_type="repo", team_id="t-1", person_id=None):
    return OwnershipMapping(
        resource_id=resource_id, resource_type=resource_type,
        owner_team_id=team_id, owner_person_id=person_id,
    )


def _chain(chain_id="esc-1", steps=None):
    if steps is None:
        steps = (
            EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=15),
            EscalationStep(step_order=2, target_person_id="p-2", timeout_minutes=30),
            EscalationStep(step_order=3, target_person_id="p-3", timeout_minutes=60),
        )
    return EscalationChain(chain_id=chain_id, name="Critical", steps=steps, created_at=T0)


def _directory(clock_time=T0):
    return OrgDirectory(clock=_clock(clock_time))


# --- OrgDirectory: Person ---


class TestOrgDirectoryPerson:
    def test_register_and_lookup(self):
        d = _directory()
        p = _person()
        d.register_person(p)
        assert d.get_person("p-1") is p

    def test_missing_person_returns_none(self):
        d = _directory()
        assert d.get_person("p-999") is None

    def test_duplicate_person_rejected(self):
        d = _directory()
        d.register_person(_person())
        with pytest.raises(ValueError, match="already registered"):
            d.register_person(_person())


# --- OrgDirectory: Team ---


class TestOrgDirectoryTeam:
    def test_register_and_lookup(self):
        d = _directory()
        t = _team()
        d.register_team(t)
        assert d.get_team("t-1") is t

    def test_missing_team_returns_none(self):
        d = _directory()
        assert d.get_team("t-999") is None

    def test_duplicate_team_rejected(self):
        d = _directory()
        d.register_team(_team())
        with pytest.raises(ValueError, match="already registered"):
            d.register_team(_team())

    def test_get_team_members(self):
        d = _directory()
        p1 = _person("p-1", "Alice", "alice@example.com")
        p2 = _person("p-2", "Bob", "bob@example.com")
        d.register_person(p1)
        d.register_person(p2)
        d.register_team(_team(members=("p-1", "p-2")))
        members = d.get_team_members("t-1")
        assert len(members) == 2
        assert members[0] is p1
        assert members[1] is p2

    def test_get_team_members_missing_team(self):
        d = _directory()
        assert d.get_team_members("t-999") == ()

    def test_get_team_members_skips_unregistered(self):
        d = _directory()
        d.register_person(_person("p-1"))
        d.register_team(_team(members=("p-1", "p-999")))
        members = d.get_team_members("t-1")
        assert len(members) == 1


# --- OrgDirectory: Ownership ---


class TestOrgDirectoryOwnership:
    def test_register_and_find(self):
        d = _directory()
        m = _ownership()
        d.register_ownership(m)
        assert d.find_owner("repo/mullu") is m

    def test_missing_ownership_returns_none(self):
        d = _directory()
        assert d.find_owner("unknown") is None

    def test_duplicate_ownership_rejected(self):
        d = _directory()
        d.register_ownership(_ownership())
        with pytest.raises(ValueError, match="already registered"):
            d.register_ownership(_ownership())


# --- OrgDirectory: Approver ---


class TestOrgDirectoryApprover:
    def test_find_approver(self):
        d = _directory()
        approver = _person("p-2", "Bob", "bob@example.com", roles=(RoleType.APPROVER,))
        operator = _person("p-1", "Alice", "alice@example.com", roles=(RoleType.OPERATOR,))
        d.register_person(operator)
        d.register_person(approver)
        d.register_team(_team(members=("p-1", "p-2")))
        d.register_ownership(_ownership())
        result = d.find_approver("repo/mullu")
        assert result is approver

    def test_find_approver_no_approver_on_team(self):
        d = _directory()
        d.register_person(_person("p-1", roles=(RoleType.OPERATOR,)))
        d.register_team(_team(members=("p-1",)))
        d.register_ownership(_ownership())
        assert d.find_approver("repo/mullu") is None

    def test_find_approver_no_ownership(self):
        d = _directory()
        assert d.find_approver("unknown") is None

    def test_find_approver_no_team(self):
        d = _directory()
        d.register_ownership(_ownership(team_id="t-missing"))
        assert d.find_approver("repo/mullu") is None

    def test_find_approver_returns_first_match(self):
        d = _directory()
        a1 = _person("p-1", "Alice", "alice@example.com", roles=(RoleType.APPROVER,))
        a2 = _person("p-2", "Bob", "bob@example.com", roles=(RoleType.APPROVER,))
        d.register_person(a1)
        d.register_person(a2)
        d.register_team(_team(members=("p-1", "p-2")))
        d.register_ownership(_ownership())
        result = d.find_approver("repo/mullu")
        assert result is a1


# --- OrgDirectory: Escalation chain registration ---


class TestOrgDirectoryEscalationChain:
    def test_register_and_find(self):
        d = _directory()
        c = _chain()
        d.register_escalation_chain(c)
        assert d.find_escalation_chain("esc-1") is c

    def test_missing_chain_returns_none(self):
        d = _directory()
        assert d.find_escalation_chain("esc-999") is None

    def test_duplicate_chain_rejected(self):
        d = _directory()
        d.register_escalation_chain(_chain())
        with pytest.raises(ValueError, match="already registered"):
            d.register_escalation_chain(_chain())


# --- EscalationManager ---


def _setup_escalation(clock_time=T0):
    d = _directory(clock_time)
    d.register_escalation_chain(_chain())
    mgr = EscalationManager(directory=d, clock=_clock(clock_time))
    return d, mgr


class TestEscalationManager:
    def test_start_escalation(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        assert state.chain_id == "esc-1"
        assert state.current_step == 1
        assert state.started_at == T0
        assert state.last_escalated_at == T0
        assert state.resolved is False

    def test_start_missing_chain_raises(self):
        d = _directory()
        mgr = EscalationManager(directory=d, clock=_clock())
        with pytest.raises(ValueError, match="not found"):
            mgr.start_escalation("esc-missing")

    def test_check_no_escalation_before_timeout(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        # Only 10 min elapsed, timeout is 15
        should, next_step = mgr.check_escalation(state, T1)
        assert should is False
        assert next_step is None

    def test_check_escalation_after_timeout(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        # 20 min elapsed, timeout is 15
        should, next_step = mgr.check_escalation(state, T2)
        assert should is True
        assert next_step is not None
        assert next_step.step_order == 2
        assert next_step.target_person_id == "p-2"

    def test_check_resolved_never_escalates(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        resolved = mgr.resolve_escalation(state)
        should, next_step = mgr.check_escalation(resolved, T3)
        assert should is False
        assert next_step is None

    def test_advance_escalation(self):
        d, _ = _setup_escalation()
        mgr = EscalationManager(directory=d, clock=_clock(T2))
        state = EscalationManager(directory=d, clock=_clock(T0)).start_escalation("esc-1")
        advanced = mgr.advance_escalation(state)
        assert advanced.current_step == 2
        assert advanced.last_escalated_at == T2
        assert advanced.started_at == T0

    def test_advance_at_last_step_raises(self):
        d, _ = _setup_escalation()
        mgr = EscalationManager(directory=d, clock=_clock(T0))
        state = mgr.start_escalation("esc-1")
        # Advance to step 2, then 3
        s2 = mgr.advance_escalation(state)
        s3 = mgr.advance_escalation(s2)
        with pytest.raises(ValueError, match="last"):
            mgr.advance_escalation(s3)

    def test_advance_resolved_raises(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        resolved = mgr.resolve_escalation(state)
        with pytest.raises(ValueError, match="resolved"):
            mgr.advance_escalation(resolved)

    def test_resolve_escalation(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        resolved = mgr.resolve_escalation(state)
        assert resolved.resolved is True
        assert resolved.current_step == 1
        assert resolved.started_at == T0

    def test_resolve_idempotent(self):
        _, mgr = _setup_escalation()
        state = mgr.start_escalation("esc-1")
        r1 = mgr.resolve_escalation(state)
        r2 = mgr.resolve_escalation(r1)
        assert r2.resolved is True

    def test_escalation_full_lifecycle(self):
        """Start -> timeout -> advance -> timeout -> advance -> resolve."""
        d = _directory(T0)
        d.register_escalation_chain(_chain())

        # Start at T0
        mgr0 = EscalationManager(directory=d, clock=_clock(T0))
        state = mgr0.start_escalation("esc-1")
        assert state.current_step == 1

        # At T2 (20 min), step 1 timed out (15 min timeout)
        should, next_step = mgr0.check_escalation(state, T2)
        assert should is True

        # Advance to step 2
        mgr2 = EscalationManager(directory=d, clock=_clock(T2))
        state = mgr2.advance_escalation(state)
        assert state.current_step == 2

        # At T3 (40 min from start, 20 min from last escalation at T2),
        # step 2 timeout is 30 min -- not yet
        should, _ = mgr2.check_escalation(state, T3)
        assert should is False

        # At T4 (75 min from start, 55 min from T2), step 2 timed out
        should, next_step = mgr2.check_escalation(state, T4)
        assert should is True
        assert next_step.step_order == 3

        # Advance to step 3 and resolve
        mgr4 = EscalationManager(directory=d, clock=_clock(T4))
        state = mgr4.advance_escalation(state)
        assert state.current_step == 3
        resolved = mgr4.resolve_escalation(state)
        assert resolved.resolved is True

    def test_check_last_step_timeout_returns_none_next(self):
        """When the last step times out, should_escalate=True but next_step=None."""
        d = _directory(T0)
        chain = EscalationChain(
            chain_id="esc-single", name="Single",
            steps=(EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=10),),
            created_at=T0,
        )
        d.register_escalation_chain(chain)
        mgr = EscalationManager(directory=d, clock=_clock(T0))
        state = mgr.start_escalation("esc-single")
        should, next_step = mgr.check_escalation(state, T2)
        assert should is True
        assert next_step is None

    def test_clock_injection_determinism(self):
        """Two managers with the same clock produce identical state."""
        d = _directory(T0)
        d.register_escalation_chain(_chain())
        mgr_a = EscalationManager(directory=d, clock=_clock(T0))
        mgr_b = EscalationManager(directory=d, clock=_clock(T0))
        state_a = mgr_a.start_escalation("esc-1")
        state_b = mgr_b.start_escalation("esc-1")
        assert state_a.to_dict() == state_b.to_dict()
