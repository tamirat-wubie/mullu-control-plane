"""Tests for PublicApiIntegration bridge.

Covers all 8 integration methods:
  1. endpoint_for_service_request
  2. endpoint_for_case_review
  3. endpoint_for_reporting_submission
  4. endpoint_for_customer_account
  5. endpoint_for_marketplace_listing
  6. endpoint_for_orchestration_plan
  7. attach_api_state_to_memory_mesh
  8. attach_api_state_to_graph
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.public_api import PublicApiEngine
from mcoi_runtime.core.public_api_integration import PublicApiIntegration
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def es() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture()
def api(es: EventSpineEngine) -> PublicApiEngine:
    return PublicApiEngine(event_spine=es)


@pytest.fixture()
def mem() -> MemoryMeshEngine:
    return MemoryMeshEngine()


@pytest.fixture()
def bridge(api: PublicApiEngine, es: EventSpineEngine, mem: MemoryMeshEngine) -> PublicApiIntegration:
    return PublicApiIntegration(api_engine=api, event_spine=es, memory_engine=mem)


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructorValidation:
    """Invariant: each engine argument must be the correct type."""

    def test_valid_construction(self, api, es, mem):
        b = PublicApiIntegration(api_engine=api, event_spine=es, memory_engine=mem)
        assert b is not None

    def test_rejects_none_api_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="api_engine"):
            PublicApiIntegration(api_engine=None, event_spine=es, memory_engine=mem)

    def test_rejects_string_api_engine(self, es, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="api_engine"):
            PublicApiIntegration(api_engine="bad", event_spine=es, memory_engine=mem)

    def test_rejects_none_event_spine(self, api, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            PublicApiIntegration(api_engine=api, event_spine=None, memory_engine=mem)

    def test_rejects_string_event_spine(self, api, mem):
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            PublicApiIntegration(api_engine=api, event_spine="bad", memory_engine=mem)

    def test_rejects_none_memory_engine(self, api, es):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            PublicApiIntegration(api_engine=api, event_spine=es, memory_engine=None)

    def test_rejects_string_memory_engine(self, api, es):
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            PublicApiIntegration(api_engine=api, event_spine=es, memory_engine="bad")

    def test_rejects_swapped_api_and_spine(self, api, es, mem):
        with pytest.raises(RuntimeCoreInvariantError):
            PublicApiIntegration(api_engine=es, event_spine=api, memory_engine=mem)


# ===================================================================
# 1. endpoint_for_service_request
# ===================================================================

class TestEndpointForServiceRequest:

    def test_returns_dict(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-1", "t1")
        assert isinstance(result, dict)

    def test_default_path(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-2", "t1")
        assert result["path"] == "/api/v1/service-requests"

    def test_custom_path(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-3", "t1", path="/custom/sr")
        assert result["path"] == "/custom/sr"

    def test_kind_is_write(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-4", "t1")
        assert result["kind"] == "write"

    def test_visibility_is_public(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-5", "t1")
        assert result["visibility"] == "public"

    def test_target_runtime(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-6", "t1")
        assert result["target_runtime"] == "service_catalog"

    def test_source_type(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-7", "t1")
        assert result["source_type"] == "service_request"

    def test_endpoint_id_preserved(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-8", "t1")
        assert result["endpoint_id"] == "ep-sr-8"

    def test_tenant_id_preserved(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-9", "tenant-abc")
        assert result["tenant_id"] == "tenant-abc"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.endpoint_for_service_request("ep-sr-10", "t1")
        # register_endpoint emits 1 + integration emits 1 = at least +2
        assert es.event_count > before

    def test_has_all_eight_keys(self, bridge):
        result = bridge.endpoint_for_service_request("ep-sr-11", "t1")
        expected_keys = {"endpoint_id", "tenant_id", "path", "kind", "visibility",
                         "target_runtime", "target_action", "source_type"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 2. endpoint_for_case_review
# ===================================================================

class TestEndpointForCaseReview:

    def test_returns_dict(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-1", "t1")
        assert isinstance(result, dict)

    def test_default_path(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-2", "t1")
        assert result["path"] == "/api/v1/case-reviews"

    def test_custom_path(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-3", "t1", path="/v2/cases")
        assert result["path"] == "/v2/cases"

    def test_kind_is_write(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-4", "t1")
        assert result["kind"] == "write"

    def test_visibility_is_internal(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-5", "t1")
        assert result["visibility"] == "internal"

    def test_target_runtime(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-6", "t1")
        assert result["target_runtime"] == "case"

    def test_source_type(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-7", "t1")
        assert result["source_type"] == "case_review"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.endpoint_for_case_review("ep-cr-8", "t1")
        assert es.event_count > before

    def test_has_all_eight_keys(self, bridge):
        result = bridge.endpoint_for_case_review("ep-cr-9", "t1")
        expected_keys = {"endpoint_id", "tenant_id", "path", "kind", "visibility",
                         "target_runtime", "target_action", "source_type"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 3. endpoint_for_reporting_submission
# ===================================================================

class TestEndpointForReportingSubmission:

    def test_returns_dict(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-1", "t1")
        assert isinstance(result, dict)

    def test_default_path(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-2", "t1")
        assert result["path"] == "/api/v1/reports"

    def test_custom_path(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-3", "t1", path="/reports/v2")
        assert result["path"] == "/reports/v2"

    def test_kind_is_mutation(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-4", "t1")
        assert result["kind"] == "mutation"

    def test_visibility_is_partner(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-5", "t1")
        assert result["visibility"] == "partner"

    def test_target_runtime(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-6", "t1")
        assert result["target_runtime"] == "reporting"

    def test_source_type(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-7", "t1")
        assert result["source_type"] == "reporting_submission"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.endpoint_for_reporting_submission("ep-rs-8", "t1")
        assert es.event_count > before

    def test_has_all_eight_keys(self, bridge):
        result = bridge.endpoint_for_reporting_submission("ep-rs-9", "t1")
        expected_keys = {"endpoint_id", "tenant_id", "path", "kind", "visibility",
                         "target_runtime", "target_action", "source_type"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 4. endpoint_for_customer_account
# ===================================================================

class TestEndpointForCustomerAccount:

    def test_returns_dict(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-1", "t1")
        assert isinstance(result, dict)

    def test_default_path(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-2", "t1")
        assert result["path"] == "/api/v1/customers"

    def test_custom_path(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-3", "t1", path="/cust/v3")
        assert result["path"] == "/cust/v3"

    def test_kind_is_query(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-4", "t1")
        assert result["kind"] == "query"

    def test_visibility_is_public(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-5", "t1")
        assert result["visibility"] == "public"

    def test_target_runtime(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-6", "t1")
        assert result["target_runtime"] == "customer"

    def test_source_type(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-7", "t1")
        assert result["source_type"] == "customer_account"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.endpoint_for_customer_account("ep-ca-8", "t1")
        assert es.event_count > before

    def test_has_all_eight_keys(self, bridge):
        result = bridge.endpoint_for_customer_account("ep-ca-9", "t1")
        expected_keys = {"endpoint_id", "tenant_id", "path", "kind", "visibility",
                         "target_runtime", "target_action", "source_type"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 5. endpoint_for_marketplace_listing
# ===================================================================

class TestEndpointForMarketplaceListing:

    def test_returns_dict(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-1", "t1")
        assert isinstance(result, dict)

    def test_default_path(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-2", "t1")
        assert result["path"] == "/api/v1/marketplace"

    def test_custom_path(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-3", "t1", path="/market/v2")
        assert result["path"] == "/market/v2"

    def test_kind_is_read(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-4", "t1")
        assert result["kind"] == "read"

    def test_visibility_is_public(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-5", "t1")
        assert result["visibility"] == "public"

    def test_target_runtime(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-6", "t1")
        assert result["target_runtime"] == "marketplace"

    def test_source_type(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-7", "t1")
        assert result["source_type"] == "marketplace_listing"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.endpoint_for_marketplace_listing("ep-ml-8", "t1")
        assert es.event_count > before

    def test_has_all_eight_keys(self, bridge):
        result = bridge.endpoint_for_marketplace_listing("ep-ml-9", "t1")
        expected_keys = {"endpoint_id", "tenant_id", "path", "kind", "visibility",
                         "target_runtime", "target_action", "source_type"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 6. endpoint_for_orchestration_plan
# ===================================================================

class TestEndpointForOrchestrationPlan:

    def test_returns_dict(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-1", "t1")
        assert isinstance(result, dict)

    def test_default_path(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-2", "t1")
        assert result["path"] == "/api/v1/orchestrations"

    def test_custom_path(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-3", "t1", path="/orch/v2")
        assert result["path"] == "/orch/v2"

    def test_kind_is_write(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-4", "t1")
        assert result["kind"] == "write"

    def test_visibility_is_admin(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-5", "t1")
        assert result["visibility"] == "admin"

    def test_target_runtime(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-6", "t1")
        assert result["target_runtime"] == "meta_orchestration"

    def test_source_type(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-7", "t1")
        assert result["source_type"] == "orchestration_plan"

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.endpoint_for_orchestration_plan("ep-op-8", "t1")
        assert es.event_count > before

    def test_has_all_eight_keys(self, bridge):
        result = bridge.endpoint_for_orchestration_plan("ep-op-9", "t1")
        expected_keys = {"endpoint_id", "tenant_id", "path", "kind", "visibility",
                         "target_runtime", "target_action", "source_type"}
        assert set(result.keys()) == expected_keys


# ===================================================================
# 7. attach_api_state_to_memory_mesh
# ===================================================================

class TestAttachApiStateToMemoryMesh:

    def test_returns_memory_record(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-1")
        assert isinstance(result, MemoryRecord)

    def test_tags_include_public_api(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-2")
        assert "public_api" in result.tags

    def test_tags_include_product_surface(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-3")
        assert "product_surface" in result.tags

    def test_tags_include_endpoints(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-4")
        assert "endpoints" in result.tags

    def test_tags_exactly_three(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-5")
        assert len(result.tags) == 3

    def test_content_has_seven_keys(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-6")
        expected = {
            "total_endpoints", "active_endpoints", "total_requests",
            "accepted_requests", "rejected_requests",
            "rate_limited_requests", "deduplicated_requests",
        }
        assert set(result.content.keys()) == expected

    def test_content_values_are_integers(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-7")
        for v in result.content.values():
            assert isinstance(v, int)

    def test_emits_event(self, bridge, es):
        before = es.event_count
        bridge.attach_api_state_to_memory_mesh("scope-8")
        assert es.event_count > before

    def test_memory_added_to_engine(self, bridge, mem):
        before = mem.memory_count
        bridge.attach_api_state_to_memory_mesh("scope-9")
        assert mem.memory_count == before + 1

    def test_scope_ref_id_preserved(self, bridge):
        result = bridge.attach_api_state_to_memory_mesh("scope-10")
        assert result.scope_ref_id == "scope-10"
        assert result.title == "Public API state"
        assert "scope-10" not in result.title

    def test_snapshot_reflects_registered_endpoints(self, bridge):
        bridge.endpoint_for_service_request("ep-snap-1", "scope-11")
        result = bridge.attach_api_state_to_memory_mesh("scope-11")
        assert result.content["total_endpoints"] >= 1

    def test_snapshot_counts_active_endpoints(self, bridge):
        bridge.endpoint_for_marketplace_listing("ep-snap-2", "scope-12")
        result = bridge.attach_api_state_to_memory_mesh("scope-12")
        assert result.content["active_endpoints"] >= 1


# ===================================================================
# 8. attach_api_state_to_graph
# ===================================================================

class TestAttachApiStateToGraph:

    def test_returns_dict(self, bridge):
        result = bridge.attach_api_state_to_graph("gscope-1")
        assert isinstance(result, dict)

    def test_has_eight_keys(self, bridge):
        result = bridge.attach_api_state_to_graph("gscope-2")
        expected = {
            "scope_ref_id", "total_endpoints", "active_endpoints",
            "total_requests", "accepted_requests", "rejected_requests",
            "rate_limited_requests", "deduplicated_requests",
        }
        assert set(result.keys()) == expected

    def test_scope_ref_id_preserved(self, bridge):
        result = bridge.attach_api_state_to_graph("gscope-3")
        assert result["scope_ref_id"] == "gscope-3"

    def test_numeric_values(self, bridge):
        result = bridge.attach_api_state_to_graph("gscope-4")
        for k, v in result.items():
            if k != "scope_ref_id":
                assert isinstance(v, int)

    def test_zero_state_when_no_endpoints(self, bridge):
        result = bridge.attach_api_state_to_graph("gscope-5")
        assert result["total_endpoints"] == 0
        assert result["active_endpoints"] == 0
        assert result["total_requests"] == 0

    def test_reflects_registered_endpoints(self, bridge):
        bridge.endpoint_for_customer_account("ep-g-1", "gscope-6")
        result = bridge.attach_api_state_to_graph("gscope-6")
        assert result["total_endpoints"] >= 1
        assert result["active_endpoints"] >= 1

    def test_emits_event_from_snapshot(self, bridge, es):
        before = es.event_count
        bridge.attach_api_state_to_graph("gscope-7")
        # api_snapshot itself emits an event
        assert es.event_count > before


# ===================================================================
# Cross-method / integration scenarios
# ===================================================================

class TestCrossMethodIntegration:

    def test_all_six_endpoints_unique_ids(self, bridge):
        """Register one of each endpoint type; all should succeed with unique ids."""
        r1 = bridge.endpoint_for_service_request("ep-all-1", "t1")
        r2 = bridge.endpoint_for_case_review("ep-all-2", "t1")
        r3 = bridge.endpoint_for_reporting_submission("ep-all-3", "t1")
        r4 = bridge.endpoint_for_customer_account("ep-all-4", "t1")
        r5 = bridge.endpoint_for_marketplace_listing("ep-all-5", "t1")
        r6 = bridge.endpoint_for_orchestration_plan("ep-all-6", "t1")
        ids = {r["endpoint_id"] for r in [r1, r2, r3, r4, r5, r6]}
        assert len(ids) == 6

    def test_duplicate_endpoint_id_raises(self, bridge):
        bridge.endpoint_for_service_request("ep-dup-1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            bridge.endpoint_for_case_review("ep-dup-1", "t1")

    def test_snapshot_after_multiple_registrations(self, bridge):
        bridge.endpoint_for_service_request("ep-multi-1", "tenant-x")
        bridge.endpoint_for_case_review("ep-multi-2", "tenant-x")
        bridge.endpoint_for_marketplace_listing("ep-multi-3", "tenant-x")
        result = bridge.attach_api_state_to_graph("tenant-x")
        assert result["total_endpoints"] == 3
        assert result["active_endpoints"] == 3

    def test_memory_mesh_after_multiple_registrations(self, bridge):
        bridge.endpoint_for_orchestration_plan("ep-mm-1", "tenant-y")
        bridge.endpoint_for_reporting_submission("ep-mm-2", "tenant-y")
        rec = bridge.attach_api_state_to_memory_mesh("tenant-y")
        assert rec.content["total_endpoints"] == 2

    def test_event_count_monotonic(self, bridge, es):
        """Every method call should increase event_count."""
        counts = [es.event_count]
        bridge.endpoint_for_service_request("ep-ec-1", "t1")
        counts.append(es.event_count)
        bridge.endpoint_for_case_review("ep-ec-2", "t1")
        counts.append(es.event_count)
        bridge.attach_api_state_to_memory_mesh("t1")
        counts.append(es.event_count)
        bridge.attach_api_state_to_graph("t1")
        counts.append(es.event_count)
        for a, b in zip(counts, counts[1:]):
            assert b > a

    def test_graph_and_memory_agree_on_counts(self, bridge):
        bridge.endpoint_for_customer_account("ep-agree-1", "scope-agree")
        bridge.endpoint_for_marketplace_listing("ep-agree-2", "scope-agree")
        graph = bridge.attach_api_state_to_graph("scope-agree")
        mem = bridge.attach_api_state_to_memory_mesh("scope-agree")
        assert graph["total_endpoints"] == mem.content["total_endpoints"]
        assert graph["active_endpoints"] == mem.content["active_endpoints"]

    def test_different_tenants_isolated(self, bridge):
        bridge.endpoint_for_service_request("ep-iso-1", "alpha")
        bridge.endpoint_for_case_review("ep-iso-2", "beta")
        g_alpha = bridge.attach_api_state_to_graph("alpha")
        g_beta = bridge.attach_api_state_to_graph("beta")
        assert g_alpha["total_endpoints"] == 1
        assert g_beta["total_endpoints"] == 1

    def test_target_action_values(self, bridge):
        """Each endpoint method sets a distinct target_action."""
        r1 = bridge.endpoint_for_service_request("ep-ta-1", "t1")
        r2 = bridge.endpoint_for_case_review("ep-ta-2", "t1")
        r3 = bridge.endpoint_for_reporting_submission("ep-ta-3", "t1")
        r4 = bridge.endpoint_for_customer_account("ep-ta-4", "t1")
        r5 = bridge.endpoint_for_marketplace_listing("ep-ta-5", "t1")
        r6 = bridge.endpoint_for_orchestration_plan("ep-ta-6", "t1")
        assert r1["target_action"] == "submit"
        assert r2["target_action"] == "review"
        assert r3["target_action"] == "submit"
        assert r4["target_action"] == "query"
        assert r5["target_action"] == "list"
        assert r6["target_action"] == "execute"
