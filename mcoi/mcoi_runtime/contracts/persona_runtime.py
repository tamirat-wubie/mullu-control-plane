"""Purpose: persona / role / behavioral style runtime contracts.
Governance scope: typed descriptors for agent persona profiles, role behavior
    policies, style directives, escalation directives, session bindings,
    decisions, assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - RETIRED personas cannot be reactivated.
  - Authority mode gates decision disposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PersonaStatus(Enum):
    """Lifecycle status of an agent persona."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class PersonaKind(Enum):
    """Category of agent persona."""
    EXECUTIVE = "executive"
    OPERATOR = "operator"
    INVESTIGATOR = "investigator"
    CUSTOMER_SUPPORT = "customer_support"
    REGULATORY = "regulatory"
    TECHNICAL = "technical"


class InteractionStyle(Enum):
    """Style of interaction for a persona."""
    CONCISE = "concise"
    DETAILED = "detailed"
    FORMAL = "formal"
    CONVERSATIONAL = "conversational"


class EscalationStyle(Enum):
    """How a persona escalates issues."""
    IMMEDIATE = "immediate"
    THRESHOLD = "threshold"
    DEFERRED = "deferred"
    MANUAL = "manual"


class AuthorityMode(Enum):
    """Authority level for persona decisions."""
    AUTONOMOUS = "autonomous"
    GUIDED = "guided"
    RESTRICTED = "restricted"
    READ_ONLY = "read_only"


class PersonaRiskLevel(Enum):
    """Risk level associated with a persona."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PersonaProfile(ContractRecord):
    """An agent persona profile."""

    persona_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: PersonaKind = PersonaKind.OPERATOR
    status: PersonaStatus = PersonaStatus.ACTIVE
    interaction_style: InteractionStyle = InteractionStyle.CONCISE
    authority_mode: AuthorityMode = AuthorityMode.GUIDED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "persona_id", require_non_empty_text(self.persona_id, "persona_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, PersonaKind):
            raise ValueError("kind must be a PersonaKind")
        if not isinstance(self.status, PersonaStatus):
            raise ValueError("status must be a PersonaStatus")
        if not isinstance(self.interaction_style, InteractionStyle):
            raise ValueError("interaction_style must be an InteractionStyle")
        if not isinstance(self.authority_mode, AuthorityMode):
            raise ValueError("authority_mode must be an AuthorityMode")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RoleBehaviorPolicy(ContractRecord):
    """A behavior policy governing a persona's role."""

    policy_id: str = ""
    tenant_id: str = ""
    persona_ref: str = ""
    escalation_style: EscalationStyle = EscalationStyle.THRESHOLD
    risk_level: PersonaRiskLevel = PersonaRiskLevel.LOW
    max_autonomy_depth: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "persona_ref", require_non_empty_text(self.persona_ref, "persona_ref"))
        if not isinstance(self.escalation_style, EscalationStyle):
            raise ValueError("escalation_style must be an EscalationStyle")
        if not isinstance(self.risk_level, PersonaRiskLevel):
            raise ValueError("risk_level must be a PersonaRiskLevel")
        object.__setattr__(self, "max_autonomy_depth", require_non_negative_int(self.max_autonomy_depth, "max_autonomy_depth"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StyleDirective(ContractRecord):
    """A style directive for a persona within a scope."""

    directive_id: str = ""
    tenant_id: str = ""
    persona_ref: str = ""
    scope: str = ""
    instruction: str = ""
    priority: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "directive_id", require_non_empty_text(self.directive_id, "directive_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "persona_ref", require_non_empty_text(self.persona_ref, "persona_ref"))
        object.__setattr__(self, "scope", require_non_empty_text(self.scope, "scope"))
        object.__setattr__(self, "instruction", require_non_empty_text(self.instruction, "instruction"))
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EscalationDirective(ContractRecord):
    """An escalation directive for a persona."""

    directive_id: str = ""
    tenant_id: str = ""
    persona_ref: str = ""
    trigger_condition: str = ""
    target_role: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "directive_id", require_non_empty_text(self.directive_id, "directive_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "persona_ref", require_non_empty_text(self.persona_ref, "persona_ref"))
        object.__setattr__(self, "trigger_condition", require_non_empty_text(self.trigger_condition, "trigger_condition"))
        object.__setattr__(self, "target_role", require_non_empty_text(self.target_role, "target_role"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonaSessionBinding(ContractRecord):
    """A binding between a persona and a session."""

    binding_id: str = ""
    tenant_id: str = ""
    persona_ref: str = ""
    session_ref: str = ""
    bound_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "persona_ref", require_non_empty_text(self.persona_ref, "persona_ref"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        require_datetime_text(self.bound_at, "bound_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonaDecision(ContractRecord):
    """A decision made under a persona's authority."""

    decision_id: str = ""
    tenant_id: str = ""
    persona_ref: str = ""
    session_ref: str = ""
    action_taken: str = ""
    style_applied: InteractionStyle = InteractionStyle.CONCISE
    authority_used: AuthorityMode = AuthorityMode.GUIDED
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "persona_ref", require_non_empty_text(self.persona_ref, "persona_ref"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "action_taken", require_non_empty_text(self.action_taken, "action_taken"))
        if not isinstance(self.style_applied, InteractionStyle):
            raise ValueError("style_applied must be an InteractionStyle")
        if not isinstance(self.authority_used, AuthorityMode):
            raise ValueError("authority_used must be an AuthorityMode")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonaAssessment(ContractRecord):
    """Assessment of persona effectiveness for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_personas: int = 0
    total_bindings: int = 0
    total_decisions: int = 0
    compliance_rate: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_personas", require_non_negative_int(self.total_personas, "total_personas"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "compliance_rate", require_unit_float(self.compliance_rate, "compliance_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonaViolation(ContractRecord):
    """A violation detected in the persona lifecycle."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonaSnapshot(ContractRecord):
    """Point-in-time snapshot of persona runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_personas: int = 0
    total_policies: int = 0
    total_bindings: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_personas", require_non_negative_int(self.total_personas, "total_personas"))
        object.__setattr__(self, "total_policies", require_non_negative_int(self.total_policies, "total_policies"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PersonaClosureReport(ContractRecord):
    """Final closure report for persona runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_personas: int = 0
    total_policies: int = 0
    total_bindings: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_personas", require_non_negative_int(self.total_personas, "total_personas"))
        object.__setattr__(self, "total_policies", require_non_negative_int(self.total_policies, "total_policies"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
