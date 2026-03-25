"""Purpose: canonical metadata mesh contracts for typed facet overlays.
Governance scope: metadata node, edge, facet typing, provenance, ownership,
    policy binding, confidence, expiry, and semantic tagging.
Dependencies: shared contract base helpers.
Invariants:
  - Every metadata node references exactly one domain entity (ref_id).
  - Edges are typed and weighted — no untyped associations.
  - Facets are immutable once attached — update by superseding.
  - Confidence facets are bounded [0.0, 1.0].
  - Expiry facets carry explicit ISO 8601 timestamps.
  - Self-referential edges are prohibited.
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
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MetadataFacetType(StrEnum):
    """Classification of metadata facets attached to nodes."""

    PROVENANCE = "provenance"
    OWNERSHIP = "ownership"
    POLICY = "policy"
    CONFIDENCE = "confidence"
    EXPIRY = "expiry"
    SEMANTIC = "semantic"
    COMMUNICATION = "communication"
    DOMAIN = "domain"
    LINEAGE = "lineage"


class MetadataEdgeRelation(StrEnum):
    """Typed relationship between two metadata nodes."""

    DERIVED_FROM = "derived_from"
    OWNED_BY = "owned_by"
    GOVERNED_BY = "governed_by"
    RELATED_TO = "related_to"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"
    ANNOTATES = "annotates"


# ---------------------------------------------------------------------------
# Typed facets
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProvenanceFacet(ContractRecord):
    """Tracks origin and transformation history of a metadata node."""

    source_system: str
    source_id: str
    ingested_at: str
    transform_chain: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_system", require_non_empty_text(self.source_system, "source_system"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        object.__setattr__(self, "ingested_at", require_datetime_text(self.ingested_at, "ingested_at"))
        object.__setattr__(self, "transform_chain", freeze_value(list(self.transform_chain)))


@dataclass(frozen=True, slots=True)
class OwnershipFacet(ContractRecord):
    """Declares who owns or is responsible for a metadata node."""

    owner_id: str
    owner_type: str
    assigned_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", require_non_empty_text(self.owner_id, "owner_id"))
        object.__setattr__(self, "owner_type", require_non_empty_text(self.owner_type, "owner_type"))
        object.__setattr__(self, "assigned_at", require_datetime_text(self.assigned_at, "assigned_at"))


@dataclass(frozen=True, slots=True)
class PolicyFacet(ContractRecord):
    """Links a metadata node to the governance policy that controls it."""

    policy_id: str
    rule_ids: tuple[str, ...]
    effect: str
    bound_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "rule_ids", freeze_value(list(self.rule_ids)))
        for rid in self.rule_ids:
            require_non_empty_text(rid, "rule_id")
        object.__setattr__(self, "effect", require_non_empty_text(self.effect, "effect"))
        object.__setattr__(self, "bound_at", require_datetime_text(self.bound_at, "bound_at"))


@dataclass(frozen=True, slots=True)
class ConfidenceFacet(ContractRecord):
    """Attaches a bounded confidence score to a metadata node."""

    confidence: float
    source: str
    assessed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "source", require_non_empty_text(self.source, "source"))
        object.__setattr__(self, "assessed_at", require_datetime_text(self.assessed_at, "assessed_at"))


@dataclass(frozen=True, slots=True)
class ExpiryFacet(ContractRecord):
    """Declares when a metadata node expires or must be re-evaluated."""

    expires_at: str
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class SemanticFacet(ContractRecord):
    """Attaches semantic tags and domain classification to a metadata node."""

    tags: tuple[str, ...]
    domain: str
    category: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        object.__setattr__(self, "domain", require_non_empty_text(self.domain, "domain"))
        object.__setattr__(self, "category", require_non_empty_text(self.category, "category"))


# ---------------------------------------------------------------------------
# Metadata nodes and edges
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetadataNode(ContractRecord):
    """A typed metadata node referencing a domain entity.

    Each node carries zero or more typed facets providing provenance,
    ownership, policy, confidence, expiry, and semantic information.
    """

    node_id: str
    node_type: str
    ref_id: str
    facets: Mapping[str, Any]
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "node_type", require_non_empty_text(self.node_type, "node_type"))
        object.__setattr__(self, "ref_id", require_non_empty_text(self.ref_id, "ref_id"))
        if not isinstance(self.facets, Mapping):
            raise ValueError("facets must be a mapping")
        object.__setattr__(self, "facets", freeze_value(self.facets))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class MetadataEdge(ContractRecord):
    """A typed, weighted edge between two metadata nodes."""

    edge_id: str
    from_node_id: str
    to_node_id: str
    relation: MetadataEdgeRelation
    weight: float = 1.0
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(self, "from_node_id", require_non_empty_text(self.from_node_id, "from_node_id"))
        object.__setattr__(self, "to_node_id", require_non_empty_text(self.to_node_id, "to_node_id"))
        if self.from_node_id == self.to_node_id:
            raise ValueError("self-referential metadata edges are prohibited")
        if not isinstance(self.relation, MetadataEdgeRelation):
            raise ValueError("relation must be a MetadataEdgeRelation value")
        object.__setattr__(self, "weight", require_unit_float(self.weight, "weight"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
