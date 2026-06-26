#!/usr/bin/env python3
"""Validate the workspace governance witness contract.

Purpose: verify that docs/workspace-governance-witness.json has a stable
machine-readable shape and references only repository-local governance files.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library, workspace governance witness JSON, and
schemas/workspace_governance_witness.schema.json.
Invariants:
  - Validation is read-only and deterministic.
  - Witness artifact paths cannot escape the repository.
  - Artifact names and paths are unique.
  - Required governance scopes and canonical witness artifact names match exactly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "docs" / "workspace-governance-witness.json"
DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "workspace_governance_witness.schema.json"
REQUIRED_WITNESS_FIELDS = (
    "witness_id",
    "capability",
    "created_at",
    "governance_scope",
    "artifact_count",
    "artifacts",
    "block_conditions",
    "release_status",
)
REQUIRED_ARTIFACT_FIELDS = ("name", "path", "purpose")
EXPECTED_WITNESS_ID = "control_plane_workspace_governance_witness_001"
EXPECTED_CAPABILITY = "repository_local_workspace_governance_surface"
EXPECTED_RELEASE_STATUS = "ready_for_repository_preflight_use"
REQUIRED_GOVERNANCE_SCOPES = frozenset(
    {
        "agents_policy_surface",
        "workspace_governance_preflight",
        "governance_artifact_inventory",
        "governance_artifact_integrity",
        "sdlc_pr_enforcement",
        "universal_action_orchestration",
    }
)


def _foundation_boundary_artifact_name(kind: str, path: Path) -> str:
    """Return the canonical witness artifact name for one Foundation boundary file."""

    if kind == "doc":
        stem = path.stem.lower()
    elif kind == "validator":
        stem = path.stem.removeprefix("validate_")
    elif kind == "tests":
        stem = path.stem.removeprefix("test_validate_")
    else:  # pragma: no cover - defensive guard for future callers.
        raise ValueError(f"unknown foundation boundary artifact kind: {kind}")
    return f"foundation_boundary_{kind}_{stem}"


def _required_foundation_boundary_artifact_names(workspace_root: Path = WORKSPACE_ROOT) -> frozenset[str]:
    """Return witness artifact names required for all Foundation boundary files."""

    docs = sorted((workspace_root / "docs").glob("FOUNDATION_*BOUNDARY.md"))
    validators = sorted((workspace_root / "scripts").glob("validate_foundation_*_boundary.py"))
    tests = sorted((workspace_root / "tests").glob("test_validate_foundation_*_boundary.py"))
    return frozenset(
        {
            *(_foundation_boundary_artifact_name("doc", path) for path in docs),
            *(_foundation_boundary_artifact_name("validator", path) for path in validators),
            *(_foundation_boundary_artifact_name("tests", path) for path in tests),
        }
    )


BASE_REQUIRED_ARTIFACT_NAMES = frozenset(
    {
        "agents_policy",
        "agents_policy_validator",
        "ci_workflow",
        "governance_normalization_map_document",
        "governance_normalization_map_tests",
        "governance_normalization_map_validator",
        "governed_code_change_loop_blocked_request_example",
        "governed_code_change_loop_receipt_validator",
        "governed_code_change_loop_receipt_validator_tests",
        "governed_code_change_loop_runner",
        "governed_code_change_loop_runner_image",
        "governed_code_change_loop_runner_tests",
        "governed_code_change_loop_sandbox_probe",
        "governed_code_change_loop_sandbox_probe_example",
        "governed_code_change_loop_sandbox_probe_tests",
        "governed_code_change_loop_sandbox_probe_validator",
        "governed_code_change_loop_sandbox_probe_validator_tests",
        "governed_code_change_loop_sandbox_readiness_runbook",
        "governed_code_change_loop_sandbox_readiness_runbook_validator",
        "governed_code_change_loop_sandbox_readiness_runbook_tests",
        "governed_code_change_loop_tests",
        "governed_code_change_loop_windows_readiness_assessor",
        "governed_code_change_loop_windows_readiness_assessor_tests",
        "governed_code_change_loop_wsl_strict_probe_launcher",
        "governed_code_change_loop_wsl_strict_probe_launcher_tests",
        "logic_governance_application_validator",
        "life_continuity_conflict_doctrine_document",
        "life_meaning_contract",
        "life_meaning_codex_notice",
        "life_meaning_deployment_example",
        "life_meaning_finance_payment_example",
        "life_meaning_governance_kernel_document",
        "life_meaning_governance_kernel_runtime",
        "life_meaning_governance_tests",
        "life_meaning_governance_validator",
        "life_meaning_governance_validator_tests",
        "life_meaning_judgment_schema",
        "life_meaning_local_proof_example",
        "life_meaning_meaning_through_feeling_document",
        "life_meaning_unknown_life_environment_example",
        "life_meaning_universal_symbol_continuity_document",
        "mullu_governance_protocol_document",
        "mullu_governance_protocol_manifest",
        "proprietary_boundary_validator",
        "protocol_manifest_validator",
        "public_repository_surface_validator",
        "pull_request_template",
        "release_status_validator",
        "sdlc_artifact_tests",
        "sdlc_artifact_validator",
        "sdlc_branch_ruleset_witness",
        "sdlc_contract_document",
        "sdlc_pr_enforcement_document",
        "sdlc_pr_enforcement_validator",
        "sdlc_release_readiness_validator",
        "sdlc_route_helper",
        "sdlc_route_tests",
        "sdlc_route_validator",
        "sdlc_security_review_validator",
        "sdlc_state_machine_validator",
        "private_pilot_uao_story_tests",
        "trusted_local_control_studio_doc",
        "trusted_local_control_studio_tests",
        "trusted_local_control_studio_validator",
        "universal_action_kernel_tests",
        "universal_action_orchestration_allowed_example",
        "universal_action_orchestration_blocked_example",
        "universal_action_orchestration_blocked_missing_approval_example",
        "universal_action_orchestration_deferred_stale_evidence_example",
        "universal_action_orchestration_document",
        "universal_action_orchestration_gateway_replay_tests",
        "universal_action_orchestration_receipt_contract_validator",
        "universal_action_orchestration_receipt_contract_tests",
        "universal_action_orchestration_receipt_validator",
        "universal_action_orchestration_receipt_tests",
        "universal_action_orchestration_runtime_bypass_detector",
        "universal_action_orchestration_runtime_bypass_tests",
        "universal_action_orchestration_schema",
        "universal_action_orchestration_simulated_low_risk_readonly_example",
        "universal_action_orchestration_validation_receipt_example",
        "universal_action_orchestration_validation_receipt_schema",
        "universal_action_orchestration_validator",
        "universal_action_orchestration_validator_tests",
        "workspace_governance_integrity_reporter",
        "workspace_governance_integrity_report_schema",
        "workspace_governance_integrity_report_example",
        "workspace_governance_integrity_report_contract_validator",
        "workspace_governance_integrity_report_contract_tests",
        "workspace_governance_integrity_tests",
        "workspace_governance_inventory_reporter",
        "workspace_governance_inventory_report_schema",
        "workspace_governance_inventory_report_example",
        "workspace_governance_inventory_report_contract_validator",
        "workspace_governance_inventory_report_contract_tests",
        "workspace_governance_inventory_tests",
        "workspace_governance_preflight_runner",
        "workspace_governance_preflight_receipt_contract_validator",
        "workspace_governance_preflight_receipt_example",
        "workspace_governance_preflight_receipt_schema",
        "workspace_governance_preflight_receipt_validator",
        "workspace_governance_preflight_tests",
        "workspace_governance_witness",
        "workspace_governance_witness_schema",
        "workspace_governance_witness_tests",
        "workspace_governance_witness_validator",
    }
)
REQUIRED_ARTIFACT_NAMES = BASE_REQUIRED_ARTIFACT_NAMES | _required_foundation_boundary_artifact_names()
REQUIRED_BLOCK_CONDITIONS = frozenset(
    {
        "witness references a missing artifact",
        "witness artifact path escapes the repository",
        "workspace governance witness schema absent or failing",
        "governance inventory report counts contradict artifact records",
        "workspace governance preflight omits inventory, integrity, or witness validation",
        "workspace governance witness omits Foundation boundary docs validators or tests",
        "workspace governance witness omits governance normalization map artifacts",
        "workspace governance witness omits Life Continuity Conflict Doctrine",
        "workspace governance witness omits Life-Meaning Governance Kernel artifacts",
        "governed code-change loop receipt validator rejects the evidence artifact",
        "governed code-change loop sandbox probe reports unvalidated execution readiness",
        "governed code-change loop sandbox probe validator rejects the evidence artifact",
        "governed code-change loop sandbox readiness runbook validator rejects the handoff",
        "governed code-change loop WSL launcher contract is missing or drifted",
        "governed code-change loop Windows readiness assessor contract is missing or drifted",
        "workspace governance witness omits Universal Action Orchestration artifacts",
    }
)


class WorkspaceGovernanceWitnessError(ValueError):
    """Raised when the workspace governance witness contract is invalid."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit artifact identity."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkspaceGovernanceWitnessError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact validation errors."""

    errors: list[str] = []
    if schema.get("$id") != "urn:mullusi:schema:workspace-governance-witness:1":
        errors.append("schema $id does not identify workspace governance witness")
    if schema.get("title") != "Workspace Governance Witness":
        errors.append("schema title does not identify workspace governance witness")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")

    required_fields = schema.get("required")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    else:
        for field_name in REQUIRED_WITNESS_FIELDS:
            if field_name not in required_fields:
                errors.append(f"schema missing required witness field: {field_name}")

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    else:
        for field_name in REQUIRED_WITNESS_FIELDS:
            if field_name not in properties:
                errors.append(f"schema missing witness property: {field_name}")

    artifact_required = schema.get("$defs", {}).get("witness_artifact", {}).get("required", [])
    if not isinstance(artifact_required, list):
        errors.append("schema witness_artifact.required must be a list")
    else:
        for field_name in REQUIRED_ARTIFACT_FIELDS:
            if field_name not in artifact_required:
                errors.append(f"schema missing required artifact field: {field_name}")
    return errors


def validate_witness(witness: dict[str, Any], workspace_root: Path = WORKSPACE_ROOT) -> list[str]:
    """Return deterministic validation errors for one governance witness."""

    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_WITNESS_FIELDS if field_name not in witness]
    errors.extend(f"witness missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(witness) - set(REQUIRED_WITNESS_FIELDS))
    errors.extend(f"witness has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors

    if witness["witness_id"] != EXPECTED_WITNESS_ID:
        errors.append("witness_id is invalid")
    if witness["capability"] != EXPECTED_CAPABILITY:
        errors.append("capability is invalid")
    if witness["release_status"] != EXPECTED_RELEASE_STATUS:
        errors.append("release_status is invalid")
    if not isinstance(witness["created_at"], str) or not witness["created_at"]:
        errors.append("created_at must be a non-empty string")

    errors.extend(_validate_string_set("governance_scope", witness["governance_scope"], REQUIRED_GOVERNANCE_SCOPES))
    errors.extend(_validate_string_set("block_conditions", witness["block_conditions"], REQUIRED_BLOCK_CONDITIONS))

    artifacts = witness["artifacts"]
    if not isinstance(artifacts, list):
        errors.append("artifacts must be a list")
        return errors
    if isinstance(witness["artifact_count"], bool) or not isinstance(witness["artifact_count"], int):
        errors.append("artifact_count must be integer")
    elif witness["artifact_count"] != len(artifacts):
        errors.append("artifact_count must match artifacts length")

    observed_names: list[str] = []
    observed_paths: list[str] = []
    for index, artifact in enumerate(artifacts):
        errors.extend(_validate_artifact_record(artifact, index, workspace_root))
        if isinstance(artifact, dict) and isinstance(artifact.get("name"), str):
            observed_names.append(artifact["name"])
        if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
            observed_paths.append(artifact["path"])

    duplicate_names = sorted(_find_duplicates(observed_names))
    duplicate_paths = sorted(_find_duplicates(observed_paths))
    errors.extend(f"duplicate artifact name: {name}" for name in duplicate_names)
    errors.extend(f"duplicate artifact path: {path}" for path in duplicate_paths)
    observed_name_set = set(observed_names)
    missing_artifact_names = sorted(REQUIRED_ARTIFACT_NAMES - observed_name_set)
    if missing_artifact_names:
        errors.append(f"witness missing required artifact name(s): {', '.join(missing_artifact_names)}")
    unexpected_artifact_names = sorted(observed_name_set - REQUIRED_ARTIFACT_NAMES)
    if unexpected_artifact_names:
        errors.append(f"witness has unexpected artifact name(s): {', '.join(unexpected_artifact_names)}")
    return errors


def validate_contract(
    witness_path: Path = DEFAULT_WITNESS_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    workspace_root: Path = WORKSPACE_ROOT,
) -> list[str]:
    """Validate schema and witness artifacts."""

    schema = load_json_object(schema_path, "workspace governance witness schema")
    witness = load_json_object(witness_path, "workspace governance witness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_witness(witness, workspace_root))
    return errors


def _validate_string_set(field_name: str, value: Any, required_values: frozenset[str]) -> list[str]:
    if not isinstance(value, list):
        return [f"{field_name} must be a list"]
    errors: list[str] = []
    observed_values: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            errors.append(f"{field_name} {index} must be a non-empty string")
        else:
            observed_values.append(item)
    duplicate_values = sorted(_find_duplicates(observed_values))
    errors.extend(f"{field_name} contains duplicate value: {item}" for item in duplicate_values)
    missing_values = sorted(required_values - set(observed_values))
    if missing_values:
        errors.append(f"{field_name} missing required value(s): {', '.join(missing_values)}")
    return errors


def _validate_artifact_record(artifact: Any, index: int, workspace_root: Path) -> list[str]:
    if not isinstance(artifact, dict):
        return [f"artifact {index} must be an object"]
    errors: list[str] = []
    missing_fields = [field_name for field_name in REQUIRED_ARTIFACT_FIELDS if field_name not in artifact]
    errors.extend(f"artifact {index} missing field: {field_name}" for field_name in missing_fields)
    extra_fields = sorted(set(artifact) - set(REQUIRED_ARTIFACT_FIELDS))
    errors.extend(f"artifact {index} has unexpected field: {field_name}" for field_name in extra_fields)
    if missing_fields:
        return errors

    for field_name in REQUIRED_ARTIFACT_FIELDS:
        if not isinstance(artifact[field_name], str) or not artifact[field_name]:
            errors.append(f"artifact {index} {field_name} must be a non-empty string")
    path_value = artifact["path"]
    if isinstance(path_value, str) and path_value:
        path_issue = _validate_relative_file_path(path_value, workspace_root)
        if path_issue is not None:
            errors.append(f"artifact {index} path invalid: {path_issue}")
    return errors


def _validate_relative_file_path(relative_path: str, workspace_root: Path) -> str | None:
    path = Path(relative_path)
    if path.is_absolute():
        return "absolute path is not allowed"
    if "\\" in relative_path:
        return "backslash path is not allowed"
    if any(path_part in ("", ".", "..") for path_part in path.parts):
        return "path segments must be explicit repository-local names"
    resolved_root = workspace_root.resolve()
    resolved_path = (workspace_root / relative_path).resolve()
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        return "path escapes the repository"
    if not resolved_path.is_file():
        return "referenced file does not exist"
    return None


def _find_duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def main(argv: list[str] | None = None) -> int:
    """Validate the workspace governance witness contract."""

    parser = argparse.ArgumentParser(description="Validate workspace governance witness contract.")
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH, help="path to governance witness JSON")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="path to governance witness schema")
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.witness, args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-workspace-governance-witness: {exc}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] workspace-governance-witness: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] workspace_governance_witness_schema\n")
    sys.stdout.write("[PASS] workspace_governance_witness_shape\n")
    sys.stdout.write("[PASS] workspace_governance_witness_artifacts\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
