#!/usr/bin/env python3
"""Produce a deterministic finance approval packet pilot witness.

Purpose: execute the blocked and successful finance approval packet paths
without live external effects and emit a machine-readable witness.
Governance scope: finance packet contracts, policy decisions, approval/effect
receipts, proof export, and local readiness evidence.
Dependencies: finance approval contracts, core policy/state/proof helpers, and
the finance approval store.
Invariants:
  - The blocked path must enter requires_review and emit no effect refs.
  - The successful path must close with approval, effect, and closure refs.
  - Both paths must export schema-shaped proof dictionaries.
  - The witness must not claim live email delivery or payment execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.finance_approval_packet import (  # noqa: E402
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
from mcoi_runtime.core.finance_approval import (  # noqa: E402
    FinancePacketTransition,
    FinancePolicyContext,
    evaluate_finance_packet_policy,
    export_finance_packet_proof,
    transition_invoice_case,
)
from mcoi_runtime.core.invariants import stable_identifier  # noqa: E402
from mcoi_runtime.persistence.finance_approval_store import FinanceApprovalPacketStore  # noqa: E402
from scripts.validate_finance_approval_pilot import (  # noqa: E402
    DEFAULT_ADAPTER_EVIDENCE,
    validate_finance_approval_pilot,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_pilot_witness.json"
NOW = "2026-05-05T12:00:00+00:00"


def produce_finance_approval_pilot_witness(
    *,
    adapter_evidence_path: Path = DEFAULT_ADAPTER_EVIDENCE,
) -> dict[str, Any]:
    """Run deterministic blocked and successful packet paths."""
    store = FinanceApprovalPacketStore()
    blocked_case, blocked_decision, blocked_proof = _blocked_path(store)
    success_case, success_decision, success_approval, success_effect, success_proof = _successful_path(store)
    readiness = validate_finance_approval_pilot(adapter_evidence_path=adapter_evidence_path)
    blockers: list[str] = []
    if blocked_case.state is not FinancePacketState.REQUIRES_REVIEW:
        blockers.append("blocked_case_not_requires_review")
    if blocked_case.effect_refs:
        blockers.append("blocked_case_emitted_effect")
    if success_case.state is not FinancePacketState.CLOSED_SENT:
        blockers.append("success_case_not_closed_sent")
    if not success_case.approval_refs:
        blockers.append("success_case_missing_approval_ref")
    if not success_case.effect_refs:
        blockers.append("success_case_missing_effect_ref")
    if not success_case.closure_certificate_id:
        blockers.append("success_case_missing_closure_certificate")

    return {
        "witness_id": stable_identifier(
            "finance-pilot-witness",
            {
                "blocked_case": blocked_case.case_id,
                "success_case": success_case.case_id,
                "checked_at": NOW,
            },
        ),
        "checked_at": NOW,
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "external_readiness": readiness.as_dict(),
        "claim_boundary": {
            "can_claim": [
                "governed finance approval packet preparation",
                "policy-reasoned blocking",
                "explicit approval receipts",
                "email-handoff effect receipts",
                "schema-backed proof export",
            ],
            "must_not_claim": [
                "autonomous payment execution",
                "bank settlement",
                "ERP reconciliation",
                "live email delivery",
                "production finance automation",
            ],
        },
        "blocked_path": {
            "case": blocked_case.to_json_dict(),
            "policy_decision": blocked_decision.to_json_dict(),
            "proof": blocked_proof.to_json_dict(),
        },
        "successful_path": {
            "case": success_case.to_json_dict(),
            "policy_decision": success_decision.to_json_dict(),
            "approval": success_approval.to_json_dict(),
            "effect": success_effect.to_json_dict(),
            "proof": success_proof.to_json_dict(),
        },
        "store_summary": store.summary(),
    }


def _blocked_path(
    store: FinanceApprovalPacketStore,
) -> tuple[InvoiceCase, Any, Any]:
    case = InvoiceCase(
        case_id="case-blocked-001",
        tenant_id="tenant-demo",
        actor_id="user-requester",
        vendor_id="vendor-acme",
        invoice_id="INV-BLOCKED-001",
        amount=InvoiceMoney(currency="USD", minor_units=1_200_000),
        source_evidence_ref="evidence:invoice:blocked",
        state=FinancePacketState.BUDGET_CHECKED,
        risk=FinancePacketRisk.HIGH,
        created_at=NOW,
        updated_at=NOW,
    )
    decision = evaluate_finance_packet_policy(
        case,
        FinancePolicyContext(
            actor_limit_minor_units=500_000,
            tenant_limit_minor_units=5_000_000,
            vendor_evidence_status=VendorEvidenceStatus.STALE,
            approval_status=ApprovalStatus.ABSENT,
            evaluated_at=NOW,
            evidence_refs=(case.source_evidence_ref, "evidence:vendor:stale"),
        ),
    )
    case = transition_invoice_case(
        case,
        FinancePacketTransition(
            next_state=FinancePacketState.REQUIRES_REVIEW,
            cause="finance_policy_requires_review",
            actor_id="finance-policy",
            occurred_at=NOW,
            evidence_refs=decision.evidence_refs,
            violation_reasons=decision.reasons,
            policy_decision_ref=decision.decision_id,
        ),
    )
    store.save_case(case)
    store.append_decision(decision)
    proof = export_finance_packet_proof(
        case,
        (decision,),
        audit_root_hash=stable_identifier("audit-root", {"case_id": case.case_id, "state": case.state.value}),
        generated_at=NOW,
    )
    return case, decision, proof


def _successful_path(
    store: FinanceApprovalPacketStore,
) -> tuple[InvoiceCase, Any, FinanceApprovalReceipt, FinanceEffectReceipt, Any]:
    case = InvoiceCase(
        case_id="case-success-001",
        tenant_id="tenant-demo",
        actor_id="user-requester",
        vendor_id="vendor-acme",
        invoice_id="INV-OK-001",
        amount=InvoiceMoney(currency="USD", minor_units=120_000),
        source_evidence_ref="evidence:invoice:success",
        state=FinancePacketState.BUDGET_CHECKED,
        risk=FinancePacketRisk.MEDIUM,
        created_at=NOW,
        updated_at=NOW,
    )
    decision = evaluate_finance_packet_policy(
        case,
        FinancePolicyContext(
            actor_limit_minor_units=500_000,
            tenant_limit_minor_units=5_000_000,
            vendor_evidence_status=VendorEvidenceStatus.FRESH,
            approval_status=ApprovalStatus.GRANTED,
            evaluated_at=NOW,
            evidence_refs=(case.source_evidence_ref, "evidence:vendor:fresh"),
        ),
    )
    approval = FinanceApprovalReceipt(
        approval_id="approval-success-001",
        case_id=case.case_id,
        tenant_id=case.tenant_id,
        approver_id="finance-admin",
        approver_role="finance_admin",
        status=ApprovalStatus.GRANTED,
        decided_at=NOW,
        evidence_refs=("evidence:approval:success",),
    )
    effect = FinanceEffectReceipt(
        effect_id="effect-email-handoff-001",
        case_id=case.case_id,
        tenant_id=case.tenant_id,
        effect_type=EffectReceiptType.EMAIL_HANDOFF_CREATED,
        capability_id="email.draft.with_approval",
        dispatched_at=NOW,
        evidence_refs=("evidence:effect:email-handoff",),
    )
    case = transition_invoice_case(
        case,
        FinancePacketTransition(
            next_state=FinancePacketState.APPROVED,
            cause="finance_policy_allowed",
            actor_id="finance-policy",
            occurred_at=NOW,
            policy_decision_ref=decision.decision_id,
            approval_ref=approval.approval_id,
        ),
    )
    case = transition_invoice_case(
        case,
        FinancePacketTransition(
            next_state=FinancePacketState.EFFECT_DISPATCHED,
            cause="email_handoff_created",
            actor_id="email-worker",
            occurred_at=NOW,
            effect_ref=effect.effect_id,
        ),
    )
    case = transition_invoice_case(
        case,
        FinancePacketTransition(
            next_state=FinancePacketState.RECONCILED,
            cause="effect_receipt_verified",
            actor_id="finance-verifier",
            occurred_at=NOW,
            evidence_refs=effect.evidence_refs,
        ),
    )
    case = transition_invoice_case(
        case,
        FinancePacketTransition(
            next_state=FinancePacketState.CLOSED_SENT,
            cause="terminal_closure_issued",
            actor_id="closure-engine",
            occurred_at=NOW,
            closure_certificate_id="closure:case-success-001:sent",
        ),
    )
    store.save_case(case)
    store.append_decision(decision)
    store.append_approval(approval)
    store.append_effect(effect)
    proof = export_finance_packet_proof(
        case,
        (decision,),
        audit_root_hash=stable_identifier("audit-root", {"case_id": case.case_id, "state": case.state.value}),
        generated_at=NOW,
    )
    return case, decision, approval, effect, proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter-evidence", default=str(DEFAULT_ADAPTER_EVIDENCE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    witness = produce_finance_approval_pilot_witness(adapter_evidence_path=Path(args.adapter_evidence))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(witness, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(witness, indent=2, sort_keys=True))
    else:
        print(f"finance approval pilot witness: {witness['status']} -> {output_path}")
    return 0 if witness["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
