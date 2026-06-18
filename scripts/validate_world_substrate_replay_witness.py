#!/usr/bin/env python3
"""Validate the WorldSubstrateReplayWitness contract.

Purpose: verify that SWEWS-style world snapshot replay evidence remains
witness-only, digest-bound, invariant-bound, and separated from live world
service calls, SQLite access, world mutation, replay execution, external
effects, raw payload retention, terminal closure, and success authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, WorldState,
UAO, LifeMeaningJudgment, SimulationReceipt, EffectAssurance, and SDLC recovery
handoff schemas.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example performs no live world service call or replay.
  - SQLite access, world mutation, planner/executor execution, external
    endpoints, secret access, filesystem writes, raw world snapshots, raw replay
    traces, terminal closure, and success claims remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "world_substrate_replay_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "world_substrate_replay_witness.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:world-substrate-replay-witness:1"
EXPECTED_SCHEMA_TITLE = "World Substrate Replay Witness"
EXPECTED_WITNESS_VERSION = "world_substrate_replay_witness.v1"
REQUIRED_RECEIPT_REFS = {
    "world_substrate_replay_witness_schema": "schemas/world_substrate_replay_witness.schema.json",
    "world_state_schema": "schemas/world_state.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
    "simulation_receipt_schema": "schemas/simulation_receipt.schema.json",
    "effect_assurance_schema": "schemas/effect_assurance.schema.json",
    "sdlc_recovery_handoff_receipt_schema": "schemas/sdlc_recovery_handoff_receipt.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/world_substrate_replay_witness.schema.json",
    "examples/world_substrate_replay_witness.foundation.json",
    "scripts/validate_world_substrate_replay_witness.py",
    "tests/test_validate_world_substrate_replay_witness.py",
    "docs/92_world_substrate_replay_witness_contract.md",
    "docs/82_cross_repo_opportunity_map.md",
    "schemas/world_state.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "schemas/simulation_receipt.schema.json",
    "schemas/effect_assurance.schema.json",
    "schemas/sdlc_recovery_handoff_receipt.schema.json",
)
DENIED_AUTHORITY_FIELDS = (
    "live_world_service_call_performed",
    "sqlite_read_performed",
    "sqlite_write_performed",
    "world_mutation_performed",
    "replay_execution_performed",
    "planner_execution_performed",
    "executor_execution_performed",
    "branch_unquarantined",
    "external_endpoint_called",
    "secret_access_performed",
    "filesystem_write_performed",
    "raw_world_snapshot_stored",
    "raw_replay_trace_stored",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_TRUE_GUARD_FIELDS = (
    "digest_refs_required",
    "sparse_cache_truth_required",
    "legal_geometry_required",
    "invariant_registry_required",
    "planner_executor_parity_required",
    "branch_quarantine_required",
    "operator_review_required",
    "incident_handoff_required_if_live",
)
REQUIRED_FALSE_GUARD_FIELDS = (
    "raw_world_snapshot_retained",
    "raw_replay_trace_retained",
)
DIGEST_REF_FIELDS = (
    ("replay_artifacts", "world_snapshot_digest_ref"),
    ("replay_artifacts", "replay_trace_digest_ref"),
    ("replay_artifacts", "sparse_cache_digest_ref"),
    ("replay_artifacts", "invariant_registry_digest_ref"),
    ("replay_artifacts", "legal_geometry_digest_ref"),
    ("replay_artifacts", "branch_quarantine_digest_ref"),
    ("planner_executor_parity", "planner_trace_ref"),
    ("planner_executor_parity", "executor_trace_ref"),
    ("planner_executor_parity", "parity_result_ref"),
)


class WorldSubstrateReplayWitnessError(ValueError):
    """Raised when a WorldSubstrateReplayWitness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorldSubstrateReplayWitnessError(f"{label} must be a JSON object")
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
            "witness_id",
            "witness_version",
            "replay_scope",
            "replay_artifacts",
            "invariant_controls",
            "planner_executor_parity",
            "authority_boundary",
            "safety_guards",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_world_substrate_replay_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one world substrate witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("world substrate replay witness must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_scope(record.get("replay_scope"), errors)
    _validate_invariant_controls(record.get("invariant_controls"), errors)
    _validate_planner_executor_parity(record.get("planner_executor_parity"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_safety_guards(record.get("safety_guards"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_world_substrate_replay_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    witness = load_json_object(witness_path, "WorldSubstrateReplayWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_world_substrate_replay_witness_record(witness, schema))
    return errors


def build_mutated_world_substrate_replay_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness."""

    witness = load_json_object(DEFAULT_WITNESS_PATH, "WorldSubstrateReplayWitness")
    mutated = deepcopy(witness)
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

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append("witness_version must match world_substrate_replay_witness.v1")
    for parent_name, field_name in DIGEST_REF_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _validate_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("replay_scope must be an object")
        return
    if scope.get("source_family") != "external/swews-core":
        errors.append("replay_scope.source_family must be external/swews-core")
    if scope.get("borrowed_concept") != "world-substrate-replay-witness":
        errors.append("replay_scope.borrowed_concept must be world-substrate-replay-witness")
    if scope.get("foundation_mode") is not True:
        errors.append("replay_scope.foundation_mode must be true")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("replay_scope.tenant_scope must be foundation-local-only")
    if scope.get("world_substrate_mode") != "witness_only_operator_supplied_refs":
        errors.append("replay_scope.world_substrate_mode must be witness_only_operator_supplied_refs")
    if not isinstance(scope.get("uao_ref"), str) or scope.get("uao_ref") == "":
        errors.append("replay_scope.uao_ref must be non-empty")
    if scope.get("life_meaning_judgment_ref") != REQUIRED_RECEIPT_REFS["life_meaning_judgment_schema"]:
        errors.append(
            "replay_scope.life_meaning_judgment_ref must be "
            f"{REQUIRED_RECEIPT_REFS['life_meaning_judgment_schema']}"
        )


def _validate_invariant_controls(controls: Any, errors: list[str]) -> None:
    if not isinstance(controls, dict):
        errors.append("invariant_controls must be an object")
        return
    for field_name in (
        "invariant_refs",
        "sparse_cache_truth_refs",
        "legal_geometry_refs",
        "field_derivation_refs",
        "branch_quarantine_refs",
        "replay_probe_refs",
    ):
        values = controls.get(field_name)
        if not isinstance(values, list) or not values:
            errors.append(f"invariant_controls.{field_name} must contain at least one ref")
        elif len(values) != len(set(values)):
            errors.append(f"invariant_controls.{field_name} must not contain duplicates")


def _validate_planner_executor_parity(parity: Any, errors: list[str]) -> None:
    if not isinstance(parity, dict):
        errors.append("planner_executor_parity must be an object")
        return
    if parity.get("parity_verified") is not True:
        errors.append("planner_executor_parity.parity_verified must be true")
    if parity.get("divergence_count") != 0:
        errors.append("planner_executor_parity.divergence_count must be 0")
    if parity.get("planner_executor_mismatch_count") != 0:
        errors.append("planner_executor_parity.planner_executor_mismatch_count must be 0")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_safety_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("safety_guards must be an object")
        return
    for field_name in REQUIRED_TRUE_GUARD_FIELDS:
        if guards.get(field_name) is not True:
            errors.append(f"safety_guards.{field_name} must be true")
    for field_name in REQUIRED_FALSE_GUARD_FIELDS:
        if guards.get(field_name) is not False:
            errors.append(f"safety_guards.{field_name} must be false")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    controls = record.get("invariant_controls")
    boundary = record.get("authority_boundary")
    guards = record.get("safety_guards")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(controls, dict) or not isinstance(boundary, dict) or not isinstance(guards, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("invariant_controls, authority_boundary, safety_guards, receipt_refs, and contract_summary must be typed")
        return
    if summary.get("witness_only") is not True:
        errors.append("contract_summary.witness_only must be true")
    if summary.get("world_mutation_denied") is not True:
        errors.append("contract_summary.world_mutation_denied must be true")
    if summary.get("replay_execution_denied") is not True:
        errors.append("contract_summary.replay_execution_denied must be true")
    expected_counts = {
        "invariant_ref_count": _list_len(controls.get("invariant_refs")),
        "sparse_cache_truth_ref_count": _list_len(controls.get("sparse_cache_truth_refs")),
        "legal_geometry_ref_count": _list_len(controls.get("legal_geometry_refs")),
        "field_derivation_ref_count": _list_len(controls.get("field_derivation_refs")),
        "branch_quarantine_ref_count": _list_len(controls.get("branch_quarantine_refs")),
        "replay_probe_ref_count": _list_len(controls.get("replay_probe_refs")),
        "authority_denial_count": len(DENIED_AUTHORITY_FIELDS),
        "safety_guard_count": len(guards),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value or "file://" in value:
        errors.append(f"{label} must not store raw world URL, file path, or body")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate WorldSubstrateReplayWitness artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate WorldSubstrateReplayWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_world_substrate_replay_witness(args.schema, args.witness)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "world_substrate_replay_witness_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "witness_path": workspace_display_path(args.witness),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] world_substrate_replay_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
