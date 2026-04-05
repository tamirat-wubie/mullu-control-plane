"""Purpose: canonical organizational awareness contracts.
Governance scope: person, team, role, ownership, and escalation typing.
Dependencies: docs/24_organizational_awareness.md, shared contract base helpers.
Invariants:
  - Every person has a non-empty ID, name, and email.
  - Every team has at least one member.
  - Ownership always binds to a team; person binding is optional.
  - Escalation chains have ordered steps with positive timeouts.
  - Escalation state tracks progression without skipping steps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)


# --- Classification enums ---


class RoleType(StrEnum):
    OWNER = "owner"
    APPROVER = "approver"
    REVIEWER = "reviewer"
    OPERATOR = "operator"
    ESCALATION_TARGET = "escalation_target"


class ContactChannel(StrEnum):
    EMAIL = "email"
    CHAT = "chat"
    NOTIFICATION = "notification"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class Person(ContractRecord):
    """An individual registered in the organizational directory."""

    person_id: str
    name: str
    email: str
    roles: tuple[RoleType, ...] = ()
    preferred_channel: ContactChannel = ContactChannel.EMAIL
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "person_id", require_non_empty_text(self.person_id, "person_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "email", require_non_empty_text(self.email, "email"))
        object.__setattr__(self, "roles", freeze_value(list(self.roles)))
        for role in self.roles:
            if not isinstance(role, RoleType):
                raise ValueError("roles must contain only RoleType values")
        if not isinstance(self.preferred_channel, ContactChannel):
            raise ValueError("preferred_channel must be a ContactChannel value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class Team(ContractRecord):
    """A team of people with a designated lead."""

    team_id: str
    name: str
    members: tuple[str, ...] = ()
    lead_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "team_id", require_non_empty_text(self.team_id, "team_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "members", require_non_empty_tuple(self.members, "members"))
        for idx, member_id in enumerate(self.members):
            require_non_empty_text(member_id, f"members[{idx}]")
        if self.lead_id is not None:
            object.__setattr__(self, "lead_id", require_non_empty_text(self.lead_id, "lead_id"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OwnershipMapping(ContractRecord):
    """Binds a resource to its owning team and optional individual owner."""

    resource_id: str
    resource_type: str
    owner_team_id: str
    owner_person_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_id", require_non_empty_text(self.resource_id, "resource_id"))
        object.__setattr__(self, "resource_type", require_non_empty_text(self.resource_type, "resource_type"))
        object.__setattr__(self, "owner_team_id", require_non_empty_text(self.owner_team_id, "owner_team_id"))
        if self.owner_person_id is not None:
            object.__setattr__(
                self, "owner_person_id",
                require_non_empty_text(self.owner_person_id, "owner_person_id"),
            )


@dataclass(frozen=True, slots=True)
class EscalationStep(ContractRecord):
    """One step in an escalation chain with timeout-based progression."""

    step_order: int
    target_person_id: str
    target_team_id: str | None = None
    timeout_minutes: int = 30
    channel: ContactChannel = ContactChannel.EMAIL

    def __post_init__(self) -> None:
        if not isinstance(self.step_order, int) or self.step_order < 1:
            raise ValueError("step_order must be a positive integer")
        object.__setattr__(
            self, "target_person_id",
            require_non_empty_text(self.target_person_id, "target_person_id"),
        )
        if self.target_team_id is not None:
            object.__setattr__(
                self, "target_team_id",
                require_non_empty_text(self.target_team_id, "target_team_id"),
            )
        if not isinstance(self.timeout_minutes, int) or self.timeout_minutes < 1:
            raise ValueError("timeout_minutes must be a positive integer")
        if not isinstance(self.channel, ContactChannel):
            raise ValueError("channel must be a ContactChannel value")


@dataclass(frozen=True, slots=True)
class EscalationChain(ContractRecord):
    """An ordered sequence of escalation steps."""

    chain_id: str
    name: str
    steps: tuple[EscalationStep, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_id", require_non_empty_text(self.chain_id, "chain_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "steps", require_non_empty_tuple(self.steps, "steps"))
        for step in self.steps:
            if not isinstance(step, EscalationStep):
                raise ValueError("each step must be an EscalationStep instance")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        # Validate step ordering is sequential starting at 1
        expected = 1
        for step in sorted(self.steps, key=lambda s: s.step_order):
            if step.step_order != expected:
                raise ValueError("step order must be sequential starting at 1")
            expected += 1


@dataclass(frozen=True, slots=True)
class EscalationState(ContractRecord):
    """Runtime state tracking progression through an escalation chain."""

    chain_id: str
    current_step: int
    started_at: str
    last_escalated_at: str | None = None
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_id", require_non_empty_text(self.chain_id, "chain_id"))
        if not isinstance(self.current_step, int) or self.current_step < 1:
            raise ValueError("current_step must be a positive integer")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        if self.last_escalated_at is not None:
            object.__setattr__(self, "last_escalated_at", require_datetime_text(self.last_escalated_at, "last_escalated_at"))
