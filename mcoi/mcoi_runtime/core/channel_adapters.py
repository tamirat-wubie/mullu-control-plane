"""Purpose: channel adapter registry and test adapters.
Governance scope: registering, routing, and managing channel adapters
    with deterministic test implementations per adapter family.
Dependencies: channel_adapter contracts, core invariants.
Invariants:
  - No duplicate adapter IDs.
  - Only AVAILABLE/DEGRADED adapters participate in routing.
  - Every adapter exposes a capability manifest.
  - Deterministic test adapters produce predictable output.
  - Immutable returns only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.channel_adapter import (
    AdapterCapabilityManifest,
    AdapterDirection,
    AdapterFailureMode,
    AdapterHealthReport,
    AdapterPolicyConstraint,
    AdapterRateLimit,
    AdapterStatus,
    ChannelAdapterDescriptor,
    ChannelAdapterFamily,
    DeliveryGuarantee,
    NormalizationLevel,
    NormalizedInbound,
    NormalizedOutbound,
)
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Abstract adapter base
# ---------------------------------------------------------------------------


class ChannelAdapter(ABC):
    """Abstract base for all channel adapters."""

    @abstractmethod
    def adapter_id(self) -> str: ...

    @abstractmethod
    def family(self) -> ChannelAdapterFamily: ...

    @abstractmethod
    def descriptor(self) -> ChannelAdapterDescriptor: ...

    @abstractmethod
    def manifest(self) -> AdapterCapabilityManifest: ...

    @abstractmethod
    def normalize_inbound(self, raw: Mapping[str, Any]) -> NormalizedInbound: ...

    @abstractmethod
    def format_outbound(
        self, recipient: str, body: str, **kwargs: Any,
    ) -> NormalizedOutbound: ...

    @abstractmethod
    def health_check(self) -> AdapterHealthReport: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ChannelAdapterRegistry:
    """Central registry for channel adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelAdapter] = {}
        self._descriptors: dict[str, ChannelAdapterDescriptor] = {}
        self._manifests: dict[str, AdapterCapabilityManifest] = {}

    def register(self, adapter: ChannelAdapter) -> ChannelAdapterDescriptor:
        """Register an adapter. Rejects duplicates."""
        if not isinstance(adapter, ChannelAdapter):
            raise RuntimeCoreInvariantError("adapter must be a ChannelAdapter")
        aid = adapter.adapter_id()
        if aid in self._adapters:
            raise RuntimeCoreInvariantError(
                f"adapter '{aid}' already registered"
            )
        desc = adapter.descriptor()
        manifest = adapter.manifest()
        self._adapters[aid] = adapter
        self._descriptors[aid] = desc
        self._manifests[aid] = manifest
        return desc

    def get_adapter(self, adapter_id: str) -> ChannelAdapter:
        if adapter_id not in self._adapters:
            raise RuntimeCoreInvariantError(f"adapter '{adapter_id}' not found")
        return self._adapters[adapter_id]

    def get_descriptor(self, adapter_id: str) -> ChannelAdapterDescriptor:
        if adapter_id not in self._descriptors:
            raise RuntimeCoreInvariantError(f"adapter '{adapter_id}' not found")
        return self._descriptors[adapter_id]

    def get_manifest(self, adapter_id: str) -> AdapterCapabilityManifest:
        if adapter_id not in self._manifests:
            raise RuntimeCoreInvariantError(f"adapter '{adapter_id}' not found")
        return self._manifests[adapter_id]

    def list_adapters(
        self, *, family: ChannelAdapterFamily | None = None,
        status: AdapterStatus | None = None,
    ) -> tuple[ChannelAdapterDescriptor, ...]:
        result = list(self._descriptors.values())
        if family is not None:
            result = [d for d in result if d.family == family]
        if status is not None:
            result = [d for d in result if d.status == status]
        return tuple(sorted(result, key=lambda d: d.adapter_id))

    def list_available(self) -> tuple[ChannelAdapterDescriptor, ...]:
        return tuple(
            d for d in sorted(self._descriptors.values(), key=lambda d: d.adapter_id)
            if d.status in (AdapterStatus.AVAILABLE, AdapterStatus.DEGRADED)
        )

    def route_by_family(
        self, family: ChannelAdapterFamily,
    ) -> tuple[ChannelAdapter, ...]:
        return tuple(
            self._adapters[d.adapter_id]
            for d in sorted(self._descriptors.values(), key=lambda d: d.adapter_id)
            if d.family == family
            and d.status in (AdapterStatus.AVAILABLE, AdapterStatus.DEGRADED)
        )

    def normalize_inbound(
        self, adapter_id: str, raw: Mapping[str, Any],
    ) -> NormalizedInbound:
        adapter = self.get_adapter(adapter_id)
        return adapter.normalize_inbound(raw)

    def format_outbound(
        self, adapter_id: str, recipient: str, body: str, **kwargs: Any,
    ) -> NormalizedOutbound:
        adapter = self.get_adapter(adapter_id)
        return adapter.format_outbound(recipient, body, **kwargs)

    def health_check(self, adapter_id: str) -> AdapterHealthReport:
        adapter = self.get_adapter(adapter_id)
        return adapter.health_check()

    def health_check_all(self) -> tuple[AdapterHealthReport, ...]:
        reports = []
        for aid in sorted(self._adapters):
            reports.append(self._adapters[aid].health_check())
        return tuple(reports)

    @property
    def adapter_count(self) -> int:
        return len(self._adapters)

    def state_hash(self) -> str:
        h = sha256()
        for aid in sorted(self._adapters):
            d = self._descriptors[aid]
            h.update(f"adapter:{aid}:{d.family.value}:{d.status.value}:{d.version}".encode())
        return h.hexdigest()


# ---------------------------------------------------------------------------
# Test adapters — one per family
# ---------------------------------------------------------------------------


class _BaseTestAdapter(ChannelAdapter):
    """Shared logic for deterministic test adapters."""

    _FAMILY: ChannelAdapterFamily
    _NAME: str
    _CHANNELS: tuple[str, ...]
    _DIRECTION: AdapterDirection = AdapterDirection.BIDIRECTIONAL
    _MAX_BODY: int = 4096
    _DELIVERY: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    _SUPPORTS_RICH: bool = False
    _SUPPORTS_ATTACH: bool = False
    _SUPPORTS_THREAD: bool = False

    def __init__(self, adapter_id: str | None = None) -> None:
        self._id = adapter_id or f"test-{self._FAMILY.value}"
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
            provider_name="test-provider",
            version="1.0.0",
            tags=("test",),
            created_at=self._now,
        )

    def manifest(self) -> AdapterCapabilityManifest:
        return AdapterCapabilityManifest(
            manifest_id=stable_identifier("manifest", {"aid": self._id}),
            adapter_id=self._id,
            family=self._FAMILY,
            direction=self._DIRECTION,
            supported_channel_types=self._CHANNELS,
            max_body_bytes=self._MAX_BODY,
            max_attachments=5 if self._SUPPORTS_ATTACH else 0,
            supports_rich_text=self._SUPPORTS_RICH,
            supports_attachments=self._SUPPORTS_ATTACH,
            supports_threading=self._SUPPORTS_THREAD,
            delivery_guarantee=self._DELIVERY,
            rate_limit=AdapterRateLimit(
                max_messages_per_second=10,
                max_messages_per_minute=100,
                max_burst_size=20,
            ),
            reliability_score=0.95,
            normalization_level=NormalizationLevel.STRUCTURED,
            created_at=self._now,
        )

    def normalize_inbound(self, raw: Mapping[str, Any]) -> NormalizedInbound:
        now = _now_iso()
        self._received += 1
        return NormalizedInbound(
            message_id=stable_identifier("msg-in", {
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
        now = _now_iso()
        self._sent += 1
        return NormalizedOutbound(
            message_id=stable_identifier("msg-out", {
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
        return AdapterHealthReport(
            report_id=stable_identifier("health", {"aid": self._id, "ts": _now_iso()}),
            adapter_id=self._id,
            status=AdapterStatus.AVAILABLE,
            reliability_score=0.95,
            messages_sent=self._sent,
            messages_received=self._received,
            avg_latency_ms=15.0,
            reported_at=_now_iso(),
        )


class SmsTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.SMS
    _NAME = "SMS/RCS Test Adapter"
    _CHANNELS = ("sms", "rcs")
    _MAX_BODY = 1600
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class ChatTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.CHAT
    _NAME = "Chat/Messaging Test Adapter"
    _CHANNELS = ("slack", "teams", "discord", "generic_chat")
    _MAX_BODY = 40000
    _SUPPORTS_RICH = True
    _SUPPORTS_ATTACH = True
    _SUPPORTS_THREAD = True
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class VoiceTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.VOICE
    _NAME = "Voice/Transcript Session Test Adapter"
    _CHANNELS = ("phone", "voip", "conference")
    _DIRECTION = AdapterDirection.BIDIRECTIONAL
    _MAX_BODY = 0  # voice — no text body
    _DELIVERY = DeliveryGuarantee.BEST_EFFORT

    def normalize_inbound(self, raw: Mapping[str, Any]) -> NormalizedInbound:
        now = _now_iso()
        self._received += 1
        transcript = str(raw.get("transcript", ""))
        return NormalizedInbound(
            message_id=stable_identifier("msg-voice-in", {
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


class WebhookTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.WEBHOOK
    _NAME = "Webhook/Push Test Adapter"
    _CHANNELS = ("webhook", "push_notification")
    _DIRECTION = AdapterDirection.OUTBOUND
    _MAX_BODY = 65536
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


class InAppTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.IN_APP
    _NAME = "In-App Chat Test Adapter"
    _CHANNELS = ("in_app_chat", "in_app_notification")
    _MAX_BODY = 10000
    _SUPPORTS_RICH = True
    _SUPPORTS_THREAD = True
    _DELIVERY = DeliveryGuarantee.EXACTLY_ONCE


class SocialTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.SOCIAL
    _NAME = "Social/DM Test Adapter"
    _CHANNELS = ("twitter_dm", "instagram_dm", "facebook_messenger", "whatsapp")
    _MAX_BODY = 2000
    _SUPPORTS_ATTACH = True
    _DELIVERY = DeliveryGuarantee.BEST_EFFORT


class EmailTestAdapter(_BaseTestAdapter):
    _FAMILY = ChannelAdapterFamily.EMAIL
    _NAME = "Email Test Adapter"
    _CHANNELS = ("email",)
    _MAX_BODY = 1048576
    _SUPPORTS_RICH = True
    _SUPPORTS_ATTACH = True
    _SUPPORTS_THREAD = True
    _DELIVERY = DeliveryGuarantee.AT_LEAST_ONCE


# ---------------------------------------------------------------------------
# Convenience: register all test adapters
# ---------------------------------------------------------------------------


def register_all_test_adapters(
    registry: ChannelAdapterRegistry,
) -> tuple[ChannelAdapterDescriptor, ...]:
    """Register one test adapter per family. Returns descriptors."""
    adapters = [
        SmsTestAdapter(),
        ChatTestAdapter(),
        VoiceTestAdapter(),
        WebhookTestAdapter(),
        InAppTestAdapter(),
        SocialTestAdapter(),
        EmailTestAdapter(),
    ]
    descs = []
    for adapter in adapters:
        descs.append(registry.register(adapter))
    return tuple(descs)
