#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR creation dry-run receipt.

Purpose: prove a future GitHub pull-request creation action can be recorded as
a dry-run receipt after binding PR admission preflight and terminal certificate
read-model evidence, without admitting live repository effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_creation_dry_run_receipt.schema.json,
examples/agentic_service_harness_github_pr_creation_dry_run_receipt.foundation.json,
scripts.validate_agentic_service_harness_github_pr_admission_preflight,
scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model,
and scripts.validate_schemas.
Invariants:
  - The dry-run consumes the certificate-read-model-bound PR admission preflight.
  - The dry-run consumes the terminal certificate read model as projection-only evidence.
  - Runtime PR creation, branch creation, repository writes, connector calls,
    receipt-store append, mutation routes, secret material, and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_github_pr_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_SCHEMA,
    EXPECTED_APPROVAL_DECISION,
    EXPECTED_PREFLIGHT_ID,
    EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
    validate_agentic_service_harness_github_pr_admission_preflight,
)
from scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_SCHEMA,
    validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_creation_dry_run_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_pr_creation_dry_run_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_creation_dry_run_receipt_validation.json"
)
EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF = (
    "examples/agentic_service_harness_github_pr_admission_preflight.foundation.json"
)
EXPECTED_DRY_RUN_ID = "github-pr-creation-dry-run-receipt-foundation"
EXPECTED_DRY_RUN_MODE = "PR_CREATION_DRY_RUN_ONLY"
EXPECTED_SIMULATED_ACTION_KIND = "future_github_pull_request_creation"
EXPECTED_RESULT_STATE = "PR_CREATION_DRY_RUN_RECORDED"
EXPECTED_EXECUTION_DECISION = "PR_CREATION_EXECUTION_BLOCKED_AWAITING_EXPLICIT_ADMISSION"
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
    EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
    EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
    "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json",
    "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_read_model.schema.json",
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
REQUIRED_DRY_RUN_OBLIGATIONS = (
    "obligation://bind-pr-admission-preflight-before-dry-run",
    "obligation://bind-terminal-certificate-read-model-before-dry-run",
    "obligation://record-pr-creation-dry-run-receipt",
    "obligation://deny-live-pr-creation",
    "obligation://deny-repository-effects",
    "obligation://deny-receipt-store-append",
    "obligation://deny-secret-material",
    "obligation://bind-execution-admission-blocker",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_github_pr_creation_dry_run_receipt.py",
    "scripts/validate_agentic_service_harness_github_pr_admission_preflight.py",
    "scripts/validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model.py",
)
REQUIRED_BEFORE_EXECUTION_REFS = (
    EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
    EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
    "evidence://operator-approval-for-pr-execution",
    "evidence://branch-write-authority-binding",
    "evidence://uao-pr-execution-admission",
    "evidence://repository-effect-rollback-plan",
    "evidence://receipt-store-write-path-binding",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_BLOCKERS = (
    "blocked://pr-creation/dry-run-only",
    "blocked://pr-admission/source-preflight-denied",
    "blocked://terminal-certificate-read-model/projection-only",
    "blocked://operator-approval/not-present",
    "blocked://uao/pr-execution-not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_creation_dry_run_receipt_schema": (
        "schemas/agentic_service_harness_github_pr_creation_dry_run_receipt.schema.json"
    ),
    "github_pr_admission_preflight_schema": (
        "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json"
    ),
    "github_pr_admission_preflight_example": EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
    "terminal_closure_certificate_read_model_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_read_model.schema.json"
    ),
    "terminal_closure_certificate_read_model_example": EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
}
REQUIRED_FALSE_FLAGS = (
    "pr_creation_enabled",
    "repository_write_enabled",
    "external_adapter_integrated",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "source_pr_admitted",
    "runtime_pr_creation_executed",
    "pull_request_opened",
    "branch_created",
    "repository_written",
    "receipt_store_appended",
    "adapter_executed",
    "connector_calls_observed",
    "mutation_route_called",
    "external_effects_observed",
    "raw_output_included",
    "raw_secret_material_included",
    "terminal_closure",
    "success_claim_allowed",
    "execution_admitted",
    "terminal_closure_allowed",
    "live_adapter_execution_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "mutation_route_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "dry_run_only",
    "dry_run_receipt_recorded",
    "source_terminal_certificate_read_model_projection_only",
    "source_terminal_certificate_read_model_not_terminal_closure",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
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
class GitHubPrCreationDryRunReceiptValidation:
    """Schema and semantic validation report for GitHub PR creation dry-run."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_pr_admission_preflight_ref: str
    terminal_certificate_read_model_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_creation_dry_run_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_pr_admission_preflight_schema_path: Path = DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_SCHEMA,
    source_pr_admission_preflight_example_paths: Sequence[Path] = DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_EXAMPLES,
    terminal_certificate_read_model_schema_path: Path = DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_SCHEMA,
    terminal_certificate_read_model_example_paths: Sequence[Path] = DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_EXAMPLES,
) -> GitHubPrCreationDryRunReceiptValidation:
    """Validate GitHub PR creation dry-run receipt examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR creation dry-run receipt schema", errors)
    source_preflight_validation = validate_agentic_service_harness_github_pr_admission_preflight(
        schema_path=source_pr_admission_preflight_schema_path,
        example_paths=source_pr_admission_preflight_example_paths,
    )
    if not source_preflight_validation.ok:
        errors.extend(f"source PR admission preflight: {error}" for error in source_preflight_validation.errors)
    source_preflight = _load_json_object(
        source_pr_admission_preflight_example_paths[0],
        "GitHub PR admission preflight source",
        errors,
    )
    read_model_validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        schema_path=terminal_certificate_read_model_schema_path,
        example_paths=terminal_certificate_read_model_example_paths,
    )
    if not read_model_validation.ok:
        errors.extend(f"terminal certificate read model: {error}" for error in read_model_validation.errors)
    read_model = _load_json_object(
        terminal_certificate_read_model_example_paths[0],
        "terminal certificate read model source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR creation dry-run receipt {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_pr_creation_dry_run_semantics(example, source_preflight, read_model, errors, _path_label(example_path))
    return GitHubPrCreationDryRunReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_pr_admission_preflight_ref=EXPECTED_SOURCE_PR_ADMISSION_PREFLIGHT_REF,
        terminal_certificate_read_model_ref=EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
    )


def write_github_pr_creation_dry_run_receipt_validation(
    validation: GitHubPrCreationDryRunReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic GitHub PR creation dry-run validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_pr_creation_dry_run_semantics(
    payload: Mapping[str, Any],
    source_preflight: Mapping[str, Any],
    read_model: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
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
    _validate_source_preflight(payload, source_preflight, errors, label)
    _validate_read_model_source(payload, read_model, errors, label)
    _validate_contract_sections(payload, errors, label)
    _validate_ref_sets(payload, errors, label)
    _validate_receipt_refs(payload, errors, label)
    _validate_flags_and_surface(payload, errors, label)


def _validate_source_preflight(
    payload: Mapping[str, Any],
    source_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not source_preflight:
        return
    for source_path, target_path in (
        (("scope", "tenant_id"), ("scope", "tenant_id")),
        (("scope", "organization_id"), ("scope", "organization_id")),
        (("scope", "project_id"), ("scope", "project_id")),
        (("scope", "repository_connection_id"), ("scope", "repository_connection_id")),
        (("scope", "repository_slug"), ("scope", "repository_slug")),
        (("scope", "task_service_id"), ("scope", "task_service_id")),
    ):
        _require_equal(payload, target_path, _get_nested(source_preflight, source_path), errors, label)
    _require_equal(
        source_preflight,
        ("preflight_contract", "preflight_id"),
        EXPECTED_PREFLIGHT_ID,
        errors,
        "source PR admission preflight",
    )
    _require_equal(
        source_preflight,
        ("approval_admission_gate", "decision"),
        EXPECTED_APPROVAL_DECISION,
        errors,
        "source PR admission preflight",
    )
    _require_equal(
        source_preflight,
        ("approval_admission_gate", "pr_admitted"),
        False,
        errors,
        "source PR admission preflight",
    )
    _require_equal(
        source_preflight,
        ("source_terminal_closure_certificate_read_model_ref",),
        EXPECTED_TERMINAL_CERTIFICATE_READ_MODEL_REF,
        errors,
        "source PR admission preflight",
    )
    _require_equal(
        payload,
        ("dry_run_contract", "source_admission_preflight_id"),
        _get_nested(source_preflight, ("preflight_contract", "preflight_id")),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("simulated_pr_creation", "source_admission_decision"),
        _get_nested(source_preflight, ("approval_admission_gate", "decision")),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("simulated_pr_creation", "source_pr_admitted"),
        _get_nested(source_preflight, ("approval_admission_gate", "pr_admitted")),
        errors,
        label,
    )


def _validate_read_model_source(
    payload: Mapping[str, Any],
    read_model: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not read_model:
        return
    for source_path, target_path in (
        (("projection_scope", "tenant_id"), ("scope", "tenant_id")),
        (("projection_scope", "organization_id"), ("scope", "organization_id")),
        (("projection_scope", "project_id"), ("scope", "project_id")),
        (("projection_scope", "repository_connection_id"), ("scope", "repository_connection_id")),
        (("projection_scope", "repository_slug"), ("scope", "repository_slug")),
        (("projection_scope", "task_service_id"), ("scope", "task_service_id")),
    ):
        _require_equal(payload, target_path, _get_nested(read_model, source_path), errors, label)
    for path, expected in (
        (("projection_scope", "read_only"), True),
        (("projection_scope", "projection_only"), True),
        (("authority_denials", "pull_request_creation_enabled"), False),
        (("effect_boundary", "repository_written_by_read_model"), False),
        (("operator_view", "contains_secret_values"), False),
        (("read_model_is_not_terminal_closure",), True),
    ):
        _require_equal(read_model, path, expected, errors, "terminal certificate read model source")
    _require_equal(
        payload,
        ("simulated_pr_creation", "source_terminal_certificate_read_model_projection_only"),
        _get_nested(read_model, ("projection_scope", "projection_only")),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("simulated_pr_creation", "source_terminal_certificate_read_model_not_terminal_closure"),
        _get_nested(read_model, ("read_model_is_not_terminal_closure",)),
        errors,
        label,
    )


def _validate_contract_sections(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _require_equal(payload, ("dry_run_contract", "dry_run_id"), EXPECTED_DRY_RUN_ID, errors, label)
    _require_equal(payload, ("dry_run_contract", "dry_run_mode"), EXPECTED_DRY_RUN_MODE, errors, label)
    _require_equal(
        payload,
        ("dry_run_contract", "simulated_action_kind"),
        EXPECTED_SIMULATED_ACTION_KIND,
        errors,
        label,
    )
    _require_equal(payload, ("simulated_pr_creation", "result_state"), EXPECTED_RESULT_STATE, errors, label)
    _require_equal(payload, ("execution_admission_gate", "decision"), EXPECTED_EXECUTION_DECISION, errors, label)
    _require_equal(
        payload,
        ("execution_admission_gate", "execution_target_ref"),
        EXPECTED_EXECUTION_TARGET_REF,
        errors,
        label,
    )
    _require_contains(payload, ("dry_run_contract", "allowed_action_classes"), "dry_run", errors, label)
    for required_ref in REQUIRED_FORBIDDEN_ACTION_CLASSES:
        _require_contains(payload, ("dry_run_contract", "forbidden_action_classes"), required_ref, errors, label)


def _validate_ref_sets(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, required_refs in (
        (("dry_run_contract", "required_source_refs"), REQUIRED_SOURCE_REFS),
        (("dry_run_contract", "required_gate_refs"), REQUIRED_GATE_REFS),
        (("dry_run_contract", "dry_run_obligations_checked"), REQUIRED_DRY_RUN_OBLIGATIONS),
        (("dry_run_contract", "validation_refs"), REQUIRED_VALIDATION_REFS),
        (("execution_admission_gate", "required_before_execution_refs"), REQUIRED_BEFORE_EXECUTION_REFS),
        (("execution_admission_gate", "blocked_reason_refs"), REQUIRED_BLOCKERS),
    ):
        for required_ref in required_refs:
            _require_contains(payload, path, required_ref, errors, label)


def _validate_receipt_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
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


def build_mutated_pr_creation_dry_run(**updates: Any) -> dict[str, Any]:
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
        "--source-pr-admission-preflight-schema",
        type=Path,
        default=DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_SCHEMA,
    )
    parser.add_argument(
        "--source-pr-admission-preflight-example",
        type=Path,
        action="append",
        dest="source_pr_admission_preflight_examples",
    )
    parser.add_argument(
        "--terminal-certificate-read-model-schema",
        type=Path,
        default=DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_SCHEMA,
    )
    parser.add_argument(
        "--terminal-certificate-read-model-example",
        type=Path,
        action="append",
        dest="terminal_certificate_read_model_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_creation_dry_run_receipt(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_pr_admission_preflight_schema_path=args.source_pr_admission_preflight_schema,
        source_pr_admission_preflight_example_paths=(
            tuple(args.source_pr_admission_preflight_examples)
            if args.source_pr_admission_preflight_examples
            else DEFAULT_SOURCE_PR_ADMISSION_PREFLIGHT_EXAMPLES
        ),
        terminal_certificate_read_model_schema_path=args.terminal_certificate_read_model_schema,
        terminal_certificate_read_model_example_paths=(
            tuple(args.terminal_certificate_read_model_examples)
            if args.terminal_certificate_read_model_examples
            else DEFAULT_TERMINAL_CERTIFICATE_READ_MODEL_EXAMPLES
        ),
    )
    write_github_pr_creation_dry_run_receipt_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR CREATION DRY-RUN RECEIPT VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
