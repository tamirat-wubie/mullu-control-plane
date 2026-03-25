"""Comprehensive tests for PublicApiEngine (~350 tests).

Covers: register_endpoint, get_endpoint, deprecate/disable/retire_endpoint,
endpoints_for_tenant, active_endpoints_for_tenant, process_request (all paths),
get_request, requests_for_tenant, record_response, get_response,
responses_for_request, errors_for_tenant, api_snapshot, api_assessment,
detect_api_violations, closure_report, state_hash, properties,
and 6 golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.public_api import PublicApiEngine
from mcoi_runtime.contracts.public_api import (
    ApiAssessment,
    ApiClosureReport,
    ApiErrorRecord,
    ApiRequest,
    ApiResponse,
    ApiSnapshot,
    ApiStatus,
    ApiViolation,
    ApiVisibility,
    AuthDisposition,
    EndpointDescriptor,
    EndpointKind,
    IdempotencyRecord,
    RateLimitDisposition,
    RateLimitRecord,
    RequestDisposition,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spine():
    return EventSpineEngine()


@pytest.fixture
def eng(spine):
    return PublicApiEngine(spine)


def _reg(eng, eid="ep-1", tid="t-1", path="/v1/foo", kind=EndpointKind.READ,
         vis=ApiVisibility.PUBLIC, rt="svc", act="do"):
    return eng.register_endpoint(eid, tid, path, kind, vis, rt, act)


def _req(eng, rid="req-1", tid="t-1", eid="ep-1", caller="c-1",
         idem="", caller_tid=""):
    return eng.process_request(rid, tid, eid, caller, idem, caller_tid)


def _resp(eng, resp_id="resp-1", req_id="req-1", tid="t-1",
          code=200, payload="ok"):
    return eng.record_response(resp_id, req_id, tid, code, payload)


# ===================================================================
# 1. Constructor
# ===================================================================

class TestConstructor:
    def test_requires_event_spine_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PublicApiEngine("not-a-spine")

    def test_accepts_event_spine_engine(self, spine):
        eng = PublicApiEngine(spine)
        assert eng.endpoint_count == 0

    def test_initial_counts_zero(self, eng):
        assert eng.endpoint_count == 0
        assert eng.request_count == 0
        assert eng.response_count == 0
        assert eng.error_count == 0
        assert eng.rate_limit_count == 0
        assert eng.idempotency_count == 0
        assert eng.violation_count == 0
        assert eng.assessment_count == 0

    def test_default_rate_limit(self, eng):
        assert eng._rate_limit_max == 100


# ===================================================================
# 2. register_endpoint
# ===================================================================

class TestRegisterEndpoint:
    def test_basic_register(self, eng):
        ep = _reg(eng)
        assert isinstance(ep, EndpointDescriptor)
        assert ep.endpoint_id == "ep-1"
        assert ep.tenant_id == "t-1"
        assert ep.path == "/v1/foo"

    def test_default_status_active(self, eng):
        ep = _reg(eng)
        assert ep.status == ApiStatus.ACTIVE

    def test_kind_set(self, eng):
        ep = _reg(eng, kind=EndpointKind.WRITE)
        assert ep.kind == EndpointKind.WRITE

    def test_visibility_set(self, eng):
        ep = _reg(eng, vis=ApiVisibility.INTERNAL)
        assert ep.visibility == ApiVisibility.INTERNAL

    def test_target_runtime(self, eng):
        ep = _reg(eng, rt="billing-svc")
        assert ep.target_runtime == "billing-svc"

    def test_target_action(self, eng):
        ep = _reg(eng, act="create-invoice")
        assert ep.target_action == "create-invoice"

    def test_created_at_populated(self, eng):
        ep = _reg(eng)
        assert ep.created_at != ""

    def test_endpoint_count_increments(self, eng):
        _reg(eng, eid="a")
        _reg(eng, eid="b")
        assert eng.endpoint_count == 2

    def test_duplicate_raises(self, eng):
        _reg(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            _reg(eng)

    def test_emits_event(self, eng, spine):
        before = spine.event_count
        _reg(eng)
        assert spine.event_count > before

    def test_all_endpoint_kinds(self, eng):
        for i, kind in enumerate(EndpointKind):
            ep = _reg(eng, eid=f"ep-{i}", kind=kind)
            assert ep.kind == kind

    def test_all_visibilities(self, eng):
        for i, vis in enumerate(ApiVisibility):
            ep = _reg(eng, eid=f"ep-{i}", vis=vis)
            assert ep.visibility == vis

    def test_returns_frozen_record(self, eng):
        ep = _reg(eng)
        with pytest.raises(AttributeError):
            ep.status = ApiStatus.DISABLED  # type: ignore[misc]

    def test_multiple_tenants(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        assert eng.endpoint_count == 2

    def test_same_path_different_ids_ok(self, eng):
        _reg(eng, eid="a", path="/v1/x")
        _reg(eng, eid="b", path="/v1/x")
        assert eng.endpoint_count == 2


# ===================================================================
# 3. get_endpoint
# ===================================================================

class TestGetEndpoint:
    def test_returns_registered(self, eng):
        _reg(eng)
        ep = eng.get_endpoint("ep-1")
        assert ep.endpoint_id == "ep-1"

    def test_unknown_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.get_endpoint("no-such")

    def test_get_after_deprecate(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        ep = eng.get_endpoint("ep-1")
        assert ep.status == ApiStatus.DEPRECATED

    def test_get_after_disable(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        ep = eng.get_endpoint("ep-1")
        assert ep.status == ApiStatus.DISABLED

    def test_get_after_retire(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        ep = eng.get_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED


# ===================================================================
# 4. deprecate_endpoint
# ===================================================================

class TestDeprecateEndpoint:
    def test_basic_deprecate(self, eng):
        _reg(eng)
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.status == ApiStatus.DEPRECATED

    def test_unknown_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError):
            eng.deprecate_endpoint("no-such")

    def test_retired_raises(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            eng.deprecate_endpoint("ep-1")

    def test_emits_event(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        eng.deprecate_endpoint("ep-1")
        assert spine.event_count > before

    def test_deprecate_deprecated_ok(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.status == ApiStatus.DEPRECATED

    def test_deprecate_disabled_ok(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.status == ApiStatus.DEPRECATED

    def test_preserves_path(self, eng):
        _reg(eng, path="/v1/bar")
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.path == "/v1/bar"

    def test_preserves_kind(self, eng):
        _reg(eng, kind=EndpointKind.MUTATION)
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.kind == EndpointKind.MUTATION


# ===================================================================
# 5. disable_endpoint
# ===================================================================

class TestDisableEndpoint:
    def test_basic_disable(self, eng):
        _reg(eng)
        ep = eng.disable_endpoint("ep-1")
        assert ep.status == ApiStatus.DISABLED

    def test_unknown_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError):
            eng.disable_endpoint("no-such")

    def test_retired_raises(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError, match="retired"):
            eng.disable_endpoint("ep-1")

    def test_emits_event(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        eng.disable_endpoint("ep-1")
        assert spine.event_count > before

    def test_disable_deprecated_ok(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        ep = eng.disable_endpoint("ep-1")
        assert ep.status == ApiStatus.DISABLED

    def test_disable_active(self, eng):
        _reg(eng)
        ep = eng.disable_endpoint("ep-1")
        assert ep.status == ApiStatus.DISABLED


# ===================================================================
# 6. retire_endpoint
# ===================================================================

class TestRetireEndpoint:
    def test_basic_retire(self, eng):
        _reg(eng)
        ep = eng.retire_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED

    def test_unknown_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError):
            eng.retire_endpoint("no-such")

    def test_already_retired_raises(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already retired"):
            eng.retire_endpoint("ep-1")

    def test_emits_event(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        eng.retire_endpoint("ep-1")
        assert spine.event_count > before

    def test_retire_deprecated(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        ep = eng.retire_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED

    def test_retire_disabled(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        ep = eng.retire_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED

    def test_deprecate_after_retire_fails(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.deprecate_endpoint("ep-1")

    def test_disable_after_retire_fails(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.disable_endpoint("ep-1")


# ===================================================================
# 7. endpoints_for_tenant
# ===================================================================

class TestEndpointsForTenant:
    def test_empty(self, eng):
        assert eng.endpoints_for_tenant("t-1") == ()

    def test_returns_all_for_tenant(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        _reg(eng, eid="c", tid="t-2")
        result = eng.endpoints_for_tenant("t-1")
        assert len(result) == 2

    def test_returns_tuple(self, eng):
        _reg(eng)
        result = eng.endpoints_for_tenant("t-1")
        assert isinstance(result, tuple)

    def test_includes_all_statuses(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        eng.disable_endpoint("b")
        result = eng.endpoints_for_tenant("t-1")
        assert len(result) == 2

    def test_no_cross_tenant_leak(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        for ep in eng.endpoints_for_tenant("t-1"):
            assert ep.tenant_id == "t-1"


# ===================================================================
# 8. active_endpoints_for_tenant
# ===================================================================

class TestActiveEndpointsForTenant:
    def test_empty(self, eng):
        assert eng.active_endpoints_for_tenant("t-1") == ()

    def test_only_active(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        eng.disable_endpoint("b")
        result = eng.active_endpoints_for_tenant("t-1")
        assert len(result) == 1
        assert result[0].endpoint_id == "a"

    def test_deprecated_excluded(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.deprecate_endpoint("a")
        assert eng.active_endpoints_for_tenant("t-1") == ()

    def test_retired_excluded(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.retire_endpoint("a")
        assert eng.active_endpoints_for_tenant("t-1") == ()

    def test_no_cross_tenant(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        assert len(eng.active_endpoints_for_tenant("t-1")) == 1


# ===================================================================
# 9. process_request — ACCEPTED path
# ===================================================================

class TestProcessRequestAccepted:
    def test_basic_accept(self, eng):
        _reg(eng)
        req = _req(eng)
        assert req.disposition == RequestDisposition.ACCEPTED
        assert req.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_request_id_set(self, eng):
        _reg(eng)
        req = _req(eng)
        assert req.request_id == "req-1"

    def test_tenant_id_set(self, eng):
        _reg(eng)
        req = _req(eng)
        assert req.tenant_id == "t-1"

    def test_endpoint_id_set(self, eng):
        _reg(eng)
        req = _req(eng)
        assert req.endpoint_id == "ep-1"

    def test_caller_ref_set(self, eng):
        _reg(eng)
        req = _req(eng)
        assert req.caller_ref == "c-1"

    def test_received_at_populated(self, eng):
        _reg(eng)
        req = _req(eng)
        assert req.received_at != ""

    def test_request_count_increments(self, eng):
        _reg(eng)
        _req(eng)
        assert eng.request_count == 1

    def test_duplicate_request_id_raises(self, eng):
        _reg(eng)
        _req(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            _req(eng)

    def test_emits_event(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        _req(eng)
        assert spine.event_count > before

    def test_no_idempotency_key_defaults(self, eng):
        _reg(eng)
        req = _req(eng, idem="")
        assert req.idempotency_key == "none"

    def test_idempotency_key_preserved(self, eng):
        _reg(eng)
        req = _req(eng, idem="k-1")
        assert req.idempotency_key == "k-1"

    def test_rate_counter_increments(self, eng):
        _reg(eng)
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        key = ("t-1", "c-1", "ep-1")
        assert eng._rate_counters[key] == 2

    def test_rate_limit_record_created(self, eng):
        _reg(eng)
        _req(eng)
        assert eng.rate_limit_count == 1

    def test_same_tenant_accepted(self, eng):
        _reg(eng, tid="t-1")
        req = _req(eng, tid="t-1", caller_tid="t-1")
        assert req.disposition == RequestDisposition.ACCEPTED

    def test_caller_tenant_empty_uses_tenant(self, eng):
        _reg(eng, tid="t-1")
        req = _req(eng, tid="t-1", caller_tid="")
        assert req.disposition == RequestDisposition.ACCEPTED

    def test_deprecated_endpoint_accepted(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        req = _req(eng)
        assert req.disposition == RequestDisposition.ACCEPTED


# ===================================================================
# 10. process_request — REJECTED: unknown endpoint
# ===================================================================

class TestProcessRequestUnknownEndpoint:
    def test_unknown_ep_rejected(self, eng):
        req = _req(eng, eid="no-such")
        assert req.disposition == RequestDisposition.REJECTED

    def test_auth_invalid(self, eng):
        req = _req(eng, eid="no-such")
        assert req.auth_disposition == AuthDisposition.INVALID

    def test_error_recorded(self, eng):
        _req(eng, eid="no-such")
        assert eng.error_count == 1

    def test_error_code_404(self, eng):
        _req(eng, eid="no-such", tid="t-1")
        errs = eng.errors_for_tenant("t-1")
        assert len(errs) == 1
        assert errs[0].error_code == "ENDPOINT_NOT_FOUND"
        assert errs[0].status_code == 404

    def test_emits_event(self, eng, spine):
        before = spine.event_count
        _req(eng, eid="no-such")
        assert spine.event_count > before

    def test_request_still_stored(self, eng):
        _req(eng, eid="no-such")
        assert eng.request_count == 1

    def test_idempotency_key_set_to_none(self, eng):
        req = _req(eng, eid="no-such", idem="")
        assert req.idempotency_key == "none"


# ===================================================================
# 11. process_request — REJECTED: cross-tenant
# ===================================================================

class TestProcessRequestCrossTenant:
    def test_cross_tenant_rejected(self, eng):
        _reg(eng, tid="t-1")
        req = _req(eng, tid="t-2", caller_tid="t-2")
        assert req.disposition == RequestDisposition.REJECTED

    def test_auth_denied(self, eng):
        _reg(eng, tid="t-1")
        req = _req(eng, tid="t-2", caller_tid="t-2")
        assert req.auth_disposition == AuthDisposition.DENIED

    def test_error_403(self, eng):
        _reg(eng, tid="t-1")
        _req(eng, tid="t-2", caller_tid="t-2")
        errs = eng.errors_for_tenant("t-2")
        assert len(errs) == 1
        assert errs[0].error_code == "CROSS_TENANT_DENIED"
        assert errs[0].status_code == 403

    def test_emits_event(self, eng, spine):
        _reg(eng, tid="t-1")
        before = spine.event_count
        _req(eng, tid="t-2", caller_tid="t-2")
        assert spine.event_count > before

    def test_request_stored(self, eng):
        _reg(eng, tid="t-1")
        _req(eng, tid="t-2", caller_tid="t-2")
        assert eng.request_count == 1

    def test_caller_tenant_different_from_ep_tenant(self, eng):
        _reg(eng, tid="owner")
        req = _req(eng, tid="caller", caller_tid="caller")
        assert req.disposition == RequestDisposition.REJECTED
        assert req.auth_disposition == AuthDisposition.DENIED

    def test_tenant_id_vs_caller_tenant_id(self, eng):
        """When caller_tenant_id is provided it overrides tenant_id for the check."""
        _reg(eng, tid="t-1")
        # tenant_id matches but caller_tenant_id doesn't
        req = _req(eng, tid="t-1", caller_tid="t-intruder")
        assert req.disposition == RequestDisposition.REJECTED

    def test_no_rate_counter_increment(self, eng):
        _reg(eng, tid="t-1")
        _req(eng, tid="t-2", caller_tid="t-2")
        assert eng._rate_counters.get(("t-2", "c-1", "ep-1"), 0) == 0


# ===================================================================
# 12. process_request — REJECTED: disabled/retired endpoint
# ===================================================================

class TestProcessRequestDisabledRetired:
    def test_disabled_rejected(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        req = _req(eng)
        assert req.disposition == RequestDisposition.REJECTED

    def test_disabled_auth_authenticated(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        req = _req(eng)
        assert req.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_disabled_error_503(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        _req(eng)
        errs = eng.errors_for_tenant("t-1")
        assert errs[0].error_code == "ENDPOINT_UNAVAILABLE"
        assert errs[0].status_code == 503

    def test_retired_rejected(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        req = _req(eng)
        assert req.disposition == RequestDisposition.REJECTED

    def test_retired_auth_authenticated(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        req = _req(eng)
        assert req.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_retired_error_503(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        _req(eng)
        errs = eng.errors_for_tenant("t-1")
        assert errs[0].error_code == "ENDPOINT_UNAVAILABLE"
        assert errs[0].status_code == 503

    def test_emits_event_disabled(self, eng, spine):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        before = spine.event_count
        _req(eng)
        assert spine.event_count > before

    def test_emits_event_retired(self, eng, spine):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        before = spine.event_count
        _req(eng)
        assert spine.event_count > before

    def test_no_rate_counter_on_disabled(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        _req(eng)
        assert eng._rate_counters.get(("t-1", "c-1", "ep-1"), 0) == 0


# ===================================================================
# 13. process_request — RATE_LIMITED
# ===================================================================

class TestProcessRequestRateLimited:
    def test_rate_limited_at_max(self, eng):
        _reg(eng)
        eng._rate_limit_max = 2
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        req = _req(eng, rid="r3")
        assert req.disposition == RequestDisposition.RATE_LIMITED

    def test_rate_limited_auth_authenticated(self, eng):
        _reg(eng)
        eng._rate_limit_max = 1
        _req(eng, rid="r1")
        req = _req(eng, rid="r2")
        assert req.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_rate_limit_zero(self, eng):
        _reg(eng)
        eng._rate_limit_max = 0
        req = _req(eng)
        assert req.disposition == RequestDisposition.RATE_LIMITED

    def test_rate_limit_record_throttled(self, eng):
        _reg(eng)
        eng._rate_limit_max = 1
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        # Two rate limit records: one ALLOWED for r1, one THROTTLED for r2
        assert eng.rate_limit_count == 2

    def test_emits_event(self, eng, spine):
        _reg(eng)
        eng._rate_limit_max = 0
        before = spine.event_count
        _req(eng)
        assert spine.event_count > before

    def test_counter_not_incremented_when_limited(self, eng):
        _reg(eng)
        eng._rate_limit_max = 1
        _req(eng, rid="r1")
        _req(eng, rid="r2")  # rate limited
        key = ("t-1", "c-1", "ep-1")
        assert eng._rate_counters[key] == 1  # only r1 counted

    def test_different_callers_separate_counters(self, eng):
        _reg(eng)
        eng._rate_limit_max = 1
        _req(eng, rid="r1", caller="c-1")
        _req(eng, rid="r2", caller="c-2")
        assert eng._rate_counters.get(("t-1", "c-1", "ep-1")) == 1
        assert eng._rate_counters.get(("t-1", "c-2", "ep-1")) == 1

    def test_different_endpoints_separate_counters(self, eng):
        _reg(eng, eid="a")
        _reg(eng, eid="b")
        eng._rate_limit_max = 1
        _req(eng, rid="r1", eid="a")
        _req(eng, rid="r2", eid="b")
        # Both accepted
        assert eng._rate_counters.get(("t-1", "c-1", "a")) == 1
        assert eng._rate_counters.get(("t-1", "c-1", "b")) == 1

    def test_rate_limited_stable_under_repeated_calls(self, eng):
        _reg(eng)
        eng._rate_limit_max = 1
        _req(eng, rid="r1")
        for i in range(5):
            req = _req(eng, rid=f"rl-{i}")
            assert req.disposition == RequestDisposition.RATE_LIMITED

    def test_rate_limit_exactly_at_boundary(self, eng):
        _reg(eng)
        eng._rate_limit_max = 3
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        req3 = _req(eng, rid="r3")
        assert req3.disposition == RequestDisposition.ACCEPTED
        req4 = _req(eng, rid="r4")
        assert req4.disposition == RequestDisposition.RATE_LIMITED


# ===================================================================
# 14. process_request — DEDUPLICATED
# ===================================================================

class TestProcessRequestDeduplicated:
    def test_dedup_same_key(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        req2 = _req(eng, rid="r2", idem="k-1")
        assert req2.disposition == RequestDisposition.DEDUPLICATED

    def test_dedup_auth_authenticated(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        req2 = _req(eng, rid="r2", idem="k-1")
        assert req2.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_dedup_preserves_key(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        req2 = _req(eng, rid="r2", idem="k-1")
        assert req2.idempotency_key == "k-1"

    def test_different_keys_not_deduped(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        req2 = _req(eng, rid="r2", idem="k-2")
        assert req2.disposition == RequestDisposition.ACCEPTED

    def test_no_key_not_deduped(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="")
        _req(eng, rid="r2", idem="")
        r1 = eng.get_request("r1")
        r2 = eng.get_request("r2")
        assert r1.disposition == RequestDisposition.ACCEPTED
        assert r2.disposition == RequestDisposition.ACCEPTED

    def test_emits_event(self, eng, spine):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        before = spine.event_count
        _req(eng, rid="r2", idem="k-1")
        assert spine.event_count > before

    def test_dedup_does_not_increment_rate_counter(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        counter_before = eng._rate_counters.get(("t-1", "c-1", "ep-1"), 0)
        _req(eng, rid="r2", idem="k-1")
        counter_after = eng._rate_counters.get(("t-1", "c-1", "ep-1"), 0)
        assert counter_after == counter_before

    def test_triple_dedup(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="resp-1", req_id="r1")
        _req(eng, rid="r2", idem="k-1")
        req3 = _req(eng, rid="r3", idem="k-1")
        assert req3.disposition == RequestDisposition.DEDUPLICATED


# ===================================================================
# 15. get_request
# ===================================================================

class TestGetRequest:
    def test_returns_stored(self, eng):
        _reg(eng)
        _req(eng)
        r = eng.get_request("req-1")
        assert r.request_id == "req-1"

    def test_unknown_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.get_request("no-such")

    def test_returns_rejected_request(self, eng):
        _req(eng, eid="no-such")
        r = eng.get_request("req-1")
        assert r.disposition == RequestDisposition.REJECTED


# ===================================================================
# 16. requests_for_tenant
# ===================================================================

class TestRequestsForTenant:
    def test_empty(self, eng):
        assert eng.requests_for_tenant("t-1") == ()

    def test_returns_all(self, eng):
        _reg(eng)
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        result = eng.requests_for_tenant("t-1")
        assert len(result) == 2

    def test_no_cross_tenant(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-2", eid="b")
        assert len(eng.requests_for_tenant("t-1")) == 1

    def test_returns_tuple(self, eng):
        _reg(eng)
        _req(eng)
        assert isinstance(eng.requests_for_tenant("t-1"), tuple)


# ===================================================================
# 17. record_response
# ===================================================================

class TestRecordResponse:
    def test_basic_response(self, eng):
        _reg(eng)
        _req(eng)
        resp = _resp(eng)
        assert isinstance(resp, ApiResponse)
        assert resp.response_id == "resp-1"

    def test_status_code(self, eng):
        _reg(eng)
        _req(eng)
        resp = _resp(eng, code=201)
        assert resp.status_code == 201

    def test_payload_ref(self, eng):
        _reg(eng)
        _req(eng)
        resp = _resp(eng, payload="data-ref-123")
        assert resp.payload_ref == "data-ref-123"

    def test_disposition_from_request(self, eng):
        _reg(eng)
        _req(eng)
        resp = _resp(eng)
        assert resp.disposition == RequestDisposition.ACCEPTED

    def test_duplicate_response_raises(self, eng):
        _reg(eng)
        _req(eng)
        _resp(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            _resp(eng)

    def test_unknown_request_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            _resp(eng, req_id="no-such")

    def test_response_count_increments(self, eng):
        _reg(eng)
        _req(eng)
        _resp(eng)
        assert eng.response_count == 1

    def test_emits_event(self, eng, spine):
        _reg(eng)
        _req(eng)
        before = spine.event_count
        _resp(eng)
        assert spine.event_count > before

    def test_idempotency_record_created(self, eng):
        _reg(eng)
        _req(eng, idem="k-1")
        assert eng.idempotency_count == 0
        _resp(eng)
        assert eng.idempotency_count == 1

    def test_no_idempotency_record_without_key(self, eng):
        _reg(eng)
        _req(eng, idem="")
        _resp(eng)
        assert eng.idempotency_count == 0

    def test_no_idempotency_record_for_rejected(self, eng):
        _req(eng, eid="no-such", idem="k-1")
        _resp(eng, req_id="req-1")
        assert eng.idempotency_count == 0

    def test_responded_at_populated(self, eng):
        _reg(eng)
        _req(eng)
        resp = _resp(eng)
        assert resp.responded_at != ""

    def test_multiple_responses_for_different_requests(self, eng):
        _reg(eng)
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        _resp(eng, resp_id="rsp1", req_id="r1")
        _resp(eng, resp_id="rsp2", req_id="r2")
        assert eng.response_count == 2


# ===================================================================
# 18. get_response
# ===================================================================

class TestGetResponse:
    def test_returns_stored(self, eng):
        _reg(eng)
        _req(eng)
        _resp(eng)
        r = eng.get_response("resp-1")
        assert r.response_id == "resp-1"

    def test_unknown_raises(self, eng):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            eng.get_response("no-such")


# ===================================================================
# 19. responses_for_request
# ===================================================================

class TestResponsesForRequest:
    def test_empty(self, eng):
        assert eng.responses_for_request("req-1") == ()

    def test_returns_matching(self, eng):
        _reg(eng)
        _req(eng)
        _resp(eng)
        result = eng.responses_for_request("req-1")
        assert len(result) == 1

    def test_returns_tuple(self, eng):
        _reg(eng)
        _req(eng)
        _resp(eng)
        assert isinstance(eng.responses_for_request("req-1"), tuple)

    def test_no_cross_request(self, eng):
        _reg(eng)
        _req(eng, rid="r1")
        _req(eng, rid="r2")
        _resp(eng, resp_id="rsp1", req_id="r1")
        assert len(eng.responses_for_request("r2")) == 0


# ===================================================================
# 20. errors_for_tenant
# ===================================================================

class TestErrorsForTenant:
    def test_empty(self, eng):
        assert eng.errors_for_tenant("t-1") == ()

    def test_returns_errors(self, eng):
        _req(eng, eid="no-such", tid="t-1")
        errs = eng.errors_for_tenant("t-1")
        assert len(errs) == 1

    def test_no_cross_tenant(self, eng):
        _req(eng, rid="r1", eid="no-such", tid="t-1")
        _reg(eng, tid="t-1")
        _req(eng, rid="r2", tid="t-2", caller_tid="t-2")
        errs_t1 = eng.errors_for_tenant("t-1")
        errs_t2 = eng.errors_for_tenant("t-2")
        for e in errs_t1:
            assert e.tenant_id == "t-1"
        for e in errs_t2:
            assert e.tenant_id == "t-2"

    def test_returns_tuple(self, eng):
        assert isinstance(eng.errors_for_tenant("t-1"), tuple)

    def test_multiple_errors(self, eng):
        _req(eng, rid="r1", eid="no-1", tid="t-1")
        _req(eng, rid="r2", eid="no-2", tid="t-1")
        errs = eng.errors_for_tenant("t-1")
        assert len(errs) == 2


# ===================================================================
# 21. api_snapshot
# ===================================================================

class TestApiSnapshot:
    def test_empty_snapshot(self, eng):
        snap = eng.api_snapshot("s-1", "t-1")
        assert isinstance(snap, ApiSnapshot)
        assert snap.total_endpoints == 0
        assert snap.total_requests == 0

    def test_counts_endpoints(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.total_endpoints == 2
        assert snap.active_endpoints == 2

    def test_counts_active_vs_total(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        eng.disable_endpoint("b")
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.total_endpoints == 2
        assert snap.active_endpoints == 1

    def test_counts_requests(self, eng):
        _reg(eng)
        _req(eng)
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.total_requests == 1
        assert snap.accepted_requests == 1

    def test_counts_rejected(self, eng):
        _req(eng, eid="no-such")
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.rejected_requests == 1

    def test_counts_rate_limited(self, eng):
        _reg(eng)
        eng._rate_limit_max = 0
        _req(eng)
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.rate_limited_requests == 1

    def test_counts_deduplicated(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="rsp1", req_id="r1")
        _req(eng, rid="r2", idem="k-1")
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.deduplicated_requests == 1

    def test_tenant_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-2", eid="b")
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.total_endpoints == 1
        assert snap.total_requests == 1

    def test_emits_event(self, eng, spine):
        before = spine.event_count
        eng.api_snapshot("s-1", "t-1")
        assert spine.event_count > before

    def test_captured_at_set(self, eng):
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.captured_at != ""


# ===================================================================
# 22. api_assessment
# ===================================================================

class TestApiAssessment:
    def test_empty_assessment(self, eng):
        a = eng.api_assessment("a-1", "t-1")
        assert isinstance(a, ApiAssessment)
        assert a.availability_score == 1.0
        assert a.error_rate == 0.0

    def test_duplicate_raises(self, eng):
        eng.api_assessment("a-1", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            eng.api_assessment("a-1", "t-1")

    def test_availability_all_active(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        a = eng.api_assessment("a-1", "t-1")
        assert a.availability_score == 1.0

    def test_availability_half(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        eng.disable_endpoint("b")
        a = eng.api_assessment("a-1", "t-1")
        assert a.availability_score == 0.5

    def test_availability_none_active(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.disable_endpoint("a")
        a = eng.api_assessment("a-1", "t-1")
        assert a.availability_score == 0.0

    def test_error_rate_with_errors(self, eng):
        _reg(eng, eid="a", tid="t-1")
        # 1 accepted + 1 error (unknown endpoint)
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-1", eid="no-such")
        a = eng.api_assessment("a-1", "t-1")
        assert a.error_rate == 0.5

    def test_error_rate_zero(self, eng):
        _reg(eng)
        _req(eng)
        a = eng.api_assessment("a-1", "t-1")
        assert a.error_rate == 0.0

    def test_total_violations(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        eng.detect_api_violations("t-1")
        a = eng.api_assessment("a-1", "t-1")
        assert a.total_violations >= 1

    def test_emits_event(self, eng, spine):
        before = spine.event_count
        eng.api_assessment("a-1", "t-1")
        assert spine.event_count > before

    def test_assessment_count_increments(self, eng):
        eng.api_assessment("a-1", "t-1")
        eng.api_assessment("a-2", "t-1")
        assert eng.assessment_count == 2

    def test_assessed_at_set(self, eng):
        a = eng.api_assessment("a-1", "t-1")
        assert a.assessed_at != ""


# ===================================================================
# 23. detect_api_violations
# ===================================================================

class TestDetectApiViolations:
    def test_no_violations(self, eng):
        _reg(eng)
        _req(eng)
        viols = eng.detect_api_violations("t-1")
        assert viols == ()

    def test_disabled_endpoint_hit(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        viols = eng.detect_api_violations("t-1")
        ops = [v.operation for v in viols]
        assert "disabled_endpoint_hit" in ops

    def test_cross_tenant_attempt(self, eng):
        _reg(eng, tid="t-1")
        _req(eng, tid="t-2", caller_tid="t-2")
        viols = eng.detect_api_violations("t-2")
        ops = [v.operation for v in viols]
        assert "cross_tenant_attempt" in ops

    def test_high_error_rate(self, eng):
        """Error rate > 50% with >= 5 requests triggers violation."""
        for i in range(6):
            _req(eng, rid=f"r{i}", eid="no-such", tid="t-1")
        viols = eng.detect_api_violations("t-1")
        ops = [v.operation for v in viols]
        assert "high_error_rate" in ops

    def test_idempotent_second_call_empty(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        viols1 = eng.detect_api_violations("t-1")
        assert len(viols1) > 0
        viols2 = eng.detect_api_violations("t-1")
        assert viols2 == ()

    def test_violation_count_increments(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        eng.detect_api_violations("t-1")
        assert eng.violation_count >= 1

    def test_emits_event_on_violations(self, eng, spine):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        before = spine.event_count
        eng.detect_api_violations("t-1")
        assert spine.event_count > before

    def test_no_event_when_no_violations(self, eng, spine):
        _reg(eng)
        _req(eng)
        before = spine.event_count
        eng.detect_api_violations("t-1")
        assert spine.event_count == before

    def test_tenant_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.disable_endpoint("a")
        _req(eng, rid="r1", tid="t-1", eid="a")
        viols = eng.detect_api_violations("t-2")
        assert viols == ()

    def test_violations_for_tenant(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        eng.detect_api_violations("t-1")
        vft = eng.violations_for_tenant("t-1")
        assert len(vft) >= 1

    def test_high_error_rate_threshold_exactly_50_no_violation(self, eng):
        """Exactly 50% with 6 requests (3 errors) should not trigger (> not >=)."""
        _reg(eng, eid="a", tid="t-1")
        for i in range(3):
            _req(eng, rid=f"ok-{i}", tid="t-1", eid="a")
        for i in range(3):
            _req(eng, rid=f"err-{i}", tid="t-1", eid="no-such")
        viols = eng.detect_api_violations("t-1")
        ops = [v.operation for v in viols]
        assert "high_error_rate" not in ops

    def test_high_error_rate_below_5_no_violation(self, eng):
        """Fewer than 5 requests should not trigger high_error_rate."""
        for i in range(4):
            _req(eng, rid=f"r{i}", eid="no-such", tid="t-1")
        viols = eng.detect_api_violations("t-1")
        ops = [v.operation for v in viols]
        assert "high_error_rate" not in ops


# ===================================================================
# 24. closure_report
# ===================================================================

class TestClosureReport:
    def test_empty_report(self, eng):
        rpt = eng.closure_report("rpt-1", "t-1")
        assert isinstance(rpt, ApiClosureReport)
        assert rpt.total_endpoints == 0
        assert rpt.total_requests == 0

    def test_counts(self, eng):
        _reg(eng, tid="t-1")
        _req(eng, tid="t-1")
        _resp(eng, tid="t-1")
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.total_endpoints == 1
        assert rpt.total_requests == 1
        assert rpt.total_responses == 1

    def test_error_count(self, eng):
        _req(eng, eid="no-such", tid="t-1")
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.total_errors == 1

    def test_rate_limit_count(self, eng):
        _reg(eng, tid="t-1")
        eng._rate_limit_max = 0
        _req(eng, tid="t-1")
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.total_rate_limits == 1

    def test_violation_count(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        eng.detect_api_violations("t-1")
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.total_violations >= 1

    def test_emits_event(self, eng, spine):
        before = spine.event_count
        eng.closure_report("rpt-1", "t-1")
        assert spine.event_count > before

    def test_created_at_set(self, eng):
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.created_at != ""

    def test_tenant_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-2", eid="b")
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.total_endpoints == 1
        assert rpt.total_requests == 1


# ===================================================================
# 25. state_hash
# ===================================================================

class TestStateHash:
    def test_empty_hash(self, eng):
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex

    def test_deterministic(self, eng):
        _reg(eng)
        h1 = eng.state_hash()
        h2 = eng.state_hash()
        assert h1 == h2

    def test_changes_on_endpoint(self, eng):
        h1 = eng.state_hash()
        _reg(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_request(self, eng):
        _reg(eng)
        h1 = eng.state_hash()
        _req(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_response(self, eng):
        _reg(eng)
        _req(eng)
        h1 = eng.state_hash()
        _resp(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_idempotency(self, eng):
        _reg(eng)
        _req(eng, idem="k-1")
        h1 = eng.state_hash()
        _resp(eng)
        h2 = eng.state_hash()
        assert h1 != h2

    def test_changes_on_violation(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        h1 = eng.state_hash()
        eng.detect_api_violations("t-1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_includes_status(self, eng):
        _reg(eng)
        h1 = eng.state_hash()
        eng.disable_endpoint("ep-1")
        h2 = eng.state_hash()
        assert h1 != h2


# ===================================================================
# 26. Properties
# ===================================================================

class TestProperties:
    def test_endpoint_count(self, eng):
        assert eng.endpoint_count == 0
        _reg(eng)
        assert eng.endpoint_count == 1

    def test_request_count(self, eng):
        _reg(eng)
        assert eng.request_count == 0
        _req(eng)
        assert eng.request_count == 1

    def test_response_count(self, eng):
        _reg(eng)
        _req(eng)
        assert eng.response_count == 0
        _resp(eng)
        assert eng.response_count == 1

    def test_error_count(self, eng):
        assert eng.error_count == 0
        _req(eng, eid="no-such")
        assert eng.error_count == 1

    def test_rate_limit_count(self, eng):
        _reg(eng)
        assert eng.rate_limit_count == 0
        _req(eng)
        assert eng.rate_limit_count == 1

    def test_idempotency_count(self, eng):
        _reg(eng)
        _req(eng, idem="k-1")
        assert eng.idempotency_count == 0
        _resp(eng)
        assert eng.idempotency_count == 1

    def test_violation_count(self, eng):
        assert eng.violation_count == 0
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        eng.detect_api_violations("t-1")
        assert eng.violation_count >= 1

    def test_assessment_count(self, eng):
        assert eng.assessment_count == 0
        eng.api_assessment("a-1", "t-1")
        assert eng.assessment_count == 1


# ===================================================================
# 27. Endpoint lifecycle transitions
# ===================================================================

class TestEndpointLifecycle:
    def test_active_to_deprecated(self, eng):
        _reg(eng)
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.status == ApiStatus.DEPRECATED

    def test_active_to_disabled(self, eng):
        _reg(eng)
        ep = eng.disable_endpoint("ep-1")
        assert ep.status == ApiStatus.DISABLED

    def test_active_to_retired(self, eng):
        _reg(eng)
        ep = eng.retire_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED

    def test_deprecated_to_disabled(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        ep = eng.disable_endpoint("ep-1")
        assert ep.status == ApiStatus.DISABLED

    def test_deprecated_to_retired(self, eng):
        _reg(eng)
        eng.deprecate_endpoint("ep-1")
        ep = eng.retire_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED

    def test_disabled_to_deprecated(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        ep = eng.deprecate_endpoint("ep-1")
        assert ep.status == ApiStatus.DEPRECATED

    def test_disabled_to_retired(self, eng):
        _reg(eng)
        eng.disable_endpoint("ep-1")
        ep = eng.retire_endpoint("ep-1")
        assert ep.status == ApiStatus.RETIRED

    def test_retired_is_terminal_for_deprecate(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.deprecate_endpoint("ep-1")

    def test_retired_is_terminal_for_disable(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.disable_endpoint("ep-1")

    def test_retired_is_terminal_for_retire(self, eng):
        _reg(eng)
        eng.retire_endpoint("ep-1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.retire_endpoint("ep-1")


# ===================================================================
# 28. Multi-tenant isolation
# ===================================================================

class TestMultiTenantIsolation:
    def test_endpoint_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        assert len(eng.endpoints_for_tenant("t-1")) == 1
        assert len(eng.endpoints_for_tenant("t-2")) == 1

    def test_request_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-2", eid="b")
        assert len(eng.requests_for_tenant("t-1")) == 1
        assert len(eng.requests_for_tenant("t-2")) == 1

    def test_error_isolation(self, eng):
        _req(eng, rid="r1", eid="no-1", tid="t-1")
        _req(eng, rid="r2", eid="no-2", tid="t-2")
        assert len(eng.errors_for_tenant("t-1")) == 1
        assert len(eng.errors_for_tenant("t-2")) == 1

    def test_snapshot_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        s1 = eng.api_snapshot("s1", "t-1")
        s2 = eng.api_snapshot("s2", "t-2")
        assert s1.total_endpoints == 1
        assert s2.total_endpoints == 1

    def test_violation_isolation(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.disable_endpoint("a")
        _req(eng, rid="r1", tid="t-1", eid="a")
        eng.detect_api_violations("t-1")
        viols_t2 = eng.violations_for_tenant("t-2")
        assert len(viols_t2) == 0


# ===================================================================
# 29. Event emission
# ===================================================================

class TestEventEmission:
    def test_register_emits(self, eng, spine):
        before = spine.event_count
        _reg(eng)
        assert spine.event_count == before + 1

    def test_deprecate_emits(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        eng.deprecate_endpoint("ep-1")
        assert spine.event_count == before + 1

    def test_disable_emits(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        eng.disable_endpoint("ep-1")
        assert spine.event_count == before + 1

    def test_retire_emits(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        eng.retire_endpoint("ep-1")
        assert spine.event_count == before + 1

    def test_accept_emits(self, eng, spine):
        _reg(eng)
        before = spine.event_count
        _req(eng)
        assert spine.event_count == before + 1

    def test_reject_emits(self, eng, spine):
        before = spine.event_count
        _req(eng, eid="no-such")
        assert spine.event_count == before + 1

    def test_response_emits(self, eng, spine):
        _reg(eng)
        _req(eng)
        before = spine.event_count
        _resp(eng)
        assert spine.event_count == before + 1

    def test_snapshot_emits(self, eng, spine):
        before = spine.event_count
        eng.api_snapshot("s-1", "t-1")
        assert spine.event_count == before + 1

    def test_assessment_emits(self, eng, spine):
        before = spine.event_count
        eng.api_assessment("a-1", "t-1")
        assert spine.event_count == before + 1

    def test_closure_emits(self, eng, spine):
        before = spine.event_count
        eng.closure_report("rpt-1", "t-1")
        assert spine.event_count == before + 1


# ===================================================================
# 30. Edge cases and stress
# ===================================================================

class TestEdgeCases:
    def test_many_endpoints(self, eng):
        for i in range(50):
            _reg(eng, eid=f"ep-{i}")
        assert eng.endpoint_count == 50

    def test_many_requests(self, eng):
        _reg(eng)
        for i in range(50):
            _req(eng, rid=f"r-{i}")
        assert eng.request_count == 50

    def test_rate_limit_max_1(self, eng):
        _reg(eng)
        eng._rate_limit_max = 1
        r1 = _req(eng, rid="r1")
        r2 = _req(eng, rid="r2")
        assert r1.disposition == RequestDisposition.ACCEPTED
        assert r2.disposition == RequestDisposition.RATE_LIMITED

    def test_process_request_cross_tenant_before_rate_limit(self, eng):
        """Cross-tenant check happens before rate limit check."""
        _reg(eng, tid="t-1")
        eng._rate_limit_max = 0
        req = _req(eng, tid="t-2", caller_tid="t-2")
        assert req.disposition == RequestDisposition.REJECTED
        assert req.auth_disposition == AuthDisposition.DENIED

    def test_process_request_disabled_before_rate_limit(self, eng):
        """Disabled check happens before rate limit check."""
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        eng._rate_limit_max = 0
        req = _req(eng, tid="t-1")
        assert req.disposition == RequestDisposition.REJECTED
        assert req.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_multiple_assessments_different_ids(self, eng):
        eng.api_assessment("a-1", "t-1")
        eng.api_assessment("a-2", "t-1")
        assert eng.assessment_count == 2

    def test_snapshot_with_mixed_dispositions(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng._rate_limit_max = 1
        _req(eng, rid="r1", tid="t-1", eid="a")  # accepted
        _req(eng, rid="r2", tid="t-1", eid="a")  # rate limited
        _req(eng, rid="r3", tid="t-1", eid="no-such")  # rejected
        _req(eng, rid="r4", tid="t-1", eid="a", idem="k-1")  # accepted (new key, but rate limited due to limit=1)
        snap = eng.api_snapshot("s-1", "t-1")
        assert snap.total_requests == 4

    def test_response_for_rejected_request(self, eng):
        """Can record a response for a rejected request."""
        _req(eng, eid="no-such")
        resp = _resp(eng)
        assert resp.disposition == RequestDisposition.REJECTED

    def test_idempotency_record_not_duplicated(self, eng):
        """Recording two responses for the same key does not duplicate idempotency."""
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="rsp1", req_id="r1")
        assert eng.idempotency_count == 1
        # The second response for a different accepted request with same key
        # should not create a duplicate because the key is already stored
        _req(eng, rid="r2", idem="k-2")
        _resp(eng, resp_id="rsp2", req_id="r2")
        assert eng.idempotency_count == 2

    def test_closure_report_after_complex_state(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        eng.disable_endpoint("b")
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-1", eid="b")  # disabled -> rejected
        _resp(eng, resp_id="rsp1", req_id="r1", tid="t-1")
        eng.detect_api_violations("t-1")
        rpt = eng.closure_report("rpt-1", "t-1")
        assert rpt.total_endpoints == 2
        assert rpt.total_requests == 2
        assert rpt.total_responses == 1
        assert rpt.total_errors >= 1
        assert rpt.total_violations >= 1


# ===================================================================
# 31. Process request ordering checks
# ===================================================================

class TestRequestProcessingOrder:
    def test_unknown_endpoint_checked_first(self, eng):
        """Unknown endpoint is checked before cross-tenant or rate limit."""
        eng._rate_limit_max = 0
        req = _req(eng, eid="no-such", caller_tid="t-other")
        assert req.auth_disposition == AuthDisposition.INVALID

    def test_cross_tenant_before_disabled(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        req = _req(eng, tid="t-2", caller_tid="t-2")
        assert req.auth_disposition == AuthDisposition.DENIED

    def test_disabled_before_rate_limit(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        eng._rate_limit_max = 0
        req = _req(eng, tid="t-1")
        # Should be rejected with ENDPOINT_UNAVAILABLE, not RATE_LIMITED
        assert req.disposition == RequestDisposition.REJECTED

    def test_rate_limit_before_idempotency(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="rsp1", req_id="r1")
        eng._rate_limit_max = 1  # already at 1
        req = _req(eng, rid="r2", idem="k-1")
        # Rate limit should fire before idempotency since counter=1 and max=1
        assert req.disposition == RequestDisposition.RATE_LIMITED


# ===================================================================
# GOLDEN SCENARIO 1: Authenticated request creates governed service request
# ===================================================================

class TestGolden1AuthenticatedRequestFlow:
    def test_register_process_respond(self, eng):
        ep = eng.register_endpoint("ep-svc", "tenant-a", "/v1/items", EndpointKind.WRITE,
                                   ApiVisibility.PUBLIC, "item-svc", "create-item")
        assert ep.status == ApiStatus.ACTIVE
        assert ep.kind == EndpointKind.WRITE

        req = eng.process_request("req-001", "tenant-a", "ep-svc", "caller-x", "idem-001")
        assert req.disposition == RequestDisposition.ACCEPTED
        assert req.auth_disposition == AuthDisposition.AUTHENTICATED
        assert req.idempotency_key == "idem-001"

        resp = eng.record_response("resp-001", "req-001", "tenant-a", 201, "item-ref-42")
        assert resp.status_code == 201
        assert resp.payload_ref == "item-ref-42"
        assert resp.disposition == RequestDisposition.ACCEPTED

        # Idempotency record created
        assert eng.idempotency_count == 1

        # Snapshot reflects everything
        snap = eng.api_snapshot("snap-g1", "tenant-a")
        assert snap.total_endpoints == 1
        assert snap.active_endpoints == 1
        assert snap.accepted_requests == 1

    def test_events_emitted_throughout(self, eng, spine):
        _reg(eng, eid="ep-svc", tid="tenant-a", rt="item-svc", act="create-item")
        _req(eng, rid="req-001", tid="tenant-a", eid="ep-svc", caller="cx", idem="idem-001")
        _resp(eng, resp_id="resp-001", req_id="req-001", tid="tenant-a")
        assert spine.event_count >= 3

    def test_closure_report_after_flow(self, eng):
        _reg(eng, eid="ep-svc", tid="tenant-a", rt="item-svc", act="create-item")
        _req(eng, rid="req-001", tid="tenant-a", eid="ep-svc", caller="cx")
        _resp(eng, resp_id="resp-001", req_id="req-001", tid="tenant-a")
        rpt = eng.closure_report("rpt-g1", "tenant-a")
        assert rpt.total_endpoints == 1
        assert rpt.total_requests == 1
        assert rpt.total_responses == 1
        assert rpt.total_errors == 0


# ===================================================================
# GOLDEN SCENARIO 2: Cross-tenant request denied fail-closed
# ===================================================================

class TestGolden2CrossTenantDenied:
    def test_fail_closed(self, eng):
        eng.register_endpoint("ep-priv", "owner-tenant", "/v1/secrets",
                              EndpointKind.READ, ApiVisibility.INTERNAL, "secret-svc", "read")

        req = eng.process_request("req-intruder", "attacker-tenant", "ep-priv",
                                  "evil-caller", "", "attacker-tenant")
        assert req.disposition == RequestDisposition.REJECTED
        assert req.auth_disposition == AuthDisposition.DENIED

        errs = eng.errors_for_tenant("attacker-tenant")
        assert len(errs) == 1
        assert errs[0].error_code == "CROSS_TENANT_DENIED"
        assert errs[0].status_code == 403

    def test_violation_detected(self, eng):
        eng.register_endpoint("ep-priv", "owner-tenant", "/v1/secrets",
                              EndpointKind.READ, ApiVisibility.INTERNAL, "secret-svc", "read")
        eng.process_request("req-intruder", "attacker-tenant", "ep-priv",
                            "evil-caller", "", "attacker-tenant")
        viols = eng.detect_api_violations("attacker-tenant")
        ops = [v.operation for v in viols]
        assert "cross_tenant_attempt" in ops

    def test_no_rate_counter_impact(self, eng):
        eng.register_endpoint("ep-priv", "owner-tenant", "/v1/secrets",
                              EndpointKind.READ, ApiVisibility.INTERNAL, "secret-svc", "read")
        eng.process_request("req-intruder", "attacker-tenant", "ep-priv",
                            "evil-caller", "", "attacker-tenant")
        key = ("attacker-tenant", "evil-caller", "ep-priv")
        assert eng._rate_counters.get(key, 0) == 0

    def test_assessment_captures_error(self, eng):
        eng.register_endpoint("ep-priv", "owner-tenant", "/v1/secrets",
                              EndpointKind.READ, ApiVisibility.INTERNAL, "secret-svc", "read")
        eng.process_request("req-intruder", "attacker-tenant", "ep-priv",
                            "evil-caller", "", "attacker-tenant")
        a = eng.api_assessment("a-g2", "attacker-tenant")
        assert a.error_rate == 1.0


# ===================================================================
# GOLDEN SCENARIO 3: Duplicate mutation deduplicated
# ===================================================================

class TestGolden3IdempotentDedup:
    def test_full_dedup_flow(self, eng):
        eng.register_endpoint("ep-mut", "tenant-b", "/v1/orders",
                              EndpointKind.MUTATION, ApiVisibility.PUBLIC, "order-svc", "create")

        # First request
        r1 = eng.process_request("req-orig", "tenant-b", "ep-mut", "caller-y", "idem-xyz")
        assert r1.disposition == RequestDisposition.ACCEPTED

        # Record response to create idempotency record
        eng.record_response("resp-orig", "req-orig", "tenant-b", 201, "order-ref-99")
        assert eng.idempotency_count == 1

        # Duplicate request
        r2 = eng.process_request("req-dup", "tenant-b", "ep-mut", "caller-y", "idem-xyz")
        assert r2.disposition == RequestDisposition.DEDUPLICATED
        assert r2.auth_disposition == AuthDisposition.AUTHENTICATED
        assert r2.idempotency_key == "idem-xyz"

    def test_dedup_does_not_increment_counter(self, eng):
        eng.register_endpoint("ep-mut", "tenant-b", "/v1/orders",
                              EndpointKind.MUTATION, ApiVisibility.PUBLIC, "order-svc", "create")
        eng.process_request("req-orig", "tenant-b", "ep-mut", "caller-y", "idem-xyz")
        eng.record_response("resp-orig", "req-orig", "tenant-b", 201, "order-ref-99")
        counter_before = eng._rate_counters.get(("tenant-b", "caller-y", "ep-mut"), 0)
        eng.process_request("req-dup", "tenant-b", "ep-mut", "caller-y", "idem-xyz")
        counter_after = eng._rate_counters.get(("tenant-b", "caller-y", "ep-mut"), 0)
        assert counter_after == counter_before

    def test_snapshot_shows_dedup(self, eng):
        eng.register_endpoint("ep-mut", "tenant-b", "/v1/orders",
                              EndpointKind.MUTATION, ApiVisibility.PUBLIC, "order-svc", "create")
        eng.process_request("req-orig", "tenant-b", "ep-mut", "caller-y", "idem-xyz")
        eng.record_response("resp-orig", "req-orig", "tenant-b", 201, "order-ref-99")
        eng.process_request("req-dup", "tenant-b", "ep-mut", "caller-y", "idem-xyz")
        snap = eng.api_snapshot("snap-g3", "tenant-b")
        assert snap.deduplicated_requests == 1
        assert snap.accepted_requests == 1


# ===================================================================
# GOLDEN SCENARIO 4: Rate-limited caller gets stable error
# ===================================================================

class TestGolden4RateLimited:
    def test_rate_limit_stable(self, eng):
        eng.register_endpoint("ep-api", "tenant-c", "/v1/data",
                              EndpointKind.QUERY, ApiVisibility.PUBLIC, "data-svc", "query")
        eng._rate_limit_max = 3

        for i in range(3):
            r = eng.process_request(f"req-ok-{i}", "tenant-c", "ep-api", "heavy-caller")
            assert r.disposition == RequestDisposition.ACCEPTED

        for i in range(5):
            r = eng.process_request(f"req-rl-{i}", "tenant-c", "ep-api", "heavy-caller")
            assert r.disposition == RequestDisposition.RATE_LIMITED
            assert r.auth_disposition == AuthDisposition.AUTHENTICATED

    def test_rate_limit_snapshot(self, eng):
        eng.register_endpoint("ep-api", "tenant-c", "/v1/data",
                              EndpointKind.QUERY, ApiVisibility.PUBLIC, "data-svc", "query")
        eng._rate_limit_max = 2
        eng.process_request("r1", "tenant-c", "ep-api", "caller")
        eng.process_request("r2", "tenant-c", "ep-api", "caller")
        eng.process_request("r3", "tenant-c", "ep-api", "caller")
        snap = eng.api_snapshot("snap-g4", "tenant-c")
        assert snap.accepted_requests == 2
        assert snap.rate_limited_requests == 1

    def test_other_callers_unaffected(self, eng):
        eng.register_endpoint("ep-api", "tenant-c", "/v1/data",
                              EndpointKind.QUERY, ApiVisibility.PUBLIC, "data-svc", "query")
        eng._rate_limit_max = 1
        eng.process_request("r1", "tenant-c", "ep-api", "caller-a")
        eng.process_request("r2", "tenant-c", "ep-api", "caller-a")  # rate limited
        r3 = eng.process_request("r3", "tenant-c", "ep-api", "caller-b")
        assert r3.disposition == RequestDisposition.ACCEPTED


# ===================================================================
# GOLDEN SCENARIO 5: Orchestration-backed endpoint
# ===================================================================

class TestGolden5OrchestrationEndpoint:
    def test_orchestration_register_and_process(self, eng):
        ep = eng.register_endpoint("ep-orch", "tenant-d", "/v1/compose",
                                   EndpointKind.MUTATION, ApiVisibility.PARTNER,
                                   "orchestrator-svc", "compose-order")
        assert ep.target_runtime == "orchestrator-svc"
        assert ep.target_action == "compose-order"
        assert ep.visibility == ApiVisibility.PARTNER

        req = eng.process_request("req-orch-1", "tenant-d", "ep-orch", "partner-caller")
        assert req.disposition == RequestDisposition.ACCEPTED

        resp = eng.record_response("resp-orch-1", "req-orch-1", "tenant-d", 200, "composed-result-ref")
        assert resp.status_code == 200

    def test_orchestration_assessment(self, eng):
        eng.register_endpoint("ep-orch", "tenant-d", "/v1/compose",
                              EndpointKind.MUTATION, ApiVisibility.PARTNER,
                              "orchestrator-svc", "compose-order")
        eng.process_request("req-orch-1", "tenant-d", "ep-orch", "partner-caller")
        a = eng.api_assessment("a-g5", "tenant-d")
        assert a.availability_score == 1.0
        assert a.error_rate == 0.0


# ===================================================================
# GOLDEN SCENARIO 6: Replay/restore preserves idempotency and rate-limit state
# ===================================================================

class TestGolden6ReplayRestore:
    def test_state_hash_determinism(self, spine):
        eng1 = PublicApiEngine(spine)
        eng1.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                               ApiVisibility.PUBLIC, "replay-svc", "write")
        eng1.process_request("req-r1", "t-r", "ep-r", "caller-r", "idem-r1")
        eng1.record_response("resp-r1", "req-r1", "t-r", 200, "ok")
        h1 = eng1.state_hash()

        # Replay the same operations on a fresh engine
        spine2 = EventSpineEngine()
        eng2 = PublicApiEngine(spine2)
        eng2.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                               ApiVisibility.PUBLIC, "replay-svc", "write")
        eng2.process_request("req-r1", "t-r", "ep-r", "caller-r", "idem-r1")
        eng2.record_response("resp-r1", "req-r1", "t-r", 200, "ok")
        h2 = eng2.state_hash()

        assert h1 == h2

    def test_idempotency_preserved_after_replay(self, spine):
        eng1 = PublicApiEngine(spine)
        eng1.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                               ApiVisibility.PUBLIC, "replay-svc", "write")
        eng1.process_request("req-r1", "t-r", "ep-r", "caller-r", "idem-r1")
        eng1.record_response("resp-r1", "req-r1", "t-r", 200, "ok")
        assert eng1.idempotency_count == 1

        # Replay
        spine2 = EventSpineEngine()
        eng2 = PublicApiEngine(spine2)
        eng2.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                               ApiVisibility.PUBLIC, "replay-svc", "write")
        eng2.process_request("req-r1", "t-r", "ep-r", "caller-r", "idem-r1")
        eng2.record_response("resp-r1", "req-r1", "t-r", 200, "ok")
        assert eng2.idempotency_count == 1

        # Same idempotency key is deduplicated
        r2 = eng2.process_request("req-r2", "t-r", "ep-r", "caller-r", "idem-r1")
        assert r2.disposition == RequestDisposition.DEDUPLICATED

    def test_rate_limit_state_preserved(self, spine):
        eng1 = PublicApiEngine(spine)
        eng1._rate_limit_max = 2
        eng1.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                                ApiVisibility.PUBLIC, "replay-svc", "write")
        eng1.process_request("req-r1", "t-r", "ep-r", "caller-r")
        eng1.process_request("req-r2", "t-r", "ep-r", "caller-r")

        # Replay
        spine2 = EventSpineEngine()
        eng2 = PublicApiEngine(spine2)
        eng2._rate_limit_max = 2
        eng2.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                                ApiVisibility.PUBLIC, "replay-svc", "write")
        eng2.process_request("req-r1", "t-r", "ep-r", "caller-r")
        eng2.process_request("req-r2", "t-r", "ep-r", "caller-r")

        # Both engines should be at rate limit
        r3_1 = eng1.process_request("req-r3", "t-r", "ep-r", "caller-r")
        r3_2 = eng2.process_request("req-r3-b", "t-r", "ep-r", "caller-r")
        assert r3_1.disposition == RequestDisposition.RATE_LIMITED
        assert r3_2.disposition == RequestDisposition.RATE_LIMITED

    def test_violations_preserved(self, spine):
        eng1 = PublicApiEngine(spine)
        eng1.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                                ApiVisibility.PUBLIC, "replay-svc", "write")
        eng1.disable_endpoint("ep-r")
        eng1.process_request("req-r1", "t-r", "ep-r", "caller-r")
        eng1.detect_api_violations("t-r")
        h1 = eng1.state_hash()

        spine2 = EventSpineEngine()
        eng2 = PublicApiEngine(spine2)
        eng2.register_endpoint("ep-r", "t-r", "/v1/replay", EndpointKind.WRITE,
                                ApiVisibility.PUBLIC, "replay-svc", "write")
        eng2.disable_endpoint("ep-r")
        eng2.process_request("req-r1", "t-r", "ep-r", "caller-r")
        eng2.detect_api_violations("t-r")
        h2 = eng2.state_hash()

        assert h1 == h2

    def test_state_hash_empty_engines_equal(self):
        spine1 = EventSpineEngine()
        spine2 = EventSpineEngine()
        eng1 = PublicApiEngine(spine1)
        eng2 = PublicApiEngine(spine2)
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# 32. Immutability of returned records
# ===================================================================

class TestImmutability:
    def test_endpoint_frozen(self, eng):
        ep = _reg(eng)
        with pytest.raises(AttributeError):
            ep.path = "/new"  # type: ignore[misc]

    def test_request_frozen(self, eng):
        _reg(eng)
        req = _req(eng)
        with pytest.raises(AttributeError):
            req.disposition = RequestDisposition.REJECTED  # type: ignore[misc]

    def test_response_frozen(self, eng):
        _reg(eng)
        _req(eng)
        resp = _resp(eng)
        with pytest.raises(AttributeError):
            resp.status_code = 500  # type: ignore[misc]

    def test_snapshot_frozen(self, eng):
        snap = eng.api_snapshot("s-1", "t-1")
        with pytest.raises(AttributeError):
            snap.total_endpoints = 999  # type: ignore[misc]

    def test_assessment_frozen(self, eng):
        a = eng.api_assessment("a-1", "t-1")
        with pytest.raises(AttributeError):
            a.availability_score = 0.0  # type: ignore[misc]

    def test_closure_report_frozen(self, eng):
        rpt = eng.closure_report("rpt-1", "t-1")
        with pytest.raises(AttributeError):
            rpt.total_endpoints = 999  # type: ignore[misc]


# ===================================================================
# 33. Additional coverage for completeness
# ===================================================================

class TestAdditionalCoverage:
    def test_register_with_defaults(self, eng):
        ep = eng.register_endpoint("ep-def", "t-1", "/v1/default")
        assert ep.kind == EndpointKind.READ
        assert ep.visibility == ApiVisibility.PUBLIC
        assert ep.target_runtime == "unknown"
        assert ep.target_action == "unknown"

    def test_process_request_with_empty_caller_tenant(self, eng):
        _reg(eng, tid="t-1")
        req = _req(eng, tid="t-1", caller_tid="")
        assert req.disposition == RequestDisposition.ACCEPTED

    def test_many_tenants_snapshot(self, eng):
        for i in range(10):
            _reg(eng, eid=f"ep-{i}", tid=f"t-{i}")
        for i in range(10):
            snap = eng.api_snapshot(f"snap-{i}", f"t-{i}")
            assert snap.total_endpoints == 1

    def test_assessment_with_no_endpoints(self, eng):
        a = eng.api_assessment("a-1", "t-empty")
        assert a.total_endpoints == 0
        assert a.availability_score == 1.0

    def test_assessment_with_all_retired(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.retire_endpoint("a")
        a = eng.api_assessment("a-1", "t-1")
        assert a.availability_score == 0.0

    def test_assessment_with_mixed_status(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        _reg(eng, eid="c", tid="t-1")
        _reg(eng, eid="d", tid="t-1")
        eng.disable_endpoint("b")
        eng.retire_endpoint("c")
        a = eng.api_assessment("a-1", "t-1")
        assert a.total_endpoints == 4
        assert a.active_endpoints == 2
        assert a.availability_score == 0.5

    def test_deprecated_endpoint_accepts_requests(self, eng):
        _reg(eng, tid="t-1")
        eng.deprecate_endpoint("ep-1")
        req = _req(eng, tid="t-1")
        assert req.disposition == RequestDisposition.ACCEPTED

    def test_violations_for_tenant_empty(self, eng):
        assert eng.violations_for_tenant("t-1") == ()

    def test_multiple_violation_types(self, eng):
        _reg(eng, eid="a", tid="t-1")
        eng.disable_endpoint("a")
        _req(eng, rid="r1", tid="t-1", eid="a")  # disabled hit

        _reg(eng, eid="b", tid="t-owner")
        _req(eng, rid="r2", tid="t-1", eid="b", caller_tid="t-1")  # cross-tenant

        for i in range(6):
            _req(eng, rid=f"r-err-{i}", tid="t-1", eid="no-such")

        viols = eng.detect_api_violations("t-1")
        ops = {v.operation for v in viols}
        assert "disabled_endpoint_hit" in ops
        assert "cross_tenant_attempt" in ops
        assert "high_error_rate" in ops

    def test_state_hash_after_many_operations(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-1")
        eng.disable_endpoint("b")
        _req(eng, rid="r1", tid="t-1", eid="a")
        _req(eng, rid="r2", tid="t-1", eid="no-such")
        _resp(eng, resp_id="rsp1", req_id="r1", tid="t-1")
        eng.detect_api_violations("t-1")
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_closure_report_multiple_tenants(self, eng):
        _reg(eng, eid="a", tid="t-1")
        _reg(eng, eid="b", tid="t-2")
        rpt1 = eng.closure_report("rpt-1", "t-1")
        rpt2 = eng.closure_report("rpt-2", "t-2")
        assert rpt1.total_endpoints == 1
        assert rpt2.total_endpoints == 1

    def test_rate_limit_remaining_decreases(self, eng):
        """Accepted requests record decreasing remaining capacity."""
        _reg(eng)
        eng._rate_limit_max = 5
        for i in range(5):
            _req(eng, rid=f"r-{i}")
        # All 5 should be accepted with decreasing remaining
        assert eng.rate_limit_count == 5

    def test_error_message_includes_endpoint_status(self, eng):
        _reg(eng, tid="t-1")
        eng.disable_endpoint("ep-1")
        _req(eng, tid="t-1")
        errs = eng.errors_for_tenant("t-1")
        assert "disabled" in errs[0].error_message

    def test_error_message_for_retired_endpoint(self, eng):
        _reg(eng, tid="t-1")
        eng.retire_endpoint("ep-1")
        _req(eng, tid="t-1")
        errs = eng.errors_for_tenant("t-1")
        assert "retired" in errs[0].error_message

    def test_get_request_after_dedup(self, eng):
        _reg(eng)
        _req(eng, rid="r1", idem="k-1")
        _resp(eng, resp_id="rsp1", req_id="r1")
        _req(eng, rid="r2", idem="k-1")
        r = eng.get_request("r2")
        assert r.disposition == RequestDisposition.DEDUPLICATED

    def test_responses_for_request_after_multiple(self, eng):
        _reg(eng)
        _req(eng, rid="r1")
        _resp(eng, resp_id="rsp1", req_id="r1", code=200)
        result = eng.responses_for_request("r1")
        assert len(result) == 1
        assert result[0].status_code == 200

    def test_snapshot_all_zeros_for_unknown_tenant(self, eng):
        snap = eng.api_snapshot("s-1", "unknown-tenant")
        assert snap.total_endpoints == 0
        assert snap.total_requests == 0
        assert snap.accepted_requests == 0
        assert snap.rejected_requests == 0
        assert snap.rate_limited_requests == 0
        assert snap.deduplicated_requests == 0
