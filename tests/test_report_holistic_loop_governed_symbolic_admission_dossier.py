"""Test the governed symbolic holistic loop admission dossier.

Purpose: verify the governed symbolic loop admission dossier remains read-only,
non-mutating, no-real-mode, and evidence-backed.
Governance scope: registry-admission boundary, proposed manifest, authority
and evidence gap reports, rollback readiness, and terminal-closure separation.
Dependencies: scripts.report_holistic_loop_governed_symbolic_admission_dossier.
Invariants:
  - Governed symbolic admission dossier reports default registry admission.
  - Governed symbolic admission dossier does not mutate loop registration.
  - Real mode is not registered for the governed symbolic loop.
  - Evidence, authority, closure, rollback, and learning gaps stay explicit.
"""

from __future__ import annotations

import copy

from scripts import report_holistic_loop_governed_symbolic_admission_dossier as reporter


def test_governed_symbolic_admission_dossier_builds_proposed_manifest() -> None:
    dossier = reporter.build_dossier()
    errors = reporter.validate_dossier(dossier)
    manifest = dossier["proposed_manifest"]

    assert errors == []
    assert dossier["candidate_id"] == "governed_symbolic_loop"
    assert manifest["loop_id"] == dossier["candidate_id"]
    assert "real" not in manifest["allowed_modes"]
    assert "dry_run" in manifest["allowed_modes"]
    assert manifest["metadata"]["behavior_rewrite"] is False
    assert manifest["metadata"]["real_mode_registered"] is False
    assert manifest["metadata"]["registered"] is True


def test_governed_symbolic_admission_dossier_reports_registry_admission() -> None:
    dossier = reporter.build_dossier()
    operator_decision = dossier["operator_decision_report"]

    assert dossier["admission_status"] == "registered"
    assert dossier["admission_blockers"] == []
    assert dossier["next_action"] == "already_registered"
    assert operator_decision["decision_required"] is False
    assert operator_decision["decision_status"] == "satisfied_by_default_registry_admission"
    assert operator_decision["decision_ref"] == "default_registry:governed_symbolic_loop"
    assert operator_decision["blocks_registration"] is False


def test_governed_symbolic_admission_dossier_does_not_register_or_mutate_runtime() -> None:
    dossier = reporter.build_dossier()
    registered_loop_ids = set(reporter.build_default_loop_registry().manifests)
    registration_effect = dossier["registration_effect"]

    assert dossier["candidate_id"] in registered_loop_ids
    assert dossier["registered"] is True
    assert registration_effect["registers_loop"] is False
    assert registration_effect["registry_mutation"] is False
    assert registration_effect["runtime_behavior_change"] is False
    assert dossier["runtime_behavior_change"] is False


def test_governed_symbolic_admission_dossier_reports_complete_readiness_sections() -> None:
    dossier = reporter.build_dossier()

    assert dossier["evidence_gap_report"]["missing_evidence"] == []
    assert dossier["authority_gap_report"]["missing_authority"] == []
    assert dossier["closure_condition_gap_report"]["missing_closure_conditions"] == []
    assert dossier["rollback_readiness"]["status"] == "ready"
    assert dossier["rollback_readiness"]["rollback_available"] is True
    assert dossier["learning_policy_readiness"]["status"] == "ready"


def test_governed_symbolic_admission_dossier_rejects_registration_or_terminal_claim() -> None:
    dossier = reporter.build_dossier()
    invalid_dossier = copy.deepcopy(dossier)
    invalid_dossier["registered"] = False
    invalid_dossier["registration_effect"]["registers_loop"] = True
    invalid_dossier["terminal_closure"] = True

    errors = reporter.validate_dossier(invalid_dossier)

    assert "dossier registered state must match default registry" in errors
    assert "registration_effect registers_loop must be false" in errors
    assert "dossier terminal_closure must be False" in errors


def test_governed_symbolic_admission_dossier_rejects_real_mode_or_gap_regression() -> None:
    dossier = reporter.build_dossier()
    invalid_dossier = copy.deepcopy(dossier)
    invalid_dossier["proposed_manifest"]["allowed_modes"].append("real")
    invalid_dossier["proposed_manifest"]["metadata"]["real_mode_registered"] = True
    invalid_dossier["existing_surface_refs"].append("missing/governed_symbolic_surface.json")
    invalid_dossier["evidence_gap_report"]["missing_evidence"] = ["verification_receipt"]
    del invalid_dossier["evidence_gap_report"]["satisfied_evidence"]["verification_receipt"]
    invalid_dossier["authority_gap_report"]["satisfied_authority"]["uao_policy_ref"].append(
        "missing/uao_policy_ref.md"
    )
    invalid_dossier["rollback_readiness"]["rollback_available"] = False

    errors = reporter.validate_dossier(invalid_dossier)

    assert "proposed_manifest must not register real mode" in errors
    assert "proposed_manifest metadata real_mode_registered must be false" in errors
    assert "missing surface: missing/governed_symbolic_surface.json" in errors
    assert "evidence_gap_report missing_evidence must be empty" in errors
    assert "evidence_gap_report satisfied_evidence missing verification_receipt" in errors
    assert (
        "authority_gap_report satisfied_authority.uao_policy_ref missing surface: "
        "missing/uao_policy_ref.md"
    ) in errors
    assert "rollback_readiness rollback_available must be true" in errors
