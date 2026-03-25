"""Comprehensive contract tests for mcoi_runtime.contracts.external_connector."""

from __future__ import annotations

import math

import pytest

from mcoi_runtime.contracts.external_connector import (
    ChannelConsentRecord,
    ConsentState,
    ConnectorAuthMode,
    ConnectorCapabilityBinding,
    ConnectorExecutionRecord,
    ConnectorFailureCategory,
    ConnectorFailureRecord,
    ConnectorHealthSnapshot,
    ConnectorHealthState,
    ConnectorQuotaState,
    ConnectorRateLimitPolicy,
    ConnectorRetentionPolicy,
    ExternalConnectorDescriptor,
    ExternalConnectorType,
    FallbackChain,
    FallbackChainEntry,
    FallbackStrategy,
    RedactionLevel,
    SecretRotationState,
    SecretScope,
)

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestExternalConnectorType:
    def test_all_values(self):
        expected = {
            "sms_provider", "chat_provider", "voice_provider",
            "email_provider", "webhook_provider", "social_provider",
            "storage_provider", "parser_provider", "generic_api",
        }
        assert {m.value for m in ExternalConnectorType} == expected

    def test_count(self):
        assert len(ExternalConnectorType) == 9


class TestConnectorAuthMode:
    def test_all_values(self):
        expected = {
            "api_key", "oauth2", "basic_auth", "bearer_token",
            "mutual_tls", "hmac_signature", "none",
        }
        assert {m.value for m in ConnectorAuthMode} == expected

    def test_count(self):
        assert len(ConnectorAuthMode) == 7


class TestConnectorHealthState:
    def test_all_values(self):
        expected = {"healthy", "degraded", "unhealthy", "unknown", "circuit_open"}
        assert {m.value for m in ConnectorHealthState} == expected

    def test_count(self):
        assert len(ConnectorHealthState) == 5


class TestConnectorFailureCategory:
    def test_all_values(self):
        expected = {
            "auth_failure", "rate_limited", "quota_exhausted", "timeout",
            "network_error", "provider_error", "payload_rejected",
            "policy_blocked", "circuit_broken", "unknown",
        }
        assert {m.value for m in ConnectorFailureCategory} == expected

    def test_count(self):
        assert len(ConnectorFailureCategory) == 10


class TestSecretRotationState:
    def test_all_values(self):
        expected = {"current", "pending_rotation", "rotating", "expired", "revoked"}
        assert {m.value for m in SecretRotationState} == expected

    def test_count(self):
        assert len(SecretRotationState) == 5


class TestRedactionLevel:
    def test_all_values(self):
        expected = {"none", "headers_only", "body_partial", "body_full", "complete"}
        assert {m.value for m in RedactionLevel} == expected

    def test_count(self):
        assert len(RedactionLevel) == 5


class TestFallbackStrategy:
    def test_all_values(self):
        expected = {
            "priority_order", "round_robin", "least_failures",
            "lowest_latency", "capability_match",
        }
        assert {m.value for m in FallbackStrategy} == expected

    def test_count(self):
        assert len(FallbackStrategy) == 5


class TestConsentState:
    def test_all_values(self):
        expected = {"granted", "denied", "pending", "expired", "withdrawn"}
        assert {m.value for m in ConsentState} == expected

    def test_count(self):
        assert len(ConsentState) == 5


# ---------------------------------------------------------------------------
# 1. ConnectorRateLimitPolicy
# ---------------------------------------------------------------------------


class TestConnectorRateLimitPolicy:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            policy_id="pol-1",
            connector_id="conn-1",
            max_requests_per_second=10,
            max_requests_per_minute=100,
            max_requests_per_hour=1000,
            max_burst_size=20,
            retry_after_seconds=30,
            created_at=NOW,
        )
        defaults.update(kw)
        return ConnectorRateLimitPolicy(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.policy_id == "pol-1"
        assert obj.connector_id == "conn-1"
        assert obj.max_requests_per_second == 10
        assert obj.retry_after_seconds == 30

    def test_empty_policy_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(policy_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_negative_max_requests_per_second_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_requests_per_second=-1)

    def test_negative_max_requests_per_minute_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_requests_per_minute=-1)

    def test_negative_max_requests_per_hour_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_requests_per_hour=-1)

    def test_negative_max_burst_size_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_burst_size=-1)

    def test_negative_retry_after_seconds_rejected(self):
        with pytest.raises(ValueError):
            self._make(retry_after_seconds=-1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.policy_id = "other"

    def test_serialization(self):
        obj = self._make()
        d = obj.to_dict()
        assert d["policy_id"] == "pol-1"
        assert d["connector_id"] == "conn-1"
        assert d["max_requests_per_second"] == 10
        assert d["created_at"] == NOW


# ---------------------------------------------------------------------------
# 2. ConnectorQuotaState
# ---------------------------------------------------------------------------


class TestConnectorQuotaState:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            quota_id="q-1",
            connector_id="conn-1",
            quota_limit=1000,
            quota_used=200,
            quota_remaining=800,
            reset_at=NOW,
            reported_at=NOW,
        )
        defaults.update(kw)
        return ConnectorQuotaState(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.quota_id == "q-1"
        assert obj.quota_limit == 1000

    def test_empty_quota_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(quota_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_negative_quota_limit_rejected(self):
        with pytest.raises(ValueError):
            self._make(quota_limit=-1)

    def test_negative_quota_used_rejected(self):
        with pytest.raises(ValueError):
            self._make(quota_used=-1)

    def test_negative_quota_remaining_rejected(self):
        with pytest.raises(ValueError):
            self._make(quota_remaining=-1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.quota_id = "other"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["quota_id"] == "q-1"
        assert d["quota_limit"] == 1000
        assert d["reset_at"] == NOW


# ---------------------------------------------------------------------------
# 3. ConnectorExecutionRecord
# ---------------------------------------------------------------------------


class TestConnectorExecutionRecord:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            execution_id="exec-1",
            connector_id="conn-1",
            connector_type=ExternalConnectorType.GENERIC_API,
            operation="send",
            success=True,
            latency_ms=42.5,
            request_bytes=128,
            response_bytes=256,
            status_code=200,
            error_message="",
            correlation_id="corr-1",
            executed_at=NOW,
            metadata={"key": "val"},
        )
        defaults.update(kw)
        return ConnectorExecutionRecord(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.execution_id == "exec-1"
        assert obj.connector_type == ExternalConnectorType.GENERIC_API
        assert obj.success is True
        assert obj.latency_ms == 42.5

    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(execution_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="")

    def test_invalid_connector_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_type="not_an_enum")

    def test_bool_success_required(self):
        with pytest.raises(ValueError):
            self._make(success=1)

    def test_negative_latency_rejected(self):
        with pytest.raises(ValueError):
            self._make(latency_ms=-1.0)

    def test_negative_request_bytes_rejected(self):
        with pytest.raises(ValueError):
            self._make(request_bytes=-1)

    def test_negative_response_bytes_rejected(self):
        with pytest.raises(ValueError):
            self._make(response_bytes=-1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.execution_id = "other"

    def test_frozen_metadata_immutable(self):
        obj = self._make()
        with pytest.raises(TypeError):
            obj.metadata["new"] = "val"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["execution_id"] == "exec-1"
        assert d["connector_type"] == ExternalConnectorType.GENERIC_API
        assert d["metadata"] == {"key": "val"}


# ---------------------------------------------------------------------------
# 4. ConnectorCapabilityBinding
# ---------------------------------------------------------------------------


class TestConnectorCapabilityBinding:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            binding_id="bind-1",
            connector_id="conn-1",
            connector_type=ExternalConnectorType.SMS_PROVIDER,
            bound_adapter_id="adapter-1",
            bound_parser_id="parser-1",
            supported_operations=("send", "receive"),
            max_payload_bytes=1024,
            reliability_score=0.95,
            priority=1,
            enabled=True,
            tags=("sms", "prod"),
            created_at=NOW,
        )
        defaults.update(kw)
        return ConnectorCapabilityBinding(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.binding_id == "bind-1"
        assert obj.reliability_score == 0.95
        assert obj.supported_operations == ("send", "receive")
        assert obj.tags == ("sms", "prod")

    def test_empty_binding_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(binding_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_invalid_connector_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_type="bad")

    def test_negative_max_payload_bytes_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_payload_bytes=-1)

    def test_reliability_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=-0.1)

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=1.1)

    def test_reliability_score_nan_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=math.nan)

    def test_reliability_score_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=True)

    def test_negative_priority_rejected(self):
        with pytest.raises(ValueError):
            self._make(priority=-1)

    def test_bool_enabled_required(self):
        with pytest.raises(ValueError):
            self._make(enabled=1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.binding_id = "other"

    def test_frozen_tuple_supported_operations(self):
        obj = self._make()
        with pytest.raises((TypeError, AttributeError)):
            obj.supported_operations.append("delete")

    def test_frozen_tuple_tags(self):
        obj = self._make()
        with pytest.raises((TypeError, AttributeError)):
            obj.tags.append("new")

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["binding_id"] == "bind-1"
        assert d["connector_type"] == ExternalConnectorType.SMS_PROVIDER
        assert d["reliability_score"] == 0.95
        assert d["supported_operations"] == ["send", "receive"]
        assert d["tags"] == ["sms", "prod"]


# ---------------------------------------------------------------------------
# 5. ConnectorFailureRecord
# ---------------------------------------------------------------------------


class TestConnectorFailureRecord:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            failure_id="fail-1",
            connector_id="conn-1",
            category=ConnectorFailureCategory.TIMEOUT,
            operation="send",
            error_message="timed out",
            status_code=504,
            is_retriable=True,
            retry_after_seconds=60,
            fallback_connector_id="conn-2",
            correlation_id="corr-1",
            occurred_at=NOW,
        )
        defaults.update(kw)
        return ConnectorFailureRecord(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.failure_id == "fail-1"
        assert obj.category == ConnectorFailureCategory.TIMEOUT
        assert obj.is_retriable is True

    def test_empty_failure_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(failure_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            self._make(operation="")

    def test_invalid_category_rejected(self):
        with pytest.raises(ValueError):
            self._make(category="not_valid")

    def test_bool_is_retriable_required(self):
        with pytest.raises(ValueError):
            self._make(is_retriable=1)

    def test_negative_retry_after_seconds_rejected(self):
        with pytest.raises(ValueError):
            self._make(retry_after_seconds=-1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.failure_id = "other"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["failure_id"] == "fail-1"
        assert d["category"] == ConnectorFailureCategory.TIMEOUT
        assert d["is_retriable"] is True


# ---------------------------------------------------------------------------
# 6. SecretScope
# ---------------------------------------------------------------------------


class TestSecretScope:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            scope_id="scope-1",
            connector_id="conn-1",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="vault://secret/key",
            rotation_interval_hours=24,
            last_rotated_at=NOW,
            expires_at=NOW,
            created_at=NOW,
        )
        defaults.update(kw)
        return SecretScope(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.scope_id == "scope-1"
        assert obj.auth_mode == ConnectorAuthMode.API_KEY
        assert obj.rotation_state == SecretRotationState.CURRENT

    def test_empty_scope_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(scope_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_empty_credential_ref_rejected(self):
        with pytest.raises(ValueError):
            self._make(credential_ref="")

    def test_invalid_auth_mode_rejected(self):
        with pytest.raises(ValueError):
            self._make(auth_mode="bad")

    def test_invalid_rotation_state_rejected(self):
        with pytest.raises(ValueError):
            self._make(rotation_state="bad")

    def test_negative_rotation_interval_hours_rejected(self):
        with pytest.raises(ValueError):
            self._make(rotation_interval_hours=-1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.scope_id = "other"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["scope_id"] == "scope-1"
        assert d["auth_mode"] == ConnectorAuthMode.API_KEY
        assert d["rotation_state"] == SecretRotationState.CURRENT
        assert d["rotation_interval_hours"] == 24


# ---------------------------------------------------------------------------
# 7. ConnectorRetentionPolicy
# ---------------------------------------------------------------------------


class TestConnectorRetentionPolicy:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            policy_id="ret-1",
            connector_id="conn-1",
            redaction_level=RedactionLevel.BODY_PARTIAL,
            retention_days=90,
            store_request_payload=False,
            store_response_payload=False,
            pii_scrub_enabled=True,
            audit_trail_required=True,
            created_at=NOW,
        )
        defaults.update(kw)
        return ConnectorRetentionPolicy(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.policy_id == "ret-1"
        assert obj.redaction_level == RedactionLevel.BODY_PARTIAL
        assert obj.pii_scrub_enabled is True

    def test_empty_policy_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(policy_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_invalid_redaction_level_rejected(self):
        with pytest.raises(ValueError):
            self._make(redaction_level="bad")

    def test_negative_retention_days_rejected(self):
        with pytest.raises(ValueError):
            self._make(retention_days=-1)

    def test_bool_store_request_payload_required(self):
        with pytest.raises(ValueError):
            self._make(store_request_payload=1)

    def test_bool_store_response_payload_required(self):
        with pytest.raises(ValueError):
            self._make(store_response_payload=1)

    def test_bool_pii_scrub_enabled_required(self):
        with pytest.raises(ValueError):
            self._make(pii_scrub_enabled=0)

    def test_bool_audit_trail_required_required(self):
        with pytest.raises(ValueError):
            self._make(audit_trail_required=0)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.policy_id = "other"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["policy_id"] == "ret-1"
        assert d["redaction_level"] == RedactionLevel.BODY_PARTIAL
        assert d["retention_days"] == 90
        assert d["store_request_payload"] is False
        assert d["audit_trail_required"] is True


# ---------------------------------------------------------------------------
# 8. ConnectorHealthSnapshot
# ---------------------------------------------------------------------------


class TestConnectorHealthSnapshot:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            snapshot_id="snap-1",
            connector_id="conn-1",
            health_state=ConnectorHealthState.HEALTHY,
            reliability_score=0.99,
            total_executions=1000,
            failed_executions=10,
            avg_latency_ms=55.0,
            circuit_breaker_trips=0,
            consecutive_failures=0,
            last_success_at=NOW,
            last_failure_at=NOW,
            reported_at=NOW,
        )
        defaults.update(kw)
        return ConnectorHealthSnapshot(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.snapshot_id == "snap-1"
        assert obj.health_state == ConnectorHealthState.HEALTHY
        assert obj.reliability_score == 0.99

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(snapshot_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_invalid_health_state_rejected(self):
        with pytest.raises(ValueError):
            self._make(health_state="bad")

    def test_reliability_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=-0.01)

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=1.01)

    def test_reliability_score_nan_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=math.nan)

    def test_reliability_score_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=True)

    def test_negative_total_executions_rejected(self):
        with pytest.raises(ValueError):
            self._make(total_executions=-1)

    def test_negative_failed_executions_rejected(self):
        with pytest.raises(ValueError):
            self._make(failed_executions=-1)

    def test_negative_avg_latency_ms_rejected(self):
        with pytest.raises(ValueError):
            self._make(avg_latency_ms=-1.0)

    def test_negative_circuit_breaker_trips_rejected(self):
        with pytest.raises(ValueError):
            self._make(circuit_breaker_trips=-1)

    def test_negative_consecutive_failures_rejected(self):
        with pytest.raises(ValueError):
            self._make(consecutive_failures=-1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.snapshot_id = "other"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["snapshot_id"] == "snap-1"
        assert d["health_state"] == ConnectorHealthState.HEALTHY
        assert d["reliability_score"] == 0.99
        assert d["total_executions"] == 1000


# ---------------------------------------------------------------------------
# 9. FallbackChainEntry
# ---------------------------------------------------------------------------


class TestFallbackChainEntry:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            entry_id="entry-1",
            chain_id="chain-1",
            connector_id="conn-1",
            priority=0,
            min_reliability=0.8,
            max_latency_ms=500.0,
            enabled=True,
            conditions={"region": "us-east"},
        )
        defaults.update(kw)
        return FallbackChainEntry(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.entry_id == "entry-1"
        assert obj.min_reliability == 0.8
        assert obj.max_latency_ms == 500.0

    def test_empty_entry_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(entry_id="")

    def test_empty_chain_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(chain_id="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_negative_priority_rejected(self):
        with pytest.raises(ValueError):
            self._make(priority=-1)

    def test_min_reliability_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(min_reliability=-0.1)

    def test_min_reliability_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(min_reliability=1.1)

    def test_min_reliability_nan_rejected(self):
        with pytest.raises(ValueError):
            self._make(min_reliability=math.nan)

    def test_min_reliability_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(min_reliability=True)

    def test_negative_max_latency_ms_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_latency_ms=-1.0)

    def test_bool_enabled_required(self):
        with pytest.raises(ValueError):
            self._make(enabled=1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.entry_id = "other"

    def test_frozen_conditions_immutable(self):
        obj = self._make()
        with pytest.raises(TypeError):
            obj.conditions["new_key"] = "val"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["entry_id"] == "entry-1"
        assert d["min_reliability"] == 0.8
        assert d["conditions"] == {"region": "us-east"}


# ---------------------------------------------------------------------------
# 10. FallbackChain
# ---------------------------------------------------------------------------


class TestFallbackChain:
    @staticmethod
    def _make_entry(**kw):
        defaults = dict(
            entry_id="entry-1",
            chain_id="chain-1",
            connector_id="conn-1",
            priority=0,
            min_reliability=0.5,
            max_latency_ms=200.0,
            enabled=True,
            conditions={},
        )
        defaults.update(kw)
        return FallbackChainEntry(**defaults)

    @classmethod
    def _make(cls, **kw):
        defaults = dict(
            chain_id="chain-1",
            name="Primary SMS fallback",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(cls._make_entry(),),
            created_at=NOW,
        )
        defaults.update(kw)
        return FallbackChain(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.chain_id == "chain-1"
        assert obj.strategy == FallbackStrategy.PRIORITY_ORDER
        assert len(obj.entries) == 1

    def test_empty_chain_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(chain_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(name="")

    def test_invalid_strategy_rejected(self):
        with pytest.raises(ValueError):
            self._make(strategy="bad")

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.chain_id = "other"

    def test_frozen_tuple_entries(self):
        obj = self._make()
        with pytest.raises((TypeError, AttributeError)):
            obj.entries.append(self._make_entry())

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["chain_id"] == "chain-1"
        assert d["strategy"] == FallbackStrategy.PRIORITY_ORDER
        assert isinstance(d["entries"], list)
        assert len(d["entries"]) == 1
        assert d["entries"][0]["entry_id"] == "entry-1"


# ---------------------------------------------------------------------------
# 11. ChannelConsentRecord
# ---------------------------------------------------------------------------


class TestChannelConsentRecord:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            consent_id="consent-1",
            identity_id="id-1",
            channel_type="sms",
            connector_id="conn-1",
            consent_state=ConsentState.GRANTED,
            granted_at=NOW,
            expires_at=NOW,
            recorded_at=NOW,
        )
        defaults.update(kw)
        return ChannelConsentRecord(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.consent_id == "consent-1"
        assert obj.consent_state == ConsentState.GRANTED

    def test_empty_consent_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(consent_id="")

    def test_empty_identity_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(identity_id="")

    def test_empty_channel_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(channel_type="")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_invalid_consent_state_rejected(self):
        with pytest.raises(ValueError):
            self._make(consent_state="bad")

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.consent_id = "other"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["consent_id"] == "consent-1"
        assert d["consent_state"] == ConsentState.GRANTED
        assert d["channel_type"] == "sms"


# ---------------------------------------------------------------------------
# 12. ExternalConnectorDescriptor
# ---------------------------------------------------------------------------


class TestExternalConnectorDescriptor:
    @staticmethod
    def _make(**kw):
        defaults = dict(
            connector_id="conn-1",
            name="Twilio SMS",
            connector_type=ExternalConnectorType.SMS_PROVIDER,
            auth_mode=ConnectorAuthMode.API_KEY,
            health_state=ConnectorHealthState.HEALTHY,
            provider_name="Twilio",
            version="2.0.0",
            base_url="https://api.twilio.com",
            bound_adapter_id="adapter-1",
            bound_parser_id="parser-1",
            reliability_score=0.99,
            enabled=True,
            tags=("sms", "production"),
            created_at=NOW,
            metadata={"tier": "premium"},
        )
        defaults.update(kw)
        return ExternalConnectorDescriptor(**defaults)

    def test_valid_construction(self):
        obj = self._make()
        assert obj.connector_id == "conn-1"
        assert obj.name == "Twilio SMS"
        assert obj.connector_type == ExternalConnectorType.SMS_PROVIDER
        assert obj.auth_mode == ConnectorAuthMode.API_KEY
        assert obj.health_state == ConnectorHealthState.HEALTHY
        assert obj.reliability_score == 0.99
        assert obj.enabled is True
        assert obj.tags == ("sms", "production")

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(name="")

    def test_empty_provider_name_rejected(self):
        with pytest.raises(ValueError):
            self._make(provider_name="")

    def test_empty_version_rejected(self):
        with pytest.raises(ValueError):
            self._make(version="")

    def test_invalid_connector_type_rejected(self):
        with pytest.raises(ValueError):
            self._make(connector_type="bad")

    def test_invalid_auth_mode_rejected(self):
        with pytest.raises(ValueError):
            self._make(auth_mode="bad")

    def test_invalid_health_state_rejected(self):
        with pytest.raises(ValueError):
            self._make(health_state="bad")

    def test_reliability_score_below_zero_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=-0.01)

    def test_reliability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=1.01)

    def test_reliability_score_nan_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=math.nan)

    def test_reliability_score_bool_rejected(self):
        with pytest.raises(ValueError):
            self._make(reliability_score=True)

    def test_bool_enabled_required(self):
        with pytest.raises(ValueError):
            self._make(enabled=1)

    def test_frozen_immutability(self):
        obj = self._make()
        with pytest.raises(AttributeError):
            obj.connector_id = "other"

    def test_frozen_tuple_tags(self):
        obj = self._make()
        with pytest.raises((TypeError, AttributeError)):
            obj.tags.append("new")

    def test_frozen_metadata_immutable(self):
        obj = self._make()
        with pytest.raises(TypeError):
            obj.metadata["new_key"] = "val"

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["connector_id"] == "conn-1"
        assert d["name"] == "Twilio SMS"
        assert d["connector_type"] == ExternalConnectorType.SMS_PROVIDER
        assert d["auth_mode"] == ConnectorAuthMode.API_KEY
        assert d["health_state"] == ConnectorHealthState.HEALTHY
        assert d["reliability_score"] == 0.99
        assert d["enabled"] is True
        assert d["tags"] == ["sms", "production"]
        assert d["metadata"] == {"tier": "premium"}
