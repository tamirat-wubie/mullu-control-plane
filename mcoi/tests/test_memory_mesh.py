"""Engine-level tests for MemoryMeshEngine."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.memory_mesh import (
    ConflictResolutionState,
    DecayMode,
    MemoryConflictRecord,
    MemoryDecayPolicy,
    MemoryLink,
    MemoryLinkRelation,
    MemoryPromotionRecord,
    MemoryRecord,
    MemoryRetrievalQuery,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.contracts.metadata_mesh import (
    MetadataEdge,
    MetadataEdgeRelation,
    MetadataNode,
)
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"
LATER = "2026-03-21T12:00:00+00:00"
PAST = "2020-01-01T00:00:00+00:00"


def _mem(mid: str = "mem-1", **overrides) -> MemoryRecord:
    defaults = dict(
        memory_id=mid,
        memory_type=MemoryType.EPISODIC,
        scope=MemoryScope.GOAL,
        scope_ref_id="goal-1",
        trust_level=MemoryTrustLevel.VERIFIED,
        title="Test",
        content={"k": "v"},
        source_ids=("src-1",),
        confidence=0.8,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return MemoryRecord(**defaults)


def _node(nid: str = "node-1", **overrides) -> MetadataNode:
    defaults = dict(
        node_id=nid,
        node_type="memory",
        ref_id="ref-1",
        facets={},
        created_at=NOW,
    )
    defaults.update(overrides)
    return MetadataNode(**defaults)


class TestMemoryMeshEngine:
    def test_empty_engine(self):
        e = MemoryMeshEngine()
        assert e.memory_count == 0
        assert e.link_count == 0
        assert e.node_count == 0
        assert e.edge_count == 0

    # -- add / get / list memory --

    def test_add_and_get(self):
        e = MemoryMeshEngine()
        rec = e.add_memory(_mem("m1"))
        assert rec.memory_id == "m1"
        assert e.get_memory("m1") is rec
        assert e.memory_count == 1

    def test_get_missing_returns_none(self):
        e = MemoryMeshEngine()
        assert e.get_memory("nope") is None

    def test_duplicate_id_rejected(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            e.add_memory(_mem("m1"))

    def test_non_record_rejected(self):
        e = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            e.add_memory("not a record")

    def test_list_all(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        assert len(e.list_memories()) == 2

    def test_list_filter_by_type(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", memory_type=MemoryType.EPISODIC))
        e.add_memory(_mem("m2", memory_type=MemoryType.STRATEGIC))
        result = e.list_memories(memory_type=MemoryType.STRATEGIC)
        assert len(result) == 1
        assert result[0].memory_id == "m2"

    def test_list_filter_by_scope(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", scope=MemoryScope.GOAL))
        e.add_memory(_mem("m2", scope=MemoryScope.WORKFLOW))
        result = e.list_memories(scope=MemoryScope.WORKFLOW)
        assert len(result) == 1

    def test_list_filter_by_trust_floor(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", confidence=0.3))
        e.add_memory(_mem("m2", confidence=0.9))
        result = e.list_memories(trust_floor=0.5)
        assert len(result) == 1
        assert result[0].memory_id == "m2"

    # -- linking --

    def test_link_memories(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        lnk = MemoryLink(
            link_id="lnk-1",
            from_memory_id="m1",
            to_memory_id="m2",
            relation=MemoryLinkRelation.SUPPORTS,
            created_at=NOW,
        )
        result = e.link_memories(lnk)
        assert result.link_id == "lnk-1"
        assert e.link_count == 1

    def test_link_missing_from_rejected(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m2"))
        lnk = MemoryLink(
            link_id="lnk-1",
            from_memory_id="m1",
            to_memory_id="m2",
            relation=MemoryLinkRelation.SUPPORTS,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="from_memory_id"):
            e.link_memories(lnk)

    def test_link_missing_to_rejected(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        lnk = MemoryLink(
            link_id="lnk-1",
            from_memory_id="m1",
            to_memory_id="m2",
            relation=MemoryLinkRelation.SUPPORTS,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="to_memory_id"):
            e.link_memories(lnk)

    def test_duplicate_link_rejected(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        lnk = MemoryLink(
            link_id="lnk-1",
            from_memory_id="m1",
            to_memory_id="m2",
            relation=MemoryLinkRelation.SUPPORTS,
            created_at=NOW,
        )
        e.link_memories(lnk)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            e.link_memories(lnk)

    def test_get_links_for(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        e.add_memory(_mem("m3"))
        e.link_memories(MemoryLink(
            link_id="lnk-1", from_memory_id="m1", to_memory_id="m2",
            relation=MemoryLinkRelation.SUPPORTS, created_at=NOW,
        ))
        e.link_memories(MemoryLink(
            link_id="lnk-2", from_memory_id="m3", to_memory_id="m1",
            relation=MemoryLinkRelation.CAUSED_BY, created_at=NOW,
        ))
        links = e.get_links_for("m1")
        assert len(links) == 2

    # -- promotion --

    def test_promote_memory(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        prm = MemoryPromotionRecord(
            promotion_id="prm-1",
            memory_id="m1",
            from_type=MemoryType.EPISODIC,
            to_type=MemoryType.PROCEDURAL,
            rationale="Repeated pattern",
            supporting_ids=("m1",),
            confidence=0.9,
            promoted_at=NOW,
        )
        result = e.promote_memory(prm)
        assert result.promotion_id == "prm-1"
        assert e.promotion_count == 1

    def test_promote_missing_memory_rejected(self):
        e = MemoryMeshEngine()
        prm = MemoryPromotionRecord(
            promotion_id="prm-1",
            memory_id="m-nope",
            from_type=MemoryType.EPISODIC,
            to_type=MemoryType.PROCEDURAL,
            rationale="test",
            supporting_ids=(),
            confidence=0.9,
            promoted_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            e.promote_memory(prm)

    # -- decay --

    def test_set_and_get_decay_policy(self):
        e = MemoryMeshEngine()
        pol = MemoryDecayPolicy(
            policy_id="dp-1",
            memory_type=MemoryType.WORKING,
            decay_mode=DecayMode.TTL,
            ttl_seconds=60,
            created_at=NOW,
        )
        e.set_decay_policy(pol)
        assert e.get_decay_policy("dp-1") is pol

    def test_apply_decay_removes_expired(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", expires_at=PAST))
        e.add_memory(_mem("m2"))
        removed = e.apply_decay()
        assert "m1" in removed
        assert e.memory_count == 1
        # Decay log is populated for auditing
        assert len(e.decay_log) == 1
        assert e.decay_log[0]["action"] == "memory_decay"
        assert e.decay_log[0]["memory_id"] == "m1"
        assert "decayed_at" in e.decay_log[0]

    def test_apply_decay_keeps_unexpired(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", expires_at="2099-01-01T00:00:00+00:00"))
        removed = e.apply_decay()
        assert len(removed) == 0
        assert e.memory_count == 1

    # -- supersession --

    def test_supersede_memory(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        new = _mem("m2", supersedes_ids=("m1",))
        result = e.supersede_memory("m1", new)
        assert result.memory_id == "m2"
        assert e.get_memory("m1") is not None  # old stays
        assert e.memory_count == 2

    def test_supersede_missing_old_rejected(self):
        e = MemoryMeshEngine()
        new = _mem("m2", supersedes_ids=("m1",))
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            e.supersede_memory("m1", new)

    def test_supersede_without_ref_rejected(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        new = _mem("m2")  # no supersedes_ids
        with pytest.raises(RuntimeCoreInvariantError, match="supersedes_ids"):
            e.supersede_memory("m1", new)

    # -- conflicts --

    def test_record_and_find_conflict(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        cfl = MemoryConflictRecord(
            conflict_id="cfl-1",
            conflicting_ids=("m1", "m2"),
            reason="Contradictory data",
            resolution_state=ConflictResolutionState.UNRESOLVED,
            created_at=NOW,
        )
        e.record_conflict(cfl)
        assert e.conflict_count == 1
        found = e.find_conflicts("m1")
        assert len(found) == 1
        assert found[0].conflict_id == "cfl-1"

    def test_conflict_missing_memory_rejected(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        cfl = MemoryConflictRecord(
            conflict_id="cfl-1",
            conflicting_ids=("m1", "m-nope"),
            reason="test",
            resolution_state=ConflictResolutionState.UNRESOLVED,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            e.record_conflict(cfl)

    # -- retrieval --

    def test_retrieve_all(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        q = MemoryRetrievalQuery(query_id="q1")
        result = e.retrieve(q)
        assert result.total == 2
        assert len(result.matched_ids) == 2

    def test_retrieve_by_scope(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", scope=MemoryScope.GOAL, scope_ref_id="g1"))
        e.add_memory(_mem("m2", scope=MemoryScope.WORKFLOW, scope_ref_id="w1"))
        q = MemoryRetrievalQuery(query_id="q1", scope=MemoryScope.GOAL)
        result = e.retrieve(q)
        assert result.total == 1

    def test_retrieve_by_scope_ref_id(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", scope=MemoryScope.GOAL, scope_ref_id="g1"))
        e.add_memory(_mem("m2", scope=MemoryScope.GOAL, scope_ref_id="g2"))
        q = MemoryRetrievalQuery(query_id="q1", scope=MemoryScope.GOAL, scope_ref_id="g1")
        result = e.retrieve(q)
        assert result.total == 1

    def test_retrieve_by_tags(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", tags=("crm", "sales")))
        e.add_memory(_mem("m2", tags=("crm",)))
        q = MemoryRetrievalQuery(query_id="q1", tags=("crm", "sales"))
        result = e.retrieve(q)
        assert result.total == 1
        assert result.matched_ids[0] == "m1"

    def test_retrieve_by_trust_floor(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", confidence=0.3))
        e.add_memory(_mem("m2", confidence=0.9))
        q = MemoryRetrievalQuery(query_id="q1", trust_floor=0.5)
        result = e.retrieve(q)
        assert result.total == 1

    def test_retrieve_by_memory_types(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", memory_type=MemoryType.EPISODIC))
        e.add_memory(_mem("m2", memory_type=MemoryType.STRATEGIC))
        q = MemoryRetrievalQuery(
            query_id="q1",
            memory_types=(MemoryType.STRATEGIC,),
        )
        result = e.retrieve(q)
        assert result.total == 1

    def test_retrieve_max_results(self):
        e = MemoryMeshEngine()
        for i in range(10):
            e.add_memory(_mem(f"m{i}"))
        q = MemoryRetrievalQuery(query_id="q1", max_results=3)
        result = e.retrieve(q)
        assert result.total == 10
        assert len(result.matched_ids) == 3

    def test_retrieve_by_lineage(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1", source_ids=("evt-1", "evt-2")))
        e.add_memory(_mem("m2", source_ids=("evt-3",)))
        q = MemoryRetrievalQuery(query_id="q1", lineage_ids=("evt-1",))
        result = e.retrieve(q)
        assert result.total == 1
        assert result.matched_ids[0] == "m1"

    def test_retrieve_deterministic_order(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m-b", confidence=0.8))
        e.add_memory(_mem("m-a", confidence=0.8))
        q = MemoryRetrievalQuery(query_id="q1")
        result = e.retrieve(q)
        # Same confidence => sorted by ID ascending
        assert result.matched_ids == ("m-a", "m-b")

    # -- metadata nodes and edges --

    def test_add_and_get_node(self):
        e = MemoryMeshEngine()
        n = e.add_metadata_node(_node("n1"))
        assert e.get_metadata_node("n1") is n
        assert e.node_count == 1

    def test_duplicate_node_rejected(self):
        e = MemoryMeshEngine()
        e.add_metadata_node(_node("n1"))
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            e.add_metadata_node(_node("n1"))

    def test_add_edge(self):
        e = MemoryMeshEngine()
        e.add_metadata_node(_node("n1"))
        e.add_metadata_node(_node("n2"))
        edge = MetadataEdge(
            edge_id="e1",
            from_node_id="n1",
            to_node_id="n2",
            relation=MetadataEdgeRelation.DERIVED_FROM,
            created_at=NOW,
        )
        result = e.add_metadata_edge(edge)
        assert result.edge_id == "e1"
        assert e.edge_count == 1

    def test_edge_missing_from_node_rejected(self):
        e = MemoryMeshEngine()
        e.add_metadata_node(_node("n2"))
        edge = MetadataEdge(
            edge_id="e1",
            from_node_id="n1",
            to_node_id="n2",
            relation=MetadataEdgeRelation.DERIVED_FROM,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="from_node_id"):
            e.add_metadata_edge(edge)

    def test_get_edges_for(self):
        e = MemoryMeshEngine()
        e.add_metadata_node(_node("n1"))
        e.add_metadata_node(_node("n2"))
        e.add_metadata_node(_node("n3"))
        e.add_metadata_edge(MetadataEdge(
            edge_id="e1", from_node_id="n1", to_node_id="n2",
            relation=MetadataEdgeRelation.RELATED_TO, created_at=NOW,
        ))
        e.add_metadata_edge(MetadataEdge(
            edge_id="e2", from_node_id="n3", to_node_id="n1",
            relation=MetadataEdgeRelation.ANNOTATES, created_at=NOW,
        ))
        edges = e.get_edges_for("n1")
        assert len(edges) == 2

    # -- state hash --

    def test_state_hash_deterministic(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        e.add_memory(_mem("m2"))
        h1 = e.state_hash()
        h2 = e.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_add(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m1"))
        h1 = e.state_hash()
        e.add_memory(_mem("m2"))
        h2 = e.state_hash()
        assert h1 != h2

    def test_empty_state_hash(self):
        e = MemoryMeshEngine()
        h = e.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


class TestBoundedContractWitnesses:
    def test_invariant_messages_do_not_reflect_ids(self):
        e = MemoryMeshEngine()
        e.add_memory(_mem("m-secret"))

        with pytest.raises(RuntimeCoreInvariantError) as duplicate_exc:
            e.add_memory(_mem("m-secret"))
        duplicate_message = str(duplicate_exc.value)
        assert duplicate_message == "duplicate memory_id"
        assert "m-secret" not in duplicate_message
        assert "memory_id" in duplicate_message

        lnk = MemoryLink(
            link_id="lnk-secret",
            from_memory_id="ghost-from",
            to_memory_id="m-secret",
            relation=MemoryLinkRelation.SUPPORTS,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError) as from_exc:
            e.link_memories(lnk)
        from_message = str(from_exc.value)
        assert from_message == "from_memory_id not found"
        assert "ghost-from" not in from_message
        assert "from_memory_id" in from_message

        e.add_metadata_node(_node("n-secret"))
        edge = MetadataEdge(
            edge_id="edge-secret",
            from_node_id="n-secret",
            to_node_id="ghost-node",
            relation=MetadataEdgeRelation.RELATED_TO,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError) as edge_exc:
            e.add_metadata_edge(edge)
        edge_message = str(edge_exc.value)
        assert edge_message == "to_node_id not found"
        assert "ghost-node" not in edge_message
        assert "to_node_id" in edge_message
