#!/usr/bin/env python3
"""Validate Personal Assistant authority coverage receipts.

Purpose: gate the no-effect authority coverage receipt on schema, risk-level,
skill, capability, effect-boundary, and secret-boundary closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: authority coverage schema, collector constants, and schema helpers.
Invariants:
  - Closed authority coverage requires P0-P5 policy coverage.
  - P4/P5 skills require explicit approval and remain non-executable here.
  - Production, customer, and live Nested Mind claims remain false.
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

from scripts.collect_personal_assistant_authority_coverage import (  # noqa: E402
    DEFAULT_OUTPUT,
    NO_EFFECT_FLAGS,
    REQUIRED_RISK_LEVELS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

AUTHORITY_COVERAGE_SCHEMA_PATH = REPO_ROOT / "schemas" / "personal_assistant_authority_coverage_receipt.schema.json"
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_authority_coverage_validation.json"
)
RECEIPT_ID_PATTERN = re.compile(r"^personal-assistant-authority-coverage-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantAuthorityCoverageValidationStep:
    """One authority coverage validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantAuthorityCoverageValidation:
    """Structured validation report for one authority coverage receipt."""

    receipt_path: str
    valid: bool
    receipt_id: str
    solver_outcome: str
    authority_coverage_closed: bool
    steps: tuple[PersonalAssistantAuthorityCoverageValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_authority_coverage_receipt(
    *,
    receipt_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = AUTHORITY_COVERAGE_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantAuthorityCoverageValidation:
    """Validate one Personal Assistant authority coverage receipt."""
    payload = _read_receipt_payload(receipt_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_receipt_id(payload),
        _check_source_refs(payload),
        _check_risk_level_records(payload),
        _check_skill_authority_records(payload),
        _check_capability_authority_records(payload),
        _check_no_effect_boundary(payload),
        _check_authority_gate(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("authority_summary"))
    return PersonalAssistantAuthorityCoverageValidation(
        receipt_path=_bounded_receipt_path(receipt_path),
        valid=all(step.passed for step in steps),
        receipt_id=_bounded_receipt_id(payload),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        authority_coverage_closed=summary.get("authority_coverage_closed") is True,
        steps=steps,
    )


def write_personal_assistant_authority_coverage_validation_report(
    validation: PersonalAssistantAuthorityCoverageValidation,
    output_path: Path,
) -> Path:
    """Write one local authority coverage validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_receipt_payload(receipt_path: Path) -> dict[str, Any]:
    try:
        raw_text = receipt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError("failed to read Personal Assistant authority coverage receipt") from exc
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Personal Assistant authority coverage receipt returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant authority coverage receipt was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantAuthorityCoverageValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantAuthorityCoverageValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantAuthorityCoverageValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_receipt_id(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    receipt_id = payload.get("receipt_id")
    passed = RECEIPT_ID_PATTERN.fullmatch(str(receipt_id)) is not None
    return PersonalAssistantAuthorityCoverageValidationStep("receipt id", passed, "valid" if passed else "invalid")


def _check_source_refs(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    sources = _list_of_objects(payload.get("source_refs"))
    kinds = {str(source.get("source_kind")) for source in sources if source.get("bound") is True}
    required = {"skill_registry", "approval_matrix", "skill_policy", "capability_pack", "coherence_ledger"}
    passed = required <= kinds
    return PersonalAssistantAuthorityCoverageValidationStep(
        "source refs",
        passed,
        f"bound={len(kinds)} required={len(required)}",
    )


def _check_risk_level_records(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    records = _list_of_objects(payload.get("risk_level_records"))
    levels = {str(record.get("level")) for record in records}
    matrix_bound = all(record.get("matrix_bound") is True for record in records)
    policy_bound = all(record.get("policy_bound") is True for record in records)
    p3_to_p5_approval = all(
        record.get("explicit_approval_required") is True
        for record in records
        if record.get("level") in {"P3", "P4", "P5"}
    )
    p5_blocked = any(record.get("level") == "P5" and record.get("allowed_modes") == ["blocked"] for record in records)
    passed = levels == set(REQUIRED_RISK_LEVELS) and matrix_bound and policy_bound and p3_to_p5_approval and p5_blocked
    return PersonalAssistantAuthorityCoverageValidationStep(
        "risk level records",
        passed,
        f"levels={len(levels)} matrix={matrix_bound} policy={policy_bound}",
    )


def _check_skill_authority_records(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    records = _list_of_objects(payload.get("skill_authority_records"))
    all_covered = all(record.get("authority_covered") is True for record in records)
    all_receipted = all(record.get("receipt_required") is True and record.get("uao_required") is True for record in records)
    no_memory_write = all(record.get("memory_write_allowed") is False for record in records)
    no_execution = all(record.get("execution_enabled") is False for record in records)
    p4_p5_approval = all(
        record.get("requires_approval") is True for record in records if record.get("risk_level") in {"P4", "P5"}
    )
    passed = bool(records) and all_covered and all_receipted and no_memory_write and no_execution and p4_p5_approval
    return PersonalAssistantAuthorityCoverageValidationStep(
        "skill authority records",
        passed,
        f"skills={len(records)} covered={all_covered} p4p5={p4_p5_approval}",
    )


def _check_capability_authority_records(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    records = _list_of_objects(payload.get("capability_authority_records"))
    all_covered = all(record.get("authority_covered") is True for record in records)
    fixture_only = all(record.get("fixture_only") is True for record in records)
    candidate_only = all(record.get("certification_status") == "candidate" for record in records)
    no_production_ready = all(record.get("production_ready") is False for record in records)
    secretless = all(record.get("secret_scope") == "none" for record in records)
    no_world_mutation = all(record.get("world_mutating") is False for record in records)
    passed = (
        bool(records)
        and all_covered
        and fixture_only
        and candidate_only
        and no_production_ready
        and secretless
        and no_world_mutation
    )
    return PersonalAssistantAuthorityCoverageValidationStep(
        "capability authority records",
        passed,
        f"capabilities={len(records)} covered={all_covered} secretless={secretless}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    summary = _object(payload.get("authority_summary"))
    passed = flags_clear and summary.get("production_ready") is False and summary.get("customer_ready") is False
    return PersonalAssistantAuthorityCoverageValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={flags_clear}",
    )


def _check_authority_gate(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    summary = _object(payload.get("authority_summary"))
    required_true = (
        "authority_coverage_closed",
        "coherence_ledger_closed",
        "approval_matrix_levels_bound",
        "skill_policy_levels_bound",
        "all_skills_have_policy_ref",
        "all_skills_have_known_risk_level",
        "all_effect_bearing_skills_require_approval",
        "p4_p5_actions_require_explicit_approval",
        "foundation_execution_disabled",
        "all_capabilities_fixture_only",
        "all_capabilities_candidate_only",
        "all_capabilities_secretless",
        "no_effect_boundary_verified",
    )
    passed = all(summary.get(key) is True for key in required_true) and payload.get("solver_outcome") == "SolvedVerified"
    return PersonalAssistantAuthorityCoverageValidationStep(
        "authority gate",
        passed,
        "closed" if passed else "open",
    )


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantAuthorityCoverageValidationStep:
    serialized = json.dumps(payload, sort_keys=True).lower()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantAuthorityCoverageValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked_terms={','.join(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantAuthorityCoverageValidationStep:
    summary = _object(payload.get("authority_summary"))
    closed = summary.get("authority_coverage_closed") is True
    passed = closed or not require_closed
    return PersonalAssistantAuthorityCoverageValidationStep(
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
    """Run the Personal Assistant authority coverage receipt validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema", type=Path, default=AUTHORITY_COVERAGE_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print validation report JSON.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_authority_coverage_receipt(
        receipt_path=args.receipt,
        schema_path=args.schema,
        require_closed=args.require_closed,
    )
    write_personal_assistant_authority_coverage_validation_report(validation, args.output)
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
