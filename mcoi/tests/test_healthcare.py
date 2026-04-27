"""Healthcare domain adapter tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from mcoi_runtime.domain_adapters import (
    ClinicalActionKind,
    ClinicalRequest,
    UniversalResult,
    healthcare_run_with_ucja,
    healthcare_translate_from_universal,
    healthcare_translate_to_universal,
)


def _request(**overrides) -> ClinicalRequest:
    base = dict(
        kind=ClinicalActionKind.PRESCRIPTION,
        summary="start ACE inhibitor",
        encounter_id="enc-001",
        primary_clinician="dr-smith",
        consulting_specialists=("dr-cardio",),
        patient_consented=True,
        consent_kind="written",
        affected_records=("mrn-12345",),
        acceptance_criteria=("clinical_indication_documented",),
        contraindication_flags=(),
        is_emergency=False,
        high_dose=False,
        blast_radius="encounter",
    )
    base.update(overrides)
    return ClinicalRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in ClinicalActionKind:
        uni = healthcare_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_primary_and_specialists():
    uni = healthcare_translate_to_universal(_request())
    assert "clinician:dr-smith" in uni.authority_required
    assert "specialist:dr-cardio" in uni.authority_required


def test_translate_consent_recorded_appears_in_observers():
    uni = healthcare_translate_to_universal(_request(consent_kind="written"))
    assert any("patient_consent:written" in o for o in uni.observer_required)


def test_translate_no_consent_no_emergency_blocks():
    uni = healthcare_translate_to_universal(
        _request(patient_consented=False, is_emergency=False),
    )
    consent = [c for c in uni.constraint_set if c["domain"] == "patient_consent"]
    assert len(consent) == 1
    assert consent[0]["violation_response"] == "block"


def test_translate_no_consent_with_emergency_warns():
    uni = healthcare_translate_to_universal(
        _request(patient_consented=False, is_emergency=True),
    )
    consent = [c for c in uni.constraint_set if c["domain"] == "patient_consent"]
    assert len(consent) == 1
    assert consent[0]["violation_response"] == "warn"


def test_translate_consent_recorded_no_consent_constraint_emitted():
    uni = healthcare_translate_to_universal(_request(patient_consented=True))
    consent = [c for c in uni.constraint_set if c["domain"] == "patient_consent"]
    assert consent == []


def test_translate_contraindication_constraint_per_flag():
    uni = healthcare_translate_to_universal(
        _request(contraindication_flags=("renal_impairment", "pregnancy")),
    )
    ci = [c for c in uni.constraint_set if c["domain"] == "contraindication"]
    assert len(ci) == 2
    assert all(c["violation_response"] == "escalate" for c in ci)


def test_translate_high_dose_only_for_prescription():
    pres = healthcare_translate_to_universal(
        _request(kind=ClinicalActionKind.PRESCRIPTION, high_dose=True),
    )
    dosage_pres = [c for c in pres.constraint_set if c["domain"] == "dosage"]
    assert len(dosage_pres) == 1

    surg = healthcare_translate_to_universal(
        _request(kind=ClinicalActionKind.SURGERY, high_dose=True),
    )
    dosage_surg = [c for c in surg.constraint_set if c["domain"] == "dosage"]
    assert dosage_surg == []


def test_translate_invalid_consent_kind_rejected():
    with pytest.raises(ValueError, match="consent_kind"):
        healthcare_translate_to_universal(_request(consent_kind="psychic"))


def test_translate_blast_radius_to_permeability():
    cases = {
        "encounter":    "closed",
        "episode":      "selective",
        "longitudinal": "selective",
        "systemic":     "open",
    }
    for blast, expected in cases.items():
        uni = healthcare_translate_to_universal(_request(blast_radius=blast))
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


def test_no_consent_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(patient_consented=False, is_emergency=False),
    )
    assert any("no_patient_consent_recorded" in f for f in out.risk_flags)


def test_emergency_mode_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(patient_consented=False, is_emergency=True),
    )
    assert any("emergency_mode" in f for f in out.risk_flags)


def test_contraindications_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(contraindication_flags=("renal", "pregnancy")),
    )
    assert any("contraindications_present" in f for f in out.risk_flags)


def test_high_dose_prescription_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(kind=ClinicalActionKind.PRESCRIPTION, high_dose=True),
    )
    assert any("high_dose_prescription" in f for f in out.risk_flags)


def test_surgery_without_specialist_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(
            kind=ClinicalActionKind.SURGERY,
            consulting_specialists=(),
        ),
    )
    assert any(
        "surgery_without_specialist_consult" in f for f in out.risk_flags
    )


def test_irreversible_action_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(kind=ClinicalActionKind.SURGERY),
    )
    assert any("surgery_irreversible" in f for f in out.risk_flags)


def test_systemic_blast_flagged():
    out = healthcare_translate_from_universal(
        _result(),
        _request(blast_radius="systemic"),
    )
    assert any("systemic_blast_radius" in f for f in out.risk_flags)


def test_protocol_includes_consent_step_when_consented():
    out = healthcare_translate_from_universal(_result(), _request())
    assert any("written" in s and "consent" in s.lower() for s in out.care_protocol)


def test_protocol_includes_emergency_step_when_no_consent_emergency():
    out = healthcare_translate_from_universal(
        _result(),
        _request(patient_consented=False, is_emergency=True),
    )
    assert any("emergency-mode implied consent" in s for s in out.care_protocol)


def test_protocol_surgery_includes_op_note():
    out = healthcare_translate_from_universal(
        _result(),
        _request(kind=ClinicalActionKind.SURGERY),
    )
    assert any("operative note" in s.lower() for s in out.care_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = healthcare_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "primary: dr-smith" in out.required_clinician_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = healthcare_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_emergency_no_consent_still_runs():
    out = healthcare_run_with_ucja(
        _request(patient_consented=False, is_emergency=True),
    )
    # UCJA still passes (emergency mode permits implied consent at warn level)
    assert out.governance_status == "approved"
    assert out.is_emergency is True


def test_result_carries_consent_and_emergency_flags():
    out = healthcare_run_with_ucja(
        _request(patient_consented=True, is_emergency=False),
    )
    assert out.consent_recorded is True
    assert out.is_emergency is False
