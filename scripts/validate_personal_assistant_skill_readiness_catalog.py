#!/usr/bin/env python3
"""Validate Personal Assistant skill readiness catalogs.

Purpose: gate the no-effect skill readiness catalog on schema, lane binding,
authority coverage, approval posture, execution denial, and secret boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: skill readiness catalog schema, collector constants, and schema
helpers.
Invariants:
  - Every skill must bind to a known foundation readiness lane.
  - P4/P5 skills require approval and remain non-executable here.
  - Customer, production, connector, memory, and live Nested Mind authority remain false.
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

from scripts.collect_personal_assistant_skill_readiness_catalog import (  # noqa: E402
    DEFAULT_OUTPUT,
    NO_EFFECT_FLAGS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

SKILL_READINESS_CATALOG_SCHEMA_PATH = (
    REPO_ROOT / "schemas" / "personal_assistant_skill_readiness_catalog.schema.json"
)
DEFAULT_VALIDATION_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "personal_assistant_skill_readiness_catalog_validation.json"
)
CATALOG_ID_PATTERN = re.compile(r"^personal-assistant-skill-readiness-catalog-[0-9a-f]{16}$")
BLOCKED_TERMS = ("access_token", "authorization", "bearer", "client_secret", "password", "private_key")


@dataclass(frozen=True, slots=True)
class PersonalAssistantSkillReadinessCatalogValidationStep:
    """One skill readiness catalog validation step."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class PersonalAssistantSkillReadinessCatalogValidation:
    """Structured validation report for one skill readiness catalog."""

    catalog_path: str
    valid: bool
    catalog_id: str
    solver_outcome: str
    catalog_closed: bool
    steps: tuple[PersonalAssistantSkillReadinessCatalogValidationStep, ...]

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable validation report."""
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


def validate_personal_assistant_skill_readiness_catalog(
    *,
    catalog_path: Path = DEFAULT_OUTPUT,
    schema_path: Path = SKILL_READINESS_CATALOG_SCHEMA_PATH,
    require_closed: bool = False,
) -> PersonalAssistantSkillReadinessCatalogValidation:
    """Validate one Personal Assistant skill readiness catalog."""
    payload = _read_catalog_payload(catalog_path)
    steps = (
        _check_schema_contract(payload, schema_path),
        _check_catalog_id(payload),
        _check_source_refs(payload),
        _check_skill_records(payload),
        _check_summary_gate(payload),
        _check_no_effect_boundary(payload),
        _check_secret_boundary(payload),
        _check_require_closed(payload, require_closed=require_closed),
    )
    summary = _object(payload.get("catalog_summary"))
    return PersonalAssistantSkillReadinessCatalogValidation(
        catalog_path=_bounded_catalog_path(catalog_path),
        valid=all(step.passed for step in steps),
        catalog_id=_bounded_text(payload.get("catalog_id")),
        solver_outcome=_bounded_text(payload.get("solver_outcome")),
        catalog_closed=summary.get("catalog_closed") is True,
        steps=steps,
    )


def write_personal_assistant_skill_readiness_catalog_validation_report(
    validation: PersonalAssistantSkillReadinessCatalogValidation,
    output_path: Path,
) -> Path:
    """Write one local skill readiness catalog validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _read_catalog_payload(catalog_path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("failed to read Personal Assistant skill readiness catalog") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("Personal Assistant skill readiness catalog was not a JSON object")
    return parsed


def _check_schema_contract(
    payload: dict[str, Any],
    schema_path: Path,
) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    try:
        schema = _load_schema(schema_path)
    except OSError:
        return PersonalAssistantSkillReadinessCatalogValidationStep("schema contract", False, "schema-read-failed")
    errors = _validate_schema_instance(schema, payload)
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "schema contract",
        not errors,
        "valid" if not errors else f"schema-errors={len(errors)}",
    )


def _check_catalog_id(payload: dict[str, Any]) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    catalog_id = payload.get("catalog_id")
    passed = CATALOG_ID_PATTERN.fullmatch(str(catalog_id)) is not None
    return PersonalAssistantSkillReadinessCatalogValidationStep("catalog id", passed, "valid" if passed else "invalid")


def _check_source_refs(payload: dict[str, Any]) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    sources = _list_of_objects(payload.get("source_refs"))
    kinds = {str(source.get("source_kind")) for source in sources if source.get("bound") is True}
    required = {"skill_registry", "readiness_index", "authority_coverage", "capability_pack"}
    passed = required <= kinds
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "source refs",
        passed,
        f"bound={len(kinds)} required={len(required)}",
    )


def _check_skill_records(payload: dict[str, Any]) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    records = _list_of_objects(payload.get("skill_records"))
    all_lane_bound = all(record.get("readiness_bound") is True for record in records)
    all_solved = all(record.get("readiness_lane_state") == "SolvedVerified" for record in records)
    all_authority_covered = all(record.get("authority_covered") is True for record in records)
    all_foundation = all(record.get("foundation_only") is True for record in records)
    no_execution = all(record.get("execution_enabled") is False for record in records)
    p4_p5_guarded = all(
        record.get("requires_approval") is True and record.get("p4_p5_approval_guarded") is True
        for record in records
        if record.get("risk_level") in {"P4", "P5"}
    )
    all_receipted = all(record.get("receipt_required") is True and record.get("uao_required") is True for record in records)
    passed = (
        bool(records)
        and all_lane_bound
        and all_solved
        and all_authority_covered
        and all_foundation
        and no_execution
        and p4_p5_guarded
        and all_receipted
    )
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "skill records",
        passed,
        f"skills={len(records)} lane_bound={all_lane_bound} p4p5={p4_p5_guarded}",
    )


def _check_summary_gate(payload: dict[str, Any]) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    summary = _object(payload.get("catalog_summary"))
    records = _list_of_objects(payload.get("skill_records"))
    required_true = (
        "catalog_closed",
        "readiness_index_closed",
        "authority_coverage_closed",
        "all_skills_lane_bound",
        "all_skills_lane_solved_verified",
        "all_skills_authority_covered",
        "all_skills_foundation_only",
        "all_skills_non_executable",
        "p4_p5_skills_require_approval",
    )
    counts_match = summary.get("skill_count") == len(records) == summary.get("registered_skill_count")
    passed = (
        counts_match
        and all(summary.get(key) is True for key in required_true)
        and payload.get("proof_state") == "Pass"
        and payload.get("solver_outcome") == "SolvedVerified"
        and summary.get("customer_ready") is False
        and summary.get("production_ready") is False
    )
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "summary gate",
        passed,
        f"counts_match={counts_match}",
    )


def _check_no_effect_boundary(payload: dict[str, Any]) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    boundary = _object(payload.get("effect_boundary"))
    flags_clear = all(boundary.get(flag) is False for flag in NO_EFFECT_FLAGS)
    passed = (
        flags_clear
        and payload.get("catalog_is_not_execution_authority") is True
        and payload.get("catalog_is_not_customer_readiness") is True
    )
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "no-effect boundary",
        passed,
        f"flags_clear={flags_clear}",
    )


def _check_secret_boundary(payload: dict[str, Any]) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    serialized = json.dumps(payload, sort_keys=True).lower()
    leaked_terms = [term for term in BLOCKED_TERMS if term in serialized]
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "secret boundary",
        not leaked_terms,
        "clean" if not leaked_terms else f"blocked_terms={','.join(leaked_terms)}",
    )


def _check_require_closed(
    payload: dict[str, Any],
    *,
    require_closed: bool,
) -> PersonalAssistantSkillReadinessCatalogValidationStep:
    closed = _object(payload.get("catalog_summary")).get("catalog_closed") is True
    passed = closed or not require_closed
    return PersonalAssistantSkillReadinessCatalogValidationStep(
        "require closed",
        passed,
        "closed" if closed else "not-required" if not require_closed else "open",
    )


def _bounded_catalog_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return "provided_catalog"


def _bounded_text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def main(argv: list[str] | None = None) -> int:
    """Run the Personal Assistant skill readiness catalog validator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema", type=Path, default=SKILL_READINESS_CATALOG_SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_VALIDATION_OUTPUT)
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print validation report JSON.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_skill_readiness_catalog(
        catalog_path=args.catalog,
        schema_path=args.schema,
        require_closed=args.require_closed,
    )
    write_personal_assistant_skill_readiness_catalog_validation_report(validation, args.output)
    if args.json:
        print(json.dumps(validation.to_json_dict(), indent=2, sort_keys=True))
    else:
        print(f"validation_report: {_bounded_catalog_path(args.output)}")
        print(f"catalog: {_bounded_catalog_path(args.catalog)}")
        print(f"catalog_id: {validation.catalog_id}")
        print(f"valid: {validation.valid}")
        for step in validation.steps:
            print(f"step: {step.name} passed={step.passed} detail={step.detail}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
