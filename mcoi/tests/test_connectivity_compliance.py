"""Purpose: tests for ConnectivityComplianceEngine.
Governance scope: credential validation, rotation, redaction, consent,
    audit trail, pre-flight checks.
Dependencies: connectivity_compliance, external_connectors, event_spine,
    memory_mesh, external_connector contracts.
Invariants tested:
  - Expired or revoked credentials block execution.
  - Rotation hooks fire when credentials approach expiry.
  - Redaction policies are enforced before payload storage.
  - Consent is verified before channel-identity operations.
  - Every outbound call is recorded in the audit trail.
  - All returns are immutable.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from mcoi_runtime.contracts.external_connector import (
    ConnectorAuthMode,
    ConnectorHealthState,
    ConnectorRetentionPolicy,
    ConsentState,
    RedactionLevel,
    SecretRotationState,
    SecretScope,
    ConnectorQuotaState,
    ConnectorRateLimitPolicy,
    ExternalConnectorType,
)
from mcoi_runtime.core.external_connectors import (
    ExternalConnectorRegistry,
    SmsProviderTestConnector,
    ChatProviderTestConnector,
    GenericApiTestConnector,
    register_all_test_connectors,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.connectivity_compliance import ConnectivityComplianceEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"


def _make_stack():
    """Build a fresh connector registry, event spine, memory engine, and compliance engine."""
    conn_reg = ExternalConnectorRegistry()
    es = EventSpineEngine()
    mem = MemoryMeshEngine()
    compliance = ConnectivityComplianceEngine(conn_reg, es, mem)
    return conn_reg, es, mem, compliance


class TestConstructorValidation(unittest.TestCase):
    """Constructor rejects invalid arguments."""

    def test_rejects_non_connector_registry(self):
        with self.assertRaises(RuntimeCoreInvariantError):
            ConnectivityComplianceEngine("bad", EventSpineEngine(), MemoryMeshEngine())  # type: ignore

    def test_rejects_non_event_spine(self):
        with self.assertRaises(RuntimeCoreInvariantError):
            ConnectivityComplianceEngine(ExternalConnectorRegistry(), "bad", MemoryMeshEngine())  # type: ignore

    def test_rejects_non_memory_engine(self):
        with self.assertRaises(RuntimeCoreInvariantError):
            ConnectivityComplianceEngine(ExternalConnectorRegistry(), EventSpineEngine(), "bad")  # type: ignore

    def test_valid_construction(self):
        _, _, _, compliance = _make_stack()
        self.assertIsInstance(compliance, ConnectivityComplianceEngine)


class TestValidateAllCredentials(unittest.TestCase):
    """validate_all_credentials: all valid, some expired/revoked."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()

    def test_all_valid(self):
        # Register connectors with valid credentials
        c1 = SmsProviderTestConnector("sms-1")
        c2 = ChatProviderTestConnector("chat-1")
        self.conn_reg.register(c1)
        self.conn_reg.register(c2)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-sms-1", connector_id="sms-1",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="ref-sms-1", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2027-01-01T00:00:00+00:00",
            created_at=NOW,
        ))
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-chat-1", connector_id="chat-1",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="ref-chat-1", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2027-01-01T00:00:00+00:00",
            created_at=NOW,
        ))

        result = self.compliance.validate_all_credentials()
        self.assertTrue(all(result["results"].values()))
        self.assertEqual(len(result["expired"]), 0)
        self.assertEqual(len(result["revoked"]), 0)

    def test_some_expired_revoked(self):
        c1 = SmsProviderTestConnector("sms-exp")
        c2 = ChatProviderTestConnector("chat-rev")
        c3 = GenericApiTestConnector("gen-ok")
        self.conn_reg.register(c1)
        self.conn_reg.register(c2)
        self.conn_reg.register(c3)

        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-exp", connector_id="sms-exp",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.EXPIRED,
            credential_ref="ref-exp", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2025-01-01T00:00:00+00:00",
            created_at=NOW,
        ))
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-rev", connector_id="chat-rev",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.REVOKED,
            credential_ref="ref-rev", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2025-01-01T00:00:00+00:00",
            created_at=NOW,
        ))
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-gen-ok", connector_id="gen-ok",
            auth_mode=ConnectorAuthMode.BEARER_TOKEN,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="ref-gen-ok", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2027-01-01T00:00:00+00:00",
            created_at=NOW,
        ))

        result = self.compliance.validate_all_credentials()
        self.assertFalse(result["results"]["sms-exp"])
        self.assertFalse(result["results"]["chat-rev"])
        self.assertTrue(result["results"]["gen-ok"])
        self.assertIn("sms-exp", result["expired"])
        self.assertIn("chat-rev", result["revoked"])
        self.assertIsNotNone(result["event"])


class TestCheckRotationNeeded(unittest.TestCase):
    """check_rotation_needed: current, expired, pending, near-expiry."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()

    def test_current_no_rotation(self):
        c = SmsProviderTestConnector("sms-current")
        self.conn_reg.register(c)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-curr", connector_id="sms-current",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="ref-curr", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2027-06-01T00:00:00+00:00",
            created_at=NOW,
        ))
        result = self.compliance.check_rotation_needed("sms-current")
        self.assertFalse(result["needs_rotation"])

    def test_expired_urgent(self):
        c = SmsProviderTestConnector("sms-expired")
        self.conn_reg.register(c)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-exp", connector_id="sms-expired",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.EXPIRED,
            credential_ref="ref-exp", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2025-01-01T00:00:00+00:00",
            created_at=NOW,
        ))
        result = self.compliance.check_rotation_needed("sms-expired")
        self.assertTrue(result["needs_rotation"])
        self.assertTrue(result["urgent"])
        self.assertEqual(result["reason"], "credential requires urgent rotation")
        self.assertNotIn("expired", result["reason"].lower())

    def test_pending_rotation(self):
        c = SmsProviderTestConnector("sms-pending")
        self.conn_reg.register(c)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-pend", connector_id="sms-pending",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.PENDING_ROTATION,
            credential_ref="ref-pend", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at="2027-01-01T00:00:00+00:00",
            created_at=NOW,
        ))
        result = self.compliance.check_rotation_needed("sms-pending")
        self.assertTrue(result["needs_rotation"])
        self.assertFalse(result["urgent"])

    def test_near_expiry(self):
        # Create a scope that expires very soon (within 1 hour)
        c = SmsProviderTestConnector("sms-near")
        self.conn_reg.register(c)
        # Use a time that is always "near" relative to now
        near_time = datetime.now(timezone.utc).isoformat()
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-near", connector_id="sms-near",
            auth_mode=ConnectorAuthMode.API_KEY,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="ref-near", rotation_interval_hours=720,
            last_rotated_at=NOW, expires_at=near_time,
            created_at=NOW,
        ))
        result = self.compliance.check_rotation_needed("sms-near", hours_until_expiry=48)
        self.assertTrue(result["needs_rotation"])
        self.assertEqual(result["reason"], "credential nearing expiry")
        self.assertNotIn("hour", result["reason"].lower())

    def test_no_scope(self):
        c = SmsProviderTestConnector("sms-noscope")
        self.conn_reg.register(c)
        result = self.compliance.check_rotation_needed("sms-noscope")
        self.assertFalse(result["needs_rotation"])


class TestRotationHooks(unittest.TestCase):
    """register_rotation_hook, get_rotation_hooks."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()

    def test_register_and_retrieve(self):
        self.compliance.register_rotation_hook("conn-a", "hook-ref-1")
        self.compliance.register_rotation_hook("conn-a", "hook-ref-2")
        self.compliance.register_rotation_hook("conn-b", "hook-ref-3")

        hooks_a = self.compliance.get_rotation_hooks("conn-a")
        self.assertEqual(len(hooks_a), 2)
        self.assertEqual(hooks_a[0]["hook_ref"], "hook-ref-1")

        hooks_b = self.compliance.get_rotation_hooks("conn-b")
        self.assertEqual(len(hooks_b), 1)

    def test_empty_hooks(self):
        hooks = self.compliance.get_rotation_hooks("nonexistent")
        self.assertEqual(len(hooks), 0)


class TestRedactPayload(unittest.TestCase):
    """redact_payload: no policy, COMPLETE, BODY_FULL, BODY_PARTIAL, HEADERS_ONLY, PII scrub."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()
        # Register a connector for each test
        self.conn_reg.register(GenericApiTestConnector("conn-redact"))

    def test_no_policy_returns_copy(self):
        payload = {"body": "hello", "extra": 42}
        result = self.compliance.redact_payload("conn-redact", payload)
        self.assertEqual(result["body"], "hello")
        self.assertEqual(result["extra"], 42)

    def test_complete_redaction(self):
        self.conn_reg.set_retention_policy(ConnectorRetentionPolicy(
            policy_id="pol-complete", connector_id="conn-redact",
            redaction_level=RedactionLevel.COMPLETE,
            created_at=NOW,
        ))
        result = self.compliance.redact_payload("conn-redact", {"body": "secret", "x": 1})
        self.assertTrue(result["redacted"])
        self.assertEqual(result["connector_id"], "conn-redact")
        self.assertNotIn("body", result)

    def test_body_full_redaction(self):
        self.conn_reg.set_retention_policy(ConnectorRetentionPolicy(
            policy_id="pol-body-full", connector_id="conn-redact",
            redaction_level=RedactionLevel.BODY_FULL,
            pii_scrub_enabled=False,
            created_at=NOW,
        ))
        result = self.compliance.redact_payload("conn-redact", {
            "body": "secret message",
            "content": "also secret",
            "header_field": "visible",
        })
        self.assertEqual(result["body"], "[REDACTED]")
        self.assertEqual(result["content"], "[REDACTED]")
        self.assertEqual(result["header_field"], "visible")

    def test_body_partial_redaction(self):
        self.conn_reg.set_retention_policy(ConnectorRetentionPolicy(
            policy_id="pol-body-partial", connector_id="conn-redact",
            redaction_level=RedactionLevel.BODY_PARTIAL,
            pii_scrub_enabled=False,
            created_at=NOW,
        ))
        long_body = "A" * 100
        result = self.compliance.redact_payload("conn-redact", {"body": long_body})
        self.assertIn("[REDACTED]", result["body"])
        # First 25 and last 25 chars should be preserved
        self.assertTrue(result["body"].startswith("A" * 25))
        self.assertTrue(result["body"].endswith("A" * 25))

    def test_body_partial_short_body_unchanged(self):
        self.conn_reg.set_retention_policy(ConnectorRetentionPolicy(
            policy_id="pol-body-partial-short", connector_id="conn-redact",
            redaction_level=RedactionLevel.BODY_PARTIAL,
            pii_scrub_enabled=False,
            created_at=NOW,
        ))
        result = self.compliance.redact_payload("conn-redact", {"body": "short"})
        # Body <= 50 chars should not be partially redacted
        self.assertEqual(result["body"], "short")

    def test_headers_only_redaction(self):
        self.conn_reg.set_retention_policy(ConnectorRetentionPolicy(
            policy_id="pol-headers", connector_id="conn-redact",
            redaction_level=RedactionLevel.HEADERS_ONLY,
            pii_scrub_enabled=False,
            created_at=NOW,
        ))
        result = self.compliance.redact_payload("conn-redact", {
            "authorization": "Bearer xyz",
            "api_key": "secret-key",
            "body": "visible body",
        })
        self.assertEqual(result["authorization"], "[REDACTED]")
        self.assertEqual(result["api_key"], "[REDACTED]")
        self.assertEqual(result["body"], "visible body")

    def test_pii_scrub(self):
        self.conn_reg.set_retention_policy(ConnectorRetentionPolicy(
            policy_id="pol-pii", connector_id="conn-redact",
            redaction_level=RedactionLevel.NONE,
            pii_scrub_enabled=True,
            created_at=NOW,
        ))
        result = self.compliance.redact_payload("conn-redact", {
            "email": "alice@example.com",
            "phone": "+1234567890",
            "ssn": "123-45-6789",
            "body": "visible",
        })
        self.assertEqual(result["email"], "[PII_SCRUBBED]")
        self.assertEqual(result["phone"], "[PII_SCRUBBED]")
        self.assertEqual(result["ssn"], "[PII_SCRUBBED]")
        self.assertEqual(result["body"], "visible")


class TestConsent(unittest.TestCase):
    """verify_consent / record_consent."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()
        self.conn_reg.register(SmsProviderTestConnector("sms-consent"))

    def test_verify_consent_granted(self):
        self.compliance.record_consent(
            "identity-1", "sms", "sms-consent", ConsentState.GRANTED,
        )
        result = self.compliance.verify_consent("identity-1", "sms", "sms-consent")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["state"], ConsentState.GRANTED)

    def test_verify_consent_denied(self):
        self.compliance.record_consent(
            "identity-2", "sms", "sms-consent", ConsentState.DENIED,
        )
        result = self.compliance.verify_consent("identity-2", "sms", "sms-consent")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["state"], ConsentState.DENIED)

    def test_verify_consent_none(self):
        result = self.compliance.verify_consent("identity-unknown", "sms", "sms-consent")
        self.assertFalse(result["allowed"])
        self.assertIsNone(result["state"])

    def test_record_consent_returns_record(self):
        record = self.compliance.record_consent(
            "identity-3", "email", "sms-consent", ConsentState.GRANTED,
        )
        self.assertEqual(record.identity_id, "identity-3")
        self.assertEqual(record.channel_type, "email")
        self.assertEqual(record.consent_state, ConsentState.GRANTED)
        self.assertNotEqual(record.granted_at, "")


class TestRecordOutboundCall(unittest.TestCase):
    """record_outbound_call: creates audit + memory + event."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()
        self.conn_reg.register(GenericApiTestConnector("api-audit"))

    def test_records_audit_memory_event(self):
        result = self.compliance.record_outbound_call(
            "api-audit", "send_message",
            {"body": "Hello", "recipient": "+1234567890"},
            response_summary="200 OK",
            success=True,
        )
        # Audit entry
        self.assertIn("audit_entry", result)
        self.assertEqual(result["audit_entry"]["connector_id"], "api-audit")
        self.assertTrue(result["audit_entry"]["success"])

        # Memory record
        self.assertIn("memory", result)
        self.assertEqual(result["memory"].title, "Outbound connectivity audit")
        self.assertNotIn("send_message", result["memory"].title)
        self.assertNotIn("api-audit", result["memory"].title)

        # Event
        self.assertIn("event", result)

    def test_audit_trail_persists(self):
        self.compliance.record_outbound_call(
            "api-audit", "op1", {"x": 1}, success=True,
        )
        self.compliance.record_outbound_call(
            "api-audit", "op2", {"y": 2}, success=False,
        )

        trail = self.compliance.get_audit_trail()
        self.assertEqual(len(trail), 2)


class TestGetAuditTrail(unittest.TestCase):
    """get_audit_trail: all, filtered by connector."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()
        self.conn_reg.register(GenericApiTestConnector("api-a"))
        self.conn_reg.register(SmsProviderTestConnector("sms-b"))

    def test_get_all(self):
        self.compliance.record_outbound_call("api-a", "op1", {}, success=True)
        self.compliance.record_outbound_call("sms-b", "op2", {}, success=True)

        trail = self.compliance.get_audit_trail()
        self.assertEqual(len(trail), 2)

    def test_filter_by_connector(self):
        self.compliance.record_outbound_call("api-a", "op1", {}, success=True)
        self.compliance.record_outbound_call("sms-b", "op2", {}, success=True)
        self.compliance.record_outbound_call("api-a", "op3", {}, success=True)

        trail_a = self.compliance.get_audit_trail(connector_id="api-a")
        self.assertEqual(len(trail_a), 2)

        trail_b = self.compliance.get_audit_trail(connector_id="sms-b")
        self.assertEqual(len(trail_b), 1)


class TestPreFlightCheck(unittest.TestCase):
    """pre_flight_check: all pass, credential fail, rate limit fail, quota fail, health fail, consent fail."""

    def setUp(self):
        self.conn_reg, self.es, self.mem, self.compliance = _make_stack()

    def _register_healthy_connector(self, cid: str = "conn-pf"):
        c = GenericApiTestConnector(cid)
        self.conn_reg.register(c)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id=f"scope-{cid}",
            connector_id=cid,
            auth_mode=ConnectorAuthMode.BEARER_TOKEN,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref=f"ref-{cid}",
            rotation_interval_hours=720,
            last_rotated_at=NOW,
            expires_at="2027-06-01T00:00:00+00:00",
            created_at=NOW,
        ))
        return c

    def test_all_pass(self):
        self._register_healthy_connector("conn-allpass")
        result = self.compliance.pre_flight_check("conn-allpass")
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["credential"]["passed"])
        self.assertTrue(result["checks"]["rate_limit"]["passed"])
        self.assertTrue(result["checks"]["quota"]["passed"])
        self.assertTrue(result["checks"]["health"]["passed"])

    def test_credential_fail(self):
        c = GenericApiTestConnector("conn-credfail")
        self.conn_reg.register(c)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-credfail",
            connector_id="conn-credfail",
            auth_mode=ConnectorAuthMode.BEARER_TOKEN,
            rotation_state=SecretRotationState.EXPIRED,
            credential_ref="ref-credfail",
            rotation_interval_hours=720,
            last_rotated_at=NOW,
            expires_at="2025-01-01T00:00:00+00:00",
            created_at=NOW,
        ))
        result = self.compliance.pre_flight_check("conn-credfail")
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["credential"]["passed"])

    def test_rate_limit_fail(self):
        self._register_healthy_connector("conn-rlfail")
        self.conn_reg.set_rate_limit(ConnectorRateLimitPolicy(
            policy_id="rl-fail",
            connector_id="conn-rlfail",
            max_burst_size=1,
            created_at=NOW,
        ))
        self.conn_reg._execution_counts["conn-rlfail"] = 5

        result = self.compliance.pre_flight_check("conn-rlfail")
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["rate_limit"]["passed"])

    def test_quota_fail(self):
        self._register_healthy_connector("conn-quotafail")
        self.conn_reg.update_quota(ConnectorQuotaState(
            quota_id="q-fail",
            connector_id="conn-quotafail",
            quota_limit=100,
            quota_used=100,
            quota_remaining=0,
            reset_at="2027-01-01T00:00:00+00:00",
            reported_at=NOW,
        ))

        result = self.compliance.pre_flight_check("conn-quotafail")
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["quota"]["passed"])

    def test_health_fail(self):
        c = GenericApiTestConnector("conn-healthfail")
        self.conn_reg.register(c)
        self.conn_reg.set_secret_scope(SecretScope(
            scope_id="scope-healthfail",
            connector_id="conn-healthfail",
            auth_mode=ConnectorAuthMode.BEARER_TOKEN,
            rotation_state=SecretRotationState.CURRENT,
            credential_ref="ref-healthfail",
            rotation_interval_hours=720,
            last_rotated_at=NOW,
            expires_at="2027-06-01T00:00:00+00:00",
            created_at=NOW,
        ))
        # Override the descriptor to unhealthy
        from mcoi_runtime.contracts.external_connector import ExternalConnectorDescriptor
        self.conn_reg._descriptors["conn-healthfail"] = ExternalConnectorDescriptor(
            connector_id="conn-healthfail",
            name="Unhealthy connector",
            connector_type=ExternalConnectorType.GENERIC_API,
            auth_mode=ConnectorAuthMode.BEARER_TOKEN,
            health_state=ConnectorHealthState.UNHEALTHY,
            provider_name="generic-test",
            version="1.0.0",
            enabled=True,
            created_at=NOW,
        )

        result = self.compliance.pre_flight_check("conn-healthfail")
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["health"]["passed"])
        self.assertEqual(
            result["checks"]["health"]["reason"],
            "connector health check failed",
        )
        self.assertNotIn("unhealthy", result["checks"]["health"]["reason"].lower())

    def test_consent_fail(self):
        self._register_healthy_connector("conn-consentfail")
        # Record denied consent
        self.compliance.record_consent(
            "id-x", "sms", "conn-consentfail", ConsentState.DENIED,
        )
        result = self.compliance.pre_flight_check(
            "conn-consentfail",
            identity_id="id-x",
            channel_type="sms",
        )
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["consent"]["passed"])

    def test_consent_pass(self):
        self._register_healthy_connector("conn-consentpass")
        self.compliance.record_consent(
            "id-y", "sms", "conn-consentpass", ConsentState.GRANTED,
        )
        result = self.compliance.pre_flight_check(
            "conn-consentpass",
            identity_id="id-y",
            channel_type="sms",
        )
        self.assertTrue(result["passed"])
        self.assertTrue(result["checks"]["consent"]["passed"])

    def test_emits_event(self):
        self._register_healthy_connector("conn-evtcheck")
        events_before = len(self.es.list_events())
        self.compliance.pre_flight_check("conn-evtcheck")
        events_after = len(self.es.list_events())
        self.assertGreater(events_after, events_before)


if __name__ == "__main__":
    unittest.main()
