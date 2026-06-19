#!/usr/bin/env python3
"""Validate the non-live quantum fixture catalog witness.

Purpose: enforce the deterministic fixture catalog planning-only contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the foundation example.
Invariants: no executable fixture generation, no source emission, no simulator
input generation, no runtime invocation, no state materialization, no shots, no
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
DEFAULT_EXAMPLE = ROOT / "examples" / "non_live_quantum_fixture_catalog_witness.foundation.json"

REQUIRED_RELATED_WITNESSES = {
    "non_live_openqasm_export_planning_witness",
    "non_live_local_quantum_simulator_boundary_witness",
}

REQUIRED_FIXTURE_GATES = {
    "ParentQuantumBoundaryGate",
    "OpenQasmPlanningBoundaryGate",
    "LocalSimulatorBoundaryGate",
    "FixtureCatalogDeclarationGate",
    "DeterministicFixtureShapeGate",
    "SymbolicCircuitIntentFixtureGate",
    "RegisterAndMeasurementPlanGate",
    "ResourceCeilingFixtureGate",
    "ExpectedInvariantOnlyGate",
    "NoExecutableArtifactGate",
    "NoRuntimeExecutionGate",
    "WitnessLedgerGate",
}

REQUIRED_ALLOWED_FIXTURE_TYPES = {
    "identity_circuit_fixture_plan",
    "single_qubit_gate_fixture_plan",
    "entanglement_topology_fixture_plan",
    "measurement_mapping_fixture_plan",
    "resource_ceiling_fixture_plan",
    "denial_case_fixture_plan",
    "future_execution_admission_fixture_plan",
}

REQUIRED_DENIED_FIXTURE_CONTENTS = {
    "openqasm_source_text",
    "qir_source_text",
    "executable_circuit_file",
    "simulator_input_blob",
    "state_vector_snapshot",
    "amplitude_table",
    "shot_count_sample",
    "measurement_histogram",
    "backend_job_id",
    "credential_material",
    "cryptanalysis_workflow",
    "quantum_advantage_claim",
    "production_readiness_claim",
}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("fixture_catalog", "executable_artifacts_allowed"),
    ("fixture_catalog", "source_text_allowed"),
    ("fixture_catalog", "simulator_input_allowed"),
    ("fixture_catalog", "expected_results_allowed"),
    ("denied_authorities", "executable_fixture_generation_enabled"),
    ("denied_authorities", "openqasm_source_emission_enabled"),
    ("denied_authorities", "qir_source_emission_enabled"),
    ("denied_authorities", "simulator_input_generation_enabled"),
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
    ("effect_boundary", "executable_fixture_written"),
    ("effect_boundary", "openqasm_source_text_emitted"),
    ("effect_boundary", "openqasm_file_written"),
    ("effect_boundary", "qir_source_text_emitted"),
    ("effect_boundary", "qir_file_written"),
    ("effect_boundary", "simulator_input_written"),
    ("effect_boundary", "simulator_runtime_invoked"),
    ("effect_boundary", "state_vector_materialized"),
    ("effect_boundary", "amplitude_table_materialized"),
    ("effect_boundary", "measurement_shots_executed"),
    ("effect_boundary", "measurement_histogram_emitted"),
    ("effect_boundary", "backend_called"),
    ("effect_boundary", "hardware_credentials_read"),
    ("effect_boundary", "quantum_job_submitted"),
    ("effect_boundary", "result_distribution_observed"),
    ("effect_boundary", "secret_values_serialized"),
    ("effect_boundary", "production_claim_made"),
)

FORCED_TRUE_PATHS = (
    ("planning_only",),
    ("read_only",),
    ("parent_boundary_required",),
    ("openqasm_planning_witness_required",),
    ("local_simulator_boundary_witness_required",),
    ("non_live_witness_required",),
    ("fixture_catalog", "deterministic_order_required"),
    ("fixture_catalog", "symbolic_only"),
    ("fixture_catalog", "requires_future_fixture_schema"),
    ("fixture_catalog", "requires_no_execution_result"),
    ("fixture_constraints", "requires_fixture_id"),
    ("fixture_constraints", "requires_symbolic_intent"),
    ("fixture_constraints", "requires_gate_subset_ref"),
    ("fixture_constraints", "requires_register_plan"),
    ("fixture_constraints", "requires_measurement_plan"),
    ("fixture_constraints", "requires_resource_ceiling"),
    ("fixture_constraints", "requires_expected_invariant_statement"),
    ("fixture_constraints", "requires_no_runtime_payload"),
    ("fixture_constraints", "requires_replayable_order"),
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


def _validate_fixture_blueprints(payload: dict[str, Any], errors: list[str]) -> None:
    blueprints = payload.get("fixture_blueprints")
    allowed_types = payload.get("allowed_fixture_types")
    if not isinstance(blueprints, list) or len(blueprints) < 5:
        errors.append("fixture_blueprints must contain at least five entries")
        return
    if not isinstance(allowed_types, list):
        errors.append("allowed_fixture_types must be a list before fixture blueprint validation")
        return

    fixture_ids: list[str] = []
    allowed_type_set = set(allowed_types)
    required_keys = {
        "fixture_id",
        "category",
        "symbolic_intent",
        "gate_subset_ref",
        "register_plan",
        "measurement_plan",
        "resource_ceiling_ref",
        "expected_invariant",
        "denied_runtime_result",
    }
    for index, blueprint in enumerate(blueprints):
        prefix = f"fixture_blueprints[{index}]"
        if not isinstance(blueprint, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing_keys = sorted(required_keys.difference(blueprint))
        if missing_keys:
            errors.append(f"{prefix} missing: {', '.join(missing_keys)}")
            continue
        fixture_id = blueprint["fixture_id"]
        if not isinstance(fixture_id, str) or not fixture_id:
            errors.append(f"{prefix}.fixture_id must be a non-empty string")
        else:
            fixture_ids.append(fixture_id)
        category = blueprint["category"]
        if category not in allowed_type_set:
            errors.append(f"{prefix}.category must reference an allowed fixture type")
        for key in (
            "symbolic_intent",
            "gate_subset_ref",
            "register_plan",
            "measurement_plan",
            "resource_ceiling_ref",
            "expected_invariant",
        ):
            if not isinstance(blueprint[key], str) or not blueprint[key]:
                errors.append(f"{prefix}.{key} must be a non-empty string")
        if blueprint["denied_runtime_result"] is not True:
            errors.append(f"{prefix}.denied_runtime_result must be true")

    if len(fixture_ids) != len(set(fixture_ids)):
        errors.append("fixture_blueprints.fixture_id values must be unique")


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_consts = {
        "binding_id": "non_live_quantum_fixture_catalog_witness",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "parent_boundary_ref": "universal_symbolic_quantum_capability_boundary",
        "architecture_name": "USQCA-PQE",
        "catalog_status": "NonLiveDeterministicFixtureCatalogOnly",
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

    catalog = payload.get("fixture_catalog")
    if not isinstance(catalog, dict):
        errors.append("fixture_catalog must be an object")
    else:
        if catalog.get("catalog_family") != "deterministic quantum fixture catalog planning boundary":
            errors.append(
                "fixture_catalog.catalog_family must be 'deterministic quantum fixture catalog planning boundary'"
            )
        if catalog.get("executable_artifact_path") is not None:
            errors.append("fixture_catalog.executable_artifact_path must be null")

    _validate_required_set(payload, "required_fixture_gates", REQUIRED_FIXTURE_GATES, errors)
    _validate_required_set(payload, "allowed_fixture_types", REQUIRED_ALLOWED_FIXTURE_TYPES, errors)
    _validate_required_set(payload, "denied_fixture_contents", REQUIRED_DENIED_FIXTURE_CONTENTS, errors)

    allowed = payload.get("allowed_fixture_types")
    denied = payload.get("denied_fixture_contents")
    if isinstance(allowed, list) and isinstance(denied, list):
        overlap = sorted(set(allowed).intersection(denied))
        if overlap:
            errors.append(f"allowed fixture types overlap denied fixture contents: {', '.join(overlap)}")

    _validate_fixture_blueprints(payload, errors)

    witnesses = payload.get("witness_requirements")
    if not isinstance(witnesses, list) or len(witnesses) < 8:
        errors.append("witness_requirements must contain at least eight entries")
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
        print("NON-LIVE QUANTUM FIXTURE CATALOG WITNESS VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
