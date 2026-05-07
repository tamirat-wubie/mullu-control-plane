"""Gateway user-owned agent identity.

Purpose: bind persistent user-owned agents to tenants, owners, capability
scopes, memory scopes, approval limits, delegation limits, budgets, evidence,
and reputation.
Governance scope: agent accountability, tenant isolation, capability admission,
memory admission, approval separation, delegation control, budget enforcement,
and evidence-backed reputation.
Dependencies: dataclasses, datetime, threading, and command-spine hashing.
Invariants:
  - Every agent identity has one owner and one tenant.
  - Allowed and forbidden capabilities must be disjoint.
  - Agent identities cannot mutate policy or approve their own requests.
  - Delegation is lease-bound and depth-limited.
  - Reputation updates require evidence refs and stay bounded.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable

from gateway.command_spine import canonical_hash


AGENT_STATUSES = ("active", "suspended", "revoked")
RISK_TIERS = ("low", "medium", "high", "critical")
OUTCOME_STATUSES = ("succeeded", "failed", "compensated", "requires_review")
MEMORY_USES = ("planning", "execution")
POLICY_MUTATION_CAPABILITIES = frozenset(
    {
        "policy.modify",
        "policy.promote",
        "authority_rules.modify",
    },
)


@dataclass(frozen=True, slots=True)
class AgentBudget:
    """Budget envelope for one persistent agent identity."""

    daily_action_limit: int
    daily_cost_limit: float
    per_action_cost_limit: float
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.daily_action_limit, int) or isinstance(self.daily_action_limit, bool):
            raise ValueError("daily_action_limit_integer_required")
        if self.daily_action_limit <= 0:
            raise ValueError("positive_daily_action_limit_required")
        _require_nonnegative_number(self.daily_cost_limit, "daily_cost_limit")
        _require_nonnegative_number(self.per_action_cost_limit, "per_action_cost_limit")
        _require_text(self.currency, "currency")


@dataclass(frozen=True, slots=True)
class AgentMemoryScope:
    """Memory classes admitted for planning or execution by one agent."""

    planning_memory_classes: tuple[str, ...]
    execution_memory_classes: tuple[str, ...]
    forbidden_memory_classes: tuple[str, ...] = ()
    tenant_bound: bool = True
    owner_bound: bool = True

    def __post_init__(self) -> None:
        planning = _normalize_text_tuple(self.planning_memory_classes, "planning_memory_classes")
        execution = _normalize_text_tuple(self.execution_memory_classes, "execution_memory_classes")
        forbidden = _normalize_text_tuple(self.forbidden_memory_classes, "forbidden_memory_classes", allow_empty=True)
        if set(forbidden).intersection(planning, execution):
            raise ValueError("memory_scope_conflict")
        if self.tenant_bound is not True:
            raise ValueError("tenant_bound_memory_scope_required")
        if self.owner_bound is not True:
            raise ValueError("owner_bound_memory_scope_required")
        object.__setattr__(self, "planning_memory_classes", planning)
        object.__setattr__(self, "execution_memory_classes", execution)
        object.__setattr__(self, "forbidden_memory_classes", forbidden)


@dataclass(frozen=True, slots=True)
class AgentApprovalScope:
    """Approval powers and limits for one agent identity."""

    can_request_approval: bool
    can_grant_approval: bool
    approval_roles: tuple[str, ...] = ()
    approval_limit: float = 0.0
    cannot_self_approve: bool = True

    def __post_init__(self) -> None:
        roles = _normalize_text_tuple(self.approval_roles, "approval_roles", allow_empty=not self.can_grant_approval)
        _require_nonnegative_number(self.approval_limit, "approval_limit")
        if self.cannot_self_approve is not True:
            raise ValueError("self_approval_must_be_forbidden")
        object.__setattr__(self, "approval_roles", roles)


@dataclass(frozen=True, slots=True)
class AgentDelegationScope:
    """Delegation controls for worker or specialist dispatch."""

    can_delegate: bool
    allowed_worker_roles: tuple[str, ...]
    allowed_worker_capabilities: tuple[str, ...]
    max_depth: int
    requires_lease: bool = True

    def __post_init__(self) -> None:
        roles = _normalize_text_tuple(self.allowed_worker_roles, "allowed_worker_roles", allow_empty=not self.can_delegate)
        capabilities = _normalize_text_tuple(
            self.allowed_worker_capabilities,
            "allowed_worker_capabilities",
            allow_empty=not self.can_delegate,
        )
        if not isinstance(self.max_depth, int) or isinstance(self.max_depth, bool):
            raise ValueError("max_depth_integer_required")
        if self.max_depth < 0:
            raise ValueError("nonnegative_max_depth_required")
        if self.requires_lease is not True:
            raise ValueError("delegation_requires_lease")
        object.__setattr__(self, "allowed_worker_roles", roles)
        object.__setattr__(self, "allowed_worker_capabilities", capabilities)


@dataclass(frozen=True, slots=True)
class AgentEvidenceRecord:
    """Evidence item attached to an agent identity history."""

    evidence_ref: str
    evidence_type: str
    observed_at: str
    command_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.evidence_ref, "evidence_ref")
        _require_text(self.evidence_type, "evidence_type")
        _require_text(self.observed_at, "observed_at")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    """Persistent accountable identity for one user-owned agent."""

    agent_id: str
    owner_id: str
    tenant_id: str
    role: str
    status: str
    allowed_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    budget: AgentBudget
    memory_scope: AgentMemoryScope
    approval_scope: AgentApprovalScope
    delegation_scope: AgentDelegationScope
    evidence_history: tuple[AgentEvidenceRecord, ...]
    reputation_score: float
    created_at: str
    updated_at: str
    identity_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.agent_id, "agent_id")
        _require_text(self.owner_id, "owner_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.role, "role")
        if self.status not in AGENT_STATUSES:
            raise ValueError("agent_status_invalid")
        allowed = _normalize_text_tuple(self.allowed_capabilities, "allowed_capabilities")
        if set(allowed).intersection(POLICY_MUTATION_CAPABILITIES):
            raise ValueError("policy_mutation_forbidden")
        forbidden = _normalize_text_tuple(
            (*self.forbidden_capabilities, *tuple(sorted(POLICY_MUTATION_CAPABILITIES))),
            "forbidden_capabilities",
        )
        if set(allowed).intersection(forbidden):
            raise ValueError("capability_scope_conflict")
        if not 0 <= self.reputation_score <= 1:
            raise ValueError("reputation_score_between_zero_and_one")
        _require_text(self.created_at, "created_at")
        _require_text(self.updated_at, "updated_at")
        object.__setattr__(self, "allowed_capabilities", allowed)
        object.__setattr__(self, "forbidden_capabilities", forbidden)
        object.__setattr__(self, "evidence_history", _normalize_evidence(self.evidence_history))
        object.__setattr__(self, "metadata", _identity_metadata(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-oriented JSON object."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentActionRequest:
    """One action admission request for an agent identity."""

    request_id: str
    agent_id: str
    tenant_id: str
    capability: str
    operation: str
    risk_tier: str
    cost_estimate: float = 0.0
    memory_class: str = ""
    memory_use: str = ""
    approval_target_agent_id: str = ""
    target_worker_capability: str = ""
    delegation_depth: int = 0
    requested_at: str = ""
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.agent_id, "agent_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.capability, "capability")
        _require_text(self.operation, "operation")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        _require_nonnegative_number(self.cost_estimate, "cost_estimate")
        if self.memory_use and self.memory_use not in MEMORY_USES:
            raise ValueError("memory_use_invalid")
        if not isinstance(self.delegation_depth, int) or isinstance(self.delegation_depth, bool):
            raise ValueError("delegation_depth_integer_required")
        if self.delegation_depth < 0:
            raise ValueError("nonnegative_delegation_depth_required")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class AgentActionDecision:
    """Deterministic admission decision for one agent action request."""

    decision_id: str
    request_id: str
    agent_id: str
    tenant_id: str
    allowed: bool
    reason: str
    required_controls: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_controls", _normalize_text_tuple(self.required_controls, "required_controls", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-oriented decision payload."""
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class AgentOutcome:
    """Observed terminal outcome used to update agent reputation."""

    outcome_id: str
    agent_id: str
    tenant_id: str
    command_id: str
    status: str
    risk_tier: str
    observed_at: str
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.outcome_id, "outcome_id")
        _require_text(self.agent_id, "agent_id")
        _require_text(self.tenant_id, "tenant_id")
        _require_text(self.command_id, "command_id")
        if self.status not in OUTCOME_STATUSES:
            raise ValueError("outcome_status_invalid")
        if self.risk_tier not in RISK_TIERS:
            raise ValueError("risk_tier_invalid")
        _require_text(self.observed_at, "observed_at")
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


class AgentIdentityRegistry:
    """In-memory accountable agent identity registry."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now
        self._agents: dict[str, AgentIdentity] = {}
        self._usage: dict[tuple[str, str], dict[str, float]] = {}
        self._lock = threading.Lock()

    def register(self, identity: AgentIdentity) -> AgentIdentity:
        """Register or replace one stamped agent identity."""
        stamped = _stamp_identity(identity)
        with self._lock:
            self._agents[stamped.agent_id] = stamped
        return stamped

    def get(self, agent_id: str) -> AgentIdentity | None:
        """Return one known agent identity by id."""
        with self._lock:
            return self._agents.get(agent_id)

    def evaluate(self, request: AgentActionRequest) -> AgentActionDecision:
        """Evaluate one action request against the registered agent identity."""
        requested_at = request.requested_at or self._clock()
        request = replace(request, requested_at=requested_at)
        with self._lock:
            agent = self._agents.get(request.agent_id)
            usage = self._usage.setdefault(_usage_key(request.agent_id, requested_at), {"actions": 0.0, "cost": 0.0})
            denial = _admission_denial(agent, request, usage) if agent else "agent_identity_not_found"
            decision = _decision(agent, request, allowed=not denial, reason=denial or "allowed")
            if decision.allowed:
                usage["actions"] += 1
                usage["cost"] += float(request.cost_estimate)
            return decision

    def record_outcome(self, outcome: AgentOutcome) -> AgentIdentity:
        """Update reputation from one evidence-backed observed outcome."""
        with self._lock:
            agent = self._agents.get(outcome.agent_id)
            if agent is None:
                raise ValueError("agent_identity_not_found")
            if agent.tenant_id != outcome.tenant_id:
                raise ValueError("tenant_mismatch")
            updated_score = _updated_reputation(agent.reputation_score, outcome)
            evidence_record = AgentEvidenceRecord(
                evidence_ref=outcome.evidence_refs[0],
                evidence_type=f"outcome:{outcome.status}",
                observed_at=outcome.observed_at,
                command_id=outcome.command_id,
                metadata={
                    "outcome_id": outcome.outcome_id,
                    "risk_tier": outcome.risk_tier,
                    "evidence_count": len(outcome.evidence_refs),
                },
            )
            updated = _stamp_identity(
                replace(
                    agent,
                    evidence_history=(*agent.evidence_history, evidence_record)[-50:],
                    reputation_score=updated_score,
                    updated_at=outcome.observed_at,
                ),
            )
            self._agents[updated.agent_id] = updated
            return updated

    def read_model(self) -> dict[str, Any]:
        """Return a bounded read model for operator inspection."""
        with self._lock:
            return {
                "agent_count": len(self._agents),
                "agents": [agent.to_json_dict() for agent in sorted(self._agents.values(), key=lambda item: item.agent_id)],
                "usage": [
                    {
                        "agent_id": agent_id,
                        "date": usage_date,
                        "actions": usage["actions"],
                        "cost": round(usage["cost"], 6),
                    }
                    for (agent_id, usage_date), usage in sorted(self._usage.items())
                ],
            }


def _admission_denial(
    agent: AgentIdentity | None,
    request: AgentActionRequest,
    usage: dict[str, float],
) -> str:
    if agent is None:
        return "agent_identity_not_found"
    if agent.status != "active":
        return "agent_status_not_active"
    if request.tenant_id != agent.tenant_id:
        return "tenant_mismatch"
    if request.capability in agent.forbidden_capabilities:
        return "capability_forbidden"
    if request.capability not in agent.allowed_capabilities:
        return "capability_not_allowed"
    if request.cost_estimate > agent.budget.per_action_cost_limit:
        return "per_action_cost_budget_exceeded"
    if usage["actions"] >= agent.budget.daily_action_limit:
        return "daily_action_budget_exhausted"
    if usage["cost"] + request.cost_estimate > agent.budget.daily_cost_limit:
        return "daily_cost_budget_exhausted"
    memory_denial = _memory_denial(agent, request)
    if memory_denial:
        return memory_denial
    approval_denial = _approval_denial(agent, request)
    if approval_denial:
        return approval_denial
    delegation_denial = _delegation_denial(agent, request)
    if delegation_denial:
        return delegation_denial
    if request.risk_tier in {"high", "critical"} and not request.evidence_refs:
        return "high_risk_evidence_required"
    return ""


def _memory_denial(agent: AgentIdentity, request: AgentActionRequest) -> str:
    if not request.memory_class:
        return ""
    if not request.memory_use:
        return "memory_use_required"
    if request.memory_class in agent.memory_scope.forbidden_memory_classes:
        return "memory_class_forbidden"
    if request.memory_use == "planning" and request.memory_class not in agent.memory_scope.planning_memory_classes:
        return "memory_class_not_allowed_for_planning"
    if request.memory_use == "execution" and request.memory_class not in agent.memory_scope.execution_memory_classes:
        return "memory_class_not_allowed_for_execution"
    return ""


def _approval_denial(agent: AgentIdentity, request: AgentActionRequest) -> str:
    if request.operation == "request_approval" and not agent.approval_scope.can_request_approval:
        return "approval_request_not_allowed"
    if request.operation == "grant_approval" or request.capability == "approval.grant":
        if not agent.approval_scope.can_grant_approval:
            return "approval_grant_not_allowed"
        if request.approval_target_agent_id == request.agent_id:
            return "self_approval_forbidden"
        if request.cost_estimate > agent.approval_scope.approval_limit:
            return "approval_limit_exceeded"
    return ""


def _delegation_denial(agent: AgentIdentity, request: AgentActionRequest) -> str:
    if request.operation != "delegate":
        return ""
    if not agent.delegation_scope.can_delegate:
        return "delegation_not_allowed"
    if request.delegation_depth > agent.delegation_scope.max_depth:
        return "delegation_depth_exceeded"
    if not request.target_worker_capability:
        return "target_worker_capability_required"
    if request.target_worker_capability not in agent.delegation_scope.allowed_worker_capabilities:
        return "worker_capability_not_allowed"
    return ""


def _decision(
    agent: AgentIdentity | None,
    request: AgentActionRequest,
    *,
    allowed: bool,
    reason: str,
) -> AgentActionDecision:
    controls = _required_controls(request) if allowed else ()
    decision = AgentActionDecision(
        decision_id="pending",
        request_id=request.request_id,
        agent_id=request.agent_id,
        tenant_id=request.tenant_id,
        allowed=allowed,
        reason=reason,
        required_controls=controls,
        evidence_refs=request.evidence_refs,
        metadata={
            "decision_is_not_execution": True,
            "agent_identity_hash": agent.identity_hash if agent else "",
            "reputation_score": agent.reputation_score if agent else 0.0,
        },
    )
    decision_hash = canonical_hash(asdict(decision))
    return replace(decision, decision_id=f"agent-decision-{decision_hash[:16]}", decision_hash=decision_hash)


def _required_controls(request: AgentActionRequest) -> tuple[str, ...]:
    controls = ["agent_identity_admission"]
    if request.risk_tier in {"high", "critical"}:
        controls.extend(["fresh_approval", "terminal_closure"])
    if request.risk_tier == "critical":
        controls.append("operator_review")
    if request.operation == "delegate":
        controls.append("active_worker_lease")
    return tuple(dict.fromkeys(controls))


def _updated_reputation(score: float, outcome: AgentOutcome) -> float:
    delta_by_status = {
        "succeeded": 0.02,
        "failed": -0.10,
        "compensated": -0.05,
        "requires_review": -0.03,
    }
    risk_weight = {
        "low": 0.5,
        "medium": 1.0,
        "high": 1.25,
        "critical": 1.5,
    }
    delta = delta_by_status[outcome.status] * risk_weight[outcome.risk_tier]
    return min(1.0, max(0.0, round(score + delta, 6)))


def _stamp_identity(identity: AgentIdentity) -> AgentIdentity:
    stamped = replace(identity, identity_hash="")
    identity_hash = canonical_hash(asdict(stamped))
    return replace(stamped, identity_hash=identity_hash)


def _usage_key(agent_id: str, timestamp: str) -> tuple[str, str]:
    return (agent_id, _parse_time(timestamp).date().isoformat())


def _normalize_evidence(values: tuple[AgentEvidenceRecord, ...]) -> tuple[AgentEvidenceRecord, ...]:
    records = tuple(values)
    for record in records:
        if not isinstance(record, AgentEvidenceRecord):
            raise ValueError("agent_evidence_record_invalid")
    return records


def _identity_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    payload = dict(metadata)
    payload["identity_is_accountable"] = True
    payload["agent_cannot_approve_self"] = True
    payload["policy_mutation_forbidden"] = True
    return payload


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _require_nonnegative_number(value: float, field_name: str) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name}_number_required")
    if value < 0:
        raise ValueError(f"nonnegative_{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
