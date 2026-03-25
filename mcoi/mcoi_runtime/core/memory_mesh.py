"""Purpose: memory mesh engine — durable cumulative intelligence store.
Governance scope: memory record CRUD, linking, promotion, decay, conflict
    detection, metadata node/edge management, and structured retrieval.
Dependencies: memory_mesh contracts, metadata_mesh contracts, core invariants.
Invariants:
  - All mutations are construct-then-commit (atomic append).
  - Public getters return frozen snapshots — callers cannot mutate engine state.
  - IDs are unique per collection; duplicate inserts raise RuntimeCoreInvariantError.
  - Self-referential links/edges are rejected by contract __post_init__.
  - Decay is explicit — no silent expiration.
  - Conflicts are surfaced, never silently resolved.
  - state_hash is deterministic over ordered records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Mapping

from ..contracts.memory_mesh import (
    ConflictResolutionState,
    DecayMode,
    MemoryConflictRecord,
    MemoryDecayPolicy,
    MemoryLink,
    MemoryLinkRelation,
    MemoryPromotionRecord,
    MemoryRecord,
    MemoryRetrievalQuery,
    MemoryRetrievalResult,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from ..contracts.metadata_mesh import (
    MetadataEdge,
    MetadataEdgeRelation,
    MetadataNode,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryMeshEngine:
    """Durable cumulative intelligence store.

    Manages memory records, links, promotions, decay policies, conflicts,
    metadata nodes, and metadata edges. All state lives in-memory with
    deterministic serialization via state_hash.
    """

    def __init__(self) -> None:
        self._memories: dict[str, MemoryRecord] = {}
        self._links: dict[str, MemoryLink] = {}
        self._promotions: dict[str, MemoryPromotionRecord] = {}
        self._decay_policies: dict[str, MemoryDecayPolicy] = {}
        self._conflicts: dict[str, MemoryConflictRecord] = {}
        self._nodes: dict[str, MetadataNode] = {}
        self._edges: dict[str, MetadataEdge] = {}
        self._decay_log: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Memory CRUD
    # ------------------------------------------------------------------

    def add_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Add a memory record. Raises on duplicate ID."""
        if not isinstance(record, MemoryRecord):
            raise RuntimeCoreInvariantError("record must be a MemoryRecord")
        if record.memory_id in self._memories:
            raise RuntimeCoreInvariantError(f"duplicate memory_id: {record.memory_id}")
        self._memories[record.memory_id] = record
        return record

    def get_memory(self, memory_id: str) -> MemoryRecord | None:
        """Return a memory record by ID, or None."""
        return self._memories.get(memory_id)

    def list_memories(
        self,
        *,
        memory_type: MemoryType | None = None,
        scope: MemoryScope | None = None,
        trust_floor: float = 0.0,
    ) -> tuple[MemoryRecord, ...]:
        """Return filtered snapshot of memory records."""
        results: list[MemoryRecord] = []
        for mem in self._memories.values():
            if memory_type is not None and mem.memory_type != memory_type:
                continue
            if scope is not None and mem.scope != scope:
                continue
            if mem.confidence < trust_floor:
                continue
            results.append(mem)
        return tuple(results)

    # ------------------------------------------------------------------
    # Memory linking
    # ------------------------------------------------------------------

    def link_memories(self, link: MemoryLink) -> MemoryLink:
        """Add a link between two memory records. Both must exist."""
        if not isinstance(link, MemoryLink):
            raise RuntimeCoreInvariantError("link must be a MemoryLink")
        if link.from_memory_id not in self._memories:
            raise RuntimeCoreInvariantError(f"from_memory_id not found: {link.from_memory_id}")
        if link.to_memory_id not in self._memories:
            raise RuntimeCoreInvariantError(f"to_memory_id not found: {link.to_memory_id}")
        if link.link_id in self._links:
            raise RuntimeCoreInvariantError(f"duplicate link_id: {link.link_id}")
        self._links[link.link_id] = link
        return link

    def get_links_for(self, memory_id: str) -> tuple[MemoryLink, ...]:
        """Return all links involving a memory record (either direction)."""
        return tuple(
            lnk for lnk in self._links.values()
            if lnk.from_memory_id == memory_id or lnk.to_memory_id == memory_id
        )

    # ------------------------------------------------------------------
    # Memory promotion
    # ------------------------------------------------------------------

    def promote_memory(self, promotion: MemoryPromotionRecord) -> MemoryPromotionRecord:
        """Record a memory type promotion. Memory must exist."""
        if not isinstance(promotion, MemoryPromotionRecord):
            raise RuntimeCoreInvariantError("promotion must be a MemoryPromotionRecord")
        if promotion.memory_id not in self._memories:
            raise RuntimeCoreInvariantError(f"memory_id not found: {promotion.memory_id}")
        if promotion.promotion_id in self._promotions:
            raise RuntimeCoreInvariantError(f"duplicate promotion_id: {promotion.promotion_id}")
        self._promotions[promotion.promotion_id] = promotion
        return promotion

    # ------------------------------------------------------------------
    # Memory decay
    # ------------------------------------------------------------------

    def set_decay_policy(self, policy: MemoryDecayPolicy) -> MemoryDecayPolicy:
        """Register or replace a decay policy for a memory type."""
        if not isinstance(policy, MemoryDecayPolicy):
            raise RuntimeCoreInvariantError("policy must be a MemoryDecayPolicy")
        self._decay_policies[policy.policy_id] = policy
        return policy

    def get_decay_policy(self, policy_id: str) -> MemoryDecayPolicy | None:
        """Return a decay policy by ID, or None."""
        return self._decay_policies.get(policy_id)

    def apply_decay(self) -> tuple[str, ...]:
        """Apply TTL-based decay: remove expired memories. Returns removed IDs.

        Each decayed memory is recorded in ``_decay_log`` before deletion so
        that the operation is auditable.
        """
        now = datetime.now(timezone.utc)
        now_iso = _now_iso()
        expired: list[str] = []
        for mem in list(self._memories.values()):
            if mem.expires_at is not None:
                try:
                    exp_dt = datetime.fromisoformat(mem.expires_at.replace("Z", "+00:00"))
                    if exp_dt <= now:
                        expired.append(mem.memory_id)
                except ValueError:
                    pass
        for mid in expired:
            self._decay_log.append({
                "action": "memory_decay",
                "memory_id": mid,
                "decayed_at": now_iso,
            })
            del self._memories[mid]
        return tuple(expired)

    @property
    def decay_log(self) -> tuple[dict[str, Any], ...]:
        """Return an immutable snapshot of the decay audit log."""
        return tuple(self._decay_log)

    # ------------------------------------------------------------------
    # Memory supersession
    # ------------------------------------------------------------------

    def supersede_memory(
        self,
        old_id: str,
        new_record: MemoryRecord,
    ) -> MemoryRecord:
        """Add new_record and mark it as superseding old_id.

        The old record stays accessible but new_record.supersedes_ids
        must contain old_id (enforced here).
        """
        if old_id not in self._memories:
            raise RuntimeCoreInvariantError(f"old memory_id not found: {old_id}")
        if old_id not in new_record.supersedes_ids:
            raise RuntimeCoreInvariantError(
                f"new_record.supersedes_ids must contain {old_id}"
            )
        return self.add_memory(new_record)

    # ------------------------------------------------------------------
    # Conflict management
    # ------------------------------------------------------------------

    def find_conflicts(
        self,
        memory_id: str,
    ) -> tuple[MemoryConflictRecord, ...]:
        """Return all conflict records involving a memory ID."""
        return tuple(
            c for c in self._conflicts.values()
            if memory_id in c.conflicting_ids
        )

    def record_conflict(self, conflict: MemoryConflictRecord) -> MemoryConflictRecord:
        """Record an explicit conflict between memory records."""
        if not isinstance(conflict, MemoryConflictRecord):
            raise RuntimeCoreInvariantError("conflict must be a MemoryConflictRecord")
        for cid in conflict.conflicting_ids:
            if cid not in self._memories:
                raise RuntimeCoreInvariantError(f"conflicting memory_id not found: {cid}")
        if conflict.conflict_id in self._conflicts:
            raise RuntimeCoreInvariantError(f"duplicate conflict_id: {conflict.conflict_id}")
        self._conflicts[conflict.conflict_id] = conflict
        return conflict

    # ------------------------------------------------------------------
    # Structured retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: MemoryRetrievalQuery) -> MemoryRetrievalResult:
        """Execute a structured memory retrieval query."""
        if not isinstance(query, MemoryRetrievalQuery):
            raise RuntimeCoreInvariantError("query must be a MemoryRetrievalQuery")

        candidates = list(self._memories.values())

        # Filter by scope
        if query.scope is not None:
            candidates = [m for m in candidates if m.scope == query.scope]

        # Filter by scope_ref_id
        if query.scope_ref_id is not None:
            candidates = [m for m in candidates if m.scope_ref_id == query.scope_ref_id]

        # Filter by tags (all query tags must be present)
        if query.tags:
            query_tags = set(query.tags)
            candidates = [m for m in candidates if query_tags.issubset(set(m.tags))]

        # Filter by lineage_ids (memory source_ids must overlap)
        if query.lineage_ids:
            lineage_set = set(query.lineage_ids)
            candidates = [m for m in candidates if lineage_set.intersection(set(m.source_ids))]

        # Filter by trust floor
        if query.trust_floor > 0.0:
            candidates = [m for m in candidates if m.confidence >= query.trust_floor]

        # Filter by memory types
        if query.memory_types:
            type_set = set(query.memory_types)
            candidates = [m for m in candidates if m.memory_type in type_set]

        # Filter by as_of (only records created before as_of)
        if query.as_of is not None:
            try:
                as_of_dt = datetime.fromisoformat(query.as_of.replace("Z", "+00:00"))
                filtered = []
                for m in candidates:
                    try:
                        m_dt = datetime.fromisoformat(m.created_at.replace("Z", "+00:00"))
                        if m_dt <= as_of_dt:
                            filtered.append(m)
                    except ValueError:
                        pass
                candidates = filtered
            except ValueError:
                pass

        # Sort by confidence descending for deterministic ordering
        candidates.sort(key=lambda m: (-m.confidence, m.memory_id))

        total = len(candidates)
        matched = candidates[: query.max_results]

        return MemoryRetrievalResult(
            query_id=query.query_id,
            matched_ids=tuple(m.memory_id for m in matched),
            total=total,
            retrieved_at=_now_iso(),
        )

    # ------------------------------------------------------------------
    # Metadata nodes and edges
    # ------------------------------------------------------------------

    def add_metadata_node(self, node: MetadataNode) -> MetadataNode:
        """Add a metadata node. Raises on duplicate ID."""
        if not isinstance(node, MetadataNode):
            raise RuntimeCoreInvariantError("node must be a MetadataNode")
        if node.node_id in self._nodes:
            raise RuntimeCoreInvariantError(f"duplicate node_id: {node.node_id}")
        self._nodes[node.node_id] = node
        return node

    def get_metadata_node(self, node_id: str) -> MetadataNode | None:
        """Return a metadata node by ID, or None."""
        return self._nodes.get(node_id)

    def add_metadata_edge(self, edge: MetadataEdge) -> MetadataEdge:
        """Add a metadata edge. Both nodes must exist."""
        if not isinstance(edge, MetadataEdge):
            raise RuntimeCoreInvariantError("edge must be a MetadataEdge")
        if edge.from_node_id not in self._nodes:
            raise RuntimeCoreInvariantError(f"from_node_id not found: {edge.from_node_id}")
        if edge.to_node_id not in self._nodes:
            raise RuntimeCoreInvariantError(f"to_node_id not found: {edge.to_node_id}")
        if edge.edge_id in self._edges:
            raise RuntimeCoreInvariantError(f"duplicate edge_id: {edge.edge_id}")
        self._edges[edge.edge_id] = edge
        return edge

    def get_edges_for(self, node_id: str) -> tuple[MetadataEdge, ...]:
        """Return all edges involving a node (either direction)."""
        return tuple(
            e for e in self._edges.values()
            if e.from_node_id == node_id or e.to_node_id == node_id
        )

    # ------------------------------------------------------------------
    # Counts and state hash
    # ------------------------------------------------------------------

    @property
    def memory_count(self) -> int:
        return len(self._memories)

    @property
    def link_count(self) -> int:
        return len(self._links)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def promotion_count(self) -> int:
        return len(self._promotions)

    @property
    def conflict_count(self) -> int:
        return len(self._conflicts)

    def state_hash(self) -> str:
        """Deterministic hash over all ordered records."""
        parts: list[str] = []
        for mid in sorted(self._memories):
            parts.append(f"mem:{mid}")
        for lid in sorted(self._links):
            parts.append(f"lnk:{lid}")
        for pid in sorted(self._promotions):
            parts.append(f"prm:{pid}")
        for cid in sorted(self._conflicts):
            parts.append(f"cfl:{cid}")
        for nid in sorted(self._nodes):
            parts.append(f"nod:{nid}")
        for eid in sorted(self._edges):
            parts.append(f"edg:{eid}")
        for entry in self._decay_log:
            parts.append(f"decay:{entry['memory_id']}")
        payload = "|".join(parts)
        return sha256(payload.encode()).hexdigest()
