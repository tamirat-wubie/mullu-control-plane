#!/usr/bin/env python3
"""Validate GitHub PR operator response command preview binding.

Purpose: prove the missing operator response witness is bound to the
command-preview approval binding before PR command execution can be considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_operator_response_command_preview_binding.schema.json,
examples/agentic_service_harness_github_pr_operator_response_command_preview_binding.foundation.json,
scripts.validate_agentic_service_harness_github_pr_operator_response_witness,
scripts.validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding,
and scripts.validate_schemas.
Invariants:
  - The binding consumes the operator response witness.
  - The binding consumes the command-preview approval binding.
  - The rendered command remains redacted and non-executed.
  - Command execution, PR creation, branch writes, repository writes,
    connector calls, mutation routes, raw content, receipt append, secrets,
    and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_COMMAND_APPROVAL_BINDING_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_COMMAND_APPROVAL_BINDING_SCHEMA,
    EXPECTED_ARGUMENT_VECTOR,
    EXPECTED_COMMAND_PREVIEW,
    EXPECTED_BINDING_ID as EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_ID,
    validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding,
)
from scripts.validate_agentic_service_harness_github_pr_operator_response_witness import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_OPERATOR_RESPONSE_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_OPERATOR_RESPONSE_SCHEMA,
    EXPECTED_APPROVAL_REQUEST_ID,
    EXPECTED_RESPONSE_WITNESS_ID,
    EXPECTED_REQUESTED_EVIDENCE_REF,
    validate_agentic_service_harness_github_pr_operator_response_witness,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_operator_response_command_preview_binding.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_operator_response_command_preview_binding.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_operator_response_command_preview_binding_validation.json"
)
EXPECTED_BINDING_ID = "agentic_service_harness_github_pr_operator_response_command_preview_binding"
EXPECTED_SOURCE_OPERATOR_RESPONSE_REF = (
    "examples/agentic_service_harness_github_pr_operator_response_witness.foundation.json"
)
EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF = (
    "examples/agentic_service_harness_github_pr_operator_approval_request_command_preview_binding.foundation.json"
)
EXPECTED_SOURCE_COMMAND_PREVIEW_REF = (
    "examples/agentic_service_harness_github_pr_creation_command_preview.foundation.json"
)
EXPECTED_WITNESS_KIND = "github_pr_operator_response_command_preview_binding"
EXPECTED_BINDING_STATUS = "operator_response_witness_bound_to_command_preview_without_execution_authority"
EXPECTED_REMAINING_WITNESSES = (
    "operator_execution_approval",
    "branch_write_authority",
    "uao_pr_execution_admission",
    "repository_effect_rollback_plan",
    "receipt_store_write_path",
    "effect_reconciliation",
    "terminal_certificate",
)
REQUIRED_PLACEHOLDER_REFS = (
    "placeholder://branch-ref",
    "placeholder://redacted-title-ref",
    "placeholder://redacted-body-file-ref",
)
REQUIRED_BEFORE_EXECUTION_REFS = (
    EXPECTED_SOURCE_OPERATOR_RESPONSE_REF,
    EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
    EXPECTED_REQUESTED_EVIDENCE_REF,
    "evidence://operator-approval-for-pr-execution",
    "evidence://branch-write-authority-binding",
    "evidence://uao-pr-execution-admission",
    "evidence://repository-effect-rollback-plan",
    "evidence://receipt-store-write-path-binding",
    "evidence://effect-reconciliation-before-terminal-closure",
    "witness://github-pr-terminal-closure-certificate",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-response/not-collected",
    "blocked://operator-approval/not-granted",
    "blocked://command-execution/not-admitted",
    "blocked://branch-write-authority/not-bound",
    "blocked://uao/pr-execution-not-admitted",
    "blocked://repository-effect-rollback/not-bound",
    "blocked://receipt-store-append/not-enabled",
    "blocked://terminal-certificate/not-verified",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
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
    "github_pr_operator_approval_request_command_preview_binding_example": (
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF
    ),
    "github_pr_creation_command_preview_schema": (
        "schemas/agentic_service_harness_github_pr_creation_command_preview.schema.json"
    ),
    "github_pr_creation_command_preview_example": EXPECTED_SOURCE_COMMAND_PREVIEW_REF,
}
COMMAND_PREVIEW_APPROVAL_REQUEST_EVIDENCE_BINDINGS = (
    ("source_binding_id", ("binding_id",)),
    ("source_command_preview_ref", ("source_command_preview_ref",)),
    (
        "source_operator_approval_request_actual_non_empty_diff_binding_ref",
        ("source_operator_approval_request_actual_non_empty_diff_binding_ref",),
    ),
    ("source_operator_approval_request_ref", ("source_operator_approval_request_ref",)),
    ("source_approval_request_id", ("approval_command_preview_binding", "approval_request_id")),
    ("source_requested_evidence_ref", ("approval_command_preview_binding", "requested_evidence_ref")),
    ("source_redacted_command_preview", ("approval_command_preview_binding", "redacted_command_preview")),
    ("source_argument_vector_template", ("approval_command_preview_binding", "argument_vector_template")),
    ("source_placeholder_refs", ("approval_command_preview_binding", "placeholder_refs")),
    ("source_required_before_execution_refs", ("approval_command_preview_binding", "required_before_execution_refs")),
    ("source_blocked_reason_refs", ("approval_command_preview_binding", "blocked_reason_refs")),
    ("source_approval_request_bound", ("approval_command_preview_binding", "approval_request_bound")),
    ("source_command_preview_bound", ("approval_command_preview_binding", "command_preview_bound")),
    ("source_preview_rendered", ("approval_command_preview_binding", "preview_rendered")),
    ("source_operator_response_collected", ("approval_command_preview_binding", "operator_response_collected")),
    ("source_operator_approval_granted", ("approval_command_preview_binding", "operator_approval_granted")),
    ("source_operator_approval_rejected", ("approval_command_preview_binding", "operator_approval_rejected")),
    ("source_command_execution_admitted", ("approval_command_preview_binding", "command_execution_admitted")),
    ("source_adapter_execution_enabled", ("approval_command_preview_binding", "adapter_execution_enabled")),
    ("source_branch_write_enabled", ("approval_command_preview_binding", "branch_write_enabled")),
    ("source_pull_request_creation_enabled", ("approval_command_preview_binding", "pull_request_creation_enabled")),
    ("source_repository_write_enabled", ("approval_command_preview_binding", "repository_write_enabled")),
    ("source_connector_call_enabled", ("approval_command_preview_binding", "connector_call_enabled")),
    ("source_mutation_route_enabled", ("approval_command_preview_binding", "mutation_route_enabled")),
    ("source_receipt_store_append_enabled", ("approval_command_preview_binding", "receipt_store_append_enabled")),
    ("source_terminal_certificate_verified", ("approval_command_preview_binding", "terminal_certificate_verified")),
    (
        "source_command_preview_execution_admission_bound",
        ("command_preview_execution_admission_evidence", "command_preview_execution_admission_bound"),
    ),
    (
        "source_operator_approval_request_consumes_execution_admission_evidence",
        (
            "command_preview_execution_admission_evidence",
            "operator_approval_request_consumes_execution_admission_evidence",
        ),
    ),
    (
        "source_operator_approval_request_remains_request_only",
        ("command_preview_execution_admission_evidence", "operator_approval_request_remains_request_only"),
    ),
    ("source_contains_secret_values", ("command_preview_execution_admission_evidence", "contains_secret_values")),
)
REQUIRED_FALSE_FLAGS = (
    "terminal_closure",
    "execution_admitted",
    "pr_creation_enabled",
    "repository_write_enabled",
    "external_adapter_integrated",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "operator_response_collected",
    "operator_approval_granted",
    "operator_approval_rejected",
    "command_execution_admitted",
    "adapter_execution_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "repository_write_enabled",
    "connector_call_enabled",
    "mutation_route_enabled",
    "receipt_store_append_enabled",
    "terminal_certificate_verified",
    "authority_granted",
    "live_adapter_execution_enabled",
    "connector_calls_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "default_high_risk_authority",
    "operator_response_recorded",
    "command_executed",
    "adapter_executed",
    "branch_pushed",
    "pull_request_opened",
    "repository_written",
    "connector_called",
    "mutation_route_admitted",
    "receipt_store_appended",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "source_operator_response_collected",
    "source_operator_approval_granted",
    "source_operator_approval_rejected",
    "source_command_execution_admitted",
    "source_adapter_execution_enabled",
    "source_branch_write_enabled",
    "source_pull_request_creation_enabled",
    "source_repository_write_enabled",
    "source_connector_call_enabled",
    "source_mutation_route_enabled",
    "source_receipt_store_append_enabled",
    "source_terminal_certificate_verified",
    "source_contains_secret_values",
)
REQUIRED_TRUE_FLAGS = (
    "planning_only",
    "read_only",
    "preview_only",
    "report_is_not_terminal_closure",
    "response_witness_only",
    "operator_response_bound",
    "command_preview_bound",
    "preview_rendered",
    "blocks_command_execution",
    "required_for_closure",
    "source_approval_request_bound",
    "source_command_preview_bound",
    "source_preview_rendered",
    "source_command_preview_execution_admission_bound",
    "source_operator_approval_request_consumes_execution_admission_evidence",
    "source_operator_approval_request_remains_request_only",
    "operator_response_consumes_approval_request_evidence",
    "operator_response_remains_uncollected",
    "command_preview_response_remains_preview_only",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "secret_values_serialized",
    "source_contains_secret_values",
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
class GitHubPrOperatorResponseCommandPreviewBindingValidation:
    """Validation report for operator response command-preview binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_operator_response_witness_ref: str
    source_operator_approval_request_command_preview_binding_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_operator_response_command_preview_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_operator_response_schema_path: Path = DEFAULT_OPERATOR_RESPONSE_SCHEMA,
    source_operator_response_example_paths: Sequence[Path] = DEFAULT_OPERATOR_RESPONSE_EXAMPLES,
    source_command_approval_binding_schema_path: Path = DEFAULT_COMMAND_APPROVAL_BINDING_SCHEMA,
    source_command_approval_binding_example_paths: Sequence[Path] = DEFAULT_COMMAND_APPROVAL_BINDING_EXAMPLES,
) -> GitHubPrOperatorResponseCommandPreviewBindingValidation:
    """Validate operator response command-preview binding examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR operator response command preview binding schema", errors)
    operator_response_validation = validate_agentic_service_harness_github_pr_operator_response_witness(
        schema_path=source_operator_response_schema_path,
        example_paths=source_operator_response_example_paths,
    )
    if not operator_response_validation.ok:
        errors.extend(f"source GitHub PR operator response witness: {error}" for error in operator_response_validation.errors)
    command_approval_validation = (
        validate_agentic_service_harness_github_pr_operator_approval_request_command_preview_binding(
            schema_path=source_command_approval_binding_schema_path,
            example_paths=source_command_approval_binding_example_paths,
        )
    )
    if not command_approval_validation.ok:
        errors.extend(
            f"source GitHub PR command-preview approval binding: {error}"
            for error in command_approval_validation.errors
        )
    source_operator_response = _load_json_object(
        source_operator_response_example_paths[0],
        "GitHub PR operator response witness source",
        errors,
    )
    source_command_approval_binding = _load_json_object(
        source_command_approval_binding_example_paths[0],
        "GitHub PR command-preview approval binding source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR operator response command preview binding {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_response_command_preview_binding_semantics(
            example,
            source_operator_response,
            source_command_approval_binding,
            errors,
            _path_label(example_path),
        )
    return GitHubPrOperatorResponseCommandPreviewBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_operator_response_witness_ref=EXPECTED_SOURCE_OPERATOR_RESPONSE_REF,
        source_operator_approval_request_command_preview_binding_ref=EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
    )


def write_github_pr_operator_response_command_preview_binding_validation(
    validation: GitHubPrOperatorResponseCommandPreviewBindingValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic operator response command-preview binding report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_response_command_preview_binding_semantics(
    payload: Mapping[str, Any],
    source_operator_response: Mapping[str, Any],
    source_command_approval_binding: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("binding_id",), EXPECTED_BINDING_ID, errors, label)
    _require_equal(payload, ("source_operator_response_witness_ref",), EXPECTED_SOURCE_OPERATOR_RESPONSE_REF, errors, label)
    _require_equal(
        payload,
        ("source_operator_approval_request_command_preview_binding_ref",),
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
        errors,
        label,
    )
    _require_equal(payload, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _require_equal(payload, ("witness_kind",), EXPECTED_WITNESS_KIND, errors, label)
    _require_equal(payload, ("binding_status",), EXPECTED_BINDING_STATUS, errors, label)
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    _validate_source_operator_response(payload, source_operator_response, errors, label)
    _validate_source_command_approval_binding(payload, source_command_approval_binding, errors, label)
    _validate_command_preview_approval_request_evidence(payload, source_command_approval_binding, errors, label)
    _validate_command_shape(payload, errors, label)
    _validate_refs(payload, errors, label)
    _validate_remaining_witnesses(payload, errors, label)
    _validate_flags_and_surface(payload, errors, label)


def _validate_source_operator_response(
    payload: Mapping[str, Any],
    source_operator_response: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not source_operator_response:
        return
    _require_equal(
        source_operator_response,
        ("response_witness_id",),
        EXPECTED_RESPONSE_WITNESS_ID,
        errors,
        "GitHub PR operator response witness source",
    )
    _require_equal(
        source_operator_response,
        ("response_record_collected",),
        False,
        errors,
        "GitHub PR operator response witness source",
    )
    for source_path, target_path in (
        (("scope", "tenant_id"), ("scope", "tenant_id")),
        (("scope", "organization_id"), ("scope", "organization_id")),
        (("scope", "project_id"), ("scope", "project_id")),
        (("scope", "repository_connection_id"), ("scope", "repository_connection_id")),
        (("scope", "repository_slug"), ("scope", "repository_slug")),
        (("scope", "task_service_id"), ("scope", "task_service_id")),
        (("response_witness_id",), ("response_command_preview_binding", "source_operator_response_witness_id")),
        (("operator_response", "approval_request_id"), ("response_command_preview_binding", "approval_request_id")),
        (("requested_evidence_ref",), ("response_command_preview_binding", "operator_response_evidence_ref")),
    ):
        _require_equal(payload, target_path, _get_nested(source_operator_response, source_path), errors, label)


def _validate_source_command_approval_binding(
    payload: Mapping[str, Any],
    source_command_approval_binding: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not source_command_approval_binding:
        return
    _require_equal(
        source_command_approval_binding,
        ("binding_id",),
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_ID,
        errors,
        "GitHub PR command-preview approval binding source",
    )
    _require_equal(
        source_command_approval_binding,
        ("approval_command_preview_binding", "operator_response_collected"),
        False,
        errors,
        "GitHub PR command-preview approval binding source",
    )
    for source_path, target_path in (
        (("binding_id",), ("response_command_preview_binding", "source_operator_approval_request_command_preview_binding_id")),
        (("approval_command_preview_binding", "redacted_command_preview"), ("response_command_preview_binding", "redacted_command_preview")),
        (("approval_command_preview_binding", "argument_vector_template"), ("response_command_preview_binding", "argument_vector_template")),
        (("approval_command_preview_binding", "placeholder_refs"), ("response_command_preview_binding", "placeholder_refs")),
    ):
        _require_equal(payload, target_path, _get_nested(source_command_approval_binding, source_path), errors, label)


def _validate_command_preview_approval_request_evidence(
    payload: Mapping[str, Any],
    source_command_approval_binding: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    evidence = _get_nested(payload, ("command_preview_approval_request_evidence",))
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: command_preview_approval_request_evidence must be an object")
        return
    if not source_command_approval_binding:
        return
    _require_equal(
        payload,
        ("command_preview_approval_request_evidence", "source_operator_approval_request_command_preview_binding_ref"),
        EXPECTED_SOURCE_COMMAND_APPROVAL_BINDING_REF,
        errors,
        label,
    )
    for evidence_key, source_path in COMMAND_PREVIEW_APPROVAL_REQUEST_EVIDENCE_BINDINGS:
        _require_equal(
            payload,
            ("command_preview_approval_request_evidence", evidence_key),
            _get_nested(source_command_approval_binding, source_path),
            errors,
            label,
        )
    _require_equal(
        payload,
        ("command_preview_approval_request_evidence", "source_redacted_command_preview"),
        _get_nested(payload, ("response_command_preview_binding", "redacted_command_preview")),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_approval_request_evidence", "operator_response_consumes_approval_request_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_approval_request_evidence", "operator_response_remains_uncollected"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_approval_request_evidence", "command_preview_response_remains_preview_only"),
        True,
        errors,
        label,
    )


def _validate_command_shape(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _require_equal(
        payload,
        ("response_command_preview_binding", "redacted_command_preview"),
        EXPECTED_COMMAND_PREVIEW,
        errors,
        label,
    )
    observed_vector = _get_nested(payload, ("response_command_preview_binding", "argument_vector_template"))
    if tuple(observed_vector) != EXPECTED_ARGUMENT_VECTOR:
        errors.append(
            f"{label}: response_command_preview_binding.argument_vector_template expected "
            f"{EXPECTED_ARGUMENT_VECTOR!r}, observed {observed_vector!r}"
        )
    preview_text = _get_nested(payload, ("response_command_preview_binding", "redacted_command_preview"))
    if isinstance(preview_text, str) and "<" not in preview_text:
        errors.append(f"{label}: response_command_preview_binding.redacted_command_preview must retain placeholders")


def _validate_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, required_refs in (
        (("response_command_preview_binding", "placeholder_refs"), REQUIRED_PLACEHOLDER_REFS),
        (("response_command_preview_binding", "required_before_execution_refs"), REQUIRED_BEFORE_EXECUTION_REFS),
        (("response_command_preview_binding", "blocked_reason_refs"), REQUIRED_BLOCKERS),
    ):
        for required_ref in required_refs:
            _require_contains(payload, path, required_ref, errors, label)
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    next_action = _get_nested(payload, ("next_action",))
    if isinstance(next_action, str):
        for phrase in ("branch-write authority", "command-preview-bound", "PR command execution", "terminal closure"):
            if phrase not in next_action:
                errors.append(f"{label}: next_action missing phrase {phrase!r}")


def _validate_remaining_witnesses(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    observed_witnesses = _get_nested(payload, ("remaining_witnesses",))
    if not isinstance(observed_witnesses, list):
        errors.append(f"{label}: remaining_witnesses must be a list")
        return
    observed_kinds = tuple(
        witness.get("witness_kind") for witness in observed_witnesses if isinstance(witness, Mapping)
    )
    if observed_kinds != EXPECTED_REMAINING_WITNESSES:
        errors.append(f"{label}: remaining_witnesses must preserve canonical witness order")


def _validate_flags_and_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        dotted_path = ".".join(path)
        key = path[-1]
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


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def build_mutated_operator_response_command_preview_binding(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--source-operator-response-schema", type=Path, default=DEFAULT_OPERATOR_RESPONSE_SCHEMA)
    parser.add_argument(
        "--source-operator-response-example",
        type=Path,
        action="append",
        dest="source_operator_response_examples",
    )
    parser.add_argument(
        "--source-command-approval-binding-schema",
        type=Path,
        default=DEFAULT_COMMAND_APPROVAL_BINDING_SCHEMA,
    )
    parser.add_argument(
        "--source-command-approval-binding-example",
        type=Path,
        action="append",
        dest="source_command_approval_binding_examples",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_operator_response_command_preview_binding(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_operator_response_schema_path=args.source_operator_response_schema,
        source_operator_response_example_paths=(
            tuple(args.source_operator_response_examples)
            if args.source_operator_response_examples
            else DEFAULT_OPERATOR_RESPONSE_EXAMPLES
        ),
        source_command_approval_binding_schema_path=args.source_command_approval_binding_schema,
        source_command_approval_binding_example_paths=(
            tuple(args.source_command_approval_binding_examples)
            if args.source_command_approval_binding_examples
            else DEFAULT_COMMAND_APPROVAL_BINDING_EXAMPLES
        ),
    )
    write_github_pr_operator_response_command_preview_binding_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR OPERATOR RESPONSE COMMAND PREVIEW BINDING VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
