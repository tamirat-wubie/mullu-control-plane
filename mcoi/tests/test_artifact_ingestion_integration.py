"""Integration tests for ArtifactIngestionIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.artifact_ingestion import (
    ArtifactDescriptor,
    ArtifactFormat,
    ArtifactParseStatus,
    ArtifactSemanticType,
    ArtifactSourceType,
)
from mcoi_runtime.contracts.event import EventSource, EventType
from mcoi_runtime.core.artifact_ingestion import ArtifactIngestionEngine
from mcoi_runtime.core.artifact_ingestion_integration import ArtifactIngestionIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

NOW = "2026-03-20T12:00:00+00:00"


def _make_integration(**kw):
    artifact_engine = kw.get("artifact_engine", ArtifactIngestionEngine())
    event_spine = kw.get("event_spine", EventSpineEngine())
    memory_engine = kw.get("memory_engine", MemoryMeshEngine())
    obligation_runtime = kw.get("obligation_runtime", ObligationRuntimeEngine())
    return ArtifactIngestionIntegration(
        artifact_engine=artifact_engine,
        event_spine=event_spine,
        memory_engine=memory_engine,
        obligation_runtime=obligation_runtime,
    )


def _desc(aid="art-1", filename="file.json", mime="application/json", size=100, **kw):
    defaults = dict(
        artifact_id=aid,
        source_type=ArtifactSourceType.FILE,
        source_ref="/data/" + filename,
        filename=filename,
        mime_type=mime,
        size_bytes=size,
        created_at=NOW,
    )
    defaults.update(kw)
    return ArtifactDescriptor(**defaults)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_valid(self):
        integration = _make_integration()
        assert integration is not None

    def test_bad_artifact_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="artifact_engine"):
            ArtifactIngestionIntegration(
                artifact_engine="not an engine",
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
                obligation_runtime=ObligationRuntimeEngine(),
            )

    def test_bad_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            ArtifactIngestionIntegration(
                artifact_engine=ArtifactIngestionEngine(),
                event_spine="not an engine",
                memory_engine=MemoryMeshEngine(),
                obligation_runtime=ObligationRuntimeEngine(),
            )

    def test_bad_memory_engine(self):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            ArtifactIngestionIntegration(
                artifact_engine=ArtifactIngestionEngine(),
                event_spine=EventSpineEngine(),
                memory_engine="not an engine",
                obligation_runtime=ObligationRuntimeEngine(),
            )

    def test_bad_obligation_runtime(self):
        with pytest.raises(RuntimeCoreInvariantError, match="obligation_runtime"):
            ArtifactIngestionIntegration(
                artifact_engine=ArtifactIngestionEngine(),
                event_spine=EventSpineEngine(),
                memory_engine=MemoryMeshEngine(),
                obligation_runtime="not an engine",
            )


# ---------------------------------------------------------------------------
# ingest_and_emit_event
# ---------------------------------------------------------------------------


class TestIngestAndEmitEvent:
    def test_accepted_emits_world_state(self):
        event_spine = EventSpineEngine()
        integration = _make_integration(event_spine=event_spine)
        desc = _desc()
        result = integration.ingest_and_emit_event(desc, b'{"key": "value"}')

        assert result["record"].status == ArtifactParseStatus.ACCEPTED
        assert result["event"].event_type == EventType.WORLD_STATE_CHANGED
        assert result["event"].payload["artifact_id"] == "art-1"

    def test_rejected_emits_custom(self):
        event_spine = EventSpineEngine()
        integration = _make_integration(event_spine=event_spine)
        desc = _desc(aid="art-bad", filename="bad.json")
        result = integration.ingest_and_emit_event(desc, b"{not json")

        assert result["record"].status == ArtifactParseStatus.MALFORMED
        assert result["event"].event_type == EventType.CUSTOM

    def test_event_has_correlation_id(self):
        integration = _make_integration()
        desc = _desc(aid="art-corr")
        result = integration.ingest_and_emit_event(desc, b'{"k": 1}')
        assert result["event"].correlation_id == "art-corr"

    def test_event_payload_has_filename(self):
        integration = _make_integration()
        desc = _desc(aid="art-fn", filename="report.json")
        result = integration.ingest_and_emit_event(desc, b'{"k": 1}')
        assert result["event"].payload["filename"] == "report.json"


# ---------------------------------------------------------------------------
# ingest_and_remember
# ---------------------------------------------------------------------------


class TestIngestAndRemember:
    def test_creates_memory(self):
        integration = _make_integration()
        desc = _desc(aid="art-mem")
        result = integration.ingest_and_remember(desc, b'{"key": "value"}')

        assert "memory" in result
        assert result["memory"].title == "Event: artifact_ingested"
        assert result["memory"].content["artifact_id"] == "art-mem"

    def test_accepted_has_verified_trust(self):
        integration = _make_integration()
        desc = _desc(aid="art-trust")
        result = integration.ingest_and_remember(desc, b'{"key": "value"}')
        from mcoi_runtime.contracts.memory_mesh import MemoryTrustLevel
        assert result["memory"].trust_level == MemoryTrustLevel.VERIFIED

    def test_rejected_has_unverified_trust(self):
        integration = _make_integration()
        desc = _desc(aid="art-untrust", filename="bad.json")
        result = integration.ingest_and_remember(desc, b"{not json")
        from mcoi_runtime.contracts.memory_mesh import MemoryTrustLevel
        assert result["memory"].trust_level == MemoryTrustLevel.UNVERIFIED

    def test_tags_propagated(self):
        integration = _make_integration()
        desc = _desc(aid="art-tags")
        result = integration.ingest_and_remember(desc, b'{"k": 1}', tags=("custom_tag",))
        assert "artifact" in result["memory"].tags
        assert "custom_tag" in result["memory"].tags

    def test_result_contains_all_keys(self):
        integration = _make_integration()
        desc = _desc(aid="art-full")
        result = integration.ingest_and_remember(desc, b'{"k": 1}')
        assert "record" in result
        assert "event" in result
        assert "memory" in result


# ---------------------------------------------------------------------------
# ingest_and_extract_obligations
# ---------------------------------------------------------------------------


class TestIngestAndExtractObligations:
    def _obl_specs(self):
        return [
            {
                "description": "Review artifact within 24h",
                "owner_id": "owner-1",
                "owner_type": "team",
                "display_name": "Review Team",
                "deadline_id": "dl-1",
                "due_at": "2026-03-21T12:00:00+00:00",
            },
        ]

    def test_creates_obligation(self):
        integration = _make_integration()
        desc = _desc(aid="art-obl")
        result = integration.ingest_and_extract_obligations(
            desc, b'{"k": 1}', self._obl_specs(),
        )
        assert len(result["obligations"]) == 1
        assert result["obligations"][0].description == "Review artifact within 24h"

    def test_rejected_creates_no_obligations(self):
        integration = _make_integration()
        desc = _desc(aid="art-obl-rej", filename="bad.json")
        result = integration.ingest_and_extract_obligations(
            desc, b"{bad", self._obl_specs(),
        )
        assert result["obligations"] == ()

    def test_multiple_obligations(self):
        specs = [
            {
                "description": "Review",
                "owner_id": "o1", "owner_type": "team",
                "display_name": "Team A",
                "deadline_id": "dl-a",
                "due_at": "2026-03-21T12:00:00+00:00",
            },
            {
                "description": "Approve",
                "owner_id": "o2", "owner_type": "manager",
                "display_name": "Manager B",
                "deadline_id": "dl-b",
                "due_at": "2026-03-22T12:00:00+00:00",
            },
        ]
        integration = _make_integration()
        desc = _desc(aid="art-multi-obl")
        result = integration.ingest_and_extract_obligations(desc, b'{"k": 1}', specs)
        assert len(result["obligations"]) == 2

    def test_obligation_has_memory(self):
        integration = _make_integration()
        desc = _desc(aid="art-obl-mem")
        result = integration.ingest_and_extract_obligations(
            desc, b'{"k": 1}', self._obl_specs(),
        )
        assert "memory" in result
        assert "obligation_source" in result["memory"].tags


# ---------------------------------------------------------------------------
# Retrieval methods
# ---------------------------------------------------------------------------


class TestRetrievalMethods:
    def test_retrieve_for_goal(self):
        integration = _make_integration()
        result = integration.retrieve_artifacts_for_goal("goal-1")
        assert result.matched_ids == ()

    def test_retrieve_for_workflow(self):
        integration = _make_integration()
        result = integration.retrieve_artifacts_for_workflow("wf-1")
        assert result.matched_ids == ()

    def test_retrieve_for_recovery(self):
        integration = _make_integration()
        result = integration.retrieve_artifacts_for_recovery()
        assert result.matched_ids == ()

    def test_retrieve_for_supervisor_tick(self):
        integration = _make_integration()
        result = integration.retrieve_artifacts_for_supervisor_tick(1)
        assert result.matched_ids == ()
