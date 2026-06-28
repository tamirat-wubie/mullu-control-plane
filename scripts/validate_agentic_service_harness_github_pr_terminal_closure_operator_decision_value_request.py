#!/usr/bin/env python3
"""Validate GitHub PR terminal closure operator decision value request.

Purpose: prove the PR terminal closure chain can request an explicit operator
decision value without collecting that value, minting a certificate, or granting
terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.schema.json,
examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.foundation.json,
scripts.validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection,
and scripts.validate_schemas.
Invariants:
  - The request remains `AwaitingEvidence`.
  - No operator decision value is collected.
  - Only approve_terminal_certificate or deny_terminal_certificate may satisfy
    the future decision value.
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

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_REJECTION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_REJECTION_SCHEMA,
    validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request_validation.json"
)
EXPECTED_SOURCE_REJECTION_REF = (
    "examples/agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection.foundation.json"
)
EXPECTED_REQUEST_ID = (
    "agentic-service-harness-github-pr-terminal-closure-operator-decision-value-request"
)
EXPECTED_ALLOWED_VALUES = ("approve_terminal_certificate", "deny_terminal_certificate")
EXPECTED_REQUIRED_FIELDS = (
    "decision_value",
    "operator_id",
    "decision_text",
    "scope",
    "created_at",
    "witness_ref",
)
EXPECTED_FORBIDDEN_FIELDS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
COMMAND_PREVIEW_GENERIC_REJECTION_EVIDENCE_KEYS = (
    "source_approval_gate_binding_id",
    "source_approval_gate_ref",
    "operator_decision_ref",
    "requires_command_preview_operator_approval_gate_evidence",
    "requires_command_preview_terminal_closure_certificate_witness",
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
ACTUAL_DIFF_GENERIC_REJECTION_EVIDENCE_KEYS = (
    "source_approval_gate_binding_id",
    "source_approval_gate_ref",
    "operator_decision_ref",
    "requires_actual_diff_operator_approval_gate_evidence",
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
    "operator_decision_value_collected",
    "explicit_operator_decision_value_present",
    "terminal_closure_certificate_minted",
    "terminal_closure_authorized",
    "authority_granted",
    "terminal_closure",
    "freeform_continuation_allowed",
    "credential_values_allowed",
    "mutation_route_allowed",
    "self_authorization_allowed",
    "certificate_minting_on_request",
    "terminal_authority_on_request",
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
    "repository_written_by_request",
    "connector_called_by_request",
    "mutation_route_admitted_by_request",
    "receipt_store_appended_by_request",
    "secret_values_serialized_by_request",
    "terminal_certificate_minted_by_request",
    "mints_terminal_certificate",
    "grants_terminal_authority",
    "operator_decision_value_present",
    "accepted_as_operator_approval",
)
REQUIRED_TRUE_FLAGS = (
    "generic_continuation_rejected",
    "requires_command_preview_generic_rejection_evidence",
    "requires_command_preview_operator_approval_gate_evidence",
    "requires_command_preview_terminal_closure_certificate_witness",
    "command_preview_bound",
    "requires_actual_diff_generic_rejection_evidence",
    "requires_actual_diff_operator_approval_gate_evidence",
    "effect_reconciliation_collected",
    "binds_branch_state",
    "binds_pull_request_state",
    "binds_check_state",
    "binds_merge_state",
    "binds_branch_deletion_state",
    "planning_only",
    "read_only",
    "report_is_not_terminal_closure",
    "required",
    "scope_must_match_request",
    "witness_ref_required",
    "records_operator_intent_only",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "secret_values_serialized_by_request",
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
class GitHubPrTerminalClosureOperatorDecisionValueRequestValidation:
    """Validation report for explicit terminal closure decision value request."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_rejection_witness_ref: str
    allowed_decision_values: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        payload["allowed_decision_values"] = list(self.allowed_decision_values)
        return payload


def validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_rejection_schema_path: Path = DEFAULT_SOURCE_REJECTION_SCHEMA,
    source_rejection_example_paths: Sequence[Path] = DEFAULT_SOURCE_REJECTION_EXAMPLES,
) -> GitHubPrTerminalClosureOperatorDecisionValueRequestValidation:
    """Validate GitHub PR terminal closure operator decision value request examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR terminal closure decision value request schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection(
        schema_path=source_rejection_schema_path,
        example_paths=source_rejection_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source PR terminal closure generic rejection: {error}" for error in source_validation.errors)
    source_rejection = _load_json_object(
        source_rejection_example_paths[0],
        "GitHub PR terminal closure generic rejection source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR terminal closure decision value request {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_decision_value_request_semantics(example, source_rejection, errors, _path_label(example_path))
    return GitHubPrTerminalClosureOperatorDecisionValueRequestValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_rejection_witness_ref=EXPECTED_SOURCE_REJECTION_REF,
        allowed_decision_values=EXPECTED_ALLOWED_VALUES,
    )


def write_github_pr_terminal_closure_operator_decision_value_request_validation(
    validation: GitHubPrTerminalClosureOperatorDecisionValueRequestValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic decision value request validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_decision_value_request_semantics(
    payload: Mapping[str, Any],
    source_rejection: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("request_id",), EXPECTED_REQUEST_ID, errors, label)
    _require_equal(payload, ("source_rejection_witness_ref",), EXPECTED_SOURCE_REJECTION_REF, errors, label)
    _require_equal(payload, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _require_equal(payload, ("request_status",), "awaiting_explicit_operator_decision_value", errors, label)
    _require_equal(payload, ("requested_input_kind",), "explicit_terminal_closure_operator_decision_value", errors, label)
    _require_equal(payload, ("allowed_decision_values",), list(EXPECTED_ALLOWED_VALUES), errors, label)
    _require_equal(payload, ("rejected_input_kind",), "generic_continuation", errors, label)
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_rejection:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_rejection, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_rejection, ("scope", "repository_connection_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("generic_continuation_rejected",),
            _get_nested(source_rejection, ("generic_continuation_rejected",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "source_rejection_binding_id"),
            _get_nested(source_rejection, ("binding_id",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "source_rejection_witness_ref"),
            EXPECTED_SOURCE_REJECTION_REF,
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "source_decision_contract_binding_id"),
            _get_nested(source_rejection, ("continuation_rejection", "source_decision_contract_binding_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "source_decision_contract_ref"),
            _get_nested(source_rejection, ("continuation_rejection", "source_decision_contract_ref")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "rejection_id"),
            _get_nested(source_rejection, ("continuation_rejection", "rejection_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "rejection_status"),
            _get_nested(source_rejection, ("rejection_status",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "requires_command_preview_generic_rejection_evidence"),
            True,
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "generic_continuation_rejected"),
            _get_nested(source_rejection, ("generic_continuation_rejected",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "operator_decision_value_present"),
            _get_nested(source_rejection, ("operator_decision_value_present",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "accepted_as_operator_approval"),
            _get_nested(source_rejection, ("accepted_as_operator_approval",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "terminal_closure_certificate_minted"),
            _get_nested(source_rejection, ("terminal_closure_certificate_minted",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("command_preview_generic_rejection_evidence", "terminal_closure_authorized"),
            _get_nested(source_rejection, ("terminal_closure_authorized",)),
            errors,
            label,
        )
        for evidence_key in COMMAND_PREVIEW_GENERIC_REJECTION_EVIDENCE_KEYS:
            _require_equal(
                payload,
                ("command_preview_generic_rejection_evidence", evidence_key),
                _get_nested(
                    source_rejection,
                    ("continuation_rejection", "command_preview_decision_contract_evidence", evidence_key),
                ),
                errors,
                label,
            )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "source_rejection_binding_id"),
            _get_nested(source_rejection, ("binding_id",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "source_rejection_witness_ref"),
            EXPECTED_SOURCE_REJECTION_REF,
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "source_decision_contract_binding_id"),
            _get_nested(source_rejection, ("continuation_rejection", "source_decision_contract_binding_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "source_decision_contract_ref"),
            _get_nested(source_rejection, ("continuation_rejection", "source_decision_contract_ref")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "rejection_id"),
            _get_nested(source_rejection, ("continuation_rejection", "rejection_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "rejection_status"),
            _get_nested(source_rejection, ("rejection_status",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "requires_actual_diff_generic_rejection_evidence"),
            True,
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "generic_continuation_rejected"),
            _get_nested(source_rejection, ("generic_continuation_rejected",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "operator_decision_value_present"),
            _get_nested(source_rejection, ("operator_decision_value_present",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "accepted_as_operator_approval"),
            _get_nested(source_rejection, ("accepted_as_operator_approval",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "terminal_closure_certificate_minted"),
            _get_nested(source_rejection, ("terminal_closure_certificate_minted",)),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("actual_diff_generic_rejection_evidence", "terminal_closure_authorized"),
            _get_nested(source_rejection, ("terminal_closure_authorized",)),
            errors,
            label,
        )
        for evidence_key in ACTUAL_DIFF_GENERIC_REJECTION_EVIDENCE_KEYS:
            _require_equal(
                payload,
                ("actual_diff_generic_rejection_evidence", evidence_key),
                _get_nested(
                    source_rejection,
                    ("continuation_rejection", "actual_diff_decision_contract_evidence", evidence_key),
                ),
                errors,
                label,
            )
    requirements = _get_nested(payload, ("decision_value_requirements",))
    if not isinstance(requirements, list):
        errors.append(f"{label}: decision_value_requirements must be a list")
    else:
        observed_values = tuple(
            entry.get("decision_value") for entry in requirements if isinstance(entry, Mapping)
        )
        if observed_values != EXPECTED_ALLOWED_VALUES:
            errors.append(f"{label}: decision values must match required order")
        for entry in requirements:
            if not isinstance(entry, Mapping):
                errors.append(f"{label}: decision value requirement entries must be objects")
                continue
            value_label = str(entry.get("decision_value", "unknown"))
            if tuple(entry.get("required_fields", ())) != EXPECTED_REQUIRED_FIELDS:
                errors.append(f"{label}: {value_label} required_fields mismatch")
            if tuple(entry.get("forbidden_fields", ())) != EXPECTED_FORBIDDEN_FIELDS:
                errors.append(f"{label}: {value_label} forbidden_fields mismatch")
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


def build_mutated_operator_decision_value_request(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--source-rejection-schema", type=Path, default=DEFAULT_SOURCE_REJECTION_SCHEMA)
    parser.add_argument("--source-rejection-example", type=Path, action="append", dest="source_rejection_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_rejection_schema_path=args.source_rejection_schema,
        source_rejection_example_paths=(
            tuple(args.source_rejection_examples)
            if args.source_rejection_examples
            else DEFAULT_SOURCE_REJECTION_EXAMPLES
        ),
    )
    write_github_pr_terminal_closure_operator_decision_value_request_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR TERMINAL CLOSURE OPERATOR DECISION VALUE REQUEST VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
