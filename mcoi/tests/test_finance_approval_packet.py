"""Purpose: M1 tests for governed finance approval packets.
Governance scope: contract validation, deterministic policy decisions,
causal state transitions, and proof export closure.
Dependencies: finance approval packet contracts and core finance approval.
Invariants: blocked fixtures emit no effects; closed fixtures require closure
and proof evidence; invalid transitions fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mcoi_runtime.contracts.finance_approval_packet import (
    ApprovalStatus,
    EffectReceiptType,
    FinanceApprovalReceipt,
    FinanceEffectReceipt,
    FinancePacketRisk,
    FinancePacketState,
    FinancePolicyVerdict,
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
from mcoi_runtime.core.finance_approval.policy import (
    APPROVAL_REQUIRED,
    BUDGET_EXCEEDED_ACTOR_LIMIT,
    POLICY_PASSED,
    VENDOR_EVIDENCE_STALE,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


NOW = "2026-05-05T12:00:00+00:00"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _case(*, amount_minor_units: int, risk: FinancePacketRisk = FinancePacketRisk.MEDIUM) -> InvoiceCase:
    return InvoiceCase(
        case_id="case-inv-001",
        tenant_id="tenant-demo",
        actor_id="user-requester",
        vendor_id="vendor-acme",
        invoice_id="INV-2026-001",
        amount=InvoiceMoney(currency="USD", minor_units=amount_minor_units),
        source_evidence_ref="evidence:invoice:INV-2026-001",
        state=FinancePacketState.BUDGET_CHECKED,
        risk=risk,
        created_at=NOW,
        updated_at=NOW,
    )


def test_invoice_money_rejects_float_amounts() -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        InvoiceMoney(currency="USD", minor_units=1200.5)  # type: ignore[arg-type]
    assert InvoiceMoney(currency="usd", minor_units=1200).currency == "USD"
    assert InvoiceMoney(currency="USD", minor_units=0).minor_units == 0


def test_blocked_fixture_requires_review_and_emits_no_effect() -> None:
    invoice_case = _case(amount_minor_units=1_200_000, risk=FinancePacketRisk.HIGH)
    decision = evaluate_finance_packet_policy(
        invoice_case,
        FinancePolicyContext(
            actor_limit_minor_units=500_000,
            tenant_limit_minor_units=5_000_000,
            vendor_evidence_status=VendorEvidenceStatus.STALE,
            approval_status=ApprovalStatus.ABSENT,
            evaluated_at=NOW,
            evidence_refs=("evidence:vendor:stale",),
        ),
    )
    review_case = transition_invoice_case(
        invoice_case,
        FinancePacketTransition(
            next_state=FinancePacketState.REQUIRES_REVIEW,
            cause="policy_requires_review",
            actor_id="system-policy",
            occurred_at=NOW,
            evidence_refs=decision.evidence_refs,
            violation_reasons=decision.reasons,
            policy_decision_ref=decision.decision_id,
        ),
    )
    proof = export_finance_packet_proof(
        review_case,
        (decision,),
        audit_root_hash="audit-root-blocked",
        generated_at=NOW,
    )

    assert decision.verdict == FinancePolicyVerdict.REQUIRE_REVIEW
    assert BUDGET_EXCEEDED_ACTOR_LIMIT in decision.reasons
    assert VENDOR_EVIDENCE_STALE in decision.reasons
    assert APPROVAL_REQUIRED in decision.reasons
    assert review_case.effect_refs == ()
    assert proof.final_state == FinancePacketState.REQUIRES_REVIEW
    assert proof.effect_refs == ()
    assert proof.policy_decisions == (decision.decision_id,)


def test_successful_fixture_exports_closed_packet_proof() -> None:
    invoice_case = _case(amount_minor_units=120_000)
    decision = evaluate_finance_packet_policy(
        invoice_case,
        FinancePolicyContext(
            actor_limit_minor_units=500_000,
            tenant_limit_minor_units=5_000_000,
            vendor_evidence_status=VendorEvidenceStatus.FRESH,
            approval_status=ApprovalStatus.GRANTED,
            evaluated_at=NOW,
            evidence_refs=("evidence:vendor:fresh",),
        ),
    )
    approval = FinanceApprovalReceipt(
        approval_id="approval-001",
        case_id=invoice_case.case_id,
        tenant_id=invoice_case.tenant_id,
        approver_id="finance-admin",
        approver_role="finance_admin",
        status=ApprovalStatus.GRANTED,
        decided_at=NOW,
        evidence_refs=("evidence:approval:001",),
    )
    effect = FinanceEffectReceipt(
        effect_id="effect-email-001",
        case_id=invoice_case.case_id,
        tenant_id=invoice_case.tenant_id,
        effect_type=EffectReceiptType.EMAIL_HANDOFF_CREATED,
        capability_id="email.draft.with_approval",
        dispatched_at=NOW,
        evidence_refs=("evidence:effect:email-001",),
    )
    approved_case = transition_invoice_case(
        invoice_case,
        FinancePacketTransition(
            next_state=FinancePacketState.APPROVED,
            cause="policy_allowed",
            actor_id="system-policy",
            occurred_at=NOW,
            policy_decision_ref=decision.decision_id,
            approval_ref=approval.approval_id,
        ),
    )
    dispatched_case = transition_invoice_case(
        approved_case,
        FinancePacketTransition(
            next_state=FinancePacketState.EFFECT_DISPATCHED,
            cause="email_handoff_created",
            actor_id="email-worker",
            occurred_at=NOW,
            effect_ref=effect.effect_id,
        ),
    )
    reconciled_case = transition_invoice_case(
        dispatched_case,
        FinancePacketTransition(
            next_state=FinancePacketState.RECONCILED,
            cause="effect_receipt_verified",
            actor_id="system-verifier",
            occurred_at=NOW,
            evidence_refs=effect.evidence_refs,
        ),
    )
    closed_case = transition_invoice_case(
        reconciled_case,
        FinancePacketTransition(
            next_state=FinancePacketState.CLOSED_SENT,
            cause="terminal_closure_issued",
            actor_id="closure-engine",
            occurred_at=NOW,
            closure_certificate_id="closure-finance-001",
        ),
    )
    proof = export_finance_packet_proof(
        closed_case,
        (decision,),
        audit_root_hash="audit-root-success",
        generated_at=NOW,
    )

    assert decision.verdict == FinancePolicyVerdict.ALLOW
    assert decision.reasons == (POLICY_PASSED,)
    assert closed_case.approval_refs == (approval.approval_id,)
    assert closed_case.effect_refs == (effect.effect_id,)
    assert proof.final_state == FinancePacketState.CLOSED_SENT
    assert proof.closure_certificate_id == "closure-finance-001"
    assert proof.effect_refs == (effect.effect_id,)


def test_finance_packet_proof_matches_public_schema() -> None:
    schema = json.loads(
        (REPO_ROOT / "schemas" / "finance_approval_packet_proof.schema.json").read_text(encoding="utf-8")
    )
    invoice_case = _case(amount_minor_units=1_200_000, risk=FinancePacketRisk.HIGH)
    decision = evaluate_finance_packet_policy(
        invoice_case,
        FinancePolicyContext(
            actor_limit_minor_units=500_000,
            tenant_limit_minor_units=5_000_000,
            vendor_evidence_status=VendorEvidenceStatus.STALE,
            approval_status=ApprovalStatus.ABSENT,
            evaluated_at=NOW,
            evidence_refs=("evidence:vendor:stale",),
        ),
    )
    review_case = transition_invoice_case(
        invoice_case,
        FinancePacketTransition(
            next_state=FinancePacketState.REQUIRES_REVIEW,
            cause="policy_requires_review",
            actor_id="system-policy",
            occurred_at=NOW,
            evidence_refs=decision.evidence_refs,
            violation_reasons=decision.reasons,
            policy_decision_ref=decision.decision_id,
        ),
    )
    proof = export_finance_packet_proof(
        review_case,
        (decision,),
        audit_root_hash="audit-root-schema",
        generated_at=NOW,
    )

    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(proof.to_json_dict()), key=lambda item: item.path)
    assert errors == []
    assert proof.final_state == FinancePacketState.REQUIRES_REVIEW
    assert proof.closure_certificate_id is None


def test_invalid_transition_is_rejected_without_mutating_case() -> None:
    invoice_case = _case(amount_minor_units=120_000)

    with pytest.raises(RuntimeCoreInvariantError, match="invalid finance packet state transition"):
        transition_invoice_case(
            invoice_case,
            FinancePacketTransition(
                next_state=FinancePacketState.CLOSED_SENT,
                cause="skip_required_states",
                actor_id="system-test",
                occurred_at=NOW,
            ),
        )
    assert invoice_case.state == FinancePacketState.BUDGET_CHECKED
    assert invoice_case.effect_refs == ()
    assert invoice_case.closure_certificate_id is None


def test_proof_export_fails_for_closed_packet_without_closure_certificate() -> None:
    invoice_case = _case(amount_minor_units=120_000)
    decision = evaluate_finance_packet_policy(
        invoice_case,
        FinancePolicyContext(
            actor_limit_minor_units=500_000,
            tenant_limit_minor_units=5_000_000,
            vendor_evidence_status=VendorEvidenceStatus.FRESH,
            evaluated_at=NOW,
            evidence_refs=("evidence:vendor:fresh",),
        ),
    )
    approved_case = transition_invoice_case(
        invoice_case,
        FinancePacketTransition(
            next_state=FinancePacketState.APPROVED,
            cause="policy_allowed",
            actor_id="system-policy",
            occurred_at=NOW,
            policy_decision_ref=decision.decision_id,
        ),
    )
    prepared_case = transition_invoice_case(
        approved_case,
        FinancePacketTransition(
            next_state=FinancePacketState.CLOSED_PREPARED,
            cause="prepared_without_effect",
            actor_id="closure-engine",
            occurred_at=NOW,
        ),
    )

    with pytest.raises(FinanceProofExportError, match="closure_certificate_id is required"):
        export_finance_packet_proof(
            prepared_case,
            (decision,),
            audit_root_hash="audit-root-missing-closure",
            generated_at=NOW,
        )
    assert prepared_case.state == FinancePacketState.CLOSED_PREPARED
    assert prepared_case.closure_certificate_id is None
    assert prepared_case.policy_decision_refs == (decision.decision_id,)
