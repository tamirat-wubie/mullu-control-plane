#!/usr/bin/env python3
"""Validate the CDG-RCCM Architecture Contract.

Purpose: verify that the Foundation Mode CDG-RCCM contract preserves separated
containment/dependency topology, continuation-local suspension, independent
certification, declared convergence, cycle classification, causal invalidation,
and denied live/effect authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and shared schema validation helpers.
Invariants:
  - Validation is read-only and deterministic.
  - CDG-RCCM remains a proposed architecture contract, not a live RCOK runtime.
  - Universal protocol compatibility does not imply universal termination.
  - No external effects, production certificates, terminal closure, or success
    claims are granted by the Foundation Mode example.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "cdg_rccm_architecture_contract.schema.json"
DEFAULT_CONTRACT_PATH = WORKSPACE_ROOT / "examples" / "cdg_rccm_architecture_contract.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:cdg-rccm-architecture-contract:1"
EXPECTED_SCHEMA_TITLE = "CDG-RCCM Architecture Contract"
EXPECTED_CONTRACT_VERSION = "cdg_rccm_architecture_contract.v1"
EXPECTED_COMPONENT_TUPLE = ("I", "Lambda", "Sigma", "Gamma", "H")
EXPECTED_OPERATIONAL_TUPLE = ("S", "K", "P", "Q", "B", "nu")
EXPECTED_MESH_TUPLE = ("V", "E_H", "E_D", "F", "Q", "W", "R", "J", "L", "X", "epoch")
EXPECTED_SEQUENCE = (
    "frame_component",
    "perform_available_local_work",
    "discover_exact_dependency",
    "preserve_blocked_continuation",
    "recursively_settle_dependency",
    "receive_certified_projection",
    "resume_continuation",
    "integrate_result",
    "reconcile_boundaries",
    "propagate_constructive_and_fracture_deltas",
    "reopen_affected_work",
    "repeat_until_certified_closure",
)
EXPECTED_DEPENDENCY_EDGE_TYPES = {
    "REQUIRES",
    "CONSTRAINS",
    "OBSERVES",
    "RECONCILES_WITH",
    "SHARES",
    "ALTERNATIVE_TO",
    "PRECEDES",
    "EVIDENCES",
    "TEMPORAL_PREVIOUS",
    "SUPERSEDES",
}
EXPECTED_REQUEST_FIELDS = (
    "requester",
    "provider",
    "projection",
    "minimumLevel",
    "gate",
    "assumptions",
    "consistency",
    "freshness",
    "budget",
    "fallback",
)
EXPECTED_GATES = {"HARD", "PROVISIONAL", "ADVISORY", "ALTERNATIVE", "QUORUM", "STREAMING", "TEMPORAL"}
EXPECTED_STEP_OUTCOMES = {"Need", "Progress", "Candidate", "Conflict", "Unknown", "Fault", "Cancelled"}
EXPECTED_SETTLEMENT_LEVELS = (
    (0, "PROVISIONAL"),
    (1, "LOCALLY_STABLE"),
    (2, "BOUNDARY_RECONCILED"),
    (3, "CLOSURE_CERTIFIED"),
    (4, "WORLD_VERIFIED"),
)
EXPECTED_CONVERGENCE_METHODS = {
    "finite_monotone_convergence",
    "well_founded_descent",
    "contractive_approximation",
    "bounded_search",
    "widening_and_narrowing",
    "external_adjudication",
    "streaming_epochs",
}
EXPECTED_CYCLE_CLASSES = {
    "STRUCTURAL_CONTAINMENT",
    "SEMANTIC_FEEDBACK",
    "TEMPORAL_FEEDBACK",
    "RESOURCE_DEADLOCK",
    "AUTHORITY_DEADLOCK",
    "ALTERNATIVE_SELECTION",
    "HIDDEN_SELF_DEPENDENCY",
}
EXPECTED_CLOSURE_OUTCOMES = {
    "CERTIFIED",
    "UNSAT",
    "UNKNOWN",
    "BLOCKED",
    "STALE",
    "FAULT",
    "CANCELLED",
    "DEGRADED",
    "RECOVERY_REQUIRED",
}
REQUIRED_CLOSURE_CONDITIONS = {
    "all_consumed_information_is_dependency",
    "components_cannot_self_certify",
    "containment_and_dependency_separate",
    "every_loop_has_convergence_or_exhaustion_contract",
    "cycles_classified_before_resolution",
    "results_versioned_and_assumption_bound",
    "invalidation_follows_actual_causal_reads",
    "local_stability_not_boundary_validity",
    "quiescence_not_correctness",
    "world_claims_do_not_exceed_evidence",
    "external_actions_separated_from_reasoning",
    "safety_liveness_fairness_independently_governed",
}
DENIED_AUTHORITY_FIELDS = (
    "live_runtime_dispatch_allowed",
    "external_write_allowed",
    "production_certificate_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_EVIDENCE_REFS = (
    "docs/93_cdg_rccm_architecture_contract.md",
    "schemas/cdg_rccm_architecture_contract.schema.json",
    "examples/cdg_rccm_architecture_contract.foundation.json",
    "scripts/validate_cdg_rccm_architecture_contract.py",
    "tests/test_validate_cdg_rccm_architecture_contract.py",
)


class CdgRccmArchitectureContractError(ValueError):
    """Raised when a CDG-RCCM contract artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CdgRccmArchitectureContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "contract_id",
            "contract_version",
            "source_spec",
            "foundation_boundary",
            "component_model",
            "mesh_model",
            "execution_protocol",
            "dependency_request_contract",
            "convergence_contracts",
            "cycle_handling",
            "closure_certification",
            "authority_boundary",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_cdg_rccm_architecture_contract_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one CDG-RCCM contract."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("cdg-rccm architecture contract must be a JSON object")
        return errors

    _validate_source_spec(record.get("source_spec"), errors)
    _validate_foundation_boundary(record.get("foundation_boundary"), errors)
    _validate_component_model(record.get("component_model"), errors)
    _validate_mesh_model(record.get("mesh_model"), errors)
    _validate_execution_protocol(record.get("execution_protocol"), errors)
    _validate_dependency_request_contract(record.get("dependency_request_contract"), errors)
    _validate_convergence_contracts(record.get("convergence_contracts"), errors)
    _validate_cycle_handling(record.get("cycle_handling"), errors)
    _validate_closure_certification(record.get("closure_certification"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_contract_summary(record, errors)
    _require_evidence_refs(record.get("evidence_refs"), errors)
    return errors


def validate_cdg_rccm_architecture_contract(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode contract."""

    schema = _load_schema(schema_path)
    contract = load_json_object(contract_path, "CDG-RCCM Architecture Contract")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_cdg_rccm_architecture_contract_record(contract, schema))
    return errors


def build_mutated_cdg_rccm_architecture_contract(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default contract."""

    contract = load_json_object(DEFAULT_CONTRACT_PATH, "CDG-RCCM Architecture Contract")
    mutated = deepcopy(contract)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return resolved.resolve().relative_to(WORKSPACE_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _validate_source_spec(source_spec: Any, errors: list[str]) -> None:
    if not isinstance(source_spec, dict):
        errors.append("source_spec must be an object")
        return
    if source_spec.get("standard_status") != "proposed_canonical_architecture":
        errors.append("source_spec.standard_status must remain proposed_canonical_architecture")
    if source_spec.get("universal_termination_claimed") is not False:
        errors.append("source_spec.universal_termination_claimed must be false")
    if source_spec.get("universal_profile_meaning") != "shared_interface_protocol_only":
        errors.append("source_spec.universal_profile_meaning must be shared_interface_protocol_only")


def _validate_foundation_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("foundation_boundary must be an object")
        return
    if boundary.get("foundation_mode") is not True:
        errors.append("foundation_boundary.foundation_mode must be true")
    for field_name in (
        "live_runtime_claimed",
        "external_effects_allowed",
        "global_convergence_claimed",
        "world_verification_claimed",
        "runtime_certificate_issuer_claimed",
    ):
        if boundary.get(field_name) is not False:
            errors.append(f"foundation_boundary.{field_name} must be false")


def _validate_component_model(component_model: Any, errors: list[str]) -> None:
    if not isinstance(component_model, dict):
        errors.append("component_model must be an object")
        return
    if tuple(component_model.get("base_symbol_tuple", ())) != EXPECTED_COMPONENT_TUPLE:
        errors.append("component_model.base_symbol_tuple does not match CDG-RCCM base tuple")
    if tuple(component_model.get("operational_tuple", ())) != EXPECTED_OPERATIONAL_TUPLE:
        errors.append("component_model.operational_tuple does not match CDG-RCCM runtime tuple")
    conditions = set(component_model.get("required_conditions", ()))
    required_conditions = {
        "sigma_models_lambda_over_identity",
        "gamma_exposes_authorized_certified_projections",
        "history_records_every_accepted_state_transition",
    }
    missing = sorted(required_conditions - conditions)
    if missing:
        errors.append(f"component_model.required_conditions missing {missing}")


def _validate_mesh_model(mesh_model: Any, errors: list[str]) -> None:
    if not isinstance(mesh_model, dict):
        errors.append("mesh_model must be an object")
        return
    if tuple(mesh_model.get("mesh_tuple", ())) != EXPECTED_MESH_TUPLE:
        errors.append("mesh_model.mesh_tuple does not match CDG-RCCM mesh tuple")
    for field_name in (
        "epoch_frozen",
        "containment_dependency_separated",
        "containment_acyclic_required",
        "dependency_cycles_allowed_when_classified",
    ):
        if mesh_model.get(field_name) is not True:
            errors.append(f"mesh_model.{field_name} must be true")
    edge_types = set(mesh_model.get("dependency_edge_types", ()))
    if edge_types != EXPECTED_DEPENDENCY_EDGE_TYPES:
        errors.append("mesh_model.dependency_edge_types must match the canonical dependency set")


def _validate_execution_protocol(execution_protocol: Any, errors: list[str]) -> None:
    if not isinstance(execution_protocol, dict):
        errors.append("execution_protocol must be an object")
        return
    if tuple(execution_protocol.get("governing_sequence", ())) != EXPECTED_SEQUENCE:
        errors.append("execution_protocol.governing_sequence must match the canonical order")
    if set(execution_protocol.get("step_outcomes", ())) != EXPECTED_STEP_OUTCOMES:
        errors.append("execution_protocol.step_outcomes must match the step outcome algebra")
    levels = tuple(
        (level.get("level"), level.get("name"))
        for level in execution_protocol.get("settlement_levels", ())
        if isinstance(level, dict)
    )
    if levels != EXPECTED_SETTLEMENT_LEVELS:
        errors.append("execution_protocol.settlement_levels must match L0-L4 order")
    if execution_protocol.get("independent_certificate_kernel_required") is not True:
        errors.append("execution_protocol.independent_certificate_kernel_required must be true")


def _validate_dependency_request_contract(request_contract: Any, errors: list[str]) -> None:
    if not isinstance(request_contract, dict):
        errors.append("dependency_request_contract must be an object")
        return
    if tuple(request_contract.get("required_fields", ())) != EXPECTED_REQUEST_FIELDS:
        errors.append("dependency_request_contract.required_fields must match the exact request tuple")
    if set(request_contract.get("gates", ())) != EXPECTED_GATES:
        errors.append("dependency_request_contract.gates must match the canonical gates")
    required_predicates = {
        "projection_matches_request",
        "level_meets_minimum",
        "certificate_current_for_epoch",
        "assumptions_compatible",
        "consistency_compatible",
    }
    if set(request_contract.get("satisfaction_predicates", ())) != required_predicates:
        errors.append("dependency_request_contract.satisfaction_predicates must match satisfaction rule")


def _validate_convergence_contracts(convergence_contracts: Any, errors: list[str]) -> None:
    if not isinstance(convergence_contracts, dict):
        errors.append("convergence_contracts must be an object")
        return
    if set(convergence_contracts.get("declared_methods", ())) != EXPECTED_CONVERGENCE_METHODS:
        errors.append("convergence_contracts.declared_methods must match canonical convergence methods")
    if convergence_contracts.get("budget_exhaustion_outcome") != "UNKNOWN":
        errors.append("convergence_contracts.budget_exhaustion_outcome must be UNKNOWN")
    if convergence_contracts.get("cycle_region_requires_declared_policy") is not True:
        errors.append("convergence_contracts.cycle_region_requires_declared_policy must be true")


def _validate_cycle_handling(cycle_handling: Any, errors: list[str]) -> None:
    if not isinstance(cycle_handling, dict):
        errors.append("cycle_handling must be an object")
        return
    if set(cycle_handling.get("cycle_classes", ())) != EXPECTED_CYCLE_CLASSES:
        errors.append("cycle_handling.cycle_classes must match canonical cycle classes")
    for field_name in (
        "semantic_feedback_requires_declared_convergence",
        "structural_containment_rejected",
        "hidden_self_dependency_exposed",
    ):
        if cycle_handling.get(field_name) is not True:
            errors.append(f"cycle_handling.{field_name} must be true")


def _validate_closure_certification(closure_certification: Any, errors: list[str]) -> None:
    if not isinstance(closure_certification, dict):
        errors.append("closure_certification must be an object")
        return
    conditions = set(closure_certification.get("required_conditions", ()))
    missing_conditions = sorted(REQUIRED_CLOSURE_CONDITIONS - conditions)
    if missing_conditions:
        errors.append(f"closure_certification.required_conditions missing {missing_conditions}")
    if set(closure_certification.get("closure_outcomes", ())) != EXPECTED_CLOSURE_OUTCOMES:
        errors.append("closure_certification.closure_outcomes must match canonical outcomes")
    if closure_certification.get("quiescence_is_not_correctness") is not True:
        errors.append("closure_certification.quiescence_is_not_correctness must be true")
    if closure_certification.get("world_claim_requires_evidence") is not True:
        errors.append("closure_certification.world_claim_requires_evidence must be true")


def _validate_authority_boundary(authority_boundary: Any, errors: list[str]) -> None:
    if not isinstance(authority_boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in ("reasoning_only", "effect_staging_required", "no_component_self_certifies"):
        if authority_boundary.get(field_name) is not True:
            errors.append(f"authority_boundary.{field_name} must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if authority_boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    expected_counts = {
        "component_tuple_count": len(record.get("component_model", {}).get("base_symbol_tuple", [])),
        "mesh_tuple_count": len(record.get("mesh_model", {}).get("mesh_tuple", [])),
        "dependency_gate_count": len(record.get("dependency_request_contract", {}).get("gates", [])),
        "step_outcome_count": len(record.get("execution_protocol", {}).get("step_outcomes", [])),
        "settlement_level_count": len(record.get("execution_protocol", {}).get("settlement_levels", [])),
        "cycle_class_count": len(record.get("cycle_handling", {}).get("cycle_classes", [])),
        "closure_outcome_count": len(record.get("closure_certification", {}).get("closure_outcomes", [])),
        "evidence_ref_count": len(record.get("evidence_refs", [])),
    }
    for field_name, expected_value in expected_counts.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"contract_summary.{field_name} must equal {expected_value}")
    if summary.get("authority_denied") is not True:
        errors.append("contract_summary.authority_denied must be true")


def _require_evidence_refs(evidence_refs: Any, errors: list[str]) -> None:
    if not isinstance(evidence_refs, list):
        errors.append("evidence_refs must be a list")
        return
    ref_set = set(evidence_refs)
    for required_ref in REQUIRED_EVIDENCE_REFS:
        if required_ref not in ref_set:
            errors.append(f"evidence_refs missing required ref: {required_ref}")
        candidate_path = WORKSPACE_ROOT / required_ref
        if not candidate_path.exists():
            errors.append(f"evidence_refs required ref missing on disk: {required_ref}")


def main(argv: list[str] | None = None) -> int:
    """Run the CDG-RCCM contract validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--json", action="store_true", help="Emit a JSON validation receipt.")
    args = parser.parse_args(argv)

    schema_path = args.schema if args.schema.is_absolute() else WORKSPACE_ROOT / args.schema
    contract_path = args.contract if args.contract.is_absolute() else WORKSPACE_ROOT / args.contract
    errors = validate_cdg_rccm_architecture_contract(schema_path, contract_path)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "passed" if not errors else "failed",
                    "schema_path": workspace_display_path(schema_path),
                    "contract_path": workspace_display_path(contract_path),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        print("CDG-RCCM architecture contract validation passed.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
