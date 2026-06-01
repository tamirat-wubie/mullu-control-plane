"""Attribution-binding for governance decision endpoints (non-repudiation).

Two governance decisions recorded WHO acted from a request-body field:
- finance_approval.approve_finance_approval_packet -> FinanceApprovalReceipt(approver_id=req.approver_id)
- software_receipts.decide_software_receipt_review_request -> queue.decide(reviewer_id=body.reviewer_id)

A caller could therefore forge the approver/reviewer identity (claim someone else
approved/reviewed), defeating non-repudiation and dual-control. Both now pass the
claimed identity through bind_claimed_actor, which rejects (403) an identity that
differs from the authenticated actor. No-op for unauthenticated dev requests
(the claimed value passes through), so existing suites are unaffected.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mcoi_runtime.app.routers import finance_approval, software_receipts
from mcoi_runtime.app.routers.auth_context import bind_claimed_actor
from mcoi_runtime.contracts.finance_approval_packet import (
    FinancePacketRisk,
    FinancePacketState,
    InvoiceCase,
    InvoiceMoney,
)


class _State:
    def __init__(self, ctx: dict) -> None:
        self.governance_context = ctx


class _Req:
    def __init__(self, ctx: dict) -> None:
        self.state = _State(ctx)


def _authed(subject: str) -> _Req:
    # Wildcard scope so the tenant-scope check is a no-op; the actor binding is
    # what is under test here.
    return _Req({
        "authenticated_subject": subject,
        "authenticated_tenant_id": "tenant-a",
        "jwt_scopes": frozenset({"*"}),
    })


# -- finance approval: forged approver_id ----------------------------------

class _Case:
    tenant_id = "tenant-x"


class _FinStore:
    def get_case(self, case_id):
        return _Case()


class _ApproveReq:
    approver_id = "victim-cfo"  # claimed != authenticated -> forgery
    status = "granted"
    approver_role = "cfo"
    evidence_refs: list = []
    create_email_handoff = False
    create_payment_handoff = False
    finalize_payment_with_receipt = False
    payment_provider_receipt_ref = ""
    ledger_reconciliation_ref = ""


def test_approve_finance_rejects_forged_approver(monkeypatch):
    monkeypatch.setattr(finance_approval, "_store", lambda: _FinStore())
    with pytest.raises(HTTPException) as exc:
        finance_approval.approve_finance_approval_packet("c1", _ApproveReq(), _authed("attacker"))
    assert exc.value.status_code == 403


class _PersistentFinStore:
    def __init__(self) -> None:
        self.case = InvoiceCase(
            case_id="case-bind-empty",
            tenant_id="tenant-x",
            actor_id="requester",
            vendor_id="vendor-a",
            invoice_id="inv-1",
            amount=InvoiceMoney(currency="USD", minor_units=100),
            source_evidence_ref="evidence:invoice:inv-1",
            state=FinancePacketState.APPROVAL_REQUIRED,
            risk=FinancePacketRisk.MEDIUM,
            created_at="2026-06-01T14:00:00+00:00",
            updated_at="2026-06-01T14:00:00+00:00",
        )
        self.approvals = []
        self.effects = []
        self.saved_case = None

    def get_case(self, case_id):
        return self.case

    def append_approval(self, approval):
        self.approvals.append(approval)

    def append_effect(self, effect):
        self.effects.append(effect)

    def save_case(self, invoice_case):
        self.saved_case = invoice_case


def test_approve_finance_binds_empty_approver_to_authenticated_transition(monkeypatch):
    store = _PersistentFinStore()
    transitions = []
    real_transition = finance_approval.transition_invoice_case

    def capture_transition(invoice_case, transition):
        transitions.append(transition)
        return real_transition(invoice_case, transition)

    monkeypatch.setattr(finance_approval, "_store", lambda: store)
    monkeypatch.setattr(finance_approval, "_clock_now", lambda: "2026-06-01T14:05:00+00:00")
    monkeypatch.setattr(finance_approval, "transition_invoice_case", capture_transition)

    result = finance_approval.approve_finance_approval_packet(
        "case-bind-empty",
        finance_approval.FinancePacketApprovalRequest(
            approver_id="",
            create_email_handoff=False,
        ),
        _authed("alice"),
    )

    assert result["approval"]["approver_id"] == "alice"
    assert store.approvals[0].approver_id == "alice"
    assert transitions[0].cause == "approval_granted"
    assert transitions[0].actor_id == "alice"
    assert store.saved_case.state == FinancePacketState.CLOSED_PREPARED


# -- software receipt review: forged reviewer_id ---------------------------

class _ReviewBody:
    reviewer_id = "victim-reviewer"
    approved = True
    comment = ""


def test_review_decision_rejects_forged_reviewer():
    with pytest.raises(HTTPException) as exc:
        software_receipts.decide_software_receipt_review_request(
            "r1", _ReviewBody(), _authed("attacker"), tenant_id="tenant-a",
        )
    assert exc.value.status_code == 403


# -- bind_claimed_actor semantics the fixes rely on ------------------------

def test_bind_claimed_actor_semantics():
    assert bind_claimed_actor(_authed("alice"), "alice") == "alice"   # match -> allowed
    assert bind_claimed_actor(_authed("alice"), "") == "alice"        # empty -> authenticated
    assert bind_claimed_actor(_Req({}), "anyone") == "anyone"         # unauth dev -> passthrough
