"""Purpose: integration core — connector registry, invocation routing, and result validation.
Governance scope: external integration plane core logic only.
Dependencies: integration contracts, invariant helpers.
Invariants:
  - Connectors must be registered before invocation.
  - Disabled connectors MUST NOT be invoked.
  - Credentials MUST NOT be used outside declared scope.
  - Every invocation produces a typed result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorResult,
    ConnectorStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier
from .provider_registry import ProviderRegistry


class ConnectorAdapter(Protocol):
    """Protocol for connector-specific invocation adapters."""

    def invoke(self, connector: ConnectorDescriptor, request: dict) -> ConnectorResult: ...


@dataclass(frozen=True, slots=True)
class InvocationRequest:
    """Request to invoke a registered connector."""

    connector_id: str
    operation: str
    parameters: dict

    def __post_init__(self) -> None:
        object.__setattr__(self, "connector_id", ensure_non_empty_text("connector_id", self.connector_id))
        object.__setattr__(self, "operation", ensure_non_empty_text("operation", self.operation))
        if not isinstance(self.parameters, dict):
            raise RuntimeCoreInvariantError("parameters must be a dict")


class IntegrationEngine:
    """Connector registry and invocation routing.

    This engine:
    - Maintains a typed connector registry
    - Routes invocations to registered adapters
    - Validates connector state before invocation
    - Returns typed results — never raw external responses
    """

    def __init__(self, *, clock: Callable[[], str], provider_registry: ProviderRegistry | None = None) -> None:
        self._clock = clock
        self._connectors: dict[str, ConnectorDescriptor] = {}
        self._adapters: dict[str, ConnectorAdapter] = {}
        self._provider_registry = provider_registry
        self._connector_provider_map: dict[str, str] = {}  # connector_id -> provider_id

    def register(
        self,
        descriptor: ConnectorDescriptor,
        adapter: ConnectorAdapter,
        *,
        provider_id: str | None = None,
    ) -> ConnectorDescriptor:
        if descriptor.connector_id in self._connectors:
            raise RuntimeCoreInvariantError(
                f"connector already registered: {descriptor.connector_id}"
            )
        self._connectors[descriptor.connector_id] = descriptor
        self._adapters[descriptor.connector_id] = adapter
        if provider_id is not None:
            self._connector_provider_map[descriptor.connector_id] = provider_id
        return descriptor

    def get_connector(self, connector_id: str) -> ConnectorDescriptor | None:
        ensure_non_empty_text("connector_id", connector_id)
        return self._connectors.get(connector_id)

    def list_connectors(self, *, enabled_only: bool = False) -> tuple[ConnectorDescriptor, ...]:
        connectors = sorted(self._connectors.values(), key=lambda c: c.connector_id)
        if enabled_only:
            connectors = [c for c in connectors if c.enabled]
        return tuple(connectors)

    def invoke(self, request: InvocationRequest) -> ConnectorResult:
        """Invoke a registered connector.

        Validates: connector exists, connector is enabled, provider is invocable,
        URL is in scope (if applicable), adapter is available.
        After invocation, updates provider health from result.
        """
        started_at = self._clock()
        provider_id = self._connector_provider_map.get(request.connector_id)

        connector = self._connectors.get(request.connector_id)
        if connector is None:
            return self._failure_result(request.connector_id, started_at, "connector_not_registered")

        if not connector.enabled:
            return self._failure_result(request.connector_id, started_at, "connector_disabled")

        # Provider registry checks (if wired)
        if self._provider_registry is not None and provider_id is not None:
            ok, reason = self._provider_registry.check_invocable(provider_id)
            if not ok:
                return self._failure_result(request.connector_id, started_at, f"provider:{reason}")

            # URL scope check
            url = request.parameters.get("url", "")
            if url and not self._provider_registry.check_url_in_scope(provider_id, url):
                return self._failure_result(request.connector_id, started_at, "credential_scope_exceeded")

        adapter = self._adapters.get(request.connector_id)
        if adapter is None:
            return self._failure_result(request.connector_id, started_at, "adapter_not_available")

        try:
            result = adapter.invoke(connector, request.parameters)
        except Exception as exc:
            result = self._failure_result(request.connector_id, started_at, f"adapter_error:{type(exc).__name__}")

        # Update provider health from result
        if self._provider_registry is not None and provider_id is not None:
            if result.status is ConnectorStatus.SUCCEEDED:
                self._provider_registry.record_success(provider_id)
            else:
                self._provider_registry.record_failure(provider_id, result.error_code or "unknown_failure")

        return result

    def _failure_result(
        self,
        connector_id: str,
        started_at: str,
        error_code: str,
    ) -> ConnectorResult:
        finished_at = self._clock()
        result_id = stable_identifier("conn-result", {
            "connector_id": connector_id,
            "error_code": error_code,
            "started_at": started_at,
        })
        return ConnectorResult(
            result_id=result_id,
            connector_id=connector_id,
            status=ConnectorStatus.FAILED,
            response_digest="none",
            started_at=started_at,
            finished_at=finished_at,
            error_code=error_code,
        )
