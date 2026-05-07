"""Purpose: verify AdapterIntegrationBridge — channel adapter and artifact
parser operations wired to event spine, memory mesh, and commitment extraction.
Governance scope: adapter integration bridge tests only.
Dependencies: adapter_integration, channel_adapters, artifact_parsers,
    event_spine, memory_mesh, commitment_extraction.
Invariants:
  - Every adapter/parser operation emits an event.
  - Extracted commitments are routed to obligation runtime.
  - All outputs are immutable.
  - Adapter health is surfaced via events.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.channel_adapter import (
    AdapterStatus,
    ChannelAdapterFamily,
    NormalizedInbound,
    NormalizedOutbound,
)
from mcoi_runtime.contracts.artifact_parser import (
    NormalizedParseOutput,
    ParseOutputKind,
    ParserFamily,
    ParserStatus,
)
from mcoi_runtime.contracts.event import EventRecord
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryType,
)
from mcoi_runtime.core.adapter_integration import AdapterIntegrationBridge
from mcoi_runtime.core.artifact_parsers import (
    ArtifactParserRegistry,
    register_all_test_parsers,
)
from mcoi_runtime.core.channel_adapters import (
    ChannelAdapterRegistry,
    register_all_test_adapters,
)
from mcoi_runtime.core.commitment_extraction import CommitmentExtractionEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _build():
    cr = ChannelAdapterRegistry()
    pr = ArtifactParserRegistry()
    es = EventSpineEngine()
    me = MemoryMeshEngine()
    ce = CommitmentExtractionEngine()
    register_all_test_adapters(cr)
    register_all_test_parsers(pr)
    bridge = AdapterIntegrationBridge(cr, pr, es, me, ce)
    return cr, pr, es, me, ce, bridge


# ===================================================================
# Constructor validation
# ===================================================================


class TestConstructorValidation:
    """AdapterIntegrationBridge rejects invalid constructor arguments."""

    def test_valid_construction(self):
        _cr, _pr, _es, _me, _ce, bridge = _build()
        assert isinstance(bridge, AdapterIntegrationBridge)

    def test_bad_channel_registry(self):
        pr = ArtifactParserRegistry()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        ce = CommitmentExtractionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="channel_registry"):
            AdapterIntegrationBridge("not-a-registry", pr, es, me, ce)

    def test_bad_parser_registry(self):
        cr = ChannelAdapterRegistry()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        ce = CommitmentExtractionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="parser_registry"):
            AdapterIntegrationBridge(cr, "not-a-registry", es, me, ce)

    def test_bad_event_spine(self):
        cr = ChannelAdapterRegistry()
        pr = ArtifactParserRegistry()
        me = MemoryMeshEngine()
        ce = CommitmentExtractionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            AdapterIntegrationBridge(cr, pr, "not-an-engine", me, ce)

    def test_bad_memory_engine(self):
        cr = ChannelAdapterRegistry()
        pr = ArtifactParserRegistry()
        es = EventSpineEngine()
        ce = CommitmentExtractionEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            AdapterIntegrationBridge(cr, pr, es, "not-an-engine", ce)

    def test_bad_extraction_engine(self):
        cr = ChannelAdapterRegistry()
        pr = ArtifactParserRegistry()
        es = EventSpineEngine()
        me = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="extraction_engine"):
            AdapterIntegrationBridge(cr, pr, es, me, "not-an-engine")


# ===================================================================
# ingest_via_adapter
# ===================================================================


class TestIngestViaAdapter:
    """ingest_via_adapter normalizes inbound, emits event, records memory."""

    def test_normalizes_emits_records(self):
        _cr, _pr, es, me, _ce, bridge = _build()
        raw = {"from": "+15551234567", "body": "Hello from SMS"}
        result = bridge.ingest_via_adapter("test-sms", raw)

        # Normalized inbound
        normalized = result["normalized"]
        assert isinstance(normalized, NormalizedInbound)
        assert normalized.family == ChannelAdapterFamily.SMS
        assert normalized.sender_address == "+15551234567"
        assert normalized.body_text == "Hello from SMS"

        # Event emitted
        event = result["event"]
        assert isinstance(event, EventRecord)
        assert event.payload["action"] == "adapter_inbound_normalized"
        assert event.payload["adapter_id"] == "test-sms"
        assert es.get_event(event.event_id) is not None

        # Memory recorded
        mem = result["memory"]
        assert isinstance(mem, MemoryRecord)
        assert mem.memory_type == MemoryType.OBSERVATION
        assert mem.scope == MemoryScope.GLOBAL
        assert me.get_memory(mem.memory_id) is not None

    def test_inbound_memory_title_redacts_family_and_sender(self):
        _cr, _pr, _es, _me, _ce, bridge = _build()
        raw = {"from": "secret@example.com", "body": "Hello from chat"}
        result = bridge.ingest_via_adapter("test-email", raw)
        mem = result["memory"]
        assert mem.title == "Inbound message"
        assert "email" not in mem.title
        assert "secret@example.com" not in mem.title


# ===================================================================
# ingest_and_extract_commitments
# ===================================================================


class TestIngestAndExtractCommitments:
    """ingest_and_extract_commitments normalizes and extracts commitments."""

    def test_normalizes_and_extracts(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        raw = {"from": "manager@co.com", "body": "This is approved by EOD"}
        result = bridge.ingest_and_extract_commitments("test-email", raw)

        # Normalized inbound is present
        normalized = result["normalized"]
        assert isinstance(normalized, NormalizedInbound)
        assert normalized.family == ChannelAdapterFamily.EMAIL

        # Extraction result has candidates
        extraction = result["extraction"]
        assert extraction is not None
        assert len(extraction.candidates) >= 1

        # Two events emitted: ingest + extraction
        assert result["ingest_event"] is not None
        assert result["extraction_event"] is not None
        assert result["extraction_event"].payload["action"] == "adapter_commitments_extracted"

        # Memory recorded
        assert result["memory"] is not None


# ===================================================================
# send_via_adapter
# ===================================================================


class TestSendViaAdapter:
    """send_via_adapter formats outbound and emits event."""

    def test_formats_outbound_emits_event(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.send_via_adapter(
            "test-chat", "user@slack", "Hello from bridge",
        )

        outbound = result["outbound"]
        assert isinstance(outbound, NormalizedOutbound)
        assert outbound.family == ChannelAdapterFamily.CHAT
        assert outbound.recipient_address == "user@slack"
        assert outbound.body_text == "Hello from bridge"

        event = result["event"]
        assert event.payload["action"] == "adapter_outbound_sent"
        assert event.payload["recipient"] == "user@slack"
        assert es.get_event(event.event_id) is not None


# ===================================================================
# check_adapter_health
# ===================================================================


class TestCheckAdapterHealth:
    """check_adapter_health returns report and emits event."""

    def test_returns_report_emits_event(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.check_adapter_health("test-sms")

        report = result["report"]
        assert report.adapter_id == "test-sms"
        assert report.status == AdapterStatus.AVAILABLE
        assert report.reliability_score > 0

        event = result["event"]
        assert event.payload["action"] == "adapter_health_checked"
        assert event.payload["adapter_id"] == "test-sms"
        assert es.get_event(event.event_id) is not None


# ===================================================================
# check_all_adapter_health
# ===================================================================


class TestCheckAllAdapterHealth:
    """check_all_adapter_health returns all reports."""

    def test_returns_all_reports(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.check_all_adapter_health()

        reports = result["reports"]
        assert len(reports) == 7  # one per family
        for report in reports:
            assert report.status == AdapterStatus.AVAILABLE

        event = result["event"]
        assert event.payload["action"] == "all_adapters_health_checked"
        assert event.payload["adapter_count"] == 7
        assert es.get_event(event.event_id) is not None


# ===================================================================
# route_by_family
# ===================================================================


class TestRouteByFamily:
    """route_by_family routes to available adapters and emits event."""

    def test_routes_to_available_adapter(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.route_by_family(
            ChannelAdapterFamily.CHAT, "user@teams", "Routed message",
        )

        outbound = result["outbound"]
        assert outbound is not None
        assert isinstance(outbound, NormalizedOutbound)
        assert outbound.family == ChannelAdapterFamily.CHAT
        assert outbound.recipient_address == "user@teams"
        assert result["adapter_count"] >= 1

        event = result["event"]
        assert event.payload["action"] == "adapter_routed"
        assert event.payload["family"] == "chat"
        assert es.get_event(event.event_id) is not None


# ===================================================================
# parse_artifact
# ===================================================================


class TestParseArtifact:
    """parse_artifact parses, emits event, and records memory."""

    def test_parses_emits_records(self):
        _cr, _pr, es, me, _ce, bridge = _build()
        result = bridge.parse_artifact(
            "test-pdf", "art-001", "report.pdf", b"test content",
        )

        output = result["output"]
        assert isinstance(output, NormalizedParseOutput)
        assert output.family == ParserFamily.DOCUMENT
        assert output.artifact_id == "art-001"
        assert output.word_count >= 0

        event = result["event"]
        assert event.payload["action"] == "artifact_parsed"
        assert event.payload["parser_id"] == "test-pdf"
        assert event.payload["artifact_id"] == "art-001"
        assert es.get_event(event.event_id) is not None

        mem = result["memory"]
        assert isinstance(mem, MemoryRecord)
        assert mem.memory_type == MemoryType.ARTIFACT
        assert me.get_memory(mem.memory_id) is not None

    def test_parsed_memory_title_redacts_family_and_filename(self):
        _cr, _pr, _es, _me, _ce, bridge = _build()
        result = bridge.parse_artifact(
            "test-pdf", "art-secret", "secret-report.pdf", b"test content",
        )
        mem = result["memory"]
        assert mem.title == "Parsed artifact"
        assert "document" not in mem.title
        assert "secret-report.pdf" not in mem.title


# ===================================================================
# auto_parse_artifact
# ===================================================================


class TestAutoParseArtifact:
    """auto_parse_artifact auto-selects parser; returns None for unknown."""

    def test_auto_selects_csv_parser(self):
        _cr, _pr, es, me, _ce, bridge = _build()
        csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,LA"
        result = bridge.auto_parse_artifact("art-csv", "data.csv", csv_content)

        output = result["output"]
        assert output is not None
        assert isinstance(output, NormalizedParseOutput)
        assert output.family == ParserFamily.SPREADSHEET
        assert output.output_kind == ParseOutputKind.TABLE

        event = result["event"]
        assert event.payload["action"] == "artifact_auto_parsed"
        assert es.get_event(event.event_id) is not None

        mem = result["memory"]
        assert isinstance(mem, MemoryRecord)
        assert me.get_memory(mem.memory_id) is not None

    def test_auto_parsed_memory_title_redacts_family_and_filename(self):
        _cr, _pr, _es, _me, _ce, bridge = _build()
        csv_content = b"name,age,city\nAlice,30,NYC\nBob,25,LA"
        result = bridge.auto_parse_artifact("art-secret", "secret-data.csv", csv_content)
        mem = result["memory"]
        assert mem.title == "Auto-parsed artifact"
        assert "spreadsheet" not in mem.title
        assert "secret-data.csv" not in mem.title

    def test_returns_none_for_unknown_format(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.auto_parse_artifact(
            "art-unk", "unknown.xyz123", b"mystery content",
        )

        assert result["output"] is None
        event = result["event"]
        assert event.payload["action"] == "artifact_parse_no_parser"
        assert es.get_event(event.event_id) is not None


# ===================================================================
# parse_and_extract_commitments
# ===================================================================


class TestParseAndExtractCommitments:
    """parse_and_extract_commitments parses and extracts commitments."""

    def test_parses_and_extracts(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        content = b"The proposal is approved deadline by Friday"
        result = bridge.parse_and_extract_commitments(
            "test-pdf", "art-commit", "proposal.pdf", content,
        )

        output = result["output"]
        assert isinstance(output, NormalizedParseOutput)

        extraction = result["extraction"]
        assert extraction is not None
        assert len(extraction.candidates) >= 1

        assert result["parse_event"] is not None
        assert result["extraction_event"].payload["action"] == "artifact_commitments_extracted"
        assert result["memory"] is not None


# ===================================================================
# check_parser_health
# ===================================================================


class TestCheckParserHealth:
    """check_parser_health returns report and emits event."""

    def test_returns_report_emits_event(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.check_parser_health("test-pdf")

        report = result["report"]
        assert report.parser_id == "test-pdf"
        assert report.status == ParserStatus.AVAILABLE
        assert report.reliability_score > 0

        event = result["event"]
        assert event.payload["action"] == "parser_health_checked"
        assert event.payload["parser_id"] == "test-pdf"
        assert es.get_event(event.event_id) is not None


# ===================================================================
# check_all_parser_health
# ===================================================================


class TestCheckAllParserHealth:
    """check_all_parser_health returns all reports."""

    def test_returns_all_reports(self):
        _cr, _pr, es, _me, _ce, bridge = _build()
        result = bridge.check_all_parser_health()

        reports = result["reports"]
        assert len(reports) == 8  # one per parser family
        for report in reports:
            assert report.status == ParserStatus.AVAILABLE

        event = result["event"]
        assert event.payload["action"] == "all_parsers_health_checked"
        assert event.payload["parser_count"] == 8
        assert es.get_event(event.event_id) is not None
