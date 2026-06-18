#!/usr/bin/env python3
"""Validate Personal Assistant capsule alignment receipts.

Purpose: gate the no-effect capsule alignment receipt on schema, capsule,
capability, schema-ref, no-effect, and secret-boundary closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capsule alignment schema, collector constants, and schema helpers.
Invariants:
  - Closed alignment requires capsule refs to match capability pack ids.
  - Referenced input and output schemas must exist and be manifest-bound.
  - Production, customer, live connector, and live Nested Mind claims remain false.
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

from scripts.collect_personal_assistant_capsule_alignment import (  # noqa: E402
    DEFAULT_OUTPUT,
    NO_EFFECT_FLAGS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

CAPSULE_ALIGNMENT_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_capsule_alignment_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = REPO_ROOT / ".change_assurance" / "personal_assistant_capsule_alignment_validation.json"
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-capsule-alignment-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantCapsuleAlignmentValidationStep:
    """One capsule alignment validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantCapsuleAlignmentValidation:
    """Structured validation report for one capsule alignment receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    capsule_alignment_closed: bool
    steps: tuple[PersonalAssistantCapsuleAlignmentValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_capsule_alignment_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = CAPSULE_ALIGNMENT_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantCapsuleAlignmentValidation:
    """Validate one Personal Assistant capsule alignment receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_source_refs(payload),
        _check_capability_binding_records(payload),
        _check_schema_binding_records(payload),
        _check_capsule_boundary(payload),
        _check_no_effect_boundary(payload),
        _check_alignment_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("alignment_summary"))
    return PersonalAssistantCapsuleAlignmentValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        capsule_alignment_closed=summary.get("capsule_alignment_closed") is True,
        steps=steps,
    )


def write_personal_assistant_capsule_alignment_validation_report(
    validation: PersonalAssistantCapsuleAlignmentValidation,
    output_path: Path,
) -> Path:
    """Write one local capsule alignment validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant capsule alignment receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant capsule alignment receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant capsule alignment receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantCapsuleAlignmentValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantCapsuleAlignmentValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantCapsuleAlignmentValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_source_refs(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    sources = _list_of_objects(payload.get("source_refs"))
    kinds = {str(source.get("source_kind")) for source in sources if source.get("bound") is True}
    required = {"capsule", "capability_pack", "protocol_manifest", "authority_coverage_receipt"}
    passed = required <= kinds
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "source refs",
        passed,
        f"bound={len(kinds)} required={len(required)}",
    )


def _check_capability_binding_records(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    records = _list_of_objects(payload.get("capability_binding_records"))
    all_covered = all(record.get("alignment_covered") is True for record in records)
    all_refs_bound = all(record.get("in_capsule") is True and record.get("in_capability_pack") is True for record in records)
    all_schemas_bound = all(record.get("input_schema_bound") is True and record.get("output_schema_bound") is True for record in records)
    candidate_only = all(record.get("certification_status") == "candidate" for record in records)
    fixture_only = all(record.get("fixture_only") is True for record in records)
    no_production_ready = all(record.get("production_ready") is False for record in records)
    secretless = all(record.get("secret_scope") == "none" for record in records)
    networkless = all(record.get("network_allowlist_empty") is True for record in records)
    non_world_mutating = all(record.get("world_mutating") is False for record in records)
    receipted = all(record.get("receipt_required") is True for record in records)
    passed = (
        bool(records)
        and all_covered
        and all_refs_bound
        and all_schemas_bound
        and candidate_only
        and fixture_only
        and no_production_ready
        and secretless
        and networkless
        and non_world_mutating
        and receipted
    )
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "capability binding records",
        passed,
        f"capabilities={len(records)} covered={all_covered} schemas={all_schemas_bound}",
    )


def _check_schema_binding_records(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    records = _list_of_objects(payload.get("schema_binding_records"))
    manifest_bound = all(record.get("manifest_bound") is True for record in records)
    file_bound = all(record.get("file_bound") is True for record in records)
    passed = bool(records) and manifest_bound and file_bound
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "schema binding records",
        passed,
        f"schemas={len(records)} manifest={manifest_bound} files={file_bound}",
    )


def _check_capsule_boundary(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    boundary = _object(payload.get("capsule_boundary"))
    passed = (
        boundary.get("foundation_mode_required") is True
        and boundary.get("production_ready") is False
        and boundary.get("live_connector_execution_allowed") is False
        and boundary.get("live_nested_mind_activation_allowed") is False
    )
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "capsule boundary",
        passed,
        "foundation-only" if passed else "open",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    summary = _object(payload.get("alignment_summary"))
    passed = flags_clear and summary.get("production_ready") is False and summary.get("customer_ready") is False
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={flags_clear}",
    )


def _check_alignment_gate(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    summary = _object(payload.get("alignment_summary"))
    required_true = (
        "capsule_alignment_closed",
        "authority_coverage_closed",
        "capsule_refs_match_pack",
        "all_capability_refs_bound",
        "all_schema_refs_bound",
        "all_policy_refs_bound",
        "all_test_fixture_refs_bound",
        "all_capabilities_candidate_only",
        "all_capabilities_fixture_only",
        "all_capabilities_secretless",
        "all_capabilities_networkless",
        "all_capabilities_non_world_mutating",
        "all_capabilities_receipted",
        "capsule_foundation_mode_required",
        "capsule_live_connector_execution_blocked",
        "capsule_live_nested_mind_activation_blocked",
        "no_effect_boundary_verified",
    )
    passed = all(summary.get(key) is True for key in required_true) and payload.get("solver_outcome") == "SolvedVerified"
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "alignment gate",
        passed,
        "closed" if passed else "open",
    )


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantCapsuleAlignmentValidationStep:
    serialized = json.dumps(payload, sort_keys=True).lower()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantCapsuleAlignmentValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked_terms={','.join(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantCapsuleAlignmentValidationStep:
    summary = _object(payload.get("alignment_summary"))
    closed = summary.get("capsule_alignment_closed") is True
    passed = closed or not require_closed
    return PersonalAssistantCapsuleAlignmentValidationStep(
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
    """Run the Personal Assistant capsule alignment receipt validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema", type=Path, default=CAPSULE_ALIGNMENT_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print validation report JSON.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_capsule_alignment_receipt(
        receipt_path=args.receipt,
        schema_path=args.schema,
        require_closed=args.require_closed,
    )
    write_personal_assistant_capsule_alignment_validation_report(validation, args.output)
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
