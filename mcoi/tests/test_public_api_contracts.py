"""Comprehensive tests for mcoi_runtime.contracts.public_api module.

Covers all 6 enums and 10 frozen dataclasses with ~300 tests:
  - Enum member counts, values, and lookup
  - Valid construction of all dataclasses
  - Frozen immutability (FrozenInstanceError)
  - Metadata stored as MappingProxyType
  - to_dict() preserving enum objects
  - Empty string rejection for text fields
  - Invalid datetime rejection
  - Non-negative int validation
  - Unit float validation (availability_score, error_rate)
  - Parametrized boundary tests
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.public_api import (
    ApiAssessment,
    ApiClosureReport,
    ApiErrorRecord,
    ApiRequest,
    ApiResponse,
    ApiSnapshot,
    ApiStatus,
    ApiVisibility,
    ApiViolation,
    AuthDisposition,
    EndpointDescriptor,
    EndpointKind,
    IdempotencyRecord,
    RateLimitDisposition,
    RateLimitRecord,
    RequestDisposition,
)

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

DT = "2025-06-01"
DT2 = "2025-07-15T10:30:00Z"


def _make_api_request(**overrides):
    defaults = dict(
        request_id="req-1",
        tenant_id="t-1",
        endpoint_id="ep-1",
        caller_ref="caller-1",
        disposition=RequestDisposition.ACCEPTED,
        auth_disposition=AuthDisposition.AUTHENTICATED,
        idempotency_key="ik-1",
        received_at=DT,
    )
    defaults.update(overrides)
    return ApiRequest(**defaults)


def _make_api_response(**overrides):
    defaults = dict(
        response_id="resp-1",
        request_id="req-1",
        tenant_id="t-1",
        status_code=200,
        disposition=RequestDisposition.ACCEPTED,
        payload_ref="payload-1",
        responded_at=DT,
    )
    defaults.update(overrides)
    return ApiResponse(**defaults)


def _make_endpoint_descriptor(**overrides):
    defaults = dict(
        endpoint_id="ep-1",
        tenant_id="t-1",
        path="/api/v1/foo",
        kind=EndpointKind.READ,
        visibility=ApiVisibility.PUBLIC,
        status=ApiStatus.ACTIVE,
        target_runtime="runtime-1",
        target_action="action-1",
        created_at=DT,
    )
    defaults.update(overrides)
    return EndpointDescriptor(**defaults)


def _make_api_error_record(**overrides):
    defaults = dict(
        error_id="err-1",
        request_id="req-1",
        tenant_id="t-1",
        error_code="E001",
        error_message="Something went wrong",
        status_code=500,
        created_at=DT,
    )
    defaults.update(overrides)
    return ApiErrorRecord(**defaults)


def _make_rate_limit_record(**overrides):
    defaults = dict(
        limit_id="lim-1",
        tenant_id="t-1",
        caller_ref="caller-1",
        endpoint_id="ep-1",
        disposition=RateLimitDisposition.ALLOWED,
        requests_remaining=100,
        window_reset_at=DT,
        checked_at=DT2,
    )
    defaults.update(overrides)
    return RateLimitRecord(**defaults)


def _make_idempotency_record(**overrides):
    defaults = dict(
        idempotency_key="ik-1",
        request_id="req-1",
        tenant_id="t-1",
        endpoint_id="ep-1",
        original_response_id="resp-orig",
        created_at=DT,
    )
    defaults.update(overrides)
    return IdempotencyRecord(**defaults)


def _make_api_snapshot(**overrides):
    defaults = dict(
        snapshot_id="snap-1",
        tenant_id="t-1",
        total_endpoints=10,
        active_endpoints=8,
        total_requests=1000,
        accepted_requests=900,
        rejected_requests=50,
        rate_limited_requests=30,
        deduplicated_requests=20,
        captured_at=DT,
    )
    defaults.update(overrides)
    return ApiSnapshot(**defaults)


def _make_api_violation(**overrides):
    defaults = dict(
        violation_id="viol-1",
        tenant_id="t-1",
        operation="write",
        reason="unauthorized",
        detected_at=DT,
    )
    defaults.update(overrides)
    return ApiViolation(**defaults)


def _make_api_assessment(**overrides):
    defaults = dict(
        assessment_id="assess-1",
        tenant_id="t-1",
        total_endpoints=10,
        active_endpoints=8,
        availability_score=0.99,
        error_rate=0.01,
        total_violations=2,
        assessed_at=DT,
    )
    defaults.update(overrides)
    return ApiAssessment(**defaults)


def _make_api_closure_report(**overrides):
    defaults = dict(
        report_id="rpt-1",
        tenant_id="t-1",
        total_endpoints=10,
        total_requests=1000,
        total_responses=990,
        total_errors=10,
        total_rate_limits=5,
        total_violations=2,
        created_at=DT,
    )
    defaults.update(overrides)
    return ApiClosureReport(**defaults)


# ===================================================================
# SECTION 1: Enum tests
# ===================================================================


class TestApiStatus:
    def test_member_count(self):
        assert len(ApiStatus) == 4

    @pytest.mark.parametrize("name,value", [
        ("ACTIVE", "active"),
        ("DEPRECATED", "deprecated"),
        ("DISABLED", "disabled"),
        ("RETIRED", "retired"),
    ])
    def test_members(self, name, value):
        member = ApiStatus[name]
        assert member.value == value

    @pytest.mark.parametrize("value", ["active", "deprecated", "disabled", "retired"])
    def test_lookup_by_value(self, value):
        assert ApiStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            ApiStatus("nonexistent")


class TestEndpointKind:
    def test_member_count(self):
        assert len(EndpointKind) == 5

    @pytest.mark.parametrize("name,value", [
        ("READ", "read"),
        ("WRITE", "write"),
        ("MUTATION", "mutation"),
        ("QUERY", "query"),
        ("HEALTH", "health"),
    ])
    def test_members(self, name, value):
        assert EndpointKind[name].value == value

    @pytest.mark.parametrize("value", ["read", "write", "mutation", "query", "health"])
    def test_lookup_by_value(self, value):
        assert EndpointKind(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            EndpointKind("nonexistent")


class TestRequestDisposition:
    def test_member_count(self):
        assert len(RequestDisposition) == 4

    @pytest.mark.parametrize("name,value", [
        ("ACCEPTED", "accepted"),
        ("REJECTED", "rejected"),
        ("RATE_LIMITED", "rate_limited"),
        ("DEDUPLICATED", "deduplicated"),
    ])
    def test_members(self, name, value):
        assert RequestDisposition[name].value == value

    @pytest.mark.parametrize("value", ["accepted", "rejected", "rate_limited", "deduplicated"])
    def test_lookup_by_value(self, value):
        assert RequestDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            RequestDisposition("nonexistent")


class TestAuthDisposition:
    def test_member_count(self):
        assert len(AuthDisposition) == 4

    @pytest.mark.parametrize("name,value", [
        ("AUTHENTICATED", "authenticated"),
        ("DENIED", "denied"),
        ("EXPIRED", "expired"),
        ("INVALID", "invalid"),
    ])
    def test_members(self, name, value):
        assert AuthDisposition[name].value == value

    @pytest.mark.parametrize("value", ["authenticated", "denied", "expired", "invalid"])
    def test_lookup_by_value(self, value):
        assert AuthDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            AuthDisposition("nonexistent")


class TestRateLimitDisposition:
    def test_member_count(self):
        assert len(RateLimitDisposition) == 4

    @pytest.mark.parametrize("name,value", [
        ("ALLOWED", "allowed"),
        ("THROTTLED", "throttled"),
        ("BLOCKED", "blocked"),
        ("EXEMPT", "exempt"),
    ])
    def test_members(self, name, value):
        assert RateLimitDisposition[name].value == value

    @pytest.mark.parametrize("value", ["allowed", "throttled", "blocked", "exempt"])
    def test_lookup_by_value(self, value):
        assert RateLimitDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            RateLimitDisposition("nonexistent")


class TestApiVisibility:
    def test_member_count(self):
        assert len(ApiVisibility) == 4

    @pytest.mark.parametrize("name,value", [
        ("PUBLIC", "public"),
        ("PARTNER", "partner"),
        ("INTERNAL", "internal"),
        ("ADMIN", "admin"),
    ])
    def test_members(self, name, value):
        assert ApiVisibility[name].value == value

    @pytest.mark.parametrize("value", ["public", "partner", "internal", "admin"])
    def test_lookup_by_value(self, value):
        assert ApiVisibility(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            ApiVisibility("nonexistent")


# ===================================================================
# SECTION 2: Dataclass tests
# ===================================================================


class TestApiRequest:
    def test_valid_construction(self):
        r = _make_api_request()
        assert r.request_id == "req-1"
        assert r.tenant_id == "t-1"
        assert r.endpoint_id == "ep-1"
        assert r.caller_ref == "caller-1"
        assert r.disposition is RequestDisposition.ACCEPTED
        assert r.auth_disposition is AuthDisposition.AUTHENTICATED
        assert r.idempotency_key == "ik-1"
        assert r.received_at == DT

    def test_frozen(self):
        r = _make_api_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.request_id = "changed"

    def test_metadata_mapping_proxy(self):
        r = _make_api_request(metadata={"key": "val"})
        assert isinstance(r.metadata, MappingProxyType)
        assert r.metadata["key"] == "val"

    def test_to_dict_preserves_enums(self):
        r = _make_api_request()
        d = r.to_dict()
        assert d["disposition"] is RequestDisposition.ACCEPTED
        assert d["auth_disposition"] is AuthDisposition.AUTHENTICATED

    def test_to_dict_metadata_is_plain_dict(self):
        r = _make_api_request(metadata={"a": 1})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", [
        "request_id", "tenant_id", "endpoint_id", "caller_ref", "idempotency_key",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_request(**{field_name: ""})

    @pytest.mark.parametrize("field_name", [
        "request_id", "tenant_id", "endpoint_id", "caller_ref", "idempotency_key",
    ])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_request(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_request(received_at="not-a-date")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _make_api_request(disposition="accepted")

    def test_invalid_auth_disposition_type(self):
        with pytest.raises(ValueError):
            _make_api_request(auth_disposition="authenticated")

    @pytest.mark.parametrize("disp", list(RequestDisposition))
    def test_all_dispositions_accepted(self, disp):
        r = _make_api_request(disposition=disp)
        assert r.disposition is disp

    @pytest.mark.parametrize("auth", list(AuthDisposition))
    def test_all_auth_dispositions_accepted(self, auth):
        r = _make_api_request(auth_disposition=auth)
        assert r.auth_disposition is auth

    def test_iso_datetime_with_tz(self):
        r = _make_api_request(received_at="2025-06-01T12:00:00+05:30")
        assert r.received_at == "2025-06-01T12:00:00+05:30"

    def test_iso_datetime_with_z(self):
        r = _make_api_request(received_at="2025-06-01T00:00:00Z")
        assert r.received_at == "2025-06-01T00:00:00Z"


class TestApiResponse:
    def test_valid_construction(self):
        r = _make_api_response()
        assert r.response_id == "resp-1"
        assert r.request_id == "req-1"
        assert r.status_code == 200

    def test_frozen(self):
        r = _make_api_response()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.response_id = "changed"

    def test_metadata_mapping_proxy(self):
        r = _make_api_response(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        d = _make_api_response().to_dict()
        assert d["disposition"] is RequestDisposition.ACCEPTED

    @pytest.mark.parametrize("field_name", [
        "response_id", "request_id", "tenant_id", "payload_ref",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_response(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_response(responded_at="bad")

    def test_negative_status_code(self):
        with pytest.raises(ValueError):
            _make_api_response(status_code=-1)

    def test_status_code_zero_ok(self):
        r = _make_api_response(status_code=0)
        assert r.status_code == 0

    def test_status_code_bool_rejected(self):
        with pytest.raises(ValueError):
            _make_api_response(status_code=True)

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _make_api_response(disposition="accepted")


class TestEndpointDescriptor:
    def test_valid_construction(self):
        e = _make_endpoint_descriptor()
        assert e.endpoint_id == "ep-1"
        assert e.kind is EndpointKind.READ
        assert e.visibility is ApiVisibility.PUBLIC
        assert e.status is ApiStatus.ACTIVE

    def test_frozen(self):
        e = _make_endpoint_descriptor()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.path = "/changed"

    def test_metadata_mapping_proxy(self):
        e = _make_endpoint_descriptor(metadata={"x": 1})
        assert isinstance(e.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        d = _make_endpoint_descriptor().to_dict()
        assert d["kind"] is EndpointKind.READ
        assert d["visibility"] is ApiVisibility.PUBLIC
        assert d["status"] is ApiStatus.ACTIVE

    @pytest.mark.parametrize("field_name", [
        "endpoint_id", "tenant_id", "path", "target_runtime", "target_action",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_endpoint_descriptor(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_endpoint_descriptor(created_at="nope")

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError):
            _make_endpoint_descriptor(kind="read")

    def test_invalid_visibility_type(self):
        with pytest.raises(ValueError):
            _make_endpoint_descriptor(visibility="public")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _make_endpoint_descriptor(status="active")

    @pytest.mark.parametrize("kind", list(EndpointKind))
    def test_all_kinds_accepted(self, kind):
        e = _make_endpoint_descriptor(kind=kind)
        assert e.kind is kind

    @pytest.mark.parametrize("vis", list(ApiVisibility))
    def test_all_visibilities_accepted(self, vis):
        e = _make_endpoint_descriptor(visibility=vis)
        assert e.visibility is vis

    @pytest.mark.parametrize("st", list(ApiStatus))
    def test_all_statuses_accepted(self, st):
        e = _make_endpoint_descriptor(status=st)
        assert e.status is st


class TestApiErrorRecord:
    def test_valid_construction(self):
        e = _make_api_error_record()
        assert e.error_id == "err-1"
        assert e.error_code == "E001"
        assert e.status_code == 500

    def test_frozen(self):
        e = _make_api_error_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.error_id = "changed"

    def test_metadata_mapping_proxy(self):
        e = _make_api_error_record(metadata={"detail": "x"})
        assert isinstance(e.metadata, MappingProxyType)

    def test_to_dict_returns_dict(self):
        d = _make_api_error_record().to_dict()
        assert isinstance(d, dict)
        assert d["error_id"] == "err-1"

    @pytest.mark.parametrize("field_name", [
        "error_id", "request_id", "tenant_id", "error_code", "error_message",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_error_record(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_error_record(created_at="xyz")

    def test_negative_status_code(self):
        with pytest.raises(ValueError):
            _make_api_error_record(status_code=-1)

    def test_status_code_zero_ok(self):
        e = _make_api_error_record(status_code=0)
        assert e.status_code == 0


class TestRateLimitRecord:
    def test_valid_construction(self):
        r = _make_rate_limit_record()
        assert r.limit_id == "lim-1"
        assert r.disposition is RateLimitDisposition.ALLOWED
        assert r.requests_remaining == 100

    def test_frozen(self):
        r = _make_rate_limit_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.limit_id = "changed"

    def test_metadata_mapping_proxy(self):
        r = _make_rate_limit_record(metadata={"q": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = _make_rate_limit_record().to_dict()
        assert d["disposition"] is RateLimitDisposition.ALLOWED

    @pytest.mark.parametrize("field_name", [
        "limit_id", "tenant_id", "caller_ref", "endpoint_id",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_rate_limit_record(**{field_name: ""})

    def test_invalid_window_reset_at(self):
        with pytest.raises(ValueError):
            _make_rate_limit_record(window_reset_at="bad")

    def test_invalid_checked_at(self):
        with pytest.raises(ValueError):
            _make_rate_limit_record(checked_at="bad")

    def test_two_distinct_datetime_fields(self):
        r = _make_rate_limit_record(
            window_reset_at="2025-06-01T00:00:00Z",
            checked_at="2025-06-01T12:00:00+00:00",
        )
        assert r.window_reset_at == "2025-06-01T00:00:00Z"
        assert r.checked_at == "2025-06-01T12:00:00+00:00"

    def test_negative_requests_remaining(self):
        with pytest.raises(ValueError):
            _make_rate_limit_record(requests_remaining=-1)

    def test_requests_remaining_zero_ok(self):
        r = _make_rate_limit_record(requests_remaining=0)
        assert r.requests_remaining == 0

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _make_rate_limit_record(disposition="allowed")

    @pytest.mark.parametrize("disp", list(RateLimitDisposition))
    def test_all_dispositions_accepted(self, disp):
        r = _make_rate_limit_record(disposition=disp)
        assert r.disposition is disp


class TestIdempotencyRecord:
    def test_valid_construction(self):
        r = _make_idempotency_record()
        assert r.idempotency_key == "ik-1"
        assert r.original_response_id == "resp-orig"

    def test_frozen(self):
        r = _make_idempotency_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.idempotency_key = "changed"

    def test_metadata_mapping_proxy(self):
        r = _make_idempotency_record(metadata={"z": 0})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_returns_dict(self):
        d = _make_idempotency_record().to_dict()
        assert isinstance(d, dict)
        assert d["idempotency_key"] == "ik-1"

    @pytest.mark.parametrize("field_name", [
        "idempotency_key", "request_id", "tenant_id", "endpoint_id", "original_response_id",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_idempotency_record(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_idempotency_record(created_at="nope")


class TestApiSnapshot:
    def test_valid_construction(self):
        s = _make_api_snapshot()
        assert s.snapshot_id == "snap-1"
        assert s.total_endpoints == 10
        assert s.active_endpoints == 8
        assert s.total_requests == 1000

    def test_frozen(self):
        s = _make_api_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.snapshot_id = "changed"

    def test_metadata_mapping_proxy(self):
        s = _make_api_snapshot(metadata={"m": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _make_api_snapshot().to_dict()
        assert d["total_endpoints"] == 10
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_snapshot(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_snapshot(captured_at="nope")

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "active_endpoints", "total_requests",
        "accepted_requests", "rejected_requests",
        "rate_limited_requests", "deduplicated_requests",
    ])
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_snapshot(**{field_name: -1})

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "active_endpoints", "total_requests",
        "accepted_requests", "rejected_requests",
        "rate_limited_requests", "deduplicated_requests",
    ])
    def test_zero_int_ok(self, field_name):
        s = _make_api_snapshot(**{field_name: 0})
        assert getattr(s, field_name) == 0

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "active_endpoints", "total_requests",
        "accepted_requests", "rejected_requests",
        "rate_limited_requests", "deduplicated_requests",
    ])
    def test_bool_rejected_for_int_field(self, field_name):
        with pytest.raises(ValueError):
            _make_api_snapshot(**{field_name: True})


class TestApiViolation:
    def test_valid_construction(self):
        v = _make_api_violation()
        assert v.violation_id == "viol-1"
        assert v.operation == "write"
        assert v.reason == "unauthorized"

    def test_frozen(self):
        v = _make_api_violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.violation_id = "changed"

    def test_metadata_mapping_proxy(self):
        v = _make_api_violation(metadata={"v": 1})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _make_api_violation().to_dict()
        assert d["violation_id"] == "viol-1"

    @pytest.mark.parametrize("field_name", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_violation(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_violation(detected_at="bad")


class TestApiAssessment:
    def test_valid_construction(self):
        a = _make_api_assessment()
        assert a.assessment_id == "assess-1"
        assert a.availability_score == 0.99
        assert a.error_rate == 0.01

    def test_frozen(self):
        a = _make_api_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.assessment_id = "changed"

    def test_metadata_mapping_proxy(self):
        a = _make_api_assessment(metadata={"score": 1})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _make_api_assessment().to_dict()
        assert d["availability_score"] == 0.99
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_assessment(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(assessed_at="bad")

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "active_endpoints", "total_violations",
    ])
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_assessment(**{field_name: -1})

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "active_endpoints", "total_violations",
    ])
    def test_zero_int_ok(self, field_name):
        a = _make_api_assessment(**{field_name: 0})
        assert getattr(a, field_name) == 0

    # --- unit float: availability_score ---

    def test_availability_score_zero(self):
        a = _make_api_assessment(availability_score=0.0)
        assert a.availability_score == 0.0

    def test_availability_score_one(self):
        a = _make_api_assessment(availability_score=1.0)
        assert a.availability_score == 1.0

    def test_availability_score_mid(self):
        a = _make_api_assessment(availability_score=0.5)
        assert a.availability_score == 0.5

    def test_availability_score_negative_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=-0.01)

    def test_availability_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=1.01)

    def test_availability_score_nan_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=float("nan"))

    def test_availability_score_inf_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=float("inf"))

    def test_availability_score_neg_inf_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=float("-inf"))

    def test_availability_score_bool_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=True)

    def test_availability_score_int_zero_ok(self):
        a = _make_api_assessment(availability_score=0)
        assert a.availability_score == 0.0

    def test_availability_score_int_one_ok(self):
        a = _make_api_assessment(availability_score=1)
        assert a.availability_score == 1.0

    # --- unit float: error_rate ---

    def test_error_rate_zero(self):
        a = _make_api_assessment(error_rate=0.0)
        assert a.error_rate == 0.0

    def test_error_rate_one(self):
        a = _make_api_assessment(error_rate=1.0)
        assert a.error_rate == 1.0

    def test_error_rate_negative_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(error_rate=-0.001)

    def test_error_rate_above_one_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(error_rate=1.001)

    def test_error_rate_nan_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(error_rate=float("nan"))

    def test_error_rate_inf_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(error_rate=float("inf"))

    def test_error_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            _make_api_assessment(error_rate=True)


class TestApiClosureReport:
    def test_valid_construction(self):
        r = _make_api_closure_report()
        assert r.report_id == "rpt-1"
        assert r.total_endpoints == 10
        assert r.total_errors == 10

    def test_frozen(self):
        r = _make_api_closure_report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "changed"

    def test_metadata_mapping_proxy(self):
        r = _make_api_closure_report(metadata={"rpt": True})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _make_api_closure_report().to_dict()
        assert d["report_id"] == "rpt-1"
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_closure_report(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            _make_api_closure_report(created_at="nope")

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "total_requests", "total_responses",
        "total_errors", "total_rate_limits", "total_violations",
    ])
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            _make_api_closure_report(**{field_name: -1})

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "total_requests", "total_responses",
        "total_errors", "total_rate_limits", "total_violations",
    ])
    def test_zero_int_ok(self, field_name):
        r = _make_api_closure_report(**{field_name: 0})
        assert getattr(r, field_name) == 0

    @pytest.mark.parametrize("field_name", [
        "total_endpoints", "total_requests", "total_responses",
        "total_errors", "total_rate_limits", "total_violations",
    ])
    def test_bool_rejected_for_int_field(self, field_name):
        with pytest.raises(ValueError):
            _make_api_closure_report(**{field_name: True})


# ===================================================================
# SECTION 3: Parametrized boundary / cross-cutting tests
# ===================================================================

ALL_MAKERS = [
    ("ApiRequest", _make_api_request),
    ("ApiResponse", _make_api_response),
    ("EndpointDescriptor", _make_endpoint_descriptor),
    ("ApiErrorRecord", _make_api_error_record),
    ("RateLimitRecord", _make_rate_limit_record),
    ("IdempotencyRecord", _make_idempotency_record),
    ("ApiSnapshot", _make_api_snapshot),
    ("ApiViolation", _make_api_violation),
    ("ApiAssessment", _make_api_assessment),
    ("ApiClosureReport", _make_api_closure_report),
]


class TestCrossCutting:
    """Cross-cutting invariants shared by all 10 dataclasses."""

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_is_frozen_dataclass(self, name, maker):
        obj = maker()
        assert dataclasses.is_dataclass(obj)
        with pytest.raises(dataclasses.FrozenInstanceError):
            obj.tenant_id = "hacked"

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_has_slots(self, name, maker):
        cls = type(maker())
        assert hasattr(cls, "__slots__")

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_has_metadata_field(self, name, maker):
        obj = maker()
        assert hasattr(obj, "metadata")

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_default_metadata_is_empty_mapping_proxy(self, name, maker):
        obj = maker()
        assert isinstance(obj.metadata, MappingProxyType)
        assert len(obj.metadata) == 0

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_metadata_with_nested_dict_frozen(self, name, maker):
        obj = maker(metadata={"nested": {"a": 1}})
        assert isinstance(obj.metadata["nested"], MappingProxyType)

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_to_dict_returns_dict(self, name, maker):
        d = maker().to_dict()
        assert isinstance(d, dict)

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_to_dict_metadata_thawed(self, name, maker):
        obj = maker(metadata={"k": "v"})
        d = obj.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["k"] == "v"

    @pytest.mark.parametrize("name,maker", ALL_MAKERS, ids=[m[0] for m in ALL_MAKERS])
    def test_has_tenant_id(self, name, maker):
        obj = maker()
        assert hasattr(obj, "tenant_id")
        assert isinstance(obj.tenant_id, str)
        assert len(obj.tenant_id.strip()) > 0


# ---------------------------------------------------------------------------
# Parametrized datetime format acceptance
# ---------------------------------------------------------------------------

VALID_DATETIMES = [
    "2025-06-01",
    "2025-06-01T12:00:00",
    "2025-06-01T12:00:00Z",
    "2025-06-01T12:00:00+00:00",
    "2025-06-01T12:00:00-05:00",
    "2025-12-31T23:59:59.999999+00:00",
]

INVALID_DATETIMES = [
    "",
    "   ",
    "not-a-date",
    "2025/06/01",
    "June 1 2025",
    "12:00:00",
]


class TestDatetimeBoundary:
    @pytest.mark.parametrize("dt_val", VALID_DATETIMES)
    def test_api_request_accepts_valid_dt(self, dt_val):
        r = _make_api_request(received_at=dt_val)
        assert r.received_at == dt_val

    @pytest.mark.parametrize("dt_val", INVALID_DATETIMES)
    def test_api_request_rejects_invalid_dt(self, dt_val):
        with pytest.raises(ValueError):
            _make_api_request(received_at=dt_val)

    @pytest.mark.parametrize("dt_val", VALID_DATETIMES)
    def test_rate_limit_window_reset_at_valid(self, dt_val):
        r = _make_rate_limit_record(window_reset_at=dt_val)
        assert r.window_reset_at == dt_val

    @pytest.mark.parametrize("dt_val", VALID_DATETIMES)
    def test_rate_limit_checked_at_valid(self, dt_val):
        r = _make_rate_limit_record(checked_at=dt_val)
        assert r.checked_at == dt_val

    @pytest.mark.parametrize("dt_val", INVALID_DATETIMES)
    def test_rate_limit_window_reset_at_invalid(self, dt_val):
        with pytest.raises(ValueError):
            _make_rate_limit_record(window_reset_at=dt_val)

    @pytest.mark.parametrize("dt_val", INVALID_DATETIMES)
    def test_rate_limit_checked_at_invalid(self, dt_val):
        with pytest.raises(ValueError):
            _make_rate_limit_record(checked_at=dt_val)


# ---------------------------------------------------------------------------
# Parametrized non-negative int boundary
# ---------------------------------------------------------------------------

class TestNonNegativeIntBoundary:
    @pytest.mark.parametrize("val,ok", [
        (0, True),
        (1, True),
        (999999, True),
        (-1, False),
        (-100, False),
    ])
    def test_api_snapshot_total_endpoints(self, val, ok):
        if ok:
            s = _make_api_snapshot(total_endpoints=val)
            assert s.total_endpoints == val
        else:
            with pytest.raises(ValueError):
                _make_api_snapshot(total_endpoints=val)

    @pytest.mark.parametrize("val,ok", [
        (0, True),
        (1, True),
        (-1, False),
    ])
    def test_api_closure_total_requests(self, val, ok):
        if ok:
            r = _make_api_closure_report(total_requests=val)
            assert r.total_requests == val
        else:
            with pytest.raises(ValueError):
                _make_api_closure_report(total_requests=val)

    @pytest.mark.parametrize("val", [1.5, "5", None, True, False])
    def test_api_snapshot_rejects_non_int(self, val):
        with pytest.raises((ValueError, TypeError)):
            _make_api_snapshot(total_endpoints=val)


# ---------------------------------------------------------------------------
# Parametrized unit float boundary
# ---------------------------------------------------------------------------

class TestUnitFloatBoundary:
    @pytest.mark.parametrize("val,ok", [
        (0.0, True),
        (0.5, True),
        (1.0, True),
        (0, True),       # int 0 is accepted
        (1, True),       # int 1 is accepted
        (-0.001, False),
        (1.001, False),
        (2.0, False),
        (-1.0, False),
    ])
    def test_availability_score_boundary(self, val, ok):
        if ok:
            a = _make_api_assessment(availability_score=val)
            assert 0.0 <= a.availability_score <= 1.0
        else:
            with pytest.raises(ValueError):
                _make_api_assessment(availability_score=val)

    @pytest.mark.parametrize("val,ok", [
        (0.0, True),
        (0.5, True),
        (1.0, True),
        (-0.001, False),
        (1.001, False),
    ])
    def test_error_rate_boundary(self, val, ok):
        if ok:
            a = _make_api_assessment(error_rate=val)
            assert 0.0 <= a.error_rate <= 1.0
        else:
            with pytest.raises(ValueError):
                _make_api_assessment(error_rate=val)

    @pytest.mark.parametrize("val", [float("nan"), float("inf"), float("-inf")])
    def test_special_floats_rejected_for_availability(self, val):
        with pytest.raises(ValueError):
            _make_api_assessment(availability_score=val)

    @pytest.mark.parametrize("val", [float("nan"), float("inf"), float("-inf")])
    def test_special_floats_rejected_for_error_rate(self, val):
        with pytest.raises(ValueError):
            _make_api_assessment(error_rate=val)

    @pytest.mark.parametrize("val", ["0.5", None, True, False])
    def test_non_numeric_rejected_for_availability(self, val):
        with pytest.raises((ValueError, TypeError)):
            _make_api_assessment(availability_score=val)

    @pytest.mark.parametrize("val", ["0.5", None, True, False])
    def test_non_numeric_rejected_for_error_rate(self, val):
        with pytest.raises((ValueError, TypeError)):
            _make_api_assessment(error_rate=val)


# ---------------------------------------------------------------------------
# Metadata freezing edge cases
# ---------------------------------------------------------------------------

class TestMetadataFreezing:
    def test_list_in_metadata_becomes_tuple(self):
        r = _make_api_request(metadata={"items": [1, 2, 3]})
        assert isinstance(r.metadata["items"], tuple)
        assert r.metadata["items"] == (1, 2, 3)

    def test_set_in_metadata_becomes_frozenset(self):
        r = _make_api_request(metadata={"tags": {1, 2}})
        assert isinstance(r.metadata["tags"], frozenset)

    def test_nested_dict_in_metadata_becomes_mapping_proxy(self):
        r = _make_api_request(metadata={"inner": {"a": "b"}})
        assert isinstance(r.metadata["inner"], MappingProxyType)

    def test_deeply_nested_metadata(self):
        r = _make_api_request(metadata={"l1": {"l2": {"l3": "deep"}}})
        assert r.metadata["l1"]["l2"]["l3"] == "deep"
        assert isinstance(r.metadata["l1"]["l2"], MappingProxyType)

    def test_metadata_mutation_blocked(self):
        r = _make_api_request(metadata={"k": "v"})
        with pytest.raises(TypeError):
            r.metadata["k"] = "new"

    def test_to_dict_thaws_nested_metadata(self):
        r = _make_api_request(metadata={"inner": {"a": 1}})
        d = r.to_dict()
        assert isinstance(d["metadata"]["inner"], dict)
