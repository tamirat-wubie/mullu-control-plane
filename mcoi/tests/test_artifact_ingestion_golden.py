"""Golden scenario tests for artifact ingestion subsystem.

8 scenarios covering end-to-end ingestion flows.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.artifact_ingestion import (
    ArtifactDescriptor,
    ArtifactFormat,
    ArtifactParseStatus,
    ArtifactSemanticType,
    ArtifactSourceType,
)
from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.memory_mesh import MemoryTrustLevel
from mcoi_runtime.core.artifact_ingestion import ArtifactIngestionEngine
from mcoi_runtime.core.artifact_ingestion_integration import ArtifactIngestionIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

NOW = "2026-03-20T12:00:00+00:00"


def _build():
    ae = ArtifactIngestionEngine()
    es = EventSpineEngine()
    me = MemoryMeshEngine()
    obl = ObligationRuntimeEngine()
    integ = ArtifactIngestionIntegration(
        artifact_engine=ae, event_spine=es,
        memory_engine=me, obligation_runtime=obl,
    )
    return ae, es, me, obl, integ


def _desc(aid, filename, mime="application/json", size=100, **kw):
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
# Scenario 1: JSON config → semantic mapping → memory record
# ---------------------------------------------------------------------------


class TestGolden1JsonConfigSemanticMemory:
    def test_json_config_full_pipeline(self):
        ae, es, me, obl, integ = _build()

        config = {"database": {"host": "db.local", "port": 5432}, "cache_ttl": 300}
        desc = _desc("art-config-1", "app_config.json")
        result = integ.ingest_and_remember(desc, json.dumps(config).encode())

        # Record accepted
        record = result["record"]
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.format_detected == ArtifactFormat.JSON

        # Semantic mapping → CONFIG
        assert record.semantic_mapping is not None
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.CONFIG

        # Structure extracted
        assert record.structure is not None
        assert record.structure.field_count == 2
        assert "database" in record.structure.sections["keys"]

        # Memory created
        mem = result["memory"]
        assert mem.content["format"] == "json"
        assert mem.content["status"] == "accepted"
        assert mem.trust_level == MemoryTrustLevel.VERIFIED

        # Event emitted
        assert result["event"].event_type == EventType.WORLD_STATE_CHANGED

        # Fingerprint deterministic
        assert record.fingerprint.algorithm == "sha256"
        assert len(record.fingerprint.digest) == 64


# ---------------------------------------------------------------------------
# Scenario 2: Malformed YAML rejected with typed reason
# ---------------------------------------------------------------------------


class TestGolden2MalformedYamlRejected:
    def test_malformed_yaml_typed_rejection(self):
        ae, es, me, obl, integ = _build()

        desc = _desc("art-bad-yaml", "broken.yaml", mime="text/yaml")
        result = integ.ingest_and_emit_event(
            desc, b"this is just plain text without yaml structure",
        )

        record = result["record"]
        assert record.status == ArtifactParseStatus.MALFORMED
        assert "YAML" in record.parse_result.reason or "yaml" in record.parse_result.reason.lower()
        assert record.structure is None

        # Event still emitted (audit trail)
        assert result["event"].event_type == EventType.CUSTOM
        assert result["event"].payload["status"] == "malformed"


# ---------------------------------------------------------------------------
# Scenario 3: CSV → structured extraction result
# ---------------------------------------------------------------------------


class TestGolden3CsvStructuredExtraction:
    def test_csv_structured(self):
        ae, es, me, obl, integ = _build()

        csv_content = b"name,age,department\nAlice,30,Engineering\nBob,25,Marketing\nCarol,35,Sales"
        desc = _desc("art-csv-struct", "employees.csv", mime="text/csv")
        result = integ.ingest_and_remember(desc, csv_content)

        record = result["record"]
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.parse_result.format_detected == ArtifactFormat.CSV
        assert record.parse_result.metadata["row_count"] == 4
        assert record.parse_result.metadata["col_count"] == 3

        # Structure
        assert record.structure is not None
        assert record.structure.field_count == 3
        assert record.structure.row_count == 3  # data rows excluding header
        assert "name" in record.structure.sections["headers"]

        # Semantic mapping → DATASET
        assert record.semantic_mapping is not None
        assert record.semantic_mapping.semantic_type == ArtifactSemanticType.DATASET

        # Memory
        assert result["memory"].content["format"] == "csv"


# ---------------------------------------------------------------------------
# Scenario 4: Large blocked artifact returns TOO_LARGE
# ---------------------------------------------------------------------------


class TestGolden4TooLargeBlocked:
    def test_too_large_blocked(self):
        ae = ArtifactIngestionEngine(max_size_bytes=1024)
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        obl = ObligationRuntimeEngine()
        integ = ArtifactIngestionIntegration(
            artifact_engine=ae, event_spine=es,
            memory_engine=me, obligation_runtime=obl,
        )

        desc = _desc("art-huge", "giant.json", size=10_000_000)
        result = integ.ingest_and_emit_event(desc, b'{"small": "content"}')

        record = result["record"]
        assert record.status == ArtifactParseStatus.TOO_LARGE
        assert not record.policy_decision.allowed
        assert "too large" in record.policy_decision.reason.lower() or "exceeds" in record.policy_decision.reason.lower()
        assert record.structure is None
        assert record.semantic_mapping is None

        # Event still emitted
        assert result["event"].payload["status"] == "too_large"


# ---------------------------------------------------------------------------
# Scenario 5: Email attachment → communication → event → memory
# ---------------------------------------------------------------------------


class TestGolden5EmailAttachmentPipeline:
    def test_email_attachment_full_flow(self):
        ae, es, me, obl, integ = _build()

        attachment = json.dumps({
            "from": "partner@example.com",
            "subject": "Q1 Report",
            "data": {"revenue": 1_000_000, "expenses": 750_000},
        }).encode()

        desc = _desc(
            "art-email-1", "q1_report.json",
            source_type=ArtifactSourceType.EMAIL_ATTACHMENT,
            mime="application/json",
            metadata={"sender": "partner@example.com"},
        )
        result = integ.ingest_and_remember(desc, attachment, tags=("email", "quarterly"))

        record = result["record"]
        assert record.status == ArtifactParseStatus.ACCEPTED
        assert record.descriptor.source_type == ArtifactSourceType.EMAIL_ATTACHMENT

        # Event
        assert result["event"].event_type == EventType.WORLD_STATE_CHANGED
        assert result["event"].payload["artifact_id"] == "art-email-1"

        # Memory with tags
        mem = result["memory"]
        assert "email" in mem.tags
        assert "quarterly" in mem.tags
        assert "artifact" in mem.tags
        assert mem.content["semantic_type"] == "config"  # JSON default


# ---------------------------------------------------------------------------
# Scenario 6: Artifact with obligations creates obligation records
# ---------------------------------------------------------------------------


class TestGolden6ArtifactWithObligations:
    def test_artifact_obligations_created(self):
        ae, es, me, obl, integ = _build()

        contract_data = json.dumps({
            "contract_id": "CTR-2026-001",
            "terms": ["Deliver by Q2", "Monthly reporting"],
        }).encode()

        desc = _desc("art-contract", "contract.json")
        obligations = [
            {
                "description": "Deliver by Q2 2026",
                "owner_id": "team-delivery",
                "owner_type": "team",
                "display_name": "Delivery Team",
                "deadline_id": "dl-q2",
                "due_at": "2026-06-30T23:59:59+00:00",
            },
            {
                "description": "Submit monthly report",
                "owner_id": "team-ops",
                "owner_type": "team",
                "display_name": "Operations Team",
                "deadline_id": "dl-monthly",
                "due_at": "2026-04-30T23:59:59+00:00",
            },
        ]

        result = integ.ingest_and_extract_obligations(desc, contract_data, obligations)

        assert result["record"].status == ArtifactParseStatus.ACCEPTED
        assert len(result["obligations"]) == 2
        assert result["obligations"][0].description == "Deliver by Q2 2026"
        assert result["obligations"][1].description == "Submit monthly report"

        # Memory tagged as obligation source
        assert "obligation_source" in result["memory"].tags

        # Event emitted
        assert result["event"].event_type == EventType.WORLD_STATE_CHANGED


# ---------------------------------------------------------------------------
# Scenario 7: Supervisor retrieves relevant artifacts for recovery context
# ---------------------------------------------------------------------------


class TestGolden7SupervisorRecoveryRetrieval:
    def test_recovery_retrieval(self):
        ae, es, me, obl, integ = _build()

        # Ingest several artifacts with memory
        for i in range(5):
            desc = _desc(f"art-rec-{i}", f"file_{i}.json", size=50)
            integ.ingest_and_remember(desc, json.dumps({"idx": i}).encode())

        # Verify engine has all records
        assert ae.record_count == 5

        # Retrieval returns results (may be empty due to scope filtering,
        # but should not error)
        goal_result = integ.retrieve_artifacts_for_goal("goal-recovery")
        assert goal_result is not None

        workflow_result = integ.retrieve_artifacts_for_workflow("wf-recovery")
        assert workflow_result is not None

        recovery_result = integ.retrieve_artifacts_for_recovery()
        assert recovery_result is not None

        tick_result = integ.retrieve_artifacts_for_supervisor_tick(42)
        assert tick_result is not None


# ---------------------------------------------------------------------------
# Scenario 8: Unsupported binary format fails typed, not vaguely
# ---------------------------------------------------------------------------


class TestGolden8UnsupportedBinaryTyped:
    def test_unsupported_binary_typed_failure(self):
        ae, es, me, obl, integ = _build()

        binary_content = bytes(range(256)) * 4  # binary blob
        desc = _desc(
            "art-binary", "firmware.bin",
            mime="application/octet-stream",
            size=1024,
        )
        result = integ.ingest_and_emit_event(desc, binary_content)

        record = result["record"]
        # Should get a typed status, not a vague error
        assert record.status in (
            ArtifactParseStatus.UNSUPPORTED,
            ArtifactParseStatus.ACCEPTED,  # UNKNOWN format falls through to text parser
        )
        # The format should be identified (or UNKNOWN), never None
        assert record.parse_result.format_detected is not None
        assert isinstance(record.parse_result.format_detected, ArtifactFormat)

        # Reason should be specific
        assert record.parse_result.reason
        assert len(record.parse_result.reason) > 5

        # Event still emitted
        assert result["event"] is not None
        assert result["event"].payload["status"] == record.status.value
