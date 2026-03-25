"""Tests for mcoi_runtime.core.live_channel_bindings (LiveChannelBindingEngine)
and mcoi_runtime.core.live_parser_bindings (LiveParserBindingEngine).

Covers: constructor validation, all bind_* methods, live adapter/parser
delegation, listing, retrieval, binding counts, and missing connector errors.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.channel_adapter import (
    AdapterStatus,
    ChannelAdapterDescriptor,
    ChannelAdapterFamily,
    NormalizedInbound,
    NormalizedOutbound,
)
from mcoi_runtime.contracts.artifact_parser import (
    ArtifactParserDescriptor,
    NormalizedParseOutput,
    ParserFamily,
    ParserStatus,
)
from mcoi_runtime.contracts.external_connector import (
    ConnectorAuthMode,
    ConnectorHealthState,
    ExternalConnectorType,
    SecretRotationState,
    SecretScope,
)
from mcoi_runtime.core.channel_adapters import ChannelAdapterRegistry
from mcoi_runtime.core.artifact_parsers import ArtifactParserRegistry
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.external_connectors import (
    ExternalConnectorRegistry,
    register_all_test_connectors,
)
from mcoi_runtime.core.live_channel_bindings import LiveChannelBindingEngine
from mcoi_runtime.core.live_parser_bindings import LiveParserBindingEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_all_secrets(connector_reg: ExternalConnectorRegistry) -> None:
    """Set valid SecretScope for every registered connector that requires auth."""
    for cid in list(connector_reg._connectors.keys()):
        conn = connector_reg._connectors[cid]
        if conn.auth_mode() == ConnectorAuthMode.NONE:
            continue
        scope = SecretScope(
            scope_id=f"scope-{cid}",
            connector_id=cid,
            auth_mode=conn.auth_mode(),
            rotation_state=SecretRotationState.CURRENT,
            credential_ref=f"vault://{cid}-key",
            rotation_interval_hours=24,
            last_rotated_at=NOW,
            expires_at="2027-01-01T00:00:00+00:00",
            created_at=NOW,
        )
        connector_reg.set_secret_scope(scope)


def _make_channel_engine() -> tuple[
    LiveChannelBindingEngine,
    ChannelAdapterRegistry,
    ExternalConnectorRegistry,
    EventSpineEngine,
]:
    ch_reg = ChannelAdapterRegistry()
    conn_reg = ExternalConnectorRegistry()
    es = EventSpineEngine()
    register_all_test_connectors(conn_reg)
    _set_all_secrets(conn_reg)
    engine = LiveChannelBindingEngine(ch_reg, conn_reg, es)
    return engine, ch_reg, conn_reg, es


def _make_parser_engine() -> tuple[
    LiveParserBindingEngine,
    ArtifactParserRegistry,
    ExternalConnectorRegistry,
    EventSpineEngine,
]:
    ps_reg = ArtifactParserRegistry()
    conn_reg = ExternalConnectorRegistry()
    es = EventSpineEngine()
    register_all_test_connectors(conn_reg)
    _set_all_secrets(conn_reg)
    engine = LiveParserBindingEngine(ps_reg, conn_reg, es)
    return engine, ps_reg, conn_reg, es


# ===================================================================
# LiveChannelBindingEngine — constructor validation
# ===================================================================


class TestChannelEngineConstructor:
    def test_rejects_non_channel_registry(self):
        conn_reg = ExternalConnectorRegistry()
        es = EventSpineEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="ChannelAdapterRegistry"):
            LiveChannelBindingEngine("bad", conn_reg, es)  # type: ignore[arg-type]

    def test_rejects_non_connector_registry(self):
        ch_reg = ChannelAdapterRegistry()
        es = EventSpineEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="ExternalConnectorRegistry"):
            LiveChannelBindingEngine(ch_reg, "bad", es)  # type: ignore[arg-type]

    def test_rejects_non_event_spine(self):
        ch_reg = ChannelAdapterRegistry()
        conn_reg = ExternalConnectorRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            LiveChannelBindingEngine(ch_reg, conn_reg, "bad")  # type: ignore[arg-type]


# ===================================================================
# LiveChannelBindingEngine — bind methods
# ===================================================================


class TestChannelBindMethods:
    def test_bind_sms(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_sms("test-sms_provider")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.SMS
        assert engine.binding_count == 1

    def test_bind_chat(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_chat("test-chat_provider")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.CHAT

    def test_bind_voice(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_voice("test-voice_provider")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.VOICE

    def test_bind_webhook(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_webhook("test-webhook_provider")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.WEBHOOK

    def test_bind_email(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_email("test-email_provider")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.EMAIL

    def test_bind_social(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_social("test-social_provider")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.SOCIAL

    def test_bind_in_app(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_in_app("test-generic_api")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.family == ChannelAdapterFamily.IN_APP

    def test_bind_registers_adapter_in_channel_registry(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_sms("test-sms_provider")
        adapter = ch_reg.get_adapter(desc.adapter_id)
        assert adapter is not None

    def test_bind_creates_capability_binding(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_sms("test-sms_provider")
        bindings = conn_reg.get_bindings_for_connector("test-sms_provider")
        assert len(bindings) >= 1
        adapter_bindings = conn_reg.get_bindings_for_adapter(desc.adapter_id)
        assert len(adapter_bindings) >= 1

    def test_bind_emits_event(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_sms("test-sms_provider")
        # Check event spine has events
        all_events = es.list_events()
        assert len(all_events) >= 1

    def test_bind_with_custom_adapter_id(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        desc = engine.bind_sms("test-sms_provider", adapter_id="my-sms-adapter")
        assert desc.adapter_id == "my-sms-adapter"

    def test_bind_missing_connector_raises(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.bind_sms("nonexistent-connector")


# ===================================================================
# LiveChannelBindingEngine — live adapter operations
# ===================================================================


class TestChannelLiveAdapterOperations:
    def test_normalize_inbound(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_sms("test-sms_provider")
        adapter = engine.get_live_adapter("live-sms")
        result = adapter.normalize_inbound({
            "from": "+15551234567",
            "body": "Hello world",
            "thread_id": "t-1",
        })
        assert isinstance(result, NormalizedInbound)
        assert result.sender_address == "+15551234567"
        assert result.body_text == "Hello world"
        assert result.family == ChannelAdapterFamily.SMS

    def test_format_outbound(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_sms("test-sms_provider")
        adapter = engine.get_live_adapter("live-sms")
        result = adapter.format_outbound("+15559876543", "Hi there")
        assert isinstance(result, NormalizedOutbound)
        assert result.recipient_address == "+15559876543"
        assert result.body_text == "Hi there"
        assert result.family == ChannelAdapterFamily.SMS

    def test_health_check_delegates(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_chat("test-chat_provider")
        adapter = engine.get_live_adapter("live-chat")
        report = adapter.health_check()
        assert report.adapter_id == "live-chat"
        assert report.status == AdapterStatus.AVAILABLE

    def test_voice_normalize_inbound(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_voice("test-voice_provider")
        adapter = engine.get_live_adapter("live-voice")
        result = adapter.normalize_inbound({
            "caller_id": "+15551112222",
            "transcript": "This is a test call",
            "duration": 60,
        })
        assert isinstance(result, NormalizedInbound)
        assert result.sender_address == "+15551112222"
        assert result.body_text == "This is a test call"


# ===================================================================
# LiveChannelBindingEngine — listing / retrieval
# ===================================================================


class TestChannelListingRetrieval:
    def test_list_live_adapters(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_sms("test-sms_provider")
        engine.bind_chat("test-chat_provider")
        adapters = engine.list_live_adapters()
        assert isinstance(adapters, tuple)
        assert len(adapters) == 2
        assert "live-sms" in adapters
        assert "live-chat" in adapters

    def test_get_live_adapter(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        engine.bind_email("test-email_provider")
        adapter = engine.get_live_adapter("live-email")
        assert adapter.adapter_id() == "live-email"

    def test_get_live_adapter_missing_raises(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.get_live_adapter("nonexistent")

    def test_binding_count(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        assert engine.binding_count == 0
        engine.bind_sms("test-sms_provider")
        assert engine.binding_count == 1
        engine.bind_chat("test-chat_provider")
        assert engine.binding_count == 2

    def test_list_live_adapters_empty(self):
        engine, ch_reg, conn_reg, es = _make_channel_engine()
        assert engine.list_live_adapters() == ()


# ===================================================================
# LiveParserBindingEngine — constructor validation
# ===================================================================


class TestParserEngineConstructor:
    def test_rejects_non_parser_registry(self):
        conn_reg = ExternalConnectorRegistry()
        es = EventSpineEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="ArtifactParserRegistry"):
            LiveParserBindingEngine("bad", conn_reg, es)  # type: ignore[arg-type]

    def test_rejects_non_connector_registry(self):
        ps_reg = ArtifactParserRegistry()
        es = EventSpineEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="ExternalConnectorRegistry"):
            LiveParserBindingEngine(ps_reg, "bad", es)  # type: ignore[arg-type]

    def test_rejects_non_event_spine(self):
        ps_reg = ArtifactParserRegistry()
        conn_reg = ExternalConnectorRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            LiveParserBindingEngine(ps_reg, conn_reg, "bad")  # type: ignore[arg-type]


# ===================================================================
# LiveParserBindingEngine — bind methods
# ===================================================================


class TestParserBindMethods:
    def test_bind_pdf(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_pdf("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.DOCUMENT
        assert engine.binding_count == 1

    def test_bind_docx(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_docx("test-parser_provider", parser_id="my-docx")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.DOCUMENT
        assert desc.parser_id == "my-docx"

    def test_bind_xlsx(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_xlsx("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.SPREADSHEET

    def test_bind_pptx(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_pptx("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.PRESENTATION

    def test_bind_image(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_image("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.IMAGE

    def test_bind_audio(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_audio("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.AUDIO

    def test_bind_archive(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_archive("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.ARCHIVE

    def test_bind_repo(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_repo("test-parser_provider")
        assert isinstance(desc, ArtifactParserDescriptor)
        assert desc.family == ParserFamily.REPOSITORY

    def test_bind_registers_parser_in_registry(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_pdf("test-parser_provider")
        parser = ps_reg.get_parser(desc.parser_id)
        assert parser is not None

    def test_bind_creates_capability_binding(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        desc = engine.bind_pdf("test-parser_provider")
        bindings = conn_reg.get_bindings_for_connector("test-parser_provider")
        assert len(bindings) >= 1
        parser_bindings = conn_reg.get_bindings_for_parser(desc.parser_id)
        assert len(parser_bindings) >= 1

    def test_bind_emits_event(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_pdf("test-parser_provider")
        all_events = es.list_events()
        assert len(all_events) >= 1

    def test_bind_missing_connector_raises(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.bind_pdf("nonexistent-connector")


# ===================================================================
# LiveParserBindingEngine — live parser operations
# ===================================================================


class TestParserLiveOperations:
    def test_parse_delegates_to_connector(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_pdf("test-parser_provider")
        parser = engine.get_live_parser("live-document")
        result = parser.parse("artifact-1", "report.pdf", b"PDF content here")
        assert isinstance(result, NormalizedParseOutput)
        assert result.parser_id == "live-document"
        assert result.artifact_id == "artifact-1"
        assert "PDF content here" in result.text_content
        assert result.extracted_metadata["connector_id"] == "test-parser_provider"
        assert result.extracted_metadata["connector_success"] is True

    def test_health_check_delegates(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_xlsx("test-parser_provider")
        parser = engine.get_live_parser("live-spreadsheet")
        report = parser.health_check()
        assert report.parser_id == "live-spreadsheet"
        assert report.status == ParserStatus.AVAILABLE

    def test_can_parse_by_extension(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_pdf("test-parser_provider")
        parser = engine.get_live_parser("live-document")
        assert parser.can_parse("report.pdf") is True
        assert parser.can_parse("report.txt") is False

    def test_can_parse_by_mime_type(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_image("test-parser_provider")
        parser = engine.get_live_parser("live-image")
        assert parser.can_parse("photo.unknown", mime_type="image/png") is True
        assert parser.can_parse("doc.unknown", mime_type="text/plain") is False


# ===================================================================
# LiveParserBindingEngine — listing / retrieval
# ===================================================================


class TestParserListingRetrieval:
    def test_list_live_parsers(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_pdf("test-parser_provider")
        engine.bind_xlsx("test-parser_provider", parser_id="live-xlsx-custom")
        parsers = engine.list_live_parsers()
        assert isinstance(parsers, tuple)
        assert len(parsers) == 2

    def test_get_live_parser(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        engine.bind_audio("test-parser_provider")
        parser = engine.get_live_parser("live-audio")
        assert parser.parser_id() == "live-audio"

    def test_get_live_parser_missing_raises(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            engine.get_live_parser("nonexistent")

    def test_binding_count(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        assert engine.binding_count == 0
        engine.bind_pdf("test-parser_provider")
        assert engine.binding_count == 1
        engine.bind_archive("test-parser_provider")
        assert engine.binding_count == 2

    def test_list_live_parsers_empty(self):
        engine, ps_reg, conn_reg, es = _make_parser_engine()
        assert engine.list_live_parsers() == ()
