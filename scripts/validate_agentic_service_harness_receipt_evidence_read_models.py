#!/usr/bin/env python3
"""Validate Agentic Service Harness Receipt and EvidenceBundle read models.

Purpose: prove harness Receipt and EvidenceBundle projections are grouped by
AgentRun while remaining read-only, append-disabled, redacted, and non-terminal.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_receipt_evidence_read_models.schema.json,
examples/agentic_service_harness_receipt_evidence_read_models.foundation.json,
and scripts.validate_schemas.
Invariants:
  - Every receipt binds to an EvidenceBundle with the same AgentRun id.
  - Receipt store append, runtime writes, command/test execution, external
    adapters, branch/PR creation, secrets, raw diffs, and terminal closure are
    denied.
  - Append preflight stays blocked until approval, UAO, cleanup, and redaction
    evidence are explicit.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_receipt_evidence_read_models.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_receipt_evidence_read_models.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_receipt_evidence_read_models_validation.json"
)
REQUIRED_SOURCE_REFS = (
    "schemas/agentic_service_harness_read_models.schema.json",
    "examples/agentic_service_harness_read_models.foundation.json",
    "schemas/agentic_service_harness_dashboard_data_contract.schema.json",
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "schemas/agentic_service_harness_actual_file_change_summary_receipt.schema.json",
    "examples/agentic_service_harness_actual_file_change_summary_receipt.foundation.json",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_FALSE_FLAGS = (
    "append_enabled",
    "receipt_store_appended",
    "runtime_state_written",
    "secret_values_serialized",
    "terminal_closure_granted",
    "raw_diff_serialized",
    "terminal_closure",
    "approval_collected",
    "uao_admission_verified",
    "cleanup_receipt_emitted",
    "redaction_evidence_collected",
    "receipt_store_append",
    "runtime_state_write",
    "command_execution",
    "test_execution",
    "filesystem_write",
    "branch_creation",
    "pull_request_creation",
    "external_adapter_execution",
    "secret_serialization",
    "contains_secret_values",
    "inline_diff_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "projection_only",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
REQUIRED_APPEND_BLOCKERS = (
    "blocked://receipt-store-append/not-enabled",
    "blocked://approval/not-collected",
    "blocked://uao-admission/not-verified",
    "blocked://cleanup-receipt/not-emitted",
    "blocked://redaction-evidence/not-collected",
)
REQUIRED_APPEND_EVIDENCE = (
    "approval://receipt-store-append/not-collected",
    "evidence://uao-receipt-append-admission",
    "receipt://sandbox-cleanup-before-receipt-append",
    "evidence://redaction-policy-for-receipt-store-append",
)
ALLOWED_SECRET_KEYS = {
    "secret_values_serialized",
    "secret_serialization",
    "contains_secret_values",
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
class ReceiptEvidenceReadModelsValidation:
    """Schema and semantic validation report for receipt/evidence read models."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_receipt_evidence_read_models(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> ReceiptEvidenceReadModelsValidation:
    """Validate Receipt and EvidenceBundle read model examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "receipt/evidence read-model schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"receipt/evidence read-model example {_path_label(example_path)}",
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
    return ReceiptEvidenceReadModelsValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
    )


def write_receipt_evidence_read_models_validation(
    validation: ReceiptEvidenceReadModelsValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic receipt/evidence read-model validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _validate_required_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_append_preflight(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_required_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_reference_integrity(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipts = _object_list(payload.get("receipt_read_models"))
    bundles = _object_list(payload.get("evidence_bundle_read_models"))
    bundles_by_id = {str(bundle.get("bundle_id")): bundle for bundle in bundles}
    receipt_ids = {str(receipt.get("receipt_id")) for receipt in receipts}
    for receipt in receipts:
        receipt_id = str(receipt.get("receipt_id"))
        bundle_id = str(receipt.get("evidence_bundle_id"))
        bundle = bundles_by_id.get(bundle_id)
        if bundle is None:
            errors.append(f"{label}: receipt {receipt_id} references missing evidence bundle {bundle_id}")
            continue
        if receipt.get("run_id") != bundle.get("run_id"):
            errors.append(f"{label}: receipt {receipt_id} run_id must match evidence bundle {bundle_id}")
        if receipt_id not in set(bundle.get("receipt_ids", [])):
            errors.append(f"{label}: evidence bundle {bundle_id} must include receipt {receipt_id}")
    for bundle in bundles:
        for receipt_id in bundle.get("receipt_ids", []):
            if str(receipt_id) not in receipt_ids:
                errors.append(f"{label}: evidence bundle {bundle.get('bundle_id')} references missing receipt {receipt_id}")
        if not bundle.get("command_log_refs"):
            errors.append(f"{label}: evidence bundle {bundle.get('bundle_id')} must include command_log_refs")
        if not bundle.get("test_log_refs"):
            errors.append(f"{label}: evidence bundle {bundle.get('bundle_id')} must include test_log_refs")
        if not bundle.get("policy_refs"):
            errors.append(f"{label}: evidence bundle {bundle.get('bundle_id')} must include policy_refs")
        if not bundle.get("blocker_refs"):
            errors.append(f"{label}: evidence bundle {bundle.get('bundle_id')} must include blocker_refs")


def _validate_append_preflight(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    preflight = payload.get("append_preflight")
    if not isinstance(preflight, Mapping):
        errors.append(f"{label}: append_preflight must be an object")
        return
    missing_evidence = sorted(set(REQUIRED_APPEND_EVIDENCE) - {str(ref) for ref in preflight.get("required_before_append_refs", [])})
    if missing_evidence:
        errors.append(f"{label}: missing required_before_append_refs: {', '.join(missing_evidence)}")
    missing_blockers = sorted(set(REQUIRED_APPEND_BLOCKERS) - {str(ref) for ref in preflight.get("blocked_reason_refs", [])})
    if missing_blockers:
        errors.append(f"{label}: missing blocked_reason_refs: {', '.join(missing_blockers)}")


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _validate_secret_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if (
            any(token in key.lower() for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_no_mutation_routes(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    for phrase in ("LoopStatus", "Receipt", "EvidenceBundle", "append-disabled"):
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


def _object_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the receipt/evidence read-model validator."""

    args = build_arg_parser().parse_args(argv)
    validation = validate_agentic_service_harness_receipt_evidence_read_models(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    write_receipt_evidence_read_models_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS RECEIPT EVIDENCE READ MODELS VALID")
    else:
        print("AGENTIC SERVICE HARNESS RECEIPT EVIDENCE READ MODELS INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
