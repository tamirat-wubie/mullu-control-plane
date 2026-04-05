"""Tests for organizational awareness contracts: Person, Team, OwnershipMapping,
EscalationStep, EscalationChain, EscalationState."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.organization import (
    ContactChannel,
    EscalationChain,
    EscalationState,
    EscalationStep,
    OwnershipMapping,
    Person,
    RoleType,
    Team,
)


T0 = "2025-06-01T09:00:00+00:00"


# --- Person ---


class TestPerson:
    def test_valid_person(self):
        p = Person(person_id="p-1", name="Alice", email="alice@example.com")
        assert p.person_id == "p-1"
        assert p.name == "Alice"
        assert p.email == "alice@example.com"
        assert p.roles == ()
        assert p.preferred_channel is ContactChannel.EMAIL

    def test_person_with_roles(self):
        p = Person(
            person_id="p-2",
            name="Bob",
            email="bob@example.com",
            roles=(RoleType.OWNER, RoleType.APPROVER),
        )
        assert RoleType.OWNER in p.roles
        assert RoleType.APPROVER in p.roles

    def test_invalid_role_error_is_bounded(self):
        with pytest.raises(ValueError, match="^roles must contain only RoleType values$") as exc_info:
            Person(
                person_id="p-4",
                name="Dora",
                email="dora@example.com",
                roles=(RoleType.OWNER, "secret-role"),  # type: ignore[arg-type]
            )
        message = str(exc_info.value)
        assert "secret-role" not in message
        assert "OWNER" not in message

    def test_person_with_metadata(self):
        p = Person(
            person_id="p-3", name="Carol", email="carol@example.com",
            metadata={"dept": "eng"},
        )
        assert p.metadata["dept"] == "eng"

    def test_empty_person_id_rejected(self):
        with pytest.raises(ValueError, match="person_id"):
            Person(person_id="", name="X", email="x@example.com")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            Person(person_id="p-1", name="", email="x@example.com")

    def test_empty_email_rejected(self):
        with pytest.raises(ValueError, match="email"):
            Person(person_id="p-1", name="X", email="")

    def test_person_frozen(self):
        p = Person(person_id="p-1", name="Alice", email="alice@example.com")
        with pytest.raises(AttributeError):
            p.name = "Bob"  # type: ignore[misc]

    def test_person_serialization_roundtrip(self):
        p = Person(person_id="p-1", name="Alice", email="alice@example.com",
                    roles=(RoleType.OWNER,))
        d = p.to_dict()
        assert d["person_id"] == "p-1"
        assert d["roles"] == ["owner"]

    def test_person_preferred_channel(self):
        p = Person(
            person_id="p-1", name="Alice", email="alice@example.com",
            preferred_channel=ContactChannel.CHAT,
        )
        assert p.preferred_channel is ContactChannel.CHAT


# --- Team ---


class TestTeam:
    def test_valid_team(self):
        t = Team(team_id="t-1", name="Platform", members=("p-1", "p-2"))
        assert t.team_id == "t-1"
        assert t.members == ("p-1", "p-2")

    def test_team_with_lead(self):
        t = Team(team_id="t-1", name="Platform", members=("p-1",), lead_id="p-1")
        assert t.lead_id == "p-1"

    def test_empty_team_id_rejected(self):
        with pytest.raises(ValueError, match="team_id"):
            Team(team_id="", name="X", members=("p-1",))

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            Team(team_id="t-1", name="", members=("p-1",))

    def test_empty_members_rejected(self):
        with pytest.raises(ValueError, match="members"):
            Team(team_id="t-1", name="Platform", members=())

    def test_team_frozen(self):
        t = Team(team_id="t-1", name="Platform", members=("p-1",))
        with pytest.raises(AttributeError):
            t.name = "Other"  # type: ignore[misc]

    def test_team_serialization_roundtrip(self):
        t = Team(team_id="t-1", name="Platform", members=("p-1", "p-2"))
        d = t.to_dict()
        assert d["members"] == ["p-1", "p-2"]


# --- OwnershipMapping ---


class TestOwnershipMapping:
    def test_valid_mapping(self):
        m = OwnershipMapping(
            resource_id="repo/mullu", resource_type="repo", owner_team_id="t-1",
        )
        assert m.resource_id == "repo/mullu"
        assert m.resource_type == "repo"
        assert m.owner_team_id == "t-1"
        assert m.owner_person_id is None

    def test_mapping_with_person(self):
        m = OwnershipMapping(
            resource_id="svc/api", resource_type="service",
            owner_team_id="t-1", owner_person_id="p-1",
        )
        assert m.owner_person_id == "p-1"

    def test_empty_resource_id_rejected(self):
        with pytest.raises(ValueError, match="resource_id"):
            OwnershipMapping(resource_id="", resource_type="repo", owner_team_id="t-1")

    def test_empty_resource_type_rejected(self):
        with pytest.raises(ValueError, match="resource_type"):
            OwnershipMapping(resource_id="r-1", resource_type="", owner_team_id="t-1")

    def test_empty_owner_team_id_rejected(self):
        with pytest.raises(ValueError, match="owner_team_id"):
            OwnershipMapping(resource_id="r-1", resource_type="repo", owner_team_id="")


# --- EscalationStep ---


class TestEscalationStep:
    def test_valid_step(self):
        s = EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=15)
        assert s.step_order == 1
        assert s.target_person_id == "p-1"
        assert s.timeout_minutes == 15
        assert s.channel is ContactChannel.EMAIL

    def test_step_with_team(self):
        s = EscalationStep(
            step_order=2, target_person_id="p-2", target_team_id="t-1",
            timeout_minutes=30, channel=ContactChannel.CHAT,
        )
        assert s.target_team_id == "t-1"
        assert s.channel is ContactChannel.CHAT

    def test_zero_step_order_rejected(self):
        with pytest.raises(ValueError, match="step_order"):
            EscalationStep(step_order=0, target_person_id="p-1")

    def test_negative_step_order_rejected(self):
        with pytest.raises(ValueError, match="step_order"):
            EscalationStep(step_order=-1, target_person_id="p-1")

    def test_empty_target_person_rejected(self):
        with pytest.raises(ValueError, match="target_person_id"):
            EscalationStep(step_order=1, target_person_id="")

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValueError, match="timeout_minutes"):
            EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=0)

    def test_negative_timeout_rejected(self):
        with pytest.raises(ValueError, match="timeout_minutes"):
            EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=-5)

    def test_step_frozen(self):
        s = EscalationStep(step_order=1, target_person_id="p-1")
        with pytest.raises(AttributeError):
            s.step_order = 2  # type: ignore[misc]


# --- EscalationChain ---


class TestEscalationChain:
    def _steps(self):
        return (
            EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=15),
            EscalationStep(step_order=2, target_person_id="p-2", timeout_minutes=30),
        )

    def test_valid_chain(self):
        c = EscalationChain(
            chain_id="esc-1", name="Critical", steps=self._steps(), created_at=T0,
        )
        assert c.chain_id == "esc-1"
        assert len(c.steps) == 2

    def test_empty_steps_rejected(self):
        with pytest.raises(ValueError, match="steps"):
            EscalationChain(chain_id="esc-1", name="X", steps=(), created_at=T0)

    def test_non_sequential_steps_rejected(self):
        steps = (
            EscalationStep(step_order=1, target_person_id="p-1", timeout_minutes=15),
            EscalationStep(step_order=3, target_person_id="p-2", timeout_minutes=30),
        )
        with pytest.raises(ValueError, match="^step order must be sequential starting at 1$") as exc_info:
            EscalationChain(chain_id="esc-1", name="X", steps=steps, created_at=T0)
        message = str(exc_info.value)
        assert "expected" not in message
        assert "3" not in message

    def test_empty_chain_id_rejected(self):
        with pytest.raises(ValueError, match="chain_id"):
            EscalationChain(chain_id="", name="X", steps=self._steps(), created_at=T0)

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            EscalationChain(chain_id="esc-1", name="X", steps=self._steps(), created_at="")

    def test_chain_serialization_roundtrip(self):
        c = EscalationChain(
            chain_id="esc-1", name="Critical", steps=self._steps(), created_at=T0,
        )
        d = c.to_dict()
        assert d["chain_id"] == "esc-1"
        assert len(d["steps"]) == 2


# --- EscalationState ---


class TestEscalationState:
    def test_valid_state(self):
        s = EscalationState(chain_id="esc-1", current_step=1, started_at=T0)
        assert s.chain_id == "esc-1"
        assert s.current_step == 1
        assert s.resolved is False

    def test_state_with_last_escalated(self):
        s = EscalationState(
            chain_id="esc-1", current_step=2, started_at=T0, last_escalated_at=T0,
        )
        assert s.last_escalated_at == T0

    def test_empty_chain_id_rejected(self):
        with pytest.raises(ValueError, match="chain_id"):
            EscalationState(chain_id="", current_step=1, started_at=T0)

    def test_zero_current_step_rejected(self):
        with pytest.raises(ValueError, match="current_step"):
            EscalationState(chain_id="esc-1", current_step=0, started_at=T0)

    def test_empty_started_at_rejected(self):
        with pytest.raises(ValueError, match="started_at"):
            EscalationState(chain_id="esc-1", current_step=1, started_at="")
