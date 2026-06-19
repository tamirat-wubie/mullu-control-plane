#!/usr/bin/env python3
"""Validate the non-live quantum fixture serializer boundary witness.

Purpose: enforce the descriptor-only fixture serializer planning contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the foundation example.
Invariants: no serializer execution, no serialized fixture artifact, no
canonical runtime bytes, no source serialization, no simulator input
serialization, no runtime invocation, no state materialization, no shots, no
histograms, no backend calls, no credentials, no result claims, and no terminal
closure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / "examples" / "non_live_quantum_fixture_serializer_boundary_witness.foundation.json"

REQUIRED_RELATED_WITNESSES = {
    "non_live_openqasm_export_planning_witness",
    "non_live_local_quantum_simulator_boundary_witness",
    "non_live_quantum_fixture_catalog_witness",
}

REQUIRED_SERIALIZER_GATES = {
    "ParentQuantumBoundaryGate",
    "FixtureCatalogWitnessGate",
    "SerializerBoundaryDeclarationGate",
    "DescriptorOnlyGate",
    "DeterministicFieldOrderGate",
    "MetadataAllowlistGate",
    "PayloadDenylistGate",
    "NullOutputPathGate",
    "NoCanonicalBytesGate",
    "NoExecutableSerializationGate",
    "NoRuntimeExecutionGate",
    "WitnessLedgerGate",
}

REQUIRED_ALLOWED_SERIALIZER_ROLES = {
    "fixture_serializer_boundary_planning",
    "canonical_field_order_planning",
    "metadata_field_allowlist_planning",
    "payload_field_denylist_planning",
    "deterministic_serializer_profile_review",
    "denial_case_serializer_profile",
    "future_serializer_authority_requirement",
}

REQUIRED_DENIED_SERIALIZER_PAYLOADS = {
    "executable_fixture_json",
    "canonical_runtime_bytes",
    "openqasm_source_text",
    "qir_source_text",
    "simulator_input_blob",
    "runtime_payload",
    "state_vector_snapshot",
    "amplitude_table",
    "shot_count_sample",
    "measurement_histogram",
    "backend_job_id",
    "credential_material",
    "result_distribution",
    "quantum_advantage_claim",
    "production_readiness_claim",
}

ALLOWED_SOURCE_FIXTURE_CATEGORIES = {
    "identity_circuit_fixture_plan",
    "single_qubit_gate_fixture_plan",
    "entanglement_topology_fixture_plan",
    "measurement_mapping_fixture_plan",
    "resource_ceiling_fixture_plan",
    "denial_case_fixture_plan",
    "future_execution_admission_fixture_plan",
}

ALLOWED_TARGET_FORMAT_CLASSES = {
    "symbolic_descriptor_only",
    "review_metadata_only",
    "denial_case_descriptor_only",
    "future_authority_descriptor_only",
}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("serializer_boundary", "serializer_execution_allowed"),
    ("serializer_boundary", "serialized_artifact_allowed"),
    ("serializer_boundary", "canonical_bytes_allowed"),
    ("serializer_boundary", "runtime_payload_allowed"),
    ("denied_authorities", "fixture_serializer_execution_enabled"),
    ("denied_authorities", "serialized_fixture_artifact_generation_enabled"),
    ("denied_authorities", "executable_fixture_serialization_enabled"),
    ("denied_authorities", "canonical_runtime_bytes_emission_enabled"),
    ("denied_authorities", "openqasm_source_serialization_enabled"),
    ("denied_authorities", "qir_source_serialization_enabled"),
    ("denied_authorities", "simulator_input_serialization_enabled"),
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
    ("planning_only",),
    ("read_only",),
    ("parent_boundary_required",),
    ("fixture_catalog_witness_required",),
    ("non_live_witness_required",),
    ("serializer_boundary", "descriptor_only"),
    ("serializer_boundary", "deterministic_order_required"),
    ("serializer_boundary", "symbolic_metadata_only"),
    ("serializer_boundary", "requires_future_serializer_schema"),
    ("serializer_boundary", "requires_no_runtime_payload"),
    ("serializer_constraints", "requires_fixture_catalog_ref"),
    ("serializer_constraints", "requires_serializer_profile_id"),
    ("serializer_constraints", "requires_canonical_field_order_plan"),
    ("serializer_constraints", "requires_allowed_metadata_field_list"),
    ("serializer_constraints", "requires_denied_payload_field_list"),
    ("serializer_constraints", "requires_null_output_path"),
    ("serializer_constraints", "requires_no_canonical_bytes"),
    ("serializer_constraints", "requires_no_runtime_payload"),
    ("serializer_constraints", "requires_future_execution_authority"),
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


def _validate_string_list(
    profile: dict[str, Any],
    prefix: str,
    key: str,
    minimum_count: int,
    errors: list[str],
) -> set[str]:
    value = profile.get(key)
    if not isinstance(value, list) or len(value) < minimum_count:
        errors.append(f"{prefix}.{key} must contain at least {minimum_count} entries")
        return set()
    if len(value) != len(set(value)):
        errors.append(f"{prefix}.{key} must not contain duplicates")
    non_strings = [entry for entry in value if not isinstance(entry, str) or not entry]
    if non_strings:
        errors.append(f"{prefix}.{key} must contain only non-empty strings")
    return {entry for entry in value if isinstance(entry, str)}


def _validate_serializer_profiles(payload: dict[str, Any], errors: list[str]) -> None:
    profiles = payload.get("serializer_profiles")
    if not isinstance(profiles, list) or len(profiles) < 4:
        errors.append("serializer_profiles must contain at least four entries")
        return

    profile_ids: list[str] = []
    required_keys = {
        "profile_id",
        "source_fixture_category_ref",
        "target_format_class",
        "canonical_field_order_plan",
        "allowed_metadata_fields",
        "denied_payload_fields",
        "output_path",
        "future_authority_required",
        "denied_serialized_output",
    }
    for index, profile in enumerate(profiles):
        prefix = f"serializer_profiles[{index}]"
        if not isinstance(profile, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing_keys = sorted(required_keys.difference(profile))
        if missing_keys:
            errors.append(f"{prefix} missing: {', '.join(missing_keys)}")
            continue

        profile_id = profile["profile_id"]
        if not isinstance(profile_id, str) or not profile_id:
            errors.append(f"{prefix}.profile_id must be a non-empty string")
        else:
            profile_ids.append(profile_id)

        if profile["source_fixture_category_ref"] not in ALLOWED_SOURCE_FIXTURE_CATEGORIES:
            errors.append(f"{prefix}.source_fixture_category_ref must reference a known fixture catalog category")
        if profile["target_format_class"] not in ALLOWED_TARGET_FORMAT_CLASSES:
            errors.append(f"{prefix}.target_format_class must be a descriptor-only target class")

        _validate_string_list(profile, prefix, "canonical_field_order_plan", 3, errors)
        allowed_metadata = _validate_string_list(profile, prefix, "allowed_metadata_fields", 4, errors)
        denied_payload = _validate_string_list(profile, prefix, "denied_payload_fields", 6, errors)

        overlap = sorted(allowed_metadata.intersection(denied_payload))
        if overlap:
            errors.append(f"{prefix} allowed metadata overlaps denied payload fields: {', '.join(overlap)}")

        if profile["output_path"] is not None:
            errors.append(f"{prefix}.output_path must be null")
        if profile["future_authority_required"] is not True:
            errors.append(f"{prefix}.future_authority_required must be true")
        if profile["denied_serialized_output"] is not True:
            errors.append(f"{prefix}.denied_serialized_output must be true")

    if len(profile_ids) != len(set(profile_ids)):
        errors.append("serializer_profiles.profile_id values must be unique")


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_consts = {
        "binding_id": "non_live_quantum_fixture_serializer_boundary_witness",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "parent_boundary_ref": "universal_symbolic_quantum_capability_boundary",
        "architecture_name": "USQCA-PQE",
        "serializer_status": "NonLiveFixtureSerializerBoundaryOnly",
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

    boundary = payload.get("serializer_boundary")
    if not isinstance(boundary, dict):
        errors.append("serializer_boundary must be an object")
    else:
        if boundary.get("boundary_family") != "quantum fixture serializer admission planning boundary":
            errors.append(
                "serializer_boundary.boundary_family must be 'quantum fixture serializer admission planning boundary'"
            )
        if boundary.get("output_path") is not None:
            errors.append("serializer_boundary.output_path must be null")

    _validate_required_set(payload, "required_serializer_gates", REQUIRED_SERIALIZER_GATES, errors)
    _validate_required_set(payload, "allowed_serializer_roles", REQUIRED_ALLOWED_SERIALIZER_ROLES, errors)
    _validate_required_set(payload, "denied_serializer_payloads", REQUIRED_DENIED_SERIALIZER_PAYLOADS, errors)

    _validate_serializer_profiles(payload, errors)

    witnesses = payload.get("witness_requirements")
    if not isinstance(witnesses, list) or len(witnesses) < 9:
        errors.append("witness_requirements must contain at least nine entries")
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
        print("NON-LIVE QUANTUM FIXTURE SERIALIZER BOUNDARY WITNESS VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
