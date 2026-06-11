"""Purpose: verify the audit/proof holistic loop admission dossier.
Governance scope: audit/proof loop admission readiness, non-registration
boundary, read-only projection, and terminal-closure separation.
Dependencies: scripts.report_holistic_loop_audit_proof_admission_dossier.
Invariants:
  - Audit/proof admission dossier can become ready for operator decision only.
  - Audit/proof admission dossier does not register loops.
  - Audit/proof admission dossier remains read-only and non-terminal.
  - Evidence, authority, closure, rollback, and learning gaps stay explicit.
"""

from __future__ import annotations

import copy

from scripts import report_holistic_loop_audit_proof_admission_dossier as reporter


def test_audit_proof_admission_dossier_builds_proposed_manifest() -> None:
    dossier = reporter.build_dossier()
    errors = reporter.validate_dossier(dossier)
    manifest = dossier["proposed_manifest"]

    assert errors == []
    assert dossier["candidate_id"] == "audit_proof_verification_loop"
    assert manifest["loop_id"] == dossier["candidate_id"]
    assert "real" in manifest["allowed_modes"]
    assert "dry_run" in manifest["allowed_modes"]
    assert manifest["metadata"]["behavior_rewrite"] is False


def test_audit_proof_admission_dossier_is_ready_only_for_operator_decision() -> None:
    dossier = reporter.build_dossier()
    operator_decision = dossier["operator_decision_report"]

    assert dossier["admission_status"] == "ready_for_operator_decision"
    assert reporter.REGISTRATION_DECISION_BLOCKER in dossier["admission_blockers"]
    assert dossier["next_action"] == "operator_registration_decision"
    assert operator_decision["decision_required"] is True
    assert operator_decision["decision_status"] == "missing"
    assert operator_decision["blocks_registration"] is True


def test_audit_proof_admission_dossier_does_not_register_or_mutate_runtime() -> None:
    dossier = reporter.build_dossier()
    registered_loop_ids = set(reporter.build_default_loop_registry().manifests)
    registration_effect = dossier["registration_effect"]

    assert dossier["candidate_id"] not in registered_loop_ids
    assert dossier["registered"] is False
    assert registration_effect["registers_loop"] is False
    assert registration_effect["registry_mutation"] is False
    assert registration_effect["runtime_behavior_change"] is False
    assert dossier["runtime_behavior_change"] is False


def test_audit_proof_admission_dossier_reports_complete_readiness_sections() -> None:
    dossier = reporter.build_dossier()

    assert dossier["evidence_gap_report"]["missing_evidence"] == []
    assert dossier["authority_gap_report"]["missing_authority"] == []
    assert dossier["closure_condition_gap_report"]["missing_closure_conditions"] == []
    assert dossier["rollback_readiness"]["status"] == "ready"
    assert dossier["rollback_readiness"]["rollback_available"] is True
    assert dossier["learning_policy_readiness"]["status"] == "ready"


def test_audit_proof_admission_dossier_rejects_registration_or_terminal_claim() -> None:
    dossier = reporter.build_dossier()
    invalid_dossier = copy.deepcopy(dossier)
    invalid_dossier["registered"] = True
    invalid_dossier["registration_effect"]["registers_loop"] = True
    invalid_dossier["terminal_closure"] = True

    errors = reporter.validate_dossier(invalid_dossier)

    assert "dossier must not claim the loop is registered" in errors
    assert "registration_effect registers_loop must be false" in errors
    assert "dossier must not claim terminal closure" in errors


def test_audit_proof_admission_dossier_rejects_missing_source_or_gap_regression() -> None:
    dossier = reporter.build_dossier()
    invalid_dossier = copy.deepcopy(dossier)
    invalid_dossier["existing_surface_refs"].append("missing/audit_proof_surface.json")
    invalid_dossier["evidence_gap_report"]["missing_evidence"] = ["audit_verification_passed"]
    invalid_dossier["rollback_readiness"]["rollback_available"] = False

    errors = reporter.validate_dossier(invalid_dossier)

    assert "missing surface: missing/audit_proof_surface.json" in errors
    assert "evidence_gap_report missing_evidence must be empty" in errors
    assert "rollback_readiness rollback_available must be true" in errors
