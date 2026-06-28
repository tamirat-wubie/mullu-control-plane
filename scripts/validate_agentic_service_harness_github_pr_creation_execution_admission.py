#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR creation execution admission.

Purpose: prove live GitHub pull-request creation remains blocked until the
dry-run receipt and explicit execution authority evidence are bound.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_creation_execution_admission.schema.json,
examples/agentic_service_harness_github_pr_creation_execution_admission.foundation.json,
scripts.validate_agentic_service_harness_github_pr_creation_dry_run_receipt,
and scripts.validate_schemas.
Invariants:
  - The admission consumes the GitHub PR creation dry-run receipt.
  - Execution admission remains false in Foundation Mode.
  - PR creation, branch creation, repository writes, receipt-store append,
    connector calls, mutation routes, secret material, and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_github_pr_creation_dry_run_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_DRY_RUN_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_DRY_RUN_SCHEMA,
    EXPECTED_EXECUTION_DECISION as EXPECTED_SOURCE_EXECUTION_DECISION,
    EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
    EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
    validate_agentic_service_harness_github_pr_creation_dry_run_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_creation_execution_admission.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_pr_creation_execution_admission.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_creation_execution_admission_validation.json"
)
EXPECTED_SOURCE_DRY_RUN_REF = "examples/agentic_service_harness_github_pr_creation_dry_run_receipt.foundation.json"
EXPECTED_ADMISSION_ID = "github-pr-creation-execution-admission-foundation"
EXPECTED_ADMISSION_MODE = "PR_CREATION_EXECUTION_ADMISSION_PREFLIGHT_ONLY"
EXPECTED_SOURCE_DRY_RUN_ID = "github-pr-creation-dry-run-receipt-foundation"
EXPECTED_DECISION = "PR_CREATION_EXECUTION_BLOCKED_DRY_RUN_BOUND_AWAITING_LIVE_AUTHORITY"
EXPECTED_EXECUTION_TARGET_REF = "github-pr://agentic-service-harness/task-run"
REQUIRED_FORBIDDEN_ACTION_CLASSES = (
    "execute_adapter",
    "write_to_branch",
    "open_pr",
    "append_receipt_store",
    "deploy",
    "dns_mutation",
    "secret_mutation",
    "destructive_operation",
    "terminal_closure",
)
REQUIRED_SOURCE_REFS = (
    EXPECTED_SOURCE_DRY_RUN_REF,
    EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
    EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
    "schemas/agentic_service_harness_github_pr_creation_execution_admission.schema.json",
    "schemas/agentic_service_harness_github_pr_creation_dry_run_receipt.schema.json",
)
REQUIRED_GATE_REFS = (
    "gate://harness/no-live-adapter-execution",
    "gate://harness/no-branch-write",
    "gate://harness/no-pr-creation",
    "gate://harness/no-repository-write",
    "gate://harness/no-receipt-store-append",
    "gate://harness/no-mutation-route",
    "gate://harness/no-secret-serialization",
    "gate://harness/terminal-closure-denied",
)
REQUIRED_OBLIGATIONS = (
    "obligation://bind-pr-creation-dry-run-before-execution-admission",
    "obligation://require-operator-approval-before-live-pr-execution",
    "obligation://require-branch-write-authority-before-live-pr-execution",
    "obligation://require-uao-before-live-pr-execution",
    "obligation://require-repository-effect-rollback-before-live-pr-execution",
    "obligation://deny-live-pr-creation",
    "obligation://deny-repository-effects",
    "obligation://deny-secret-material",
    "obligation://bind-terminal-closure-blocker",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_github_pr_creation_execution_admission.py",
    "scripts/validate_agentic_service_harness_github_pr_creation_dry_run_receipt.py",
)
REQUIRED_BEFORE_EXECUTION_REFS = (
    EXPECTED_SOURCE_DRY_RUN_REF,
    "evidence://operator-approval-for-pr-execution",
    "evidence://branch-write-authority-binding",
    "evidence://uao-pr-execution-admission",
    "evidence://repository-effect-rollback-plan",
    "evidence://receipt-store-write-path-binding",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_BLOCKERS = (
    "blocked://pr-creation/execution-admission-preflight-only",
    "blocked://operator-approval/not-present",
    "blocked://branch-write-authority/not-bound",
    "blocked://uao/pr-execution-not-admitted",
    "blocked://repository-effect-rollback/not-bound",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_creation_execution_admission_schema": (
        "schemas/agentic_service_harness_github_pr_creation_execution_admission.schema.json"
    ),
    "github_pr_creation_dry_run_receipt_schema": (
        "schemas/agentic_service_harness_github_pr_creation_dry_run_receipt.schema.json"
    ),
    "github_pr_creation_dry_run_receipt_example": EXPECTED_SOURCE_DRY_RUN_REF,
    "github_pr_admission_preflight_schema": (
        "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json"
    ),
    "terminal_closure_certificate_read_model_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_read_model.schema.json"
    ),
}
REQUIRED_FALSE_FLAGS = (
    "execution_admitted",
    "pr_creation_enabled",
    "repository_write_enabled",
    "external_adapter_integrated",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "source_runtime_pr_creation_executed",
    "source_pull_request_opened",
    "source_branch_created",
    "source_repository_written",
    "source_receipt_store_appended",
    "source_adapter_executed",
    "source_connector_calls_observed",
    "source_mutation_route_called",
    "source_terminal_closure",
    "source_success_claim_allowed",
    "terminal_closure_allowed",
    "live_adapter_execution_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "mutation_route_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "admission_only",
    "dry_run_receipt_recorded",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation",
    "secret_mutation_enabled",
    "secret_values_serialized",
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
class GitHubPrCreationExecutionAdmissionValidation:
    """Validation report for GitHub PR creation execution admission."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_dry_run_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_creation_execution_admission(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_dry_run_schema_path: Path = DEFAULT_SOURCE_DRY_RUN_SCHEMA,
    source_dry_run_example_paths: Sequence[Path] = DEFAULT_SOURCE_DRY_RUN_EXAMPLES,
) -> GitHubPrCreationExecutionAdmissionValidation:
    """Validate GitHub PR creation execution admission examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR creation execution admission schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_creation_dry_run_receipt(
        schema_path=source_dry_run_schema_path,
        example_paths=source_dry_run_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source dry-run receipt: {error}" for error in source_validation.errors)
    source_dry_run = _load_json_object(
        source_dry_run_example_paths[0],
        "GitHub PR creation dry-run receipt source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR creation execution admission {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_execution_admission_semantics(example, source_dry_run, errors, _path_label(example_path))
    return GitHubPrCreationExecutionAdmissionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_dry_run_ref=EXPECTED_SOURCE_DRY_RUN_REF,
    )


def write_github_pr_creation_execution_admission_validation(
    validation: GitHubPrCreationExecutionAdmissionValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic execution-admission validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_execution_admission_semantics(
    payload: Mapping[str, Any],
    source_dry_run: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("source_pr_creation_dry_run_receipt_ref",), EXPECTED_SOURCE_DRY_RUN_REF, errors, label)
    _require_equal(
        payload,
        ("source_pr_admission_preflight_ref",),
        EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("source_terminal_closure_certificate_read_model_ref",),
        EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
        errors,
        label,
    )
    _validate_source_dry_run_binding(payload, source_dry_run, errors, label)
    _validate_contract(payload, errors, label)
    _validate_refs(payload, errors, label)
    _validate_flags_and_surface(payload, errors, label)


def _validate_source_dry_run_binding(
    payload: Mapping[str, Any],
    source_dry_run: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not source_dry_run:
        return
    for source_path, target_path in (
        (("scope", "tenant_id"), ("scope", "tenant_id")),
        (("scope", "organization_id"), ("scope", "organization_id")),
        (("scope", "project_id"), ("scope", "project_id")),
        (("scope", "repository_connection_id"), ("scope", "repository_connection_id")),
        (("scope", "repository_slug"), ("scope", "repository_slug")),
        (("scope", "task_service_id"), ("scope", "task_service_id")),
    ):
        _require_equal(payload, target_path, _get_nested(source_dry_run, source_path), errors, label)
    _require_equal(
        source_dry_run,
        ("dry_run_contract", "dry_run_id"),
        EXPECTED_SOURCE_DRY_RUN_ID,
        errors,
        "source dry-run receipt",
    )
    _require_equal(
        source_dry_run,
        ("execution_admission_gate", "decision"),
        EXPECTED_SOURCE_EXECUTION_DECISION,
        errors,
        "source dry-run receipt",
    )
    _require_equal(
        source_dry_run,
        ("execution_admission_gate", "execution_admitted"),
        False,
        errors,
        "source dry-run receipt",
    )
    for source_path, target_path in (
        (("simulated_pr_creation", "dry_run_receipt_recorded"), ("source_dry_run_binding", "dry_run_receipt_recorded")),
        (("execution_admission_gate", "decision"), ("source_dry_run_binding", "source_execution_decision")),
        (("simulated_pr_creation", "runtime_pr_creation_executed"), ("source_dry_run_binding", "source_runtime_pr_creation_executed")),
        (("simulated_pr_creation", "pull_request_opened"), ("source_dry_run_binding", "source_pull_request_opened")),
        (("simulated_pr_creation", "branch_created"), ("source_dry_run_binding", "source_branch_created")),
        (("simulated_pr_creation", "repository_written"), ("source_dry_run_binding", "source_repository_written")),
        (("simulated_pr_creation", "receipt_store_appended"), ("source_dry_run_binding", "source_receipt_store_appended")),
        (("simulated_pr_creation", "adapter_executed"), ("source_dry_run_binding", "source_adapter_executed")),
        (("simulated_pr_creation", "connector_calls_observed"), ("source_dry_run_binding", "source_connector_calls_observed")),
        (("simulated_pr_creation", "mutation_route_called"), ("source_dry_run_binding", "source_mutation_route_called")),
        (("simulated_pr_creation", "terminal_closure"), ("source_dry_run_binding", "source_terminal_closure")),
        (("simulated_pr_creation", "success_claim_allowed"), ("source_dry_run_binding", "source_success_claim_allowed")),
    ):
        _require_equal(payload, target_path, _get_nested(source_dry_run, source_path), errors, label)


def _validate_contract(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _require_equal(payload, ("execution_admission_contract", "admission_id"), EXPECTED_ADMISSION_ID, errors, label)
    _require_equal(payload, ("execution_admission_contract", "admission_mode"), EXPECTED_ADMISSION_MODE, errors, label)
    _require_equal(
        payload,
        ("execution_admission_contract", "source_dry_run_id"),
        EXPECTED_SOURCE_DRY_RUN_ID,
        errors,
        label,
    )
    _require_equal(payload, ("execution_admission_decision", "decision"), EXPECTED_DECISION, errors, label)
    _require_equal(
        payload,
        ("execution_admission_decision", "execution_target_ref"),
        EXPECTED_EXECUTION_TARGET_REF,
        errors,
        label,
    )
    _require_contains(
        payload,
        ("execution_admission_contract", "allowed_action_classes"),
        "execution_admission_preflight",
        errors,
        label,
    )
    for required_ref in REQUIRED_FORBIDDEN_ACTION_CLASSES:
        _require_contains(payload, ("execution_admission_contract", "forbidden_action_classes"), required_ref, errors, label)


def _validate_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, required_refs in (
        (("execution_admission_contract", "required_source_refs"), REQUIRED_SOURCE_REFS),
        (("execution_admission_contract", "required_gate_refs"), REQUIRED_GATE_REFS),
        (("execution_admission_contract", "admission_obligations_checked"), REQUIRED_OBLIGATIONS),
        (("execution_admission_contract", "validation_refs"), REQUIRED_VALIDATION_REFS),
        (("execution_admission_decision", "required_before_execution_refs"), REQUIRED_BEFORE_EXECUTION_REFS),
        (("execution_admission_decision", "blocked_reason_refs"), REQUIRED_BLOCKERS),
    ):
        for required_ref in required_refs:
            _require_contains(payload, path, required_ref, errors, label)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)


def _validate_flags_and_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        key = path[-1]
        dotted_path = ".".join(path)
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if key not in ALLOWED_SECRET_KEYS and any(token in key.lower() for token in FORBIDDEN_SECRET_KEY_TOKENS):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


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


def _require_contains(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: str,
    errors: list[str],
    label: str,
) -> None:
    observed = _get_nested(payload, path)
    if not isinstance(observed, list) or expected not in observed:
        errors.append(f"{label}: {'.'.join(path)} missing required ref {expected!r}")


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


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_mutated_pr_creation_execution_admission(**updates: Any) -> dict[str, Any]:
    """Build a deep-copied example with double-underscore path overrides."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--source-dry-run-schema", type=Path, default=DEFAULT_SOURCE_DRY_RUN_SCHEMA)
    parser.add_argument("--source-dry-run-example", type=Path, action="append", dest="source_dry_run_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_creation_execution_admission(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_dry_run_schema_path=args.source_dry_run_schema,
        source_dry_run_example_paths=(
            tuple(args.source_dry_run_examples) if args.source_dry_run_examples else DEFAULT_SOURCE_DRY_RUN_EXAMPLES
        ),
    )
    write_github_pr_creation_execution_admission_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR CREATION EXECUTION ADMISSION VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
