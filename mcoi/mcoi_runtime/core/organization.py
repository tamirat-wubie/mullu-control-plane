"""Purpose: organizational directory and escalation management.
Governance scope: person/team/ownership registration, approver lookup, escalation lifecycle.
Dependencies: organization contracts, invariant helpers.
Invariants:
  - Registration is idempotent on ID; duplicate IDs are rejected.
  - Lookups return None for missing records; never raise.
  - Escalation follows step order without skipping.
  - Resolved escalations cannot be advanced.
  - Clock is injected for determinism.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from mcoi_runtime.contracts.organization import (
    EscalationChain,
    EscalationState,
    EscalationStep,
    OwnershipMapping,
    Person,
    RoleType,
    Team,
)
from .invariants import ensure_non_empty_text


class OrgDirectory:
    """In-memory directory of people, teams, and ownership mappings.

    Rules:
    - Duplicate IDs are rejected on registration.
    - Lookups return None when no matching record exists.
    - find_approver walks the owning team's members for the first approver role.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._persons: dict[str, Person] = {}
        self._teams: dict[str, Team] = {}
        self._ownership: dict[str, OwnershipMapping] = {}
        self._chains: dict[str, EscalationChain] = {}

    # --- Person ---

    def register_person(self, person: Person) -> Person:
        if person.person_id in self._persons:
            raise ValueError("person already registered")
        self._persons[person.person_id] = person
        return person

    def get_person(self, person_id: str) -> Person | None:
        return self._persons.get(person_id)

    # --- Team ---

    def register_team(self, team: Team) -> Team:
        if team.team_id in self._teams:
            raise ValueError("team already registered")
        self._teams[team.team_id] = team
        return team

    def get_team(self, team_id: str) -> Team | None:
        return self._teams.get(team_id)

    def get_team_members(self, team_id: str) -> tuple[Person, ...]:
        team = self._teams.get(team_id)
        if team is None:
            return ()
        return tuple(
            self._persons[pid]
            for pid in team.members
            if pid in self._persons
        )

    # --- Ownership ---

    def register_ownership(self, mapping: OwnershipMapping) -> OwnershipMapping:
        if mapping.resource_id in self._ownership:
            raise ValueError("ownership already registered")
        self._ownership[mapping.resource_id] = mapping
        return mapping

    def find_owner(self, resource_id: str) -> OwnershipMapping | None:
        return self._ownership.get(resource_id)

    def find_approver(self, resource_id: str) -> Person | None:
        """Find the first person with approver role on the owning team."""
        mapping = self._ownership.get(resource_id)
        if mapping is None:
            return None
        team = self._teams.get(mapping.owner_team_id)
        if team is None:
            return None
        for member_id in team.members:
            person = self._persons.get(member_id)
            if person is not None and RoleType.APPROVER in person.roles:
                return person
        return None

    # --- Escalation chains ---

    def register_escalation_chain(self, chain: EscalationChain) -> EscalationChain:
        if chain.chain_id in self._chains:
            raise ValueError("escalation chain already registered")
        self._chains[chain.chain_id] = chain
        return chain

    def find_escalation_chain(self, chain_id: str) -> EscalationChain | None:
        return self._chains.get(chain_id)


class EscalationManager:
    """Manages the lifecycle of escalation state against registered chains.

    Rules:
    - start_escalation creates state at step 1 using the injected clock.
    - check_escalation computes whether the current step has timed out.
    - advance_escalation moves to the next step; fails if already at the last step.
    - resolve_escalation marks the chain resolved; resolved chains cannot advance.
    """

    def __init__(self, *, directory: OrgDirectory, clock: Callable[[], str]) -> None:
        self._directory = directory
        self._clock = clock

    def start_escalation(self, chain_id: str) -> EscalationState:
        ensure_non_empty_text("chain_id", chain_id)
        chain = self._directory.find_escalation_chain(chain_id)
        if chain is None:
            raise ValueError("escalation chain not found")
        now = self._clock()
        return EscalationState(
            chain_id=chain_id,
            current_step=1,
            started_at=now,
            last_escalated_at=now,
            resolved=False,
        )

    def check_escalation(
        self, state: EscalationState, now: str,
    ) -> tuple[bool, EscalationStep | None]:
        """Check whether the current step has timed out.

        Returns (should_escalate, next_step_or_None).
        """
        if state.resolved:
            return False, None

        chain = self._directory.find_escalation_chain(state.chain_id)
        if chain is None:
            return False, None

        # Find current step
        current = None
        for step in chain.steps:
            if step.step_order == state.current_step:
                current = step
                break
        if current is None:
            return False, None

        # Compute elapsed time since last escalation
        reference = state.last_escalated_at or state.started_at
        ref_dt = datetime.fromisoformat(reference.replace("Z", "+00:00"))
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        elapsed = now_dt - ref_dt
        timeout = timedelta(minutes=current.timeout_minutes)

        if elapsed >= timeout:
            # Find next step
            next_step = None
            for step in chain.steps:
                if step.step_order == state.current_step + 1:
                    next_step = step
                    break
            return True, next_step
        return False, None

    def advance_escalation(self, state: EscalationState) -> EscalationState:
        if state.resolved:
            raise ValueError("cannot advance a resolved escalation")

        chain = self._directory.find_escalation_chain(state.chain_id)
        if chain is None:
            raise ValueError("escalation chain not found")

        max_step = max(s.step_order for s in chain.steps)
        if state.current_step >= max_step:
            raise ValueError("already at the last escalation step")

        now = self._clock()
        return EscalationState(
            chain_id=state.chain_id,
            current_step=state.current_step + 1,
            started_at=state.started_at,
            last_escalated_at=now,
            resolved=False,
        )

    def resolve_escalation(self, state: EscalationState) -> EscalationState:
        if state.resolved:
            return state
        return EscalationState(
            chain_id=state.chain_id,
            current_step=state.current_step,
            started_at=state.started_at,
            last_escalated_at=state.last_escalated_at,
            resolved=True,
        )
