"""Purpose: finance approval packet proof export.
Governance scope: final-state proof validation, closure certificate checks,
approval/effect evidence binding, and audit-root anchoring.
Dependencies: finance approval packet contracts and runtime invariant helpers.
Invariants: incomplete packets fail closed with explicit missing fields.
"""

from __future__ import annotations

from mcoi_runtime.contracts.finance_approval_packet import (
    FinanceApprovalPacketProof,
    FinancePacketState,
    FinancePolicyDecision,
    InvoiceCase,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


class FinanceProofExportError(RuntimeCoreInvariantError):
    """Raised when a finance packet proof cannot be exported safely."""


_CLOSED_STATES = frozenset(
    {
        FinancePacketState.CLOSED_PREPARED,
        FinancePacketState.CLOSED_SENT,
        FinancePacketState.CLOSED_REJECTED,
        FinancePacketState.CLOSED_DUPLICATE,
        FinancePacketState.CLOSED_ACCEPTED_RISK,
        FinancePacketState.FAILED_WITH_RECOVERY,
    }
)
_PROOF_ALLOWED_STATES = _CLOSED_STATES | {FinancePacketState.REQUIRES_REVIEW}


def export_finance_packet_proof(
    invoice_case: InvoiceCase,
    policy_decisions: tuple[FinancePolicyDecision, ...],
    *,
    audit_root_hash: str,
    generated_at: str,
) -> FinanceApprovalPacketProof:
    """Export a strict proof artifact for a closed or review-bound packet."""
    if not isinstance(invoice_case, InvoiceCase):
        raise FinanceProofExportError("invoice_case must be an InvoiceCase")
    if invoice_case.state not in _PROOF_ALLOWED_STATES:
        raise FinanceProofExportError("final_state is not proof-exportable")
    if not policy_decisions:
        raise FinanceProofExportError("policy_decisions are required")
    for decision in policy_decisions:
        if not isinstance(decision, FinancePolicyDecision):
            raise FinanceProofExportError("policy_decisions must contain FinancePolicyDecision values")
        if decision.case_id != invoice_case.case_id:
            raise FinanceProofExportError("policy decision case_id mismatch")
    if not audit_root_hash:
        raise FinanceProofExportError("audit_root_hash is required")
    if invoice_case.state in _CLOSED_STATES and invoice_case.closure_certificate_id is None:
        raise FinanceProofExportError("closure_certificate_id is required for closed states")
    if invoice_case.state is FinancePacketState.CLOSED_SENT and not invoice_case.effect_refs:
        raise FinanceProofExportError("effect_refs are required for closed_sent")

    evidence_refs = _collect_evidence_refs(invoice_case, policy_decisions)
    return FinanceApprovalPacketProof(
        proof_id=stable_identifier(
            "fin-proof",
            {
                "case_id": invoice_case.case_id,
                "final_state": invoice_case.state.value,
                "audit_root_hash": audit_root_hash,
            },
        ),
        case_id=invoice_case.case_id,
        tenant_id=invoice_case.tenant_id,
        final_state=invoice_case.state,
        policy_decisions=tuple(decision.decision_id for decision in policy_decisions),
        evidence_refs=evidence_refs,
        approval_refs=invoice_case.approval_refs,
        effect_refs=invoice_case.effect_refs,
        closure_certificate_id=invoice_case.closure_certificate_id,
        audit_root_hash=audit_root_hash,
        generated_at=generated_at,
    )


def _collect_evidence_refs(
    invoice_case: InvoiceCase,
    policy_decisions: tuple[FinancePolicyDecision, ...],
) -> tuple[str, ...]:
    evidence_refs: list[str] = [invoice_case.source_evidence_ref]
    for decision in policy_decisions:
        evidence_refs.extend(decision.evidence_refs)
    evidence_refs.extend(invoice_case.approval_refs)
    evidence_refs.extend(invoice_case.effect_refs)
    seen: set[str] = set()
    deduped: list[str] = []
    for evidence_ref in evidence_refs:
        if evidence_ref not in seen:
            seen.add(evidence_ref)
            deduped.append(evidence_ref)
    if not deduped:
        raise FinanceProofExportError("evidence_refs are required")
    return tuple(deduped)
