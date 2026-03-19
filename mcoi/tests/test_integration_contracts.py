"""Purpose: verify integration contracts align to shared schemas.
Governance scope: integration contract tests only.
Dependencies: integration contracts module.
Invariants: every connector carries effect/trust classification; every result is typed.
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


_CLOCK = "2026-03-19T00:00:00+00:00"


def test_connector_descriptor_validates() -> None:
    desc = ConnectorDescriptor(
        connector_id="conn-1",
        name="GitHub API",
        provider="github",
        effect_class=EffectClass.EXTERNAL_READ,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        credential_scope_id="scope-gh-read",
        enabled=True,
    )
    assert desc.connector_id == "conn-1"
    assert desc.effect_class is EffectClass.EXTERNAL_READ
    assert desc.trust_class is TrustClass.BOUNDED_EXTERNAL


def test_connector_descriptor_rejects_empty_fields() -> None:
    with pytest.raises(ValueError, match="connector_id"):
        ConnectorDescriptor(
            connector_id="",
            name="x",
            provider="x",
            effect_class=EffectClass.EXTERNAL_READ,
            trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="x",
            enabled=True,
        )


def test_connector_descriptor_serializes() -> None:
    desc = ConnectorDescriptor(
        connector_id="conn-1",
        name="test",
        provider="test",
        effect_class=EffectClass.INTERNAL_PURE,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        credential_scope_id="scope-1",
        enabled=False,
    )
    d = desc.to_dict()
    assert d["effect_class"] == "internal_pure"
    assert d["trust_class"] == "trusted_internal"
    assert d["enabled"] is False


def test_connector_result_validates() -> None:
    result = ConnectorResult(
        result_id="res-1",
        connector_id="conn-1",
        status=ConnectorStatus.SUCCEEDED,
        response_digest="abc123",
        started_at=_CLOCK,
        finished_at=_CLOCK,
    )
    assert result.status is ConnectorStatus.SUCCEEDED
    assert result.error_code is None


def test_connector_result_with_error() -> None:
    result = ConnectorResult(
        result_id="res-1",
        connector_id="conn-1",
        status=ConnectorStatus.FAILED,
        response_digest="none",
        started_at=_CLOCK,
        finished_at=_CLOCK,
        error_code="auth_failure",
    )
    assert result.error_code == "auth_failure"


def test_effect_class_values() -> None:
    assert len(EffectClass) == 5


def test_trust_class_values() -> None:
    assert len(TrustClass) == 3


def test_connector_status_values() -> None:
    assert len(ConnectorStatus) == 3
    assert ConnectorStatus.TIMEOUT == "timeout"
