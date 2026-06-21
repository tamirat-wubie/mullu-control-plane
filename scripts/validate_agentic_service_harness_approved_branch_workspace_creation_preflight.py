#!/usr/bin/env python3
"""Validate approved branch workspace creation preflight.

Purpose: prove branch workspace creation remains blocked until task creation
admission, temporary workspace policy, sandbox policy, operator approval, UAO
admission, cleanup evidence, and rollback evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_approved_branch_workspace_creation_preflight.schema.json,
examples/agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json,
and source validators for task creation admission, temporary branch workspace,
and workspace sandbox preflights.
Invariants:
  - Source preflight validators pass first.
  - Branch workspace creation and filesystem writes are not admitted.
  - Adapter execution, connector calls, receipt append, secrets, and terminal
    closure fail closed.
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

from scripts.validate_agentic_service_harness_task_creation_admission_preflight import (  # noqa: E402
    validate_agentic_service_harness_task_creation_admission_preflight,
)
from scripts.validate_agentic_service_harness_temporary_branch_workspace_preflight import (  # noqa: E402
    validate_agentic_service_harness_temporary_branch_workspace_preflight,
)
from scripts.validate_agentic_service_harness_workspace_sandbox_preflight import (  # noqa: E402
    validate_agentic_service_harness_workspace_sandbox_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_approved_branch_workspace_creation_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_approved_branch_workspace_creation_preflight_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_approved_branch_workspace_creation_preflight"
EXPECTED_ACTION = "create_approved_branch_workspace"
EXPECTED_ROUTE_REF = "route://harness/branch-workspace/create/not-admitted"
EXPECTED_APPROVAL_STATE = "AWAITING_OPERATOR_APPROVAL"
EXPECTED_WORKSPACE_MODE = "approved_branch_workspace_preflight_only"
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json",
    "examples/agentic_service_harness_temporary_branch_workspace_preflight.foundation.json",
    "examples/agentic_service_harness_workspace_sandbox_preflight.foundation.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_CREATE_REFS = (
    "approval://operator/branch-workspace-create",
    "evidence://task-creation-admission-remains-blocked",
    "evidence://temporary-branch-workspace-preflight-valid",
    "evidence://workspace-sandbox-preflight-valid",
    "evidence://cleanup-receipt-plan",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-approval/not-collected",
    "blocked://uao-admission/not-collected",
    "blocked://cleanup-evidence/not-collected",
    "blocked://branch-workspace/create-not-admitted",
    "blocked://filesystem-write/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_NEXT_EVIDENCE = (
    "evidence://dry-run-test-runner-plan-receipt",
    "evidence://task-record-write-uao-admission",
    "approval://adapter-execution/operator-decision",
)
REQUIRED_FALSE_FLAGS = (
    "branch_workspace_creation_admitted",
    "branch_created",
    "filesystem_write_enabled",
    "cleanup_verified",
    "secret_values_serialized",
    "operator_approval_collected",
    "uao_admission_collected",
    "cleanup_evidence_collected",
    "workspace_create_route_admitted",
    "branch_workspace_create_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "preflight_only",
    "read_only_sources",
    "task_creation_admission_valid",
    "temporary_workspace_policy_valid",
    "workspace_sandbox_policy_valid",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
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
class ApprovedBranchWorkspaceCreationPreflightValidation:
    """Validation report for approved branch workspace creation preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_validators_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_approved_branch_workspace_creation_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> ApprovedBranchWorkspaceCreationPreflightValidation:
    """Validate approved branch workspace creation preflight examples."""

    errors: list[str] = []
    source_errors = _validate_sources()
    errors.extend(source_errors)
    schema = _load_json_object(schema_path, "approved branch workspace creation schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"approved branch workspace creation example {_path_label(example_path)}",
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
        _validate_semantics(example, errors, _path_label(example_path))

    return ApprovedBranchWorkspaceCreationPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
    )


def write_approved_branch_workspace_creation_preflight_validation(
    validation: ApprovedBranchWorkspaceCreationPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic approved branch workspace validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**changes: Any) -> dict[str, Any]:
    """Return a mutated copy of the default fixture for tests."""

    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default fixture", [])
    mutated = deepcopy(payload)
    for dotted_path, value in changes.items():
        cursor: dict[str, Any] = mutated
        path_parts = dotted_path.split("__")
        for key in path_parts[:-1]:
            next_cursor = cursor[key]
            if not isinstance(next_cursor, dict):
                raise TypeError(f"cannot mutate non-object path component {key}")
            cursor = next_cursor
        cursor[path_parts[-1]] = value
    return mutated


def _validate_sources() -> list[str]:
    errors: list[str] = []
    source_results = (
        (
            "task_creation_admission_preflight",
            validate_agentic_service_harness_task_creation_admission_preflight(),
        ),
        (
            "temporary_branch_workspace_preflight",
            validate_agentic_service_harness_temporary_branch_workspace_preflight(),
        ),
        (
            "workspace_sandbox_preflight",
            validate_agentic_service_harness_workspace_sandbox_preflight(),
        ),
    )
    for source_name, validation in source_results:
        if not validation.ok:
            errors.extend(f"source {source_name} invalid: {error}" for error in validation.errors)
    return errors


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    if payload.get("report_id") != EXPECTED_REPORT_ID:
        errors.append(f"{label}: report_id must be {EXPECTED_REPORT_ID}")
    _validate_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_ref_sets(payload, errors, label)
    _validate_required_evidence(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_reference_integrity(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(payload.get("scope"))
    binding = _mapping(payload.get("approval_binding"))
    if scope.get("repository_slug") != "tamirat-wubie/mullu-control-plane":
        errors.append(f"{label}: scope.repository_slug must bind the repository")
    if scope.get("approval_gate_id") != "gate.branchwrite":
        errors.append(f"{label}: scope.approval_gate_id must bind gate.branchwrite")
    if binding.get("requested_action") != EXPECTED_ACTION:
        errors.append(f"{label}: approval_binding.requested_action must be {EXPECTED_ACTION}")
    if binding.get("requested_route_ref") != EXPECTED_ROUTE_REF:
        errors.append(f"{label}: approval_binding.requested_route_ref must remain not-admitted")
    if binding.get("approval_state") != EXPECTED_APPROVAL_STATE:
        errors.append(f"{label}: approval_binding.approval_state must be {EXPECTED_APPROVAL_STATE}")
    if binding.get("workspace_mode") != EXPECTED_WORKSPACE_MODE:
        errors.append(f"{label}: approval_binding.workspace_mode must be {EXPECTED_WORKSPACE_MODE}")
    if binding.get("branch_name_template") != "codex/harness-approved-workspace-{run_id}":
        errors.append(f"{label}: approval_binding.branch_name_template must use governed harness prefix")


def _validate_ref_sets(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    binding = _mapping(payload.get("approval_binding"))
    _require_refs(
        binding.get("required_before_create_refs"),
        REQUIRED_BEFORE_CREATE_REFS,
        f"{label}: approval_binding.required_before_create_refs",
        errors,
    )
    _require_refs(
        binding.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        f"{label}: approval_binding.blocked_reason_refs",
        errors,
    )
    _require_refs(
        binding.get("next_required_evidence_refs"),
        REQUIRED_NEXT_EVIDENCE,
        f"{label}: approval_binding.next_required_evidence_refs",
        errors,
    )


def _validate_required_evidence(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    required_evidence = _mapping(payload.get("required_evidence"))
    expected_sections = (
        "must_have_before_workspace_create",
        "must_have_before_filesystem_write",
        "must_have_before_adapter_execution",
        "must_have_before_receipt_append",
    )
    for section in expected_sections:
        refs = required_evidence.get(section)
        if not isinstance(refs, list) or len(refs) < 3:
            errors.append(f"{label}: required_evidence.{section} must contain at least three refs")
    _require_refs(
        required_evidence.get("must_have_before_workspace_create"),
        (
            "approval://operator/branch-workspace-create",
            "evidence://cleanup-receipt-plan",
            "evidence://workspace-path-confinement",
        ),
        f"{label}: required_evidence.must_have_before_workspace_create",
        errors,
    )


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _validate_secret_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        key = path[-1] if path else ""
        lowered_key = key.lower()
        if (
            any(token in lowered_key for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_no_mutation_routes(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    for phrase in (
        "dry-run test runner plan receipt",
        "branch workspace creation",
        "blocked",
        "terminal closure",
    ):
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


def _require_refs(
    actual: object,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(actual, list):
        errors.append(f"{label} must be a list")
        return
    actual_set = {str(item) for item in actual}
    for ref in required:
        if ref not in actual_set:
            errors.append(f"{label} missing required ref {ref}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label}: missing file {path}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON at line {exc.lineno}: {exc.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label}: expected JSON object")
        return {}
    return payload


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _walk_values(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_values(child, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, (*path, str(index)))
        return
    yield path, value


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse approved branch workspace preflight validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate the approved branch workspace creation preflight contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", action="append", type=Path, dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print JSON validation output.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on validation failure.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run approved branch workspace creation preflight validation."""

    args = parse_args(argv)
    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_approved_branch_workspace_creation_preflight(
        schema_path=args.schema,
        example_paths=example_paths,
    )
    write_approved_branch_workspace_creation_preflight_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS APPROVED BRANCH WORKSPACE CREATION PREFLIGHT VALID")
    else:
        print("AGENTIC SERVICE HARNESS APPROVED BRANCH WORKSPACE CREATION PREFLIGHT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
