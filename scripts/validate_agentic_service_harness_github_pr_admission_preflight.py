#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR admission preflight.

Purpose: prove a future GitHub pull-request action remains blocked until
operator approval, branch-write authority, UAO admission, rollback, and CI
evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_admission_preflight.schema.json,
examples/agentic_service_harness_github_pr_admission_preflight.foundation.json,
agentic_service_harness_non_empty_diff_file_summary_receipt schema/example,
scripts.validate_agentic_service_harness_github_task_receipt_emitter_dry_run, and scripts.validate_schemas.
Invariants:
  - The preflight binds to the GitHub task receipt-emitter dry-run.
  - The preflight binds to the non-empty diff file summary receipt before PR admission.
  - Operator approval is absent and PR admission is denied.
  - Branch writes, PR creation, repository writes, adapter execution, connector
    calls, mutation routes, secret material, and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_github_task_receipt_emitter_dry_run import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_RECEIPT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_RECEIPT_SCHEMA,
    validate_agentic_service_harness_github_task_receipt_emitter_dry_run,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_admission_preflight.schema.json"
DEFAULT_EXAMPLES = (REPO_ROOT / "examples" / "agentic_service_harness_github_pr_admission_preflight.foundation.json",)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_admission_preflight_validation.json"
)
DEFAULT_FILE_SUMMARY_RECEIPT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json"
)
DEFAULT_FILE_SUMMARY_RECEIPT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json",
)
EXPECTED_SOURCE_RECEIPT_REF = "examples/agentic_service_harness_github_task_receipt_emitter_dry_run.foundation.json"
EXPECTED_FILE_SUMMARY_RECEIPT_REF = (
    "examples/agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json"
)
EXPECTED_TASK_SERVICE_ID = "github-repo-task-service-read-only-foundation"
EXPECTED_SOURCE_TASK_REF = "task://agentic-service-harness/github-repo-read-only"
EXPECTED_PREFLIGHT_ID = "github-pr-admission-preflight-foundation"
EXPECTED_PREFLIGHT_MODE = "PR_ADMISSION_PREFLIGHT_ONLY"
EXPECTED_RESULT_STATE = "PR_ADMISSION_PREFLIGHT_RECORDED"
EXPECTED_SIMULATED_ACTION_KIND = "future_github_pull_request_admission"
EXPECTED_APPROVAL_DECISION = "PR_ADMISSION_BLOCKED_AWAITING_OPERATOR_APPROVAL_AND_BRANCH_BINDING"
EXPECTED_APPROVAL_TARGET_REF = "github-pr://agentic-service-harness/task-run"
REQUIRED_ALLOWED_ACTION_CLASSES = ("dry_run", "approval_preflight")
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
    EXPECTED_SOURCE_RECEIPT_REF,
    EXPECTED_FILE_SUMMARY_RECEIPT_REF,
    "examples/agentic_service_harness_github_repo_task_service.foundation.json",
    "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json",
)
REQUIRED_GATE_REFS = (
    "gate://harness/no-live-adapter-execution",
    "gate://harness/no-branch-write",
    "gate://harness/no-pr-creation",
    "gate://harness/no-repository-write",
    "gate://harness/no-mutation-route",
    "gate://harness/no-secret-serialization",
    "gate://harness/terminal-closure-denied",
)
REQUIRED_ADMISSION_OBLIGATIONS = (
    "obligation://record-pr-admission-preflight",
    "obligation://require-operator-approval-before-pr",
    "obligation://require-branch-write-authority-before-pr",
    "obligation://deny-pr-creation-without-approval",
    "obligation://deny-repository-effects",
    "obligation://deny-secret-material",
    "obligation://bind-terminal-closure-blocker",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_github_pr_admission_preflight.py",
    "scripts/validate_agentic_service_harness_github_task_receipt_emitter_dry_run.py",
    "scripts/validate_agentic_service_harness_non_empty_diff_file_summary_receipt.py",
    "scripts/validate_agentic_service_harness_github_repo_task_service.py",
)
REQUIRED_BEFORE_PR_REFS = (
    EXPECTED_FILE_SUMMARY_RECEIPT_REF,
    "evidence://operator-approval-for-pr-admission",
    "evidence://branch-write-authority-binding",
    "evidence://repository-effect-rollback-plan",
    "evidence://uao-pr-admission",
    "evidence://ci-gate-before-ready-for-review",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-approval/not-present",
    "blocked://branch-write-authority/not-bound",
    "blocked://pr-creation/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_admission_preflight_schema": (
        "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json"
    ),
    "github_task_receipt_emitter_dry_run_schema": (
        "schemas/agentic_service_harness_github_task_receipt_emitter_dry_run.schema.json"
    ),
    "non_empty_diff_file_summary_receipt_schema": (
        "schemas/agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json"
    ),
    "non_empty_diff_file_summary_receipt_example": EXPECTED_FILE_SUMMARY_RECEIPT_REF,
    "github_repo_task_service_schema": "schemas/agentic_service_harness_github_repo_task_service.schema.json",
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "agentic_service_harness_read_models_schema": "schemas/agentic_service_harness_read_models.schema.json",
}
REQUIRED_FALSE_FLAGS = (
    "operator_approval_present",
    "branch_write_authority_enabled",
    "pull_request_creation_enabled",
    "repository_write_enabled",
    "external_adapter_integrated",
    "secret_values_serialized",
    "pr_admitted",
    "terminal_closure_allowed",
    "operator_approval_observed",
    "branch_created",
    "pull_request_opened",
    "repository_written",
    "adapter_executed",
    "connector_calls_observed",
    "mutation_route_called",
    "receipt_store_appended",
    "external_effects_observed",
    "raw_secret_material_included",
    "terminal_closure",
    "success_claim_allowed",
    "live_adapter_execution_enabled",
    "branch_write_enabled",
    "repository_write_enabled",
    "mutation_route_enabled",
    "receipt_store_append_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "preflight_only",
    "preflight_recorded",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "raw_secret_material_included",
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
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class GitHubPrAdmissionPreflightValidation:
    """Schema and semantic validation report for GitHub PR admission preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_receipt_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_receipt_schema_path: Path = DEFAULT_SOURCE_RECEIPT_SCHEMA,
    source_receipt_example_paths: Sequence[Path] = DEFAULT_SOURCE_RECEIPT_EXAMPLES,
    file_summary_receipt_schema_path: Path = DEFAULT_FILE_SUMMARY_RECEIPT_SCHEMA,
    file_summary_receipt_example_paths: Sequence[Path] = DEFAULT_FILE_SUMMARY_RECEIPT_EXAMPLES,
) -> GitHubPrAdmissionPreflightValidation:
    """Validate GitHub PR admission preflight examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR admission preflight schema", errors)
    source_validation = validate_agentic_service_harness_github_task_receipt_emitter_dry_run(
        schema_path=source_receipt_schema_path,
        example_paths=source_receipt_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source receipt dry-run: {error}" for error in source_validation.errors)
    file_summary_schema = _load_json_object(
        file_summary_receipt_schema_path,
        "non-empty diff file summary receipt schema",
        errors,
    )
    for file_summary_example_path in file_summary_receipt_example_paths:
        file_summary_example = _load_json_object(
            file_summary_example_path,
            f"non-empty diff file summary receipt {_path_label(file_summary_example_path)}",
            errors,
        )
        if file_summary_schema and file_summary_example:
            errors.extend(
                f"non-empty diff file summary receipt {_path_label(file_summary_example_path)}: {error}"
                for error in _validate_schema_instance(file_summary_schema, file_summary_example)
            )
    source_receipt = _load_json_object(
        source_receipt_example_paths[0],
        "GitHub task receipt-emitter dry-run source",
        errors,
    )
    file_summary_receipt = _load_json_object(
        file_summary_receipt_example_paths[0],
        "non-empty diff file summary receipt source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(example_path, f"GitHub PR admission preflight {_path_label(example_path)}", errors)
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_preflight_semantics(
            example,
            source_receipt,
            file_summary_receipt,
            errors,
            _path_label(example_path),
        )
    return GitHubPrAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_receipt_ref=EXPECTED_SOURCE_RECEIPT_REF,
    )


def write_github_pr_admission_preflight_validation(
    validation: GitHubPrAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic GitHub PR admission preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_preflight_semantics(
    payload: Mapping[str, Any],
    source_receipt: Mapping[str, Any],
    file_summary_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("source_receipt_emitter_ref",), EXPECTED_SOURCE_RECEIPT_REF, errors, label)
    _require_equal(
        payload,
        ("source_non_empty_diff_file_summary_receipt_ref",),
        EXPECTED_FILE_SUMMARY_RECEIPT_REF,
        errors,
        label,
    )
    _require_equal(payload, ("scope", "task_service_id"), EXPECTED_TASK_SERVICE_ID, errors, label)
    _require_equal(payload, ("preflight_contract", "preflight_id"), EXPECTED_PREFLIGHT_ID, errors, label)
    _require_equal(payload, ("preflight_contract", "preflight_mode"), EXPECTED_PREFLIGHT_MODE, errors, label)
    _require_equal(payload, ("preflight_contract", "source_task_ref"), EXPECTED_SOURCE_TASK_REF, errors, label)
    _require_equal(payload, ("approval_admission_gate", "decision"), EXPECTED_APPROVAL_DECISION, errors, label)
    _require_equal(payload, ("approval_admission_gate", "approval_target_ref"), EXPECTED_APPROVAL_TARGET_REF, errors, label)
    _require_equal(payload, ("simulated_pr_admission", "result_state"), EXPECTED_RESULT_STATE, errors, label)
    _require_equal(
        payload,
        ("simulated_pr_admission", "simulated_action_kind"),
        EXPECTED_SIMULATED_ACTION_KIND,
        errors,
        label,
    )
    if source_receipt:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_receipt, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_receipt, ("scope", "repository_connection_id")),
            errors,
            label,
        )
    if file_summary_receipt:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(file_summary_receipt, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(file_summary_receipt, ("scope", "repository_connection_id")),
            errors,
            label,
        )
        _require_equal(
            file_summary_receipt,
            ("solver_outcome",),
            "AwaitingEvidence",
            errors,
            "non-empty diff file summary receipt source",
        )
        _require_equal(
            file_summary_receipt,
            ("authority_denials", "pr_creation_enabled"),
            False,
            errors,
            "non-empty diff file summary receipt source",
        )
    for required_ref in REQUIRED_ALLOWED_ACTION_CLASSES:
        _require_contains(
            payload,
            ("preflight_contract", "allowed_action_classes"),
            required_ref,
            errors,
            label,
        )
    for required_ref in REQUIRED_FORBIDDEN_ACTION_CLASSES:
        _require_contains(
            payload,
            ("preflight_contract", "forbidden_action_classes"),
            required_ref,
            errors,
            label,
        )
    for path, required_refs in (
        (("preflight_contract", "required_source_refs"), REQUIRED_SOURCE_REFS),
        (("preflight_contract", "required_gate_refs"), REQUIRED_GATE_REFS),
        (("preflight_contract", "admission_obligations_checked"), REQUIRED_ADMISSION_OBLIGATIONS),
        (("preflight_contract", "validation_refs"), REQUIRED_VALIDATION_REFS),
        (("approval_admission_gate", "required_before_pr_refs"), REQUIRED_BEFORE_PR_REFS),
        (("approval_admission_gate", "blocked_reason_refs"), REQUIRED_BLOCKERS),
    ):
        for required_ref in required_refs:
            _require_contains(payload, path, required_ref, errors, label)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    for path, value in _walk_leaves(payload):
        dotted_path = ".".join(path)
        if path[-1] in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if path[-1] in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if path[-1] not in ALLOWED_SECRET_KEYS and _contains_secret_token(path[-1]):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


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


def _contains_secret_token(key: str) -> bool:
    lowered_key = key.lower()
    return any(token in lowered_key for token in FORBIDDEN_SECRET_KEY_TOKENS)


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_mutated_preflight(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--source-receipt-schema", type=Path, default=DEFAULT_SOURCE_RECEIPT_SCHEMA)
    parser.add_argument("--source-receipt-example", type=Path, action="append", dest="source_receipt_examples")
    parser.add_argument("--file-summary-receipt-schema", type=Path, default=DEFAULT_FILE_SUMMARY_RECEIPT_SCHEMA)
    parser.add_argument("--file-summary-receipt-example", type=Path, action="append", dest="file_summary_receipt_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_admission_preflight(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_receipt_schema_path=args.source_receipt_schema,
        source_receipt_example_paths=(
            tuple(args.source_receipt_examples) if args.source_receipt_examples else DEFAULT_SOURCE_RECEIPT_EXAMPLES
        ),
        file_summary_receipt_schema_path=args.file_summary_receipt_schema,
        file_summary_receipt_example_paths=(
            tuple(args.file_summary_receipt_examples)
            if args.file_summary_receipt_examples
            else DEFAULT_FILE_SUMMARY_RECEIPT_EXAMPLES
        ),
    )
    write_github_pr_admission_preflight_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR ADMISSION PREFLIGHT VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
