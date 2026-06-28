#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR branch-write authority binding.

Purpose: prove the GitHub pull-request branch-write authority binding request
is command-preview-response-bound, read-only, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_branch_write_authority_binding.schema.json,
examples/agentic_service_harness_github_pr_branch_write_authority_binding.foundation.json,
scripts.validate_agentic_service_harness_github_pr_operator_response_command_preview_binding, and
scripts.validate_schemas.
Invariants:
  - The binding request binds to the command-preview GitHub PR operator response witness.
  - Branch-write authority remains AwaitingEvidence and uncollected.
  - Binding request alone grants no branch, PR, repository, connector, network,
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


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_github_pr_branch_write_authority_binding.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_pr_branch_write_authority_binding.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_pr_branch_write_authority_binding_validation.json"
)
DEFAULT_SOURCE_RESPONSE_COMMAND_PREVIEW_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_operator_response_command_preview_binding.schema.json"
)
DEFAULT_SOURCE_RESPONSE_COMMAND_PREVIEW_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_operator_response_command_preview_binding.foundation.json",
)
EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF = (
    "examples/agentic_service_harness_github_pr_operator_response_command_preview_binding.foundation.json"
)
EXPECTED_SOURCE_OPERATOR_RESPONSE_REF = (
    "examples/agentic_service_harness_github_pr_operator_response_witness.foundation.json"
)
EXPECTED_SOURCE_RESPONSE_WITNESS_REF = EXPECTED_SOURCE_OPERATOR_RESPONSE_REF
EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF = (
    "examples/agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.foundation.json"
)
EXPECTED_SOURCE_ACTUAL_DIFF_APPROVAL_BINDING_REF = (
    "examples/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.foundation.json"
)
EXPECTED_SOURCE_COMMAND_PREVIEW_REF = (
    "examples/agentic_service_harness_github_pr_creation_command_preview.foundation.json"
)
EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF = "witness://actual-non-empty-diff-receipt"
EXPECTED_REDACTED_DIFF_BUNDLE_REF = "digest://redacted-filesystem-write-diff-bundle-candidate"
EXPECTED_REDACTED_OUTPUT_REF = "witness://filesystem-write-output-redacted"
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
EXPECTED_BINDING_ID = "agentic_service_harness_github_pr_branch_write_authority_binding"
EXPECTED_AUTHORITY_REQUEST_ID = "authority-binding.github-pr-branch-write"
EXPECTED_APPROVAL_REQUEST_ID = "approval-request.github-pr-admission"
EXPECTED_REQUESTED_EVIDENCE_REF = "evidence://branch-write-authority-binding"
EXPECTED_SOURCE_RESPONSE_RECORD_REF = "evidence://operator-pr-approval-response-record"
EXPECTED_REMAINING_WITNESSES = (
    "operator_execution_approval",
    "uao_pr_admission",
    "repository_effect_rollback_plan",
    "receipt_store_write_path",
    "ci_gate_before_ready_for_review",
    "effect_reconciliation",
    "terminal_certificate",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_branch_write_authority_binding_schema": (
        "schemas/agentic_service_harness_github_pr_branch_write_authority_binding.schema.json"
    ),
    "github_pr_operator_response_command_preview_binding_schema": (
        "schemas/agentic_service_harness_github_pr_operator_response_command_preview_binding.schema.json"
    ),
    "github_pr_operator_response_command_preview_binding_example": (
        "examples/agentic_service_harness_github_pr_operator_response_command_preview_binding.foundation.json"
    ),
    "github_pr_operator_response_witness_schema": (
        "schemas/agentic_service_harness_github_pr_operator_response_witness.schema.json"
    ),
    "github_pr_operator_response_witness_example": EXPECTED_SOURCE_OPERATOR_RESPONSE_REF,
    "github_pr_operator_approval_request_command_preview_binding_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.schema.json"
    ),
    "github_pr_operator_approval_request_command_preview_binding_example": EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
    "github_pr_operator_approval_request_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request.schema.json"
    ),
    "github_pr_creation_command_preview_schema": (
        "schemas/agentic_service_harness_github_pr_creation_command_preview.schema.json"
    ),
    "github_pr_creation_command_preview_example": EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
    "github_pr_admission_preflight_schema": "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json",
    "github_repo_task_service_schema": "schemas/agentic_service_harness_github_repo_task_service.schema.json",
}
REQUIRED_FALSE_FLAGS = (
    "authority_binding_collected",
    "authority_granted",
    "terminal_closure",
    "response_witness_satisfied",
    "branch_write_authority_collected",
    "pr_creation_authorized_after_binding",
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
    "requires_command_preview_operator_response_witness",
    "command_preview_bound",
    "operator_response_bound",
    "response_witness_required",
    "branch_write_authority_required",
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
class GitHubPrBranchWriteAuthorityBindingValidation:
    """Schema and semantic validation report for branch-write authority binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_response_command_preview_binding_ref: str
    command_preview_operator_response_witness_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_branch_write_authority_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_response_command_preview_schema_path: Path = DEFAULT_SOURCE_RESPONSE_COMMAND_PREVIEW_SCHEMA,
    source_response_command_preview_example_paths: Sequence[Path] = DEFAULT_SOURCE_RESPONSE_COMMAND_PREVIEW_EXAMPLES,
) -> GitHubPrBranchWriteAuthorityBindingValidation:
    """Validate GitHub PR branch-write authority binding examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR branch-write authority binding schema", errors)
    source_schema = _load_json_object(
        source_response_command_preview_schema_path,
        "GitHub PR operator response command-preview binding schema source",
        errors,
    )
    source_response_command_preview = _load_json_object(
        source_response_command_preview_example_paths[0],
        "GitHub PR operator response command-preview binding source",
        errors,
    )
    if source_schema and source_response_command_preview:
        errors.extend(
            f"source PR operator response command-preview binding: {error}"
            for error in _validate_schema_instance(source_schema, source_response_command_preview)
        )
    _validate_source_response_command_preview_minimal(source_response_command_preview, errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR branch-write authority binding {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_branch_write_authority_binding_semantics(
            example,
            source_response_command_preview,
            errors,
            _path_label(example_path),
        )
    return GitHubPrBranchWriteAuthorityBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_response_command_preview_binding_ref=EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
        command_preview_operator_response_witness_ref=EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
    )


def write_github_pr_branch_write_authority_binding_validation(
    validation: GitHubPrBranchWriteAuthorityBindingValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic branch-write authority binding validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_source_response_command_preview_minimal(
    source_response_command_preview: Mapping[str, Any],
    errors: list[str],
) -> None:
    """Validate the source binding without importing its validator and creating a cycle."""
    if not source_response_command_preview:
        return
    label = "GitHub PR operator response command-preview binding source"
    _require_equal(
        source_response_command_preview,
        ("binding_id",),
        "agentic_service_harness_github_pr_operator_response_command_preview_binding",
        errors,
        label,
    )
    _require_equal(
        source_response_command_preview,
        ("solver_outcome",),
        "AwaitingEvidence",
        errors,
        label,
    )
    _require_equal(
        source_response_command_preview,
        ("source_operator_response_witness_ref",),
        EXPECTED_SOURCE_OPERATOR_RESPONSE_REF,
        errors,
        label,
    )
    _require_equal(
        source_response_command_preview,
        ("source_operator_approval_request_command_preview_binding_ref",),
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        source_response_command_preview,
        ("response_command_preview_binding", "command_preview_ref"),
        EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
        errors,
        label,
    )
    _require_equal(
        source_response_command_preview,
        ("response_command_preview_binding", "redacted_command_preview"),
        EXPECTED_COMMAND_PREVIEW,
        errors,
        label,
    )
    observed_vector = _get_nested(
        source_response_command_preview,
        ("response_command_preview_binding", "argument_vector_template"),
    )
    if tuple(observed_vector) != EXPECTED_ARGUMENT_VECTOR:
        errors.append(
            f"{label}: response_command_preview_binding.argument_vector_template expected "
            f"{EXPECTED_ARGUMENT_VECTOR!r}, observed {observed_vector!r}"
        )
    for path in (
        ("response_command_preview_binding", "operator_response_collected"),
        ("response_command_preview_binding", "command_execution_admitted"),
        ("response_command_preview_binding", "branch_write_enabled"),
        ("response_command_preview_binding", "pull_request_creation_enabled"),
        ("response_command_preview_binding", "repository_write_enabled"),
        ("response_command_preview_binding", "connector_call_enabled"),
        ("response_command_preview_binding", "receipt_store_append_enabled"),
        ("terminal_closure",),
    ):
        _require_equal(source_response_command_preview, path, False, errors, label)


def _validate_branch_write_authority_binding_semantics(
    payload: Mapping[str, Any],
    source_response_command_preview: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("binding_id",), EXPECTED_BINDING_ID, errors, label)
    _require_equal(
        payload,
        ("source_response_command_preview_binding_ref",),
        EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
        errors,
        label,
    )
    _require_equal(payload, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _require_equal(payload, ("witness_kind",), "branch_write_authority_binding", errors, label)
    _require_equal(payload, ("requested_evidence_ref",), EXPECTED_REQUESTED_EVIDENCE_REF, errors, label)
    _require_equal(
        payload,
        ("binding_status",),
        "AwaitingEvidence",
        errors,
        label,
    )
    _require_equal(payload, ("branch_write_binding", "authority_request_id"), EXPECTED_AUTHORITY_REQUEST_ID, errors, label)
    _require_equal(payload, ("branch_write_binding", "source_approval_request_id"), EXPECTED_APPROVAL_REQUEST_ID, errors, label)
    _require_equal(
        payload,
        ("branch_write_binding", "source_response_record_ref"),
        EXPECTED_SOURCE_RESPONSE_RECORD_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "requires_command_preview_operator_response_witness"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "command_preview_operator_response_binding_ref"),
        EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "operator_response_witness_ref"),
        EXPECTED_SOURCE_OPERATOR_RESPONSE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "operator_approval_request_command_preview_binding_ref"),
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "command_preview_ref"),
        EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "redacted_command_preview"),
        EXPECTED_COMMAND_PREVIEW,
        errors,
        label,
    )
    observed_vector = _get_nested(payload, ("branch_write_binding", "argument_vector_template"))
    if tuple(observed_vector) != EXPECTED_ARGUMENT_VECTOR:
        errors.append(
            f"{label}: branch_write_binding.argument_vector_template expected "
            f"{EXPECTED_ARGUMENT_VECTOR!r}, observed {observed_vector!r}"
        )
    _require_equal(payload, ("branch_write_binding", "command_preview_bound"), True, errors, label)
    _require_equal(payload, ("branch_write_binding", "operator_response_bound"), True, errors, label)
    _require_equal(
        payload,
        ("branch_write_binding", "required_authority_kind"),
        "branch_write_authority",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "required_evidence_ref"),
        EXPECTED_REQUESTED_EVIDENCE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("branch_write_binding", "branch_write_authority_effect"),
        "permits_branch_workspace_request_only_after_separate_uao",
        errors,
        label,
    )
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_response_command_preview:
        source_binding = _mapping(_get_nested(source_response_command_preview, ("response_command_preview_binding",)))
        _require_equal(
            payload,
            ("branch_write_binding", "operator_response_witness_ref"),
            _get_nested(source_response_command_preview, ("source_operator_response_witness_ref",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("branch_write_binding", "operator_approval_request_command_preview_binding_ref"),
            _get_nested(source_response_command_preview, ("source_operator_approval_request_command_preview_binding_ref",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("branch_write_binding", "command_preview_ref"),
            source_binding.get("command_preview_ref"),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("branch_write_binding", "redacted_command_preview"),
            source_binding.get("redacted_command_preview"),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("branch_write_binding", "argument_vector_template"),
            source_binding.get("argument_vector_template"),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("branch_write_binding", "placeholder_refs"),
            source_binding.get("placeholder_refs"),
            errors,
            label,
        )
        for required_ref in (
            EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
            EXPECTED_SOURCE_OPERATOR_RESPONSE_REF,
            EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
            EXPECTED_REQUESTED_EVIDENCE_REF,
            "evidence://operator-approval-for-pr-execution",
            "evidence://uao-pr-execution-admission",
            "evidence://repository-effect-rollback-plan",
            "evidence://receipt-store-write-path-binding",
            "evidence://effect-reconciliation-before-terminal-closure",
            "witness://github-pr-terminal-closure-certificate",
        ):
            _require_contains(
                payload,
                ("branch_write_binding", "required_before_execution_refs"),
                required_ref,
                errors,
                label,
            )
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_response_command_preview, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_response_command_preview, ("scope", "repository_connection_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "foundation_phase"),
            "foundation_pr_branch_write_command_preview_response_bound",
            errors,
            label,
        )
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
    next_action = _get_nested(payload, ("next_action",))
    if isinstance(next_action, str):
        for phrase in (
            "UAO PR admission",
            "command-preview branch-write authority",
            "PR command execution",
            "terminal closure",
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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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


def build_mutated_branch_write_authority_binding(**updates: Any) -> dict[str, Any]:
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
        "--source-response-command-preview-schema",
        type=Path,
        default=DEFAULT_SOURCE_RESPONSE_COMMAND_PREVIEW_SCHEMA,
    )
    parser.add_argument(
        "--source-response-command-preview-example",
        type=Path,
        action="append",
        dest="source_response_command_preview_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_branch_write_authority_binding(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_response_command_preview_schema_path=args.source_response_command_preview_schema,
        source_response_command_preview_example_paths=(
            tuple(args.source_response_command_preview_examples)
            if args.source_response_command_preview_examples
            else DEFAULT_SOURCE_RESPONSE_COMMAND_PREVIEW_EXAMPLES
        ),
    )
    write_github_pr_branch_write_authority_binding_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR BRANCH WRITE AUTHORITY BINDING VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
