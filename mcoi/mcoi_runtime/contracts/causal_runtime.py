"""Purpose: causal / counterfactual runtime contracts.
Governance scope: typed descriptors for causal nodes, edges, interventions,
    counterfactual scenarios, attributions, propagation records, decisions,
    assessments, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
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


class CausalStatus(Enum):
    """Lifecycle status of a causal node."""
    ACTIVE = "active"
    HYPOTHESIZED = "hypothesized"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"


class CausalEdgeKind(Enum):
    """Category of causal edge."""
    DIRECT = "direct"
    INDIRECT = "indirect"
    MEDIATING = "mediating"
    CONFOUNDING = "confounding"
    MODERATING = "moderating"


class InterventionDisposition(Enum):
    """Disposition of an intervention."""
    PROPOSED = "proposed"
    APPLIED = "applied"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"


class CounterfactualStatus(Enum):
    """Status of a counterfactual scenario."""
    PENDING = "pending"
    EVALUATED = "evaluated"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class AttributionStrength(Enum):
    """Strength of a causal attribution."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


class CausalRiskLevel(Enum):
    """Risk level associated with causal operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CausalNode(ContractRecord):
    """A node in the causal graph."""

    node_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: CausalStatus = CausalStatus.ACTIVE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, CausalStatus):
            raise ValueError("status must be a CausalStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CausalEdge(ContractRecord):
    """A directed edge in the causal graph."""

    edge_id: str = ""
    tenant_id: str = ""
    cause_ref: str = ""
    effect_ref: str = ""
    kind: CausalEdgeKind = CausalEdgeKind.DIRECT
    strength: AttributionStrength = AttributionStrength.MODERATE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "cause_ref", require_non_empty_text(self.cause_ref, "cause_ref"))
        object.__setattr__(self, "effect_ref", require_non_empty_text(self.effect_ref, "effect_ref"))
        if not isinstance(self.kind, CausalEdgeKind):
            raise ValueError("kind must be a CausalEdgeKind")
        if not isinstance(self.strength, AttributionStrength):
            raise ValueError("strength must be an AttributionStrength")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InterventionRecord(ContractRecord):
    """An intervention targeting a causal node."""

    intervention_id: str = ""
    tenant_id: str = ""
    target_node_ref: str = ""
    disposition: InterventionDisposition = InterventionDisposition.PROPOSED
    expected_effect: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "intervention_id", require_non_empty_text(self.intervention_id, "intervention_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_node_ref", require_non_empty_text(self.target_node_ref, "target_node_ref"))
        if not isinstance(self.disposition, InterventionDisposition):
            raise ValueError("disposition must be an InterventionDisposition")
        object.__setattr__(self, "expected_effect", require_non_empty_text(self.expected_effect, "expected_effect"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CounterfactualScenario(ContractRecord):
    """A counterfactual scenario based on an intervention."""

    scenario_id: str = ""
    tenant_id: str = ""
    intervention_ref: str = ""
    premise: str = ""
    status: CounterfactualStatus = CounterfactualStatus.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "intervention_ref", require_non_empty_text(self.intervention_ref, "intervention_ref"))
        object.__setattr__(self, "premise", require_non_empty_text(self.premise, "premise"))
        if not isinstance(self.status, CounterfactualStatus):
            raise ValueError("status must be a CounterfactualStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CausalAttribution(ContractRecord):
    """An attribution linking an outcome to a cause."""

    attribution_id: str = ""
    tenant_id: str = ""
    outcome_ref: str = ""
    cause_ref: str = ""
    strength: AttributionStrength = AttributionStrength.MODERATE
    evidence_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attribution_id", require_non_empty_text(self.attribution_id, "attribution_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "outcome_ref", require_non_empty_text(self.outcome_ref, "outcome_ref"))
        object.__setattr__(self, "cause_ref", require_non_empty_text(self.cause_ref, "cause_ref"))
        if not isinstance(self.strength, AttributionStrength):
            raise ValueError("strength must be an AttributionStrength")
        object.__setattr__(self, "evidence_count", require_non_negative_int(self.evidence_count, "evidence_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PropagationRecord(ContractRecord):
    """A propagation trace from source to target through the causal graph."""

    propagation_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    target_ref: str = ""
    hop_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "propagation_id", require_non_empty_text(self.propagation_id, "propagation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        object.__setattr__(self, "hop_count", require_non_negative_int(self.hop_count, "hop_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CausalDecision(ContractRecord):
    """A decision based on causal attribution."""

    decision_id: str = ""
    tenant_id: str = ""
    attribution_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "attribution_ref", require_non_empty_text(self.attribution_ref, "attribution_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CausalAssessment(ContractRecord):
    """Assessment of causal coverage for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_nodes: int = 0
    total_edges: int = 0
    total_interventions: int = 0
    attribution_coverage: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_edges", require_non_negative_int(self.total_edges, "total_edges"))
        object.__setattr__(self, "total_interventions", require_non_negative_int(self.total_interventions, "total_interventions"))
        object.__setattr__(self, "attribution_coverage", require_unit_float(self.attribution_coverage, "attribution_coverage"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CausalSnapshot(ContractRecord):
    """Point-in-time snapshot of causal runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_nodes: int = 0
    total_edges: int = 0
    total_interventions: int = 0
    total_counterfactuals: int = 0
    total_attributions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_edges", require_non_negative_int(self.total_edges, "total_edges"))
        object.__setattr__(self, "total_interventions", require_non_negative_int(self.total_interventions, "total_interventions"))
        object.__setattr__(self, "total_counterfactuals", require_non_negative_int(self.total_counterfactuals, "total_counterfactuals"))
        object.__setattr__(self, "total_attributions", require_non_negative_int(self.total_attributions, "total_attributions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CausalClosureReport(ContractRecord):
    """Final closure report for causal runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_nodes: int = 0
    total_edges: int = 0
    total_interventions: int = 0
    total_attributions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_nodes", require_non_negative_int(self.total_nodes, "total_nodes"))
        object.__setattr__(self, "total_edges", require_non_negative_int(self.total_edges, "total_edges"))
        object.__setattr__(self, "total_interventions", require_non_negative_int(self.total_interventions, "total_interventions"))
        object.__setattr__(self, "total_attributions", require_non_negative_int(self.total_attributions, "total_attributions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
