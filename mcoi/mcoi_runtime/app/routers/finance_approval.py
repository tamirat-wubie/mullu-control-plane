"""Purpose: finance approval packet HTTP endpoints.
Governance scope: create/list/get/approve/proof read model for the M1 finance
approval packet pilot.
Dependencies: router deps, finance approval packet contracts, and core finance
approval policy/state/proof helpers.
Invariants:
  - Packet creation evaluates policy before exposing a case.
  - Approval actions are explicit receipts, not silent state flips.
  - Proof export is allowed only for review-bound or closed packet states.
  - Responses expose governed=True and bounded error codes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.contracts.finance_approval_packet import (
    ApprovalStatus,
    EffectReceiptType,
    FinanceApprovalReceipt,
    FinanceEffectReceipt,
    FinancePacketRisk,
    FinancePacketState,
    InvoiceCase,
    InvoiceMoney,
    VendorEvidenceStatus,
)
from mcoi_runtime.core.finance_approval import (
    FinancePacketTransition,
    FinancePolicyContext,
    FinanceProofExportError,
    evaluate_finance_packet_policy,
    export_finance_packet_proof,
    transition_invoice_case,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.persistence.finance_approval_store import FinanceApprovalPacketStore

router = APIRouter()

_fallback_store = FinanceApprovalPacketStore()


class FinancePacketCreateRequest(BaseModel):
    case_id: str
    tenant_id: str
    actor_id: str
    vendor_id: str
    invoice_id: str
    currency: str = "USD"
    minor_units: int
    source_evidence_ref: str
    risk: str = FinancePacketRisk.MEDIUM.value
    actor_limit_minor_units: int
    tenant_limit_minor_units: int
    vendor_evidence_status: str = VendorEvidenceStatus.FRESH.value
    approval_status: str = ApprovalStatus.ABSENT.value
    duplicate_invoice: bool = False
    recovery_path_present: bool = True
    capability_maturity_level: int = 6
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinancePacketApprovalRequest(BaseModel):
    approver_id: str
    approver_role: str = "finance_admin"
    status: str = ApprovalStatus.GRANTED.value
    create_email_handoff: bool = True
    closure_certificate_id: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


def reset_finance_approval_packets_for_tests() -> None:
    """Clear in-memory pilot state for isolated router tests."""
    global _fallback_store
    _fallback_store = FinanceApprovalPacketStore()


def _clock_now() -> str:
    return deps.clock()


def _store() -> FinanceApprovalPacketStore:
    try:
        return deps.finance_approval_store
    except RuntimeError:
        return _fallback_store


def _error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _case_body(case: InvoiceCase) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "tenant_id": case.tenant_id,
        "actor_id": case.actor_id,
        "vendor_id": case.vendor_id,
        "invoice_id": case.invoice_id,
        "amount": case.amount.to_json_dict(),
        "source_evidence_ref": case.source_evidence_ref,
        "state": case.state.value,
        "risk": case.risk.value,
        "policy_decision_refs": list(case.policy_decision_refs),
        "approval_refs": list(case.approval_refs),
        "effect_refs": list(case.effect_refs),
        "closure_certificate_id": case.closure_certificate_id,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "metadata": dict(case.metadata),
    }


def _decision_body(decision: Any) -> dict[str, Any]:
    return decision.to_json_dict()


def _proof_exportable_state(state: FinancePacketState) -> bool:
    return state in {
        FinancePacketState.CLOSED_PREPARED,
        FinancePacketState.CLOSED_SENT,
        FinancePacketState.CLOSED_REJECTED,
        FinancePacketState.CLOSED_DUPLICATE,
        FinancePacketState.CLOSED_ACCEPTED_RISK,
        FinancePacketState.REQUIRES_REVIEW,
        FinancePacketState.FAILED_WITH_RECOVERY,
    }


@router.post("/api/v1/finance/approval-packets")
def create_finance_approval_packet(req: FinancePacketCreateRequest):
    """Create and evaluate a governed finance approval packet."""
    deps.metrics.inc("requests_governed")
    store = _store()
    if store.get_case(req.case_id) is not None:
        raise HTTPException(400, detail=_error_detail("case already exists", "duplicate_case_id"))
    try:
        now = _clock_now()
        risk = FinancePacketRisk(req.risk)
        vendor_status = VendorEvidenceStatus(req.vendor_evidence_status)
        approval_status = ApprovalStatus(req.approval_status)
        case = InvoiceCase(
            case_id=req.case_id,
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            vendor_id=req.vendor_id,
            invoice_id=req.invoice_id,
            amount=InvoiceMoney(currency=req.currency, minor_units=req.minor_units),
            source_evidence_ref=req.source_evidence_ref,
            state=FinancePacketState.BUDGET_CHECKED,
            risk=risk,
            created_at=now,
            updated_at=now,
            metadata=req.metadata,
        )
        decision = evaluate_finance_packet_policy(
            case,
            FinancePolicyContext(
                actor_limit_minor_units=req.actor_limit_minor_units,
                tenant_limit_minor_units=req.tenant_limit_minor_units,
                vendor_evidence_status=vendor_status,
                approval_status=approval_status,
                duplicate_invoice=req.duplicate_invoice,
                recovery_path_present=req.recovery_path_present,
                capability_maturity_level=req.capability_maturity_level,
                evaluated_at=now,
                evidence_refs=(req.source_evidence_ref,),
            ),
        )
        next_state = (
            FinancePacketState.REQUIRES_REVIEW
            if decision.verdict.value in {"require_review", "block"}
            else FinancePacketState.APPROVAL_REQUIRED
            if decision.verdict.value == "require_approval"
            else FinancePacketState.APPROVED
        )
        case = transition_invoice_case(
            case,
            FinancePacketTransition(
                next_state=next_state,
                cause="finance_policy_evaluated",
                actor_id="finance-policy",
                occurred_at=now,
                evidence_refs=decision.evidence_refs,
                violation_reasons=decision.reasons,
                policy_decision_ref=decision.decision_id,
            ),
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail(str(exc), "invalid_finance_packet")) from exc

    store.save_case(case)
    store.append_decision(decision)
    return {"packet": _case_body(case), "policy_decision": _decision_body(decision), "governed": True}


@router.get("/api/v1/finance/approval-packets/operator/read-model")
def finance_approval_operator_read_model(
    tenant_id: str = "",
    state: str = "",
    limit: int = 50,
):
    """Return a bounded operator read model for finance approval packets."""
    deps.metrics.inc("requests_governed")
    if limit < 1 or limit > 200:
        raise HTTPException(400, detail=_error_detail("limit must be between 1 and 200", "invalid_limit"))
    try:
        state_filter = FinancePacketState(state) if state else None
    except ValueError:
        raise HTTPException(400, detail=_error_detail("invalid state", "invalid_state"))
    store = _store()
    summary = store.summary()
    cases = store.list_cases(tenant_id=tenant_id, state=state_filter)[:limit]
    packets: list[dict[str, Any]] = []
    blocked_count = 0
    approval_wait_count = 0
    proof_ready_count = 0
    for case in cases:
        decisions = store.list_decisions(case_id=case.case_id)
        latest_decision = decisions[-1] if decisions else None
        reasons = list(latest_decision.reasons) if latest_decision is not None else []
        if case.state is FinancePacketState.REQUIRES_REVIEW:
            blocked_count += 1
        if case.state is FinancePacketState.APPROVAL_REQUIRED:
            approval_wait_count += 1
        proof_exportable = _proof_exportable_state(case.state)
        if proof_exportable:
            proof_ready_count += 1
        packets.append(
            {
                "case_id": case.case_id,
                "tenant_id": case.tenant_id,
                "invoice_id": case.invoice_id,
                "vendor_id": case.vendor_id,
                "amount": case.amount.to_json_dict(),
                "state": case.state.value,
                "risk": case.risk.value,
                "latest_policy_verdict": latest_decision.verdict.value if latest_decision else "",
                "latest_policy_reasons": reasons,
                "approval_ref_count": len(case.approval_refs),
                "effect_ref_count": len(case.effect_refs),
                "closure_certificate_id": case.closure_certificate_id,
                "proof_exportable": proof_exportable,
                "updated_at": case.updated_at,
            }
        )
    return {
        "summary": summary,
        "visible_count": len(packets),
        "blocked_count": blocked_count,
        "approval_wait_count": approval_wait_count,
        "proof_ready_count": proof_ready_count,
        "packets": packets,
        "filters": {"tenant_id": tenant_id, "state": state, "limit": limit},
        "governed": True,
    }


@router.get("/api/v1/finance/approval-packets")
def list_finance_approval_packets(tenant_id: str = "", state: str = ""):
    """List governed finance approval packets from the in-memory pilot store."""
    deps.metrics.inc("requests_governed")
    try:
        state_filter = FinancePacketState(state) if state else None
    except ValueError:
        raise HTTPException(400, detail=_error_detail("invalid state", "invalid_state"))
    cases = _store().list_cases(tenant_id=tenant_id, state=state_filter)
    return {"packets": [_case_body(case) for case in cases], "count": len(cases), "governed": True}


@router.get("/api/v1/finance/approval-packets/{case_id}")
def get_finance_approval_packet(case_id: str):
    """Return one finance approval packet and its policy decisions."""
    deps.metrics.inc("requests_governed")
    store = _store()
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(404, detail=_error_detail("packet not found", "packet_not_found"))
    return {
        "packet": _case_body(case),
        "policy_decisions": [_decision_body(decision) for decision in store.list_decisions(case_id=case_id)],
        "approvals": [receipt.to_json_dict() for receipt in store.list_approvals(case_id=case_id)],
        "effects": [receipt.to_json_dict() for receipt in store.list_effects(case_id=case_id)],
        "governed": True,
    }


@router.post("/api/v1/finance/approval-packets/{case_id}/approval")
def approve_finance_approval_packet(case_id: str, req: FinancePacketApprovalRequest):
    """Record an explicit approval decision and close a prepared/sent packet."""
    deps.metrics.inc("requests_governed")
    store = _store()
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(404, detail=_error_detail("packet not found", "packet_not_found"))
    try:
        now = _clock_now()
        approval_status = ApprovalStatus(req.status)
        approval = FinanceApprovalReceipt(
            approval_id=stable_identifier(
                "fin-approval",
                {"case_id": case_id, "approver_id": req.approver_id, "decided_at": now},
            ),
            case_id=case.case_id,
            tenant_id=case.tenant_id,
            approver_id=req.approver_id,
            approver_role=req.approver_role,
            status=approval_status,
            decided_at=now,
            evidence_refs=tuple(req.evidence_refs or [f"evidence:approval:{case_id}"]),
        )
        if approval_status is not ApprovalStatus.GRANTED:
            updated = transition_invoice_case(
                case,
                FinancePacketTransition(
                    next_state=FinancePacketState.CLOSED_REJECTED,
                    cause="approval_not_granted",
                    actor_id=req.approver_id,
                    occurred_at=now,
                    approval_ref=approval.approval_id,
                    closure_certificate_id=req.closure_certificate_id or f"closure:{case_id}:rejected",
                ),
            )
        else:
            current = case
            if current.state is FinancePacketState.APPROVAL_REQUIRED:
                current = transition_invoice_case(
                    current,
                    FinancePacketTransition(
                        next_state=FinancePacketState.APPROVED,
                        cause="approval_granted",
                        actor_id=req.approver_id,
                        occurred_at=now,
                        approval_ref=approval.approval_id,
                    ),
                )
            elif current.state is not FinancePacketState.APPROVED:
                raise RuntimeCoreInvariantError("packet is not approval-ready")
            if req.create_email_handoff:
                effect = FinanceEffectReceipt(
                    effect_id=stable_identifier("fin-effect", {"case_id": case_id, "dispatched_at": now}),
                    case_id=case.case_id,
                    tenant_id=case.tenant_id,
                    effect_type=EffectReceiptType.EMAIL_HANDOFF_CREATED,
                    capability_id="email.draft.with_approval",
                    dispatched_at=now,
                    evidence_refs=(f"evidence:effect:{case_id}",),
                )
                current = transition_invoice_case(
                    current,
                    FinancePacketTransition(
                        next_state=FinancePacketState.EFFECT_DISPATCHED,
                        cause="email_handoff_created",
                        actor_id="email-worker",
                        occurred_at=now,
                        approval_ref=approval.approval_id,
                        effect_ref=effect.effect_id,
                    ),
                )
                current = transition_invoice_case(
                    current,
                    FinancePacketTransition(
                        next_state=FinancePacketState.RECONCILED,
                        cause="effect_receipt_verified",
                        actor_id="finance-verifier",
                        occurred_at=now,
                        evidence_refs=effect.evidence_refs,
                    ),
                )
                updated = transition_invoice_case(
                    current,
                    FinancePacketTransition(
                        next_state=FinancePacketState.CLOSED_SENT,
                        cause="terminal_closure_issued",
                        actor_id="closure-engine",
                        occurred_at=now,
                        closure_certificate_id=req.closure_certificate_id or f"closure:{case_id}:sent",
                    ),
                )
            else:
                updated = transition_invoice_case(
                    current,
                    FinancePacketTransition(
                        next_state=FinancePacketState.CLOSED_PREPARED,
                        cause="terminal_closure_issued",
                        actor_id="closure-engine",
                        occurred_at=now,
                        approval_ref=approval.approval_id,
                        closure_certificate_id=req.closure_certificate_id or f"closure:{case_id}:prepared",
                    ),
                )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(400, detail=_error_detail(str(exc), "finance_approval_failed")) from exc

    store.append_approval(approval)
    if approval_status is ApprovalStatus.GRANTED and req.create_email_handoff:
        store.append_effect(effect)
    store.save_case(updated)
    return {"packet": _case_body(updated), "approval": approval.to_json_dict(), "governed": True}


@router.get("/api/v1/finance/approval-packets/{case_id}/proof")
def get_finance_approval_packet_proof(case_id: str):
    """Export a governed proof artifact for one packet."""
    deps.metrics.inc("requests_governed")
    store = _store()
    case = store.get_case(case_id)
    if case is None:
        raise HTTPException(404, detail=_error_detail("packet not found", "packet_not_found"))
    try:
        proof = export_finance_packet_proof(
            case,
            store.list_decisions(case_id=case_id),
            audit_root_hash=stable_identifier("audit-root", {"case_id": case_id, "state": case.state.value}),
            generated_at=_clock_now(),
        )
    except FinanceProofExportError as exc:
        raise HTTPException(400, detail=_error_detail(str(exc), "proof_not_exportable")) from exc
    return {"proof": proof.to_json_dict(), "governed": True}
