"""Tests for governed invoice swarm workflow.

Purpose: verify invoice handling as the first concrete S2 governed swarm use
case with WHQR claims, supervisor quorum, MIL gating, and closure proof.
Governance scope: invoice claims remain bounded until approval, quorum, static
verification, and proof closure all pass.
Dependencies: mcoi_runtime.swarm.invoice_workflow.
Invariants: payment intent requires approval, duplicate/vendor failures block
closure, and budget uncertainty escalates.
"""

from __future__ import annotations

from decimal import Decimal

from mcoi_runtime.swarm import SwarmDecisionVerdict
from mcoi_runtime.swarm.invoice_workflow import InvoiceSwarmRequest, run_invoice_swarm
from mcoi_runtime.swarm.mil import MILInstructionKind


def _request(**overrides: object) -> InvoiceSwarmRequest:
    values = {
        "goal_id": "goal_invoice_demo_001",
        "tenant_id": "tenant_a",
        "invoice_ref": "invoice_001",
        "invoice_amount_usd": Decimal("1250.00"),
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }
    values.update(overrides)
    return InvoiceSwarmRequest(**values)


def test_invoice_swarm_closes_after_human_approval_and_mil_verification() -> None:
    result = run_invoice_swarm(_request())

    assert result.swarm.decision.verdict is SwarmDecisionVerdict.PASSED
    assert result.swarm.closure is not None
    assert result.closure is result.swarm.closure
    assert result.mil_verification.passed is True
    assert result.mil_program.instructions[-1].kind is MILInstructionKind.CALL_CAPABILITY
    assert result.mil_program.instructions[-1].capability == "payment.dispatch"


def test_invoice_swarm_escalates_when_required_approval_is_missing() -> None:
    result = run_invoice_swarm(_request(human_approved=False))

    assert result.swarm.decision.verdict is SwarmDecisionVerdict.ESCALATE
    assert result.swarm.decision.requires_human_approval is True
    assert result.swarm.closure is None
    assert result.closure is None
    assert result.mil_verification.passed is False
    assert result.mil_verification.reason == "decision_not_passed"


def test_invoice_swarm_blocks_duplicate_invoice_without_payment_intent() -> None:
    result = run_invoice_swarm(_request(duplicate_found=True))

    assert result.swarm.decision.verdict is SwarmDecisionVerdict.FAILED
    assert result.swarm.closure is None
    assert result.closure is None
    assert result.mil_verification.passed is False
    assert result.mil_program.instructions[-1].kind is MILInstructionKind.REQUIRE_APPROVAL
    assert result.mil_program.instructions[-1].capability == "approval.manager"


def test_invoice_swarm_escalates_budget_unknown_as_review_case() -> None:
    result = run_invoice_swarm(_request(budget_available=False, human_approved=True))

    assert result.swarm.decision.verdict is SwarmDecisionVerdict.ESCALATE
    assert result.swarm.decision.reason == "unknown_claim_present"
    assert result.swarm.closure is None
    assert result.closure is None
    assert result.mil_verification.passed is False
    assert len(result.swarm.receipts) == 7
