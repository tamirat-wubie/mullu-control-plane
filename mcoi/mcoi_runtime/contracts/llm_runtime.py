"""Purpose: LLM / model runtime contracts.
Governance scope: typed descriptors for models, providers, prompts, context
    packs, generation requests/results, tool permissions, grounding evidence,
    safety assessments, and runtime snapshots.
Dependencies: _base contract utilities.
Invariants:
  - LLMs are non-authoritative execution substrates.
  - Every generation references a tenant.
  - All outputs are frozen and traceable.
  - Budget enforcement is mandatory.
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
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ModelStatus(Enum):
    """Status of a registered model."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    RETIRED = "retired"


class ProviderStatus(Enum):
    """Status of a provider route."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    SUSPENDED = "suspended"


class PromptDisposition(Enum):
    """Disposition of a prompt template."""
    APPROVED = "approved"
    DRAFT = "draft"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class GroundingStatus(Enum):
    """Grounding verification status."""
    GROUNDED = "grounded"
    PARTIALLY_GROUNDED = "partially_grounded"
    UNGROUNDED = "ungrounded"
    NOT_CHECKED = "not_checked"


class SafetyVerdict(Enum):
    """Safety assessment verdict."""
    SAFE = "safe"
    FLAGGED = "flagged"
    BLOCKED = "blocked"
    REQUIRES_REVIEW = "requires_review"


class GenerationStatus(Enum):
    """Status of a generation request."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    TIMED_OUT = "timed_out"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelDescriptor(ContractRecord):
    """A registered LLM model."""

    model_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    provider_ref: str = ""
    status: ModelStatus = ModelStatus.ACTIVE
    max_tokens: int = 0
    cost_per_token: float = 0.0
    registered_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "provider_ref", require_non_empty_text(self.provider_ref, "provider_ref"))
        if not isinstance(self.status, ModelStatus):
            raise ValueError("status must be a ModelStatus")
        object.__setattr__(self, "max_tokens", require_non_negative_int(self.max_tokens, "max_tokens"))
        object.__setattr__(self, "cost_per_token", require_non_negative_float(self.cost_per_token, "cost_per_token"))
        require_datetime_text(self.registered_at, "registered_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProviderRoute(ContractRecord):
    """A provider routing entry for model fallback chains."""

    route_id: str = ""
    tenant_id: str = ""
    provider_ref: str = ""
    model_id: str = ""
    priority: int = 0
    status: ProviderStatus = ProviderStatus.AVAILABLE
    latency_budget_ms: int = 0
    cost_budget: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "route_id", require_non_empty_text(self.route_id, "route_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "provider_ref", require_non_empty_text(self.provider_ref, "provider_ref"))
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "priority", require_non_negative_int(self.priority, "priority"))
        if not isinstance(self.status, ProviderStatus):
            raise ValueError("status must be a ProviderStatus")
        object.__setattr__(self, "latency_budget_ms", require_non_negative_int(self.latency_budget_ms, "latency_budget_ms"))
        object.__setattr__(self, "cost_budget", require_non_negative_float(self.cost_budget, "cost_budget"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PromptTemplate(ContractRecord):
    """A registered prompt template."""

    template_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    template_text: str = ""
    disposition: PromptDisposition = PromptDisposition.DRAFT
    version: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "template_id", require_non_empty_text(self.template_id, "template_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "template_text", require_non_empty_text(self.template_text, "template_text"))
        if not isinstance(self.disposition, PromptDisposition):
            raise ValueError("disposition must be a PromptDisposition")
        object.__setattr__(self, "version", require_non_negative_int(self.version, "version"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContextPack(ContractRecord):
    """An assembled context pack for a generation request."""

    pack_id: str = ""
    tenant_id: str = ""
    template_id: str = ""
    model_id: str = ""
    token_count: int = 0
    source_count: int = 0
    assembled_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pack_id", require_non_empty_text(self.pack_id, "pack_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "template_id", require_non_empty_text(self.template_id, "template_id"))
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "token_count", require_non_negative_int(self.token_count, "token_count"))
        object.__setattr__(self, "source_count", require_non_negative_int(self.source_count, "source_count"))
        require_datetime_text(self.assembled_at, "assembled_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GenerationRequest(ContractRecord):
    """A request to generate output from an LLM."""

    request_id: str = ""
    tenant_id: str = ""
    model_id: str = ""
    pack_id: str = ""
    status: GenerationStatus = GenerationStatus.PENDING
    token_budget: int = 0
    cost_budget: float = 0.0
    latency_budget_ms: int = 0
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "pack_id", require_non_empty_text(self.pack_id, "pack_id"))
        if not isinstance(self.status, GenerationStatus):
            raise ValueError("status must be a GenerationStatus")
        object.__setattr__(self, "token_budget", require_non_negative_int(self.token_budget, "token_budget"))
        object.__setattr__(self, "cost_budget", require_non_negative_float(self.cost_budget, "cost_budget"))
        object.__setattr__(self, "latency_budget_ms", require_non_negative_int(self.latency_budget_ms, "latency_budget_ms"))
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GenerationResult(ContractRecord):
    """The result of a generation request."""

    result_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    model_id: str = ""
    status: GenerationStatus = GenerationStatus.COMPLETED
    tokens_used: int = 0
    cost_incurred: float = 0.0
    latency_ms: float = 0.0
    output_ref: str = ""
    grounding_status: GroundingStatus = GroundingStatus.NOT_CHECKED
    safety_verdict: SafetyVerdict = SafetyVerdict.SAFE
    confidence: float = 0.0
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        if not isinstance(self.status, GenerationStatus):
            raise ValueError("status must be a GenerationStatus")
        object.__setattr__(self, "tokens_used", require_non_negative_int(self.tokens_used, "tokens_used"))
        object.__setattr__(self, "cost_incurred", require_non_negative_float(self.cost_incurred, "cost_incurred"))
        object.__setattr__(self, "latency_ms", require_non_negative_float(self.latency_ms, "latency_ms"))
        object.__setattr__(self, "output_ref", require_non_empty_text(self.output_ref, "output_ref"))
        if not isinstance(self.grounding_status, GroundingStatus):
            raise ValueError("grounding_status must be a GroundingStatus")
        if not isinstance(self.safety_verdict, SafetyVerdict):
            raise ValueError("safety_verdict must be a SafetyVerdict")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ToolPermission(ContractRecord):
    """A tool permission scope for LLM tool use."""

    permission_id: str = ""
    tenant_id: str = ""
    model_id: str = ""
    tool_ref: str = ""
    allowed: bool = True
    scope_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "permission_id", require_non_empty_text(self.permission_id, "permission_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "tool_ref", require_non_empty_text(self.tool_ref, "tool_ref"))
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a bool")
        object.__setattr__(self, "scope_ref", require_non_empty_text(self.scope_ref, "scope_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GroundingEvidence(ContractRecord):
    """Evidence used to ground a generation result."""

    evidence_id: str = ""
    result_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    relevance_score: float = 0.0
    grounding_status: GroundingStatus = GroundingStatus.GROUNDED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", require_non_empty_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "relevance_score", require_unit_float(self.relevance_score, "relevance_score"))
        if not isinstance(self.grounding_status, GroundingStatus):
            raise ValueError("grounding_status must be a GroundingStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SafetyAssessment(ContractRecord):
    """Safety assessment for a generation result."""

    assessment_id: str = ""
    result_id: str = ""
    tenant_id: str = ""
    verdict: SafetyVerdict = SafetyVerdict.SAFE
    reason: str = ""
    confidence: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.verdict, SafetyVerdict):
            raise ValueError("verdict must be a SafetyVerdict")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LlmRuntimeSnapshot(ContractRecord):
    """Point-in-time snapshot of LLM runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_routes: int = 0
    total_templates: int = 0
    total_requests: int = 0
    total_results: int = 0
    total_permissions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_routes", require_non_negative_int(self.total_routes, "total_routes"))
        object.__setattr__(self, "total_templates", require_non_negative_int(self.total_templates, "total_templates"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_permissions", require_non_negative_int(self.total_permissions, "total_permissions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LlmAssessment(ContractRecord):
    """Assessment of LLM runtime health for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_routes: int = 0
    total_requests: int = 0
    total_results: int = 0
    total_violations: int = 0
    completion_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_routes", require_non_negative_int(self.total_routes, "total_routes"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "completion_rate", require_unit_float(self.completion_rate, "completion_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LlmClosureReport(ContractRecord):
    """Closure report for LLM runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_routes: int = 0
    total_requests: int = 0
    total_results: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_routes", require_non_negative_int(self.total_routes, "total_routes"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
