"""Comprehensive tests for DataQualityIntegration bridge.

Covers quality record creation from all source types, memory mesh attachment,
operational graph attachment, event emission, and type validation (~70 tests).
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.data_quality import (
    DataQualityStatus,
    TrustScore,
)
from mcoi_runtime.contracts.memory_mesh import MemoryRecord
from mcoi_runtime.core.data_quality import DataQualityEngine
from mcoi_runtime.core.data_quality_integration import DataQualityIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def dq(es):
    return DataQualityEngine(es)


@pytest.fixture
def mem():
    return MemoryMeshEngine()


@pytest.fixture
def integration(dq, es, mem):
    return DataQualityIntegration(dq, es, mem)


# ===================================================================
# 1. Construction validation
# ===================================================================


class TestConstructionValidation:
    def test_happy_path(self, dq, es, mem):
        integ = DataQualityIntegration(dq, es, mem)
        assert integ is not None

    def test_rejects_non_dq_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="DataQualityEngine"):
            DataQualityIntegration("bad", es, mem)

    def test_rejects_non_event_spine(self, dq, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            DataQualityIntegration(dq, "bad", mem)

    def test_rejects_non_memory_engine(self, dq, es):
        with pytest.raises(RuntimeCoreInvariantError, match="MemoryMeshEngine"):
            DataQualityIntegration(dq, es, "bad")

    def test_rejects_none_dq(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            DataQualityIntegration(None, es, mem)

    def test_rejects_none_es(self, dq, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            DataQualityIntegration(dq, None, mem)

    def test_rejects_none_mem(self, dq, es):
        with pytest.raises(RuntimeCoreInvariantError):
            DataQualityIntegration(dq, es, None)


# ===================================================================
# 2. quality_from_artifact_ingestion
# ===================================================================


class TestQualityFromArtifactIngestion:
    def test_returns_dict(self, integration):
        result = integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        assert isinstance(result, dict)

    def test_dict_keys(self, integration):
        result = integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        assert "record_id" in result
        assert "tenant_id" in result
        assert "source_type" in result
        assert "source_ref" in result
        assert "status" in result
        assert "trust_score" in result
        assert "error_count" in result

    def test_source_type(self, integration):
        result = integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        assert result["source_type"] == "artifact_ingestion"

    def test_default_status_clean(self, integration):
        result = integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        assert result["status"] == "clean"

    def test_custom_status_dirty(self, integration):
        result = integration.quality_from_artifact_ingestion(
            "r1", "t1", "src1", status=DataQualityStatus.DIRTY,
        )
        assert result["status"] == "dirty"

    def test_error_count_propagated(self, integration):
        result = integration.quality_from_artifact_ingestion(
            "r1", "t1", "src1", error_count=5,
        )
        assert result["error_count"] == 5
        assert result["trust_score"] == "low"

    def test_trust_score_auto(self, integration):
        result = integration.quality_from_artifact_ingestion(
            "r1", "t1", "src1", error_count=0,
        )
        assert result["trust_score"] == "high"

    def test_registers_in_dq_engine(self, integration, dq):
        integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        assert dq.record_count == 1

    def test_emits_events(self, integration, es):
        before = es.event_count
        integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        # dq engine emits 1 + integration emits 1
        assert es.event_count >= before + 2

    def test_duplicate_id_rejected(self, integration):
        integration.quality_from_artifact_ingestion("r1", "t1", "src1")
        with pytest.raises(RuntimeCoreInvariantError):
            integration.quality_from_artifact_ingestion("r1", "t1", "src2")


# ===================================================================
# 3. quality_from_records_runtime
# ===================================================================


class TestQualityFromRecordsRuntime:
    def test_source_type(self, integration):
        result = integration.quality_from_records_runtime("r1", "t1", "src1")
        assert result["source_type"] == "records_runtime"

    def test_registers_record(self, integration, dq):
        integration.quality_from_records_runtime("r1", "t1", "src1")
        assert dq.record_count == 1

    def test_custom_error_count(self, integration):
        result = integration.quality_from_records_runtime("r1", "t1", "src1", error_count=10)
        assert result["trust_score"] == "untrusted"


# ===================================================================
# 4. quality_from_knowledge_query
# ===================================================================


class TestQualityFromKnowledgeQuery:
    def test_source_type(self, integration):
        result = integration.quality_from_knowledge_query("r1", "t1", "src1")
        assert result["source_type"] == "knowledge_query"

    def test_registers_record(self, integration, dq):
        integration.quality_from_knowledge_query("r1", "t1", "src1")
        assert dq.record_count == 1


# ===================================================================
# 5. quality_from_reporting
# ===================================================================


class TestQualityFromReporting:
    def test_source_type(self, integration):
        result = integration.quality_from_reporting("r1", "t1", "src1")
        assert result["source_type"] == "reporting"

    def test_registers_record(self, integration, dq):
        integration.quality_from_reporting("r1", "t1", "src1")
        assert dq.record_count == 1


# ===================================================================
# 6. quality_from_research
# ===================================================================


class TestQualityFromResearch:
    def test_source_type(self, integration):
        result = integration.quality_from_research("r1", "t1", "src1")
        assert result["source_type"] == "research"

    def test_registers_record(self, integration, dq):
        integration.quality_from_research("r1", "t1", "src1")
        assert dq.record_count == 1


# ===================================================================
# 7. quality_from_memory_mesh
# ===================================================================


class TestQualityFromMemoryMesh:
    def test_source_type(self, integration):
        result = integration.quality_from_memory_mesh("r1", "t1", "src1")
        assert result["source_type"] == "memory_mesh"

    def test_registers_record(self, integration, dq):
        integration.quality_from_memory_mesh("r1", "t1", "src1")
        assert dq.record_count == 1

    def test_custom_status_degraded(self, integration):
        result = integration.quality_from_memory_mesh(
            "r1", "t1", "src1", status=DataQualityStatus.DEGRADED,
        )
        assert result["status"] == "degraded"


# ===================================================================
# 8. attach_data_quality_to_memory_mesh
# ===================================================================


class TestAttachToMemoryMesh:
    def test_returns_memory_record(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert isinstance(mem_rec, MemoryRecord)

    def test_memory_id_set(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert mem_rec.memory_id != ""

    def test_title_contains_scope(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert "scope1" in mem_rec.title

    def test_tags_include_data_quality(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert "data_quality" in mem_rec.tags

    def test_tags_include_schema_evolution(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert "schema_evolution" in mem_rec.tags

    def test_tags_include_lineage(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert "lineage" in mem_rec.tags

    def test_content_has_totals(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        content = mem_rec.content
        assert "total_records" in content
        assert "total_schemas" in content
        assert "total_drifts" in content
        assert "total_duplicates" in content
        assert "total_lineages" in content
        assert "total_violations" in content

    def test_content_totals_zero_initially(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert mem_rec.content["total_records"] == 0
        assert mem_rec.content["total_schemas"] == 0

    def test_content_reflects_state(self, integration, dq, es):
        dq.register_quality_record("r1", "t1", "src1")
        dq.register_schema_version("v1", "t1", "sch1")
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert mem_rec.content["total_records"] == 1
        assert mem_rec.content["total_schemas"] == 1

    def test_emits_event(self, integration, es):
        before = es.event_count
        integration.attach_data_quality_to_memory_mesh("scope1")
        assert es.event_count > before

    def test_confidence_is_one(self, integration):
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert mem_rec.confidence == 1.0


# ===================================================================
# 9. attach_data_quality_to_graph
# ===================================================================


class TestAttachToGraph:
    def test_returns_dict(self, integration):
        result = integration.attach_data_quality_to_graph("scope1")
        assert isinstance(result, dict)

    def test_scope_ref_id(self, integration):
        result = integration.attach_data_quality_to_graph("scope1")
        assert result["scope_ref_id"] == "scope1"

    def test_all_keys_present(self, integration):
        result = integration.attach_data_quality_to_graph("scope1")
        expected_keys = {
            "scope_ref_id", "total_records", "total_schemas",
            "total_drifts", "total_duplicates", "total_lineages",
            "total_reconciliations", "total_policies", "total_violations",
        }
        assert set(result.keys()) == expected_keys

    def test_totals_zero_initially(self, integration):
        result = integration.attach_data_quality_to_graph("scope1")
        assert result["total_records"] == 0
        assert result["total_schemas"] == 0
        assert result["total_drifts"] == 0
        assert result["total_duplicates"] == 0
        assert result["total_lineages"] == 0
        assert result["total_reconciliations"] == 0
        assert result["total_policies"] == 0
        assert result["total_violations"] == 0

    def test_reflects_state(self, integration, dq, es):
        dq.register_quality_record("r1", "t1", "src1")
        dq.register_schema_version("v1", "t1", "sch1")
        dq.detect_drift("d1", "t1", "sch1", "f", "str", "int")
        dq.detect_duplicate("dup1", "t1", "ra", "rb")
        dq.register_lineage("l1", "t1", "src1", "tgt1")
        dq.reconcile_record("rec1", "t1", "src1", "can1")
        dq.register_source_policy("pol1", "t1", "src1")
        result = integration.attach_data_quality_to_graph("scope1")
        assert result["total_records"] == 1
        assert result["total_schemas"] == 1
        assert result["total_drifts"] == 1
        assert result["total_duplicates"] == 1
        assert result["total_lineages"] == 1
        assert result["total_reconciliations"] == 1
        assert result["total_policies"] == 1


# ===================================================================
# 10. Cross-source integration
# ===================================================================


class TestCrossSourceIntegration:
    """Multiple source types can register records that show up in graph/memory."""

    SOURCE_METHODS = [
        "quality_from_artifact_ingestion",
        "quality_from_records_runtime",
        "quality_from_knowledge_query",
        "quality_from_reporting",
        "quality_from_research",
        "quality_from_memory_mesh",
    ]

    def test_all_sources_register_records(self, integration, dq):
        for i, method_name in enumerate(self.SOURCE_METHODS):
            method = getattr(integration, method_name)
            method(f"r{i}", "t1", f"src{i}")
        assert dq.record_count == len(self.SOURCE_METHODS)

    def test_graph_reflects_all_sources(self, integration, dq):
        for i, method_name in enumerate(self.SOURCE_METHODS):
            method = getattr(integration, method_name)
            method(f"r{i}", "t1", f"src{i}")
        result = integration.attach_data_quality_to_graph("scope1")
        assert result["total_records"] == len(self.SOURCE_METHODS)

    def test_memory_reflects_all_sources(self, integration, dq):
        for i, method_name in enumerate(self.SOURCE_METHODS):
            method = getattr(integration, method_name)
            method(f"r{i}", "t1", f"src{i}")
        mem_rec = integration.attach_data_quality_to_memory_mesh("scope1")
        assert mem_rec.content["total_records"] == len(self.SOURCE_METHODS)

    def test_each_source_emits_events(self, integration, es):
        for i, method_name in enumerate(self.SOURCE_METHODS):
            before = es.event_count
            method = getattr(integration, method_name)
            method(f"r{i}", "t1", f"src{i}")
            assert es.event_count > before
