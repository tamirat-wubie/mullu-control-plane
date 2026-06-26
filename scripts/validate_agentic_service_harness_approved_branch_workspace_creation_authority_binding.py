#!/usr/bin/env python3
"""Validate approved branch workspace creation authority binding.

Purpose: prove the harness can bind a narrow branch-workspace creation
authority envelope without creating a workspace or granting later effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_approved_branch_workspace_creation_authority_binding.schema.json,
examples/agentic_service_harness_approved_branch_workspace_creation_authority_binding.foundation.json,
scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
and scripts.validate_schemas.
Invariants:
  - Source approved branch workspace preflight passes first.
  - Workspace creation authority is bounded to one confined workspace.
  - Filesystem writes, adapter execution, connector calls, receipt append, PR
    creation, mutation routes, secrets, destructive operations, and terminal
    closure remain denied.
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

from scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_PREFLIGHT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_PREFLIGHT_SCHEMA,
    validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_approved_branch_workspace_creation_authority_binding.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_approved_branch_workspace_creation_authority_binding.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_approved_branch_workspace_creation_authority_binding_validation.json"
)
EXPECTED_BINDING_ID = "agentic_service_harness_approved_branch_workspace_creation_authority_binding"
EXPECTED_SOURCE_PREFLIGHT_REF = (
    "examples/agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json"
)
EXPECTED_AUTHORITY_REQUEST_ID = "authority-binding.approved-branch-workspace-create"
EXPECTED_BRANCH_NAME = "codex/harness-branch-workspace-authority-20260626"
REQUIRED_BEFORE_AUTHORITY_BINDING_REFS = (
    EXPECTED_SOURCE_PREFLIGHT_REF,
    "approval://operator/branch-workspace-create",
    "evidence://uao/branch-workspace-create-admission",
    "evidence://cleanup-receipt-plan",
    "evidence://workspace-create-rollback-plan",
    "evidence://secret-redaction-policy",
)
REQUIRED_BEFORE_WORKSPACE_CREATE_REFS = (
    "evidence://workspace-path-confinement",
    "evidence://workspace-create-timeout-bound",
    "evidence://workspace-create-post-observation-required",
)
REQUIRED_BEFORE_TERMINAL_CLOSURE_REFS = (
    "evidence://branch-workspace-create-observed",
    "evidence://cleanup-receipt-after-workspace-use",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_RECEIPT_REFS = {
    "authority_binding_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_authority_binding.schema.json"
    ),
    "source_preflight_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_preflight.schema.json"
    ),
    "temporary_workspace_schema": (
        "schemas/agentic_service_harness_temporary_branch_workspace_preflight.schema.json"
    ),
    "workspace_sandbox_schema": "schemas/agentic_service_harness_workspace_sandbox_preflight.schema.json",
}
REQUIRED_TRUE_FLAGS = (
    "authority_binding_collected",
    "workspace_creation_authority_granted",
    "planning_only",
    "report_is_not_terminal_closure",
    "source_preflight_satisfied",
    "expires_after_single_workspace_create",
    "requires_post_create_observation",
    "requires_cleanup_receipt_before_close",
    "workspace_create_authorized",
    "required_for_closure",
)
REQUIRED_FALSE_FLAGS = (
    "workspace_created",
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
class ApprovedBranchWorkspaceCreationAuthorityBindingValidation:
    """Validation report for approved branch workspace authority binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_preflight_ref: str
    source_preflight_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_preflight_schema_path: Path = DEFAULT_SOURCE_PREFLIGHT_SCHEMA,
    source_preflight_example_paths: Sequence[Path] = DEFAULT_SOURCE_PREFLIGHT_EXAMPLES,
) -> ApprovedBranchWorkspaceCreationAuthorityBindingValidation:
    """Validate approved branch workspace creation authority binding examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "approved branch workspace authority binding schema", errors)
    source_validation = validate_agentic_service_harness_approved_branch_workspace_creation_preflight(
        schema_path=source_preflight_schema_path,
        example_paths=source_preflight_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source approved branch workspace preflight: {error}" for error in source_validation.errors)
    source_preflight = _load_json_object(
        source_preflight_example_paths[0],
        "approved branch workspace preflight source",
        errors,
    )

    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"approved branch workspace authority binding {_path_label(example_path)}",
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
        _validate_authority_binding_semantics(
            example,
            source_preflight,
            errors,
            _path_label(example_path),
        )

    return ApprovedBranchWorkspaceCreationAuthorityBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_preflight_ref=EXPECTED_SOURCE_PREFLIGHT_REF,
        source_preflight_ok=source_validation.ok,
    )


def write_approved_branch_workspace_creation_authority_binding_validation(
    validation: ApprovedBranchWorkspaceCreationAuthorityBindingValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic workspace authority binding validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_authority_binding_semantics(
    payload: Mapping[str, Any],
    source_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("binding_id",), EXPECTED_BINDING_ID, errors, label)
    _require_equal(payload, ("source_preflight_ref",), EXPECTED_SOURCE_PREFLIGHT_REF, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(payload, ("authority_kind",), "approved_branch_workspace_creation_authority", errors, label)
    _require_equal(payload, ("authority_status",), "authority_bound_not_executed", errors, label)
    _require_equal(payload, ("scope", "branch_name"), EXPECTED_BRANCH_NAME, errors, label)
    _require_equal(
        payload,
        ("scope", "workspace_mode"),
        "approved_branch_workspace_creation_authority_only",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("authority_binding", "authority_request_id"),
        EXPECTED_AUTHORITY_REQUEST_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("authority_binding", "authorized_effect"),
        "create_one_confined_branch_workspace_without_file_writes",
        errors,
        label,
    )
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_preflight:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_preflight, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_preflight, ("scope", "repository_connection_id")),
            errors,
            label,
        )
    _require_refs(
        _get_nested(payload, ("required_evidence", "before_authority_binding")),
        REQUIRED_BEFORE_AUTHORITY_BINDING_REFS,
        f"{label}: required_evidence.before_authority_binding",
        errors,
    )
    _require_refs(
        _get_nested(payload, ("required_evidence", "before_workspace_create")),
        REQUIRED_BEFORE_WORKSPACE_CREATE_REFS,
        f"{label}: required_evidence.before_workspace_create",
        errors,
    )
    _require_refs(
        _get_nested(payload, ("required_evidence", "before_terminal_closure")),
        REQUIRED_BEFORE_TERMINAL_CLOSURE_REFS,
        f"{label}: required_evidence.before_terminal_closure",
        errors,
    )
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
    else:
        for phrase in (
            "confined branch workspace",
            "filesystem write",
            "adapter execution",
            "receipt append",
            "terminal closure",
        ):
            if phrase not in next_action:
                errors.append(f"{label}: next_action must mention {phrase}")
    _validate_flags_and_forbidden_surfaces(payload, errors, label)


def _validate_flags_and_forbidden_surfaces(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        dotted_path = ".".join(path)
        key = path[-1]
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if key not in ALLOWED_SECRET_KEYS and _contains_secret_token(key):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


def _require_refs(
    observed: object,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_refs = {str(item) for item in observed}
    for required_ref in required:
        if required_ref not in observed_refs:
            errors.append(f"{label} missing required ref {required_ref}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} missing: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _require_equal(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: object,
    errors: list[str],
    label: str,
) -> None:
    observed = _get_nested(payload, path)
    if observed != expected:
        errors.append(f"{label}: {'.'.join(path)} expected {expected!r}, observed {observed!r}")


def _get_nested(payload: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _walk_leaves(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        leaves: list[tuple[tuple[str, ...], Any]] = []
        for key, child in value.items():
            leaves.extend(_walk_leaves(child, (*path, str(key))))
        return leaves
    if isinstance(value, list):
        leaves = []
        for index, child in enumerate(value):
            leaves.extend(_walk_leaves(child, (*path, str(index))))
        return leaves
    return [(path, value)]


def _contains_secret_token(key: str) -> bool:
    lowered_key = key.lower()
    return any(token in lowered_key for token in FORBIDDEN_SECRET_KEY_TOKENS)


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_mutated_authority_binding(**updates: Any) -> dict[str, Any]:
    """Build a deep-copied fixture with double-underscore path overrides."""

    payload = json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8"))
    mutated = deepcopy(payload)
    for key, value in updates.items():
        parts = key.split("__")
        current: Any = mutated
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = value
    return mutated


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse workspace authority binding validation arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--source-preflight-schema", type=Path, default=DEFAULT_SOURCE_PREFLIGHT_SCHEMA)
    parser.add_argument("--source-preflight-example", type=Path, action="append", dest="source_preflight_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run approved branch workspace creation authority binding validation."""

    args = parse_args(argv)
    validation = validate_agentic_service_harness_approved_branch_workspace_creation_authority_binding(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_preflight_schema_path=args.source_preflight_schema,
        source_preflight_example_paths=(
            tuple(args.source_preflight_examples)
            if args.source_preflight_examples
            else DEFAULT_SOURCE_PREFLIGHT_EXAMPLES
        ),
    )
    write_approved_branch_workspace_creation_authority_binding_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS APPROVED BRANCH WORKSPACE CREATION AUTHORITY BINDING VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
