#!/usr/bin/env python3
"""Validate Agentic Service Harness filesystem write admission preflight.

Purpose: prove future filesystem writes remain blocked until branch/workspace
authority, cleanup, redaction, UAO admission, and receipt-store evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_filesystem_write_admission_preflight.schema.json,
examples/agentic_service_harness_filesystem_write_admission_preflight.foundation.json,
scripts.validate_agentic_service_harness_dry_run_test_execution_observation_receipt,
and scripts.validate_schemas.
Invariants:
  - The preflight binds to the dry-run test execution observation receipt.
  - Candidate write refs and diff refs remain empty while authority is absent.
  - Raw diffs, raw file content, receipt append, mutation routes, secrets, and
    terminal closure remain denied.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_dry_run_test_execution_observation_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_DRY_RUN_RECEIPT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_DRY_RUN_RECEIPT_SCHEMA,
    validate_agentic_service_harness_dry_run_test_execution_observation_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_filesystem_write_admission_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_filesystem_write_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_filesystem_write_admission_preflight_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_filesystem_write_admission_preflight"
EXPECTED_DRY_RUN_RECEIPT_REF = (
    "examples/agentic_service_harness_dry_run_test_execution_observation_receipt.foundation.json"
)
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_REDACTION_REF = "evidence://redaction-policy-for-file-change-collection"
EXPECTED_RECEIPT_STORE_WRITE_PATH_REF = "evidence://receipt-store-write-path-for-filesystem-write"
EXPECTED_CLEANUP_RECEIPT_REF = "evidence://cleanup-receipt-after-workspace-use"
EXPECTED_UAO_REF = "evidence://uao-filesystem-write-admission"
REQUIRED_SOURCE_REFS = (
    EXPECTED_DRY_RUN_RECEIPT_REF,
    "examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json",
    "examples/agentic_service_harness_approved_branch_workspace_creation_observation_receipt.foundation.json",
    "examples/agentic_service_harness_non_empty_diff_receipt_admission_preflight.foundation.json",
    "examples/agentic_service_harness_receipt_store_append_preflight.foundation.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_REFS = (
    "approval://operator/filesystem-write-admission",
    "evidence://branch-write-authority-binding",
    "evidence://workspace-write-authority",
    EXPECTED_CLEANUP_RECEIPT_REF,
    EXPECTED_REDACTION_REF,
    EXPECTED_UAO_REF,
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "evidence://filesystem-write-rollback-plan",
    "evidence://non-empty-diff-admission-preflight",
    "witness://no-secret-paths-in-filesystem-write",
    "witness://filesystem-write-output-redacted",
    "digest://redacted-filesystem-write-diff-bundle",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-approval/not-collected",
    "blocked://branch-write-authority/not-verified",
    "blocked://workspace-write-authority/not-verified",
    "blocked://cleanup-receipt/not-verified",
    "blocked://redaction-evidence/not-verified",
    "blocked://uao-filesystem-write/not-verified",
    "blocked://receipt-store-write-path/not-verified",
    "blocked://filesystem-write-authority/not-verified",
    "blocked://raw-diff-body/not-allowed",
    "blocked://secret-paths/not-allowed",
)
REQUIRED_NEXT_REFS = (
    "witness://actual-diff-collection-receipt",
    "evidence://branch-write-authority-binding",
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "witness://filesystem-write-output-redacted",
)
REQUIRED_RECEIPT_REFS = {
    "filesystem_write_admission_preflight_schema": (
        "schemas/agentic_service_harness_filesystem_write_admission_preflight.schema.json"
    ),
    "dry_run_test_execution_observation_example": EXPECTED_DRY_RUN_RECEIPT_REF,
    "dry_run_test_execution_observation_schema": (
        "schemas/agentic_service_harness_dry_run_test_execution_observation_receipt.schema.json"
    ),
    "receipt_store_write_path_ref": EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
    "uao_filesystem_write_admission_ref": EXPECTED_UAO_REF,
}
REQUIRED_FALSE_FLAGS = (
    "filesystem_write_admitted",
    "branch_write_authority_verified",
    "workspace_write_authority_verified",
    "operator_approval_collected",
    "cleanup_receipt_verified",
    "redaction_evidence_verified",
    "uao_filesystem_write_admission_verified",
    "receipt_store_write_path_verified",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "branch_write_enabled",
    "workspace_write_enabled",
    "raw_diff_body_stored",
    "raw_file_content_stored",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "secret_values_serialized",
    "terminal_closure",
    "raw_secret_value_storage_allowed",
    "raw_output_storage_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "dry_run_receipt_verified",
    "secret_redaction_required",
    "diff_redaction_required",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_paths_allowed",
    "secret_redaction_required",
    "secret_values_serialized",
    "raw_secret_value_storage_allowed",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FilesystemWriteAdmissionPreflightValidation:
    """Schema and semantic validation report for filesystem write admission."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    dry_run_receipt_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_filesystem_write_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    dry_run_receipt_schema_path: Path = DEFAULT_DRY_RUN_RECEIPT_SCHEMA,
    dry_run_receipt_example_paths: Sequence[Path] = DEFAULT_DRY_RUN_RECEIPT_EXAMPLES,
) -> FilesystemWriteAdmissionPreflightValidation:
    """Validate filesystem write admission preflight examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "filesystem write admission schema", errors)
    dry_run_validation = validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
        schema_path=dry_run_receipt_schema_path,
        example_paths=dry_run_receipt_example_paths,
    )
    if not dry_run_validation.ok:
        errors.extend(f"dry-run receipt: {error}" for error in dry_run_validation.errors)
    dry_run_receipt = _load_json_object(
        dry_run_receipt_example_paths[0],
        "dry-run test execution observation receipt source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"filesystem write admission example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_preflight_semantics(example, dry_run_receipt, errors, _path_label(example_path))
    return FilesystemWriteAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        dry_run_receipt_ref=EXPECTED_DRY_RUN_RECEIPT_REF,
    )


def write_filesystem_write_admission_preflight_validation(
    validation: FilesystemWriteAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic filesystem write admission validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default filesystem write admission example", [])
    mutated = deepcopy(payload)
    for dotted_key, value in updates.items():
        cursor: dict[str, Any] = mutated
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            next_value = cursor.setdefault(part, {})
            if not isinstance(next_value, dict):
                raise ValueError(f"cannot descend into non-object field: {dotted_key}")
            cursor = next_value
        cursor[parts[-1]] = value
    return mutated


def _validate_preflight_semantics(
    preflight: Mapping[str, Any],
    dry_run_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(preflight, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(preflight, ("admission_status",), "AwaitingEvidence", errors, label)
    _validate_source_refs(preflight, errors, label)
    _validate_scope(preflight, dry_run_receipt, errors, label)
    _validate_source_receipts(preflight, dry_run_receipt, errors, label)
    _validate_admission_gates(preflight, errors, label)
    _validate_filesystem_write_contract(preflight, errors, label)
    _validate_receipt_refs(preflight, errors, label)
    _validate_next_action(preflight, errors, label)
    _validate_flags(preflight, errors, label)
    _scan_forbidden_text(preflight, errors, label)


def _validate_source_refs(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    _require_all_refs(preflight.get("source_contract_refs"), REQUIRED_SOURCE_REFS, "source_contract_refs", errors, label)


def _validate_scope(
    preflight: Mapping[str, Any],
    dry_run_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(preflight.get("scope"))
    zero_scope = _mapping(dry_run_receipt.get("scope"))
    for field in ("project_id", "repository_connection_id", "repository_slug"):
        _check_value(scope, (field,), zero_scope.get(field), errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    _check_value(scope, ("foundation_phase",), "foundation_filesystem_write_admission_preflight", errors, label)


def _validate_source_receipts(
    preflight: Mapping[str, Any],
    dry_run_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    source_receipts = _mapping(preflight.get("source_receipts"))
    _check_value(source_receipts, ("dry_run_receipt_ref",), EXPECTED_DRY_RUN_RECEIPT_REF, errors, label)
    execution_observation = _mapping(dry_run_receipt.get("execution_observation"))
    effect_boundary = _mapping(dry_run_receipt.get("effect_boundary"))
    if execution_observation.get("all_exit_codes_zero") is not True:
        errors.append(f"{label}: dry-run source must prove all exit codes zero")
    if effect_boundary.get("filesystem_write_authority_granted") is not False:
        errors.append(f"{label}: dry-run source must deny filesystem write authority")
    if effect_boundary.get("receipt_store_appended") is not False:
        errors.append(f"{label}: dry-run source must deny receipt-store append")
    if source_receipts.get("dry_run_changed_file_count") != 0:
        errors.append(f"{label}: source_receipts.dry_run_changed_file_count must be 0")
    if source_receipts.get("dry_run_refs") != []:
        errors.append(f"{label}: source_receipts.dry_run_refs must be empty")


def _validate_admission_gates(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _mapping(preflight.get("admission_gates"))
    _require_all_refs(
        gates.get("required_before_filesystem_write_refs"),
        REQUIRED_BEFORE_REFS,
        "admission_gates.required_before_filesystem_write_refs",
        errors,
        label,
    )
    _require_all_refs(
        gates.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        "admission_gates.blocked_reason_refs",
        errors,
        label,
    )
    _require_all_refs(
        gates.get("next_required_evidence_refs"),
        REQUIRED_NEXT_REFS,
        "admission_gates.next_required_evidence_refs",
        errors,
        label,
    )


def _validate_filesystem_write_contract(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    contract = _mapping(preflight.get("filesystem_write_contract"))
    if contract.get("candidate_changed_file_count") != 0:
        errors.append(f"{label}: filesystem_write_contract.candidate_changed_file_count must be 0")
    if contract.get("changed_file_refs") != []:
        errors.append(f"{label}: filesystem_write_contract.changed_file_refs must be empty")
    if contract.get("diff_refs") != []:
        errors.append(f"{label}: filesystem_write_contract.diff_refs must be empty")
    if contract.get("redacted_diff_bundle_ref") != "diff-bundle://not-admitted":
        errors.append(f"{label}: filesystem_write_contract.redacted_diff_bundle_ref must remain not-admitted")
    if contract.get("receipt_append_ref") != "blocked://receipt-store-write-path/not-verified":
        errors.append(f"{label}: filesystem_write_contract.receipt_append_ref must remain blocked")


def _validate_receipt_refs(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(preflight.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_next_action(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = preflight.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be text")
        return
    required_phrases = ("actual diff collection", "filesystem write", "terminal closure blocked")
    for phrase in required_phrases:
        if phrase not in next_action:
            errors.append(f"{label}: next_action missing phrase {phrase}")


def _validate_flags(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(preflight):
        if not path:
            continue
        key = path[-1]
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _scan_forbidden_text(value: Any, errors: list[str], label: str) -> None:
    for path in _walk_paths(value):
        key = path[-1]
        normalized_key = key.lower()
        if key not in ALLOWED_SECRET_KEYS:
            for token in FORBIDDEN_SECRET_KEY_TOKENS:
                if token in normalized_key:
                    errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
    for path, item in _walk(value):
        if isinstance(item, str):
            if MUTATION_ROUTE_PATTERN.search(item):
                errors.append(f"{label}: mutation route string at {'.'.join(path)}")
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(item):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _load_json_object(path: Path, description: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{description} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{description} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check_value(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: Any,
    errors: list[str],
    label: str,
) -> None:
    cursor: Any = payload
    for part in path:
        if not isinstance(cursor, Mapping) or part not in cursor:
            errors.append(f"{label}: missing {'.'.join(path)}")
            return
        cursor = cursor[part]
    if cursor != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


def _require_all_refs(
    observed: Any,
    required: Iterable[str],
    field: str,
    errors: list[str],
    label: str,
) -> None:
    observed_set = set(observed) if isinstance(observed, list) else set()
    for required_ref in required:
        if required_ref not in observed_set:
            errors.append(f"{label}: {field} missing required ref {required_ref}")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield from _walk(nested, (*path, str(key)))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk(nested, (*path, str(index)))
    else:
        yield path, value


def _walk_paths(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, ...]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            nested_path = (*path, str(key))
            yield nested_path
            yield from _walk_paths(nested, nested_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nested_path = (*path, str(index))
            yield nested_path
            yield from _walk_paths(nested, nested_path)


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", dest="examples", action="append", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run filesystem write admission preflight validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_filesystem_write_admission_preflight(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_filesystem_write_admission_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS FILESYSTEM WRITE ADMISSION PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS FILESYSTEM WRITE ADMISSION PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
