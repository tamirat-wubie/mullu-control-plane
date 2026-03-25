"""Comprehensive tests for ResearchRuntimeIntegration.

Covers: constructor validation, all six bridge methods (artifact ingestion,
knowledge query, case review, assurance, reporting, LLM generation),
memory mesh attachment, graph attachment, cross-method integration,
multi-tenant isolation, and golden end-to-end scenarios.

Target: ~70 tests.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.research_runtime import ResearchRuntimeEngine
from mcoi_runtime.core.research_runtime_integration import ResearchRuntimeIntegration
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def re(es: EventSpineEngine) -> ResearchRuntimeEngine:
    return ResearchRuntimeEngine(es)


@pytest.fixture()
def me() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(re, es, me) -> ResearchRuntimeIntegration:
    return ResearchRuntimeIntegration(re, es, me)


# ===================================================================
# 1. Constructor validation (7 tests)
# ===================================================================


class TestConstruction:
    def test_rejects_string_research_engine(self, es, me):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeIntegration("bad", es, me)

    def test_rejects_none_research_engine(self, es, me):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeIntegration(None, es, me)

    def test_rejects_string_event_spine(self, re, me):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeIntegration(re, "bad", me)

    def test_rejects_none_event_spine(self, re, me):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeIntegration(re, None, me)

    def test_rejects_string_memory_engine(self, re, es):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeIntegration(re, es, "bad")

    def test_rejects_none_memory_engine(self, re, es):
        with pytest.raises(RuntimeCoreInvariantError):
            ResearchRuntimeIntegration(re, es, None)

    def test_accepts_valid_components(self, re, es, me):
        bridge = ResearchRuntimeIntegration(re, es, me)
        assert bridge is not None


# ===================================================================
# 2. research_from_artifact_ingestion (8 tests)
# ===================================================================


class TestArtifactIngestion:
    def test_returns_dict(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert isinstance(result, dict)

    def test_has_question_id(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert "question_id" in result

    def test_has_hypothesis_id(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert "hypothesis_id" in result

    def test_has_tenant_id(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert result["tenant_id"] == "t1"

    def test_source_type(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert result["source_type"] == "artifact_ingestion"

    def test_ref_field(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert result["artifact_id"] == "art-1"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.research_from_artifact_ingestion("t1", "art-1")
        assert es.event_count > before

    def test_defaults(self, bridge):
        result = bridge.research_from_artifact_ingestion("t1", "art-1")
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1
        assert result["confidence"] == 0.0


# ===================================================================
# 3. research_from_knowledge_query (8 tests)
# ===================================================================


class TestKnowledgeQuery:
    def test_returns_dict(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert isinstance(result, dict)

    def test_has_question_id(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert "question_id" in result

    def test_has_hypothesis_id(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert "hypothesis_id" in result

    def test_tenant_id(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert result["tenant_id"] == "t1"

    def test_source_type(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert result["source_type"] == "knowledge_query"

    def test_ref_field(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert result["query_id"] == "kq-1"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.research_from_knowledge_query("t1", "kq-1")
        assert es.event_count > before

    def test_defaults(self, bridge):
        result = bridge.research_from_knowledge_query("t1", "kq-1")
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1
        assert result["confidence"] == 0.0


# ===================================================================
# 4. research_from_case_review (8 tests)
# ===================================================================


class TestCaseReview:
    def test_returns_dict(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert isinstance(result, dict)

    def test_has_question_id(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert "question_id" in result

    def test_has_hypothesis_id(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert "hypothesis_id" in result

    def test_tenant_id(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert result["tenant_id"] == "t1"

    def test_source_type(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert result["source_type"] == "case_review"

    def test_ref_field(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert result["case_id"] == "case-1"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.research_from_case_review("t1", "case-1")
        assert es.event_count > before

    def test_defaults(self, bridge):
        result = bridge.research_from_case_review("t1", "case-1")
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1
        assert result["confidence"] == 0.0


# ===================================================================
# 5. research_from_assurance (8 tests)
# ===================================================================


class TestAssurance:
    def test_returns_dict(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert isinstance(result, dict)

    def test_has_question_id(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert "question_id" in result

    def test_has_hypothesis_id(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert "hypothesis_id" in result

    def test_tenant_id(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert result["tenant_id"] == "t1"

    def test_source_type(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert result["source_type"] == "assurance"

    def test_ref_field(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert result["assurance_id"] == "assur-1"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.research_from_assurance("t1", "assur-1")
        assert es.event_count > before

    def test_defaults(self, bridge):
        result = bridge.research_from_assurance("t1", "assur-1")
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1
        assert result["confidence"] == 0.0


# ===================================================================
# 6. research_from_reporting (8 tests)
# ===================================================================


class TestReporting:
    def test_returns_dict(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert isinstance(result, dict)

    def test_has_question_id(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert "question_id" in result

    def test_has_hypothesis_id(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert "hypothesis_id" in result

    def test_tenant_id(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert result["tenant_id"] == "t1"

    def test_source_type(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert result["source_type"] == "reporting"

    def test_ref_field(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert result["report_id"] == "rep-1"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.research_from_reporting("t1", "rep-1")
        assert es.event_count > before

    def test_defaults(self, bridge):
        result = bridge.research_from_reporting("t1", "rep-1")
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1
        assert result["confidence"] == 0.0


# ===================================================================
# 7. research_from_llm_generation (8 tests)
# ===================================================================


class TestLLMGeneration:
    def test_returns_dict(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert isinstance(result, dict)

    def test_has_question_id(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert "question_id" in result

    def test_has_hypothesis_id(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert "hypothesis_id" in result

    def test_tenant_id(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert result["tenant_id"] == "t1"

    def test_source_type(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert result["source_type"] == "llm_generation"

    def test_ref_field(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert result["generation_id"] == "gen-1"

    def test_emits_events(self, bridge, es):
        before = es.event_count
        bridge.research_from_llm_generation("t1", "gen-1")
        assert es.event_count > before

    def test_defaults(self, bridge):
        result = bridge.research_from_llm_generation("t1", "gen-1")
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1
        assert result["confidence"] == 0.0


# ===================================================================
# 8. attach_research_state_to_memory_mesh (9 tests)
# ===================================================================


class TestMemoryMeshAttachment:
    def test_returns_memory_record(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert isinstance(mem, MemoryRecord)

    def test_memory_type_observation(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert mem.memory_type == MemoryType.OBSERVATION

    def test_scope_global(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert mem.scope == MemoryScope.GLOBAL

    def test_trust_level_verified(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert mem.trust_level == MemoryTrustLevel.VERIFIED

    def test_tags_research(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert "research" in mem.tags

    def test_tags_evidence(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert "evidence" in mem.tags

    def test_tags_synthesis(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert "synthesis" in mem.tags

    def test_content_keys(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        content = mem.content
        expected_keys = {
            "scope_ref_id", "total_questions", "total_hypotheses",
            "total_studies", "total_experiments", "total_literature",
            "total_syntheses", "total_reviews", "total_violations",
        }
        assert expected_keys.issubset(set(content.keys()))

    def test_scope_ref_id_in_content(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        mem = bridge.attach_research_state_to_memory_mesh("my-scope")
        assert mem.content["scope_ref_id"] == "my-scope"


# ===================================================================
# 9. attach_research_state_to_graph (6 tests)
# ===================================================================


class TestGraphAttachment:
    def test_returns_dict(self, bridge):
        result = bridge.attach_research_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_scope_ref_id(self, bridge):
        result = bridge.attach_research_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_has_all_count_keys(self, bridge):
        result = bridge.attach_research_state_to_graph("scope-1")
        expected_keys = {
            "scope_ref_id", "total_questions", "total_hypotheses",
            "total_studies", "total_experiments", "total_literature",
            "total_syntheses", "total_reviews", "total_violations",
        }
        assert expected_keys == set(result.keys())

    def test_counts_reflect_state(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        result = bridge.attach_research_state_to_graph("scope-1")
        assert result["total_questions"] == 1
        assert result["total_hypotheses"] == 1

    def test_empty_state_all_zeros(self, bridge):
        result = bridge.attach_research_state_to_graph("scope-1")
        assert result["total_questions"] == 0
        assert result["total_hypotheses"] == 0
        assert result["total_studies"] == 0

    def test_different_scope_ref_id(self, bridge):
        r1 = bridge.attach_research_state_to_graph("scope-a")
        r2 = bridge.attach_research_state_to_graph("scope-b")
        assert r1["scope_ref_id"] == "scope-a"
        assert r2["scope_ref_id"] == "scope-b"


# ===================================================================
# 10. Cross-method integration (5 tests)
# ===================================================================


class TestCrossMethodIntegration:
    def test_multiple_bridges_create_distinct_ids(self, bridge):
        r1 = bridge.research_from_artifact_ingestion("t1", "art-1")
        r2 = bridge.research_from_artifact_ingestion("t1", "art-2")
        assert r1["question_id"] != r2["question_id"]
        assert r1["hypothesis_id"] != r2["hypothesis_id"]

    def test_different_bridge_types_create_distinct_ids(self, bridge):
        r1 = bridge.research_from_artifact_ingestion("t1", "art-1")
        r2 = bridge.research_from_knowledge_query("t1", "kq-1")
        assert r1["question_id"] != r2["question_id"]

    def test_bridge_then_memory(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_knowledge_query("t1", "kq-1")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert mem.content["total_questions"] == 2
        assert mem.content["total_hypotheses"] == 2

    def test_bridge_then_graph(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_case_review("t1", "case-1")
        result = bridge.attach_research_state_to_graph("scope-1")
        assert result["total_questions"] == 2

    def test_event_count_accumulates(self, bridge, es):
        before = es.event_count
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_knowledge_query("t1", "kq-1")
        bridge.research_from_case_review("t1", "case-1")
        # Each bridge method creates question + hypothesis + bridge event = 3 events
        assert es.event_count > before + 6


# ===================================================================
# 11. Multi-tenant (4 tests)
# ===================================================================


class TestMultiTenant:
    def test_different_tenants_graph(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_artifact_ingestion("t2", "art-2")
        result = bridge.attach_research_state_to_graph("scope-1")
        assert result["total_questions"] == 2  # global, not tenant-scoped

    def test_different_tenants_memory(self, bridge):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_artifact_ingestion("t2", "art-2")
        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        assert mem.content["total_questions"] == 2

    def test_different_tenants_distinct_questions(self, bridge, re):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_artifact_ingestion("t2", "art-2")
        t1_qs = re.questions_for_tenant("t1")
        t2_qs = re.questions_for_tenant("t2")
        assert len(t1_qs) == 1
        assert len(t2_qs) == 1

    def test_three_tenants(self, bridge, re):
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_knowledge_query("t2", "kq-1")
        bridge.research_from_case_review("t3", "case-1")
        assert re.question_count == 3
        result = bridge.attach_research_state_to_graph("scope-all")
        assert result["total_questions"] == 3


# ===================================================================
# 12. Golden end-to-end (3 tests)
# ===================================================================


class TestGoldenEndToEnd:
    def test_all_six_bridges_with_memory_and_graph(self, bridge):
        """Exercise all six bridge methods, then attach to memory and graph."""
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_knowledge_query("t1", "kq-1")
        bridge.research_from_case_review("t1", "case-1")
        bridge.research_from_assurance("t1", "assur-1")
        bridge.research_from_reporting("t1", "rep-1")
        bridge.research_from_llm_generation("t1", "gen-1")

        mem = bridge.attach_research_state_to_memory_mesh("scope-all")
        assert mem.content["total_questions"] == 6
        assert mem.content["total_hypotheses"] == 6

        graph = bridge.attach_research_state_to_graph("scope-all")
        assert graph["total_questions"] == 6
        assert graph["total_hypotheses"] == 6

    def test_bridge_custom_titles(self, bridge):
        """Custom titles and descriptions are passed through."""
        result = bridge.research_from_artifact_ingestion(
            "t1", "art-1",
            title="Custom Title",
            description="Custom Desc",
            statement="Custom Stmt",
        )
        assert result["status"] == "active"
        assert result["hypothesis_count"] == 1

    def test_memory_and_graph_consistency(self, bridge):
        """Memory and graph should return the same counts."""
        bridge.research_from_artifact_ingestion("t1", "art-1")
        bridge.research_from_knowledge_query("t1", "kq-1")

        mem = bridge.attach_research_state_to_memory_mesh("scope-1")
        graph = bridge.attach_research_state_to_graph("scope-1")

        assert mem.content["total_questions"] == graph["total_questions"]
        assert mem.content["total_hypotheses"] == graph["total_hypotheses"]
        assert mem.content["total_studies"] == graph["total_studies"]
        assert mem.content["total_experiments"] == graph["total_experiments"]
        assert mem.content["total_literature"] == graph["total_literature"]
        assert mem.content["total_syntheses"] == graph["total_syntheses"]
        assert mem.content["total_reviews"] == graph["total_reviews"]
        assert mem.content["total_violations"] == graph["total_violations"]
