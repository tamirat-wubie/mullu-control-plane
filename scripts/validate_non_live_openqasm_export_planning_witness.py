#!/usr/bin/env python3
"""Validate the non-live OpenQASM export planning witness.

Purpose: enforce the planning-only OpenQASM witness contract.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS.
Dependencies: stdlib JSON parsing and the foundation example.
Invariants: no source emission, no simulator/backend execution, no credentials,
no job submission, no result claims, and no terminal closure.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / "examples" / "non_live_openqasm_export_planning_witness.foundation.json"

REQUIRED_PLANNING_GATES = {
    "ParentQuantumBoundaryGate",
    "OpenQasmVersionDeclarationGate",
    "SymbolicCircuitIntentGate",
    "RegisterSizingGate",
    "GateSetDeclarationGate",
    "MeasurementMappingGate",
    "ResourceProjectionGate",
    "BackendIndependenceGate",
    "NoExecutionAuthorityGate",
    "WitnessLedgerGate",
}

REQUIRED_ALLOWED_OUTPUTS = {
    "symbolic_circuit_intent",
    "openqasm_target_version_declaration",
    "register_sizing_plan",
    "gate_set_plan",
    "measurement_mapping_plan",
    "resource_projection_plan",
    "export_precondition_list",
    "future_exporter_witness_requirement",
}

REQUIRED_DENIED_OUTPUTS = {
    "openqasm_source_text",
    "openqasm_source_file",
    "qir_source_file",
    "simulator_result",
    "backend_job_id",
    "hardware_calibration_record",
    "credential_material",
    "cryptanalysis_workflow",
    "quantum_advantage_claim",
    "production_readiness_claim",
}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("openqasm_target", "source_text_embedded"),
    ("openqasm_target", "backend_specific_pragmas_allowed"),
    ("denied_authorities", "openqasm_source_emission_enabled"),
    ("denied_authorities", "qir_source_emission_enabled"),
    ("denied_authorities", "simulator_runtime_execution_enabled"),
    ("denied_authorities", "backend_execution_enabled"),
    ("denied_authorities", "hardware_credentials_access_enabled"),
    ("denied_authorities", "quantum_job_submission_enabled"),
    ("denied_authorities", "cryptanalysis_execution_enabled"),
    ("denied_authorities", "quantum_advantage_claim_enabled"),
    ("denied_authorities", "production_readiness_claim_enabled"),
    ("denied_authorities", "terminal_closure"),
    ("effect_boundary", "openqasm_source_text_emitted"),
    ("effect_boundary", "openqasm_file_written"),
    ("effect_boundary", "qir_file_written"),
    ("effect_boundary", "simulator_invoked"),
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
    ("openqasm_target", "backend_independent"),
    ("openqasm_target", "requires_future_exporter_witness"),
    ("planning_constraints", "requires_symbolic_circuit_intent"),
    ("planning_constraints", "requires_register_declarations"),
    ("planning_constraints", "requires_measurement_mapping"),
    ("planning_constraints", "requires_resource_projection"),
    ("planning_constraints", "requires_no_backend_profile"),
    ("planning_constraints", "requires_future_exporter_schema"),
    ("planning_constraints", "requires_no_execution_result"),
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
        "binding_id": "non_live_openqasm_export_planning_witness",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "parent_boundary_ref": "universal_symbolic_quantum_capability_boundary",
        "architecture_name": "USQCA-PQE",
        "planning_status": "NonLiveOpenQasmPlanningOnly",
    }

    for key, expected in expected_consts.items():
        if payload.get(key) != expected:
            errors.append(f"{key} must be {expected!r}")

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

    target = payload.get("openqasm_target")
    if not isinstance(target, dict):
        errors.append("openqasm_target must be an object")
    else:
        if target.get("target_version") != "OpenQASM 3.0 planning target":
            errors.append("openqasm_target.target_version must be 'OpenQASM 3.0 planning target'")
        if target.get("source_file_path") is not None:
            errors.append("openqasm_target.source_file_path must be null")

    _validate_required_set(payload, "required_planning_gates", REQUIRED_PLANNING_GATES, errors)
    _validate_required_set(payload, "allowed_planning_outputs", REQUIRED_ALLOWED_OUTPUTS, errors)
    _validate_required_set(payload, "denied_outputs", REQUIRED_DENIED_OUTPUTS, errors)

    allowed = payload.get("allowed_planning_outputs")
    denied = payload.get("denied_outputs")
    if isinstance(allowed, list) and isinstance(denied, list):
        overlap = sorted(set(allowed).intersection(denied))
        if overlap:
            errors.append(f"allowed planning outputs overlap denied outputs: {', '.join(overlap)}")

    obligations = payload.get("resource_projection_obligations")
    if not isinstance(obligations, list) or len(obligations) < 5:
        errors.append("resource_projection_obligations must contain at least five entries")
    elif len(obligations) != len(set(obligations)):
        errors.append("resource_projection_obligations must not contain duplicates")

    witnesses = payload.get("witness_requirements")
    if not isinstance(witnesses, list) or len(witnesses) < 6:
        errors.append("witness_requirements must contain at least six entries")
    elif len(witnesses) != len(set(witnesses)):
        errors.append("witness_requirements must not contain duplicates")

    constructive = payload.get("constructive_deltas")
    fracture = payload.get("fracture_deltas")
    if not isinstance(constructive, list) or len(constructive) < 3:
        errors.append("constructive_deltas must contain at least three entries")
    if not isinstance(fracture, list) or len(fracture) < 5:
        errors.append("fracture_deltas must contain at least five entries")

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
        print("NON-LIVE OPENQASM EXPORT PLANNING WITNESS VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
