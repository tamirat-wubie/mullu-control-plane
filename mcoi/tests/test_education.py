"""Education domain adapter tests."""
from __future__ import annotations

import pytest
from uuid import uuid4

from mcoi_runtime.domain_adapters import (
    EducationActionKind,
    EducationRequest,
    UniversalResult,
    education_run_with_ucja,
    education_translate_from_universal,
    education_translate_to_universal,
)


def _request(**overrides) -> EducationRequest:
    base = dict(
        kind=EducationActionKind.GRADING,
        summary="grade midterm exam",
        course_id="CS-101",
        instructor="prof-jones",
        curriculum_committee=("dr-bloom",),
        accreditation_body="",
        affected_learners=("student-1", "student-2", "student-3"),
        learning_objectives=("LO1", "LO2"),
        acceptance_criteria=("rubric_applied_uniformly",),
        prerequisite_courses=("CS-099",),
        accessibility_requirements=("extended_time_for_accommodations",),
        blast_radius="course",
    )
    base.update(overrides)
    return EducationRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in EducationActionKind:
        uni = education_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_instructor_and_committee():
    uni = education_translate_to_universal(_request())
    assert "instructor:prof-jones" in uni.authority_required
    assert "committee:dr-bloom" in uni.authority_required


def test_translate_accreditor_only_for_certification_kinds():
    cert = education_translate_to_universal(
        _request(
            kind=EducationActionKind.CERTIFICATION,
            accreditation_body="ABET",
        ),
    )
    assert "accreditor:ABET" in cert.authority_required

    grading = education_translate_to_universal(
        _request(
            kind=EducationActionKind.GRADING,
            accreditation_body="ABET",
        ),
    )
    assert "accreditor:ABET" not in grading.authority_required


def test_translate_prerequisite_constraints_emitted_per_course():
    uni = education_translate_to_universal(
        _request(prerequisite_courses=("CS-100", "MATH-101")),
    )
    pre = [c for c in uni.constraint_set if c["domain"] == "prerequisite"]
    assert len(pre) == 2
    assert all(c["violation_response"] == "escalate" for c in pre)


def test_translate_accessibility_constraints_block():
    uni = education_translate_to_universal(
        _request(accessibility_requirements=("captions", "screen_reader")),
    )
    acc = [c for c in uni.constraint_set if c["domain"] == "accessibility"]
    assert len(acc) == 2
    assert all(c["violation_response"] == "block" for c in acc)


def test_translate_learning_objectives_constraint_warns():
    uni = education_translate_to_universal(
        _request(learning_objectives=("L1", "L2", "L3")),
    )
    lo = [c for c in uni.constraint_set if c["domain"] == "learning_objectives"]
    assert len(lo) == 1
    assert lo[0]["violation_response"] == "warn"
    assert "3" in lo[0]["restriction"]


def test_translate_blast_radius_to_permeability():
    cases = {
        "course":      "closed",
        "program":     "selective",
        "department":  "selective",
        "institution": "open",
    }
    for blast, expected in cases.items():
        uni = education_translate_to_universal(_request(blast_radius=blast))
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


def test_enrollment_without_prerequisites_flagged():
    out = education_translate_from_universal(
        _result(),
        _request(
            kind=EducationActionKind.ENROLLMENT,
            prerequisite_courses=(),
        ),
    )
    assert any("no_prerequisites_declared" in f for f in out.risk_flags)


def test_no_accessibility_flagged_when_learners_exist():
    out = education_translate_from_universal(
        _result(),
        _request(accessibility_requirements=()),
    )
    assert any(
        "no_accessibility_requirements_declared" in f for f in out.risk_flags
    )


def test_certification_without_objectives_flagged():
    out = education_translate_from_universal(
        _result(),
        _request(
            kind=EducationActionKind.CERTIFICATION,
            learning_objectives=(),
            accreditation_body="ABET",
        ),
    )
    assert any(
        "certification_without_learning_objectives" in f for f in out.risk_flags
    )


def test_certification_without_accreditor_flagged():
    out = education_translate_from_universal(
        _result(),
        _request(
            kind=EducationActionKind.CERTIFICATION,
            accreditation_body="",
        ),
    )
    assert any(
        "certification_without_accreditor" in f for f in out.risk_flags
    )


def test_institution_blast_flagged():
    out = education_translate_from_universal(
        _result(),
        _request(blast_radius="institution"),
    )
    assert any("institution_blast_radius" in f for f in out.risk_flags)


def test_certification_irreversible_flag():
    out = education_translate_from_universal(
        _result(),
        _request(
            kind=EducationActionKind.CERTIFICATION,
            accreditation_body="ABET",
        ),
    )
    assert any("certification_irreversible" in f for f in out.risk_flags)


def test_protocol_includes_prerequisite_verification():
    out = education_translate_from_universal(_result(), _request())
    assert any("CS-099" in s for s in out.instructional_protocol)


def test_protocol_includes_accessibility_verification():
    out = education_translate_from_universal(_result(), _request())
    assert any("extended_time" in s for s in out.instructional_protocol)


def test_protocol_certification_includes_credential_step():
    out = education_translate_from_universal(
        _result(),
        _request(
            kind=EducationActionKind.CERTIFICATION,
            accreditation_body="ABET",
        ),
    )
    assert any("Issue credential" in s for s in out.instructional_protocol)


def test_protocol_grade_appeal_includes_registrar_step():
    out = education_translate_from_universal(
        _result(),
        _request(kind=EducationActionKind.GRADE_APPEAL),
    )
    assert any("appeal outcome" in s for s in out.instructional_protocol)


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = education_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "instructor: prof-jones" in out.required_signoffs


def test_run_certification_with_accreditor():
    out = education_run_with_ucja(
        _request(
            kind=EducationActionKind.CERTIFICATION,
            accreditation_body="ABET",
        ),
    )
    assert out.governance_status == "approved"
    assert "accreditor: ABET" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = education_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_result_carries_learning_objectives():
    out = education_run_with_ucja(
        _request(learning_objectives=("LO_A", "LO_B")),
    )
    assert out.learning_objectives == ("LO_A", "LO_B")
