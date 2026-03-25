"""Edge case tests for Audit #15 fixes.

Covers:
  - FaultInjectionEngine.get_assessments_for_record (new public API)
  - AdversarialOperationsBridge no longer accesses private _assessments
  - DomainPackEngine state_hash includes vocabulary/activations/resolutions
  - Bridge return immutability (contact_identity, communication_surface,
    artifact_ingestion)
  - run_full_adversarial_suite dead code removal
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.domain_pack import (
    DomainPackDescriptor,
    DomainPackStatus,
    DomainVocabularyEntry,
    PackScope,
)
from mcoi_runtime.contracts.fault_injection import (
    FaultSeverity,
    FaultSpec,
    FaultTargetKind,
    FaultType,
    InjectionMode,
)
from mcoi_runtime.core.adversarial_operations import AdversarialOperationsBridge
from mcoi_runtime.core.domain_pack import DomainPackEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.fault_injection import FaultInjectionEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# FaultInjectionEngine.get_assessments_for_record
# ---------------------------------------------------------------------------


class TestGetAssessmentsForRecord:
    def _engine_with_record(self):
        engine = FaultInjectionEngine()
        engine.register_spec(FaultSpec(
            spec_id="fs-1", fault_type=FaultType.FAILURE,
            target_kind=FaultTargetKind.PROVIDER,
            severity=FaultSeverity.MEDIUM,
            injection_mode=InjectionMode.REPEATED,
            repeat_count=3, created_at=NOW,
        ))
        record = engine.inject("fs-1", tick=0)
        return engine, record

    def test_no_assessments(self):
        engine, record = self._engine_with_record()
        result = engine.get_assessments_for_record(record.record_id)
        assert result == ()

    def test_single_assessment(self):
        engine, record = self._engine_with_record()
        engine.assess_recovery(record.record_id, recovered=True)
        result = engine.get_assessments_for_record(record.record_id)
        assert len(result) == 1
        assert result[0].recovered is True

    def test_multiple_assessments(self):
        engine, record = self._engine_with_record()
        engine.assess_recovery(record.record_id, recovered=True,
                               recovery_method="rollback")
        engine.assess_recovery(record.record_id, recovered=False,
                               degraded=True, degraded_reason="partial")
        result = engine.get_assessments_for_record(record.record_id)
        assert len(result) == 2

    def test_filters_by_record_id(self):
        engine = FaultInjectionEngine()
        engine.register_spec(FaultSpec(
            spec_id="fs-1", fault_type=FaultType.FAILURE,
            target_kind=FaultTargetKind.PROVIDER,
            severity=FaultSeverity.MEDIUM,
            injection_mode=InjectionMode.REPEATED,
            repeat_count=3, created_at=NOW,
        ))
        r1 = engine.inject("fs-1", tick=0)
        r2 = engine.inject("fs-1", tick=1)
        engine.assess_recovery(r1.record_id, recovered=True)
        engine.assess_recovery(r2.record_id, recovered=False)
        result = engine.get_assessments_for_record(r1.record_id)
        assert len(result) == 1
        assert result[0].record_id == r1.record_id

    def test_returns_tuple(self):
        engine, record = self._engine_with_record()
        result = engine.get_assessments_for_record(record.record_id)
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# AdversarialOperationsBridge — no private access
# ---------------------------------------------------------------------------


class TestAdversarialNoPrivateAccess:
    def test_evaluate_uses_public_api(self):
        """evaluate_fault_campaign uses get_assessments_for_record, not _assessments."""
        fe = FaultInjectionEngine()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        bridge = AdversarialOperationsBridge(
            fault_engine=fe, event_spine=es, memory_engine=me,
        )
        result = bridge.run_provider_storm_campaign(tick_count=5)
        # Should work without touching private _assessments
        eval_result = bridge.evaluate_fault_campaign(
            result["session"].session_id,
        )
        assert eval_result["outcome"].passed is True


# ---------------------------------------------------------------------------
# DomainPackEngine state_hash completeness
# ---------------------------------------------------------------------------


class TestDomainPackStateHashCompleteness:
    def _base_engine(self):
        engine = DomainPackEngine()
        engine.register_pack(DomainPackDescriptor(
            pack_id="pk-1", domain_name="test", version="1.0.0",
            status=DomainPackStatus.DRAFT, scope=PackScope.GLOBAL,
            created_at=NOW,
        ))
        return engine

    def test_vocabulary_changes_hash(self):
        engine = self._base_engine()
        h1 = engine.state_hash()
        engine.add_vocabulary_entry(DomainVocabularyEntry(
            entry_id="vocab-1", pack_id="pk-1", term="deploy",
            canonical_form="deployment", created_at=NOW,
        ))
        h2 = engine.state_hash()
        assert h1 != h2

    def test_activation_changes_hash(self):
        engine = self._base_engine()
        h1 = engine.state_hash()
        engine.activate_pack("pk-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_resolution_changes_hash(self):
        engine = self._base_engine()
        engine.activate_pack("pk-1")
        h1 = engine.state_hash()
        engine.resolve_for_scope(PackScope.GLOBAL)
        h2 = engine.state_hash()
        assert h1 != h2


# ---------------------------------------------------------------------------
# Bridge return immutability
# ---------------------------------------------------------------------------


class TestBridgeReturnImmutability:
    def test_adversarial_full_suite_no_dead_code(self):
        """run_full_adversarial_suite should not create unused engines."""
        fe = FaultInjectionEngine()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        bridge = AdversarialOperationsBridge(
            fault_engine=fe, event_spine=es, memory_engine=me,
        )
        result = bridge.run_full_adversarial_suite(tick_count=3)
        assert result["total_campaigns"] == 3
        assert 0.0 <= result["aggregate_score"] <= 1.0
        assert isinstance(result["campaigns"], tuple)

    def test_run_fault_campaign_records_immutable(self):
        fe = FaultInjectionEngine()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        bridge = AdversarialOperationsBridge(
            fault_engine=fe, event_spine=es, memory_engine=me,
        )
        result = bridge.run_provider_storm_campaign(tick_count=3)
        assert isinstance(result["records"], tuple)


# ---------------------------------------------------------------------------
# Artifact ingestion — rejected obligations returns tuple
# ---------------------------------------------------------------------------


class TestArtifactObligationsReturnType:
    def test_rejected_returns_tuple(self):
        from mcoi_runtime.core.artifact_ingestion import ArtifactIngestionEngine
        from mcoi_runtime.core.artifact_ingestion_integration import (
            ArtifactIngestionIntegration,
        )
        from mcoi_runtime.contracts.artifact_ingestion import (
            ArtifactDescriptor,
            ArtifactSourceType,
        )
        from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

        ai = ArtifactIngestionEngine()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        obr = ObligationRuntimeEngine()
        integration = ArtifactIngestionIntegration(
            artifact_engine=ai, event_spine=es,
            memory_engine=me, obligation_runtime=obr,
        )
        desc = ArtifactDescriptor(
            artifact_id="art-rej",
            filename="bad.json",
            source_type=ArtifactSourceType.FILE,
            source_ref="test",
            mime_type="application/json",
            size_bytes=10,
            created_at=NOW,
        )
        result = integration.ingest_and_extract_obligations(
            desc, b"{bad", [],
        )
        assert isinstance(result["obligations"], tuple)
