"""End-to-end domain adapter test — full SCCCE round trip."""
from __future__ import annotations

from mcoi_runtime.domain_adapters.software_dev import (
    SoftwareRequest,
    SoftwareWorkKind,
    run_with_cognitive_cycle,
)


def test_e2e_bug_fix_round_trip():
    req = SoftwareRequest(
        kind=SoftwareWorkKind.BUG_FIX,
        summary="fix budget enforcement leak",
        repository="mullu-control-plane",
        target_branch="main",
        affected_files=("mcoi/mcoi_runtime/core/tenant_budget.py",),
        acceptance_criteria=(
            "budget_leak_test_passes",
            "no_regression_in_existing_tests",
        ),
        blast_radius="module",
        reviewer_required=True,
    )

    result = run_with_cognitive_cycle(req)

    assert result.governance_status == "approved"
    assert "code_reviewer" in result.required_reviewers
    # Plan contains expected steps based on construct counts the cycle produced
    assert any("Read current state" in step for step in result.work_plan)
    assert any("Infer required changes" in step for step in result.work_plan)
    assert any("transformations" in step for step in result.work_plan)
    assert any("validation suite" in step for step in result.work_plan)


def test_e2e_feature_request_no_reviewer():
    req = SoftwareRequest(
        kind=SoftwareWorkKind.FEATURE,
        summary="add export endpoint",
        repository="x",
        affected_files=("a.py",),
        acceptance_criteria=("works",),
        blast_radius="function",
        reviewer_required=False,
    )

    result = run_with_cognitive_cycle(req)
    assert result.governance_status == "approved"
    assert result.required_reviewers == ()


def test_e2e_deploy_appends_rollback_step():
    req = SoftwareRequest(
        kind=SoftwareWorkKind.DEPLOY,
        summary="deploy v4.1.0",
        repository="x",
        affected_files=("infra/manifest.yaml",),
        acceptance_criteria=("manifest_validated",),
        blast_radius="service",
        reviewer_required=True,
    )

    result = run_with_cognitive_cycle(req)
    assert any("rollback" in step.lower() for step in result.work_plan)


def test_e2e_no_acceptance_criteria_still_works():
    req = SoftwareRequest(
        kind=SoftwareWorkKind.INVESTIGATE,
        summary="figure out flakiness",
        repository="x",
        affected_files=(),
        acceptance_criteria=(),
        reviewer_required=False,
    )
    result = run_with_cognitive_cycle(req)
    # No acceptance criteria → plan still has plausible steps
    assert isinstance(result.work_plan, tuple)
