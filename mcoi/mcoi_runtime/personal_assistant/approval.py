"""Purpose: deterministic approval queue for personal-assistant actions.
Governance scope: P3/P4/P5 approval packets, decision records, receipt
emission, and no-execution guarantees for effect-bearing proposed actions.
Dependencies: personal-assistant contracts, skill registry, approval matrix,
and standard regex.
Invariants:
  - The queue records approval evidence only and never executes a proposed action.
  - Approval-required packets require explicit approver and evidence bindings.
  - Receipts record actions taken and effect-bearing actions not taken.
  - Raw private connector payloads and secret-like values are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from .approval_matrix import (
    PersonalAssistantApprovalMatrix,
    load_default_personal_assistant_approval_matrix,
)
from .contracts import PersonalAssistantInvariantError, SkillRiskLevel
from .intake import ApprovalScope
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_KEY_FRAGMENTS = (
    "raw",
    "body",
    "payload",
    "secret",
    "token",
    "credential",
    "private_key",
    "authorization",
    "cookie",
)
_APPROVAL_ACTIONS_NOT_TAKEN = (
    "proposed_action_not_executed",
    "external_message_not_sent",
    "connector_state_not_mutated",
    "system_of_record_not_written",
    "money_legal_public_action_not_performed",
)


class ApprovalDecision(StrEnum):
    """Schema-backed approval queue decision values."""

    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"
    EXPIRED = "expired"
    BLOCKED = "blocked"

    @staticmethod
    def coerce(value: str | "ApprovalDecision") -> "ApprovalDecision":
        """Coerce text into an approval decision."""
        if isinstance(value, ApprovalDecision):
            return value
        try:
            return ApprovalDecision(str(value))
        except ValueError as exc:
            raise PersonalAssistantInvariantError(f"unknown approval decision: {value}") from exc


@dataclass(frozen=True, slots=True)
class ApprovalProposedAction:
    """One effect-bearing action proposed for explicit operator approval."""

    action_id: str
    skill_id: str
    risk_level: SkillRiskLevel | str
    effect_boundary: str
    summary: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", _require_text(self.action_id, "action_id"))
        object.__setattr__(self, "skill_id", _require_skill_id(self.skill_id))
        risk_level = (
            self.risk_level
            if isinstance(self.risk_level, SkillRiskLevel)
            else SkillRiskLevel.coerce(str(self.risk_level))
        )
        object.__setattr__(self, "risk_level", risk_level)
        object.__setattr__(self, "effect_boundary", _require_text(self.effect_boundary, "effect_boundary"))
        object.__setattr__(self, "summary", _require_text(self.summary, "summary"))

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "ApprovalProposedAction":
        """Build one proposed action from a schema-shaped mapping."""
        if not isinstance(payload, Mapping):
            raise PersonalAssistantInvariantError("proposed action must be a mapping")
        _scan_private_or_secret_payload(payload, path="proposed_action")
        return ApprovalProposedAction(
            action_id=_require_mapping_text(payload, "action_id"),
            skill_id=_require_mapping_text(payload, "skill_id"),
            risk_level=_require_mapping_text(payload, "risk_level"),
            effect_boundary=_require_mapping_text(payload, "effect_boundary"),
            summary=_require_mapping_text(payload, "summary"),
        )

    def as_dict(self) -> dict[str, str]:
        """Return a schema-ready proposed action."""
        return {
            "action_id": self.action_id,
            "skill_id": self.skill_id,
            "risk_level": self.risk_level.value,
            "effect_boundary": self.effect_boundary,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class ApprovalPlanProposal:
    """No-effect approval proposal derived from a matrix-bound plan."""

    request_id: str
    plan_id: str
    approval_scope: ApprovalScope
    risk_level: SkillRiskLevel
    proposed_actions: tuple[ApprovalProposedAction, ...]
    forbidden_without_approval: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    approval_matrix_ref: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_prefix(self.request_id, "request_id", "pa_request_"))
        object.__setattr__(self, "plan_id", _require_prefix(self.plan_id, "plan_id", "pa_plan_"))
        object.__setattr__(self, "approval_scope", _coerce_approval_scope(self.approval_scope))
        risk_level = (
            self.risk_level
            if isinstance(self.risk_level, SkillRiskLevel)
            else SkillRiskLevel.coerce(str(self.risk_level))
        )
        object.__setattr__(self, "risk_level", risk_level)
        object.__setattr__(self, "proposed_actions", _action_tuple(self.proposed_actions))
        object.__setattr__(
            self,
            "forbidden_without_approval",
            _text_tuple(self.forbidden_without_approval, "forbidden_without_approval"),
        )
        object.__setattr__(self, "evidence_refs", _text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(
            self,
            "approval_matrix_ref",
            _require_text(self.approval_matrix_ref, "approval_matrix_ref"),
        )
        if not isinstance(self.execution_allowed, bool):
            raise PersonalAssistantInvariantError("execution_allowed must be a boolean")
        if self.execution_allowed:
            raise PersonalAssistantInvariantError("approval proposal cannot authorize execution")
        if _max_action_risk(self.proposed_actions) is not risk_level:
            raise PersonalAssistantInvariantError("proposal risk_level must match proposed action risk")

    def as_enqueue_kwargs(self, *, approver_ref: str, created_at: str) -> dict[str, Any]:
        """Return keyword arguments accepted by PersonalAssistantApprovalQueue.enqueue."""
        return {
            "request_id": self.request_id,
            "plan_id": self.plan_id,
            "approver_ref": _require_text(approver_ref, "approver_ref"),
            "approval_scope": self.approval_scope,
            "proposed_actions": self.proposed_actions,
            "forbidden_without_approval": self.forbidden_without_approval,
            "evidence_refs": self.evidence_refs,
            "created_at": _require_text(created_at, "created_at"),
        }

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready approval proposal."""
        return {
            "request_id": self.request_id,
            "plan_id": self.plan_id,
            "approval_scope": self.approval_scope.value,
            "risk_level": self.risk_level.value,
            "proposed_actions": [action.as_dict() for action in self.proposed_actions],
            "forbidden_without_approval": list(self.forbidden_without_approval),
            "evidence_refs": list(self.evidence_refs),
            "approval_matrix_ref": self.approval_matrix_ref,
            "execution_allowed": self.execution_allowed,
            "approval_is_execution": False,
        }

    def as_review_packet(self, *, generated_at: str, reviewer_ref: str) -> dict[str, Any]:
        """Return an operator-facing no-effect review packet for this proposal."""
        generated_at = _require_text(generated_at, "generated_at")
        reviewer_ref = _require_text(reviewer_ref, "reviewer_ref")
        return {
            "schema_version": "personal_assistant.approval_review_packet.v1",
            "review_packet_id": f"pa_approval_review_{_plan_suffix(self.plan_id)}",
            "request_id": self.request_id,
            "plan_id": self.plan_id,
            "generated_at": generated_at,
            "reviewer_ref": reviewer_ref,
            "risk_level": self.risk_level.value,
            "approval_scope": self.approval_scope.value,
            "review_state": "preview_only",
            "proposed_actions": [action.as_dict() for action in self.proposed_actions],
            "forbidden_without_approval": list(self.forbidden_without_approval),
            "evidence_refs": list(self.evidence_refs),
            "required_operator_checks": _review_required_checks(self.risk_level),
            "authority_denials": _review_authority_denials(self.risk_level),
            "effect_boundary": {
                "execution_allowed": False,
                "approval_is_execution": False,
                "approval_enqueued": False,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
                "system_of_record_write_allowed": False,
                "money_legal_public_action_allowed": False,
            },
            "metadata": {
                "foundation_only": True,
                "approval_matrix_ref": self.approval_matrix_ref,
                "approval_packet_is_execution": False,
                "review_packet_is_execution": False,
                "live_nested_mind_activation_allowed": False,
                "customer_readiness_claim_allowed": False,
            },
        }


@dataclass(frozen=True, slots=True)
class ApprovalQueueRecord:
    """Immutable approval packet plus its emitted receipts."""

    approval_id: str
    packet: Mapping[str, Any]
    receipts: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "approval_id", _require_prefix(self.approval_id, "approval_id", "pa_approval_"))
        if not isinstance(self.packet, Mapping):
            raise PersonalAssistantInvariantError("approval packet must be a mapping")
        for receipt in self.receipts:
            if not isinstance(receipt, Mapping):
                raise PersonalAssistantInvariantError("approval receipt must be a mapping")
        object.__setattr__(self, "packet", MappingProxyType(dict(self.packet)))
        object.__setattr__(self, "receipts", tuple(MappingProxyType(dict(receipt)) for receipt in self.receipts))

    @property
    def latest_receipt(self) -> Mapping[str, Any]:
        """Return the most recent receipt for this approval record."""
        return self.receipts[-1]

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready approval record."""
        return {
            "approval_id": self.approval_id,
            "packet": dict(self.packet),
            "receipts": [dict(receipt) for receipt in self.receipts],
        }


def prepare_approval_proposal_from_plan(
    plan: Mapping[str, Any],
    *,
    approval_scope: ApprovalScope | str = ApprovalScope.PER_PLAN,
    approval_matrix: PersonalAssistantApprovalMatrix | None = None,
) -> ApprovalPlanProposal:
    """Derive an approval-queue proposal from a no-execution preview plan.

    Input contract: a planner-produced mapping with approval matrix metadata.
    Output contract: enqueue-ready approval proposal with no execution authority.
    Error contract: raises PersonalAssistantInvariantError for non-approval
    plans, matrix drift, unsafe forbidden actions, or missing evidence refs.
    """
    if not isinstance(plan, Mapping):
        raise PersonalAssistantInvariantError("plan must be a mapping")
    matrix = approval_matrix or load_default_personal_assistant_approval_matrix()
    request_id = _require_prefix(plan.get("request_id"), "request_id", "pa_request_")
    plan_id = _require_prefix(plan.get("plan_id"), "plan_id", "pa_plan_")
    if plan.get("execution_allowed") is not False:
        raise PersonalAssistantInvariantError(f"{plan_id}: plan must not authorize execution")
    gate = plan.get("approval_gate")
    if not isinstance(gate, Mapping):
        raise PersonalAssistantInvariantError(f"{plan_id}: approval_gate must be a mapping")
    if gate.get("approval_required") is not True:
        raise PersonalAssistantInvariantError(f"{plan_id}: plan does not require approval")
    matrix_metadata = _plan_approval_matrix_metadata(plan)
    metadata_matrix_id = _require_mapping_text(matrix_metadata, "matrix_id")
    if metadata_matrix_id != matrix.matrix_id:
        raise PersonalAssistantInvariantError(
            f"{plan_id}: plan approval matrix {metadata_matrix_id} does not match runtime {matrix.matrix_id}"
        )
    plan_risk = SkillRiskLevel.coerce(_require_mapping_text(plan, "risk_level"))
    approval_level = _require_mapping_text(gate, "approval_level")
    if approval_level != plan_risk.value:
        raise PersonalAssistantInvariantError(f"{plan_id}: approval level must match plan risk")
    approval_ref = _require_mapping_text(gate, "approval_ref")
    if not approval_ref.endswith(f"#{plan_risk.value}"):
        raise PersonalAssistantInvariantError(f"{plan_id}: approval_ref must bind matrix risk level")

    actions = _proposal_actions_from_plan_steps(plan)
    risk_level = max((plan_risk, *(action.risk_level for action in actions)), key=lambda risk: risk.order)
    forbidden = _matrix_forbidden_actions_from_plan(plan, matrix)
    evidence_refs = _text_tuple(plan.get("evidence_refs"), "evidence_refs")
    matrix.assert_action_admitted(
        risk_level=risk_level,
        execution_mode="blocked" if risk_level is SkillRiskLevel.P5 else "execute_with_approval",
        forbidden_without_approval=forbidden,
    )
    return ApprovalPlanProposal(
        request_id=request_id,
        plan_id=plan_id,
        approval_scope=approval_scope,
        risk_level=risk_level,
        proposed_actions=actions,
        forbidden_without_approval=forbidden,
        evidence_refs=evidence_refs,
        approval_matrix_ref=matrix.matrix_id,
        execution_allowed=False,
    )


@dataclass(slots=True)
class PersonalAssistantApprovalQueue:
    """In-memory approval queue read model for governed assistant actions."""

    _records: dict[str, ApprovalQueueRecord] = field(default_factory=dict)

    def enqueue(
        self,
        *,
        request_id: str,
        plan_id: str,
        approver_ref: str,
        approval_scope: ApprovalScope | str,
        proposed_actions: Sequence[ApprovalProposedAction | Mapping[str, Any]],
        forbidden_without_approval: Sequence[str],
        evidence_refs: Sequence[str],
        created_at: str,
        registry: PersonalAssistantSkillRegistry | None = None,
        approval_matrix: PersonalAssistantApprovalMatrix | None = None,
        approval_id: str | None = None,
    ) -> ApprovalQueueRecord:
        """Create a requested approval packet and request receipt."""
        request_id = _require_prefix(request_id, "request_id", "pa_request_")
        plan_id = _require_prefix(plan_id, "plan_id", "pa_plan_")
        approver_ref = _require_text(approver_ref, "approver_ref")
        created_at = _require_text(created_at, "created_at")
        scope = _coerce_approval_scope(approval_scope)
        actions = _action_tuple(proposed_actions)
        forbidden = _text_tuple(forbidden_without_approval, "forbidden_without_approval")
        evidence = _text_tuple(evidence_refs, "evidence_refs")
        skill_registry = registry or load_default_skill_registry()
        matrix = approval_matrix or load_default_personal_assistant_approval_matrix()
        _assert_actions_match_registry(actions, skill_registry)
        risk_level = _max_action_risk(actions)
        matrix.assert_action_admitted(
            risk_level=risk_level,
            execution_mode="blocked" if risk_level is SkillRiskLevel.P5 else "execute_with_approval",
            forbidden_without_approval=forbidden,
        )
        if not risk_level.requires_explicit_approval:
            raise PersonalAssistantInvariantError(
                f"{risk_level.value} proposed actions do not belong in the approval queue"
            )
        if scope is ApprovalScope.NONE:
            raise PersonalAssistantInvariantError("approval_scope cannot be none for approval-required actions")
        packet_id = approval_id or f"pa_approval_{_request_suffix(request_id)}_{_plan_suffix(plan_id)}"
        packet_id = _require_prefix(packet_id, "approval_id", "pa_approval_")
        if packet_id in self._records:
            raise PersonalAssistantInvariantError(f"duplicate approval_id: {packet_id}")
        receipt_id = f"pa_receipt_{_approval_suffix(packet_id)}_request"
        packet = {
            "approval_id": packet_id,
            "request_id": request_id,
            "plan_id": plan_id,
            "created_at": created_at,
            "risk_level": risk_level.value,
            "approval_state": "requested",
            "explicit_approval_required": True,
            "approver_ref": approver_ref,
            "approval_scope": scope.value,
            "proposed_actions": [action.as_dict() for action in actions],
            "forbidden_without_approval": list(forbidden),
            "decision_record": {
                "decision": "pending",
                "reason_codes": ["effect_bearing_action_requires_explicit_approval"],
                "decided_at": "",
            },
            "receipt_ref": receipt_id,
            "evidence_refs": list(evidence),
            "metadata": _approval_metadata(
                approval_decision="pending",
                execution_allowed=False,
                queue_state="requested",
                approval_matrix_ref=matrix.matrix_id,
            ),
        }
        receipt = _approval_receipt(
            packet=packet,
            receipt_id=receipt_id,
            timestamp=created_at,
            decision="approval_required",
            outcome="AwaitingEvidence",
            actions_taken=("approval_request_enqueued", "approval_packet_created", "receipt_created"),
            evidence_refs=evidence,
            metadata={
                "approval_decision": "pending",
                "queue_state": "requested",
                "execution_allowed": False,
                "approval_matrix_ref": matrix.matrix_id,
            },
        )
        record = ApprovalQueueRecord(packet_id, packet, (receipt,))
        self._records[packet_id] = record
        return record

    def record_decision(
        self,
        approval_id: str,
        *,
        decision: ApprovalDecision | str,
        reason_codes: Sequence[str],
        decided_at: str,
        decision_evidence_ref: str = "",
        revision_request: str = "",
    ) -> ApprovalQueueRecord:
        """Record an approval decision without executing the proposed action."""
        approval_id = _require_prefix(approval_id, "approval_id", "pa_approval_")
        approval_decision = ApprovalDecision.coerce(decision)
        decided_at = _require_text(decided_at, "decided_at")
        reasons = _text_tuple(reason_codes, "reason_codes")
        if approval_decision is ApprovalDecision.APPROVED:
            decision_evidence_ref = _require_text(decision_evidence_ref, "decision_evidence_ref")
        elif decision_evidence_ref:
            decision_evidence_ref = _require_text(decision_evidence_ref, "decision_evidence_ref")
        if approval_decision is ApprovalDecision.REVISED:
            revision_request = _require_text(revision_request, "revision_request")
        elif revision_request:
            revision_request = _require_text(revision_request, "revision_request")
        try:
            current = self._records[approval_id]
        except KeyError as exc:
            raise PersonalAssistantInvariantError(f"unknown approval_id: {approval_id}") from exc
        packet = dict(current.packet)
        if packet["approval_state"] != "requested":
            raise PersonalAssistantInvariantError(
                f"{approval_id}: approval decision already recorded as {packet['approval_state']}"
            )
        evidence_refs = list(packet["evidence_refs"])
        if decision_evidence_ref and decision_evidence_ref not in evidence_refs:
            evidence_refs.append(decision_evidence_ref)
        packet["approval_state"] = approval_decision.value
        packet["decision_record"] = {
            "decision": approval_decision.value,
            "reason_codes": list(reasons),
            "decided_at": decided_at,
        }
        packet["receipt_ref"] = f"pa_receipt_{_approval_suffix(approval_id)}_{approval_decision.value}"
        packet["evidence_refs"] = evidence_refs
        packet["metadata"] = _approval_metadata(
            approval_decision=approval_decision.value,
            execution_allowed=False,
            queue_state=approval_decision.value,
            revision_request=revision_request,
        )
        receipt = _approval_receipt(
            packet=packet,
            receipt_id=packet["receipt_ref"],
            timestamp=decided_at,
            decision=_receipt_decision_for(approval_decision),
            outcome="SolvedVerified",
            actions_taken=_decision_actions_taken(approval_decision),
            evidence_refs=tuple(evidence_refs),
            metadata={
                "approval_decision": approval_decision.value,
                "queue_state": approval_decision.value,
                "execution_allowed": False,
                "revision_request": revision_request,
            },
        )
        updated = ApprovalQueueRecord(approval_id, packet, (*current.receipts, receipt))
        self._records[approval_id] = updated
        return updated

    def get(self, approval_id: str) -> ApprovalQueueRecord:
        """Return one approval queue record."""
        approval_id = _require_prefix(approval_id, "approval_id", "pa_approval_")
        try:
            return self._records[approval_id]
        except KeyError as exc:
            raise PersonalAssistantInvariantError(f"unknown approval_id: {approval_id}") from exc

    def read_model(self) -> dict[str, Any]:
        """Return a deterministic operator-facing approval queue read model."""
        records = tuple(self._records[approval_id] for approval_id in sorted(self._records))
        state_counts = {state: 0 for state in ("requested", "approved", "rejected", "revised", "expired", "blocked")}
        for record in records:
            state = str(record.packet["approval_state"])
            state_counts[state] = state_counts.get(state, 0) + 1
        receipt_ids = [
            str(receipt["receipt_id"])
            for record in records
            for receipt in record.receipts
            if isinstance(receipt.get("receipt_id"), str)
        ]
        return {
            "approval_count": len(records),
            "approval_ids": [record.approval_id for record in records],
            "state_counts": state_counts,
            "receipt_ids": receipt_ids,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "approval_is_execution": False,
            "records": [record.as_dict() for record in records],
            "metadata": {
                "foundation_only": True,
                "queue_projection": "read_model",
                "persistence_boundary": "stateless_unless_hosted_store_is_explicitly_bound",
                "live_connector_execution_allowed": False,
                "approval_decision_executes_action": False,
            },
        }


def _assert_actions_match_registry(
    actions: tuple[ApprovalProposedAction, ...],
    registry: PersonalAssistantSkillRegistry,
) -> None:
    for action in actions:
        skill = registry.get(action.skill_id)
        if action.risk_level is not skill.risk_level:
            raise PersonalAssistantInvariantError(
                f"{action.action_id}: action risk {action.risk_level.value} does not match {skill.skill_id} "
                f"registry risk {skill.risk_level.value}"
            )
        if not skill.requires_approval:
            raise PersonalAssistantInvariantError(f"{skill.skill_id}: skill does not require approval")


def _plan_approval_matrix_metadata(plan: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = plan.get("metadata")
    if not isinstance(metadata, Mapping):
        raise PersonalAssistantInvariantError("plan metadata must be a mapping")
    matrix_metadata = metadata.get("approval_matrix")
    if not isinstance(matrix_metadata, Mapping):
        raise PersonalAssistantInvariantError("plan metadata.approval_matrix must be a mapping")
    return matrix_metadata


def _proposal_actions_from_plan_steps(plan: Mapping[str, Any]) -> tuple[ApprovalProposedAction, ...]:
    steps = plan.get("steps")
    if isinstance(steps, (str, bytes)) or not isinstance(steps, Sequence):
        raise PersonalAssistantInvariantError("plan steps must be a sequence")
    actions: list[ApprovalProposedAction] = []
    for offset, step in enumerate(steps):
        if not isinstance(step, Mapping):
            raise PersonalAssistantInvariantError(f"steps[{offset}] must be a mapping")
        approval_required = step.get("approval_required")
        if approval_required is not True:
            continue
        risk_level = SkillRiskLevel.coerce(_require_mapping_text(step, "risk_level"))
        if not risk_level.requires_explicit_approval:
            continue
        skill_id = _require_mapping_text(step, "skill_id")
        step_id = _require_mapping_text(step, "step_id")
        action = _require_mapping_text(step, "action")
        effect_boundary = _require_mapping_text(step, "effect_boundary")
        actions.append(
            ApprovalProposedAction(
                action_id=_safe_identifier(f"{step_id}_{action}"),
                skill_id=skill_id,
                risk_level=risk_level,
                effect_boundary=effect_boundary,
                summary=f"Request approval for {action} through {skill_id} at {effect_boundary}.",
            )
        )
    if not actions:
        raise PersonalAssistantInvariantError("plan has no approval-required effect-bearing steps")
    return tuple(actions)


def _matrix_forbidden_actions_from_plan(
    plan: Mapping[str, Any],
    matrix: PersonalAssistantApprovalMatrix,
) -> tuple[str, ...]:
    not_authorized = _text_tuple(plan.get("actions_not_authorized"), "actions_not_authorized")
    matrix_blockers = set(matrix.blocked_without_approval)
    forbidden = [action for action in not_authorized if action in matrix_blockers]
    if not forbidden:
        step_actions = [
            _require_mapping_text(step, "action")
            for step in plan.get("steps", ())
            if isinstance(step, Mapping) and step.get("approval_required") is True
        ]
        forbidden = [action for action in step_actions if action in matrix_blockers]
    if not forbidden:
        raise PersonalAssistantInvariantError("plan has no matrix-blocked actions for approval proposal")
    return tuple(_dedupe_texts(forbidden))


def _approval_receipt(
    *,
    packet: Mapping[str, Any],
    receipt_id: str,
    timestamp: str,
    decision: str,
    outcome: str,
    actions_taken: tuple[str, ...],
    evidence_refs: Sequence[str],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    actions = tuple(ApprovalProposedAction.from_mapping(action) for action in packet["proposed_actions"])
    risk_level = _max_action_risk(actions)
    return {
        "receipt_id": receipt_id,
        "request_id": str(packet["request_id"]),
        "skill_id": actions[0].skill_id,
        "mode": "execute_with_approval",
        "risk_level": risk_level.value,
        "inputs_used": ["approval_packet", "operator_decision_record"],
        "connectors_used": _connectors_for_actions(actions),
        "decision": decision,
        "approval_required": True,
        "approval_ref": str(packet["approval_id"]),
        "actions_taken": list(actions_taken),
        "actions_not_taken": list(_APPROVAL_ACTIONS_NOT_TAKEN),
        "redactions": ["approval_refs_only", "private_connector_payload_not_serialized"],
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "body_projection": "none",
        },
        "timestamp": timestamp,
        "evidence_refs": list(_dedupe_texts(evidence_refs)),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/approval/{_approval_suffix(str(packet['approval_id']))}"],
        "outcome": outcome,
        "metadata": {
            **dict(metadata),
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "money_legal_public_action_allowed": False,
            "approval_is_execution": False,
        },
    }


def _connectors_for_actions(actions: tuple[ApprovalProposedAction, ...]) -> list[str]:
    connector_names: list[str] = []
    for action in actions:
        if action.skill_id.startswith("email."):
            connector_names.append("gmail")
        if action.skill_id.startswith("calendar."):
            connector_names.append("google_calendar")
    return list(_dedupe_texts(connector_names))


def _approval_metadata(
    *,
    approval_decision: str,
    execution_allowed: bool,
    queue_state: str,
    revision_request: str = "",
    approval_matrix_ref: str = "",
) -> dict[str, Any]:
    metadata = {
        "foundation_only": True,
        "approval_decision": approval_decision,
        "queue_state": queue_state,
        "execution_allowed": execution_allowed,
        "approval_is_execution": False,
        "live_connector_execution_allowed": False,
        "connector_mutation_allowed": False,
        "external_write_allowed": False,
        "system_of_record_write_allowed": False,
        "money_legal_public_action_allowed": False,
    }
    if approval_matrix_ref:
        metadata["approval_matrix_ref"] = approval_matrix_ref
    if revision_request:
        metadata["revision_request"] = revision_request
    return metadata


def _review_required_checks(risk_level: SkillRiskLevel) -> list[str]:
    checks = [
        "confirm_request_identity",
        "confirm_plan_identity",
        "confirm_proposed_action_scope",
        "confirm_evidence_refs_present",
        "confirm_forbidden_actions_remain_unexecuted",
        "confirm_receipt_required",
    ]
    if risk_level.order >= SkillRiskLevel.P4.order:
        checks.append("confirm_external_recipient_or_target_scope")
    if risk_level is SkillRiskLevel.P5:
        checks.append("confirm_money_legal_public_deployment_boundary_blocked")
    return checks


def _review_authority_denials(risk_level: SkillRiskLevel) -> list[dict[str, str | bool]]:
    denials = [
        (
            "execution",
            "Approval review packets are no-effect previews and cannot execute proposed actions.",
        ),
        (
            "approval_enqueue",
            "Approval review packets do not enqueue approval records without an explicit queue action.",
        ),
        (
            "connector_mutation",
            "Connector mutation remains blocked until a future approved execution gate exists.",
        ),
        (
            "memory_write",
            "Memory writes remain blocked; review packets are evidence projections only.",
        ),
    ]
    if risk_level.order >= SkillRiskLevel.P4.order:
        denials.append(
            (
                "external_send",
                "External communication remains blocked until a separate approved execution path exists.",
            )
        )
    if risk_level is SkillRiskLevel.P5:
        denials.extend(
            (
                (
                    "money_legal_public_action",
                    "Money, legal, public, deployment, and customer-impacting actions remain blocked.",
                ),
                (
                    "deployment_mutation",
                    "Deployment mutation remains blocked in Foundation Mode.",
                ),
            )
        )
    return [
        {
            "authority": authority,
            "denied": True,
            "reason": reason,
        }
        for authority, reason in denials
    ]


def _decision_actions_taken(decision: ApprovalDecision) -> tuple[str, ...]:
    if decision is ApprovalDecision.APPROVED:
        return ("approval_decision_recorded", "approval_evidence_linked", "receipt_created")
    if decision is ApprovalDecision.REJECTED:
        return ("approval_rejection_recorded", "receipt_created")
    if decision is ApprovalDecision.REVISED:
        return ("approval_revision_requested", "receipt_created")
    if decision is ApprovalDecision.EXPIRED:
        return ("approval_expiration_recorded", "receipt_created")
    return ("approval_block_recorded", "receipt_created")


def _receipt_decision_for(decision: ApprovalDecision) -> str:
    if decision in {ApprovalDecision.REJECTED, ApprovalDecision.EXPIRED, ApprovalDecision.BLOCKED}:
        return "blocked"
    return "deferred"


def _action_tuple(
    values: Sequence[ApprovalProposedAction | Mapping[str, Any]],
) -> tuple[ApprovalProposedAction, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError("proposed_actions must be a sequence")
    actions = tuple(
        value if isinstance(value, ApprovalProposedAction) else ApprovalProposedAction.from_mapping(value)
        for value in values
    )
    if not actions:
        raise PersonalAssistantInvariantError("proposed_actions must contain at least one item")
    return actions


def _max_action_risk(actions: tuple[ApprovalProposedAction, ...]) -> SkillRiskLevel:
    return max((action.risk_level for action in actions), key=lambda risk: risk.order)


def _coerce_approval_scope(value: ApprovalScope | str) -> ApprovalScope:
    if isinstance(value, ApprovalScope):
        return value
    try:
        return ApprovalScope(str(value))
    except ValueError as exc:
        raise PersonalAssistantInvariantError(f"unknown approval_scope: {value}") from exc


def _text_tuple(values: Sequence[Any], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        item = _require_text(value, f"{field_name}[{index}]")
        if item not in normalized:
            normalized.append(item)
    if not normalized:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _dedupe_texts(values: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for value in values:
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _require_mapping_text(payload: Mapping[str, Any], field_name: str) -> str:
    return _require_text(payload.get(field_name), field_name)


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _require_prefix(value: Any, field_name: str, prefix: str) -> str:
    text = _require_text(value, field_name)
    if not text.startswith(prefix):
        raise PersonalAssistantInvariantError(f"{field_name} must start with {prefix}")
    return text


def _require_skill_id(value: Any) -> str:
    text = _require_text(value, "skill_id")
    if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z0-9_]+)+", text):
        raise PersonalAssistantInvariantError("skill_id must use dotted lower-case form")
    return text


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if any(fragment in normalized_key for fragment in _RAW_PRIVATE_KEY_FRAGMENTS):
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str) and _contains_secret_like_value(payload):
        raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _request_suffix(request_id: str) -> str:
    return _safe_identifier(request_id.removeprefix("pa_request_"))


def _plan_suffix(plan_id: str) -> str:
    return _safe_identifier(plan_id.removeprefix("pa_plan_"))


def _approval_suffix(approval_id: str) -> str:
    return _safe_identifier(approval_id.removeprefix("pa_approval_"))


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "approval"
