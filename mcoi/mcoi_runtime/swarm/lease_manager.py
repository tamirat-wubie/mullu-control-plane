"""Lease manager for governed swarm tasks.

Purpose: issue bounded task leases only when identity authority covers the task.
Governance scope: no lease, no work; no child authority expansion; no side
effects from specialist agents.
Dependencies: datetime, decimal, and swarm contracts.
Invariants: lease actions are a subset of both task requirements and agent
allowed capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .contracts import AgentIdentity, SwarmInvariantViolation, SwarmTask, TaskLease


@dataclass
class TaskLeaseManager:
    """Issue and track bounded leases for specialist work."""

    default_lease_seconds: int = 900
    _leases: dict[str, TaskLease] = field(default_factory=dict)
    _counter: int = 0

    def issue(
        self,
        agent: AgentIdentity,
        task: SwarmTask,
        *,
        now: datetime | None = None,
        max_cost_usd: Decimal = Decimal("0.00"),
    ) -> TaskLease:
        """Issue a task lease when all authority checks pass."""

        if agent.tenant_id != task.tenant_id:
            raise SwarmInvariantViolation("agent tenant cannot differ from task tenant")
        if agent.role != task.required_role:
            raise SwarmInvariantViolation("agent role cannot differ from task role")
        if not agent.can_perform(task.required_capabilities):
            raise SwarmInvariantViolation("agent lacks required task capability")
        if task.side_effects_allowed:
            raise SwarmInvariantViolation("task side effects cannot be leased")
        issued_at = now or datetime.now(timezone.utc)
        expires_at = (
            issued_at.astimezone(timezone.utc)
            + timedelta(seconds=self.default_lease_seconds)
        ).replace(microsecond=0)
        self._counter += 1
        lease = TaskLease(
            lease_id=f"lease_{self._counter:06d}",
            agent_id=agent.agent_id,
            tenant_id=task.tenant_id,
            task_id=task.task_id,
            allowed_actions=task.required_capabilities,
            expires_at=expires_at.isoformat().replace("+00:00", "Z"),
            max_cost_usd=max_cost_usd,
            side_effects_allowed=False,
        )
        self._leases[lease.lease_id] = lease
        return lease

    def get(self, lease_id: str) -> TaskLease:
        """Return a lease or raise an explicit invariant error."""

        try:
            return self._leases[lease_id]
        except KeyError as exc:
            raise SwarmInvariantViolation(f"unknown lease_id: {lease_id}") from exc

    @property
    def count(self) -> int:
        """Return active lease count."""

        return len(self._leases)
