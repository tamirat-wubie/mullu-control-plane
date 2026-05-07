"""Tests for procurement runtime contracts."""

from __future__ import annotations

from types import MappingProxyType

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


def _vendor(**overrides) -> VendorRecord:
    defaults = dict(
        vendor_id="vnd-001",
        name="Acme Corp",
        tenant_id="ten-001",
        status=VendorStatus.ACTIVE,
        risk_level=VendorRiskLevel.LOW,
        category="supplies",
        registered_at=TS,
    )
    defaults.update(overrides)
    return VendorRecord(**defaults)


def _procurement_request(**overrides) -> ProcurementRequest:
    defaults = dict(
        request_id="req-001",
        vendor_id="vnd-001",
        tenant_id="ten-001",
        status=ProcurementRequestStatus.DRAFT,
        description="Office supplies",
        estimated_amount=500.0,
        currency="USD",
        requested_by="user-001",
        requested_at=TS,
    )
    defaults.update(overrides)
    return ProcurementRequest(**defaults)


def _purchase_order(**overrides) -> PurchaseOrder:
    defaults = dict(
        po_id="po-001",
        request_id="req-001",
        vendor_id="vnd-001",
        tenant_id="ten-001",
        status=PurchaseOrderStatus.DRAFT,
        amount=500.0,
        currency="USD",
        issued_at=TS,
    )
    defaults.update(overrides)
    return PurchaseOrder(**defaults)


def _vendor_assessment(**overrides) -> VendorAssessment:
    defaults = dict(
        assessment_id="asmnt-001",
        vendor_id="vnd-001",
        risk_level=VendorRiskLevel.LOW,
        performance_score=0.85,
        fault_count=0,
        assessed_by="auditor-001",
        assessed_at=TS,
    )
    defaults.update(overrides)
    return VendorAssessment(**defaults)


def _vendor_commitment(**overrides) -> VendorCommitment:
    defaults = dict(
        commitment_id="cmt-001",
        vendor_id="vnd-001",
        contract_ref="ctr-001",
        description="SLA uptime 99.9%",
        target_value="99.9%",
        created_at=TS,
    )
    defaults.update(overrides)
    return VendorCommitment(**defaults)


def _procurement_decision(**overrides) -> ProcurementDecision:
    defaults = dict(
        decision_id="dec-001",
        request_id="req-001",
        status=ProcurementDecisionStatus.PENDING,
        decided_by="mgr-001",
        reason="Budget available",
        decided_at=TS,
    )
    defaults.update(overrides)
    return ProcurementDecision(**defaults)


def _renewal_window(**overrides) -> ProcurementRenewalWindow:
    defaults = dict(
        renewal_id="rnw-001",
        vendor_id="vnd-001",
        contract_ref="ctr-001",
        disposition=RenewalDisposition.PENDING,
        opens_at=TS,
        closes_at=TS2,
    )
    defaults.update(overrides)
    return ProcurementRenewalWindow(**defaults)


def _vendor_violation(**overrides) -> VendorViolation:
    defaults = dict(
        violation_id="viol-001",
        vendor_id="vnd-001",
        tenant_id="ten-001",
        operation="late_delivery",
        reason="Delivered 5 days late",
        detected_at=TS,
    )
    defaults.update(overrides)
    return VendorViolation(**defaults)


def _procurement_snapshot(**overrides) -> ProcurementSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_vendors=10,
        total_requests=20,
        total_purchase_orders=15,
        total_assessments=5,
        total_commitments=8,
        total_renewals=3,
        total_violations=2,
        total_procurement_value=50000.0,
        captured_at=TS,
    )
    defaults.update(overrides)
    return ProcurementSnapshot(**defaults)


def _closure_report(**overrides) -> ProcurementClosureReport:
    defaults = dict(
        report_id="rpt-001",
        tenant_id="ten-001",
        total_vendors=10,
        total_requests=20,
        total_purchase_orders=15,
        total_fulfilled=12,
        total_cancelled=3,
        total_procurement_value=50000.0,
        closed_at=TS,
    )
    defaults.update(overrides)
    return ProcurementClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestVendorStatus:
    def test_member_count(self):
        assert len(VendorStatus) == 5

    @pytest.mark.parametrize("member", list(VendorStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert VendorStatus.ACTIVE.value == "active"
        assert VendorStatus.SUSPENDED.value == "suspended"
        assert VendorStatus.BLOCKED.value == "blocked"
        assert VendorStatus.TERMINATED.value == "terminated"
        assert VendorStatus.UNDER_REVIEW.value == "under_review"

    def test_membership(self):
        assert VendorStatus("active") is VendorStatus.ACTIVE

    def test_iteration(self):
        members = list(VendorStatus)
        assert len(members) == 5

    def test_string_representation(self):
        assert "ACTIVE" in repr(VendorStatus.ACTIVE)


class TestProcurementRequestStatus:
    def test_member_count(self):
        assert len(ProcurementRequestStatus) == 6

    @pytest.mark.parametrize("member", list(ProcurementRequestStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert ProcurementRequestStatus.DRAFT.value == "draft"
        assert ProcurementRequestStatus.SUBMITTED.value == "submitted"
        assert ProcurementRequestStatus.APPROVED.value == "approved"
        assert ProcurementRequestStatus.DENIED.value == "denied"
        assert ProcurementRequestStatus.CANCELLED.value == "cancelled"
        assert ProcurementRequestStatus.FULFILLED.value == "fulfilled"

    def test_membership(self):
        assert ProcurementRequestStatus("draft") is ProcurementRequestStatus.DRAFT

    def test_iteration(self):
        members = list(ProcurementRequestStatus)
        assert len(members) == 6

    def test_string_representation(self):
        assert "DRAFT" in repr(ProcurementRequestStatus.DRAFT)


class TestPurchaseOrderStatus:
    def test_member_count(self):
        assert len(PurchaseOrderStatus) == 6

    @pytest.mark.parametrize("member", list(PurchaseOrderStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert PurchaseOrderStatus.DRAFT.value == "draft"
        assert PurchaseOrderStatus.ISSUED.value == "issued"
        assert PurchaseOrderStatus.ACKNOWLEDGED.value == "acknowledged"
        assert PurchaseOrderStatus.FULFILLED.value == "fulfilled"
        assert PurchaseOrderStatus.CANCELLED.value == "cancelled"
        assert PurchaseOrderStatus.DISPUTED.value == "disputed"

    def test_membership(self):
        assert PurchaseOrderStatus("draft") is PurchaseOrderStatus.DRAFT

    def test_iteration(self):
        members = list(PurchaseOrderStatus)
        assert len(members) == 6

    def test_string_representation(self):
        assert "DRAFT" in repr(PurchaseOrderStatus.DRAFT)


class TestVendorRiskLevel:
    def test_member_count(self):
        assert len(VendorRiskLevel) == 4

    @pytest.mark.parametrize("member", list(VendorRiskLevel))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert VendorRiskLevel.LOW.value == "low"
        assert VendorRiskLevel.MEDIUM.value == "medium"
        assert VendorRiskLevel.HIGH.value == "high"
        assert VendorRiskLevel.CRITICAL.value == "critical"

    def test_membership(self):
        assert VendorRiskLevel("low") is VendorRiskLevel.LOW

    def test_iteration(self):
        members = list(VendorRiskLevel)
        assert len(members) == 4

    def test_string_representation(self):
        assert "LOW" in repr(VendorRiskLevel.LOW)


class TestRenewalDisposition:
    def test_member_count(self):
        assert len(RenewalDisposition) == 5

    @pytest.mark.parametrize("member", list(RenewalDisposition))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert RenewalDisposition.PENDING.value == "pending"
        assert RenewalDisposition.APPROVED.value == "approved"
        assert RenewalDisposition.DENIED.value == "denied"
        assert RenewalDisposition.DEFERRED.value == "deferred"
        assert RenewalDisposition.AUTO_RENEWED.value == "auto_renewed"

    def test_membership(self):
        assert RenewalDisposition("pending") is RenewalDisposition.PENDING

    def test_iteration(self):
        members = list(RenewalDisposition)
        assert len(members) == 5

    def test_string_representation(self):
        assert "PENDING" in repr(RenewalDisposition.PENDING)


class TestProcurementDecisionStatus:
    def test_member_count(self):
        assert len(ProcurementDecisionStatus) == 4

    @pytest.mark.parametrize("member", list(ProcurementDecisionStatus))
    def test_each_member_has_string_value(self, member):
        assert isinstance(member.value, str)

    def test_values(self):
        assert ProcurementDecisionStatus.PENDING.value == "pending"
        assert ProcurementDecisionStatus.APPROVED.value == "approved"
        assert ProcurementDecisionStatus.DENIED.value == "denied"
        assert ProcurementDecisionStatus.ESCALATED.value == "escalated"

    def test_membership(self):
        assert ProcurementDecisionStatus("pending") is ProcurementDecisionStatus.PENDING

    def test_iteration(self):
        members = list(ProcurementDecisionStatus)
        assert len(members) == 4

    def test_string_representation(self):
        assert "PENDING" in repr(ProcurementDecisionStatus.PENDING)


# ===================================================================
# VendorRecord tests
# ===================================================================


class TestVendorRecord:
    def test_happy_path(self):
        rec = _vendor()
        assert rec.vendor_id == "vnd-001"
        assert rec.name == "Acme Corp"
        assert rec.tenant_id == "ten-001"
        assert rec.status is VendorStatus.ACTIVE
        assert rec.risk_level is VendorRiskLevel.LOW
        assert rec.category == "supplies"
        assert rec.registered_at == TS

    def test_frozen(self):
        rec = _vendor()
        with pytest.raises(AttributeError):
            rec.vendor_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(VendorRecord)

    def test_metadata_frozen(self):
        rec = _vendor(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _vendor(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _vendor(metadata={"items": [1, 2, 3]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["vendor_id", "name", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor(**{field: ""})

    @pytest.mark.parametrize("field", ["vendor_id", "name", "tenant_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _vendor(status="active")

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValueError):
            _vendor(risk_level="low")

    def test_empty_registered_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor(registered_at="")

    def test_invalid_registered_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor(registered_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _vendor()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_status_enum(self):
        rec = _vendor()
        d = rec.to_dict()
        assert isinstance(d["status"], VendorStatus)
        assert d["status"] is VendorStatus.ACTIVE

    def test_to_dict_preserves_risk_level_enum(self):
        rec = _vendor()
        d = rec.to_dict()
        assert isinstance(d["risk_level"], VendorRiskLevel)
        assert d["risk_level"] is VendorRiskLevel.LOW

    def test_to_dict_keys(self):
        rec = _vendor()
        d = rec.to_dict()
        expected_keys = {
            "vendor_id", "name", "tenant_id", "status",
            "risk_level", "category", "registered_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(VendorStatus))
    def test_all_statuses_accepted(self, status):
        rec = _vendor(status=status)
        assert rec.status is status

    @pytest.mark.parametrize("risk_level", list(VendorRiskLevel))
    def test_all_risk_levels_accepted(self, risk_level):
        rec = _vendor(risk_level=risk_level)
        assert rec.risk_level is risk_level

    def test_empty_category_accepted(self):
        rec = _vendor(category="")
        assert rec.category == ""


# ===================================================================
# ProcurementRequest tests
# ===================================================================


class TestProcurementRequest:
    def test_happy_path(self):
        rec = _procurement_request()
        assert rec.request_id == "req-001"
        assert rec.vendor_id == "vnd-001"
        assert rec.tenant_id == "ten-001"
        assert rec.status is ProcurementRequestStatus.DRAFT
        assert rec.description == "Office supplies"
        assert rec.estimated_amount == 500.0
        assert rec.currency == "USD"
        assert rec.requested_by == "user-001"
        assert rec.requested_at == TS
        assert rec.cancelled_by == ""

    def test_frozen(self):
        rec = _procurement_request()
        with pytest.raises(AttributeError):
            rec.request_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ProcurementRequest)

    def test_metadata_frozen(self):
        rec = _procurement_request(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _procurement_request(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _procurement_request(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["request_id", "vendor_id", "tenant_id", "currency", "requested_by"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _procurement_request(**{field: ""})

    @pytest.mark.parametrize("field", ["request_id", "vendor_id", "tenant_id", "currency", "requested_by"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _procurement_request(**{field: "   "})

    def test_negative_estimated_amount_rejected(self):
        with pytest.raises(ValueError):
            _procurement_request(estimated_amount=-1.0)

    def test_zero_estimated_amount_accepted(self):
        rec = _procurement_request(estimated_amount=0.0)
        assert rec.estimated_amount == 0.0

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _procurement_request(status="draft")

    def test_empty_requested_at_rejected(self):
        with pytest.raises(ValueError):
            _procurement_request(requested_at="")

    def test_invalid_requested_at_rejected(self):
        with pytest.raises(ValueError):
            _procurement_request(requested_at="not-a-date")

    def test_cancelled_requires_cancelled_by(self):
        with pytest.raises(ValueError, match="^cancelled requests must declare cancelled_by$") as exc_info:
            _procurement_request(status=ProcurementRequestStatus.CANCELLED, cancelled_by="")
        message = str(exc_info.value)
        assert message == "cancelled requests must declare cancelled_by"
        assert "req-001" not in message

    def test_system_cancelled_by_rejected(self):
        with pytest.raises(ValueError, match="^cancelled_by must exclude system$") as exc_info:
            _procurement_request(status=ProcurementRequestStatus.CANCELLED, cancelled_by="system")
        message = str(exc_info.value)
        assert message == "cancelled_by must exclude system"
        assert "system" in message

    def test_to_dict_returns_dict(self):
        rec = _procurement_request()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_status_enum(self):
        rec = _procurement_request()
        d = rec.to_dict()
        assert isinstance(d["status"], ProcurementRequestStatus)
        assert d["status"] is ProcurementRequestStatus.DRAFT

    def test_to_dict_keys(self):
        rec = _procurement_request()
        d = rec.to_dict()
        expected_keys = {
            "request_id", "vendor_id", "tenant_id", "status",
            "description", "estimated_amount", "currency",
            "requested_by", "requested_at", "cancelled_by", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(ProcurementRequestStatus))
    def test_all_statuses_accepted(self, status):
        overrides = {"status": status}
        if status is ProcurementRequestStatus.CANCELLED:
            overrides["cancelled_by"] = "ops-001"
        rec = _procurement_request(**overrides)
        assert rec.status is status

    def test_empty_description_accepted(self):
        rec = _procurement_request(description="")
        assert rec.description == ""


# ===================================================================
# PurchaseOrder tests
# ===================================================================


class TestPurchaseOrder:
    def test_happy_path(self):
        rec = _purchase_order()
        assert rec.po_id == "po-001"
        assert rec.request_id == "req-001"
        assert rec.vendor_id == "vnd-001"
        assert rec.tenant_id == "ten-001"
        assert rec.status is PurchaseOrderStatus.DRAFT
        assert rec.amount == 500.0
        assert rec.currency == "USD"
        assert rec.issued_at == TS

    def test_frozen(self):
        rec = _purchase_order()
        with pytest.raises(AttributeError):
            rec.po_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(PurchaseOrder)

    def test_metadata_frozen(self):
        rec = _purchase_order(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _purchase_order(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _purchase_order(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["po_id", "request_id", "vendor_id", "tenant_id", "currency"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _purchase_order(**{field: ""})

    @pytest.mark.parametrize("field", ["po_id", "request_id", "vendor_id", "tenant_id", "currency"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _purchase_order(**{field: "   "})

    def test_negative_amount_rejected(self):
        with pytest.raises(ValueError):
            _purchase_order(amount=-1.0)

    def test_zero_amount_accepted(self):
        rec = _purchase_order(amount=0.0)
        assert rec.amount == 0.0

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _purchase_order(status="draft")

    def test_empty_issued_at_rejected(self):
        with pytest.raises(ValueError):
            _purchase_order(issued_at="")

    def test_invalid_issued_at_rejected(self):
        with pytest.raises(ValueError):
            _purchase_order(issued_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _purchase_order()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_status_enum(self):
        rec = _purchase_order()
        d = rec.to_dict()
        assert isinstance(d["status"], PurchaseOrderStatus)
        assert d["status"] is PurchaseOrderStatus.DRAFT

    def test_to_dict_keys(self):
        rec = _purchase_order()
        d = rec.to_dict()
        expected_keys = {
            "po_id", "request_id", "vendor_id", "tenant_id",
            "status", "amount", "currency", "issued_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(PurchaseOrderStatus))
    def test_all_statuses_accepted(self, status):
        rec = _purchase_order(status=status)
        assert rec.status is status


# ===================================================================
# VendorAssessment tests
# ===================================================================


class TestVendorAssessment:
    def test_happy_path(self):
        rec = _vendor_assessment()
        assert rec.assessment_id == "asmnt-001"
        assert rec.vendor_id == "vnd-001"
        assert rec.risk_level is VendorRiskLevel.LOW
        assert rec.performance_score == 0.85
        assert rec.fault_count == 0
        assert rec.assessed_by == "auditor-001"
        assert rec.assessed_at == TS

    def test_frozen(self):
        rec = _vendor_assessment()
        with pytest.raises(AttributeError):
            rec.assessment_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(VendorAssessment)

    def test_metadata_frozen(self):
        rec = _vendor_assessment(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _vendor_assessment(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _vendor_assessment(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["assessment_id", "vendor_id", "assessed_by"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor_assessment(**{field: ""})

    @pytest.mark.parametrize("field", ["assessment_id", "vendor_id", "assessed_by"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor_assessment(**{field: "   "})

    def test_invalid_risk_level_rejected(self):
        with pytest.raises(ValueError):
            _vendor_assessment(risk_level="low")

    def test_performance_score_zero_accepted(self):
        rec = _vendor_assessment(performance_score=0.0)
        assert rec.performance_score == 0.0

    def test_performance_score_one_accepted(self):
        rec = _vendor_assessment(performance_score=1.0)
        assert rec.performance_score == 1.0

    def test_performance_score_mid_accepted(self):
        rec = _vendor_assessment(performance_score=0.5)
        assert rec.performance_score == 0.5

    def test_performance_score_negative_rejected(self):
        with pytest.raises(ValueError):
            _vendor_assessment(performance_score=-0.1)

    def test_performance_score_above_one_rejected(self):
        with pytest.raises(ValueError):
            _vendor_assessment(performance_score=1.01)

    def test_negative_fault_count_rejected(self):
        with pytest.raises(ValueError):
            _vendor_assessment(fault_count=-1)

    def test_zero_fault_count_accepted(self):
        rec = _vendor_assessment(fault_count=0)
        assert rec.fault_count == 0

    def test_positive_fault_count_accepted(self):
        rec = _vendor_assessment(fault_count=5)
        assert rec.fault_count == 5

    def test_empty_assessed_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor_assessment(assessed_at="")

    def test_invalid_assessed_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor_assessment(assessed_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _vendor_assessment()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_risk_level_enum(self):
        rec = _vendor_assessment()
        d = rec.to_dict()
        assert isinstance(d["risk_level"], VendorRiskLevel)
        assert d["risk_level"] is VendorRiskLevel.LOW

    def test_to_dict_keys(self):
        rec = _vendor_assessment()
        d = rec.to_dict()
        expected_keys = {
            "assessment_id", "vendor_id", "risk_level",
            "performance_score", "fault_count", "assessed_by",
            "assessed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("risk_level", list(VendorRiskLevel))
    def test_all_risk_levels_accepted(self, risk_level):
        rec = _vendor_assessment(risk_level=risk_level)
        assert rec.risk_level is risk_level


# ===================================================================
# VendorCommitment tests
# ===================================================================


class TestVendorCommitment:
    def test_happy_path(self):
        rec = _vendor_commitment()
        assert rec.commitment_id == "cmt-001"
        assert rec.vendor_id == "vnd-001"
        assert rec.contract_ref == "ctr-001"
        assert rec.description == "SLA uptime 99.9%"
        assert rec.target_value == "99.9%"
        assert rec.created_at == TS

    def test_frozen(self):
        rec = _vendor_commitment()
        with pytest.raises(AttributeError):
            rec.commitment_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(VendorCommitment)

    def test_metadata_frozen(self):
        rec = _vendor_commitment(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _vendor_commitment(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _vendor_commitment(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["commitment_id", "vendor_id", "contract_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor_commitment(**{field: ""})

    @pytest.mark.parametrize("field", ["commitment_id", "vendor_id", "contract_ref"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor_commitment(**{field: "   "})

    def test_empty_description_accepted(self):
        rec = _vendor_commitment(description="")
        assert rec.description == ""

    def test_empty_target_value_accepted(self):
        rec = _vendor_commitment(target_value="")
        assert rec.target_value == ""

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor_commitment(created_at="")

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor_commitment(created_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _vendor_commitment()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _vendor_commitment()
        d = rec.to_dict()
        expected_keys = {
            "commitment_id", "vendor_id", "contract_ref",
            "description", "target_value", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ProcurementDecision tests
# ===================================================================


class TestProcurementDecision:
    def test_happy_path(self):
        rec = _procurement_decision()
        assert rec.decision_id == "dec-001"
        assert rec.request_id == "req-001"
        assert rec.status is ProcurementDecisionStatus.PENDING
        assert rec.decided_by == "mgr-001"
        assert rec.reason == "Budget available"
        assert rec.decided_at == TS

    def test_frozen(self):
        rec = _procurement_decision()
        with pytest.raises(AttributeError):
            rec.decision_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ProcurementDecision)

    def test_metadata_frozen(self):
        rec = _procurement_decision(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _procurement_decision(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _procurement_decision(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["decision_id", "request_id", "decided_by"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _procurement_decision(**{field: ""})

    @pytest.mark.parametrize("field", ["decision_id", "request_id", "decided_by"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _procurement_decision(**{field: "   "})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            _procurement_decision(status="pending")

    def test_empty_reason_accepted(self):
        rec = _procurement_decision(reason="")
        assert rec.reason == ""

    def test_empty_decided_at_rejected(self):
        with pytest.raises(ValueError):
            _procurement_decision(decided_at="")

    def test_invalid_decided_at_rejected(self):
        with pytest.raises(ValueError):
            _procurement_decision(decided_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _procurement_decision()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_status_enum(self):
        rec = _procurement_decision()
        d = rec.to_dict()
        assert isinstance(d["status"], ProcurementDecisionStatus)
        assert d["status"] is ProcurementDecisionStatus.PENDING

    def test_to_dict_keys(self):
        rec = _procurement_decision()
        d = rec.to_dict()
        expected_keys = {
            "decision_id", "request_id", "status",
            "decided_by", "reason", "decided_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("status", list(ProcurementDecisionStatus))
    def test_all_statuses_accepted(self, status):
        rec = _procurement_decision(status=status)
        assert rec.status is status


# ===================================================================
# ProcurementRenewalWindow tests
# ===================================================================


class TestProcurementRenewalWindow:
    def test_happy_path(self):
        rec = _renewal_window()
        assert rec.renewal_id == "rnw-001"
        assert rec.vendor_id == "vnd-001"
        assert rec.contract_ref == "ctr-001"
        assert rec.disposition is RenewalDisposition.PENDING
        assert rec.opens_at == TS
        assert rec.closes_at == TS2

    def test_frozen(self):
        rec = _renewal_window()
        with pytest.raises(AttributeError):
            rec.renewal_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ProcurementRenewalWindow)

    def test_metadata_frozen(self):
        rec = _renewal_window(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _renewal_window(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _renewal_window(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["renewal_id", "vendor_id", "contract_ref"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _renewal_window(**{field: ""})

    @pytest.mark.parametrize("field", ["renewal_id", "vendor_id", "contract_ref"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _renewal_window(**{field: "   "})

    def test_invalid_disposition_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(disposition="pending")

    def test_empty_opens_at_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(opens_at="")

    def test_invalid_opens_at_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(opens_at="not-a-date")

    def test_empty_closes_at_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(closes_at="")

    def test_invalid_closes_at_rejected(self):
        with pytest.raises(ValueError):
            _renewal_window(closes_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _renewal_window()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_preserves_disposition_enum(self):
        rec = _renewal_window()
        d = rec.to_dict()
        assert isinstance(d["disposition"], RenewalDisposition)
        assert d["disposition"] is RenewalDisposition.PENDING

    def test_to_dict_keys(self):
        rec = _renewal_window()
        d = rec.to_dict()
        expected_keys = {
            "renewal_id", "vendor_id", "contract_ref",
            "disposition", "opens_at", "closes_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    @pytest.mark.parametrize("disposition", list(RenewalDisposition))
    def test_all_dispositions_accepted(self, disposition):
        rec = _renewal_window(disposition=disposition)
        assert rec.disposition is disposition


# ===================================================================
# VendorViolation tests
# ===================================================================


class TestVendorViolation:
    def test_happy_path(self):
        rec = _vendor_violation()
        assert rec.violation_id == "viol-001"
        assert rec.vendor_id == "vnd-001"
        assert rec.tenant_id == "ten-001"
        assert rec.operation == "late_delivery"
        assert rec.reason == "Delivered 5 days late"
        assert rec.detected_at == TS

    def test_frozen(self):
        rec = _vendor_violation()
        with pytest.raises(AttributeError):
            rec.violation_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(VendorViolation)

    def test_metadata_frozen(self):
        rec = _vendor_violation(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _vendor_violation(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _vendor_violation(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["violation_id", "vendor_id", "tenant_id", "operation"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor_violation(**{field: ""})

    @pytest.mark.parametrize("field", ["violation_id", "vendor_id", "tenant_id", "operation"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _vendor_violation(**{field: "   "})

    def test_empty_reason_accepted(self):
        rec = _vendor_violation(reason="")
        assert rec.reason == ""

    def test_empty_detected_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor_violation(detected_at="")

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError):
            _vendor_violation(detected_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _vendor_violation()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _vendor_violation()
        d = rec.to_dict()
        expected_keys = {
            "violation_id", "vendor_id", "tenant_id",
            "operation", "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ProcurementSnapshot tests
# ===================================================================


class TestProcurementSnapshot:
    def test_happy_path(self):
        rec = _procurement_snapshot()
        assert rec.snapshot_id == "snap-001"
        assert rec.total_vendors == 10
        assert rec.total_requests == 20
        assert rec.total_purchase_orders == 15
        assert rec.total_assessments == 5
        assert rec.total_commitments == 8
        assert rec.total_renewals == 3
        assert rec.total_violations == 2
        assert rec.total_procurement_value == 50000.0
        assert rec.captured_at == TS

    def test_frozen(self):
        rec = _procurement_snapshot()
        with pytest.raises(AttributeError):
            rec.snapshot_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ProcurementSnapshot)

    def test_metadata_frozen(self):
        rec = _procurement_snapshot(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _procurement_snapshot(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _procurement_snapshot(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _procurement_snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _procurement_snapshot(snapshot_id="   ")

    @pytest.mark.parametrize("field", [
        "total_vendors", "total_requests", "total_purchase_orders",
        "total_assessments", "total_commitments", "total_renewals",
        "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _procurement_snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_vendors", "total_requests", "total_purchase_orders",
        "total_assessments", "total_commitments", "total_renewals",
        "total_violations",
    ])
    def test_zero_int_accepted(self, field):
        rec = _procurement_snapshot(**{field: 0})
        assert getattr(rec, field) == 0

    def test_negative_total_procurement_value_rejected(self):
        with pytest.raises(ValueError):
            _procurement_snapshot(total_procurement_value=-1.0)

    def test_zero_total_procurement_value_accepted(self):
        rec = _procurement_snapshot(total_procurement_value=0.0)
        assert rec.total_procurement_value == 0.0

    def test_empty_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _procurement_snapshot(captured_at="")

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError):
            _procurement_snapshot(captured_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _procurement_snapshot()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _procurement_snapshot()
        d = rec.to_dict()
        expected_keys = {
            "snapshot_id", "total_vendors", "total_requests",
            "total_purchase_orders", "total_assessments",
            "total_commitments", "total_renewals", "total_violations",
            "total_procurement_value", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# ProcurementClosureReport tests
# ===================================================================


class TestProcurementClosureReport:
    def test_happy_path(self):
        rec = _closure_report()
        assert rec.report_id == "rpt-001"
        assert rec.tenant_id == "ten-001"
        assert rec.total_vendors == 10
        assert rec.total_requests == 20
        assert rec.total_purchase_orders == 15
        assert rec.total_fulfilled == 12
        assert rec.total_cancelled == 3
        assert rec.total_procurement_value == 50000.0
        assert rec.closed_at == TS

    def test_frozen(self):
        rec = _closure_report()
        with pytest.raises(AttributeError):
            rec.report_id = "changed"

    def test_slots(self):
        assert "__slots__" in dir(ProcurementClosureReport)

    def test_metadata_frozen(self):
        rec = _closure_report(metadata={"key": "val"})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["key"] == "val"

    def test_nested_metadata_frozen(self):
        rec = _closure_report(metadata={"inner": {"a": 1}})
        assert isinstance(rec.metadata["inner"], MappingProxyType)

    def test_metadata_list_becomes_tuple(self):
        rec = _closure_report(metadata={"items": [1, 2]})
        assert isinstance(rec.metadata["items"], tuple)

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: ""})

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_whitespace_text_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: "   "})

    @pytest.mark.parametrize("field", [
        "total_vendors", "total_requests", "total_purchase_orders",
        "total_fulfilled", "total_cancelled",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure_report(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_vendors", "total_requests", "total_purchase_orders",
        "total_fulfilled", "total_cancelled",
    ])
    def test_zero_int_accepted(self, field):
        rec = _closure_report(**{field: 0})
        assert getattr(rec, field) == 0

    def test_negative_total_procurement_value_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(total_procurement_value=-1.0)

    def test_zero_total_procurement_value_accepted(self):
        rec = _closure_report(total_procurement_value=0.0)
        assert rec.total_procurement_value == 0.0

    def test_empty_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="")

    def test_invalid_closed_at_rejected(self):
        with pytest.raises(ValueError):
            _closure_report(closed_at="not-a-date")

    def test_to_dict_returns_dict(self):
        rec = _closure_report()
        d = rec.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_keys(self):
        rec = _closure_report()
        d = rec.to_dict()
        expected_keys = {
            "report_id", "tenant_id", "total_vendors", "total_requests",
            "total_purchase_orders", "total_fulfilled", "total_cancelled",
            "total_procurement_value", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected_keys
