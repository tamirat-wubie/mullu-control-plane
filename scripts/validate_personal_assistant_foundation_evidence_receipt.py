#!/usr/bin/env python3
"""Validate personal-assistant foundation evidence receipts.

Purpose: gate aggregate personal-assistant foundation evidence on schema,
console, public probe, component witness, and no-effect boundary closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: foundation evidence schema, collector constants, and schema helpers.
Invariants:
  - Closed evidence requires all three source evidence items to be closed.
  - Open receipts remain valid only when their own gate state is consistent.
  - Secret-shaped values and raw private payload flags are rejected.
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

from scripts.collect_personal_assistant_foundation_evidence import (  # noqa: E402
    DEFAULT_OUTPUT,
    EVIDENCE_KINDS,
    NO_EFFECT_FLAGS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_foundation_evidence_validation.json"
)
EVIDENCE_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_foundation_evidence_receipt.schema.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-foundation-evidence-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantFoundationEvidenceValidationStep:
    """One foundation evidence validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantFoundationEvidenceValidation:
    """Structured validation report for one foundation evidence receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    foundation_evidence_closed: bool
    steps: tuple[PersonalAssistantFoundationEvidenceValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_foundation_evidence_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = EVIDENCE_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantFoundationEvidenceValidation:
    """Validate one personal-assistant foundation evidence receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_evidence_items(payload),
        _check_no_effect_boundary(payload),
        _check_evidence_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("summary"))
    return PersonalAssistantFoundationEvidenceValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        foundation_evidence_closed=summary.get("foundation_evidence_closed") is True,
        steps=steps,
    )


def write_personal_assistant_foundation_evidence_validation_report(
    validation: PersonalAssistantFoundationEvidenceValidation,
    output_path: Path,
) -> Path:
    """Write one local foundation evidence validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read personal-assistant foundation evidence receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("personal-assistant foundation evidence receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("personal-assistant foundation evidence receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantFoundationEvidenceValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantFoundationEvidenceValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantFoundationEvidenceValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantFoundationEvidenceValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantFoundationEvidenceValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_evidence_items(payload: dict[str, Any]) -> PersonalAssistantFoundationEvidenceValidationStep:
    items = _list_of_objects(payload.get("evidence_items"))
    kinds = {str(item.get("evidence_kind")) for item in items}
    closed_items = [
        item
        for item in items
        if item.get("proof_state") == "Pass"
        and item.get("solver_outcome") == "SolvedVerified"
        and item.get("closed") is True
        and item.get("no_effect_boundary_verified") is True
    ]
    passed = kinds == set(EVIDENCE_KINDS) and len(closed_items) == len(EVIDENCE_KINDS)
    return PersonalAssistantFoundationEvidenceValidationStep(
        "evidence items",
        passed,
        f"kinds={','.join(sorted(kinds))} closed={len(closed_items)}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantFoundationEvidenceValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    additional_flags_clear = (
        boundary.get("secret_values_serialized") is False
        and boundary.get("raw_private_payloads_serialized") is False
    )
    passed = (
        flags_clear
        and additional_flags_clear
        and payload.get("receipt_is_not_execution_authority") is True
        and payload.get("receipt_is_not_terminal_closure") is True
    )
    return PersonalAssistantFoundationEvidenceValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={str(flags_clear and additional_flags_clear).lower()}",
    )


def _check_evidence_gate(payload: dict[str, Any]) -> PersonalAssistantFoundationEvidenceValidationStep:
    summary = _object(payload.get("summary"))
    closed = summary.get("foundation_evidence_closed") is True
    if closed:
        passed = (
            payload.get("proof_state") == "Pass"
            and payload.get("solver_outcome") == "SolvedVerified"
            and summary.get("evidence_item_count") == 3
            and summary.get("console_read_model_verified") is True
            and summary.get("public_console_probe_verified") is True
            and summary.get("component_witness_verified") is True
            and summary.get("no_effect_boundary_verified") is True
        )
        detail = "closed" if passed else "closed-with-incomplete-evidence"
    else:
        passed = payload.get("proof_state") == "Fail" and payload.get("solver_outcome") == "AwaitingEvidence"
        detail = "awaiting-evidence" if passed else "open-state-mismatch"
    return PersonalAssistantFoundationEvidenceValidationStep("evidence gate", passed, detail)


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantFoundationEvidenceValidationStep:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantFoundationEvidenceValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked-terms={len(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantFoundationEvidenceValidationStep:
    if not require_closed:
        return PersonalAssistantFoundationEvidenceValidationStep("require closed", True, "not-required")
    summary = _object(payload.get("summary"))
    passed = payload.get("solver_outcome") == "SolvedVerified" and summary.get("foundation_evidence_closed") is True
    return PersonalAssistantFoundationEvidenceValidationStep(
        "require closed",
        passed,
        "closed" if passed else "awaiting-evidence",
    )


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return "examples/personal_assistant_foundation_evidence_receipt.json"
    return "provided_receipt"


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    if RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None:
        return str(receipt_id)
    return "invalid"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _bounded_text(value: Any) -> str:
    return str(value) if isinstance(value, str) and value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse foundation evidence receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate a personal-assistant foundation evidence receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(EVIDENCE_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for foundation evidence receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_personal_assistant_foundation_evidence_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_closed=args.require_closed,
        )
    except RuntimeError:
        print("personal-assistant foundation evidence receipt validation failed")
        return 1

    output_path = write_personal_assistant_foundation_evidence_validation_report(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {output_path}")
        print(f"receipt: {validation.receipt_path}")
        print(f"receipt_id: {validation.receipt_id}")
        print(f"valid: {str(validation.valid).lower()}")
        for step in validation.steps:
            print(f"step: {step.name} passed={str(step.passed).lower()} detail={step.detail}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
