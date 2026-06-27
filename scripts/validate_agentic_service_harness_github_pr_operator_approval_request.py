#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR operator approval request.

Purpose: prove the GitHub pull-request admission approval request is explicit,
uncollected, read-only, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_operator_approval_request.schema.json,
examples/agentic_service_harness_github_pr_operator_approval_request.foundation.json,
schemas/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.schema.json,
examples/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.foundation.json,
and scripts.validate_schemas.
Invariants:
  - The request binds to the GitHub PR actual non-empty diff admission binding.
  - The request consumes redacted non-empty diff evidence before asking for
    operator approval.
  - Approval remains AwaitingEvidence and uncollected.
  - Approval request alone grants no branch, PR, repository, connector, network,
    mutation-route, receipt-store, secret, destructive, or terminal authority.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_operator_approval_request.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_pr_operator_approval_request.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_operator_approval_request_validation.json"
)
DEFAULT_SOURCE_DIFF_ADMISSION_BINDING_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.schema.json"
)
DEFAULT_SOURCE_DIFF_ADMISSION_BINDING_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.foundation.json",
)
EXPECTED_SOURCE_DIFF_ADMISSION_BINDING_REF = (
    "examples/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.foundation.json"
)
EXPECTED_SOURCE_DIFF_ADMISSION_BINDING_ID = "agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding"
EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF = "witness://actual-non-empty-diff-receipt"
EXPECTED_REDACTED_DIFF_BUNDLE_REF = "digest://redacted-filesystem-write-diff-bundle-candidate"
EXPECTED_REDACTED_OUTPUT_REF = "witness://filesystem-write-output-redacted"
EXPECTED_REQUEST_ID = "agentic_service_harness_github_pr_operator_approval_request"
EXPECTED_APPROVAL_REQUEST_ID = "approval-request.github-pr-admission"
EXPECTED_REQUESTED_EVIDENCE_REF = "approval://operator-github-pr-admission-required"
EXPECTED_ALLOWED_RESPONSE_KINDS = (
    "record_operator_pr_approval_witness",
    "record_operator_pr_rejection_witness",
)
EXPECTED_REMAINING_WITNESSES = (
    "operator_response_record",
    "branch_write_authority",
    "uao_pr_admission",
    "repository_effect_rollback_plan",
    "ci_gate_before_ready_for_review",
    "effect_reconciliation",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_operator_approval_request_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request.schema.json"
    ),
    "github_pr_actual_non_empty_diff_admission_binding_schema": (
        "schemas/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.schema.json"
    ),
    "github_pr_actual_non_empty_diff_admission_binding_example": EXPECTED_SOURCE_DIFF_ADMISSION_BINDING_REF,
    "github_pr_admission_preflight_schema": "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json",
    "github_task_receipt_emitter_dry_run_schema": (
        "schemas/agentic_service_harness_github_task_receipt_emitter_dry_run.schema.json"
    ),
    "github_repo_task_service_schema": "schemas/agentic_service_harness_github_repo_task_service.schema.json",
}
REQUIRED_FALSE_FLAGS = (
    "approval_collected",
    "authority_granted",
    "terminal_closure",
    "response_record_collected",
    "pr_creation_authorized_after_response",
    "operator_approval_collected",
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
    "branch_created",
    "pull_request_opened",
    "repository_written",
    "connector_called",
    "mutation_route_admitted",
    "receipt_store_appended",
    "secret_values_serialized",
)
REQUIRED_TRUE_FLAGS = (
    "planning_only",
    "read_only",
    "report_is_not_terminal_closure",
    "approval_request_only",
    "response_record_required",
    "blocks_pr_admission",
    "requires_actual_non_empty_diff_binding",
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
class GitHubPrOperatorApprovalRequestValidation:
    """Schema and semantic validation report for GitHub PR approval request."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_diff_admission_binding_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_operator_approval_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_diff_admission_binding_schema_path: Path = DEFAULT_SOURCE_DIFF_ADMISSION_BINDING_SCHEMA,
    source_diff_admission_binding_example_paths: Sequence[Path] = DEFAULT_SOURCE_DIFF_ADMISSION_BINDING_EXAMPLES,
) -> GitHubPrOperatorApprovalRequestValidation:
    """Validate GitHub PR operator approval request examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR operator approval request schema", errors)
    source_diff_admission_binding_schema = _load_json_object(
        source_diff_admission_binding_schema_path,
        "GitHub PR actual non-empty diff admission binding source schema",
        errors,
    )
    source_diff_admission_binding = _load_json_object(
        source_diff_admission_binding_example_paths[0],
        "GitHub PR actual non-empty diff admission binding source",
        errors,
    )
    if source_diff_admission_binding_schema and source_diff_admission_binding:
        errors.extend(
            "source PR actual non-empty diff admission binding: " + error
            for error in _validate_schema_instance(source_diff_admission_binding_schema, source_diff_admission_binding)
        )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(example_path, f"GitHub PR operator approval request {_path_label(example_path)}", errors)
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_approval_request_semantics(example, source_diff_admission_binding, errors, _path_label(example_path))
    return GitHubPrOperatorApprovalRequestValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_diff_admission_binding_ref=EXPECTED_SOURCE_DIFF_ADMISSION_BINDING_REF,
    )


def write_github_pr_operator_approval_request_validation(
    validation: GitHubPrOperatorApprovalRequestValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic GitHub PR operator approval request report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_approval_request_semantics(
    payload: Mapping[str, Any],
    source_diff_admission_binding: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("request_id",), EXPECTED_REQUEST_ID, errors, label)
    _require_equal(
        payload,
        ("source_actual_non_empty_diff_admission_binding_ref",),
        EXPECTED_SOURCE_DIFF_ADMISSION_BINDING_REF,
        errors,
        label,
    )
    _require_equal(payload, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _require_equal(payload, ("witness_kind",), "operator_approval_request", errors, label)
    _require_equal(payload, ("requested_evidence_ref",), EXPECTED_REQUESTED_EVIDENCE_REF, errors, label)
    _require_equal(payload, ("approval_status",), "AwaitingEvidence", errors, label)
    _require_equal(payload, ("approval_request", "approval_request_id"), EXPECTED_APPROVAL_REQUEST_ID, errors, label)
    _require_equal(payload, ("approval_request", "approver_role"), "operator", errors, label)
    _require_equal(payload, ("approval_request", "decision_required"), "operator_response_required", errors, label)
    _require_equal(
        payload,
        ("approval_request", "default_response_kind"),
        "record_operator_pr_rejection_witness",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("approval_request", "approval_effect"),
        "satisfies_operator_pr_approval_witness_only",
        errors,
        label,
    )
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_diff_admission_binding:
        _require_equal(
            source_diff_admission_binding,
            ("binding_id",),
            EXPECTED_SOURCE_DIFF_ADMISSION_BINDING_ID,
            errors,
            "GitHub PR actual non-empty diff admission binding source",
        )
        _require_equal(
            source_diff_admission_binding,
            ("pr_admission_diff_binding", "actual_non_empty_diff_receipt_ref"),
            EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF,
            errors,
            "GitHub PR actual non-empty diff admission binding source",
        )
        _require_equal(
            source_diff_admission_binding,
            ("effect_boundary", "pull_request_opened"),
            False,
            errors,
            "GitHub PR actual non-empty diff admission binding source",
        )
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_diff_admission_binding, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_diff_admission_binding, ("scope", "repository_connection_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("approval_request", "actual_non_empty_diff_receipt_ref"),
            _get_nested(
                source_diff_admission_binding,
                ("pr_admission_diff_binding", "actual_non_empty_diff_receipt_ref"),
            ),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("approval_request", "redacted_diff_bundle_ref"),
            _get_nested(source_diff_admission_binding, ("pr_admission_diff_binding", "redacted_diff_bundle_ref")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("approval_request", "redacted_output_ref"),
            _get_nested(source_diff_admission_binding, ("pr_admission_diff_binding", "redacted_output_ref")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("approval_request", "changed_file_refs"),
            _get_nested(source_diff_admission_binding, ("pr_admission_diff_binding", "changed_file_refs")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("approval_request", "diff_refs"),
            _get_nested(source_diff_admission_binding, ("pr_admission_diff_binding", "diff_refs")),
            errors,
            label,
        )
    for response_kind in EXPECTED_ALLOWED_RESPONSE_KINDS:
        _require_contains(payload, ("approval_request", "allowed_response_kinds"), response_kind, errors, label)
    observed_witnesses = _get_nested(payload, ("remaining_witnesses",))
    if not isinstance(observed_witnesses, list):
        errors.append(f"{label}: remaining_witnesses must be a list")
    else:
        observed_kinds = tuple(
            witness.get("witness_kind") for witness in observed_witnesses if isinstance(witness, Mapping)
        )
        if observed_kinds != EXPECTED_REMAINING_WITNESSES:
            errors.append(f"{label}: remaining_witnesses must preserve canonical witness order")
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
        errors.append(f"{label}: {'.'.join(path)} missing required value {expected!r}")


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


def build_mutated_approval_request(**updates: Any) -> dict[str, Any]:
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
        "--source-diff-admission-binding-schema",
        type=Path,
        default=DEFAULT_SOURCE_DIFF_ADMISSION_BINDING_SCHEMA,
    )
    parser.add_argument(
        "--source-diff-admission-binding-example",
        type=Path,
        action="append",
        dest="source_diff_admission_binding_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_operator_approval_request(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_diff_admission_binding_schema_path=args.source_diff_admission_binding_schema,
        source_diff_admission_binding_example_paths=(
            tuple(args.source_diff_admission_binding_examples)
            if args.source_diff_admission_binding_examples
            else DEFAULT_SOURCE_DIFF_ADMISSION_BINDING_EXAMPLES
        ),
    )
    write_github_pr_operator_approval_request_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR OPERATOR APPROVAL REQUEST VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
