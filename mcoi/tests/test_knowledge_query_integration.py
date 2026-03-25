"""Purpose: comprehensive tests for KnowledgeQueryIntegration bridge.
Governance scope: validates constructor validation, all 6 query methods,
    memory mesh attachment, graph attachment, event emission, and sequencing.
Dependencies: pytest, mcoi_runtime core engines and contracts.
Invariants: tests are isolated per function; each test builds its own fixtures.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.knowledge_query_integration import KnowledgeQueryIntegration
from mcoi_runtime.core.knowledge_query import KnowledgeQueryEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.contracts.knowledge_query import EvidenceKind, QueryScope, RankingStrategy
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engines():
    """Create a fresh set of engines for testing."""
    es = EventSpineEngine()
    qe = KnowledgeQueryEngine(es)
    me = MemoryMeshEngine()
    return qe, es, me


def _make_bridge():
    """Create a fresh integration bridge with its engines."""
    qe, es, me = _make_engines()
    bridge = KnowledgeQueryIntegration(qe, es, me)
    return bridge, qe, es, me


def _seed_evidence(qe: KnowledgeQueryEngine, tenant_id: str, scope_ref_id: str, count: int = 3):
    """Register evidence so queries have something to find."""
    for i in range(count):
        qe.register_evidence(
            reference_id=f"ref-{scope_ref_id}-{i}",
            source_id=f"src-{scope_ref_id}-{i}",
            tenant_id=tenant_id,
            evidence_kind=EvidenceKind.RECORD,
            scope_ref_id=scope_ref_id,
            title=f"Evidence {scope_ref_id} item {i}",
            confidence=0.8,
        )


def _event_count(es: EventSpineEngine) -> int:
    """Return total events emitted."""
    return len(es._events)


# ===================================================================
# Constructor validation tests
# ===================================================================


class TestConstructorValidation:
    """Tests that constructor validates all three engine arguments."""

    def test_valid_construction(self):
        bridge, _, _, _ = _make_bridge()
        assert isinstance(bridge, KnowledgeQueryIntegration)

    def test_query_engine_wrong_type_none(self):
        _, es, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(None, es, me)

    def test_query_engine_wrong_type_string(self):
        _, es, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration("not_an_engine", es, me)

    def test_query_engine_wrong_type_int(self):
        _, es, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(42, es, me)

    def test_event_spine_wrong_type_none(self):
        qe, _, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(qe, None, me)

    def test_event_spine_wrong_type_string(self):
        qe, _, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(qe, "not_an_engine", me)

    def test_event_spine_wrong_type_dict(self):
        qe, _, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(qe, {}, me)

    def test_memory_engine_wrong_type_none(self):
        qe, es, _ = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(qe, es, None)

    def test_memory_engine_wrong_type_string(self):
        qe, es, _ = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(qe, es, "not_an_engine")

    def test_memory_engine_wrong_type_list(self):
        qe, es, _ = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(qe, es, [])

    def test_all_wrong_types(self):
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration("a", "b", "c")

    def test_swapped_engines_query_and_spine(self):
        qe, es, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(es, qe, me)

    def test_swapped_engines_query_and_memory(self):
        qe, es, me = _make_engines()
        with pytest.raises(RuntimeCoreInvariantError):
            KnowledgeQueryIntegration(me, es, qe)


# ===================================================================
# query_for_case_review tests
# ===================================================================


class TestQueryForCaseReview:
    """Tests for the case review query method."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-001")
        result = bridge.query_for_case_review("q1", "e1", "t1", "case-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-002")
        result = bridge.query_for_case_review("q2", "e2", "t1", "case-002")
        expected_keys = {"query_id", "execution_id", "tenant_id", "case_ref",
                         "total_matches", "total_results", "status", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-003")
        result = bridge.query_for_case_review("q3", "e3", "t1", "case-003")
        assert result["source_type"] == "case_review"

    def test_ref_field_name(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-004")
        result = bridge.query_for_case_review("q4", "e4", "t1", "case-004")
        assert result["case_ref"] == "case-004"

    def test_ids_match(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-005")
        result = bridge.query_for_case_review("q5", "e5", "t1", "case-005")
        assert result["query_id"] == "q5"
        assert result["execution_id"] == "e5"
        assert result["tenant_id"] == "t1"

    def test_with_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-006")
        result = bridge.query_for_case_review("q6", "e6", "t1", "case-006",
                                               search_text="Evidence")
        assert result["source_type"] == "case_review"
        assert result["total_matches"] >= 0

    def test_without_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-007")
        result = bridge.query_for_case_review("q7", "e7", "t1", "case-007")
        assert result["source_type"] == "case_review"

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-008")
        before = _event_count(es)
        bridge.query_for_case_review("q8", "e8", "t1", "case-008")
        after = _event_count(es)
        assert after > before

    def test_total_matches_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "case-009")
        result = bridge.query_for_case_review("q9", "e9", "t1", "case-009")
        assert isinstance(result["total_matches"], int)
        assert isinstance(result["total_results"], int)


# ===================================================================
# query_for_regulatory_package tests
# ===================================================================


class TestQueryForRegulatoryPackage:
    """Tests for the regulatory package query method."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-001")
        result = bridge.query_for_regulatory_package("q1", "e1", "t1", "sub-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-002")
        result = bridge.query_for_regulatory_package("q2", "e2", "t1", "sub-002")
        expected_keys = {"query_id", "execution_id", "tenant_id", "submission_ref",
                         "total_matches", "total_results", "status", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-003")
        result = bridge.query_for_regulatory_package("q3", "e3", "t1", "sub-003")
        assert result["source_type"] == "regulatory_package"

    def test_ref_field_name(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-004")
        result = bridge.query_for_regulatory_package("q4", "e4", "t1", "sub-004")
        assert result["submission_ref"] == "sub-004"

    def test_with_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-005")
        result = bridge.query_for_regulatory_package("q5", "e5", "t1", "sub-005",
                                                      search_text="Evidence")
        assert result["source_type"] == "regulatory_package"

    def test_without_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-006")
        result = bridge.query_for_regulatory_package("q6", "e6", "t1", "sub-006")
        assert result["source_type"] == "regulatory_package"

    def test_default_max_results_100(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-007")
        result = bridge.query_for_regulatory_package("q7", "e7", "t1", "sub-007")
        # Just verify it executes without error with the default 100
        assert result["status"] is not None

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "sub-008")
        before = _event_count(es)
        bridge.query_for_regulatory_package("q8", "e8", "t1", "sub-008")
        after = _event_count(es)
        assert after > before


# ===================================================================
# query_for_remediation_verification tests
# ===================================================================


class TestQueryForRemediationVerification:
    """Tests for the remediation verification query method."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-001")
        result = bridge.query_for_remediation_verification("q1", "e1", "t1", "rem-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-002")
        result = bridge.query_for_remediation_verification("q2", "e2", "t1", "rem-002")
        expected_keys = {"query_id", "execution_id", "tenant_id", "remediation_ref",
                         "total_matches", "total_results", "status", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-003")
        result = bridge.query_for_remediation_verification("q3", "e3", "t1", "rem-003")
        assert result["source_type"] == "remediation_verification"

    def test_ref_field_name(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-004")
        result = bridge.query_for_remediation_verification("q4", "e4", "t1", "rem-004")
        assert result["remediation_ref"] == "rem-004"

    def test_with_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-005")
        result = bridge.query_for_remediation_verification("q5", "e5", "t1", "rem-005",
                                                            search_text="Evidence")
        assert result["source_type"] == "remediation_verification"

    def test_without_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-006")
        result = bridge.query_for_remediation_verification("q6", "e6", "t1", "rem-006")
        assert result["source_type"] == "remediation_verification"

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "rem-007")
        before = _event_count(es)
        bridge.query_for_remediation_verification("q7", "e7", "t1", "rem-007")
        after = _event_count(es)
        assert after > before


# ===================================================================
# query_for_assurance_decision tests
# ===================================================================


class TestQueryForAssuranceDecision:
    """Tests for the assurance decision query method."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-001")
        result = bridge.query_for_assurance_decision("q1", "e1", "t1", "asr-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-002")
        result = bridge.query_for_assurance_decision("q2", "e2", "t1", "asr-002")
        expected_keys = {"query_id", "execution_id", "tenant_id", "assurance_ref",
                         "total_matches", "total_results", "status", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-003")
        result = bridge.query_for_assurance_decision("q3", "e3", "t1", "asr-003")
        assert result["source_type"] == "assurance_decision"

    def test_ref_field_name(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-004")
        result = bridge.query_for_assurance_decision("q4", "e4", "t1", "asr-004")
        assert result["assurance_ref"] == "asr-004"

    def test_with_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-005")
        result = bridge.query_for_assurance_decision("q5", "e5", "t1", "asr-005",
                                                      search_text="Evidence")
        assert result["source_type"] == "assurance_decision"

    def test_without_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-006")
        result = bridge.query_for_assurance_decision("q6", "e6", "t1", "asr-006")
        assert result["source_type"] == "assurance_decision"

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "asr-007")
        before = _event_count(es)
        bridge.query_for_assurance_decision("q7", "e7", "t1", "asr-007")
        after = _event_count(es)
        assert after > before


# ===================================================================
# query_for_executive_control tests
# ===================================================================


class TestQueryForExecutiveControl:
    """Tests for the executive control query method."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-001")
        result = bridge.query_for_executive_control("q1", "e1", "t1", "dir-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-002")
        result = bridge.query_for_executive_control("q2", "e2", "t1", "dir-002")
        expected_keys = {"query_id", "execution_id", "tenant_id", "directive_ref",
                         "total_matches", "total_results", "status", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-003")
        result = bridge.query_for_executive_control("q3", "e3", "t1", "dir-003")
        assert result["source_type"] == "executive_control"

    def test_ref_field_name(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-004")
        result = bridge.query_for_executive_control("q4", "e4", "t1", "dir-004")
        assert result["directive_ref"] == "dir-004"

    def test_with_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-005")
        result = bridge.query_for_executive_control("q5", "e5", "t1", "dir-005",
                                                     search_text="Evidence")
        assert result["source_type"] == "executive_control"

    def test_without_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-006")
        result = bridge.query_for_executive_control("q6", "e6", "t1", "dir-006")
        assert result["source_type"] == "executive_control"

    def test_uses_program_scope(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-007")
        bridge.query_for_executive_control("q7", "e7", "t1", "dir-007")
        query = qe.get_query("q7")
        assert query.scope == QueryScope.PROGRAM

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "dir-008")
        before = _event_count(es)
        bridge.query_for_executive_control("q8", "e8", "t1", "dir-008")
        after = _event_count(es)
        assert after > before


# ===================================================================
# query_for_service_request tests
# ===================================================================


class TestQueryForServiceRequest:
    """Tests for the service request query method."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-001")
        result = bridge.query_for_service_request("q1", "e1", "t1", "svc-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-002")
        result = bridge.query_for_service_request("q2", "e2", "t1", "svc-002")
        expected_keys = {"query_id", "execution_id", "tenant_id", "service_ref",
                         "total_matches", "total_results", "status", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-003")
        result = bridge.query_for_service_request("q3", "e3", "t1", "svc-003")
        assert result["source_type"] == "service_request"

    def test_ref_field_name(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-004")
        result = bridge.query_for_service_request("q4", "e4", "t1", "svc-004")
        assert result["service_ref"] == "svc-004"

    def test_uses_service_scope(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-005")
        bridge.query_for_service_request("q5", "e5", "t1", "svc-005")
        query = qe.get_query("q5")
        assert query.scope == QueryScope.SERVICE

    def test_with_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-006")
        result = bridge.query_for_service_request("q6", "e6", "t1", "svc-006",
                                                   search_text="Evidence")
        assert result["source_type"] == "service_request"

    def test_without_search_text(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-007")
        result = bridge.query_for_service_request("q7", "e7", "t1", "svc-007")
        assert result["source_type"] == "service_request"

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "svc-008")
        before = _event_count(es)
        bridge.query_for_service_request("q8", "e8", "t1", "svc-008")
        after = _event_count(es)
        assert after > before


# ===================================================================
# attach_query_state_to_memory_mesh tests
# ===================================================================


class TestAttachQueryStateToMemoryMesh:
    """Tests for memory mesh attachment."""

    def test_returns_memory_record(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-001")
        assert isinstance(result, MemoryRecord)

    def test_memory_record_tags(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-002")
        assert "knowledge_query" in result.tags
        assert "evidence" in result.tags
        assert "retrieval" in result.tags

    def test_memory_record_title(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-003")
        assert "scope-003" in result.title

    def test_memory_record_scope_ref_id(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-004")
        assert result.scope_ref_id == "scope-004"

    def test_memory_record_content_keys(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-005")
        content = result.content
        expected_content_keys = {"scope_ref_id", "total_queries", "total_filters",
                                 "total_references", "total_matches", "total_results",
                                 "total_executions", "total_bundles", "total_violations"}
        assert set(content.keys()) == expected_content_keys

    def test_memory_record_added_to_mesh(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-006")
        retrieved = me.get_memory(result.memory_id)
        assert retrieved.memory_id == result.memory_id

    def test_emits_event(self):
        bridge, qe, es, me = _make_bridge()
        before = _event_count(es)
        bridge.attach_query_state_to_memory_mesh("scope-007")
        after = _event_count(es)
        assert after > before

    def test_content_reflects_zero_state(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_memory_mesh("scope-008")
        assert result.content["total_queries"] == 0
        assert result.content["total_filters"] == 0

    def test_content_reflects_queries_after_use(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "scope-009")
        bridge.query_for_case_review("q1", "e1", "t1", "scope-009")
        result = bridge.attach_query_state_to_memory_mesh("scope-009")
        assert result.content["total_queries"] == 1
        assert result.content["total_executions"] == 1


# ===================================================================
# attach_query_state_to_graph tests
# ===================================================================


class TestAttachQueryStateToGraph:
    """Tests for graph attachment."""

    def test_returns_dict(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_graph("scope-001")
        assert isinstance(result, dict)

    def test_correct_keys(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_graph("scope-002")
        expected_keys = {"scope_ref_id", "total_queries", "total_filters",
                         "total_references", "total_matches", "total_results",
                         "total_executions", "total_bundles", "total_violations"}
        assert set(result.keys()) == expected_keys

    def test_scope_ref_id_matches(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_graph("scope-003")
        assert result["scope_ref_id"] == "scope-003"

    def test_zero_state(self):
        bridge, qe, es, me = _make_bridge()
        result = bridge.attach_query_state_to_graph("scope-004")
        assert result["total_queries"] == 0
        assert result["total_filters"] == 0
        assert result["total_references"] == 0
        assert result["total_matches"] == 0
        assert result["total_results"] == 0
        assert result["total_executions"] == 0
        assert result["total_bundles"] == 0
        assert result["total_violations"] == 0

    def test_reflects_queries_after_use(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "scope-005")
        bridge.query_for_case_review("q1", "e1", "t1", "scope-005")
        result = bridge.attach_query_state_to_graph("scope-005")
        assert result["total_queries"] == 1
        assert result["total_executions"] == 1
        assert result["total_references"] == 3  # _seed_evidence creates 3

    def test_reflects_evidence_count(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "scope-006", count=5)
        result = bridge.attach_query_state_to_graph("scope-006")
        assert result["total_references"] == 5


# ===================================================================
# Event emission tests
# ===================================================================


class TestEventEmission:
    """Tests for event emission across bridge methods."""

    def test_case_review_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "ev-001")
        before = _event_count(es)
        bridge.query_for_case_review("q1", "e1", "t1", "ev-001")
        assert _event_count(es) > before

    def test_regulatory_package_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "ev-002")
        before = _event_count(es)
        bridge.query_for_regulatory_package("q2", "e2", "t1", "ev-002")
        assert _event_count(es) > before

    def test_remediation_verification_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "ev-003")
        before = _event_count(es)
        bridge.query_for_remediation_verification("q3", "e3", "t1", "ev-003")
        assert _event_count(es) > before

    def test_assurance_decision_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "ev-004")
        before = _event_count(es)
        bridge.query_for_assurance_decision("q4", "e4", "t1", "ev-004")
        assert _event_count(es) > before

    def test_executive_control_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "ev-005")
        before = _event_count(es)
        bridge.query_for_executive_control("q5", "e5", "t1", "ev-005")
        assert _event_count(es) > before

    def test_service_request_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "ev-006")
        before = _event_count(es)
        bridge.query_for_service_request("q6", "e6", "t1", "ev-006")
        assert _event_count(es) > before

    def test_memory_mesh_attachment_increases_events(self):
        bridge, qe, es, me = _make_bridge()
        before = _event_count(es)
        bridge.attach_query_state_to_memory_mesh("ev-007")
        assert _event_count(es) > before


# ===================================================================
# Multiple queries in sequence tests
# ===================================================================


class TestMultipleQueriesInSequence:
    """Tests for running multiple queries sequentially."""

    def test_two_case_reviews(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "seq-001")
        _seed_evidence(qe, "t1", "seq-002")
        r1 = bridge.query_for_case_review("q1", "e1", "t1", "seq-001")
        r2 = bridge.query_for_case_review("q2", "e2", "t1", "seq-002")
        assert r1["query_id"] != r2["query_id"]
        assert r1["source_type"] == r2["source_type"] == "case_review"

    def test_mixed_query_types(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "mix-001")
        _seed_evidence(qe, "t1", "mix-002")
        _seed_evidence(qe, "t1", "mix-003")
        r1 = bridge.query_for_case_review("q1", "e1", "t1", "mix-001")
        r2 = bridge.query_for_regulatory_package("q2", "e2", "t1", "mix-002")
        r3 = bridge.query_for_remediation_verification("q3", "e3", "t1", "mix-003")
        assert r1["source_type"] == "case_review"
        assert r2["source_type"] == "regulatory_package"
        assert r3["source_type"] == "remediation_verification"

    def test_all_six_query_types_in_sequence(self):
        bridge, qe, es, me = _make_bridge()
        for i in range(6):
            _seed_evidence(qe, "t1", f"all-{i}")
        r1 = bridge.query_for_case_review("q1", "e1", "t1", "all-0")
        r2 = bridge.query_for_regulatory_package("q2", "e2", "t1", "all-1")
        r3 = bridge.query_for_remediation_verification("q3", "e3", "t1", "all-2")
        r4 = bridge.query_for_assurance_decision("q4", "e4", "t1", "all-3")
        r5 = bridge.query_for_executive_control("q5", "e5", "t1", "all-4")
        r6 = bridge.query_for_service_request("q6", "e6", "t1", "all-5")
        source_types = {r["source_type"] for r in [r1, r2, r3, r4, r5, r6]}
        assert len(source_types) == 6

    def test_graph_state_after_multiple_queries(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "gstate-001")
        _seed_evidence(qe, "t1", "gstate-002")
        bridge.query_for_case_review("q1", "e1", "t1", "gstate-001")
        bridge.query_for_regulatory_package("q2", "e2", "t1", "gstate-002")
        graph = bridge.attach_query_state_to_graph("gstate-all")
        assert graph["total_queries"] == 2
        assert graph["total_executions"] == 2

    def test_memory_mesh_state_after_multiple_queries(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "mstate-001")
        _seed_evidence(qe, "t1", "mstate-002")
        bridge.query_for_case_review("q1", "e1", "t1", "mstate-001")
        bridge.query_for_service_request("q2", "e2", "t1", "mstate-002")
        mem = bridge.attach_query_state_to_memory_mesh("mstate-all")
        assert mem.content["total_queries"] == 2
        assert mem.content["total_executions"] == 2

    def test_event_count_grows_with_each_query(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "grow-001")
        _seed_evidence(qe, "t1", "grow-002")
        _seed_evidence(qe, "t1", "grow-003")
        c0 = _event_count(es)
        bridge.query_for_case_review("q1", "e1", "t1", "grow-001")
        c1 = _event_count(es)
        bridge.query_for_regulatory_package("q2", "e2", "t1", "grow-002")
        c2 = _event_count(es)
        bridge.query_for_executive_control("q3", "e3", "t1", "grow-003")
        c3 = _event_count(es)
        assert c1 > c0
        assert c2 > c1
        assert c3 > c2

    def test_different_tenants(self):
        bridge, qe, es, me = _make_bridge()
        _seed_evidence(qe, "t1", "tenant-001")
        _seed_evidence(qe, "t2", "tenant-002")
        r1 = bridge.query_for_case_review("q1", "e1", "t1", "tenant-001")
        r2 = bridge.query_for_case_review("q2", "e2", "t2", "tenant-002")
        assert r1["tenant_id"] == "t1"
        assert r2["tenant_id"] == "t2"
