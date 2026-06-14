#!/usr/bin/env python3
"""Validate holistic loop extension admission.

Purpose: prove every default holistic loop registration remains read-only,
blocker-aware, non-terminal, and proof-anchored before extension.
Governance scope: default loop registry admission, manifest completeness,
state blocker semantics, closure boundary, and proof witness anchoring.
Dependencies: holistic loop registry, read-model reporter, and proof coverage
matrix.
Invariants:
  - Validation is read-only and deterministic.
  - Default loop registrations must not execute or mutate runtime behavior.
  - Missing authority or evidence is always reported as a blocker.
  - Admission evidence is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.core.holistic_loop_registry import (  # noqa: E402
    LoopRegistry,
    build_default_loop_registry,
)
from scripts.proof_coverage_matrix import (  # noqa: E402
    proof_coverage_matrix,
    witness_integrity_report,
)
from scripts.report_holistic_loop_read_model import build_report  # noqa: E402


HOLISTIC_SURFACE_ID = "holistic_loop_read_model_kernel"
RECEIPT_ID = "holistic_loop_extension_admission_validation"
REQUIRED_LOOP_IDS = (
    "audit_proof_verification_loop",
    "authority_obligation_loop",
    "universal_action_orchestration_loop",
    "workflow_execution_loop",
    "deployment_witness_loop",
    "runtime_conformance_loop",
    "cognitive_outcome_loop",
    "governed_code_change_loop",
    "governed_symbolic_loop",
)


def _as_tuple(values: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(values)


def validate_manifest_admission(registry: LoopRegistry) -> list[str]:
    """Return manifest admission errors for the default loop registry."""

    errors: list[str] = []
    manifests = registry.list_manifests()
    loop_ids = tuple(manifest.loop_id for manifest in manifests)
    if loop_ids != tuple(sorted(loop_ids)):
        errors.append("registered loop ids must be deterministic and sorted")
    if set(REQUIRED_LOOP_IDS) - set(loop_ids):
        missing = sorted(set(REQUIRED_LOOP_IDS) - set(loop_ids))
        errors.append("default registry missing required loop ids: " + ", ".join(missing))
    if len(loop_ids) != len(set(loop_ids)):
        errors.append("default registry contains duplicate loop ids")

    for manifest in manifests:
        prefix = f"loop {manifest.loop_id}"
        if not manifest.required_authority:
            errors.append(f"{prefix} must declare required authority")
        if not manifest.required_evidence:
            errors.append(f"{prefix} must declare required evidence")
        if not manifest.closure_conditions:
            errors.append(f"{prefix} must declare closure conditions")
        if not manifest.rollback_policy:
            errors.append(f"{prefix} must declare rollback policy")
        if not manifest.learning_policy:
            errors.append(f"{prefix} must declare learning policy")
        if manifest.metadata.get("behavior_rewrite") is not False:
            errors.append(f"{prefix} metadata behavior_rewrite must be false")
        if "existing_surfaces" not in manifest.metadata:
            errors.append(f"{prefix} metadata must cite existing surfaces")
        if not manifest.canonical_steps:
            errors.append(f"{prefix} must declare canonical loop steps")
        if not manifest.allowed_modes:
            errors.append(f"{prefix} must declare allowed modes")
    return errors


def validate_summary_admission(report: dict[str, Any]) -> list[str]:
    """Return read-model summary admission errors for default loops."""

    errors: list[str] = []
    loops = report.get("loops")
    if not isinstance(loops, list):
        return ["read model report loops must be a list"]
    if report.get("report_is_not_terminal_closure") is not True:
        errors.append("read model report must not be a terminal closure certificate")
    if report.get("terminal_closure_required") is not True:
        errors.append("read model report must require terminal closure")

    for loop in loops:
        if not isinstance(loop, dict):
            errors.append("read model loop summary must be an object")
            continue
        loop_id = loop.get("loop_id")
        prefix = f"loop {loop_id}"
        missing_authority = _as_tuple(loop.get("missing_authority", ()))
        missing_evidence = _as_tuple(loop.get("missing_evidence", ()))
        open_blockers = _as_tuple(loop.get("open_blockers", ()))
        required_authority = _as_tuple(loop.get("required_authority", ()))
        required_evidence = _as_tuple(loop.get("required_evidence", ()))
        closure_conditions = _as_tuple(loop.get("closure_conditions", ()))
        if set(missing_authority) != set(required_authority):
            errors.append(f"{prefix} missing authority must match required authority for admission")
        if set(missing_evidence) != set(required_evidence):
            errors.append(f"{prefix} missing evidence must match required evidence for admission")
        expected_blockers = {
            *(f"missing_authority:{authority}" for authority in missing_authority),
            *(f"missing_evidence:{evidence}" for evidence in missing_evidence),
        }
        if not expected_blockers.issubset(set(open_blockers)):
            errors.append(f"{prefix} open blockers must include all missing authority and evidence")
        if loop.get("status") != "blocked":
            errors.append(f"{prefix} admission baseline must remain blocked until evidence is observed")
        errors.extend(_validate_nested_read_only_boundaries(loop, prefix))
        closure_report = loop.get("closure_report")
        if not isinstance(closure_report, dict):
            errors.append(f"{prefix} closure report must be present")
        elif closure_report.get("closed") is not False:
            errors.append(f"{prefix} closure report must not claim closure")
        if not closure_conditions:
            errors.append(f"{prefix} must expose closure conditions")
    return errors


def _validate_nested_read_only_boundaries(loop: dict[str, Any], prefix: str) -> list[str]:
    """Return errors when nested read-model records become effect-bearing."""

    errors: list[str] = []
    object_fields = (
        "status_binding",
        "mode_binding",
        "risk_binding",
        "rollback_binding",
        "learning_binding",
        "closure_evidence_pack",
        "operator_closure_readiness_view",
        "proof_obligation_view",
        "audit_evolution_view",
        "recovery_readiness_view",
    )
    list_fields = (
        "transition_bindings",
        "closure_condition_bindings",
        "authority_bindings",
        "evidence_bindings",
        "receipt_lineage_bindings",
    )
    for field_name in object_fields:
        value = loop.get(field_name)
        if not isinstance(value, dict):
            errors.append(f"{prefix} {field_name} must be present")
            continue
        errors.extend(_validate_read_only_record(value, f"{prefix} {field_name}"))
    for field_name in list_fields:
        values = loop.get(field_name)
        if not isinstance(values, list) or not values:
            errors.append(f"{prefix} {field_name} must be a non-empty list")
            continue
        for index, value in enumerate(values):
            if not isinstance(value, dict):
                errors.append(f"{prefix} {field_name}[{index}] must be an object")
                continue
            errors.extend(_validate_read_only_record(value, f"{prefix} {field_name}[{index}]"))
    for index, receipt in enumerate(loop.get("step_receipts", ())):
        if not isinstance(receipt, dict):
            errors.append(f"{prefix} step_receipts[{index}] must be an object")
            continue
        if receipt.get("status") == "closed":
            errors.append(f"{prefix} step_receipts[{index}] must not claim closure")
    return errors


def _validate_read_only_record(record: dict[str, Any], label: str) -> list[str]:
    """Return errors for read-model records that lose read-only boundaries."""

    errors: list[str] = []
    if record.get("read_only") is not True:
        errors.append(f"{label} must be read-only")
    if record.get("terminal_closure") is not False:
        errors.append(f"{label} must not claim terminal closure")
    return errors


def validate_proof_anchor_admission(matrix: dict[str, Any] | None = None) -> list[str]:
    """Return proof anchoring errors for the holistic loop admission surface."""

    current_matrix = matrix or proof_coverage_matrix()
    surfaces = current_matrix.get("surfaces")
    if not isinstance(surfaces, list):
        return ["proof matrix surfaces must be a list"]
    surface = next(
        (
            candidate
            for candidate in surfaces
            if isinstance(candidate, dict) and candidate.get("surface_id") == HOLISTIC_SURFACE_ID
        ),
        None,
    )
    if surface is None:
        return ["holistic loop proof surface is missing"]
    runtime_witnesses = surface.get("runtime_witnesses", [])
    if "holistic_loop_extension_admission_guards_default_registry" not in runtime_witnesses:
        return ["holistic loop extension admission witness is missing from proof matrix"]
    integrity = witness_integrity_report(surfaces)
    surface_records = {
        record.get("surface_id"): record
        for record in integrity.get("surfaces", [])
        if isinstance(record, dict)
    }
    holistic_record = surface_records.get(HOLISTIC_SURFACE_ID)
    if not isinstance(holistic_record, dict):
        return ["holistic loop witness integrity record is missing"]
    if holistic_record.get("unanchored_witness_count") != 0:
        return ["holistic loop proof surface has unanchored witness labels"]
    return []


def validate_extension_admission(
    *,
    registry: LoopRegistry | None = None,
    report: dict[str, Any] | None = None,
    matrix: dict[str, Any] | None = None,
) -> list[str]:
    """Validate default holistic loop extension admission."""

    current_registry = registry or build_default_loop_registry()
    current_report = report or build_report()
    errors: list[str] = []
    errors.extend(validate_manifest_admission(current_registry))
    errors.extend(validate_summary_admission(current_report))
    errors.extend(validate_proof_anchor_admission(matrix))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate default holistic loop extension admission."""

    parser = argparse.ArgumentParser(description="Validate holistic loop extension admission.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)

    errors = validate_extension_admission()
    receipt = {
        "receipt_id": RECEIPT_ID,
        "status": "passed" if not errors else "blocked",
        "valid": not errors,
        "surface_id": HOLISTIC_SURFACE_ID,
        "registered_loop_ids": list(REQUIRED_LOOP_IDS),
        "receipt_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "errors": errors,
    }
    if args.json:
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 0 if receipt["valid"] else 1
    if errors:
        for error in errors:
            sys.stderr.write(f"[BLOCKED] holistic-loop-extension-admission: {error}\n")
        sys.stderr.write("STATUS: blocked\n")
        return 1
    sys.stdout.write("[PASS] holistic_loop_extension_admission_guards_default_registry\n")
    sys.stdout.write("[PASS] holistic_loop_extension_admission_preserves_blockers\n")
    sys.stdout.write("[PASS] holistic_loop_extension_admission_is_not_terminal_closure\n")
    sys.stdout.write("[PASS] holistic_loop_extension_admission_is_proof_anchored\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
