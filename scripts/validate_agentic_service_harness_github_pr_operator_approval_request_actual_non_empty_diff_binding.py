#!/usr/bin/env python3
"""Validate GitHub PR approval request actual non-empty diff binding.

Purpose: prove the GitHub PR operator approval request consumes actual
non-empty diff admission evidence before any operator response or PR creation
path is considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.schema.json,
examples/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.foundation.json,
scripts.validate_agentic_service_harness_github_pr_operator_approval_request,
scripts.validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding,
and scripts.validate_schemas.
Invariants:
  - The binding consumes the GitHub PR operator approval request.
  - The binding consumes the GitHub PR actual non-empty diff admission binding.
  - Redacted changed-file and diff refs match the source actual-diff admission binding.
  - Operator response, PR creation, branch writes, repository writes, connector
    calls, mutation routes, raw content, receipt append, secrets, and terminal
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
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_ACTUAL_DIFF_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_ACTUAL_DIFF_ADMISSION_SCHEMA,
    validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding,
)
from scripts.validate_agentic_service_harness_github_pr_operator_approval_request import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_OPERATOR_APPROVAL_REQUEST_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_OPERATOR_APPROVAL_REQUEST_SCHEMA,
    validate_agentic_service_harness_github_pr_operator_approval_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding_validation.json"
)
EXPECTED_BINDING_ID = (
    "agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding"
)
EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_REF = (
    "examples/agentic_service_harness_github_pr_operator_approval_request.foundation.json"
)
EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF = (
    "examples/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.foundation.json"
)
EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_ID = (
    "agentic_service_harness_github_pr_operator_approval_request"
)
EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_ID = (
    "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding"
)
EXPECTED_APPROVAL_REQUEST_ID = "approval-request.github-pr-admission"
EXPECTED_REQUESTED_EVIDENCE_REF = "approval://operator-github-pr-admission-required"
EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF = "witness://actual-non-empty-diff-receipt"
EXPECTED_REDACTED_DIFF_BUNDLE_REF = "digest://redacted-filesystem-write-diff-bundle-candidate"
EXPECTED_REDACTED_OUTPUT_REF = "witness://filesystem-write-output-redacted"
EXPECTED_REMAINING_WITNESSES = (
    "operator_response_record",
    "operator_approval_decision",
    "branch_write_authority",
    "uao_pr_admission",
    "repository_effect_rollback_plan",
    "ci_gate_before_ready_for_review",
    "effect_reconciliation",
    "terminal_certificate",
)
REQUIRED_BEFORE_PR_REFS = (
    EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_REF,
    EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF,
    EXPECTED_REQUESTED_EVIDENCE_REF,
    EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF,
    "evidence://redacted-file-change-candidate/schema-addition",
    "evidence://redacted-diff-candidate/schema-addition",
    EXPECTED_REDACTED_DIFF_BUNDLE_REF,
    EXPECTED_REDACTED_OUTPUT_REF,
    "evidence://operator-approval-for-pr-admission",
    "evidence://branch-write-authority-binding",
    "evidence://uao-pr-admission",
    "evidence://repository-effect-rollback-plan",
    "evidence://ci-gate-before-ready-for-review",
    "evidence://effect-reconciliation-before-terminal-closure",
    "witness://github-pr-terminal-closure-certificate",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-response/not-collected",
    "blocked://operator-approval/not-granted",
    "blocked://branch-write-authority/not-bound",
    "blocked://uao-pr-admission/not-present",
    "blocked://repository-effect-rollback-plan/not-present",
    "blocked://ci-gate-before-ready-for-review/not-present",
    "blocked://effect-reconciliation/not-present",
    "blocked://terminal-certificate/not-verified",
    "blocked://pr-creation/not-admitted",
    "blocked://raw-diff-body/not-allowed",
    "blocked://raw-file-content/not-allowed",
    "blocked://receipt-store-append/not-enabled",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_operator_approval_request_actual_non_empty_diff_binding_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.schema.json"
    ),
    "github_pr_operator_approval_request_actual_non_empty_diff_binding_example": (
        "examples/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.foundation.json"
    ),
    "github_pr_operator_approval_request_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request.schema.json"
    ),
    "github_pr_operator_approval_request_example": EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_REF,
    "github_pr_actual_non_empty_diff_admission_binding_schema": (
        "schemas/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.schema.json"
    ),
    "github_pr_actual_non_empty_diff_admission_binding_example": EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF,
    "github_pr_admission_preflight_schema": (
        "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json"
    ),
    "actual_non_empty_diff_receipt_binding_schema": (
        "schemas/agentic_service_harness_actual_non_empty_diff_receipt_binding.schema.json"
    ),
    "github_repo_task_service_schema": "schemas/agentic_service_harness_github_repo_task_service.schema.json",
}
REQUIRED_FALSE_FLAGS = (
    "terminal_closure",
    "operator_response_collected",
    "operator_approval_granted",
    "operator_approval_rejected",
    "pr_admitted",
    "pull_request_creation_authorized",
    "raw_diff_body_allowed",
    "raw_file_content_allowed",
    "receipt_store_append_allowed",
    "terminal_certificate_verified",
    "authority_granted",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "repository_write_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "receipt_store_append_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "operator_response_recorded",
    "branch_created",
    "pull_request_opened",
    "repository_written",
    "connector_called",
    "mutation_route_admitted",
    "receipt_store_appended",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "secret_values_serialized",
)
REQUIRED_TRUE_FLAGS = (
    "planning_only",
    "read_only",
    "report_is_not_terminal_closure",
    "approval_request_only",
    "approval_request_bound",
    "blocks_pr_admission",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
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
class GitHubPrOperatorApprovalRequestActualNonEmptyDiffBindingValidation:
    """Validation report for approval request actual-diff binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_operator_approval_request_ref: str
    source_actual_non_empty_diff_admission_binding_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_operator_approval_request_schema_path: Path = DEFAULT_OPERATOR_APPROVAL_REQUEST_SCHEMA,
    source_operator_approval_request_example_paths: Sequence[Path] = DEFAULT_OPERATOR_APPROVAL_REQUEST_EXAMPLES,
    source_actual_diff_admission_schema_path: Path = DEFAULT_ACTUAL_DIFF_ADMISSION_SCHEMA,
    source_actual_diff_admission_example_paths: Sequence[Path] = DEFAULT_ACTUAL_DIFF_ADMISSION_EXAMPLES,
) -> GitHubPrOperatorApprovalRequestActualNonEmptyDiffBindingValidation:
    """Validate approval request actual non-empty diff binding examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR approval request actual diff binding schema", errors)
    approval_request_validation = validate_agentic_service_harness_github_pr_operator_approval_request(
        schema_path=source_operator_approval_request_schema_path,
        example_paths=source_operator_approval_request_example_paths,
    )
    if not approval_request_validation.ok:
        errors.extend(
            f"source GitHub PR operator approval request: {error}"
            for error in approval_request_validation.errors
        )
    actual_diff_admission_validation = (
        validate_agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding(
            schema_path=source_actual_diff_admission_schema_path,
            example_paths=source_actual_diff_admission_example_paths,
        )
    )
    if not actual_diff_admission_validation.ok:
        errors.extend(
            f"source GitHub PR actual non-empty diff admission binding: {error}"
            for error in actual_diff_admission_validation.errors
        )
    source_approval_request = _load_json_object(
        source_operator_approval_request_example_paths[0],
        "GitHub PR operator approval request source",
        errors,
    )
    source_actual_diff_admission = _load_json_object(
        source_actual_diff_admission_example_paths[0],
        "GitHub PR actual non-empty diff admission source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR approval request actual diff binding {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_approval_request_actual_diff_binding_semantics(
            example,
            source_approval_request,
            source_actual_diff_admission,
            errors,
            _path_label(example_path),
        )
    return GitHubPrOperatorApprovalRequestActualNonEmptyDiffBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_operator_approval_request_ref=EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_REF,
        source_actual_non_empty_diff_admission_binding_ref=EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF,
    )


def write_github_pr_operator_approval_request_actual_non_empty_diff_binding_validation(
    validation: GitHubPrOperatorApprovalRequestActualNonEmptyDiffBindingValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic approval request actual-diff binding report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_approval_request_actual_diff_binding_semantics(
    payload: Mapping[str, Any],
    source_approval_request: Mapping[str, Any],
    source_actual_diff_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("binding_id",), EXPECTED_BINDING_ID, errors, label)
    _require_equal(
        payload,
        ("source_operator_approval_request_ref",),
        EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("source_actual_non_empty_diff_admission_binding_ref",),
        EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF,
        errors,
        label,
    )
    _require_equal(payload, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _require_equal(
        payload,
        ("witness_kind",),
        "github_pr_operator_approval_request_actual_non_empty_diff_binding",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("binding_status",),
        "operator_approval_request_bound_to_actual_non_empty_diff_without_authority",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "source_operator_approval_request_id"),
        EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "source_actual_non_empty_diff_admission_binding_id"),
        EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "approval_request_id"),
        EXPECTED_APPROVAL_REQUEST_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "requested_evidence_ref"),
        EXPECTED_REQUESTED_EVIDENCE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "actual_non_empty_diff_admission_ref"),
        EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "actual_non_empty_diff_receipt_ref"),
        EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "redacted_diff_bundle_ref"),
        EXPECTED_REDACTED_DIFF_BUNDLE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request_diff_binding", "redacted_output_ref"),
        EXPECTED_REDACTED_OUTPUT_REF,
        errors,
        label,
    )
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_approval_request:
        _require_equal(
            source_approval_request,
            ("request_id",),
            EXPECTED_SOURCE_OPERATOR_APPROVAL_REQUEST_ID,
            errors,
            "GitHub PR operator approval request source",
        )
        _require_equal(
            source_approval_request,
            ("approval_request", "approval_request_id"),
            EXPECTED_APPROVAL_REQUEST_ID,
            errors,
            "GitHub PR operator approval request source",
        )
        _require_equal(
            source_approval_request,
            ("requested_evidence_ref",),
            EXPECTED_REQUESTED_EVIDENCE_REF,
            errors,
            "GitHub PR operator approval request source",
        )
        _require_equal(
            source_approval_request,
            ("approval_collected",),
            False,
            errors,
            "GitHub PR operator approval request source",
        )
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_approval_request, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_approval_request, ("scope", "repository_connection_id")),
            errors,
            label,
        )
    if source_actual_diff_admission:
        _require_equal(
            source_actual_diff_admission,
            ("binding_id",),
            EXPECTED_SOURCE_ACTUAL_DIFF_ADMISSION_ID,
            errors,
            "GitHub PR actual non-empty diff admission source",
        )
        _require_equal(
            source_actual_diff_admission,
            ("pr_admission_diff_binding", "pr_admitted"),
            False,
            errors,
            "GitHub PR actual non-empty diff admission source",
        )
        diff_binding = _mapping(source_actual_diff_admission.get("pr_admission_diff_binding"))
        for key in (
            "changed_file_count",
            "changed_file_refs",
            "diff_refs",
            "redacted_diff_bundle_ref",
            "redacted_output_ref",
            "actual_non_empty_diff_receipt_ref",
        ):
            _require_equal(
                payload,
                ("approval_request_diff_binding", key),
                diff_binding.get(key),
                errors,
                label,
            )
        changed_file_refs = diff_binding.get("changed_file_refs")
        diff_refs = diff_binding.get("diff_refs")
        if not isinstance(changed_file_refs, list) or not changed_file_refs:
            errors.append("GitHub PR actual non-empty diff admission source: changed_file_refs must be non-empty")
        if not isinstance(diff_refs, list) or not diff_refs:
            errors.append("GitHub PR actual non-empty diff admission source: diff_refs must be non-empty")
    observed_witnesses = _get_nested(payload, ("remaining_witnesses",))
    if not isinstance(observed_witnesses, list):
        errors.append(f"{label}: remaining_witnesses must be a list")
    else:
        observed_kinds = tuple(
            witness.get("witness_kind") for witness in observed_witnesses if isinstance(witness, Mapping)
        )
        if observed_kinds != EXPECTED_REMAINING_WITNESSES:
            errors.append(f"{label}: remaining_witnesses must preserve canonical witness order")
    for path, required_refs in (
        (("approval_request_diff_binding", "required_before_pr_refs"), REQUIRED_BEFORE_PR_REFS),
        (("approval_request_diff_binding", "blocked_reason_refs"), REQUIRED_BLOCKERS),
    ):
        for required_ref in required_refs:
            _require_contains(payload, path, required_ref, errors, label)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    next_action = _get_nested(payload, ("next_action",))
    if isinstance(next_action, str):
        for phrase in (
            "operator response witness",
            "actual non-empty diff binding",
            "PR creation",
            "terminal certificate evidence",
        ):
            if phrase not in next_action:
                errors.append(f"{label}: next_action missing phrase {phrase!r}")
    for path, value in _walk_leaves(payload):
        if not path:
            continue
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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def build_mutated_approval_request_actual_non_empty_diff_binding(**updates: Any) -> dict[str, Any]:
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
        "--source-operator-approval-request-schema",
        type=Path,
        default=DEFAULT_OPERATOR_APPROVAL_REQUEST_SCHEMA,
    )
    parser.add_argument(
        "--source-operator-approval-request-example",
        type=Path,
        action="append",
        dest="source_operator_approval_request_examples",
    )
    parser.add_argument("--source-actual-diff-admission-schema", type=Path, default=DEFAULT_ACTUAL_DIFF_ADMISSION_SCHEMA)
    parser.add_argument(
        "--source-actual-diff-admission-example",
        type=Path,
        action="append",
        dest="source_actual_diff_admission_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_operator_approval_request_schema_path=args.source_operator_approval_request_schema,
        source_operator_approval_request_example_paths=(
            tuple(args.source_operator_approval_request_examples)
            if args.source_operator_approval_request_examples
            else DEFAULT_OPERATOR_APPROVAL_REQUEST_EXAMPLES
        ),
        source_actual_diff_admission_schema_path=args.source_actual_diff_admission_schema,
        source_actual_diff_admission_example_paths=(
            tuple(args.source_actual_diff_admission_examples)
            if args.source_actual_diff_admission_examples
            else DEFAULT_ACTUAL_DIFF_ADMISSION_EXAMPLES
        ),
    )
    write_github_pr_operator_approval_request_actual_non_empty_diff_binding_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR OPERATOR APPROVAL REQUEST ACTUAL NON-EMPTY DIFF BINDING VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
