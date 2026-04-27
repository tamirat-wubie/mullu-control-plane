"""Manufacturing domain adapter tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from mcoi_runtime.domain_adapters import (
    ManufacturingActionKind,
    ManufacturingRequest,
    UniversalResult,
    manufacturing_run_with_ucja,
    manufacturing_translate_from_universal,
    manufacturing_translate_to_universal,
)


def _request(**overrides) -> ManufacturingRequest:
    base = dict(
        kind=ManufacturingActionKind.QUALITY_INSPECTION,
        summary="inspect machined bracket",
        line_id="line-3",
        operator_id="op-7",
        quality_engineer="qe-alice",
        iso_certifications=("9001", "13485"),
        affected_part_numbers=("PN-001", "PN-002"),
        acceptance_criteria=("dimensions_within_tolerance",),
        tolerance_microns=10.0,
        expected_yield_pct=0.97,
        safety_critical=False,
        blast_radius="line",
    )
    base.update(overrides)
    return ManufacturingRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in ManufacturingActionKind:
        uni = manufacturing_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_qe_and_operator_in_authority():
    uni = manufacturing_translate_to_universal(_request())
    assert "quality_engineer:qe-alice" in uni.authority_required
    assert "operator:op-7" in uni.authority_required


def test_translate_no_qe_falls_back_to_operator():
    uni = manufacturing_translate_to_universal(_request(quality_engineer=""))
    assert uni.authority_required == ("operator:op-7",)


def test_translate_iso_certs_become_observers():
    uni = manufacturing_translate_to_universal(_request())
    assert "iso:9001" in uni.observer_required
    assert "iso:13485" in uni.observer_required


def test_translate_emits_tolerance_constraint():
    uni = manufacturing_translate_to_universal(_request(tolerance_microns=2.5))
    tol = [c for c in uni.constraint_set if c["domain"] == "dimensional_tolerance"]
    assert len(tol) == 1
    assert "2.5" in tol[0]["restriction"]
    assert tol[0]["violation_response"] == "escalate"


def test_translate_no_tolerance_no_tolerance_constraint():
    uni = manufacturing_translate_to_universal(_request(tolerance_microns=None))
    tol = [c for c in uni.constraint_set if c["domain"] == "dimensional_tolerance"]
    assert tol == []


def test_translate_yield_constraint_is_warn():
    uni = manufacturing_translate_to_universal(_request())
    yld = [c for c in uni.constraint_set if c["domain"] == "yield"]
    assert len(yld) == 1
    assert yld[0]["violation_response"] == "warn"


def test_translate_safety_critical_adds_block_constraint():
    uni = manufacturing_translate_to_universal(_request(safety_critical=True))
    safety = [c for c in uni.constraint_set if c["domain"] == "safety"]
    assert len(safety) == 1
    assert safety[0]["violation_response"] == "block"


def test_translate_rejects_negative_tolerance():
    with pytest.raises(ValueError, match="tolerance_microns"):
        manufacturing_translate_to_universal(_request(tolerance_microns=-1.0))


def test_translate_rejects_invalid_yield():
    with pytest.raises(ValueError, match="expected_yield_pct"):
        manufacturing_translate_to_universal(_request(expected_yield_pct=1.5))


def test_translate_blast_radius_to_permeability():
    cases = {
        "station":    "closed",
        "line":       "selective",
        "plant":      "selective",
        "enterprise": "open",
    }
    for blast, expected in cases.items():
        uni = manufacturing_translate_to_universal(_request(blast_radius=blast))
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


def test_tight_tolerance_flagged():
    out = manufacturing_translate_from_universal(
        _result(), _request(tolerance_microns=3.0),
    )
    assert any("tight_tolerance" in f for f in out.risk_flags)


def test_low_yield_flagged():
    out = manufacturing_translate_from_universal(
        _result(), _request(expected_yield_pct=0.85),
    )
    assert any("low_yield_target" in f for f in out.risk_flags)


def test_tight_tolerance_low_yield_combo_flagged():
    out = manufacturing_translate_from_universal(
        _result(), _request(tolerance_microns=3.0, expected_yield_pct=0.9),
    )
    assert any("tight_tolerance_low_yield" in f for f in out.risk_flags)


def test_safety_critical_flagged():
    out = manufacturing_translate_from_universal(
        _result(), _request(safety_critical=True),
    )
    assert any("safety_critical" in f for f in out.risk_flags)


def test_recall_flagged():
    out = manufacturing_translate_from_universal(
        _result(), _request(kind=ManufacturingActionKind.RECALL),
    )
    assert any("recall" in f for f in out.risk_flags)


def test_batch_release_without_qe_flagged():
    out = manufacturing_translate_from_universal(
        _result(),
        _request(
            kind=ManufacturingActionKind.BATCH_RELEASE,
            quality_engineer="",
        ),
    )
    assert any("batch_release_without_qe" in f for f in out.risk_flags)


def test_protocol_includes_qe_and_iso_steps():
    out = manufacturing_translate_from_universal(_result(), _request())
    assert any("qe-alice" in s for s in out.production_protocol)
    assert any("9001" in s for s in out.production_protocol)


def test_protocol_recall_includes_field_notification():
    out = manufacturing_translate_from_universal(
        _result(), _request(kind=ManufacturingActionKind.RECALL),
    )
    assert any("field service" in s.lower() for s in out.production_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = manufacturing_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "QE: qe-alice" in out.required_signoffs
    assert "ISO: 9001" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = manufacturing_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_recall_marked_irreversible():
    """Recall is structurally irreversible at the framework level."""
    out = manufacturing_run_with_ucja(
        _request(kind=ManufacturingActionKind.RECALL),
    )
    assert out.governance_status == "approved"
    assert any("recall" in f for f in out.risk_flags)


def test_result_carries_tolerance_and_yield():
    out = manufacturing_run_with_ucja(
        _request(tolerance_microns=15.0, expected_yield_pct=0.99),
    )
    assert out.tolerance_microns == 15.0
    assert out.expected_yield_pct == 0.99
