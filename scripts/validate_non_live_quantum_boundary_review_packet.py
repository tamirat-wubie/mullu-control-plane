#!/usr/bin/env python3
"""Validate the non-live quantum boundary review packet.

Purpose: enforce review-only closure for the non-live quantum witness stack.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the foundation example.
Invariants: no implementation authority, source emission, simulator runtime
invocation, backend execution, credential access, result claim, or terminal
closure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / "examples" / "non_live_quantum_boundary_review_packet.foundation.json"

REQUIRED_REVIEWED_WITNESSES = {
    "universal_symbolic_quantum_capability_boundary",
    "non_live_openqasm_export_planning_witness",
    "non_live_local_quantum_simulator_boundary_witness",
    "non_live_quantum_fixture_catalog_witness",
    "non_live_quantum_fixture_serializer_boundary_witness",
}

REQUIRED_REVIEW_GATES = {
    "ParentQuantumBoundaryGate",
    "OpenQasmPlanningWitnessGate",
    "LocalSimulatorBoundaryWitnessGate",
    "FixtureCatalogWitnessGate",
    "FixtureSerializerBoundaryWitnessGate",
    "DenialInvariantRetentionGate",
    "NoImplementationAuthorityGate",
    "NoRuntimeExecutionGate",
    "NoSourceEmissionGate",
    "NoCredentialAuthorityGate",
    "FutureSeparatePrGate",
    "WitnessLedgerGate",
}

REQUIRED_ALLOWED_REVIEW_ROLES = {
    "witness_stack_review",
    "denial_invariant_review",
    "future_authority_gap_review",
    "implementation_precondition_review",
    "operator_handoff_review",
}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("implementation_allowed",),
    ("review_boundary", "implementation_authority_allowed"),
    ("review_boundary", "source_emission_allowed"),
    ("review_boundary", "runtime_execution_allowed"),
    ("denied_authorities", "openqasm_exporter_implementation_enabled"),
    ("denied_authorities", "qir_exporter_implementation_enabled"),
    ("denied_authorities", "fixture_catalog_implementation_enabled"),
    ("denied_authorities", "fixture_serializer_implementation_enabled"),
    ("denied_authorities", "simulator_engine_selection_enabled"),
    ("denied_authorities", "simulator_runtime_invocation_enabled"),
    ("denied_authorities", "state_vector_materialization_enabled"),
    ("denied_authorities", "shot_execution_enabled"),
    ("denied_authorities", "measurement_histogram_emission_enabled"),
    ("denied_authorities", "backend_execution_enabled"),
    ("denied_authorities", "hardware_credentials_access_enabled"),
    ("denied_authorities", "quantum_job_submission_enabled"),
    ("denied_authorities", "cryptanalysis_execution_enabled"),
    ("denied_authorities", "quantum_advantage_claim_enabled"),
    ("denied_authorities", "fault_tolerant_readiness_claim_enabled"),
    ("denied_authorities", "production_readiness_claim_enabled"),
    ("denied_authorities", "terminal_closure"),
    ("effect_boundary", "openqasm_source_emitted"),
    ("effect_boundary", "qir_source_emitted"),
    ("effect_boundary", "executable_fixture_written"),
    ("effect_boundary", "fixture_serializer_executed"),
    ("effect_boundary", "serialized_artifact_written"),
    ("effect_boundary", "canonical_bytes_materialized"),
    ("effect_boundary", "simulator_input_generated"),
    ("effect_boundary", "simulator_runtime_invoked"),
    ("effect_boundary", "state_vector_materialized"),
    ("effect_boundary", "measurement_shots_executed"),
    ("effect_boundary", "measurement_histogram_emitted"),
    ("effect_boundary", "backend_called"),
    ("effect_boundary", "hardware_credentials_read"),
    ("effect_boundary", "quantum_job_submitted"),
    ("effect_boundary", "cryptanalysis_executed"),
    ("effect_boundary", "result_distribution_observed"),
    ("effect_boundary", "quantum_advantage_claim_made"),
    ("effect_boundary", "production_claim_made"),
)

FORCED_TRUE_PATHS = (
    ("planning_only",),
    ("read_only",),
    ("witness_stack_reviewed",),
    ("non_live_witness_required",),
    ("future_separate_pr_required",),
    ("review_boundary", "descriptor_only"),
    ("review_boundary", "review_only"),
    ("review_boundary", "requires_future_implementation_witness"),
    ("review_boundary", "requires_operator_authorization"),
    ("review_constraints", "requires_all_child_witnesses_valid"),
    ("review_constraints", "requires_denial_invariant_retention"),
    ("review_constraints", "requires_no_runtime_payload"),
    ("review_constraints", "requires_no_source_artifact"),
    ("review_constraints", "requires_no_credential_material"),
    ("review_constraints", "requires_no_result_distribution"),
    ("review_constraints", "requires_future_authority_pr"),
)


def _get_path(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict) or key not in value:
            raise KeyError(".".join(path))
        value = value[key]
    return value


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _validate_required_set(
    payload: dict[str, Any],
    key: str,
    required_values: set[str],
    errors: list[str],
) -> None:
    value = payload.get(key)
    if not isinstance(value, list):
        errors.append(f"{key} must be a list")
        return
    missing = sorted(required_values.difference(value))
    if missing:
        errors.append(f"{key} missing: {', '.join(missing)}")
    if len(value) != len(set(value)):
        errors.append(f"{key} must not contain duplicates")


def _validate_witness_reviews(payload: dict[str, Any], errors: list[str]) -> None:
    reviews = payload.get("witness_reviews")
    if not isinstance(reviews, list) or len(reviews) != len(REQUIRED_REVIEWED_WITNESSES):
        errors.append("witness_reviews must contain one review per required witness")
        return

    observed_refs: list[str] = []
    forced_false_keys = (
        "implementation_authority_granted",
        "runtime_authority_granted",
        "source_emission_authority_granted",
        "credential_authority_granted",
        "result_claim_authority_granted",
    )
    for index, review in enumerate(reviews):
        prefix = f"witness_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{prefix} must be an object")
            continue
        witness_ref = review.get("witness_ref")
        if not isinstance(witness_ref, str) or not witness_ref:
            errors.append(f"{prefix}.witness_ref must be a non-empty string")
        else:
            observed_refs.append(witness_ref)
        if review.get("review_decision") != "reviewed_as_planning_only":
            errors.append(f"{prefix}.review_decision must be 'reviewed_as_planning_only'")
        for key in forced_false_keys:
            if review.get(key) is not False:
                errors.append(f"{prefix}.{key} must be false")
        if review.get("required_future_authority") is not True:
            errors.append(f"{prefix}.required_future_authority must be true")

    missing_refs = sorted(REQUIRED_REVIEWED_WITNESSES.difference(observed_refs))
    if missing_refs:
        errors.append(f"witness_reviews missing: {', '.join(missing_refs)}")
    if len(observed_refs) != len(set(observed_refs)):
        errors.append("witness_reviews.witness_ref values must be unique")


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_consts = {
        "binding_id": "non_live_quantum_boundary_review_packet",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "parent_boundary_ref": "universal_symbolic_quantum_capability_boundary",
        "architecture_name": "USQCA-PQE",
        "review_status": "NonLiveQuantumBoundaryStackReviewed",
    }
    for key, expected in expected_consts.items():
        if payload.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")

    reviewed = payload.get("reviewed_witness_refs")
    if not isinstance(reviewed, list):
        errors.append("reviewed_witness_refs must be a list")
    else:
        missing_reviewed = sorted(REQUIRED_REVIEWED_WITNESSES.difference(reviewed))
        if missing_reviewed:
            errors.append(f"reviewed_witness_refs missing: {', '.join(missing_reviewed)}")
        if len(reviewed) != len(set(reviewed)):
            errors.append("reviewed_witness_refs must not contain duplicates")

    for path in FORCED_FALSE_PATHS:
        try:
            value = _get_path(payload, path)
        except KeyError:
            errors.append(f"{'.'.join(path)} is required")
            continue
        if value is not False:
            errors.append(f"{'.'.join(path)} must be false")

    for path in FORCED_TRUE_PATHS:
        try:
            value = _get_path(payload, path)
        except KeyError:
            errors.append(f"{'.'.join(path)} is required")
            continue
        if value is not True:
            errors.append(f"{'.'.join(path)} must be true")

    boundary = payload.get("review_boundary")
    if not isinstance(boundary, dict):
        errors.append("review_boundary must be an object")
    else:
        if boundary.get("boundary_family") != "quantum boundary witness stack review packet":
            errors.append("review_boundary.boundary_family must be 'quantum boundary witness stack review packet'")
        if boundary.get("output_path") is not None:
            errors.append("review_boundary.output_path must be null")

    _validate_required_set(payload, "allowed_review_roles", REQUIRED_ALLOWED_REVIEW_ROLES, errors)
    _validate_required_set(payload, "required_review_gates", REQUIRED_REVIEW_GATES, errors)
    _validate_witness_reviews(payload, errors)

    requirements = payload.get("witness_requirements")
    if not isinstance(requirements, list) or len(requirements) < 8:
        errors.append("witness_requirements must contain at least eight entries")
    elif len(requirements) != len(set(requirements)):
        errors.append("witness_requirements must not contain duplicates")

    constructive = payload.get("constructive_deltas")
    fracture = payload.get("fracture_deltas")
    if not isinstance(constructive, list) or len(constructive) < 3:
        errors.append("constructive_deltas must contain at least three entries")
    if not isinstance(fracture, list) or len(fracture) < 8:
        errors.append("fracture_deltas must contain at least eight entries")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--json", action="store_true", help="emit machine-readable validation result")
    args = parser.parse_args(argv)

    path = pathlib.Path(args.path)
    payload = _load_json(path)
    errors = validate_payload(payload)

    if args.json:
        print(json.dumps({"passed": not errors, "errors": errors}, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("NON-LIVE QUANTUM BOUNDARY REVIEW PACKET VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
