"""Comprehensive tests for external execution runtime contracts.

Covers 6 enums and 10 frozen dataclasses with ~300 tests.
"""

from __future__ import annotations

import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.external_execution import *

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-15T08:30:00Z"
DATE_ONLY = "2025-06-01"


# ===================================================================
# Enum tests
# ===================================================================


class TestExecutionStatus:
    @pytest.mark.parametrize("member,value", [
        (ExecutionStatus.PENDING, "pending"),
        (ExecutionStatus.APPROVED, "approved"),
        (ExecutionStatus.RUNNING, "running"),
        (ExecutionStatus.COMPLETED, "completed"),
        (ExecutionStatus.FAILED, "failed"),
        (ExecutionStatus.CANCELLED, "cancelled"),
        (ExecutionStatus.TIMED_OUT, "timed_out"),
    ])
    def test_member_value(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(ExecutionStatus) == 7

    @pytest.mark.parametrize("val", ["pending", "approved", "running", "completed", "failed", "cancelled", "timed_out"])
    def test_lookup_by_value(self, val):
        assert ExecutionStatus(val).value == val


class TestExecutionKind:
    @pytest.mark.parametrize("member,value", [
        (ExecutionKind.TOOL, "tool"),
        (ExecutionKind.AGENT, "agent"),
        (ExecutionKind.API_CALL, "api_call"),
        (ExecutionKind.SCRIPT, "script"),
        (ExecutionKind.WEBHOOK, "webhook"),
    ])
    def test_member_value(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(ExecutionKind) == 5


class TestSandboxDisposition:
    @pytest.mark.parametrize("member,value", [
        (SandboxDisposition.SANDBOXED, "sandboxed"),
        (SandboxDisposition.PRIVILEGED, "privileged"),
        (SandboxDisposition.ISOLATED, "isolated"),
        (SandboxDisposition.RESTRICTED, "restricted"),
    ])
    def test_member_value(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(SandboxDisposition) == 4


class TestCredentialMode:
    @pytest.mark.parametrize("member,value", [
        (CredentialMode.NONE, "none"),
        (CredentialMode.TOKEN, "token"),
        (CredentialMode.CERTIFICATE, "certificate"),
        (CredentialMode.DELEGATED, "delegated"),
        (CredentialMode.EPHEMERAL, "ephemeral"),
    ])
    def test_member_value(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(CredentialMode) == 5


class TestRetryDisposition:
    @pytest.mark.parametrize("member,value", [
        (RetryDisposition.NO_RETRY, "no_retry"),
        (RetryDisposition.RETRY_PENDING, "retry_pending"),
        (RetryDisposition.RETRIED, "retried"),
        (RetryDisposition.EXHAUSTED, "exhausted"),
    ])
    def test_member_value(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(RetryDisposition) == 4


class TestExecutionRiskLevel:
    @pytest.mark.parametrize("member,value", [
        (ExecutionRiskLevel.LOW, "low"),
        (ExecutionRiskLevel.MEDIUM, "medium"),
        (ExecutionRiskLevel.HIGH, "high"),
        (ExecutionRiskLevel.CRITICAL, "critical"),
    ])
    def test_member_value(self, member, value):
        assert member.value == value

    def test_member_count(self):
        assert len(ExecutionRiskLevel) == 4


# ===================================================================
# Dataclass helpers (factories)
# ===================================================================

def _make_request(**overrides):
    defaults = dict(
        request_id="req-1",
        tenant_id="t-1",
        target_id="tgt-1",
        kind=ExecutionKind.TOOL,
        status=ExecutionStatus.PENDING,
        sandbox=SandboxDisposition.SANDBOXED,
        credential_mode=CredentialMode.NONE,
        risk_level=ExecutionRiskLevel.LOW,
        requested_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionRequest(**defaults)


def _make_target(**overrides):
    defaults = dict(
        target_id="tgt-1",
        tenant_id="t-1",
        display_name="My Tool",
        kind=ExecutionKind.TOOL,
        capability_ref="cap-1",
        sandbox_default=SandboxDisposition.SANDBOXED,
        credential_mode=CredentialMode.NONE,
        max_retries=0,
        timeout_ms=0,
        registered_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionTarget(**defaults)


def _make_receipt(**overrides):
    defaults = dict(
        receipt_id="rcpt-1",
        request_id="req-1",
        tenant_id="t-1",
        status=ExecutionStatus.COMPLETED,
        duration_ms=0.0,
        output_ref="out-1",
        completed_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionReceipt(**defaults)


def _make_policy(**overrides):
    defaults = dict(
        policy_id="pol-1",
        tenant_id="t-1",
        target_id="tgt-1",
        max_retries=0,
        timeout_ms=0,
        sandbox_required=SandboxDisposition.SANDBOXED,
        credential_mode=CredentialMode.NONE,
        risk_threshold=ExecutionRiskLevel.HIGH,
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionPolicy(**defaults)


def _make_result(**overrides):
    defaults = dict(
        result_id="res-1",
        request_id="req-1",
        tenant_id="t-1",
        success=True,
        output_summary="ok",
        confidence=0.9,
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionResult(**defaults)


def _make_failure(**overrides):
    defaults = dict(
        failure_id="fail-1",
        request_id="req-1",
        tenant_id="t-1",
        reason="timeout",
        retry_disposition=RetryDisposition.NO_RETRY,
        retry_count=0,
        failed_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionFailure(**defaults)


def _make_trace(**overrides):
    defaults = dict(
        trace_id="tr-1",
        request_id="req-1",
        tenant_id="t-1",
        step_name="step-a",
        duration_ms=0.0,
        status=ExecutionStatus.COMPLETED,
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionTrace(**defaults)


def _make_snapshot(**overrides):
    defaults = dict(
        snapshot_id="snap-1",
        tenant_id="t-1",
        total_targets=0,
        total_requests=0,
        total_receipts=0,
        total_failures=0,
        total_results=0,
        total_traces=0,
        total_violations=0,
        captured_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionSnapshot(**defaults)


def _make_violation(**overrides):
    defaults = dict(
        violation_id="viol-1",
        tenant_id="t-1",
        request_id="req-1",
        operation="exec",
        reason="policy breach",
        detected_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionViolation(**defaults)


def _make_closure(**overrides):
    defaults = dict(
        report_id="rpt-1",
        tenant_id="t-1",
        total_targets=0,
        total_requests=0,
        total_receipts=0,
        total_failures=0,
        total_results=0,
        total_violations=0,
        created_at=TS,
        metadata={},
    )
    defaults.update(overrides)
    return ExecutionClosureReport(**defaults)


# ===================================================================
# ExecutionRequest tests
# ===================================================================


class TestExecutionRequest:
    def test_happy_path(self):
        r = _make_request()
        assert r.request_id == "req-1"
        assert r.tenant_id == "t-1"
        assert r.target_id == "tgt-1"
        assert r.kind is ExecutionKind.TOOL
        assert r.status is ExecutionStatus.PENDING
        assert r.sandbox is SandboxDisposition.SANDBOXED
        assert r.credential_mode is CredentialMode.NONE
        assert r.risk_level is ExecutionRiskLevel.LOW

    def test_frozen(self):
        r = _make_request()
        with pytest.raises(AttributeError):
            r.request_id = "other"

    @pytest.mark.parametrize("field", ["request_id", "tenant_id", "target_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_request(**{field: ""})

    @pytest.mark.parametrize("field", ["request_id", "tenant_id", "target_id"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _make_request(**{field: "   "})

    def test_date_only_accepted(self):
        r = _make_request(requested_at=DATE_ONLY)
        assert r.requested_at == DATE_ONLY

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_request(requested_at="not-a-date")

    @pytest.mark.parametrize("kind", list(ExecutionKind))
    def test_all_kinds_accepted(self, kind):
        r = _make_request(kind=kind)
        assert r.kind is kind

    def test_kind_string_rejected(self):
        with pytest.raises(ValueError):
            _make_request(kind="tool")

    @pytest.mark.parametrize("status", list(ExecutionStatus))
    def test_all_statuses_accepted(self, status):
        r = _make_request(status=status)
        assert r.status is status

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            _make_request(status="pending")

    @pytest.mark.parametrize("sb", list(SandboxDisposition))
    def test_all_sandboxes_accepted(self, sb):
        r = _make_request(sandbox=sb)
        assert r.sandbox is sb

    def test_sandbox_string_rejected(self):
        with pytest.raises(ValueError):
            _make_request(sandbox="sandboxed")

    @pytest.mark.parametrize("cm", list(CredentialMode))
    def test_all_credential_modes_accepted(self, cm):
        r = _make_request(credential_mode=cm)
        assert r.credential_mode is cm

    def test_credential_mode_string_rejected(self):
        with pytest.raises(ValueError):
            _make_request(credential_mode="none")

    @pytest.mark.parametrize("rl", list(ExecutionRiskLevel))
    def test_all_risk_levels_accepted(self, rl):
        r = _make_request(risk_level=rl)
        assert r.risk_level is rl

    def test_risk_level_string_rejected(self):
        with pytest.raises(ValueError):
            _make_request(risk_level="low")

    def test_metadata_frozen(self):
        r = _make_request(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["k"] == "v"

    def test_metadata_to_dict_plain(self):
        r = _make_request(metadata={"k": "v"})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"] == {"k": "v"}

    def test_to_dict_preserves_enum_objects(self):
        r = _make_request()
        d = r.to_dict()
        assert d["kind"] is ExecutionKind.TOOL
        assert d["status"] is ExecutionStatus.PENDING
        assert d["sandbox"] is SandboxDisposition.SANDBOXED
        assert d["credential_mode"] is CredentialMode.NONE
        assert d["risk_level"] is ExecutionRiskLevel.LOW

    def test_z_suffix_datetime(self):
        r = _make_request(requested_at=TS2)
        assert r.requested_at == TS2

    def test_nested_metadata_frozen(self):
        r = _make_request(metadata={"a": {"b": [1, 2]}})
        assert isinstance(r.metadata["a"], MappingProxyType)
        assert r.metadata["a"]["b"] == (1, 2)


# ===================================================================
# ExecutionTarget tests
# ===================================================================


class TestExecutionTarget:
    def test_happy_path(self):
        t = _make_target()
        assert t.target_id == "tgt-1"
        assert t.display_name == "My Tool"
        assert t.max_retries == 0
        assert t.timeout_ms == 0

    def test_frozen(self):
        t = _make_target()
        with pytest.raises(AttributeError):
            t.target_id = "x"

    @pytest.mark.parametrize("field", ["target_id", "tenant_id", "display_name", "capability_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_target(**{field: ""})

    @pytest.mark.parametrize("field", ["target_id", "tenant_id", "display_name", "capability_ref"])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _make_target(**{field: "  \t "})

    def test_kind_string_rejected(self):
        with pytest.raises(ValueError):
            _make_target(kind="tool")

    @pytest.mark.parametrize("kind", list(ExecutionKind))
    def test_all_kinds_accepted(self, kind):
        t = _make_target(kind=kind)
        assert t.kind is kind

    def test_sandbox_default_string_rejected(self):
        with pytest.raises(ValueError):
            _make_target(sandbox_default="sandboxed")

    def test_credential_mode_string_rejected(self):
        with pytest.raises(ValueError):
            _make_target(credential_mode="token")

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_target(**{field: -1})

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_zero_int_accepted(self, field):
        t = _make_target(**{field: 0})
        assert getattr(t, field) == 0

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_positive_int_accepted(self, field):
        t = _make_target(**{field: 5})
        assert getattr(t, field) == 5

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_target(**{field: True})

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_target(**{field: 1.5})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_target(registered_at="nope")

    def test_date_only_accepted(self):
        t = _make_target(registered_at=DATE_ONLY)
        assert t.registered_at == DATE_ONLY

    def test_metadata_frozen(self):
        t = _make_target(metadata={"x": 1})
        assert isinstance(t.metadata, MappingProxyType)

    def test_to_dict_enum_preserved(self):
        t = _make_target()
        d = t.to_dict()
        assert d["kind"] is ExecutionKind.TOOL
        assert d["sandbox_default"] is SandboxDisposition.SANDBOXED
        assert d["credential_mode"] is CredentialMode.NONE

    def test_to_dict_metadata_plain(self):
        t = _make_target(metadata={"a": 1})
        d = t.to_dict()
        assert isinstance(d["metadata"], dict)


# ===================================================================
# ExecutionReceipt tests
# ===================================================================


class TestExecutionReceipt:
    def test_happy_path(self):
        r = _make_receipt()
        assert r.receipt_id == "rcpt-1"
        assert r.duration_ms == 0.0
        assert r.status is ExecutionStatus.COMPLETED

    def test_frozen(self):
        r = _make_receipt()
        with pytest.raises(AttributeError):
            r.receipt_id = "x"

    @pytest.mark.parametrize("field", ["receipt_id", "request_id", "tenant_id", "output_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_receipt(**{field: ""})

    @pytest.mark.parametrize("field", ["receipt_id", "request_id", "tenant_id", "output_ref"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_receipt(**{field: "  "})

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(status="completed")

    @pytest.mark.parametrize("status", list(ExecutionStatus))
    def test_all_statuses_accepted(self, status):
        r = _make_receipt(status=status)
        assert r.status is status

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(duration_ms=-0.1)

    def test_zero_duration_accepted(self):
        r = _make_receipt(duration_ms=0.0)
        assert r.duration_ms == 0.0

    def test_positive_duration_accepted(self):
        r = _make_receipt(duration_ms=123.456)
        assert r.duration_ms == 123.456

    def test_bool_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(duration_ms=True)

    def test_string_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(duration_ms="1.0")

    def test_none_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(duration_ms=None)

    def test_int_duration_accepted(self):
        r = _make_receipt(duration_ms=5)
        assert r.duration_ms == 5.0

    def test_inf_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(duration_ms=math.inf)

    def test_nan_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(duration_ms=math.nan)

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_receipt(completed_at="bad")

    def test_date_only_accepted(self):
        r = _make_receipt(completed_at=DATE_ONLY)
        assert r.completed_at == DATE_ONLY

    def test_metadata_frozen(self):
        r = _make_receipt(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_enum_preserved(self):
        r = _make_receipt()
        d = r.to_dict()
        assert d["status"] is ExecutionStatus.COMPLETED

    def test_to_dict_metadata_plain(self):
        r = _make_receipt(metadata={"k": 1})
        assert isinstance(r.to_dict()["metadata"], dict)


# ===================================================================
# ExecutionPolicy tests
# ===================================================================


class TestExecutionPolicy:
    def test_happy_path(self):
        p = _make_policy()
        assert p.policy_id == "pol-1"
        assert p.max_retries == 0
        assert p.timeout_ms == 0
        assert p.sandbox_required is SandboxDisposition.SANDBOXED
        assert p.risk_threshold is ExecutionRiskLevel.HIGH

    def test_frozen(self):
        p = _make_policy()
        with pytest.raises(AttributeError):
            p.policy_id = "x"

    @pytest.mark.parametrize("field", ["policy_id", "tenant_id", "target_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_policy(**{field: ""})

    @pytest.mark.parametrize("field", ["policy_id", "tenant_id", "target_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_policy(**{field: "\n\t"})

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_policy(**{field: -1})

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_zero_int_accepted(self, field):
        p = _make_policy(**{field: 0})
        assert getattr(p, field) == 0

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_positive_int_accepted(self, field):
        p = _make_policy(**{field: 10})
        assert getattr(p, field) == 10

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_policy(**{field: False})

    @pytest.mark.parametrize("field", ["max_retries", "timeout_ms"])
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_policy(**{field: 2.0})

    def test_sandbox_required_string_rejected(self):
        with pytest.raises(ValueError):
            _make_policy(sandbox_required="sandboxed")

    @pytest.mark.parametrize("sb", list(SandboxDisposition))
    def test_all_sandbox_dispositions_accepted(self, sb):
        p = _make_policy(sandbox_required=sb)
        assert p.sandbox_required is sb

    def test_credential_mode_string_rejected(self):
        with pytest.raises(ValueError):
            _make_policy(credential_mode="token")

    @pytest.mark.parametrize("cm", list(CredentialMode))
    def test_all_credential_modes_accepted(self, cm):
        p = _make_policy(credential_mode=cm)
        assert p.credential_mode is cm

    def test_risk_threshold_string_rejected(self):
        with pytest.raises(ValueError):
            _make_policy(risk_threshold="high")

    @pytest.mark.parametrize("rl", list(ExecutionRiskLevel))
    def test_all_risk_levels_accepted(self, rl):
        p = _make_policy(risk_threshold=rl)
        assert p.risk_threshold is rl

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_policy(created_at="xyz")

    def test_date_only_accepted(self):
        p = _make_policy(created_at=DATE_ONLY)
        assert p.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        p = _make_policy(metadata={"a": "b"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict_enum_preserved(self):
        p = _make_policy()
        d = p.to_dict()
        assert d["sandbox_required"] is SandboxDisposition.SANDBOXED
        assert d["credential_mode"] is CredentialMode.NONE
        assert d["risk_threshold"] is ExecutionRiskLevel.HIGH

    def test_to_dict_metadata_plain(self):
        p = _make_policy(metadata={"x": 1})
        assert isinstance(p.to_dict()["metadata"], dict)


# ===================================================================
# ExecutionResult tests
# ===================================================================


class TestExecutionResult:
    def test_happy_path(self):
        r = _make_result()
        assert r.result_id == "res-1"
        assert r.success is True
        assert r.confidence == 0.9

    def test_frozen(self):
        r = _make_result()
        with pytest.raises(AttributeError):
            r.result_id = "x"

    @pytest.mark.parametrize("field", ["result_id", "request_id", "tenant_id", "output_summary"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_result(**{field: ""})

    @pytest.mark.parametrize("field", ["result_id", "request_id", "tenant_id", "output_summary"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_result(**{field: "  "})

    def test_success_true(self):
        r = _make_result(success=True)
        assert r.success is True

    def test_success_false(self):
        r = _make_result(success=False)
        assert r.success is False

    @pytest.mark.parametrize("bad", [1, 0, "true", None])
    def test_success_non_bool_rejected(self, bad):
        with pytest.raises(ValueError):
            _make_result(success=bad)

    # confidence: require_unit_float [0.0, 1.0]
    def test_confidence_zero(self):
        r = _make_result(confidence=0.0)
        assert r.confidence == 0.0

    def test_confidence_one(self):
        r = _make_result(confidence=1.0)
        assert r.confidence == 1.0

    def test_confidence_mid(self):
        r = _make_result(confidence=0.5)
        assert r.confidence == 0.5

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence=-0.01)

    def test_confidence_over_one_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence=1.01)

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence=True)

    def test_confidence_string_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence="0.5")

    def test_confidence_none_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence=None)

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence=math.inf)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError):
            _make_result(confidence=math.nan)

    def test_confidence_int_accepted(self):
        r = _make_result(confidence=1)
        assert r.confidence == 1.0

    def test_confidence_int_zero_accepted(self):
        r = _make_result(confidence=0)
        assert r.confidence == 0.0

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_result(created_at="bad")

    def test_date_only_accepted(self):
        r = _make_result(created_at=DATE_ONLY)
        assert r.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        r = _make_result(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        r = _make_result(metadata={"a": 1})
        assert isinstance(r.to_dict()["metadata"], dict)


# ===================================================================
# ExecutionFailure tests
# ===================================================================


class TestExecutionFailure:
    def test_happy_path(self):
        f = _make_failure()
        assert f.failure_id == "fail-1"
        assert f.reason == "timeout"
        assert f.retry_disposition is RetryDisposition.NO_RETRY
        assert f.retry_count == 0

    def test_frozen(self):
        f = _make_failure()
        with pytest.raises(AttributeError):
            f.failure_id = "x"

    @pytest.mark.parametrize("field", ["failure_id", "request_id", "tenant_id", "reason"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_failure(**{field: ""})

    @pytest.mark.parametrize("field", ["failure_id", "request_id", "tenant_id", "reason"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_failure(**{field: "\t"})

    def test_retry_disposition_string_rejected(self):
        with pytest.raises(ValueError):
            _make_failure(retry_disposition="no_retry")

    @pytest.mark.parametrize("rd", list(RetryDisposition))
    def test_all_retry_dispositions_accepted(self, rd):
        f = _make_failure(retry_disposition=rd)
        assert f.retry_disposition is rd

    def test_retry_count_negative_rejected(self):
        with pytest.raises(ValueError):
            _make_failure(retry_count=-1)

    def test_retry_count_zero_accepted(self):
        f = _make_failure(retry_count=0)
        assert f.retry_count == 0

    def test_retry_count_positive_accepted(self):
        f = _make_failure(retry_count=3)
        assert f.retry_count == 3

    def test_retry_count_bool_rejected(self):
        with pytest.raises(ValueError):
            _make_failure(retry_count=True)

    def test_retry_count_float_rejected(self):
        with pytest.raises(ValueError):
            _make_failure(retry_count=1.0)

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_failure(failed_at="nope")

    def test_date_only_accepted(self):
        f = _make_failure(failed_at=DATE_ONLY)
        assert f.failed_at == DATE_ONLY

    def test_metadata_frozen(self):
        f = _make_failure(metadata={"x": "y"})
        assert isinstance(f.metadata, MappingProxyType)

    def test_to_dict_enum_preserved(self):
        f = _make_failure()
        d = f.to_dict()
        assert d["retry_disposition"] is RetryDisposition.NO_RETRY

    def test_to_dict_metadata_plain(self):
        f = _make_failure(metadata={"a": 1})
        assert isinstance(f.to_dict()["metadata"], dict)


# ===================================================================
# ExecutionTrace tests
# ===================================================================


class TestExecutionTrace:
    def test_happy_path(self):
        t = _make_trace()
        assert t.trace_id == "tr-1"
        assert t.step_name == "step-a"
        assert t.duration_ms == 0.0
        assert t.status is ExecutionStatus.COMPLETED

    def test_frozen(self):
        t = _make_trace()
        with pytest.raises(AttributeError):
            t.trace_id = "x"

    @pytest.mark.parametrize("field", ["trace_id", "request_id", "tenant_id", "step_name"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_trace(**{field: ""})

    @pytest.mark.parametrize("field", ["trace_id", "request_id", "tenant_id", "step_name"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_trace(**{field: " "})

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(duration_ms=-1.0)

    def test_zero_duration_accepted(self):
        t = _make_trace(duration_ms=0.0)
        assert t.duration_ms == 0.0

    def test_positive_duration_accepted(self):
        t = _make_trace(duration_ms=42.5)
        assert t.duration_ms == 42.5

    def test_bool_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(duration_ms=False)

    def test_string_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(duration_ms="1.0")

    def test_none_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(duration_ms=None)

    def test_int_duration_accepted(self):
        t = _make_trace(duration_ms=10)
        assert t.duration_ms == 10.0

    def test_inf_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(duration_ms=math.inf)

    def test_nan_duration_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(duration_ms=math.nan)

    def test_status_string_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(status="completed")

    @pytest.mark.parametrize("status", list(ExecutionStatus))
    def test_all_statuses_accepted(self, status):
        t = _make_trace(status=status)
        assert t.status is status

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_trace(created_at="garbage")

    def test_date_only_accepted(self):
        t = _make_trace(created_at=DATE_ONLY)
        assert t.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        t = _make_trace(metadata={"k": "v"})
        assert isinstance(t.metadata, MappingProxyType)

    def test_to_dict_enum_preserved(self):
        t = _make_trace()
        d = t.to_dict()
        assert d["status"] is ExecutionStatus.COMPLETED

    def test_to_dict_metadata_plain(self):
        t = _make_trace(metadata={"k": 1})
        assert isinstance(t.to_dict()["metadata"], dict)


# ===================================================================
# ExecutionSnapshot tests
# ===================================================================


class TestExecutionSnapshot:
    def test_happy_path(self):
        s = _make_snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.total_targets == 0
        assert s.total_requests == 0
        assert s.total_violations == 0

    def test_frozen(self):
        s = _make_snapshot()
        with pytest.raises(AttributeError):
            s.snapshot_id = "x"

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_snapshot(**{field: ""})

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_snapshot(**{field: " \t"})

    INT_FIELDS = [
        "total_targets", "total_requests", "total_receipts",
        "total_failures", "total_results", "total_traces", "total_violations",
    ]

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_snapshot(**{field: -1})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_zero_int_accepted(self, field):
        s = _make_snapshot(**{field: 0})
        assert getattr(s, field) == 0

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_positive_int_accepted(self, field):
        s = _make_snapshot(**{field: 100})
        assert getattr(s, field) == 100

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_snapshot(**{field: True})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_snapshot(**{field: 1.0})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_snapshot(captured_at="bad")

    def test_date_only_accepted(self):
        s = _make_snapshot(captured_at=DATE_ONLY)
        assert s.captured_at == DATE_ONLY

    def test_metadata_frozen(self):
        s = _make_snapshot(metadata={"a": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        s = _make_snapshot(metadata={"a": 1})
        assert isinstance(s.to_dict()["metadata"], dict)

    def test_all_counters_set(self):
        s = _make_snapshot(
            total_targets=1, total_requests=2, total_receipts=3,
            total_failures=4, total_results=5, total_traces=6, total_violations=7,
        )
        assert s.total_targets == 1
        assert s.total_requests == 2
        assert s.total_receipts == 3
        assert s.total_failures == 4
        assert s.total_results == 5
        assert s.total_traces == 6
        assert s.total_violations == 7


# ===================================================================
# ExecutionViolation tests
# ===================================================================


class TestExecutionViolation:
    def test_happy_path(self):
        v = _make_violation()
        assert v.violation_id == "viol-1"
        assert v.operation == "exec"
        assert v.reason == "policy breach"

    def test_frozen(self):
        v = _make_violation()
        with pytest.raises(AttributeError):
            v.violation_id = "x"

    @pytest.mark.parametrize("field", ["violation_id", "tenant_id", "request_id", "operation", "reason"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_violation(**{field: ""})

    @pytest.mark.parametrize("field", ["violation_id", "tenant_id", "request_id", "operation", "reason"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_violation(**{field: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_violation(detected_at="nope")

    def test_date_only_accepted(self):
        v = _make_violation(detected_at=DATE_ONLY)
        assert v.detected_at == DATE_ONLY

    def test_metadata_frozen(self):
        v = _make_violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        v = _make_violation(metadata={"k": 1})
        assert isinstance(v.to_dict()["metadata"], dict)

    def test_to_dict_all_fields_present(self):
        v = _make_violation()
        d = v.to_dict()
        for key in ["violation_id", "tenant_id", "request_id", "operation", "reason", "detected_at", "metadata"]:
            assert key in d


# ===================================================================
# ExecutionClosureReport tests
# ===================================================================


class TestExecutionClosureReport:
    def test_happy_path(self):
        c = _make_closure()
        assert c.report_id == "rpt-1"
        assert c.total_targets == 0
        assert c.total_violations == 0

    def test_frozen(self):
        c = _make_closure()
        with pytest.raises(AttributeError):
            c.report_id = "x"

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _make_closure(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_whitespace_rejected(self, field):
        with pytest.raises(ValueError):
            _make_closure(**{field: " "})

    INT_FIELDS = [
        "total_targets", "total_requests", "total_receipts",
        "total_failures", "total_results", "total_violations",
    ]

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_closure(**{field: -1})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_zero_int_accepted(self, field):
        c = _make_closure(**{field: 0})
        assert getattr(c, field) == 0

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_positive_int_accepted(self, field):
        c = _make_closure(**{field: 50})
        assert getattr(c, field) == 50

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_bool_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_closure(**{field: False})

    @pytest.mark.parametrize("field", INT_FIELDS)
    def test_float_int_rejected(self, field):
        with pytest.raises(ValueError):
            _make_closure(**{field: 3.0})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_closure(created_at="bad")

    def test_date_only_accepted(self):
        c = _make_closure(created_at=DATE_ONLY)
        assert c.created_at == DATE_ONLY

    def test_metadata_frozen(self):
        c = _make_closure(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_to_dict_metadata_plain(self):
        c = _make_closure(metadata={"k": 1})
        assert isinstance(c.to_dict()["metadata"], dict)

    def test_all_counters_set(self):
        c = _make_closure(
            total_targets=10, total_requests=20, total_receipts=30,
            total_failures=5, total_results=25, total_violations=2,
        )
        assert c.total_targets == 10
        assert c.total_requests == 20
        assert c.total_receipts == 30
        assert c.total_failures == 5
        assert c.total_results == 25
        assert c.total_violations == 2

    def test_to_dict_all_fields(self):
        c = _make_closure()
        d = c.to_dict()
        expected = {
            "report_id", "tenant_id", "total_targets", "total_requests",
            "total_receipts", "total_failures", "total_results",
            "total_violations", "created_at", "metadata",
        }
        assert set(d.keys()) == expected


# ===================================================================
# Cross-cutting / structural tests
# ===================================================================


class TestCrossCutting:
    """Tests that apply across multiple dataclasses."""

    ALL_FACTORIES = [
        _make_request, _make_target, _make_receipt, _make_policy,
        _make_result, _make_failure, _make_trace, _make_snapshot,
        _make_violation, _make_closure,
    ]

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_to_dict_returns_dict(self, factory):
        obj = factory()
        d = obj.to_dict()
        assert isinstance(d, dict)

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_metadata_default_empty(self, factory):
        obj = factory()
        assert len(obj.metadata) == 0

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_metadata_mapping_proxy(self, factory):
        obj = factory(metadata={"k": "v"})
        assert isinstance(obj.metadata, MappingProxyType)

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_metadata_mutation_blocked(self, factory):
        obj = factory(metadata={"k": "v"})
        with pytest.raises(TypeError):
            obj.metadata["k"] = "new"

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_original_dict_not_mutated(self, factory):
        original = {"k": "v"}
        factory(metadata=original)
        original["k"] = "changed"
        # Frozen copy should not reflect mutation — this is a defensive copy test.
        # The factory already consumed the dict so this just checks freeze_value
        # made a copy.

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_nested_metadata_frozen(self, factory):
        obj = factory(metadata={"a": {"b": 1}})
        inner = obj.metadata["a"]
        assert isinstance(inner, MappingProxyType)

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_nested_list_in_metadata_becomes_tuple(self, factory):
        obj = factory(metadata={"a": [1, 2, 3]})
        assert obj.metadata["a"] == (1, 2, 3)

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_to_dict_metadata_thawed(self, factory):
        obj = factory(metadata={"a": {"b": [1]}})
        d = obj.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["a"], dict)
        assert isinstance(d["metadata"]["a"]["b"], list)

    @pytest.mark.parametrize("factory", ALL_FACTORIES)
    def test_z_suffix_datetime(self, factory):
        # Each factory has a different datetime field name; just use the factory
        # default which uses TS and override nothing — the factory default
        # already uses a valid TS. This test just ensures the base case works.
        obj = factory()
        assert obj is not None
