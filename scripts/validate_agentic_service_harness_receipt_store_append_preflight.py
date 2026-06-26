#!/usr/bin/env python3
"""Validate Agentic Service Harness receipt-store append preflight.

Purpose: prove harness receipt-store append authority remains blocked until
operator approval, append audit, writer registration, write path, idempotency,
durability replay, rollback, and redaction evidence are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_receipt_store_append_preflight.schema.json,
examples/agentic_service_harness_receipt_store_append_preflight.foundation.json,
scripts.validate_agentic_service_harness_task_record_write_uao_admission_preflight,
scripts.validate_universal_symbol_receipt_store_write_path_witness,
scripts.validate_universal_symbol_receipt_store_authority_witness, and
scripts.validate_schemas.
Invariants:
  - Source task-record UAO, write-path, and authority witnesses pass first.
  - Receipt-store append is not admitted or performed.
  - Runtime state writes, mutation routes, raw payloads, secrets, and terminal
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

from scripts.validate_agentic_service_harness_task_record_write_uao_admission_preflight import (  # noqa: E402
    validate_agentic_service_harness_task_record_write_uao_admission_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402
from scripts.validate_universal_symbol_receipt_store_authority_witness import (  # noqa: E402
    validate_universal_symbol_receipt_store_authority_witness,
)
from scripts.validate_universal_symbol_receipt_store_write_path_witness import (  # noqa: E402
    validate_universal_symbol_receipt_store_write_path_witness,
)


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_receipt_store_append_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_receipt_store_append_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_receipt_store_append_preflight_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_receipt_store_append_preflight"
EXPECTED_ROUTE_REF = "route://harness/receipts/append/not-admitted"
EXPECTED_DECISION = "BLOCKED_PENDING_APPEND_AUTHORITY_AND_AUDIT"
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_task_record_write_uao_admission_preflight.foundation.json",
    "examples/agentic_service_harness_receipt_projection.foundation.json",
    "examples/agentic_service_harness_receipt_evidence_read_models.foundation.json",
    "examples/universal_symbol_receipt_store_write_path_witness.foundation.json",
    "examples/universal_symbol_receipt_store_authority_witness.foundation.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_APPEND_REFS = (
    "approval://operator/harness-receipt-store-append",
    "witness://universal-symbol/receipt-append-audit",
    "authority://universal-symbol/receipt-store-writer",
    "authority://universal-symbol/receipt-store-write-path",
    "proof://universal-symbol/receipt-store-idempotency",
    "proof://universal-symbol/receipt-store-durability-replay",
    "recovery://universal-symbol/receipt-store-authority",
    "evidence://harness-receipt-redaction",
)
REQUIRED_BLOCKERS = (
    "blocked://receipt-store-append/operator-approval-missing",
    "blocked://receipt-store-append/append-audit-missing",
    "blocked://receipt-store-append/writer-registration-missing",
    "blocked://receipt-store-append/write-path-not-registered",
    "blocked://receipt-store-append/idempotency-missing",
    "blocked://receipt-store-append/durability-replay-missing",
    "blocked://receipt-store-append/rollback-missing",
    "blocked://receipt-store-append/redaction-missing",
    "blocked://runtime-state-write/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_NEXT_EVIDENCE = (
    "evidence://executed-test-receipt-admission",
    "approval://receipt-store-append/operator-decision",
    "witness://harness-receipt-store-append-audit",
)
REQUIRED_FALSE_FLAGS = (
    "receipt_store_append_admitted",
    "receipt_store_appended",
    "runtime_state_write_enabled",
    "raw_payload_stored",
    "secret_values_serialized",
    "operator_approval_collected",
    "append_audit_witness_valid",
    "writer_registration_valid",
    "write_path_registered",
    "tenant_scope_valid",
    "idempotency_key_valid",
    "durability_replay_valid",
    "rollback_evidence_collected",
    "redaction_evidence_collected",
    "append_result_claimed",
    "receipt_store_append_enabled",
    "receipt_store_append_performed",
    "receipt_store_write_path_registered",
    "task_record_write_enabled",
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
    "task_record_write_uao_valid",
    "universal_write_path_witness_valid",
    "universal_authority_witness_valid",
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
class ReceiptStoreAppendPreflightValidation:
    """Validation report for harness receipt-store append preflight."""

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


def validate_agentic_service_harness_receipt_store_append_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> ReceiptStoreAppendPreflightValidation:
    """Validate harness receipt-store append preflight examples."""

    errors: list[str] = []
    source_errors = _validate_sources()
    errors.extend(source_errors)
    schema = _load_json_object(schema_path, "receipt-store append schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"receipt-store append example {_path_label(example_path)}",
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

    return ReceiptStoreAppendPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
    )


def write_receipt_store_append_preflight_validation(
    validation: ReceiptStoreAppendPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic harness receipt-store append validation report."""

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
            "task_record_write_uao_admission_preflight",
            validate_agentic_service_harness_task_record_write_uao_admission_preflight,
        ),
        (
            "universal_symbol_receipt_store_write_path_witness",
            validate_universal_symbol_receipt_store_write_path_witness,
        ),
        (
            "universal_symbol_receipt_store_authority_witness",
            validate_universal_symbol_receipt_store_authority_witness,
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
    append = _mapping(payload.get("append_admission"))
    if scope.get("repository_slug") != "tamirat-wubie/mullu-control-plane":
        errors.append(f"{label}: scope.repository_slug must bind the repository")
    if append.get("requested_action") != "admit_harness_receipt_store_append":
        errors.append(f"{label}: append_admission.requested_action is invalid")
    if append.get("requested_route_ref") != EXPECTED_ROUTE_REF:
        errors.append(f"{label}: append_admission.requested_route_ref must remain not-admitted")
    if append.get("append_decision") != EXPECTED_DECISION:
        errors.append(f"{label}: append_admission.append_decision must be {EXPECTED_DECISION}")


def _validate_ref_sets(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    append = _mapping(payload.get("append_admission"))
    _require_refs(
        append.get("required_before_append_refs"),
        REQUIRED_BEFORE_APPEND_REFS,
        f"{label}: append_admission.required_before_append_refs",
        errors,
    )
    _require_refs(
        append.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        f"{label}: append_admission.blocked_reason_refs",
        errors,
    )
    _require_refs(
        append.get("next_required_evidence_refs"),
        REQUIRED_NEXT_EVIDENCE,
        f"{label}: append_admission.next_required_evidence_refs",
        errors,
    )


def _validate_receipt_contract(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    contract = _mapping(payload.get("receipt_contract"))
    allowed = contract.get("allowed_metadata_refs")
    forbidden = contract.get("forbidden_inline_fields")
    if not isinstance(allowed, list) or len(allowed) < 5:
        errors.append(f"{label}: receipt_contract.allowed_metadata_refs incomplete")
    if not isinstance(forbidden, list) or len(forbidden) < 5:
        errors.append(f"{label}: receipt_contract.forbidden_inline_fields incomplete")
    if contract.get("stored_receipt_ref") != "receipt-store://not-appended":
        errors.append(f"{label}: receipt_contract.stored_receipt_ref must remain not-appended")


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
        "executed test receipt admission preflight",
        "receipt-store append",
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
    """Parse harness receipt-store append preflight validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate the harness receipt-store append preflight contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", action="append", type=Path, dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print JSON validation output.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on validation failure.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run harness receipt-store append preflight validation."""

    args = parse_args(argv)
    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_receipt_store_append_preflight(
        schema_path=args.schema,
        example_paths=example_paths,
    )
    write_receipt_store_append_preflight_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS RECEIPT STORE APPEND PREFLIGHT VALID")
    else:
        print("AGENTIC SERVICE HARNESS RECEIPT STORE APPEND PREFLIGHT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
