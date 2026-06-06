"""Purpose: Universal Evidence Graph contract for evidence-bearing causal meshes.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, and PRS evidence graph typing.
Dependencies: shared contract base helpers and Python standard library enums.
Invariants: graph nodes and edges are explicit, evidence-backed, cross-referenced, and deterministic.
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
    require_non_empty_tuple,
    require_unit_float,
)


class UniversalEvidenceGraphNodeKind(StrEnum):
    """Evidence-bearing source classes that can participate in the universal mesh."""

    NOTE = "note"
    MEMORY = "memory"
    RECEIPT = "receipt"
    TRACE = "trace"
    POLICY = "policy"
    CLAIM = "claim"
    CAPABILITY = "capability"
    DEPLOYMENT = "deployment"
    ORGOS_CASE = "orgos_case"
    SKILL = "skill"


class UniversalEvidenceGraphEdgeKind(StrEnum):
    """Directed evidence relation between two graph nodes."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    GOVERNED_BY = "governed_by"
    VERIFIED_BY = "verified_by"
    PRODUCED_BY = "produced_by"
    DEPENDS_ON = "depends_on"
    ANSWERS = "answers"


class UniversalEvidenceQuestionKind(StrEnum):
    """Question classes the graph can answer without external interpretation."""

    WHY = "why"
    HOW = "how"
    WHAT_SUPPORTS = "what_supports"
    WHAT_CONTRADICTS = "what_contradicts"


@dataclass(frozen=True, slots=True)
class UniversalEvidenceGraphNode(ContractRecord):
    """A typed evidence-bearing node with explicit source and supporting evidence refs."""

    node_id: str
    node_kind: UniversalEvidenceGraphNodeKind
    label: str
    source_ref: str
    evidence_refs: tuple[str, ...]
    confidence: float
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        if not isinstance(self.node_kind, UniversalEvidenceGraphNodeKind):
            raise ValueError("node_kind must be a UniversalEvidenceGraphNodeKind value")
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniversalEvidenceGraphEdge(ContractRecord):
    """A typed directed edge whose relation is backed by at least one evidence ref."""

    edge_id: str
    edge_kind: UniversalEvidenceGraphEdgeKind
    source_node_id: str
    target_node_id: str
    evidence_refs: tuple[str, ...]
    confidence: float
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        if not isinstance(self.edge_kind, UniversalEvidenceGraphEdgeKind):
            raise ValueError("edge_kind must be a UniversalEvidenceGraphEdgeKind value")
        object.__setattr__(self, "source_node_id", require_non_empty_text(self.source_node_id, "source_node_id"))
        object.__setattr__(self, "target_node_id", require_non_empty_text(self.target_node_id, "target_node_id"))
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniversalEvidenceQuestionAnswer(ContractRecord):
    """A precomputed graph answer binding a question to answer nodes and edges."""

    question_id: str
    question_kind: UniversalEvidenceQuestionKind
    target_node_id: str
    answer_node_ids: tuple[str, ...]
    answer_edge_ids: tuple[str, ...]
    confidence: float
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "question_id", require_non_empty_text(self.question_id, "question_id"))
        if not isinstance(self.question_kind, UniversalEvidenceQuestionKind):
            raise ValueError("question_kind must be a UniversalEvidenceQuestionKind value")
        object.__setattr__(self, "target_node_id", require_non_empty_text(self.target_node_id, "target_node_id"))
        object.__setattr__(self, "answer_node_ids", _require_text_tuple(self.answer_node_ids, "answer_node_ids"))
        object.__setattr__(self, "answer_edge_ids", _require_text_tuple(self.answer_edge_ids, "answer_edge_ids"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class UniversalEvidenceGraph(ContractRecord):
    """A portable evidence graph snapshot with explicit closure question indexes."""

    graph_id: str
    version: str
    generated_at: str
    nodes: tuple[UniversalEvidenceGraphNode, ...]
    edges: tuple[UniversalEvidenceGraphEdge, ...]
    questions: tuple[UniversalEvidenceQuestionAnswer, ...]
    receipt_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "graph_id", require_non_empty_text(self.graph_id, "graph_id"))
        object.__setattr__(self, "version", require_non_empty_text(self.version, "version"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))
        object.__setattr__(self, "nodes", _require_record_tuple(self.nodes, UniversalEvidenceGraphNode, "nodes"))
        object.__setattr__(self, "edges", _require_record_tuple(self.edges, UniversalEvidenceGraphEdge, "edges"))
        object.__setattr__(
            self,
            "questions",
            _require_record_tuple(self.questions, UniversalEvidenceQuestionAnswer, "questions"),
        )
        object.__setattr__(self, "receipt_refs", _require_text_tuple(self.receipt_refs, "receipt_refs"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        _validate_graph_references(self.nodes, self.edges, self.questions)


def _require_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    items = require_non_empty_tuple(values, field_name)
    for item in items:
        require_non_empty_text(item, f"{field_name} element")
    if len(set(items)) != len(items):
        raise ValueError(f"{field_name} must not contain duplicates")
    return tuple(items)


def _require_record_tuple(values: tuple[Any, ...], record_type: type[Any], field_name: str) -> tuple[Any, ...]:
    items = require_non_empty_tuple(values, field_name)
    for item in items:
        if not isinstance(item, record_type):
            raise ValueError(f"{field_name} must contain {record_type.__name__} records")
    return tuple(items)


def _validate_graph_references(
    nodes: tuple[UniversalEvidenceGraphNode, ...],
    edges: tuple[UniversalEvidenceGraphEdge, ...],
    questions: tuple[UniversalEvidenceQuestionAnswer, ...],
) -> None:
    node_ids = [node.node_id for node in nodes]
    edge_ids = [edge.edge_id for edge in edges]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("nodes must not contain duplicate node_id values")
    if len(set(edge_ids)) != len(edge_ids):
        raise ValueError("edges must not contain duplicate edge_id values")

    node_id_set = set(node_ids)
    edge_id_set = set(edge_ids)
    for edge in edges:
        if edge.source_node_id not in node_id_set:
            raise ValueError("edges must reference existing source_node_id values")
        if edge.target_node_id not in node_id_set:
            raise ValueError("edges must reference existing target_node_id values")

    question_ids = [question.question_id for question in questions]
    if len(set(question_ids)) != len(question_ids):
        raise ValueError("questions must not contain duplicate question_id values")
    for question in questions:
        if question.target_node_id not in node_id_set:
            raise ValueError("questions must reference existing target_node_id values")
        if not set(question.answer_node_ids).issubset(node_id_set):
            raise ValueError("questions must reference existing answer_node_ids values")
        if not set(question.answer_edge_ids).issubset(edge_id_set):
            raise ValueError("questions must reference existing answer_edge_ids values")
