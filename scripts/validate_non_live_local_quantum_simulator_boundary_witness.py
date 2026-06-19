#!/usr/bin/env python3
"""Validate the non-live local quantum simulator boundary witness.

Purpose: enforce the planning-only simulator boundary contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the foundation example.
Invariants: no engine selection, no simulator runtime invocation, no state
materialization, no shot execution, no histogram emission, no backend calls,
no credentials, no result claims, and no terminal closure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / "examples" / "non_live_local_quantum_simulator_boundary_witness.foundation.json"

REQUIRED_BOUNDARY_GATES = {
    "ParentQuantumBoundaryGate",
    "SimulatorBoundaryDeclarationGate",
    "DeterministicFixturePlanGate",
    "QubitCountCeilingGate",
    "GateSetSubsetGate",
    "MeasurementPlanBoundaryGate",
    "NoRuntimeExecutionGate",
    "NoBackendCredentialGate",
    "ResourceBudgetGate",
    "ResultClaimDenialGate",
    "WitnessLedgerGate",
}

REQUIRED_ALLOWED_OUTPUTS = {
    "tiny_simulator_eligibility_plan",
    "deterministic_fixture_plan",
    "qubit_ceiling_declaration",
    "gate_subset_declaration",
    "measurement_plan_boundary",
    "resource_budget_plan",
    "result_claim_denial_policy",
    "future_simulator_witness_requirement",
}

REQUIRED_DENIED_OUTPUTS = {
    "simulator_engine_selection",
    "simulator_result",
    "state_vector_snapshot",
    "amplitude_table",
    "measurement_shot_counts",
    "measurement_histogram",
    "backend_job_id",
    "credential_material",
    "quantum_advantage_claim",
    "production_readiness_claim",
}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("simulator_boundary", "engine_selected"),
    ("simulator_boundary", "runtime_invocation_allowed"),
    ("simulator_boundary", "state_vector_materialization_allowed"),
    ("simulator_boundary", "shot_execution_allowed"),
    ("simulator_boundary", "measurement_histogram_allowed"),
    ("denied_authorities", "simulator_engine_selection_enabled"),
    ("denied_authorities", "simulator_runtime_invocation_enabled"),
    ("denied_authorities", "state_vector_materialization_enabled"),
    ("denied_authorities", "shot_execution_enabled"),
    ("denied_authorities", "measurement_histogram_emission_enabled"),
    ("denied_authorities", "backend_execution_enabled"),
    ("denied_authorities", "hardware_credentials_access_enabled"),
    ("denied_authorities", "quantum_job_submission_enabled"),
    ("denied_authorities", "quantum_advantage_claim_enabled"),
    ("denied_authorities", "production_readiness_claim_enabled"),
    ("denied_authorities", "terminal_closure"),
    ("effect_boundary", "simulator_engine_selected"),
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
    ("non_live_witness_required",),
    ("simulator_boundary", "backend_independent"),
    ("simulator_boundary", "requires_future_simulator_witness"),
    ("resource_ceiling_plan", "requires_qubit_count_ceiling"),
    ("resource_ceiling_plan", "requires_gate_count_ceiling"),
    ("resource_ceiling_plan", "requires_depth_ceiling"),
    ("resource_ceiling_plan", "requires_memory_ceiling"),
    ("resource_ceiling_plan", "requires_timeout_ceiling"),
    ("resource_ceiling_plan", "requires_no_runtime_benchmark_claim"),
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


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_consts = {
        "binding_id": "non_live_local_quantum_simulator_boundary_witness",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "parent_boundary_ref": "universal_symbolic_quantum_capability_boundary",
        "architecture_name": "USQCA-PQE",
        "boundary_status": "NonLiveLocalSimulatorBoundaryOnly",
    }

    for key, expected in expected_consts.items():
        if payload.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")

    related = payload.get("related_witness_refs")
    if not isinstance(related, list):
        errors.append("related_witness_refs must be a list")
    elif "non_live_openqasm_export_planning_witness" not in related:
        errors.append("related_witness_refs must include non_live_openqasm_export_planning_witness")
    elif len(related) != len(set(related)):
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

    boundary = payload.get("simulator_boundary")
    if not isinstance(boundary, dict):
        errors.append("simulator_boundary must be an object")
    else:
        if boundary.get("simulator_family") != "tiny local simulator planning boundary":
            errors.append("simulator_boundary.simulator_family must be 'tiny local simulator planning boundary'")
        if boundary.get("engine_name") is not None:
            errors.append("simulator_boundary.engine_name must be null")

    _validate_required_set(payload, "required_boundary_gates", REQUIRED_BOUNDARY_GATES, errors)
    _validate_required_set(payload, "allowed_planning_outputs", REQUIRED_ALLOWED_OUTPUTS, errors)
    _validate_required_set(payload, "denied_outputs", REQUIRED_DENIED_OUTPUTS, errors)

    allowed = payload.get("allowed_planning_outputs")
    denied = payload.get("denied_outputs")
    if isinstance(allowed, list) and isinstance(denied, list):
        overlap = sorted(set(allowed).intersection(denied))
        if overlap:
            errors.append(f"allowed planning outputs overlap denied outputs: {', '.join(overlap)}")

    fixture_obligations = payload.get("fixture_obligations")
    if not isinstance(fixture_obligations, list) or len(fixture_obligations) < 5:
        errors.append("fixture_obligations must contain at least five entries")
    elif len(fixture_obligations) != len(set(fixture_obligations)):
        errors.append("fixture_obligations must not contain duplicates")

    witnesses = payload.get("witness_requirements")
    if not isinstance(witnesses, list) or len(witnesses) < 7:
        errors.append("witness_requirements must contain at least seven entries")
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
        print("NON-LIVE LOCAL QUANTUM SIMULATOR BOUNDARY WITNESS VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
