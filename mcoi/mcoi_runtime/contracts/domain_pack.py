"""Purpose: canonical domain-pack contracts.
Governance scope: domain pack descriptors, vocabulary, extraction/routing/memory/
    simulation/utility/benchmark/escalation rules and profiles, activation,
    resolution, and conflicts.
Dependencies: shared contract base helpers.
Invariants:
  - Every domain pack has explicit status, scope, and version.
  - Only ACTIVE packs participate in resolution.
  - Rules/profiles always reference their parent pack_id.
  - Higher-specificity scope beats lower-specificity scope.
  - Version conflicts surfaced explicitly.
  - All fields validated at construction time.
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
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DomainPackStatus(StrEnum):
    """Lifecycle status of a domain pack."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class DomainRuleKind(StrEnum):
    """What aspect of the runtime this rule/profile targets."""

    EXTRACTION = "extraction"
    ROUTING = "routing"
    MEMORY = "memory"
    SIMULATION = "simulation"
    UTILITY = "utility"
    GOVERNANCE = "governance"
    BENCHMARK = "benchmark"
    ESCALATION = "escalation"
    IDENTITY = "identity"
    INGESTION = "ingestion"


class PackScope(StrEnum):
    """Scope at which a domain pack applies."""

    GLOBAL = "global"
    DOMAIN = "domain"
    FUNCTION = "function"
    TEAM = "team"
    WORKFLOW = "workflow"
    GOAL = "goal"


# Scope specificity order: higher index = more specific = higher priority
_SCOPE_SPECIFICITY: dict[PackScope, int] = {
    PackScope.GLOBAL: 0,
    PackScope.DOMAIN: 1,
    PackScope.FUNCTION: 2,
    PackScope.TEAM: 3,
    PackScope.WORKFLOW: 4,
    PackScope.GOAL: 5,
}


def scope_specificity(scope: PackScope) -> int:
    """Return the specificity rank for a scope (higher = more specific)."""
    return _SCOPE_SPECIFICITY[scope]


# ---------------------------------------------------------------------------
# DomainPackDescriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainPackDescriptor(ContractRecord):
    """Describes a domain pack and its metadata."""

    pack_id: str = ""
    domain_name: str = ""
    version: str = ""
    status: DomainPackStatus = DomainPackStatus.DRAFT
    scope: PackScope = PackScope.GLOBAL
    scope_ref_id: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.pack_id, "pack_id")
        require_non_empty_text(self.domain_name, "domain_name")
        require_non_empty_text(self.version, "version")
        if not isinstance(self.status, DomainPackStatus):
            raise ValueError(f"status must be DomainPackStatus, got {type(self.status)}")
        if not isinstance(self.scope, PackScope):
            raise ValueError(f"scope must be PackScope, got {type(self.scope)}")
        require_datetime_text(self.created_at, "created_at")
        if self.updated_at:
            require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainVocabularyEntry
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainVocabularyEntry(ContractRecord):
    """A domain-specific term and its canonical meaning."""

    entry_id: str = ""
    pack_id: str = ""
    term: str = ""
    canonical_form: str = ""
    aliases: tuple[str, ...] = ()
    rule_kind: DomainRuleKind = DomainRuleKind.EXTRACTION
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.entry_id, "entry_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_non_empty_text(self.term, "term")
        require_non_empty_text(self.canonical_form, "canonical_form")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "aliases", tuple(self.aliases))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainExtractionRule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainExtractionRule(ContractRecord):
    """Domain-specific extraction pattern."""

    rule_id: str = ""
    pack_id: str = ""
    pattern: str = ""
    commitment_type: str = ""
    priority: int = 0
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.rule_id, "rule_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_non_empty_text(self.pattern, "pattern")
        require_non_empty_text(self.commitment_type, "commitment_type")
        require_non_negative_int(self.priority, "priority")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainRoutingRule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainRoutingRule(ContractRecord):
    """Domain-specific routing configuration."""

    rule_id: str = ""
    pack_id: str = ""
    source_role: str = ""
    target_role: str = ""
    channel_type: str = ""
    priority: int = 0
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.rule_id, "rule_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_non_empty_text(self.target_role, "target_role")
        require_non_negative_int(self.priority, "priority")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainMemoryRule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainMemoryRule(ContractRecord):
    """Domain-specific memory management configuration."""

    rule_id: str = ""
    pack_id: str = ""
    memory_type: str = ""
    trust_level: str = ""
    decay_mode: str = ""
    ttl_seconds: int = 0
    promotion_eligible: bool = True
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.rule_id, "rule_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_non_empty_text(self.memory_type, "memory_type")
        require_non_negative_int(self.ttl_seconds, "ttl_seconds")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainSimulationProfile
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainSimulationProfile(ContractRecord):
    """Domain-specific simulation risk weights and parameters."""

    profile_id: str = ""
    pack_id: str = ""
    risk_weights: Mapping[str, float] = field(default_factory=dict)
    default_risk_level: str = "medium"
    scenario_templates: tuple[str, ...] = ()
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.profile_id, "profile_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "risk_weights", freeze_value(self.risk_weights))
        object.__setattr__(self, "scenario_templates", tuple(self.scenario_templates))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainUtilityProfile
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainUtilityProfile(ContractRecord):
    """Domain-specific utility tradeoff defaults."""

    profile_id: str = ""
    pack_id: str = ""
    bias_weights: Mapping[str, float] = field(default_factory=dict)
    default_tradeoff_direction: str = "balanced"
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.profile_id, "profile_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "bias_weights", freeze_value(self.bias_weights))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainBenchmarkProfile
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainBenchmarkProfile(ContractRecord):
    """Domain-specific benchmark suite selection and thresholds."""

    profile_id: str = ""
    pack_id: str = ""
    suite_ids: tuple[str, ...] = ()
    adversarial_categories: tuple[str, ...] = ()
    pass_thresholds: Mapping[str, float] = field(default_factory=dict)
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.profile_id, "profile_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "suite_ids", tuple(self.suite_ids))
        object.__setattr__(self, "adversarial_categories", tuple(self.adversarial_categories))
        object.__setattr__(self, "pass_thresholds", freeze_value(self.pass_thresholds))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainEscalationProfile
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainEscalationProfile(ContractRecord):
    """Domain-specific escalation chain configuration."""

    profile_id: str = ""
    pack_id: str = ""
    escalation_roles: tuple[str, ...] = ()
    escalation_mode: str = "sequential"
    timeout_seconds: int = 300
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.profile_id, "profile_id")
        require_non_empty_text(self.pack_id, "pack_id")
        if not self.escalation_roles:
            raise ValueError("escalation_roles must have at least one role")
        require_non_negative_int(self.timeout_seconds, "timeout_seconds")
        if self.timeout_seconds == 0:
            raise ValueError("timeout_seconds must be positive")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "escalation_roles", tuple(self.escalation_roles))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainPackActivation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainPackActivation(ContractRecord):
    """Records when a domain pack was activated or deactivated."""

    activation_id: str = ""
    pack_id: str = ""
    previous_status: DomainPackStatus = DomainPackStatus.DRAFT
    new_status: DomainPackStatus = DomainPackStatus.ACTIVE
    activated_at: str = ""
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.activation_id, "activation_id")
        require_non_empty_text(self.pack_id, "pack_id")
        require_datetime_text(self.activated_at, "activated_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainPackResolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainPackResolution(ContractRecord):
    """Result of resolving which domain packs apply to a given scope."""

    resolution_id: str = ""
    scope: PackScope = PackScope.GLOBAL
    scope_ref_id: str = ""
    resolved_pack_ids: tuple[str, ...] = ()
    rule_kind: DomainRuleKind = DomainRuleKind.EXTRACTION
    conflict_ids: tuple[str, ...] = ()
    resolved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.resolution_id, "resolution_id")
        require_datetime_text(self.resolved_at, "resolved_at")
        object.__setattr__(self, "resolved_pack_ids", tuple(self.resolved_pack_ids))
        object.__setattr__(self, "conflict_ids", tuple(self.conflict_ids))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# DomainPackConflict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomainPackConflict(ContractRecord):
    """Records a detected conflict between two domain packs."""

    conflict_id: str = ""
    pack_id_a: str = ""
    pack_id_b: str = ""
    rule_kind: DomainRuleKind = DomainRuleKind.EXTRACTION
    scope: PackScope = PackScope.GLOBAL
    description: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.conflict_id, "conflict_id")
        require_non_empty_text(self.pack_id_a, "pack_id_a")
        require_non_empty_text(self.pack_id_b, "pack_id_b")
        if self.pack_id_a == self.pack_id_b:
            raise ValueError("pack_id_a and pack_id_b must be different")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
