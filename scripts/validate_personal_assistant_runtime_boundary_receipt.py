#!/usr/bin/env python3
"""Validate Personal Assistant runtime boundary receipts.

Purpose: gate the no-effect runtime boundary receipt on schema, runtime module
authority, capability non-mutation, policy-matrix closure, and no-effect flags.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: runtime boundary schema, collector constants, and schema helpers.
Invariants:
  - Runtime modules must not gain connector, provider, deployment, or external write authority.
  - Capability records remain fixture-only, networkless, secretless, and non-mutating.
  - The receipt may list blocked field names but must not serialize secret values.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.collect_personal_assistant_runtime_boundary import (  # noqa: E402
    DEFAULT_OUTPUT,
    NO_EFFECT_FLAGS,
    REQUIRED_RUNTIME_MODULES,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

RUNTIME_BOUNDARY_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_runtime_boundary_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = REPO_ROOT / ".change_assurance" / "personal_assistant_runtime_boundary_validation.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-runtime-boundary-[0-9a-f]{16}$")
BLOCKED_SECRET_VALUE_MARKERS = ("bearer ", "client_secret=", "password=", "-----begin private key-----")


@dataclass(frozen=True, slots=True)
class PersonalAssistantRuntimeBoundaryValidationStep:
    """One runtime boundary validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantRuntimeBoundaryValidation:
    """Structured validation report for one runtime boundary receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    runtime_boundary_closed: bool
    steps: tuple[PersonalAssistantRuntimeBoundaryValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_runtime_boundary_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = RUNTIME_BOUNDARY_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantRuntimeBoundaryValidation:
    """Validate one Personal Assistant runtime boundary receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_source_refs(payload),
        _check_module_records(payload),
        _check_capability_records(payload),
        _check_no_effect_boundary(payload),
        _check_runtime_boundary_gate(payload),
        _check_secret_value_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("runtime_boundary_summary"))
    return PersonalAssistantRuntimeBoundaryValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        runtime_boundary_closed=summary.get("runtime_boundary_closed") is True,
        steps=steps,
    )


def write_personal_assistant_runtime_boundary_validation_report(
    validation: PersonalAssistantRuntimeBoundaryValidation,
    output_path: Path,
) -> Path:
    """Write one local runtime boundary validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant runtime boundary receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant runtime boundary receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant runtime boundary receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantRuntimeBoundaryValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantRuntimeBoundaryValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantRuntimeBoundaryValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_source_refs(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    sources = _list_of_objects(payload.get("source_refs"))
    kinds = {str(source.get("source_kind")) for source in sources if source.get("bound") is True}
    required = {"runtime_modules", "capability_pack", "policy_matrix_receipt"}
    passed = required <= kinds
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "source refs",
        passed,
        f"bound={len(kinds)} required={len(required)}",
    )


def _check_module_records(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    records = _list_of_objects(payload.get("module_records"))
    module_names = {str(record.get("module_name")) for record in records}
    required_bound = set(REQUIRED_RUNTIME_MODULES) <= module_names
    parsed = all(record.get("parse_status") == "parsed" for record in records)
    headers = all(record.get("has_governance_header") is True for record in records)
    no_forbidden_imports = all(record.get("forbidden_import_count") == 0 for record in records)
    no_forbidden_calls = all(record.get("forbidden_call_count") == 0 for record in records)
    no_authority_markers = all(record.get("runtime_authority_marker_count") == 0 for record in records)
    closed = all(record.get("module_boundary_closed") is True for record in records)
    passed = bool(records) and required_bound and parsed and headers and no_forbidden_imports and no_forbidden_calls and no_authority_markers and closed
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "module records",
        passed,
        (
            f"modules={len(module_names)} required={len(REQUIRED_RUNTIME_MODULES)} "
            f"parsed={parsed} headers={headers} imports={no_forbidden_imports} "
            f"calls={no_forbidden_calls} authority={no_authority_markers}"
        ),
    )


def _check_capability_records(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    records = _list_of_objects(payload.get("capability_runtime_records"))
    fixture_only = all(record.get("fixture_only") is True for record in records)
    secretless = all(record.get("secret_scope") == "none" for record in records)
    networkless = all(record.get("network_allowlist_empty") is True for record in records)
    non_mutating = all(record.get("world_mutating") is False for record in records)
    closed = all(record.get("runtime_boundary_closed") is True for record in records)
    passed = bool(records) and fixture_only and secretless and networkless and non_mutating and closed
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "capability records",
        passed,
        f"capabilities={len(records)} fixture={fixture_only} secretless={secretless} networkless={networkless}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    summary = _object(payload.get("runtime_boundary_summary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    passed = flags_clear and summary.get("production_ready") is False and summary.get("customer_ready") is False
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={flags_clear}",
    )


def _check_runtime_boundary_gate(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    summary = _object(payload.get("runtime_boundary_summary"))
    required_true = (
        "runtime_boundary_closed",
        "policy_matrix_closed",
        "required_modules_bound",
        "all_modules_have_headers",
        "all_modules_parse",
        "no_forbidden_imports",
        "no_forbidden_calls",
        "no_runtime_authority_markers",
        "capability_pack_fixture_only",
        "capability_pack_secretless",
        "capability_pack_networkless",
        "capability_pack_non_mutating",
        "no_effect_boundary_verified",
    )
    passed = all(summary.get(key) is True for key in required_true) and payload.get("solver_outcome") == "SolvedVerified"
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "runtime boundary gate",
        passed,
        "closed" if passed else "open",
    )


def _check_secret_value_boundary(payload: dict[str, Any]) -> PersonalAssistantRuntimeBoundaryValidationStep:
    serialized = json.dumps(payload, sort_keys=True).lower()
    leaked_markers = [marker for marker in BLOCKED_SECRET_VALUE_MARKERS if marker in serialized]
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "secret value boundary",
        not leaked_markers,
        "clean" if not leaked_markers else f"blocked_markers={','.join(leaked_markers)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantRuntimeBoundaryValidationStep:
    summary = _object(payload.get("runtime_boundary_summary"))
    closed = summary.get("runtime_boundary_closed") is True
    passed = closed or not require_closed
    return PersonalAssistantRuntimeBoundaryValidationStep(
        "require closed",
        passed,
        "closed" if closed else "not-required" if not require_closed else "open",
    )


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    return str(receipt_id) if isinstance(receipt_id, str) else ""


def _bounded_receipt_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return "provided_receipt"


def _bounded_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    """Run the Personal Assistant runtime boundary receipt validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema", type=Path, default=RUNTIME_BOUNDARY_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print validation report JSON.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_runtime_boundary_receipt(
        receipt_path=args.receipt,
        schema_path=args.schema,
        require_closed=args.require_closed,
    )
    write_personal_assistant_runtime_boundary_validation_report(validation, args.output)
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {_bounded_receipt_path(args.output)}")
        print(f"receipt: {_bounded_receipt_path(args.receipt)}")
        print(f"receipt_id: {validation.receipt_id}")
        print(f"valid: {validation.valid}")
        for step in validation.steps:
            print(f"step: {step.name} passed={step.passed} detail={step.detail}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
