"""Contract-level tests for memory_mesh and metadata_mesh contracts."""

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
    MemoryRetrievalResult,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.contracts.metadata_mesh import (
    ConfidenceFacet,
    ExpiryFacet,
    MetadataEdge,
    MetadataEdgeRelation,
    MetadataFacetType,
    MetadataNode,
    OwnershipFacet,
    PolicyFacet,
    ProvenanceFacet,
    SemanticFacet,
)

NOW = "2026-03-20T12:00:00+00:00"
LATER = "2026-03-21T12:00:00+00:00"


# ---------------------------------------------------------------------------
# MemoryRecord
# ---------------------------------------------------------------------------


class TestMemoryRecord:
    def _make(self, **overrides):
        defaults = dict(
            memory_id="mem-1",
            memory_type=MemoryType.EPISODIC,
            scope=MemoryScope.GOAL,
            scope_ref_id="goal-1",
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Test memory",
            content={"key": "value"},
            source_ids=("src-1",),
            created_at=NOW,
            updated_at=NOW,
        )
        defaults.update(overrides)
        return MemoryRecord(**defaults)

    def test_valid_construction(self):
        rec = self._make()
        assert rec.memory_id == "mem-1"
        assert rec.memory_type == MemoryType.EPISODIC
        assert rec.confidence == 0.5  # default

    def test_content_frozen(self):
        rec = self._make(content={"a": [1, 2]})
        with pytest.raises(TypeError):
            rec.content["b"] = 3

    def test_source_ids_frozen(self):
        rec = self._make(source_ids=("s1", "s2"))
        assert isinstance(rec.source_ids, tuple)

    def test_empty_memory_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(memory_id="")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError):
            self._make(title="")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.5)

    def test_confidence_negative(self):
        with pytest.raises(ValueError):
            self._make(confidence=-0.1)

    def test_invalid_memory_type(self):
        with pytest.raises(ValueError):
            self._make(memory_type="invalid")

    def test_invalid_scope(self):
        with pytest.raises(ValueError):
            self._make(scope="bad")

    def test_invalid_trust_level(self):
        with pytest.raises(ValueError):
            self._make(trust_level="nope")

    def test_serialization_roundtrip(self):
        rec = self._make()
        d = rec.to_dict()
        assert d["memory_id"] == "mem-1"
        assert d["memory_type"] == "episodic"
        assert isinstance(d["content"], dict)

    def test_expires_at_optional(self):
        rec = self._make(expires_at=LATER)
        assert rec.expires_at == LATER

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    def test_supersedes_ids_frozen(self):
        rec = self._make(supersedes_ids=("old-1",))
        assert rec.supersedes_ids == ("old-1",)

    def test_frozen_immutable(self):
        rec = self._make()
        with pytest.raises(AttributeError):
            rec.memory_id = "new"

    def test_all_memory_types(self):
        for mt in MemoryType:
            rec = self._make(memory_type=mt)
            assert rec.memory_type == mt

    def test_all_scopes(self):
        for sc in MemoryScope:
            rec = self._make(scope=sc)
            assert rec.scope == sc

    def test_all_trust_levels(self):
        for tl in MemoryTrustLevel:
            rec = self._make(trust_level=tl)
            assert rec.trust_level == tl


# ---------------------------------------------------------------------------
# MemoryLink
# ---------------------------------------------------------------------------


class TestMemoryLink:
    def _make(self, **overrides):
        defaults = dict(
            link_id="lnk-1",
            from_memory_id="mem-a",
            to_memory_id="mem-b",
            relation=MemoryLinkRelation.SUPPORTS,
            created_at=NOW,
        )
        defaults.update(overrides)
        return MemoryLink(**defaults)

    def test_valid_construction(self):
        lnk = self._make()
        assert lnk.link_id == "lnk-1"
        assert lnk.confidence == 1.0

    def test_self_referential_rejected(self):
        with pytest.raises(ValueError, match="self-referential"):
            self._make(from_memory_id="mem-x", to_memory_id="mem-x")

    def test_empty_link_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(link_id="")

    def test_all_relations(self):
        for rel in MemoryLinkRelation:
            lnk = self._make(relation=rel)
            assert lnk.relation == rel

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["relation"] == "supports"


# ---------------------------------------------------------------------------
# MemoryPromotionRecord
# ---------------------------------------------------------------------------


class TestMemoryPromotionRecord:
    def _make(self, **overrides):
        defaults = dict(
            promotion_id="prm-1",
            memory_id="mem-1",
            from_type=MemoryType.EPISODIC,
            to_type=MemoryType.PROCEDURAL,
            rationale="Pattern observed 3 times",
            supporting_ids=("mem-2", "mem-3"),
            confidence=0.85,
            promoted_at=NOW,
        )
        defaults.update(overrides)
        return MemoryPromotionRecord(**defaults)

    def test_valid_construction(self):
        prm = self._make()
        assert prm.promotion_id == "prm-1"

    def test_same_type_rejected(self):
        with pytest.raises(ValueError, match="must change"):
            self._make(from_type=MemoryType.EPISODIC, to_type=MemoryType.EPISODIC)

    def test_empty_rationale_rejected(self):
        with pytest.raises(ValueError):
            self._make(rationale="")


# ---------------------------------------------------------------------------
# MemoryDecayPolicy
# ---------------------------------------------------------------------------


class TestMemoryDecayPolicy:
    def _make(self, **overrides):
        defaults = dict(
            policy_id="decay-1",
            memory_type=MemoryType.WORKING,
            decay_mode=DecayMode.TTL,
            ttl_seconds=3600,
            created_at=NOW,
        )
        defaults.update(overrides)
        return MemoryDecayPolicy(**defaults)

    def test_valid_construction(self):
        p = self._make()
        assert p.decay_mode == DecayMode.TTL

    def test_negative_ttl_rejected(self):
        with pytest.raises(ValueError):
            self._make(ttl_seconds=-1)

    def test_zero_ttl_rejected(self):
        with pytest.raises(ValueError):
            self._make(ttl_seconds=0)

    def test_none_ttl_allowed(self):
        p = self._make(ttl_seconds=None)
        assert p.ttl_seconds is None

    def test_all_decay_modes(self):
        for dm in DecayMode:
            p = self._make(decay_mode=dm)
            assert p.decay_mode == dm


# ---------------------------------------------------------------------------
# MemoryRetrievalQuery
# ---------------------------------------------------------------------------


class TestMemoryRetrievalQuery:
    def _make(self, **overrides):
        defaults = dict(query_id="qry-1")
        defaults.update(overrides)
        return MemoryRetrievalQuery(**defaults)

    def test_valid_construction(self):
        q = self._make()
        assert q.max_results == 100

    def test_zero_max_results_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_results=0)

    def test_with_filters(self):
        q = self._make(
            scope=MemoryScope.DOMAIN,
            tags=("tag1",),
            trust_floor=0.5,
            memory_types=(MemoryType.SEMANTIC,),
        )
        assert q.scope == MemoryScope.DOMAIN
        assert q.trust_floor == 0.5


# ---------------------------------------------------------------------------
# MemoryRetrievalResult
# ---------------------------------------------------------------------------


class TestMemoryRetrievalResult:
    def test_valid_construction(self):
        r = MemoryRetrievalResult(
            query_id="qry-1",
            matched_ids=("mem-1", "mem-2"),
            total=2,
            retrieved_at=NOW,
        )
        assert r.total == 2
        assert len(r.matched_ids) == 2


# ---------------------------------------------------------------------------
# MemoryConflictRecord
# ---------------------------------------------------------------------------


class TestMemoryConflictRecord:
    def _make(self, **overrides):
        defaults = dict(
            conflict_id="cfl-1",
            conflicting_ids=("mem-a", "mem-b"),
            reason="Contradictory facts",
            resolution_state=ConflictResolutionState.UNRESOLVED,
            created_at=NOW,
        )
        defaults.update(overrides)
        return MemoryConflictRecord(**defaults)

    def test_valid_construction(self):
        c = self._make()
        assert c.resolution_state == ConflictResolutionState.UNRESOLVED

    def test_fewer_than_two_ids_rejected(self):
        with pytest.raises(ValueError, match="at least two"):
            self._make(conflicting_ids=("only-one",))

    def test_empty_conflicting_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(conflicting_ids=("mem-a", ""))

    def test_all_resolution_states(self):
        for rs in ConflictResolutionState:
            c = self._make(resolution_state=rs)
            assert c.resolution_state == rs


# ---------------------------------------------------------------------------
# Metadata facets
# ---------------------------------------------------------------------------


class TestProvenanceFacet:
    def test_valid(self):
        f = ProvenanceFacet(
            source_system="crm",
            source_id="rec-1",
            ingested_at=NOW,
            transform_chain=("normalize", "dedupe"),
        )
        assert f.source_system == "crm"
        assert len(f.transform_chain) == 2

    def test_empty_source_rejected(self):
        with pytest.raises(ValueError):
            ProvenanceFacet(source_system="", source_id="x", ingested_at=NOW)


class TestOwnershipFacet:
    def test_valid(self):
        f = OwnershipFacet(owner_id="user-1", owner_type="operator", assigned_at=NOW)
        assert f.owner_type == "operator"


class TestPolicyFacet:
    def test_valid(self):
        f = PolicyFacet(
            policy_id="pol-1",
            rule_ids=("r1", "r2"),
            effect="allow",
            bound_at=NOW,
        )
        assert len(f.rule_ids) == 2

    def test_empty_rule_id_rejected(self):
        with pytest.raises(ValueError):
            PolicyFacet(policy_id="pol-1", rule_ids=("",), effect="allow", bound_at=NOW)


class TestConfidenceFacet:
    def test_valid(self):
        f = ConfidenceFacet(confidence=0.95, source="model-v2", assessed_at=NOW)
        assert f.confidence == 0.95

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            ConfidenceFacet(confidence=1.1, source="x", assessed_at=NOW)


class TestExpiryFacet:
    def test_valid(self):
        f = ExpiryFacet(expires_at=LATER, reason="TTL policy")
        assert f.reason == "TTL policy"


class TestSemanticFacet:
    def test_valid(self):
        f = SemanticFacet(tags=("crm", "sales"), domain="customer", category="lead")
        assert f.domain == "customer"

    def test_empty_domain_rejected(self):
        with pytest.raises(ValueError):
            SemanticFacet(tags=(), domain="", category="x")


# ---------------------------------------------------------------------------
# MetadataNode
# ---------------------------------------------------------------------------


class TestMetadataNode:
    def _make(self, **overrides):
        defaults = dict(
            node_id="node-1",
            node_type="memory",
            ref_id="mem-1",
            facets={"provenance": {"source": "crm"}},
            created_at=NOW,
        )
        defaults.update(overrides)
        return MetadataNode(**defaults)

    def test_valid_construction(self):
        n = self._make()
        assert n.node_type == "memory"

    def test_facets_frozen(self):
        n = self._make()
        with pytest.raises(TypeError):
            n.facets["new"] = "val"

    def test_empty_node_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(node_id="")

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["node_id"] == "node-1"


# ---------------------------------------------------------------------------
# MetadataEdge
# ---------------------------------------------------------------------------


class TestMetadataEdge:
    def _make(self, **overrides):
        defaults = dict(
            edge_id="edge-1",
            from_node_id="node-a",
            to_node_id="node-b",
            relation=MetadataEdgeRelation.DERIVED_FROM,
            created_at=NOW,
        )
        defaults.update(overrides)
        return MetadataEdge(**defaults)

    def test_valid_construction(self):
        e = self._make()
        assert e.weight == 1.0

    def test_self_referential_rejected(self):
        with pytest.raises(ValueError, match="self-referential"):
            self._make(from_node_id="node-x", to_node_id="node-x")

    def test_all_relations(self):
        for rel in MetadataEdgeRelation:
            e = self._make(relation=rel)
            assert e.relation == rel

    def test_weight_out_of_range(self):
        with pytest.raises(ValueError):
            self._make(weight=1.5)


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnumValues:
    def test_metadata_facet_type_count(self):
        assert len(MetadataFacetType) == 9

    def test_memory_type_count(self):
        assert len(MemoryType) == 11

    def test_memory_scope_count(self):
        assert len(MemoryScope) == 12

    def test_memory_trust_level_count(self):
        assert len(MemoryTrustLevel) == 6

    def test_memory_link_relation_count(self):
        assert len(MemoryLinkRelation) == 8

    def test_decay_mode_count(self):
        assert len(DecayMode) == 4

    def test_conflict_resolution_state_count(self):
        assert len(ConflictResolutionState) == 4

    def test_metadata_edge_relation_count(self):
        assert len(MetadataEdgeRelation) == 7
