"""Purpose: live channel bindings — provider-backed adapter slots.
Governance scope: connecting Phase 41 channel adapters to Phase 42 external
    connectors, enabling governed outbound/inbound via real provider APIs.
Dependencies: channel_adapters, external_connectors, external_connector contracts,
    channel_adapter contracts, event_spine, core invariants.
Invariants:
  - Every live channel operation goes through external connector governance.
  - Credential and rate limit checks happen before execution.
  - Failures are recorded and fallback is attempted when configured.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.channel_adapter import (
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
from ..contracts.external_connector import (
    ConnectorCapabilityBinding,
    ConnectorExecutionRecord,
    ConnectorFailureCategory,
    ExternalConnectorType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .channel_adapters import ChannelAdapter, ChannelAdapterRegistry
from .external_connectors import ExternalConnectorRegistry
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-live-ch", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# ---------------------------------------------------------------------------
# Provider-backed channel adapters — one slot per family
# ---------------------------------------------------------------------------


class _LiveChannelAdapter(ChannelAdapter):
    """A channel adapter backed by an external connector.

    Delegates actual send/receive to the connector while preserving
    the canonical adapter interface.
    """

    _FAMILY: ChannelAdapterFamily
    _NAME: str
    _CHANNELS: tuple[str, ...]
    _CONNECTOR_TYPE: ExternalConnectorType
    _DIRECTION: AdapterDirection = AdapterDirection.BIDIRECTIONAL
    _MAX_BODY: int = 4096
    _DELIVERY: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE

    def __init__(
        self,
        connector_registry: ExternalConnectorRegistry,
        connector_id: str,
        adapter_id: str | None = None,
    ) -> None:
        self._connector_registry = connector_registry
        self._connector_id = connector_id
        self._id = adapter_id or f"live-{self._FAMILY.value}"
        self._now = _now_iso()
        self._sent = 0
        self._received = 0

    def adapter_id(self) -> str:
        return self._id

    def family(self) -> ChannelAdapterFamily:
        return self._FAMILY

    def descriptor(self) -> ChannelAdapterDescriptor:
        return ChannelAdapterDescriptor(
            adapter_id=self._id,
            name=self._NAME,
            family=self._FAMILY,
            direction=self._DIRECTION,
            status=AdapterStatus.AVAILABLE,
            provider_name=self._connector_id,
            version="1.0.0",
            tags=("live", "provider-backed"),
            created_at=self._now,
        )

    def manifest(self) -> AdapterCapabilityManifest:
        from ..contracts.channel_adapter import AdapterRateLimit
        return AdapterCapabilityManifest(
            manifest_id=stable_identifier("manifest-live", {"aid": self._id}),
            adapter_id=self._id,
            family=self._FAMILY,
            direction=self._DIRECTION,
            supported_channel_types=self._CHANNELS,
            max_body_bytes=self._MAX_BODY,
            delivery_guarantee=self._DELIVERY,
            rate_limit=AdapterRateLimit(
                max_messages_per_second=10,
                max_messages_per_minute=100,
                max_burst_size=20,
            ),
            reliability_score=0.9,
            normalization_level=NormalizationLevel.STRUCTURED,
            created_at=self._now,
        )

    def normalize_inbound(self, raw: Mapping[str, Any]) -> NormalizedInbound:
        """Receive via external connector, then normalize."""
        now = _now_iso()
        self._received += 1

        # Execute receive via connector
        self._connector_registry.execute(
            self._connector_id, "receive",
            {"family": self._FAMILY.value, "raw": dict(raw)},
        )

        return NormalizedInbound(
            message_id=stable_identifier("msg-live-in", {
                "aid": self._id, "ts": now, "n": self._received,
            }),
            adapter_id=self._id,
            family=self._FAMILY,
            sender_address=str(raw.get("from", "unknown")),
            body_text=str(raw.get("body", "")),
            body_html=str(raw.get("body_html", "")),
            subject=str(raw.get("subject", "")),
            thread_id=str(raw.get("thread_id", "")),
            normalization_level=NormalizationLevel.STRUCTURED,
            raw_payload=raw,
            received_at=now,
        )

    def format_outbound(
        self, recipient: str, body: str, **kwargs: Any,
    ) -> NormalizedOutbound:
        """Format and send via external connector."""
        now = _now_iso()
        self._sent += 1

        # Execute send via connector
        self._connector_registry.execute(
            self._connector_id, "send",
            {
                "family": self._FAMILY.value,
                "recipient": recipient,
                "body": body,
                **{k: str(v) for k, v in kwargs.items()},
            },
        )

        return NormalizedOutbound(
            message_id=stable_identifier("msg-live-out", {
                "aid": self._id, "ts": now, "n": self._sent,
            }),
            adapter_id=self._id,
            family=self._FAMILY,
            recipient_address=recipient,
            body_text=body,
            subject=str(kwargs.get("subject", "")),
            thread_id=str(kwargs.get("thread_id", "")),
            priority=str(kwargs.get("priority", "normal")),
            prepared_at=now,
        )

    def health_check(self) -> AdapterHealthReport:
        # Delegate to connector health
        snap = self._connector_registry.health_check(self._connector_id)
        return AdapterHealthReport(
            report_id=stable_identifier("health-live", {
                "aid": self._id, "ts": _now_iso(),
            }),
            adapter_id=self._id,
            status=(
                AdapterStatus.AVAILABLE
                if snap.health_state.value in ("healthy",)
                else AdapterStatus.DEGRADED
            ),
            reliability_score=snap.reliability_score,
            messages_sent=self._sent,
            messages_received=self._received,
            avg_latency_ms=snap.avg_latency_ms,
            reported_at=_now_iso(),
        )


class LiveSmsAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.SMS
    _NAME = "Live SMS/RCS Adapter"
    _CHANNELS = ("sms", "rcs")
    _CONNECTOR_TYPE = ExternalConnectorType.SMS_PROVIDER
    _MAX_BODY = 1600
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class LiveChatAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.CHAT
    _NAME = "Live Chat/Messaging Adapter"
    _CHANNELS = ("slack", "teams", "discord", "generic_chat")
    _CONNECTOR_TYPE = ExternalConnectorType.CHAT_PROVIDER
    _MAX_BODY = 40000
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class LiveVoiceAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.VOICE
    _NAME = "Live Voice/Transcript Adapter"
    _CHANNELS = ("phone", "voip", "conference")
    _CONNECTOR_TYPE = ExternalConnectorType.VOICE_PROVIDER
    _MAX_BODY = 0
    _DELIVERY = DeliveryGuarantee.BEST_EFFORT

    def normalize_inbound(self, raw: Mapping[str, Any]) -> NormalizedInbound:
        now = _now_iso()
        self._received += 1
        self._connector_registry.execute(
            self._connector_id, "receive_transcript",
            {"family": self._FAMILY.value, "raw": dict(raw)},
        )
        transcript = str(raw.get("transcript", ""))
        return NormalizedInbound(
            message_id=stable_identifier("msg-live-voice-in", {
                "aid": self._id, "ts": now, "n": self._received,
            }),
            adapter_id=self._id,
            family=self._FAMILY,
            sender_address=str(raw.get("caller_id", "unknown")),
            body_text=transcript,
            subject=str(raw.get("call_subject", "")),
            normalization_level=NormalizationLevel.STRUCTURED,
            raw_payload=raw,
            received_at=now,
            metadata={"call_duration_seconds": raw.get("duration", 0)},
        )


class LiveWebhookAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.WEBHOOK
    _NAME = "Live Webhook/Push Adapter"
    _CHANNELS = ("webhook", "push_notification")
    _CONNECTOR_TYPE = ExternalConnectorType.WEBHOOK_PROVIDER
    _DIRECTION = AdapterDirection.OUTBOUND
    _MAX_BODY = 65536
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class LiveEmailAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.EMAIL
    _NAME = "Live Email Adapter"
    _CHANNELS = ("email",)
    _CONNECTOR_TYPE = ExternalConnectorType.EMAIL_PROVIDER
    _MAX_BODY = 1048576
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class LiveSocialAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.SOCIAL
    _NAME = "Live Social/DM Adapter"
    _CHANNELS = ("twitter_dm", "instagram_dm", "facebook_messenger", "whatsapp")
    _CONNECTOR_TYPE = ExternalConnectorType.SOCIAL_PROVIDER
    _MAX_BODY = 2000
    _DELIVERY = DeliveryGuarantee.BEST_EFFORT


class LiveInAppAdapter(_LiveChannelAdapter):
    _FAMILY = ChannelAdapterFamily.IN_APP
    _NAME = "Live In-App Chat Adapter"
    _CHANNELS = ("in_app_chat", "in_app_notification")
    _CONNECTOR_TYPE = ExternalConnectorType.GENERIC_API
    _MAX_BODY = 10000
    _DELIVERY = DeliveryGuarantee.EXACTLY_ONCE


# ---------------------------------------------------------------------------
# Binding engine — wires live adapters into registries
# ---------------------------------------------------------------------------


class LiveChannelBindingEngine:
    """Creates and manages live channel adapter bindings backed by connectors."""

    def __init__(
        self,
        channel_registry: ChannelAdapterRegistry,
        connector_registry: ExternalConnectorRegistry,
        event_spine: EventSpineEngine,
    ) -> None:
        if not isinstance(channel_registry, ChannelAdapterRegistry):
            raise RuntimeCoreInvariantError(
                "channel_registry must be a ChannelAdapterRegistry"
            )
        if not isinstance(connector_registry, ExternalConnectorRegistry):
            raise RuntimeCoreInvariantError(
                "connector_registry must be an ExternalConnectorRegistry"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        self._channels = channel_registry
        self._connectors = connector_registry
        self._events = event_spine
        self._live_adapters: dict[str, _LiveChannelAdapter] = {}

    def bind_sms(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveSmsAdapter, connector_id, adapter_id)

    def bind_chat(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveChatAdapter, connector_id, adapter_id)

    def bind_voice(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveVoiceAdapter, connector_id, adapter_id)

    def bind_webhook(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveWebhookAdapter, connector_id, adapter_id)

    def bind_email(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveEmailAdapter, connector_id, adapter_id)

    def bind_social(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveSocialAdapter, connector_id, adapter_id)

    def bind_in_app(self, connector_id: str, adapter_id: str | None = None) -> ChannelAdapterDescriptor:
        return self._bind(LiveInAppAdapter, connector_id, adapter_id)

    def _bind(
        self,
        adapter_cls: type[_LiveChannelAdapter],
        connector_id: str,
        adapter_id: str | None,
    ) -> ChannelAdapterDescriptor:
        # Verify connector exists
        self._connectors.get_connector(connector_id)

        adapter = adapter_cls(self._connectors, connector_id, adapter_id)
        desc = self._channels.register(adapter)
        self._live_adapters[adapter.adapter_id()] = adapter

        # Create capability binding
        now = _now_iso()
        binding = ConnectorCapabilityBinding(
            binding_id=stable_identifier("bind-ch", {
                "aid": adapter.adapter_id(), "cid": connector_id, "ts": now,
            }),
            connector_id=connector_id,
            connector_type=adapter._CONNECTOR_TYPE,
            bound_adapter_id=adapter.adapter_id(),
            supported_operations=("send", "receive"),
            max_payload_bytes=adapter._MAX_BODY,
            reliability_score=0.9,
            enabled=True,
            tags=("live", "channel", adapter._FAMILY.value),
            created_at=now,
        )
        self._connectors.add_binding(binding)

        _emit(self._events, "live_channel_bound", {
            "adapter_id": adapter.adapter_id(),
            "connector_id": connector_id,
            "family": adapter._FAMILY.value,
        }, adapter.adapter_id())

        return desc

    def get_live_adapter(self, adapter_id: str) -> _LiveChannelAdapter:
        if adapter_id not in self._live_adapters:
            raise RuntimeCoreInvariantError("live adapter not found")
        return self._live_adapters[adapter_id]

    def list_live_adapters(self) -> tuple[str, ...]:
        return tuple(sorted(self._live_adapters.keys()))

    @property
    def binding_count(self) -> int:
        return len(self._live_adapters)
