"""Purpose: vendor / procurement / third-party runtime engine.
Governance scope: registering vendors, creating procurement requests,
    approving/denying requests, issuing purchase orders, tracking vendor
    risk and renewals, detecting procurement violations, producing
    immutable snapshots.
Dependencies: procurement_runtime contracts, event_spine, core invariants.
Invariants:
  - Unapproved requests cannot produce POs.
  - Blocked/terminated vendors cannot receive POs.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from ..contracts.procurement_runtime import (
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-proc", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


def _require_human_actor(field_name: str, value: str, missing_message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(missing_message)
    normalized = value.strip()
    if normalized == "system":
        raise RuntimeCoreInvariantError(f"{field_name} must exclude system")
    return normalized


_VENDOR_BLOCKED = frozenset({VendorStatus.BLOCKED, VendorStatus.TERMINATED})
_REQUEST_TERMINAL = frozenset({
    ProcurementRequestStatus.DENIED,
    ProcurementRequestStatus.CANCELLED,
    ProcurementRequestStatus.FULFILLED,
})
_PO_TERMINAL = frozenset({
    PurchaseOrderStatus.FULFILLED,
    PurchaseOrderStatus.CANCELLED,
})
_RENEWAL_TERMINAL = frozenset({
    RenewalDisposition.APPROVED,
    RenewalDisposition.DENIED,
    RenewalDisposition.AUTO_RENEWED,
})


class ProcurementRuntimeEngine:
    """Vendor, procurement, and third-party governance engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._vendors: dict[str, VendorRecord] = {}
        self._requests: dict[str, ProcurementRequest] = {}
        self._pos: dict[str, PurchaseOrder] = {}
        self._assessments: dict[str, VendorAssessment] = {}
        self._commitments: dict[str, VendorCommitment] = {}
        self._decisions: dict[str, ProcurementDecision] = {}
        self._renewals: dict[str, ProcurementRenewalWindow] = {}
        self._violations: dict[str, VendorViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def vendor_count(self) -> int:
        return len(self._vendors)

    @property
    def request_count(self) -> int:
        return len(self._requests)

    @property
    def po_count(self) -> int:
        return len(self._pos)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def commitment_count(self) -> int:
        return len(self._commitments)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def renewal_count(self) -> int:
        return len(self._renewals)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Vendors
    # ------------------------------------------------------------------

    def register_vendor(
        self,
        vendor_id: str,
        name: str,
        tenant_id: str,
        *,
        category: str = "",
    ) -> VendorRecord:
        """Register a vendor."""
        if vendor_id in self._vendors:
            raise RuntimeCoreInvariantError("Duplicate vendor_id")
        now = _now_iso()
        v = VendorRecord(
            vendor_id=vendor_id,
            name=name,
            tenant_id=tenant_id,
            status=VendorStatus.ACTIVE,
            risk_level=VendorRiskLevel.LOW,
            category=category,
            registered_at=now,
        )
        self._vendors[vendor_id] = v
        _emit(self._events, "vendor_registered", {
            "vendor_id": vendor_id, "name": name,
        }, vendor_id)
        return v

    def get_vendor(self, vendor_id: str) -> VendorRecord:
        """Get a vendor by ID."""
        v = self._vendors.get(vendor_id)
        if v is None:
            raise RuntimeCoreInvariantError("Unknown vendor_id")
        return v

    def suspend_vendor(self, vendor_id: str) -> VendorRecord:
        """Suspend a vendor."""
        old = self.get_vendor(vendor_id)
        if old.status != VendorStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Can only suspend ACTIVE vendors")
        updated = VendorRecord(
            vendor_id=old.vendor_id, name=old.name, tenant_id=old.tenant_id,
            status=VendorStatus.SUSPENDED, risk_level=old.risk_level,
            category=old.category, registered_at=old.registered_at,
            metadata=old.metadata,
        )
        self._vendors[vendor_id] = updated
        _emit(self._events, "vendor_suspended", {"vendor_id": vendor_id}, vendor_id)
        return updated

    def block_vendor(self, vendor_id: str) -> VendorRecord:
        """Block a vendor."""
        old = self.get_vendor(vendor_id)
        if old.status in _VENDOR_BLOCKED:
            raise RuntimeCoreInvariantError("Vendor already in current status")
        updated = VendorRecord(
            vendor_id=old.vendor_id, name=old.name, tenant_id=old.tenant_id,
            status=VendorStatus.BLOCKED, risk_level=old.risk_level,
            category=old.category, registered_at=old.registered_at,
            metadata=old.metadata,
        )
        self._vendors[vendor_id] = updated
        _emit(self._events, "vendor_blocked", {"vendor_id": vendor_id}, vendor_id)
        return updated

    def terminate_vendor(self, vendor_id: str) -> VendorRecord:
        """Terminate a vendor."""
        old = self.get_vendor(vendor_id)
        if old.status == VendorStatus.TERMINATED:
            raise RuntimeCoreInvariantError("Vendor already terminated")
        updated = VendorRecord(
            vendor_id=old.vendor_id, name=old.name, tenant_id=old.tenant_id,
            status=VendorStatus.TERMINATED, risk_level=old.risk_level,
            category=old.category, registered_at=old.registered_at,
            metadata=old.metadata,
        )
        self._vendors[vendor_id] = updated
        _emit(self._events, "vendor_terminated", {"vendor_id": vendor_id}, vendor_id)
        return updated

    def review_vendor(self, vendor_id: str) -> VendorRecord:
        """Place a vendor under review."""
        old = self.get_vendor(vendor_id)
        if old.status in _VENDOR_BLOCKED:
            raise RuntimeCoreInvariantError("Cannot review vendor in current status")
        updated = VendorRecord(
            vendor_id=old.vendor_id, name=old.name, tenant_id=old.tenant_id,
            status=VendorStatus.UNDER_REVIEW, risk_level=old.risk_level,
            category=old.category, registered_at=old.registered_at,
            metadata=old.metadata,
        )
        self._vendors[vendor_id] = updated
        _emit(self._events, "vendor_under_review", {"vendor_id": vendor_id}, vendor_id)
        return updated

    def vendors_for_tenant(self, tenant_id: str) -> tuple[VendorRecord, ...]:
        """Return all vendors for a tenant."""
        return tuple(v for v in self._vendors.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Procurement requests
    # ------------------------------------------------------------------

    def create_request(
        self,
        request_id: str,
        vendor_id: str,
        tenant_id: str,
        estimated_amount: float,
        *,
        currency: str = "USD",
        description: str = "",
        requested_by: str = "system",
    ) -> ProcurementRequest:
        """Create a procurement request."""
        if request_id in self._requests:
            raise RuntimeCoreInvariantError("Duplicate request_id")
        if vendor_id not in self._vendors:
            raise RuntimeCoreInvariantError("Unknown vendor_id")
        vendor = self._vendors[vendor_id]
        if vendor.status in _VENDOR_BLOCKED:
            raise RuntimeCoreInvariantError("Cannot create request for vendor in current status")
        now = _now_iso()
        req = ProcurementRequest(
            request_id=request_id,
            vendor_id=vendor_id,
            tenant_id=tenant_id,
            status=ProcurementRequestStatus.DRAFT,
            description=description,
            estimated_amount=estimated_amount,
            currency=currency,
            requested_by=requested_by,
            requested_at=now,
        )
        self._requests[request_id] = req
        _emit(self._events, "request_created", {
            "request_id": request_id, "vendor_id": vendor_id,
            "estimated_amount": estimated_amount,
        }, request_id)
        return req

    def get_request(self, request_id: str) -> ProcurementRequest:
        """Get a request by ID."""
        r = self._requests.get(request_id)
        if r is None:
            raise RuntimeCoreInvariantError("Unknown request_id")
        return r

    def submit_request(self, request_id: str) -> ProcurementRequest:
        """Submit a draft request for approval."""
        old = self.get_request(request_id)
        if old.status != ProcurementRequestStatus.DRAFT:
            raise RuntimeCoreInvariantError("Can only submit DRAFT requests")
        updated = ProcurementRequest(
            request_id=old.request_id, vendor_id=old.vendor_id,
            tenant_id=old.tenant_id, status=ProcurementRequestStatus.SUBMITTED,
            description=old.description, estimated_amount=old.estimated_amount,
            currency=old.currency, requested_by=old.requested_by,
            requested_at=old.requested_at, cancelled_by=old.cancelled_by,
            metadata=old.metadata,
        )
        self._requests[request_id] = updated
        _emit(self._events, "request_submitted", {"request_id": request_id}, request_id)
        return updated

    def approve_request(
        self, request_id: str, *, decided_by: str = "approver",
    ) -> ProcurementRequest:
        """Approve a submitted request."""
        old = self.get_request(request_id)
        if old.status != ProcurementRequestStatus.SUBMITTED:
            raise RuntimeCoreInvariantError("Can only approve SUBMITTED requests")
        now = _now_iso()
        updated = ProcurementRequest(
            request_id=old.request_id, vendor_id=old.vendor_id,
            tenant_id=old.tenant_id, status=ProcurementRequestStatus.APPROVED,
            description=old.description, estimated_amount=old.estimated_amount,
            currency=old.currency, requested_by=old.requested_by,
            requested_at=old.requested_at, cancelled_by=old.cancelled_by,
            metadata=old.metadata,
        )
        self._requests[request_id] = updated

        # Record decision
        did = stable_identifier("dec-proc", {"req": request_id, "op": "approve"})
        if did not in self._decisions:
            d = ProcurementDecision(
                decision_id=did, request_id=request_id,
                status=ProcurementDecisionStatus.APPROVED,
                decided_by=decided_by, reason="Approved",
                decided_at=now,
            )
            self._decisions[did] = d

        _emit(self._events, "request_approved", {
            "request_id": request_id, "decided_by": decided_by,
        }, request_id)
        return updated

    def deny_request(
        self, request_id: str, *, decided_by: str = "approver", reason: str = "",
    ) -> ProcurementRequest:
        """Deny a submitted request."""
        old = self.get_request(request_id)
        if old.status != ProcurementRequestStatus.SUBMITTED:
            raise RuntimeCoreInvariantError("Can only deny SUBMITTED requests")
        now = _now_iso()
        updated = ProcurementRequest(
            request_id=old.request_id, vendor_id=old.vendor_id,
            tenant_id=old.tenant_id, status=ProcurementRequestStatus.DENIED,
            description=old.description, estimated_amount=old.estimated_amount,
            currency=old.currency, requested_by=old.requested_by,
            requested_at=old.requested_at, cancelled_by=old.cancelled_by,
            metadata=old.metadata,
        )
        self._requests[request_id] = updated

        did = stable_identifier("dec-proc", {"req": request_id, "op": "deny"})
        if did not in self._decisions:
            d = ProcurementDecision(
                decision_id=did, request_id=request_id,
                status=ProcurementDecisionStatus.DENIED,
                decided_by=decided_by, reason=reason,
                decided_at=now,
            )
            self._decisions[did] = d

        _emit(self._events, "request_denied", {
            "request_id": request_id, "decided_by": decided_by,
        }, request_id)
        return updated

    def cancel_request(self, request_id: str, *, cancelled_by: str = "") -> ProcurementRequest:
        """Cancel a request."""
        old = self.get_request(request_id)
        if old.status in _REQUEST_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot cancel request in current status")
        normalized_cancelled_by = _require_human_actor(
            "cancelled_by",
            cancelled_by,
            "cancelled_by required for cancellation",
        )
        updated = ProcurementRequest(
            request_id=old.request_id, vendor_id=old.vendor_id,
            tenant_id=old.tenant_id, status=ProcurementRequestStatus.CANCELLED,
            description=old.description, estimated_amount=old.estimated_amount,
            currency=old.currency, requested_by=old.requested_by,
            requested_at=old.requested_at, cancelled_by=normalized_cancelled_by,
            metadata=old.metadata,
        )
        self._requests[request_id] = updated
        _emit(self._events, "request_cancelled", {
            "request_id": request_id,
            "cancelled_by": normalized_cancelled_by,
        }, request_id)
        return updated

    def requests_for_vendor(self, vendor_id: str) -> tuple[ProcurementRequest, ...]:
        """Return all requests for a vendor."""
        return tuple(r for r in self._requests.values() if r.vendor_id == vendor_id)

    # ------------------------------------------------------------------
    # Purchase orders
    # ------------------------------------------------------------------

    def issue_po(
        self,
        po_id: str,
        request_id: str,
    ) -> PurchaseOrder:
        """Issue a purchase order from an approved request."""
        if po_id in self._pos:
            raise RuntimeCoreInvariantError("Duplicate po_id")
        req = self.get_request(request_id)
        if req.status != ProcurementRequestStatus.APPROVED:
            raise RuntimeCoreInvariantError("Can only issue PO from APPROVED requests")
        vendor = self._vendors.get(req.vendor_id)
        if vendor and vendor.status in _VENDOR_BLOCKED:
            raise RuntimeCoreInvariantError("Cannot issue PO to vendor in current status")
        now = _now_iso()
        po = PurchaseOrder(
            po_id=po_id, request_id=request_id,
            vendor_id=req.vendor_id, tenant_id=req.tenant_id,
            status=PurchaseOrderStatus.ISSUED,
            amount=req.estimated_amount, currency=req.currency,
            issued_at=now,
        )
        self._pos[po_id] = po

        # Mark request as fulfilled
        fulfilled = ProcurementRequest(
            request_id=req.request_id, vendor_id=req.vendor_id,
            tenant_id=req.tenant_id, status=ProcurementRequestStatus.FULFILLED,
            description=req.description, estimated_amount=req.estimated_amount,
            currency=req.currency, requested_by=req.requested_by,
            requested_at=req.requested_at, cancelled_by=req.cancelled_by,
            metadata=req.metadata,
        )
        self._requests[request_id] = fulfilled

        _emit(self._events, "po_issued", {
            "po_id": po_id, "request_id": request_id,
            "vendor_id": req.vendor_id, "amount": req.estimated_amount,
        }, po_id)
        return po

    def get_po(self, po_id: str) -> PurchaseOrder:
        """Get a purchase order by ID."""
        p = self._pos.get(po_id)
        if p is None:
            raise RuntimeCoreInvariantError("Unknown po_id")
        return p

    def acknowledge_po(self, po_id: str) -> PurchaseOrder:
        """Mark a PO as acknowledged by the vendor."""
        old = self.get_po(po_id)
        if old.status != PurchaseOrderStatus.ISSUED:
            raise RuntimeCoreInvariantError("Can only acknowledge ISSUED POs")
        updated = PurchaseOrder(
            po_id=old.po_id, request_id=old.request_id,
            vendor_id=old.vendor_id, tenant_id=old.tenant_id,
            status=PurchaseOrderStatus.ACKNOWLEDGED,
            amount=old.amount, currency=old.currency,
            issued_at=old.issued_at, metadata=old.metadata,
        )
        self._pos[po_id] = updated
        _emit(self._events, "po_acknowledged", {"po_id": po_id}, po_id)
        return updated

    def fulfill_po(self, po_id: str) -> PurchaseOrder:
        """Mark a PO as fulfilled."""
        old = self.get_po(po_id)
        if old.status in _PO_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot fulfill PO in current status")
        updated = PurchaseOrder(
            po_id=old.po_id, request_id=old.request_id,
            vendor_id=old.vendor_id, tenant_id=old.tenant_id,
            status=PurchaseOrderStatus.FULFILLED,
            amount=old.amount, currency=old.currency,
            issued_at=old.issued_at, metadata=old.metadata,
        )
        self._pos[po_id] = updated
        _emit(self._events, "po_fulfilled", {"po_id": po_id}, po_id)
        return updated

    def cancel_po(self, po_id: str) -> PurchaseOrder:
        """Cancel a purchase order."""
        old = self.get_po(po_id)
        if old.status in _PO_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot cancel PO in current status")
        updated = PurchaseOrder(
            po_id=old.po_id, request_id=old.request_id,
            vendor_id=old.vendor_id, tenant_id=old.tenant_id,
            status=PurchaseOrderStatus.CANCELLED,
            amount=old.amount, currency=old.currency,
            issued_at=old.issued_at, metadata=old.metadata,
        )
        self._pos[po_id] = updated
        _emit(self._events, "po_cancelled", {"po_id": po_id}, po_id)
        return updated

    def dispute_po(self, po_id: str) -> PurchaseOrder:
        """Mark a PO as disputed."""
        old = self.get_po(po_id)
        if old.status in _PO_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot dispute PO in current status")
        updated = PurchaseOrder(
            po_id=old.po_id, request_id=old.request_id,
            vendor_id=old.vendor_id, tenant_id=old.tenant_id,
            status=PurchaseOrderStatus.DISPUTED,
            amount=old.amount, currency=old.currency,
            issued_at=old.issued_at, metadata=old.metadata,
        )
        self._pos[po_id] = updated
        _emit(self._events, "po_disputed", {"po_id": po_id}, po_id)
        return updated

    def pos_for_vendor(self, vendor_id: str) -> tuple[PurchaseOrder, ...]:
        """Return all POs for a vendor."""
        return tuple(p for p in self._pos.values() if p.vendor_id == vendor_id)

    # ------------------------------------------------------------------
    # Vendor assessments
    # ------------------------------------------------------------------

    def assess_vendor(
        self,
        assessment_id: str,
        vendor_id: str,
        performance_score: float,
        fault_count: int,
        *,
        assessed_by: str = "system",
    ) -> VendorAssessment:
        """Assess a vendor's risk and performance."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("Duplicate assessment_id")
        if vendor_id not in self._vendors:
            raise RuntimeCoreInvariantError("Unknown vendor_id")

        # Compute risk level from performance and faults
        if fault_count >= 5 or performance_score < 0.3:
            risk = VendorRiskLevel.CRITICAL
        elif fault_count >= 3 or performance_score < 0.5:
            risk = VendorRiskLevel.HIGH
        elif fault_count >= 1 or performance_score < 0.8:
            risk = VendorRiskLevel.MEDIUM
        else:
            risk = VendorRiskLevel.LOW

        now = _now_iso()
        a = VendorAssessment(
            assessment_id=assessment_id, vendor_id=vendor_id,
            risk_level=risk, performance_score=performance_score,
            fault_count=fault_count, assessed_by=assessed_by,
            assessed_at=now,
        )
        self._assessments[assessment_id] = a

        # Update vendor risk level
        old_vendor = self._vendors[vendor_id]
        if old_vendor.risk_level != risk:
            updated = VendorRecord(
                vendor_id=old_vendor.vendor_id, name=old_vendor.name,
                tenant_id=old_vendor.tenant_id, status=old_vendor.status,
                risk_level=risk, category=old_vendor.category,
                registered_at=old_vendor.registered_at, metadata=old_vendor.metadata,
            )
            self._vendors[vendor_id] = updated

        _emit(self._events, "vendor_assessed", {
            "assessment_id": assessment_id, "vendor_id": vendor_id,
            "risk_level": risk.value, "performance_score": performance_score,
        }, vendor_id)
        return a

    def assessments_for_vendor(
        self, vendor_id: str,
    ) -> tuple[VendorAssessment, ...]:
        """Return all assessments for a vendor."""
        return tuple(
            a for a in self._assessments.values() if a.vendor_id == vendor_id
        )

    # ------------------------------------------------------------------
    # Vendor commitments
    # ------------------------------------------------------------------

    def register_commitment(
        self,
        commitment_id: str,
        vendor_id: str,
        contract_ref: str,
        *,
        description: str = "",
        target_value: str = "",
    ) -> VendorCommitment:
        """Register a vendor commitment."""
        if commitment_id in self._commitments:
            raise RuntimeCoreInvariantError("Duplicate commitment_id")
        if vendor_id not in self._vendors:
            raise RuntimeCoreInvariantError("Unknown vendor_id")
        now = _now_iso()
        c = VendorCommitment(
            commitment_id=commitment_id, vendor_id=vendor_id,
            contract_ref=contract_ref, description=description,
            target_value=target_value, created_at=now,
        )
        self._commitments[commitment_id] = c
        _emit(self._events, "commitment_registered", {
            "commitment_id": commitment_id, "vendor_id": vendor_id,
        }, commitment_id)
        return c

    def commitments_for_vendor(
        self, vendor_id: str,
    ) -> tuple[VendorCommitment, ...]:
        """Return all commitments for a vendor."""
        return tuple(
            c for c in self._commitments.values() if c.vendor_id == vendor_id
        )

    # ------------------------------------------------------------------
    # Renewal windows
    # ------------------------------------------------------------------

    def schedule_renewal(
        self,
        renewal_id: str,
        vendor_id: str,
        contract_ref: str,
        opens_at: str,
        closes_at: str,
    ) -> ProcurementRenewalWindow:
        """Schedule a vendor contract renewal window."""
        if renewal_id in self._renewals:
            raise RuntimeCoreInvariantError("Duplicate renewal_id")
        if vendor_id not in self._vendors:
            raise RuntimeCoreInvariantError("Unknown vendor_id")
        r = ProcurementRenewalWindow(
            renewal_id=renewal_id, vendor_id=vendor_id,
            contract_ref=contract_ref, disposition=RenewalDisposition.PENDING,
            opens_at=opens_at, closes_at=closes_at,
        )
        self._renewals[renewal_id] = r
        _emit(self._events, "renewal_scheduled", {
            "renewal_id": renewal_id, "vendor_id": vendor_id,
        }, renewal_id)
        return r

    def approve_renewal(self, renewal_id: str) -> ProcurementRenewalWindow:
        """Approve a renewal."""
        old = self._renewals.get(renewal_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown renewal_id")
        if old.disposition in _RENEWAL_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot approve renewal in current disposition")
        # Check vendor risk — HIGH/CRITICAL blocks renewal
        vendor = self._vendors.get(old.vendor_id)
        if vendor and vendor.risk_level in (VendorRiskLevel.HIGH, VendorRiskLevel.CRITICAL):
            raise RuntimeCoreInvariantError("Cannot approve renewal for vendor with elevated risk")
        updated = ProcurementRenewalWindow(
            renewal_id=old.renewal_id, vendor_id=old.vendor_id,
            contract_ref=old.contract_ref, disposition=RenewalDisposition.APPROVED,
            opens_at=old.opens_at, closes_at=old.closes_at,
            metadata=old.metadata,
        )
        self._renewals[renewal_id] = updated
        _emit(self._events, "renewal_approved", {"renewal_id": renewal_id}, renewal_id)
        return updated

    def deny_renewal(self, renewal_id: str) -> ProcurementRenewalWindow:
        """Deny a renewal."""
        old = self._renewals.get(renewal_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown renewal_id")
        if old.disposition in _RENEWAL_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot deny renewal in current disposition")
        updated = ProcurementRenewalWindow(
            renewal_id=old.renewal_id, vendor_id=old.vendor_id,
            contract_ref=old.contract_ref, disposition=RenewalDisposition.DENIED,
            opens_at=old.opens_at, closes_at=old.closes_at,
            metadata=old.metadata,
        )
        self._renewals[renewal_id] = updated
        _emit(self._events, "renewal_denied", {"renewal_id": renewal_id}, renewal_id)
        return updated

    def defer_renewal(self, renewal_id: str) -> ProcurementRenewalWindow:
        """Defer a renewal decision."""
        old = self._renewals.get(renewal_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown renewal_id")
        if old.disposition in _RENEWAL_TERMINAL:
            raise RuntimeCoreInvariantError("Cannot defer renewal in current disposition")
        updated = ProcurementRenewalWindow(
            renewal_id=old.renewal_id, vendor_id=old.vendor_id,
            contract_ref=old.contract_ref, disposition=RenewalDisposition.DEFERRED,
            opens_at=old.opens_at, closes_at=old.closes_at,
            metadata=old.metadata,
        )
        self._renewals[renewal_id] = updated
        _emit(self._events, "renewal_deferred", {"renewal_id": renewal_id}, renewal_id)
        return updated

    def renewals_for_vendor(
        self, vendor_id: str,
    ) -> tuple[ProcurementRenewalWindow, ...]:
        """Return all renewals for a vendor."""
        return tuple(
            r for r in self._renewals.values() if r.vendor_id == vendor_id
        )

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_procurement_violations(self) -> tuple[VendorViolation, ...]:
        """Detect procurement and vendor violations."""
        now = _now_iso()
        new_violations: list[VendorViolation] = []

        # High/critical risk vendors with active POs
        for vendor in self._vendors.values():
            if vendor.risk_level in (VendorRiskLevel.HIGH, VendorRiskLevel.CRITICAL):
                active_pos = [
                    p for p in self._pos.values()
                    if p.vendor_id == vendor.vendor_id
                    and p.status not in _PO_TERMINAL
                ]
                if active_pos:
                    vid = stable_identifier("viol-proc", {
                        "vendor": vendor.vendor_id, "op": "risky_active_po",
                    })
                    if vid not in self._violations:
                        v = VendorViolation(
                            violation_id=vid,
                            vendor_id=vendor.vendor_id,
                            tenant_id=vendor.tenant_id,
                            operation="risky_active_po",
                            reason="Vendor has elevated risk with active purchase orders",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Blocked/terminated vendors with non-terminal POs
        for vendor in self._vendors.values():
            if vendor.status in _VENDOR_BLOCKED:
                active_pos = [
                    p for p in self._pos.values()
                    if p.vendor_id == vendor.vendor_id
                    and p.status not in _PO_TERMINAL
                ]
                if active_pos:
                    vid = stable_identifier("viol-proc", {
                        "vendor": vendor.vendor_id, "op": "blocked_active_po",
                    })
                    if vid not in self._violations:
                        v = VendorViolation(
                            violation_id=vid,
                            vendor_id=vendor.vendor_id,
                            tenant_id=vendor.tenant_id,
                            operation="blocked_active_po",
                            reason="Vendor is inactive with active purchase orders",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "procurement_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_vendor(
        self, vendor_id: str,
    ) -> tuple[VendorViolation, ...]:
        """Return all violations for a vendor."""
        return tuple(
            v for v in self._violations.values() if v.vendor_id == vendor_id
        )

    # ------------------------------------------------------------------
    # Procurement snapshot
    # ------------------------------------------------------------------

    def procurement_snapshot(self, snapshot_id: str) -> ProcurementSnapshot:
        """Capture a point-in-time procurement snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")
        now = _now_iso()
        total_value = sum(
            p.amount for p in self._pos.values()
            if p.status not in {PurchaseOrderStatus.CANCELLED}
        )
        snap = ProcurementSnapshot(
            snapshot_id=snapshot_id,
            total_vendors=self.vendor_count,
            total_requests=self.request_count,
            total_purchase_orders=self.po_count,
            total_assessments=self.assessment_count,
            total_commitments=self.commitment_count,
            total_renewals=self.renewal_count,
            total_violations=self.violation_count,
            total_procurement_value=total_value,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "procurement_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"vendors={self.vendor_count}",
            f"requests={self.request_count}",
            f"pos={self.po_count}",
            f"assessments={self.assessment_count}",
            f"commitments={self.commitment_count}",
            f"renewals={self.renewal_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
