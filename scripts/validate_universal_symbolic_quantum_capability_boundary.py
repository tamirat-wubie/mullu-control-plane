#!/usr/bin/env python3
"""Validate the Universal Symbolic Quantum Capability Boundary example.

The validator is intentionally stdlib-only so the boundary can be checked in
Foundation Mode without adding package or runtime dependencies.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE = ROOT / "examples" / "universal_symbolic_quantum_capability_boundary.foundation.json"

REQUIRED_GATES = {
    "QuantumEligibilityGate",
    "QuantumSemanticLawGate",
    "ProofCarryingCompilerGate",
    "ResourceHonestyGate",
    "BackendCapabilityProfileGate",
    "NoiseAndCalibrationGate",
    "StatisticalResultConfidenceGate",
    "PostQuantumSecurityGate",
    "WitnessLedgerGate",
}

REQUIRED_GOVERNANCE_SCOPE = {"OCE", "RAG", "CDCV", "CQTE", "UWMA", "SRCA", "PRS"}

FORCED_FALSE_PATHS = (
    ("authority_granted",),
    ("runtime_quantum_execution_enabled",),
    ("hardware_backend_authority_granted",),
    ("quantum_hardware_claim_made",),
    ("fault_tolerant_claim_made",),
    ("quantum_advantage_claim_made",),
    ("denied_authorities", "live_qpu_execution_enabled"),
    ("denied_authorities", "simulator_runtime_execution_enabled"),
    ("denied_authorities", "hardware_credentials_access_enabled"),
    ("denied_authorities", "quantum_job_submission_enabled"),
    ("denied_authorities", "cryptanalysis_execution_enabled"),
    ("denied_authorities", "external_backend_network_calls_enabled"),
    ("denied_authorities", "production_readiness_claim_enabled"),
    ("denied_authorities", "terminal_closure"),
    ("effect_boundary", "backend_called"),
    ("effect_boundary", "quantum_job_submitted"),
    ("effect_boundary", "simulator_executed"),
    ("effect_boundary", "hardware_credentials_read"),
    ("effect_boundary", "result_distribution_observed"),
    ("effect_boundary", "repository_runtime_mutated"),
    ("effect_boundary", "secret_values_serialized"),
)

FORCED_TRUE_PATHS = (
    ("planning_only",),
    ("read_only",),
    ("physical_boundary", "requires_declared_qubit_substrate"),
    ("physical_boundary", "requires_initialization_model"),
    ("physical_boundary", "requires_coherence_or_noise_model"),
    ("physical_boundary", "requires_backend_capability_profile"),
    ("physical_boundary", "requires_statistical_result_validation"),
    ("physical_boundary", "requires_fault_tolerance_evidence_for_logical_claims"),
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
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    expected_consts = {
        "binding_id": "universal_symbolic_quantum_capability_boundary",
        "schema_version": 1,
        "solver_outcome": "FoundationModeOnly",
        "architecture_name": "USQCA-PQE",
        "full_name": "Universal Symbolic Quantum Computing Architecture with Proof-Carrying Execution",
        "integration_decision": "FitsAsGovernedPlanningSurface",
        "capability_status": "PlanningOnly",
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

    governance_scope = payload.get("governance_scope")
    if not isinstance(governance_scope, list):
        errors.append("governance_scope must be a list")
    elif set(governance_scope) != REQUIRED_GOVERNANCE_SCOPE:
        errors.append("governance_scope must exactly match OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS")

    gates = payload.get("required_gates")
    if not isinstance(gates, list):
        errors.append("required_gates must be a list")
    else:
        missing_gates = sorted(REQUIRED_GATES.difference(gates))
        if missing_gates:
            errors.append(f"required_gates missing: {', '.join(missing_gates)}")
        if len(gates) != len(set(gates)):
            errors.append("required_gates must not contain duplicates")

    role = payload.get("symbolic_control_plane_role")
    if not isinstance(role, dict):
        errors.append("symbolic_control_plane_role must be an object")
    else:
        allowed = role.get("allowed_roles")
        denied = role.get("denied_roles")
        if not isinstance(allowed, list) or len(allowed) < 5:
            errors.append("symbolic_control_plane_role.allowed_roles must contain at least five roles")
        if not isinstance(denied, list) or len(denied) < 5:
            errors.append("symbolic_control_plane_role.denied_roles must contain at least five roles")
        if isinstance(allowed, list) and isinstance(denied, list):
            overlap = sorted(set(allowed).intersection(denied))
            if overlap:
                errors.append(f"allowed and denied roles overlap: {', '.join(overlap)}")

    witness_requirements = payload.get("witness_requirements")
    if not isinstance(witness_requirements, list) or len(witness_requirements) < 6:
        errors.append("witness_requirements must contain at least six witness requirements")
    elif len(witness_requirements) != len(set(witness_requirements)):
        errors.append("witness_requirements must not contain duplicates")

    constructive = payload.get("constructive_deltas")
    fracture = payload.get("fracture_deltas")
    if not isinstance(constructive, list) or len(constructive) < 3:
        errors.append("constructive_deltas must contain at least three entries")
    if not isinstance(fracture, list) or len(fracture) < 3:
        errors.append("fracture_deltas must contain at least three entries")

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
        print("UNIVERSAL SYMBOLIC QUANTUM CAPABILITY BOUNDARY VALID")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
