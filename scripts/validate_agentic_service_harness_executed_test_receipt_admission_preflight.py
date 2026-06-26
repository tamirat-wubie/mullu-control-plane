#!/usr/bin/env python3
"""Validate Agentic Service Harness executed-test receipt admission preflight.

Purpose: prove executed-test receipt admission remains blocked until operator
approval, approved workspace, command timeout, subprocess redaction, exit-code,
output-digest, receipt-store append admission, and audit evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_executed_test_receipt_admission_preflight.schema.json,
examples/agentic_service_harness_executed_test_receipt_admission_preflight.foundation.json,
scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
scripts.validate_agentic_service_harness_receipt_store_append_preflight, and
scripts.validate_schemas.
Invariants:
  - Source dry-run plan, approved workspace, and receipt append preflight pass.
  - Executed-test receipt admission is not granted.
  - Command execution, subprocess execution, test-result claims, coverage claims,
    receipt-store append, runtime writes, raw output, secrets, mutation routes,
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
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight import (  # noqa: E402
    validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
)
from scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt import (  # noqa: E402
    validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
)
from scripts.validate_agentic_service_harness_receipt_store_append_preflight import (  # noqa: E402
    validate_agentic_service_harness_receipt_store_append_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_executed_test_receipt_admission_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_executed_test_receipt_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_executed_test_receipt_admission_preflight_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_executed_test_receipt_admission_preflight"
EXPECTED_ROUTE_REF = "route://harness/tests/executed-receipt/not-admitted"
EXPECTED_DECISION = (
    "BLOCKED_PENDING_APPROVED_WORKSPACE_COMMAND_EXECUTION_AND_RESULT_EVIDENCE"
)
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json",
    "examples/agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json",
    "examples/agentic_service_harness_receipt_store_append_preflight.foundation.json",
    "schemas/agentic_service_harness.schema.json",
    "scripts/validate_agentic_service_harness_readiness_map.py",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_EXECUTION_REFS = (
    "approval://operator/test-command-execution",
    "evidence://branch-workspace-created-with-approval",
    "evidence://workspace-path-confinement",
    "evidence://test-command-timeout-policy",
    "evidence://subprocess-output-redaction-policy",
    "evidence://test-command-exit-code",
    "evidence://test-output-redaction-digest",
    "evidence://receipt-store-append-admission",
)
REQUIRED_BLOCKERS = (
    "blocked://test-execution/operator-approval-missing",
    "blocked://test-execution/live-workspace-not-created",
    "blocked://test-execution/timeout-policy-missing",
    "blocked://test-execution/subprocess-redaction-missing",
    "blocked://test-execution/commands-not-executed",
    "blocked://test-results/exit-code-not-observed",
    "blocked://test-results/output-not-redacted",
    "blocked://receipt-store-append/not-admitted",
    "blocked://runtime-state-write/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_NEXT_EVIDENCE = (
    "evidence://non-empty-diff-receipt-admission",
    "approval://executed-test-receipt/operator-decision",
    "witness://harness-executed-test-receipt-audit",
)
REQUIRED_ALLOWED_METADATA_REFS = (
    "field://executed-test-receipt/id",
    "field://executed-test-receipt/agent_run_id",
    "field://executed-test-receipt/command_id",
    "field://executed-test-receipt/exit_code_ref",
    "field://executed-test-receipt/output_digest_ref",
    "field://executed-test-receipt/evidence_refs",
)
REQUIRED_FORBIDDEN_INLINE_FIELDS = (
    "field://executed-test-receipt/raw-secret",
    "field://executed-test-receipt/raw-stdout",
    "field://executed-test-receipt/raw-stderr",
    "field://executed-test-receipt/raw-diff",
    "field://executed-test-receipt/external-token",
)
REQUIRED_FALSE_FLAGS = (
    "test_execution_admitted",
    "commands_executed",
    "test_results_claimed",
    "executed_test_receipt_admitted",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "operator_approval_collected",
    "live_workspace_created",
    "command_timeout_policy_valid",
    "subprocess_redaction_policy_valid",
    "command_execution_performed",
    "exit_code_observed",
    "test_output_redacted",
    "coverage_claimed",
    "receipt_store_append_admitted",
    "test_result_claimed",
    "test_execution_enabled",
    "command_execution_enabled",
    "subprocess_execution_enabled",
    "test_result_claim_enabled",
    "coverage_claim_enabled",
    "receipt_store_append_performed",
    "runtime_state_write_enabled",
    "filesystem_write_enabled",
    "branch_write_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "raw_test_output_stored",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "admission_only",
    "read_only_sources",
    "dry_run_test_runner_plan_valid",
    "approved_branch_workspace_preflight_valid",
    "receipt_store_append_preflight_valid",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {"secret_values_serialized"}
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
class ExecutedTestReceiptAdmissionPreflightValidation:
    """Validation report for harness executed-test receipt admission preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_validators_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_executed_test_receipt_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> ExecutedTestReceiptAdmissionPreflightValidation:
    """Validate harness executed-test receipt admission preflight examples."""

    errors: list[str] = []
    source_errors = _validate_sources()
    errors.extend(source_errors)
    schema = _load_json_object(schema_path, "executed-test receipt admission schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"executed-test receipt admission example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_semantics(example, errors, _path_label(example_path))

    return ExecutedTestReceiptAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
    )


def write_executed_test_receipt_admission_preflight_validation(
    validation: ExecutedTestReceiptAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic executed-test receipt admission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**changes: Any) -> dict[str, Any]:
    """Return a mutated copy of the default fixture for tests."""

    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default fixture", [])
    mutated = deepcopy(payload)
    for dotted_path, value in changes.items():
        cursor: dict[str, Any] = mutated
        path_parts = dotted_path.split("__")
        for key in path_parts[:-1]:
            next_cursor = cursor[key]
            if not isinstance(next_cursor, dict):
                raise TypeError(f"cannot mutate non-object path component {key}")
            cursor = next_cursor
        cursor[path_parts[-1]] = value
    return mutated


def _validate_sources() -> list[str]:
    validators = (
        (
            "dry_run_test_runner_plan_receipt",
            validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
        ),
        (
            "approved_branch_workspace_creation_preflight",
            validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
        ),
        (
            "receipt_store_append_preflight",
            validate_agentic_service_harness_receipt_store_append_preflight,
        ),
    )
    errors: list[str] = []
    for validator_id, validator in validators:
        source_validation = validator()
        if _source_validation_ok(source_validation):
            continue
        errors.extend(
            f"source {validator_id} invalid: {error}"
            for error in _source_validation_errors(source_validation)
        )
    return errors


def _source_validation_ok(source_validation: object) -> bool:
    if isinstance(source_validation, Mapping):
        return bool(source_validation.get("ok", source_validation.get("valid", False)))
    return bool(getattr(source_validation, "ok", False))


def _source_validation_errors(source_validation: object) -> tuple[str, ...]:
    if isinstance(source_validation, Mapping):
        errors = source_validation.get("errors", ())
    else:
        errors = getattr(source_validation, "errors", ())
    if isinstance(errors, list):
        return tuple(str(error) for error in errors)
    if isinstance(errors, tuple):
        return tuple(str(error) for error in errors)
    if errors:
        return (str(errors),)
    return ("unknown source validation failure",)


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    if payload.get("report_id") != EXPECTED_REPORT_ID:
        errors.append(f"{label}: report_id must be {EXPECTED_REPORT_ID}")
    if payload.get("admission_status") != "AwaitingEvidence":
        errors.append(f"{label}: admission_status must remain AwaitingEvidence")
    _validate_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_ref_sets(payload, errors, label)
    _validate_receipt_contract(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_reference_integrity(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(payload.get("scope"))
    admission = _mapping(payload.get("test_execution_admission"))
    if scope.get("repository_slug") != "tamirat-wubie/mullu-control-plane":
        errors.append(f"{label}: scope.repository_slug must bind the repository")
    if scope.get("foundation_phase") != "foundation_executed_test_receipt_admission_preflight":
        errors.append(f"{label}: scope.foundation_phase must bind executed-test receipt admission")
    if admission.get("requested_action") != "admit_executed_test_receipt":
        errors.append(f"{label}: test_execution_admission.requested_action is invalid")
    if admission.get("requested_route_ref") != EXPECTED_ROUTE_REF:
        errors.append(
            f"{label}: test_execution_admission.requested_route_ref must remain not-admitted"
        )
    if admission.get("admission_decision") != EXPECTED_DECISION:
        errors.append(
            f"{label}: test_execution_admission.admission_decision must be {EXPECTED_DECISION}"
        )


def _validate_ref_sets(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    admission = _mapping(payload.get("test_execution_admission"))
    _require_refs(
        admission.get("required_before_execution_refs"),
        REQUIRED_BEFORE_EXECUTION_REFS,
        f"{label}: test_execution_admission.required_before_execution_refs",
        errors,
    )
    _require_refs(
        admission.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        f"{label}: test_execution_admission.blocked_reason_refs",
        errors,
    )
    _require_refs(
        admission.get("next_required_evidence_refs"),
        REQUIRED_NEXT_EVIDENCE,
        f"{label}: test_execution_admission.next_required_evidence_refs",
        errors,
    )


def _validate_receipt_contract(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    contract = _mapping(payload.get("executed_test_receipt_contract"))
    if contract.get("receipt_shape_ref") != "schema://agentic-service-harness/ExecutedTestReceipt":
        errors.append(f"{label}: executed_test_receipt_contract.receipt_shape_ref invalid")
    _require_refs(
        contract.get("allowed_metadata_refs"),
        REQUIRED_ALLOWED_METADATA_REFS,
        f"{label}: executed_test_receipt_contract.allowed_metadata_refs",
        errors,
    )
    _require_refs(
        contract.get("forbidden_inline_fields"),
        REQUIRED_FORBIDDEN_INLINE_FIELDS,
        f"{label}: executed_test_receipt_contract.forbidden_inline_fields",
        errors,
    )
    if contract.get("stored_receipt_ref") != "executed-test-receipt://not-admitted":
        errors.append(
            f"{label}: executed_test_receipt_contract.stored_receipt_ref must remain not-admitted"
        )


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _validate_secret_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        key = path[-1] if path else ""
        lowered_key = key.lower()
        if (
            any(token in lowered_key for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_no_mutation_routes(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    required_phrases = (
        "non-empty diff receipt admission preflight",
        "executed test receipt",
        "blocked",
        "terminal closure",
    )
    for phrase in required_phrases:
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


def _require_refs(
    actual: object,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(actual, list):
        errors.append(f"{label} must be a list")
        return
    actual_set = {str(item) for item in actual}
    for ref in required:
        if ref not in actual_set:
            errors.append(f"{label} missing required ref {ref}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label}: missing file {path}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON at line {exc.lineno}: {exc.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label}: expected JSON object")
        return {}
    return payload


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _walk_values(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_values(child, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, (*path, str(index)))
        return
    yield path, value


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse executed-test receipt admission preflight validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate the harness executed-test receipt admission preflight contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", action="append", type=Path, dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print JSON validation output.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on validation failure.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run executed-test receipt admission preflight validation."""

    args = parse_args(argv)
    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_executed_test_receipt_admission_preflight(
        schema_path=args.schema,
        example_paths=example_paths,
    )
    write_executed_test_receipt_admission_preflight_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS EXECUTED TEST RECEIPT ADMISSION PREFLIGHT VALID")
    else:
        print("AGENTIC SERVICE HARNESS EXECUTED TEST RECEIPT ADMISSION PREFLIGHT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
