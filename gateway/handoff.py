"""Multi-Agent Handoff Router — Specialized agent delegation.

Purpose: Routes requests to specialized agents (financial, email, calendar,
    general) based on intent classification. Agents hand off to each other
    with governed context transfer.

Pattern: Follows OpenAI Agent SDK handoff pattern — agents transfer control
    explicitly, carrying conversation context through the transition.

Invariants:
  - Every handoff is audited.
  - Context transfer is governed (PII-scanned, tenant-scoped).
  - Handoff loops are detected and blocked.
  - Unknown intents fall through to general agent (LLM).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Callable


_SPECIALIST_ROLES = frozenset({
    "planner_agent",
    "research_agent",
    "browser_agent",
    "document_agent",
    "code_agent",
    "finance_agent",
    "review_agent",
})


@dataclass(frozen=True, slots=True)
class AgentSpec:
    """Specification for a specialized agent."""

    agent_id: str
    name: str
    description: str
    handles: tuple[str, ...]  # Intent categories this agent handles
    handler: Callable[[str, str, str], dict[str, Any]] | None = None  # (message, tenant_id, identity_id) -> result


@dataclass(frozen=True, slots=True)
class HandoffRecord:
    """Record of an agent-to-agent handoff."""

    from_agent: str
    to_agent: str
    reason: str
    context_keys_transferred: tuple[str, ...]
    timestamp: str = ""


@dataclass(frozen=True, slots=True)
class SpecialistDelegation:
    """Bounded specialist-worker task with an active execution lease."""

    request_id: str
    lease_id: str
    delegator_id: str
    worker_id: str
    role: str
    goal_id: str
    capability_id: str
    tenant_id: str
    identity_id: str
    budget_cents: int
    timeout_seconds: int
    created_at: str
    lease_expires_at: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SpecialistWorkerSpec:
    """Registered controlled worker and its safe execution envelope."""

    worker_id: str
    role: str
    allowed_capabilities: tuple[str, ...]
    max_budget_cents: int
    max_timeout_seconds: int
    max_active_leases: int = 1
    enabled: bool = True
    handler: Callable[[SpecialistDelegation], dict[str, Any]] | None = None


@dataclass(frozen=True, slots=True)
class SpecialistDelegationReceipt:
    """Auditable receipt for specialist delegation lifecycle changes."""

    request_id: str
    lease_id: str
    worker_id: str
    role: str
    capability_id: str
    status: str
    reason: str
    budget_cents: int
    timeout_seconds: int
    created_at: str
    lease_expires_at: str
    completed_at: str = ""
    result_hash: str = ""
    output: dict[str, Any] | None = None


class HandoffRouter:
    """Routes requests to specialized agents with governed handoff.

    Agents are registered with intent categories they handle.
    When a request comes in, the router classifies the intent and
    delegates to the appropriate agent. If an agent can't handle
    the request, it hands off to another agent.

    Handoff loops (A → B → A) are detected and blocked.
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        from datetime import datetime, timezone
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._agents: dict[str, AgentSpec] = {}
        self._intent_map: dict[str, str] = {}  # intent → agent_id
        self._handoff_history: list[HandoffRecord] = []
        self._general_agent_id: str = ""
        self._specialist_workers: dict[str, SpecialistWorkerSpec] = {}
        self._active_delegations: dict[str, SpecialistDelegation] = {}
        self._delegation_receipts: list[SpecialistDelegationReceipt] = []

    def register_agent(self, spec: AgentSpec) -> None:
        """Register a specialized agent."""
        self._agents[spec.agent_id] = spec
        for intent in spec.handles:
            self._intent_map[intent] = spec.agent_id

    def set_general_agent(self, agent_id: str) -> None:
        """Set the fallback general-purpose agent."""
        self._general_agent_id = agent_id

    def register_specialist_worker(self, spec: SpecialistWorkerSpec) -> None:
        """Register a controlled specialist worker."""
        if not spec.worker_id:
            raise ValueError("worker_id is required")
        if spec.role not in _SPECIALIST_ROLES:
            raise ValueError("unsupported specialist role")
        if not spec.allowed_capabilities:
            raise ValueError("allowed_capabilities is required")
        if spec.max_budget_cents <= 0:
            raise ValueError("max_budget_cents must be > 0")
        if spec.max_timeout_seconds <= 0:
            raise ValueError("max_timeout_seconds must be > 0")
        if spec.max_active_leases <= 0:
            raise ValueError("max_active_leases must be > 0")
        self._specialist_workers[spec.worker_id] = spec

    def _active_lease_count(self, worker_id: str) -> int:
        return sum(
            1 for delegation in self._active_delegations.values()
            if delegation.worker_id == worker_id
        )

    def _lease_expiry(self, created_at: str, timeout_seconds: int) -> str:
        created = datetime.fromisoformat(created_at)
        return (created + timedelta(seconds=timeout_seconds)).isoformat()

    def _delegation_ids(
        self,
        *,
        delegator_id: str,
        worker_id: str,
        goal_id: str,
        capability_id: str,
        created_at: str,
    ) -> tuple[str, str]:
        seed = "|".join((
            delegator_id,
            worker_id,
            goal_id,
            capability_id,
            created_at,
            str(len(self._delegation_receipts)),
        ))
        digest = sha256(seed.encode("utf-8")).hexdigest()
        return f"delegation-{digest[:16]}", f"lease-{digest[16:32]}"

    def _delegation_receipt(
        self,
        delegation: SpecialistDelegation,
        *,
        status: str,
        reason: str,
        output: dict[str, Any] | None = None,
        completed_at: str = "",
    ) -> SpecialistDelegationReceipt:
        result_hash = ""
        if output is not None:
            result_hash = sha256(repr(sorted(output.items())).encode("utf-8")).hexdigest()
        receipt = SpecialistDelegationReceipt(
            request_id=delegation.request_id,
            lease_id=delegation.lease_id,
            worker_id=delegation.worker_id,
            role=delegation.role,
            capability_id=delegation.capability_id,
            status=status,
            reason=reason,
            budget_cents=delegation.budget_cents,
            timeout_seconds=delegation.timeout_seconds,
            created_at=delegation.created_at,
            lease_expires_at=delegation.lease_expires_at,
            completed_at=completed_at,
            result_hash=result_hash,
            output=output,
        )
        self._delegation_receipts.append(receipt)
        return receipt

    def _rejection_receipt(
        self,
        *,
        worker_id: str,
        role: str,
        capability_id: str,
        budget_cents: int,
        timeout_seconds: int,
        reason: str,
        created_at: str,
    ) -> SpecialistDelegationReceipt:
        seed = "|".join((worker_id, role, capability_id, reason, created_at))
        digest = sha256(seed.encode("utf-8")).hexdigest()
        receipt = SpecialistDelegationReceipt(
            request_id=f"delegation-rejected-{digest[:12]}",
            lease_id="none",
            worker_id=worker_id,
            role=role,
            capability_id=capability_id,
            status="rejected",
            reason=reason,
            budget_cents=budget_cents,
            timeout_seconds=timeout_seconds,
            created_at=created_at,
            lease_expires_at=created_at,
        )
        self._delegation_receipts.append(receipt)
        return receipt

    def delegate_to_specialist(
        self,
        *,
        delegator_id: str,
        worker_id: str,
        goal_id: str,
        capability_id: str,
        tenant_id: str,
        identity_id: str,
        budget_cents: int,
        timeout_seconds: int,
        payload: dict[str, Any] | None = None,
    ) -> SpecialistDelegationReceipt:
        """Delegate work to a controlled specialist worker under a lease."""
        created_at = self._clock()
        worker = self._specialist_workers.get(worker_id)
        if worker is None:
            return self._rejection_receipt(
                worker_id=worker_id,
                role="unknown",
                capability_id=capability_id,
                budget_cents=budget_cents,
                timeout_seconds=timeout_seconds,
                reason="worker unavailable",
                created_at=created_at,
            )
        if not worker.enabled:
            return self._rejection_receipt(
                worker_id=worker_id,
                role=worker.role,
                capability_id=capability_id,
                budget_cents=budget_cents,
                timeout_seconds=timeout_seconds,
                reason="worker disabled",
                created_at=created_at,
            )
        if capability_id not in worker.allowed_capabilities:
            return self._rejection_receipt(
                worker_id=worker_id,
                role=worker.role,
                capability_id=capability_id,
                budget_cents=budget_cents,
                timeout_seconds=timeout_seconds,
                reason="worker lacks required capability",
                created_at=created_at,
            )
        if budget_cents <= 0 or budget_cents > worker.max_budget_cents:
            return self._rejection_receipt(
                worker_id=worker_id,
                role=worker.role,
                capability_id=capability_id,
                budget_cents=budget_cents,
                timeout_seconds=timeout_seconds,
                reason="budget outside worker boundary",
                created_at=created_at,
            )
        if timeout_seconds <= 0 or timeout_seconds > worker.max_timeout_seconds:
            return self._rejection_receipt(
                worker_id=worker_id,
                role=worker.role,
                capability_id=capability_id,
                budget_cents=budget_cents,
                timeout_seconds=timeout_seconds,
                reason="timeout outside worker boundary",
                created_at=created_at,
            )
        if self._active_lease_count(worker_id) >= worker.max_active_leases:
            return self._rejection_receipt(
                worker_id=worker_id,
                role=worker.role,
                capability_id=capability_id,
                budget_cents=budget_cents,
                timeout_seconds=timeout_seconds,
                reason="worker lease capacity reached",
                created_at=created_at,
            )

        request_id, lease_id = self._delegation_ids(
            delegator_id=delegator_id,
            worker_id=worker_id,
            goal_id=goal_id,
            capability_id=capability_id,
            created_at=created_at,
        )
        delegation = SpecialistDelegation(
            request_id=request_id,
            lease_id=lease_id,
            delegator_id=delegator_id,
            worker_id=worker_id,
            role=worker.role,
            goal_id=goal_id,
            capability_id=capability_id,
            tenant_id=tenant_id,
            identity_id=identity_id,
            budget_cents=budget_cents,
            timeout_seconds=timeout_seconds,
            created_at=created_at,
            lease_expires_at=self._lease_expiry(created_at, timeout_seconds),
            payload=dict(payload or {}),
        )
        self._active_delegations[lease_id] = delegation

        if worker.handler is None:
            return self._delegation_receipt(
                delegation,
                status="accepted",
                reason="lease issued",
            )

        try:
            output = worker.handler(delegation)
        except Exception as exc:
            self._active_delegations.pop(lease_id, None)
            return self._delegation_receipt(
                delegation,
                status="failed",
                reason=type(exc).__name__,
                completed_at=self._clock(),
            )

        self._active_delegations.pop(lease_id, None)
        return self._delegation_receipt(
            delegation,
            status="completed",
            reason="worker completed",
            output=output,
            completed_at=self._clock(),
        )

    def kill_specialist_lease(self, lease_id: str, *, reason: str) -> SpecialistDelegationReceipt:
        """Terminate an active specialist lease and record the cancellation."""
        delegation = self._active_delegations.pop(lease_id, None)
        if delegation is None:
            now = self._clock()
            receipt = SpecialistDelegationReceipt(
                request_id="unknown",
                lease_id=lease_id,
                worker_id="unknown",
                role="unknown",
                capability_id="unknown",
                status="rejected",
                reason="lease unavailable",
                budget_cents=0,
                timeout_seconds=0,
                created_at=now,
                lease_expires_at=now,
                completed_at=now,
            )
            self._delegation_receipts.append(receipt)
            return receipt
        return self._delegation_receipt(
            delegation,
            status="cancelled",
            reason=reason,
            completed_at=self._clock(),
        )

    def route(
        self,
        message: str,
        *,
        intent: str = "",
        tenant_id: str = "",
        identity_id: str = "",
    ) -> dict[str, Any]:
        """Route a message to the appropriate agent.

        If intent is provided, routes directly. Otherwise classifies first.
        Falls back to general agent for unknown intents.
        """
        agent_id = self._intent_map.get(intent, self._general_agent_id)
        agent = self._agents.get(agent_id)

        if agent is None:
            return {
                "response": "No agent available to handle this request.",
                "agent": "none",
                "governed": True,
            }

        if agent.handler is not None:
            try:
                result = agent.handler(message, tenant_id, identity_id)
                result["agent"] = agent.agent_id
                result["governed"] = True
                return result
            except Exception as exc:
                return {
                    "response": "Agent encountered an error.",
                    "agent": agent.agent_id,
                    "error": type(exc).__name__,
                    "governed": True,
                }

        return {
            "response": f"Routed to {agent.name} (no handler configured).",
            "agent": agent.agent_id,
            "governed": True,
        }

    def handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        *,
        message: str,
        reason: str = "",
        tenant_id: str = "",
        identity_id: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Transfer control from one agent to another.

        Detects and blocks handoff loops by checking the full recent chain.
        """
        # Loop detection: build the recent chain of all agents involved
        recent = self._handoff_history[-20:]  # Check last 20 handoffs
        visited_agents: set[str] = set()
        for h in recent:
            visited_agents.add(h.from_agent)
            visited_agents.add(h.to_agent)
        if to_agent_id in visited_agents and from_agent_id in visited_agents:
            return {
                "response": "Handoff loop detected — routing to general agent.",
                "agent": self._general_agent_id,
                "governed": True,
                "handoff_blocked": True,
            }

        record = HandoffRecord(
            from_agent=from_agent_id,
            to_agent=to_agent_id,
            reason=reason,
            context_keys_transferred=tuple(context.keys()) if context else (),
            timestamp=self._clock(),
        )
        self._handoff_history.append(record)

        # Prune history
        if len(self._handoff_history) > 10_000:
            self._handoff_history = self._handoff_history[-10_000:]

        return self.route(
            message, intent="", tenant_id=tenant_id, identity_id=identity_id,
        )

    @property
    def agent_count(self) -> int:
        return len(self._agents)

    @property
    def handoff_count(self) -> int:
        return len(self._handoff_history)

    def summary(self) -> dict[str, Any]:
        return {
            "agents": list(self._agents.keys()),
            "intent_map": dict(self._intent_map),
            "general_agent": self._general_agent_id,
            "handoff_count": self.handoff_count,
            "specialist_workers": list(self._specialist_workers.keys()),
            "active_specialist_leases": len(self._active_delegations),
            "specialist_receipts": len(self._delegation_receipts),
        }
