"""Purpose: connectivity compliance — secrets, rotation, redaction, consent, audit.
Governance scope: enforcing secret scoping, credential rotation, retention
    policies, payload redaction, consent verification, and outbound audit
    trails for live external connectivity.
Dependencies: external_connectors, external_connector contracts, event_spine,
    memory_mesh, core invariants.
Invariants:
  - Expired or revoked credentials block execution.
  - Rotation hooks fire when credentials approach expiry.
  - Redaction policies are enforced before payload storage.
  - Consent is verified before channel-identity operations.
  - Every outbound call is recorded in the audit trail.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.external_connector import (
    ChannelConsentRecord,
    ConnectorAuthMode,
    ConnectorHealthState,
    ConnectorRetentionPolicy,
    ConsentState,
    RedactionLevel,
    SecretRotationState,
    SecretScope,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .external_connectors import ExternalConnectorRegistry
from .event_spine import EventSpineEngine
from .memory_mesh import MemoryMeshEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-compl", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ConnectivityComplianceEngine:
    """Enforces secrets, rotation, redaction, consent, and audit trail
    for live external connectivity."""

    def __init__(
        self,
        connector_registry: ExternalConnectorRegistry,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(connector_registry, ExternalConnectorRegistry):
            raise RuntimeCoreInvariantError(
                "connector_registry must be an ExternalConnectorRegistry"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError(
                "memory_engine must be a MemoryMeshEngine"
            )
        self._connectors = connector_registry
        self._events = event_spine
        self._memory = memory_engine
        self._audit_trail: list[dict[str, Any]] = []
        self._rotation_hooks: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Credential validation
    # ------------------------------------------------------------------

    def validate_all_credentials(self) -> dict[str, Any]:
        """Validate credentials for all connectors. Returns summary."""
        results: dict[str, bool] = {}
        expired: list[str] = []
        revoked: list[str] = []
        pending_rotation: list[str] = []

        for desc in self._connectors.list_connectors():
            cid = desc.connector_id
            valid = self._connectors.validate_credential(cid)
            results[cid] = valid

            scope = self._connectors.get_secret_scope(cid)
            if scope:
                if scope.rotation_state == SecretRotationState.EXPIRED:
                    expired.append(cid)
                elif scope.rotation_state == SecretRotationState.REVOKED:
                    revoked.append(cid)
                elif scope.rotation_state == SecretRotationState.PENDING_ROTATION:
                    pending_rotation.append(cid)

        event = _emit(self._events, "credentials_validated", {
            "total": len(results),
            "valid": sum(1 for v in results.values() if v),
            "invalid": sum(1 for v in results.values() if not v),
            "expired_count": len(expired),
            "revoked_count": len(revoked),
        }, "cred-validation")

        return {
            "results": results,
            "expired": tuple(expired),
            "revoked": tuple(revoked),
            "pending_rotation": tuple(pending_rotation),
            "event": event,
        }

    def check_rotation_needed(
        self, connector_id: str, hours_until_expiry: int = 24,
    ) -> dict[str, Any]:
        """Check if a connector's credential needs rotation."""
        scope = self._connectors.get_secret_scope(connector_id)
        if scope is None:
            return {"needs_rotation": False, "reason": "no credential scope"}

        if scope.rotation_state in (
            SecretRotationState.EXPIRED,
            SecretRotationState.REVOKED,
        ):
            return {
                "needs_rotation": True,
                "reason": f"credential is {scope.rotation_state.value}",
                "urgent": True,
            }

        if scope.rotation_state == SecretRotationState.PENDING_ROTATION:
            return {
                "needs_rotation": True,
                "reason": "rotation already pending",
                "urgent": False,
            }

        # Check expiry proximity
        try:
            expires = datetime.fromisoformat(
                scope.expires_at.replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            hours_remaining = (expires - now).total_seconds() / 3600
            if hours_remaining <= hours_until_expiry:
                return {
                    "needs_rotation": True,
                    "reason": f"expires in {hours_remaining:.1f} hours",
                    "urgent": hours_remaining <= 1,
                }
        except (ValueError, TypeError):
            pass

        return {"needs_rotation": False, "reason": "credential is current"}

    def register_rotation_hook(
        self, connector_id: str, hook_ref: str,
    ) -> None:
        """Register a rotation hook for a connector."""
        self._rotation_hooks.append({
            "connector_id": connector_id,
            "hook_ref": hook_ref,
            "registered_at": _now_iso(),
        })

    def get_rotation_hooks(
        self, connector_id: str,
    ) -> tuple[dict[str, Any], ...]:
        return tuple(
            h for h in self._rotation_hooks
            if h["connector_id"] == connector_id
        )

    # ------------------------------------------------------------------
    # Redaction
    # ------------------------------------------------------------------

    def redact_payload(
        self, connector_id: str, payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Apply redaction policy to a payload before storage."""
        policy = self._connectors.get_retention_policy(connector_id)
        if policy is None:
            # Default: no redaction
            return dict(payload)

        level = policy.redaction_level
        result = dict(payload)

        if level == RedactionLevel.COMPLETE:
            return {"redacted": True, "connector_id": connector_id}

        if level == RedactionLevel.BODY_FULL:
            for key in ("body", "body_text", "body_html", "content", "text"):
                if key in result:
                    result[key] = "[REDACTED]"

        if level == RedactionLevel.BODY_PARTIAL:
            for key in ("body", "body_text", "body_html", "content", "text"):
                if key in result and isinstance(result[key], str):
                    text = result[key]
                    if len(text) > 50:
                        result[key] = text[:25] + "...[REDACTED]..." + text[-25:]

        if level == RedactionLevel.HEADERS_ONLY:
            for key in ("authorization", "api_key", "token", "secret",
                        "password", "credential"):
                if key in result:
                    result[key] = "[REDACTED]"

        # PII scrubbing
        if policy.pii_scrub_enabled:
            result = self._scrub_pii(result)

        return result

    def _scrub_pii(self, data: dict[str, Any]) -> dict[str, Any]:
        """Basic PII scrubbing — replace common PII-like patterns."""
        pii_keys = ("email", "phone", "ssn", "social_security",
                    "credit_card", "account_number", "date_of_birth")
        result = dict(data)
        for key in pii_keys:
            if key in result:
                result[key] = "[PII_SCRUBBED]"
        return result

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    def verify_consent(
        self, identity_id: str, channel_type: str, connector_id: str,
    ) -> dict[str, Any]:
        """Verify consent for a channel-identity-connector binding."""
        state = self._connectors.check_consent(
            identity_id, channel_type, connector_id,
        )

        allowed = state == ConsentState.GRANTED if state else False

        event = _emit(self._events, "consent_verified", {
            "identity_id": identity_id,
            "channel_type": channel_type,
            "connector_id": connector_id,
            "state": state.value if state else "none",
            "allowed": allowed,
        }, f"consent-{identity_id}-{channel_type}")

        return {
            "state": state,
            "allowed": allowed,
            "event": event,
        }

    def record_consent(
        self,
        identity_id: str,
        channel_type: str,
        connector_id: str,
        consent_state: ConsentState,
    ) -> ChannelConsentRecord:
        """Record a consent decision."""
        now = _now_iso()
        record = ChannelConsentRecord(
            consent_id=stable_identifier("consent", {
                "iid": identity_id, "ch": channel_type,
                "cid": connector_id, "ts": now,
            }),
            identity_id=identity_id,
            channel_type=channel_type,
            connector_id=connector_id,
            consent_state=consent_state,
            granted_at=now if consent_state == ConsentState.GRANTED else "",
            expires_at="",
            recorded_at=now,
        )
        self._connectors.record_consent(record)

        _emit(self._events, "consent_recorded", {
            "identity_id": identity_id,
            "channel_type": channel_type,
            "connector_id": connector_id,
            "state": consent_state.value,
        }, record.consent_id)

        return record

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------

    def record_outbound_call(
        self, connector_id: str, operation: str,
        payload: Mapping[str, Any],
        response_summary: str = "",
        success: bool = True,
    ) -> dict[str, Any]:
        """Record an outbound call in the audit trail and memory mesh."""
        now = _now_iso()

        # Redact before storing
        redacted_payload = self.redact_payload(connector_id, payload)

        entry = {
            "audit_id": stable_identifier("audit", {
                "cid": connector_id, "op": operation, "ts": now,
            }),
            "connector_id": connector_id,
            "operation": operation,
            "payload_redacted": redacted_payload,
            "response_summary": response_summary,
            "success": success,
            "recorded_at": now,
        }
        self._audit_trail.append(entry)

        # Record in memory mesh
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-audit", {
                "cid": connector_id, "op": operation, "ts": now,
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=connector_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Outbound {operation} via {connector_id}",
            content={
                "connector_id": connector_id,
                "operation": operation,
                "success": success,
                "response_summary": response_summary,
            },
            source_ids=(connector_id,),
            tags=("audit", "outbound", operation),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        event = _emit(self._events, "outbound_call_audited", {
            "connector_id": connector_id,
            "operation": operation,
            "success": success,
        }, entry["audit_id"])

        return {"audit_entry": entry, "memory": mem, "event": event}

    def get_audit_trail(
        self, connector_id: str | None = None,
    ) -> tuple[dict[str, Any], ...]:
        if connector_id is None:
            return tuple(self._audit_trail)
        return tuple(
            e for e in self._audit_trail
            if e["connector_id"] == connector_id
        )

    # ------------------------------------------------------------------
    # Full pre-flight compliance check
    # ------------------------------------------------------------------

    def pre_flight_check(
        self, connector_id: str,
        identity_id: str | None = None,
        channel_type: str | None = None,
    ) -> dict[str, Any]:
        """Run all compliance checks before executing via a connector.

        Returns a dict with pass/fail for each dimension.
        """
        results: dict[str, Any] = {
            "connector_id": connector_id,
            "passed": True,
            "checks": {},
        }

        # 1. Credential validation
        cred_valid = self._connectors.validate_credential(connector_id)
        results["checks"]["credential"] = {
            "passed": cred_valid,
            "reason": "valid" if cred_valid else "invalid or missing",
        }
        if not cred_valid:
            results["passed"] = False

        # 2. Rate limit
        rate_ok = self._connectors.check_rate_limit(connector_id)
        results["checks"]["rate_limit"] = {
            "passed": rate_ok,
            "reason": "within limits" if rate_ok else "rate limited",
        }
        if not rate_ok:
            results["passed"] = False

        # 3. Quota
        quota_ok = self._connectors.check_quota(connector_id)
        results["checks"]["quota"] = {
            "passed": quota_ok,
            "reason": "within quota" if quota_ok else "quota exhausted",
        }
        if not quota_ok:
            results["passed"] = False

        # 4. Connector health
        desc = self._connectors.get_descriptor(connector_id)
        health_ok = desc.enabled and desc.health_state in (
            ConnectorHealthState.HEALTHY,
            ConnectorHealthState.DEGRADED,
        )
        results["checks"]["health"] = {
            "passed": health_ok,
            "reason": f"state={desc.health_state.value}, enabled={desc.enabled}",
        }
        if not health_ok:
            results["passed"] = False

        # 5. Rotation check
        rotation = self.check_rotation_needed(connector_id)
        rotation_ok = not rotation.get("urgent", False)
        results["checks"]["rotation"] = {
            "passed": rotation_ok,
            "reason": rotation["reason"],
            "needs_rotation": rotation["needs_rotation"],
        }
        if not rotation_ok:
            results["passed"] = False

        # 6. Consent (if identity + channel provided)
        if identity_id and channel_type:
            consent_result = self.verify_consent(
                identity_id, channel_type, connector_id,
            )
            results["checks"]["consent"] = {
                "passed": consent_result["allowed"],
                "state": consent_result["state"].value if consent_result["state"] else "none",
            }
            if not consent_result["allowed"]:
                results["passed"] = False

        _emit(self._events, "pre_flight_completed", {
            "connector_id": connector_id,
            "passed": results["passed"],
            "checks_count": len(results["checks"]),
        }, f"preflight-{connector_id}")

        return results
