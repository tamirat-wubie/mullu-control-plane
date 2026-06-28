"""Purpose: universal governed event and receipt contracts for capability fabric v2.
Governance scope: surface-neutral event admission, risk-tier decisions, causal
    episode stages, capability passport specs, memory gates, and receipts.
Dependencies: shared contract base helpers and Python standard library hashing.
Invariants:
  - Surface adapters normalize only; they do not authorize execution.
  - External content is evidence only; actor, policy, and authority decide action.
  - Risk tiers fail closed for sensitive, external-obligation, and blocked work.
  - Durable memory requires scope, permission, validation, and auditability.
  - Receipts preserve evidence, blocked actions, verification, and memory result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_unit_float,
)


class FabricRiskClass(StrEnum):
    """Risk tier for the universal capability fabric."""

    CLASS_0_OBSERVE = "class_0_observe"
    CLASS_1_PREPARE = "class_1_prepare"
    CLASS_2_REVERSIBLE = "class_2_reversible"
    CLASS_3_SENSITIVE = "class_3_sensitive"
    CLASS_4_EXTERNAL_OBLIGATION = "class_4_external_obligation"
    CLASS_5_BLOCKED = "class_5_blocked"


class FabricPolicyDecision(StrEnum):
    """Governance decision emitted before capability routing."""

    ALLOW = "allow"
    ALLOW_READ_ONLY = "allow_read_only"
    ALLOW_DRAFT_ONLY = "allow_draft_only"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"
    ESCALATE = "escalate"


class FabricMemoryClass(StrEnum):
    """Allowed memory destination classes."""

    EPHEMERAL = "ephemeral"
    PROJECT = "project"
    USER_PREFERENCE = "user_preference"
    POLICY = "policy"
    RECEIPT = "receipt"
    BLOCKED = "blocked"


class FabricMemoryDecisionStatus(StrEnum):
    """Memory-gate decision status."""

    NOT_REQUIRED = "not_required"
    STORE = "store"
    BLOCK = "block"
    DEFER = "defer"


class FabricSensitivity(StrEnum):
    """Context and memory sensitivity boundary."""

    PUBLIC = "public"
    OPERATIONAL = "operational"
    TENANT_CONFIDENTIAL = "tenant_confidential"
    PERSONAL = "personal"
    FINANCIAL = "financial"
    SECURITY = "security"
    REGULATED = "regulated"


class CausalEpisodeStage(StrEnum):
    """Mandatory causal-chain episode stage order."""

    CAUSE = "cause"
    INTERPRETATION = "interpretation"
    CONSTRAINT = "constraint"
    EVIDENCE = "evidence"
    OPTIONS = "options"
    DECISION = "decision"
    ACTION = "action"
    CONSEQUENCE = "consequence"
    RECEIPT = "receipt"
    MEMORY_GATE = "memory_gate"


CAUSAL_EPISODE_STAGE_ORDER: tuple[CausalEpisodeStage, ...] = (
    CausalEpisodeStage.CAUSE,
    CausalEpisodeStage.INTERPRETATION,
    CausalEpisodeStage.CONSTRAINT,
    CausalEpisodeStage.EVIDENCE,
    CausalEpisodeStage.OPTIONS,
    CausalEpisodeStage.DECISION,
    CausalEpisodeStage.ACTION,
    CausalEpisodeStage.CONSEQUENCE,
    CausalEpisodeStage.RECEIPT,
    CausalEpisodeStage.MEMORY_GATE,
)


def derive_universal_event_idempotency_key(
    *,
    surface: str,
    surface_event_id: str,
    actor_id: str,
    occurred_at: str,
    intent: str,
) -> str:
    """Derive the duplicate-suppression key for one normalized event."""

    payload = {
        "actor_id": require_non_empty_text(actor_id, "actor_id"),
        "intent": require_non_empty_text(intent, "intent"),
        "occurred_at": require_datetime_text(occurred_at, "occurred_at"),
        "surface": require_non_empty_text(surface, "surface"),
        "surface_event_id": require_non_empty_text(surface_event_id, "surface_event_id"),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return f"ueid:{digest}"


def default_policy_decision_for_risk(risk_class: FabricRiskClass) -> FabricPolicyDecision:
    """Return the default governance posture for a fabric risk tier."""

    if risk_class is FabricRiskClass.CLASS_0_OBSERVE:
        return FabricPolicyDecision.ALLOW_READ_ONLY
    if risk_class is FabricRiskClass.CLASS_1_PREPARE:
        return FabricPolicyDecision.ALLOW_DRAFT_ONLY
    if risk_class is FabricRiskClass.CLASS_2_REVERSIBLE:
        return FabricPolicyDecision.ALLOW
    if risk_class in {
        FabricRiskClass.CLASS_3_SENSITIVE,
        FabricRiskClass.CLASS_4_EXTERNAL_OBLIGATION,
    }:
        return FabricPolicyDecision.REQUIRE_APPROVAL
    return FabricPolicyDecision.BLOCK


@dataclass(frozen=True, slots=True)
class UniversalGovernedEvent(ContractRecord):
    """Surface-neutral event emitted before symbolic compilation and UAO."""

    event_id: str
    surface_event_id: str
    actor_id: str
    workspace_id: str
    surface: str
    channel_id: str
    intent: str
    target_object: str
    requested_action: str
    context_refs: tuple[str, ...]
    risk_class: FabricRiskClass
    authority_ref: str
    occurred_at: str
    trace_ref: str
    idempotency_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "surface_event_id",
            "actor_id",
            "workspace_id",
            "surface",
            "intent",
            "target_object",
            "requested_action",
            "authority_ref",
            "trace_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if self.channel_id:
            object.__setattr__(self, "channel_id", require_non_empty_text(self.channel_id, "channel_id"))
        object.__setattr__(self, "context_refs", require_non_empty_tuple(self.context_refs, "context_refs"))
        for index, context_ref in enumerate(self.context_refs):
            require_non_empty_text(context_ref, f"context_refs[{index}]")
        if not isinstance(self.risk_class, FabricRiskClass):
            raise ValueError("risk_class must be a FabricRiskClass value")
        object.__setattr__(self, "occurred_at", require_datetime_text(self.occurred_at, "occurred_at"))
        if self.idempotency_key:
            object.__setattr__(self, "idempotency_key", require_non_empty_text(self.idempotency_key, "idempotency_key"))
        else:
            object.__setattr__(
                self,
                "idempotency_key",
                derive_universal_event_idempotency_key(
                    surface=self.surface,
                    surface_event_id=self.surface_event_id,
                    actor_id=self.actor_id,
                    occurred_at=self.occurred_at,
                    intent=self.intent,
                ),
            )
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "UniversalGovernedEvent":
        return cls(
            event_id=payload["event_id"],
            surface_event_id=payload["surface_event_id"],
            actor_id=payload["actor_id"],
            workspace_id=payload["workspace_id"],
            surface=payload["surface"],
            channel_id=payload.get("channel_id", ""),
            intent=payload["intent"],
            target_object=payload["target_object"],
            requested_action=payload["requested_action"],
            context_refs=tuple(payload["context_refs"]),
            risk_class=FabricRiskClass(payload["risk_class"]),
            authority_ref=payload["authority_ref"],
            occurred_at=payload["occurred_at"],
            trace_ref=payload["trace_ref"],
            idempotency_key=payload.get("idempotency_key", ""),
            metadata=payload.get("metadata", {}),
            extensions=payload.get("extensions", {}),
        )


@dataclass(frozen=True, slots=True)
class FabricContextEvidence(ContractRecord):
    """Context item retrieved for one event; context is evidence, not authority."""

    context_ref: str
    source: str
    permission_scope: str
    sensitivity: FabricSensitivity
    observed_at: str
    confidence: float
    freshness_seconds: int
    trusted_for_authority: bool = False

    def __post_init__(self) -> None:
        for field_name in ("context_ref", "source", "permission_scope"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.sensitivity, FabricSensitivity):
            raise ValueError("sensitivity must be a FabricSensitivity value")
        object.__setattr__(self, "observed_at", require_datetime_text(self.observed_at, "observed_at"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        if not isinstance(self.freshness_seconds, int) or isinstance(self.freshness_seconds, bool) or self.freshness_seconds < 0:
            raise ValueError("freshness_seconds must be a non-negative integer")
        if not isinstance(self.trusted_for_authority, bool):
            raise ValueError("trusted_for_authority must be a boolean")


@dataclass(frozen=True, slots=True)
class SymbolicEventCompilation(ContractRecord):
    """Compiled meaning from a raw normalized event."""

    compilation_id: str
    event_id: str
    interpreted_intent: str
    target_kind: str
    requested_action: str
    blocked_actions: tuple[str, ...]
    evidence_needed: tuple[str, ...]
    assumptions: tuple[str, ...]
    compiled_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "compilation_id",
            "event_id",
            "interpreted_intent",
            "target_kind",
            "requested_action",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in ("blocked_actions", "evidence_needed", "assumptions"):
            object.__setattr__(self, field_name, require_non_empty_tuple(getattr(self, field_name), field_name))
            for index, item in enumerate(getattr(self, field_name)):
                require_non_empty_text(item, f"{field_name}[{index}]")
        object.__setattr__(self, "compiled_at", require_datetime_text(self.compiled_at, "compiled_at"))


@dataclass(frozen=True, slots=True)
class AuthorityResolution(ContractRecord):
    """Actor, workspace, surface, object, and action authority binding."""

    resolution_id: str
    event_id: str
    actor_id: str
    workspace_id: str
    surface: str
    channel_id: str
    target_object: str
    decision: FabricPolicyDecision
    allowed_scope: str
    allowed_actions: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    reason: str
    resolved_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "resolution_id",
            "event_id",
            "actor_id",
            "workspace_id",
            "surface",
            "target_object",
            "allowed_scope",
            "reason",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if self.channel_id:
            object.__setattr__(self, "channel_id", require_non_empty_text(self.channel_id, "channel_id"))
        if not isinstance(self.decision, FabricPolicyDecision):
            raise ValueError("decision must be a FabricPolicyDecision value")
        object.__setattr__(self, "allowed_actions", require_non_empty_tuple(self.allowed_actions, "allowed_actions"))
        object.__setattr__(self, "blocked_actions", freeze_value(tuple(self.blocked_actions)))
        for index, item in enumerate(self.allowed_actions):
            require_non_empty_text(item, f"allowed_actions[{index}]")
        for index, item in enumerate(self.blocked_actions):
            require_non_empty_text(item, f"blocked_actions[{index}]")
        if self.decision in {FabricPolicyDecision.BLOCK, FabricPolicyDecision.REQUIRE_APPROVAL} and not self.blocked_actions:
            raise ValueError("blocked or approval-required decisions must name blocked_actions")
        object.__setattr__(self, "resolved_at", require_datetime_text(self.resolved_at, "resolved_at"))


@dataclass(frozen=True, slots=True)
class RiskPolicyResult(ContractRecord):
    """Risk-tier governance decision before capability routing."""

    policy_result_id: str
    event_id: str
    risk_class: FabricRiskClass
    decision: FabricPolicyDecision
    allowed_tools: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    required_approvals: tuple[str, ...]
    policy_refs: tuple[str, ...]
    reason: str
    decided_at: str

    def __post_init__(self) -> None:
        for field_name in ("policy_result_id", "event_id", "reason"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.risk_class, FabricRiskClass):
            raise ValueError("risk_class must be a FabricRiskClass value")
        if not isinstance(self.decision, FabricPolicyDecision):
            raise ValueError("decision must be a FabricPolicyDecision value")
        expected_decision = default_policy_decision_for_risk(self.risk_class)
        if self.risk_class is FabricRiskClass.CLASS_5_BLOCKED and self.decision is not FabricPolicyDecision.BLOCK:
            raise ValueError("class_5_blocked must block")
        if self.risk_class is FabricRiskClass.CLASS_4_EXTERNAL_OBLIGATION and self.decision not in {
            FabricPolicyDecision.REQUIRE_APPROVAL,
            FabricPolicyDecision.BLOCK,
            FabricPolicyDecision.ESCALATE,
        }:
            raise ValueError("class_4_external_obligation requires approval, block, or escalation")
        if expected_decision is FabricPolicyDecision.BLOCK and not self.blocked_actions:
            raise ValueError("blocked risk decision must name blocked_actions")
        for field_name in ("allowed_tools", "blocked_actions", "required_approvals", "policy_refs"):
            object.__setattr__(self, field_name, freeze_value(tuple(getattr(self, field_name))))
            for index, item in enumerate(getattr(self, field_name)):
                require_non_empty_text(item, f"{field_name}[{index}]")
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class UniversalCapabilityPassport(ContractRecord):
    """Plug-compatible capability declaration; never execution authority alone."""

    passport_id: str
    name: str
    domain: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    required_evidence: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    risk_class: FabricRiskClass
    verification_rules: tuple[str, ...]
    receipt_fields: tuple[str, ...]
    memory_policy: str
    passport_is_not_execution_authority: bool = True

    def __post_init__(self) -> None:
        for field_name in ("passport_id", "name", "domain", "memory_policy"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        for field_name in (
            "inputs",
            "outputs",
            "required_evidence",
            "allowed_tools",
            "blocked_actions",
            "verification_rules",
            "receipt_fields",
        ):
            object.__setattr__(self, field_name, require_non_empty_tuple(getattr(self, field_name), field_name))
            for index, item in enumerate(getattr(self, field_name)):
                require_non_empty_text(item, f"{field_name}[{index}]")
        if not isinstance(self.risk_class, FabricRiskClass):
            raise ValueError("risk_class must be a FabricRiskClass value")
        if self.passport_is_not_execution_authority is not True:
            raise ValueError("passport_is_not_execution_authority must be true")


@dataclass(frozen=True, slots=True)
class CausalEpisodeStep(ContractRecord):
    """One step in the mandatory causal-chain episode."""

    stage: CausalEpisodeStage
    status: str
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.stage, CausalEpisodeStage):
            raise ValueError("stage must be a CausalEpisodeStage value")
        object.__setattr__(self, "status", require_non_empty_text(self.status, "status"))
        object.__setattr__(self, "input_refs", freeze_value(tuple(self.input_refs)))
        object.__setattr__(self, "output_refs", freeze_value(tuple(self.output_refs)))
        for field_name in ("input_refs", "output_refs"):
            for index, item in enumerate(getattr(self, field_name)):
                require_non_empty_text(item, f"{field_name}[{index}]")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class CausalEpisodePlan(ContractRecord):
    """Ordered causal-chain plan for one universal event."""

    episode_id: str
    event_id: str
    capability_id: str
    steps: tuple[CausalEpisodeStep, ...]
    planned_at: str

    def __post_init__(self) -> None:
        for field_name in ("episode_id", "event_id", "capability_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "steps", require_non_empty_tuple(self.steps, "steps"))
        stages = tuple(step.stage for step in self.steps)
        if stages != CAUSAL_EPISODE_STAGE_ORDER:
            raise ValueError("steps must follow the canonical causal episode stage order")
        for step in self.steps:
            if not isinstance(step, CausalEpisodeStep):
                raise ValueError("each step must be a CausalEpisodeStep value")
        object.__setattr__(self, "planned_at", require_datetime_text(self.planned_at, "planned_at"))


@dataclass(frozen=True, slots=True)
class MemoryGateDecision(ContractRecord):
    """Decision for whether episode output can become memory."""

    decision_id: str
    event_id: str
    receipt_id: str
    memory_class: FabricMemoryClass
    status: FabricMemoryDecisionStatus
    scope_ref: str
    validated: bool
    durable: bool
    sensitivity: FabricSensitivity
    reasons: tuple[str, ...]
    decided_at: str
    can_delete: bool = True
    audit_ref: str = ""

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "event_id", "receipt_id", "scope_ref"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.memory_class, FabricMemoryClass):
            raise ValueError("memory_class must be a FabricMemoryClass value")
        if not isinstance(self.status, FabricMemoryDecisionStatus):
            raise ValueError("status must be a FabricMemoryDecisionStatus value")
        if not isinstance(self.sensitivity, FabricSensitivity):
            raise ValueError("sensitivity must be a FabricSensitivity value")
        for field_name in ("validated", "durable", "can_delete"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        object.__setattr__(self, "reasons", require_non_empty_tuple(self.reasons, "reasons"))
        for index, reason in enumerate(self.reasons):
            require_non_empty_text(reason, f"reasons[{index}]")
        if self.durable and not self.validated:
            raise ValueError("durable memory requires validated evidence")
        if self.status is FabricMemoryDecisionStatus.STORE and self.memory_class is FabricMemoryClass.BLOCKED:
            raise ValueError("blocked memory class cannot be stored")
        if self.status is FabricMemoryDecisionStatus.STORE and not self.audit_ref:
            raise ValueError("stored memory requires audit_ref")
        if self.audit_ref:
            object.__setattr__(self, "audit_ref", require_non_empty_text(self.audit_ref, "audit_ref"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class CausalCapabilityReceipt(ContractRecord):
    """Causal proof-of-work receipt for one governed event episode."""

    receipt_id: str
    event_id: str
    actor_id: str
    surface: str
    intent: str
    target_object: str
    risk_class: FabricRiskClass
    evidence_used: tuple[str, ...]
    policy_decision: FabricPolicyDecision
    actions_taken: tuple[str, ...]
    actions_blocked: tuple[str, ...]
    assumptions: tuple[str, ...]
    verification_result: str
    final_judgment: str
    memory_update: FabricMemoryDecisionStatus
    timestamp: str
    partial_failure_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "receipt_id",
            "event_id",
            "actor_id",
            "surface",
            "intent",
            "target_object",
            "verification_result",
            "final_judgment",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.risk_class, FabricRiskClass):
            raise ValueError("risk_class must be a FabricRiskClass value")
        if not isinstance(self.policy_decision, FabricPolicyDecision):
            raise ValueError("policy_decision must be a FabricPolicyDecision value")
        if not isinstance(self.memory_update, FabricMemoryDecisionStatus):
            raise ValueError("memory_update must be a FabricMemoryDecisionStatus value")
        for field_name in (
            "evidence_used",
            "actions_taken",
            "actions_blocked",
            "assumptions",
            "partial_failure_reasons",
        ):
            object.__setattr__(self, field_name, freeze_value(tuple(getattr(self, field_name))))
            for index, item in enumerate(getattr(self, field_name)):
                require_non_empty_text(item, f"{field_name}[{index}]")
        if self.policy_decision is not FabricPolicyDecision.BLOCK and not self.evidence_used:
            raise ValueError("non-blocked receipt requires evidence_used")
        if self.policy_decision is FabricPolicyDecision.BLOCK and not self.actions_blocked:
            raise ValueError("blocked receipt requires actions_blocked")
        if self.risk_class is FabricRiskClass.CLASS_4_EXTERNAL_OBLIGATION and self.policy_decision not in {
            FabricPolicyDecision.REQUIRE_APPROVAL,
            FabricPolicyDecision.BLOCK,
            FabricPolicyDecision.ESCALATE,
        }:
            raise ValueError("external obligation receipt cannot claim direct execution")
        object.__setattr__(self, "timestamp", require_datetime_text(self.timestamp, "timestamp"))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CausalCapabilityReceipt":
        return cls(
            receipt_id=payload["receipt_id"],
            event_id=payload["event_id"],
            actor_id=payload["actor_id"],
            surface=payload["surface"],
            intent=payload["intent"],
            target_object=payload["target_object"],
            risk_class=FabricRiskClass(payload["risk_class"]),
            evidence_used=tuple(payload["evidence_used"]),
            policy_decision=FabricPolicyDecision(payload["policy_decision"]),
            actions_taken=tuple(payload["actions_taken"]),
            actions_blocked=tuple(payload["actions_blocked"]),
            assumptions=tuple(payload["assumptions"]),
            verification_result=payload["verification_result"],
            final_judgment=payload["final_judgment"],
            memory_update=FabricMemoryDecisionStatus(payload["memory_update"]),
            timestamp=payload["timestamp"],
            partial_failure_reasons=tuple(payload.get("partial_failure_reasons", ())),
        )
