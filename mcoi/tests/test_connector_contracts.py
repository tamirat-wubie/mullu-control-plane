"""Tests for connector contracts (connector_descriptor + connector_result)."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts._shared_enums import EffectClass, TrustClass
from mcoi_runtime.contracts.connector import (
    ConnectorDescriptor,
    ConnectorResult,
    ConnectorStatus,
)

NOW = "2025-01-01T00:00:00Z"
LATER = "2025-01-01T00:01:00Z"


# ---------------------------------------------------------------------------
# ConnectorDescriptor
# ---------------------------------------------------------------------------


class TestConnectorDescriptor:

    def test_valid_construction(self):
        cd = ConnectorDescriptor(
            connector_id="c1",
            name="GitHub API",
            provider="github",
            effect_class=EffectClass.EXTERNAL_READ,
            trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="scope-gh",
            enabled=True,
        )
        assert cd.connector_id == "c1"
        assert cd.name == "GitHub API"
        assert cd.provider == "github"
        assert cd.effect_class == EffectClass.EXTERNAL_READ
        assert cd.trust_class == TrustClass.BOUNDED_EXTERNAL
        assert cd.enabled is True

    def test_with_metadata(self):
        cd = ConnectorDescriptor(
            connector_id="c2",
            name="Slack",
            provider="slack",
            effect_class=EffectClass.EXTERNAL_WRITE,
            trust_class=TrustClass.BOUNDED_EXTERNAL,
            credential_scope_id="scope-slack",
            enabled=False,
            metadata={"region": "us-east-1"},
        )
        assert cd.metadata["region"] == "us-east-1"
        # Metadata is frozen
        with pytest.raises(TypeError):
            cd.metadata["new"] = "fail"  # type: ignore[index]

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            ConnectorDescriptor(
                connector_id="",
                name="test",
                provider="test",
                effect_class=EffectClass.INTERNAL_PURE,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                credential_scope_id="s1",
                enabled=True,
            )

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            ConnectorDescriptor(
                connector_id="c1",
                name="",
                provider="test",
                effect_class=EffectClass.INTERNAL_PURE,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                credential_scope_id="s1",
                enabled=True,
            )

    def test_empty_provider_rejected(self):
        with pytest.raises(ValueError):
            ConnectorDescriptor(
                connector_id="c1",
                name="test",
                provider="",
                effect_class=EffectClass.INTERNAL_PURE,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                credential_scope_id="s1",
                enabled=True,
            )

    def test_invalid_effect_class_rejected(self):
        with pytest.raises(ValueError):
            ConnectorDescriptor(
                connector_id="c1",
                name="test",
                provider="test",
                effect_class="invalid",  # type: ignore
                trust_class=TrustClass.TRUSTED_INTERNAL,
                credential_scope_id="s1",
                enabled=True,
            )

    def test_invalid_trust_class_rejected(self):
        with pytest.raises(ValueError):
            ConnectorDescriptor(
                connector_id="c1",
                name="test",
                provider="test",
                effect_class=EffectClass.INTERNAL_PURE,
                trust_class="invalid",  # type: ignore
                credential_scope_id="s1",
                enabled=True,
            )

    def test_non_boolean_enabled_rejected(self):
        with pytest.raises(ValueError):
            ConnectorDescriptor(
                connector_id="c1",
                name="test",
                provider="test",
                effect_class=EffectClass.INTERNAL_PURE,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                credential_scope_id="s1",
                enabled=1,  # type: ignore
            )

    def test_serialization_round_trip(self):
        cd = ConnectorDescriptor(
            connector_id="c1",
            name="test",
            provider="test-provider",
            effect_class=EffectClass.EXTERNAL_WRITE,
            trust_class=TrustClass.UNTRUSTED_EXTERNAL,
            credential_scope_id="scope-1",
            enabled=True,
        )
        d = cd.to_dict()
        assert d["connector_id"] == "c1"
        assert d["effect_class"] == "external_write"
        assert d["trust_class"] == "untrusted_external"
        assert d["enabled"] is True

    def test_all_effect_classes(self):
        for ec in EffectClass:
            cd = ConnectorDescriptor(
                connector_id=f"c-{ec.value}",
                name=ec.value,
                provider="test",
                effect_class=ec,
                trust_class=TrustClass.TRUSTED_INTERNAL,
                credential_scope_id="s1",
                enabled=True,
            )
            assert cd.effect_class == ec

    def test_all_trust_classes(self):
        for tc in TrustClass:
            cd = ConnectorDescriptor(
                connector_id=f"c-{tc.value}",
                name=tc.value,
                provider="test",
                effect_class=EffectClass.INTERNAL_PURE,
                trust_class=tc,
                credential_scope_id="s1",
                enabled=True,
            )
            assert cd.trust_class == tc

    def test_frozen(self):
        cd = ConnectorDescriptor(
            connector_id="c1",
            name="test",
            provider="test",
            effect_class=EffectClass.INTERNAL_PURE,
            trust_class=TrustClass.TRUSTED_INTERNAL,
            credential_scope_id="s1",
            enabled=True,
        )
        with pytest.raises(AttributeError):
            cd.name = "changed"  # type: ignore


# ---------------------------------------------------------------------------
# ConnectorResult
# ---------------------------------------------------------------------------


class TestConnectorResult:

    def test_valid_construction(self):
        cr = ConnectorResult(
            result_id="r1",
            connector_id="c1",
            status=ConnectorStatus.SUCCEEDED,
            response_digest="sha256:abc123",
            started_at=NOW,
            finished_at=LATER,
        )
        assert cr.result_id == "r1"
        assert cr.status == ConnectorStatus.SUCCEEDED
        assert cr.error_code is None

    def test_failed_with_error_code(self):
        cr = ConnectorResult(
            result_id="r2",
            connector_id="c1",
            status=ConnectorStatus.FAILED,
            response_digest="sha256:def456",
            started_at=NOW,
            finished_at=LATER,
            error_code="ECONNREFUSED",
        )
        assert cr.status == ConnectorStatus.FAILED
        assert cr.error_code == "ECONNREFUSED"

    def test_timeout_status(self):
        cr = ConnectorResult(
            result_id="r3",
            connector_id="c1",
            status=ConnectorStatus.TIMEOUT,
            response_digest="sha256:timeout",
            started_at=NOW,
            finished_at=LATER,
        )
        assert cr.status == ConnectorStatus.TIMEOUT

    def test_empty_result_id_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="",
                connector_id="c1",
                status=ConnectorStatus.SUCCEEDED,
                response_digest="sha256:abc",
                started_at=NOW,
                finished_at=LATER,
            )

    def test_empty_connector_id_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="r1",
                connector_id="",
                status=ConnectorStatus.SUCCEEDED,
                response_digest="sha256:abc",
                started_at=NOW,
                finished_at=LATER,
            )

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="r1",
                connector_id="c1",
                status="invalid",  # type: ignore
                response_digest="sha256:abc",
                started_at=NOW,
                finished_at=LATER,
            )

    def test_empty_response_digest_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="r1",
                connector_id="c1",
                status=ConnectorStatus.SUCCEEDED,
                response_digest="",
                started_at=NOW,
                finished_at=LATER,
            )

    def test_invalid_started_at_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="r1",
                connector_id="c1",
                status=ConnectorStatus.SUCCEEDED,
                response_digest="sha256:abc",
                started_at="not-a-date",
                finished_at=LATER,
            )

    def test_invalid_finished_at_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="r1",
                connector_id="c1",
                status=ConnectorStatus.SUCCEEDED,
                response_digest="sha256:abc",
                started_at=NOW,
                finished_at="not-a-date",
            )

    def test_whitespace_error_code_rejected(self):
        with pytest.raises(ValueError):
            ConnectorResult(
                result_id="r1",
                connector_id="c1",
                status=ConnectorStatus.FAILED,
                response_digest="sha256:abc",
                started_at=NOW,
                finished_at=LATER,
                error_code="   ",
            )

    def test_serialization_round_trip(self):
        cr = ConnectorResult(
            result_id="r1",
            connector_id="c1",
            status=ConnectorStatus.SUCCEEDED,
            response_digest="sha256:abc123",
            started_at=NOW,
            finished_at=LATER,
            metadata={"latency_ms": 42},
        )
        d = cr.to_dict()
        assert d["result_id"] == "r1"
        assert d["status"] == "succeeded"
        assert d["metadata"]["latency_ms"] == 42

    def test_metadata_frozen(self):
        cr = ConnectorResult(
            result_id="r1",
            connector_id="c1",
            status=ConnectorStatus.SUCCEEDED,
            response_digest="sha256:abc",
            started_at=NOW,
            finished_at=LATER,
            metadata={"key": "value"},
        )
        with pytest.raises(TypeError):
            cr.metadata["new"] = "fail"  # type: ignore[index]

    def test_frozen(self):
        cr = ConnectorResult(
            result_id="r1",
            connector_id="c1",
            status=ConnectorStatus.SUCCEEDED,
            response_digest="sha256:abc",
            started_at=NOW,
            finished_at=LATER,
        )
        with pytest.raises(AttributeError):
            cr.status = ConnectorStatus.FAILED  # type: ignore
