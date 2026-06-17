#!/usr/bin/env python3
"""Validate Component Harness route-family promotion approval candidates.

Purpose: prove blocked promotion gates have draft approval candidates without
approving promotion, mutating router inventory, or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: approval candidates schema/example, runtime builder, and
promotion witness evidence validation.
Invariants:
  - Approval candidates remain draft-only and not approved.
  - Candidate records do not satisfy promotion requirements.
  - Candidate records cannot grant execution, connector, mutation, or terminal
    closure authority.
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

from mcoi_runtime.app.component_route_family_promotion_approval_candidates import (  # noqa: E402
    build_component_route_family_promotion_approval_candidates,
)
from scripts.validate_component_route_family_promotion_witness_evidence import (  # noqa: E402
    validate_component_route_family_promotion_witness_evidence,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_approval_candidates.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT / "examples" / "component_route_family_promotion_approval_candidates.governed_connector_framework.json"
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_route_family_promotion_approval_candidates_validation.json"
TARGET_CANDIDATE_GATES = {
    "route_binding_gate",
    "lifecycle_gate",
    "authority_upgrade_gate",
    "product_specific_boundary_gate",
}
REQUIRED_APPROVAL_EVIDENCE = {
    "selected_component_bound_router_inventory_delta",
    "component_lifecycle_transition_receipt",
    "authority_upgrade_witness",
    "product_specific_ownership_decision",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionApprovalCandidatesValidation:
    """Schema and semantic validation report for promotion approval candidates."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    approval_candidate_count: int
    approval_evidence_required_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_approval_candidates(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionApprovalCandidatesValidation:
    """Validate approval candidates schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion approval candidates schema", errors)
    example = _load_json_object(example_path, "component route-family promotion approval candidates example", errors)

    evidence_validation = validate_component_route_family_promotion_witness_evidence()
    if not evidence_validation.ok:
        errors.extend(
            f"component route-family promotion witness evidence validation failed: {error}"
            for error in evidence_validation.errors
        )

    runtime_report = build_component_route_family_promotion_approval_candidates()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_candidates_semantics(example, errors, _path_label(example_path))
    _validate_candidates_semantics(runtime_report, errors, "runtime component route-family promotion approval candidates")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionApprovalCandidatesValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        approval_candidate_count=int(summary.get("approval_candidate_count", 0)) if isinstance(summary, dict) else 0,
        approval_evidence_required_count=(
            int(summary.get("approval_evidence_required_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_approval_candidates_validation(
    validation: ComponentRouteFamilyPromotionApprovalCandidatesValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic promotion approval candidates validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_candidates_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("candidate_decision") != "not_approved":
        errors.append(f"{label}: candidate_decision must be not_approved")
    if report.get("approval_candidates_are_not_execution_authority") is not True:
        errors.append(f"{label}: approval candidates must not be execution authority")
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

    candidates = report.get("approval_candidates")
    summary = report.get("summary")
    if not isinstance(candidates, list) or not candidates:
        errors.append(f"{label}: approval_candidates must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    candidate_ids = [str(candidate.get("candidate_id")) for candidate in candidates if isinstance(candidate, dict)]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append(f"{label}: candidate_ids must be unique")

    observed_gates: set[str] = set()
    not_approved_count = 0
    draft_count = 0
    blocking_count = 0
    satisfied_count = 0
    reported_approval_evidence_required = set(_string_list(report.get("approval_evidence_required")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_approval_evidence_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    approval_evidence_required = set(reported_approval_evidence_required)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append(f"{label}: approval_candidates entries must be objects")
            continue
        gate_id = str(candidate.get("gate_id", ""))
        observed_gates.add(gate_id)
        approval_evidence_required.update(_string_list(candidate.get("approval_required_artifacts")))
        approval_evidence_required.update(_string_list(candidate.get("approval_preconditions")))
        if candidate.get("approval_state") != "not_approved":
            errors.append(f"{label}: candidate {gate_id} approval_state must be not_approved")
        if candidate.get("candidate_state") != "draft_only":
            errors.append(f"{label}: candidate {gate_id} candidate_state must be draft_only")
        if candidate.get("proof_state") != "Unknown":
            errors.append(f"{label}: candidate {gate_id} proof_state must be Unknown")
        if candidate.get("satisfies_requirement") is not False:
            errors.append(f"{label}: candidate {gate_id} must not satisfy requirement")
        if candidate.get("blocks_promotion") is not True:
            errors.append(f"{label}: candidate {gate_id} must block promotion")
        for field_name in ("requires_operator_approval", "required_before_promotion", "approval_would_replace_denial"):
            if candidate.get(field_name) is not True:
                errors.append(f"{label}: candidate {gate_id} {field_name} must be true")
        if candidate.get("candidate_is_not_execution_authority") is not True:
            errors.append(f"{label}: candidate {gate_id} candidate_is_not_execution_authority must be true")
        for field_name in (
            "mutates_router_inventory",
            "grants_execution_authority",
            "grants_connector_authority",
            "grants_terminal_closure",
        ):
            if candidate.get(field_name) is not False:
                errors.append(f"{label}: candidate {gate_id} {field_name} must be false")
        if not candidate.get("approval_required_artifacts"):
            errors.append(f"{label}: candidate {gate_id} must carry approval_required_artifacts")
        if not candidate.get("approval_preconditions"):
            errors.append(f"{label}: candidate {gate_id} must carry approval_preconditions")
        if candidate.get("approval_state") == "not_approved":
            not_approved_count += 1
        if candidate.get("candidate_state") == "draft_only":
            draft_count += 1
        if candidate.get("blocks_promotion") is True:
            blocking_count += 1
        if candidate.get("satisfies_requirement") is True:
            satisfied_count += 1

    if observed_gates != TARGET_CANDIDATE_GATES:
        errors.append(f"{label}: approval_candidates must cover exactly {sorted(TARGET_CANDIDATE_GATES)}")
    if reported_approval_evidence_required != approval_evidence_required:
        errors.append(f"{label}: approval_evidence_required must match candidate artifacts and preconditions")

    expected_counts = {
        "approval_candidate_count": len(candidates),
        "not_approved_candidate_count": not_approved_count,
        "draft_only_candidate_count": draft_count,
        "satisfied_requirement_count": satisfied_count,
        "blocking_candidate_count": blocking_count,
        "approval_evidence_required_count": len(approval_evidence_required),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match approval candidates")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_approval_candidates_receipt",
        "component_route_family_promotion_approval_intake_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_witness_evidence_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "operator_approval_required_receipt",
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
    """Parse promotion approval candidates validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness promotion approval candidates.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for promotion approval candidates validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_approval_candidates(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_approval_candidates_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION APPROVAL CANDIDATES VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
