"""Comprehensive tests for mcoi_runtime.contracts.knowledge_query contracts."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.knowledge_query import (
    EvidenceBundle,
    EvidenceKind,
    EvidenceReference,
    KnowledgeQuery,
    KnowledgeQueryClosureReport,
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

# =========================================================================
# Shared fixtures / helpers
# =========================================================================

TS = "2025-06-01T00:00:00Z"


def _kq(**kw):
    defaults = dict(
        query_id="q1", tenant_id="t1", scope=QueryScope.TENANT,
        scope_ref_id="sr1", search_text="hello", status=QueryStatus.PENDING,
        max_results=10, created_at=TS,
    )
    defaults.update(kw)
    return KnowledgeQuery(**defaults)


def _qf(**kw):
    defaults = dict(
        filter_id="f1", query_id="q1", field_name="fname",
        field_value="fval", evidence_kind=EvidenceKind.RECORD, created_at=TS,
    )
    defaults.update(kw)
    return QueryFilter(**defaults)


def _er(**kw):
    defaults = dict(
        reference_id="r1", source_id="s1", evidence_kind=EvidenceKind.RECORD,
        tenant_id="t1", scope_ref_id="sr1", title="Evidence Title",
        confidence=0.9, created_at=TS,
    )
    defaults.update(kw)
    return EvidenceReference(**defaults)


def _mr(**kw):
    defaults = dict(
        match_id="m1", query_id="q1", reference_id="r1",
        disposition=MatchDisposition.EXACT, relevance_score=0.8,
        matched_at=TS,
    )
    defaults.update(kw)
    return MatchRecord(**defaults)


def _rr(**kw):
    defaults = dict(
        result_id="res1", query_id="q1", reference_id="r1",
        rank=1, score=0.95, ranking_strategy=RankingStrategy.RELEVANCE,
        ranked_at=TS,
    )
    defaults.update(kw)
    return RankedResult(**defaults)


def _qer(**kw):
    defaults = dict(
        execution_id="e1", query_id="q1", status=QueryResultStatus.COMPLETE,
        total_matches=5, total_results=3, execution_ms=12.5,
        executed_at=TS,
    )
    defaults.update(kw)
    return QueryExecutionRecord(**defaults)


def _qs(**kw):
    defaults = dict(
        snapshot_id="snap1", total_queries=1, total_filters=2,
        total_references=3, total_matches=4, total_results=5,
        total_executions=6, total_bundles=7, total_violations=8,
        captured_at=TS,
    )
    defaults.update(kw)
    return QuerySnapshot(**defaults)


def _qv(**kw):
    defaults = dict(
        violation_id="v1", tenant_id="t1", query_id="q1",
        operation="search", reason="cross-tenant", detected_at=TS,
    )
    defaults.update(kw)
    return QueryViolation(**defaults)


def _eb(**kw):
    defaults = dict(
        bundle_id="b1", query_id="q1", tenant_id="t1",
        title="Bundle Title", evidence_count=3, confidence=0.85,
        assembled_at=TS,
    )
    defaults.update(kw)
    return EvidenceBundle(**defaults)


def _cr(**kw):
    defaults = dict(
        report_id="rpt1", tenant_id="t1", total_queries=10,
        total_executions=8, total_bundles=5, total_violations=2,
        total_matches=50, total_results=40, closed_at=TS,
    )
    defaults.update(kw)
    return KnowledgeQueryClosureReport(**defaults)


# =========================================================================
# Enum tests
# =========================================================================


class TestQueryStatus:
    def test_values(self):
        assert QueryStatus.PENDING.value == "pending"
        assert QueryStatus.EXECUTING.value == "executing"
        assert QueryStatus.COMPLETED.value == "completed"
        assert QueryStatus.FAILED.value == "failed"
        assert QueryStatus.CANCELLED.value == "cancelled"

    def test_member_count(self):
        assert len(QueryStatus) == 5

    def test_membership(self):
        for m in ("PENDING", "EXECUTING", "COMPLETED", "FAILED", "CANCELLED"):
            assert m in QueryStatus.__members__


class TestQueryScope:
    def test_values(self):
        assert QueryScope.TENANT.value == "tenant"
        assert QueryScope.WORKSPACE.value == "workspace"
        assert QueryScope.ENVIRONMENT.value == "environment"
        assert QueryScope.SERVICE.value == "service"
        assert QueryScope.PROGRAM.value == "program"
        assert QueryScope.GLOBAL.value == "global"

    def test_member_count(self):
        assert len(QueryScope) == 6

    def test_membership(self):
        for m in ("TENANT", "WORKSPACE", "ENVIRONMENT", "SERVICE", "PROGRAM", "GLOBAL"):
            assert m in QueryScope.__members__


class TestEvidenceKind:
    def test_values(self):
        assert EvidenceKind.RECORD.value == "record"
        assert EvidenceKind.CASE.value == "case"
        assert EvidenceKind.ASSURANCE.value == "assurance"
        assert EvidenceKind.REPORTING.value == "reporting"
        assert EvidenceKind.ARTIFACT.value == "artifact"
        assert EvidenceKind.MEMORY.value == "memory"

    def test_member_count(self):
        assert len(EvidenceKind) == 6

    def test_membership(self):
        for m in ("RECORD", "CASE", "ASSURANCE", "REPORTING", "ARTIFACT", "MEMORY"):
            assert m in EvidenceKind.__members__


class TestMatchDisposition:
    def test_values(self):
        assert MatchDisposition.EXACT.value == "exact"
        assert MatchDisposition.PARTIAL.value == "partial"
        assert MatchDisposition.RELATED.value == "related"
        assert MatchDisposition.EXCLUDED.value == "excluded"

    def test_member_count(self):
        assert len(MatchDisposition) == 4

    def test_membership(self):
        for m in ("EXACT", "PARTIAL", "RELATED", "EXCLUDED"):
            assert m in MatchDisposition.__members__


class TestRankingStrategy:
    def test_values(self):
        assert RankingStrategy.RELEVANCE.value == "relevance"
        assert RankingStrategy.RECENCY.value == "recency"
        assert RankingStrategy.CONFIDENCE.value == "confidence"
        assert RankingStrategy.SEVERITY.value == "severity"

    def test_member_count(self):
        assert len(RankingStrategy) == 4

    def test_membership(self):
        for m in ("RELEVANCE", "RECENCY", "CONFIDENCE", "SEVERITY"):
            assert m in RankingStrategy.__members__


class TestQueryResultStatus:
    def test_values(self):
        assert QueryResultStatus.COMPLETE.value == "complete"
        assert QueryResultStatus.PARTIAL.value == "partial"
        assert QueryResultStatus.EMPTY.value == "empty"
        assert QueryResultStatus.TRUNCATED.value == "truncated"

    def test_member_count(self):
        assert len(QueryResultStatus) == 4

    def test_membership(self):
        for m in ("COMPLETE", "PARTIAL", "EMPTY", "TRUNCATED"):
            assert m in QueryResultStatus.__members__


# =========================================================================
# KnowledgeQuery
# =========================================================================


class TestKnowledgeQuery:
    def test_valid_construction(self):
        obj = _kq()
        assert obj.query_id == "q1"
        assert obj.tenant_id == "t1"
        assert obj.scope is QueryScope.TENANT
        assert obj.scope_ref_id == "sr1"
        assert obj.search_text == "hello"
        assert obj.status is QueryStatus.PENDING
        assert obj.max_results == 10
        assert obj.created_at == TS

    def test_all_scopes(self):
        for s in QueryScope:
            obj = _kq(scope=s)
            assert obj.scope is s

    def test_all_statuses(self):
        for s in QueryStatus:
            obj = _kq(status=s)
            assert obj.status is s

    def test_frozen(self):
        obj = _kq()
        with pytest.raises(AttributeError):
            obj.query_id = "other"

    def test_query_id_empty_rejected(self):
        with pytest.raises(ValueError):
            _kq(query_id="")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError):
            _kq(tenant_id="")

    def test_scope_invalid(self):
        with pytest.raises(ValueError):
            _kq(scope="tenant")

    def test_status_invalid(self):
        with pytest.raises(ValueError):
            _kq(status="pending")

    def test_max_results_zero_ok(self):
        obj = _kq(max_results=0)
        assert obj.max_results == 0

    def test_max_results_positive_ok(self):
        obj = _kq(max_results=100)
        assert obj.max_results == 100

    def test_max_results_negative_rejected(self):
        with pytest.raises(ValueError):
            _kq(max_results=-1)

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            _kq(created_at="not-a-date")

    def test_created_at_empty_rejected(self):
        with pytest.raises(ValueError):
            _kq(created_at="")

    def test_metadata_frozen(self):
        obj = _kq(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)
        assert obj.metadata["k"] == "v"

    def test_metadata_nested_list_frozen_to_tuple(self):
        obj = _kq(metadata={"items": [1, 2, 3]})
        assert isinstance(obj.metadata["items"], tuple)
        assert obj.metadata["items"] == (1, 2, 3)

    def test_metadata_nested_dict_frozen(self):
        obj = _kq(metadata={"inner": {"a": 1}})
        assert isinstance(obj.metadata["inner"], MappingProxyType)

    def test_to_dict(self):
        obj = _kq()
        d = obj.to_dict()
        assert d["query_id"] == "q1"
        assert d["scope"] is QueryScope.TENANT
        assert d["status"] is QueryStatus.PENDING

    def test_to_dict_preserves_enum_objects(self):
        obj = _kq(scope=QueryScope.GLOBAL, status=QueryStatus.FAILED)
        d = obj.to_dict()
        assert d["scope"] is QueryScope.GLOBAL
        assert d["status"] is QueryStatus.FAILED

    def test_metadata_default_empty(self):
        obj = _kq()
        assert isinstance(obj.metadata, MappingProxyType)
        assert len(obj.metadata) == 0


# =========================================================================
# QueryFilter
# =========================================================================


class TestQueryFilter:
    def test_valid_construction(self):
        obj = _qf()
        assert obj.filter_id == "f1"
        assert obj.query_id == "q1"
        assert obj.field_name == "fname"
        assert obj.field_value == "fval"
        assert obj.evidence_kind is EvidenceKind.RECORD
        assert obj.created_at == TS

    def test_all_evidence_kinds(self):
        for k in EvidenceKind:
            obj = _qf(evidence_kind=k)
            assert obj.evidence_kind is k

    def test_frozen(self):
        obj = _qf()
        with pytest.raises(AttributeError):
            obj.filter_id = "other"

    def test_filter_id_empty(self):
        with pytest.raises(ValueError):
            _qf(filter_id="")

    def test_query_id_empty(self):
        with pytest.raises(ValueError):
            _qf(query_id="")

    def test_field_name_empty(self):
        with pytest.raises(ValueError):
            _qf(field_name="")

    def test_evidence_kind_invalid(self):
        with pytest.raises(ValueError):
            _qf(evidence_kind="record")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            _qf(created_at="nope")

    def test_metadata_frozen(self):
        obj = _qf(metadata={"x": [1]})
        assert isinstance(obj.metadata, MappingProxyType)
        assert obj.metadata["x"] == (1,)

    def test_to_dict(self):
        obj = _qf()
        d = obj.to_dict()
        assert d["filter_id"] == "f1"
        assert d["evidence_kind"] is EvidenceKind.RECORD

    def test_field_value_empty_allowed(self):
        # field_value has no require_non_empty_text validation
        obj = _qf(field_value="")
        assert obj.field_value == ""


# =========================================================================
# EvidenceReference
# =========================================================================


class TestEvidenceReference:
    def test_valid_construction(self):
        obj = _er()
        assert obj.reference_id == "r1"
        assert obj.source_id == "s1"
        assert obj.evidence_kind is EvidenceKind.RECORD
        assert obj.tenant_id == "t1"
        assert obj.scope_ref_id == "sr1"
        assert obj.title == "Evidence Title"
        assert obj.confidence == 0.9
        assert obj.created_at == TS

    def test_frozen(self):
        obj = _er()
        with pytest.raises(AttributeError):
            obj.reference_id = "other"

    def test_reference_id_empty(self):
        with pytest.raises(ValueError):
            _er(reference_id="")

    def test_source_id_empty(self):
        with pytest.raises(ValueError):
            _er(source_id="")

    def test_tenant_id_empty(self):
        with pytest.raises(ValueError):
            _er(tenant_id="")

    def test_title_empty(self):
        with pytest.raises(ValueError):
            _er(title="")

    def test_evidence_kind_invalid(self):
        with pytest.raises(ValueError):
            _er(evidence_kind="record")

    def test_confidence_zero(self):
        obj = _er(confidence=0.0)
        assert obj.confidence == 0.0

    def test_confidence_one(self):
        obj = _er(confidence=1.0)
        assert obj.confidence == 1.0

    def test_confidence_negative(self):
        with pytest.raises(ValueError):
            _er(confidence=-0.01)

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            _er(confidence=1.01)

    def test_created_at_invalid(self):
        with pytest.raises(ValueError):
            _er(created_at="bad")

    def test_metadata_frozen(self):
        obj = _er(metadata={"a": {"b": [1]}})
        assert isinstance(obj.metadata, MappingProxyType)
        assert isinstance(obj.metadata["a"], MappingProxyType)
        assert obj.metadata["a"]["b"] == (1,)

    def test_to_dict(self):
        obj = _er()
        d = obj.to_dict()
        assert d["reference_id"] == "r1"
        assert d["evidence_kind"] is EvidenceKind.RECORD
        assert d["confidence"] == 0.9

    def test_all_evidence_kinds(self):
        for k in EvidenceKind:
            obj = _er(evidence_kind=k)
            assert obj.evidence_kind is k


# =========================================================================
# MatchRecord
# =========================================================================


class TestMatchRecord:
    def test_valid_construction(self):
        obj = _mr()
        assert obj.match_id == "m1"
        assert obj.query_id == "q1"
        assert obj.reference_id == "r1"
        assert obj.disposition is MatchDisposition.EXACT
        assert obj.relevance_score == 0.8
        assert obj.matched_at == TS

    def test_frozen(self):
        obj = _mr()
        with pytest.raises(AttributeError):
            obj.match_id = "other"

    def test_match_id_empty(self):
        with pytest.raises(ValueError):
            _mr(match_id="")

    def test_query_id_empty(self):
        with pytest.raises(ValueError):
            _mr(query_id="")

    def test_reference_id_empty(self):
        with pytest.raises(ValueError):
            _mr(reference_id="")

    def test_disposition_invalid(self):
        with pytest.raises(ValueError):
            _mr(disposition="exact")

    def test_all_dispositions(self):
        for d in MatchDisposition:
            obj = _mr(disposition=d)
            assert obj.disposition is d

    def test_relevance_score_zero(self):
        obj = _mr(relevance_score=0.0)
        assert obj.relevance_score == 0.0

    def test_relevance_score_one(self):
        obj = _mr(relevance_score=1.0)
        assert obj.relevance_score == 1.0

    def test_relevance_score_negative(self):
        with pytest.raises(ValueError):
            _mr(relevance_score=-0.01)

    def test_relevance_score_above_one(self):
        with pytest.raises(ValueError):
            _mr(relevance_score=1.01)

    def test_matched_at_invalid(self):
        with pytest.raises(ValueError):
            _mr(matched_at="nope")

    def test_metadata_frozen(self):
        obj = _mr(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _mr()
        d = obj.to_dict()
        assert d["match_id"] == "m1"
        assert d["disposition"] is MatchDisposition.EXACT


# =========================================================================
# RankedResult
# =========================================================================


class TestRankedResult:
    def test_valid_construction(self):
        obj = _rr()
        assert obj.result_id == "res1"
        assert obj.query_id == "q1"
        assert obj.reference_id == "r1"
        assert obj.rank == 1
        assert obj.score == 0.95
        assert obj.ranking_strategy is RankingStrategy.RELEVANCE
        assert obj.ranked_at == TS

    def test_frozen(self):
        obj = _rr()
        with pytest.raises(AttributeError):
            obj.result_id = "other"

    def test_result_id_empty(self):
        with pytest.raises(ValueError):
            _rr(result_id="")

    def test_query_id_empty(self):
        with pytest.raises(ValueError):
            _rr(query_id="")

    def test_reference_id_empty(self):
        with pytest.raises(ValueError):
            _rr(reference_id="")

    def test_rank_zero_ok(self):
        obj = _rr(rank=0)
        assert obj.rank == 0

    def test_rank_positive_ok(self):
        obj = _rr(rank=42)
        assert obj.rank == 42

    def test_rank_negative_rejected(self):
        with pytest.raises(ValueError):
            _rr(rank=-1)

    def test_score_zero(self):
        obj = _rr(score=0.0)
        assert obj.score == 0.0

    def test_score_one(self):
        obj = _rr(score=1.0)
        assert obj.score == 1.0

    def test_score_negative(self):
        with pytest.raises(ValueError):
            _rr(score=-0.01)

    def test_score_above_one(self):
        with pytest.raises(ValueError):
            _rr(score=1.01)

    def test_ranking_strategy_invalid(self):
        with pytest.raises(ValueError):
            _rr(ranking_strategy="relevance")

    def test_all_ranking_strategies(self):
        for s in RankingStrategy:
            obj = _rr(ranking_strategy=s)
            assert obj.ranking_strategy is s

    def test_ranked_at_invalid(self):
        with pytest.raises(ValueError):
            _rr(ranked_at="nope")

    def test_metadata_frozen(self):
        obj = _rr(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _rr()
        d = obj.to_dict()
        assert d["result_id"] == "res1"
        assert d["ranking_strategy"] is RankingStrategy.RELEVANCE


# =========================================================================
# QueryExecutionRecord
# =========================================================================


class TestQueryExecutionRecord:
    def test_valid_construction(self):
        obj = _qer()
        assert obj.execution_id == "e1"
        assert obj.query_id == "q1"
        assert obj.status is QueryResultStatus.COMPLETE
        assert obj.total_matches == 5
        assert obj.total_results == 3
        assert obj.execution_ms == 12.5
        assert obj.executed_at == TS

    def test_frozen(self):
        obj = _qer()
        with pytest.raises(AttributeError):
            obj.execution_id = "other"

    def test_execution_id_empty(self):
        with pytest.raises(ValueError):
            _qer(execution_id="")

    def test_query_id_empty(self):
        with pytest.raises(ValueError):
            _qer(query_id="")

    def test_status_invalid(self):
        with pytest.raises(ValueError):
            _qer(status="complete")

    def test_all_result_statuses(self):
        for s in QueryResultStatus:
            obj = _qer(status=s)
            assert obj.status is s

    def test_total_matches_zero(self):
        obj = _qer(total_matches=0)
        assert obj.total_matches == 0

    def test_total_matches_negative(self):
        with pytest.raises(ValueError):
            _qer(total_matches=-1)

    def test_total_results_zero(self):
        obj = _qer(total_results=0)
        assert obj.total_results == 0

    def test_total_results_negative(self):
        with pytest.raises(ValueError):
            _qer(total_results=-1)

    def test_execution_ms_zero(self):
        obj = _qer(execution_ms=0.0)
        assert obj.execution_ms == 0.0

    def test_execution_ms_positive(self):
        obj = _qer(execution_ms=999.9)
        assert obj.execution_ms == 999.9

    def test_execution_ms_negative(self):
        with pytest.raises(ValueError):
            _qer(execution_ms=-0.1)

    def test_executed_at_invalid(self):
        with pytest.raises(ValueError):
            _qer(executed_at="bad")

    def test_metadata_frozen(self):
        obj = _qer(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _qer()
        d = obj.to_dict()
        assert d["execution_id"] == "e1"
        assert d["status"] is QueryResultStatus.COMPLETE


# =========================================================================
# QuerySnapshot
# =========================================================================


class TestQuerySnapshot:
    def test_valid_construction(self):
        obj = _qs()
        assert obj.snapshot_id == "snap1"
        assert obj.total_queries == 1
        assert obj.total_filters == 2
        assert obj.total_references == 3
        assert obj.total_matches == 4
        assert obj.total_results == 5
        assert obj.total_executions == 6
        assert obj.total_bundles == 7
        assert obj.total_violations == 8
        assert obj.captured_at == TS

    def test_frozen(self):
        obj = _qs()
        with pytest.raises(AttributeError):
            obj.snapshot_id = "other"

    def test_snapshot_id_empty(self):
        with pytest.raises(ValueError):
            _qs(snapshot_id="")

    @pytest.mark.parametrize("field_name", [
        "total_queries", "total_filters", "total_references",
        "total_matches", "total_results", "total_executions",
        "total_bundles", "total_violations",
    ])
    def test_int_fields_zero_ok(self, field_name):
        obj = _qs(**{field_name: 0})
        assert getattr(obj, field_name) == 0

    @pytest.mark.parametrize("field_name", [
        "total_queries", "total_filters", "total_references",
        "total_matches", "total_results", "total_executions",
        "total_bundles", "total_violations",
    ])
    def test_int_fields_negative_rejected(self, field_name):
        with pytest.raises(ValueError):
            _qs(**{field_name: -1})

    def test_captured_at_invalid(self):
        with pytest.raises(ValueError):
            _qs(captured_at="bad")

    def test_metadata_frozen(self):
        obj = _qs(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _qs()
        d = obj.to_dict()
        assert d["snapshot_id"] == "snap1"
        assert d["total_queries"] == 1


# =========================================================================
# QueryViolation
# =========================================================================


class TestQueryViolation:
    def test_valid_construction(self):
        obj = _qv()
        assert obj.violation_id == "v1"
        assert obj.tenant_id == "t1"
        assert obj.query_id == "q1"
        assert obj.operation == "search"
        assert obj.reason == "cross-tenant"
        assert obj.detected_at == TS

    def test_frozen(self):
        obj = _qv()
        with pytest.raises(AttributeError):
            obj.violation_id = "other"

    @pytest.mark.parametrize("field_name", [
        "violation_id", "tenant_id", "query_id", "operation", "reason",
    ])
    def test_text_fields_empty_rejected(self, field_name):
        with pytest.raises(ValueError):
            _qv(**{field_name: ""})

    def test_detected_at_invalid(self):
        with pytest.raises(ValueError):
            _qv(detected_at="bad")

    def test_metadata_frozen(self):
        obj = _qv(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _qv()
        d = obj.to_dict()
        assert d["violation_id"] == "v1"
        assert d["reason"] == "cross-tenant"


# =========================================================================
# EvidenceBundle
# =========================================================================


class TestEvidenceBundle:
    def test_valid_construction(self):
        obj = _eb()
        assert obj.bundle_id == "b1"
        assert obj.query_id == "q1"
        assert obj.tenant_id == "t1"
        assert obj.title == "Bundle Title"
        assert obj.evidence_count == 3
        assert obj.confidence == 0.85
        assert obj.assembled_at == TS

    def test_frozen(self):
        obj = _eb()
        with pytest.raises(AttributeError):
            obj.bundle_id = "other"

    @pytest.mark.parametrize("field_name", [
        "bundle_id", "query_id", "tenant_id", "title",
    ])
    def test_text_fields_empty_rejected(self, field_name):
        with pytest.raises(ValueError):
            _eb(**{field_name: ""})

    def test_evidence_count_zero(self):
        obj = _eb(evidence_count=0)
        assert obj.evidence_count == 0

    def test_evidence_count_negative(self):
        with pytest.raises(ValueError):
            _eb(evidence_count=-1)

    def test_confidence_zero(self):
        obj = _eb(confidence=0.0)
        assert obj.confidence == 0.0

    def test_confidence_one(self):
        obj = _eb(confidence=1.0)
        assert obj.confidence == 1.0

    def test_confidence_negative(self):
        with pytest.raises(ValueError):
            _eb(confidence=-0.01)

    def test_confidence_above_one(self):
        with pytest.raises(ValueError):
            _eb(confidence=1.01)

    def test_assembled_at_invalid(self):
        with pytest.raises(ValueError):
            _eb(assembled_at="bad")

    def test_metadata_frozen(self):
        obj = _eb(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _eb()
        d = obj.to_dict()
        assert d["bundle_id"] == "b1"
        assert d["confidence"] == 0.85


# =========================================================================
# KnowledgeQueryClosureReport
# =========================================================================


class TestKnowledgeQueryClosureReport:
    def test_valid_construction(self):
        obj = _cr()
        assert obj.report_id == "rpt1"
        assert obj.tenant_id == "t1"
        assert obj.total_queries == 10
        assert obj.total_executions == 8
        assert obj.total_bundles == 5
        assert obj.total_violations == 2
        assert obj.total_matches == 50
        assert obj.total_results == 40
        assert obj.closed_at == TS

    def test_frozen(self):
        obj = _cr()
        with pytest.raises(AttributeError):
            obj.report_id = "other"

    def test_report_id_empty(self):
        with pytest.raises(ValueError):
            _cr(report_id="")

    def test_tenant_id_empty(self):
        with pytest.raises(ValueError):
            _cr(tenant_id="")

    @pytest.mark.parametrize("field_name", [
        "total_queries", "total_executions", "total_bundles",
        "total_violations", "total_matches", "total_results",
    ])
    def test_int_fields_zero_ok(self, field_name):
        obj = _cr(**{field_name: 0})
        assert getattr(obj, field_name) == 0

    @pytest.mark.parametrize("field_name", [
        "total_queries", "total_executions", "total_bundles",
        "total_violations", "total_matches", "total_results",
    ])
    def test_int_fields_negative_rejected(self, field_name):
        with pytest.raises(ValueError):
            _cr(**{field_name: -1})

    def test_closed_at_invalid(self):
        with pytest.raises(ValueError):
            _cr(closed_at="bad")

    def test_metadata_frozen(self):
        obj = _cr(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_to_dict(self):
        obj = _cr()
        d = obj.to_dict()
        assert d["report_id"] == "rpt1"
        assert d["total_queries"] == 10


# =========================================================================
# Cross-cutting edge cases
# =========================================================================


class TestEdgeCases:
    """Edge cases that span multiple dataclasses."""

    def test_unit_float_boundary_0(self):
        obj = _er(confidence=0.0)
        assert obj.confidence == 0.0

    def test_unit_float_boundary_1(self):
        obj = _er(confidence=1.0)
        assert obj.confidence == 1.0

    def test_unit_float_just_below_0(self):
        with pytest.raises(ValueError):
            _er(confidence=-0.001)

    def test_unit_float_just_above_1(self):
        with pytest.raises(ValueError):
            _er(confidence=1.001)

    def test_unit_float_mid(self):
        obj = _mr(relevance_score=0.5)
        assert obj.relevance_score == 0.5

    def test_non_negative_int_zero(self):
        obj = _qs(total_queries=0)
        assert obj.total_queries == 0

    def test_non_negative_int_large(self):
        obj = _qs(total_queries=999999)
        assert obj.total_queries == 999999

    def test_non_negative_int_minus_one(self):
        with pytest.raises(ValueError):
            _qs(total_queries=-1)

    def test_non_negative_float_zero(self):
        obj = _qer(execution_ms=0.0)
        assert obj.execution_ms == 0.0

    def test_non_negative_float_large(self):
        obj = _qer(execution_ms=1e6)
        assert obj.execution_ms == 1e6

    def test_non_negative_float_negative(self):
        with pytest.raises(ValueError):
            _qer(execution_ms=-0.001)

    def test_datetime_iso_with_timezone(self):
        obj = _kq(created_at="2025-06-01T12:00:00+05:30")
        assert obj.created_at == "2025-06-01T12:00:00+05:30"

    def test_datetime_iso_utc_z(self):
        obj = _kq(created_at="2025-06-01T00:00:00Z")
        assert obj.created_at == "2025-06-01T00:00:00Z"

    def test_datetime_plain_iso(self):
        obj = _kq(created_at="2025-06-01T00:00:00")
        assert obj.created_at == "2025-06-01T00:00:00"

    def test_metadata_empty_dict_becomes_mapping_proxy(self):
        obj = _kq(metadata={})
        assert isinstance(obj.metadata, MappingProxyType)

    def test_metadata_mutation_blocked(self):
        obj = _kq(metadata={"k": "v"})
        with pytest.raises(TypeError):
            obj.metadata["k2"] = "v2"

    def test_metadata_deeply_nested(self):
        obj = _kq(metadata={"a": {"b": {"c": [1, 2]}}})
        assert isinstance(obj.metadata["a"], MappingProxyType)
        assert isinstance(obj.metadata["a"]["b"], MappingProxyType)
        assert obj.metadata["a"]["b"]["c"] == (1, 2)

    def test_to_dict_metadata_thawed(self):
        obj = _kq(metadata={"items": [1, 2]})
        d = obj.to_dict()
        # thaw_value converts tuples back to lists, MappingProxy to dict
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["items"] == [1, 2]

    def test_whitespace_only_text_rejected(self):
        with pytest.raises(ValueError):
            _kq(query_id="   ")

    def test_non_empty_text_accepts_any_nonblank(self):
        obj = _kq(query_id="x")
        assert obj.query_id == "x"

    def test_scope_ref_id_empty_allowed_in_knowledge_query(self):
        # scope_ref_id has no require_non_empty_text in KnowledgeQuery
        obj = _kq(scope_ref_id="")
        assert obj.scope_ref_id == ""

    def test_search_text_empty_allowed_in_knowledge_query(self):
        # search_text has no require_non_empty_text in KnowledgeQuery
        obj = _kq(search_text="")
        assert obj.search_text == ""

    def test_multiple_instances_independent(self):
        a = _kq(query_id="a1")
        b = _kq(query_id="b1")
        assert a.query_id != b.query_id

    def test_frozen_setattr_on_every_dataclass(self):
        instances = [_kq(), _qf(), _er(), _mr(), _rr(), _qer(), _qs(), _qv(), _eb(), _cr()]
        for inst in instances:
            with pytest.raises(AttributeError):
                setattr(inst, list(inst.__dataclass_fields__.keys())[0], "x")

    def test_evidence_reference_scope_ref_id_empty_allowed(self):
        # scope_ref_id is not validated with require_non_empty_text
        obj = _er(scope_ref_id="")
        assert obj.scope_ref_id == ""

    def test_query_filter_field_value_empty_allowed(self):
        obj = _qf(field_value="")
        assert obj.field_value == ""


# =========================================================================
# Additional parametrized tests for broader coverage
# =========================================================================


class TestAllDataclassesToDict:
    """Ensure to_dict works for every dataclass."""

    def test_knowledge_query_to_dict_keys(self):
        d = _kq().to_dict()
        expected = {"query_id", "tenant_id", "scope", "scope_ref_id",
                    "search_text", "status", "max_results", "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_query_filter_to_dict_keys(self):
        d = _qf().to_dict()
        expected = {"filter_id", "query_id", "field_name", "field_value",
                    "evidence_kind", "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_evidence_reference_to_dict_keys(self):
        d = _er().to_dict()
        expected = {"reference_id", "source_id", "evidence_kind", "tenant_id",
                    "scope_ref_id", "title", "confidence", "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_match_record_to_dict_keys(self):
        d = _mr().to_dict()
        expected = {"match_id", "query_id", "reference_id", "disposition",
                    "relevance_score", "matched_at", "metadata"}
        assert set(d.keys()) == expected

    def test_ranked_result_to_dict_keys(self):
        d = _rr().to_dict()
        expected = {"result_id", "query_id", "reference_id", "rank",
                    "score", "ranking_strategy", "ranked_at", "metadata"}
        assert set(d.keys()) == expected

    def test_query_execution_record_to_dict_keys(self):
        d = _qer().to_dict()
        expected = {"execution_id", "query_id", "status", "total_matches",
                    "total_results", "execution_ms", "executed_at", "metadata"}
        assert set(d.keys()) == expected

    def test_query_snapshot_to_dict_keys(self):
        d = _qs().to_dict()
        expected = {"snapshot_id", "total_queries", "total_filters",
                    "total_references", "total_matches", "total_results",
                    "total_executions", "total_bundles", "total_violations",
                    "captured_at", "metadata"}
        assert set(d.keys()) == expected

    def test_query_violation_to_dict_keys(self):
        d = _qv().to_dict()
        expected = {"violation_id", "tenant_id", "query_id", "operation",
                    "reason", "detected_at", "metadata"}
        assert set(d.keys()) == expected

    def test_evidence_bundle_to_dict_keys(self):
        d = _eb().to_dict()
        expected = {"bundle_id", "query_id", "tenant_id", "title",
                    "evidence_count", "confidence", "assembled_at", "metadata"}
        assert set(d.keys()) == expected

    def test_closure_report_to_dict_keys(self):
        d = _cr().to_dict()
        expected = {"report_id", "tenant_id", "total_queries", "total_executions",
                    "total_bundles", "total_violations", "total_matches",
                    "total_results", "closed_at", "metadata"}
        assert set(d.keys()) == expected


class TestEnumPreservationInToDict:
    """Verify every enum field is preserved as enum object in to_dict()."""

    def test_kq_scope_preserved(self):
        assert isinstance(_kq().to_dict()["scope"], QueryScope)

    def test_kq_status_preserved(self):
        assert isinstance(_kq().to_dict()["status"], QueryStatus)

    def test_qf_evidence_kind_preserved(self):
        assert isinstance(_qf().to_dict()["evidence_kind"], EvidenceKind)

    def test_er_evidence_kind_preserved(self):
        assert isinstance(_er().to_dict()["evidence_kind"], EvidenceKind)

    def test_mr_disposition_preserved(self):
        assert isinstance(_mr().to_dict()["disposition"], MatchDisposition)

    def test_rr_ranking_strategy_preserved(self):
        assert isinstance(_rr().to_dict()["ranking_strategy"], RankingStrategy)

    def test_qer_status_preserved(self):
        assert isinstance(_qer().to_dict()["status"], QueryResultStatus)


class TestImmutabilityAllDataclasses:
    """Frozen check on every single field of every dataclass."""

    @pytest.mark.parametrize("field_name", [
        "query_id", "tenant_id", "scope", "scope_ref_id",
        "search_text", "status", "max_results", "created_at", "metadata",
    ])
    def test_knowledge_query_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_kq(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "filter_id", "query_id", "field_name", "field_value",
        "evidence_kind", "created_at", "metadata",
    ])
    def test_query_filter_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_qf(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "reference_id", "source_id", "evidence_kind", "tenant_id",
        "scope_ref_id", "title", "confidence", "created_at", "metadata",
    ])
    def test_evidence_reference_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_er(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "match_id", "query_id", "reference_id", "disposition",
        "relevance_score", "matched_at", "metadata",
    ])
    def test_match_record_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_mr(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "result_id", "query_id", "reference_id", "rank",
        "score", "ranking_strategy", "ranked_at", "metadata",
    ])
    def test_ranked_result_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_rr(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "execution_id", "query_id", "status", "total_matches",
        "total_results", "execution_ms", "executed_at", "metadata",
    ])
    def test_query_execution_record_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_qer(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "snapshot_id", "total_queries", "total_filters", "total_references",
        "total_matches", "total_results", "total_executions",
        "total_bundles", "total_violations", "captured_at", "metadata",
    ])
    def test_query_snapshot_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_qs(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "violation_id", "tenant_id", "query_id", "operation",
        "reason", "detected_at", "metadata",
    ])
    def test_query_violation_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_qv(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "bundle_id", "query_id", "tenant_id", "title",
        "evidence_count", "confidence", "assembled_at", "metadata",
    ])
    def test_evidence_bundle_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_eb(), field_name, "x")

    @pytest.mark.parametrize("field_name", [
        "report_id", "tenant_id", "total_queries", "total_executions",
        "total_bundles", "total_violations", "total_matches",
        "total_results", "closed_at", "metadata",
    ])
    def test_closure_report_frozen_fields(self, field_name):
        with pytest.raises(AttributeError):
            setattr(_cr(), field_name, "x")
