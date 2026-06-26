#!/usr/bin/env python3
"""Validate task record write UAO admission preflight.

Purpose: prove AgentTask record writes remain blocked until operator approval,
UAO admission, tenant/project binding, idempotency, rollback, and receipt-store
write-path evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_task_record_write_uao_admission_preflight.schema.json,
examples/agentic_service_harness_task_record_write_uao_admission_preflight.foundation.json,
scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
and scripts.validate_schemas.
Invariants:
  - Source dry-run test runner plan receipt passes first.
  - Task records are not persisted.
  - Runtime state writes, mutation routes, receipt append, secrets, and terminal
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
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt import (  # noqa: E402
    validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_task_record_write_uao_admission_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_task_record_write_uao_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_task_record_write_uao_admission_preflight_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_task_record_write_uao_admission_preflight"
EXPECTED_ROUTE_REF = "route://harness/tasks/write/not-admitted"
EXPECTED_DECISION = "BLOCKED_PENDING_OPERATOR_APPROVAL_AND_RECEIPT_STORE"
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json",
    "examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json",
    "examples/agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json",
    "schemas/agentic_service_harness.schema.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_WRITE_REFS = (
    "approval://operator/task-record-write",
    "evidence://tenant-project-binding",
    "evidence://task-record-idempotency-key",
    "evidence://task-record-rollback-plan",
    "evidence://receipt-store-write-path",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-approval/not-collected",
    "blocked://task-record-write/uao-not-admitted",
    "blocked://rollback-evidence/not-collected",
    "blocked://receipt-store/write-path-not-verified",
    "blocked://runtime-state-write/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_NEXT_EVIDENCE = (
    "evidence://receipt-store-append-admission",
    "evidence://executed-test-receipt",
    "approval://task-record-write/operator-decision",
)
REQUIRED_FALSE_FLAGS = (
    "task_record_write_admitted",
    "task_record_persisted",
    "runtime_state_write_enabled",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "operator_approval_collected",
    "rollback_evidence_collected",
    "receipt_store_write_path_valid",
    "write_result_claimed",
    "task_record_write_enabled",
    "task_creation_route_enabled",
    "filesystem_write_enabled",
    "branch_write_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "admission_only",
    "read_only_sources",
    "task_creation_admission_valid",
    "dry_run_test_runner_plan_valid",
    "tenant_project_binding_valid",
    "idempotency_key_required",
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
class TaskRecordWriteUaoAdmissionPreflightValidation:
    """Validation report for task record write UAO admission preflight."""

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


def validate_agentic_service_harness_task_record_write_uao_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> TaskRecordWriteUaoAdmissionPreflightValidation:
    """Validate task record write UAO admission preflight examples."""

    errors: list[str] = []
    source_errors = _validate_sources()
    errors.extend(source_errors)
    schema = _load_json_object(schema_path, "task record write UAO schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"task record write UAO example {_path_label(example_path)}",
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

    return TaskRecordWriteUaoAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
    )


def write_task_record_write_uao_admission_preflight_validation(
    validation: TaskRecordWriteUaoAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic task record write UAO validation report."""

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
    source_validation = validate_agentic_service_harness_dry_run_test_runner_plan_receipt()
    if source_validation.ok:
        return []
    return [
        "source dry_run_test_runner_plan_receipt invalid: " + error
        for error in source_validation.errors
    ]


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    if payload.get("report_id") != EXPECTED_REPORT_ID:
        errors.append(f"{label}: report_id must be {EXPECTED_REPORT_ID}")
    _validate_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_ref_sets(payload, errors, label)
    _validate_task_record_contract(payload, errors, label)
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
    uao = _mapping(payload.get("uao_admission"))
    if scope.get("repository_slug") != "tamirat-wubie/mullu-control-plane":
        errors.append(f"{label}: scope.repository_slug must bind the repository")
    if uao.get("requested_action") != "admit_task_record_write":
        errors.append(f"{label}: uao_admission.requested_action must be admit_task_record_write")
    if uao.get("requested_route_ref") != EXPECTED_ROUTE_REF:
        errors.append(f"{label}: uao_admission.requested_route_ref must remain not-admitted")
    if uao.get("uao_decision") != EXPECTED_DECISION:
        errors.append(f"{label}: uao_admission.uao_decision must be {EXPECTED_DECISION}")


def _validate_ref_sets(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    uao = _mapping(payload.get("uao_admission"))
    _require_refs(
        uao.get("required_before_write_refs"),
        REQUIRED_BEFORE_WRITE_REFS,
        f"{label}: uao_admission.required_before_write_refs",
        errors,
    )
    _require_refs(
        uao.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        f"{label}: uao_admission.blocked_reason_refs",
        errors,
    )
    _require_refs(
        uao.get("next_required_evidence_refs"),
        REQUIRED_NEXT_EVIDENCE,
        f"{label}: uao_admission.next_required_evidence_refs",
        errors,
    )


def _validate_task_record_contract(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    contract = _mapping(payload.get("task_record_contract"))
    allowed = contract.get("allowed_field_refs")
    forbidden = contract.get("forbidden_inline_fields")
    if not isinstance(allowed, list) or len(allowed) < 5:
        errors.append(f"{label}: task_record_contract.allowed_field_refs incomplete")
    if not isinstance(forbidden, list) or len(forbidden) < 4:
        errors.append(f"{label}: task_record_contract.forbidden_inline_fields incomplete")
    if contract.get("stored_record_ref") != "task-record://not-written":
        errors.append(f"{label}: task_record_contract.stored_record_ref must remain not-written")


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
        "receipt-store append admission preflight",
        "task record writes",
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
    """Parse task record write UAO preflight validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate the task record write UAO admission preflight contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", action="append", type=Path, dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print JSON validation output.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on validation failure.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run task record write UAO admission preflight validation."""

    args = parse_args(argv)
    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_task_record_write_uao_admission_preflight(
        schema_path=args.schema,
        example_paths=example_paths,
    )
    write_task_record_write_uao_admission_preflight_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS TASK RECORD WRITE UAO ADMISSION PREFLIGHT VALID")
    else:
        print("AGENTIC SERVICE HARNESS TASK RECORD WRITE UAO ADMISSION PREFLIGHT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
