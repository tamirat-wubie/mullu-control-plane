"""Finance domain adapter tests."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    FinancialActionKind,
    FinancialRequest,
    UniversalResult,
    finance_run_with_ucja,
    finance_translate_from_universal,
    finance_translate_to_universal,
)


def _request(**overrides) -> FinancialRequest:
    base = dict(
        kind=FinancialActionKind.WIRE_TRANSFER,
        summary="vendor payment Q2",
        transaction_id="TX-001",
        responsible_officer="alice",
        approver_chain=("bob",),
        counterparty="acme-corp",
        amount=Decimal("10000.00"),
        currency="USD",
        jurisdiction="US",
        regulatory_regime=("SOX",),
        affected_accounts=("1001",),
        acceptance_criteria=("balance_sufficient",),
        aml_flags=(),
        requires_dual_control=False,
        dual_control_satisfied=False,
        is_high_value=False,
        blast_radius="transaction",
    )
    base.update(overrides)
    return FinancialRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in FinancialActionKind:
        uni = finance_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_officer_and_approvers():
    uni = finance_translate_to_universal(_request(approver_chain=("bob", "carol")))
    assert "officer:alice" in uni.authority_required
    assert "approver:bob" in uni.authority_required
    assert "approver:carol" in uni.authority_required


def test_translate_observers_include_regulator_and_jurisdiction():
    uni = finance_translate_to_universal(
        _request(regulatory_regime=("SOX", "BSA"), jurisdiction="US"),
    )
    assert "transaction_journal_audit" in uni.observer_required
    assert "regulator:SOX" in uni.observer_required
    assert "regulator:BSA" in uni.observer_required
    assert "jurisdiction:US" in uni.observer_required


def test_translate_dual_control_satisfied_recorded_as_observer():
    uni = finance_translate_to_universal(
        _request(requires_dual_control=True, dual_control_satisfied=True),
    )
    assert "maker_checker_attestation" in uni.observer_required
    dc = [c for c in uni.constraint_set if c["domain"] == "dual_control"]
    assert dc == []


def test_translate_dual_control_required_but_unsatisfied_blocks():
    uni = finance_translate_to_universal(
        _request(requires_dual_control=True, dual_control_satisfied=False),
    )
    dc = [c for c in uni.constraint_set if c["domain"] == "dual_control"]
    assert len(dc) == 1
    assert dc[0]["violation_response"] == "block"


def test_translate_aml_flag_per_constraint_escalates():
    uni = finance_translate_to_universal(
        _request(aml_flags=("PEP_match", "OFAC_partial")),
    )
    aml = [c for c in uni.constraint_set if c["domain"] == "aml_sanctions"]
    assert len(aml) == 2
    assert all(c["violation_response"] == "escalate" for c in aml)


def test_translate_high_value_only_for_money_movement_kinds():
    for kind in (
        FinancialActionKind.WIRE_TRANSFER,
        FinancialActionKind.TRADE,
        FinancialActionKind.TRANSACTION,
    ):
        uni = finance_translate_to_universal(_request(kind=kind, is_high_value=True))
        thr = [c for c in uni.constraint_set if c["domain"] == "threshold"]
        assert len(thr) == 1
        assert thr[0]["violation_response"] == "escalate"

    uni = finance_translate_to_universal(
        _request(kind=FinancialActionKind.RECONCILIATION, is_high_value=True),
    )
    thr = [c for c in uni.constraint_set if c["domain"] == "threshold"]
    assert thr == []


def test_translate_invalid_currency_rejected():
    with pytest.raises(ValueError, match="currency"):
        finance_translate_to_universal(_request(currency="DOLLARS"))


def test_translate_negative_amount_rejected():
    with pytest.raises(ValueError, match="amount"):
        finance_translate_to_universal(_request(amount=Decimal("-1.00")))


def test_translate_blast_radius_to_permeability():
    cases = {
        "transaction": "closed",
        "account":     "selective",
        "book":        "selective",
        "systemic":    "open",
    }
    for blast, expected in cases.items():
        uni = finance_translate_to_universal(_request(blast_radius=blast))
        assert uni.boundary_specification["permeability"] == expected


def _result(state: str = "Pass") -> UniversalResult:
    return UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=1,
        converged=True,
        proof_state=state,
    )


def test_dual_control_unsatisfied_flagged():
    out = finance_translate_from_universal(
        _result(),
        _request(requires_dual_control=True, dual_control_satisfied=False),
    )
    assert any("dual_control_required_but_not_satisfied" in f for f in out.risk_flags)


def test_aml_flags_surfaced_in_risk():
    out = finance_translate_from_universal(
        _result(),
        _request(aml_flags=("PEP_match",)),
    )
    assert any("aml_sanctions_flags_present" in f for f in out.risk_flags)


def test_high_value_wire_flagged():
    out = finance_translate_from_universal(
        _result(),
        _request(kind=FinancialActionKind.WIRE_TRANSFER, is_high_value=True),
    )
    assert any("high_value_wire_transfer" in f for f in out.risk_flags)


def test_wire_without_approver_flagged():
    out = finance_translate_from_universal(
        _result(),
        _request(kind=FinancialActionKind.WIRE_TRANSFER, approver_chain=()),
    )
    assert any(
        "wire_transfer_without_approver_chain" in f for f in out.risk_flags
    )


def test_irreversible_action_flagged():
    out = finance_translate_from_universal(
        _result(),
        _request(kind=FinancialActionKind.WIRE_TRANSFER),
    )
    assert any("wire_transfer_irreversible" in f for f in out.risk_flags)


def test_systemic_blast_flagged():
    out = finance_translate_from_universal(
        _result(),
        _request(blast_radius="systemic"),
    )
    assert any("systemic_blast_radius" in f for f in out.risk_flags)


def test_regime_without_jurisdiction_flagged():
    out = finance_translate_from_universal(
        _result(),
        _request(regulatory_regime=("SOX",), jurisdiction=""),
    )
    assert any(
        "regulatory_regime_specified_without_jurisdiction" in f
        for f in out.risk_flags
    )


def test_protocol_wire_includes_swift_step():
    out = finance_translate_from_universal(
        _result(),
        _request(kind=FinancialActionKind.WIRE_TRANSFER),
    )
    assert any("SWIFT" in s or "Fedwire" in s for s in out.settlement_protocol)


def test_protocol_includes_dual_control_step_when_satisfied():
    out = finance_translate_from_universal(
        _result(),
        _request(requires_dual_control=True, dual_control_satisfied=True),
    )
    assert any("maker-checker" in s for s in out.settlement_protocol)


def test_protocol_includes_aml_clearance_step():
    out = finance_translate_from_universal(
        _result(),
        _request(aml_flags=("PEP_match",)),
    )
    assert any("AML" in s and "clear" in s.lower() for s in out.settlement_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = finance_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "officer: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = finance_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_high_value_wire_with_full_governance_passes():
    out = finance_run_with_ucja(
        _request(
            kind=FinancialActionKind.WIRE_TRANSFER,
            amount=Decimal("250000.00"),
            is_high_value=True,
            requires_dual_control=True,
            dual_control_satisfied=True,
            approver_chain=("bob", "carol"),
            acceptance_criteria=(
                "balance_sufficient",
                "counterparty_verified",
            ),
        ),
    )
    assert out.governance_status == "approved"
    assert out.is_high_value is True
    assert out.dual_control_satisfied is True


def test_result_carries_dual_control_and_high_value_flags():
    out = finance_run_with_ucja(
        _request(
            requires_dual_control=True,
            dual_control_satisfied=True,
            is_high_value=False,
        ),
    )
    assert out.dual_control_satisfied is True
    assert out.is_high_value is False
