"""Purpose: canonical operational graph runtime contracts.
Governance scope: node, edge, evidence, decision, obligation, state-delta, causal-path, snapshot, and query-result typing.
Dependencies: docs/31_operational_graph.md, shared contract base helpers.
Invariants:
  - Every node carries explicit type, identity, and creation timestamp.
  - Every edge carries explicit type, source, target, and creation timestamp.
  - Edges are append-only; no edge deletion or mutation.
  - No edge without both source and target nodes existing.
  - No backdating edges.
  - Confidence values are bounded [0.0, 1.0].
  - Obligation fulfillment is explicitly tracked.
  - Causal paths contain at least one node and one edge.
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
    require_unit_float,
    require_non_empty_tuple,
)


# --- Classification enums ---


class NodeType(StrEnum):
    """Classification of nodes in the operational graph."""

    GOAL = "goal"
    WORKFLOW = "workflow"
    SKILL = "skill"
    JOB = "job"
    INCIDENT = "incident"
    APPROVAL = "approval"
    REVIEW = "review"
    RUNBOOK = "runbook"
    PROVIDER_ACTION = "provider_action"
    VERIFICATION = "verification"
    COMMUNICATION_THREAD = "communication_thread"
    DOCUMENT = "document"
    FUNCTION = "function"
    PERSON = "person"
    TEAM = "team"


class EdgeType(StrEnum):
    """Classification of edges in the operational graph."""

    CAUSED_BY = "caused_by"
    DEPENDS_ON = "depends_on"
    OWNS = "owns"
    OBLIGATED_TO = "obligated_to"
    DECIDED_BY = "decided_by"
    BLOCKED_BY = "blocked_by"
    ESCALATED_TO = "escalated_to"
    PRODUCED = "produced"
    VERIFIED_BY = "verified_by"
    ASSIGNED_TO = "assigned_to"
    COMMUNICATES_VIA = "communicates_via"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class OperationalNode(ContractRecord):
    """A typed node in the operational graph."""

    node_id: str
    node_type: NodeType
    label: str
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        if not isinstance(self.node_type, NodeType):
            raise ValueError("node_type must be a NodeType value")
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OperationalEdge(ContractRecord):
    """A typed, directed edge in the operational graph."""

    edge_id: str
    edge_type: EdgeType
    source_node_id: str
    target_node_id: str
    label: str
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        if not isinstance(self.edge_type, EdgeType):
            raise ValueError("edge_type must be an EdgeType value")
        object.__setattr__(self, "source_node_id", require_non_empty_text(self.source_node_id, "source_node_id"))
        object.__setattr__(self, "target_node_id", require_non_empty_text(self.target_node_id, "target_node_id"))
        object.__setattr__(self, "label", require_non_empty_text(self.label, "label"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceLink(ContractRecord):
    """An edge annotated with evidence type and confidence score."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    evidence_type: str
    confidence: float
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(self, "source_node_id", require_non_empty_text(self.source_node_id, "source_node_id"))
        object.__setattr__(self, "target_node_id", require_non_empty_text(self.target_node_id, "target_node_id"))
        object.__setattr__(self, "evidence_type", require_non_empty_text(self.evidence_type, "evidence_type"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class DecisionLink(ContractRecord):
    """An edge recording a decision and who made it."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    decision: str
    decided_by_id: str
    created_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(self, "source_node_id", require_non_empty_text(self.source_node_id, "source_node_id"))
        object.__setattr__(self, "target_node_id", require_non_empty_text(self.target_node_id, "target_node_id"))
        object.__setattr__(self, "decision", require_non_empty_text(self.decision, "decision"))
        object.__setattr__(self, "decided_by_id", require_non_empty_text(self.decided_by_id, "decided_by_id"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class ObligationLink(ContractRecord):
    """An edge recording a formal obligation with optional deadline and fulfillment tracking."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    obligation: str
    fulfilled: bool
    created_at: str
    deadline: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "edge_id", require_non_empty_text(self.edge_id, "edge_id"))
        object.__setattr__(self, "source_node_id", require_non_empty_text(self.source_node_id, "source_node_id"))
        object.__setattr__(self, "target_node_id", require_non_empty_text(self.target_node_id, "target_node_id"))
        object.__setattr__(self, "obligation", require_non_empty_text(self.obligation, "obligation"))
        if not isinstance(self.fulfilled, bool):
            raise ValueError("fulfilled must be a boolean")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        if self.deadline is not None:
            object.__setattr__(self, "deadline", require_datetime_text(self.deadline, "deadline"))


@dataclass(frozen=True, slots=True)
class StateDelta(ContractRecord):
    """A single field-level change on a node, supporting append-only audit."""

    delta_id: str
    node_id: str
    field_name: str
    old_value: str
    new_value: str
    changed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "delta_id", require_non_empty_text(self.delta_id, "delta_id"))
        object.__setattr__(self, "node_id", require_non_empty_text(self.node_id, "node_id"))
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        if not isinstance(self.old_value, str):
            raise ValueError("old_value must be a string")
        if not isinstance(self.new_value, str):
            raise ValueError("new_value must be a string")
        object.__setattr__(self, "changed_at", require_datetime_text(self.changed_at, "changed_at"))


@dataclass(frozen=True, slots=True)
class CausalPath(ContractRecord):
    """An ordered path of nodes and edges tracing causation through the graph."""

    path_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    description: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", require_non_empty_text(self.path_id, "path_id"))
        object.__setattr__(self, "node_ids", require_non_empty_tuple(self.node_ids, "node_ids"))
        object.__setattr__(self, "edge_ids", require_non_empty_tuple(self.edge_ids, "edge_ids"))
        for nid in self.node_ids:
            require_non_empty_text(nid, "node_ids element")
        for eid in self.edge_ids:
            require_non_empty_text(eid, "edge_ids element")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class GraphSnapshot(ContractRecord):
    """A point-in-time summary of graph size for replay and audit."""

    snapshot_id: str
    node_count: int
    edge_count: int
    captured_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        if not isinstance(self.node_count, int) or self.node_count < 0:
            raise ValueError("node_count must be a non-negative integer")
        if not isinstance(self.edge_count, int) or self.edge_count < 0:
            raise ValueError("edge_count must be a non-negative integer")
        object.__setattr__(self, "captured_at", require_datetime_text(self.captured_at, "captured_at"))


@dataclass(frozen=True, slots=True)
class GraphQueryResult(ContractRecord):
    """The result of a graph traversal or filter query."""

    query_id: str
    matched_nodes: tuple[OperationalNode, ...]
    matched_edges: tuple[OperationalEdge, ...]
    executed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "query_id", require_non_empty_text(self.query_id, "query_id"))
        if not isinstance(self.matched_nodes, tuple):
            object.__setattr__(self, "matched_nodes", tuple(self.matched_nodes))
        if not isinstance(self.matched_edges, tuple):
            object.__setattr__(self, "matched_edges", tuple(self.matched_edges))
        for node in self.matched_nodes:
            if not isinstance(node, OperationalNode):
                raise ValueError("matched_nodes must contain OperationalNode instances")
        for edge in self.matched_edges:
            if not isinstance(edge, OperationalEdge):
                raise ValueError("matched_edges must contain OperationalEdge instances")
        object.__setattr__(self, "executed_at", require_datetime_text(self.executed_at, "executed_at"))
