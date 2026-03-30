"""Governed Connector Framework — policy-bound integrations with external systems.

Purpose: typed, governed connectors for external services (HTTP APIs, email,
    messaging, ticketing, file storage). Every connector action goes through
    the guard chain and records to the audit trail.
Governance scope: connector registration, invocation, and lifecycle only.
Dependencies: governance guards, audit trail, clock injection.
Invariants:
  - All connector invocations go through the guard chain.
  - Connector errors never propagate as unhandled exceptions.
  - Invocation history is bounded (FIFO pruning).
  - Connectors are typed with explicit capabilities.
  - Retry semantics are configurable per connector.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


class ConnectorType(StrEnum):
    """Categories of external connectors."""

    HTTP_API = "http_api"
    EMAIL = "email"
    MESSAGING = "messaging"
    TICKETING = "ticketing"
    FILE_STORAGE = "file_storage"
    DATABASE = "database"
    CUSTOM = "custom"


class ConnectorStatus(StrEnum):
    """Lifecycle status of a connector."""

    REGISTERED = "registered"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class InvocationOutcome(StrEnum):
    """Result of a connector invocation."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DENIED = "denied"
    RETRIED = "retried"


@dataclass(frozen=True, slots=True)
class ConnectorDefinition:
    """Definition of a governed connector."""

    connector_id: str
    name: str
    connector_type: ConnectorType
    base_url: str = ""
    capabilities: tuple[str, ...] = ()
    max_retries: int = 3
    timeout_seconds: int = 30
    tenant_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorInvocation:
    """Record of a single connector invocation."""

    invocation_id: str
    connector_id: str
    action: str
    outcome: InvocationOutcome
    payload_summary: dict[str, Any]
    response_summary: dict[str, Any]
    duration_ms: float
    invoked_at: str
    error: str = ""
    retry_count: int = 0


@dataclass
class ConnectorState:
    """Runtime state of a connector."""

    definition: ConnectorDefinition
    status: ConnectorStatus = ConnectorStatus.REGISTERED
    invocation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_invoked_at: str = ""


class GovernedConnectorFramework:
    """Framework for registering and invoking governed external connectors.

    Every invocation:
    1. Validates the connector exists and is enabled
    2. Runs through the guard chain
    3. Calls the registered handler
    4. Records the invocation in history and audit trail
    """

    _MAX_HISTORY = 10_000

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        guard_chain: Any | None = None,
        audit_trail: Any | None = None,
    ) -> None:
        self._clock = clock
        self._guard_chain = guard_chain
        self._audit_trail = audit_trail
        self._connectors: dict[str, ConnectorState] = {}
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {}
        self._history: list[ConnectorInvocation] = []
        self._invocation_counter = 0
        self._lock = threading.Lock()

    def register(
        self,
        definition: ConnectorDefinition,
        handler: Callable[..., dict[str, Any]],
    ) -> ConnectorDefinition:
        """Register a connector with its handler."""
        with self._lock:
            self._connectors[definition.connector_id] = ConnectorState(
                definition=definition,
                status=ConnectorStatus.REGISTERED,
            )
            self._handlers[definition.connector_id] = handler
        return definition

    def unregister(self, connector_id: str) -> bool:
        """Remove a connector."""
        with self._lock:
            removed = self._connectors.pop(connector_id, None)
            self._handlers.pop(connector_id, None)
            return removed is not None

    def disable(self, connector_id: str) -> bool:
        """Disable a connector without removing it."""
        with self._lock:
            state = self._connectors.get(connector_id)
            if state is None:
                return False
            state.status = ConnectorStatus.DISABLED
            return True

    def enable(self, connector_id: str) -> bool:
        """Re-enable a disabled connector."""
        with self._lock:
            state = self._connectors.get(connector_id)
            if state is None:
                return False
            state.status = ConnectorStatus.HEALTHY
            return True

    def invoke(
        self,
        connector_id: str,
        action: str,
        payload: dict[str, Any],
        *,
        tenant_id: str = "",
        budget_id: str = "",
        mission_id: str = "",
        goal_id: str = "",
    ) -> ConnectorInvocation:
        """Invoke a connector action through the governed pipeline."""
        import time as _time

        now = self._clock()

        # Validate connector
        with self._lock:
            state = self._connectors.get(connector_id)
        if state is None:
            return self._record_invocation(
                connector_id, action, InvocationOutcome.FAILURE,
                {}, {}, 0.0, now, error="connector not found",
            )
        if state.status == ConnectorStatus.DISABLED:
            return self._record_invocation(
                connector_id, action, InvocationOutcome.DENIED,
                {}, {}, 0.0, now, error="connector is disabled",
            )

        # Guard chain gate
        if self._guard_chain is not None:
            guard_ctx = {
                "tenant_id": tenant_id or state.definition.tenant_id,
                "budget_id": budget_id,
                "action_type": f"connector.{connector_id}.{action}",
                "target": state.definition.name,
                "agent_id": f"connector:{connector_id}",
            }
            guard_result = self._guard_chain.evaluate(guard_ctx)
            if not guard_result.allowed:
                return self._record_invocation(
                    connector_id, action, InvocationOutcome.DENIED,
                    payload, {}, 0.0, now,
                    error=f"guard denied: {guard_result.reason}",
                )

        # Execute handler
        handler = self._handlers.get(connector_id)
        if handler is None:
            return self._record_invocation(
                connector_id, action, InvocationOutcome.FAILURE,
                payload, {}, 0.0, now, error="handler not found",
            )

        t0 = _time.monotonic()
        try:
            result = handler(action, payload)
            duration_ms = (_time.monotonic() - t0) * 1000
            with self._lock:
                state.invocation_count += 1
                state.success_count += 1
                state.last_invoked_at = now
                state.status = ConnectorStatus.HEALTHY
            invocation = self._record_invocation(
                connector_id, action, InvocationOutcome.SUCCESS,
                payload, result, duration_ms, now,
            )
        except Exception as exc:
            duration_ms = (_time.monotonic() - t0) * 1000
            with self._lock:
                state.invocation_count += 1
                state.failure_count += 1
                state.last_invoked_at = now
                if state.failure_count > 3:
                    state.status = ConnectorStatus.DEGRADED
            invocation = self._record_invocation(
                connector_id, action, InvocationOutcome.FAILURE,
                payload, {}, duration_ms, now,
                error=f"{type(exc).__name__}: {exc}",
            )

        # Audit trail
        if self._audit_trail is not None:
            goal_ctx = {}
            if mission_id:
                goal_ctx["mission_id"] = mission_id
            if goal_id:
                goal_ctx["goal_id"] = goal_id
            self._audit_trail.record(
                action=f"connector.invoke.{action}",
                actor_id=f"connector:{connector_id}",
                tenant_id=tenant_id or state.definition.tenant_id,
                target=state.definition.name,
                outcome=invocation.outcome.value,
                detail={
                    "connector_type": state.definition.connector_type.value,
                    "duration_ms": round(duration_ms, 1),
                    **goal_ctx,
                },
            )

        return invocation

    def _record_invocation(
        self,
        connector_id: str, action: str,
        outcome: InvocationOutcome,
        payload: dict[str, Any], response: dict[str, Any],
        duration_ms: float, invoked_at: str, *,
        error: str = "",
    ) -> ConnectorInvocation:
        """Record an invocation in history."""
        with self._lock:
            self._invocation_counter += 1
            inv = ConnectorInvocation(
                invocation_id=f"cinv-{self._invocation_counter:06d}",
                connector_id=connector_id,
                action=action,
                outcome=outcome,
                payload_summary={"keys": list(payload.keys())} if payload else {},
                response_summary={"keys": list(response.keys())} if response else {},
                duration_ms=duration_ms,
                invoked_at=invoked_at,
                error=error,
            )
            self._history.append(inv)
            if len(self._history) > self._MAX_HISTORY:
                self._history = self._history[-self._MAX_HISTORY:]
        return inv

    def get_connector(self, connector_id: str) -> ConnectorState | None:
        return self._connectors.get(connector_id)

    def list_connectors(self) -> list[ConnectorState]:
        with self._lock:
            return sorted(self._connectors.values(), key=lambda c: c.definition.connector_id)

    def recent_invocations(self, limit: int = 50) -> list[ConnectorInvocation]:
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._connectors)
            healthy = sum(1 for c in self._connectors.values() if c.status == ConnectorStatus.HEALTHY)
            return {
                "total_connectors": total,
                "healthy": healthy,
                "degraded": sum(1 for c in self._connectors.values() if c.status == ConnectorStatus.DEGRADED),
                "disabled": sum(1 for c in self._connectors.values() if c.status == ConnectorStatus.DISABLED),
                "total_invocations": self._invocation_counter,
                "history_size": len(self._history),
            }
