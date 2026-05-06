"""Gateway agent runtime coordination contract.

Purpose: coordinate tenant-bound agent identities, leases, tasks, and handoffs.
Governance scope: parent authority inheritance, capability scope, memory scope,
    budget scope, tenant isolation, self-approval denial, and receipt evidence.
Dependencies: dataclasses, enum, typing, and command-spine canonical hashing.
Invariants:
  - Child agents cannot exceed parent capability, memory, or budget scope.
  - Agents cannot delegate capabilities they do not possess.
  - Cross-tenant task assignment and handoff fail closed.
  - Agents cannot approve their own high-risk action.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterable

from gateway.command_spine import canonical_hash


FORBIDDEN_AUTHORITY_CAPABILITIES = frozenset({
    "policy.modify",
    "policy.promote",
    "authority.grant",
    "authority.modify",
})
RISK_TIERS = frozenset({"low", "medium", "high", "critical"})


class AgentRuntimeStatus(StrEnum):
    """Runtime availability state for one agent identity."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class AgentTaskStatus(StrEnum):
    """Task assignment state."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


class AgentReceiptStatus(StrEnum):
    """Receipt outcome for runtime coordination decisions."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    RECORDED = "recorded"


@dataclass(frozen=True, slots=True)
class AgentRuntimeIdentity:
    """Tenant-bound runtime identity for one agent process or role."""

    agent_id: str
    tenant_id: str
    role: str
    status: AgentRuntimeStatus
    capability_scope: tuple[str, ...]
    memory_scope: tuple[str, ...]
    budget_scope_cents: int
    parent_agent_id: str = ""
    lease_expires_at: str = ""
    evidence_refs: tuple[str, ...] = ()
    identity_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.agent_id, "agent_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.role, "role")
        if not isinstance(self.status, AgentRuntimeStatus):
            raise ValueError("agent_runtime_status_invalid")
        capabilities = _normalize_text_tuple(self.capability_scope, "capability_scope")
        if set(capabilities).intersection(FORBIDDEN_AUTHORITY_CAPABILITIES):
            raise ValueError("governance_mutation_capability_forbidden")
        if self.budget_scope_cents < 0:
            raise ValueError("budget_scope_cents_nonnegative_required")
        object.__setattr__(self, "capability_scope", capabilities)
        object.__setattr__(self, "memory_scope", _normalize_text_tuple(self.memory_scope, "memory_scope"))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentLease:
    """Short-lived execution lease binding an agent to inherited authority."""

    lease_id: str
    agent_id: str
    tenant_id: str
    issued_by_agent_id: str
    capability_scope: tuple[str, ...]
    budget_scope_cents: int
    issued_at: str
    expires_at: str
    evidence_refs: tuple[str, ...]
    lease_hash: str = ""

    def __post_init__(self) -> None:
        for field_name in ("lease_id", "agent_id", "tenant_id", "issued_by_agent_id", "issued_at", "expires_at"):
            _require_text(getattr(self, field_name), field_name)
        if self.budget_scope_cents < 0:
            raise ValueError("budget_scope_cents_nonnegative_required")
        object.__setattr__(self, "capability_scope", _normalize_text_tuple(self.capability_scope, "capability_scope"))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentTask:
    """Governed task assignment for one agent."""

    task_id: str
    agent_id: str
    tenant_id: str
    capability: str
    goal_id: str
    risk_tier: str
    budget_cents: int
    status: AgentTaskStatus
    assigned_at: str
    evidence_refs: tuple[str, ...]
    task_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("task_id", "agent_id", "tenant_id", "capability", "goal_id", "assigned_at"):
            _require_text(getattr(self, field_name), field_name)
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        if self.budget_cents < 0:
            raise ValueError("budget_cents_nonnegative_required")
        if not isinstance(self.status, AgentTaskStatus):
            raise ValueError("agent_task_status_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentHandoff:
    """Authority-preserving handoff from one agent to another."""

    handoff_id: str
    from_agent_id: str
    to_agent_id: str
    tenant_id: str
    goal_id: str
    task_id: str
    capability_scope: tuple[str, ...]
    budget_cents: int
    context_refs: tuple[str, ...]
    handed_off_at: str
    handoff_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("handoff_id", "from_agent_id", "to_agent_id", "tenant_id", "goal_id", "task_id", "handed_off_at"):
            _require_text(getattr(self, field_name), field_name)
        if self.from_agent_id == self.to_agent_id:
            raise ValueError("handoff_parties_must_differ")
        if self.budget_cents < 0:
            raise ValueError("budget_cents_nonnegative_required")
        object.__setattr__(self, "capability_scope", _normalize_text_tuple(self.capability_scope, "capability_scope"))
        object.__setattr__(self, "context_refs", _normalize_text_tuple(self.context_refs, "context_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentReceipt:
    """Auditable outcome for one runtime coordination decision."""

    receipt_id: str
    receipt_type: str
    status: AgentReceiptStatus
    actor_agent_id: str
    tenant_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    subject_ref: str = ""
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("receipt_id", "receipt_type", "actor_agent_id", "tenant_id", "reason"):
            _require_text(getattr(self, field_name), field_name)
        if not isinstance(self.status, AgentReceiptStatus):
            raise ValueError("agent_receipt_status_invalid")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentRuntimeSnapshot:
    """Operator read model for the gateway agent runtime."""

    runtime_id: str
    tenant_id: str
    agents: tuple[AgentRuntimeIdentity, ...]
    leases: tuple[AgentLease, ...]
    tasks: tuple[AgentTask, ...]
    handoffs: tuple[AgentHandoff, ...]
    receipts: tuple[AgentReceipt, ...]
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.runtime_id, "runtime_id")
        _require_text(self.tenant_id, "tenant_id")
        object.__setattr__(self, "agents", tuple(self.agents))
        object.__setattr__(self, "leases", tuple(self.leases))
        object.__setattr__(self, "tasks", tuple(self.tasks))
        object.__setattr__(self, "handoffs", tuple(self.handoffs))
        object.__setattr__(self, "receipts", tuple(self.receipts))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


class AgentRuntimeCoordinator:
    """Deterministic in-memory coordinator for governed multi-agent work."""

    def __init__(self, *, runtime_id: str = "gateway-agent-runtime", clock: Any | None = None) -> None:
        self._runtime_id = runtime_id
        self._clock = clock or (lambda: "2026-05-05T00:00:00Z")
        self._agents: dict[str, AgentRuntimeIdentity] = {}
        self._leases: dict[str, AgentLease] = {}
        self._tasks: dict[str, AgentTask] = {}
        self._handoffs: dict[str, AgentHandoff] = {}
        self._receipts: list[AgentReceipt] = []

    def register_root_agent(self, identity: AgentRuntimeIdentity) -> AgentRuntimeIdentity:
        """Register a root or supervisor agent identity."""
        if identity.parent_agent_id:
            raise ValueError("root_agent_cannot_have_parent")
        stamped = _stamp_identity(identity)
        self._agents[stamped.agent_id] = stamped
        self._record_receipt("agent_register", AgentReceiptStatus.RECORDED, stamped.agent_id, stamped.tenant_id, "root_agent_registered", stamped.agent_id, stamped.evidence_refs)
        return stamped

    def spawn_child_agent(
        self,
        *,
        parent_agent_id: str,
        child_agent_id: str,
        tenant_id: str,
        role: str,
        capability_scope: Iterable[str],
        memory_scope: Iterable[str],
        budget_scope_cents: int,
        issued_at: str,
        expires_at: str,
        evidence_refs: Iterable[str],
    ) -> tuple[AgentRuntimeIdentity | None, AgentLease | None, AgentReceipt]:
        """Spawn a child agent only when requested authority is a parent subset."""
        parent = self._agents.get(parent_agent_id)
        refs = tuple(evidence_refs)
        requested_capabilities = _normalize_text_tuple(tuple(capability_scope), "capability_scope")
        requested_memory = _normalize_text_tuple(tuple(memory_scope), "memory_scope")
        denial = _child_spawn_denial(parent, tenant_id, requested_capabilities, requested_memory, budget_scope_cents)
        if denial:
            return None, None, self._record_receipt("agent_spawn", AgentReceiptStatus.REJECTED, parent_agent_id, tenant_id, denial, child_agent_id, refs)

        child = _stamp_identity(AgentRuntimeIdentity(
            agent_id=child_agent_id,
            tenant_id=tenant_id,
            role=role,
            status=AgentRuntimeStatus.ACTIVE,
            capability_scope=requested_capabilities,
            memory_scope=requested_memory,
            budget_scope_cents=budget_scope_cents,
            parent_agent_id=parent_agent_id,
            lease_expires_at=expires_at,
            evidence_refs=refs,
        ))
        lease = _stamp_lease(AgentLease(
            lease_id=f"agent-lease-{canonical_hash({'parent': parent_agent_id, 'child': child_agent_id, 'expires_at': expires_at})[:16]}",
            agent_id=child_agent_id,
            tenant_id=tenant_id,
            issued_by_agent_id=parent_agent_id,
            capability_scope=requested_capabilities,
            budget_scope_cents=budget_scope_cents,
            issued_at=issued_at,
            expires_at=expires_at,
            evidence_refs=refs,
        ))
        self._agents[child.agent_id] = child
        self._leases[lease.lease_id] = lease
        receipt = self._record_receipt("agent_spawn", AgentReceiptStatus.ACCEPTED, parent_agent_id, tenant_id, "child_agent_lease_issued", child.agent_id, refs)
        return child, lease, receipt

    def assign_task(
        self,
        *,
        task_id: str,
        agent_id: str,
        tenant_id: str,
        capability: str,
        goal_id: str,
        risk_tier: str,
        budget_cents: int,
        evidence_refs: Iterable[str] = (),
        assigned_at: str = "",
    ) -> tuple[AgentTask, AgentReceipt]:
        """Assign a task only within agent capability and budget scope."""
        agent = self._agents.get(agent_id)
        refs = tuple(evidence_refs)
        denial = _task_denial(agent, tenant_id, capability, risk_tier, budget_cents, refs)
        status = AgentTaskStatus.REJECTED if denial else AgentTaskStatus.ACCEPTED
        task = _stamp_task(AgentTask(
            task_id=task_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            capability=capability,
            goal_id=goal_id,
            risk_tier=risk_tier,
            budget_cents=budget_cents,
            status=status,
            assigned_at=assigned_at or self._clock(),
            evidence_refs=refs,
            metadata={"admission_reason": denial or "agent_task_scope_satisfied"},
        ))
        self._tasks[task.task_id] = task
        receipt = self._record_receipt("agent_task", AgentReceiptStatus.REJECTED if denial else AgentReceiptStatus.ACCEPTED, agent_id, tenant_id, denial or "agent_task_accepted", task.task_id, refs)
        return task, receipt

    def record_handoff(
        self,
        *,
        handoff_id: str,
        from_agent_id: str,
        to_agent_id: str,
        tenant_id: str,
        goal_id: str,
        task_id: str,
        capability_scope: Iterable[str],
        budget_cents: int,
        context_refs: Iterable[str],
        handed_off_at: str = "",
    ) -> tuple[AgentHandoff | None, AgentReceipt]:
        """Record a handoff only when both agents remain inside one authority boundary."""
        from_agent = self._agents.get(from_agent_id)
        to_agent = self._agents.get(to_agent_id)
        capabilities = _normalize_text_tuple(tuple(capability_scope), "capability_scope")
        refs = tuple(context_refs)
        denial = _handoff_denial(from_agent, to_agent, tenant_id, capabilities, budget_cents, refs)
        if denial:
            receipt = self._record_receipt("agent_handoff", AgentReceiptStatus.REJECTED, from_agent_id, tenant_id, denial, handoff_id, refs)
            return None, receipt
        handoff = _stamp_handoff(AgentHandoff(
            handoff_id=handoff_id,
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            tenant_id=tenant_id,
            goal_id=goal_id,
            task_id=task_id,
            capability_scope=capabilities,
            budget_cents=budget_cents,
            context_refs=refs,
            handed_off_at=handed_off_at or self._clock(),
        ))
        self._handoffs[handoff.handoff_id] = handoff
        receipt = self._record_receipt("agent_handoff", AgentReceiptStatus.RECORDED, from_agent_id, tenant_id, "handoff_recorded", handoff.handoff_id, refs)
        return handoff, receipt

    def evaluate_approval(
        self,
        *,
        approver_agent_id: str,
        requester_agent_id: str,
        tenant_id: str,
        risk_tier: str,
        evidence_refs: Iterable[str] = (),
    ) -> AgentReceipt:
        """Evaluate whether one agent may approve another agent's action."""
        refs = tuple(evidence_refs)
        approver = self._agents.get(approver_agent_id)
        if approver is None:
            return self._record_receipt("agent_approval", AgentReceiptStatus.REJECTED, approver_agent_id, tenant_id, "approver_agent_unknown", requester_agent_id, refs)
        if approver.tenant_id != tenant_id:
            return self._record_receipt("agent_approval", AgentReceiptStatus.REJECTED, approver_agent_id, tenant_id, "tenant_boundary_denied", requester_agent_id, refs)
        if risk_tier in {"high", "critical"} and approver_agent_id == requester_agent_id:
            return self._record_receipt("agent_approval", AgentReceiptStatus.REJECTED, approver_agent_id, tenant_id, "self_approval_forbidden", requester_agent_id, refs)
        return self._record_receipt("agent_approval", AgentReceiptStatus.ACCEPTED, approver_agent_id, tenant_id, "approval_authority_satisfied", requester_agent_id, refs)

    def snapshot(self, *, tenant_id: str) -> AgentRuntimeSnapshot:
        """Return an immutable tenant-scoped runtime read model."""
        snapshot = AgentRuntimeSnapshot(
            runtime_id=self._runtime_id,
            tenant_id=tenant_id,
            agents=tuple(agent for agent in self._agents.values() if agent.tenant_id == tenant_id),
            leases=tuple(lease for lease in self._leases.values() if lease.tenant_id == tenant_id),
            tasks=tuple(task for task in self._tasks.values() if task.tenant_id == tenant_id),
            handoffs=tuple(handoff for handoff in self._handoffs.values() if handoff.tenant_id == tenant_id),
            receipts=tuple(receipt for receipt in self._receipts if receipt.tenant_id == tenant_id),
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _record_receipt(
        self,
        receipt_type: str,
        status: AgentReceiptStatus,
        actor_agent_id: str,
        tenant_id: str,
        reason: str,
        subject_ref: str,
        evidence_refs: Iterable[str],
    ) -> AgentReceipt:
        receipt = AgentReceipt(
            receipt_id="pending",
            receipt_type=receipt_type,
            status=status,
            actor_agent_id=actor_agent_id or "unknown",
            tenant_id=tenant_id,
            reason=reason,
            subject_ref=subject_ref,
            evidence_refs=tuple(evidence_refs),
        )
        payload = receipt.to_json_dict()
        payload["receipt_hash"] = ""
        receipt_hash = canonical_hash(payload)
        stamped = replace(receipt, receipt_id=f"agent-receipt-{receipt_hash[:16]}", receipt_hash=receipt_hash)
        self._receipts.append(stamped)
        return stamped


def agent_runtime_snapshot_to_json_dict(snapshot: AgentRuntimeSnapshot) -> dict[str, Any]:
    """Return the public JSON-contract representation of a runtime snapshot."""
    return snapshot.to_json_dict()


def _child_spawn_denial(
    parent: AgentRuntimeIdentity | None,
    tenant_id: str,
    requested_capabilities: tuple[str, ...],
    requested_memory: tuple[str, ...],
    budget_scope_cents: int,
) -> str:
    if parent is None:
        return "parent_agent_unknown"
    if parent.status != AgentRuntimeStatus.ACTIVE:
        return "parent_agent_not_active"
    if parent.tenant_id != tenant_id:
        return "tenant_boundary_denied"
    if not set(requested_capabilities).issubset(parent.capability_scope):
        return "child_capability_exceeds_parent"
    if not set(requested_memory).issubset(parent.memory_scope):
        return "child_memory_exceeds_parent"
    if budget_scope_cents > parent.budget_scope_cents:
        return "child_budget_exceeds_parent"
    return ""


def _task_denial(
    agent: AgentRuntimeIdentity | None,
    tenant_id: str,
    capability: str,
    risk_tier: str,
    budget_cents: int,
    evidence_refs: tuple[str, ...],
) -> str:
    if agent is None:
        return "agent_unknown"
    if agent.status != AgentRuntimeStatus.ACTIVE:
        return "agent_not_active"
    if agent.tenant_id != tenant_id:
        return "tenant_boundary_denied"
    if capability not in agent.capability_scope:
        return "capability_not_in_agent_scope"
    if budget_cents > agent.budget_scope_cents:
        return "task_budget_exceeds_agent_scope"
    if risk_tier in {"high", "critical"} and not evidence_refs:
        return "high_risk_evidence_required"
    return ""


def _handoff_denial(
    from_agent: AgentRuntimeIdentity | None,
    to_agent: AgentRuntimeIdentity | None,
    tenant_id: str,
    capability_scope: tuple[str, ...],
    budget_cents: int,
    context_refs: tuple[str, ...],
) -> str:
    if from_agent is None:
        return "from_agent_unknown"
    if to_agent is None:
        return "to_agent_unknown"
    if from_agent.tenant_id != tenant_id or to_agent.tenant_id != tenant_id:
        return "tenant_boundary_denied"
    if from_agent.status != AgentRuntimeStatus.ACTIVE or to_agent.status != AgentRuntimeStatus.ACTIVE:
        return "agent_not_active"
    if not set(capability_scope).issubset(from_agent.capability_scope):
        return "handoff_capability_exceeds_sender"
    if not set(capability_scope).issubset(to_agent.capability_scope):
        return "handoff_capability_exceeds_receiver"
    if budget_cents > from_agent.budget_scope_cents or budget_cents > to_agent.budget_scope_cents:
        return "handoff_budget_exceeds_agent_scope"
    if not context_refs:
        return "handoff_context_required"
    return ""


def _stamp_identity(identity: AgentRuntimeIdentity) -> AgentRuntimeIdentity:
    payload = identity.to_json_dict()
    payload["identity_hash"] = ""
    return replace(identity, identity_hash=canonical_hash(payload))


def _stamp_lease(lease: AgentLease) -> AgentLease:
    payload = lease.to_json_dict()
    payload["lease_hash"] = ""
    return replace(lease, lease_hash=canonical_hash(payload))


def _stamp_task(task: AgentTask) -> AgentTask:
    payload = task.to_json_dict()
    payload["task_hash"] = ""
    return replace(task, task_hash=canonical_hash(payload))


def _stamp_handoff(handoff: AgentHandoff) -> AgentHandoff:
    payload = handoff.to_json_dict()
    payload["handoff_hash"] = ""
    return replace(handoff, handoff_hash=canonical_hash(payload))


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
