"""Tests for WorkforceRuntimeIntegration bridge.

Covers constructor validation, all 6 assignment methods, memory mesh attachment,
graph attachment, event emission, sequential assignments, escalation, and
multi-tenant isolation.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.workforce_runtime import WorkforceRuntimeEngine
from mcoi_runtime.core.workforce_runtime_integration import WorkforceRuntimeIntegration
from mcoi_runtime.contracts.memory_mesh import MemoryRecord


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engines():
    """Return (EventSpineEngine, MemoryMeshEngine, WorkforceRuntimeEngine) ready to use."""
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    wf = WorkforceRuntimeEngine(es)
    return es, mm, wf


@pytest.fixture()
def populated(engines):
    """Return a WorkforceRuntimeIntegration with two analyst workers registered."""
    es, mm, wf = engines
    wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
    wf.register_worker("w2", "T1", "analyst", "team-a", "Bob", max_assignments=5)
    wi = WorkforceRuntimeIntegration(wf, es, mm)
    return wi, es, mm, wf


# ===================================================================
# Constructor validation
# ===================================================================

class TestConstructorValidation:

    def test_wrong_workforce_engine_type(self, engines):
        es, mm, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="workforce_engine"):
            WorkforceRuntimeIntegration("not-an-engine", es, mm)

    def test_wrong_event_spine_type(self, engines):
        es, mm, wf = engines
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            WorkforceRuntimeIntegration(wf, "not-an-engine", mm)

    def test_wrong_memory_engine_type(self, engines):
        es, _, wf = engines
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            WorkforceRuntimeIntegration(wf, es, "not-an-engine")

    def test_none_workforce_engine(self, engines):
        es, mm, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeIntegration(None, es, mm)

    def test_none_event_spine(self, engines):
        es, mm, wf = engines
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeIntegration(wf, None, mm)

    def test_none_memory_engine(self, engines):
        es, _, wf = engines
        with pytest.raises(RuntimeCoreInvariantError):
            WorkforceRuntimeIntegration(wf, es, None)

    def test_valid_construction(self, populated):
        wi, _, _, _ = populated
        assert isinstance(wi, WorkforceRuntimeIntegration)


# ===================================================================
# assignment_from_campaign
# ===================================================================

class TestAssignmentFromCampaign:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert isinstance(result, dict)

    def test_required_keys(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        expected_keys = {"request_id", "decision_id", "worker_id", "disposition",
                         "tenant_id", "campaign_ref", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["source_type"] == "campaign"

    def test_campaign_ref_field(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["campaign_ref"] == "camp-1"

    def test_disposition_assigned(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["disposition"] == "assigned"

    def test_request_id_preserved(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["request_id"] == "r1"

    def test_decision_id_preserved(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["decision_id"] == "d1"

    def test_tenant_id_preserved(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["tenant_id"] == "T1"

    def test_worker_id_is_one_of_registered(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["worker_id"] in ("w1", "w2")


# ===================================================================
# assignment_from_case_review
# ===================================================================

class TestAssignmentFromCaseReview:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_case_review("r1", "d1", "T1", "case-7", "analyst")
        assert isinstance(result, dict)

    def test_required_keys(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_case_review("r1", "d1", "T1", "case-7", "analyst")
        expected_keys = {"request_id", "decision_id", "worker_id", "disposition",
                         "tenant_id", "case_ref", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_case_review("r1", "d1", "T1", "case-7", "analyst")
        assert result["source_type"] == "case_review"

    def test_case_ref_field(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_case_review("r1", "d1", "T1", "case-7", "analyst")
        assert result["case_ref"] == "case-7"

    def test_disposition_assigned(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_case_review("r1", "d1", "T1", "case-7", "analyst")
        assert result["disposition"] == "assigned"


# ===================================================================
# assignment_from_service_request
# ===================================================================

class TestAssignmentFromServiceRequest:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_service_request("r1", "d1", "T1", "svc-3", "analyst")
        assert isinstance(result, dict)

    def test_required_keys(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_service_request("r1", "d1", "T1", "svc-3", "analyst")
        expected_keys = {"request_id", "decision_id", "worker_id", "disposition",
                         "tenant_id", "service_ref", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_service_request("r1", "d1", "T1", "svc-3", "analyst")
        assert result["source_type"] == "service_request"

    def test_service_ref_field(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_service_request("r1", "d1", "T1", "svc-3", "analyst")
        assert result["service_ref"] == "svc-3"

    def test_disposition_assigned(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_service_request("r1", "d1", "T1", "svc-3", "analyst")
        assert result["disposition"] == "assigned"


# ===================================================================
# assignment_from_remediation
# ===================================================================

class TestAssignmentFromRemediation:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_remediation("r1", "d1", "T1", "rem-9", "analyst")
        assert isinstance(result, dict)

    def test_required_keys(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_remediation("r1", "d1", "T1", "rem-9", "analyst")
        expected_keys = {"request_id", "decision_id", "worker_id", "disposition",
                         "tenant_id", "remediation_ref", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_remediation("r1", "d1", "T1", "rem-9", "analyst")
        assert result["source_type"] == "remediation"

    def test_remediation_ref_field(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_remediation("r1", "d1", "T1", "rem-9", "analyst")
        assert result["remediation_ref"] == "rem-9"

    def test_disposition_assigned(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_remediation("r1", "d1", "T1", "rem-9", "analyst")
        assert result["disposition"] == "assigned"


# ===================================================================
# assignment_from_regulatory_review
# ===================================================================

class TestAssignmentFromRegulatoryReview:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-2", "analyst")
        assert isinstance(result, dict)

    def test_required_keys(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-2", "analyst")
        expected_keys = {"request_id", "decision_id", "worker_id", "disposition",
                         "tenant_id", "regulatory_ref", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-2", "analyst")
        assert result["source_type"] == "regulatory_review"

    def test_regulatory_ref_field(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-2", "analyst")
        assert result["regulatory_ref"] == "reg-2"

    def test_disposition_assigned(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-2", "analyst")
        assert result["disposition"] == "assigned"


# ===================================================================
# assignment_from_human_workflow
# ===================================================================

class TestAssignmentFromHumanWorkflow:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-5", "analyst")
        assert isinstance(result, dict)

    def test_required_keys(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-5", "analyst")
        expected_keys = {"request_id", "decision_id", "worker_id", "disposition",
                         "tenant_id", "workflow_ref", "source_type"}
        assert set(result.keys()) == expected_keys

    def test_source_type(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-5", "analyst")
        assert result["source_type"] == "human_workflow"

    def test_workflow_ref_field(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-5", "analyst")
        assert result["workflow_ref"] == "wf-5"

    def test_disposition_assigned(self, populated):
        wi, *_ = populated
        result = wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-5", "analyst")
        assert result["disposition"] == "assigned"


# ===================================================================
# Memory mesh attachment
# ===================================================================

class TestAttachWorkforceStateToMemoryMesh:

    def test_returns_memory_record(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        assert isinstance(result, MemoryRecord)

    def test_title(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        assert result.title == "Workforce runtime state"

    def test_tags(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        assert result.tags == ("workforce", "capacity", "assignment")

    def test_content_keys(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        expected_keys = {"workers", "role_capacities", "team_capacities",
                         "requests", "decisions", "gaps", "violations"}
        assert set(result.content.keys()) == expected_keys

    def test_content_workers_count(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        assert result.content["workers"] == 2

    def test_content_zero_requests_before_assignment(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        assert result.content["requests"] == 0

    def test_content_after_assignment(self, populated):
        wi, *_ = populated
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        result = wi.attach_workforce_state_to_memory_mesh("scope-2")
        assert result.content["requests"] == 1
        assert result.content["decisions"] == 1

    def test_memory_id_is_string(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_memory_mesh("scope-1")
        assert isinstance(result.memory_id, str)
        assert len(result.memory_id) > 0


# ===================================================================
# Graph attachment
# ===================================================================

class TestAttachWorkforceStateToGraph:

    def test_returns_dict(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_graph("scope-1")
        assert isinstance(result, dict)

    def test_dict_keys(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_graph("scope-1")
        expected_keys = {"scope_ref_id", "workers", "role_capacities",
                         "team_capacities", "requests", "decisions",
                         "gaps", "violations"}
        assert set(result.keys()) == expected_keys

    def test_scope_ref_id(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_graph("scope-1")
        assert result["scope_ref_id"] == "scope-1"

    def test_zero_state(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_graph("scope-1")
        assert result["workers"] == 2
        assert result["requests"] == 0
        assert result["decisions"] == 0
        assert result["gaps"] == 0
        assert result["violations"] == 0

    def test_post_assignment_state(self, populated):
        wi, *_ = populated
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        result = wi.attach_workforce_state_to_graph("scope-1")
        assert result["requests"] == 1
        assert result["decisions"] == 1

    def test_workers_count_correct(self, populated):
        wi, *_ = populated
        result = wi.attach_workforce_state_to_graph("scope-1")
        assert result["workers"] == 2


# ===================================================================
# Event emission
# ===================================================================

class TestEventEmission:

    def test_campaign_emits_events(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        after = es.event_count
        assert after > before

    def test_case_review_emits_events(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.assignment_from_case_review("r1", "d1", "T1", "case-1", "analyst")
        after = es.event_count
        assert after > before

    def test_service_request_emits_events(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.assignment_from_service_request("r1", "d1", "T1", "svc-1", "analyst")
        after = es.event_count
        assert after > before

    def test_remediation_emits_events(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.assignment_from_remediation("r1", "d1", "T1", "rem-1", "analyst")
        after = es.event_count
        assert after > before

    def test_regulatory_review_emits_events(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-1", "analyst")
        after = es.event_count
        assert after > before

    def test_human_workflow_emits_events(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-1", "analyst")
        after = es.event_count
        assert after > before

    def test_memory_mesh_attach_emits_event(self, populated):
        wi, es, _, _ = populated
        before = es.event_count
        wi.attach_workforce_state_to_memory_mesh("scope-1")
        after = es.event_count
        assert after > before

    def test_cumulative_event_count_grows(self, populated):
        wi, es, _, _ = populated
        c0 = es.event_count
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        c1 = es.event_count
        wi.assignment_from_case_review("r2", "d2", "T1", "case-1", "analyst")
        c2 = es.event_count
        assert c2 > c1 > c0


# ===================================================================
# Multiple assignments in sequence
# ===================================================================

class TestMultipleAssignments:

    def test_two_campaigns_different_ids(self, populated):
        wi, *_ = populated
        r1 = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        r2 = wi.assignment_from_campaign("r2", "d2", "T1", "camp-2", "analyst")
        assert r1["request_id"] != r2["request_id"]
        assert r1["decision_id"] != r2["decision_id"]

    def test_mixed_methods_in_sequence(self, populated):
        wi, *_ = populated
        r1 = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        r2 = wi.assignment_from_case_review("r2", "d2", "T1", "case-1", "analyst")
        r3 = wi.assignment_from_service_request("r3", "d3", "T1", "svc-1", "analyst")
        assert r1["source_type"] == "campaign"
        assert r2["source_type"] == "case_review"
        assert r3["source_type"] == "service_request"

    def test_load_balancing_distributes_across_workers(self, populated):
        wi, *_ = populated
        r1 = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        r2 = wi.assignment_from_campaign("r2", "d2", "T1", "camp-2", "analyst")
        workers = {r1["worker_id"], r2["worker_id"]}
        # Both workers should be used since they start at 0 load
        assert len(workers) == 2

    def test_graph_reflects_sequential_assignments(self, populated):
        wi, *_ = populated
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        wi.assignment_from_remediation("r2", "d2", "T1", "rem-1", "analyst")
        graph = wi.attach_workforce_state_to_graph("scope-1")
        assert graph["requests"] == 2
        assert graph["decisions"] == 2

    def test_memory_reflects_sequential_assignments(self, populated):
        wi, *_ = populated
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        wi.assignment_from_regulatory_review("r2", "d2", "T1", "reg-1", "analyst")
        mem = wi.attach_workforce_state_to_memory_mesh("scope-seq")
        assert mem.content["requests"] == 2
        assert mem.content["decisions"] == 2


# ===================================================================
# Escalation when no workers available
# ===================================================================

class TestEscalation:

    def test_escalated_when_role_has_no_workers(self):
        """Register workers for 'analyst' but request 'manager' role -> escalated."""
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "manager")
        assert result["disposition"] == "escalated"

    def test_escalated_worker_id(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        result = wi.assignment_from_case_review("r1", "d1", "T1", "case-1", "manager")
        assert result["worker_id"] == "escalation"

    def test_escalated_service_request(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        result = wi.assignment_from_service_request("r1", "d1", "T1", "svc-1", "director")
        assert result["disposition"] == "escalated"

    def test_escalated_remediation(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        result = wi.assignment_from_remediation("r1", "d1", "T1", "rem-1", "director")
        assert result["disposition"] == "escalated"

    def test_escalated_regulatory_review(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        result = wi.assignment_from_regulatory_review("r1", "d1", "T1", "reg-1", "director")
        assert result["disposition"] == "escalated"

    def test_escalated_human_workflow(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        result = wi.assignment_from_human_workflow("r1", "d1", "T1", "wf-1", "director")
        assert result["disposition"] == "escalated"

    def test_escalated_when_all_workers_at_max(self):
        """Workers exist for role but all are at max capacity."""
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=1)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        # First assignment uses up the only slot
        r1 = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert r1["disposition"] == "assigned"
        # Second should escalate
        r2 = wi.assignment_from_campaign("r2", "d2", "T1", "camp-2", "analyst")
        assert r2["disposition"] == "escalated"


# ===================================================================
# Multi-tenant isolation
# ===================================================================

class TestMultiTenantIsolation:

    def _make_multi_tenant(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        wf = WorkforceRuntimeEngine(es)
        wf.register_worker("w1", "T1", "analyst", "team-a", "Alice", max_assignments=5)
        wf.register_worker("w2", "T2", "analyst", "team-b", "Bob", max_assignments=5)
        wi = WorkforceRuntimeIntegration(wf, es, mm)
        return wi, es, mm, wf

    def test_tenant1_assigned_tenant1_worker(self):
        wi, *_ = self._make_multi_tenant()
        result = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        assert result["worker_id"] == "w1"
        assert result["tenant_id"] == "T1"

    def test_tenant2_assigned_tenant2_worker(self):
        wi, *_ = self._make_multi_tenant()
        result = wi.assignment_from_campaign("r1", "d1", "T2", "camp-1", "analyst")
        assert result["worker_id"] == "w2"
        assert result["tenant_id"] == "T2"

    def test_tenant_with_no_workers_escalates(self):
        wi, *_ = self._make_multi_tenant()
        result = wi.assignment_from_campaign("r1", "d1", "T3", "camp-1", "analyst")
        assert result["disposition"] == "escalated"

    def test_cross_tenant_assignments_independent(self):
        wi, *_ = self._make_multi_tenant()
        r1 = wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        r2 = wi.assignment_from_campaign("r2", "d2", "T2", "camp-2", "analyst")
        assert r1["worker_id"] == "w1"
        assert r2["worker_id"] == "w2"

    def test_graph_counts_are_global(self):
        wi, *_ = self._make_multi_tenant()
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        wi.assignment_from_campaign("r2", "d2", "T2", "camp-2", "analyst")
        graph = wi.attach_workforce_state_to_graph("scope-multi")
        assert graph["workers"] == 2
        assert graph["requests"] == 2
        assert graph["decisions"] == 2

    def test_memory_counts_are_global(self):
        wi, *_ = self._make_multi_tenant()
        wi.assignment_from_campaign("r1", "d1", "T1", "camp-1", "analyst")
        wi.assignment_from_case_review("r2", "d2", "T2", "case-1", "analyst")
        mem = wi.attach_workforce_state_to_memory_mesh("scope-multi")
        assert mem.content["workers"] == 2
        assert mem.content["requests"] == 2
        assert mem.content["decisions"] == 2
