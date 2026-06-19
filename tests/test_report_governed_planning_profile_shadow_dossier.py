"""Tests for GovernedPlanningProfile shadow dossier reporting.

Purpose: verify representative gateway plan classes are projected into
read-only planning-profile admission reports without runtime promotion.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: scripts.report_governed_planning_profile_shadow_dossier and
governed planning profile schemas.
Invariants: dossier generation is deterministic, no report grants execution
authority, and nested admission reports remain schema-compatible.
"""

from __future__ import annotations

import copy

from scripts import report_governed_planning_profile_shadow_dossier as reporter
from scripts.validate_schemas import _load_schema, _validate_schema_instance


def test_shadow_dossier_covers_expected_plan_classes_without_authority() -> None:
    dossier = reporter.build_shadow_dossier()
    errors = reporter.validate_shadow_dossier(dossier)
    scenario_classes = {scenario["plan_class"] for scenario in dossier["scenarios"]}

    assert errors == []
    assert dossier["status"] == "verified"
    assert dossier["scenario_count"] == 5
    assert dossier["report_count"] == 5
    assert dossier["missing_plan_classes"] == []
    assert scenario_classes == set(reporter.EXPECTED_PLAN_CLASSES)
    assert dossier["execution_allowed"] is False
    assert dossier["dispatch_allowed"] is False
    assert dossier["runtime_replanning_enabled"] is False
    assert dossier["terminal_closure"] is False
    assert dossier["success_claim_allowed"] is False
    assert dossier["solver_outcome"] == "AwaitingEvidence"


def test_shadow_dossier_schema_accepts_dossier_and_nested_reports() -> None:
    dossier = reporter.build_shadow_dossier()
    dossier_schema = _load_schema(
        reporter.WORKSPACE_ROOT / "schemas" / "governed_planning_profile_shadow_dossier.schema.json"
    )
    report_schema = _load_schema(
        reporter.WORKSPACE_ROOT / "schemas" / "governed_planning_profile_admission_report.schema.json"
    )

    dossier_errors = _validate_schema_instance(dossier_schema, dossier)
    nested_errors = [
        error
        for report in dossier["admission_reports"]
        for error in _validate_schema_instance(report_schema, report)
    ]

    assert dossier_errors == []
    assert nested_errors == []
    assert dossier["dossier_id"].startswith("governed-planning-profile-shadow-dossier-")
    assert len(dossier["dossier_hash"]) == 64
    assert all(report["solver_outcome"] == "AwaitingEvidence" for report in dossier["admission_reports"])


def test_shadow_dossier_records_distinct_blocker_shapes() -> None:
    dossier = reporter.build_shadow_dossier()
    by_class = {scenario["plan_class"]: scenario for scenario in dossier["scenarios"]}
    reports_by_id = {
        report["report_id"]: report
        for report in dossier["admission_reports"]
    }
    compound_report = reports_by_id[by_class["compound_search_notification"]["admission_report_id"]]
    payment_report = reports_by_id[by_class["high_risk_payment"]["admission_report_id"]]
    contradiction_report = reports_by_id[by_class["world_contradiction_search"]["admission_report_id"]]

    assert by_class["uncompiled_conversation"]["step_count"] == 0
    assert by_class["read_only_search"]["step_count"] == 1
    assert by_class["compound_search_notification"]["step_count"] == 2
    assert by_class["high_risk_payment"]["risk_tier"] == "high"
    assert by_class["world_contradiction_search"]["required_control_count"] == 1
    assert any(finding["category"] == "authority" for finding in compound_report["promotion_blockers"])
    assert any(
        "approval_obligation_count:1" == finding["observed_ref"]
        for finding in payment_report["promotion_blockers"]
    )
    assert any("required_controls:1" == finding["observed_ref"] for finding in payment_report["promotion_blockers"])
    assert any("required_controls:1" == finding["observed_ref"] for finding in contradiction_report["promotion_blockers"])


def test_shadow_dossier_rejects_runtime_authority_claim() -> None:
    dossier = reporter.build_shadow_dossier()
    invalid_dossier = copy.deepcopy(dossier)
    invalid_dossier["execution_allowed"] = True
    invalid_dossier["admission_reports"][0]["projection"]["execution_allowed"] = True

    errors = reporter.validate_shadow_dossier(invalid_dossier)

    assert "shadow dossier execution_allowed must be False" in errors
    assert "shadow dossier report execution_allowed must be false" in errors
    assert "shadow dossier status must match validation result" in errors
    assert invalid_dossier["admission_reports"][0]["projection"]["execution_allowed"] is True
