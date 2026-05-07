"""Purpose: tests for effect assurance contracts.
Governance scope: effect plan, observation, and reconciliation validation.
Dependencies: effect assurance contracts.
Invariants:
  - Effect plans require expected and forbidden effects.
  - Observed effects require evidence references.
  - Reconciliation status is explicit.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.effect_assurance import (
    EffectPlan,
    EffectReconciliation,
    ExpectedEffect,
    ObservedEffect,
    ReconciliationStatus,
)


TS = "2026-04-24T12:00:00+00:00"


def _expected(**overrides):
    defaults = {
        "effect_id": "ledger_entry_created",
        "name": "ledger_entry_created",
        "target_ref": "ledger:tenant-1",
        "required": True,
        "verification_method": "ledger_lookup",
        "expected_value": {"amount": 300},
    }
    defaults.update(overrides)
    return ExpectedEffect(**defaults)


def _plan(**overrides):
    defaults = {
        "effect_plan_id": "effect-plan-1",
        "command_id": "cmd-1",
        "tenant_id": "tenant-1",
        "capability_id": "send_payment",
        "expected_effects": (_expected(),),
        "forbidden_effects": ("duplicate_payment",),
        "rollback_plan_id": None,
        "compensation_plan_id": "refund-payment",
        "graph_node_refs": ("command:cmd-1",),
        "graph_edge_refs": ("command produced effect",),
        "created_at": TS,
    }
    defaults.update(overrides)
    return EffectPlan(**defaults)


def _observed(**overrides):
    defaults = {
        "effect_id": "ledger_entry_created",
        "name": "ledger_entry_created",
        "source": "provider",
        "observed_value": {"amount": 300},
        "evidence_ref": "receipt:1",
        "observed_at": TS,
    }
    defaults.update(overrides)
    return ObservedEffect(**defaults)


def test_expected_effect_validates_identity_and_contract():
    effect = _expected()
    assert effect.effect_id == "ledger_entry_created"
    assert effect.required is True
    assert effect.expected_value["amount"] == 300


def test_effect_plan_requires_expected_effects():
    with pytest.raises(ValueError, match="expected_effects"):
        _plan(expected_effects=())


def test_effect_plan_requires_forbidden_effects():
    with pytest.raises(ValueError, match="forbidden_effects"):
        _plan(forbidden_effects=())


def test_effect_plan_rejects_non_expected_effect_value():
    with pytest.raises(ValueError, match="ExpectedEffect"):
        _plan(expected_effects=("ledger_entry_created",))


def test_observed_effect_requires_evidence_ref():
    with pytest.raises(ValueError, match="evidence_ref"):
        _observed(evidence_ref="")


def test_reconciliation_accepts_empty_effect_sets_for_unknown_status():
    reconciliation = EffectReconciliation(
        reconciliation_id="rec-1",
        command_id="cmd-1",
        effect_plan_id="effect-plan-1",
        status=ReconciliationStatus.UNKNOWN,
        matched_effects=(),
        missing_effects=(),
        unexpected_effects=(),
        verification_result_id=None,
        case_id="case-1",
        decided_at=TS,
    )
    assert reconciliation.status is ReconciliationStatus.UNKNOWN
    assert reconciliation.case_id == "case-1"
    assert reconciliation.matched_effects == ()


def test_reconciliation_rejects_invalid_status():
    with pytest.raises(ValueError, match="ReconciliationStatus"):
        EffectReconciliation(
            reconciliation_id="rec-1",
            command_id="cmd-1",
            effect_plan_id="effect-plan-1",
            status="done",
            matched_effects=(),
            missing_effects=(),
            unexpected_effects=(),
            verification_result_id=None,
            case_id=None,
            decided_at=TS,
        )
