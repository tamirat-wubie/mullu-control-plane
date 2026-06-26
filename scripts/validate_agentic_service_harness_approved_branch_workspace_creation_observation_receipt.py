#!/usr/bin/env python3
"""Validate approved branch workspace creation observation receipt.

Purpose: prove one approved branch workspace creation can be observed after
authority binding without granting later harness effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_approved_branch_workspace_creation_observation_receipt.schema.json,
examples/agentic_service_harness_approved_branch_workspace_creation_observation_receipt.foundation.json,
scripts.validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding,
and scripts.validate_schemas.
Invariants:
  - Source approved branch workspace authority binding passes first.
  - The receipt observes only one confined workspace create effect.
  - File writes, branch pushes, adapter execution, connector calls, receipt
    append, PR creation, mutation routes, secrets, destructive operations, and
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
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_AUTHORITY_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_AUTHORITY_SCHEMA,
    EXPECTED_AUTHORITY_REQUEST_ID,
    validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_approved_branch_workspace_creation_observation_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_approved_branch_workspace_creation_observation_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_approved_branch_workspace_creation_observation_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_approved_branch_workspace_creation_observation_receipt"
EXPECTED_SOURCE_AUTHORITY_REF = (
    "examples/agentic_service_harness_approved_branch_workspace_creation_authority_binding.foundation.json"
)
EXPECTED_BRANCH_NAME = "codex/harness-branch-workspace-observation-20260626"
REQUIRED_NEXT_EVIDENCE_REFS = {
    "before_filesystem_write": (
        "evidence://workspace/post-create-observation",
        "evidence://filesystem-write-rollback-plan",
        "evidence://non-empty-diff-admission-preflight",
    ),
    "before_adapter_execution": (
        "approval://adapter-execution/operator-decision",
        "evidence://worker-lease-sandbox-boundary",
        "evidence://executed-test-receipt-admission-preflight",
    ),
    "before_receipt_append": (
        "evidence://receipt-store-append-preflight",
        "evidence://workspace-post-create-observation-digest",
        "evidence://receipt-append-idempotency-key",
    ),
    "before_pull_request_creation": (
        "evidence://github-pr-admission-preflight",
        "evidence://branch-write-authority-binding",
        "evidence://effect-reconciliation-before-pr",
    ),
    "before_terminal_closure": (
        "evidence://cleanup-receipt-after-workspace-use",
        "evidence://effect-reconciliation-before-terminal-closure",
        "evidence://terminal-closure-certificate-candidate",
    ),
}
REQUIRED_RECEIPT_REFS = {
    "observation_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_observation_receipt.schema.json"
    ),
    "source_authority_binding_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_authority_binding.schema.json"
    ),
    "source_preflight_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_preflight.schema.json"
    ),
}
REQUIRED_TRUE_FLAGS = (
    "workspace_creation_observed",
    "workspace_created",
    "report_is_not_terminal_closure",
    "source_authority_binding_satisfied",
    "workspace_path_confined",
    "cleanup_required_before_close",
    "workspace_create_authorized",
    "required_for_closure",
)
REQUIRED_FALSE_FLAGS = (
    "planning_only",
    "terminal_closure",
    "filesystem_written",
    "branch_pushed",
    "pull_request_opened",
    "adapter_executed",
    "connector_called",
    "receipt_store_appended",
    "mutation_route_admitted",
    "secret_values_serialized",
    "filesystem_write_enabled",
    "branch_push_enabled",
    "pull_request_creation_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "destructive_operation_enabled",
    "default_high_risk_authority",
)
ALLOWED_SECRET_KEYS = {"secret_values_serialized"}
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
class ApprovedBranchWorkspaceCreationObservationReceiptValidation:
    """Validation report for approved branch workspace creation observation."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_authority_binding_ref: str
    source_authority_binding_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_authority_schema_path: Path = DEFAULT_SOURCE_AUTHORITY_SCHEMA,
    source_authority_example_paths: Sequence[Path] = DEFAULT_SOURCE_AUTHORITY_EXAMPLES,
) -> ApprovedBranchWorkspaceCreationObservationReceiptValidation:
    """Validate approved branch workspace creation observation examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "approved branch workspace observation schema", errors)
    source_validation = validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding(
        schema_path=source_authority_schema_path,
        example_paths=source_authority_example_paths,
    )
    if not source_validation.ok:
        errors.extend(
            f"source approved branch workspace authority binding: {error}"
            for error in source_validation.errors
        )
    source_authority = _load_json_object(
        source_authority_example_paths[0],
        "approved branch workspace authority binding source",
        errors,
    )

    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"approved branch workspace observation {_path_label(example_path)}",
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
        _validate_observation_semantics(example, source_authority, errors, _path_label(example_path))

    return ApprovedBranchWorkspaceCreationObservationReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_authority_binding_ref=EXPECTED_SOURCE_AUTHORITY_REF,
        source_authority_binding_ok=source_validation.ok,
    )


def write_approved_branch_workspace_creation_observation_receipt_validation(
    validation: ApprovedBranchWorkspaceCreationObservationReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic workspace observation validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_observation_semantics(
    payload: Mapping[str, Any],
    source_authority: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _require_equal(payload, ("source_authority_binding_ref",), EXPECTED_SOURCE_AUTHORITY_REF, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(
        payload,
        ("observation_status",),
        "workspace_creation_observed_without_later_effects",
        errors,
        label,
    )
    _require_equal(payload, ("scope", "branch_name"), EXPECTED_BRANCH_NAME, errors, label)
    _require_equal(payload, ("observation", "created_branch_name"), EXPECTED_BRANCH_NAME, errors, label)
    _require_equal(
        payload,
        ("scope", "workspace_mode"),
        "approved_branch_workspace_creation_observation_only",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("observation", "authority_request_id"),
        EXPECTED_AUTHORITY_REQUEST_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("observation", "observed_effect"),
        "created_one_confined_branch_workspace_without_file_writes",
        errors,
        label,
    )
    _validate_source_authority_consistency(payload, source_authority, errors, label)
    _require_flags(payload, REQUIRED_TRUE_FLAGS, True, errors, label)
    _require_flags(payload, REQUIRED_FALSE_FLAGS, False, errors, label)
    _require_next_evidence_refs(payload, errors, label)
    _require_receipt_refs(payload, errors, label)
    _reject_forbidden_text(payload, errors, label)


def _validate_source_authority_consistency(
    payload: Mapping[str, Any],
    source_authority: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    source_scope = source_authority.get("scope")
    scope = payload.get("scope")
    if not isinstance(source_scope, Mapping) or not isinstance(scope, Mapping):
        errors.append(f"{label}: missing source or observation scope")
        return
    for field in (
        "tenant_id",
        "organization_id",
        "project_id",
        "repository_connection_id",
        "repository_slug",
        "workspace_root_policy_ref",
    ):
        if scope.get(field) != source_scope.get(field):
            errors.append(f"{label}: scope.{field} does not match source authority binding")
    if source_authority.get("workspace_creation_authority_granted") is not True:
        errors.append(f"{label}: source authority binding did not grant workspace creation authority")
    source_effect_boundary = source_authority.get("effect_boundary")
    if not isinstance(source_effect_boundary, Mapping):
        errors.append(f"{label}: source authority binding missing effect_boundary")
    elif source_effect_boundary.get("workspace_created") is not False:
        errors.append(f"{label}: source authority binding must precede workspace creation")


def _require_flags(
    payload: Mapping[str, Any],
    names: Sequence[str],
    expected: bool,
    errors: list[str],
    label: str,
) -> None:
    for name in names:
        paths = _find_key_paths(payload, name)
        if not paths:
            errors.append(f"{label}: missing required flag {name}")
            continue
        for path in paths:
            actual = _get_path(payload, path)
            if actual is not expected:
                errors.append(f"{label}: {'.'.join(path)} must be {str(expected).lower()}")


def _require_next_evidence_refs(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    required_next_evidence = payload.get("required_next_evidence")
    if not isinstance(required_next_evidence, Mapping):
        errors.append(f"{label}: required_next_evidence must be an object")
        return
    for key, required_refs in REQUIRED_NEXT_EVIDENCE_REFS.items():
        refs = required_next_evidence.get(key)
        if not isinstance(refs, list):
            errors.append(f"{label}: required_next_evidence.{key} must be a list")
            continue
        for required_ref in required_refs:
            if required_ref not in refs:
                errors.append(
                    f"{label}: required_next_evidence.{key} missing required ref {required_ref}"
                )


def _require_receipt_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = payload.get("receipt_refs")
    if not isinstance(receipt_refs, Mapping):
        errors.append(f"{label}: receipt_refs must be an object")
        return
    for key, expected_ref in REQUIRED_RECEIPT_REFS.items():
        actual_ref = receipt_refs.get(key)
        if actual_ref != expected_ref:
            errors.append(f"{label}: receipt_refs.{key} must equal {expected_ref}")


def _reject_forbidden_text(value: Any, errors: list[str], label: str, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            next_path = (*path, str(key))
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_SECRET_KEYS and any(
                token in normalized_key for token in FORBIDDEN_SECRET_KEY_TOKENS
            ):
                errors.append(f"{label}: forbidden secret-bearing key {'.'.join(next_path)}")
            _reject_forbidden_text(nested_value, errors, label, next_path)
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            _reject_forbidden_text(nested_value, errors, label, (*path, str(index)))
    elif isinstance(value, str):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string is not allowed at {'.'.join(path)}")
        for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{label}: credential-like value is not allowed at {'.'.join(path)}")


def build_mutated_observation_receipt(**updates: Any) -> dict[str, Any]:
    """Return a mutated copy of the default observation fixture for tests."""

    payload = json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8"))
    for dotted_key, value in updates.items():
        keys = dotted_key.split("__")
        target: dict[str, Any] = payload
        for key in keys[:-1]:
            nested = target.get(key)
            if not isinstance(nested, dict):
                nested = {}
                target[key] = nested
            target = nested
        target[keys[-1]] = deepcopy(value)
    return payload


def _load_json_object(path: Path, description: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{description} not found: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{description} is not valid JSON: {_path_label(path)}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{description} must be a JSON object: {_path_label(path)}")
        return {}
    return payload


def _find_key_paths(value: Any, target_key: str, prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_path = (*prefix, str(key))
            if key == target_key:
                paths.append(key_path)
            paths.extend(_find_key_paths(nested_value, target_key, key_path))
    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            paths.extend(_find_key_paths(nested_value, target_key, (*prefix, str(index))))
    return paths


def _get_path(value: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = value
    for part in path:
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def _require_equal(
    payload: Mapping[str, Any],
    path: Sequence[str],
    expected: Any,
    errors: list[str],
    label: str,
) -> None:
    actual = _get_path(payload, path)
    if actual != expected:
        errors.append(f"{label}: {'.'.join(path)} must equal {expected!r}")


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the approved branch workspace creation observation receipt contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="print machine-readable validation report")
    parser.add_argument("--strict", action="store_true", help="return non-zero when validation fails")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run approved branch workspace creation observation validation."""

    args = _parse_args(argv)
    validation = validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    if args.output:
        write_approved_branch_workspace_creation_observation_receipt_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("[PASS] agentic_service_harness_approved_branch_workspace_creation_observation_receipt")
        print("STATUS: passed")
    else:
        print("[FAIL] agentic_service_harness_approved_branch_workspace_creation_observation_receipt")
        for error in validation.errors:
            print(f"  - {error}")
        print("STATUS: failed")
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
