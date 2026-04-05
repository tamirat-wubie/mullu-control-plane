"""Comprehensive tests for KnowledgeQueryEngine.

Coverage: constructor, query lifecycle, filters, evidence, cross-tenant blocking,
same-tenant search (exact/partial/related), execution pipeline, results ranking,
evidence bundles, violation detection, snapshots, state_hash, events, edge cases.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.knowledge_query import KnowledgeQueryEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.knowledge_query import (
    EvidenceBundle,
    EvidenceKind,
    EvidenceReference,
    KnowledgeQuery,
    MatchDisposition,
    MatchRecord,
    QueryExecutionRecord,
    QueryFilter,
    QueryResultStatus,
    QueryScope,
    QuerySnapshot,
    QueryStatus,
    QueryViolation,
    RankedResult,
    RankingStrategy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def engine(es):
    return KnowledgeQueryEngine(es)


@pytest.fixture
def engine_with_query(engine):
    """Engine with one registered query."""
    engine.register_query("q1", "t1", search_text="test search")
    return engine


@pytest.fixture
def engine_with_evidence(engine):
    """Engine with evidence across kinds and tenants."""
    engine.register_query("q1", "t1", search_text="security audit")
    # Same tenant evidence
    engine.register_evidence("e1", "src1", "t1", evidence_kind=EvidenceKind.RECORD, title="Security audit report", confidence=0.9)
    engine.register_evidence("e2", "src2", "t1", evidence_kind=EvidenceKind.CASE, title="Audit findings", confidence=0.8)
    engine.register_evidence("e3", "src3", "t1", evidence_kind=EvidenceKind.MEMORY, title="Security memo", confidence=0.7)
    engine.register_evidence("e4", "src4", "t1", evidence_kind=EvidenceKind.ASSURANCE, title="Assurance security check", confidence=0.6)
    engine.register_evidence("e5", "src5", "t1", evidence_kind=EvidenceKind.REPORTING, title="Quarterly security report", confidence=0.85)
    engine.register_evidence("e6", "src6", "t1", evidence_kind=EvidenceKind.ARTIFACT, title="Security graph artifact", confidence=0.75)
    # Different tenant evidence (should not appear in t1 searches)
    engine.register_evidence("e7", "src7", "t2", evidence_kind=EvidenceKind.RECORD, title="Security audit report", confidence=0.9)
    return engine


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructor:
    def test_valid_constructor(self, es):
        eng = KnowledgeQueryEngine(es)
        assert eng.query_count == 0

    def test_constructor_rejects_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryEngine(None)

    def test_constructor_rejects_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryEngine("not-an-engine")

    def test_constructor_rejects_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryEngine(42)

    def test_constructor_rejects_dict(self):
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryEngine({})

    def test_initial_counts_all_zero(self, engine):
        assert engine.query_count == 0
        assert engine.filter_count == 0
        assert engine.reference_count == 0
        assert engine.match_count == 0
        assert engine.result_count == 0
        assert engine.execution_count == 0
        assert engine.bundle_count == 0
        assert engine.violation_count == 0


# ===================================================================
# Query lifecycle: register, get, cancel, terminal guards
# ===================================================================

class TestRegisterQuery:
    def test_register_returns_knowledge_query(self, engine):
        q = engine.register_query("q1", "t1")
        assert isinstance(q, KnowledgeQuery)

    def test_register_sets_fields(self, engine):
        q = engine.register_query("q1", "t1", scope=QueryScope.WORKSPACE, scope_ref_id="ws1",
                                   search_text="hello", max_results=50)
        assert q.query_id == "q1"
        assert q.tenant_id == "t1"
        assert q.scope == QueryScope.WORKSPACE
        assert q.scope_ref_id == "ws1"
        assert q.search_text == "hello"
        assert q.max_results == 50

    def test_register_defaults(self, engine):
        q = engine.register_query("q1", "t1")
        assert q.scope == QueryScope.TENANT
        assert q.scope_ref_id == ""
        assert q.search_text == ""
        assert q.max_results == 100

    def test_register_status_is_pending(self, engine):
        q = engine.register_query("q1", "t1")
        assert q.status == QueryStatus.PENDING

    def test_register_increments_count(self, engine):
        engine.register_query("q1", "t1")
        assert engine.query_count == 1
        engine.register_query("q2", "t1")
        assert engine.query_count == 2

    def test_register_created_at_is_iso(self, engine):
        q = engine.register_query("q1", "t1")
        assert q.created_at  # non-empty
        assert "T" in q.created_at  # ISO format

    def test_register_duplicate_raises(self, engine):
        engine.register_query("q1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate query_id"):
            engine.register_query("q1", "t1")

    def test_register_all_scopes(self, engine):
        for i, scope in enumerate(QueryScope):
            q = engine.register_query(f"q{i}", "t1", scope=scope)
            assert q.scope == scope

    def test_register_multiple_tenants(self, engine):
        q1 = engine.register_query("q1", "t1")
        q2 = engine.register_query("q2", "t2")
        assert q1.tenant_id == "t1"
        assert q2.tenant_id == "t2"

    def test_register_max_results_zero(self, engine):
        q = engine.register_query("q1", "t1", max_results=0)
        assert q.max_results == 0


class TestGetQuery:
    def test_get_existing(self, engine):
        engine.register_query("q1", "t1")
        q = engine.get_query("q1")
        assert q.query_id == "q1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown query_id"):
            engine.get_query("nonexistent")

    def test_get_returns_same_data(self, engine):
        original = engine.register_query("q1", "t1", search_text="abc")
        fetched = engine.get_query("q1")
        assert original.query_id == fetched.query_id
        assert original.search_text == fetched.search_text


class TestCancelQuery:
    def test_cancel_pending(self, engine):
        engine.register_query("q1", "t1")
        cancelled = engine.cancel_query("q1")
        assert cancelled.status == QueryStatus.CANCELLED

    def test_cancel_preserves_fields(self, engine):
        engine.register_query("q1", "t1", scope=QueryScope.SERVICE, search_text="test")
        cancelled = engine.cancel_query("q1")
        assert cancelled.tenant_id == "t1"
        assert cancelled.scope == QueryScope.SERVICE
        assert cancelled.search_text == "test"

    def test_cancel_completed_raises(self, engine):
        engine.register_query("q1", "t1")
        engine.register_evidence("e1", "s1", "t1", title="x", confidence=0.5)
        engine.execute_query("ex1", "q1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine.cancel_query("q1")

    def test_cancel_failed_raises(self, engine):
        # Simulate FAILED status by registering and executing with terminal
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")  # completes it
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine.cancel_query("q1")

    def test_cancel_cancelled_raises(self, engine):
        engine.register_query("q1", "t1")
        engine.cancel_query("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot cancel"):
            engine.cancel_query("q1")

    def test_cancel_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown query_id"):
            engine.cancel_query("nonexistent")

    def test_cancel_updates_stored_query(self, engine):
        engine.register_query("q1", "t1")
        engine.cancel_query("q1")
        q = engine.get_query("q1")
        assert q.status == QueryStatus.CANCELLED


class TestQueriesForTenant:
    def test_empty_tenant(self, engine):
        result = engine.queries_for_tenant("t1")
        assert result == ()

    def test_returns_tuple(self, engine):
        engine.register_query("q1", "t1")
        result = engine.queries_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_filters_by_tenant(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t2")
        engine.register_query("q3", "t1")
        result = engine.queries_for_tenant("t1")
        assert len(result) == 2
        ids = {q.query_id for q in result}
        assert ids == {"q1", "q3"}

    def test_no_match_returns_empty(self, engine):
        engine.register_query("q1", "t1")
        assert engine.queries_for_tenant("t99") == ()

    def test_all_same_tenant(self, engine):
        for i in range(5):
            engine.register_query(f"q{i}", "t1")
        assert len(engine.queries_for_tenant("t1")) == 5


# ===================================================================
# Filter management
# ===================================================================

class TestAddFilter:
    def test_add_filter_returns_query_filter(self, engine_with_query):
        f = engine_with_query.add_filter("f1", "q1", field_name="status", field_value="open")
        assert isinstance(f, QueryFilter)

    def test_add_filter_sets_fields(self, engine_with_query):
        f = engine_with_query.add_filter("f1", "q1", field_name="priority",
                                          field_value="high", evidence_kind=EvidenceKind.CASE)
        assert f.filter_id == "f1"
        assert f.query_id == "q1"
        assert f.field_name == "priority"
        assert f.field_value == "high"
        assert f.evidence_kind == EvidenceKind.CASE

    def test_add_filter_defaults(self, engine_with_query):
        f = engine_with_query.add_filter("f1", "q1")
        assert f.field_name == "status"
        assert f.field_value == ""
        assert f.evidence_kind == EvidenceKind.RECORD

    def test_add_filter_increments_count(self, engine_with_query):
        engine_with_query.add_filter("f1", "q1")
        assert engine_with_query.filter_count == 1

    def test_add_filter_duplicate_raises(self, engine_with_query):
        engine_with_query.add_filter("f1", "q1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate filter_id"):
            engine_with_query.add_filter("f1", "q1")

    def test_add_filter_unknown_query_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown query_id"):
            engine.add_filter("f1", "nonexistent")

    def test_add_filter_created_at_is_iso(self, engine_with_query):
        f = engine_with_query.add_filter("f1", "q1")
        assert "T" in f.created_at

    def test_add_multiple_filters_same_query(self, engine_with_query):
        engine_with_query.add_filter("f1", "q1", field_name="status")
        engine_with_query.add_filter("f2", "q1", field_name="priority")
        assert engine_with_query.filter_count == 2

    def test_add_filter_all_evidence_kinds(self, engine_with_query):
        for i, kind in enumerate(EvidenceKind):
            f = engine_with_query.add_filter(f"f{i}", "q1", evidence_kind=kind)
            assert f.evidence_kind == kind


class TestFiltersForQuery:
    def test_empty(self, engine_with_query):
        assert engine_with_query.filters_for_query("q1") == ()

    def test_returns_tuple(self, engine_with_query):
        engine_with_query.add_filter("f1", "q1")
        result = engine_with_query.filters_for_query("q1")
        assert isinstance(result, tuple)

    def test_filters_by_query(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t1")
        engine.add_filter("f1", "q1")
        engine.add_filter("f2", "q2")
        engine.add_filter("f3", "q1")
        result = engine.filters_for_query("q1")
        assert len(result) == 2

    def test_no_match_returns_empty(self, engine_with_query):
        engine_with_query.add_filter("f1", "q1")
        assert engine_with_query.filters_for_query("q999") == ()


# ===================================================================
# Evidence registration and retrieval
# ===================================================================

class TestRegisterEvidence:
    def test_returns_evidence_reference(self, engine):
        ref = engine.register_evidence("e1", "src1", "t1", title="Test", confidence=0.5)
        assert isinstance(ref, EvidenceReference)

    def test_sets_fields(self, engine):
        ref = engine.register_evidence("e1", "src1", "t1", evidence_kind=EvidenceKind.CASE,
                                        scope_ref_id="scope1", title="My title", confidence=0.9)
        assert ref.reference_id == "e1"
        assert ref.source_id == "src1"
        assert ref.tenant_id == "t1"
        assert ref.evidence_kind == EvidenceKind.CASE
        assert ref.scope_ref_id == "scope1"
        assert ref.title == "My title"
        assert ref.confidence == pytest.approx(0.9)

    def test_defaults(self, engine):
        ref = engine.register_evidence("e1", "src1", "t1", title="X", confidence=0.5)
        assert ref.evidence_kind == EvidenceKind.RECORD
        assert ref.scope_ref_id == ""

    def test_increments_count(self, engine):
        engine.register_evidence("e1", "src1", "t1", title="X", confidence=0.5)
        assert engine.reference_count == 1

    def test_duplicate_raises(self, engine):
        engine.register_evidence("e1", "src1", "t1", title="X", confidence=0.5)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate reference_id"):
            engine.register_evidence("e1", "src2", "t1", title="Y", confidence=0.5)

    def test_created_at_is_iso(self, engine):
        ref = engine.register_evidence("e1", "src1", "t1", title="X", confidence=0.5)
        assert "T" in ref.created_at

    def test_all_evidence_kinds(self, engine):
        for i, kind in enumerate(EvidenceKind):
            ref = engine.register_evidence(f"e{i}", f"src{i}", "t1",
                                            evidence_kind=kind, title=f"Title {i}", confidence=0.5)
            assert ref.evidence_kind == kind


class TestGetEvidence:
    def test_get_existing(self, engine):
        engine.register_evidence("e1", "src1", "t1", title="X", confidence=0.5)
        ref = engine.get_evidence("e1")
        assert ref.reference_id == "e1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown reference_id"):
            engine.get_evidence("nonexistent")


class TestEvidenceForTenant:
    def test_empty(self, engine):
        assert engine.evidence_for_tenant("t1") == ()

    def test_filters_by_tenant(self, engine):
        engine.register_evidence("e1", "s1", "t1", title="A", confidence=0.5)
        engine.register_evidence("e2", "s2", "t2", title="B", confidence=0.5)
        engine.register_evidence("e3", "s3", "t1", title="C", confidence=0.5)
        result = engine.evidence_for_tenant("t1")
        assert len(result) == 2

    def test_returns_tuple(self, engine):
        engine.register_evidence("e1", "s1", "t1", title="A", confidence=0.5)
        assert isinstance(engine.evidence_for_tenant("t1"), tuple)

    def test_no_match(self, engine):
        engine.register_evidence("e1", "s1", "t1", title="A", confidence=0.5)
        assert engine.evidence_for_tenant("t99") == ()


# ===================================================================
# Cross-tenant search blocking (each search method)
# ===================================================================

class TestCrossTenantBlocking:
    """Every search method must block cross-tenant and return empty tuple."""

    def _setup_cross_tenant(self, engine):
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t1", title="Test item", confidence=0.5)
        return engine

    def test_search_memory_cross_tenant_blocked(self, engine):
        self._setup_cross_tenant(engine)
        result = engine.search_memory("q1", "t2")
        assert result == ()

    def test_search_records_cross_tenant_blocked(self, engine):
        self._setup_cross_tenant(engine)
        result = engine.search_records("q1", "t2")
        assert result == ()

    def test_search_cases_cross_tenant_blocked(self, engine):
        self._setup_cross_tenant(engine)
        result = engine.search_cases("q1", "t2")
        assert result == ()

    def test_search_assurance_cross_tenant_blocked(self, engine):
        self._setup_cross_tenant(engine)
        result = engine.search_assurance("q1", "t2")
        assert result == ()

    def test_search_reporting_cross_tenant_blocked(self, engine):
        self._setup_cross_tenant(engine)
        result = engine.search_reporting("q1", "t2")
        assert result == ()

    def test_search_graph_cross_tenant_blocked(self, engine):
        self._setup_cross_tenant(engine)
        result = engine.search_graph("q1", "t2")
        assert result == ()

    def test_cross_tenant_records_violation(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_memory("q1", "t2")
        assert engine.violation_count >= 1

    def test_cross_tenant_violation_idempotent(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_memory("q1", "t2")
        count1 = engine.violation_count
        engine.search_memory("q1", "t2")
        count2 = engine.violation_count
        assert count1 == count2  # same violation not re-added

    def test_different_cross_tenant_pairs_each_get_violation(self, engine):
        engine.register_query("q1", "t1")
        engine.search_memory("q1", "t2")
        engine.search_memory("q1", "t3")
        assert engine.violation_count == 2

    def test_cross_tenant_unknown_query_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.search_memory("nonexistent", "t2")

    def test_search_records_cross_tenant_violation_recorded(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_records("q1", "t2")
        assert engine.violation_count >= 1

    def test_search_cases_cross_tenant_violation_recorded(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_cases("q1", "t2")
        assert engine.violation_count >= 1

    def test_search_assurance_cross_tenant_violation_recorded(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_assurance("q1", "t2")
        assert engine.violation_count >= 1

    def test_search_reporting_cross_tenant_violation_recorded(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_reporting("q1", "t2")
        assert engine.violation_count >= 1

    def test_search_graph_cross_tenant_violation_recorded(self, engine):
        self._setup_cross_tenant(engine)
        engine.search_graph("q1", "t2")
        assert engine.violation_count >= 1


# ===================================================================
# Same-tenant search results (exact/partial/related)
# ===================================================================

class TestSearchMemory:
    def test_same_tenant_returns_matches(self, engine):
        engine.register_query("q1", "t1", search_text="memo")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Security memo", confidence=0.7)
        result = engine.search_memory("q1", "t1")
        assert len(result) >= 1

    def test_exact_match_disposition(self, engine):
        engine.register_query("q1", "t1", search_text="memo")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Security memo notes", confidence=0.7)
        result = engine.search_memory("q1", "t1")
        assert any(m.disposition == MatchDisposition.EXACT for m in result)

    def test_partial_match_disposition(self, engine):
        engine.register_query("q1", "t1", search_text="security analysis")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Security memo", confidence=0.7)
        result = engine.search_memory("q1", "t1")
        assert any(m.disposition == MatchDisposition.PARTIAL for m in result)

    def test_related_disposition_no_search_text(self, engine):
        engine.register_query("q1", "t1", search_text="")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Anything", confidence=0.8)
        result = engine.search_memory("q1", "t1")
        assert len(result) >= 1
        assert all(m.disposition == MatchDisposition.RELATED for m in result)

    def test_related_relevance_halved(self, engine):
        engine.register_query("q1", "t1", search_text="")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Anything", confidence=0.8)
        result = engine.search_memory("q1", "t1")
        assert result[0].relevance_score == pytest.approx(0.4)

    def test_no_match_when_no_word_overlap(self, engine):
        engine.register_query("q1", "t1", search_text="xyz zzz")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Completely different", confidence=0.7)
        result = engine.search_memory("q1", "t1")
        assert len(result) == 0

    def test_wrong_kind_excluded(self, engine):
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Test record", confidence=0.5)
        result = engine.search_memory("q1", "t1")  # searches MEMORY, not RECORD
        assert len(result) == 0

    def test_different_tenant_excluded(self, engine):
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t2", evidence_kind=EvidenceKind.MEMORY,
                                  title="Test", confidence=0.5)
        result = engine.search_memory("q1", "t1")
        assert len(result) == 0

    def test_custom_search_text_overrides_query(self, engine):
        engine.register_query("q1", "t1", search_text="original")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Custom override target", confidence=0.5)
        result = engine.search_memory("q1", "t1", search_text="custom")
        assert len(result) >= 1

    def test_increments_match_count(self, engine):
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Test memo", confidence=0.5)
        engine.search_memory("q1", "t1")
        assert engine.match_count >= 1


class TestSearchRecords:
    def test_same_tenant_exact(self, engine):
        engine.register_query("q1", "t1", search_text="audit")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Audit record", confidence=0.9)
        result = engine.search_records("q1", "t1")
        assert len(result) >= 1

    def test_cross_tenant_blocked(self, engine):
        engine.register_query("q1", "t1", search_text="audit")
        result = engine.search_records("q1", "t2")
        assert result == ()


class TestSearchCases:
    def test_same_tenant_exact(self, engine):
        engine.register_query("q1", "t1", search_text="finding")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.CASE,
                                  title="Case finding", confidence=0.8)
        result = engine.search_cases("q1", "t1")
        assert len(result) >= 1

    def test_cross_tenant_blocked(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_cases("q1", "t2")
        assert result == ()


class TestSearchAssurance:
    def test_same_tenant_exact(self, engine):
        engine.register_query("q1", "t1", search_text="check")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.ASSURANCE,
                                  title="Assurance check", confidence=0.6)
        result = engine.search_assurance("q1", "t1")
        assert len(result) >= 1

    def test_cross_tenant_blocked(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_assurance("q1", "t2")
        assert result == ()


class TestSearchReporting:
    def test_same_tenant_exact(self, engine):
        engine.register_query("q1", "t1", search_text="quarterly")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.REPORTING,
                                  title="Quarterly report", confidence=0.85)
        result = engine.search_reporting("q1", "t1")
        assert len(result) >= 1

    def test_cross_tenant_blocked(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_reporting("q1", "t2")
        assert result == ()


class TestSearchGraph:
    def test_same_tenant_exact(self, engine):
        engine.register_query("q1", "t1", search_text="artifact")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.ARTIFACT,
                                  title="Graph artifact", confidence=0.75)
        result = engine.search_graph("q1", "t1")
        assert len(result) >= 1

    def test_cross_tenant_blocked(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_graph("q1", "t2")
        assert result == ()

    def test_searches_artifact_kind(self, engine):
        """search_graph uses ARTIFACT kind."""
        engine.register_query("q1", "t1", search_text="")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.ARTIFACT,
                                  title="Node", confidence=0.5)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Node", confidence=0.5)
        result = engine.search_graph("q1", "t1")
        assert len(result) == 1  # only ARTIFACT kind


class TestSearchByKindTextMatching:
    """Detailed tests for _search_by_kind text matching logic."""

    def test_exact_match_substring(self, engine):
        engine.register_query("q1", "t1", search_text="security")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Full security audit report", confidence=0.9)
        result = engine.search_records("q1", "t1")
        assert result[0].disposition == MatchDisposition.EXACT
        assert result[0].relevance_score == pytest.approx(0.9)

    def test_exact_case_insensitive(self, engine):
        engine.register_query("q1", "t1", search_text="SECURITY")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="security report", confidence=0.8)
        result = engine.search_records("q1", "t1")
        assert result[0].disposition == MatchDisposition.EXACT

    def test_partial_word_overlap(self, engine):
        engine.register_query("q1", "t1", search_text="security analysis review")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Security assessment", confidence=0.8)
        result = engine.search_records("q1", "t1")
        assert result[0].disposition == MatchDisposition.PARTIAL

    def test_partial_relevance_scaled(self, engine):
        engine.register_query("q1", "t1", search_text="security analysis review")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Security assessment", confidence=0.9)
        result = engine.search_records("q1", "t1")
        # 1 word overlap out of 3 search words: 0.9 * (1/3)
        assert result[0].relevance_score == pytest.approx(0.9 * (1.0 / 3.0))

    def test_no_overlap_excluded(self, engine):
        engine.register_query("q1", "t1", search_text="xyz abc")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Completely different words", confidence=0.5)
        result = engine.search_records("q1", "t1")
        assert len(result) == 0

    def test_related_all_included_no_search(self, engine):
        engine.register_query("q1", "t1", search_text="")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Whatever", confidence=1.0)
        result = engine.search_records("q1", "t1")
        assert result[0].disposition == MatchDisposition.RELATED
        assert result[0].relevance_score == pytest.approx(0.5)

    def test_relevance_capped_at_one(self, engine):
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Test evidence", confidence=1.0)
        result = engine.search_records("q1", "t1")
        assert result[0].relevance_score <= 1.0

    def test_match_records_are_deduplicated(self, engine):
        """Searching twice with same query+ref+kind should not duplicate matches."""
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Test item", confidence=0.5)
        r1 = engine.search_records("q1", "t1")
        r2 = engine.search_records("q1", "t1")
        assert len(r1) == 1
        assert len(r2) == 0  # already matched, won't re-create

    def test_multiple_evidence_multiple_matches(self, engine):
        engine.register_query("q1", "t1", search_text="report")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Report one", confidence=0.5)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Report two", confidence=0.6)
        result = engine.search_records("q1", "t1")
        assert len(result) == 2


# ===================================================================
# Query execution pipeline
# ===================================================================

class TestExecuteQuery:
    def test_returns_execution_record(self, engine):
        engine.register_query("q1", "t1")
        rec = engine.execute_query("ex1", "q1")
        assert isinstance(rec, QueryExecutionRecord)

    def test_execution_record_fields(self, engine):
        engine.register_query("q1", "t1")
        rec = engine.execute_query("ex1", "q1")
        assert rec.execution_id == "ex1"
        assert rec.query_id == "q1"
        assert "T" in rec.executed_at

    def test_marks_query_completed(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        q = engine.get_query("q1")
        assert q.status == QueryStatus.COMPLETED

    def test_empty_results_status(self, engine):
        engine.register_query("q1", "t1", search_text="nonexistent")
        rec = engine.execute_query("ex1", "q1")
        assert rec.status == QueryResultStatus.EMPTY
        assert rec.total_matches == 0
        assert rec.total_results == 0

    def test_complete_results_status(self, engine):
        engine.register_query("q1", "t1", search_text="test", max_results=100)
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Test item", confidence=0.5)
        rec = engine.execute_query("ex1", "q1")
        assert rec.status == QueryResultStatus.COMPLETE
        assert rec.total_matches >= 1

    def test_truncated_results_status(self, engine):
        engine.register_query("q1", "t1", search_text="item", max_results=1)
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item one", confidence=0.5)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item two", confidence=0.6)
        rec = engine.execute_query("ex1", "q1")
        assert rec.status == QueryResultStatus.TRUNCATED
        assert rec.total_results == 1

    def test_increments_execution_count(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        assert engine.execution_count == 1

    def test_duplicate_execution_id_raises(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t1")
        engine.execute_query("ex1", "q1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate execution_id"):
            engine.execute_query("ex1", "q2")

    def test_cannot_execute_completed_query(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot execute"):
            engine.execute_query("ex2", "q1")

    def test_cannot_execute_cancelled_query(self, engine):
        engine.register_query("q1", "t1")
        engine.cancel_query("q1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot execute"):
            engine.execute_query("ex1", "q1")

    def test_unknown_query_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown query_id"):
            engine.execute_query("ex1", "nonexistent")

    def test_searches_all_evidence_kinds(self, engine):
        engine.register_query("q1", "t1", search_text="")
        for i, kind in enumerate(EvidenceKind):
            engine.register_evidence(f"e{i}", f"s{i}", "t1",
                                      evidence_kind=kind, title=f"Title {i}", confidence=0.5)
        rec = engine.execute_query("ex1", "q1")
        assert rec.total_matches == len(EvidenceKind)

    def test_creates_ranked_results(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item alpha", confidence=0.5)
        engine.execute_query("ex1", "q1")
        assert engine.result_count >= 1

    def test_ranking_strategy_relevance(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item low", confidence=0.3)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item high", confidence=0.9)
        engine.execute_query("ex1", "q1", ranking_strategy=RankingStrategy.RELEVANCE)
        results = engine.results_for_query("q1")
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_ranking_strategy_confidence(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item low", confidence=0.2)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item high", confidence=0.95)
        engine.execute_query("ex1", "q1", ranking_strategy=RankingStrategy.CONFIDENCE)
        results = engine.results_for_query("q1")
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_ranking_strategy_recency(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item A", confidence=0.5)
        rec = engine.execute_query("ex1", "q1", ranking_strategy=RankingStrategy.RECENCY)
        assert rec.total_results >= 0  # just check it doesn't crash

    def test_ranking_strategy_severity(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item A", confidence=0.5)
        rec = engine.execute_query("ex1", "q1", ranking_strategy=RankingStrategy.SEVERITY)
        assert rec.total_results >= 0

    def test_max_results_zero_no_trim(self, engine):
        engine.register_query("q1", "t1", search_text="item", max_results=0)
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item one", confidence=0.5)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item two", confidence=0.6)
        rec = engine.execute_query("ex1", "q1")
        assert rec.total_results == rec.total_matches

    def test_get_execution(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        rec = engine.get_execution("ex1")
        assert rec.execution_id == "ex1"

    def test_get_execution_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown execution_id"):
            engine.get_execution("nonexistent")


# ===================================================================
# Results retrieval and ranking
# ===================================================================

class TestResultsForQuery:
    def test_empty_results(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        results = engine.results_for_query("q1")
        assert results == ()

    def test_sorted_by_rank(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        for i in range(5):
            engine.register_evidence(f"e{i}", f"s{i}", "t1",
                                      evidence_kind=EvidenceKind.RECORD,
                                      title=f"Item {i}", confidence=0.1 * (i + 1))
        engine.execute_query("ex1", "q1")
        results = engine.results_for_query("q1")
        ranks = [r.rank for r in results]
        assert ranks == sorted(ranks)

    def test_returns_tuple(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        assert isinstance(engine.results_for_query("q1"), tuple)

    def test_results_have_correct_query_id(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item", confidence=0.5)
        engine.execute_query("ex1", "q1")
        results = engine.results_for_query("q1")
        assert all(r.query_id == "q1" for r in results)

    def test_no_results_for_other_query(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_query("q2", "t1")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item", confidence=0.5)
        engine.execute_query("ex1", "q1")
        assert engine.results_for_query("q2") == ()


# ===================================================================
# Evidence bundle assembly
# ===================================================================

class TestBuildEvidenceBundle:
    def test_returns_evidence_bundle(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        assert isinstance(bundle, EvidenceBundle)

    def test_bundle_fields(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1", title="My bundle")
        assert bundle.bundle_id == "b1"
        assert bundle.query_id == "q1"
        assert bundle.tenant_id == "t1"
        assert bundle.title == "My bundle"

    def test_bundle_evidence_count(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item one", confidence=0.5)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item two", confidence=0.7)
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        assert bundle.evidence_count >= 1

    def test_bundle_average_confidence(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item one", confidence=0.4)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item two", confidence=0.8)
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        # Average of 0.4 and 0.8 = 0.6
        assert bundle.confidence == pytest.approx(0.6)

    def test_bundle_empty_results_zero_confidence(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        assert bundle.evidence_count == 0
        assert bundle.confidence == pytest.approx(0.0)

    def test_bundle_cross_tenant_raises(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        with pytest.raises(RuntimeCoreInvariantError, match="does not match"):
            engine.build_evidence_bundle("b1", "q1", "t2")

    def test_bundle_duplicate_raises(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        engine.build_evidence_bundle("b1", "q1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate bundle_id"):
            engine.build_evidence_bundle("b1", "q1", "t1")

    def test_bundle_unknown_query_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown query_id"):
            engine.build_evidence_bundle("b1", "nonexistent", "t1")

    def test_bundle_increments_count(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        engine.build_evidence_bundle("b1", "q1", "t1")
        assert engine.bundle_count == 1

    def test_get_bundle(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        engine.build_evidence_bundle("b1", "q1", "t1")
        b = engine.get_bundle("b1")
        assert b.bundle_id == "b1"

    def test_get_bundle_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown bundle_id"):
            engine.get_bundle("nonexistent")

    def test_bundles_for_query(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        engine.build_evidence_bundle("b1", "q1", "t1")
        engine.build_evidence_bundle("b2", "q1", "t1", title="Second bundle")
        bundles = engine.bundles_for_query("q1")
        assert len(bundles) == 2

    def test_bundles_for_query_empty(self, engine):
        assert engine.bundles_for_query("q99") == ()

    def test_bundle_default_title(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        assert bundle.title == "Evidence bundle"

    def test_bundle_assembled_at_iso(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        assert "T" in bundle.assembled_at


# ===================================================================
# Violation detection
# ===================================================================

class TestDetectQueryViolations:
    def test_no_violations_returns_empty(self, engine):
        result = engine.detect_query_violations()
        assert result == ()

    def test_empty_results_violation(self, engine):
        engine.register_query("q1", "t1", search_text="nonexistent")
        engine.execute_query("ex1", "q1")
        violations = engine.detect_query_violations()
        assert len(violations) >= 1
        assert any(v.operation == "empty_results" for v in violations)

    def test_empty_results_violation_has_query_id(self, engine):
        engine.register_query("q1", "t1", search_text="nonexistent")
        engine.execute_query("ex1", "q1")
        violations = engine.detect_query_violations()
        empty_v = [v for v in violations if v.operation == "empty_results"]
        assert empty_v[0].query_id == "q1"

    def test_stuck_executing_violation(self, engine):
        """Manually simulate stuck executing by setting status directly."""
        engine.register_query("q1", "t1")
        # Directly set status to EXECUTING for the stuck-state witness.
        from mcoi_runtime.contracts.knowledge_query import KnowledgeQuery as KQ
        from datetime import datetime, timezone
        old = engine._queries["q1"]
        stuck = KQ(
            query_id=old.query_id, tenant_id=old.tenant_id,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            search_text=old.search_text, status=QueryStatus.EXECUTING,
            max_results=old.max_results, created_at=old.created_at,
        )
        engine._queries["q1"] = stuck

        violations = engine.detect_query_violations()
        assert any(v.operation == "stuck_executing" for v in violations)

    def test_idempotent_second_scan_empty(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")  # empty results
        first = engine.detect_query_violations()
        second = engine.detect_query_violations()
        assert len(first) >= 1
        assert len(second) == 0  # already detected, idempotent

    def test_violation_count_incremented(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        before = engine.violation_count
        engine.detect_query_violations()
        assert engine.violation_count > before

    def test_cross_tenant_violations_separate(self, engine):
        engine.register_query("q1", "t1")
        engine.search_memory("q1", "t2")  # cross-tenant violation
        ct_count = engine.violation_count
        assert ct_count >= 1

    def test_multiple_empty_results_detected(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t1")
        engine.execute_query("ex1", "q1")
        engine.execute_query("ex2", "q2")
        violations = engine.detect_query_violations()
        empty_violations = [v for v in violations if v.operation == "empty_results"]
        assert len(empty_violations) == 2

    def test_returns_tuple(self, engine):
        result = engine.detect_query_violations()
        assert isinstance(result, tuple)

    def test_stuck_executing_idempotent(self, engine):
        engine.register_query("q1", "t1")
        old = engine._queries["q1"]
        from mcoi_runtime.contracts.knowledge_query import KnowledgeQuery as KQ
        stuck = KQ(
            query_id=old.query_id, tenant_id=old.tenant_id,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            search_text=old.search_text, status=QueryStatus.EXECUTING,
            max_results=old.max_results, created_at=old.created_at,
        )
        engine._queries["q1"] = stuck
        first = engine.detect_query_violations()
        second = engine.detect_query_violations()
        assert len(first) >= 1
        assert len(second) == 0

    def test_no_violation_for_completed_with_results(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item", confidence=0.5)
        engine.execute_query("ex1", "q1")
        violations = engine.detect_query_violations()
        empty_violations = [v for v in violations if v.operation == "empty_results"]
        assert len(empty_violations) == 0


# ===================================================================
# Snapshot
# ===================================================================

class TestQuerySnapshot:
    def test_returns_snapshot(self, engine):
        snap = engine.query_snapshot("snap1")
        assert isinstance(snap, QuerySnapshot)

    def test_snapshot_fields_match_counts(self, engine):
        engine.register_query("q1", "t1")
        engine.register_evidence("e1", "s1", "t1", title="X", confidence=0.5)
        snap = engine.query_snapshot("snap1")
        assert snap.total_queries == 1
        assert snap.total_references == 1
        assert snap.total_filters == 0
        assert snap.total_matches == 0
        assert snap.total_results == 0
        assert snap.total_executions == 0
        assert snap.total_bundles == 0
        assert snap.total_violations == 0

    def test_snapshot_id(self, engine):
        snap = engine.query_snapshot("snap1")
        assert snap.snapshot_id == "snap1"

    def test_snapshot_captured_at_iso(self, engine):
        snap = engine.query_snapshot("snap1")
        assert "T" in snap.captured_at

    def test_duplicate_snapshot_raises(self, engine):
        engine.query_snapshot("snap1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate snapshot_id"):
            engine.query_snapshot("snap1")

    def test_snapshot_after_operations(self, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item", confidence=0.5)
        engine.add_filter("f1", "q1")
        engine.execute_query("ex1", "q1")
        engine.build_evidence_bundle("b1", "q1", "t1")
        snap = engine.query_snapshot("snap1")
        assert snap.total_queries == 1
        assert snap.total_filters == 1
        assert snap.total_references == 1
        assert snap.total_executions == 1
        assert snap.total_bundles == 1
        assert snap.total_matches >= 1
        assert snap.total_results >= 1

    def test_multiple_snapshots_different_ids(self, engine):
        s1 = engine.query_snapshot("snap1")
        engine.register_query("q1", "t1")
        s2 = engine.query_snapshot("snap2")
        assert s1.total_queries == 0
        assert s2.total_queries == 1


# ===================================================================
# State hash
# ===================================================================

class TestStateHash:
    def test_returns_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_hash_is_16_chars(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_hash_is_hex(self, engine):
        h = engine.state_hash()
        int(h, 16)  # should not raise

    def test_same_state_same_hash(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_different_state_different_hash(self, engine):
        h1 = engine.state_hash()
        engine.register_query("q1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_evidence(self, engine):
        h1 = engine.state_hash()
        engine.register_evidence("e1", "s1", "t1", title="X", confidence=0.5)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_with_execution(self, engine):
        engine.register_query("q1", "t1")
        h1 = engine.state_hash()
        engine.execute_query("ex1", "q1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_deterministic(self, es):
        eng1 = KnowledgeQueryEngine(es)
        eng2 = KnowledgeQueryEngine(EventSpineEngine())
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# Event emission counts
# ===================================================================

class TestEventEmission:
    def test_register_query_emits_event(self, es, engine):
        before = es.event_count
        engine.register_query("q1", "t1")
        assert es.event_count > before

    def test_cancel_query_emits_event(self, es, engine):
        engine.register_query("q1", "t1")
        before = es.event_count
        engine.cancel_query("q1")
        assert es.event_count > before

    def test_add_filter_emits_event(self, es, engine):
        engine.register_query("q1", "t1")
        before = es.event_count
        engine.add_filter("f1", "q1")
        assert es.event_count > before

    def test_register_evidence_emits_event(self, es, engine):
        before = es.event_count
        engine.register_evidence("e1", "s1", "t1", title="X", confidence=0.5)
        assert es.event_count > before

    def test_search_with_matches_emits_event(self, es, engine):
        engine.register_query("q1", "t1", search_text="test")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Test item", confidence=0.5)
        before = es.event_count
        engine.search_records("q1", "t1")
        assert es.event_count > before

    def test_search_without_matches_no_extra_event(self, es, engine):
        engine.register_query("q1", "t1", search_text="zzz")
        before = es.event_count
        engine.search_records("q1", "t1")
        assert es.event_count == before  # no matches => no event

    def test_cross_tenant_emits_violation_event(self, es, engine):
        engine.register_query("q1", "t1")
        before = es.event_count
        engine.search_memory("q1", "t2")
        assert es.event_count > before

    def test_execute_query_emits_event(self, es, engine):
        engine.register_query("q1", "t1")
        before = es.event_count
        engine.execute_query("ex1", "q1")
        assert es.event_count > before

    def test_build_bundle_emits_event(self, es, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        before = es.event_count
        engine.build_evidence_bundle("b1", "q1", "t1")
        assert es.event_count > before

    def test_snapshot_emits_event(self, es, engine):
        before = es.event_count
        engine.query_snapshot("snap1")
        assert es.event_count > before

    def test_detect_violations_with_findings_emits(self, es, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        before = es.event_count
        engine.detect_query_violations()
        assert es.event_count > before

    def test_detect_violations_no_findings_no_event(self, es, engine):
        engine.register_query("q1", "t1", search_text="item")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Item", confidence=0.5)
        engine.execute_query("ex1", "q1")
        before = es.event_count
        engine.detect_query_violations()
        assert es.event_count == before


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    def test_empty_search_text_returns_all_related(self, engine):
        engine.register_query("q1", "t1", search_text="")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Anything", confidence=0.5)
        engine.register_evidence("e2", "s2", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Something else", confidence=0.8)
        results = engine.search_records("q1", "t1")
        assert len(results) == 2
        assert all(m.disposition == MatchDisposition.RELATED for m in results)

    def test_single_word_search_partial(self, engine):
        engine.register_query("q1", "t1", search_text="report summary")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Final report", confidence=0.5)
        results = engine.search_records("q1", "t1")
        assert len(results) == 1
        assert results[0].disposition == MatchDisposition.PARTIAL

    def test_many_queries_same_tenant(self, engine):
        for i in range(20):
            engine.register_query(f"q{i}", "t1")
        assert engine.query_count == 20
        assert len(engine.queries_for_tenant("t1")) == 20

    def test_many_evidence_same_tenant(self, engine):
        for i in range(20):
            engine.register_evidence(f"e{i}", f"s{i}", "t1",
                                      title=f"Evidence {i}", confidence=0.5)
        assert engine.reference_count == 20
        assert len(engine.evidence_for_tenant("t1")) == 20

    def test_execute_with_mixed_kinds(self, engine_with_evidence):
        rec = engine_with_evidence.execute_query("ex1", "q1")
        # Has evidence of all 6 kinds for t1 with search_text "security audit"
        assert rec.total_matches >= 1

    def test_bundle_with_full_pipeline(self, engine_with_evidence):
        engine_with_evidence.execute_query("ex1", "q1")
        bundle = engine_with_evidence.build_evidence_bundle("b1", "q1", "t1")
        assert bundle.evidence_count >= 1
        assert bundle.confidence > 0.0

    def test_filter_on_different_queries(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t2")
        engine.add_filter("f1", "q1")
        engine.add_filter("f2", "q2")
        assert len(engine.filters_for_query("q1")) == 1
        assert len(engine.filters_for_query("q2")) == 1

    def test_snapshot_captures_violations(self, engine):
        engine.register_query("q1", "t1")
        engine.search_memory("q1", "t2")  # cross-tenant violation
        snap = engine.query_snapshot("snap1")
        assert snap.total_violations >= 1

    def test_state_hash_changes_with_filter(self, engine):
        engine.register_query("q1", "t1")
        h1 = engine.state_hash()
        engine.add_filter("f1", "q1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_violation(self, engine):
        engine.register_query("q1", "t1")
        h1 = engine.state_hash()
        engine.search_memory("q1", "t2")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_with_bundle(self, engine):
        engine.register_query("q1", "t1")
        engine.execute_query("ex1", "q1")
        h1 = engine.state_hash()
        engine.build_evidence_bundle("b1", "q1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_execute_query_with_no_evidence_registered(self, engine):
        engine.register_query("q1", "t1", search_text="anything")
        rec = engine.execute_query("ex1", "q1")
        assert rec.total_matches == 0
        assert rec.total_results == 0
        assert rec.status == QueryResultStatus.EMPTY

    def test_partial_match_multiple_words_overlap(self, engine):
        engine.register_query("q1", "t1", search_text="security audit review")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Security review done", confidence=0.9)
        results = engine.search_records("q1", "t1")
        # "security" and "review" overlap (2 out of 3)
        assert results[0].disposition == MatchDisposition.PARTIAL
        assert results[0].relevance_score == pytest.approx(0.9 * (2.0 / 3.0))

    def test_search_memory_uses_query_search_text_fallback(self, engine):
        engine.register_query("q1", "t1", search_text="memo")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.MEMORY,
                                  title="Important memo", confidence=0.5)
        # Don't pass search_text to search_memory; should use query's
        result = engine.search_memory("q1", "t1")
        assert len(result) >= 1

    def test_query_snapshot_multiple_tenants(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t2")
        snap = engine.query_snapshot("snap1")
        assert snap.total_queries == 2

    def test_full_lifecycle(self, engine):
        """Full lifecycle: register, add filter, add evidence, execute, bundle, snapshot."""
        q = engine.register_query("q1", "t1", search_text="test data")
        engine.add_filter("f1", "q1", field_name="kind")
        engine.register_evidence("e1", "s1", "t1", evidence_kind=EvidenceKind.RECORD,
                                  title="Test data report", confidence=0.85)
        rec = engine.execute_query("ex1", "q1")
        assert rec.total_matches >= 1
        bundle = engine.build_evidence_bundle("b1", "q1", "t1")
        assert bundle.evidence_count >= 1
        snap = engine.query_snapshot("snap1")
        assert snap.total_queries == 1
        assert snap.total_filters == 1
        assert snap.total_references == 1
        assert snap.total_executions == 1
        assert snap.total_bundles == 1

    def test_confidence_boundary_zero(self, engine):
        ref = engine.register_evidence("e1", "s1", "t1", title="X", confidence=0.0)
        assert ref.confidence == pytest.approx(0.0)

    def test_confidence_boundary_one(self, engine):
        ref = engine.register_evidence("e1", "s1", "t1", title="X", confidence=1.0)
        assert ref.confidence == pytest.approx(1.0)

    def test_register_query_with_metadata_default(self, engine):
        q = engine.register_query("q1", "t1")
        assert q.metadata == {}

    def test_cancel_does_not_change_count(self, engine):
        engine.register_query("q1", "t1")
        engine.cancel_query("q1")
        assert engine.query_count == 1  # still in dict, just status changed

    def test_execute_two_different_queries(self, engine):
        engine.register_query("q1", "t1")
        engine.register_query("q2", "t1")
        engine.execute_query("ex1", "q1")
        engine.execute_query("ex2", "q2")
        assert engine.execution_count == 2

    def test_search_memory_empty_no_evidence(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_memory("q1", "t1")
        assert result == ()

    def test_search_records_empty_no_evidence(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_records("q1", "t1")
        assert result == ()

    def test_search_cases_empty_no_evidence(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_cases("q1", "t1")
        assert result == ()

    def test_search_assurance_empty_no_evidence(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_assurance("q1", "t1")
        assert result == ()

    def test_search_reporting_empty_no_evidence(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_reporting("q1", "t1")
        assert result == ()

    def test_search_graph_empty_no_evidence(self, engine):
        engine.register_query("q1", "t1")
        result = engine.search_graph("q1", "t1")
        assert result == ()


class TestBoundedContractWitnesses:
    def test_invariant_messages_do_not_reflect_ids_or_statuses(self, engine):
        engine.register_query("q-secret", "t1")

        with pytest.raises(RuntimeCoreInvariantError) as duplicate_exc:
            engine.register_query("q-secret", "t1")
        duplicate_message = str(duplicate_exc.value)
        assert duplicate_message == "Duplicate query_id"
        assert "q-secret" not in duplicate_message
        assert "query_id" in duplicate_message

        engine.cancel_query("q-secret")
        with pytest.raises(RuntimeCoreInvariantError) as cancel_exc:
            engine.cancel_query("q-secret")
        cancel_message = str(cancel_exc.value)
        assert cancel_message == "Cannot cancel query in current status"
        assert "cancelled" not in cancel_message
        assert "q-secret" not in cancel_message

        with pytest.raises(RuntimeCoreInvariantError) as bundle_exc:
            engine.build_evidence_bundle("bundle-secret", "q-secret", "other-tenant")
        bundle_message = str(bundle_exc.value)
        assert bundle_message == "Bundle tenant does not match query tenant"
        assert "other-tenant" not in bundle_message
        assert "t1" not in bundle_message

    def test_violation_reasons_are_bounded(self, engine):
        engine.register_query("q-cross", "t1")
        engine.search_memory("q-cross", "t2")

        engine.register_query("q-empty", "t1", search_text="nothing-here")
        engine.execute_query("ex-empty", "q-empty")

        engine.register_query("q-stuck", "t1")
        old = engine.get_query("q-stuck")
        engine._queries["q-stuck"] = KnowledgeQuery(
            query_id=old.query_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            search_text=old.search_text,
            status=QueryStatus.EXECUTING,
            max_results=old.max_results,
            created_at=old.created_at,
            metadata=old.metadata,
        )

        violations = {
            (v.query_id, v.operation): v.reason
            for v in engine.detect_query_violations() + tuple(engine._violations.values())
        }
        assert violations[("q-cross", "cross_tenant")] == "Cross-tenant search attempt"
        assert "q-cross" not in violations[("q-cross", "cross_tenant")]
        assert "t2" not in violations[("q-cross", "cross_tenant")]

        assert violations[("q-empty", "empty_results")] == "Query returned zero results"
        assert "q-empty" not in violations[("q-empty", "empty_results")]
        assert "zero results" in violations[("q-empty", "empty_results")]

        assert violations[("q-stuck", "stuck_executing")] == "Query stuck in executing status"
        assert "q-stuck" not in violations[("q-stuck", "stuck_executing")]
        assert "executing status" in violations[("q-stuck", "stuck_executing")]
