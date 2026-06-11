"""Purpose: verify the holistic loop candidate map report.
Governance scope: future loop candidate discovery, non-registration boundary,
read-only projection, and terminal-closure separation.
Dependencies: scripts.report_holistic_loop_candidate_map.
Invariants:
  - Candidate map lists evidence-backed unregistered loop surfaces.
  - Candidate map does not register loops.
  - Candidate map remains read-only and non-terminal.
  - Candidate blockers are explicit.
"""

from __future__ import annotations

import copy

from scripts import report_holistic_loop_candidate_map as reporter


def test_holistic_loop_candidate_map_lists_unregistered_surfaces() -> None:
    report = reporter.build_candidate_map()
    errors = reporter.validate_candidate_map(report)
    candidate_ids = [candidate["candidate_id"] for candidate in report["candidates"]]

    assert errors == []
    assert candidate_ids == sorted(candidate_ids)
    assert "authority_obligation_loop" in candidate_ids
    assert "workflow_execution_loop" in candidate_ids
    assert "audit_proof_verification_loop" in candidate_ids
    assert "universal_action_orchestration_loop" in candidate_ids


def test_holistic_loop_candidate_map_does_not_register_loops() -> None:
    report = reporter.build_candidate_map()
    registered_loop_ids = set(reporter.build_default_loop_registry().manifests)

    assert report["registered_candidate_count"] == 0
    assert all(candidate["candidate_id"] not in registered_loop_ids for candidate in report["candidates"])
    assert all(candidate["registered"] is False for candidate in report["candidates"])
    assert all(candidate["admission_status"] == "blocked" for candidate in report["candidates"])


def test_holistic_loop_candidate_map_is_read_only_non_terminal() -> None:
    report = reporter.build_candidate_map()

    assert report["read_only"] is True
    assert report["mutation_route"] is False
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True
    assert all(candidate["read_only"] is True for candidate in report["candidates"])
    assert all(candidate["terminal_closure"] is False for candidate in report["candidates"])


def test_candidate_map_rejects_missing_existing_surface() -> None:
    report = reporter.build_candidate_map()
    invalid_report = copy.deepcopy(report)
    invalid_report["candidates"][0]["existing_surfaces"].append("missing/candidate_surface.json")

    errors = reporter.validate_candidate_map(invalid_report)

    assert any("missing surface: missing/candidate_surface.json" in error for error in errors)
    assert invalid_report["candidates"][0]["existing_surfaces"][-1] == "missing/candidate_surface.json"
    assert invalid_report["candidates"][0]["candidate_id"]


def test_candidate_map_rejects_registration_or_closure_claim() -> None:
    report = reporter.build_candidate_map()
    invalid_report = copy.deepcopy(report)
    invalid_candidate = invalid_report["candidates"][0]
    invalid_candidate["registered"] = True
    invalid_candidate["admission_status"] = "registered"
    invalid_candidate["terminal_closure"] = True

    errors = reporter.validate_candidate_map(invalid_report)

    assert any("must remain unregistered" in error for error in errors)
    assert any("must remain blocked until registration" in error for error in errors)
    assert any("terminal_closure must be False" in error for error in errors)


def test_candidate_map_rejects_missing_blocker() -> None:
    report = reporter.build_candidate_map()
    invalid_report = copy.deepcopy(report)
    invalid_candidate = invalid_report["candidates"][0]
    invalid_candidate["admission_blockers"] = [reporter.NOT_REGISTERED_BLOCKER]

    errors = reporter.validate_candidate_map(invalid_report)

    assert any("missing registration decision blocker" in error for error in errors)
    assert reporter.REGISTRATION_DECISION_BLOCKER not in invalid_candidate["admission_blockers"]
    assert reporter.NOT_REGISTERED_BLOCKER in invalid_candidate["admission_blockers"]
