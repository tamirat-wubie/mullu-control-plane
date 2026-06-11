#!/usr/bin/env python3
"""Report the UAO holistic loop admission dossier.

Purpose: expose a read-only admission dossier for the Universal Action
Orchestration loop candidate before any operator registration decision.
Governance scope: proposed loop manifest, evidence readiness, authority
readiness, closure-condition readiness, rollback readiness, learning policy
readiness, and non-registration boundary.
Dependencies: holistic loop contracts, candidate map reporter, and
repository-local Universal Action Orchestration proof surfaces.
Invariants:
  - The dossier is read-only and deterministic.
  - The dossier does not register the UAO loop.
  - The dossier does not execute or rewrite UAO runtime behavior.
  - Operator registration remains a required blocker before admission.
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


DOSSIER_ID = "holistic_loop_uao_admission_dossier"
DOSSIER_VERSION = "holistic_loop_uao_admission_dossier.v1"
CANDIDATE_ID = "universal_action_orchestration_loop"
OPERATOR_DECISION_REF = "operator_registration_decision_ref"
ADMISSION_STATUS_READY = "ready_for_operator_decision"


def _uao_candidate() -> Any:
    for candidate in candidate_loop_catalog():
        if candidate.candidate_id == CANDIDATE_ID:
            return candidate
    raise RuntimeError(f"candidate not found: {CANDIDATE_ID}")


def _relative_path_exists(path_text: str) -> bool:
    return (WORKSPACE_ROOT / path_text).exists()


def _proposed_manifest() -> dict[str, Any]:
    candidate = _uao_candidate()
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
            LoopMode.REAL,
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
            "registered": False,
            "operator_decision_required": True,
        },
    )
    return manifest.to_json_dict()


def _existing_surface_refs() -> tuple[str, ...]:
    return (
        "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
        "schemas/universal_action_orchestration.schema.json",
        "schemas/universal_action_orchestration_validation_receipt.schema.json",
        "scripts/validate_universal_action_orchestration.py",
        "scripts/validate_universal_action_orchestration_receipt.py",
        "scripts/validate_universal_action_orchestration_receipt_contract.py",
        "scripts/detect_uao_runtime_bypass.py",
        "tests/test_validate_universal_action_orchestration.py",
        "tests/test_validate_universal_action_orchestration_receipt.py",
        "tests/test_validate_universal_action_orchestration_receipt_contract.py",
        "tests/test_detect_uao_runtime_bypass.py",
        "mcoi/mcoi_runtime/core/universal_action_kernel.py",
        "mcoi/tests/test_universal_action_kernel.py",
        "examples/universal_action_orchestration.allowed_status_publish.json",
        "examples/universal_action_orchestration.blocked_invoice_payment.json",
        "examples/uao/blocked_missing_approval.json",
        "examples/uao/deferred_stale_evidence.json",
        "examples/uao/simulated_low_risk_readonly.json",
    )


def build_dossier() -> dict[str, Any]:
    """Build the read-only UAO admission dossier."""

    registered_loop_ids = set(build_default_loop_registry().manifests)
    proposed_manifest = _proposed_manifest()
    registered = CANDIDATE_ID in registered_loop_ids
    existing_surface_refs = _existing_surface_refs()
    return {
        "dossier_id": DOSSIER_ID,
        "dossier_version": DOSSIER_VERSION,
        "candidate_id": CANDIDATE_ID,
        "admission_status": ADMISSION_STATUS_READY,
        "admission_blockers": [REGISTRATION_DECISION_BLOCKER],
        "next_action": "operator_registration_decision",
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
            "decision_required": True,
            "decision_status": "missing",
            "decision_ref": "",
            "blocks_registration": True,
        },
        "proposed_manifest": proposed_manifest,
        "existing_surface_refs": list(existing_surface_refs),
        "evidence_gap_report": {
            "status": "complete",
            "required_evidence": list(proposed_manifest["required_evidence"]),
            "satisfied_evidence": {
                "action_admission_receipt_valid": [
                    "scripts/validate_universal_action_orchestration.py",
                    "tests/test_validate_universal_action_orchestration.py",
                    "examples/universal_action_orchestration.allowed_status_publish.json",
                    "examples/universal_action_orchestration.blocked_invoice_payment.json",
                ],
                "no_bypass_detector_passed": [
                    "scripts/detect_uao_runtime_bypass.py",
                    "tests/test_detect_uao_runtime_bypass.py",
                ],
                "replay_or_rollback_ref_present": [
                    "docs/UNIVERSAL_ACTION_ORCHESTRATION.md",
                    "mcoi/mcoi_runtime/core/universal_action_kernel.py",
                    "mcoi/tests/test_universal_action_kernel.py",
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
                    "scripts/validate_agents_governance.py",
                ],
            },
            "missing_authority": [],
        },
        "closure_condition_gap_report": {
            "status": "complete",
            "closure_conditions": list(proposed_manifest["closure_conditions"]),
            "satisfied_conditions": {
                "effect_reconciled": [
                    "schemas/universal_action_orchestration.schema.json",
                    "examples/universal_action_orchestration.allowed_status_publish.json",
                ],
                "receipt_and_memory_deltas_recorded": [
                    "schemas/universal_action_orchestration_validation_receipt.schema.json",
                    "docs/universal-action-orchestration-validation-receipt-example.json",
                ],
            },
            "missing_closure_conditions": [],
        },
        "rollback_readiness": {
            "status": "ready",
            "rollback_available": True,
            "rollback_policy": proposed_manifest["rollback_policy"],
            "evidence_refs": [
                "scripts/validate_universal_action_orchestration.py",
                "examples/uao/blocked_missing_approval.json",
                "examples/uao/deferred_stale_evidence.json",
            ],
        },
        "learning_policy_readiness": {
            "status": "ready",
            "learning_policy": proposed_manifest["learning_policy"],
            "learning_candidates": [
                "rejected_action_causes",
                "runtime_bypass_findings",
                "stale_evidence_deferrals",
            ],
        },
    }


def validate_dossier(dossier: dict[str, Any] | None = None) -> list[str]:
    """Return validation errors for the UAO admission dossier."""

    report = dossier or build_dossier()
    errors: list[str] = []
    if report.get("dossier_id") != DOSSIER_ID:
        errors.append("dossier_id is invalid")
    if report.get("dossier_version") != DOSSIER_VERSION:
        errors.append("dossier_version is invalid")
    if report.get("candidate_id") != CANDIDATE_ID:
        errors.append("candidate_id must be universal_action_orchestration_loop")
    if report.get("admission_status") != ADMISSION_STATUS_READY:
        errors.append("admission_status must remain ready_for_operator_decision")
    if REGISTRATION_DECISION_BLOCKER not in report.get("admission_blockers", []):
        errors.append("operator registration decision blocker is required")
    if report.get("registered") is not False:
        errors.append("dossier must not claim the loop is registered")
    if report.get("read_only") is not True:
        errors.append("dossier must be read-only")
    if report.get("mutation_route") is not False:
        errors.append("dossier must not expose a mutation route")
    if report.get("runtime_behavior_change") is not False:
        errors.append("dossier must not change runtime behavior")
    if report.get("behavior_rewrite") is not False:
        errors.append("dossier must not rewrite behavior")
    if report.get("terminal_closure") is not False:
        errors.append("dossier must not claim terminal closure")
    if report.get("report_is_not_terminal_closure") is not True:
        errors.append("dossier report must not be terminal closure")
    if report.get("terminal_closure_required") is not True:
        errors.append("dossier must require terminal closure before admission")

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
    errors.extend(_validate_gap_report(report, "evidence_gap_report", "missing_evidence"))
    errors.extend(_validate_gap_report(report, "authority_gap_report", "missing_authority"))
    errors.extend(
        _validate_gap_report(
            report,
            "closure_condition_gap_report",
            "missing_closure_conditions",
        )
    )
    errors.extend(_validate_readiness_report(report, "rollback_readiness"))
    errors.extend(_validate_readiness_report(report, "learning_policy_readiness"))

    registered_loop_ids = set(build_default_loop_registry().manifests)
    if CANDIDATE_ID in registered_loop_ids:
        errors.append("default registry must not include the UAO candidate")
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
    if manifest.get("metadata", {}).get("registered") is not False:
        errors.append("proposed_manifest metadata registered must be false")
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


def _validate_gap_report(report: dict[str, Any], report_name: str, missing_field: str) -> list[str]:
    section = report.get(report_name)
    if not isinstance(section, dict):
        return [f"{report_name} must be present"]
    errors: list[str] = []
    if section.get("status") != "complete":
        errors.append(f"{report_name} status must be complete")
    if section.get(missing_field) != []:
        errors.append(f"{report_name} {missing_field} must be empty")
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
        f"evidence_gaps={len(dossier['evidence_gap_report']['missing_evidence'])}; "
        f"admission_blockers={len(dossier['admission_blockers'])}\n"
    )
    stream.write(
        f"[{dossier['admission_status']}] "
        f"{dossier['proposed_manifest']['name']}: "
        f"next={dossier['next_action']}\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Emit the UAO admission dossier."""

    parser = argparse.ArgumentParser(description="Report the UAO holistic loop admission dossier.")
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
