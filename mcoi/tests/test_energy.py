"""Energy / utilities domain adapter tests."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    EnergyActionKind,
    EnergyRequest,
    UniversalResult,
    energy_run_with_ucja,
    energy_translate_from_universal,
    energy_translate_to_universal,
)


def _request(**overrides) -> EnergyRequest:
    base = dict(
        kind=EnergyActionKind.GENERATION_DISPATCH,
        summary="ramp Unit 3 up 200 MW",
        operation_id="OP-001",
        responsible_operator="alice",
        approver_chain=("shift-supervisor",),
        balancing_authority="CAISO",
        service_territory="PG&E",
        jurisdiction="FERC",
        regulatory_regime=("NERC_BAL",),
        affected_assets=("GEN-3",),
        megawatts=Decimal("200"),
        acceptance_criteria=("frequency_within_band",),
        reliability_critical=True,
        n_minus_1_compliant=True,
        is_emergency=False,
        blast_radius="balancing_area",
    )
    base.update(overrides)
    return EnergyRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in EnergyActionKind:
        # carbon/rate/meter aren't reliability-critical by default; allow
        rc = kind in (
            EnergyActionKind.GENERATION_DISPATCH,
            EnergyActionKind.LOAD_CURTAILMENT,
            EnergyActionKind.OUTAGE_RESPONSE,
            EnergyActionKind.GRID_RECONFIGURATION,
            EnergyActionKind.EMERGENCY_DEMAND_RESPONSE,
        )
        uni = energy_translate_to_universal(
            _request(kind=kind, reliability_critical=rc),
        )
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_operator_and_approvers():
    uni = energy_translate_to_universal(
        _request(approver_chain=("shift-sup", "rc")),
    )
    assert "operator:alice" in uni.authority_required
    assert "approver:shift-sup" in uni.authority_required
    assert "approver:rc" in uni.authority_required


def test_translate_observers_include_ba_jurisdiction_regulator_rc():
    uni = energy_translate_to_universal(_request())
    assert "control_room_log" in uni.observer_required
    assert "balancing_authority:CAISO" in uni.observer_required
    assert "territory:PG&E" in uni.observer_required
    assert "jurisdiction:FERC" in uni.observer_required
    assert "regulator:NERC_BAL" in uni.observer_required
    assert "reliability_coordinator" in uni.observer_required


def test_translate_n_minus_1_violation_blocks_routine():
    uni = energy_translate_to_universal(
        _request(n_minus_1_compliant=False, is_emergency=False),
    )
    n1 = [c for c in uni.constraint_set if c["domain"] == "n_minus_1"]
    assert len(n1) == 1
    assert n1[0]["violation_response"] == "block"


def test_translate_n_minus_1_violation_escalates_under_emergency():
    uni = energy_translate_to_universal(
        _request(n_minus_1_compliant=False, is_emergency=True),
    )
    n1 = [c for c in uni.constraint_set if c["domain"] == "n_minus_1"]
    assert n1[0]["violation_response"] == "escalate"


def test_translate_rc_engagement_required_for_reliability_critical():
    uni = energy_translate_to_universal(_request(reliability_critical=True))
    rc = [c for c in uni.constraint_set if c["domain"] == "rc_engagement"]
    assert len(rc) == 1
    assert rc[0]["violation_response"] == "escalate"


def test_translate_rc_engagement_skipped_for_non_critical():
    uni = energy_translate_to_universal(
        _request(
            kind=EnergyActionKind.METER_DATA_VALIDATION,
            reliability_critical=False,
        ),
    )
    rc = [c for c in uni.constraint_set if c["domain"] == "rc_engagement"]
    assert rc == []


def test_translate_regulatory_regime_per_constraint():
    uni = energy_translate_to_universal(
        _request(regulatory_regime=("NERC_BAL", "FERC_OATT")),
    )
    reg = [c for c in uni.constraint_set if c["domain"] == "regulatory"]
    assert len(reg) == 2
    assert all(c["violation_response"] == "escalate" for c in reg)


def test_translate_reliability_critical_without_ba_rejected():
    with pytest.raises(ValueError, match="balancing_authority"):
        energy_translate_to_universal(
            _request(reliability_critical=True, balancing_authority=""),
        )


def test_translate_blast_radius_to_permeability():
    cases = {
        "asset":           "closed",
        "feeder":          "selective",
        "balancing_area":  "selective",
        "interconnect":    "open",
    }
    for blast, expected in cases.items():
        uni = energy_translate_to_universal(_request(blast_radius=blast))
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


def test_n_minus_1_routine_violation_flagged():
    out = energy_translate_from_universal(
        _result(),
        _request(n_minus_1_compliant=False, is_emergency=False),
    )
    assert any(
        "n_minus_1_violation_non_emergency" in f for f in out.risk_flags
    )


def test_n_minus_1_emergency_violation_flagged_differently():
    out = energy_translate_from_universal(
        _result(),
        _request(n_minus_1_compliant=False, is_emergency=True),
    )
    assert any(
        "n_minus_1_violation_under_emergency" in f for f in out.risk_flags
    )


def test_emergency_state_flagged():
    out = energy_translate_from_universal(_result(), _request(is_emergency=True))
    assert any("emergency_operating_state" in f for f in out.risk_flags)


def test_reliability_critical_dispatch_flagged():
    out = energy_translate_from_universal(
        _result(),
        _request(
            kind=EnergyActionKind.GENERATION_DISPATCH,
            reliability_critical=True,
        ),
    )
    assert any(
        "reliability_critical_generation_dispatch" in f for f in out.risk_flags
    )


def test_irreversible_action_flagged():
    out = energy_translate_from_universal(
        _result(),
        _request(kind=EnergyActionKind.GENERATION_DISPATCH),
    )
    assert any(
        "generation_dispatch_irreversible" in f for f in out.risk_flags
    )


def test_interconnect_blast_flagged():
    out = energy_translate_from_universal(
        _result(),
        _request(blast_radius="interconnect"),
    )
    assert any("interconnect_blast_radius" in f for f in out.risk_flags)


def test_rate_filing_without_regulatory_regime_flagged():
    out = energy_translate_from_universal(
        _result(),
        _request(
            kind=EnergyActionKind.RATE_FILING,
            reliability_critical=False,
            regulatory_regime=(),
        ),
    )
    assert any(
        "rate_filing_without_regulatory_regime" in f for f in out.risk_flags
    )


def test_protocol_includes_n_minus_1_step_when_compliant():
    out = energy_translate_from_universal(
        _result(),
        _request(n_minus_1_compliant=True, reliability_critical=True),
    )
    assert any("N-1 contingency" in s for s in out.operating_protocol)


def test_protocol_includes_emergency_n1_step():
    out = energy_translate_from_universal(
        _result(),
        _request(
            n_minus_1_compliant=False,
            is_emergency=True,
            reliability_critical=True,
        ),
    )
    assert any(
        "emergency operating state" in s and "N-1 deviation" in s
        for s in out.operating_protocol
    )


def test_protocol_dispatch_includes_setpoint_step():
    out = energy_translate_from_universal(
        _result(),
        _request(kind=EnergyActionKind.GENERATION_DISPATCH),
    )
    assert any("setpoint" in s.lower() for s in out.operating_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = energy_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "operator: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = energy_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_emergency_dispatch_with_n1_violation_passes():
    out = energy_run_with_ucja(
        _request(
            kind=EnergyActionKind.EMERGENCY_DEMAND_RESPONSE,
            n_minus_1_compliant=False,
            is_emergency=True,
            acceptance_criteria=("emergency_declaration_present",),
        ),
    )
    assert out.governance_status == "approved"
    assert out.is_emergency is True


def test_result_carries_n1_and_emergency_flags():
    out = energy_run_with_ucja(
        _request(n_minus_1_compliant=True, is_emergency=False),
    )
    assert out.n_minus_1_compliant is True
    assert out.is_emergency is False
