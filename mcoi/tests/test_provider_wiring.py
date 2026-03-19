"""Purpose: verify provider registry is consulted during integration/communication/model invocations.
Governance scope: provider runtime wiring tests only.
Dependencies: provider registry, integration/communication/model cores, adapters.
Invariants: scope enforced, health updated, disabled/unhealthy providers fail closed.
"""

from __future__ import annotations

from pathlib import Path

from mcoi_runtime.adapters.file_communication import FileCommunicationAdapter
from mcoi_runtime.adapters.stub_model import StubModelAdapter
from mcoi_runtime.contracts.communication import CommunicationChannel
from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorResult,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)
from mcoi_runtime.contracts.model import ModelInvocation, ModelStatus
from mcoi_runtime.contracts.provider import (
    CredentialScope,
    ProviderClass,
    ProviderDescriptor,
    ProviderHealthStatus,
)
from mcoi_runtime.core.communication import ApprovalRequest, CommunicationEngine
from mcoi_runtime.core.integration import IntegrationEngine, InvocationRequest
from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.core.model_orchestration import ModelDescriptor, ModelOrchestrationEngine
from mcoi_runtime.core.provider_registry import ProviderRegistry


_CLOCK = "2026-03-19T00:00:00+00:00"


# --- Integration + Provider Registry ---


class FakeConnectorAdapter:
    def invoke(self, connector: ConnectorDescriptor, request: dict) -> ConnectorResult:
        return ConnectorResult(
            result_id=stable_identifier("res", {"c": connector.connector_id}),
            connector_id=connector.connector_id,
            status=ConnectorStatus.SUCCEEDED,
            response_digest="digest-ok",
            started_at=_CLOCK,
            finished_at=_CLOCK,
        )


def test_integration_checks_provider_before_invoke() -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-http", name="HTTP",
            provider_class=ProviderClass.INTEGRATION,
            credential_scope_id="scope-http", enabled=True,
        ),
        CredentialScope(
            scope_id="scope-http", provider_id="prov-http",
            allowed_base_urls=("https://allowed.com",),
        ),
    )

    engine = IntegrationEngine(clock=lambda: _CLOCK, provider_registry=registry)
    engine.register(
        ConnectorDescriptor(
            connector_id="conn-1", name="Test", provider="test",
            effect_class=EffectClass.EXTERNAL_READ, trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="scope-http", enabled=True,
        ),
        FakeConnectorAdapter(),
        provider_id="prov-http",
    )

    # In-scope URL succeeds
    result = engine.invoke(InvocationRequest(
        connector_id="conn-1", operation="fetch",
        parameters={"url": "https://allowed.com/data"},
    ))
    assert result.status is ConnectorStatus.SUCCEEDED
    assert registry.get_health("prov-http").status is ProviderHealthStatus.HEALTHY


def test_integration_rejects_out_of_scope_url() -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-1", name="P",
            provider_class=ProviderClass.INTEGRATION,
            credential_scope_id="s-1", enabled=True,
        ),
        CredentialScope(
            scope_id="s-1", provider_id="prov-1",
            allowed_base_urls=("https://allowed.com",),
        ),
    )

    engine = IntegrationEngine(clock=lambda: _CLOCK, provider_registry=registry)
    engine.register(
        ConnectorDescriptor(
            connector_id="c-1", name="C", provider="p",
            effect_class=EffectClass.EXTERNAL_READ, trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="s-1", enabled=True,
        ),
        FakeConnectorAdapter(),
        provider_id="prov-1",
    )

    result = engine.invoke(InvocationRequest(
        connector_id="c-1", operation="fetch",
        parameters={"url": "https://evil.com/steal"},
    ))
    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "credential_scope_exceeded"


def test_integration_rejects_disabled_provider() -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-1", name="P",
            provider_class=ProviderClass.INTEGRATION,
            credential_scope_id="s-1", enabled=False,
        ),
        CredentialScope(scope_id="s-1", provider_id="prov-1"),
    )

    engine = IntegrationEngine(clock=lambda: _CLOCK, provider_registry=registry)
    engine.register(
        ConnectorDescriptor(
            connector_id="c-1", name="C", provider="p",
            effect_class=EffectClass.EXTERNAL_READ, trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="s-1", enabled=True,
        ),
        FakeConnectorAdapter(),
        provider_id="prov-1",
    )

    result = engine.invoke(InvocationRequest(
        connector_id="c-1", operation="op", parameters={},
    ))
    assert result.status is ConnectorStatus.FAILED
    assert "provider:provider_disabled" in result.error_code


# --- Communication + Provider Registry ---


def test_communication_checks_provider(tmp_path: Path) -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-file", name="File",
            provider_class=ProviderClass.COMMUNICATION,
            credential_scope_id="s-file", enabled=True,
        ),
        CredentialScope(scope_id="s-file", provider_id="prov-file"),
    )

    adapter = FileCommunicationAdapter(outbox_path=tmp_path / "outbox", clock=lambda: _CLOCK)
    engine = CommunicationEngine(
        sender_id="agent-1", clock=lambda: _CLOCK,
        adapters={CommunicationChannel.APPROVAL: adapter},
        provider_registry=registry,
        channel_provider_map={CommunicationChannel.APPROVAL: "prov-file"},
    )

    result = engine.request_approval(
        ApprovalRequest(subject_id="s", goal_id="g", action_description="a", reason="r"),
        recipient_id="operator-1",
    )
    assert result.status.value == "delivered"
    assert registry.get_health("prov-file").status is ProviderHealthStatus.HEALTHY


def test_communication_rejects_unavailable_provider(tmp_path: Path) -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-down", name="Down",
            provider_class=ProviderClass.COMMUNICATION,
            credential_scope_id="s-down", enabled=True,
        ),
        CredentialScope(scope_id="s-down", provider_id="prov-down"),
    )
    # Make unavailable
    for _ in range(3):
        registry.record_failure("prov-down", "error")

    adapter = FileCommunicationAdapter(outbox_path=tmp_path / "outbox", clock=lambda: _CLOCK)
    engine = CommunicationEngine(
        sender_id="agent-1", clock=lambda: _CLOCK,
        adapters={CommunicationChannel.APPROVAL: adapter},
        provider_registry=registry,
        channel_provider_map={CommunicationChannel.APPROVAL: "prov-down"},
    )

    result = engine.request_approval(
        ApprovalRequest(subject_id="s", goal_id="g", action_description="a", reason="r"),
        recipient_id="op-1",
    )
    assert result.status.value == "failed"
    assert "provider" in result.error_code


# --- Model + Provider Registry ---


def test_model_checks_provider() -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-model", name="Stub",
            provider_class=ProviderClass.MODEL,
            credential_scope_id="s-model", enabled=True,
        ),
        CredentialScope(scope_id="s-model", provider_id="prov-model"),
    )

    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK, provider_registry=registry)
    engine.register(
        ModelDescriptor(model_id="stub-1", name="Stub", provider="local"),
        StubModelAdapter(clock=lambda: _CLOCK),
        provider_id="prov-model",
    )

    resp = engine.invoke(ModelInvocation(
        invocation_id="inv-1", model_id="stub-1",
        prompt_hash="hash-1", invoked_at=_CLOCK,
    ))
    assert resp.status is ModelStatus.SUCCEEDED
    assert registry.get_health("prov-model").status is ProviderHealthStatus.HEALTHY


def test_model_rejects_disabled_provider() -> None:
    registry = ProviderRegistry(clock=lambda: _CLOCK)
    registry.register(
        ProviderDescriptor(
            provider_id="prov-off", name="Off",
            provider_class=ProviderClass.MODEL,
            credential_scope_id="s-off", enabled=False,
        ),
        CredentialScope(scope_id="s-off", provider_id="prov-off"),
    )

    engine = ModelOrchestrationEngine(clock=lambda: _CLOCK, provider_registry=registry)
    engine.register(
        ModelDescriptor(model_id="m-1", name="M", provider="p"),
        StubModelAdapter(clock=lambda: _CLOCK),
        provider_id="prov-off",
    )

    resp = engine.invoke(ModelInvocation(
        invocation_id="inv-1", model_id="m-1",
        prompt_hash="h-1", invoked_at=_CLOCK,
    ))
    assert resp.status is ModelStatus.FAILED
