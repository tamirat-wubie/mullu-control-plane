#!/usr/bin/env python3
"""Validate Personal Assistant coherence ledger receipts.

Purpose: gate the no-effect coherence ledger on schema, source receipts, lane
dependency records, authority blocks, and secret-boundary closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: coherence ledger schema, collector constants, and schema helpers.
Invariants:
  - Closed coherence requires a closed readiness index and bound lane evidence.
  - Production and customer-readiness claims remain false.
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

from scripts.collect_personal_assistant_coherence_ledger import DEFAULT_OUTPUT, NO_EFFECT_FLAGS  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_coherence_ledger_validation.json"
)
COHERENCE_LEDGER_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_coherence_ledger_receipt.schema.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-coherence-ledger-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantCoherenceLedgerValidationStep:
    """One coherence ledger validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantCoherenceLedgerValidation:
    """Structured validation report for one coherence ledger receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    coherence_ledger_closed: bool
    steps: tuple[PersonalAssistantCoherenceLedgerValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_coherence_ledger_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = COHERENCE_LEDGER_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantCoherenceLedgerValidation:
    """Validate one Personal Assistant coherence ledger receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_source_receipts(payload),
        _check_lane_ledger_records(payload),
        _check_coherence_counts(payload),
        _check_authority_blocks(payload),
        _check_no_effect_boundary(payload),
        _check_coherence_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("coherence_summary"))
    return PersonalAssistantCoherenceLedgerValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        coherence_ledger_closed=summary.get("coherence_ledger_closed") is True,
        steps=steps,
    )


def write_personal_assistant_coherence_ledger_validation_report(
    validation: PersonalAssistantCoherenceLedgerValidation,
    output_path: Path,
) -> Path:
    """Write one local coherence ledger validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant coherence ledger receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant coherence ledger receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant coherence ledger receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantCoherenceLedgerValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantCoherenceLedgerValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantCoherenceLedgerValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantCoherenceLedgerValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_source_receipts(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    sources = _list_of_objects(payload.get("source_receipts"))
    closed_sources = [
        source
        for source in sources
        if source.get("source_id") == "personal_assistant_readiness_index"
        and source.get("proof_state") == "Pass"
        and source.get("solver_outcome") == "SolvedVerified"
        and source.get("closed") is True
        and source.get("no_effect_boundary_verified") is True
    ]
    passed = len(sources) >= 1 and len(closed_sources) == 1
    return PersonalAssistantCoherenceLedgerValidationStep(
        "source receipts",
        passed,
        f"sources={len(sources)} closed={len(closed_sources)}",
    )


def _check_lane_ledger_records(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    lanes = _list_of_objects(payload.get("lane_ledger_records"))
    lane_ids = {str(lane.get("lane_id")) for lane in lanes}
    valid_lanes = [
        lane
        for lane in lanes
        if lane.get("state") == "SolvedVerified"
        and lane.get("receipt_required") is True
        and lane.get("foundation_only") is True
        and lane.get("no_effect_boundary_verified") is True
        and bool(_list(lane.get("source_receipt_ids")))
        and bool(_list(lane.get("schema_refs")))
        and bool(_list(lane.get("validator_refs")))
        and bool(_list(lane.get("blocked_authority_refs")))
        and _int(lane.get("dependency_edge_count")) >= 1
        and lane.get("next_allowed_action") == "continue_foundation_hardening_only"
    ]
    passed = len(lanes) >= 1 and len(lane_ids) == len(lanes) and len(valid_lanes) == len(lanes)
    return PersonalAssistantCoherenceLedgerValidationStep(
        "lane ledger records",
        passed,
        f"lanes={len(lanes)} bound={len(valid_lanes)}",
    )


def _check_coherence_counts(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    summary = _object(payload.get("coherence_summary"))
    lanes = _list_of_objects(payload.get("lane_ledger_records"))
    authority_blocks = _list_of_objects(payload.get("authority_block_records"))
    dependency_edges = sum(_int(lane.get("dependency_edge_count")) for lane in lanes)
    next_actions = sum(
        1 for lane in lanes if lane.get("next_allowed_action") == "continue_foundation_hardening_only"
    )
    passed = (
        summary.get("lane_count") == len(lanes)
        and summary.get("dependency_edge_count") == dependency_edges
        and summary.get("blocked_authority_count") == sum(1 for block in authority_blocks if block.get("blocked") is True)
        and summary.get("next_action_count") == next_actions
        and summary.get("production_ready") is False
        and summary.get("customer_ready") is False
    )
    return PersonalAssistantCoherenceLedgerValidationStep(
        "coherence counts",
        passed,
        f"lanes={summary.get('lane_count')} edges={summary.get('dependency_edge_count')}",
    )


def _check_authority_blocks(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    blocks = _list_of_objects(payload.get("authority_block_records"))
    block_ids = {str(block.get("authority_id")) for block in blocks}
    passed = bool(blocks) and len(block_ids) == len(blocks) and all(block.get("blocked") is True for block in blocks)
    return PersonalAssistantCoherenceLedgerValidationStep(
        "authority blocks",
        passed,
        f"blocked={sum(1 for block in blocks if block.get('blocked') is True)}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    payload_clear = boundary.get("secret_values_serialized") is False and boundary.get("raw_private_payloads_serialized") is False
    passed = (
        flags_clear
        and payload_clear
        and payload.get("receipt_is_not_execution_authority") is True
        and payload.get("receipt_is_not_terminal_closure") is True
    )
    return PersonalAssistantCoherenceLedgerValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={str(flags_clear and payload_clear).lower()}",
    )


def _check_coherence_gate(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    summary = _object(payload.get("coherence_summary"))
    closed = summary.get("coherence_ledger_closed") is True
    if closed:
        passed = (
            payload.get("proof_state") == "Pass"
            and payload.get("solver_outcome") == "SolvedVerified"
            and summary.get("readiness_index_closed") is True
            and summary.get("all_lanes_bound_to_sources") is True
            and summary.get("all_edges_no_effect") is True
            and summary.get("no_effect_boundary_verified") is True
            and summary.get("production_ready") is False
            and summary.get("customer_ready") is False
        )
        detail = "closed" if passed else "closed-with-incomplete-evidence"
    else:
        passed = payload.get("proof_state") == "Fail" and payload.get("solver_outcome") == "AwaitingEvidence"
        detail = "awaiting-evidence" if passed else "open-state-mismatch"
    return PersonalAssistantCoherenceLedgerValidationStep("coherence gate", passed, detail)


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantCoherenceLedgerValidationStep:
    serialized = json.dumps(payload, sort_keys=True).casefold()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantCoherenceLedgerValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked-terms={len(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantCoherenceLedgerValidationStep:
    if not require_closed:
        return PersonalAssistantCoherenceLedgerValidationStep("require closed", True, "not-required")
    summary = _object(payload.get("coherence_summary"))
    passed = payload.get("solver_outcome") == "SolvedVerified" and summary.get("coherence_ledger_closed") is True
    return PersonalAssistantCoherenceLedgerValidationStep(
        "require closed",
        passed,
        "closed" if passed else "awaiting-evidence",
    )


def _bounded_receipt_path(receipt_path: Path) -> str:
    if receipt_path == DEFAULT_OUTPUT:
        return "examples/personal_assistant_coherence_ledger_receipt.json"
    return "provided_receipt"


def _bounded_receipt_id(payload: dict[str, Any]) -> str:
    receipt_id = payload.get("receipt_id")
    if RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None:
        return str(receipt_id)
    return "invalid"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> tuple[Any, ...]:
    return tuple(value) if isinstance(value, list) else ()


def _list_of_objects(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _bounded_text(value: Any) -> str:
    return str(value) if isinstance(value, str) and value else "missing"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse coherence ledger receipt validation arguments."""
    parser = argparse.ArgumentParser(description="Validate a Personal Assistant coherence ledger receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--schema", default=str(COHERENCE_LEDGER_SCHEMA_PATH))
    parser.add_argument("--output", default=str(DEFAULT_VALIDATION_OUTPUT))
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for coherence ledger receipt validation."""
    args = parse_args(argv)
    try:
        validation = validate_personal_assistant_coherence_ledger_receipt(
            receipt_path=Path(args.receipt),
            schema_path=Path(args.schema),
            require_closed=args.require_closed,
        )
    except RuntimeError:
        print("Personal Assistant coherence ledger receipt validation failed")
        return 1

    output_path = write_personal_assistant_coherence_ledger_validation_report(validation, Path(args.output))
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
