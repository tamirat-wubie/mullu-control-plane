#!/usr/bin/env python3
"""Validate Component Harness promotion router-inventory delta candidates.

Purpose: prove missing-evidence ledgers can define one dry-run selected
component router-inventory delta candidate without applying a delta, mutating
router inventory, creating evidence, granting authority, approving promotion,
or claiming terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: router-inventory delta candidate schema/example, runtime
builder, and promotion missing-evidence ledger validation.
Invariants:
  - A router-inventory delta candidate is not a delta witness.
  - Candidate records cannot mutate router inventory or bind routes.
  - Candidate records cannot satisfy promotion evidence.
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

from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (  # noqa: E402
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_candidate import (  # noqa: E402
    DOWNSTREAM_REQUIRED_ARTIFACTS,
    TARGET_ARTIFACT_ID,
    build_component_route_family_promotion_router_inventory_delta_candidate,
)
from scripts.validate_component_route_family_promotion_missing_evidence_ledger import (  # noqa: E402
    validate_component_route_family_promotion_missing_evidence_ledger,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_router_inventory_delta_candidate.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_router_inventory_delta_candidate.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_router_inventory_delta_candidate_validation.json"
)
DOWNSTREAM_ARTIFACT_SET = set(DOWNSTREAM_REQUIRED_ARTIFACTS)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateValidation:
    """Schema and semantic validation report for dry-run delta candidates."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    candidate_count: int
    applied_delta_count: int
    router_inventory_mutation_count: int
    selected_component_binding_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_router_inventory_delta_candidate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateValidation:
    """Validate router-inventory delta candidate schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "router-inventory delta candidate schema", errors)
    example = _load_json_object(example_path, "router-inventory delta candidate example", errors)

    ledger_validation = validate_component_route_family_promotion_missing_evidence_ledger()
    if not ledger_validation.ok:
        errors.extend(
            f"component route-family promotion missing evidence ledger validation failed: {error}"
            for error in ledger_validation.errors
        )

    runtime_report = build_component_route_family_promotion_router_inventory_delta_candidate()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_candidate_semantics(example, errors, _path_label(example_path))
    _validate_candidate_semantics(
        runtime_report,
        errors,
        "runtime component route-family promotion router-inventory delta candidate",
    )

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        candidate_count=int(summary.get("candidate_count", 0)) if isinstance(summary, dict) else 0,
        applied_delta_count=int(summary.get("applied_delta_count", 0)) if isinstance(summary, dict) else 0,
        router_inventory_mutation_count=(
            int(summary.get("router_inventory_mutation_count", 0)) if isinstance(summary, dict) else 0
        ),
        selected_component_binding_count=(
            int(summary.get("selected_component_binding_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_router_inventory_delta_candidate_validation(
    validation: ComponentRouteFamilyPromotionRouterInventoryDeltaCandidateValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic router-inventory delta candidate validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_candidate_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "candidate_status": "draft_not_applied",
        "promotion_decision": "blocked_router_inventory_delta_not_applied",
        "evidence_status": "candidate_defined_not_witnessed",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "router_inventory_delta_candidate_issued",
        "router_inventory_delta_candidate_is_not_delta",
        "router_inventory_delta_candidate_is_not_evidence",
        "router_inventory_delta_candidate_is_not_witness",
        "router_inventory_delta_candidate_is_not_route_binding",
        "router_inventory_delta_candidate_is_not_authority_grant",
        "router_inventory_delta_candidate_is_not_promotion_approval",
        "router_inventory_delta_candidate_is_not_terminal_closure",
        "separate_router_inventory_delta_required",
        "separate_route_binding_receipt_required",
        "separate_lifecycle_transition_receipt_required",
        "separate_authority_upgrade_witness_required",
        "separate_product_ownership_witness_required",
        "separate_terminal_closure_certificate_required",
        "dry_run_only",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "delta_applied",
        "router_inventory_mutated",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "selected_component_binding_created",
        "route_binding_authorized",
        "lifecycle_transition_authorized",
        "authority_upgrade_authorized",
        "authority_granted",
        "promotion_approved",
        "terminal_certificate_minted",
        "terminal_closure_authorized",
        "terminal_closure_claimed",
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
    for field_name in (
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "route_binding_receipt_refs",
        "lifecycle_transition_receipt_refs",
        "authority_upgrade_witness_refs",
        "authority_grant_refs",
        "product_ownership_witness_refs",
        "terminal_closure_certificate_refs",
        "terminal_closure_refs",
        "promotion_approval_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until a separate delta witness exists")

    candidates = report.get("router_inventory_delta_candidates")
    summary = report.get("summary")
    if not isinstance(candidates, list) or len(candidates) != 1:
        errors.append(f"{label}: router_inventory_delta_candidates must contain exactly one candidate")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        errors.append(f"{label}: router_inventory_delta_candidates entries must be objects")
        return
    _validate_candidate(candidate, errors, label)

    if _string_list(report.get("router_inventory_delta_candidate_refs")) != [str(candidate.get("candidate_id"))]:
        errors.append(f"{label}: router_inventory_delta_candidate_refs must match candidate_id")
    if _string_list(report.get("source_missing_evidence_record_refs")) != [
        str(candidate.get("source_missing_evidence_id"))
    ]:
        errors.append(f"{label}: source_missing_evidence_record_refs must match source missing evidence id")
    if set(_string_list(report.get("required_downstream_artifacts"))) != DOWNSTREAM_ARTIFACT_SET:
        errors.append(f"{label}: required_downstream_artifacts must match downstream artifact set")

    expected_counts = {
        "candidate_count": 1,
        "draft_candidate_count": 1 if candidate.get("candidate_state") == "draft_not_applied" else 0,
        "applied_delta_count": 1 if candidate.get("delta_applied") is True else 0,
        "present_evidence_count": 1 if candidate.get("evidence_present") is True else 0,
        "witness_emission_count": 1 if candidate.get("witness_emitted") is True else 0,
        "router_inventory_mutation_count": 1 if candidate.get("router_inventory_mutated") is True else 0,
        "router_inventory_delta_authorization_count": (
            1 if candidate.get("router_inventory_delta_authorized") is True else 0
        ),
        "selected_component_binding_count": (
            1 if candidate.get("selected_component_binding_created") is True else 0
        ),
        "route_binding_authorization_count": 1 if candidate.get("route_binding_authorized") is True else 0,
        "authority_grant_count": 1 if candidate.get("authority_granted") is True else 0,
        "promotion_approval_count": 1 if candidate.get("promotion_approved") is True else 0,
        "terminal_closure_authorization_count": 1 if candidate.get("terminal_closure_authorized") is True else 0,
        "terminal_closure_claim_count": 1 if candidate.get("terminal_closure_claimed") is True else 0,
        "accepted_evidence_count": len(_string_list(candidate.get("accepted_evidence_refs"))),
        "required_downstream_artifact_count": len(_string_list(candidate.get("required_downstream_artifacts"))),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match router-inventory delta candidate")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("router_inventory_mutation", "selected_component_binding", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")


def _validate_candidate(candidate: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "artifact_id": TARGET_ARTIFACT_ID,
        "candidate_state": "draft_not_applied",
        "delta_kind": "selected_component_bound_router_inventory_delta",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "source_evidence_state": "missing",
        "source_proof_state": "Unknown",
        "proposed_binding_state": "selected_component_bound",
    }
    for field_name, expected_value in expected_strings.items():
        if candidate.get(field_name) != expected_value:
            errors.append(f"{label}: candidate {field_name} must be {expected_value}")
    for field_name in (
        "proposed_binding_is_not_current_state",
        "dry_run_only",
        "candidate_is_not_delta",
        "candidate_is_not_evidence",
        "candidate_is_not_witness",
        "candidate_is_not_route_binding",
        "candidate_is_not_authority_grant",
        "candidate_is_not_promotion_approval",
        "candidate_is_not_terminal_closure",
    ):
        if candidate.get(field_name) is not True:
            errors.append(f"{label}: candidate {field_name} must be true")
    for field_name in (
        "delta_applied",
        "evidence_present",
        "witness_emitted",
        "router_inventory_mutated",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
        "selected_component_binding_created",
        "route_binding_authorized",
        "lifecycle_transition_authorized",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_authorized",
        "terminal_closure_claimed",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
    ):
        if candidate.get(field_name) is not False:
            errors.append(f"{label}: candidate {field_name} must be false")
    for field_name in (
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "accepted_evidence_refs",
        "witness_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(candidate.get(field_name)):
            errors.append(f"{label}: candidate {field_name} must remain empty")
    if _string_list(candidate.get("source_missing_evidence_refs")) != [
        str(candidate.get("source_missing_evidence_id"))
    ]:
        errors.append(f"{label}: source_missing_evidence_refs must contain only the source missing evidence id")
    if set(_string_list(candidate.get("required_downstream_artifacts"))) != DOWNSTREAM_ARTIFACT_SET:
        errors.append(f"{label}: candidate required_downstream_artifacts must match downstream artifact set")
    proposed_delta = candidate.get("proposed_delta")
    if not isinstance(proposed_delta, dict):
        errors.append(f"{label}: proposed_delta must be an object")
        return
    if proposed_delta.get("would_bind_surface_id") != "governed_connector_framework":
        errors.append(f"{label}: proposed_delta would_bind_surface_id must match target surface")
    if proposed_delta.get("would_bind_component_id") != "gmail_account_binding_gate":
        errors.append(f"{label}: proposed_delta would_bind_component_id must match target component")
    if proposed_delta.get("would_bind_product_bundle_id") != DEFAULT_PRODUCT_BUNDLE_ID:
        errors.append(f"{label}: proposed_delta would_bind_product_bundle_id must match target bundle")
    if proposed_delta.get("would_require_separate_witness") is not True:
        errors.append(f"{label}: proposed_delta would_require_separate_witness must be true")
    if proposed_delta.get("would_not_enable_live_action") is not True:
        errors.append(f"{label}: proposed_delta would_not_enable_live_action must be true")
    if "router_inventory_mutation" not in set(_string_list(proposed_delta.get("would_preserve_blocked_actions"))):
        errors.append(f"{label}: proposed_delta blocked actions must preserve router_inventory_mutation")


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
    """Parse router-inventory delta candidate validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness router-inventory delta candidate.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for router-inventory delta candidate validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_router_inventory_delta_candidate(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_router_inventory_delta_candidate_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION ROUTER INVENTORY DELTA CANDIDATE VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
