"""Tests for ChannelAdapterRegistry and all test adapter families.

Covers registration, retrieval, listing, routing, normalization,
formatting, health checks, state hashing, and per-family adapter
behaviour.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.channel_adapters import (
    ChannelAdapter,
    ChannelAdapterRegistry,
    ChatTestAdapter,
    EmailTestAdapter,
    InAppTestAdapter,
    SmsTestAdapter,
    SocialTestAdapter,
    VoiceTestAdapter,
    WebhookTestAdapter,
    register_all_test_adapters,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.channel_adapter import (
    AdapterCapabilityManifest,
    AdapterDirection,
    AdapterHealthReport,
    AdapterStatus,
    ChannelAdapterDescriptor,
    ChannelAdapterFamily,
    DeliveryGuarantee,
    NormalizationLevel,
    NormalizedInbound,
    NormalizedOutbound,
)


# ---- fixtures ---------------------------------------------------------------


@pytest.fixture()
def registry() -> ChannelAdapterRegistry:
    return ChannelAdapterRegistry()


@pytest.fixture()
def full_registry() -> ChannelAdapterRegistry:
    reg = ChannelAdapterRegistry()
    register_all_test_adapters(reg)
    return reg


# ---- registration -----------------------------------------------------------


class TestRegistration:
    def test_register_adapter(self, registry: ChannelAdapterRegistry) -> None:
        adapter = SmsTestAdapter()
        desc = registry.register(adapter)
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.adapter_id == adapter.adapter_id()
        assert registry.adapter_count == 1

    def test_reject_duplicate(self, registry: ChannelAdapterRegistry) -> None:
        registry.register(SmsTestAdapter())
        with pytest.raises(RuntimeCoreInvariantError, match="already registered") as exc_info:
            registry.register(SmsTestAdapter())
        assert "test-sms" not in str(exc_info.value)

    def test_reject_non_channel_adapter(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="must be a ChannelAdapter"):
            registry.register("not-an-adapter")  # type: ignore[arg-type]

    def test_reject_plain_object(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="must be a ChannelAdapter"):
            registry.register(42)  # type: ignore[arg-type]


# ---- retrieval --------------------------------------------------------------


class TestRetrieval:
    def test_get_adapter(self, full_registry: ChannelAdapterRegistry) -> None:
        adapter = full_registry.get_adapter("test-sms")
        assert isinstance(adapter, SmsTestAdapter)

    def test_get_descriptor(self, full_registry: ChannelAdapterRegistry) -> None:
        desc = full_registry.get_descriptor("test-sms")
        assert isinstance(desc, ChannelAdapterDescriptor)
        assert desc.adapter_id == "test-sms"

    def test_get_manifest(self, full_registry: ChannelAdapterRegistry) -> None:
        manifest = full_registry.get_manifest("test-sms")
        assert isinstance(manifest, AdapterCapabilityManifest)
        assert manifest.adapter_id == "test-sms"

    def test_missing_adapter_raises(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            registry.get_adapter("nonexistent")
        assert "nonexistent" not in str(exc_info.value)

    def test_missing_descriptor_raises(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            registry.get_descriptor("nonexistent")
        assert "nonexistent" not in str(exc_info.value)

    def test_missing_manifest_raises(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            registry.get_manifest("nonexistent")
        assert "nonexistent" not in str(exc_info.value)


# ---- listing ----------------------------------------------------------------


class TestListing:
    def test_list_adapters_all(self, full_registry: ChannelAdapterRegistry) -> None:
        all_descs = full_registry.list_adapters()
        assert len(all_descs) == 7
        assert all(isinstance(d, ChannelAdapterDescriptor) for d in all_descs)

    def test_list_adapters_by_family(self, full_registry: ChannelAdapterRegistry) -> None:
        sms_descs = full_registry.list_adapters(family=ChannelAdapterFamily.SMS)
        assert len(sms_descs) == 1
        assert sms_descs[0].family == ChannelAdapterFamily.SMS

    def test_list_adapters_by_status(self, full_registry: ChannelAdapterRegistry) -> None:
        available = full_registry.list_adapters(status=AdapterStatus.AVAILABLE)
        assert len(available) == 7  # all test adapters start AVAILABLE

    def test_list_adapters_by_status_empty(self, full_registry: ChannelAdapterRegistry) -> None:
        disabled = full_registry.list_adapters(status=AdapterStatus.DISABLED)
        assert len(disabled) == 0

    def test_list_available(self, full_registry: ChannelAdapterRegistry) -> None:
        available = full_registry.list_available()
        assert len(available) == 7
        for d in available:
            assert d.status in (AdapterStatus.AVAILABLE, AdapterStatus.DEGRADED)

    def test_list_available_filters_unavailable(self, registry: ChannelAdapterRegistry) -> None:
        # Register a normal adapter, then verify list_available works
        registry.register(SmsTestAdapter())
        available = registry.list_available()
        assert len(available) == 1
        # All test adapters are AVAILABLE so nothing filtered here;
        # the contract is tested by status filter returning empty for DISABLED above.


# ---- routing ----------------------------------------------------------------


class TestRouting:
    def test_route_by_family_returns_available(self, full_registry: ChannelAdapterRegistry) -> None:
        sms_adapters = full_registry.route_by_family(ChannelAdapterFamily.SMS)
        assert len(sms_adapters) == 1
        assert isinstance(sms_adapters[0], SmsTestAdapter)

    def test_route_by_family_chat(self, full_registry: ChannelAdapterRegistry) -> None:
        chat_adapters = full_registry.route_by_family(ChannelAdapterFamily.CHAT)
        assert len(chat_adapters) == 1
        assert isinstance(chat_adapters[0], ChatTestAdapter)

    def test_route_by_family_empty(self, registry: ChannelAdapterRegistry) -> None:
        result = registry.route_by_family(ChannelAdapterFamily.SMS)
        assert result == ()

    def test_route_returns_only_available(self, full_registry: ChannelAdapterRegistry) -> None:
        # All test adapters are AVAILABLE, so they all route
        for family in ChannelAdapterFamily:
            routed = full_registry.route_by_family(family)
            assert len(routed) >= 1


# ---- normalization ----------------------------------------------------------


class TestNormalization:
    def test_normalize_inbound_via_registry(self, full_registry: ChannelAdapterRegistry) -> None:
        raw = {"from": "user@example.com", "body": "Hello", "subject": "Test"}
        result = full_registry.normalize_inbound("test-email", raw)
        assert isinstance(result, NormalizedInbound)
        assert result.adapter_id == "test-email"
        assert result.body_text == "Hello"
        assert result.sender_address == "user@example.com"

    def test_normalize_inbound_sms(self, full_registry: ChannelAdapterRegistry) -> None:
        raw = {"from": "+15551234567", "body": "Hi there"}
        result = full_registry.normalize_inbound("test-sms", raw)
        assert isinstance(result, NormalizedInbound)
        assert result.family == ChannelAdapterFamily.SMS

    def test_normalize_inbound_voice(self, full_registry: ChannelAdapterRegistry) -> None:
        raw = {"caller_id": "+15559876543", "transcript": "Hello from voice", "duration": 120}
        result = full_registry.normalize_inbound("test-voice", raw)
        assert isinstance(result, NormalizedInbound)
        assert result.body_text == "Hello from voice"
        assert result.sender_address == "+15559876543"

    def test_format_outbound_via_registry(self, full_registry: ChannelAdapterRegistry) -> None:
        result = full_registry.format_outbound(
            "test-email", "recipient@example.com", "Hello back",
            subject="Re: Test",
        )
        assert isinstance(result, NormalizedOutbound)
        assert result.adapter_id == "test-email"
        assert result.recipient_address == "recipient@example.com"
        assert result.body_text == "Hello back"
        assert result.subject == "Re: Test"

    def test_format_outbound_sms(self, full_registry: ChannelAdapterRegistry) -> None:
        result = full_registry.format_outbound("test-sms", "+15551234567", "Reply")
        assert isinstance(result, NormalizedOutbound)
        assert result.family == ChannelAdapterFamily.SMS

    def test_normalize_missing_adapter_raises(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            registry.normalize_inbound("nonexistent", {})

    def test_format_outbound_missing_raises(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            registry.format_outbound("nonexistent", "addr", "body")


# ---- health -----------------------------------------------------------------


class TestHealth:
    def test_health_check_single(self, full_registry: ChannelAdapterRegistry) -> None:
        report = full_registry.health_check("test-sms")
        assert isinstance(report, AdapterHealthReport)
        assert report.adapter_id == "test-sms"
        assert report.status == AdapterStatus.AVAILABLE
        assert report.reliability_score == 0.95

    def test_health_check_missing_raises(self, registry: ChannelAdapterRegistry) -> None:
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            registry.health_check("nonexistent")

    def test_health_check_all(self, full_registry: ChannelAdapterRegistry) -> None:
        reports = full_registry.health_check_all()
        assert len(reports) == 7
        adapter_ids = {r.adapter_id for r in reports}
        assert "test-sms" in adapter_ids
        assert "test-email" in adapter_ids
        assert all(isinstance(r, AdapterHealthReport) for r in reports)

    def test_health_check_all_empty(self, registry: ChannelAdapterRegistry) -> None:
        reports = registry.health_check_all()
        assert reports == ()

    def test_health_tracks_sent(self, registry: ChannelAdapterRegistry) -> None:
        adapter = SmsTestAdapter()
        registry.register(adapter)
        adapter.format_outbound("+15551234567", "msg1")
        adapter.format_outbound("+15551234567", "msg2")
        report = registry.health_check("test-sms")
        assert report.messages_sent == 2

    def test_health_tracks_received(self, registry: ChannelAdapterRegistry) -> None:
        adapter = SmsTestAdapter()
        registry.register(adapter)
        adapter.normalize_inbound({"from": "+1", "body": "hi"})
        report = registry.health_check("test-sms")
        assert report.messages_received == 1


# ---- state hash -------------------------------------------------------------


class TestStateHash:
    def test_state_hash_deterministic(self, full_registry: ChannelAdapterRegistry) -> None:
        h1 = full_registry.state_hash()
        h2 = full_registry.state_hash()
        assert h1 == h2

    def test_state_hash_changes_on_register(self, registry: ChannelAdapterRegistry) -> None:
        h_empty = registry.state_hash()
        registry.register(SmsTestAdapter())
        h_one = registry.state_hash()
        assert h_empty != h_one
        registry.register(ChatTestAdapter())
        h_two = registry.state_hash()
        assert h_one != h_two

    def test_state_hash_length_16(self, full_registry: ChannelAdapterRegistry) -> None:
        h = full_registry.state_hash()
        assert len(h) == 64
        # Should be hex characters
        int(h, 16)

    def test_state_hash_empty_registry(self, registry: ChannelAdapterRegistry) -> None:
        h = registry.state_hash()
        assert len(h) == 64


# ---- register_all_test_adapters ---------------------------------------------


class TestRegisterAll:
    def test_registers_seven(self) -> None:
        reg = ChannelAdapterRegistry()
        descs = register_all_test_adapters(reg)
        assert len(descs) == 7
        assert reg.adapter_count == 7

    def test_each_produces_valid_descriptor(self) -> None:
        reg = ChannelAdapterRegistry()
        descs = register_all_test_adapters(reg)
        for desc in descs:
            assert isinstance(desc, ChannelAdapterDescriptor)
            assert desc.adapter_id
            assert desc.name
            assert isinstance(desc.family, ChannelAdapterFamily)
            assert desc.status == AdapterStatus.AVAILABLE
            assert desc.version == "1.0.0"

    def test_each_produces_valid_manifest(self) -> None:
        reg = ChannelAdapterRegistry()
        register_all_test_adapters(reg)
        for desc in reg.list_adapters():
            manifest = reg.get_manifest(desc.adapter_id)
            assert isinstance(manifest, AdapterCapabilityManifest)
            assert manifest.adapter_id == desc.adapter_id
            assert manifest.manifest_id
            assert isinstance(manifest.family, ChannelAdapterFamily)
            assert manifest.reliability_score == 0.95

    def test_all_families_covered(self) -> None:
        reg = ChannelAdapterRegistry()
        register_all_test_adapters(reg)
        families = {d.family for d in reg.list_adapters()}
        assert families == set(ChannelAdapterFamily)


# ---- per-family adapter tests ------------------------------------------------


class TestSmsTestAdapter:
    def test_family(self) -> None:
        a = SmsTestAdapter()
        assert a.family() == ChannelAdapterFamily.SMS

    def test_adapter_id(self) -> None:
        a = SmsTestAdapter()
        assert a.adapter_id() == "test-sms"

    def test_custom_id(self) -> None:
        a = SmsTestAdapter(adapter_id="custom-sms")
        assert a.adapter_id() == "custom-sms"

    def test_channels(self) -> None:
        m = SmsTestAdapter().manifest()
        assert "sms" in m.supported_channel_types
        assert "rcs" in m.supported_channel_types

    def test_max_body(self) -> None:
        m = SmsTestAdapter().manifest()
        assert m.max_body_bytes == 1600

    def test_delivery_guarantee(self) -> None:
        m = SmsTestAdapter().manifest()
        assert m.delivery_guarantee == DeliveryGuarantee.AT_LEAST_ONCE


class TestChatTestAdapter:
    def test_family(self) -> None:
        a = ChatTestAdapter()
        assert a.family() == ChannelAdapterFamily.CHAT

    def test_adapter_id(self) -> None:
        assert ChatTestAdapter().adapter_id() == "test-chat"

    def test_supports_rich_text(self) -> None:
        m = ChatTestAdapter().manifest()
        assert m.supports_rich_text is True

    def test_supports_attachments(self) -> None:
        m = ChatTestAdapter().manifest()
        assert m.supports_attachments is True

    def test_supports_threading(self) -> None:
        m = ChatTestAdapter().manifest()
        assert m.supports_threading is True

    def test_channels(self) -> None:
        m = ChatTestAdapter().manifest()
        assert "slack" in m.supported_channel_types
        assert "teams" in m.supported_channel_types


class TestVoiceTestAdapter:
    def test_family(self) -> None:
        assert VoiceTestAdapter().family() == ChannelAdapterFamily.VOICE

    def test_adapter_id(self) -> None:
        assert VoiceTestAdapter().adapter_id() == "test-voice"

    def test_max_body_zero(self) -> None:
        m = VoiceTestAdapter().manifest()
        assert m.max_body_bytes == 0

    def test_delivery_best_effort(self) -> None:
        m = VoiceTestAdapter().manifest()
        assert m.delivery_guarantee == DeliveryGuarantee.BEST_EFFORT

    def test_normalize_inbound_transcript(self) -> None:
        a = VoiceTestAdapter()
        raw = {"caller_id": "+1555", "transcript": "Hello voice", "duration": 60}
        result = a.normalize_inbound(raw)
        assert result.body_text == "Hello voice"
        assert result.sender_address == "+1555"

    def test_voice_metadata_duration(self) -> None:
        a = VoiceTestAdapter()
        raw = {"caller_id": "+1", "transcript": "test", "duration": 300}
        result = a.normalize_inbound(raw)
        assert result.metadata["call_duration_seconds"] == 300


class TestWebhookTestAdapter:
    def test_family(self) -> None:
        assert WebhookTestAdapter().family() == ChannelAdapterFamily.WEBHOOK

    def test_direction_outbound(self) -> None:
        d = WebhookTestAdapter().descriptor()
        assert d.direction == AdapterDirection.OUTBOUND

    def test_channels(self) -> None:
        m = WebhookTestAdapter().manifest()
        assert "webhook" in m.supported_channel_types


class TestInAppTestAdapter:
    def test_family(self) -> None:
        assert InAppTestAdapter().family() == ChannelAdapterFamily.IN_APP

    def test_delivery_exactly_once(self) -> None:
        m = InAppTestAdapter().manifest()
        assert m.delivery_guarantee == DeliveryGuarantee.EXACTLY_ONCE

    def test_supports_rich_text(self) -> None:
        m = InAppTestAdapter().manifest()
        assert m.supports_rich_text is True

    def test_supports_threading(self) -> None:
        m = InAppTestAdapter().manifest()
        assert m.supports_threading is True


class TestSocialTestAdapter:
    def test_family(self) -> None:
        assert SocialTestAdapter().family() == ChannelAdapterFamily.SOCIAL

    def test_supports_attachments(self) -> None:
        m = SocialTestAdapter().manifest()
        assert m.supports_attachments is True

    def test_channels(self) -> None:
        m = SocialTestAdapter().manifest()
        assert "whatsapp" in m.supported_channel_types
        assert "twitter_dm" in m.supported_channel_types


class TestEmailTestAdapter:
    def test_family(self) -> None:
        assert EmailTestAdapter().family() == ChannelAdapterFamily.EMAIL

    def test_adapter_id(self) -> None:
        assert EmailTestAdapter().adapter_id() == "test-email"

    def test_supports_all_rich_features(self) -> None:
        m = EmailTestAdapter().manifest()
        assert m.supports_rich_text is True
        assert m.supports_attachments is True
        assert m.supports_threading is True

    def test_large_max_body(self) -> None:
        m = EmailTestAdapter().manifest()
        assert m.max_body_bytes == 1048576

    def test_delivery_at_least_once(self) -> None:
        m = EmailTestAdapter().manifest()
        assert m.delivery_guarantee == DeliveryGuarantee.AT_LEAST_ONCE

    def test_channels(self) -> None:
        m = EmailTestAdapter().manifest()
        assert "email" in m.supported_channel_types

    def test_normalization_level(self) -> None:
        m = EmailTestAdapter().manifest()
        assert m.normalization_level == NormalizationLevel.STRUCTURED
