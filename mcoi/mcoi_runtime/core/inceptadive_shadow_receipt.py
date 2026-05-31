"""Receipts for the InceptaDive Shadow Pass.

Purpose: create deterministic audit receipts that prove which shadow result,
findings, context hash, and retrieval receipts influenced a request or candidate
plan before Mullu governance.
Governance scope: receipts are audit records only; they cannot approve, mutate,
promote, retrieve, or execute.
Dependencies: shared shadow types and deterministic hashing.
Invariants: every receipt records no execution authority, links finding IDs, and
preserves context lineage without storing raw secrets beyond the already-redacted
context hash.
"""

from __future__ import annotations

from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowPassResult,
    ShadowReceipt,
)


def create_shadow_receipt(
    context: ShadowContext,
    result: ShadowPassResult,
    *,
    governance_verdict: str = "not_evaluated",
) -> ShadowReceipt:
    """Create a deterministic receipt for a shadow pass result.

    The caller may attach a later governance verdict, but this receipt still has
    no execution authority. It proves shadow influence only.
    """

    checked_context = context.with_integrity()
    checked_result = result.with_integrity()
    return ShadowReceipt(
        receipt_id="pending",
        request_id=checked_context.request_id,
        mode=checked_result.mode,
        stage=checked_result.stage,
        context_hash=checked_context.context_hash,
        result_id=checked_result.result_id,
        finding_ids=tuple(finding.finding_id for finding in checked_result.findings),
        retrieval_receipt_ids=checked_context.retrieval_receipt_ids,
        shadow_verdict=checked_result.verdict,
        governance_verdict=governance_verdict,
        created_at=checked_result.created_at,
    ).with_integrity()


def attach_governance_verdict(receipt: ShadowReceipt, *, governance_verdict: str) -> ShadowReceipt:
    """Return a new receipt view with governance verdict attached.

    This preserves the original request/result/finding lineage and recalculates
    the deterministic snapshot hash.
    """

    if not governance_verdict.strip():
        governance_verdict = "not_evaluated"
    return ShadowReceipt(
        receipt_id="pending",
        request_id=receipt.request_id,
        mode=receipt.mode,
        stage=receipt.stage,
        context_hash=receipt.context_hash,
        result_id=receipt.result_id,
        finding_ids=receipt.finding_ids,
        retrieval_receipt_ids=receipt.retrieval_receipt_ids,
        shadow_verdict=receipt.shadow_verdict,
        governance_verdict=governance_verdict,
        created_at=receipt.created_at,
    ).with_integrity()
