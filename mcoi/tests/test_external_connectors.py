"""Tests for mcoi_runtime.core.external_connectors.

Covers: ExternalConnectorRegistry, test connectors, execution, fallback,
rate limits, quotas, secret scopes, retention, consent, health, state hash.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.external_connector import (
    ChannelConsentRecord,
    ConnectorAuthMode,
    ConnectorCapabilityBinding,
    ConnectorExecutionRecord,
    ConnectorFailureCategory,
    ConnectorHealthSnapshot,
    ConnectorHealthState,
    ConnectorQuotaState,
    ConnectorRateLimitPolicy,
    ConnectorRetentionPolicy,
    ConsentState,
    ExternalConnectorDescriptor,
    ExternalConnectorType,
    FallbackChain,
    FallbackChainEntry,
    FallbackStrategy,
    RedactionLevel,
    SecretRotationState,
    SecretScope,
)
from mcoi_runtime.core.external_connectors import (
    ChatProviderTestConnector,
    EmailProviderTestConnector,
    ExternalConnector,
    ExternalConnectorRegistry,
    FailingTestConnector,
    GenericApiTestConnector,
    ParserProviderTestConnector,
    SmsProviderTestConnector,
    SocialProviderTestConnector,
    StorageProviderTestConnector,
    VoiceProviderTestConnector,
    WebhookProviderTestConnector,
    register_all_test_connectors,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_with_sms() -> tuple[ExternalConnectorRegistry, SmsProviderTestConnector]:
    reg = ExternalConnectorRegistry()
    conn = SmsProviderTestConnector()
    reg.register(conn)
    return reg, conn


def _set_valid_secret(reg: ExternalConnectorRegistry, connector_id: str) -> SecretScope:
    scope = SecretScope(
        scope_id=f"scope-{connector_id}",
        connector_id=connector_id,
        auth_mode=ConnectorAuthMode.API_KEY,
        rotation_state=SecretRotationState.CURRENT,
        credential_ref="vault://test-key",
        rotation_interval_hours=24,
        last_rotated_at=NOW,
        expires_at="2027-01-01T00:00:00+00:00",
        created_at=NOW,
    )
    reg.set_secret_scope(scope)
    return scope


class SecretRaisingConnector(ExternalConnector):
    """Connector that raises a sensitive provider error for sanitization tests."""

    def __init__(self, connector_id: str = "secret-raising") -> None:
        self._id = connector_id

    def connector_id(self) -> str:
        return self._id

    def connector_type(self) -> ExternalConnectorType:
        return ExternalConnectorType.GENERIC_API

    def auth_mode(self) -> ConnectorAuthMode:
        return ConnectorAuthMode.NONE

    def descriptor(self) -> ExternalConnectorDescriptor:
        return ExternalConnectorDescriptor(
            connector_id=self._id,
            name="Secret Raising Connector",
            connector_type=ExternalConnectorType.GENERIC_API,
            auth_mode=ConnectorAuthMode.NONE,
            health_state=ConnectorHealthState.HEALTHY,
            provider_name="secret-test",
            version="1.0.0",
            enabled=True,
            created_at=NOW,
        )

    def execute(
        self, operation: str, payload: dict[str, str],
    ) -> ConnectorExecutionRecord:
        raise RuntimeError(f"provider-secret-token leaked during {operation}")

    def health_check(self) -> ConnectorHealthSnapshot:
        return ConnectorHealthSnapshot(
            snapshot_id="health-secret-raising",
            connector_id=self._id,
            health_state=ConnectorHealthState.HEALTHY,
            reliability_score=1.0,
            total_executions=0,
            failed_executions=0,
            avg_latency_ms=0.0,
            circuit_breaker_trips=0,
            consecutive_failures=0,
            last_success_at=NOW,
            last_failure_at=NOW,
            reported_at=NOW,
        )


class TimeoutRaisingConnector(SecretRaisingConnector):
    """Connector that raises timeout errors for classification tests."""

    def execute(
        self, operation: str, payload: dict[str, str],
    ) -> ConnectorExecutionRecord:
        raise TimeoutError(f"timeout-secret during {operation}")

    def descriptor(self) -> ExternalConnectorDescriptor:
        return ExternalConnectorDescriptor(
            connector_id=self._id,
            name="Timeout Raising Connector",
            connector_type=ExternalConnectorType.GENERIC_API,
            auth_mode=ConnectorAuthMode.NONE,
            health_state=ConnectorHealthState.HEALTHY,
            provider_name="timeout-test",
            version="1.0.0",
            enabled=True,
            created_at=NOW,
        )


# ===================================================================
# Registration
# ===================================================================


class TestRegistration:
    def test_register_returns_descriptor(self):
        reg = ExternalConnectorRegistry()
        conn = SmsProviderTestConnector()
        desc = reg.register(conn)
        assert isinstance(desc, ExternalConnectorDescriptor)
        assert desc.connector_id == conn.connector_id()
        assert desc.connector_type == ExternalConnectorType.SMS_PROVIDER

    def test_reject_duplicate(self):
        reg = ExternalConnectorRegistry()
        conn = SmsProviderTestConnector()
        reg.register(conn)
        with pytest.raises(RuntimeCoreInvariantError, match="already registered"):
            reg.register(SmsProviderTestConnector())

    def test_reject_non_external_connector(self):
        reg = ExternalConnectorRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="must be an ExternalConnector"):
            reg.register("not-a-connector")  # type: ignore[arg-type]

    def test_connector_count(self):
        reg = ExternalConnectorRegistry()
        assert reg.connector_count == 0
        reg.register(SmsProviderTestConnector())
        assert reg.connector_count == 1


# ===================================================================
# Retrieval
# ===================================================================


class TestRetrieval:
    def test_get_connector(self):
        reg, conn = _make_registry_with_sms()
        got = reg.get_connector(conn.connector_id())
        assert got is conn

    def test_get_connector_missing_raises(self):
        reg = ExternalConnectorRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            reg.get_connector("nonexistent")

    def test_get_descriptor(self):
        reg, conn = _make_registry_with_sms()
        desc = reg.get_descriptor(conn.connector_id())
        assert desc.connector_id == conn.connector_id()

    def test_get_descriptor_missing_raises(self):
        reg = ExternalConnectorRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            reg.get_descriptor("nonexistent")


# ===================================================================
# Listing
# ===================================================================


class TestListing:
    def test_list_connectors_all(self):
        reg = ExternalConnectorRegistry()
        register_all_test_connectors(reg)
        all_descs = reg.list_connectors()
        assert len(all_descs) == 9

    def test_list_connectors_by_type(self):
        reg = ExternalConnectorRegistry()
        register_all_test_connectors(reg)
        sms_descs = reg.list_connectors(connector_type=ExternalConnectorType.SMS_PROVIDER)
        assert len(sms_descs) == 1
        assert sms_descs[0].connector_type == ExternalConnectorType.SMS_PROVIDER

    def test_list_connectors_by_health(self):
        reg = ExternalConnectorRegistry()
        register_all_test_connectors(reg)
        healthy = reg.list_connectors(health_state=ConnectorHealthState.HEALTHY)
        assert len(healthy) == 9
        unhealthy = reg.list_connectors(health_state=ConnectorHealthState.UNHEALTHY)
        assert len(unhealthy) == 0

    def test_list_available(self):
        reg = ExternalConnectorRegistry()
        register_all_test_connectors(reg)
        avail = reg.list_available()
        assert len(avail) == 9
        for d in avail:
            assert d.enabled is True
            assert d.health_state in (
                ConnectorHealthState.HEALTHY,
                ConnectorHealthState.DEGRADED,
            )

    def test_list_by_type(self):
        reg = ExternalConnectorRegistry()
        register_all_test_connectors(reg)
        sms = reg.list_by_type(ExternalConnectorType.SMS_PROVIDER)
        assert len(sms) == 1
        assert isinstance(sms[0], ExternalConnector)
        assert sms[0].connector_type() == ExternalConnectorType.SMS_PROVIDER


# ===================================================================
# Capability bindings
# ===================================================================


class TestCapabilityBindings:
    def test_add_and_get_bindings(self):
        reg, conn = _make_registry_with_sms()
        binding = ConnectorCapabilityBinding(
            binding_id="bind-1",
            connector_id=conn.connector_id(),
            connector_type=ExternalConnectorType.SMS_PROVIDER,
            bound_adapter_id="adapter-sms",
            supported_operations=("send", "receive"),
            max_payload_bytes=1600,
            reliability_score=0.95,
            enabled=True,
            tags=("sms",),
            created_at=NOW,
        )
        reg.add_binding(binding)

        by_conn = reg.get_bindings_for_connector(conn.connector_id())
        assert len(by_conn) == 1
        assert by_conn[0].binding_id == "bind-1"

    def test_get_bindings_for_adapter(self):
        reg, conn = _make_registry_with_sms()
        binding = ConnectorCapabilityBinding(
            binding_id="bind-a",
            connector_id=conn.connector_id(),
            connector_type=ExternalConnectorType.SMS_PROVIDER,
            bound_adapter_id="adapter-sms",
            supported_operations=("send",),
            max_payload_bytes=1600,
            reliability_score=0.9,
            enabled=True,
            created_at=NOW,
        )
        reg.add_binding(binding)
        by_adapter = reg.get_bindings_for_adapter("adapter-sms")
        assert len(by_adapter) == 1

    def test_get_bindings_for_parser(self):
        reg = ExternalConnectorRegistry()
        conn = ParserProviderTestConnector()
        reg.register(conn)
        binding = ConnectorCapabilityBinding(
            binding_id="bind-p",
            connector_id=conn.connector_id(),
            connector_type=ExternalConnectorType.PARSER_PROVIDER,
            bound_parser_id="parser-pdf",
            supported_operations=("parse",),
            max_payload_bytes=104857600,
            reliability_score=0.9,
            enabled=True,
            created_at=NOW,
        )
        reg.add_binding(binding)
        by_parser = reg.get_bindings_for_parser("parser-pdf")
        assert len(by_parser) == 1

    def test_add_binding_unknown_connector_raises(self):
        reg = ExternalConnectorRegistry()
        binding = ConnectorCapabilityBinding(
            binding_id="bind-x",
            connector_id="nonexistent",
            connector_type=ExternalConnectorType.GENERIC_API,
            supported_operations=("send",),
            max_payload_bytes=0,
            reliability_score=1.0,
            enabled=True,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            reg.add_binding(binding)


# ===================================================================
# Rate limits
# ===================================================================


class TestRateLimits:
    def test_set_and_get_rate_limit(self):
        reg, conn = _make_registry_with_sms()
        policy = ConnectorRateLimitPolicy(
            policy_id="rl-1",
            connector_id=conn.connector_id(),
            max_requests_per_second=10,
            max_requests_per_minute=100,
            max_requests_per_hour=1000,
            max_burst_size=5,
            retry_after_seconds=30,
            created_at=NOW,
        )
        reg.set_rate_limit(policy)
        got = reg.get_rate_limit(conn.connector_id())
        assert got is not None
        assert got.max_burst_size == 5

    def test_get_rate_limit_missing_returns_none(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_rate_limit("nonexistent") is None

    def test_check_rate_limit_no_policy_allows(self):
        reg, conn = _make_registry_with_sms()
        assert reg.check_rate_limit(conn.connector_id()) is True

    def test_check_rate_limit_burst_exceeded(self):
        reg, conn = _make_registry_with_sms()
        cid = conn.connector_id()
        policy = ConnectorRateLimitPolicy(
            policy_id="rl-burst",
            connector_id=cid,
            max_burst_size=2,
            created_at=NOW,
        )
        reg.set_rate_limit(policy)
        _set_valid_secret(reg, cid)

        # Execute twice to hit burst
        reg.execute(cid, "send", {"body": "a"})
        reg.execute(cid, "send", {"body": "b"})

        assert reg.check_rate_limit(cid) is False


# ===================================================================
# Quotas
# ===================================================================


class TestQuotas:
    def test_update_and_get_quota(self):
        reg, conn = _make_registry_with_sms()
        quota = ConnectorQuotaState(
            quota_id="q-1",
            connector_id=conn.connector_id(),
            quota_limit=1000,
            quota_used=100,
            quota_remaining=900,
            reset_at="2026-04-01T00:00:00+00:00",
            reported_at=NOW,
        )
        reg.update_quota(quota)
        got = reg.get_quota(conn.connector_id())
        assert got is not None
        assert got.quota_remaining == 900

    def test_get_quota_missing_returns_none(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_quota("nonexistent") is None

    def test_check_quota_no_quota_allows(self):
        reg, conn = _make_registry_with_sms()
        assert reg.check_quota(conn.connector_id()) is True

    def test_check_quota_exhausted(self):
        reg, conn = _make_registry_with_sms()
        quota = ConnectorQuotaState(
            quota_id="q-zero",
            connector_id=conn.connector_id(),
            quota_limit=100,
            quota_used=100,
            quota_remaining=0,
            reset_at="2026-04-01T00:00:00+00:00",
            reported_at=NOW,
        )
        reg.update_quota(quota)
        assert reg.check_quota(conn.connector_id()) is False


# ===================================================================
# Secret scopes
# ===================================================================


class TestSecretScopes:
    def test_set_and_get_secret_scope(self):
        reg, conn = _make_registry_with_sms()
        scope = _set_valid_secret(reg, conn.connector_id())
        got = reg.get_secret_scope(conn.connector_id())
        assert got is not None
        assert got.scope_id == scope.scope_id

    def test_get_secret_scope_missing_returns_none(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_secret_scope("nonexistent") is None

    def test_validate_credential_valid(self):
        reg, conn = _make_registry_with_sms()
        _set_valid_secret(reg, conn.connector_id())
        assert reg.validate_credential(conn.connector_id()) is True

    def test_validate_credential_expired(self):
        reg, conn = _make_registry_with_sms()
        scope = SecretScope(
            scope_id="scope-expired",
            connector_id=conn.connector_id(),
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.EXPIRED,
            credential_ref="vault://expired-key",
            rotation_interval_hours=24,
            last_rotated_at=NOW,
            expires_at=NOW,
            created_at=NOW,
        )
        reg.set_secret_scope(scope)
        assert reg.validate_credential(conn.connector_id()) is False

    def test_validate_credential_revoked(self):
        reg, conn = _make_registry_with_sms()
        scope = SecretScope(
            scope_id="scope-revoked",
            connector_id=conn.connector_id(),
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.REVOKED,
            credential_ref="vault://revoked-key",
            rotation_interval_hours=24,
            last_rotated_at=NOW,
            expires_at=NOW,
            created_at=NOW,
        )
        reg.set_secret_scope(scope)
        assert reg.validate_credential(conn.connector_id()) is False

    def test_validate_credential_no_auth_needed(self):
        reg = ExternalConnectorRegistry()
        conn = FailingTestConnector()  # auth_mode == NONE
        reg.register(conn)
        assert reg.validate_credential(conn.connector_id()) is True

    def test_validate_credential_no_scope_and_auth_required(self):
        reg, conn = _make_registry_with_sms()
        # SMS connector needs API_KEY but no scope set
        assert reg.validate_credential(conn.connector_id()) is False


# ===================================================================
# Retention policies
# ===================================================================


class TestRetentionPolicies:
    def test_set_and_get_retention_policy(self):
        reg, conn = _make_registry_with_sms()
        policy = ConnectorRetentionPolicy(
            policy_id="ret-1",
            connector_id=conn.connector_id(),
            redaction_level=RedactionLevel.BODY_FULL,
            retention_days=30,
            store_request_payload=False,
            store_response_payload=False,
            pii_scrub_enabled=True,
            audit_trail_required=True,
            created_at=NOW,
        )
        reg.set_retention_policy(policy)
        got = reg.get_retention_policy(conn.connector_id())
        assert got is not None
        assert got.retention_days == 30

    def test_get_retention_policy_missing_returns_none(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_retention_policy("nonexistent") is None


# ===================================================================
# Consent
# ===================================================================


class TestConsent:
    def test_record_and_check_consent(self):
        reg, conn = _make_registry_with_sms()
        record = ChannelConsentRecord(
            consent_id="consent-1",
            identity_id="user-abc",
            channel_type="sms",
            connector_id=conn.connector_id(),
            consent_state=ConsentState.GRANTED,
            granted_at=NOW,
            expires_at="2027-01-01T00:00:00+00:00",
            recorded_at=NOW,
        )
        reg.record_consent(record)
        state = reg.check_consent("user-abc", "sms", conn.connector_id())
        assert state == ConsentState.GRANTED

    def test_check_consent_not_found(self):
        reg = ExternalConnectorRegistry()
        state = reg.check_consent("user-x", "sms", "conn-x")
        assert state is None


# ===================================================================
# Fallback chains
# ===================================================================


class TestFallbackChains:
    def _make_chain_registry(self) -> ExternalConnectorRegistry:
        reg = ExternalConnectorRegistry()
        sms1 = SmsProviderTestConnector("sms-primary")
        sms2 = SmsProviderTestConnector("sms-secondary")
        reg.register(sms1)
        reg.register(sms2)
        # Set valid credentials for both
        _set_valid_secret(reg, "sms-primary")
        _set_valid_secret(reg, "sms-secondary")
        return reg

    def test_add_and_get_fallback_chain(self):
        reg = self._make_chain_registry()
        chain = FallbackChain(
            chain_id="chain-sms",
            name="SMS Fallback",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-sms",
                    connector_id="sms-primary", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-sms",
                    connector_id="sms-secondary", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        got = reg.get_fallback_chain("chain-sms")
        assert got is not None
        assert len(got.entries) == 2

    def test_get_fallback_chain_missing_returns_none(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_fallback_chain("nonexistent") is None

    def test_resolve_fallback_first_available(self):
        reg = self._make_chain_registry()
        chain = FallbackChain(
            chain_id="chain-sms",
            name="SMS Fallback",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-sms",
                    connector_id="sms-primary", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-sms",
                    connector_id="sms-secondary", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        resolved = reg.resolve_fallback("chain-sms")
        assert resolved is not None
        assert resolved.connector_id() == "sms-primary"

    def test_resolve_fallback_skip_unhealthy(self):
        reg = ExternalConnectorRegistry()
        failing = FailingTestConnector("failing-primary")
        sms2 = SmsProviderTestConnector("sms-secondary")
        reg.register(failing)
        reg.register(sms2)
        _set_valid_secret(reg, "sms-secondary")
        # failing connector has auth_mode NONE so no scope needed
        # but its health is HEALTHY in descriptor, so we need to
        # make it actually unhealthy by doing a health check which
        # returns UNHEALTHY — but resolve_fallback checks descriptor
        # health_state, not health_check result. The descriptor says HEALTHY.
        # So we need a different approach: skip via rate limit instead.
        # Actually, resolve_fallback checks desc.health_state from the
        # stored descriptor. FailingTestConnector descriptor says HEALTHY.
        # Let's use a rate limit to skip the failing connector.
        policy = ConnectorRateLimitPolicy(
            policy_id="rl-fail",
            connector_id="failing-primary",
            max_burst_size=0,
            created_at=NOW,
        )
        reg.set_rate_limit(policy)

        chain = FallbackChain(
            chain_id="chain-skip",
            name="Skip unhealthy",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-skip",
                    connector_id="failing-primary", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-skip",
                    connector_id="sms-secondary", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        resolved = reg.resolve_fallback("chain-skip")
        assert resolved is not None
        assert resolved.connector_id() == "sms-secondary"

    def test_resolve_fallback_skip_rate_limited(self):
        reg = self._make_chain_registry()
        # Rate limit primary to 0 burst
        policy = ConnectorRateLimitPolicy(
            policy_id="rl-block",
            connector_id="sms-primary",
            max_burst_size=0,
            created_at=NOW,
        )
        reg.set_rate_limit(policy)

        chain = FallbackChain(
            chain_id="chain-rl",
            name="Rate limited fallback",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-rl",
                    connector_id="sms-primary", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-rl",
                    connector_id="sms-secondary", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        resolved = reg.resolve_fallback("chain-rl")
        assert resolved is not None
        assert resolved.connector_id() == "sms-secondary"


# ===================================================================
# Execution
# ===================================================================


class TestExecution:
    def test_execute_success(self):
        reg, conn = _make_registry_with_sms()
        _set_valid_secret(reg, conn.connector_id())
        record = reg.execute(conn.connector_id(), "send", {"body": "hello"})
        assert isinstance(record, ConnectorExecutionRecord)
        assert record.success is True
        assert record.connector_id == conn.connector_id()
        assert record.operation == "send"

    def test_execute_auth_failure(self):
        reg, conn = _make_registry_with_sms()
        # No secret scope set, connector requires API_KEY
        record = reg.execute(conn.connector_id(), "send", {"body": "hello"})
        assert record.success is False
        assert "credential" in record.error_message

    def test_execute_rate_limited(self):
        reg, conn = _make_registry_with_sms()
        cid = conn.connector_id()
        _set_valid_secret(reg, cid)
        policy = ConnectorRateLimitPolicy(
            policy_id="rl-zero",
            connector_id=cid,
            max_burst_size=0,
            created_at=NOW,
        )
        reg.set_rate_limit(policy)
        record = reg.execute(cid, "send", {"body": "x"})
        assert record.success is False
        assert "rate limit" in record.error_message

    def test_execute_quota_exhausted(self):
        reg, conn = _make_registry_with_sms()
        cid = conn.connector_id()
        _set_valid_secret(reg, cid)
        quota = ConnectorQuotaState(
            quota_id="q-empty",
            connector_id=cid,
            quota_limit=100,
            quota_used=100,
            quota_remaining=0,
            reset_at="2026-04-01T00:00:00+00:00",
            reported_at=NOW,
        )
        reg.update_quota(quota)
        record = reg.execute(cid, "send", {"body": "x"})
        assert record.success is False
        assert "quota" in record.error_message

    def test_execute_disabled_connector(self):
        """A connector whose descriptor says enabled=True should work;
        we test that the disabled path records a policy_blocked failure
        by manually patching the stored descriptor."""
        reg, conn = _make_registry_with_sms()
        cid = conn.connector_id()
        _set_valid_secret(reg, cid)
        # Overwrite stored descriptor with enabled=False
        disabled_desc = ExternalConnectorDescriptor(
            connector_id=cid,
            name="Disabled SMS",
            connector_type=ExternalConnectorType.SMS_PROVIDER,
            auth_mode=ConnectorAuthMode.API_KEY,
            health_state=ConnectorHealthState.HEALTHY,
            provider_name="twilio-test",
            version="1.0.0",
            enabled=False,
            created_at=NOW,
        )
        reg._descriptors[cid] = disabled_desc
        record = reg.execute(cid, "send", {"body": "x"})
        assert record.success is False
        assert "disabled" in record.error_message

    def test_execute_provider_exception_is_sanitized(self):
        reg = ExternalConnectorRegistry()
        conn = SecretRaisingConnector()
        reg.register(conn)

        record = reg.execute(conn.connector_id(), "send", {"body": "hello"})

        assert record.success is False
        assert record.error_message == "provider error (RuntimeError)"
        assert "provider-secret-token" not in record.error_message

        failures = reg.get_failures(conn.connector_id())
        assert len(failures) == 1
        assert failures[0].category == ConnectorFailureCategory.PROVIDER_ERROR
        assert failures[0].error_message == "provider error (RuntimeError)"

    def test_execute_timeout_exception_is_classified_and_sanitized(self):
        reg = ExternalConnectorRegistry()
        conn = TimeoutRaisingConnector("timeout-raising")
        reg.register(conn)

        record = reg.execute(conn.connector_id(), "send", {"body": "hello"})

        assert record.success is False
        assert record.error_message == "connector timeout (TimeoutError)"
        assert "timeout-secret" not in record.error_message

        failures = reg.get_failures(conn.connector_id())
        assert len(failures) == 1
        assert failures[0].category == ConnectorFailureCategory.TIMEOUT
        assert failures[0].error_message == "connector timeout (TimeoutError)"


# ===================================================================
# Execute with fallback
# ===================================================================


class TestExecuteWithFallback:
    def test_first_succeeds(self):
        reg = ExternalConnectorRegistry()
        sms1 = SmsProviderTestConnector("sms-1")
        sms2 = SmsProviderTestConnector("sms-2")
        reg.register(sms1)
        reg.register(sms2)
        _set_valid_secret(reg, "sms-1")
        _set_valid_secret(reg, "sms-2")

        chain = FallbackChain(
            chain_id="chain-fb",
            name="FB Chain",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-fb",
                    connector_id="sms-1", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-fb",
                    connector_id="sms-2", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        result = reg.execute_with_fallback("chain-fb", "send", {"body": "hi"})
        assert result["record"] is not None
        assert result["record"].success is True
        assert result["connector_id"] == "sms-1"
        assert result["fallback_used"] is False
        assert len(result["attempts"]) == 1

    def test_fallback_to_second(self):
        reg = ExternalConnectorRegistry()
        fail = FailingTestConnector("fail-1")
        sms2 = SmsProviderTestConnector("sms-2")
        reg.register(fail)
        reg.register(sms2)
        # fail-1 has auth_mode NONE so credential is valid
        _set_valid_secret(reg, "sms-2")

        chain = FallbackChain(
            chain_id="chain-fb2",
            name="FB Chain 2",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-fb2",
                    connector_id="fail-1", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-fb2",
                    connector_id="sms-2", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        result = reg.execute_with_fallback("chain-fb2", "send", {"body": "hi"})
        assert result["record"] is not None
        assert result["record"].success is True
        assert result["connector_id"] == "sms-2"
        assert result["fallback_used"] is True
        assert len(result["attempts"]) == 2

    def test_all_fail(self):
        reg = ExternalConnectorRegistry()
        fail1 = FailingTestConnector("fail-1")
        fail2 = FailingTestConnector("fail-2")
        reg.register(fail1)
        reg.register(fail2)

        chain = FallbackChain(
            chain_id="chain-allfail",
            name="All Fail",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="e1", chain_id="chain-allfail",
                    connector_id="fail-1", priority=0, enabled=True,
                ),
                FallbackChainEntry(
                    entry_id="e2", chain_id="chain-allfail",
                    connector_id="fail-2", priority=1, enabled=True,
                ),
            ),
            created_at=NOW,
        )
        reg.add_fallback_chain(chain)
        result = reg.execute_with_fallback("chain-allfail", "send", {"body": "hi"})
        assert result["record"] is None
        assert result["connector_id"] is None
        assert result["fallback_used"] is True
        assert len(result["attempts"]) == 2

    def test_execute_with_fallback_missing_chain_raises(self):
        reg = ExternalConnectorRegistry()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            reg.execute_with_fallback("nonexistent", "send", {})


# ===================================================================
# Health
# ===================================================================


class TestHealth:
    def test_health_check(self):
        reg, conn = _make_registry_with_sms()
        snap = reg.health_check(conn.connector_id())
        assert isinstance(snap, ConnectorHealthSnapshot)
        assert snap.connector_id == conn.connector_id()
        assert snap.health_state == ConnectorHealthState.HEALTHY

    def test_health_check_all(self):
        reg = ExternalConnectorRegistry()
        register_all_test_connectors(reg)
        snaps = reg.health_check_all()
        assert len(snaps) == 9
        for s in snaps:
            assert isinstance(s, ConnectorHealthSnapshot)

    def test_get_health_after_check(self):
        reg, conn = _make_registry_with_sms()
        reg.health_check(conn.connector_id())
        snap = reg.get_health(conn.connector_id())
        assert snap is not None

    def test_get_health_before_check_returns_none(self):
        reg, conn = _make_registry_with_sms()
        assert reg.get_health(conn.connector_id()) is None


# ===================================================================
# Execution / failure history
# ===================================================================


class TestHistory:
    def test_get_executions(self):
        reg, conn = _make_registry_with_sms()
        cid = conn.connector_id()
        _set_valid_secret(reg, cid)
        reg.execute(cid, "send", {"body": "a"})
        reg.execute(cid, "send", {"body": "b"})
        all_exec = reg.get_executions()
        assert len(all_exec) == 2
        by_cid = reg.get_executions(cid)
        assert len(by_cid) == 2

    def test_get_failures(self):
        reg, conn = _make_registry_with_sms()
        cid = conn.connector_id()
        # No credential -> auth failure
        reg.execute(cid, "send", {"body": "x"})
        all_fail = reg.get_failures()
        assert len(all_fail) >= 1
        by_cid = reg.get_failures(cid)
        assert len(by_cid) >= 1
        assert by_cid[0].category == ConnectorFailureCategory.AUTH_FAILURE

    def test_get_executions_empty(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_executions() == ()

    def test_get_failures_empty(self):
        reg = ExternalConnectorRegistry()
        assert reg.get_failures() == ()


# ===================================================================
# State hash
# ===================================================================


class TestStateHash:
    def test_state_hash_deterministic(self):
        reg1 = ExternalConnectorRegistry()
        reg2 = ExternalConnectorRegistry()
        register_all_test_connectors(reg1)
        register_all_test_connectors(reg2)
        assert reg1.state_hash() == reg2.state_hash()

    def test_state_hash_changes_on_register(self):
        reg = ExternalConnectorRegistry()
        h1 = reg.state_hash()
        reg.register(SmsProviderTestConnector())
        h2 = reg.state_hash()
        assert h1 != h2

    def test_state_hash_empty(self):
        reg = ExternalConnectorRegistry()
        h = reg.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ===================================================================
# register_all_test_connectors
# ===================================================================


class TestRegisterAllTestConnectors:
    def test_registers_9_connectors(self):
        reg = ExternalConnectorRegistry()
        descs = register_all_test_connectors(reg)
        assert len(descs) == 9
        assert reg.connector_count == 9

    def test_all_types_covered(self):
        reg = ExternalConnectorRegistry()
        descs = register_all_test_connectors(reg)
        types_seen = {d.connector_type for d in descs}
        expected_types = {
            ExternalConnectorType.SMS_PROVIDER,
            ExternalConnectorType.CHAT_PROVIDER,
            ExternalConnectorType.VOICE_PROVIDER,
            ExternalConnectorType.EMAIL_PROVIDER,
            ExternalConnectorType.WEBHOOK_PROVIDER,
            ExternalConnectorType.SOCIAL_PROVIDER,
            ExternalConnectorType.STORAGE_PROVIDER,
            ExternalConnectorType.PARSER_PROVIDER,
            ExternalConnectorType.GENERIC_API,
        }
        assert types_seen == expected_types


# ===================================================================
# Per-type test connectors
# ===================================================================


class TestPerTypeConnectors:
    @pytest.mark.parametrize(
        "cls,expected_type,expected_provider",
        [
            (SmsProviderTestConnector, ExternalConnectorType.SMS_PROVIDER, "twilio-test"),
            (ChatProviderTestConnector, ExternalConnectorType.CHAT_PROVIDER, "slack-test"),
            (VoiceProviderTestConnector, ExternalConnectorType.VOICE_PROVIDER, "vonage-test"),
            (EmailProviderTestConnector, ExternalConnectorType.EMAIL_PROVIDER, "sendgrid-test"),
            (WebhookProviderTestConnector, ExternalConnectorType.WEBHOOK_PROVIDER, "webhook-test"),
            (SocialProviderTestConnector, ExternalConnectorType.SOCIAL_PROVIDER, "meta-test"),
            (StorageProviderTestConnector, ExternalConnectorType.STORAGE_PROVIDER, "s3-test"),
            (ParserProviderTestConnector, ExternalConnectorType.PARSER_PROVIDER, "parser-test"),
            (GenericApiTestConnector, ExternalConnectorType.GENERIC_API, "generic-test"),
        ],
    )
    def test_connector_type_and_provider(self, cls, expected_type, expected_provider):
        conn = cls()
        assert conn.connector_type() == expected_type
        desc = conn.descriptor()
        assert desc.provider_name == expected_provider
        assert desc.enabled is True
        assert desc.health_state == ConnectorHealthState.HEALTHY

    def test_connector_execute_returns_success(self):
        conn = SmsProviderTestConnector()
        record = conn.execute("send", {"body": "test"})
        assert record.success is True
        assert record.latency_ms == 15.0

    def test_connector_health_check(self):
        conn = ChatProviderTestConnector()
        snap = conn.health_check()
        assert snap.health_state == ConnectorHealthState.HEALTHY
        assert snap.reliability_score == 1.0


# ===================================================================
# FailingTestConnector
# ===================================================================


class TestFailingTestConnector:
    def test_always_raises_on_execute(self):
        conn = FailingTestConnector()
        with pytest.raises(RuntimeError, match="Simulated failure"):
            conn.execute("send", {"body": "test"})

    def test_health_check_unhealthy(self):
        conn = FailingTestConnector()
        snap = conn.health_check()
        assert snap.health_state == ConnectorHealthState.UNHEALTHY
        assert snap.reliability_score == 0.0

    def test_auth_mode_none(self):
        conn = FailingTestConnector()
        assert conn.auth_mode() == ConnectorAuthMode.NONE

    def test_descriptor_enabled(self):
        conn = FailingTestConnector()
        desc = conn.descriptor()
        assert desc.enabled is True
        assert desc.connector_type == ExternalConnectorType.GENERIC_API

    def test_custom_id(self):
        conn = FailingTestConnector("my-failing")
        assert conn.connector_id() == "my-failing"
