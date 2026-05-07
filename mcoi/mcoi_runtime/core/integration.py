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
from mcoi_runtime.contracts.effect_assurance import ExpectedEffect, ReconciliationStatus
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.effect_case_anchor import open_effect_reconciliation_case
from mcoi_runtime.core.effect_result_adapter import execution_result_from_connector
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

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        provider_registry: ProviderRegistry | None = None,
        effect_assurance: EffectAssuranceGate | None = None,
        effect_assurance_tenant_id: str = "integration",
        case_runtime: CaseRuntimeEngine | None = None,
    ) -> None:
        self._clock = clock
        self._connectors: dict[str, ConnectorDescriptor] = {}
        self._adapters: dict[str, ConnectorAdapter] = {}
        self._provider_registry = provider_registry
        self._connector_provider_map: dict[str, str] = {}  # connector_id -> provider_id
        self._effect_assurance = effect_assurance
        self._effect_assurance_tenant_id = ensure_non_empty_text(
            "effect_assurance_tenant_id",
            effect_assurance_tenant_id,
        )
        self._case_runtime = case_runtime

    def register(
        self,
        descriptor: ConnectorDescriptor,
        adapter: ConnectorAdapter,
        *,
        provider_id: str | None = None,
    ) -> ConnectorDescriptor:
        if descriptor.connector_id in self._connectors:
            raise RuntimeCoreInvariantError("connector already registered")
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
        if provider_id is not None:
            result = ConnectorResult(
                result_id=result.result_id,
                connector_id=result.connector_id,
                status=result.status,
                response_digest=result.response_digest,
                started_at=result.started_at,
                finished_at=result.finished_at,
                error_code=result.error_code,
                metadata={**dict(result.metadata), "provider_id": provider_id},
            )
        if self._effect_assurance is not None:
            result = self._assure_connector_effect(connector, request, result)

        # Update provider health from result
        if self._provider_registry is not None and provider_id is not None:
            if result.status is ConnectorStatus.SUCCEEDED:
                self._provider_registry.record_success(provider_id)
            else:
                self._provider_registry.record_failure(provider_id, result.error_code or "unknown_failure")

        return result

    def _assure_connector_effect(
        self,
        connector: ConnectorDescriptor,
        request: InvocationRequest,
        result: ConnectorResult,
    ) -> ConnectorResult:
        try:
            execution_result = execution_result_from_connector(
                result,
                goal_id=f"{request.connector_id}:{request.operation}",
            )
            effect = execution_result.actual_effects[0]
            plan = self._effect_assurance.create_plan(
                command_id=result.result_id,
                tenant_id=self._effect_assurance_tenant_id,
                capability_id=f"connector:{connector.connector_id}:{request.operation}",
                expected_effects=(
                    ExpectedEffect(
                        effect_id=effect.name,
                        name=effect.name,
                        target_ref=connector.connector_id,
                        required=True,
                        verification_method="receipt",
                    ),
                ),
                forbidden_effects=("connector_duplicate_mutation",),
            )
            observed = self._effect_assurance.observe(execution_result)
            verification = self._effect_assurance.verify(
                plan=plan,
                execution_result=execution_result,
                observed_effects=observed,
            )
            reconciliation = self._effect_assurance.reconcile(
                plan=plan,
                observed_effects=observed,
                verification_result=verification,
            )
        except RuntimeCoreInvariantError as exc:
            return ConnectorResult(
                result_id=result.result_id,
                connector_id=result.connector_id,
                status=ConnectorStatus.FAILED,
                response_digest=result.response_digest,
                started_at=result.started_at,
                finished_at=result.finished_at,
                error_code="effect_assurance_failed",
                metadata={
                    **dict(result.metadata),
                    "effect_assurance_error": str(exc),
                },
            )

        assurance_metadata = {
            "effect_plan_id": plan.effect_plan_id,
            "verification_result_id": verification.verification_id,
            "reconciliation_id": reconciliation.reconciliation_id,
            "reconciliation_status": reconciliation.status.value,
        }
        if reconciliation.status is not ReconciliationStatus.MATCH:
            case_id = open_effect_reconciliation_case(
                self._case_runtime,
                command_id=plan.command_id,
                tenant_id=plan.tenant_id,
                source_type="connector_invocation",
                source_id=result.result_id,
                effect_plan_id=plan.effect_plan_id,
                verification_result_id=verification.verification_id,
                reconciliation_status=reconciliation.status,
            )
            if case_id is not None:
                reconciliation = self._effect_assurance.reconcile(
                    plan=plan,
                    observed_effects=observed,
                    verification_result=verification,
                    case_id=case_id,
                )
                assurance_metadata = {
                    "effect_plan_id": plan.effect_plan_id,
                    "verification_result_id": verification.verification_id,
                    "reconciliation_id": reconciliation.reconciliation_id,
                    "reconciliation_status": reconciliation.status.value,
                    "case_id": case_id,
                }
            return ConnectorResult(
                result_id=result.result_id,
                connector_id=result.connector_id,
                status=ConnectorStatus.FAILED,
                response_digest=result.response_digest,
                started_at=result.started_at,
                finished_at=result.finished_at,
                error_code="effect_reconciliation_mismatch",
                metadata={**dict(result.metadata), "effect_assurance": assurance_metadata},
            )
        if self._effect_assurance.graph_commit_available:
            try:
                self._effect_assurance.commit_graph(
                    plan=plan,
                    observed_effects=observed,
                    reconciliation=reconciliation,
                )
            except RuntimeCoreInvariantError as exc:
                return ConnectorResult(
                    result_id=result.result_id,
                    connector_id=result.connector_id,
                    status=ConnectorStatus.FAILED,
                    response_digest=result.response_digest,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                    error_code="effect_graph_commit_failed",
                    metadata={
                        **dict(result.metadata),
                        "effect_assurance": assurance_metadata,
                        "effect_assurance_error": str(exc),
                    },
                )
        return ConnectorResult(
            result_id=result.result_id,
            connector_id=result.connector_id,
            status=result.status,
            response_digest=result.response_digest,
            started_at=result.started_at,
            finished_at=result.finished_at,
            error_code=result.error_code,
            metadata={**dict(result.metadata), "effect_assurance": assurance_metadata},
        )

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
