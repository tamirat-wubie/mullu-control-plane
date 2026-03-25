"""Tests for channel adapter contracts — enums, descriptors, capability manifests,
normalized messages, health reports, rate limits, policy constraints, and failure modes."""

from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.channel_adapter import (
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

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnums:
    def test_channel_adapter_family_count(self):
        assert len(ChannelAdapterFamily) == 7
        assert ChannelAdapterFamily.SMS.value == "sms"
        assert ChannelAdapterFamily.EMAIL.value == "email"

    def test_adapter_status_count(self):
        assert len(AdapterStatus) == 4
        assert AdapterStatus.AVAILABLE.value == "available"
        assert AdapterStatus.DISABLED.value == "disabled"

    def test_adapter_direction_count(self):
        assert len(AdapterDirection) == 3
        assert AdapterDirection.INBOUND.value == "inbound"
        assert AdapterDirection.BIDIRECTIONAL.value == "bidirectional"

    def test_normalization_level_count(self):
        assert len(NormalizationLevel) == 4
        assert NormalizationLevel.RAW.value == "raw"
        assert NormalizationLevel.SEMANTIC.value == "semantic"

    def test_delivery_guarantee_count(self):
        assert len(DeliveryGuarantee) == 3
        assert DeliveryGuarantee.BEST_EFFORT.value == "best_effort"
        assert DeliveryGuarantee.EXACTLY_ONCE.value == "exactly_once"


# ---------------------------------------------------------------------------
# AdapterRateLimit
# ---------------------------------------------------------------------------


class TestAdapterRateLimit:
    def _valid(self, **overrides):
        defaults = dict(
            max_messages_per_second=10,
            max_messages_per_minute=500,
            max_burst_size=20,
            cooldown_seconds=5,
        )
        defaults.update(overrides)
        return AdapterRateLimit(**defaults)

    def test_valid_creation(self):
        r = self._valid()
        assert r.max_messages_per_second == 10
        assert r.max_messages_per_minute == 500
        assert r.max_burst_size == 20
        assert r.cooldown_seconds == 5

    def test_defaults_are_zero(self):
        r = AdapterRateLimit()
        assert r.max_messages_per_second == 0
        assert r.max_messages_per_minute == 0

    def test_negative_max_messages_per_second_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_messages_per_second=-1)

    def test_negative_max_messages_per_minute_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_messages_per_minute=-1)

    def test_negative_max_burst_size_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_burst_size=-1)

    def test_negative_cooldown_seconds_rejected(self):
        with pytest.raises(ValueError):
            self._valid(cooldown_seconds=-1)

    def test_non_int_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_messages_per_second=1.5)

    def test_bool_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_burst_size=True)

    def test_frozen_immutability(self):
        r = self._valid()
        with pytest.raises(AttributeError):
            r.max_messages_per_second = 99

    def test_serialization(self):
        r = self._valid()
        d = r.to_dict()
        assert d["max_messages_per_second"] == 10
        assert d["cooldown_seconds"] == 5
        assert isinstance(d, dict)


# ---------------------------------------------------------------------------
# AdapterPolicyConstraint
# ---------------------------------------------------------------------------


class TestAdapterPolicyConstraint:
    def _valid(self, **overrides):
        defaults = dict(
            constraint_id="pc-001",
            description="max payload size",
            constraint_type="size_limit",
            value="1048576",
            enforced=True,
        )
        defaults.update(overrides)
        return AdapterPolicyConstraint(**defaults)

    def test_valid_creation(self):
        p = self._valid()
        assert p.constraint_id == "pc-001"
        assert p.constraint_type == "size_limit"
        assert p.enforced is True

    def test_empty_constraint_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(constraint_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._valid(description="")

    def test_empty_constraint_type_rejected(self):
        with pytest.raises(ValueError):
            self._valid(constraint_type="")

    def test_whitespace_only_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(constraint_id="   ")

    def test_non_string_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(constraint_id=123)

    def test_frozen_immutability(self):
        p = self._valid()
        with pytest.raises(AttributeError):
            p.constraint_id = "changed"

    def test_serialization(self):
        d = self._valid().to_dict()
        assert d["constraint_id"] == "pc-001"
        assert d["enforced"] is True


# ---------------------------------------------------------------------------
# AdapterFailureMode
# ---------------------------------------------------------------------------


class TestAdapterFailureMode:
    def _valid(self, **overrides):
        defaults = dict(
            mode_id="fm-001",
            description="timeout on upstream",
            severity="medium",
            is_recoverable=True,
            recommended_action="retry",
        )
        defaults.update(overrides)
        return AdapterFailureMode(**defaults)

    def test_valid_creation(self):
        f = self._valid()
        assert f.mode_id == "fm-001"
        assert f.severity == "medium"
        assert f.is_recoverable is True

    def test_all_valid_severities(self):
        for sev in ("low", "medium", "high", "critical"):
            f = self._valid(severity=sev)
            assert f.severity == sev

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            self._valid(severity="extreme")

    def test_empty_severity_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            self._valid(severity="")

    def test_empty_mode_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(mode_id="")

    def test_empty_description_rejected(self):
        with pytest.raises(ValueError):
            self._valid(description="")

    def test_non_string_mode_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(mode_id=42)

    def test_frozen_immutability(self):
        f = self._valid()
        with pytest.raises(AttributeError):
            f.severity = "high"

    def test_serialization(self):
        d = self._valid().to_dict()
        assert d["mode_id"] == "fm-001"
        assert d["severity"] == "medium"


# ---------------------------------------------------------------------------
# AdapterCapabilityManifest
# ---------------------------------------------------------------------------


class TestAdapterCapabilityManifest:
    def _valid(self, **overrides):
        defaults = dict(
            manifest_id="man-001",
            adapter_id="adp-001",
            family=ChannelAdapterFamily.SMS,
            direction=AdapterDirection.OUTBOUND,
            supported_channel_types=("sms_domestic", "sms_intl"),
            max_body_bytes=4096,
            max_attachments=0,
            supports_rich_text=False,
            supports_attachments=False,
            supports_threading=False,
            supports_read_receipts=False,
            supports_typing_indicator=False,
            delivery_guarantee=DeliveryGuarantee.AT_LEAST_ONCE,
            rate_limit=AdapterRateLimit(max_messages_per_second=10),
            reliability_score=0.95,
            normalization_level=NormalizationLevel.BASIC,
            created_at=NOW,
            metadata={"vendor": "acme"},
        )
        defaults.update(overrides)
        return AdapterCapabilityManifest(**defaults)

    def test_valid_creation(self):
        m = self._valid()
        assert m.manifest_id == "man-001"
        assert m.family == ChannelAdapterFamily.SMS
        assert m.direction == AdapterDirection.OUTBOUND
        assert m.reliability_score == 0.95

    def test_empty_manifest_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(manifest_id="")

    def test_empty_adapter_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(adapter_id="")

    def test_invalid_family_rejected(self):
        with pytest.raises(ValueError):
            self._valid(family="not_a_family")

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValueError):
            self._valid(direction="up")

    def test_invalid_delivery_guarantee_rejected(self):
        with pytest.raises(ValueError):
            self._valid(delivery_guarantee="guaranteed")

    def test_invalid_normalization_level_rejected(self):
        with pytest.raises(ValueError):
            self._valid(normalization_level="ultra")

    def test_reliability_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=-0.1)

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=1.01)

    def test_reliability_score_nan_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=float("nan"))

    def test_reliability_score_inf_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=float("inf"))

    def test_reliability_score_bool_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=True)

    def test_reliability_score_boundary_zero(self):
        m = self._valid(reliability_score=0.0)
        assert m.reliability_score == 0.0

    def test_reliability_score_boundary_one(self):
        m = self._valid(reliability_score=1.0)
        assert m.reliability_score == 1.0

    def test_negative_max_body_bytes_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_body_bytes=-1)

    def test_negative_max_attachments_rejected(self):
        with pytest.raises(ValueError):
            self._valid(max_attachments=-1)

    def test_supported_channel_types_frozen(self):
        m = self._valid(supported_channel_types=["sms_domestic"])
        assert isinstance(m.supported_channel_types, tuple)

    def test_policy_constraints_frozen(self):
        pc = AdapterPolicyConstraint(
            constraint_id="pc-1",
            description="limit",
            constraint_type="size",
        )
        m = self._valid(policy_constraints=[pc])
        assert isinstance(m.policy_constraints, tuple)
        assert len(m.policy_constraints) == 1

    def test_failure_modes_frozen(self):
        fm = AdapterFailureMode(
            mode_id="fm-1",
            description="timeout",
            severity="low",
        )
        m = self._valid(failure_modes=[fm])
        assert isinstance(m.failure_modes, tuple)

    def test_metadata_frozen(self):
        m = self._valid(metadata={"nested": {"a": 1}})
        assert isinstance(m.metadata, MappingProxyType)
        assert isinstance(m.metadata["nested"], MappingProxyType)

    def test_metadata_immutable(self):
        m = self._valid(metadata={"key": "val"})
        with pytest.raises(TypeError):
            m.metadata["key"] = "new"

    def test_frozen_immutability(self):
        m = self._valid()
        with pytest.raises(AttributeError):
            m.manifest_id = "changed"

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            self._valid(created_at="not-a-date")

    def test_serialization(self):
        m = self._valid()
        d = m.to_dict()
        assert d["manifest_id"] == "man-001"
        assert d["family"] == ChannelAdapterFamily.SMS
        assert d["reliability_score"] == 0.95
        assert isinstance(d["supported_channel_types"], list)
        assert isinstance(d["metadata"], dict)


# ---------------------------------------------------------------------------
# ChannelAdapterDescriptor
# ---------------------------------------------------------------------------


class TestChannelAdapterDescriptor:
    def _valid(self, **overrides):
        defaults = dict(
            adapter_id="adp-001",
            name="Acme SMS Gateway",
            family=ChannelAdapterFamily.SMS,
            direction=AdapterDirection.OUTBOUND,
            status=AdapterStatus.AVAILABLE,
            provider_name="acme",
            version="2.1.0",
            manifest_id="man-001",
            tags=("production", "sms"),
            created_at=NOW,
            metadata={"region": "us-east"},
        )
        defaults.update(overrides)
        return ChannelAdapterDescriptor(**defaults)

    def test_valid_creation(self):
        d = self._valid()
        assert d.adapter_id == "adp-001"
        assert d.name == "Acme SMS Gateway"
        assert d.status == AdapterStatus.AVAILABLE

    def test_empty_adapter_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(adapter_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            self._valid(name="")

    def test_empty_version_rejected(self):
        with pytest.raises(ValueError):
            self._valid(version="")

    def test_non_string_adapter_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(adapter_id=999)

    def test_invalid_family_rejected(self):
        with pytest.raises(ValueError):
            self._valid(family="pigeon")

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValueError):
            self._valid(direction="sideways")

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._valid(status="broken")

    def test_tags_frozen_to_tuple(self):
        d = self._valid(tags=["alpha", "beta"])
        assert isinstance(d.tags, tuple)
        assert d.tags == ("alpha", "beta")

    def test_tags_immutable(self):
        d = self._valid()
        with pytest.raises(TypeError):
            d.tags[0] = "changed"

    def test_metadata_frozen(self):
        d = self._valid(metadata={"k": {"nested": True}})
        assert isinstance(d.metadata, MappingProxyType)
        assert isinstance(d.metadata["k"], MappingProxyType)

    def test_metadata_immutable(self):
        d = self._valid()
        with pytest.raises(TypeError):
            d.metadata["region"] = "eu-west"

    def test_frozen_immutability(self):
        d = self._valid()
        with pytest.raises(AttributeError):
            d.adapter_id = "changed"

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            self._valid(created_at="yesterday")

    def test_serialization(self):
        d = self._valid().to_dict()
        assert d["adapter_id"] == "adp-001"
        assert isinstance(d["tags"], list)
        assert isinstance(d["metadata"], dict)


# ---------------------------------------------------------------------------
# NormalizedInbound
# ---------------------------------------------------------------------------


class TestNormalizedInbound:
    def _valid(self, **overrides):
        defaults = dict(
            message_id="msg-in-001",
            adapter_id="adp-001",
            family=ChannelAdapterFamily.CHAT,
            sender_address="user@example.com",
            body_text="Hello",
            body_html="<p>Hello</p>",
            subject="Greeting",
            thread_id="thr-001",
            attachment_refs=("att-1",),
            normalization_level=NormalizationLevel.STRUCTURED,
            raw_payload={"original": "data"},
            received_at=NOW,
            metadata={"source": "web"},
        )
        defaults.update(overrides)
        return NormalizedInbound(**defaults)

    def test_valid_creation(self):
        m = self._valid()
        assert m.message_id == "msg-in-001"
        assert m.family == ChannelAdapterFamily.CHAT
        assert m.sender_address == "user@example.com"

    def test_empty_message_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(message_id="")

    def test_empty_adapter_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(adapter_id="")

    def test_non_string_message_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(message_id=42)

    def test_invalid_family_rejected(self):
        with pytest.raises(ValueError):
            self._valid(family="carrier_pigeon")

    def test_attachment_refs_frozen(self):
        m = self._valid(attachment_refs=["a", "b"])
        assert isinstance(m.attachment_refs, tuple)
        assert m.attachment_refs == ("a", "b")

    def test_raw_payload_frozen(self):
        m = self._valid(raw_payload={"nested": {"deep": 1}})
        assert isinstance(m.raw_payload, MappingProxyType)
        assert isinstance(m.raw_payload["nested"], MappingProxyType)

    def test_raw_payload_immutable(self):
        m = self._valid()
        with pytest.raises(TypeError):
            m.raw_payload["original"] = "tampered"

    def test_metadata_frozen(self):
        m = self._valid(metadata={"k": [1, 2]})
        assert isinstance(m.metadata, MappingProxyType)
        assert isinstance(m.metadata["k"], tuple)

    def test_metadata_immutable(self):
        m = self._valid()
        with pytest.raises(TypeError):
            m.metadata["source"] = "changed"

    def test_frozen_immutability(self):
        m = self._valid()
        with pytest.raises(AttributeError):
            m.message_id = "changed"

    def test_invalid_received_at_rejected(self):
        with pytest.raises(ValueError):
            self._valid(received_at="not-a-date")

    def test_serialization(self):
        d = self._valid().to_dict()
        assert d["message_id"] == "msg-in-001"
        assert isinstance(d["attachment_refs"], list)
        assert isinstance(d["raw_payload"], dict)
        assert isinstance(d["metadata"], dict)


# ---------------------------------------------------------------------------
# NormalizedOutbound
# ---------------------------------------------------------------------------


class TestNormalizedOutbound:
    def _valid(self, **overrides):
        defaults = dict(
            message_id="msg-out-001",
            adapter_id="adp-001",
            family=ChannelAdapterFamily.EMAIL,
            recipient_address="dest@example.com",
            body_text="Hi there",
            body_html="<p>Hi there</p>",
            subject="Hello",
            thread_id="thr-001",
            attachment_refs=("att-x",),
            priority="normal",
            prepared_at=NOW,
            metadata={"campaign": "launch"},
        )
        defaults.update(overrides)
        return NormalizedOutbound(**defaults)

    def test_valid_creation(self):
        m = self._valid()
        assert m.message_id == "msg-out-001"
        assert m.recipient_address == "dest@example.com"
        assert m.priority == "normal"

    def test_empty_message_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(message_id="")

    def test_empty_adapter_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(adapter_id="")

    def test_empty_recipient_address_rejected(self):
        with pytest.raises(ValueError):
            self._valid(recipient_address="")

    def test_non_string_message_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(message_id=100)

    def test_invalid_family_rejected(self):
        with pytest.raises(ValueError):
            self._valid(family="fax")

    def test_all_valid_priorities(self):
        for pri in ("low", "normal", "high", "urgent"):
            m = self._valid(priority=pri)
            assert m.priority == pri

    def test_invalid_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            self._valid(priority="critical")

    def test_empty_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            self._valid(priority="")

    def test_attachment_refs_frozen(self):
        m = self._valid(attachment_refs=["x", "y"])
        assert isinstance(m.attachment_refs, tuple)

    def test_metadata_frozen(self):
        m = self._valid(metadata={"k": {"v": 1}})
        assert isinstance(m.metadata, MappingProxyType)

    def test_metadata_immutable(self):
        m = self._valid()
        with pytest.raises(TypeError):
            m.metadata["campaign"] = "changed"

    def test_frozen_immutability(self):
        m = self._valid()
        with pytest.raises(AttributeError):
            m.priority = "high"

    def test_invalid_prepared_at_rejected(self):
        with pytest.raises(ValueError):
            self._valid(prepared_at="last-tuesday")

    def test_serialization(self):
        d = self._valid().to_dict()
        assert d["message_id"] == "msg-out-001"
        assert d["priority"] == "normal"
        assert isinstance(d["attachment_refs"], list)
        assert isinstance(d["metadata"], dict)


# ---------------------------------------------------------------------------
# AdapterHealthReport
# ---------------------------------------------------------------------------


class TestAdapterHealthReport:
    def _valid(self, **overrides):
        defaults = dict(
            report_id="rpt-001",
            adapter_id="adp-001",
            status=AdapterStatus.AVAILABLE,
            reliability_score=0.99,
            messages_sent=1000,
            messages_received=950,
            messages_failed=5,
            avg_latency_ms=42.5,
            active_failure_modes=("fm-timeout",),
            reported_at=NOW,
        )
        defaults.update(overrides)
        return AdapterHealthReport(**defaults)

    def test_valid_creation(self):
        h = self._valid()
        assert h.report_id == "rpt-001"
        assert h.status == AdapterStatus.AVAILABLE
        assert h.reliability_score == 0.99
        assert h.messages_sent == 1000

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(report_id="")

    def test_empty_adapter_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(adapter_id="")

    def test_non_string_report_id_rejected(self):
        with pytest.raises(ValueError):
            self._valid(report_id=42)

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            self._valid(status="offline")

    def test_reliability_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=-0.01)

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=1.1)

    def test_reliability_score_nan_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=float("nan"))

    def test_reliability_score_bool_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reliability_score=False)

    def test_negative_messages_sent_rejected(self):
        with pytest.raises(ValueError):
            self._valid(messages_sent=-1)

    def test_negative_messages_received_rejected(self):
        with pytest.raises(ValueError):
            self._valid(messages_received=-1)

    def test_negative_messages_failed_rejected(self):
        with pytest.raises(ValueError):
            self._valid(messages_failed=-1)

    def test_non_int_messages_sent_rejected(self):
        with pytest.raises(ValueError):
            self._valid(messages_sent=10.5)

    def test_bool_messages_sent_rejected(self):
        with pytest.raises(ValueError):
            self._valid(messages_sent=True)

    def test_active_failure_modes_frozen(self):
        h = self._valid(active_failure_modes=["a", "b"])
        assert isinstance(h.active_failure_modes, tuple)
        assert h.active_failure_modes == ("a", "b")

    def test_frozen_immutability(self):
        h = self._valid()
        with pytest.raises(AttributeError):
            h.report_id = "changed"

    def test_invalid_reported_at_rejected(self):
        with pytest.raises(ValueError):
            self._valid(reported_at="not-valid")

    def test_serialization(self):
        d = self._valid().to_dict()
        assert d["report_id"] == "rpt-001"
        assert d["reliability_score"] == 0.99
        assert d["messages_sent"] == 1000
        assert isinstance(d["active_failure_modes"], list)
        assert isinstance(d, dict)
