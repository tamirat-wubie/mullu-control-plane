"""Purpose: verify holistic loop admission closure reporting.
Governance scope: default loop admission closure, candidate admission closure,
proof-anchor integrity, read-only projection, and terminal-closure separation.
Dependencies: scripts.report_holistic_loop_admission_closure.
Invariants:
  - Admission closure report does not mutate registry or runtime behavior.
  - Admission closure report remains read-only and non-terminal.
  - No pending candidate admission is reported as a verified read-model fact.
  - Proof witness integrity remains anchored before admission closure is claimed.
"""

from __future__ import annotations

import copy

from scripts import report_holistic_loop_admission_closure as reporter


def test_holistic_loop_admission_closure_reports_no_pending_candidates() -> None:
    report = reporter.build_admission_closure_report()
    errors = reporter.validate_admission_closure_report(report)

    assert errors == []
    assert report["status"] == "verified"
    assert report["loop_count"] == 8
    assert report["required_loop_count"] == 8
    assert report["candidate_count"] == 4
    assert report["registered_candidate_count"] == 4
    assert report["blocked_candidate_count"] == 0
    assert report["pending_candidate_ids"] == []
    assert report["unregistered_candidate_ids"] == []
    assert report["next_action"] == "maintain_kernel_v1_freeze"


def test_holistic_loop_admission_closure_is_read_only_non_terminal() -> None:
    report = reporter.build_admission_closure_report()

    assert report["read_only"] is True
    assert report["mutation_route"] is False
    assert report["runtime_behavior_change"] is False
    assert report["report_is_not_terminal_closure"] is True
    assert report["terminal_closure_required"] is True
    assert report["terminal_closure"] is False
    assert report["admission_closure_verified"] is True


def test_holistic_loop_admission_closure_proves_witness_integrity() -> None:
    report = reporter.build_admission_closure_report()
    witness = report["proof_witness_integrity"]
    closure_conditions = report["closure_conditions"]

    assert witness["runtime_witness_count"] == witness["exact_test_anchor_count"]
    assert witness["unanchored_witness_count"] == 0
    assert witness["unanchored_witnesses"] == []
    assert closure_conditions["holistic_proof_labels_anchored"] is True
    assert closure_conditions["extension_admission_valid"] is True
    assert closure_conditions["no_pending_candidate_admissions"] is True


def test_admission_closure_rejects_pending_candidate_claim() -> None:
    report = reporter.build_admission_closure_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["blocked_candidate_count"] = 1
    invalid_report["pending_candidate_ids"] = ["workflow_execution_loop"]
    invalid_report["closure_conditions"]["no_pending_candidate_admissions"] = False
    invalid_report["closure_blockers"] = [
        "closure_condition_failed:no_pending_candidate_admissions"
    ]

    errors = reporter.validate_admission_closure_report(invalid_report)

    assert "blocked_candidate_count must remain zero after admission" in errors
    assert "pending_candidate_ids must be empty after admission" in errors
    assert "closure condition must pass: no_pending_candidate_admissions" in errors
    assert "closure_blockers must be empty after admission" in errors


def test_admission_closure_rejects_terminal_or_mutating_report() -> None:
    report = reporter.build_admission_closure_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["read_only"] = False
    invalid_report["mutation_route"] = True
    invalid_report["runtime_behavior_change"] = True
    invalid_report["terminal_closure"] = True

    errors = reporter.validate_admission_closure_report(invalid_report)

    assert "admission closure read_only must be True" in errors
    assert "admission closure mutation_route must be False" in errors
    assert "admission closure runtime_behavior_change must be False" in errors
    assert "admission closure terminal_closure must be False" in errors


def test_admission_closure_rejects_unanchored_proof_claim() -> None:
    report = reporter.build_admission_closure_report()
    invalid_report = copy.deepcopy(report)
    invalid_report["proof_witness_integrity"]["unanchored_witness_count"] = 1
    invalid_report["proof_witness_integrity"]["unanchored_witnesses"] = [
        "unanchored_claim"
    ]
    invalid_report["closure_conditions"]["holistic_proof_labels_anchored"] = False

    errors = reporter.validate_admission_closure_report(invalid_report)

    assert "proof_witness_integrity must have zero unanchored witnesses" in errors
    assert "closure condition must pass: holistic_proof_labels_anchored" in errors
    assert invalid_report["proof_witness_integrity"]["unanchored_witnesses"] == [
        "unanchored_claim"
    ]
