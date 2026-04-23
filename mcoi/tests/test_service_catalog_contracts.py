"""Tests for service catalog contracts."""

from __future__ import annotations

import dataclasses
import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.service_catalog import (
    CatalogAssessment,
    CatalogItemKind,
    EntitlementDisposition,
    EntitlementRule,
    FulfillmentDecision,
    FulfillmentStatus,
    FulfillmentTask,
    RequestAssignment,
    RequestPriority,
    RequestSnapshot,
    RequestStatus,
    RequestViolation,
    ServiceCatalogItem,
    ServiceClosureReport,
    ServiceRequest,
    ServiceStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _catalog_item(**overrides) -> ServiceCatalogItem:
    defaults = dict(
        item_id="item-001",
        name="VM Provisioning",
        tenant_id="t-001",
        kind=CatalogItemKind.INFRASTRUCTURE,
        status=ServiceStatus.ACTIVE,
        owner_ref="owner-001",
        sla_ref="sla-001",
        approval_required=False,
        estimated_cost=100.0,
        created_at=TS,
    )
    defaults.update(overrides)
    return ServiceCatalogItem(**defaults)


def _service_request(**overrides) -> ServiceRequest:
    defaults = dict(
        request_id="req-001",
        item_id="item-001",
        tenant_id="t-001",
        requester_ref="user-001",
        status=RequestStatus.DRAFT,
        priority=RequestPriority.MEDIUM,
        description="Need a VM",
        estimated_cost=50.0,
        submitted_at=TS,
        due_at="",
    )
    defaults.update(overrides)
    return ServiceRequest(**defaults)


def _assignment(**overrides) -> RequestAssignment:
    defaults = dict(
        assignment_id="asgn-001",
        request_id="req-001",
        assignee_ref="eng-001",
        assigned_by="mgr-001",
        assigned_at=TS,
    )
    defaults.update(overrides)
    return RequestAssignment(**defaults)


def _entitlement_rule(**overrides) -> EntitlementRule:
    defaults = dict(
        rule_id="rule-001",
        item_id="item-001",
        tenant_id="t-001",
        disposition=EntitlementDisposition.GRANTED,
        scope_ref="scope-001",
        reason="Policy allows",
        evaluated_at=TS,
    )
    defaults.update(overrides)
    return EntitlementRule(**defaults)


def _fulfillment_task(**overrides) -> FulfillmentTask:
    defaults = dict(
        task_id="task-001",
        request_id="req-001",
        assignee_ref="eng-001",
        created_by="mgr-001",
        status=FulfillmentStatus.PENDING,
        description="Deploy VM",
        dependency_ref="dep-001",
        created_at=TS,
        completed_at="",
    )
    defaults.update(overrides)
    return FulfillmentTask(**defaults)


def _fulfillment_decision(**overrides) -> FulfillmentDecision:
    defaults = dict(
        decision_id="dec-001",
        request_id="req-001",
        disposition="approved",
        decided_by="mgr-001",
        reason="Meets criteria",
        decided_at=TS,
    )
    defaults.update(overrides)
    return FulfillmentDecision(**defaults)


def _request_snapshot(**overrides) -> RequestSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_catalog_items=10,
        total_requests=50,
        total_submitted=20,
        total_in_fulfillment=5,
        total_fulfilled=15,
        total_denied=3,
        total_tasks=25,
        total_violations=2,
        total_estimated_cost=5000.0,
        captured_at=TS,
    )
    defaults.update(overrides)
    return RequestSnapshot(**defaults)


def _request_violation(**overrides) -> RequestViolation:
    defaults = dict(
        violation_id="viol-001",
        request_id="req-001",
        tenant_id="t-001",
        operation="reopen",
        reason="Fulfilled requests cannot be re-opened",
        detected_at=TS,
    )
    defaults.update(overrides)
    return RequestViolation(**defaults)


def _closure_report(**overrides) -> ServiceClosureReport:
    defaults = dict(
        report_id="rpt-001",
        tenant_id="t-001",
        total_requests=100,
        total_fulfilled=80,
        total_denied=10,
        total_cancelled=5,
        total_tasks=50,
        total_violations=3,
        total_estimated_cost=25000.0,
        closed_at=TS,
    )
    defaults.update(overrides)
    return ServiceClosureReport(**defaults)


def _catalog_assessment(**overrides) -> CatalogAssessment:
    defaults = dict(
        assessment_id="assess-001",
        item_id="item-001",
        fulfillment_rate=0.85,
        satisfaction_score=0.9,
        assessed_by="auditor-001",
        assessed_at=TS,
    )
    defaults.update(overrides)
    return CatalogAssessment(**defaults)


# ===================================================================
# 1. Enum coverage
# ===================================================================


class TestServiceStatusEnum:
    def test_active_value(self):
        assert ServiceStatus.ACTIVE.value == "active"

    def test_draft_value(self):
        assert ServiceStatus.DRAFT.value == "draft"

    def test_deprecated_value(self):
        assert ServiceStatus.DEPRECATED.value == "deprecated"

    def test_retired_value(self):
        assert ServiceStatus.RETIRED.value == "retired"

    def test_member_count(self):
        assert len(ServiceStatus) == 4

    def test_isinstance(self):
        assert isinstance(ServiceStatus.ACTIVE, ServiceStatus)

    def test_all_members_are_enum(self):
        for member in ServiceStatus:
            assert isinstance(member, ServiceStatus)


class TestRequestStatusEnum:
    def test_draft_value(self):
        assert RequestStatus.DRAFT.value == "draft"

    def test_submitted_value(self):
        assert RequestStatus.SUBMITTED.value == "submitted"

    def test_entitled_value(self):
        assert RequestStatus.ENTITLED.value == "entitled"

    def test_pending_approval_value(self):
        assert RequestStatus.PENDING_APPROVAL.value == "pending_approval"

    def test_approved_value(self):
        assert RequestStatus.APPROVED.value == "approved"

    def test_in_fulfillment_value(self):
        assert RequestStatus.IN_FULFILLMENT.value == "in_fulfillment"

    def test_fulfilled_value(self):
        assert RequestStatus.FULFILLED.value == "fulfilled"

    def test_denied_value(self):
        assert RequestStatus.DENIED.value == "denied"

    def test_cancelled_value(self):
        assert RequestStatus.CANCELLED.value == "cancelled"

    def test_member_count(self):
        assert len(RequestStatus) == 9

    def test_isinstance(self):
        assert isinstance(RequestStatus.DRAFT, RequestStatus)


class TestRequestPriorityEnum:
    def test_low_value(self):
        assert RequestPriority.LOW.value == "low"

    def test_medium_value(self):
        assert RequestPriority.MEDIUM.value == "medium"

    def test_high_value(self):
        assert RequestPriority.HIGH.value == "high"

    def test_critical_value(self):
        assert RequestPriority.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(RequestPriority) == 4

    def test_isinstance(self):
        assert isinstance(RequestPriority.LOW, RequestPriority)


class TestFulfillmentStatusEnum:
    def test_pending_value(self):
        assert FulfillmentStatus.PENDING.value == "pending"

    def test_in_progress_value(self):
        assert FulfillmentStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_value(self):
        assert FulfillmentStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert FulfillmentStatus.FAILED.value == "failed"

    def test_cancelled_value(self):
        assert FulfillmentStatus.CANCELLED.value == "cancelled"

    def test_member_count(self):
        assert len(FulfillmentStatus) == 5

    def test_isinstance(self):
        assert isinstance(FulfillmentStatus.PENDING, FulfillmentStatus)


class TestEntitlementDispositionEnum:
    def test_granted_value(self):
        assert EntitlementDisposition.GRANTED.value == "granted"

    def test_denied_value(self):
        assert EntitlementDisposition.DENIED.value == "denied"

    def test_requires_approval_value(self):
        assert EntitlementDisposition.REQUIRES_APPROVAL.value == "requires_approval"

    def test_expired_value(self):
        assert EntitlementDisposition.EXPIRED.value == "expired"

    def test_member_count(self):
        assert len(EntitlementDisposition) == 4

    def test_isinstance(self):
        assert isinstance(EntitlementDisposition.GRANTED, EntitlementDisposition)


class TestCatalogItemKindEnum:
    def test_infrastructure_value(self):
        assert CatalogItemKind.INFRASTRUCTURE.value == "infrastructure"

    def test_application_value(self):
        assert CatalogItemKind.APPLICATION.value == "application"

    def test_access_value(self):
        assert CatalogItemKind.ACCESS.value == "access"

    def test_support_value(self):
        assert CatalogItemKind.SUPPORT.value == "support"

    def test_procurement_value(self):
        assert CatalogItemKind.PROCUREMENT.value == "procurement"

    def test_data_value(self):
        assert CatalogItemKind.DATA.value == "data"

    def test_member_count(self):
        assert len(CatalogItemKind) == 6

    def test_isinstance(self):
        assert isinstance(CatalogItemKind.INFRASTRUCTURE, CatalogItemKind)

    def test_all_members_are_enum(self):
        for member in CatalogItemKind:
            assert isinstance(member, CatalogItemKind)


# ===================================================================
# 2. Dataclass construction (valid)
# ===================================================================


class TestServiceCatalogItemConstruction:
    def test_valid_defaults(self):
        item = _catalog_item()
        assert item.item_id == "item-001"
        assert item.name == "VM Provisioning"
        assert item.tenant_id == "t-001"
        assert item.kind == CatalogItemKind.INFRASTRUCTURE
        assert item.status == ServiceStatus.ACTIVE
        assert item.owner_ref == "owner-001"
        assert item.sla_ref == "sla-001"
        assert item.approval_required is False
        assert item.estimated_cost == 100.0
        assert item.created_at == TS

    def test_approval_required_true(self):
        item = _catalog_item(approval_required=True, approver_refs=("ops-lead",))
        assert item.approval_required is True
        assert item.approver_refs == ("ops-lead",)

    def test_duplicate_approver_refs_rejected(self):
        with pytest.raises(ValueError, match="^approver_refs must not contain duplicates$") as exc_info:
            _catalog_item(approver_refs=("ops-lead", "ops-lead"))
        message = str(exc_info.value)
        assert message == "approver_refs must not contain duplicates"
        assert "ops-lead" not in message

    def test_system_not_allowed_in_approver_refs(self):
        with pytest.raises(ValueError, match="^approver_refs must exclude system$") as exc_info:
            _catalog_item(approver_refs=("system", "ops-lead"))
        message = str(exc_info.value)
        assert message == "approver_refs must exclude system"
        assert "ops-lead" not in message
        assert "(" not in message

    def test_system_not_allowed_as_owner_ref(self):
        with pytest.raises(ValueError, match="^owner_ref must exclude system$") as exc_info:
            _catalog_item(owner_ref="system")
        message = str(exc_info.value)
        assert message == "owner_ref must exclude system"
        assert "owner-001" not in message
        assert "(" not in message

    def test_owner_ref_not_allowed_in_approver_refs(self):
        with pytest.raises(ValueError, match="^approver_refs must exclude owner_ref$") as exc_info:
            _catalog_item(owner_ref="ops-lead", approver_refs=("ops-lead", "cfo"))
        message = str(exc_info.value)
        assert message == "approver_refs must exclude owner_ref"
        assert "ops-lead" not in message

    def test_approval_required_without_owner_ref_rejected(self):
        with pytest.raises(ValueError, match="^approval_required items must declare owner_ref$") as exc_info:
            _catalog_item(owner_ref="", approval_required=True, approver_refs=("ops-lead",))
        message = str(exc_info.value)
        assert message == "approval_required items must declare owner_ref"
        assert "owner-001" not in message

    def test_approval_required_without_approver_refs_rejected(self):
        with pytest.raises(ValueError, match="^approval_required items must declare approver_refs$") as exc_info:
            _catalog_item(approval_required=True, approver_refs=())
        message = str(exc_info.value)
        assert message == "approval_required items must declare approver_refs"
        assert "item-001" not in message

    def test_all_catalog_item_kinds(self):
        for kind in CatalogItemKind:
            item = _catalog_item(kind=kind)
            assert item.kind == kind

    def test_all_service_statuses(self):
        for status in ServiceStatus:
            item = _catalog_item(status=status)
            assert item.status == status

    def test_zero_cost(self):
        item = _catalog_item(estimated_cost=0.0)
        assert item.estimated_cost == 0.0

    def test_is_dataclass(self):
        item = _catalog_item()
        assert dataclasses.is_dataclass(item)

    def test_with_metadata(self):
        item = _catalog_item(metadata={"region": "us-east-1"})
        assert item.metadata["region"] == "us-east-1"


class TestServiceRequestConstruction:
    def test_valid_defaults(self):
        req = _service_request()
        assert req.request_id == "req-001"
        assert req.item_id == "item-001"
        assert req.tenant_id == "t-001"
        assert req.requester_ref == "user-001"
        assert req.status == RequestStatus.DRAFT
        assert req.priority == RequestPriority.MEDIUM
        assert req.description == "Need a VM"
        assert req.estimated_cost == 50.0
        assert req.submitted_at == TS
        assert req.due_at == ""

    def test_with_due_at(self):
        req = _service_request(due_at=TS2)
        assert req.due_at == TS2

    def test_all_request_statuses(self):
        for status in RequestStatus:
            req = _service_request(status=status)
            assert req.status == status

    def test_all_priorities(self):
        for priority in RequestPriority:
            req = _service_request(priority=priority)
            assert req.priority == priority

    def test_is_dataclass(self):
        req = _service_request()
        assert dataclasses.is_dataclass(req)

    def test_with_metadata(self):
        req = _service_request(metadata={"urgency": "asap"})
        assert req.metadata["urgency"] == "asap"


class TestRequestAssignmentConstruction:
    def test_valid_defaults(self):
        asgn = _assignment()
        assert asgn.assignment_id == "asgn-001"
        assert asgn.request_id == "req-001"
        assert asgn.assignee_ref == "eng-001"
        assert asgn.assigned_by == "mgr-001"
        assert asgn.assigned_at == TS

    def test_is_dataclass(self):
        asgn = _assignment()
        assert dataclasses.is_dataclass(asgn)

    def test_with_metadata(self):
        asgn = _assignment(metadata={"team": "infra"})
        assert asgn.metadata["team"] == "infra"


class TestEntitlementRuleConstruction:
    def test_valid_defaults(self):
        rule = _entitlement_rule()
        assert rule.rule_id == "rule-001"
        assert rule.item_id == "item-001"
        assert rule.tenant_id == "t-001"
        assert rule.disposition == EntitlementDisposition.GRANTED
        assert rule.scope_ref == "scope-001"
        assert rule.reason == "Policy allows"
        assert rule.evaluated_at == TS

    def test_all_dispositions(self):
        for disp in EntitlementDisposition:
            rule = _entitlement_rule(disposition=disp)
            assert rule.disposition == disp

    def test_is_dataclass(self):
        rule = _entitlement_rule()
        assert dataclasses.is_dataclass(rule)

    def test_with_metadata(self):
        rule = _entitlement_rule(metadata={"policy": "p-001"})
        assert rule.metadata["policy"] == "p-001"


class TestFulfillmentTaskConstruction:
    def test_valid_defaults(self):
        task = _fulfillment_task()
        assert task.task_id == "task-001"
        assert task.request_id == "req-001"
        assert task.assignee_ref == "eng-001"
        assert task.created_by == "mgr-001"
        assert task.status == FulfillmentStatus.PENDING
        assert task.description == "Deploy VM"
        assert task.dependency_ref == "dep-001"
        assert task.created_at == TS
        assert task.completed_at == ""

    def test_with_completed_at(self):
        task = _fulfillment_task(completed_at=TS2)
        assert task.completed_at == TS2

    def test_all_fulfillment_statuses(self):
        for status in FulfillmentStatus:
            task = _fulfillment_task(status=status)
            assert task.status == status

    def test_is_dataclass(self):
        task = _fulfillment_task()
        assert dataclasses.is_dataclass(task)


class TestFulfillmentDecisionConstruction:
    def test_valid_defaults(self):
        dec = _fulfillment_decision()
        assert dec.decision_id == "dec-001"
        assert dec.request_id == "req-001"
        assert dec.disposition == "approved"
        assert dec.decided_by == "mgr-001"
        assert dec.reason == "Meets criteria"
        assert dec.decided_at == TS

    def test_is_dataclass(self):
        dec = _fulfillment_decision()
        assert dataclasses.is_dataclass(dec)

    def test_with_metadata(self):
        dec = _fulfillment_decision(metadata={"notes": "fast-track"})
        assert dec.metadata["notes"] == "fast-track"


class TestRequestSnapshotConstruction:
    def test_valid_defaults(self):
        snap = _request_snapshot()
        assert snap.snapshot_id == "snap-001"
        assert snap.total_catalog_items == 10
        assert snap.total_requests == 50
        assert snap.total_submitted == 20
        assert snap.total_in_fulfillment == 5
        assert snap.total_fulfilled == 15
        assert snap.total_denied == 3
        assert snap.total_tasks == 25
        assert snap.total_violations == 2
        assert snap.total_estimated_cost == 5000.0
        assert snap.captured_at == TS

    def test_all_zeros(self):
        snap = _request_snapshot(
            total_catalog_items=0,
            total_requests=0,
            total_submitted=0,
            total_in_fulfillment=0,
            total_fulfilled=0,
            total_denied=0,
            total_tasks=0,
            total_violations=0,
            total_estimated_cost=0.0,
        )
        assert snap.total_catalog_items == 0

    def test_is_dataclass(self):
        snap = _request_snapshot()
        assert dataclasses.is_dataclass(snap)


class TestRequestViolationConstruction:
    def test_valid_defaults(self):
        viol = _request_violation()
        assert viol.violation_id == "viol-001"
        assert viol.request_id == "req-001"
        assert viol.tenant_id == "t-001"
        assert viol.operation == "reopen"
        assert viol.reason == "Fulfilled requests cannot be re-opened"
        assert viol.detected_at == TS

    def test_is_dataclass(self):
        viol = _request_violation()
        assert dataclasses.is_dataclass(viol)

    def test_with_metadata(self):
        viol = _request_violation(metadata={"severity": "high"})
        assert viol.metadata["severity"] == "high"


class TestServiceClosureReportConstruction:
    def test_valid_defaults(self):
        rpt = _closure_report()
        assert rpt.report_id == "rpt-001"
        assert rpt.tenant_id == "t-001"
        assert rpt.total_requests == 100
        assert rpt.total_fulfilled == 80
        assert rpt.total_denied == 10
        assert rpt.total_cancelled == 5
        assert rpt.total_tasks == 50
        assert rpt.total_violations == 3
        assert rpt.total_estimated_cost == 25000.0
        assert rpt.closed_at == TS

    def test_all_zeros(self):
        rpt = _closure_report(
            total_requests=0,
            total_fulfilled=0,
            total_denied=0,
            total_cancelled=0,
            total_tasks=0,
            total_violations=0,
            total_estimated_cost=0.0,
        )
        assert rpt.total_requests == 0

    def test_is_dataclass(self):
        rpt = _closure_report()
        assert dataclasses.is_dataclass(rpt)


class TestCatalogAssessmentConstruction:
    def test_valid_defaults(self):
        assess = _catalog_assessment()
        assert assess.assessment_id == "assess-001"
        assert assess.item_id == "item-001"
        assert assess.fulfillment_rate == 0.85
        assert assess.satisfaction_score == 0.9
        assert assess.assessed_by == "auditor-001"
        assert assess.assessed_at == TS

    def test_boundary_rates(self):
        assess = _catalog_assessment(fulfillment_rate=0.0, satisfaction_score=0.0)
        assert assess.fulfillment_rate == 0.0
        assert assess.satisfaction_score == 0.0

    def test_max_rates(self):
        assess = _catalog_assessment(fulfillment_rate=1.0, satisfaction_score=1.0)
        assert assess.fulfillment_rate == 1.0
        assert assess.satisfaction_score == 1.0

    def test_is_dataclass(self):
        assess = _catalog_assessment()
        assert dataclasses.is_dataclass(assess)


# ===================================================================
# 3. Validation failures
# ===================================================================


class TestServiceCatalogItemValidation:
    def test_empty_item_id(self):
        with pytest.raises(ValueError):
            _catalog_item(item_id="")

    def test_whitespace_item_id(self):
        with pytest.raises(ValueError):
            _catalog_item(item_id="   ")

    def test_empty_name(self):
        with pytest.raises(ValueError):
            _catalog_item(name="")

    def test_whitespace_name(self):
        with pytest.raises(ValueError):
            _catalog_item(name="  \t  ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _catalog_item(tenant_id="")

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError, match="kind must be a CatalogItemKind"):
            _catalog_item(kind="infrastructure")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be a ServiceStatus"):
            _catalog_item(status="active")

    def test_negative_estimated_cost(self):
        with pytest.raises(ValueError):
            _catalog_item(estimated_cost=-1.0)

    def test_nan_estimated_cost(self):
        with pytest.raises(ValueError):
            _catalog_item(estimated_cost=float("nan"))

    def test_inf_estimated_cost(self):
        with pytest.raises(ValueError):
            _catalog_item(estimated_cost=float("inf"))

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _catalog_item(created_at="not-a-date")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _catalog_item(created_at="")

    def test_bool_estimated_cost(self):
        with pytest.raises(ValueError):
            _catalog_item(estimated_cost=True)

    def test_kind_wrong_enum_type(self):
        with pytest.raises(ValueError):
            _catalog_item(kind=FulfillmentStatus.PENDING)

    def test_status_wrong_enum_type(self):
        with pytest.raises(ValueError):
            _catalog_item(status=RequestStatus.DRAFT)


class TestServiceRequestValidation:
    def test_empty_request_id(self):
        with pytest.raises(ValueError):
            _service_request(request_id="")

    def test_whitespace_request_id(self):
        with pytest.raises(ValueError):
            _service_request(request_id="   ")

    def test_empty_item_id(self):
        with pytest.raises(ValueError):
            _service_request(item_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _service_request(tenant_id="")

    def test_empty_requester_ref(self):
        with pytest.raises(ValueError):
            _service_request(requester_ref="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be a RequestStatus"):
            _service_request(status="draft")

    def test_invalid_priority_type(self):
        with pytest.raises(ValueError, match="priority must be a RequestPriority"):
            _service_request(priority="medium")

    def test_negative_estimated_cost(self):
        with pytest.raises(ValueError):
            _service_request(estimated_cost=-10.0)

    def test_nan_estimated_cost(self):
        with pytest.raises(ValueError):
            _service_request(estimated_cost=float("nan"))

    def test_invalid_submitted_at(self):
        with pytest.raises(ValueError):
            _service_request(submitted_at="bad-date")

    def test_empty_submitted_at(self):
        with pytest.raises(ValueError):
            _service_request(submitted_at="")

    def test_invalid_due_at(self):
        with pytest.raises(ValueError):
            _service_request(due_at="bad-date")

    def test_due_at_empty_is_valid(self):
        req = _service_request(due_at="")
        assert req.due_at == ""

    def test_status_wrong_enum_type(self):
        with pytest.raises(ValueError):
            _service_request(status=ServiceStatus.ACTIVE)

    def test_priority_wrong_enum_type(self):
        with pytest.raises(ValueError):
            _service_request(priority=FulfillmentStatus.PENDING)

    def test_bool_estimated_cost(self):
        with pytest.raises(ValueError):
            _service_request(estimated_cost=False)


class TestRequestAssignmentValidation:
    def test_empty_assignment_id(self):
        with pytest.raises(ValueError):
            _assignment(assignment_id="")

    def test_empty_request_id(self):
        with pytest.raises(ValueError):
            _assignment(request_id="")

    def test_empty_assignee_ref(self):
        with pytest.raises(ValueError):
            _assignment(assignee_ref="")

    def test_empty_assigned_by(self):
        with pytest.raises(ValueError):
            _assignment(assigned_by="")

    def test_system_assigned_by_rejected(self):
        with pytest.raises(ValueError, match="^assigned_by must exclude system$") as exc_info:
            _assignment(assigned_by="system")
        message = str(exc_info.value)
        assert message == "assigned_by must exclude system"
        assert "mgr-001" not in message

    def test_invalid_assigned_at(self):
        with pytest.raises(ValueError):
            _assignment(assigned_at="not-a-date")

    def test_empty_assigned_at(self):
        with pytest.raises(ValueError):
            _assignment(assigned_at="")

    def test_whitespace_assignment_id(self):
        with pytest.raises(ValueError):
            _assignment(assignment_id="  ")

    def test_whitespace_request_id(self):
        with pytest.raises(ValueError):
            _assignment(request_id="\t")


class TestEntitlementRuleValidation:
    def test_empty_rule_id(self):
        with pytest.raises(ValueError):
            _entitlement_rule(rule_id="")

    def test_empty_item_id(self):
        with pytest.raises(ValueError):
            _entitlement_rule(item_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _entitlement_rule(tenant_id="")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError, match="disposition must be an EntitlementDisposition"):
            _entitlement_rule(disposition="granted")

    def test_invalid_evaluated_at(self):
        with pytest.raises(ValueError):
            _entitlement_rule(evaluated_at="bad")

    def test_empty_evaluated_at(self):
        with pytest.raises(ValueError):
            _entitlement_rule(evaluated_at="")

    def test_disposition_wrong_enum_type(self):
        with pytest.raises(ValueError):
            _entitlement_rule(disposition=RequestStatus.APPROVED)

    def test_whitespace_rule_id(self):
        with pytest.raises(ValueError):
            _entitlement_rule(rule_id="   ")


class TestFulfillmentTaskValidation:
    def test_empty_task_id(self):
        with pytest.raises(ValueError):
            _fulfillment_task(task_id="")

    def test_empty_request_id(self):
        with pytest.raises(ValueError):
            _fulfillment_task(request_id="")

    def test_empty_assignee_ref(self):
        with pytest.raises(ValueError):
            _fulfillment_task(assignee_ref="")

    def test_empty_created_by(self):
        with pytest.raises(ValueError):
            _fulfillment_task(created_by="")

    def test_system_created_by_rejected(self):
        with pytest.raises(ValueError, match="^created_by must exclude system$") as exc_info:
            _fulfillment_task(created_by="system")
        message = str(exc_info.value)
        assert message == "created_by must exclude system"
        assert "mgr-001" not in message

    def test_invalid_status_type(self):
        with pytest.raises(ValueError, match="status must be a FulfillmentStatus"):
            _fulfillment_task(status="pending")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _fulfillment_task(created_at="nope")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _fulfillment_task(created_at="")

    def test_invalid_completed_at(self):
        with pytest.raises(ValueError):
            _fulfillment_task(completed_at="bad-ts")

    def test_completed_at_empty_is_valid(self):
        task = _fulfillment_task(completed_at="")
        assert task.completed_at == ""

    def test_status_wrong_enum_type(self):
        with pytest.raises(ValueError):
            _fulfillment_task(status=ServiceStatus.ACTIVE)

    def test_whitespace_task_id(self):
        with pytest.raises(ValueError):
            _fulfillment_task(task_id="   ")


class TestFulfillmentDecisionValidation:
    def test_empty_decision_id(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(decision_id="")

    def test_empty_request_id(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(request_id="")

    def test_empty_disposition(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(disposition="")

    def test_empty_decided_by(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(decided_by="")

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(decided_at="not-valid")

    def test_empty_decided_at(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(decided_at="")

    def test_whitespace_disposition(self):
        with pytest.raises(ValueError):
            _fulfillment_decision(disposition="   ")


class TestRequestSnapshotValidation:
    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _request_snapshot(snapshot_id="")

    def test_negative_total_catalog_items(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_catalog_items=-1)

    def test_negative_total_requests(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_requests=-1)

    def test_negative_total_submitted(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_submitted=-1)

    def test_negative_total_in_fulfillment(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_in_fulfillment=-1)

    def test_negative_total_fulfilled(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_fulfilled=-1)

    def test_negative_total_denied(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_denied=-1)

    def test_negative_total_tasks(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_tasks=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_violations=-1)

    def test_negative_total_estimated_cost(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_estimated_cost=-1.0)

    def test_nan_total_estimated_cost(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_estimated_cost=float("nan"))

    def test_inf_total_estimated_cost(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_estimated_cost=float("inf"))

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _request_snapshot(captured_at="bad")

    def test_empty_captured_at(self):
        with pytest.raises(ValueError):
            _request_snapshot(captured_at="")

    def test_bool_total_catalog_items(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_catalog_items=True)

    def test_bool_total_requests(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_requests=False)

    def test_float_total_catalog_items(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_catalog_items=1.5)

    def test_whitespace_snapshot_id(self):
        with pytest.raises(ValueError):
            _request_snapshot(snapshot_id="   ")


class TestRequestViolationValidation:
    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            _request_violation(violation_id="")

    def test_empty_request_id(self):
        with pytest.raises(ValueError):
            _request_violation(request_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _request_violation(tenant_id="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _request_violation(operation="")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _request_violation(detected_at="bad")

    def test_empty_detected_at(self):
        with pytest.raises(ValueError):
            _request_violation(detected_at="")

    def test_whitespace_violation_id(self):
        with pytest.raises(ValueError):
            _request_violation(violation_id="  ")


class TestServiceClosureReportValidation:
    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _closure_report(tenant_id="")

    def test_negative_total_requests(self):
        with pytest.raises(ValueError):
            _closure_report(total_requests=-1)

    def test_negative_total_fulfilled(self):
        with pytest.raises(ValueError):
            _closure_report(total_fulfilled=-1)

    def test_negative_total_denied(self):
        with pytest.raises(ValueError):
            _closure_report(total_denied=-1)

    def test_negative_total_cancelled(self):
        with pytest.raises(ValueError):
            _closure_report(total_cancelled=-1)

    def test_negative_total_tasks(self):
        with pytest.raises(ValueError):
            _closure_report(total_tasks=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _closure_report(total_violations=-1)

    def test_negative_total_estimated_cost(self):
        with pytest.raises(ValueError):
            _closure_report(total_estimated_cost=-100.0)

    def test_nan_total_estimated_cost(self):
        with pytest.raises(ValueError):
            _closure_report(total_estimated_cost=float("nan"))

    def test_invalid_closed_at(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="bad")

    def test_empty_closed_at(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="")

    def test_bool_total_requests(self):
        with pytest.raises(ValueError):
            _closure_report(total_requests=True)

    def test_float_total_requests(self):
        with pytest.raises(ValueError):
            _closure_report(total_requests=2.5)

    def test_whitespace_report_id(self):
        with pytest.raises(ValueError):
            _closure_report(report_id="  \n  ")


class TestCatalogAssessmentValidation:
    def test_empty_assessment_id(self):
        with pytest.raises(ValueError):
            _catalog_assessment(assessment_id="")

    def test_empty_item_id(self):
        with pytest.raises(ValueError):
            _catalog_assessment(item_id="")

    def test_empty_assessed_by(self):
        with pytest.raises(ValueError):
            _catalog_assessment(assessed_by="")

    def test_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            _catalog_assessment(assessed_at="bad")

    def test_empty_assessed_at(self):
        with pytest.raises(ValueError):
            _catalog_assessment(assessed_at="")

    def test_fulfillment_rate_below_zero(self):
        with pytest.raises(ValueError):
            _catalog_assessment(fulfillment_rate=-0.01)

    def test_fulfillment_rate_above_one(self):
        with pytest.raises(ValueError):
            _catalog_assessment(fulfillment_rate=1.01)

    def test_satisfaction_score_below_zero(self):
        with pytest.raises(ValueError):
            _catalog_assessment(satisfaction_score=-0.1)

    def test_satisfaction_score_above_one(self):
        with pytest.raises(ValueError):
            _catalog_assessment(satisfaction_score=1.5)

    def test_fulfillment_rate_nan(self):
        with pytest.raises(ValueError):
            _catalog_assessment(fulfillment_rate=float("nan"))

    def test_satisfaction_score_nan(self):
        with pytest.raises(ValueError):
            _catalog_assessment(satisfaction_score=float("nan"))

    def test_fulfillment_rate_inf(self):
        with pytest.raises(ValueError):
            _catalog_assessment(fulfillment_rate=float("inf"))

    def test_satisfaction_score_inf(self):
        with pytest.raises(ValueError):
            _catalog_assessment(satisfaction_score=float("inf"))

    def test_fulfillment_rate_neg_inf(self):
        with pytest.raises(ValueError):
            _catalog_assessment(fulfillment_rate=float("-inf"))

    def test_satisfaction_score_neg_inf(self):
        with pytest.raises(ValueError):
            _catalog_assessment(satisfaction_score=float("-inf"))

    def test_fulfillment_rate_bool(self):
        with pytest.raises(ValueError):
            _catalog_assessment(fulfillment_rate=True)

    def test_satisfaction_score_bool(self):
        with pytest.raises(ValueError):
            _catalog_assessment(satisfaction_score=False)

    def test_whitespace_assessment_id(self):
        with pytest.raises(ValueError):
            _catalog_assessment(assessment_id="  ")


# ===================================================================
# 4. Frozen immutability
# ===================================================================


class TestServiceCatalogItemFrozen:
    def test_set_item_id(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.item_id = "new"

    def test_set_name(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.name = "new"

    def test_set_tenant_id(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.tenant_id = "new"

    def test_set_kind(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.kind = CatalogItemKind.DATA

    def test_set_status(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.status = ServiceStatus.RETIRED

    def test_set_estimated_cost(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.estimated_cost = 999.0

    def test_set_metadata(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.metadata = {}

    def test_set_approval_required(self):
        item = _catalog_item()
        with pytest.raises(dataclasses.FrozenInstanceError):
            item.approval_required = True


class TestServiceRequestFrozen:
    def test_set_request_id(self):
        req = _service_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.request_id = "new"

    def test_set_status(self):
        req = _service_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.status = RequestStatus.FULFILLED

    def test_set_priority(self):
        req = _service_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.priority = RequestPriority.CRITICAL

    def test_set_metadata(self):
        req = _service_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.metadata = {}


class TestRequestAssignmentFrozen:
    def test_set_assignment_id(self):
        asgn = _assignment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            asgn.assignment_id = "new"

    def test_set_assignee_ref(self):
        asgn = _assignment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            asgn.assignee_ref = "new"


class TestEntitlementRuleFrozen:
    def test_set_rule_id(self):
        rule = _entitlement_rule()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.rule_id = "new"

    def test_set_disposition(self):
        rule = _entitlement_rule()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rule.disposition = EntitlementDisposition.DENIED


class TestFulfillmentTaskFrozen:
    def test_set_task_id(self):
        task = _fulfillment_task()
        with pytest.raises(dataclasses.FrozenInstanceError):
            task.task_id = "new"

    def test_set_status(self):
        task = _fulfillment_task()
        with pytest.raises(dataclasses.FrozenInstanceError):
            task.status = FulfillmentStatus.COMPLETED


class TestFulfillmentDecisionFrozen:
    def test_set_decision_id(self):
        dec = _fulfillment_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            dec.decision_id = "new"

    def test_set_disposition(self):
        dec = _fulfillment_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            dec.disposition = "denied"


class TestRequestSnapshotFrozen:
    def test_set_snapshot_id(self):
        snap = _request_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.snapshot_id = "new"

    def test_set_total_requests(self):
        snap = _request_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            snap.total_requests = 999


class TestRequestViolationFrozen:
    def test_set_violation_id(self):
        viol = _request_violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            viol.violation_id = "new"

    def test_set_operation(self):
        viol = _request_violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            viol.operation = "new"


class TestServiceClosureReportFrozen:
    def test_set_report_id(self):
        rpt = _closure_report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rpt.report_id = "new"

    def test_set_total_fulfilled(self):
        rpt = _closure_report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rpt.total_fulfilled = 999


class TestCatalogAssessmentFrozen:
    def test_set_assessment_id(self):
        assess = _catalog_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            assess.assessment_id = "new"

    def test_set_fulfillment_rate(self):
        assess = _catalog_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            assess.fulfillment_rate = 0.5


# ===================================================================
# 5. Metadata freezing
# ===================================================================


class TestServiceCatalogItemMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        item = _catalog_item()
        assert isinstance(item.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        item = _catalog_item(metadata={"key": "val"})
        assert isinstance(item.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            item.metadata["key"] = "new"

    def test_nested_list_frozen_to_tuple(self):
        item = _catalog_item(metadata={"tags": ["a", "b"]})
        assert isinstance(item.metadata["tags"], tuple)

    def test_nested_dict_frozen(self):
        item = _catalog_item(metadata={"inner": {"k": "v"}})
        assert isinstance(item.metadata["inner"], MappingProxyType)

    def test_empty_metadata(self):
        item = _catalog_item()
        assert len(item.metadata) == 0


class TestServiceRequestMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        req = _service_request()
        assert isinstance(req.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        req = _service_request(metadata={"key": "val"})
        assert isinstance(req.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            req.metadata["key"] = "new"

    def test_nested_list_frozen_to_tuple(self):
        req = _service_request(metadata={"items": [1, 2, 3]})
        assert isinstance(req.metadata["items"], tuple)


class TestRequestAssignmentMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        asgn = _assignment()
        assert isinstance(asgn.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        asgn = _assignment(metadata={"team": "ops"})
        assert isinstance(asgn.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            asgn.metadata["team"] = "dev"


class TestEntitlementRuleMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        rule = _entitlement_rule()
        assert isinstance(rule.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        rule = _entitlement_rule(metadata={"audit": True})
        assert isinstance(rule.metadata, MappingProxyType)


class TestFulfillmentTaskMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        task = _fulfillment_task()
        assert isinstance(task.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        task = _fulfillment_task(metadata={"step": 1})
        assert isinstance(task.metadata, MappingProxyType)


class TestFulfillmentDecisionMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        dec = _fulfillment_decision()
        assert isinstance(dec.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        dec = _fulfillment_decision(metadata={"reason_code": "rc-001"})
        assert isinstance(dec.metadata, MappingProxyType)


class TestRequestSnapshotMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        snap = _request_snapshot()
        assert isinstance(snap.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        snap = _request_snapshot(metadata={"source": "system"})
        assert isinstance(snap.metadata, MappingProxyType)


class TestRequestViolationMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        viol = _request_violation()
        assert isinstance(viol.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        viol = _request_violation(metadata={"action": "block"})
        assert isinstance(viol.metadata, MappingProxyType)


class TestServiceClosureReportMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        rpt = _closure_report()
        assert isinstance(rpt.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        rpt = _closure_report(metadata={"period": "Q1"})
        assert isinstance(rpt.metadata, MappingProxyType)


class TestCatalogAssessmentMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        assess = _catalog_assessment()
        assert isinstance(assess.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        assess = _catalog_assessment(metadata={"method": "automated"})
        assert isinstance(assess.metadata, MappingProxyType)


# ===================================================================
# 6. to_dict()
# ===================================================================


class TestServiceCatalogItemToDict:
    def test_returns_dict(self):
        item = _catalog_item()
        d = item.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        item = _catalog_item()
        d = item.to_dict()
        expected_keys = {
            "item_id", "name", "tenant_id", "kind", "status",
            "owner_ref", "sla_ref", "approval_required", "approver_refs", "estimated_cost",
            "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_preserved_not_value(self):
        item = _catalog_item()
        d = item.to_dict()
        assert d["kind"] == CatalogItemKind.INFRASTRUCTURE
        assert d["status"] == ServiceStatus.ACTIVE

    def test_metadata_thawed_to_dict(self):
        item = _catalog_item(metadata={"k": "v"})
        d = item.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["k"] == "v"

    def test_values_match(self):
        item = _catalog_item()
        d = item.to_dict()
        assert d["item_id"] == "item-001"
        assert d["name"] == "VM Provisioning"
        assert d["estimated_cost"] == 100.0
        assert d["approval_required"] is False
        assert d["approver_refs"] == []


class TestServiceRequestToDict:
    def test_returns_dict(self):
        req = _service_request()
        d = req.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        req = _service_request()
        d = req.to_dict()
        expected_keys = {
            "request_id", "item_id", "tenant_id", "requester_ref",
            "status", "priority", "description", "estimated_cost",
            "submitted_at", "due_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_preserved_not_value(self):
        req = _service_request()
        d = req.to_dict()
        assert d["status"] == RequestStatus.DRAFT
        assert d["priority"] == RequestPriority.MEDIUM

    def test_due_at_empty_string(self):
        req = _service_request(due_at="")
        d = req.to_dict()
        assert d["due_at"] == ""


class TestRequestAssignmentToDict:
    def test_returns_dict(self):
        asgn = _assignment()
        d = asgn.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        asgn = _assignment()
        d = asgn.to_dict()
        expected_keys = {
            "assignment_id", "request_id", "assignee_ref",
            "assigned_by", "assigned_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


class TestEntitlementRuleToDict:
    def test_returns_dict(self):
        rule = _entitlement_rule()
        d = rule.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        rule = _entitlement_rule()
        d = rule.to_dict()
        expected_keys = {
            "rule_id", "item_id", "tenant_id", "disposition",
            "scope_ref", "reason", "evaluated_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_preserved_not_value(self):
        rule = _entitlement_rule()
        d = rule.to_dict()
        assert d["disposition"] == EntitlementDisposition.GRANTED


class TestFulfillmentTaskToDict:
    def test_returns_dict(self):
        task = _fulfillment_task()
        d = task.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        task = _fulfillment_task()
        d = task.to_dict()
        expected_keys = {
            "task_id", "request_id", "assignee_ref", "created_by", "status",
            "description", "dependency_ref", "created_at",
            "completed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_enum_preserved(self):
        task = _fulfillment_task()
        d = task.to_dict()
        assert d["status"] == FulfillmentStatus.PENDING


class TestFulfillmentDecisionToDict:
    def test_returns_dict(self):
        dec = _fulfillment_decision()
        d = dec.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        dec = _fulfillment_decision()
        d = dec.to_dict()
        expected_keys = {
            "decision_id", "request_id", "disposition",
            "decided_by", "reason", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


class TestRequestSnapshotToDict:
    def test_returns_dict(self):
        snap = _request_snapshot()
        d = snap.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        snap = _request_snapshot()
        d = snap.to_dict()
        expected_keys = {
            "snapshot_id", "total_catalog_items", "total_requests",
            "total_submitted", "total_in_fulfillment", "total_fulfilled",
            "total_denied", "total_tasks", "total_violations",
            "total_estimated_cost", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_values_match(self):
        snap = _request_snapshot()
        d = snap.to_dict()
        assert d["total_catalog_items"] == 10
        assert d["total_requests"] == 50
        assert d["total_estimated_cost"] == 5000.0


class TestRequestViolationToDict:
    def test_returns_dict(self):
        viol = _request_violation()
        d = viol.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        viol = _request_violation()
        d = viol.to_dict()
        expected_keys = {
            "violation_id", "request_id", "tenant_id",
            "operation", "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


class TestServiceClosureReportToDict:
    def test_returns_dict(self):
        rpt = _closure_report()
        d = rpt.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        rpt = _closure_report()
        d = rpt.to_dict()
        expected_keys = {
            "report_id", "tenant_id", "total_requests", "total_fulfilled",
            "total_denied", "total_cancelled", "total_tasks",
            "total_violations", "total_estimated_cost", "closed_at",
            "metadata",
        }
        assert set(d.keys()) == expected_keys


class TestCatalogAssessmentToDict:
    def test_returns_dict(self):
        assess = _catalog_assessment()
        d = assess.to_dict()
        assert isinstance(d, dict)

    def test_all_keys_present(self):
        assess = _catalog_assessment()
        d = assess.to_dict()
        expected_keys = {
            "assessment_id", "item_id", "fulfillment_rate",
            "satisfaction_score", "assessed_by", "assessed_at",
            "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_values_match(self):
        assess = _catalog_assessment()
        d = assess.to_dict()
        assert d["fulfillment_rate"] == 0.85
        assert d["satisfaction_score"] == 0.9


# ===================================================================
# 7. Optional fields
# ===================================================================


class TestServiceRequestOptionalDueAt:
    def test_due_at_empty_string_valid(self):
        req = _service_request(due_at="")
        assert req.due_at == ""

    def test_due_at_with_iso_datetime(self):
        req = _service_request(due_at=TS2)
        assert req.due_at == TS2

    def test_due_at_date_only(self):
        req = _service_request(due_at="2025-06-01")
        assert req.due_at == "2025-06-01"

    def test_due_at_with_z_suffix(self):
        req = _service_request(due_at="2025-06-01T12:00:00Z")
        assert req.due_at == "2025-06-01T12:00:00Z"


class TestFulfillmentTaskOptionalCompletedAt:
    def test_completed_at_empty_string_valid(self):
        task = _fulfillment_task(completed_at="")
        assert task.completed_at == ""

    def test_completed_at_with_iso_datetime(self):
        task = _fulfillment_task(completed_at=TS2)
        assert task.completed_at == TS2

    def test_completed_at_date_only(self):
        task = _fulfillment_task(completed_at="2025-06-01")
        assert task.completed_at == "2025-06-01"

    def test_completed_at_with_z_suffix(self):
        task = _fulfillment_task(completed_at="2025-06-01T00:00:00Z")
        assert task.completed_at == "2025-06-01T00:00:00Z"


# ===================================================================
# 8. Datetime validation with various ISO formats
# ===================================================================


class TestDatetimeFormats:
    def test_catalog_item_date_only(self):
        item = _catalog_item(created_at="2025-06-01")
        assert item.created_at == "2025-06-01"

    def test_catalog_item_with_z(self):
        item = _catalog_item(created_at="2025-06-01T12:00:00Z")
        assert item.created_at == "2025-06-01T12:00:00Z"

    def test_catalog_item_with_offset(self):
        item = _catalog_item(created_at="2025-06-01T12:00:00+05:30")
        assert item.created_at == "2025-06-01T12:00:00+05:30"

    def test_assignment_with_z(self):
        asgn = _assignment(assigned_at="2025-01-01T00:00:00Z")
        assert asgn.assigned_at == "2025-01-01T00:00:00Z"

    def test_entitlement_with_offset(self):
        rule = _entitlement_rule(evaluated_at="2025-12-31T23:59:59-08:00")
        assert rule.evaluated_at == "2025-12-31T23:59:59-08:00"

    def test_decision_date_only(self):
        dec = _fulfillment_decision(decided_at="2025-06-01")
        assert dec.decided_at == "2025-06-01"

    def test_snapshot_date_only(self):
        snap = _request_snapshot(captured_at="2025-06-01")
        assert snap.captured_at == "2025-06-01"

    def test_violation_with_z(self):
        viol = _request_violation(detected_at="2025-06-01T00:00:00Z")
        assert viol.detected_at == "2025-06-01T00:00:00Z"

    def test_closure_report_with_offset(self):
        rpt = _closure_report(closed_at="2025-06-01T12:00:00+00:00")
        assert rpt.closed_at == "2025-06-01T12:00:00+00:00"

    def test_assessment_date_only(self):
        assess = _catalog_assessment(assessed_at="2025-06-01")
        assert assess.assessed_at == "2025-06-01"


# ===================================================================
# 9. Additional edge cases and cross-cutting concerns
# ===================================================================


class TestCatalogItemIntegerCost:
    """Integer values should be accepted for float fields."""

    def test_int_estimated_cost(self):
        item = _catalog_item(estimated_cost=100)
        assert item.estimated_cost == 100.0

    def test_zero_int_estimated_cost(self):
        item = _catalog_item(estimated_cost=0)
        assert item.estimated_cost == 0.0


class TestServiceRequestIntegerCost:
    def test_int_estimated_cost(self):
        req = _service_request(estimated_cost=75)
        assert req.estimated_cost == 75.0


class TestRequestSnapshotIntegerCost:
    def test_int_total_estimated_cost(self):
        snap = _request_snapshot(total_estimated_cost=1000)
        assert snap.total_estimated_cost == 1000.0


class TestClosureReportIntegerCost:
    def test_int_total_estimated_cost(self):
        rpt = _closure_report(total_estimated_cost=5000)
        assert rpt.total_estimated_cost == 5000.0


class TestCatalogAssessmentIntRates:
    def test_int_zero_fulfillment_rate(self):
        assess = _catalog_assessment(fulfillment_rate=0)
        assert assess.fulfillment_rate == 0.0

    def test_int_one_fulfillment_rate(self):
        assess = _catalog_assessment(fulfillment_rate=1)
        assert assess.fulfillment_rate == 1.0

    def test_int_zero_satisfaction_score(self):
        assess = _catalog_assessment(satisfaction_score=0)
        assert assess.satisfaction_score == 0.0

    def test_int_one_satisfaction_score(self):
        assess = _catalog_assessment(satisfaction_score=1)
        assert assess.satisfaction_score == 1.0


class TestMetadataNotMutatedByConstruction:
    """Original dict passed to constructor is not reflected back."""

    def test_catalog_item_metadata_isolation(self):
        original = {"key": "val"}
        item = _catalog_item(metadata=original)
        original["key"] = "changed"
        assert item.metadata["key"] == "val"

    def test_service_request_metadata_isolation(self):
        original = {"key": "val"}
        req = _service_request(metadata=original)
        original["key"] = "changed"
        assert req.metadata["key"] == "val"

    def test_assignment_metadata_isolation(self):
        original = {"key": "val"}
        asgn = _assignment(metadata=original)
        original["key"] = "changed"
        assert asgn.metadata["key"] == "val"

    def test_entitlement_metadata_isolation(self):
        original = {"key": "val"}
        rule = _entitlement_rule(metadata=original)
        original["key"] = "changed"
        assert rule.metadata["key"] == "val"

    def test_task_metadata_isolation(self):
        original = {"key": "val"}
        task = _fulfillment_task(metadata=original)
        original["key"] = "changed"
        assert task.metadata["key"] == "val"

    def test_decision_metadata_isolation(self):
        original = {"key": "val"}
        dec = _fulfillment_decision(metadata=original)
        original["key"] = "changed"
        assert dec.metadata["key"] == "val"

    def test_snapshot_metadata_isolation(self):
        original = {"key": "val"}
        snap = _request_snapshot(metadata=original)
        original["key"] = "changed"
        assert snap.metadata["key"] == "val"

    def test_violation_metadata_isolation(self):
        original = {"key": "val"}
        viol = _request_violation(metadata=original)
        original["key"] = "changed"
        assert viol.metadata["key"] == "val"

    def test_closure_metadata_isolation(self):
        original = {"key": "val"}
        rpt = _closure_report(metadata=original)
        original["key"] = "changed"
        assert rpt.metadata["key"] == "val"

    def test_assessment_metadata_isolation(self):
        original = {"key": "val"}
        assess = _catalog_assessment(metadata=original)
        original["key"] = "changed"
        assert assess.metadata["key"] == "val"


class TestToDictMetadataThawed:
    """to_dict should thaw metadata back to regular dict."""

    def test_catalog_item_metadata_thawed(self):
        item = _catalog_item(metadata={"a": [1, 2]})
        d = item.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["a"], list)

    def test_service_request_metadata_thawed(self):
        req = _service_request(metadata={"b": {"c": 3}})
        d = req.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["b"], dict)

    def test_assignment_metadata_thawed(self):
        asgn = _assignment(metadata={"x": (1, 2)})
        d = asgn.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_entitlement_metadata_thawed(self):
        rule = _entitlement_rule(metadata={"p": "q"})
        d = rule.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_task_metadata_thawed(self):
        task = _fulfillment_task(metadata={"s": 1})
        d = task.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_decision_metadata_thawed(self):
        dec = _fulfillment_decision(metadata={"r": "s"})
        d = dec.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_snapshot_metadata_thawed(self):
        snap = _request_snapshot(metadata={"t": True})
        d = snap.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_violation_metadata_thawed(self):
        viol = _request_violation(metadata={"u": 0})
        d = viol.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_closure_metadata_thawed(self):
        rpt = _closure_report(metadata={"v": "w"})
        d = rpt.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_assessment_metadata_thawed(self):
        assess = _catalog_assessment(metadata={"z": None})
        d = assess.to_dict()
        assert isinstance(d["metadata"], dict)


class TestNegativeInfForNonNegativeFloat:
    def test_catalog_item_neg_inf(self):
        with pytest.raises(ValueError):
            _catalog_item(estimated_cost=float("-inf"))

    def test_service_request_neg_inf(self):
        with pytest.raises(ValueError):
            _service_request(estimated_cost=float("-inf"))

    def test_snapshot_neg_inf(self):
        with pytest.raises(ValueError):
            _request_snapshot(total_estimated_cost=float("-inf"))

    def test_closure_neg_inf(self):
        with pytest.raises(ValueError):
            _closure_report(total_estimated_cost=float("-inf"))


class TestLargeValues:
    def test_large_estimated_cost(self):
        item = _catalog_item(estimated_cost=1e15)
        assert item.estimated_cost == 1e15

    def test_large_int_counts(self):
        snap = _request_snapshot(total_requests=10**9)
        assert snap.total_requests == 10**9


class TestStringFieldsWithSpecialCharacters:
    def test_unicode_item_name(self):
        item = _catalog_item(name="VM-Bereitstellung")
        assert item.name == "VM-Bereitstellung"

    def test_item_id_with_dashes(self):
        item = _catalog_item(item_id="item-abc-123-def")
        assert item.item_id == "item-abc-123-def"

    def test_description_multiline(self):
        req = _service_request(description="Line 1\nLine 2\nLine 3")
        assert "Line 1" in req.description

    def test_reason_with_punctuation(self):
        viol = _request_violation(reason="SLA breached: response > 24h!")
        assert viol.reason == "SLA breached: response > 24h!"
