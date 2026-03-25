"""Purpose: external connector runtime engine.
Governance scope: registering live providers/connectors, binding to channel
    adapters and artifact parsers, enforcing scoped credentials and rate limits,
    tracking health, exposing capability manifests, supporting fallback chains,
    and emitting execution records and failures.
Dependencies: external_connector contracts, channel_adapter contracts,
    artifact_parser contracts, core invariants, event spine.
Invariants:
  - No duplicate connector IDs.
  - Only HEALTHY/DEGRADED connectors participate in routing.
  - Every execution emits an execution record.
  - Every failure emits a failure record.
  - Credential scopes are validated before execution.
  - Rate limits are checked before execution.
  - Fallback chains are evaluated deterministically.
  - All returns are immutable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from ..contracts.external_connector import (
    ChannelConsentRecord,
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
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Abstract connector base
# ---------------------------------------------------------------------------


class ExternalConnector(ABC):
    """Abstract base for all external connectors."""

    @abstractmethod
    def connector_id(self) -> str: ...

    @abstractmethod
    def connector_type(self) -> ExternalConnectorType: ...

    @abstractmethod
    def descriptor(self) -> ExternalConnectorDescriptor: ...

    @abstractmethod
    def execute(
        self, operation: str, payload: Mapping[str, Any],
    ) -> ConnectorExecutionRecord: ...

    @abstractmethod
    def health_check(self) -> ConnectorHealthSnapshot: ...

    @abstractmethod
    def auth_mode(self) -> ConnectorAuthMode: ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ExternalConnectorRegistry:
    """Central registry for external connectors with rate limiting,
    credential scoping, fallback chains, and health tracking."""

    def __init__(self) -> None:
        self._connectors: dict[str, ExternalConnector] = {}
        self._descriptors: dict[str, ExternalConnectorDescriptor] = {}
        self._bindings: dict[str, ConnectorCapabilityBinding] = {}
        self._rate_limits: dict[str, ConnectorRateLimitPolicy] = {}
        self._quotas: dict[str, ConnectorQuotaState] = {}
        self._secret_scopes: dict[str, SecretScope] = {}
        self._retention_policies: dict[str, ConnectorRetentionPolicy] = {}
        self._fallback_chains: dict[str, FallbackChain] = {}
        self._consent_records: dict[str, ChannelConsentRecord] = {}
        self._executions: list[ConnectorExecutionRecord] = []
        self._failures: list[ConnectorFailureRecord] = []
        self._health_snapshots: dict[str, ConnectorHealthSnapshot] = {}
        # Counters for rate tracking
        self._execution_counts: dict[str, int] = {}
        self._failure_counts: dict[str, int] = {}
        self._consecutive_failures: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, connector: ExternalConnector) -> ExternalConnectorDescriptor:
        """Register a connector. Rejects duplicates and non-ExternalConnector."""
        if not isinstance(connector, ExternalConnector):
            raise RuntimeCoreInvariantError("connector must be an ExternalConnector")
        cid = connector.connector_id()
        if cid in self._connectors:
            raise RuntimeCoreInvariantError(
                f"connector '{cid}' already registered"
            )
        desc = connector.descriptor()
        self._connectors[cid] = connector
        self._descriptors[cid] = desc
        self._execution_counts[cid] = 0
        self._failure_counts[cid] = 0
        self._consecutive_failures[cid] = 0
        return desc

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_connector(self, connector_id: str) -> ExternalConnector:
        if connector_id not in self._connectors:
            raise RuntimeCoreInvariantError(f"connector '{connector_id}' not found")
        return self._connectors[connector_id]

    def get_descriptor(self, connector_id: str) -> ExternalConnectorDescriptor:
        if connector_id not in self._descriptors:
            raise RuntimeCoreInvariantError(f"connector '{connector_id}' not found")
        return self._descriptors[connector_id]

    def list_connectors(
        self, *,
        connector_type: ExternalConnectorType | None = None,
        health_state: ConnectorHealthState | None = None,
    ) -> tuple[ExternalConnectorDescriptor, ...]:
        result = list(self._descriptors.values())
        if connector_type is not None:
            result = [d for d in result if d.connector_type == connector_type]
        if health_state is not None:
            result = [d for d in result if d.health_state == health_state]
        return tuple(sorted(result, key=lambda d: d.connector_id))

    def list_available(self) -> tuple[ExternalConnectorDescriptor, ...]:
        return tuple(
            d for d in sorted(self._descriptors.values(), key=lambda d: d.connector_id)
            if d.enabled and d.health_state in (
                ConnectorHealthState.HEALTHY,
                ConnectorHealthState.DEGRADED,
            )
        )

    def list_by_type(
        self, connector_type: ExternalConnectorType,
    ) -> tuple[ExternalConnector, ...]:
        return tuple(
            self._connectors[d.connector_id]
            for d in sorted(self._descriptors.values(), key=lambda d: d.connector_id)
            if d.connector_type == connector_type
            and d.enabled
            and d.health_state in (
                ConnectorHealthState.HEALTHY,
                ConnectorHealthState.DEGRADED,
            )
        )

    # ------------------------------------------------------------------
    # Capability bindings
    # ------------------------------------------------------------------

    def add_binding(self, binding: ConnectorCapabilityBinding) -> None:
        if not isinstance(binding, ConnectorCapabilityBinding):
            raise RuntimeCoreInvariantError("binding must be a ConnectorCapabilityBinding")
        if binding.connector_id not in self._connectors:
            raise RuntimeCoreInvariantError(
                f"connector '{binding.connector_id}' not found"
            )
        self._bindings[binding.binding_id] = binding

    def get_bindings_for_connector(
        self, connector_id: str,
    ) -> tuple[ConnectorCapabilityBinding, ...]:
        return tuple(
            b for b in sorted(self._bindings.values(), key=lambda b: b.binding_id)
            if b.connector_id == connector_id
        )

    def get_bindings_for_adapter(
        self, adapter_id: str,
    ) -> tuple[ConnectorCapabilityBinding, ...]:
        return tuple(
            b for b in sorted(self._bindings.values(), key=lambda b: b.binding_id)
            if b.bound_adapter_id == adapter_id and b.enabled
        )

    def get_bindings_for_parser(
        self, parser_id: str,
    ) -> tuple[ConnectorCapabilityBinding, ...]:
        return tuple(
            b for b in sorted(self._bindings.values(), key=lambda b: b.binding_id)
            if b.bound_parser_id == parser_id and b.enabled
        )

    # ------------------------------------------------------------------
    # Rate limits & quotas
    # ------------------------------------------------------------------

    def set_rate_limit(self, policy: ConnectorRateLimitPolicy) -> None:
        if not isinstance(policy, ConnectorRateLimitPolicy):
            raise RuntimeCoreInvariantError("policy must be a ConnectorRateLimitPolicy")
        if policy.connector_id not in self._connectors:
            raise RuntimeCoreInvariantError(
                f"connector '{policy.connector_id}' not found"
            )
        self._rate_limits[policy.connector_id] = policy

    def get_rate_limit(self, connector_id: str) -> ConnectorRateLimitPolicy | None:
        return self._rate_limits.get(connector_id)

    def update_quota(self, quota: ConnectorQuotaState) -> None:
        if not isinstance(quota, ConnectorQuotaState):
            raise RuntimeCoreInvariantError("quota must be a ConnectorQuotaState")
        self._quotas[quota.connector_id] = quota

    def get_quota(self, connector_id: str) -> ConnectorQuotaState | None:
        return self._quotas.get(connector_id)

    def check_rate_limit(self, connector_id: str) -> bool:
        """Returns True if execution is allowed under rate limits.

        A max_burst_size of 0 means no burst is allowed (blocks all).
        """
        policy = self._rate_limits.get(connector_id)
        if policy is None:
            return True
        # Burst check: 0 means block all, otherwise check against count
        count = self._execution_counts.get(connector_id, 0)
        if count >= policy.max_burst_size:
            return False
        return True

    def check_quota(self, connector_id: str) -> bool:
        """Returns True if quota allows execution."""
        quota = self._quotas.get(connector_id)
        if quota is None:
            return True
        return quota.quota_remaining > 0

    # ------------------------------------------------------------------
    # Secret scopes
    # ------------------------------------------------------------------

    def set_secret_scope(self, scope: SecretScope) -> None:
        if not isinstance(scope, SecretScope):
            raise RuntimeCoreInvariantError("scope must be a SecretScope")
        if scope.connector_id not in self._connectors:
            raise RuntimeCoreInvariantError(
                f"connector '{scope.connector_id}' not found"
            )
        self._secret_scopes[scope.connector_id] = scope

    def get_secret_scope(self, connector_id: str) -> SecretScope | None:
        return self._secret_scopes.get(connector_id)

    def validate_credential(self, connector_id: str) -> bool:
        """Validate that the connector has a valid, non-expired credential."""
        scope = self._secret_scopes.get(connector_id)
        if scope is None:
            # No credential required (auth_mode == NONE)
            connector = self._connectors.get(connector_id)
            if connector and connector.auth_mode() == ConnectorAuthMode.NONE:
                return True
            return False
        if scope.rotation_state in (
            SecretRotationState.EXPIRED,
            SecretRotationState.REVOKED,
        ):
            return False
        return True

    # ------------------------------------------------------------------
    # Retention policies
    # ------------------------------------------------------------------

    def set_retention_policy(self, policy: ConnectorRetentionPolicy) -> None:
        if not isinstance(policy, ConnectorRetentionPolicy):
            raise RuntimeCoreInvariantError(
                "policy must be a ConnectorRetentionPolicy"
            )
        self._retention_policies[policy.connector_id] = policy

    def get_retention_policy(
        self, connector_id: str,
    ) -> ConnectorRetentionPolicy | None:
        return self._retention_policies.get(connector_id)

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    def record_consent(self, record: ChannelConsentRecord) -> None:
        if not isinstance(record, ChannelConsentRecord):
            raise RuntimeCoreInvariantError(
                "record must be a ChannelConsentRecord"
            )
        self._consent_records[record.consent_id] = record

    def check_consent(
        self, identity_id: str, channel_type: str, connector_id: str,
    ) -> ConsentState | None:
        """Check consent state for identity + channel + connector."""
        for rec in self._consent_records.values():
            if (
                rec.identity_id == identity_id
                and rec.channel_type == channel_type
                and rec.connector_id == connector_id
            ):
                return rec.consent_state
        return None

    # ------------------------------------------------------------------
    # Fallback chains
    # ------------------------------------------------------------------

    def add_fallback_chain(self, chain: FallbackChain) -> None:
        if not isinstance(chain, FallbackChain):
            raise RuntimeCoreInvariantError("chain must be a FallbackChain")
        self._fallback_chains[chain.chain_id] = chain

    def get_fallback_chain(self, chain_id: str) -> FallbackChain | None:
        return self._fallback_chains.get(chain_id)

    def resolve_fallback(
        self, chain_id: str,
    ) -> ExternalConnector | None:
        """Walk a fallback chain and return the first available connector."""
        chain = self._fallback_chains.get(chain_id)
        if chain is None:
            return None

        entries = sorted(chain.entries, key=lambda e: e.priority)

        for entry in entries:
            if not entry.enabled:
                continue
            cid = entry.connector_id
            if cid not in self._connectors:
                continue
            desc = self._descriptors.get(cid)
            if desc is None or not desc.enabled:
                continue
            # Prefer health snapshot if available, else use descriptor
            snap = self._health_snapshots.get(cid)
            effective_health = (
                snap.health_state if snap else desc.health_state
            )
            if effective_health not in (
                ConnectorHealthState.HEALTHY,
                ConnectorHealthState.DEGRADED,
            ):
                continue
            # Check reliability threshold
            snap = self._health_snapshots.get(cid)
            if snap and entry.min_reliability > 0:
                if snap.reliability_score < entry.min_reliability:
                    continue
            # Check latency threshold
            if snap and entry.max_latency_ms > 0:
                if snap.avg_latency_ms > entry.max_latency_ms:
                    continue
            # Check credential validity
            if not self.validate_credential(cid):
                continue
            # Check rate limit
            if not self.check_rate_limit(cid):
                continue
            # Check quota
            if not self.check_quota(cid):
                continue
            return self._connectors[cid]

        return None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self, connector_id: str, operation: str, payload: Mapping[str, Any],
    ) -> ConnectorExecutionRecord:
        """Execute an operation on a connector with full governance checks."""
        connector = self.get_connector(connector_id)
        desc = self._descriptors[connector_id]

        # Pre-flight checks
        if not desc.enabled:
            return self._record_failure(
                connector_id, operation,
                ConnectorFailureCategory.POLICY_BLOCKED,
                "connector is disabled",
            )

        if not self.validate_credential(connector_id):
            return self._record_failure(
                connector_id, operation,
                ConnectorFailureCategory.AUTH_FAILURE,
                "credential invalid or expired",
            )

        if not self.check_rate_limit(connector_id):
            return self._record_failure(
                connector_id, operation,
                ConnectorFailureCategory.RATE_LIMITED,
                "rate limit exceeded",
            )

        if not self.check_quota(connector_id):
            return self._record_failure(
                connector_id, operation,
                ConnectorFailureCategory.QUOTA_EXHAUSTED,
                "quota exhausted",
            )

        # Execute via the connector
        try:
            record = connector.execute(operation, payload)
            self._executions.append(record)
            self._execution_counts[connector_id] = (
                self._execution_counts.get(connector_id, 0) + 1
            )
            if record.success:
                self._consecutive_failures[connector_id] = 0
            else:
                self._consecutive_failures[connector_id] = (
                    self._consecutive_failures.get(connector_id, 0) + 1
                )
                self._failure_counts[connector_id] = (
                    self._failure_counts.get(connector_id, 0) + 1
                )
            return record
        except Exception as exc:
            return self._record_failure(
                connector_id, operation,
                ConnectorFailureCategory.PROVIDER_ERROR,
                str(exc),
            )

    def execute_with_fallback(
        self, chain_id: str, operation: str, payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Execute with fallback chain: try each connector in order."""
        chain = self._fallback_chains.get(chain_id)
        if chain is None:
            raise RuntimeCoreInvariantError(f"fallback chain '{chain_id}' not found")

        entries = sorted(chain.entries, key=lambda e: e.priority)
        attempts: list[ConnectorExecutionRecord] = []

        for entry in entries:
            if not entry.enabled:
                continue
            cid = entry.connector_id
            if cid not in self._connectors:
                continue

            record = self.execute(cid, operation, payload)
            attempts.append(record)

            if record.success:
                return {
                    "record": record,
                    "connector_id": cid,
                    "attempts": tuple(attempts),
                    "fallback_used": len(attempts) > 1,
                }

        return {
            "record": None,
            "connector_id": None,
            "attempts": tuple(attempts),
            "fallback_used": True,
        }

    def _record_failure(
        self, connector_id: str, operation: str,
        category: ConnectorFailureCategory, message: str,
    ) -> ConnectorExecutionRecord:
        """Record a failure and return a failed execution record."""
        now = _now_iso()
        self._consecutive_failures[connector_id] = (
            self._consecutive_failures.get(connector_id, 0) + 1
        )
        self._failure_counts[connector_id] = (
            self._failure_counts.get(connector_id, 0) + 1
        )

        failure = ConnectorFailureRecord(
            failure_id=stable_identifier("fail", {
                "cid": connector_id, "op": operation, "ts": now,
            }),
            connector_id=connector_id,
            category=category,
            operation=operation,
            error_message=message,
            is_retriable=category not in (
                ConnectorFailureCategory.POLICY_BLOCKED,
                ConnectorFailureCategory.AUTH_FAILURE,
            ),
            occurred_at=now,
        )
        self._failures.append(failure)

        record = ConnectorExecutionRecord(
            execution_id=stable_identifier("exec", {
                "cid": connector_id, "op": operation, "ts": now,
            }),
            connector_id=connector_id,
            operation=operation,
            success=False,
            error_message=message,
            executed_at=now,
        )
        self._executions.append(record)
        return record

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self, connector_id: str) -> ConnectorHealthSnapshot:
        connector = self.get_connector(connector_id)
        snapshot = connector.health_check()
        self._health_snapshots[connector_id] = snapshot
        return snapshot

    def health_check_all(self) -> tuple[ConnectorHealthSnapshot, ...]:
        snapshots = []
        for cid in sorted(self._connectors):
            snap = self._connectors[cid].health_check()
            self._health_snapshots[cid] = snap
            snapshots.append(snap)
        return tuple(snapshots)

    def get_health(self, connector_id: str) -> ConnectorHealthSnapshot | None:
        return self._health_snapshots.get(connector_id)

    # ------------------------------------------------------------------
    # Execution / failure history
    # ------------------------------------------------------------------

    def get_executions(
        self, connector_id: str | None = None,
    ) -> tuple[ConnectorExecutionRecord, ...]:
        if connector_id is None:
            return tuple(self._executions)
        return tuple(e for e in self._executions if e.connector_id == connector_id)

    def get_failures(
        self, connector_id: str | None = None,
    ) -> tuple[ConnectorFailureRecord, ...]:
        if connector_id is None:
            return tuple(self._failures)
        return tuple(f for f in self._failures if f.connector_id == connector_id)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def connector_count(self) -> int:
        return len(self._connectors)

    def state_hash(self) -> str:
        h = sha256()
        for cid in sorted(self._connectors):
            d = self._descriptors[cid]
            h.update(
                f"conn:{cid}:{d.connector_type.value}:{d.health_state.value}"
                f":{d.enabled}:{d.version}".encode()
            )
            # Include execution/failure counts
            h.update(
                f":exec:{self._execution_counts.get(cid, 0)}"
                f":fail:{self._failure_counts.get(cid, 0)}".encode()
            )
        for bid in sorted(self._bindings):
            b = self._bindings[bid]
            h.update(f"bind:{bid}:{b.connector_id}:{b.enabled}".encode())
        for chid in sorted(self._fallback_chains):
            ch = self._fallback_chains[chid]
            h.update(f"chain:{chid}:{ch.strategy.value}:{len(ch.entries)}".encode())
        return h.hexdigest()


# ---------------------------------------------------------------------------
# Test connectors — one per type
# ---------------------------------------------------------------------------


class _BaseTestConnector(ExternalConnector):
    """Shared logic for deterministic test connectors."""

    _TYPE: ExternalConnectorType
    _NAME: str
    _AUTH: ConnectorAuthMode = ConnectorAuthMode.API_KEY
    _PROVIDER: str = "test-provider"

    def __init__(self, connector_id: str | None = None) -> None:
        self._id = connector_id or f"test-{self._TYPE.value}"
        self._now = _now_iso()
        self._exec_count = 0
        self._fail_count = 0

    def connector_id(self) -> str:
        return self._id

    def connector_type(self) -> ExternalConnectorType:
        return self._TYPE

    def auth_mode(self) -> ConnectorAuthMode:
        return self._AUTH

    def descriptor(self) -> ExternalConnectorDescriptor:
        return ExternalConnectorDescriptor(
            connector_id=self._id,
            name=self._NAME,
            connector_type=self._TYPE,
            auth_mode=self._AUTH,
            health_state=ConnectorHealthState.HEALTHY,
            provider_name=self._PROVIDER,
            version="1.0.0",
            enabled=True,
            tags=("test",),
            created_at=self._now,
        )

    def execute(
        self, operation: str, payload: Mapping[str, Any],
    ) -> ConnectorExecutionRecord:
        now = _now_iso()
        self._exec_count += 1
        return ConnectorExecutionRecord(
            execution_id=stable_identifier("exec", {
                "cid": self._id, "op": operation, "ts": now,
                "n": self._exec_count,
            }),
            connector_id=self._id,
            connector_type=self._TYPE,
            operation=operation,
            success=True,
            latency_ms=15.0,
            request_bytes=len(str(payload)),
            response_bytes=64,
            status_code=200,
            correlation_id=str(payload.get("correlation_id", "")),
            executed_at=now,
        )

    def health_check(self) -> ConnectorHealthSnapshot:
        now = _now_iso()
        total = self._exec_count
        reliability = 1.0 if total == 0 else max(0.0, 1.0 - self._fail_count / max(total, 1))
        return ConnectorHealthSnapshot(
            snapshot_id=stable_identifier("health", {"cid": self._id, "ts": now}),
            connector_id=self._id,
            health_state=ConnectorHealthState.HEALTHY,
            reliability_score=min(reliability, 1.0),
            total_executions=total,
            failed_executions=self._fail_count,
            avg_latency_ms=15.0,
            last_success_at=now,
            last_failure_at=now,
            reported_at=now,
        )


class SmsProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.SMS_PROVIDER
    _NAME = "SMS Provider Test Connector"
    _PROVIDER = "twilio-test"


class ChatProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.CHAT_PROVIDER
    _NAME = "Chat Provider Test Connector"
    _PROVIDER = "slack-test"


class VoiceProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.VOICE_PROVIDER
    _NAME = "Voice Provider Test Connector"
    _PROVIDER = "vonage-test"


class EmailProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.EMAIL_PROVIDER
    _NAME = "Email Provider Test Connector"
    _PROVIDER = "sendgrid-test"


class WebhookProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.WEBHOOK_PROVIDER
    _NAME = "Webhook Provider Test Connector"
    _PROVIDER = "webhook-test"
    _AUTH = ConnectorAuthMode.HMAC_SIGNATURE


class SocialProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.SOCIAL_PROVIDER
    _NAME = "Social Provider Test Connector"
    _PROVIDER = "meta-test"
    _AUTH = ConnectorAuthMode.OAUTH2


class StorageProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.STORAGE_PROVIDER
    _NAME = "Storage Provider Test Connector"
    _PROVIDER = "s3-test"
    _AUTH = ConnectorAuthMode.BEARER_TOKEN


class ParserProviderTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.PARSER_PROVIDER
    _NAME = "Parser Provider Test Connector"
    _PROVIDER = "parser-test"
    _AUTH = ConnectorAuthMode.API_KEY


class GenericApiTestConnector(_BaseTestConnector):
    _TYPE = ExternalConnectorType.GENERIC_API
    _NAME = "Generic API Test Connector"
    _PROVIDER = "generic-test"
    _AUTH = ConnectorAuthMode.BEARER_TOKEN


class FailingTestConnector(ExternalConnector):
    """A test connector that always fails — used for fallback testing."""

    def __init__(self, connector_id: str = "test-failing") -> None:
        self._id = connector_id
        self._now = _now_iso()

    def connector_id(self) -> str:
        return self._id

    def connector_type(self) -> ExternalConnectorType:
        return ExternalConnectorType.GENERIC_API

    def auth_mode(self) -> ConnectorAuthMode:
        return ConnectorAuthMode.NONE

    def descriptor(self) -> ExternalConnectorDescriptor:
        return ExternalConnectorDescriptor(
            connector_id=self._id,
            name="Failing Test Connector",
            connector_type=ExternalConnectorType.GENERIC_API,
            auth_mode=ConnectorAuthMode.NONE,
            health_state=ConnectorHealthState.HEALTHY,
            provider_name="fail-test",
            version="1.0.0",
            enabled=True,
            created_at=self._now,
        )

    def execute(
        self, operation: str, payload: Mapping[str, Any],
    ) -> ConnectorExecutionRecord:
        raise RuntimeError(f"Simulated failure for {operation}")

    def health_check(self) -> ConnectorHealthSnapshot:
        now = _now_iso()
        return ConnectorHealthSnapshot(
            snapshot_id=stable_identifier("health", {"cid": self._id, "ts": now}),
            connector_id=self._id,
            health_state=ConnectorHealthState.UNHEALTHY,
            reliability_score=0.0,
            last_success_at=now,
            last_failure_at=now,
            reported_at=now,
        )


# ---------------------------------------------------------------------------
# Convenience: register all test connectors
# ---------------------------------------------------------------------------


def register_all_test_connectors(
    registry: ExternalConnectorRegistry,
) -> tuple[ExternalConnectorDescriptor, ...]:
    """Register one test connector per type. Returns descriptors."""
    connectors = [
        SmsProviderTestConnector(),
        ChatProviderTestConnector(),
        VoiceProviderTestConnector(),
        EmailProviderTestConnector(),
        WebhookProviderTestConnector(),
        SocialProviderTestConnector(),
        StorageProviderTestConnector(),
        ParserProviderTestConnector(),
        GenericApiTestConnector(),
    ]
    descs = []
    for conn in connectors:
        descs.append(registry.register(conn))
    return tuple(descs)
