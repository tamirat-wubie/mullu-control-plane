#!/usr/bin/env python3
"""Validate the non-live quantum fixture serializer authority requirements witness.

Purpose: enforce the future-authority requirements-only contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the foundation example.
Invariants: no serializer implementation, no serializer execution, no serialized
fixture artifact, no canonical runtime bytes, no source serialization, no
simulator input serialization, no runtime invocation, no backend calls, no
credentials, no result claims, and no terminal closure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = (
    ROOT / "examples" / "non_live_quantum_fixture_serializer_authority_requirements_witness.foundation.json"
)

REQUIRED_RELATED_WITNESSES = {
    "non_live_openqasm_export_planning_witness",
    "non_live_local_quantum_simulator_boundary_witness",
    "non_live_quantum_fixture_catalog_witness",
    "non_live_quantum_fixture_serializer_boundary_witness",
}

REQUIRED_AUTHORITY_GATES = {
    "ParentQuantumBoundaryGate",
    "FixtureCatalogWitnessGate",
    "SerializerBoundaryGate",
    "AuthorityRequirementsDeclarationGate",
    "SeparateImplementationChangeGate",
    "OperatorAuthorizationGate",
    "IsolationProfileGate",
    "OutputPathPolicyGate",
    "RuntimeDenialGuardGate",
    "ReceiptAndRollbackGate",
    "ResultClaimPolicyGate",
    "NoImplementationEffectGate",
    "NoRuntimeExecutionGate",
    "WitnessLedgerGate",
}

REQUIRED_ALLOWED_REQUIREMENT_CATEGORIES = {
    "implementation_admission_requirement",
    "schema_contract_requirement",
    "isolation_profile_requirement",
    "output_path_policy_requirement",
    "canonicalization_determinism_requirement",
    "runtime_denial_guard_requirement",
    "receipt_and_rollback_requirement",
    "result_claim_policy_requirement",
    "operator_authorization_requirement",
}

REQUIRED_DENIED_CURRENT_AUTHORITIES = {
    "serializer_implementation",
    "fixture_serializer_execution",
    "serialized_fixture_artifact_generation",
    "canonical_runtime_bytes_emission",
    "openqasm_source_serialization",
    "qir_source_serialization",
    "simulator_input_serialization",
    "runtime_payload_generation",
    "backend_execution",
    "credential_access",
    "quantum_job_submission",
    "result_distribution_claim",
    "quantum_advantage_claim",
    "production_readiness_claim",
}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("authority_requirements_boundary", "implementation_allowed"),
    ("authority_requirements_boundary", "serializer_execution_allowed"),
    ("authority_requirements_boundary", "artifact_writes_allowed"),
    ("authority_requirements_boundary", "runtime_payload_allowed"),
    ("authority_requirements_boundary", "operator_authorization_granted"),
    ("denied_authorities", "serializer_implementation_enabled"),
    ("denied_authorities", "fixture_serializer_execution_enabled"),
    ("denied_authorities", "serialized_fixture_artifact_generation_enabled"),
    ("denied_authorities", "executable_fixture_serialization_enabled"),
    ("denied_authorities", "canonical_runtime_bytes_emission_enabled"),
    ("denied_authorities", "openqasm_source_serialization_enabled"),
    ("denied_authorities", "qir_source_serialization_enabled"),
    ("denied_authorities", "simulator_input_serialization_enabled"),
    ("denied_authorities", "runtime_payload_generation_enabled"),
    ("denied_authorities", "simulator_runtime_invocation_enabled"),
    ("denied_authorities", "state_vector_materialization_enabled"),
    ("denied_authorities", "shot_execution_enabled"),
    ("denied_authorities", "measurement_histogram_emission_enabled"),
    ("denied_authorities", "backend_execution_enabled"),
    ("denied_authorities", "hardware_credentials_access_enabled"),
    ("denied_authorities", "quantum_job_submission_enabled"),
    ("denied_authorities", "cryptanalysis_execution_enabled"),
    ("denied_authorities", "quantum_advantage_claim_enabled"),
    ("denied_authorities", "production_readiness_claim_enabled"),
    ("denied_authorities", "terminal_closure"),
    ("effect_boundary", "implementation_file_written"),
    ("effect_boundary", "serializer_executed"),
    ("effect_boundary", "serialized_artifact_written"),
    ("effect_boundary", "canonical_json_emitted"),
    ("effect_boundary", "canonical_bytes_materialized"),
    ("effect_boundary", "executable_fixture_serialized"),
    ("effect_boundary", "openqasm_source_text_serialized"),
    ("effect_boundary", "qir_source_text_serialized"),
    ("effect_boundary", "simulator_input_serialized"),
    ("effect_boundary", "runtime_payload_written"),
    ("effect_boundary", "simulator_runtime_invoked"),
    ("effect_boundary", "state_vector_materialized"),
    ("effect_boundary", "amplitude_table_materialized"),
    ("effect_boundary", "measurement_shots_executed"),
    ("effect_boundary", "measurement_histogram_emitted"),
    ("effect_boundary", "backend_called"),
    ("effect_boundary", "hardware_credentials_read"),
    ("effect_boundary", "quantum_job_submitted"),
    ("effect_boundary", "result_distribution_observed"),
    ("effect_boundary", "production_claim_made"),
)

FORCED_TRUE_PATHS = (
    ("requirements_only",),
    ("planning_only",),
    ("read_only",),
    ("parent_boundary_required",),
    ("fixture_catalog_witness_required",),
    ("serializer_boundary_witness_required",),
    ("non_live_witness_required",),
    ("authority_requirements_boundary", "requirements_only"),
    ("authority_requirements_boundary", "requires_separate_pr"),
    ("authority_requirements_boundary", "requires_explicit_operator_authorization"),
    ("authority_requirements_boundary", "requires_isolation_profile"),
    ("authority_requirements_boundary", "requires_output_path_policy"),
    ("authority_requirements_boundary", "requires_runtime_denial_guard"),
    ("authority_requirements_boundary", "requires_receipt_schema"),
    ("authority_requirements_boundary", "requires_rollback_plan"),
    ("authority_requirements_boundary", "requires_result_claim_policy"),
    ("authority_requirement_constraints", "requires_serializer_boundary_ref"),
    ("authority_requirement_constraints", "requires_requirement_id"),
    ("authority_requirement_constraints", "requires_future_evidence_ref"),
    ("authority_requirement_constraints", "requires_denial_if_missing"),
    ("authority_requirement_constraints", "requires_no_current_authority_satisfaction"),
    ("authority_requirement_constraints", "requires_no_implementation_effect"),
    ("authority_requirement_constraints", "requires_no_runtime_payload"),
    ("authority_requirement_constraints", "requires_operator_authorization_before_future_implementation"),
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


def _validate_authority_requirements(payload: dict[str, Any], errors: list[str]) -> None:
    requirements = payload.get("authority_requirements")
    categories = payload.get("allowed_requirement_categories")
    if not isinstance(requirements, list) or len(requirements) < 8:
        errors.append("authority_requirements must contain at least eight entries")
        return
    if not isinstance(categories, list):
        errors.append("allowed_requirement_categories must be a list before requirement validation")
        return

    allowed_categories = set(categories)
    requirement_ids: list[str] = []
    required_keys = {
        "requirement_id",
        "category",
        "requirement",
        "required_evidence",
        "denial_if_missing",
        "future_evidence_required",
        "current_witness_satisfies_authority",
    }
    for index, requirement in enumerate(requirements):
        prefix = f"authority_requirements[{index}]"
        if not isinstance(requirement, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing_keys = sorted(required_keys.difference(requirement))
        if missing_keys:
            errors.append(f"{prefix} missing: {', '.join(missing_keys)}")
            continue
        requirement_id = requirement["requirement_id"]
        if not isinstance(requirement_id, str) or not requirement_id:
            errors.append(f"{prefix}.requirement_id must be a non-empty string")
        else:
            requirement_ids.append(requirement_id)
        if requirement["category"] not in allowed_categories:
            errors.append(f"{prefix}.category must reference an allowed requirement category")
        for key in ("requirement", "required_evidence", "denial_if_missing"):
            if not isinstance(requirement[key], str) or not requirement[key]:
                errors.append(f"{prefix}.{key} must be a non-empty string")
        if requirement["future_evidence_required"] is not True:
            errors.append(f"{prefix}.future_evidence_required must be true")
        if requirement["current_witness_satisfies_authority"] is not False:
            errors.append(f"{prefix}.current_witness_satisfies_authority must be false")

    if len(requirement_ids) != len(set(requirement_ids)):
        errors.append("authority_requirements.requirement_id values must be unique")


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_consts = {
        "binding_id": "non_live_quantum_fixture_serializer_authority_requirements_witness",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "parent_boundary_ref": "universal_symbolic_quantum_capability_boundary",
        "architecture_name": "USQCA-PQE",
        "authority_status": "NonLiveSerializerImplementationAuthorityRequirementsOnly",
    }

    for key, expected in expected_consts.items():
        if payload.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")

    related = payload.get("related_witness_refs")
    if not isinstance(related, list):
        errors.append("related_witness_refs must be a list")
    else:
        missing_related = sorted(REQUIRED_RELATED_WITNESSES.difference(related))
        if missing_related:
            errors.append(f"related_witness_refs missing: {', '.join(missing_related)}")
        if len(related) != len(set(related)):
            errors.append("related_witness_refs must not contain duplicates")

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

    boundary = payload.get("authority_requirements_boundary")
    if not isinstance(boundary, dict):
        errors.append("authority_requirements_boundary must be an object")
    else:
        if boundary.get("boundary_family") != "quantum fixture serializer implementation authority requirements":
            errors.append(
                "authority_requirements_boundary.boundary_family must be "
                "'quantum fixture serializer implementation authority requirements'"
            )
        if boundary.get("implementation_file_path") is not None:
            errors.append("authority_requirements_boundary.implementation_file_path must be null")
        if boundary.get("output_path") is not None:
            errors.append("authority_requirements_boundary.output_path must be null")

    _validate_required_set(
        payload,
        "allowed_requirement_categories",
        REQUIRED_ALLOWED_REQUIREMENT_CATEGORIES,
        errors,
    )
    _validate_required_set(
        payload,
        "denied_current_authorities",
        REQUIRED_DENIED_CURRENT_AUTHORITIES,
        errors,
    )
    _validate_required_set(payload, "required_authority_gates", REQUIRED_AUTHORITY_GATES, errors)
    _validate_authority_requirements(payload, errors)

    witnesses = payload.get("witness_requirements")
    if not isinstance(witnesses, list) or len(witnesses) < 10:
        errors.append("witness_requirements must contain at least ten entries")
    elif len(witnesses) != len(set(witnesses)):
        errors.append("witness_requirements must not contain duplicates")

    constructive = payload.get("constructive_deltas")
    fracture = payload.get("fracture_deltas")
    if not isinstance(constructive, list) or len(constructive) < 3:
        errors.append("constructive_deltas must contain at least three entries")
    if not isinstance(fracture, list) or len(fracture) < 6:
        errors.append("fracture_deltas must contain at least six entries")

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
        print("NON-LIVE QUANTUM FIXTURE SERIALIZER AUTHORITY REQUIREMENTS WITNESS VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
