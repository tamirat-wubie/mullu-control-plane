"""Purpose: operational graph core engine — causal, evidence, decision, and obligation links.
Governance scope: graph construction, traversal, causal path finding, obligation lifecycle.
Dependencies: graph contracts, invariant helpers.
Invariants:
  - Append-only: no node or edge deletion.
  - Both source and target nodes must exist before adding any edge.
  - Clock function is injected for determinism.
  - Confidence values are clamped to [0.0, 1.0].
  - Fulfilled obligations produce a new frozen record (original is immutable).
  - BFS traversals respect directed edge semantics.
"""

from __future__ import annotations

from collections import deque
from typing import Callable, Union

from mcoi_runtime.contracts.graph import (
    CausalPath,
    DecisionLink,
    EdgeType,
    EvidenceLink,
    GraphQueryResult,
    GraphSnapshot,
    NodeType,
    ObligationLink,
    OperationalEdge,
    OperationalNode,
    StateDelta,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


# Union of all edge types stored in the graph
AnyEdge = Union[OperationalEdge, EvidenceLink, DecisionLink, ObligationLink]

# Edge types that represent causal relationships for path-finding
_CAUSAL_EDGE_TYPES: frozenset[EdgeType] = frozenset({
    EdgeType.CAUSED_BY,
    EdgeType.PRODUCED,
    EdgeType.DEPENDS_ON,
})


def _edge_type_of(edge: AnyEdge) -> EdgeType:
    """Extract the EdgeType from any edge variant."""
    if isinstance(edge, OperationalEdge):
        return edge.edge_type
    if isinstance(edge, EvidenceLink):
        return EdgeType.VERIFIED_BY
    if isinstance(edge, DecisionLink):
        return EdgeType.DECIDED_BY
    if isinstance(edge, ObligationLink):
        return EdgeType.OBLIGATED_TO
    raise RuntimeCoreInvariantError("unknown edge type")


def _edge_source(edge: AnyEdge) -> str:
    return edge.source_node_id


def _edge_target(edge: AnyEdge) -> str:
    return edge.target_node_id


class OperationalGraph:
    """In-memory append-only operational graph with typed nodes and edges.

    All timestamps are produced by the injected clock function for determinism.
    Nodes and edges can be added but never removed.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._nodes: dict[str, OperationalNode] = {}
        self._edges: dict[str, AnyEdge] = {}
        self._outgoing: dict[str, list[str]] = {}  # node_id -> [edge_id, ...]
        self._incoming: dict[str, list[str]] = {}  # node_id -> [edge_id, ...]
        self._deltas: list[StateDelta] = []

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: NodeType,
        label: str,
    ) -> OperationalNode:
        """Add a node to the graph. Rejects duplicate node_ids."""
        ensure_non_empty_text("node_id", node_id)
        ensure_non_empty_text("label", label)
        if node_id in self._nodes:
            raise RuntimeCoreInvariantError("duplicate node")
        now = self._clock()
        node = OperationalNode(
            node_id=node_id,
            node_type=node_type,
            label=label,
            created_at=now,
        )
        self._nodes[node_id] = node
        self._outgoing.setdefault(node_id, [])
        self._incoming.setdefault(node_id, [])
        return node

    def get_node(self, node_id: str) -> OperationalNode | None:
        """Return a node by ID or None if not found."""
        return self._nodes.get(node_id)

    def query_by_type(self, node_type: NodeType) -> tuple[OperationalNode, ...]:
        """Return all nodes matching the given type."""
        return tuple(n for n in self._nodes.values() if n.node_type == node_type)

    # ------------------------------------------------------------------
    # Edge helpers
    # ------------------------------------------------------------------

    def _validate_endpoints(self, source_id: str, target_id: str) -> None:
        """Ensure both endpoint nodes exist and no self-loop."""
        if source_id == target_id:
            raise RuntimeCoreInvariantError("self-loop not permitted")
        if source_id not in self._nodes:
            raise RuntimeCoreInvariantError("source node not found")
        if target_id not in self._nodes:
            raise RuntimeCoreInvariantError("target node not found")

    def _register_edge(self, edge_id: str, source_id: str, target_id: str, edge: AnyEdge) -> None:
        """Insert an edge into the internal indexes."""
        self._edges[edge_id] = edge
        self._outgoing[source_id].append(edge_id)
        self._incoming[target_id].append(edge_id)

    # ------------------------------------------------------------------
    # Generic edge
    # ------------------------------------------------------------------

    def add_edge(
        self,
        edge_type: EdgeType,
        source_id: str,
        target_id: str,
        label: str = "",
    ) -> OperationalEdge:
        """Add a directed edge between two existing nodes."""
        self._validate_endpoints(source_id, target_id)
        if not label:
            label = edge_type.value
        now = self._clock()
        edge_id = stable_identifier("edge", {
            "source": source_id,
            "target": target_id,
            "type": edge_type.value,
            "created_at": now,
        })
        edge = OperationalEdge(
            edge_id=edge_id,
            edge_type=edge_type,
            source_node_id=source_id,
            target_node_id=target_id,
            label=label,
            created_at=now,
        )
        self._register_edge(edge_id, source_id, target_id, edge)
        return edge

    # ------------------------------------------------------------------
    # Evidence link
    # ------------------------------------------------------------------

    def add_evidence_link(
        self,
        source_id: str,
        target_id: str,
        evidence_type: str,
        confidence: float,
    ) -> EvidenceLink:
        """Add an evidence link with a confidence score clamped to [0.0, 1.0]."""
        self._validate_endpoints(source_id, target_id)
        ensure_non_empty_text("evidence_type", evidence_type)
        confidence = max(0.0, min(1.0, float(confidence)))
        now = self._clock()
        edge_id = stable_identifier("evidence", {
            "source": source_id,
            "target": target_id,
            "type": evidence_type,
            "created_at": now,
        })
        link = EvidenceLink(
            edge_id=edge_id,
            source_node_id=source_id,
            target_node_id=target_id,
            evidence_type=evidence_type,
            confidence=confidence,
            created_at=now,
        )
        self._register_edge(edge_id, source_id, target_id, link)
        return link

    # ------------------------------------------------------------------
    # Decision link
    # ------------------------------------------------------------------

    def add_decision_link(
        self,
        source_id: str,
        target_id: str,
        decision: str,
        decided_by_id: str,
    ) -> DecisionLink:
        """Add a decision link between two nodes."""
        self._validate_endpoints(source_id, target_id)
        ensure_non_empty_text("decision", decision)
        ensure_non_empty_text("decided_by_id", decided_by_id)
        now = self._clock()
        edge_id = stable_identifier("decision", {
            "source": source_id,
            "target": target_id,
            "decision": decision,
            "created_at": now,
        })
        link = DecisionLink(
            edge_id=edge_id,
            source_node_id=source_id,
            target_node_id=target_id,
            decision=decision,
            decided_by_id=decided_by_id,
            created_at=now,
        )
        self._register_edge(edge_id, source_id, target_id, link)
        return link

    # ------------------------------------------------------------------
    # Obligation link
    # ------------------------------------------------------------------

    def add_obligation(
        self,
        source_id: str,
        target_id: str,
        obligation: str,
        deadline: str | None = None,
    ) -> ObligationLink:
        """Add an obligation link between two nodes."""
        self._validate_endpoints(source_id, target_id)
        ensure_non_empty_text("obligation", obligation)
        now = self._clock()
        edge_id = stable_identifier("obligation", {
            "source": source_id,
            "target": target_id,
            "obligation": obligation,
            "created_at": now,
        })
        link = ObligationLink(
            edge_id=edge_id,
            source_node_id=source_id,
            target_node_id=target_id,
            obligation=obligation,
            deadline=deadline,
            fulfilled=False,
            created_at=now,
        )
        self._register_edge(edge_id, source_id, target_id, link)
        return link

    def fulfill_obligation(self, edge_id: str) -> ObligationLink:
        """Mark an obligation as fulfilled. Returns a new frozen record."""
        ensure_non_empty_text("edge_id", edge_id)
        edge = self._edges.get(edge_id)
        if edge is None:
            raise RuntimeCoreInvariantError("edge not found")
        if not isinstance(edge, ObligationLink):
            raise RuntimeCoreInvariantError("edge is not an obligation")
        if edge.fulfilled:
            raise RuntimeCoreInvariantError("obligation already fulfilled")
        fulfilled = ObligationLink(
            edge_id=edge.edge_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            obligation=edge.obligation,
            deadline=edge.deadline,
            fulfilled=True,
            created_at=edge.created_at,
        )
        self._edges[edge_id] = fulfilled
        return fulfilled

    def find_obligations(
        self,
        node_id: str,
        fulfilled: bool | None = None,
    ) -> tuple[ObligationLink, ...]:
        """Find obligations where node_id is source or target.

        If fulfilled is None, returns all obligations involving the node.
        """
        results: list[ObligationLink] = []
        candidate_ids = set(
            self._outgoing.get(node_id, []) + self._incoming.get(node_id, [])
        )
        for eid in candidate_ids:
            edge = self._edges.get(eid)
            if isinstance(edge, ObligationLink):
                if fulfilled is None or edge.fulfilled == fulfilled:
                    results.append(edge)
        return tuple(results)

    # ------------------------------------------------------------------
    # State deltas
    # ------------------------------------------------------------------

    def record_state_delta(
        self,
        node_id: str,
        field_name: str,
        old_value: str,
        new_value: str,
    ) -> StateDelta:
        """Record a field-level change on a node. Values must be strings."""
        if node_id not in self._nodes:
            raise RuntimeCoreInvariantError("node not found")
        ensure_non_empty_text("field_name", field_name)
        now = self._clock()
        delta_id = stable_identifier("delta", {
            "node_id": node_id,
            "field": field_name,
            "changed_at": now,
        })
        delta = StateDelta(
            delta_id=delta_id,
            node_id=node_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            changed_at=now,
        )
        self._deltas.append(delta)
        return delta

    # ------------------------------------------------------------------
    # Edge queries
    # ------------------------------------------------------------------

    def get_outgoing_edges(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> tuple[AnyEdge, ...]:
        """Return outgoing edges from a node, optionally filtered by type."""
        edge_ids = self._outgoing.get(node_id, [])
        edges = [self._edges[eid] for eid in edge_ids if eid in self._edges]
        if edge_type is not None:
            edges = [e for e in edges if _edge_type_of(e) == edge_type]
        return tuple(edges)

    def get_incoming_edges(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> tuple[AnyEdge, ...]:
        """Return incoming edges to a node, optionally filtered by type."""
        edge_ids = self._incoming.get(node_id, [])
        edges = [self._edges[eid] for eid in edge_ids if eid in self._edges]
        if edge_type is not None:
            edges = [e for e in edges if _edge_type_of(e) == edge_type]
        return tuple(edges)

    def get_neighbors(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> tuple[str, ...]:
        """Return IDs of nodes reachable via outgoing edges from node_id."""
        outgoing = self.get_outgoing_edges(node_id, edge_type)
        return tuple(_edge_target(e) for e in outgoing)

    # ------------------------------------------------------------------
    # Causal path finding (BFS through causal edges)
    # ------------------------------------------------------------------

    def find_causal_path(
        self,
        from_node_id: str,
        to_node_id: str,
    ) -> CausalPath | None:
        """Find a directed path from from_node_id to to_node_id through causal edges.

        Causal edges are: caused_by, produced, depends_on.
        Returns None if no path exists or if from == to (a causal path requires edges).
        Uses BFS for shortest path.
        """
        if from_node_id not in self._nodes or to_node_id not in self._nodes:
            return None
        if from_node_id == to_node_id:
            return None  # CausalPath contract requires non-empty edge_ids

        # BFS: queue items are (current_node, path_of_node_ids, path_of_edge_ids)
        queue: deque[tuple[str, list[str], list[str]]] = deque()
        queue.append((from_node_id, [from_node_id], []))
        visited: set[str] = {from_node_id}

        while queue:
            current, node_path, edge_path = queue.popleft()
            for eid in self._outgoing.get(current, []):
                edge = self._edges.get(eid)
                if edge is None:
                    continue
                if not isinstance(edge, OperationalEdge):
                    continue
                if edge.edge_type not in _CAUSAL_EDGE_TYPES:
                    continue
                neighbor = edge.target_node_id
                if neighbor in visited:
                    continue
                new_node_path = node_path + [neighbor]
                new_edge_path = edge_path + [eid]
                if neighbor == to_node_id:
                    path_id = stable_identifier("causal-path", {
                        "from": from_node_id,
                        "to": to_node_id,
                    })
                    return CausalPath(
                        path_id=path_id,
                        node_ids=tuple(new_node_path),
                        edge_ids=tuple(new_edge_path),
                        description="causal path located",
                    )
                visited.add(neighbor)
                queue.append((neighbor, new_node_path, new_edge_path))

        return None

    # ------------------------------------------------------------------
    # Connected subgraph query (BFS up to max_depth)
    # ------------------------------------------------------------------

    def query_connected(
        self,
        node_id: str,
        max_depth: int = 3,
    ) -> GraphQueryResult:
        """BFS from node_id up to max_depth hops, following all outgoing edges.

        Returns all reached nodes and traversed edges.
        """
        if node_id not in self._nodes:
            raise RuntimeCoreInvariantError("node not found")

        reached_nodes: list[OperationalNode] = [self._nodes[node_id]]
        traversed_edges: list[OperationalEdge] = []
        visited: set[str] = {node_id}
        queue: deque[tuple[str, int]] = deque()
        queue.append((node_id, 0))

        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for eid in self._outgoing.get(current, []):
                edge = self._edges.get(eid)
                if edge is None:
                    continue
                # Only include OperationalEdge in matched_edges for type safety
                if isinstance(edge, OperationalEdge):
                    traversed_edges.append(edge)
                neighbor = _edge_target(edge)
                if neighbor not in visited:
                    visited.add(neighbor)
                    reached_nodes.append(self._nodes[neighbor])
                    queue.append((neighbor, depth + 1))

        now = self._clock()
        query_id = stable_identifier("query", {
            "origin": node_id,
            "max_depth": str(max_depth),
            "executed_at": now,
        })
        return GraphQueryResult(
            query_id=query_id,
            matched_nodes=tuple(reached_nodes),
            matched_edges=tuple(traversed_edges),
            executed_at=now,
        )

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def capture_snapshot(self) -> GraphSnapshot:
        """Capture a point-in-time summary of the graph."""
        now = self._clock()
        snapshot_id = stable_identifier("snapshot", {"captured_at": now})
        return GraphSnapshot(
            snapshot_id=snapshot_id,
            node_count=len(self._nodes),
            edge_count=len(self._edges),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Ensure-node (idempotent add)
    # ------------------------------------------------------------------

    def ensure_node(
        self,
        node_id: str,
        node_type: NodeType,
        label: str | None = None,
    ) -> OperationalNode:
        """Return existing node or create it. Validates type match if exists."""
        existing = self._nodes.get(node_id)
        if existing is not None:
            if existing.node_type != node_type:
                raise RuntimeCoreInvariantError("node already exists with different type")
            return existing
        return self.add_node(node_id, node_type, label or node_id)

    # ------------------------------------------------------------------
    # Bulk accessors (used by view models)
    # ------------------------------------------------------------------

    def all_nodes(self) -> tuple[OperationalNode, ...]:
        """Return all nodes in insertion order."""
        return tuple(self._nodes.values())

    def all_edges(self) -> tuple[AnyEdge, ...]:
        """Return all edges in insertion order."""
        return tuple(self._edges.values())

    def all_obligations(self) -> tuple[ObligationLink, ...]:
        """Return all obligation links."""
        return tuple(e for e in self._edges.values() if isinstance(e, ObligationLink))
