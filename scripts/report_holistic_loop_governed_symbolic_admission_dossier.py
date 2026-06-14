"""Report the governed symbolic holistic loop admission dossier.

Purpose: expose a read-only admission dossier for the governed symbolic loop
candidate and its registry admission state.
Governance scope: proposed loop manifest, evidence readiness, authority
readiness, closure-condition readiness, rollback readiness, learning policy
readiness, and non-registration boundary.
Dependencies: holistic loop contracts, candidate map reporter, and
repository-local governed symbolic loop proof surfaces.
Invariants:
  - The dossier is read-only and deterministic.
  - The dossier does not mutate the governed symbolic loop registration.
  - The dossier does not execute or rewrite runtime behavior.
  - Real mode is not registered for the governed symbolic loop.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.holistic_loop import LoopManifest, LoopMode, LoopPhase  # noqa: E402
from mcoi_runtime.core.holistic_loop_registry import build_default_loop_registry  # noqa: E402
from scripts.report_holistic_loop_candidate_map import (  # noqa: E402
    REGISTRATION_DECISION_BLOCKER,
    candidate_loop_catalog,
)


DOSSIER_ID = "holistic_loop_governed_symbolic_admission_dossier"
DOSSIER_VERSION = "holistic_loop_governed_symbolic_admission_dossier.v1"
CANDIDATE_ID = "governed_symbolic_loop"
ADMISSION_STATUS_READY = "ready_for_operator_decision"


def _governed_symbolic_candidate() -> Any:
    for candidate in candidate_loop_catalog():
        if candidate.candidate_id == CANDIDATE_ID:
            return candidate
    raise RuntimeError(f"candidate not found: {CANDIDATE_ID}")


def _relative_path_exists(path_text: str) -> bool:
    return (WORKSPACE_ROOT / path_text).exists()


def _proposed_manifest(*, registered: bool) -> dict[str, Any]:
    candidate = _governed_symbolic_candidate()
    manifest = LoopManifest(
        loop_id=candidate.candidate_id,
        name=candidate.name,
        purpose=candidate.purpose,
        owner=candidate.owner,
        risk_class=candidate.risk_class,
        allowed_modes=(
            LoopMode.DRY_RUN,
            LoopMode.SHADOW,
            LoopMode.SIMULATION,
            LoopMode.REPLAY,
        ),
        required_authority=candidate.proposed_required_authority,
        required_evidence=candidate.proposed_required_evidence,
        closure_conditions=candidate.proposed_closure_conditions,
        rollback_policy=candidate.proposed_rollback_policy,
        learning_policy=candidate.proposed_learning_policy,
        canonical_steps=(
            LoopPhase.OBSERVE,
            LoopPhase.DECIDE,
            LoopPhase.ACT,
            LoopPhase.VERIFY,
            LoopPhase.RECORD_RECEIPT,
            LoopPhase.UPDATE_STATE,
            LoopPhase.LEARN,
            LoopPhase.AUDIT,
        ),
        metadata={
            "source_candidate_map": "scripts/report_holistic_loop_candidate_map.py",
            "behavior_rewrite": False,
            "registered": registered,
            "operator_decision_required": not registered,
            "real_mode_registered": False,
        },
    )
    return manifest.to_json_dict()


def _existing_surface_refs() -> tuple[str, ...]:
    return (
        "schemas/governed_symbolic_loop_contract.schema.json",
        "examples/governed_symbolic_loop_contract.foundation.json",
        "examples/sdlc/requirement_governed_symbolic_loop_20260614.json",
        "examples/sdlc/design_governed_symbolic_loop_20260614.json",
        "scripts/validate_governed_symbolic_loop_contract.py",
        "tests/test_validate_governed_symbolic_loop_contract.py",
        "schemas/universal_action_orchestration.schema.json",
        "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
        "schemas/life_meaning_judgment.schema.json",
        "docs/LIFE_MEANING_GOVERNANCE_KERNEL.md",
        "scripts/validate_life_meaning_governance.py",
        "scripts/validate_sdlc_artifact.py",
        "scripts/validate_holistic_loop_extension_admission.py",
    )


def build_dossier() -> dict[str, Any]:
    """Build the read-only governed symbolic loop admission dossier."""

    registered_loop_ids = set(build_default_loop_registry().manifests)
    registered = CANDIDATE_ID in registered_loop_ids
    proposed_manifest = _proposed_manifest(registered=registered)
    existing_surface_refs = _existing_surface_refs()
    return {
        "dossier_id": DOSSIER_ID,
        "dossier_version": DOSSIER_VERSION,
        "candidate_id": CANDIDATE_ID,
        "admission_status": "registered" if registered else ADMISSION_STATUS_READY,
        "admission_blockers": [] if registered else [REGISTRATION_DECISION_BLOCKER],
        "next_action": "already_registered" if registered else "operator_registration_decision",
        "registered": registered,
        "read_only": True,
        "mutation_route": False,
        "runtime_behavior_change": False,
        "behavior_rewrite": False,
        "terminal_closure": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "registration_effect": {
            "registers_loop": False,
            "registry_mutation": False,
            "runtime_behavior_change": False,
        },
        "operator_decision_report": {
            "decision_required": not registered,
            "decision_status": (
                "satisfied_by_default_registry_admission" if registered else "missing"
            ),
            "decision_ref": f"default_registry:{CANDIDATE_ID}" if registered else "",
            "blocks_registration": not registered,
        },
        "proposed_manifest": proposed_manifest,
        "existing_surface_refs": list(existing_surface_refs),
        "evidence_gap_report": {
            "status": "complete",
            "required_evidence": list(proposed_manifest["required_evidence"]),
            "satisfied_evidence": {
                "problem_star_compilation_receipt": [
                    "schemas/governed_symbolic_loop_contract.schema.json",
                    "examples/governed_symbolic_loop_contract.foundation.json",
                ],
                "action_classification_receipt": [
                    "schemas/governed_symbolic_loop_contract.schema.json",
                    "examples/governed_symbolic_loop_contract.foundation.json",
                ],
                "capability_admission_receipt": [
                    "schemas/universal_action_orchestration.schema.json",
                    "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
                ],
                "verification_receipt": [
                    "scripts/validate_governed_symbolic_loop_contract.py",
                    "tests/test_validate_governed_symbolic_loop_contract.py",
                    "scripts/validate_sdlc_artifact.py",
                ],
                "rollback_or_recovery_handoff_receipt": [
                    "examples/sdlc/design_governed_symbolic_loop_20260614.json",
                    "scripts/validate_sdlc_artifact.py",
                ],
                "learning_admission_receipt": [
                    "schemas/governed_symbolic_loop_contract.schema.json",
                    "schemas/learning_admission.schema.json",
                ],
            },
            "missing_evidence": [],
        },
        "authority_gap_report": {
            "status": "complete",
            "required_authority": list(proposed_manifest["required_authority"]),
            "satisfied_authority": {
                "uao_policy_ref": [
                    "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
                    "scripts/validate_universal_action_orchestration.py",
                ],
                "phi_gov_authority_ref": [
                    "AGENTS.md",
                    "scripts/validate_agents_governance.py",
                ],
                "life_meaning_judgment_ref": [
                    "schemas/life_meaning_judgment.schema.json",
                    "scripts/validate_life_meaning_governance.py",
                ],
                "operator_registration_decision_ref": [
                    "scripts/validate_holistic_loop_extension_admission.py",
                    "scripts/report_holistic_loop_candidate_map.py",
                ],
            },
            "missing_authority": [],
        },
        "closure_condition_gap_report": {
            "status": "complete",
            "closure_conditions": list(proposed_manifest["closure_conditions"]),
            "satisfied_conditions": {
                "canonical_episode_phases_preserved": [
                    "examples/governed_symbolic_loop_contract.foundation.json",
                    "tests/test_validate_governed_symbolic_loop_contract.py",
                ],
                "deterministic_kernel_boundaries_preserved": [
                    "examples/sdlc/design_governed_symbolic_loop_20260614.json",
                    "scripts/validate_sdlc_artifact.py",
                ],
                "runtime_authority_denials_preserved": [
                    "schemas/universal_action_orchestration.schema.json",
                    "scripts/validate_holistic_loop_extension_admission.py",
                ],
                "post_verification_learning_preserved": [
                    "schemas/learning_admission.schema.json",
                    "schemas/life_meaning_judgment.schema.json",
                ],
            },
            "missing_closure_conditions": [],
        },
        "rollback_readiness": {
            "status": "ready",
            "rollback_available": True,
            "rollback_policy": proposed_manifest["rollback_policy"],
            "evidence_refs": [
                "mcoi/mcoi_runtime/core/holistic_loop_registry.py",
                "schemas/governed_symbolic_loop_contract.schema.json",
                "examples/sdlc/design_governed_symbolic_loop_20260614.json",
            ],
        },
        "learning_policy_readiness": {
            "status": "ready",
            "learning_policy": proposed_manifest["learning_policy"],
            "learning_candidates": [
                "loop_guard_regressions",
                "proof_receipt_gap_patterns",
                "runtime_authority_denial_regressions",
            ],
        },
    }


def validate_dossier(dossier: dict[str, Any] | None = None) -> list[str]:
    """Return validation errors for the governed symbolic loop admission dossier."""

    report = dossier or build_dossier()
    errors: list[str] = []
    if report.get("dossier_id") != DOSSIER_ID:
        errors.append("dossier_id is invalid")
    if report.get("dossier_version") != DOSSIER_VERSION:
        errors.append("dossier_version is invalid")
    if report.get("candidate_id") != CANDIDATE_ID:
        errors.append("candidate_id must be governed_symbolic_loop")
    registered_loop_ids = set(build_default_loop_registry().manifests)
    expected_registered = CANDIDATE_ID in registered_loop_ids
    if report.get("registered") is not expected_registered:
        errors.append("dossier registered state must match default registry")
    if expected_registered:
        if report.get("admission_status") != "registered":
            errors.append("admission_status must be registered after admission")
        if report.get("admission_blockers") != []:
            errors.append("admission_blockers must be empty after admission")
    else:
        if report.get("admission_status") != ADMISSION_STATUS_READY:
            errors.append("admission_status must remain ready_for_operator_decision")
        if REGISTRATION_DECISION_BLOCKER not in report.get("admission_blockers", []):
            errors.append("operator registration decision blocker is required")
    for field_name, expected in (
        ("read_only", True),
        ("mutation_route", False),
        ("runtime_behavior_change", False),
        ("behavior_rewrite", False),
        ("terminal_closure", False),
        ("report_is_not_terminal_closure", True),
        ("terminal_closure_required", True),
    ):
        if report.get(field_name) is not expected:
            errors.append(f"dossier {field_name} must be {expected}")

    registration_effect = report.get("registration_effect")
    if not isinstance(registration_effect, dict):
        errors.append("registration_effect must be present")
    else:
        for field_name in ("registers_loop", "registry_mutation", "runtime_behavior_change"):
            if registration_effect.get(field_name) is not False:
                errors.append(f"registration_effect {field_name} must be false")

    operator_decision = report.get("operator_decision_report")
    if not isinstance(operator_decision, dict):
        errors.append("operator_decision_report must be present")
    else:
        if expected_registered:
            if operator_decision.get("decision_required") is not False:
                errors.append("operator decision must not be required after admission")
            if operator_decision.get("decision_status") != "satisfied_by_default_registry_admission":
                errors.append("operator decision status must report registry admission")
            if operator_decision.get("decision_ref") != f"default_registry:{CANDIDATE_ID}":
                errors.append("operator decision ref must match default registry admission")
            if operator_decision.get("blocks_registration") is not False:
                errors.append("operator decision must not block after admission")
        else:
            if operator_decision.get("decision_required") is not True:
                errors.append("operator decision must be required")
            if operator_decision.get("decision_status") != "missing":
                errors.append("operator decision status must remain missing")
            if operator_decision.get("decision_ref"):
                errors.append("operator decision ref must remain empty before admission")
            if operator_decision.get("blocks_registration") is not True:
                errors.append("operator decision must block registration")

    errors.extend(_validate_manifest(report.get("proposed_manifest")))
    errors.extend(_validate_existing_surfaces(report.get("existing_surface_refs")))
    errors.extend(
        _validate_gap_report(
            report,
            "evidence_gap_report",
            "required_evidence",
            "satisfied_evidence",
            "missing_evidence",
        )
    )
    errors.extend(
        _validate_gap_report(
            report,
            "authority_gap_report",
            "required_authority",
            "satisfied_authority",
            "missing_authority",
        )
    )
    errors.extend(
        _validate_gap_report(
            report,
            "closure_condition_gap_report",
            "closure_conditions",
            "satisfied_conditions",
            "missing_closure_conditions",
        )
    )
    errors.extend(_validate_readiness_report(report, "rollback_readiness"))
    errors.extend(_validate_readiness_report(report, "learning_policy_readiness"))
    return errors


def _validate_manifest(manifest: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["proposed_manifest must be present"]
    expected_fields = (
        "loop_id",
        "name",
        "purpose",
        "owner",
        "risk_class",
        "allowed_modes",
        "required_authority",
        "required_evidence",
        "closure_conditions",
        "rollback_policy",
        "learning_policy",
        "canonical_steps",
    )
    for field_name in expected_fields:
        value = manifest.get(field_name)
        if isinstance(value, list):
            if not value:
                errors.append(f"proposed_manifest {field_name} must not be empty")
        elif not str(value or "").strip():
            errors.append(f"proposed_manifest {field_name} must not be empty")
    if manifest.get("loop_id") != CANDIDATE_ID:
        errors.append("proposed_manifest loop_id must match candidate_id")
    if manifest.get("metadata", {}).get("behavior_rewrite") is not False:
        errors.append("proposed_manifest metadata behavior_rewrite must be false")
    if manifest.get("metadata", {}).get("real_mode_registered") is not False:
        errors.append("proposed_manifest metadata real_mode_registered must be false")
    if "real" in manifest.get("allowed_modes", []):
        errors.append("proposed_manifest must not register real mode")
    return errors


def _validate_existing_surfaces(surface_refs: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(surface_refs, list) or not surface_refs:
        return ["existing_surface_refs must be a non-empty list"]
    for surface_ref in surface_refs:
        if not isinstance(surface_ref, str) or not surface_ref.strip():
            errors.append("existing_surface_refs entries must be non-empty strings")
        elif not _relative_path_exists(surface_ref):
            errors.append(f"missing surface: {surface_ref}")
    return errors


def _validate_gap_report(
    report: dict[str, Any],
    report_name: str,
    required_field: str,
    satisfied_field: str,
    missing_field: str,
) -> list[str]:
    section = report.get(report_name)
    if not isinstance(section, dict):
        return [f"{report_name} must be present"]
    errors: list[str] = []
    if section.get("status") != "complete":
        errors.append(f"{report_name} status must be complete")
    if section.get(missing_field) != []:
        errors.append(f"{report_name} {missing_field} must be empty")
    manifest = report.get("proposed_manifest")
    expected_refs = ()
    if isinstance(manifest, dict):
        manifest_refs = manifest.get(required_field)
        if isinstance(manifest_refs, list):
            expected_refs = tuple(str(ref) for ref in manifest_refs)
    reported_refs = section.get(required_field)
    if tuple(reported_refs or ()) != expected_refs:
        errors.append(f"{report_name} {required_field} must match proposed_manifest")
    satisfied_refs = section.get(satisfied_field)
    if not isinstance(satisfied_refs, dict):
        errors.append(f"{report_name} {satisfied_field} must be an object")
        return errors
    missing_satisfied_refs = sorted(set(expected_refs) - set(satisfied_refs))
    extra_satisfied_refs = sorted(set(satisfied_refs) - set(expected_refs))
    for ref in missing_satisfied_refs:
        errors.append(f"{report_name} {satisfied_field} missing {ref}")
    for ref in extra_satisfied_refs:
        errors.append(f"{report_name} {satisfied_field} has unexpected {ref}")
    for ref, evidence_refs in satisfied_refs.items():
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"{report_name} {satisfied_field}.{ref} must be a non-empty list")
            continue
        for evidence_ref in evidence_refs:
            if not isinstance(evidence_ref, str) or not evidence_ref.strip():
                errors.append(f"{report_name} {satisfied_field}.{ref} entries must be non-empty strings")
            elif not _relative_path_exists(evidence_ref):
                errors.append(f"{report_name} {satisfied_field}.{ref} missing surface: {evidence_ref}")
    return errors


def _validate_readiness_report(report: dict[str, Any], report_name: str) -> list[str]:
    section = report.get(report_name)
    if not isinstance(section, dict):
        return [f"{report_name} must be present"]
    errors: list[str] = []
    if section.get("status") != "ready":
        errors.append(f"{report_name} status must be ready")
    if report_name == "rollback_readiness" and section.get("rollback_available") is not True:
        errors.append("rollback_readiness rollback_available must be true")
    return errors


def render_dossier(dossier: dict[str, Any], stream: TextIO) -> None:
    """Render a compact human-readable dossier summary."""

    stream.write(
        "STATUS: "
        f"{dossier['admission_status']}; "
        f"candidate={dossier['candidate_id']}; "
        f"real_mode_registered={dossier['proposed_manifest']['metadata']['real_mode_registered']}; "
        f"admission_blockers={len(dossier['admission_blockers'])}\n"
    )
    stream.write(
        f"[{dossier['admission_status']}] "
        f"{dossier['proposed_manifest']['name']}: "
        f"next={dossier['next_action']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Emit the governed symbolic loop admission dossier."""

    parser = argparse.ArgumentParser(
        description="Report the governed symbolic holistic loop admission dossier."
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    dossier = build_dossier()
    errors = validate_dossier(dossier)
    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] {error}\n")
        return 1
    if args.json:
        json.dump(dossier, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        render_dossier(dossier, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
