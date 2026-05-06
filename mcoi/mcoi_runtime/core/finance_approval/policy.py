"""Purpose: deterministic policy evaluation for finance approval packets.
Governance scope: budget, vendor evidence, approval, recovery, maturity, and
duplicate-invoice admission.
Dependencies: finance approval packet contracts and runtime invariant helpers.
Invariants: evaluation does not mutate packet state; violations are explicit
reason codes; effect-bearing work fails closed without required controls.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.finance_approval_packet import (
    ApprovalStatus,
    FinancePacketRisk,
    FinancePolicyDecision,
    FinancePolicyVerdict,
    InvoiceCase,
    VendorEvidenceStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier


BUDGET_EXCEEDED_ACTOR_LIMIT = "budget_exceeded_actor_limit"
BUDGET_EXCEEDED_TENANT_LIMIT = "budget_exceeded_tenant_limit"
VENDOR_EVIDENCE_MISSING = "vendor_evidence_missing"
VENDOR_EVIDENCE_STALE = "vendor_evidence_stale"
APPROVAL_REQUIRED = "approval_required"
APPROVAL_MISSING = "approval_missing"
APPROVAL_EXPIRED = "approval_expired"
DUPLICATE_INVOICE = "duplicate_invoice"
RECOVERY_PATH_MISSING = "recovery_path_missing"
CAPABILITY_MATURITY_INSUFFICIENT = "capability_maturity_insufficient"
POLICY_PASSED = "policy_passed"


@dataclass(frozen=True, slots=True)
class FinancePolicyContext:
    """Bounded inputs for finance packet policy evaluation."""

    actor_limit_minor_units: int
    tenant_limit_minor_units: int
    vendor_evidence_status: VendorEvidenceStatus
    approval_status: ApprovalStatus = ApprovalStatus.ABSENT
    duplicate_invoice: bool = False
    recovery_path_present: bool = True
    capability_maturity_level: int = 6
    evaluated_at: str = ""
    evidence_refs: tuple[str, ...] = ()


def evaluate_finance_packet_policy(
    invoice_case: InvoiceCase,
    context: FinancePolicyContext,
) -> FinancePolicyDecision:
    """Return a deterministic policy decision without mutating the case."""
    if not isinstance(invoice_case, InvoiceCase):
        raise RuntimeCoreInvariantError("invoice_case must be an InvoiceCase")
    if not isinstance(context, FinancePolicyContext):
        raise RuntimeCoreInvariantError("context must be a FinancePolicyContext")
    _validate_context(context)

    reasons: list[str] = []
    controls: list[str] = []
    amount = invoice_case.amount.minor_units

    if amount > context.tenant_limit_minor_units:
        reasons.append(BUDGET_EXCEEDED_TENANT_LIMIT)
        controls.append("tenant_finance_review")
    if amount > context.actor_limit_minor_units:
        reasons.append(BUDGET_EXCEEDED_ACTOR_LIMIT)
        controls.append("finance_admin_approval")
    if context.vendor_evidence_status is VendorEvidenceStatus.MISSING:
        reasons.append(VENDOR_EVIDENCE_MISSING)
        controls.append("vendor_evidence_required")
    elif context.vendor_evidence_status is VendorEvidenceStatus.STALE:
        reasons.append(VENDOR_EVIDENCE_STALE)
        controls.append("vendor_evidence_refresh")
    if context.duplicate_invoice:
        reasons.append(DUPLICATE_INVOICE)
        controls.append("duplicate_invoice_review")
    if not context.recovery_path_present:
        reasons.append(RECOVERY_PATH_MISSING)
        controls.append("recovery_path_required")
    if context.capability_maturity_level < 6:
        reasons.append(CAPABILITY_MATURITY_INSUFFICIENT)
        controls.append("capability_promotion_required")

    approval_needed = (
        invoice_case.risk in (FinancePacketRisk.HIGH, FinancePacketRisk.CRITICAL)
        or amount > context.actor_limit_minor_units
    )
    if approval_needed:
        reasons.append(APPROVAL_REQUIRED)
        controls.append("approval_receipt_required")
        if context.approval_status is ApprovalStatus.ABSENT:
            reasons.append(APPROVAL_MISSING)
        elif context.approval_status is ApprovalStatus.EXPIRED:
            reasons.append(APPROVAL_EXPIRED)
    elif context.approval_status is ApprovalStatus.EXPIRED:
        reasons.append(APPROVAL_EXPIRED)
        controls.append("fresh_approval_required")

    reasons = _dedupe(reasons)
    controls = _dedupe(controls)
    if not reasons:
        reasons = [POLICY_PASSED]

    verdict = _verdict_for(reasons, context.approval_status)
    return FinancePolicyDecision(
        decision_id=stable_identifier(
            "fin-pol",
            {
                "case_id": invoice_case.case_id,
                "reasons": reasons,
                "evaluated_at": context.evaluated_at,
            },
        ),
        case_id=invoice_case.case_id,
        tenant_id=invoice_case.tenant_id,
        verdict=verdict,
        reasons=tuple(reasons),
        required_controls=tuple(controls),
        evidence_refs=tuple(context.evidence_refs),
        created_at=context.evaluated_at,
        metadata={
            "actor_limit_minor_units": context.actor_limit_minor_units,
            "tenant_limit_minor_units": context.tenant_limit_minor_units,
            "vendor_evidence_status": context.vendor_evidence_status.value,
            "approval_status": context.approval_status.value,
            "capability_maturity_level": context.capability_maturity_level,
        },
    )


def _validate_context(context: FinancePolicyContext) -> None:
    for field_name in ("actor_limit_minor_units", "tenant_limit_minor_units", "capability_maturity_level"):
        value = getattr(context, field_name)
        if not isinstance(value, int) or value < 0:
            raise RuntimeCoreInvariantError(f"{field_name} must be a non-negative integer")
    if not isinstance(context.vendor_evidence_status, VendorEvidenceStatus):
        raise RuntimeCoreInvariantError("vendor_evidence_status must be a VendorEvidenceStatus")
    if not isinstance(context.approval_status, ApprovalStatus):
        raise RuntimeCoreInvariantError("approval_status must be an ApprovalStatus")
    if not context.evaluated_at:
        raise RuntimeCoreInvariantError("evaluated_at is required")


def _verdict_for(reasons: list[str], approval_status: ApprovalStatus) -> FinancePolicyVerdict:
    hard_blocks = {
        BUDGET_EXCEEDED_TENANT_LIMIT,
        VENDOR_EVIDENCE_MISSING,
        DUPLICATE_INVOICE,
        RECOVERY_PATH_MISSING,
        CAPABILITY_MATURITY_INSUFFICIENT,
        APPROVAL_EXPIRED,
    }
    if any(reason in hard_blocks for reason in reasons):
        return FinancePolicyVerdict.REQUIRE_REVIEW
    if BUDGET_EXCEEDED_ACTOR_LIMIT in reasons or APPROVAL_REQUIRED in reasons:
        if approval_status is ApprovalStatus.GRANTED:
            return FinancePolicyVerdict.ALLOW
        return FinancePolicyVerdict.REQUIRE_REVIEW
    return FinancePolicyVerdict.ALLOW


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
