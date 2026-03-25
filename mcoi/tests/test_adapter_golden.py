"""Purpose: golden scenario tests for AdapterIntegrationBridge — end-to-end
workflows validating the full adapter/parser pipeline with commitment
extraction, memory recording, and event spine integration.
Governance scope: golden scenario coverage for adapter integration.
Dependencies: adapter_integration, channel_adapters, artifact_parsers,
    event_spine, memory_mesh, commitment_extraction.
Invariants:
  - Every scenario exercises a real-world communication or artifact workflow.
  - Events, memory, and commitments are verified for each scenario.
  - Deterministic test adapters/parsers produce predictable output.
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
from mcoi_runtime.contracts.commitment_extraction import (
    CommitmentType,
)
from mcoi_runtime.contracts.event import EventRecord
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
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
# Golden Scenarios
# ===================================================================


class TestGoldenScenarios:
    """Seven end-to-end golden scenarios for the AdapterIntegrationBridge."""

    # ---------------------------------------------------------------
    # 1. SMS inbound with approval -> commitment extracted, memory recorded
    # ---------------------------------------------------------------

    def test_sms_inbound_with_approval(self):
        _cr, _pr, es, me, ce, bridge = _build()

        raw = {
            "from": "+15559876543",
            "body": "The budget request is approved by EOD, please proceed",
        }
        result = bridge.ingest_and_extract_commitments("test-sms", raw)

        # Normalized as SMS
        normalized = result["normalized"]
        assert isinstance(normalized, NormalizedInbound)
        assert normalized.family == ChannelAdapterFamily.SMS
        assert normalized.sender_address == "+15559876543"

        # Commitment extracted — approval signal detected
        extraction = result["extraction"]
        assert extraction is not None
        assert len(extraction.candidates) >= 1
        approval_types = [
            c for c in extraction.candidates
            if c.commitment_type == CommitmentType.APPROVAL
        ]
        assert len(approval_types) >= 1, "expected at least one approval commitment"

        # Memory recorded for the ingest
        mem = result["memory"]
        assert isinstance(mem, MemoryRecord)
        assert mem.memory_type == MemoryType.OBSERVATION
        assert me.get_memory(mem.memory_id) is not None

        # Events emitted: ingest event + extraction event
        assert es.get_event(result["ingest_event"].event_id) is not None
        assert es.get_event(result["extraction_event"].event_id) is not None
        assert result["extraction_event"].payload["candidate_count"] >= 1

    # ---------------------------------------------------------------
    # 2. Voice transcript with follow-up -> commitment extracted
    # ---------------------------------------------------------------

    def test_voice_transcript_with_follow_up(self):
        _cr, _pr, es, me, ce, bridge = _build()

        raw = {
            "caller_id": "+15551112222",
            "transcript": (
                "Let's follow up on the deployment issue. "
                "Sarah will handle the rollback within 2 hours."
            ),
            "duration": 300,
            "call_subject": "Deployment incident",
        }
        result = bridge.ingest_and_extract_commitments("test-voice", raw)

        # Normalized as VOICE
        normalized = result["normalized"]
        assert normalized.family == ChannelAdapterFamily.VOICE
        assert normalized.sender_address == "+15551112222"

        # Commitment extracted — follow-up and/or task detected
        extraction = result["extraction"]
        assert extraction is not None
        assert len(extraction.candidates) >= 1

        follow_ups = [
            c for c in extraction.candidates
            if c.commitment_type == CommitmentType.FOLLOW_UP
        ]
        assert len(follow_ups) >= 1, "expected at least one follow-up commitment"

        # Memory and events present
        assert me.get_memory(result["memory"].memory_id) is not None
        assert es.get_event(result["ingest_event"].event_id) is not None

    # ---------------------------------------------------------------
    # 3. Auto-parse CSV -> table output with headers, memory recorded
    # ---------------------------------------------------------------

    def test_auto_parse_csv_table_output(self):
        _cr, _pr, es, me, _ce, bridge = _build()

        csv_content = b"product,price,quantity\nWidget,9.99,100\nGadget,24.50,50\nTool,5.00,200"
        result = bridge.auto_parse_artifact("art-csv-001", "sales_data.csv", csv_content)

        # Output has table structure
        output = result["output"]
        assert output is not None
        assert isinstance(output, NormalizedParseOutput)
        assert output.family == ParserFamily.SPREADSHEET
        assert output.output_kind == ParseOutputKind.TABLE
        assert output.has_tables is True

        # Structured data has headers
        assert output.structured_data is not None
        headers = output.structured_data.get("headers", ())
        assert "product" in headers
        assert "price" in headers
        assert "quantity" in headers
        assert output.structured_data["row_count"] == 3

        # Memory recorded
        mem = result["memory"]
        assert isinstance(mem, MemoryRecord)
        assert mem.memory_type == MemoryType.ARTIFACT
        assert me.get_memory(mem.memory_id) is not None

        # Event emitted
        event = result["event"]
        assert event.payload["action"] == "artifact_auto_parsed"
        assert es.get_event(event.event_id) is not None

    # ---------------------------------------------------------------
    # 4. PDF parse + commitment extraction pipeline
    # ---------------------------------------------------------------

    def test_pdf_parse_and_commitment_extraction(self):
        _cr, _pr, es, me, _ce, bridge = _build()

        pdf_content = b"The project proposal is approved deadline by Friday. Escalate to management if delayed."
        result = bridge.parse_and_extract_commitments(
            "test-pdf", "art-pdf-001", "proposal.pdf", pdf_content,
        )

        # Parsed output
        output = result["output"]
        assert isinstance(output, NormalizedParseOutput)
        assert output.family == ParserFamily.DOCUMENT
        assert output.artifact_id == "art-pdf-001"

        # Commitments extracted from parsed text
        extraction = result["extraction"]
        assert extraction is not None
        assert len(extraction.candidates) >= 1

        # At least one approval commitment
        approval_types = [
            c for c in extraction.candidates
            if c.commitment_type == CommitmentType.APPROVAL
        ]
        assert len(approval_types) >= 1

        # Parse event and extraction event both present
        assert result["parse_event"].payload["action"] == "artifact_parsed"
        assert result["extraction_event"].payload["action"] == "artifact_commitments_extracted"
        assert es.get_event(result["parse_event"].event_id) is not None
        assert es.get_event(result["extraction_event"].event_id) is not None

        # Memory recorded
        assert me.get_memory(result["memory"].memory_id) is not None

    # ---------------------------------------------------------------
    # 5. Route via chat family -> adapter selected, outbound formatted
    # ---------------------------------------------------------------

    def test_route_via_chat_family(self):
        _cr, _pr, es, _me, _ce, bridge = _build()

        result = bridge.route_by_family(
            ChannelAdapterFamily.CHAT,
            "dev-channel@slack",
            "Deployment complete: all services green.",
        )

        # Adapter selected and outbound formatted
        outbound = result["outbound"]
        assert outbound is not None
        assert isinstance(outbound, NormalizedOutbound)
        assert outbound.family == ChannelAdapterFamily.CHAT
        assert outbound.recipient_address == "dev-channel@slack"
        assert "Deployment complete" in outbound.body_text

        # At least one adapter was available
        assert result["adapter_count"] >= 1

        # Event emitted for routing
        event = result["event"]
        assert event.payload["action"] == "adapter_routed"
        assert event.payload["family"] == "chat"
        assert es.get_event(event.event_id) is not None

    # ---------------------------------------------------------------
    # 6. Health check all adapters -> 7 reports, all AVAILABLE
    # ---------------------------------------------------------------

    def test_health_check_all_adapters(self):
        _cr, _pr, es, _me, _ce, bridge = _build()

        result = bridge.check_all_adapter_health()

        reports = result["reports"]
        assert len(reports) == 7, f"expected 7 adapter reports, got {len(reports)}"

        for report in reports:
            assert report.status == AdapterStatus.AVAILABLE
            assert report.reliability_score > 0
            assert report.adapter_id  # non-empty

        # All adapter IDs are unique
        adapter_ids = [r.adapter_id for r in reports]
        assert len(set(adapter_ids)) == 7

        # Event emitted
        event = result["event"]
        assert event.payload["action"] == "all_adapters_health_checked"
        assert event.payload["adapter_count"] == 7
        assert es.get_event(event.event_id) is not None

    # ---------------------------------------------------------------
    # 7. Unknown file format -> auto_parse returns None, event emitted
    # ---------------------------------------------------------------

    def test_unknown_file_format_returns_none(self):
        _cr, _pr, es, _me, _ce, bridge = _build()

        result = bridge.auto_parse_artifact(
            "art-unknown-001",
            "mystery_file.qwerty789",
            b"completely unknown binary content",
        )

        # No parser found
        assert result["output"] is None

        # Event emitted indicating no parser
        event = result["event"]
        assert isinstance(event, EventRecord)
        assert event.payload["action"] == "artifact_parse_no_parser"
        assert event.payload["artifact_id"] == "art-unknown-001"
        assert event.payload["filename"] == "mystery_file.qwerty789"
        assert es.get_event(event.event_id) is not None

        # No memory recorded (output was None)
        assert "memory" not in result
