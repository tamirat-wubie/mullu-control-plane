#!/usr/bin/env python3
"""Validate GitHub PR terminal closure certificate read model.

Purpose: prove the minted GitHub PR terminal closure certificate is projected
for operator inspection without creating a new terminal closure or authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_pr_terminal_closure_certificate_read_model.schema.json,
examples/agentic_service_harness_github_pr_terminal_closure_certificate_read_model.foundation.json,
scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting,
and scripts.validate_schemas.
Invariants:
  - The read model is read-only and projection-only.
  - The read model certificate summary matches the source minted certificate.
  - The read model grants no repository mutation, connector, deployment,
    receipt-store append, secret, destructive, or new terminal-closure authority.
  - Evidence is reference-only; no mutation route or credential-like value is serialized.
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

from scripts.validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_MINTING_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_MINTING_SCHEMA,
    EXPECTED_CERTIFICATE_ID,
    EXPECTED_DECISION_VALUE,
    EXPECTED_EFFECT_RECONCILIATION_ID,
    EXPECTED_EXECUTION_ID,
    EXPECTED_VERIFICATION_RESULT_ID,
    REQUIRED_EVIDENCE_REFS,
    validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_read_model.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_read_model.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_github_pr_terminal_closure_certificate_read_model_validation.json"
)
EXPECTED_READ_MODEL_ID = "agentic-service-harness-github-pr-terminal-closure-certificate-read-model"
EXPECTED_SOURCE_MINTING_REF = (
    "examples/agentic_service_harness_github_pr_terminal_closure_certificate_minting.foundation.json"
)
EXPECTED_COMMAND_ID = "github-pr-terminal-closure-chain"
EXPECTED_TERMINAL_SCOPE = "github_pr_terminal_closure_proof_thread_only"
ACTUAL_DIFF_CERTIFICATE_MINTING_EVIDENCE_BINDINGS = (
    ("source_minting_id", ("minting_id",)),
    ("source_minting_ref", None),
    ("source_minted_at", ("minted_at",)),
    ("source_certificate_id", ("terminal_closure_certificate", "certificate_id")),
    ("source_decision_value_record_ref", ("source_decision_value_record_ref",)),
    ("source_certificate_candidate_ref", ("source_certificate_candidate_ref",)),
    ("source_live_evidence_ref", ("source_live_evidence_ref",)),
    ("source_decision_value_record_id", ("actual_diff_decision_value_record_evidence", "source_decision_value_record_id")),
    ("operator_decision_ref", ("terminal_closure_certificate", "response_closure_ref")),
    ("decision_value", ("operator_decision_value",)),
    ("operator_decision_gate_satisfied", ("operator_decision_gate_satisfied",)),
    ("terminal_closure_certificate_minted", ("terminal_closure_certificate_minted",)),
    ("terminal_closure_authorized", ("terminal_closure_authorized",)),
    ("terminal_closure", ("terminal_closure",)),
    ("authority_scope_kind", ("authority_scope", "authority_scope_kind")),
    ("terminal_certificate_minting_authority_ref", ("authority_scope", "terminal_certificate_minting_authority_ref")),
    (
        "requires_actual_diff_decision_value_record_evidence",
        ("actual_diff_decision_value_record_evidence", "requires_actual_diff_decision_value_record_evidence"),
    ),
    (
        "actual_diff_terminal_closure_certificate_witness_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_terminal_closure_certificate_witness_ref"),
    ),
    (
        "actual_diff_effect_reconciliation_witness_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_effect_reconciliation_witness_ref"),
    ),
    (
        "actual_diff_ci_gate_before_ready_for_review_witness_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_ci_gate_before_ready_for_review_witness_ref"),
    ),
    (
        "actual_diff_repository_effect_rollback_plan_witness_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_repository_effect_rollback_plan_witness_ref"),
    ),
    (
        "actual_diff_uao_admission_witness_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_uao_admission_witness_ref"),
    ),
    (
        "actual_diff_branch_write_binding_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_branch_write_binding_ref"),
    ),
    (
        "actual_diff_operator_response_witness_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_operator_response_witness_ref"),
    ),
    (
        "actual_diff_approval_request_binding_ref",
        ("actual_diff_decision_value_record_evidence", "actual_diff_approval_request_binding_ref"),
    ),
    ("actual_non_empty_diff_receipt_ref", ("actual_diff_decision_value_record_evidence", "actual_non_empty_diff_receipt_ref")),
    ("changed_file_refs", ("actual_diff_decision_value_record_evidence", "changed_file_refs")),
    ("diff_refs", ("actual_diff_decision_value_record_evidence", "diff_refs")),
    ("redacted_diff_bundle_ref", ("actual_diff_decision_value_record_evidence", "redacted_diff_bundle_ref")),
    ("redacted_output_ref", ("actual_diff_decision_value_record_evidence", "redacted_output_ref")),
    ("effect_reconciliation_match", ("evidence_bindings", "effect_reconciliation_match")),
    ("forbidden_effects_checked", ("evidence_bindings", "forbidden_effects_checked")),
    ("effect_reconciliation_collected", ("actual_diff_decision_value_record_evidence", "effect_reconciliation_collected")),
    ("evidence_refs", ("terminal_closure_certificate", "evidence_refs")),
    ("graph_refs", ("terminal_closure_certificate", "graph_refs")),
)
REQUIRED_SOURCE_REFS = (
    "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_read_model.schema.json",
    "schemas/agentic_service_harness_github_pr_terminal_closure_certificate_minting.schema.json",
    "examples/agentic_service_harness_github_pr_terminal_closure_certificate_minting.foundation.json",
    "schemas/terminal_closure_certificate.schema.json",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "projection_only",
    "terminal_certificate_authority_projected",
    "terminal_closure_projected",
    "terminal_certificate_minted",
    "effect_reconciliation_match",
    "forbidden_effects_checked",
    "read_model_is_not_terminal_closure",
    "required_for_closure",
    "requires_actual_diff_certificate_minting_evidence",
    "requires_actual_diff_decision_value_record_evidence",
    "operator_decision_gate_satisfied",
    "terminal_closure_certificate_minted",
    "terminal_closure_authorized",
    "terminal_closure",
    "effect_reconciliation_collected",
)
REQUIRED_FALSE_FLAGS = (
    "new_terminal_closure_authority_granted",
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
    "new_terminal_closure_enabled",
    "repository_written_by_read_model",
    "connector_called_by_read_model",
    "mutation_route_admitted_by_read_model",
    "receipt_store_appended_by_read_model",
    "secret_values_serialized_by_read_model",
    "terminal_certificate_minted_by_read_model",
    "contains_secret_values",
    "inline_evidence_payloads_allowed",
)
REQUIRED_BLOCKED_AUTHORITY_REFS = (
    "blocked://repository-write/not-granted-by-certificate-read-model",
    "blocked://connector-call/not-granted-by-certificate-read-model",
    "blocked://deployment/not-granted-by-certificate-read-model",
    "blocked://receipt-store-append/not-granted-by-certificate-read-model",
    "blocked://secret-mutation/not-granted-by-certificate-read-model",
    "blocked://destructive-operation/not-granted-by-certificate-read-model",
    "blocked://new-terminal-closure/not-granted-by-read-model",
)
ALLOWED_SECRET_KEYS = {
    "contains_secret_values",
    "secret_authority_granted",
    "secret_mutation_enabled",
    "secret_values_serialized_by_read_model",
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
class GitHubPrTerminalClosureCertificateReadModelValidation:
    """Validation report for the GitHub PR terminal certificate read model."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    read_model_id: str
    source_minting_ref: str
    source_certificate_id: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_minting_schema_path: Path = DEFAULT_SOURCE_MINTING_SCHEMA,
    source_minting_example_paths: Sequence[Path] = DEFAULT_SOURCE_MINTING_EXAMPLES,
) -> GitHubPrTerminalClosureCertificateReadModelValidation:
    """Validate read-only GitHub PR terminal closure certificate projections."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "GitHub PR terminal closure certificate read-model schema", errors)
    source_validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_minting(
        schema_path=source_minting_schema_path,
        example_paths=source_minting_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source minting: {error}" for error in source_validation.errors)
    source_minting = _load_json_object(
        source_minting_example_paths[0],
        "GitHub PR terminal closure certificate minting source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub PR terminal closure certificate read-model {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example)
            )
        _validate_read_model_semantics(example, source_minting, errors, _path_label(example_path))
    return GitHubPrTerminalClosureCertificateReadModelValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        read_model_id=EXPECTED_READ_MODEL_ID,
        source_minting_ref=EXPECTED_SOURCE_MINTING_REF,
        source_certificate_id=EXPECTED_CERTIFICATE_ID,
    )


def write_github_pr_terminal_closure_certificate_read_model_validation(
    validation: GitHubPrTerminalClosureCertificateReadModelValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic read-model validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_read_model_semantics(
    payload: Mapping[str, Any],
    source_minting: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_equal(payload, ("read_model_id",), EXPECTED_READ_MODEL_ID, errors, label)
    _require_equal(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _require_equal(payload, ("source_minting_ref",), EXPECTED_SOURCE_MINTING_REF, errors, label)
    _require_equal(payload, ("source_certificate_id",), EXPECTED_CERTIFICATE_ID, errors, label)
    _require_equal(payload, ("certificate_summary", "certificate_id"), EXPECTED_CERTIFICATE_ID, errors, label)
    _require_equal(payload, ("certificate_summary", "command_id"), EXPECTED_COMMAND_ID, errors, label)
    _require_equal(payload, ("certificate_summary", "execution_id"), EXPECTED_EXECUTION_ID, errors, label)
    _require_equal(payload, ("certificate_summary", "disposition"), "committed", errors, label)
    _require_equal(
        payload,
        ("certificate_summary", "verification_result_id"),
        EXPECTED_VERIFICATION_RESULT_ID,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("certificate_summary", "effect_reconciliation_id"),
        EXPECTED_EFFECT_RECONCILIATION_ID,
        errors,
        label,
    )
    _require_equal(payload, ("certificate_summary", "operator_decision_value"), EXPECTED_DECISION_VALUE, errors, label)
    _require_equal(payload, ("certificate_summary", "terminal_scope"), EXPECTED_TERMINAL_SCOPE, errors, label)
    _require_equal(payload, ("projection_scope", "source_terminal_scope"), EXPECTED_TERMINAL_SCOPE, errors, label)
    _require_equal(payload, ("operator_view", "state"), "closed_for_github_pr_proof_thread", errors, label)
    _require_equal(
        payload,
        ("operator_view", "risk_posture"),
        "terminal_certificate_visible_repository_authority_denied",
        errors,
        label,
    )
    _require_equal(payload, ("operator_view", "redaction_policy"), "reference_only_no_raw_payloads", errors, label)
    _require_equal(payload, ("effect_boundary", "network_policy"), "none", errors, label)
    _validate_source_refs(payload, errors, label)
    _validate_source_minting_alignment(payload, source_minting, errors, label)
    _validate_blocked_authority_refs(payload, errors, label)
    _validate_flags_and_surface(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_refs: {', '.join(missing)}")


def _validate_source_minting_alignment(
    payload: Mapping[str, Any],
    source_minting: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not source_minting:
        return
    source_certificate = source_minting.get("terminal_closure_certificate")
    if not isinstance(source_certificate, Mapping):
        errors.append("source_minting: terminal_closure_certificate must be an object")
        return
    for source_path, target_path in (
        (("scope", "tenant_id"), ("projection_scope", "tenant_id")),
        (("scope", "organization_id"), ("projection_scope", "organization_id")),
        (("scope", "project_id"), ("projection_scope", "project_id")),
        (("scope", "repository_connection_id"), ("projection_scope", "repository_connection_id")),
        (("scope", "repository_slug"), ("projection_scope", "repository_slug")),
        (("scope", "task_service_id"), ("projection_scope", "task_service_id")),
        (("terminal_closure_certificate", "closed_at"), ("certificate_summary", "closed_at")),
        (("terminal_closure_certificate", "graph_refs"), ("certificate_summary", "graph_refs")),
        (("terminal_closure_certificate", "evidence_refs"), ("certificate_summary", "evidence_refs")),
        (("evidence_bindings", "effect_reconciliation_match"), ("certificate_summary", "effect_reconciliation_match")),
        (("evidence_bindings", "forbidden_effects_checked"), ("certificate_summary", "forbidden_effects_checked")),
    ):
        _require_equal(payload, target_path, _get_nested(source_minting, source_path), errors, label)
    if source_minting.get("operator_decision_value") != EXPECTED_DECISION_VALUE:
        errors.append("source_minting: operator_decision_value must be approve_terminal_certificate")
    if source_minting.get("terminal_closure_certificate_minted") is not True:
        errors.append("source_minting: terminal_closure_certificate_minted must be true")
    _validate_actual_diff_certificate_minting_evidence(payload, source_minting, errors, label)
    evidence_refs = _get_nested(payload, ("certificate_summary", "evidence_refs"))
    if not isinstance(evidence_refs, list):
        errors.append(f"{label}: certificate_summary.evidence_refs must be a list")
        return
    for required_ref in REQUIRED_EVIDENCE_REFS:
        if required_ref not in evidence_refs:
            errors.append(f"{label}: certificate_summary.evidence_refs missing {required_ref}")


def _validate_actual_diff_certificate_minting_evidence(
    payload: Mapping[str, Any],
    source_minting: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    evidence = _get_nested(payload, ("actual_diff_certificate_minting_evidence",))
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: actual_diff_certificate_minting_evidence must be an object")
        return
    _require_equal(
        payload,
        ("actual_diff_certificate_minting_evidence", "requires_actual_diff_certificate_minting_evidence"),
        True,
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_certificate_minting_evidence", "source_minting_ref"),
        _get_nested(payload, ("source_minting_ref",)),
        errors,
        label,
    )
    _require_equal(
        payload,
        ("actual_diff_certificate_minting_evidence", "source_certificate_id"),
        _get_nested(payload, ("source_certificate_id",)),
        errors,
        label,
    )
    for evidence_key, source_path in ACTUAL_DIFF_CERTIFICATE_MINTING_EVIDENCE_BINDINGS:
        expected = EXPECTED_SOURCE_MINTING_REF if source_path is None else _get_nested(source_minting, source_path)
        _require_equal(
            payload,
            ("actual_diff_certificate_minting_evidence", evidence_key),
            expected,
            errors,
            label,
        )


def _validate_blocked_authority_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    blocked_refs = _get_nested(payload, ("operator_view", "blocked_authority_refs"))
    if not isinstance(blocked_refs, list):
        errors.append(f"{label}: operator_view.blocked_authority_refs must be a list")
        return
    missing = sorted(set(REQUIRED_BLOCKED_AUTHORITY_REFS) - {str(ref) for ref in blocked_refs})
    if missing:
        errors.append(f"{label}: missing blocked_authority_refs: {', '.join(missing)}")


def _validate_flags_and_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_leaves(payload):
        if not path:
            continue
        key = path[-1]
        dotted_path = ".".join(path)
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {dotted_path} must be true")
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {dotted_path} must be false")
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: {dotted_path} contains mutation route string")
        if key not in ALLOWED_SECRET_KEYS and _contains_secret_token(key):
            errors.append(f"{label}: {dotted_path} uses forbidden secret-bearing key")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: {dotted_path} contains credential-like value")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    required_phrases = (
        "read-only certificate read model",
        "operator inspection",
        "repository mutation",
        "new terminal-closure authority",
    )
    for phrase in required_phrases:
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


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


def build_mutated_terminal_closure_certificate_read_model(**updates: Any) -> dict[str, Any]:
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
    parser.add_argument("--source-minting-schema", type=Path, default=DEFAULT_SOURCE_MINTING_SCHEMA)
    parser.add_argument("--source-minting-example", type=Path, action="append", dest="source_minting_examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation output.")
    parser.add_argument("--strict", action="store_true", help="Return nonzero when validation fails.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    validation = validate_agentic_service_harness_github_pr_terminal_closure_certificate_read_model(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
        source_minting_schema_path=args.source_minting_schema,
        source_minting_example_paths=(
            tuple(args.source_minting_examples)
            if args.source_minting_examples
            else DEFAULT_SOURCE_MINTING_EXAMPLES
        ),
    )
    write_github_pr_terminal_closure_certificate_read_model_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB PR TERMINAL CLOSURE CERTIFICATE READ MODEL VALID")
    else:
        for error in validation.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    if args.strict and not validation.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
