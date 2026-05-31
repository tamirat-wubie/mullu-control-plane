"""Governed swarm work fabric contracts.

Purpose: define typed identities, tasks, leases, messages, decisions, receipts,
and closure certificates for supervisor-led symbolic intelligence work.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS invariants for
bounded multi-worker coordination.
Dependencies: Python dataclasses, enums, decimal arithmetic, and UTC time.
Invariants: no anonymous agent, no lease without authority, no side effect from
agents, no closure without receipt-backed proof.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence


class SwarmInvariantViolation(ValueError):
    """Raised when a governed swarm invariant is violated."""


class WHQRGate(str, Enum):
    """Typed proof state for WHQR claims."""

    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
    BUDGET_UNKNOWN = "budget-unknown"


class SwarmMessageType(str, Enum):
    """Allowed structured message types."""

    CLAIM = "claim"
    DECISION = "decision"
    RECEIPT = "receipt"
    VIOLATION = "violation"


class SwarmDecisionVerdict(str, Enum):
    """Terminal or escalation verdict for supervisor decisions."""

    PASSED = "passed"
    FAILED = "failed"
    ESCALATE = "escalate"


class SwarmTaskRisk(str, Enum):
    """Bounded task risk classes."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def utc_now_iso() -> str:
    """Return an auditable UTC timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_non_empty(value: str, field_name: str) -> str:
    """Validate a required symbolic identifier."""

    if not value or not value.strip():
        raise SwarmInvariantViolation(f"{field_name} must be non-empty")
    return value


def require_no_duplicates(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    """Validate a deterministic sequence with no duplicate symbols."""

    normalized = tuple(values)
    if len(normalized) != len(set(normalized)):
        raise SwarmInvariantViolation(f"{field_name} contains duplicate entries")
    return normalized


def parse_utc(value: str, field_name: str) -> datetime:
    """Parse an ISO timestamp and return a UTC-aware datetime."""

    require_non_empty(value, field_name)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SwarmInvariantViolation(f"{field_name} must include timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class AgentIdentity:
    """Governed identity and authority scope for a specialist worker."""

    agent_id: str
    tenant_id: str
    role: str
    allowed_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...] = ()
    budget_scope: str = "analysis_only"
    memory_scope: str = ""
    requires_supervisor: bool = True

    def __post_init__(self) -> None:
        require_non_empty(self.agent_id, "agent_id")
        require_non_empty(self.tenant_id, "tenant_id")
        require_non_empty(self.role, "role")
        if self.memory_scope == "":
            object.__setattr__(self, "memory_scope", f"{self.tenant_id}.{self.role}")
        allowed = require_no_duplicates(self.allowed_capabilities, "allowed_capabilities")
        forbidden = require_no_duplicates(self.forbidden_capabilities, "forbidden_capabilities")
        overlap = set(allowed).intersection(forbidden)
        if overlap:
            raise SwarmInvariantViolation(f"capability both allowed and forbidden: {sorted(overlap)}")
        object.__setattr__(self, "allowed_capabilities", allowed)
        object.__setattr__(self, "forbidden_capabilities", forbidden)

    def can_perform(self, actions: Sequence[str]) -> bool:
        """Return whether every requested action is within identity authority."""

        requested = set(actions)
        return requested.issubset(set(self.allowed_capabilities)) and not requested.intersection(
            self.forbidden_capabilities
        )


@dataclass(frozen=True)
class SwarmGoal:
    """User goal compiled into bounded specialist task requirements."""

    goal_id: str
    tenant_id: str
    description: str
    task_specs: tuple[Mapping[str, object], ...]
    max_cost_usd: Decimal = Decimal("0.00")

    def __post_init__(self) -> None:
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.tenant_id, "tenant_id")
        require_non_empty(self.description, "description")
        if not isinstance(self.task_specs, tuple):
            raise SwarmInvariantViolation("task_specs must be a tuple of task spec mappings")
        if not self.task_specs:
            raise SwarmInvariantViolation("goal must include at least one task spec")
        for index, spec in enumerate(self.task_specs):
            if not isinstance(spec, MappingABC):
                raise SwarmInvariantViolation(f"task_specs[{index}] must be a mapping")
        if self.max_cost_usd < Decimal("0.00"):
            raise SwarmInvariantViolation("max_cost_usd cannot be negative")


@dataclass(frozen=True)
class SwarmTask:
    """Bounded task assigned by the supervisor to one specialist identity."""

    task_id: str
    goal_id: str
    tenant_id: str
    required_role: str
    required_capabilities: tuple[str, ...]
    input_refs: tuple[str, ...]
    expected_output: str
    risk: SwarmTaskRisk = SwarmTaskRisk.LOW
    deadline: str | None = None
    requires_receipt: bool = True
    side_effects_allowed: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.task_id, "task_id")
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.tenant_id, "tenant_id")
        require_non_empty(self.required_role, "required_role")
        require_non_empty(self.expected_output, "expected_output")
        object.__setattr__(
            self,
            "required_capabilities",
            require_no_duplicates(self.required_capabilities, "required_capabilities"),
        )
        object.__setattr__(self, "input_refs", require_no_duplicates(self.input_refs, "input_refs"))
        if self.deadline is not None:
            parse_utc(self.deadline, "deadline")
        if self.side_effects_allowed:
            raise SwarmInvariantViolation("agents cannot receive side-effect authority")


@dataclass(frozen=True)
class TaskLease:
    """Time, cost, and action boundary for one task run."""

    lease_id: str
    agent_id: str
    tenant_id: str
    task_id: str
    allowed_actions: tuple[str, ...]
    expires_at: str
    max_cost_usd: Decimal
    side_effects_allowed: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.lease_id, "lease_id")
        require_non_empty(self.agent_id, "agent_id")
        require_non_empty(self.tenant_id, "tenant_id")
        require_non_empty(self.task_id, "task_id")
        object.__setattr__(self, "allowed_actions", require_no_duplicates(self.allowed_actions, "allowed_actions"))
        parse_utc(self.expires_at, "expires_at")
        if self.max_cost_usd < Decimal("0.00"):
            raise SwarmInvariantViolation("max_cost_usd cannot be negative")
        if self.side_effects_allowed:
            raise SwarmInvariantViolation("task leases cannot allow side effects")

    def is_expired(self, now: str) -> bool:
        """Return whether the lease has expired at the supplied UTC timestamp."""

        return parse_utc(now, "now") >= parse_utc(self.expires_at, "expires_at")


@dataclass(frozen=True)
class SwarmClaim:
    """Structured WHQR claim emitted by an agent."""

    role: str
    target: str
    gate: WHQRGate
    reason: str

    def __post_init__(self) -> None:
        require_non_empty(self.role, "role")
        require_non_empty(self.target, "target")
        require_non_empty(self.reason, "reason")


@dataclass(frozen=True)
class SwarmMessage:
    """Auditable inter-agent message with evidence references."""

    message_id: str
    goal_id: str
    task_id: str
    from_agent: str
    to_agent: str
    message_type: SwarmMessageType
    claim: SwarmClaim
    evidence_refs: tuple[str, ...]
    confidence: Decimal
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        require_non_empty(self.message_id, "message_id")
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.task_id, "task_id")
        require_non_empty(self.from_agent, "from_agent")
        require_non_empty(self.to_agent, "to_agent")
        object.__setattr__(self, "evidence_refs", require_no_duplicates(self.evidence_refs, "evidence_refs"))
        if self.confidence < Decimal("0") or self.confidence > Decimal("1"):
            raise SwarmInvariantViolation("confidence must be between 0 and 1")
        parse_utc(self.created_at, "created_at")


@dataclass(frozen=True)
class SwarmDecision:
    """Supervisor decision after conflict, policy, and quorum checks."""

    decision_id: str
    goal_id: str
    verdict: SwarmDecisionVerdict
    reason: str
    message_ids: tuple[str, ...]
    requires_human_approval: bool = False

    def __post_init__(self) -> None:
        require_non_empty(self.decision_id, "decision_id")
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.reason, "reason")
        object.__setattr__(self, "message_ids", require_no_duplicates(self.message_ids, "message_ids"))


@dataclass(frozen=True)
class SwarmReceipt:
    """Receipt proving a task was completed, blocked, or escalated."""

    receipt_id: str
    goal_id: str
    task_id: str
    agent_id: str
    lease_id: str
    outcome: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.receipt_id, "receipt_id")
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.task_id, "task_id")
        require_non_empty(self.agent_id, "agent_id")
        require_non_empty(self.lease_id, "lease_id")
        require_non_empty(self.outcome, "outcome")
        object.__setattr__(self, "evidence_refs", require_no_duplicates(self.evidence_refs, "evidence_refs"))


@dataclass(frozen=True)
class SwarmTraceEntry:
    """Append-only causal trace record for swarm events."""

    trace_id: str
    goal_id: str
    event_type: str
    actor_id: str
    caused_by: str
    summary: str
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        require_non_empty(self.trace_id, "trace_id")
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.event_type, "event_type")
        require_non_empty(self.actor_id, "actor_id")
        require_non_empty(self.caused_by, "caused_by")
        require_non_empty(self.summary, "summary")
        parse_utc(self.created_at, "created_at")


@dataclass(frozen=True)
class SwarmClosureCertificate:
    """Terminal proof object for a completed governed swarm goal."""

    certificate_id: str
    goal_id: str
    decision_id: str
    receipt_ids: tuple[str, ...]
    trace_ids: tuple[str, ...]
    status: str
    proof_stamp: str

    def __post_init__(self) -> None:
        require_non_empty(self.certificate_id, "certificate_id")
        require_non_empty(self.goal_id, "goal_id")
        require_non_empty(self.decision_id, "decision_id")
        require_non_empty(self.status, "status")
        require_non_empty(self.proof_stamp, "proof_stamp")
        object.__setattr__(self, "receipt_ids", require_no_duplicates(self.receipt_ids, "receipt_ids"))
        object.__setattr__(self, "trace_ids", require_no_duplicates(self.trace_ids, "trace_ids"))
        if not self.receipt_ids:
            raise SwarmInvariantViolation("closure requires at least one receipt")
        if not self.trace_ids:
            raise SwarmInvariantViolation("closure requires at least one trace")
