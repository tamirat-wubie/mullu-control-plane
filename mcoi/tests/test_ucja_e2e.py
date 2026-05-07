"""End-to-end UCJA → SCCCE → domain result test."""
from __future__ import annotations

from mcoi_runtime.domain_adapters import (
    SoftwareRequest,
    SoftwareWorkKind,
    software_run_with_ucja,
)


def test_ucja_e2e_complete_request_passes_through():
    req = SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="fix auth issue",
        repository="x",
        affected_files=("auth.py",),
        acceptance_criteria=("auth_test_passes",),
        blast_radius="module",
        reviewer_required=True,
    )
    result = software_run_with_ucja(req)
    assert result.governance_status == "approved"
    assert any("Read current state" in s for s in result.work_plan)


def test_ucja_e2e_no_acceptance_criteria_blocks_at_l9():
    """L9 reclassifies when there are no acceptance criteria."""
    req = SoftwareRequest(
        kind=SoftwareWorkKind.FEATURE,
        summary="add thing",
        repository="x",
        affected_files=("a.py",),
        acceptance_criteria=(),  # blank
        blast_radius="module",
        reviewer_required=False,
    )
    result = software_run_with_ucja(req)
    # UCJA halted before SCCCE → governance_status reflects the gate verdict
    assert "Unknown" in result.governance_status or "blocked" in result.governance_status


def test_ucja_e2e_unknown_after_reclassify():
    """Reclassify maps to Unknown proof state — distinct from Fail."""
    req = SoftwareRequest(
        kind=SoftwareWorkKind.FEATURE,
        summary="something",
        repository="x",
        affected_files=("a.py",),
        acceptance_criteria=(),
        blast_radius="module",
    )
    result = software_run_with_ucja(req)
    assert "Unknown" in result.governance_status
