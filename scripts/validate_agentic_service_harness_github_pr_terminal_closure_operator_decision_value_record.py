#!/usr/bin/env python3
"""Validate GitHub PR terminal closure operator decision value record.

Purpose: prove the explicit PR terminal closure operator decision value was
recorded without minting a terminal certificate or granting terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.schema.json,
examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json,
scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request,
and scripts.validate_schemas.
Invariants:
  - The decision value is exactly approve_terminal_certificate.
  - The source request remains validated as a non-authorizing request.
  - The operator decision gate is satisfied.
  - Certificate minting and terminal closure remain denied.
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

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_REQUEST_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_REQUEST_SCHEMA,
    EXPECTED_ALLOWED_VALUES,
    validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record_validation.json"
)
EXPECTED_SOURCE_REQUEST_REF = (
    "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.foundation.json"
)
EXPECTED_RECORD_ID = (
    "agentic-service-harness-github-pr-terminal-closure-operator-decision-value-record"
)
EXPECTED_DECISION_VALUE = "approve_terminal_certificate"
EXPECTED_CERTIFICATE_MINTING_DECISION = "approved_for_next_minting_step"
COMMAND_PREVIEW_DECISION_VALUE_REQUEST_EVIDENCE_KEYS = (
    "source_rejection_binding_id",
    "source_rejection_witness_ref",
    "source_decision_contract_binding_id",
    "source_decision_contract_ref",
    "operator_decision_ref",
    "requires_command_preview_generic_rejection_evidence",
    "generic_continuation_rejected",
    "operator_decision_value_present",
    "accepted_as_operator_approval",
    "terminal_closure_certificate_minted",
    "terminal_closure_authorized",
    "source_approval_gate_binding_id",
    "source_approval_gate_ref",
    "command_preview_terminal_closure_certificate_witness_ref",
    "command_preview_effect_reconciliation_witness_ref",
    "command_preview_ci_gate_before_ready_for_review_witness_ref",
    "command_preview_repository_effect_rollback_plan_witness_ref",
    "command_preview_uao_admission_witness_ref",
    "command_preview_branch_write_binding_ref",
    "command_preview_operator_response_binding_ref",
    "command_preview_operator_response_witness_ref",
    "command_preview_operator_approval_request_binding_ref",
    "command_preview_ref",
    "redacted_command_preview",
    "command_preview_bound",
)
ACTUAL_DIFF_DECISION_VALUE_REQUEST_EVIDENCE_KEYS = (
    "source_rejection_binding_id",
    "source_rejection_witness_ref",
    "source_decision_contract_binding_id",
    "source_decision_contract_ref",
    "operator_decision_ref",
    "requires_actual_diff_generic_rejection_evidence",
    "generic_continuation_rejected",
    "operator_decision_value_present",
    "accepted_as_operator_approval",
    "terminal_closure_certificate_minted",
    "terminal_closure_authorized",
    "source_approval_gate_binding_id",
    "source_approval_gate_ref",
    "actual_diff_terminal_closure_certificate_witness_ref",
    "actual_diff_effect_reconciliation_witness_ref",
    "actual_diff_ci_gate_before_ready_for_review_witness_ref",
    "actual_diff_repository_effect_rollback_plan_witness_ref",
    "actual_diff_uao_admission_witness_ref",
    "actual_diff_branch_write_binding_ref",
    "actual_diff_operator_response_witness_ref",
    "actual_diff_approval_request_binding_ref",
    "actual_non_empty_diff_receipt_ref",
    "changed_file_refs",
    "diff_refs",
    "redacted_diff_bundle_ref",
    "redacted_output_ref",
    "effect_reconciliation_collected",
    "binds_branch_state",
    "binds_pull_request_state",
    "binds_check_state",
    "binds_merge_state",
    "binds_branch_deletion_state",
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_terminal_closure_operator_decision_value_record_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.schema.json"
    ),
    "github_pr_terminal_closure_operator_decision_value_request_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.schema.json"
    ),
    "github_pr_terminal_closure_generic_continuation_rejection_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection.schema.json"
    ),
    "github_pr_terminal_closure_operator_decision_contract_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_contract.schema.json"
    ),
    "github_pr_terminal_closure_certificate_witness_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_witness.schema.json"
    ),
}
REQUIRED_FALSE_FLAGS = (
    "terminal_closure_certificate_minted",
    "terminal_closure_authorized",
    "authority_granted",
    "terminal_closure",
    "generic_continuation_accepted",
    "credential_values_allowed",
    "mutation_route_allowed",
    "self_authorization_allowed",
    "certificate_minted_by_record",
    "terminal_authority_on_record",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "ready_for_review_enabled",
    "pull_request_merge_enabled",
    "repository_write_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "receipt_store_append_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "repository_written_by_record",
    "connector_called_by_record",
    "mutation_route_admitted_by_record",
    "receipt_store_appended_by_record",
    "secret_values_serialized_by_record",
    "terminal_certificate_minted_by_record",
    "operator_decision_value_present",
    "accepted_as_operator_approval",
)
REQUIRED_TRUE_FLAGS = (
    "operator_decision_gate_satisfied",
    "planning_only",
    "read_only",
    "report_is_not_terminal_closure",
    "source_request_validated",
    "decision_value_matches_allowed_values",
    "scope_matches_request",
    "requires_command_preview_decision_value_request_evidence",
    "requires_command_preview_generic_rejection_evidence",
    "requires_actual_diff_decision_value_request_evidence",
    "requires_actual_diff_generic_rejection_evidence",
    "generic_continuation_rejected",
    "effect_reconciliation_collected",
    "binds_branch_state",
    "binds_pull_request_state",
    "binds_check_state",
    "binds_merge_state",
    "binds_branch_deletion_state",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "secret_values_serialized_by_record",
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
class GitHubPrTerminalClosureOperatorDecisionValueRecordValidation:
    """Validation report for explicit terminal closure decision value record."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_request_ref: str
    decision_value: str
    certificate_minting_decision: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_request_schema_path: Path = DEFAULT_SOURCE_REQUEST_SCHEMA,
    source_request_example_paths: Sequence[Path] = DEFAULT_SOURCE_REQUEST_EXAMPLES,
) -> GitHubPrTerminalClosureOperatorDecisionValueRecordValidation:
    """Validate GitHub PR terminal closure operator decision value record examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR terminal closure decision value record schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        schema_path=source_request_schema_path,
        example_paths=source_request_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source PR terminal closure decision value request: {error}" for error in source_validation.errors)
    source_request = _load_json_object(
        source_request_example_paths[0],
        "GitHub PR terminal closure decision value request source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR terminal closure decision value record {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_decision_value_record_semantics(example, source_request, errors, _path_label(example_path))
    return GitHubPrTerminalClosureOperatorDecisionValueRecordValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_request_ref=EXPECTED_SOURCE_REQUEST_REF,
        decision_value=EXPECTED_DECISION_VALUE,
        certificate_minting_decision=EXPECTED_CERTIFICATE_MINTING_DECISION,
    )


def write_github_pr_terminal_closure_operator_decision_value_record_validation(
    validation: GitHubPrTerminalClosureOperatorDecisionValueRecordValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic decision value record validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_decision_value_record_semantics(
    payload: Mapping[str, Any],
    source_request: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("record_id",), EXPECTED_RECORD_ID, errors, label)
    _require_equal(payload, ("source_request_ref",), EXPECTED_SOURCE_REQUEST_REF, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(payload, ("source_request_status",), "awaiting_explicit_operator_decision_value", errors, label)
    _require_equal(payload, ("operator_decision_value_collected",), True, errors, label)
    _require_equal(payload, ("explicit_operator_decision_value_present",), True, errors, label)
    _require_equal(payload, ("decision_value",), EXPECTED_DECISION_VALUE, errors, label)
    _require_equal(payload, ("decision_text",), EXPECTED_DECISION_VALUE, errors, label)
    _require_equal(payload, ("certificate_minting_decision",), EXPECTED_CERTIFICATE_MINTING_DECISION, errors, label)
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_request:
        _validate_source_request_binding(payload, source_request, errors, label)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
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


def _validate_source_request_binding(
    payload: Mapping[str, Any],
    source_request: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for path in (
        ("scope", "tenant_id"),
        ("scope", "organization_id"),
        ("scope", "project_id"),
        ("scope", "repository_connection_id"),
        ("scope", "repository_slug"),
        ("scope", "task_service_id"),
        ("scope", "read_only"),
    ):
        _require_equal(payload, path, _get_nested(source_request, path), errors, label)
    allowed_values = tuple(_get_nested(source_request, ("allowed_decision_values",)) or ())
    if allowed_values != EXPECTED_ALLOWED_VALUES:
        errors.append(f"{label}: source allowed decision values mismatch")
    if payload.get("decision_value") not in allowed_values:
        errors.append(f"{label}: decision_value is not allowed by source request")
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "source_request_id"),
        _get_nested(source_request, ("request_id",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "source_request_ref"),
        EXPECTED_SOURCE_REQUEST_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "source_request_status"),
        _get_nested(source_request, ("request_status",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "allowed_decision_values"),
        list(allowed_values),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "requires_command_preview_decision_value_request_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "operator_decision_value_collected"),
        _get_nested(source_request, ("operator_decision_value_collected",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_request_evidence", "explicit_operator_decision_value_present"),
        _get_nested(source_request, ("explicit_operator_decision_value_present",)),
        errors,
        label,
    )
    for evidence_key in COMMAND_PREVIEW_DECISION_VALUE_REQUEST_EVIDENCE_KEYS:
        _require_equal(
            payload,
            ("command_preview_decision_value_request_evidence", evidence_key),
            _get_nested(source_request, ("command_preview_generic_rejection_evidence", evidence_key)),
            errors,
            label,
        )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "source_request_id"),
        _get_nested(source_request, ("request_id",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "source_request_ref"),
        EXPECTED_SOURCE_REQUEST_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "source_request_status"),
        _get_nested(source_request, ("request_status",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "allowed_decision_values"),
        list(allowed_values),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "requires_actual_diff_decision_value_request_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "operator_decision_value_collected"),
        _get_nested(source_request, ("operator_decision_value_collected",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_request_evidence", "explicit_operator_decision_value_present"),
        _get_nested(source_request, ("explicit_operator_decision_value_present",)),
        errors,
        label,
    )
    for evidence_key in ACTUAL_DIFF_DECISION_VALUE_REQUEST_EVIDENCE_KEYS:
        _require_equal(
            payload,
            ("actual_diff_decision_value_request_evidence", evidence_key),
            _get_nested(source_request, ("actual_diff_generic_rejection_evidence", evidence_key)),
            errors,
            label,
        )


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


def build_mutated_operator_decision_value_record(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--source-request-schema", type=Path, default=DEFAULT_SOURCE_REQUEST_SCHEMA)
    parser.add_argument("--source-request-example", type=Path, action="append", dest="source_request_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_request_schema_path=args.source_request_schema,
        source_request_example_paths=(
            tuple(args.source_request_examples)
            if args.source_request_examples
            else DEFAULT_SOURCE_REQUEST_EXAMPLES
        ),
    )
    write_github_pr_terminal_closure_operator_decision_value_record_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR TERMINAL CLOSURE OPERATOR DECISION VALUE RECORD VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
