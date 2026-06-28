#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub PR terminal closure certificate witness.

Purpose: prove the GitHub pull-request terminal closure certificate request is
explicit, read-only, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_terminal_closure_certificate_witness.schema.json,
examples/agentic_service_harness_github_pr_terminal_closure_certificate_witness.foundation.json,
scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_witness, and
scripts.validate_schemas.
Invariants:
  - The certificate request binds to the GitHub PR effect reconciliation witness.
  - Terminal closure remains AwaitingEvidence and uncertified.
  - Certificate request alone grants no branch, PR, ready-for-review, merge,
    repository, connector, network, mutation-route, receipt-store, secret,
    destructive, or terminal authority.
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

from scripts.validate_agentic_service_harness_github_pr_effect_reconciliation_witness import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_EFFECT_RECONCILIATION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_EFFECT_RECONCILIATION_SCHEMA,
    EXPECTED_ARGUMENT_VECTOR,
    EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF,
    EXPECTED_COMMAND_PREVIEW,
    EXPECTED_PLACEHOLDER_REFS,
    EXPECTED_REDACTED_DIFF_BUNDLE_REF,
    EXPECTED_REDACTED_OUTPUT_REF,
    EXPECTED_SOURCE_ACTUAL_DIFF_APPROVAL_BINDING_REF,
    EXPECTED_SOURCE_BRANCH_WRITE_BINDING_REF,
    EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
    EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
    EXPECTED_SOURCE_CI_GATE_WITNESS_REF,
    EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
    EXPECTED_SOURCE_RESPONSE_WITNESS_REF,
    EXPECTED_SOURCE_ROLLBACK_PLAN_WITNESS_REF,
    EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF,
    validate_agentic_service_harness_github_pr_effect_reconciliation_witness,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_witness.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_witness.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_witness_validation.json"
)
EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF = (
    "examples/agentic_service_harness_github_pr_effect_reconciliation_witness.foundation.json"
)
EXPECTED_BINDING_ID = "agentic_service_harness_github_pr_terminal_closure_certificate_witness"
EXPECTED_TERMINAL_CLOSURE_CERTIFICATE_REQUEST_ID = "terminal-closure.github-pr-chain"
EXPECTED_SOURCE_EFFECT_RECONCILIATION_REQUEST_ID = "effect-reconciliation.github-pr-before-terminal-closure"
EXPECTED_REQUESTED_EVIDENCE_REF = "evidence://github-pr-terminal-closure-certificate"
EXPECTED_SOURCE_EFFECT_RECONCILIATION_EVIDENCE_REF = "evidence://effect-reconciliation-before-terminal-closure"
EXPECTED_REMAINING_WITNESSES: tuple[str, ...] = ()
REQUIRED_RECEIPT_REFS = {
    "github_pr_terminal_closure_certificate_witness_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_witness.schema.json"
    ),
    "github_pr_effect_reconciliation_witness_schema": (
        "schemas/agentic_service_harness_github_pr_effect_reconciliation_witness.schema.json"
    ),
    "github_pr_effect_reconciliation_witness_example": (
        "examples/agentic_service_harness_github_pr_effect_reconciliation_witness.foundation.json"
    ),
    "github_pr_ci_gate_before_ready_for_review_witness_schema": (
        "schemas/agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness.schema.json"
    ),
    "github_pr_ci_gate_before_ready_for_review_witness_example": (
        "examples/agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness.foundation.json"
    ),
    "github_pr_repository_effect_rollback_plan_witness_schema": (
        "schemas/agentic_service_harness_github_pr_repository_effect_rollback_plan_witness.schema.json"
    ),
    "github_pr_repository_effect_rollback_plan_witness_example": (
        "examples/agentic_service_harness_github_pr_repository_effect_rollback_plan_witness.foundation.json"
    ),
    "github_pr_uao_admission_witness_schema": (
        "schemas/agentic_service_harness_github_pr_uao_admission_witness.schema.json"
    ),
    "github_pr_uao_admission_witness_example": "examples/agentic_service_harness_github_pr_uao_admission_witness.foundation.json",
    "github_pr_operator_response_command_preview_binding_schema": (
        "schemas/agentic_service_harness_github_pr_operator_response_command_preview_binding.schema.json"
    ),
    "github_pr_operator_response_command_preview_binding_example": (
        EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF
    ),
    "github_pr_operator_approval_request_command_preview_binding_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.schema.json"
    ),
    "github_pr_operator_approval_request_command_preview_binding_example": (
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF
    ),
    "github_pr_creation_command_preview_schema": (
        "schemas/agentic_service_harness_github_pr_creation_command_preview.schema.json"
    ),
    "github_pr_creation_command_preview_example": EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
    "github_pr_branch_write_authority_binding_schema": (
        "schemas/agentic_service_harness_github_pr_branch_write_authority_binding.schema.json"
    ),
    "github_pr_branch_write_authority_binding_example": (
        "examples/agentic_service_harness_github_pr_branch_write_authority_binding.foundation.json"
    ),
    "github_pr_operator_response_witness_schema": (
        "schemas/agentic_service_harness_github_pr_operator_response_witness.schema.json"
    ),
    "github_pr_operator_response_witness_example": (
        "examples/agentic_service_harness_github_pr_operator_response_witness.foundation.json"
    ),
    "github_pr_operator_approval_request_actual_non_empty_diff_binding_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.schema.json"
    ),
    "github_pr_operator_approval_request_actual_non_empty_diff_binding_example": (
        "examples/agentic_service_harness_github_pr_operator_approval_request_actual_non_empty_diff_binding.foundation.json"
    ),
    "github_pr_operator_approval_request_schema": (
        "schemas/agentic_service_harness_github_pr_operator_approval_request.schema.json"
    ),
    "github_pr_actual_non_empty_diff_admission_binding_schema": (
        "schemas/agentic_service_harness_github_pr_actual_non_empty_diff_admission_binding.schema.json"
    ),
    "github_pr_admission_preflight_schema": "schemas/agentic_service_harness_github_pr_admission_preflight.schema.json",
    "github_repo_task_service_schema": "schemas/agentic_service_harness_github_repo_task_service.schema.json",
}
REQUIRED_FALSE_FLAGS = (
    "terminal_closure_certificate_collected",
    "authority_granted",
    "terminal_closure",
    "effect_reconciliation_collected",
    "terminal_closure_authorized",
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
    "branch_created",
    "pull_request_opened",
    "ready_for_review_marked",
    "pull_request_merged",
    "branch_deleted",
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
    "requires_command_preview_effect_reconciliation_witness",
    "requires_actual_diff_effect_reconciliation_witness",
    "command_preview_bound",
    "operator_response_bound",
    "effect_reconciliation_required",
    "terminal_closure_certificate_required",
    "certifies_branch_state",
    "certifies_pull_request_state",
    "certifies_check_state",
    "certifies_merge_state",
    "certifies_branch_deletion_state",
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
class GitHubPrTerminalClosureCertificateWitnessValidation:
    """Schema and semantic validation report for terminal closure certificate witness."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_effect_reconciliation_witness_ref: str
    command_preview_effect_reconciliation_witness_ref: str
    actual_diff_effect_reconciliation_witness_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_terminal_closure_certificate_witness(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_effect_reconciliation_schema_path: Path = DEFAULT_SOURCE_EFFECT_RECONCILIATION_SCHEMA,
    source_effect_reconciliation_example_paths: Sequence[Path] = DEFAULT_SOURCE_EFFECT_RECONCILIATION_EXAMPLES,
) -> GitHubPrTerminalClosureCertificateWitnessValidation:
    """Validate GitHub PR terminal closure certificate witness examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR terminal closure certificate witness schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_effect_reconciliation_witness(
        schema_path=source_effect_reconciliation_schema_path,
        example_paths=source_effect_reconciliation_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source PR effect reconciliation witness: {error}" for error in source_validation.errors)
    source_effect_reconciliation_witness = _load_json_object(
        source_effect_reconciliation_example_paths[0],
        "GitHub PR effect reconciliation witness source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR terminal closure certificate witness {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_terminal_closure_certificate_witness_semantics(
            example,
            source_effect_reconciliation_witness,
            errors,
            _path_label(example_path),
        )
    return GitHubPrTerminalClosureCertificateWitnessValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_effect_reconciliation_witness_ref=EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF,
        command_preview_effect_reconciliation_witness_ref=EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF,
        actual_diff_effect_reconciliation_witness_ref=EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF,
    )


def write_github_pr_terminal_closure_certificate_witness_validation(
    validation: GitHubPrTerminalClosureCertificateWitnessValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic terminal closure certificate witness validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_terminal_closure_certificate_witness_semantics(
    payload: Mapping[str, Any],
    source_effect_reconciliation_witness: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("binding_id",), EXPECTED_BINDING_ID, errors, label)
    _require_equal(
        payload,
        ("source_effect_reconciliation_witness_ref",),
        EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(payload, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _require_equal(payload, ("witness_kind",), "terminal_closure_certificate_witness", errors, label)
    _require_equal(payload, ("requested_evidence_ref",), EXPECTED_REQUESTED_EVIDENCE_REF, errors, label)
    _require_equal(payload, ("terminal_closure_status",), "AwaitingEvidence", errors, label)
    _require_equal(
        payload,
        ("terminal_closure_certificate", "terminal_closure_certificate_request_id"),
        EXPECTED_TERMINAL_CLOSURE_CERTIFICATE_REQUEST_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "source_effect_reconciliation_request_id"),
        EXPECTED_SOURCE_EFFECT_RECONCILIATION_REQUEST_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "source_effect_reconciliation_evidence_ref"),
        EXPECTED_SOURCE_EFFECT_RECONCILIATION_EVIDENCE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "requires_command_preview_effect_reconciliation_witness"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_effect_reconciliation_witness_ref"),
        EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_ci_gate_before_ready_for_review_witness_ref"),
        EXPECTED_SOURCE_CI_GATE_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_repository_effect_rollback_plan_witness_ref"),
        EXPECTED_SOURCE_ROLLBACK_PLAN_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_uao_admission_witness_ref"),
        EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_branch_write_binding_ref"),
        EXPECTED_SOURCE_BRANCH_WRITE_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_operator_response_binding_ref"),
        EXPECTED_SOURCE_RESPONSE_COMMAND_PREVIEW_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_operator_response_witness_ref"),
        EXPECTED_SOURCE_RESPONSE_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_operator_approval_request_binding_ref"),
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "command_preview_ref"),
        EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "redacted_command_preview"),
        EXPECTED_COMMAND_PREVIEW,
        errors,
        label,
    )
    observed_vector = _get_nested(payload, ("terminal_closure_certificate", "argument_vector_template"))
    if tuple(observed_vector) != EXPECTED_ARGUMENT_VECTOR:
        errors.append(
            f"{label}: terminal_closure_certificate.argument_vector_template expected "
            f"{EXPECTED_ARGUMENT_VECTOR!r}, observed {observed_vector!r}"
        )
    observed_placeholders = _get_nested(payload, ("terminal_closure_certificate", "placeholder_refs"))
    if tuple(observed_placeholders) != EXPECTED_PLACEHOLDER_REFS:
        errors.append(
            f"{label}: terminal_closure_certificate.placeholder_refs expected "
            f"{EXPECTED_PLACEHOLDER_REFS!r}, observed {observed_placeholders!r}"
        )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_effect_reconciliation_witness_ref"),
        EXPECTED_SOURCE_EFFECT_RECONCILIATION_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_ci_gate_before_ready_for_review_witness_ref"),
        EXPECTED_SOURCE_CI_GATE_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_repository_effect_rollback_plan_witness_ref"),
        EXPECTED_SOURCE_ROLLBACK_PLAN_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_uao_admission_witness_ref"),
        EXPECTED_SOURCE_UAO_ADMISSION_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_branch_write_binding_ref"),
        EXPECTED_SOURCE_BRANCH_WRITE_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_operator_response_witness_ref"),
        EXPECTED_SOURCE_RESPONSE_WITNESS_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_diff_approval_request_binding_ref"),
        EXPECTED_SOURCE_ACTUAL_DIFF_APPROVAL_BINDING_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "actual_non_empty_diff_receipt_ref"),
        EXPECTED_ACTUAL_NON_EMPTY_DIFF_RECEIPT_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "redacted_diff_bundle_ref"),
        EXPECTED_REDACTED_DIFF_BUNDLE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "redacted_output_ref"),
        EXPECTED_REDACTED_OUTPUT_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "required_witness_kind"),
        "terminal_closure_certificate",
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "required_evidence_ref"),
        EXPECTED_REQUESTED_EVIDENCE_REF,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "required_certificate_result"),
        "terminal_closure_certificate_requires_effect_reconciliation_evidence",
        errors,
        label,
    )
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    if source_effect_reconciliation_witness:
        _require_equal(
            payload,
            ("scope", "repository_slug"),
            _get_nested(source_effect_reconciliation_witness, ("scope", "repository_slug")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("scope", "repository_connection_id"),
            _get_nested(source_effect_reconciliation_witness, ("scope", "repository_connection_id")),
            errors,
            label,
        )
        _require_equal(
            payload,
            ("terminal_closure_certificate", "effect_reconciliation_collected"),
            _get_nested(source_effect_reconciliation_witness, ("effect_reconciliation_collected",)),
            errors,
            label,
        )
        source_effect_reconciliation = _mapping(
            _get_nested(source_effect_reconciliation_witness, ("effect_reconciliation",))
        )
        for key in (
            "command_preview_ci_gate_before_ready_for_review_witness_ref",
            "command_preview_repository_effect_rollback_plan_witness_ref",
            "command_preview_uao_admission_witness_ref",
            "command_preview_branch_write_binding_ref",
            "command_preview_operator_response_binding_ref",
            "command_preview_operator_response_witness_ref",
            "command_preview_operator_approval_request_binding_ref",
            "command_preview_ref",
            "redacted_command_preview",
            "argument_vector_template",
            "placeholder_refs",
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
        ):
            _require_equal(
                payload,
                ("terminal_closure_certificate", key),
                source_effect_reconciliation.get(key),
                errors,
                label,
            )
    _require_equal(payload, ("terminal_closure_certificate", "command_preview_bound"), True, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "operator_response_bound"), True, errors, label)
    observed_witnesses = _get_nested(payload, ("remaining_witnesses",))
    if not isinstance(observed_witnesses, list):
        errors.append(f"{label}: remaining_witnesses must be a list")
    elif tuple(observed_witnesses) != EXPECTED_REMAINING_WITNESSES:
        errors.append(f"{label}: remaining_witnesses must be empty after terminal closure certificate request")
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


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


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


def build_mutated_terminal_closure_certificate_witness(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--source-effect-reconciliation-schema", type=Path, default=DEFAULT_SOURCE_EFFECT_RECONCILIATION_SCHEMA)
    parser.add_argument(
        "--source-effect-reconciliation-example",
        type=Path,
        action="append",
        dest="source_effect_reconciliation_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_witness(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_effect_reconciliation_schema_path=args.source_effect_reconciliation_schema,
        source_effect_reconciliation_example_paths=(
            tuple(args.source_effect_reconciliation_examples)
            if args.source_effect_reconciliation_examples
            else DEFAULT_SOURCE_EFFECT_RECONCILIATION_EXAMPLES
        ),
    )
    write_github_pr_terminal_closure_certificate_witness_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR TERMINAL CLOSURE CERTIFICATE WITNESS VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
