"""Comprehensive tests for the MemoryConsolidationIntegration bridge.

Tests cover: construction validation, surface-specific consolidation methods,
memory mesh attachment, graph attachment, event emission, cross-source
consolidation, and golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.memory_consolidation import (
    ConsolidationStatus,
    MemoryImportance,
    PersonalizationScope,
    RetentionDisposition,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_consolidation import MemoryConsolidationEngine
from mcoi_runtime.core.memory_consolidation_integration import MemoryConsolidationIntegration
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def clock():
    return FixedClock("2026-01-01T00:00:00+00:00")


@pytest.fixture()
def consolidation_engine(es, clock):
    return MemoryConsolidationEngine(es, clock=clock)


@pytest.fixture()
def memory_engine():
    return MemoryMeshEngine()


@pytest.fixture()
def integration(consolidation_engine, es, memory_engine):
    return MemoryConsolidationIntegration(consolidation_engine, es, memory_engine)


# ===================================================================
# Construction Validation
# ===================================================================


class TestIntegrationConstruction:
    def test_valid_construction(self, consolidation_engine, es, memory_engine):
        integ = MemoryConsolidationIntegration(consolidation_engine, es, memory_engine)
        assert integ is not None

    def test_invalid_consolidation_engine(self, es, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="consolidation_engine"):
            MemoryConsolidationIntegration("not-an-engine", es, memory_engine)

    def test_invalid_event_spine(self, consolidation_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            MemoryConsolidationIntegration(consolidation_engine, "not-es", memory_engine)

    def test_invalid_memory_engine(self, consolidation_engine, es):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            MemoryConsolidationIntegration(consolidation_engine, es, "not-memory")

    def test_none_consolidation_engine(self, es, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            MemoryConsolidationIntegration(None, es, memory_engine)

    def test_none_event_spine(self, consolidation_engine, memory_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            MemoryConsolidationIntegration(consolidation_engine, None, memory_engine)

    def test_none_memory_engine(self, consolidation_engine, es):
        with pytest.raises(RuntimeCoreInvariantError):
            MemoryConsolidationIntegration(consolidation_engine, es, None)


# ===================================================================
# Surface-specific consolidation methods
# ===================================================================


class TestConsolidateFromCopilotSessions:
    def test_returns_dict(self, integration):
        result = integration.consolidate_from_copilot_sessions("t-1", "sess-1", "User prefers dark mode")
        assert isinstance(result, dict)

    def test_dict_keys(self, integration):
        result = integration.consolidate_from_copilot_sessions("t-1", "sess-1", "summary")
        expected_keys = {
            "candidate_id", "tenant_id", "source_ref", "source_type",
            "content_summary", "importance", "status", "occurrence_count",
        }
        assert set(result.keys()) == expected_keys

    def test_source_type(self, integration):
        result = integration.consolidate_from_copilot_sessions("t-1", "sess-1", "s")
        assert result["source_type"] == "copilot_sessions"

    def test_default_importance(self, integration):
        result = integration.consolidate_from_copilot_sessions("t-1", "sess-1", "s")
        assert result["importance"] == "medium"

    def test_default_status(self, integration):
        result = integration.consolidate_from_copilot_sessions("t-1", "sess-1", "s")
        assert result["status"] == "candidate"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.consolidate_from_copilot_sessions("t-1", "sess-1", "s")
        assert es.event_count > before

    def test_registers_candidate(self, integration, consolidation_engine):
        integration.consolidate_from_copilot_sessions("t-1", "sess-1", "s")
        assert consolidation_engine.candidate_count == 1


class TestConsolidateFromMultimodalSessions:
    def test_returns_dict(self, integration):
        result = integration.consolidate_from_multimodal_sessions("t-1", "mm-1", "s")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        result = integration.consolidate_from_multimodal_sessions("t-1", "mm-1", "s")
        assert result["source_type"] == "multimodal_sessions"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.consolidate_from_multimodal_sessions("t-1", "mm-1", "s")
        assert es.event_count > before


class TestConsolidateFromOperatorActions:
    def test_returns_dict(self, integration):
        result = integration.consolidate_from_operator_actions("t-1", "act-1", "s")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        result = integration.consolidate_from_operator_actions("t-1", "act-1", "s")
        assert result["source_type"] == "operator_actions"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.consolidate_from_operator_actions("t-1", "act-1", "s")
        assert es.event_count > before


class TestConsolidateFromResearchRuns:
    def test_returns_dict(self, integration):
        result = integration.consolidate_from_research_runs("t-1", "rr-1", "s")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        result = integration.consolidate_from_research_runs("t-1", "rr-1", "s")
        assert result["source_type"] == "research_runs"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.consolidate_from_research_runs("t-1", "rr-1", "s")
        assert es.event_count > before


class TestConsolidateFromCustomerHistory:
    def test_returns_dict(self, integration):
        result = integration.consolidate_from_customer_history("t-1", "cust-1", "s")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        result = integration.consolidate_from_customer_history("t-1", "cust-1", "s")
        assert result["source_type"] == "customer_history"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.consolidate_from_customer_history("t-1", "cust-1", "s")
        assert es.event_count > before

    def test_tenant_id_preserved(self, integration):
        result = integration.consolidate_from_customer_history("tenant-abc", "cust-1", "s")
        assert result["tenant_id"] == "tenant-abc"


class TestConsolidateFromExecutivePatterns:
    def test_returns_dict(self, integration):
        result = integration.consolidate_from_executive_patterns("t-1", "exec-1", "s")
        assert isinstance(result, dict)

    def test_source_type(self, integration):
        result = integration.consolidate_from_executive_patterns("t-1", "exec-1", "s")
        assert result["source_type"] == "executive_patterns"

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.consolidate_from_executive_patterns("t-1", "exec-1", "s")
        assert es.event_count > before


# ===================================================================
# Memory Mesh Attachment
# ===================================================================


class TestAttachConsolidationStateToMemoryMesh:
    def test_returns_memory_record(self, integration):
        record = integration.attach_consolidation_state_to_memory_mesh("scope-1")
        assert isinstance(record, MemoryRecord)

    def test_memory_record_title(self, integration):
        record = integration.attach_consolidation_state_to_memory_mesh("scope-1")
        assert record.title == "Memory consolidation state"
        assert "scope-1" not in record.title
        assert record.scope_ref_id == "scope-1"

    def test_memory_record_added_to_mesh(self, integration, memory_engine):
        before = memory_engine.memory_count
        integration.attach_consolidation_state_to_memory_mesh("scope-1")
        assert memory_engine.memory_count == before + 1

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.attach_consolidation_state_to_memory_mesh("scope-1")
        assert es.event_count > before

    def test_memory_record_content_keys(self, integration):
        record = integration.attach_consolidation_state_to_memory_mesh("scope-1")
        content = record.content
        assert "scope_ref_id" in content
        assert "total_candidates" in content
        assert "total_decisions" in content

    def test_memory_record_tags(self, integration):
        record = integration.attach_consolidation_state_to_memory_mesh("scope-1")
        assert "memory_consolidation" in record.tags
        assert "personalization" in record.tags

    def test_reflects_engine_state(self, integration, consolidation_engine):
        consolidation_engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        record = integration.attach_consolidation_state_to_memory_mesh("scope-1")
        assert record.content["total_candidates"] == 1


# ===================================================================
# Graph Attachment
# ===================================================================


class TestAttachConsolidationStateToGraph:
    def test_returns_dict(self, integration):
        result = integration.attach_consolidation_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_dict_keys(self, integration):
        result = integration.attach_consolidation_state_to_graph("scope-1")
        expected = {
            "scope_ref_id", "total_candidates", "total_decisions", "total_rules",
            "total_profiles", "total_conflicts", "total_batches", "total_violations",
        }
        assert set(result.keys()) == expected

    def test_reflects_engine_state(self, integration, consolidation_engine):
        consolidation_engine.register_memory_candidate("c-1", "t-1", "s-1", "s")
        result = integration.attach_consolidation_state_to_graph("scope-1")
        assert result["total_candidates"] == 1

    def test_scope_ref_id_passed_through(self, integration):
        result = integration.attach_consolidation_state_to_graph("my-scope")
        assert result["scope_ref_id"] == "my-scope"


# ===================================================================
# Cross-source consolidation
# ===================================================================


class TestCrossSourceConsolidation:
    def test_multiple_sources_same_tenant(self, integration, consolidation_engine):
        integration.consolidate_from_copilot_sessions("t-1", "s1", "pref A")
        integration.consolidate_from_multimodal_sessions("t-1", "s2", "pref B")
        integration.consolidate_from_operator_actions("t-1", "s3", "pref C")
        integration.consolidate_from_research_runs("t-1", "s4", "pref D")
        integration.consolidate_from_customer_history("t-1", "s5", "pref E")
        integration.consolidate_from_executive_patterns("t-1", "s6", "pref F")
        assert consolidation_engine.candidate_count == 6

    def test_different_tenants_isolated(self, integration, consolidation_engine):
        integration.consolidate_from_copilot_sessions("t-1", "s1", "pref A")
        integration.consolidate_from_copilot_sessions("t-2", "s2", "pref B")
        t1_candidates = consolidation_engine.candidates_for_tenant("t-1")
        t2_candidates = consolidation_engine.candidates_for_tenant("t-2")
        assert len(t1_candidates) == 1
        assert len(t2_candidates) == 1

    def test_unique_candidate_ids(self, integration):
        r1 = integration.consolidate_from_copilot_sessions("t-1", "s1", "s")
        r2 = integration.consolidate_from_multimodal_sessions("t-1", "s2", "s")
        assert r1["candidate_id"] != r2["candidate_id"]


# ===================================================================
# Golden Integration Scenarios
# ===================================================================


class TestGoldenIntegrationScenarios:
    def test_end_to_end_consolidation_pipeline(self, integration, consolidation_engine, es):
        """Full pipeline: ingest from multiple sources, batch, profile, attach."""
        integration.consolidate_from_copilot_sessions("t-1", "s1", "Prefers dark mode")
        integration.consolidate_from_customer_history("t-1", "c1", "Purchases premium plans")
        integration.consolidate_from_operator_actions("t-1", "a1", "Auto-scales infrastructure")

        assert consolidation_engine.candidate_count == 3

        # Score and batch
        for c in consolidation_engine.candidates_for_tenant("t-1"):
            consolidation_engine.score_memory_importance(c.candidate_id)
        consolidation_engine.consolidate_batch("b-1", "t-1")

        # Build profile
        consolidation_engine.build_personalization_profile("p-1", "t-1", "user-1", PersonalizationScope.ACCOUNT)

        # Attach to mesh and graph
        record = integration.attach_consolidation_state_to_memory_mesh("t-1-scope")
        graph = integration.attach_consolidation_state_to_graph("t-1-scope")

        assert record.content["total_candidates"] == 3
        assert graph["total_candidates"] == 3
        assert graph["total_batches"] == 1
        assert graph["total_profiles"] == 1

    def test_event_trail_complete(self, integration, es):
        """Every surface method emits events."""
        before = es.event_count
        integration.consolidate_from_copilot_sessions("t-1", "s1", "s")
        integration.consolidate_from_multimodal_sessions("t-1", "s2", "s")
        integration.consolidate_from_operator_actions("t-1", "s3", "s")
        integration.consolidate_from_research_runs("t-1", "s4", "s")
        integration.consolidate_from_customer_history("t-1", "s5", "s")
        integration.consolidate_from_executive_patterns("t-1", "s6", "s")
        # Each consolidate_from_X emits at least 2 events (register + surface)
        assert es.event_count >= before + 12

    def test_mesh_attachment_after_batch(self, integration, consolidation_engine, memory_engine):
        """Mesh attachment reflects post-batch state."""
        integration.consolidate_from_copilot_sessions("t-1", "s1", "Important pref")
        # Manually promote via engine
        for c in consolidation_engine.candidates_for_tenant("t-1"):
            consolidation_engine.score_memory_importance(c.candidate_id)
        consolidation_engine.consolidate_batch("b-1", "t-1")

        record = integration.attach_consolidation_state_to_memory_mesh("scope-batch")
        assert record.content["total_batches"] == 1
        assert record.content["total_decisions"] >= 0
