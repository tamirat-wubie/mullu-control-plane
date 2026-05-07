"""Cybersecurity / SecOps domain adapter tests."""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    SecOpsActionKind,
    SecOpsRequest,
    UniversalResult,
    cybersecurity_run_with_ucja,
    cybersecurity_translate_from_universal,
    cybersecurity_translate_to_universal,
)


def _request(**overrides) -> SecOpsRequest:
    base = dict(
        kind=SecOpsActionKind.INCIDENT_RESPONSE,
        summary="suspicious lateral movement",
        incident_id="INC-001",
        lead_analyst="alice",
        escalation_chain=("ir-mgr",),
        affected_assets=("host-001",),
        severity="medium",
        cvss_score=Decimal("5.5"),
        data_classifications=(),
        regulatory_regime=(),
        jurisdiction="US",
        acceptance_criteria=("playbook_followed",),
        active_threat=False,
        data_exfil_suspected=False,
        is_emergency=False,
        blast_radius="host",
    )
    base.update(overrides)
    return SecOpsRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in SecOpsActionKind:
        uni = cybersecurity_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_analyst_and_escalation():
    uni = cybersecurity_translate_to_universal(
        _request(escalation_chain=("ir-mgr", "ciso")),
    )
    assert "analyst:alice" in uni.authority_required
    assert "escalation:ir-mgr" in uni.authority_required
    assert "escalation:ciso" in uni.authority_required


def test_translate_observers_include_ciso_for_high_severity():
    uni = cybersecurity_translate_to_universal(_request(severity="critical"))
    assert "ciso_attestation" in uni.observer_required

    uni_high = cybersecurity_translate_to_universal(_request(severity="high"))
    assert "ciso_attestation" in uni_high.observer_required

    uni_med = cybersecurity_translate_to_universal(_request(severity="medium"))
    assert "ciso_attestation" not in uni_med.observer_required


def test_translate_observers_include_data_class_and_regulator():
    uni = cybersecurity_translate_to_universal(
        _request(
            data_classifications=("PII", "PHI"),
            regulatory_regime=("GDPR", "HIPAA"),
        ),
    )
    assert "data_class:PII" in uni.observer_required
    assert "data_class:PHI" in uni.observer_required
    assert "regulator:GDPR" in uni.observer_required
    assert "regulator:HIPAA" in uni.observer_required


def test_translate_legal_counsel_observer_when_exfil_suspected():
    uni = cybersecurity_translate_to_universal(_request(data_exfil_suspected=True))
    assert "legal_counsel" in uni.observer_required


def test_translate_active_threat_blocks_routine_change():
    uni = cybersecurity_translate_to_universal(
        _request(
            kind=SecOpsActionKind.CHANGE_REVIEW,
            active_threat=True,
            is_emergency=False,
        ),
    )
    atc = [
        c for c in uni.constraint_set
        if c["domain"] == "active_threat_change_freeze"
    ]
    assert len(atc) == 1
    assert atc[0]["violation_response"] == "block"


def test_translate_active_threat_change_escalates_under_emergency():
    uni = cybersecurity_translate_to_universal(
        _request(
            kind=SecOpsActionKind.CHANGE_REVIEW,
            active_threat=True,
            is_emergency=True,
        ),
    )
    atc = [
        c for c in uni.constraint_set
        if c["domain"] == "active_threat_change_freeze"
    ]
    assert atc[0]["violation_response"] == "escalate"


def test_translate_active_threat_does_not_block_response_kinds():
    for kind in (
        SecOpsActionKind.CONTAINMENT,
        SecOpsActionKind.ERADICATION,
        SecOpsActionKind.RECOVERY,
        SecOpsActionKind.FORENSIC_INVESTIGATION,
        SecOpsActionKind.THREAT_HUNTING,
    ):
        uni = cybersecurity_translate_to_universal(
            _request(kind=kind, active_threat=True),
        )
        atc = [
            c for c in uni.constraint_set
            if c["domain"] == "active_threat_change_freeze"
        ]
        assert atc == [], f"{kind.value} should not be frozen"


def test_translate_data_exfil_escalates():
    uni = cybersecurity_translate_to_universal(_request(data_exfil_suspected=True))
    exf = [c for c in uni.constraint_set if c["domain"] == "data_exfiltration"]
    assert len(exf) == 1
    assert exf[0]["violation_response"] == "escalate"


def test_translate_critical_severity_requires_ciso_engagement():
    uni = cybersecurity_translate_to_universal(_request(severity="critical"))
    ciso = [c for c in uni.constraint_set if c["domain"] == "ciso_engagement"]
    assert len(ciso) == 1
    assert ciso[0]["violation_response"] == "escalate"


def test_translate_breach_notification_per_regime():
    uni = cybersecurity_translate_to_universal(
        _request(
            kind=SecOpsActionKind.BREACH_NOTIFICATION,
            regulatory_regime=("GDPR", "HIPAA"),
            data_classifications=("PII",),
        ),
    )
    bn = [c for c in uni.constraint_set if c["domain"] == "breach_notification"]
    assert len(bn) == 2
    assert all(c["violation_response"] == "escalate" for c in bn)


def test_translate_invalid_severity_rejected():
    with pytest.raises(ValueError, match="severity"):
        cybersecurity_translate_to_universal(_request(severity="catastrophic"))


def test_translate_cvss_out_of_range_rejected():
    with pytest.raises(ValueError, match="cvss_score"):
        cybersecurity_translate_to_universal(_request(cvss_score=Decimal("11")))


def test_translate_blast_radius_to_permeability():
    cases = {
        "host":         "closed",
        "tenant":       "selective",
        "enterprise":   "selective",
        "supply_chain": "open",
    }
    for blast, expected in cases.items():
        uni = cybersecurity_translate_to_universal(_request(blast_radius=blast))
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


def test_routine_change_during_active_threat_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(kind=SecOpsActionKind.CHANGE_REVIEW, active_threat=True),
    )
    assert any(
        "routine_change_review_during_active_threat" in f
        for f in out.risk_flags
    )


def test_data_exfil_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(data_exfil_suspected=True),
    )
    assert any(
        "data_exfiltration_suspected" in f for f in out.risk_flags
    )


def test_critical_severity_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(severity="critical"),
    )
    assert any("critical_severity" in f for f in out.risk_flags)


def test_emergency_mode_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(is_emergency=True),
    )
    assert any("emergency_mode" in f for f in out.risk_flags)


def test_supply_chain_blast_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(blast_radius="supply_chain"),
    )
    assert any("supply_chain_blast_radius" in f for f in out.risk_flags)


def test_breach_notification_irreversible_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(kind=SecOpsActionKind.BREACH_NOTIFICATION),
    )
    assert any(
        "breach_notification_irreversible" in f for f in out.risk_flags
    )


def test_eradication_evidence_warning_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(kind=SecOpsActionKind.ERADICATION),
    )
    assert any(
        "eradication_may_destroy_evidence" in f for f in out.risk_flags
    )


def test_forensic_without_assets_flagged():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(
            kind=SecOpsActionKind.FORENSIC_INVESTIGATION,
            affected_assets=(),
        ),
    )
    assert any(
        "forensic_investigation_without_affected_assets" in f
        for f in out.risk_flags
    )


def test_protocol_critical_engages_ciso():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(severity="critical"),
    )
    assert any("Engage CISO" in s for s in out.response_protocol)


def test_protocol_containment_isolates_hosts():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(kind=SecOpsActionKind.CONTAINMENT),
    )
    assert any("Isolate" in s for s in out.response_protocol)


def test_protocol_breach_notification_files_with_regulators():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(kind=SecOpsActionKind.BREACH_NOTIFICATION),
    )
    assert any(
        "File breach notification" in s for s in out.response_protocol
    )


def test_protocol_emergency_change_under_threat_invokes_ecab():
    out = cybersecurity_translate_from_universal(
        _result(),
        _request(
            kind=SecOpsActionKind.CHANGE_REVIEW,
            active_threat=True,
            is_emergency=True,
        ),
    )
    assert any("ECAB" in s for s in out.response_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = cybersecurity_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "analyst: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = cybersecurity_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_critical_containment_with_active_threat_passes():
    out = cybersecurity_run_with_ucja(
        _request(
            kind=SecOpsActionKind.CONTAINMENT,
            severity="critical",
            cvss_score=Decimal("9.8"),
            active_threat=True,
            data_exfil_suspected=True,
            data_classifications=("PII",),
            regulatory_regime=("GDPR",),
            is_emergency=True,
            escalation_chain=("ir-mgr", "ciso"),
            acceptance_criteria=("hosts_isolated", "credentials_rotated"),
        ),
    )
    assert out.governance_status == "approved"
    assert out.active_threat is True
    assert out.is_emergency is True


def test_result_carries_active_threat_and_emergency_flags():
    out = cybersecurity_run_with_ucja(
        _request(active_threat=False, is_emergency=False),
    )
    assert out.active_threat is False
    assert out.is_emergency is False
