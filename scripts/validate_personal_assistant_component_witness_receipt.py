#!/usr/bin/env python3
"""Validate personal-assistant component witness receipts.

Purpose: gate local personal-assistant component witness claims on schema,
request-path, lifecycle, and no-effect authority evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component witness schema, collector constants, and schema helpers.
Invariants:
  - Closed receipts require draft-only component, gated request path, lifecycle, and no-effect evidence.
  - Open receipts remain valid unless closed evidence is explicitly required.
  - Secret-shaped values and raw private connector payloads are rejected.
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

from scripts.collect_personal_assistant_component_witness import (  # noqa: E402
    DEFAULT_OUTPUT,
    FORBIDDEN_CLAIMS,
    NO_EFFECT_FLAGS,
    PRIVATE_ACTIONS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_component_witness_validation.json"
)
WITNESS_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_component_witness_receipt.schema.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-component-witness-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantComponentWitnessValidationStep:
    """One component witness validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantComponentWitnessValidation:
    """Structured validation report for one component witness receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    witness_closed: bool
    steps: tuple[PersonalAssistantComponentWitnessValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_component_witness_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = WITNESS_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantComponentWitnessValidation:
    """Validate one personal-assistant component witness receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_component_witness(payload),
        _check_request_path_witness(payload),
        _check_lifecycle_witness(payload),
        _check_no_effect_boundary(payload),
        _check_forbidden_claims(payload),
        _check_witness_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("summary"))
    return PersonalAssistantComponentWitnessValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        witness_closed=summary.get("witness_closed") is True,
        steps=steps,
    )


def write_personal_assistant_component_witness_validation_report(
    validation: PersonalAssistantComponentWitnessValidation,
    output_path: Path,
) -> Path:
    """Write one local component witness validation report."""
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
        raise RuntimeError("failed to read personal-assistant component witness receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("personal-assistant component witness receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("personal-assistant component witness receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantComponentWitnessValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantComponentWitnessValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantComponentWitnessValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantComponentWitnessValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_component_witness(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    witness = _object(payload.get("component_witness"))
    passed = (
        payload.get("component_id") == "personal_assistant"
        and payload.get("bundle_id") == "personal_assistant_v0"
        and witness.get("component_present") is True
        and witness.get("mode") == "draft_only"
        and witness.get("state") == "draft_only"
        and witness.get("authority_level") == "draft_only"
        and witness.get("proof_binding_state") == "proof_bound"
        and witness.get("route_binding_state") == "bound"
        and witness.get("bundle_membership_is_not_execution_authority") is True
    )
    return PersonalAssistantComponentWitnessValidationStep(
        "component witness",
        passed,
        _verified_detail(passed),
    )


def _check_request_path_witness(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    witness = _object(payload.get("request_path_witness"))
    blocked_actions = set(_string_list(witness.get("blocked_actions")))
    passed = (
        witness.get("inbox_probe_path_bound") is True
        and witness.get("send_email_path_blocked") is True
        and witness.get("gmail_gate_required") is True
        and witness.get("approval_required") is True
        and witness.get("inbox_probe_outcome") == "AwaitingEvidence"
        and witness.get("send_email_outcome") == "GovernanceBlocked"
        and all(action in blocked_actions for action in PRIVATE_ACTIONS)
    )
    return PersonalAssistantComponentWitnessValidationStep(
        "request path witness",
        passed,
        f"blocked_actions={len(blocked_actions)}",
    )


def _check_lifecycle_witness(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    witness = _object(payload.get("lifecycle_witness"))
    passed = (
        witness.get("from_state") == "mounted"
        and witness.get("to_state") == "draft_only"
        and witness.get("authority_level") == "draft_only"
        and witness.get("external_effect") is False
        and witness.get("operator_approval_required") is False
        and witness.get("receipt_is_not_execution_authority") is True
        and witness.get("receipt_is_not_terminal_closure") is True
    )
    return PersonalAssistantComponentWitnessValidationStep(
        "lifecycle witness",
        passed,
        _verified_detail(passed),
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    additional_flags_clear = (
        boundary.get("can_send_external_message") is False
        and boundary.get("can_write_files") is False
        and boundary.get("secret_values_serialized") is False
        and boundary.get("raw_private_connector_payloads_serialized") is False
    )
    passed = (
        flags_clear
        and additional_flags_clear
        and payload.get("receipt_is_not_execution_authority") is True
        and payload.get("receipt_is_not_terminal_closure") is True
    )
    return PersonalAssistantComponentWitnessValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={str(flags_clear and additional_flags_clear).lower()}",
    )


def _check_forbidden_claims(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    claims = set(_string_list(payload.get("forbidden_claims_preserved")))
    passed = all(claim in claims for claim in FORBIDDEN_CLAIMS)
    return PersonalAssistantComponentWitnessValidationStep(
        "forbidden claims",
        passed,
        f"claims={len(claims)}",
    )


def _check_witness_gate(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    summary = _object(payload.get("summary"))
    closed = summary.get("witness_closed") is True
    if closed:
        passed = (
            payload.get("proof_state") == "Pass"
            and payload.get("solver_outcome") == "SolvedVerified"
            and summary.get("component_witness_verified") is True
            and summary.get("request_path_witness_verified") is True
            and summary.get("lifecycle_witness_verified") is True
            and summary.get("no_effect_boundary_verified") is True
        )
        detail = "closed" if passed else "closed-with-incomplete-evidence"
    else:
        passed = payload.get("proof_state") == "Fail" and payload.get("solver_outcome") == "AwaitingEvidence"
        detail = "awaiting-evidence" if passed else "open-state-mismatch"
    return PersonalAssistantComponentWitnessValidationStep("witness gate", passed, detail)


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantComponentWitnessValidationStep:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantComponentWitnessValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked-terms={len(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantComponentWitnessValidationStep:
    if not require_closed:
        return PersonalAssistantComponentWitnessValidationStep("require closed", True, "not-required")
    summary = _object(payload.get("summary"))
    passed = (
        payload.get("proof_state") == "Pass"
        and payload.get("solver_outcome") == "SolvedVerified"
        and summary.get("component_witness_verified") is True
        and summary.get("request_path_witness_verified") is True
        and summary.get("lifecycle_witness_verified") is True
        and summary.get("no_effect_boundary_verified") is True
        and summary.get("witness_closed") is True
    )
    return PersonalAssistantComponentWitnessValidationStep(
        "require closed",
        passed,
        "closed" if passed else "awaiting-evidence",
    )


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return "examples/personal_assistant_component_witness_receipt.json"
    return "provided_receipt"


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    if RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None:
        return str(receipt_id)
    return "invalid"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _bounded_text(value: Any) -> str:
    return str(value) if isinstance(value, str) and value else "missing"


def _verified_detail(passed: bool) -> str:
    return "verified" if passed else "drift"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse component witness receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate a personal-assistant component witness receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(WITNESS_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for component witness receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_personal_assistant_component_witness_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_closed=args.require_closed,
        )
    except RuntimeError:
        print("personal-assistant component witness receipt validation failed")
        return 1

    output_path = write_personal_assistant_component_witness_validation_report(validation, Path(args.output))
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
