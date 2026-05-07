"""Tests for deterministic red-team release harness.

Purpose: verify adversarial release-gate scoring across injection, budget, audit, and policy cases.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: red-team harness core module.
Invariants: reports are deterministic, all default cases pass, and failed cases reduce pass rate.
"""
from __future__ import annotations

from mcoi_runtime.core.red_team_harness import RedTeamCase, RedTeamHarness, default_red_team_cases


def test_default_red_team_harness_passes_all_cases() -> None:
    report = RedTeamHarness().run()

    assert report["suite_id"] == "mullu-red-team-release-gate-v1"
    assert report["mode"] == "offline_deterministic"
    assert report["case_count"] == 8
    assert report["passed_count"] == 8
    assert report["failed_count"] == 0
    assert report["pass_rate"] == 1.0
    assert report["report_hash"].startswith("sha256:")


def test_red_team_harness_report_is_deterministic() -> None:
    first_report = RedTeamHarness().run()
    second_report = RedTeamHarness().run()

    assert first_report == second_report
    assert len(first_report["category_summary"]) == 4
    assert first_report["category_summary"]["prompt_injection"]["pass_rate"] == 1.0
    assert first_report["category_summary"]["budget_evasion"]["pass_rate"] == 1.0
    assert first_report["category_summary"]["audit_tampering"]["pass_rate"] == 1.0
    assert first_report["category_summary"]["policy_bypass"]["pass_rate"] == 1.0


def test_red_team_default_cases_cover_required_categories() -> None:
    cases = default_red_team_cases()
    categories = {case.category for case in cases}
    case_ids = {case.case_id for case in cases}

    assert categories == {"prompt_injection", "budget_evasion", "audit_tampering", "policy_bypass"}
    assert len(cases) == 8
    assert len(case_ids) == len(cases)
    assert all(case.expected_reason for case in cases)
    assert all(case.payload for case in cases)


def test_red_team_harness_failed_expectation_reduces_pass_rate() -> None:
    case = RedTeamCase(
        case_id="rt-negative-001",
        category="audit_tampering",
        title="Intentionally wrong expectation",
        payload={
            "original": {"event": "policy_denied", "tenant_id": "tenant-a"},
            "tampered": {"event": "policy_allowed", "tenant_id": "tenant-a"},
        },
        expected_reason="audit_tampering_missed",
    )

    report = RedTeamHarness((case,)).run()

    assert report["case_count"] == 1
    assert report["passed_count"] == 0
    assert report["failed_count"] == 1
    assert report["pass_rate"] == 0.0
    assert report["results"][0]["observed_reason"] == "audit_hash_mismatch_detected"
