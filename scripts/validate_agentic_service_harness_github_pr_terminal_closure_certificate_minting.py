#!/usr/bin/env python3
"""Validate GitHub PR terminal closure certificate minting.

Purpose: prove an explicit approve_terminal_certificate operator decision can
mint exactly one terminal closure certificate for the GitHub PR proof thread.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_terminal_closure_certificate_minting.schema.json,
examples/agentic_service_harness_github_pr_terminal_closure_certificate_minting.foundation.json,
scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record,
scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate,
and scripts.validate_schemas.
Invariants:
  - The source operator decision value is exactly approve_terminal_certificate.
  - The source candidate is ready and bound to solved live effect reconciliation evidence.
  - The embedded certificate validates against the generic terminal closure certificate schema.
  - The certificate grants no repository mutation, connector, deployment, secret,
    destructive, or receipt-store append authority.
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

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_CANDIDATE_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_CANDIDATE_SCHEMA,
    validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate,
)
from scripts.validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_DECISION_RECORD_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_DECISION_RECORD_SCHEMA,
    validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_minting.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_minting.foundation.json",
)
DEFAULT_TERMINAL_CLOSURE_SCHEMA = REPO_ROOT / "schemas" / "terminal_closure_certificate.schema.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_minting_validation.json"
)
EXPECTED_MINTING_ID = "agentic-service-harness-github-pr-terminal-closure-certificate-minting"
EXPECTED_SOURCE_DECISION_VALUE_RECORD_REF = (
    "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json"
)
EXPECTED_SOURCE_CANDIDATE_REF = (
    "examples/agentic_service_harness_github_pr_terminal_closure_certificate_candidate.foundation.json"
)
EXPECTED_SOURCE_LIVE_EVIDENCE_REF = (
    "examples/agentic_service_harness_github_pr_effect_reconciliation_live_evidence.foundation.json"
)
EXPECTED_DECISION_VALUE = "approve_terminal_certificate"
EXPECTED_CERTIFICATE_ID = "terminal-closure-certificate.github-pr-chain.foundation"
EXPECTED_COMMAND_ID = "github-pr-terminal-closure-chain"
EXPECTED_EXECUTION_ID = "terminal-closure-certificate-candidate.github-pr-chain"
EXPECTED_VERIFICATION_RESULT_ID = "verification.github-pr-chain.effect-reconciliation-live-evidence"
EXPECTED_EFFECT_RECONCILIATION_ID = "effect-reconciliation.github-pr-before-terminal-closure"
EXPECTED_AUTHORITY_REF = "operator-decision://github-pr-terminal-closure/2026-06-26/approve-terminal-certificate"
REQUIRED_EVIDENCE_REFS = (
    "examples/agentic_service_harness_github_pr_effect_reconciliation_live_evidence.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_certificate_candidate.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_operator_approval_gate.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_contract.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record.foundation.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_certificate_witness.foundation.json",
)
ACTUAL_DIFF_DECISION_VALUE_RECORD_EVIDENCE_BINDINGS = (
    ("source_decision_value_record_id", ("record_id",)),
    ("source_decision_value_record_ref", None),
    ("source_request_id", ("actual_diff_decision_value_request_evidence", "source_request_id")),
    ("source_request_ref", ("source_request_ref",)),
    ("source_request_status", ("source_request_status",)),
    ("source_rejection_binding_id", ("actual_diff_decision_value_request_evidence", "source_rejection_binding_id")),
    ("source_rejection_witness_ref", ("actual_diff_decision_value_request_evidence", "source_rejection_witness_ref")),
    (
        "source_decision_contract_binding_id",
        ("actual_diff_decision_value_request_evidence", "source_decision_contract_binding_id"),
    ),
    ("source_decision_contract_ref", ("actual_diff_decision_value_request_evidence", "source_decision_contract_ref")),
    ("operator_decision_ref", ("witness_ref",)),
    ("allowed_decision_values", ("actual_diff_decision_value_request_evidence", "allowed_decision_values")),
    ("decision_value", ("decision_value",)),
    ("operator_decision_gate_satisfied", ("operator_decision_gate_satisfied",)),
    ("certificate_minting_decision", ("certificate_minting_decision",)),
    ("operator_decision_value_collected", ("operator_decision_value_collected",)),
    ("explicit_operator_decision_value_present", ("explicit_operator_decision_value_present",)),
    (
        "source_approval_gate_binding_id",
        ("actual_diff_decision_value_request_evidence", "source_approval_gate_binding_id"),
    ),
    ("source_approval_gate_ref", ("actual_diff_decision_value_request_evidence", "source_approval_gate_ref")),
    (
        "actual_diff_terminal_closure_certificate_witness_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_terminal_closure_certificate_witness_ref"),
    ),
    (
        "actual_diff_effect_reconciliation_witness_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_effect_reconciliation_witness_ref"),
    ),
    (
        "actual_diff_ci_gate_before_ready_for_review_witness_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_ci_gate_before_ready_for_review_witness_ref"),
    ),
    (
        "actual_diff_repository_effect_rollback_plan_witness_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_repository_effect_rollback_plan_witness_ref"),
    ),
    (
        "actual_diff_uao_admission_witness_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_uao_admission_witness_ref"),
    ),
    (
        "actual_diff_branch_write_binding_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_branch_write_binding_ref"),
    ),
    (
        "actual_diff_operator_response_witness_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_operator_response_witness_ref"),
    ),
    (
        "actual_diff_approval_request_binding_ref",
        ("actual_diff_decision_value_request_evidence", "actual_diff_approval_request_binding_ref"),
    ),
    ("actual_non_empty_diff_receipt_ref", ("actual_diff_decision_value_request_evidence", "actual_non_empty_diff_receipt_ref")),
    ("changed_file_refs", ("actual_diff_decision_value_request_evidence", "changed_file_refs")),
    ("diff_refs", ("actual_diff_decision_value_request_evidence", "diff_refs")),
    ("redacted_diff_bundle_ref", ("actual_diff_decision_value_request_evidence", "redacted_diff_bundle_ref")),
    ("redacted_output_ref", ("actual_diff_decision_value_request_evidence", "redacted_output_ref")),
    ("effect_reconciliation_collected", ("actual_diff_decision_value_request_evidence", "effect_reconciliation_collected")),
    ("binds_branch_state", ("actual_diff_decision_value_request_evidence", "binds_branch_state")),
    ("binds_pull_request_state", ("actual_diff_decision_value_request_evidence", "binds_pull_request_state")),
    ("binds_check_state", ("actual_diff_decision_value_request_evidence", "binds_check_state")),
    ("binds_merge_state", ("actual_diff_decision_value_request_evidence", "binds_merge_state")),
    ("binds_branch_deletion_state", ("actual_diff_decision_value_request_evidence", "binds_branch_deletion_state")),
)
COMMAND_PREVIEW_DECISION_VALUE_RECORD_EVIDENCE_BINDINGS = (
    ("source_decision_value_record_id", ("record_id",)),
    ("source_decision_value_record_ref", None),
    ("source_request_id", ("command_preview_decision_value_request_evidence", "source_request_id")),
    ("source_request_ref", ("source_request_ref",)),
    ("source_request_status", ("source_request_status",)),
    ("source_rejection_binding_id", ("command_preview_decision_value_request_evidence", "source_rejection_binding_id")),
    ("source_rejection_witness_ref", ("command_preview_decision_value_request_evidence", "source_rejection_witness_ref")),
    (
        "source_decision_contract_binding_id",
        ("command_preview_decision_value_request_evidence", "source_decision_contract_binding_id"),
    ),
    ("source_decision_contract_ref", ("command_preview_decision_value_request_evidence", "source_decision_contract_ref")),
    ("operator_decision_ref", ("witness_ref",)),
    ("allowed_decision_values", ("command_preview_decision_value_request_evidence", "allowed_decision_values")),
    ("decision_value", ("decision_value",)),
    ("operator_decision_gate_satisfied", ("operator_decision_gate_satisfied",)),
    ("certificate_minting_decision", ("certificate_minting_decision",)),
    ("operator_decision_value_collected", ("operator_decision_value_collected",)),
    ("explicit_operator_decision_value_present", ("explicit_operator_decision_value_present",)),
    (
        "source_approval_gate_binding_id",
        ("command_preview_decision_value_request_evidence", "source_approval_gate_binding_id"),
    ),
    ("source_approval_gate_ref", ("command_preview_decision_value_request_evidence", "source_approval_gate_ref")),
    (
        "command_preview_terminal_closure_certificate_witness_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_terminal_closure_certificate_witness_ref"),
    ),
    (
        "command_preview_effect_reconciliation_witness_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_effect_reconciliation_witness_ref"),
    ),
    (
        "command_preview_ci_gate_before_ready_for_review_witness_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_ci_gate_before_ready_for_review_witness_ref"),
    ),
    (
        "command_preview_repository_effect_rollback_plan_witness_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_repository_effect_rollback_plan_witness_ref"),
    ),
    (
        "command_preview_uao_admission_witness_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_uao_admission_witness_ref"),
    ),
    (
        "command_preview_branch_write_binding_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_branch_write_binding_ref"),
    ),
    (
        "command_preview_operator_response_binding_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_operator_response_binding_ref"),
    ),
    (
        "command_preview_operator_response_witness_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_operator_response_witness_ref"),
    ),
    (
        "command_preview_operator_approval_request_binding_ref",
        ("command_preview_decision_value_request_evidence", "command_preview_operator_approval_request_binding_ref"),
    ),
    ("command_preview_ref", ("command_preview_decision_value_request_evidence", "command_preview_ref")),
    ("redacted_command_preview", ("command_preview_decision_value_request_evidence", "redacted_command_preview")),
    ("command_preview_bound", ("command_preview_decision_value_request_evidence", "command_preview_bound")),
)
REQUIRED_RECEIPT_REFS = {
    "github_pr_terminal_closure_certificate_minting_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_minting.schema.json"
    ),
    "terminal_closure_certificate_schema": "schemas/terminal_closure_certificate.schema.json",
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
    "github_pr_terminal_closure_operator_approval_gate_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_operator_approval_gate.schema.json"
    ),
    "github_pr_terminal_closure_certificate_candidate_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_candidate.schema.json"
    ),
    "github_pr_effect_reconciliation_live_evidence_schema": (
        "schemas/agentic_service_harness_github_pr_effect_reconciliation_live_evidence.schema.json"
    ),
    "github_pr_terminal_closure_certificate_witness_schema": (
        "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_witness.schema.json"
    ),
}
REQUIRED_TRUE_FLAGS = (
    "operator_decision_gate_satisfied",
    "terminal_closure_certificate_minted",
    "terminal_closure_authorized",
    "terminal_closure",
    "terminal_certificate_minting_authorized",
    "terminal_certificate_minted_by_record",
    "terminal_proof",
    "source_live_evidence_solved",
    "certificate_candidate_ready",
    "operator_decision_value_recorded",
    "generic_continuation_rejected",
    "effect_reconciliation_match",
    "forbidden_effects_checked",
    "read_only_inputs",
    "requires_command_preview_decision_value_record_evidence",
    "requires_command_preview_decision_value_request_evidence",
    "requires_actual_diff_decision_value_record_evidence",
    "requires_actual_diff_decision_value_request_evidence",
    "operator_decision_value_collected",
    "explicit_operator_decision_value_present",
    "effect_reconciliation_collected",
    "binds_branch_state",
    "binds_pull_request_state",
    "binds_check_state",
    "binds_merge_state",
    "binds_branch_deletion_state",
)
REQUIRED_FALSE_FLAGS = (
    "repository_mutation_authority_granted",
    "connector_authority_granted",
    "deployment_authority_granted",
    "secret_authority_granted",
    "destructive_authority_granted",
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
    "repository_written_by_minting_runtime",
    "connector_called_by_minting_runtime",
    "mutation_route_admitted_by_minting_runtime",
    "receipt_store_appended_by_minting_runtime",
    "secret_values_serialized_by_minting_runtime",
)
ALLOWED_SECRET_KEYS = {
    "secret_authority_granted",
    "secret_mutation_enabled",
    "secret_values_serialized_by_minting_runtime",
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
class GitHubPrTerminalClosureCertificateMintingValidation:
    """Validation report for the terminal closure certificate minting record."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    certificate_id: str
    source_decision_value_record_ref: str
    source_certificate_candidate_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    terminal_closure_schema_path: Path = DEFAULT_TERMINAL_CLOSURE_SCHEMA,
    source_decision_record_schema_path: Path = DEFAULT_SOURCE_DECISION_RECORD_SCHEMA,
    source_decision_record_example_paths: Sequence[Path] = DEFAULT_SOURCE_DECISION_RECORD_EXAMPLES,
    source_candidate_schema_path: Path = DEFAULT_SOURCE_CANDIDATE_SCHEMA,
    source_candidate_example_paths: Sequence[Path] = DEFAULT_SOURCE_CANDIDATE_EXAMPLES,
) -> GitHubPrTerminalClosureCertificateMintingValidation:
    """Validate GitHub PR terminal closure certificate minting examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR terminal closure certificate minting schema", errors)
    terminal_closure_schema = _load_json_object(
        terminal_closure_schema_path,
        "terminal closure certificate schema",
        errors,
    )
    decision_validation = validate_agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record(
        schema_path=source_decision_record_schema_path,
        example_paths=source_decision_record_example_paths,
    )
    if not decision_validation.ok:
        errors.extend(f"source decision value record: {error}" for error in decision_validation.errors)
    candidate_validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_candidate(
        schema_path=source_candidate_schema_path,
        example_paths=source_candidate_example_paths,
    )
    if not candidate_validation.ok:
        errors.extend(f"source certificate candidate: {error}" for error in candidate_validation.errors)
    source_decision_record = _load_json_object(
        source_decision_record_example_paths[0],
        "GitHub PR terminal closure decision value record source",
        errors,
    )
    source_candidate = _load_json_object(
        source_candidate_example_paths[0],
        "GitHub PR terminal closure certificate candidate source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR terminal closure certificate minting {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        certificate = example.get("terminal_closure_certificate")
        if terminal_closure_schema and isinstance(certificate, dict):
            errors.extend(
                f"{_path_label(example_path)} terminal_closure_certificate: {error}"
                for error in _validate_schema_instance(terminal_closure_schema, certificate)
            )
        _validate_certificate_minting_semantics(
            example,
            source_decision_record,
            source_candidate,
            errors,
            _path_label(example_path),
        )
    return GitHubPrTerminalClosureCertificateMintingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        certificate_id=EXPECTED_CERTIFICATE_ID,
        source_decision_value_record_ref=EXPECTED_SOURCE_DECISION_VALUE_RECORD_REF,
        source_certificate_candidate_ref=EXPECTED_SOURCE_CANDIDATE_REF,
    )


def write_github_pr_terminal_closure_certificate_minting_validation(
    validation: GitHubPrTerminalClosureCertificateMintingValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic terminal closure certificate minting validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_certificate_minting_semantics(
    payload: Mapping[str, Any],
    source_decision_record: Mapping[str, Any],
    source_candidate: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("minting_id",), EXPECTED_MINTING_ID, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(
        payload,
        ("source_decision_value_record_ref",),
        EXPECTED_SOURCE_DECISION_VALUE_RECORD_REF,
        errors,
        label,
    )
    _require_equal(payload, ("source_certificate_candidate_ref",), EXPECTED_SOURCE_CANDIDATE_REF, errors, label)
    _require_equal(payload, ("source_live_evidence_ref",), EXPECTED_SOURCE_LIVE_EVIDENCE_REF, errors, label)
    _require_equal(payload, ("operator_decision_value",), EXPECTED_DECISION_VALUE, errors, label)
    _require_equal(payload, ("authority_scope", "terminal_certificate_minting_authority_ref"), EXPECTED_AUTHORITY_REF, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "certificate_id"), EXPECTED_CERTIFICATE_ID, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "command_id"), EXPECTED_COMMAND_ID, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "execution_id"), EXPECTED_EXECUTION_ID, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "disposition"), "committed", errors, label)
    _require_equal(
        payload,
        ("terminal_closure_certificate", "verification_result_id"),
        EXPECTED_VERIFICATION_RESULT_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("terminal_closure_certificate", "effect_reconciliation_id"),
        EXPECTED_EFFECT_RECONCILIATION_ID,
        errors,
        label,
    )
    _require_equal(payload, ("terminal_closure_certificate", "response_closure_ref"), EXPECTED_AUTHORITY_REF, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "compensation_outcome_id"), None, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "accepted_risk_id"), None, errors, label)
    _require_equal(payload, ("terminal_closure_certificate", "case_id"), None, errors, label)
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    _validate_source_bindings(payload, source_decision_record, source_candidate, errors, label)
    evidence_refs = _get_nested(payload, ("terminal_closure_certificate", "evidence_refs"))
    if not isinstance(evidence_refs, list):
        errors.append(f"{label}: terminal_closure_certificate.evidence_refs must be a list")
    else:
        for required_ref in REQUIRED_EVIDENCE_REFS:
            if required_ref not in evidence_refs:
                errors.append(f"{label}: terminal_closure_certificate.evidence_refs missing {required_ref}")
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        _require_equal(payload, ("receipt_refs", key), expected_value, errors, label)
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        dotted_path = ".".join(path)
        if path[-1] in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if path[-1] in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if path[-1] not in ALLOWED_SECRET_KEYS and _contains_secret_token(path[-1]):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


def _validate_source_bindings(
    payload: Mapping[str, Any],
    source_decision_record: Mapping[str, Any],
    source_candidate: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if source_decision_record:
        _require_equal(source_decision_record, ("decision_value",), EXPECTED_DECISION_VALUE, errors, "source_decision_record")
        _require_equal(source_decision_record, ("operator_decision_gate_satisfied",), True, errors, "source_decision_record")
        _require_equal(
            source_decision_record,
            ("certificate_minting_decision",),
            "approved_for_next_minting_step",
            errors,
            "source_decision_record",
        )
        _validate_command_preview_decision_value_record_evidence(payload, source_decision_record, errors, label)
        _validate_actual_diff_decision_value_record_evidence(payload, source_decision_record, errors, label)
        for source_path, target_path in (
            (("scope", "tenant_id"), ("scope", "tenant_id")),
            (("scope", "organization_id"), ("scope", "organization_id")),
            (("scope", "project_id"), ("scope", "project_id")),
            (("scope", "repository_connection_id"), ("scope", "repository_connection_id")),
            (("scope", "repository_slug"), ("scope", "repository_slug")),
            (("scope", "task_service_id"), ("scope", "task_service_id")),
        ):
            _require_equal(payload, target_path, _get_nested(source_decision_record, source_path), errors, label)
    if source_candidate:
        _require_equal(
            source_candidate,
            ("terminal_closure_certificate_candidate_ready",),
            True,
            errors,
            "source_candidate",
        )
        _require_equal(source_candidate, ("effect_reconciliation_collected",), True, errors, "source_candidate")
        _require_equal(
            source_candidate,
            ("certificate_candidate", "candidate_id"),
            EXPECTED_EXECUTION_ID,
            errors,
            "source_candidate",
        )
        _require_equal(
            source_candidate,
            ("certificate_candidate", "source_live_evidence_ref"),
            EXPECTED_SOURCE_LIVE_EVIDENCE_REF,
            errors,
            "source_candidate",
        )


def _validate_actual_diff_decision_value_record_evidence(
    payload: Mapping[str, Any],
    source_decision_record: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    evidence_path = ("actual_diff_decision_value_record_evidence",)
    evidence = _get_nested(payload, evidence_path)
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: actual_diff_decision_value_record_evidence must be an object")
        return

    _require_equal(
        payload,
        ("actual_diff_decision_value_record_evidence", "requires_actual_diff_decision_value_record_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_record_evidence", "requires_actual_diff_decision_value_request_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_decision_value_record_evidence", "source_decision_value_record_ref"),
        _get_nested(payload, ("source_decision_value_record_ref",)),
        errors,
        label,
    )
    for evidence_key, source_path in ACTUAL_DIFF_DECISION_VALUE_RECORD_EVIDENCE_BINDINGS:
        expected = (
            EXPECTED_SOURCE_DECISION_VALUE_RECORD_REF
            if source_path is None
            else _get_nested(source_decision_record, source_path)
        )
        _require_equal(
            payload,
            ("actual_diff_decision_value_record_evidence", evidence_key),
            expected,
            errors,
            label,
        )


def _validate_command_preview_decision_value_record_evidence(
    payload: Mapping[str, Any],
    source_decision_record: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    evidence = _get_nested(payload, ("command_preview_decision_value_record_evidence",))
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: command_preview_decision_value_record_evidence must be an object")
        return

    _require_equal(
        payload,
        ("command_preview_decision_value_record_evidence", "requires_command_preview_decision_value_record_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_record_evidence", "requires_command_preview_decision_value_request_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("command_preview_decision_value_record_evidence", "source_decision_value_record_ref"),
        _get_nested(payload, ("source_decision_value_record_ref",)),
        errors,
        label,
    )
    for evidence_key, source_path in COMMAND_PREVIEW_DECISION_VALUE_RECORD_EVIDENCE_BINDINGS:
        expected = (
            EXPECTED_SOURCE_DECISION_VALUE_RECORD_REF
            if source_path is None
            else _get_nested(source_decision_record, source_path)
        )
        _require_equal(
            payload,
            ("command_preview_decision_value_record_evidence", evidence_key),
            expected,
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


def build_mutated_terminal_closure_certificate_minting(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--terminal-closure-schema", type=Path, default=DEFAULT_TERMINAL_CLOSURE_SCHEMA)
    parser.add_argument("--source-decision-record-schema", type=Path, default=DEFAULT_SOURCE_DECISION_RECORD_SCHEMA)
    parser.add_argument("--source-decision-record-example", type=Path, action="append", dest="source_decision_record_examples")
    parser.add_argument("--source-candidate-schema", type=Path, default=DEFAULT_SOURCE_CANDIDATE_SCHEMA)
    parser.add_argument("--source-candidate-example", type=Path, action="append", dest="source_candidate_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        terminal_closure_schema_path=args.terminal_closure_schema,
        source_decision_record_schema_path=args.source_decision_record_schema,
        source_decision_record_example_paths=(
            tuple(args.source_decision_record_examples)
            if args.source_decision_record_examples
            else DEFAULT_SOURCE_DECISION_RECORD_EXAMPLES
        ),
        source_candidate_schema_path=args.source_candidate_schema,
        source_candidate_example_paths=(
            tuple(args.source_candidate_examples)
            if args.source_candidate_examples
            else DEFAULT_SOURCE_CANDIDATE_EXAMPLES
        ),
    )
    write_github_pr_terminal_closure_certificate_minting_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR TERMINAL CLOSURE CERTIFICATE MINTING VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
