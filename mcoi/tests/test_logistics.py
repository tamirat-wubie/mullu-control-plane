"""Logistics / supply chain domain adapter tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    LogisticsActionKind,
    LogisticsRequest,
    UniversalResult,
    logistics_run_with_ucja,
    logistics_translate_from_universal,
    logistics_translate_to_universal,
)


def _request(**overrides) -> LogisticsRequest:
    base = dict(
        kind=LogisticsActionKind.SHIPMENT_DISPATCH,
        summary="Q2 wholesale shipment",
        shipment_id="SHIP-001",
        responsible_dispatcher="alice",
        carrier_chain=("ups",),
        shipper="acme-corp",
        consignee="widget-inc",
        origin="US",
        destination="US",
        modes=("road",),
        hazmat_class="",
        temperature_controlled=False,
        customs_required=False,
        hs_codes=(),
        affected_skus=("SKU-1",),
        acceptance_criteria=("manifest_signed",),
        chain_of_custody_intact=True,
        is_expedited=False,
        blast_radius="shipment",
    )
    base.update(overrides)
    return LogisticsRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in LogisticsActionKind:
        uni = logistics_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_dispatcher_and_carriers():
    uni = logistics_translate_to_universal(
        _request(carrier_chain=("ups", "fedex")),
    )
    assert "dispatcher:alice" in uni.authority_required
    assert "carrier:ups" in uni.authority_required
    assert "carrier:fedex" in uni.authority_required


def test_translate_observers_include_shipper_consignee_origin_destination():
    uni = logistics_translate_to_universal(_request())
    assert "shipment_log" in uni.observer_required
    assert "shipper:acme-corp" in uni.observer_required
    assert "consignee:widget-inc" in uni.observer_required
    assert "origin:US" in uni.observer_required
    assert "destination:US" in uni.observer_required


def test_translate_customs_observer_when_required():
    uni = logistics_translate_to_universal(
        _request(customs_required=True, hs_codes=("8471.30",)),
    )
    assert "customs_authority" in uni.observer_required


def test_translate_hazmat_observer_when_present():
    uni = logistics_translate_to_universal(
        _request(hazmat_class="Class 3 Flammable"),
    )
    assert "hazmat_authority" in uni.observer_required


def test_translate_cold_chain_observer_when_temperature_controlled():
    uni = logistics_translate_to_universal(_request(temperature_controlled=True))
    assert "cold_chain_monitor" in uni.observer_required


def test_translate_custody_attestation_when_intact():
    uni = logistics_translate_to_universal(_request(chain_of_custody_intact=True))
    assert "chain_of_custody_attestation" in uni.observer_required

    uni2 = logistics_translate_to_universal(_request(chain_of_custody_intact=False))
    assert "chain_of_custody_attestation" not in uni2.observer_required


def test_translate_customs_without_hs_codes_blocks():
    uni = logistics_translate_to_universal(
        _request(customs_required=True, hs_codes=()),
    )
    customs = [c for c in uni.constraint_set if c["domain"] == "customs"]
    assert len(customs) == 1
    assert customs[0]["violation_response"] == "block"


def test_translate_customs_with_hs_codes_no_constraint():
    uni = logistics_translate_to_universal(
        _request(customs_required=True, hs_codes=("8471.30",)),
    )
    customs = [c for c in uni.constraint_set if c["domain"] == "customs"]
    assert customs == []


def test_translate_hazmat_constraint_escalates():
    uni = logistics_translate_to_universal(
        _request(hazmat_class="Class 3 Flammable"),
    )
    haz = [c for c in uni.constraint_set if c["domain"] == "hazmat"]
    assert len(haz) == 1
    assert haz[0]["violation_response"] == "escalate"


def test_translate_broken_custody_blocks_when_hazmat_or_cold_chain():
    haz_uni = logistics_translate_to_universal(
        _request(
            chain_of_custody_intact=False,
            hazmat_class="Class 3 Flammable",
        ),
    )
    coc_haz = [c for c in haz_uni.constraint_set if c["domain"] == "chain_of_custody"]
    assert coc_haz[0]["violation_response"] == "block"

    cold_uni = logistics_translate_to_universal(
        _request(chain_of_custody_intact=False, temperature_controlled=True),
    )
    coc_cold = [c for c in cold_uni.constraint_set if c["domain"] == "chain_of_custody"]
    assert coc_cold[0]["violation_response"] == "block"


def test_translate_broken_custody_warns_when_neither_haz_nor_cold():
    uni = logistics_translate_to_universal(_request(chain_of_custody_intact=False))
    coc = [c for c in uni.constraint_set if c["domain"] == "chain_of_custody"]
    assert coc[0]["violation_response"] == "warn"


def test_translate_cold_chain_escalates():
    uni = logistics_translate_to_universal(_request(temperature_controlled=True))
    cc = [c for c in uni.constraint_set if c["domain"] == "cold_chain"]
    assert len(cc) == 1
    assert cc[0]["violation_response"] == "escalate"


def test_translate_invalid_mode_rejected():
    with pytest.raises(ValueError, match="transport mode"):
        logistics_translate_to_universal(_request(modes=("teleport",)))


def test_translate_invalid_origin_rejected():
    with pytest.raises(ValueError, match="origin"):
        logistics_translate_to_universal(_request(origin="USA"))


def test_translate_invalid_destination_rejected():
    with pytest.raises(ValueError, match="destination"):
        logistics_translate_to_universal(_request(destination="GERMANY"))


def test_translate_blast_radius_to_permeability():
    cases = {
        "shipment": "closed",
        "lane":     "selective",
        "network":  "selective",
        "systemic": "open",
    }
    for blast, expected in cases.items():
        uni = logistics_translate_to_universal(_request(blast_radius=blast))
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


def test_customs_without_hs_codes_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(customs_required=True, hs_codes=()),
    )
    assert any(
        "customs_required_without_hs_codes" in f for f in out.risk_flags
    )


def test_hazmat_flagged_in_risk():
    out = logistics_translate_from_universal(
        _result(),
        _request(hazmat_class="Class 3 Flammable"),
    )
    assert any("hazmat_present" in f for f in out.risk_flags)


def test_cold_chain_with_broken_custody_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(temperature_controlled=True, chain_of_custody_intact=False),
    )
    assert any(
        "cold_chain_with_broken_custody" in f for f in out.risk_flags
    )


def test_broken_custody_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(chain_of_custody_intact=False),
    )
    assert any("chain_of_custody_broken" in f for f in out.risk_flags)


def test_expedited_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(is_expedited=True),
    )
    assert any("expedited_mode" in f for f in out.risk_flags)


def test_dispatch_without_carrier_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(kind=LogisticsActionKind.SHIPMENT_DISPATCH, carrier_chain=()),
    )
    assert any(
        "shipment_dispatch_without_carrier_chain" in f for f in out.risk_flags
    )


def test_irreversible_action_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(kind=LogisticsActionKind.CUSTOMS_CLEARANCE),
    )
    assert any("customs_clearance_irreversible" in f for f in out.risk_flags)


def test_systemic_blast_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(blast_radius="systemic"),
    )
    assert any("systemic_blast_radius" in f for f in out.risk_flags)


def test_international_without_customs_flagged():
    out = logistics_translate_from_universal(
        _result(),
        _request(origin="US", destination="DE", customs_required=False),
    )
    assert any(
        "international_shipment_US_to_DE_without_customs_required" in f
        for f in out.risk_flags
    )


def test_protocol_includes_hs_codes_when_filed():
    out = logistics_translate_from_universal(
        _result(),
        _request(customs_required=True, hs_codes=("8471.30",)),
    )
    assert any("HS codes" in s for s in out.fulfillment_protocol)


def test_protocol_includes_hazmat_step():
    out = logistics_translate_from_universal(
        _result(),
        _request(hazmat_class="Class 3 Flammable"),
    )
    assert any("Hazmat clearance" in s for s in out.fulfillment_protocol)


def test_protocol_includes_carrier_handoff_signoffs():
    out = logistics_translate_from_universal(
        _result(),
        _request(carrier_chain=("ups", "fedex")),
    )
    assert sum(
        1 for s in out.fulfillment_protocol if "Carrier handoff signoff" in s
    ) == 2


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = logistics_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "dispatcher: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = logistics_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_international_hazmat_with_full_governance_passes():
    out = logistics_run_with_ucja(
        _request(
            kind=LogisticsActionKind.CUSTOMS_CLEARANCE,
            origin="US",
            destination="DE",
            modes=("sea", "road"),
            hazmat_class="Class 3 Flammable",
            customs_required=True,
            hs_codes=("2710.19",),
            carrier_chain=("maersk", "db-schenker"),
            acceptance_criteria=("docs_complete", "manifest_signed"),
        ),
    )
    assert out.governance_status == "approved"


def test_result_carries_custody_and_expedited_flags():
    out = logistics_run_with_ucja(
        _request(chain_of_custody_intact=True, is_expedited=False),
    )
    assert out.chain_of_custody_intact is True
    assert out.is_expedited is False
