#!/usr/bin/env python3
"""Validate personal-assistant public console probe receipts.

Purpose: gate deployed personal-assistant console witness claims on schema-backed
public route evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: public console probe schema, collector constants, and schema validation helpers.
Invariants:
  - AwaitingEvidence receipts may be structurally valid.
  - SolvedVerified requires JSON, HTML, and no-effect boundary closure.
  - Secret-shaped values and raw response bodies are not serialized.
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

from scripts.collect_personal_assistant_public_console_probe import (  # noqa: E402
    DEFAULT_OUTPUT,
    EXPECTED_LANE_IDS,
    NO_EFFECT_FLAGS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_public_console_probe_validation.json"
)
PROBE_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_public_console_probe_receipt.schema.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-public-console-probe-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantPublicConsoleProbeValidationStep:
    """One personal-assistant public console probe validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantPublicConsoleProbeValidation:
    """Structured validation report for one public console probe receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    probe_closed: bool
    observed_lane_count: int
    steps: tuple[PersonalAssistantPublicConsoleProbeValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_public_console_probe_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = PROBE_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantPublicConsoleProbeValidation:
    """Validate one personal-assistant public console probe receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_route_observations(payload),
        _check_no_effect_boundary(payload),
        _check_probe_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("summary"))
    return PersonalAssistantPublicConsoleProbeValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        probe_closed=summary.get("probe_closed") is True,
        observed_lane_count=_bounded_int(summary.get("observed_lane_count")),
        steps=steps,
    )


def write_personal_assistant_public_console_probe_validation_report(
    validation: PersonalAssistantPublicConsoleProbeValidation,
    output_path: Path,
) -> Path:
    """Write one local public console probe validation report."""
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
        raise RuntimeError("failed to read personal-assistant public console probe receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("personal-assistant public console probe receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("personal-assistant public console probe receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantPublicConsoleProbeValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantPublicConsoleProbeValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantPublicConsoleProbeValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantPublicConsoleProbeValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantPublicConsoleProbeValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_route_observations(payload: dict[str, Any]) -> PersonalAssistantPublicConsoleProbeValidationStep:
    observations = _list_of_objects(payload.get("route_observations"))
    route_ids = {str(item.get("route_id")) for item in observations}
    passed = route_ids == {"console_json", "console_html"} and all(
        item.get("request_reached_endpoint") is True and item.get("observed_status_code") == 200
        for item in observations
        if payload.get("solver_outcome") == "SolvedVerified"
    )
    return PersonalAssistantPublicConsoleProbeValidationStep(
        "route observations",
        passed,
        f"routes={','.join(sorted(route_ids))}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantPublicConsoleProbeValidationStep:
    effect_boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(effect_boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    serialized_flags_clear = (
        effect_boundary.get("secret_values_serialized") is False
        and effect_boundary.get("raw_response_bodies_serialized") is False
    )
    summary = _object(payload.get("summary"))
    lane_count_matches = summary.get("observed_lane_count") == len(EXPECTED_LANE_IDS)
    passed = flags_clear and serialized_flags_clear and (
        summary.get("no_effect_boundary_verified") is False or lane_count_matches
    )
    detail = f"flags_clear={str(flags_clear).lower()} lane_count={summary.get('observed_lane_count')}"
    return PersonalAssistantPublicConsoleProbeValidationStep("no-effect boundary", passed, detail)


def _check_probe_gate(payload: dict[str, Any]) -> PersonalAssistantPublicConsoleProbeValidationStep:
    summary = _object(payload.get("summary"))
    closed = summary.get("probe_closed") is True
    if closed:
        passed = (
            payload.get("proof_state") == "Pass"
            and payload.get("solver_outcome") == "SolvedVerified"
            and summary.get("console_read_model_verified") is True
            and summary.get("html_view_verified") is True
            and summary.get("no_effect_boundary_verified") is True
        )
        detail = "closed" if passed else "closed-with-incomplete-evidence"
    else:
        passed = payload.get("proof_state") == "Fail" and payload.get("solver_outcome") == "AwaitingEvidence"
        detail = "awaiting-evidence" if passed else "open-state-mismatch"
    return PersonalAssistantPublicConsoleProbeValidationStep("probe gate", passed, detail)


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantPublicConsoleProbeValidationStep:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantPublicConsoleProbeValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked-terms={len(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantPublicConsoleProbeValidationStep:
    if not require_closed:
        return PersonalAssistantPublicConsoleProbeValidationStep("require closed", True, "not-required")
    summary = _object(payload.get("summary"))
    passed = summary.get("probe_closed") is True and payload.get("solver_outcome") == "SolvedVerified"
    return PersonalAssistantPublicConsoleProbeValidationStep(
        "require closed",
        passed,
        "closed" if passed else "awaiting-evidence",
    )


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return "examples/personal_assistant_public_console_probe_receipt.json"
    return "provided_receipt"


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    if RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None:
        return str(receipt_id)
    return "invalid"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _bounded_int(value: Any) -> int:
    return max(value, 0) if isinstance(value, int) else 0


def _bounded_text(value: Any) -> str:
    return str(value) if isinstance(value, str) and value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse public console probe receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate a personal-assistant public console probe receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(PROBE_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for public console probe receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_personal_assistant_public_console_probe_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_closed=args.require_closed,
        )
    except RuntimeError:
        print("personal-assistant public console probe receipt validation failed")
        return 1

    output_path = write_personal_assistant_public_console_probe_validation_report(validation, Path(args.output))
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
