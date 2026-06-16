#!/usr/bin/env python3
"""Validate Component Harness route-family promotion witness requirements.

Purpose: prove blocked route-family promotions have an explicit witness
requirements contract before router ownership can change.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: promotion witness requirements schema/example, runtime builder,
and component route-family promotion preflight validation.
Invariants:
  - Requirements remain blocked while hard witnesses are missing.
  - Missing evidence mirrors the failed promotion preflight gates.
  - Requirement reports cannot grant execution, connector, mutation, or
    terminal-closure authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_route_family_promotion_witness_requirements import (  # noqa: E402
    build_component_route_family_promotion_witness_requirements,
)
from scripts.validate_component_route_family_promotion_preflight import (  # noqa: E402
    validate_component_route_family_promotion_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_witness_requirements.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT / "examples" / "component_route_family_promotion_witness_requirements.governed_connector_framework.json"
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_route_family_promotion_witness_requirements_validation.json"
REQUIRED_FAILED_EVIDENCE = {
    "missing_selected_component_route_binding",
    "missing_lifecycle_transition_receipt",
    "missing_authority_upgrade_witness",
    "generic_connector_surface_not_product_specific_authority",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionWitnessRequirementsValidation:
    """Schema and semantic validation report for promotion witness requirements."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    witness_requirement_count: int
    missing_witness_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_witness_requirements(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionWitnessRequirementsValidation:
    """Validate promotion witness requirements schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion witness requirements schema", errors)
    example = _load_json_object(example_path, "component route-family promotion witness requirements example", errors)

    preflight_validation = validate_component_route_family_promotion_preflight()
    if not preflight_validation.ok:
        errors.extend(
            f"component route-family promotion preflight validation failed: {error}"
            for error in preflight_validation.errors
        )

    runtime_report = build_component_route_family_promotion_witness_requirements()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_requirements_semantics(example, errors, _path_label(example_path))
    _validate_requirements_semantics(runtime_report, errors, "runtime component route-family promotion witness requirements")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionWitnessRequirementsValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        witness_requirement_count=int(summary.get("witness_requirement_count", 0)) if isinstance(summary, dict) else 0,
        missing_witness_count=int(summary.get("missing_witness_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_witness_requirements_validation(
    validation: ComponentRouteFamilyPromotionWitnessRequirementsValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic promotion witness requirements validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_requirements_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("requirements_are_not_execution_authority") is not True:
        errors.append(f"{label}: requirements must not be execution authority")
    for field_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "ready_for_promotion",
    ):
        if report.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    if report.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    if report.get("target_surface_id") != "governed_connector_framework":
        errors.append(f"{label}: target_surface_id must remain governed_connector_framework")
    if report.get("target_component_id") != "gmail_account_binding_gate":
        errors.append(f"{label}: target_component_id must remain gmail_account_binding_gate")

    requirements = report.get("promotion_witness_requirements")
    summary = report.get("summary")
    if not isinstance(requirements, list) or not requirements:
        errors.append(f"{label}: promotion_witness_requirements must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    requirement_ids = [str(requirement.get("requirement_id")) for requirement in requirements if isinstance(requirement, dict)]
    if len(requirement_ids) != len(set(requirement_ids)):
        errors.append(f"{label}: requirement_ids must be unique")

    missing_evidence = set(_string_list(report.get("missing_evidence")))
    failed_evidence: set[str] = set()
    satisfied_count = 0
    missing_count = 0
    hard_blocker_count = 0
    kinds: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict):
            errors.append(f"{label}: requirement entries must be objects")
            continue
        evidence_key = str(requirement.get("evidence_key", ""))
        proof_state = str(requirement.get("proof_state", ""))
        requirement_state = str(requirement.get("requirement_state", ""))
        kinds.add(str(requirement.get("witness_kind", "")))
        if requirement.get("witness_is_not_execution_authority") is not True:
            errors.append(f"{label}: requirement {requirement.get('requirement_id')} must not be execution authority")
        if requirement.get("required_before_promotion") is not True:
            errors.append(f"{label}: requirement {requirement.get('requirement_id')} must be required before promotion")
        if proof_state == "Pass":
            satisfied_count += 1
            if requirement_state != "satisfied" or requirement.get("blocks_promotion") is not False:
                errors.append(f"{label}: pass requirement {evidence_key} must be satisfied and non-blocking")
        elif proof_state == "Fail":
            missing_count += 1
            hard_blocker_count += 1 if requirement.get("blocks_promotion") is True else 0
            failed_evidence.add(evidence_key)
            if requirement_state != "missing" or requirement.get("blocks_promotion") is not True:
                errors.append(f"{label}: fail requirement {evidence_key} must be missing and blocking")
        else:
            errors.append(f"{label}: requirement {evidence_key} proof_state must be Pass or Fail")

    if failed_evidence != missing_evidence:
        errors.append(f"{label}: missing_evidence must match failed requirement evidence keys")
    missing_required = sorted(REQUIRED_FAILED_EVIDENCE - missing_evidence)
    if missing_required:
        errors.append(f"{label}: missing_evidence omits required blockers {missing_required}")
    required_kinds = {
        "route_binding",
        "proof_binding",
        "lifecycle_transition",
        "current_authority_envelope",
        "authority_upgrade",
        "product_specific_ownership",
        "terminal_closure_denial",
    }
    if not required_kinds <= kinds:
        errors.append(f"{label}: promotion witness requirements missing witness kinds {sorted(required_kinds - kinds)}")
    expected_counts = {
        "witness_requirement_count": len(requirements),
        "satisfied_witness_count": satisfied_count,
        "missing_witness_count": missing_count,
        "hard_blocker_count": hard_blocker_count,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match promotion_witness_requirements")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_witness_requirements_receipt",
        "component_route_family_promotion_witness_evidence_receipt",
        "component_route_family_promotion_approval_candidates_receipt",
        "component_route_family_promotion_approval_intake_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_preflight_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
    ):
        if expected_receipt not in expected_receipts:
            errors.append(f"{label}: expected_receipts must include {expected_receipt}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse promotion witness requirements validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness promotion witness requirements.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for promotion witness requirements validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_witness_requirements(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_witness_requirements_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION WITNESS REQUIREMENTS VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
