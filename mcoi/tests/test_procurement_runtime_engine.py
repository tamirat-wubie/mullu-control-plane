"""Comprehensive tests for ProcurementRuntimeEngine.

Covers: vendor CRUD and lifecycle, procurement requests, purchase orders,
vendor assessments, vendor commitments, renewal windows, violation detection,
procurement snapshots, state hashing, and six golden scenarios.
"""

import pytest

from mcoi_runtime.contracts.procurement_runtime import (
    ProcurementClosureReport,
    ProcurementDecision,
    ProcurementDecisionStatus,
    ProcurementRenewalWindow,
    ProcurementRequest,
    ProcurementRequestStatus,
    ProcurementSnapshot,
    PurchaseOrder,
    PurchaseOrderStatus,
    RenewalDisposition,
    VendorAssessment,
    VendorCommitment,
    VendorRecord,
    VendorRiskLevel,
    VendorStatus,
    VendorViolation,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.procurement_runtime import ProcurementRuntimeEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def es():
    return EventSpineEngine()


@pytest.fixture()
def engine(es):
    return ProcurementRuntimeEngine(es)


@pytest.fixture()
def vendor_engine(engine):
    """Engine with a single registered vendor."""
    engine.register_vendor("v-1", "Acme Corp", "tenant-1", category="IT")
    return engine


@pytest.fixture()
def request_engine(vendor_engine):
    """Engine with a vendor and a draft request."""
    vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
    return vendor_engine


@pytest.fixture()
def submitted_engine(request_engine):
    """Engine with a vendor and a submitted request."""
    request_engine.submit_request("req-1")
    return request_engine


@pytest.fixture()
def approved_engine(submitted_engine):
    """Engine with a vendor and an approved request."""
    submitted_engine.approve_request("req-1")
    return submitted_engine


@pytest.fixture()
def po_engine(approved_engine):
    """Engine with a vendor, approved request, and an issued PO."""
    approved_engine.issue_po("po-1", "req-1")
    return approved_engine


# ===========================================================================
# Constructor
# ===========================================================================


class TestConstructor:
    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ProcurementRuntimeEngine("not-an-engine")

    def test_accepts_event_spine(self, es):
        eng = ProcurementRuntimeEngine(es)
        assert eng.vendor_count == 0

    def test_initial_vendor_count_zero(self, engine):
        assert engine.vendor_count == 0

    def test_initial_request_count_zero(self, engine):
        assert engine.request_count == 0

    def test_initial_po_count_zero(self, engine):
        assert engine.po_count == 0

    def test_initial_assessment_count_zero(self, engine):
        assert engine.assessment_count == 0

    def test_initial_commitment_count_zero(self, engine):
        assert engine.commitment_count == 0

    def test_initial_decision_count_zero(self, engine):
        assert engine.decision_count == 0

    def test_initial_renewal_count_zero(self, engine):
        assert engine.renewal_count == 0

    def test_initial_violation_count_zero(self, engine):
        assert engine.violation_count == 0


# ===========================================================================
# Vendor CRUD
# ===========================================================================


class TestRegisterVendor:
    def test_returns_vendor_record(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert isinstance(v, VendorRecord)

    def test_vendor_id_matches(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.vendor_id == "v-1"

    def test_vendor_name_matches(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.name == "Acme"

    def test_vendor_tenant_id_matches(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.tenant_id == "t-1"

    def test_vendor_status_active(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.status == VendorStatus.ACTIVE

    def test_vendor_risk_low(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.risk_level == VendorRiskLevel.LOW

    def test_vendor_default_category_empty(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.category == ""

    def test_vendor_custom_category(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1", category="IT")
        assert v.category == "IT"

    def test_vendor_has_registered_at(self, engine):
        v = engine.register_vendor("v-1", "Acme", "t-1")
        assert v.registered_at

    def test_increments_vendor_count(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        assert engine.vendor_count == 1

    def test_duplicate_raises(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.register_vendor("v-1", "Other", "t-1")

    def test_multiple_vendors(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        assert engine.vendor_count == 2

    def test_emits_event(self, es, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        assert es.event_count >= 1


class TestGetVendor:
    def test_returns_registered_vendor(self, vendor_engine):
        v = vendor_engine.get_vendor("v-1")
        assert v.vendor_id == "v-1"

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_vendor("v-missing")


class TestSuspendVendor:
    def test_suspends_active_vendor(self, vendor_engine):
        v = vendor_engine.suspend_vendor("v-1")
        assert v.status == VendorStatus.SUSPENDED

    def test_suspend_non_active_raises(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.suspend_vendor("v-1")

    def test_preserves_vendor_fields(self, vendor_engine):
        v = vendor_engine.suspend_vendor("v-1")
        assert v.name == "Acme Corp"
        assert v.tenant_id == "tenant-1"
        assert v.category == "IT"

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.suspend_vendor("v-missing")


class TestBlockVendor:
    def test_blocks_active_vendor(self, vendor_engine):
        v = vendor_engine.block_vendor("v-1")
        assert v.status == VendorStatus.BLOCKED

    def test_blocks_suspended_vendor(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        v = vendor_engine.block_vendor("v-1")
        assert v.status == VendorStatus.BLOCKED

    def test_already_blocked_raises(self, vendor_engine):
        vendor_engine.block_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already"):
            vendor_engine.block_vendor("v-1")

    def test_terminated_vendor_raises(self, vendor_engine):
        vendor_engine.terminate_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.block_vendor("v-1")

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.block_vendor("v-missing")


class TestTerminateVendor:
    def test_terminates_active_vendor(self, vendor_engine):
        v = vendor_engine.terminate_vendor("v-1")
        assert v.status == VendorStatus.TERMINATED

    def test_terminates_suspended_vendor(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        v = vendor_engine.terminate_vendor("v-1")
        assert v.status == VendorStatus.TERMINATED

    def test_terminates_blocked_vendor(self, vendor_engine):
        vendor_engine.block_vendor("v-1")
        v = vendor_engine.terminate_vendor("v-1")
        assert v.status == VendorStatus.TERMINATED

    def test_already_terminated_raises(self, vendor_engine):
        vendor_engine.terminate_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminated"):
            vendor_engine.terminate_vendor("v-1")

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.terminate_vendor("v-missing")


class TestReviewVendor:
    def test_review_active_vendor(self, vendor_engine):
        v = vendor_engine.review_vendor("v-1")
        assert v.status == VendorStatus.UNDER_REVIEW

    def test_review_suspended_vendor(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        v = vendor_engine.review_vendor("v-1")
        assert v.status == VendorStatus.UNDER_REVIEW

    def test_blocked_vendor_raises(self, vendor_engine):
        vendor_engine.block_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.review_vendor("v-1")

    def test_terminated_vendor_raises(self, vendor_engine):
        vendor_engine.terminate_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.review_vendor("v-1")

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError):
            engine.review_vendor("v-missing")


class TestVendorsForTenant:
    def test_returns_empty_tuple(self, engine):
        assert engine.vendors_for_tenant("t-1") == ()

    def test_returns_matching_vendors(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.register_vendor("v-3", "Gamma", "t-2")
        result = engine.vendors_for_tenant("t-1")
        assert len(result) == 2

    def test_returns_tuple_type(self, vendor_engine):
        result = vendor_engine.vendors_for_tenant("tenant-1")
        assert isinstance(result, tuple)

    def test_filters_by_tenant(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-2")
        result = engine.vendors_for_tenant("t-2")
        assert len(result) == 1
        assert result[0].vendor_id == "v-2"


# ===========================================================================
# Procurement Requests
# ===========================================================================


class TestCreateRequest:
    def test_returns_procurement_request(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert isinstance(r, ProcurementRequest)

    def test_request_id_matches(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.request_id == "req-1"

    def test_vendor_id_matches(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.vendor_id == "v-1"

    def test_tenant_id_matches(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.tenant_id == "tenant-1"

    def test_status_draft(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.status == ProcurementRequestStatus.DRAFT

    def test_estimated_amount(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.estimated_amount == 5000.0

    def test_default_currency(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.currency == "USD"

    def test_custom_currency(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0, currency="EUR")
        assert r.currency == "EUR"

    def test_default_description(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.description == ""

    def test_custom_description(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0, description="Office supplies")
        assert r.description == "Office supplies"

    def test_default_requested_by(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.requested_by == "system"

    def test_custom_requested_by(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0, requested_by="alice")
        assert r.requested_by == "alice"

    def test_has_requested_at(self, vendor_engine):
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert r.requested_at

    def test_increments_request_count(self, vendor_engine):
        vendor_engine.create_request("req-1", "v-1", "tenant-1", 5000.0)
        assert vendor_engine.request_count == 1

    def test_duplicate_raises(self, request_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            request_engine.create_request("req-1", "v-1", "tenant-1", 1000.0)

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.create_request("req-1", "v-missing", "t-1", 1000.0)

    def test_blocked_vendor_raises(self, vendor_engine):
        vendor_engine.block_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.create_request("req-1", "v-1", "tenant-1", 1000.0)

    def test_terminated_vendor_raises(self, vendor_engine):
        vendor_engine.terminate_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.create_request("req-1", "v-1", "tenant-1", 1000.0)

    def test_suspended_vendor_allowed(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        r = vendor_engine.create_request("req-1", "v-1", "tenant-1", 1000.0)
        assert r.status == ProcurementRequestStatus.DRAFT


class TestGetRequest:
    def test_returns_request(self, request_engine):
        r = request_engine.get_request("req-1")
        assert r.request_id == "req-1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_request("req-missing")


class TestSubmitRequest:
    def test_submits_draft(self, request_engine):
        r = request_engine.submit_request("req-1")
        assert r.status == ProcurementRequestStatus.SUBMITTED

    def test_non_draft_raises(self, submitted_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="DRAFT"):
            submitted_engine.submit_request("req-1")

    def test_preserves_amount(self, request_engine):
        r = request_engine.submit_request("req-1")
        assert r.estimated_amount == 5000.0

    def test_preserves_vendor_id(self, request_engine):
        r = request_engine.submit_request("req-1")
        assert r.vendor_id == "v-1"


class TestApproveRequest:
    def test_approves_submitted(self, submitted_engine):
        r = submitted_engine.approve_request("req-1")
        assert r.status == ProcurementRequestStatus.APPROVED

    def test_non_submitted_raises(self, request_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="SUBMITTED"):
            request_engine.approve_request("req-1")

    def test_already_approved_raises(self, approved_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            approved_engine.approve_request("req-1")

    def test_creates_decision(self, submitted_engine):
        submitted_engine.approve_request("req-1")
        assert submitted_engine.decision_count == 1

    def test_default_decided_by(self, submitted_engine):
        submitted_engine.approve_request("req-1")
        assert submitted_engine.decision_count >= 1

    def test_custom_decided_by(self, submitted_engine):
        submitted_engine.approve_request("req-1", decided_by="manager")
        assert submitted_engine.decision_count >= 1

    def test_preserves_amount(self, submitted_engine):
        r = submitted_engine.approve_request("req-1")
        assert r.estimated_amount == 5000.0


class TestDenyRequest:
    def test_denies_submitted(self, submitted_engine):
        r = submitted_engine.deny_request("req-1")
        assert r.status == ProcurementRequestStatus.DENIED

    def test_non_submitted_raises(self, request_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="SUBMITTED"):
            request_engine.deny_request("req-1")

    def test_creates_decision(self, submitted_engine):
        submitted_engine.deny_request("req-1")
        assert submitted_engine.decision_count == 1

    def test_custom_decided_by(self, submitted_engine):
        submitted_engine.deny_request("req-1", decided_by="cfo")
        assert submitted_engine.decision_count >= 1

    def test_custom_reason(self, submitted_engine):
        submitted_engine.deny_request("req-1", reason="Over budget")
        assert submitted_engine.decision_count >= 1

    def test_denied_cannot_approve(self, submitted_engine):
        submitted_engine.deny_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            submitted_engine.approve_request("req-1")

    def test_denied_cannot_cancel(self, submitted_engine):
        submitted_engine.deny_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            submitted_engine.cancel_request("req-1")


class TestCancelRequest:
    def test_cancel_draft(self, request_engine):
        r = request_engine.cancel_request("req-1")
        assert r.status == ProcurementRequestStatus.CANCELLED

    def test_cancel_submitted(self, submitted_engine):
        r = submitted_engine.cancel_request("req-1")
        assert r.status == ProcurementRequestStatus.CANCELLED

    def test_cancel_approved(self, approved_engine):
        r = approved_engine.cancel_request("req-1")
        assert r.status == ProcurementRequestStatus.CANCELLED

    def test_cancel_denied_raises(self, submitted_engine):
        submitted_engine.deny_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            submitted_engine.cancel_request("req-1")

    def test_cancel_cancelled_raises(self, request_engine):
        request_engine.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError):
            request_engine.cancel_request("req-1")

    def test_cancel_fulfilled_raises(self, po_engine):
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.cancel_request("req-1")


class TestRequestsForVendor:
    def test_returns_empty_tuple(self, vendor_engine):
        assert vendor_engine.requests_for_vendor("v-1") == ()

    def test_returns_matching_requests(self, request_engine):
        result = request_engine.requests_for_vendor("v-1")
        assert len(result) == 1

    def test_returns_tuple_type(self, request_engine):
        result = request_engine.requests_for_vendor("v-1")
        assert isinstance(result, tuple)

    def test_filters_by_vendor(self, vendor_engine):
        vendor_engine.register_vendor("v-2", "Beta", "tenant-1")
        vendor_engine.create_request("req-1", "v-1", "tenant-1", 1000.0)
        vendor_engine.create_request("req-2", "v-2", "tenant-1", 2000.0)
        assert len(vendor_engine.requests_for_vendor("v-1")) == 1
        assert len(vendor_engine.requests_for_vendor("v-2")) == 1


# ===========================================================================
# Purchase Orders
# ===========================================================================


class TestIssuePo:
    def test_returns_purchase_order(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert isinstance(po, PurchaseOrder)

    def test_po_id_matches(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.po_id == "po-1"

    def test_request_id_matches(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.request_id == "req-1"

    def test_vendor_id_from_request(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.vendor_id == "v-1"

    def test_tenant_id_from_request(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.tenant_id == "tenant-1"

    def test_status_issued(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.status == PurchaseOrderStatus.ISSUED

    def test_amount_from_request(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.amount == 5000.0

    def test_currency_from_request(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.currency == "USD"

    def test_has_issued_at(self, approved_engine):
        po = approved_engine.issue_po("po-1", "req-1")
        assert po.issued_at

    def test_marks_request_fulfilled(self, approved_engine):
        approved_engine.issue_po("po-1", "req-1")
        req = approved_engine.get_request("req-1")
        assert req.status == ProcurementRequestStatus.FULFILLED

    def test_increments_po_count(self, approved_engine):
        approved_engine.issue_po("po-1", "req-1")
        assert approved_engine.po_count == 1

    def test_duplicate_raises(self, po_engine):
        # req-1 is now FULFILLED, need a new approved request
        po_engine.register_vendor("v-2", "Beta", "tenant-1")
        po_engine.create_request("req-2", "v-2", "tenant-1", 3000.0)
        po_engine.submit_request("req-2")
        po_engine.approve_request("req-2")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            po_engine.issue_po("po-1", "req-2")

    def test_unapproved_request_raises(self, submitted_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            submitted_engine.issue_po("po-1", "req-1")

    def test_draft_request_raises(self, request_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            request_engine.issue_po("po-1", "req-1")

    def test_blocked_vendor_raises(self, approved_engine):
        approved_engine.block_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            approved_engine.issue_po("po-1", "req-1")

    def test_terminated_vendor_raises(self, approved_engine):
        approved_engine.terminate_vendor("v-1")
        with pytest.raises(RuntimeCoreInvariantError):
            approved_engine.issue_po("po-1", "req-1")

    def test_fulfilled_request_blocks_second_po(self, po_engine):
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            po_engine.issue_po("po-2", "req-1")


class TestGetPo:
    def test_returns_po(self, po_engine):
        po = po_engine.get_po("po-1")
        assert po.po_id == "po-1"

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_po("po-missing")


class TestAcknowledgePo:
    def test_acknowledges_issued(self, po_engine):
        po = po_engine.acknowledge_po("po-1")
        assert po.status == PurchaseOrderStatus.ACKNOWLEDGED

    def test_non_issued_raises(self, po_engine):
        po_engine.acknowledge_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError, match="ISSUED"):
            po_engine.acknowledge_po("po-1")

    def test_preserves_amount(self, po_engine):
        po = po_engine.acknowledge_po("po-1")
        assert po.amount == 5000.0

    def test_preserves_vendor_id(self, po_engine):
        po = po_engine.acknowledge_po("po-1")
        assert po.vendor_id == "v-1"


class TestFulfillPo:
    def test_fulfills_issued(self, po_engine):
        po = po_engine.fulfill_po("po-1")
        assert po.status == PurchaseOrderStatus.FULFILLED

    def test_fulfills_acknowledged(self, po_engine):
        po_engine.acknowledge_po("po-1")
        po = po_engine.fulfill_po("po-1")
        assert po.status == PurchaseOrderStatus.FULFILLED

    def test_fulfills_disputed(self, po_engine):
        po_engine.dispute_po("po-1")
        po = po_engine.fulfill_po("po-1")
        assert po.status == PurchaseOrderStatus.FULFILLED

    def test_already_fulfilled_raises(self, po_engine):
        po_engine.fulfill_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.fulfill_po("po-1")

    def test_cancelled_raises(self, po_engine):
        po_engine.cancel_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.fulfill_po("po-1")


class TestCancelPo:
    def test_cancels_issued(self, po_engine):
        po = po_engine.cancel_po("po-1")
        assert po.status == PurchaseOrderStatus.CANCELLED

    def test_cancels_acknowledged(self, po_engine):
        po_engine.acknowledge_po("po-1")
        po = po_engine.cancel_po("po-1")
        assert po.status == PurchaseOrderStatus.CANCELLED

    def test_cancels_disputed(self, po_engine):
        po_engine.dispute_po("po-1")
        po = po_engine.cancel_po("po-1")
        assert po.status == PurchaseOrderStatus.CANCELLED

    def test_already_cancelled_raises(self, po_engine):
        po_engine.cancel_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.cancel_po("po-1")

    def test_fulfilled_raises(self, po_engine):
        po_engine.fulfill_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.cancel_po("po-1")


class TestDisputePo:
    def test_disputes_issued(self, po_engine):
        po = po_engine.dispute_po("po-1")
        assert po.status == PurchaseOrderStatus.DISPUTED

    def test_disputes_acknowledged(self, po_engine):
        po_engine.acknowledge_po("po-1")
        po = po_engine.dispute_po("po-1")
        assert po.status == PurchaseOrderStatus.DISPUTED

    def test_fulfilled_raises(self, po_engine):
        po_engine.fulfill_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.dispute_po("po-1")

    def test_cancelled_raises(self, po_engine):
        po_engine.cancel_po("po-1")
        with pytest.raises(RuntimeCoreInvariantError):
            po_engine.dispute_po("po-1")


class TestPosForVendor:
    def test_returns_empty_tuple(self, vendor_engine):
        assert vendor_engine.pos_for_vendor("v-1") == ()

    def test_returns_matching_pos(self, po_engine):
        result = po_engine.pos_for_vendor("v-1")
        assert len(result) == 1

    def test_returns_tuple_type(self, po_engine):
        result = po_engine.pos_for_vendor("v-1")
        assert isinstance(result, tuple)

    def test_filters_by_vendor(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        engine.create_request("r-2", "v-2", "t-1", 2000.0)
        engine.submit_request("r-2")
        engine.approve_request("r-2")
        engine.issue_po("po-2", "r-2")
        assert len(engine.pos_for_vendor("v-1")) == 1
        assert len(engine.pos_for_vendor("v-2")) == 1


# ===========================================================================
# Vendor Assessments
# ===========================================================================


class TestAssessVendor:
    def test_returns_vendor_assessment(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert isinstance(a, VendorAssessment)

    def test_assessment_id_matches(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert a.assessment_id == "a-1"

    def test_vendor_id_matches(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert a.vendor_id == "v-1"

    def test_performance_score_matches(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.85, 0)
        assert a.performance_score == 0.85

    def test_fault_count_matches(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 2)
        assert a.fault_count == 2

    def test_default_assessed_by(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert a.assessed_by == "system"

    def test_custom_assessed_by(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0, assessed_by="auditor")
        assert a.assessed_by == "auditor"

    def test_has_assessed_at(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert a.assessed_at

    def test_increments_assessment_count(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert vendor_engine.assessment_count == 1

    def test_duplicate_raises(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            vendor_engine.assess_vendor("a-1", "v-1", 0.8, 1)

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.assess_vendor("a-1", "v-missing", 0.9, 0)

    # Risk level computation
    def test_risk_low_high_score_no_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert a.risk_level == VendorRiskLevel.LOW

    def test_risk_low_score_exactly_0_8_no_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.8, 0)
        assert a.risk_level == VendorRiskLevel.LOW

    def test_risk_medium_score_below_0_8(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.79, 0)
        assert a.risk_level == VendorRiskLevel.MEDIUM

    def test_risk_medium_one_fault(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 1)
        assert a.risk_level == VendorRiskLevel.MEDIUM

    def test_risk_medium_two_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 2)
        assert a.risk_level == VendorRiskLevel.MEDIUM

    def test_risk_high_score_below_0_5(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.49, 0)
        assert a.risk_level == VendorRiskLevel.HIGH

    def test_risk_high_three_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 3)
        assert a.risk_level == VendorRiskLevel.HIGH

    def test_risk_high_four_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 4)
        assert a.risk_level == VendorRiskLevel.HIGH

    def test_risk_critical_score_below_0_3(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.29, 0)
        assert a.risk_level == VendorRiskLevel.CRITICAL

    def test_risk_critical_five_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 5)
        assert a.risk_level == VendorRiskLevel.CRITICAL

    def test_risk_critical_many_faults(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.9, 10)
        assert a.risk_level == VendorRiskLevel.CRITICAL

    def test_risk_critical_both_triggers(self, vendor_engine):
        a = vendor_engine.assess_vendor("a-1", "v-1", 0.1, 7)
        assert a.risk_level == VendorRiskLevel.CRITICAL

    # Vendor risk auto-update
    def test_updates_vendor_risk_level(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        v = vendor_engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.HIGH

    def test_no_update_when_risk_same(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        v = vendor_engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.LOW

    def test_risk_upgrade_critical(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.1, 5)
        v = vendor_engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.CRITICAL

    def test_risk_downgrade_after_improvement(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.2, 6)
        vendor_engine.assess_vendor("a-2", "v-1", 0.95, 0)
        v = vendor_engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.LOW


class TestAssessmentsForVendor:
    def test_returns_empty_tuple(self, vendor_engine):
        assert vendor_engine.assessments_for_vendor("v-1") == ()

    def test_returns_matching(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        vendor_engine.assess_vendor("a-2", "v-1", 0.8, 1)
        result = vendor_engine.assessments_for_vendor("v-1")
        assert len(result) == 2

    def test_returns_tuple(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        result = vendor_engine.assessments_for_vendor("v-1")
        assert isinstance(result, tuple)

    def test_filters_by_vendor(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.9, 0)
        engine.assess_vendor("a-2", "v-2", 0.8, 1)
        assert len(engine.assessments_for_vendor("v-1")) == 1
        assert len(engine.assessments_for_vendor("v-2")) == 1


# ===========================================================================
# Vendor Commitments
# ===========================================================================


class TestRegisterCommitment:
    def test_returns_vendor_commitment(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert isinstance(c, VendorCommitment)

    def test_commitment_id_matches(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert c.commitment_id == "c-1"

    def test_vendor_id_matches(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert c.vendor_id == "v-1"

    def test_contract_ref_matches(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert c.contract_ref == "contract-100"

    def test_default_description(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert c.description == ""

    def test_custom_description(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100", description="SLA target")
        assert c.description == "SLA target"

    def test_default_target_value(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert c.target_value == ""

    def test_custom_target_value(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100", target_value="99.9%")
        assert c.target_value == "99.9%"

    def test_has_created_at(self, vendor_engine):
        c = vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert c.created_at

    def test_increments_commitment_count(self, vendor_engine):
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert vendor_engine.commitment_count == 1

    def test_duplicate_raises(self, vendor_engine):
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            vendor_engine.register_commitment("c-1", "v-1", "contract-200")

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.register_commitment("c-1", "v-missing", "contract-100")


class TestCommitmentsForVendor:
    def test_returns_empty_tuple(self, vendor_engine):
        assert vendor_engine.commitments_for_vendor("v-1") == ()

    def test_returns_matching(self, vendor_engine):
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        result = vendor_engine.commitments_for_vendor("v-1")
        assert len(result) == 1

    def test_returns_tuple(self, vendor_engine):
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        result = vendor_engine.commitments_for_vendor("v-1")
        assert isinstance(result, tuple)

    def test_multiple_commitments(self, vendor_engine):
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        vendor_engine.register_commitment("c-2", "v-1", "contract-200")
        result = vendor_engine.commitments_for_vendor("v-1")
        assert len(result) == 2


# ===========================================================================
# Renewal Windows
# ===========================================================================


class TestScheduleRenewal:
    def test_returns_renewal_window(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert isinstance(r, ProcurementRenewalWindow)

    def test_renewal_id_matches(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert r.renewal_id == "ren-1"

    def test_vendor_id_matches(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert r.vendor_id == "v-1"

    def test_contract_ref_matches(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert r.contract_ref == "contract-100"

    def test_disposition_pending(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert r.disposition == RenewalDisposition.PENDING

    def test_opens_at_matches(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert r.opens_at == "2026-01-01"

    def test_closes_at_matches(self, vendor_engine):
        r = vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert r.closes_at == "2026-06-01"

    def test_increments_renewal_count(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        assert vendor_engine.renewal_count == 1

    def test_duplicate_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            vendor_engine.schedule_renewal("ren-1", "v-1", "contract-200", "2026-01-01", "2026-06-01")

    def test_unknown_vendor_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.schedule_renewal("ren-1", "v-missing", "contract-100", "2026-01-01", "2026-06-01")


class TestApproveRenewal:
    def test_approves_pending(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.approve_renewal("ren-1")
        assert r.disposition == RenewalDisposition.APPROVED

    def test_approves_deferred(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.defer_renewal("ren-1")
        r = vendor_engine.approve_renewal("ren-1")
        assert r.disposition == RenewalDisposition.APPROVED

    def test_already_approved_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.approve_renewal("ren-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.approve_renewal("ren-1")

    def test_denied_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.deny_renewal("ren-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.approve_renewal("ren-1")

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.approve_renewal("ren-missing")

    def test_high_risk_vendor_blocks(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        with pytest.raises(RuntimeCoreInvariantError, match="risk"):
            vendor_engine.approve_renewal("ren-1")

    def test_critical_risk_vendor_blocks(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.1, 5)
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        with pytest.raises(RuntimeCoreInvariantError, match="risk"):
            vendor_engine.approve_renewal("ren-1")

    def test_medium_risk_vendor_allowed(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.7, 1)
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.approve_renewal("ren-1")
        assert r.disposition == RenewalDisposition.APPROVED

    def test_low_risk_vendor_allowed(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.approve_renewal("ren-1")
        assert r.disposition == RenewalDisposition.APPROVED


class TestDenyRenewal:
    def test_denies_pending(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.deny_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DENIED

    def test_denies_deferred(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.defer_renewal("ren-1")
        r = vendor_engine.deny_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DENIED

    def test_already_denied_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.deny_renewal("ren-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.deny_renewal("ren-1")

    def test_approved_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.approve_renewal("ren-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.deny_renewal("ren-1")

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.deny_renewal("ren-missing")


class TestDeferRenewal:
    def test_defers_pending(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.defer_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DEFERRED

    def test_approved_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.approve_renewal("ren-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.defer_renewal("ren-1")

    def test_denied_raises(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.deny_renewal("ren-1")
        with pytest.raises(RuntimeCoreInvariantError):
            vendor_engine.defer_renewal("ren-1")

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.defer_renewal("ren-missing")


class TestRenewalsForVendor:
    def test_returns_empty_tuple(self, vendor_engine):
        assert vendor_engine.renewals_for_vendor("v-1") == ()

    def test_returns_matching(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        result = vendor_engine.renewals_for_vendor("v-1")
        assert len(result) == 1

    def test_returns_tuple(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        result = vendor_engine.renewals_for_vendor("v-1")
        assert isinstance(result, tuple)

    def test_multiple_renewals(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "contract-100", "2026-01-01", "2026-06-01")
        vendor_engine.schedule_renewal("ren-2", "v-1", "contract-200", "2026-07-01", "2026-12-01")
        result = vendor_engine.renewals_for_vendor("v-1")
        assert len(result) == 2

    def test_filters_by_vendor(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        engine.schedule_renewal("ren-2", "v-2", "c-200", "2026-01-01", "2026-06-01")
        assert len(engine.renewals_for_vendor("v-1")) == 1
        assert len(engine.renewals_for_vendor("v-2")) == 1


# ===========================================================================
# Violation Detection
# ===========================================================================


class TestDetectProcurementViolations:
    def test_no_violations_clean_state(self, engine):
        result = engine.detect_procurement_violations()
        assert result == ()

    def test_no_violations_low_risk_active_po(self, po_engine):
        result = po_engine.detect_procurement_violations()
        assert result == ()

    def test_high_risk_vendor_with_active_po(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert len(result) >= 1

    def test_critical_risk_vendor_with_active_po(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.1, 5)
        result = po_engine.detect_procurement_violations()
        assert len(result) >= 1

    def test_blocked_vendor_with_active_po(self, po_engine):
        # Block vendor after PO issued
        po_engine.block_vendor("v-1")
        result = po_engine.detect_procurement_violations()
        assert len(result) >= 1

    def test_terminated_vendor_with_active_po(self, po_engine):
        po_engine.terminate_vendor("v-1")
        result = po_engine.detect_procurement_violations()
        assert len(result) >= 1

    def test_no_violation_fulfilled_po(self, po_engine):
        po_engine.fulfill_po("po-1")
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result == ()

    def test_no_violation_cancelled_po(self, po_engine):
        po_engine.cancel_po("po-1")
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result == ()

    def test_idempotent(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        first = po_engine.detect_procurement_violations()
        second = po_engine.detect_procurement_violations()
        assert len(first) >= 1
        assert len(second) == 0

    def test_increments_violation_count(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        po_engine.detect_procurement_violations()
        assert po_engine.violation_count >= 1

    def test_violation_has_vendor_id(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result[0].vendor_id == "v-1"

    def test_violation_has_tenant_id(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result[0].tenant_id == "tenant-1"

    def test_violation_has_operation(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result[0].operation == "risky_active_po"

    def test_blocked_violation_operation(self, po_engine):
        po_engine.block_vendor("v-1")
        result = po_engine.detect_procurement_violations()
        ops = {v.operation for v in result}
        assert "blocked_active_po" in ops

    def test_violation_has_reason(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result[0].reason

    def test_violation_has_detected_at(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        result = po_engine.detect_procurement_violations()
        assert result[0].detected_at

    def test_medium_risk_no_violation(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.7, 1)
        result = po_engine.detect_procurement_violations()
        assert result == ()


class TestViolationsForVendor:
    def test_returns_empty_tuple(self, vendor_engine):
        assert vendor_engine.violations_for_vendor("v-1") == ()

    def test_returns_matching(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        po_engine.detect_procurement_violations()
        result = po_engine.violations_for_vendor("v-1")
        assert len(result) >= 1

    def test_returns_tuple(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        po_engine.detect_procurement_violations()
        result = po_engine.violations_for_vendor("v-1")
        assert isinstance(result, tuple)


# ===========================================================================
# Procurement Snapshot
# ===========================================================================


class TestProcurementSnapshot:
    def test_returns_snapshot(self, engine):
        s = engine.procurement_snapshot("snap-1")
        assert isinstance(s, ProcurementSnapshot)

    def test_snapshot_id_matches(self, engine):
        s = engine.procurement_snapshot("snap-1")
        assert s.snapshot_id == "snap-1"

    def test_empty_state(self, engine):
        s = engine.procurement_snapshot("snap-1")
        assert s.total_vendors == 0
        assert s.total_requests == 0
        assert s.total_purchase_orders == 0
        assert s.total_assessments == 0
        assert s.total_commitments == 0
        assert s.total_renewals == 0
        assert s.total_violations == 0
        assert s.total_procurement_value == 0.0

    def test_has_captured_at(self, engine):
        s = engine.procurement_snapshot("snap-1")
        assert s.captured_at

    def test_duplicate_raises(self, engine):
        engine.procurement_snapshot("snap-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.procurement_snapshot("snap-1")

    def test_total_vendors(self, vendor_engine):
        s = vendor_engine.procurement_snapshot("snap-1")
        assert s.total_vendors == 1

    def test_total_requests(self, request_engine):
        s = request_engine.procurement_snapshot("snap-1")
        assert s.total_requests == 1

    def test_total_pos(self, po_engine):
        s = po_engine.procurement_snapshot("snap-1")
        assert s.total_purchase_orders == 1

    def test_total_assessments(self, vendor_engine):
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        s = vendor_engine.procurement_snapshot("snap-1")
        assert s.total_assessments == 1

    def test_total_commitments(self, vendor_engine):
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        s = vendor_engine.procurement_snapshot("snap-1")
        assert s.total_commitments == 1

    def test_total_renewals(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        s = vendor_engine.procurement_snapshot("snap-1")
        assert s.total_renewals == 1

    def test_total_violations(self, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        po_engine.detect_procurement_violations()
        s = po_engine.procurement_snapshot("snap-1")
        assert s.total_violations >= 1

    def test_procurement_value_from_pos(self, po_engine):
        s = po_engine.procurement_snapshot("snap-1")
        assert s.total_procurement_value == 5000.0

    def test_cancelled_po_excluded_from_value(self, po_engine):
        po_engine.cancel_po("po-1")
        s = po_engine.procurement_snapshot("snap-1")
        assert s.total_procurement_value == 0.0

    def test_fulfilled_po_included_in_value(self, po_engine):
        po_engine.fulfill_po("po-1")
        s = po_engine.procurement_snapshot("snap-1")
        assert s.total_procurement_value == 5000.0

    def test_multiple_pos_summed(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        engine.create_request("r-2", "v-2", "t-1", 2000.0)
        engine.submit_request("r-2")
        engine.approve_request("r-2")
        engine.issue_po("po-2", "r-2")
        s = engine.procurement_snapshot("snap-1")
        assert s.total_procurement_value == 3000.0

    def test_multiple_pos_one_cancelled(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        engine.create_request("r-2", "v-2", "t-1", 2000.0)
        engine.submit_request("r-2")
        engine.approve_request("r-2")
        engine.issue_po("po-2", "r-2")
        engine.cancel_po("po-1")
        s = engine.procurement_snapshot("snap-1")
        assert s.total_procurement_value == 2000.0


# ===========================================================================
# State Hash
# ===========================================================================


class TestStateHash:
    def test_returns_string(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)

    def test_returns_16_chars(self, engine):
        h = engine.state_hash()
        assert len(h) == 64

    def test_hex_string(self, engine):
        h = engine.state_hash()
        int(h, 16)  # should not raise

    def test_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_with_vendor(self, engine):
        h1 = engine.state_hash()
        engine.register_vendor("v-1", "Acme", "t-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_request(self, vendor_engine):
        h1 = vendor_engine.state_hash()
        vendor_engine.create_request("req-1", "v-1", "tenant-1", 1000.0)
        h2 = vendor_engine.state_hash()
        assert h1 != h2

    def test_changes_with_po(self, approved_engine):
        h1 = approved_engine.state_hash()
        approved_engine.issue_po("po-1", "req-1")
        h2 = approved_engine.state_hash()
        assert h1 != h2

    def test_changes_with_assessment(self, vendor_engine):
        h1 = vendor_engine.state_hash()
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        h2 = vendor_engine.state_hash()
        assert h1 != h2

    def test_changes_with_commitment(self, vendor_engine):
        h1 = vendor_engine.state_hash()
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        h2 = vendor_engine.state_hash()
        assert h1 != h2

    def test_changes_with_renewal(self, vendor_engine):
        h1 = vendor_engine.state_hash()
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        h2 = vendor_engine.state_hash()
        assert h1 != h2

    def test_changes_with_violation(self, po_engine):
        h1 = po_engine.state_hash()
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        po_engine.detect_procurement_violations()
        h2 = po_engine.state_hash()
        assert h1 != h2


# ===========================================================================
# Properties
# ===========================================================================


class TestProperties:
    def test_vendor_count(self, engine):
        assert engine.vendor_count == 0
        engine.register_vendor("v-1", "Acme", "t-1")
        assert engine.vendor_count == 1
        engine.register_vendor("v-2", "Beta", "t-1")
        assert engine.vendor_count == 2

    def test_request_count(self, vendor_engine):
        assert vendor_engine.request_count == 0
        vendor_engine.create_request("r-1", "v-1", "tenant-1", 1000.0)
        assert vendor_engine.request_count == 1

    def test_po_count(self, approved_engine):
        assert approved_engine.po_count == 0
        approved_engine.issue_po("po-1", "req-1")
        assert approved_engine.po_count == 1

    def test_assessment_count(self, vendor_engine):
        assert vendor_engine.assessment_count == 0
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert vendor_engine.assessment_count == 1

    def test_commitment_count(self, vendor_engine):
        assert vendor_engine.commitment_count == 0
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert vendor_engine.commitment_count == 1

    def test_decision_count(self, submitted_engine):
        assert submitted_engine.decision_count == 0
        submitted_engine.approve_request("req-1")
        assert submitted_engine.decision_count == 1

    def test_renewal_count(self, vendor_engine):
        assert vendor_engine.renewal_count == 0
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        assert vendor_engine.renewal_count == 1

    def test_violation_count(self, po_engine):
        assert po_engine.violation_count == 0
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        po_engine.detect_procurement_violations()
        assert po_engine.violation_count >= 1


# ===========================================================================
# Golden Scenarios
# ===========================================================================


class TestGoldenScenario1BudgetApprovedRequestCreatesPO:
    """Register vendor -> create request -> submit -> approve -> issue PO
    -> verify FULFILLED request, ISSUED PO."""

    def test_full_lifecycle(self, engine):
        engine.register_vendor("v-1", "Acme Corp", "t-1", category="IT")
        engine.create_request("req-1", "v-1", "t-1", 10_000.0, description="Server hardware")
        engine.submit_request("req-1")
        engine.approve_request("req-1", decided_by="cfo")
        po = engine.issue_po("po-1", "req-1")
        assert po.status == PurchaseOrderStatus.ISSUED
        assert po.amount == 10_000.0
        req = engine.get_request("req-1")
        assert req.status == ProcurementRequestStatus.FULFILLED

    def test_decision_created(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        engine.submit_request("req-1")
        engine.approve_request("req-1")
        assert engine.decision_count == 1

    def test_po_vendor_matches(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        engine.submit_request("req-1")
        engine.approve_request("req-1")
        po = engine.issue_po("po-1", "req-1")
        assert po.vendor_id == "v-1"

    def test_po_currency_inherited(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0, currency="GBP")
        engine.submit_request("req-1")
        engine.approve_request("req-1")
        po = engine.issue_po("po-1", "req-1")
        assert po.currency == "GBP"

    def test_event_spine_received_events(self, es):
        engine = ProcurementRuntimeEngine(es)
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        engine.submit_request("req-1")
        engine.approve_request("req-1")
        engine.issue_po("po-1", "req-1")
        assert es.event_count >= 5


class TestGoldenScenario2MissingApprovalBlocksPO:
    """Register vendor -> create request -> submit -> try issue_po
    -> RuntimeCoreInvariantError."""

    def test_submitted_request_cannot_issue_po(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        engine.submit_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            engine.issue_po("po-1", "req-1")

    def test_draft_request_cannot_issue_po(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            engine.issue_po("po-1", "req-1")

    def test_denied_request_cannot_issue_po(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        engine.submit_request("req-1")
        engine.deny_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            engine.issue_po("po-1", "req-1")

    def test_cancelled_request_cannot_issue_po(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("req-1", "v-1", "t-1", 5000.0)
        engine.cancel_request("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="APPROVED"):
            engine.issue_po("po-1", "req-1")


class TestGoldenScenario3RiskyVendorBlocksRenewal:
    """Register vendor -> assess with high faults -> schedule renewal
    -> approve_renewal raises."""

    def test_high_risk_blocks_renewal(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.4, 4)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.HIGH
        engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        with pytest.raises(RuntimeCoreInvariantError, match="risk"):
            engine.approve_renewal("ren-1")

    def test_critical_risk_blocks_renewal(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.1, 6)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.CRITICAL
        engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        with pytest.raises(RuntimeCoreInvariantError, match="risk"):
            engine.approve_renewal("ren-1")

    def test_deny_still_works_for_risky_vendor(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.4, 4)
        engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        r = engine.deny_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DENIED

    def test_defer_still_works_for_risky_vendor(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.4, 4)
        engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        r = engine.defer_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DEFERRED


class TestGoldenScenario4ConnectorDependencyCreatesProcurement:
    """Register vendor -> create request with connector description
    -> submit -> approve -> issue PO."""

    def test_connector_procurement_flow(self, engine):
        engine.register_vendor("v-1", "Cloud Connector Inc", "t-1", category="SaaS")
        engine.create_request(
            "req-1", "v-1", "t-1", 25_000.0,
            description="Connector: Salesforce integration bridge",
            requested_by="connector-mgr",
        )
        engine.submit_request("req-1")
        engine.approve_request("req-1", decided_by="connector-approver")
        po = engine.issue_po("po-1", "req-1")
        assert po.status == PurchaseOrderStatus.ISSUED
        assert po.amount == 25_000.0

    def test_connector_request_description_preserved(self, engine):
        engine.register_vendor("v-1", "Cloud Connector Inc", "t-1")
        engine.create_request(
            "req-1", "v-1", "t-1", 25_000.0,
            description="Connector: Salesforce integration bridge",
        )
        req = engine.get_request("req-1")
        assert "Connector" in req.description

    def test_connector_requested_by_preserved(self, engine):
        engine.register_vendor("v-1", "Cloud Connector Inc", "t-1")
        engine.create_request(
            "req-1", "v-1", "t-1", 25_000.0,
            requested_by="connector-mgr",
        )
        req = engine.get_request("req-1")
        assert req.requested_by == "connector-mgr"


class TestGoldenScenario5RepeatedFailuresDegradeVendor:
    """Register vendor -> assess low -> assess high faults
    -> verify risk upgrades."""

    def test_risk_escalation(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        # First assessment: MEDIUM risk
        engine.assess_vendor("a-1", "v-1", 0.7, 1)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.MEDIUM
        # Second assessment: HIGH risk
        engine.assess_vendor("a-2", "v-1", 0.4, 3)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.HIGH

    def test_risk_escalation_to_critical(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.7, 1)
        engine.assess_vendor("a-2", "v-1", 0.4, 3)
        engine.assess_vendor("a-3", "v-1", 0.1, 7)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.CRITICAL

    def test_risk_recovery(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.2, 6)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.CRITICAL
        engine.assess_vendor("a-2", "v-1", 0.95, 0)
        v = engine.get_vendor("v-1")
        assert v.risk_level == VendorRiskLevel.LOW

    def test_multiple_assessments_tracked(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.assess_vendor("a-1", "v-1", 0.7, 1)
        engine.assess_vendor("a-2", "v-1", 0.4, 3)
        engine.assess_vendor("a-3", "v-1", 0.1, 7)
        assert engine.assessment_count == 3
        assert len(engine.assessments_for_vendor("v-1")) == 3


class TestGoldenScenario6SnapshotReflectsState:
    """Mixed vendors/requests/POs -> snapshot -> verify counts."""

    def test_comprehensive_snapshot(self, engine):
        # Two vendors
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        # Two requests, one approved with PO
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        # Second request denied
        engine.create_request("r-2", "v-2", "t-1", 2000.0)
        engine.submit_request("r-2")
        engine.deny_request("r-2")
        # Assessment and commitment
        engine.assess_vendor("a-1", "v-1", 0.9, 0)
        engine.register_commitment("c-1", "v-1", "contract-100")
        # Renewal
        engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")

        snap = engine.procurement_snapshot("snap-1")
        assert snap.total_vendors == 2
        assert snap.total_requests == 2
        assert snap.total_purchase_orders == 1
        assert snap.total_assessments == 1
        assert snap.total_commitments == 1
        assert snap.total_renewals == 1
        assert snap.total_violations == 0
        assert snap.total_procurement_value == 1000.0

    def test_snapshot_with_violations(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 5000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        engine.assess_vendor("a-1", "v-1", 0.3, 4)
        engine.detect_procurement_violations()
        snap = engine.procurement_snapshot("snap-1")
        assert snap.total_violations >= 1
        assert snap.total_procurement_value == 5000.0

    def test_snapshot_cancelled_po_excluded(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        engine.create_request("r-2", "v-2", "t-1", 3000.0)
        engine.submit_request("r-2")
        engine.approve_request("r-2")
        engine.issue_po("po-2", "r-2")
        engine.cancel_po("po-2")
        snap = engine.procurement_snapshot("snap-1")
        assert snap.total_purchase_orders == 2
        assert snap.total_procurement_value == 1000.0

    def test_multiple_snapshots(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        snap1 = engine.procurement_snapshot("snap-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        snap2 = engine.procurement_snapshot("snap-2")
        assert snap1.total_vendors == 1
        assert snap2.total_vendors == 2


# ===========================================================================
# Edge Cases and Integration
# ===========================================================================


class TestVendorStatusTransitions:
    def test_active_to_suspended_to_under_review(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        v = vendor_engine.review_vendor("v-1")
        assert v.status == VendorStatus.UNDER_REVIEW

    def test_active_to_under_review(self, vendor_engine):
        v = vendor_engine.review_vendor("v-1")
        assert v.status == VendorStatus.UNDER_REVIEW

    def test_active_to_blocked_to_terminated(self, vendor_engine):
        vendor_engine.block_vendor("v-1")
        v = vendor_engine.terminate_vendor("v-1")
        assert v.status == VendorStatus.TERMINATED

    def test_suspended_to_blocked(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        v = vendor_engine.block_vendor("v-1")
        assert v.status == VendorStatus.BLOCKED

    def test_suspended_to_terminated(self, vendor_engine):
        vendor_engine.suspend_vendor("v-1")
        v = vendor_engine.terminate_vendor("v-1")
        assert v.status == VendorStatus.TERMINATED


class TestRequestStatusTransitions:
    def test_draft_to_submitted_to_approved_to_fulfilled(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.submit_request("r-1")
        engine.approve_request("r-1")
        engine.issue_po("po-1", "r-1")
        assert engine.get_request("r-1").status == ProcurementRequestStatus.FULFILLED

    def test_draft_to_cancelled(self, request_engine):
        r = request_engine.cancel_request("req-1")
        assert r.status == ProcurementRequestStatus.CANCELLED

    def test_submitted_to_denied(self, submitted_engine):
        r = submitted_engine.deny_request("req-1")
        assert r.status == ProcurementRequestStatus.DENIED


class TestPOStatusTransitions:
    def test_issued_to_acknowledged_to_fulfilled(self, po_engine):
        po_engine.acknowledge_po("po-1")
        po = po_engine.fulfill_po("po-1")
        assert po.status == PurchaseOrderStatus.FULFILLED

    def test_issued_to_disputed_to_cancelled(self, po_engine):
        po_engine.dispute_po("po-1")
        po = po_engine.cancel_po("po-1")
        assert po.status == PurchaseOrderStatus.CANCELLED

    def test_issued_to_disputed_to_fulfilled(self, po_engine):
        po_engine.dispute_po("po-1")
        po = po_engine.fulfill_po("po-1")
        assert po.status == PurchaseOrderStatus.FULFILLED

    def test_issued_to_cancelled(self, po_engine):
        po = po_engine.cancel_po("po-1")
        assert po.status == PurchaseOrderStatus.CANCELLED

    def test_issued_to_fulfilled(self, po_engine):
        po = po_engine.fulfill_po("po-1")
        assert po.status == PurchaseOrderStatus.FULFILLED

    def test_acknowledged_to_disputed(self, po_engine):
        po_engine.acknowledge_po("po-1")
        po = po_engine.dispute_po("po-1")
        assert po.status == PurchaseOrderStatus.DISPUTED


class TestMultiVendorWorkflows:
    def test_two_vendors_independent_requests(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.create_request("r-1", "v-1", "t-1", 1000.0)
        engine.create_request("r-2", "v-2", "t-1", 2000.0)
        engine.submit_request("r-1")
        engine.submit_request("r-2")
        engine.approve_request("r-1")
        engine.deny_request("r-2")
        assert engine.get_request("r-1").status == ProcurementRequestStatus.APPROVED
        assert engine.get_request("r-2").status == ProcurementRequestStatus.DENIED

    def test_blocking_one_vendor_does_not_affect_other(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-1")
        engine.block_vendor("v-1")
        r = engine.create_request("r-1", "v-2", "t-1", 1000.0)
        assert r.status == ProcurementRequestStatus.DRAFT

    def test_multi_tenant_isolation(self, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        engine.register_vendor("v-2", "Beta", "t-2")
        assert len(engine.vendors_for_tenant("t-1")) == 1
        assert len(engine.vendors_for_tenant("t-2")) == 1

    def test_multiple_requests_same_vendor(self, vendor_engine):
        vendor_engine.create_request("r-1", "v-1", "tenant-1", 1000.0)
        vendor_engine.create_request("r-2", "v-1", "tenant-1", 2000.0)
        vendor_engine.create_request("r-3", "v-1", "tenant-1", 3000.0)
        assert len(vendor_engine.requests_for_vendor("v-1")) == 3


class TestRenewalDispositionTransitions:
    def test_pending_to_approved(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.approve_renewal("ren-1")
        assert r.disposition == RenewalDisposition.APPROVED

    def test_pending_to_denied(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.deny_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DENIED

    def test_pending_to_deferred(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        r = vendor_engine.defer_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DEFERRED

    def test_deferred_to_approved(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        vendor_engine.defer_renewal("ren-1")
        r = vendor_engine.approve_renewal("ren-1")
        assert r.disposition == RenewalDisposition.APPROVED

    def test_deferred_to_denied(self, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        vendor_engine.defer_renewal("ren-1")
        r = vendor_engine.deny_renewal("ren-1")
        assert r.disposition == RenewalDisposition.DENIED


class TestEventEmission:
    def test_vendor_registration_emits(self, es, engine):
        engine.register_vendor("v-1", "Acme", "t-1")
        assert es.event_count >= 1

    def test_request_creation_emits(self, es, vendor_engine):
        initial = es.event_count
        vendor_engine.create_request("r-1", "v-1", "tenant-1", 1000.0)
        assert es.event_count > initial

    def test_po_issuance_emits(self, es, approved_engine):
        initial = es.event_count
        approved_engine.issue_po("po-1", "req-1")
        assert es.event_count > initial

    def test_vendor_suspension_emits(self, es, vendor_engine):
        initial = es.event_count
        vendor_engine.suspend_vendor("v-1")
        assert es.event_count > initial

    def test_assessment_emits(self, es, vendor_engine):
        initial = es.event_count
        vendor_engine.assess_vendor("a-1", "v-1", 0.9, 0)
        assert es.event_count > initial

    def test_commitment_emits(self, es, vendor_engine):
        initial = es.event_count
        vendor_engine.register_commitment("c-1", "v-1", "contract-100")
        assert es.event_count > initial

    def test_renewal_scheduling_emits(self, es, vendor_engine):
        initial = es.event_count
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        assert es.event_count > initial

    def test_renewal_approval_emits(self, es, vendor_engine):
        vendor_engine.schedule_renewal("ren-1", "v-1", "c-100", "2026-01-01", "2026-06-01")
        initial = es.event_count
        vendor_engine.approve_renewal("ren-1")
        assert es.event_count > initial

    def test_violation_detection_emits(self, es, po_engine):
        po_engine.assess_vendor("a-1", "v-1", 0.4, 3)
        initial = es.event_count
        po_engine.detect_procurement_violations()
        assert es.event_count > initial

    def test_snapshot_emits(self, es, engine):
        initial = es.event_count
        engine.procurement_snapshot("snap-1")
        assert es.event_count > initial


class TestBoundedContracts:
    def test_duplicate_vendor_error_is_bounded(self, engine):
        engine.register_vendor("vendor-secret", "Sensitive Vendor", "tenant-secret")

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.register_vendor("vendor-secret", "Sensitive Vendor", "tenant-secret")

        message = str(excinfo.value)
        assert message == "Duplicate vendor_id"
        assert "vendor-secret" not in message
        assert "tenant-secret" not in message

    def test_procurement_violation_reason_is_bounded(self, po_engine):
        po_engine.assess_vendor("assessment-secret", "v-1", 0.4, 3)

        violations = po_engine.detect_procurement_violations()
        assert len(violations) == 1
        assert violations[0].reason == "Vendor has elevated risk with active purchase orders"
        assert "v-1" not in violations[0].reason
        assert "HIGH" not in violations[0].reason
        assert "3" not in violations[0].reason
