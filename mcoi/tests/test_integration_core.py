"""Purpose: verify integration engine — connector registry, routing, and failure handling.
Governance scope: integration core tests only.
Dependencies: integration engine, contracts.
Invariants: disabled connectors MUST NOT be invoked; missing connectors fail closed.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.integration import (
    ConnectorDescriptor,
    ConnectorResult,
    ConnectorStatus,
    EffectClass,
    TrustClass,
)
from mcoi_runtime.contracts.effect_assurance import EffectReconciliation, ReconciliationStatus
from mcoi_runtime.core.integration import (
    IntegrationEngine,
    InvocationRequest,
)
from mcoi_runtime.core.case_runtime import CaseRuntimeEngine
from mcoi_runtime.core.effect_assurance import EffectAssuranceGate
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


_CLOCK = "2026-03-19T00:00:00+00:00"


class FakeConnectorAdapter:
    def __init__(self, response_digest: str = "resp-digest", *, include_receipt: bool = False) -> None:
        self._digest = response_digest
        self._include_receipt = include_receipt
        self.invoked: list[dict] = []

    def invoke(self, connector: ConnectorDescriptor, request: dict) -> ConnectorResult:
        self.invoked.append(request)
        result_id = stable_identifier("res", {"connector_id": connector.connector_id})
        metadata = {}
        if self._include_receipt:
            metadata = {
                "connector_receipt": {
                    "receipt_id": "connector-receipt-1",
                    "evidence_ref": f"connector-invocation:{connector.connector_id}:receipt-1",
                    "status": "succeeded",
                    "response_digest": self._digest,
                }
            }
        return ConnectorResult(
            result_id=result_id,
            connector_id=connector.connector_id,
            status=ConnectorStatus.SUCCEEDED,
            response_digest=self._digest,
            started_at=_CLOCK,
            finished_at=_CLOCK,
            metadata=metadata,
        )


class MismatchEffectAssuranceGate(EffectAssuranceGate):
    def reconcile(self, **kwargs) -> EffectReconciliation:
        base = super().reconcile(**kwargs)
        return EffectReconciliation(
            reconciliation_id=base.reconciliation_id,
            command_id=base.command_id,
            effect_plan_id=base.effect_plan_id,
            status=ReconciliationStatus.MISMATCH,
            matched_effects=base.matched_effects,
            missing_effects=("forced_missing_effect",),
            unexpected_effects=base.unexpected_effects,
            verification_result_id=base.verification_result_id,
            case_id=kwargs.get("case_id"),
            decided_at=base.decided_at,
        )


def _descriptor(connector_id: str = "conn-1", enabled: bool = True) -> ConnectorDescriptor:
    return ConnectorDescriptor(
        connector_id=connector_id,
        name="Test API",
        provider="test",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-1",
        enabled=enabled,
    )


def test_register_and_invoke() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    adapter = FakeConnectorAdapter()
    engine.register(_descriptor(), adapter)

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="list_repos",
        parameters={"org": "mullu"},
    ))

    assert result.status is ConnectorStatus.SUCCEEDED
    assert len(adapter.invoked) == 1


def test_invoke_unregistered_connector_fails() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)

    result = engine.invoke(InvocationRequest(
        connector_id="nonexistent",
        operation="op",
        parameters={},
    ))

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "connector_not_registered"


def test_invoke_disabled_connector_fails() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(enabled=False), FakeConnectorAdapter())

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="op",
        parameters={},
    ))

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "connector_disabled"


def test_duplicate_registration_rejected() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor(), FakeConnectorAdapter())

    with pytest.raises(RuntimeCoreInvariantError, match="^connector already registered$") as exc_info:
        engine.register(_descriptor(), FakeConnectorAdapter())
    assert "conn-1" not in str(exc_info.value)


def test_list_connectors() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor("conn-a"), FakeConnectorAdapter())
    engine.register(_descriptor("conn-b", enabled=False), FakeConnectorAdapter())

    assert len(engine.list_connectors()) == 2
    assert len(engine.list_connectors(enabled_only=True)) == 1


def test_get_connector() -> None:
    engine = IntegrationEngine(clock=lambda: _CLOCK)
    engine.register(_descriptor("conn-1"), FakeConnectorAdapter())

    assert engine.get_connector("conn-1") is not None
    assert engine.get_connector("nonexistent") is None


def test_invoke_with_effect_assurance_reconciles_receipt() -> None:
    engine = IntegrationEngine(
        clock=lambda: _CLOCK,
        effect_assurance=EffectAssuranceGate(clock=lambda: _CLOCK),
    )
    adapter = FakeConnectorAdapter(include_receipt=True)
    engine.register(_descriptor(), adapter)

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="list_repos",
        parameters={"org": "mullu"},
    ))

    assurance = result.metadata["effect_assurance"]
    assert result.status is ConnectorStatus.SUCCEEDED
    assert assurance["reconciliation_status"] == "match"
    assert assurance["effect_plan_id"].startswith("effect-plan-")
    assert assurance["verification_result_id"].startswith("effect-verification-")


def test_invoke_with_effect_assurance_fails_without_receipt() -> None:
    engine = IntegrationEngine(
        clock=lambda: _CLOCK,
        effect_assurance=EffectAssuranceGate(clock=lambda: _CLOCK),
    )
    engine.register(_descriptor(), FakeConnectorAdapter())

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="list_repos",
        parameters={"org": "mullu"},
    ))

    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "effect_assurance_failed"
    assert "required for effect observation" in result.metadata["effect_assurance_error"]


def test_invoke_effect_mismatch_opens_case() -> None:
    case_runtime = CaseRuntimeEngine(EventSpineEngine(clock=lambda: _CLOCK))
    engine = IntegrationEngine(
        clock=lambda: _CLOCK,
        effect_assurance=MismatchEffectAssuranceGate(clock=lambda: _CLOCK),
        case_runtime=case_runtime,
    )
    engine.register(_descriptor(), FakeConnectorAdapter(include_receipt=True))

    result = engine.invoke(InvocationRequest(
        connector_id="conn-1",
        operation="list_repos",
        parameters={"org": "mullu"},
    ))

    assurance = result.metadata["effect_assurance"]
    assert result.status is ConnectorStatus.FAILED
    assert result.error_code == "effect_reconciliation_mismatch"
    assert assurance["reconciliation_status"] == "mismatch"
    assert assurance["case_id"].startswith("case-res-")
    assert case_runtime.open_case_count == 1
    assert case_runtime.evidence_count == 1
    assert case_runtime.finding_count == 1
