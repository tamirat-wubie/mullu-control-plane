"""Golden scenario tests for the memory mesh kernel.

Tests end-to-end flows that span contracts, engine, and integration bridge
to verify the complete memory lifecycle.
"""

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
from mcoi_runtime.core.memory_mesh_integration import MemoryMeshIntegration

NOW = "2026-03-20T12:00:00+00:00"
PAST = "2020-01-01T00:00:00+00:00"


class TestGoldenFullLifecycle:
    """Full lifecycle: ingest -> link -> promote -> supersede -> conflict -> retrieve."""

    def test_full_lifecycle(self):
        engine = MemoryMeshEngine()
        bridge = MemoryMeshIntegration(engine)

        # 1. Ingest events via bridge
        evt1 = bridge.remember_event(
            event_id="evt-order-1",
            event_type="order_placed",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="sales",
            content={"order_id": "ord-1", "amount": 500},
            tags=("crm", "sales"),
        )
        evt2 = bridge.remember_event(
            event_id="evt-order-2",
            event_type="order_placed",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="sales",
            content={"order_id": "ord-2", "amount": 1200},
            tags=("crm", "sales"),
        )
        assert engine.memory_count == 2

        # 2. Link them as related
        link = MemoryLink(
            link_id="lnk-orders",
            from_memory_id=evt1.memory_id,
            to_memory_id=evt2.memory_id,
            relation=MemoryLinkRelation.RELATED_TO,
            created_at=NOW,
        )
        engine.link_memories(link)
        assert engine.link_count == 1

        # 3. Promote evt1 from OBSERVATION to SEMANTIC (pattern recognized)
        prm = MemoryPromotionRecord(
            promotion_id="prm-sales-pattern",
            memory_id=evt1.memory_id,
            from_type=MemoryType.OBSERVATION,
            to_type=MemoryType.SEMANTIC,
            rationale="Recurring sales pattern detected",
            supporting_ids=(evt2.memory_id,),
            confidence=0.85,
            promoted_at=NOW,
        )
        engine.promote_memory(prm)
        assert engine.promotion_count == 1

        # 4. Supersede evt1 with a refined version
        refined = MemoryRecord(
            memory_id="mem-refined-sales",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.DOMAIN,
            scope_ref_id="sales",
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Refined sales pattern",
            content={"pattern": "high-value orders", "avg_amount": 850},
            source_ids=(evt1.memory_id, evt2.memory_id),
            tags=("crm", "sales", "pattern"),
            confidence=0.9,
            created_at=NOW,
            updated_at=NOW,
            supersedes_ids=(evt1.memory_id,),
        )
        engine.supersede_memory(evt1.memory_id, refined)
        assert engine.memory_count == 3

        # 5. Record a conflict between evt2 and refined
        conflict = MemoryConflictRecord(
            conflict_id="cfl-amount-discrepancy",
            conflicting_ids=(evt2.memory_id, refined.memory_id),
            reason="Amount in evt2 differs from avg in refined",
            resolution_state=ConflictResolutionState.UNRESOLVED,
            created_at=NOW,
        )
        engine.record_conflict(conflict)
        assert engine.conflict_count == 1

        # 6. Retrieve by domain scope
        q = MemoryRetrievalQuery(
            query_id="qry-sales",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="sales",
            tags=("crm",),
        )
        result = engine.retrieve(q)
        assert result.total == 3  # evt1, evt2, refined all in domain/sales

        # 7. Retrieve with trust floor filters
        q2 = MemoryRetrievalQuery(
            query_id="qry-high-conf",
            scope=MemoryScope.DOMAIN,
            trust_floor=0.85,
        )
        result2 = engine.retrieve(q2)
        assert result2.total == 1  # only refined has 0.9

        # 8. State hash is stable
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


class TestGoldenDecayLifecycle:
    """Decay: add memories with expiry -> apply decay -> verify removal."""

    def test_decay_lifecycle(self):
        engine = MemoryMeshEngine()

        # Add expired memory
        expired = MemoryRecord(
            memory_id="mem-expired",
            memory_type=MemoryType.WORKING,
            scope=MemoryScope.JOB,
            scope_ref_id="job-1",
            trust_level=MemoryTrustLevel.UNVERIFIED,
            title="Stale working memory",
            content={"temp": True},
            source_ids=("src-1",),
            confidence=0.5,
            created_at=PAST,
            updated_at=PAST,
            expires_at=PAST,
        )
        engine.add_memory(expired)

        # Add non-expiring memory
        permanent = MemoryRecord(
            memory_id="mem-permanent",
            memory_type=MemoryType.STRATEGIC,
            scope=MemoryScope.GLOBAL,
            scope_ref_id="runtime",
            trust_level=MemoryTrustLevel.POLICY_BOUND,
            title="Core strategy",
            content={"strategy": "always"},
            source_ids=("src-2",),
            confidence=1.0,
            created_at=NOW,
            updated_at=NOW,
        )
        engine.add_memory(permanent)

        assert engine.memory_count == 2

        # Set decay policy
        engine.set_decay_policy(MemoryDecayPolicy(
            policy_id="dp-working",
            memory_type=MemoryType.WORKING,
            decay_mode=DecayMode.TTL,
            ttl_seconds=3600,
            created_at=NOW,
        ))

        # Apply decay
        removed = engine.apply_decay()
        assert "mem-expired" in removed
        assert engine.memory_count == 1
        assert engine.get_memory("mem-permanent") is not None


class TestGoldenMetadataOverlay:
    """Metadata mesh overlay: nodes + edges over memory records."""

    def test_metadata_overlay(self):
        engine = MemoryMeshEngine()
        bridge = MemoryMeshIntegration(engine)

        # Create memories
        rec = bridge.remember_event(
            event_id="evt-1",
            event_type="ticket_created",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="support",
            content={"ticket_id": "t-1"},
        )

        # Create metadata nodes for the memory and its owner
        mem_node = MetadataNode(
            node_id="mdn-mem-1",
            node_type="memory",
            ref_id=rec.memory_id,
            facets={"provenance": {"source": "crm", "transform": "normalize"}},
            created_at=NOW,
        )
        owner_node = MetadataNode(
            node_id="mdn-owner-1",
            node_type="operator",
            ref_id="op-1",
            facets={"ownership": {"level": "admin"}},
            created_at=NOW,
        )
        engine.add_metadata_node(mem_node)
        engine.add_metadata_node(owner_node)
        assert engine.node_count == 2

        # Link them
        edge = MetadataEdge(
            edge_id="mde-owned",
            from_node_id="mdn-mem-1",
            to_node_id="mdn-owner-1",
            relation=MetadataEdgeRelation.OWNED_BY,
            weight=1.0,
            created_at=NOW,
        )
        engine.add_metadata_edge(edge)
        assert engine.edge_count == 1

        # Query edges
        edges = engine.get_edges_for("mdn-mem-1")
        assert len(edges) == 1
        assert edges[0].relation == MetadataEdgeRelation.OWNED_BY


class TestGoldenMultiSourceRetrieval:
    """Retrieve memories from multiple sources using bridge methods."""

    def test_multi_source_retrieval(self):
        engine = MemoryMeshEngine()
        bridge = MemoryMeshIntegration(engine)

        # Ingest from multiple domains
        bridge.remember_event(
            event_id="e1", event_type="order",
            scope=MemoryScope.GOAL, scope_ref_id="goal-1",
            content={"order": 1},
        )
        bridge.remember_obligation(
            obligation_id="obl-1", state="created",
            scope=MemoryScope.GOAL, scope_ref_id="goal-1",
            content={"type": "followup"},
        )
        bridge.remember_job(
            job_id="job-1", job_state="completed",
            scope=MemoryScope.GOAL, scope_ref_id="goal-1",
            content={"result": "ok"},
        )
        bridge.remember_workflow(
            workflow_id="wfl-1", stage="done",
            scope=MemoryScope.WORKFLOW, scope_ref_id="wfl-1",
            content={},
        )
        bridge.remember_simulation(
            simulation_id="sim-1", verdict="proceed",
            scope=MemoryScope.GOAL, scope_ref_id="goal-1",
            content={"risk": "low"},
        )

        assert engine.memory_count == 5

        # Retrieve all for goal-1
        result = bridge.retrieve_for_goal("goal-1")
        assert result.total == 4  # 4 scoped to GOAL

        # Retrieve for workflow
        wfl_result = bridge.retrieve_for_workflow("wfl-1")
        assert wfl_result.total == 1


class TestGoldenConflictResolution:
    """Conflict surfacing and verification."""

    def test_conflict_surfacing(self):
        engine = MemoryMeshEngine()

        m1 = MemoryRecord(
            memory_id="mem-a",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.DOMAIN,
            scope_ref_id="pricing",
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Price is $100",
            content={"price": 100},
            source_ids=("src-1",),
            confidence=0.9,
            created_at=NOW,
            updated_at=NOW,
        )
        m2 = MemoryRecord(
            memory_id="mem-b",
            memory_type=MemoryType.SEMANTIC,
            scope=MemoryScope.DOMAIN,
            scope_ref_id="pricing",
            trust_level=MemoryTrustLevel.OBSERVED,
            title="Price is $120",
            content={"price": 120},
            source_ids=("src-2",),
            confidence=0.7,
            created_at=NOW,
            updated_at=NOW,
        )
        engine.add_memory(m1)
        engine.add_memory(m2)

        # Surface conflict
        cfl = MemoryConflictRecord(
            conflict_id="cfl-price",
            conflicting_ids=("mem-a", "mem-b"),
            reason="Price contradiction",
            resolution_state=ConflictResolutionState.UNRESOLVED,
            created_at=NOW,
        )
        engine.record_conflict(cfl)

        # Both memories are findable via conflict
        for mid in ("mem-a", "mem-b"):
            conflicts = engine.find_conflicts(mid)
            assert len(conflicts) == 1
            assert conflicts[0].conflict_id == "cfl-price"

        # Higher confidence wins in retrieval ordering
        q = MemoryRetrievalQuery(query_id="qry-pricing", scope=MemoryScope.DOMAIN)
        result = engine.retrieve(q)
        assert result.matched_ids[0] == "mem-a"  # 0.9 > 0.7


class TestGoldenStateHashIntegrity:
    """State hash integrity across operations."""

    def test_hash_tracks_all_collections(self):
        engine = MemoryMeshEngine()

        h_empty = engine.state_hash()

        # Add memory
        engine.add_memory(MemoryRecord(
            memory_id="m1",
            memory_type=MemoryType.EPISODIC,
            scope=MemoryScope.GLOBAL,
            scope_ref_id="g",
            trust_level=MemoryTrustLevel.OBSERVED,
            title="T",
            content={},
            source_ids=("s",),
            confidence=0.5,
            created_at=NOW,
            updated_at=NOW,
        ))
        h_mem = engine.state_hash()
        assert h_mem != h_empty

        # Add node
        engine.add_metadata_node(MetadataNode(
            node_id="n1", node_type="t", ref_id="r", facets={}, created_at=NOW,
        ))
        h_node = engine.state_hash()
        assert h_node != h_mem

        # Add edge
        engine.add_metadata_node(MetadataNode(
            node_id="n2", node_type="t", ref_id="r2", facets={}, created_at=NOW,
        ))
        engine.add_metadata_edge(MetadataEdge(
            edge_id="e1", from_node_id="n1", to_node_id="n2",
            relation=MetadataEdgeRelation.RELATED_TO, created_at=NOW,
        ))
        h_edge = engine.state_hash()
        assert h_edge != h_node
