#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR creation command preview.

Purpose: prove a future GitHub pull-request creation command can be previewed
without executing an adapter, opening a pull request, writing a branch, or
serializing secret material.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_creation_command_preview.schema.json,
examples/agentic_service_harness_github_pr_creation_command_preview.foundation.json,
scripts.validate_agentic_service_harness_github_pr_creation_execution_admission,
and scripts.validate_schemas.
Invariants:
  - Command preview consumes execution-admission evidence.
  - Command execution remains false in Foundation Mode.
  - PR creation, branch pushes, repository writes, receipt-store append,
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

from scripts.validate_agentic_service_harness_github_pr_creation_execution_admission import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_EXECUTION_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_EXECUTION_ADMISSION_SCHEMA,
    EXPECTED_ADMISSION_ID as EXPECTED_SOURCE_ADMISSION_ID,
    EXPECTED_DECISION as EXPECTED_SOURCE_DECISION,
    validate_agentic_service_harness_github_pr_creation_execution_admission,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_creation_command_preview.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_pr_creation_command_preview.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_creation_command_preview_validation.json"
)
EXPECTED_SOURCE_EXECUTION_ADMISSION_REF = (
    "examples/agentic_service_harness_github_pr_creation_execution_admission.foundation.json"
)
EXPECTED_PREVIEW_ID = "github-pr-creation-command-preview-foundation"
EXPECTED_PREVIEW_MODE = "PR_CREATION_COMMAND_PREVIEW_ONLY"
EXPECTED_COMMAND_ID = "github-pr-create-command-preview-foundation"
EXPECTED_COMMAND_FAMILY = "github-cli-pr-create"
EXPECTED_DECISION = "PR_CREATION_COMMAND_EXECUTION_BLOCKED_PREVIEW_ONLY"
EXPECTED_COMMAND_PREVIEW = (
    "gh pr create --base main --head <branch-ref> --title <redacted-title-ref> "
    "--body-file <redacted-body-file-ref>"
)
EXPECTED_ARGUMENT_VECTOR = (
    "gh",
    "pr",
    "create",
    "--base",
    "main",
    "--head",
    "<branch-ref>",
    "--title",
    "<redacted-title-ref>",
    "--body-file",
    "<redacted-body-file-ref>",
)
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
    EXPECTED_SOURCE_EXECUTION_ADMISSION_REF,
    "schemas/agentic_service_harness_github_pr_creation_execution_admission.schema.json",
    "examples/agentic_service_harness_github_pr_creation_dry_run_receipt.foundation.json",
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
    "obligation://bind-execution-admission-before-command-preview",
    "obligation://render-redacted-command-preview-only",
    "obligation://require-operator-approval-before-command-execution",
    "obligation://require-branch-write-authority-before-command-execution",
    "obligation://require-uao-before-command-execution",
    "obligation://require-rollback-before-command-execution",
    "obligation://deny-live-pr-creation",
    "obligation://deny-secret-material",
    "obligation://deny-terminal-closure",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_github_pr_creation_command_preview.py",
    "scripts/validate_agentic_service_harness_github_pr_creation_execution_admission.py",
)
REQUIRED_PLACEHOLDER_REFS = (
    "placeholder://branch-ref",
    "placeholder://redacted-title-ref",
    "placeholder://redacted-body-file-ref",
)
REQUIRED_BEFORE_EXECUTION_REFS = (
    "examples/agentic_service_harness_github_pr_creation_command_preview.foundation.json",
    "evidence://operator-approval-for-pr-execution",
    "evidence://branch-write-authority-binding",
    "evidence://uao-pr-execution-admission",
    "evidence://repository-effect-rollback-plan",
    "evidence://receipt-store-write-path-binding",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_BLOCKERS = (
    "blocked://pr-creation/command-preview-only",
    "blocked://operator-approval/not-present",
    "blocked://branch-write-authority/not-bound",
    "blocked://uao/pr-execution-not-admitted",
    "blocked://repository-effect-rollback/not-bound",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_creation_command_preview_schema": (
        "schemas/agentic_service_harness_github_pr_creation_command_preview.schema.json"
    ),
    "github_pr_creation_command_preview_example": (
        "examples/agentic_service_harness_github_pr_creation_command_preview.foundation.json"
    ),
    "github_pr_creation_execution_admission_schema": (
        "schemas/agentic_service_harness_github_pr_creation_execution_admission.schema.json"
    ),
    "github_pr_creation_execution_admission_example": EXPECTED_SOURCE_EXECUTION_ADMISSION_REF,
}
EXECUTION_ADMISSION_EVIDENCE_BINDINGS = (
    ("source_admission_id", ("execution_admission_contract", "admission_id")),
    ("source_decision", ("execution_admission_decision", "decision")),
    ("source_execution_admitted", ("execution_admission_decision", "execution_admitted")),
    ("source_execution_target_ref", ("execution_admission_decision", "execution_target_ref")),
    ("source_terminal_closure_allowed", ("execution_admission_decision", "terminal_closure_allowed")),
    ("source_required_before_execution_refs", ("execution_admission_decision", "required_before_execution_refs")),
    ("source_blocked_reason_refs", ("execution_admission_decision", "blocked_reason_refs")),
    ("source_dry_run_ref", ("command_preview_dry_run_receipt_evidence", "source_dry_run_ref")),
    ("source_dry_run_receipt_recorded", ("command_preview_dry_run_receipt_evidence", "source_dry_run_receipt_recorded")),
    ("source_command_preview_bound", ("command_preview_dry_run_receipt_evidence", "command_preview_bound")),
    ("source_command_preview_ref", ("command_preview_dry_run_receipt_evidence", "command_preview_ref")),
    ("source_redacted_command_preview", ("command_preview_dry_run_receipt_evidence", "redacted_command_preview")),
    ("source_operator_decision_ref", ("command_preview_dry_run_receipt_evidence", "source_operator_decision_ref")),
    ("source_decision_value", ("command_preview_dry_run_receipt_evidence", "source_decision_value")),
    ("source_pull_request_creation_enabled", ("command_preview_dry_run_receipt_evidence", "pull_request_creation_enabled")),
    ("source_repository_write_enabled", ("command_preview_dry_run_receipt_evidence", "repository_write_enabled")),
    ("source_receipt_store_append_enabled", ("command_preview_dry_run_receipt_evidence", "source_receipt_store_appended")),
    ("source_mutation_route_enabled", ("authority_denials", "mutation_route_enabled")),
    ("source_secret_values_serialized", ("scope", "secret_values_serialized")),
    ("source_adapter_executed", ("command_preview_dry_run_receipt_evidence", "source_adapter_executed")),
    ("source_connector_calls_observed", ("command_preview_dry_run_receipt_evidence", "source_connector_calls_observed")),
    ("source_terminal_closure", ("command_preview_dry_run_receipt_evidence", "source_terminal_closure")),
    ("source_success_claim_allowed", ("command_preview_dry_run_receipt_evidence", "source_success_claim_allowed")),
)
REQUIRED_FALSE_FLAGS = (
    "execution_admitted",
    "pr_creation_enabled",
    "repository_write_enabled",
    "external_adapter_integrated",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "source_execution_admitted",
    "source_terminal_closure_allowed",
    "source_pull_request_creation_enabled",
    "source_repository_write_enabled",
    "source_receipt_store_append_enabled",
    "source_mutation_route_enabled",
    "source_secret_values_serialized",
    "source_adapter_executed",
    "source_connector_calls_observed",
    "source_terminal_closure",
    "source_success_claim_allowed",
    "contains_secret_values",
    "command_executed",
    "adapter_executed",
    "connector_call_executed",
    "pull_request_opened",
    "branch_pushed",
    "repository_written",
    "receipt_store_appended",
    "mutation_route_called",
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
    "preview_only",
    "preview_rendered",
    "source_dry_run_receipt_recorded",
    "source_command_preview_bound",
    "command_preview_execution_admission_bound",
    "command_preview_remains_preview_only",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation",
    "secret_mutation_enabled",
    "secret_values_serialized",
    "source_secret_values_serialized",
    "contains_secret_values",
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
class GitHubPrCreationCommandPreviewValidation:
    """Validation report for GitHub PR creation command preview."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_execution_admission_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_creation_command_preview(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_execution_admission_schema_path: Path = DEFAULT_SOURCE_EXECUTION_ADMISSION_SCHEMA,
    source_execution_admission_example_paths: Sequence[Path] = DEFAULT_SOURCE_EXECUTION_ADMISSION_EXAMPLES,
) -> GitHubPrCreationCommandPreviewValidation:
    """Validate GitHub PR creation command preview examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR creation command preview schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_creation_execution_admission(
        schema_path=source_execution_admission_schema_path,
        example_paths=source_execution_admission_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source execution admission: {error}" for error in source_validation.errors)
    source_execution_admission = _load_json_object(
        source_execution_admission_example_paths[0],
        "GitHub PR creation execution admission source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR creation command preview {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_command_preview_semantics(example, source_execution_admission, errors, _path_label(example_path))
    return GitHubPrCreationCommandPreviewValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_execution_admission_ref=EXPECTED_SOURCE_EXECUTION_ADMISSION_REF,
    )


def write_github_pr_creation_command_preview_validation(
    validation: GitHubPrCreationCommandPreviewValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic command-preview validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_command_preview_semantics(
    payload: Mapping[str, Any],
    source_execution_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(
        payload,
        ("source_pr_creation_execution_admission_ref",),
        EXPECTED_SOURCE_EXECUTION_ADMISSION_REF,
        errors,
        label,
    )
    _validate_source_execution_admission_binding(payload, source_execution_admission, errors, label)
    _validate_execution_admission_evidence(payload, source_execution_admission, errors, label)
    _validate_contract(payload, errors, label)
    _validate_refs(payload, errors, label)
    _validate_command_shape(payload, errors, label)
    _validate_flags_and_surface(payload, errors, label)


def _validate_source_execution_admission_binding(
    payload: Mapping[str, Any],
    source_execution_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not source_execution_admission:
        return
    for source_path, target_path in (
        (("scope", "tenant_id"), ("scope", "tenant_id")),
        (("scope", "organization_id"), ("scope", "organization_id")),
        (("scope", "project_id"), ("scope", "project_id")),
        (("scope", "repository_connection_id"), ("scope", "repository_connection_id")),
        (("scope", "repository_slug"), ("scope", "repository_slug")),
        (("scope", "task_service_id"), ("scope", "task_service_id")),
    ):
        _require_equal(payload, target_path, _get_nested(source_execution_admission, source_path), errors, label)
    _require_equal(
        source_execution_admission,
        ("execution_admission_contract", "admission_id"),
        EXPECTED_SOURCE_ADMISSION_ID,
        errors,
        "source execution admission",
    )
    _require_equal(
        source_execution_admission,
        ("execution_admission_decision", "decision"),
        EXPECTED_SOURCE_DECISION,
        errors,
        "source execution admission",
    )
    for source_path, target_path in (
        (("execution_admission_contract", "admission_id"), ("source_execution_admission_binding", "source_admission_id")),
        (("execution_admission_decision", "decision"), ("source_execution_admission_binding", "source_decision")),
        (("execution_admission_decision", "execution_admitted"), ("source_execution_admission_binding", "source_execution_admitted")),
        (("execution_admission_decision", "terminal_closure_allowed"), ("source_execution_admission_binding", "source_terminal_closure_allowed")),
        (("authority_denials", "pull_request_creation_enabled"), ("source_execution_admission_binding", "source_pull_request_creation_enabled")),
        (("authority_denials", "repository_write_enabled"), ("source_execution_admission_binding", "source_repository_write_enabled")),
        (("authority_denials", "receipt_store_append_enabled"), ("source_execution_admission_binding", "source_receipt_store_append_enabled")),
        (("authority_denials", "mutation_route_enabled"), ("source_execution_admission_binding", "source_mutation_route_enabled")),
        (("scope", "secret_values_serialized"), ("source_execution_admission_binding", "source_secret_values_serialized")),
    ):
        _require_equal(payload, target_path, _get_nested(source_execution_admission, source_path), errors, label)


def _validate_execution_admission_evidence(
    payload: Mapping[str, Any],
    source_execution_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    evidence = _get_nested(payload, ("execution_admission_evidence",))
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: execution_admission_evidence must be an object")
        return
    if not source_execution_admission:
        return
    _require_equal(
        payload,
        ("execution_admission_evidence", "source_execution_admission_ref"),
        EXPECTED_SOURCE_EXECUTION_ADMISSION_REF,
        errors,
        label,
    )
    for evidence_key, source_path in EXECUTION_ADMISSION_EVIDENCE_BINDINGS:
        _require_equal(
            payload,
            ("execution_admission_evidence", evidence_key),
            _get_nested(source_execution_admission, source_path),
            errors,
            label,
        )
    _require_equal(
        payload,
        ("execution_admission_evidence", "source_redacted_command_preview"),
        _get_nested(payload, ("command_preview", "redacted_command_preview")),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("execution_admission_evidence", "command_preview_execution_admission_bound"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("execution_admission_evidence", "command_preview_remains_preview_only"),
        True,
        errors,
        label,
    )
    _require_equal(payload, ("execution_admission_evidence", "contains_secret_values"), False, errors, label)


def _validate_contract(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _require_equal(payload, ("command_preview_contract", "preview_id"), EXPECTED_PREVIEW_ID, errors, label)
    _require_equal(payload, ("command_preview_contract", "preview_mode"), EXPECTED_PREVIEW_MODE, errors, label)
    _require_equal(
        payload,
        ("command_preview_contract", "source_execution_admission_id"),
        EXPECTED_SOURCE_ADMISSION_ID,
        errors,
        label,
    )
    _require_contains(payload, ("command_preview_contract", "allowed_action_classes"), "command_preview", errors, label)
    for required_ref in REQUIRED_FORBIDDEN_ACTION_CLASSES:
        _require_contains(payload, ("command_preview_contract", "forbidden_action_classes"), required_ref, errors, label)


def _validate_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, required_refs in (
        (("command_preview_contract", "required_source_refs"), REQUIRED_SOURCE_REFS),
        (("command_preview_contract", "required_gate_refs"), REQUIRED_GATE_REFS),
        (("command_preview_contract", "preview_obligations_checked"), REQUIRED_OBLIGATIONS),
        (("command_preview_contract", "validation_refs"), REQUIRED_VALIDATION_REFS),
        (("command_preview", "placeholder_refs"), REQUIRED_PLACEHOLDER_REFS),
        (("execution_decision", "required_before_execution_refs"), REQUIRED_BEFORE_EXECUTION_REFS),
        (("execution_decision", "blocked_reason_refs"), REQUIRED_BLOCKERS),
    ):
        for required_ref in required_refs:
            _require_contains(payload, path, required_ref, errors, label)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)


def _validate_command_shape(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _require_equal(payload, ("command_preview", "command_id"), EXPECTED_COMMAND_ID, errors, label)
    _require_equal(payload, ("command_preview", "command_family"), EXPECTED_COMMAND_FAMILY, errors, label)
    _require_equal(payload, ("command_preview", "redacted_command_preview"), EXPECTED_COMMAND_PREVIEW, errors, label)
    observed_vector = _get_nested(payload, ("command_preview", "argument_vector_template"))
    if tuple(observed_vector) != EXPECTED_ARGUMENT_VECTOR:
        errors.append(
            f"{label}: command_preview.argument_vector_template expected {EXPECTED_ARGUMENT_VECTOR!r}, "
            f"observed {observed_vector!r}"
        )
    preview_text = _get_nested(payload, ("command_preview", "redacted_command_preview"))
    if isinstance(preview_text, str) and "<" not in preview_text:
        errors.append(f"{label}: command_preview.redacted_command_preview must retain redacted placeholders")


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


def build_mutated_pr_creation_command_preview(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument(
        "--source-execution-admission-schema",
        type=Path,
        default=DEFAULT_SOURCE_EXECUTION_ADMISSION_SCHEMA,
    )
    parser.add_argument(
        "--source-execution-admission-example",
        type=Path,
        action="append",
        dest="source_execution_admission_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_creation_command_preview(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_execution_admission_schema_path=args.source_execution_admission_schema,
        source_execution_admission_example_paths=(
            tuple(args.source_execution_admission_examples)
            if args.source_execution_admission_examples
            else DEFAULT_SOURCE_EXECUTION_ADMISSION_EXAMPLES
        ),
    )
    write_github_pr_creation_command_preview_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR CREATION COMMAND PREVIEW VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
