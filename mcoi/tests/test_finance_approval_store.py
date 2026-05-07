"""Purpose: verify finance approval packet persistence.
Governance scope: invoice case snapshots, policy decisions, approval/effect
receipts, deterministic file round-trip, and malformed payload rejection.
Dependencies: finance approval store and packet contracts.
Invariants:
  - File-backed state round-trips deterministically.
  - Duplicate matching receipts are idempotent.
  - Id collisions with changed payloads fail closed.
  - Corrupt payloads fail closed without exposing partial state.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.finance_approval_packet import (
    ApprovalStatus,
    EffectReceiptType,
    FinanceApprovalReceipt,
    FinanceEffectReceipt,
    FinancePacketRisk,
    FinancePacketState,
    FinancePolicyDecision,
    FinancePolicyVerdict,
    InvoiceCase,
    InvoiceMoney,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PersistenceError
from mcoi_runtime.persistence.finance_approval_store import (
    FileFinanceApprovalPacketStore,
    FinanceApprovalPacketStore,
)

NOW = "2026-05-05T12:00:00+00:00"


def _case() -> InvoiceCase:
    return InvoiceCase(
        case_id="case-store-001",
        tenant_id="tenant-demo",
        actor_id="user-requester",
        vendor_id="vendor-acme",
        invoice_id="INV-STORE-001",
        amount=InvoiceMoney(currency="USD", minor_units=120_000),
        source_evidence_ref="evidence:invoice:store",
        state=FinancePacketState.REQUIRES_REVIEW,
        risk=FinancePacketRisk.HIGH,
        created_at=NOW,
        updated_at=NOW,
        policy_decision_refs=("decision-store-001",),
    )


def _decision() -> FinancePolicyDecision:
    return FinancePolicyDecision(
        decision_id="decision-store-001",
        case_id="case-store-001",
        tenant_id="tenant-demo",
        verdict=FinancePolicyVerdict.REQUIRE_REVIEW,
        reasons=("budget_exceeded_actor_limit", "approval_required"),
        required_controls=("finance_admin_approval",),
        evidence_refs=("evidence:invoice:store",),
        created_at=NOW,
    )


def _approval(approval_id: str = "approval-store-001") -> FinanceApprovalReceipt:
    return FinanceApprovalReceipt(
        approval_id=approval_id,
        case_id="case-store-001",
        tenant_id="tenant-demo",
        approver_id="finance-admin",
        approver_role="finance_admin",
        status=ApprovalStatus.GRANTED,
        decided_at=NOW,
        evidence_refs=("evidence:approval:store",),
    )


def _effect() -> FinanceEffectReceipt:
    return FinanceEffectReceipt(
        effect_id="effect-store-001",
        case_id="case-store-001",
        tenant_id="tenant-demo",
        effect_type=EffectReceiptType.EMAIL_HANDOFF_CREATED,
        capability_id="email.draft.with_approval",
        dispatched_at=NOW,
        evidence_refs=("evidence:effect:store",),
    )


def test_memory_store_saves_case_decision_approval_and_effect() -> None:
    store = FinanceApprovalPacketStore()

    store.save_case(_case())
    store.append_decision(_decision())
    store.append_approval(_approval())
    store.append_effect(_effect())

    assert store.get_case("case-store-001").state == FinancePacketState.REQUIRES_REVIEW
    assert store.list_cases(tenant_id="tenant-demo") == (_case(),)
    assert store.list_decisions(case_id="case-store-001") == (_decision(),)
    assert store.list_approvals(case_id="case-store-001") == (_approval(),)
    assert store.list_effects(case_id="case-store-001") == (_effect(),)
    assert store.summary()["case_count"] == 1
    assert store.summary()["effect_count"] == 1


def test_duplicate_approval_id_with_different_payload_fails_closed() -> None:
    store = FinanceApprovalPacketStore()
    first = _approval("approval-collision")
    second = FinanceApprovalReceipt(
        approval_id="approval-collision",
        case_id="case-store-001",
        tenant_id="tenant-demo",
        approver_id="other-admin",
        approver_role="finance_admin",
        status=ApprovalStatus.GRANTED,
        decided_at=NOW,
        evidence_refs=("evidence:approval:other",),
    )

    store.append_approval(first)
    repeated = store.append_approval(first)

    with pytest.raises(PersistenceError, match="approval id collision"):
        store.append_approval(second)
    assert repeated == first
    assert store.list_approvals() == (first,)


def test_file_store_round_trips_finance_packet_state(tmp_path) -> None:
    path = tmp_path / "finance_approval.json"
    store = FileFinanceApprovalPacketStore(path)

    store.save_case(_case())
    store.append_decision(_decision())
    store.append_approval(_approval())
    store.append_effect(_effect())
    reloaded = FileFinanceApprovalPacketStore(path)

    assert reloaded.get_case("case-store-001") == _case()
    assert reloaded.list_decisions(case_id="case-store-001") == (_decision(),)
    assert reloaded.list_approvals(case_id="case-store-001") == (_approval(),)
    assert reloaded.list_effects(case_id="case-store-001") == (_effect(),)
    assert reloaded.summary()["by_state"][FinancePacketState.REQUIRES_REVIEW.value] == 1


def test_file_store_rejects_malformed_payload(tmp_path) -> None:
    path = tmp_path / "finance_approval.json"
    path.write_text(json.dumps({"cases": [{"case_id": "incomplete"}]}), encoding="utf-8")

    with pytest.raises(CorruptedDataError, match="invalid finance packet case"):
        FileFinanceApprovalPacketStore(path)
    assert path.exists()
    assert "incomplete" in path.read_text(encoding="utf-8")
