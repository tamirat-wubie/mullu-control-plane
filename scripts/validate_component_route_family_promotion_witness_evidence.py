#!/usr/bin/env python3
"""Validate Component Harness route-family promotion witness evidence.

Purpose: prove blocked promotion gates carry concrete denial
evidence without granting route, connector, mutation, or terminal authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: promotion witness evidence schema/example, runtime builder, and
promotion witness requirements validation.
Invariants:
  - Witness evidence remains blocked and non-authoritative.
  - Route-binding, lifecycle, authority-upgrade, and product-specific evidence
    are present denials.
  - Denial evidence does not satisfy promotion approval requirements.
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

from mcoi_runtime.app.component_route_family_promotion_witness_evidence import (  # noqa: E402
    build_component_route_family_promotion_witness_evidence,
)
from scripts.validate_component_route_family_promotion_witness_requirements import (  # noqa: E402
    validate_component_route_family_promotion_witness_requirements,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_witness_evidence.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT / "examples" / "component_route_family_promotion_witness_evidence.governed_connector_framework.json"
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_route_family_promotion_witness_evidence_validation.json"
TARGET_WITNESS_GATES = {
    "route_binding_gate",
    "lifecycle_gate",
    "authority_upgrade_gate",
    "product_specific_boundary_gate",
}
TARGET_WITNESSED_EVIDENCE = {
    "missing_selected_component_route_binding",
    "missing_lifecycle_transition_receipt",
    "missing_authority_upgrade_witness",
    "generic_connector_surface_not_product_specific_authority",
}
REQUIRED_APPROVAL_EVIDENCE = {
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionWitnessEvidenceValidation:
    """Schema and semantic validation report for promotion witness evidence."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    witness_record_count: int
    remaining_unwitnessed_blocker_count: int
    approval_evidence_required_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_witness_evidence(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionWitnessEvidenceValidation:
    """Validate promotion witness evidence schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion witness evidence schema", errors)
    example = _load_json_object(example_path, "component route-family promotion witness evidence example", errors)

    requirements_validation = validate_component_route_family_promotion_witness_requirements()
    if not requirements_validation.ok:
        errors.extend(
            f"component route-family promotion witness requirements validation failed: {error}"
            for error in requirements_validation.errors
        )

    runtime_report = build_component_route_family_promotion_witness_evidence()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_evidence_semantics(example, errors, _path_label(example_path))
    _validate_evidence_semantics(runtime_report, errors, "runtime component route-family promotion witness evidence")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionWitnessEvidenceValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        witness_record_count=int(summary.get("witness_record_count", 0)) if isinstance(summary, dict) else 0,
        remaining_unwitnessed_blocker_count=(
            int(summary.get("remaining_unwitnessed_blocker_count", 0)) if isinstance(summary, dict) else 0
        ),
        approval_evidence_required_count=(
            int(summary.get("approval_evidence_required_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_witness_evidence_validation(
    validation: ComponentRouteFamilyPromotionWitnessEvidenceValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic promotion witness evidence validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_evidence_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("evidence_decision") != "denied":
        errors.append(f"{label}: evidence_decision must be denied")
    if report.get("witness_evidence_is_not_execution_authority") is not True:
        errors.append(f"{label}: witness evidence must not be execution authority")
    for field_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
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

    witness_records = report.get("witness_records")
    summary = report.get("summary")
    if not isinstance(witness_records, list) or not witness_records:
        errors.append(f"{label}: witness_records must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    witness_ids = [str(record.get("witness_id")) for record in witness_records if isinstance(record, dict)]
    if len(witness_ids) != len(set(witness_ids)):
        errors.append(f"{label}: witness_ids must be unique")

    observed_gate_ids: set[str] = set()
    witnessed_evidence_keys: set[str] = set()
    witnessed_blocker_count = 0
    satisfied_requirement_count = 0
    for record in witness_records:
        if not isinstance(record, dict):
            errors.append(f"{label}: witness_records entries must be objects")
            continue
        gate_id = str(record.get("gate_id", ""))
        observed_gate_ids.add(gate_id)
        witnessed_evidence_keys.add(str(record.get("evidence_key", "")))
        if record.get("proof_state") != "Fail":
            errors.append(f"{label}: witness {gate_id} proof_state must remain Fail")
        if record.get("witness_state") != "present_denial":
            errors.append(f"{label}: witness {gate_id} must be present_denial")
        if record.get("satisfies_requirement") is not False:
            errors.append(f"{label}: witness {gate_id} must not satisfy requirement")
        if record.get("blocks_promotion") is not True:
            errors.append(f"{label}: witness {gate_id} must block promotion")
        if record.get("required_before_promotion") is not True:
            errors.append(f"{label}: witness {gate_id} must be required before promotion")
        for field_name in (
            "witness_is_not_execution_authority",
        ):
            if record.get(field_name) is not True:
                errors.append(f"{label}: witness {gate_id} {field_name} must be true")
        for field_name in (
            "mutates_router_inventory",
            "grants_execution_authority",
            "grants_connector_authority",
            "grants_terminal_closure",
        ):
            if record.get(field_name) is not False:
                errors.append(f"{label}: witness {gate_id} {field_name} must be false")
        if not record.get("denial_reason"):
            errors.append(f"{label}: witness {gate_id} must carry denial_reason")
        if not record.get("source_refs"):
            errors.append(f"{label}: witness {gate_id} must carry source_refs")
        if record.get("blocks_promotion") is True:
            witnessed_blocker_count += 1
        if record.get("satisfies_requirement") is True:
            satisfied_requirement_count += 1

    if observed_gate_ids != TARGET_WITNESS_GATES:
        errors.append(f"{label}: witness_records must cover exactly {sorted(TARGET_WITNESS_GATES)}")
    if witnessed_evidence_keys != TARGET_WITNESSED_EVIDENCE:
        errors.append(f"{label}: witnessed evidence keys must cover all hard blocker denials")
    if set(_string_list(report.get("witnessed_evidence_keys"))) != TARGET_WITNESSED_EVIDENCE:
        errors.append(f"{label}: witnessed_evidence_keys must match witness records")
    if set(_string_list(report.get("remaining_missing_evidence"))) != set():
        errors.append(f"{label}: remaining_missing_evidence must be empty after all blockers are witnessed as denials")
    approval_evidence_required = set(_string_list(report.get("approval_evidence_required")))
    if not REQUIRED_APPROVAL_EVIDENCE <= approval_evidence_required:
        errors.append(f"{label}: approval_evidence_required omits required approval evidence")

    expected_counts = {
        "witness_record_count": len(witness_records),
        "witnessed_blocker_count": witnessed_blocker_count,
        "satisfied_requirement_count": satisfied_requirement_count,
        "unsatisfied_requirement_count": len(witness_records) - satisfied_requirement_count,
        "remaining_unwitnessed_blocker_count": 0,
        "original_missing_requirement_count": 4,
        "approval_evidence_required_count": len(approval_evidence_required),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match witness evidence records")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_witness_evidence_receipt",
        "component_route_family_promotion_approval_candidates_receipt",
        "component_route_family_promotion_approval_intake_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_witness_requirements_receipt",
        "component_route_binding_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "authority_denial_receipt",
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
    """Parse promotion witness evidence validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness promotion witness evidence.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for promotion witness evidence validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_witness_evidence(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_witness_evidence_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION WITNESS EVIDENCE VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
