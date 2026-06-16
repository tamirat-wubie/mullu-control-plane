#!/usr/bin/env python3
"""Validate Component Harness route-family ownership readiness artifacts.

Purpose: prove route-family ownership readiness is generated from registry,
router inventory, and proof binding evidence without granting execution
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_route_family_ownership.schema.json,
examples/component_route_family_ownership.foundation.json, component
route-family ownership runtime, and component harness validators.
Invariants:
  - Platform-classified route families remain blocked until proof, lifecycle,
    route-binding, and authority witnesses exist.
  - Selected component-bound route families do not imply live execution.
  - Ownership readiness cannot claim terminal closure.
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

from mcoi_runtime.app.component_route_family_ownership import (  # noqa: E402
    build_component_route_family_ownership_report,
)
from scripts.validate_component_proof_binding import validate_component_proof_binding  # noqa: E402
from scripts.validate_component_registry import validate_component_registry  # noqa: E402
from scripts.validate_component_router_inventory import validate_component_router_inventory  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_ownership.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_route_family_ownership.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_route_family_ownership_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyOwnershipValidation:
    """Schema and semantic validation report for route-family ownership."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    route_family_count: int
    declared_route_count: int
    selected_component_bound_count: int
    promotion_blocked_count: int
    proof_binding_gap_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_ownership(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyOwnershipValidation:
    """Validate ownership readiness schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family ownership schema", errors)
    example = _load_json_object(example_path, "component route-family ownership example", errors)

    registry_validation = validate_component_registry()
    if not registry_validation.ok:
        errors.extend(f"component registry validation failed: {error}" for error in registry_validation.errors)
    router_validation = validate_component_router_inventory()
    if not router_validation.ok:
        errors.extend(f"component router inventory validation failed: {error}" for error in router_validation.errors)
    proof_binding_validation = validate_component_proof_binding()
    if not proof_binding_validation.ok:
        errors.extend(f"component proof binding validation failed: {error}" for error in proof_binding_validation.errors)

    runtime_report = build_component_route_family_ownership_report()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_ownership_semantics(example, errors, _path_label(example_path))
    _validate_ownership_semantics(runtime_report, errors, "runtime component route-family ownership")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyOwnershipValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        route_family_count=int(summary.get("route_family_count", 0)) if isinstance(summary, dict) else 0,
        declared_route_count=int(summary.get("declared_route_count", 0)) if isinstance(summary, dict) else 0,
        selected_component_bound_count=(
            int(summary.get("selected_component_bound_count", 0)) if isinstance(summary, dict) else 0
        ),
        promotion_blocked_count=int(summary.get("promotion_blocked_count", 0)) if isinstance(summary, dict) else 0,
        proof_binding_gap_count=int(summary.get("proof_binding_gap_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_ownership_validation(
    validation: ComponentRouteFamilyOwnershipValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic route-family ownership validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_ownership_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("ownership_readiness_is_not_execution_authority") is not True:
        errors.append(f"{label}: ownership readiness must not be execution authority")
    for field_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
    ):
        if report.get(field_name) is not False:
            errors.append(f"{label}: {field_name} must be false")
    if report.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")

    summary = report.get("summary")
    records = report.get("ownership_records")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if not isinstance(records, list) or not records:
        errors.append(f"{label}: ownership_records must be non-empty")
        return

    surface_ids = [str(record.get("surface_id")) for record in records if isinstance(record, dict)]
    if len(surface_ids) != len(set(surface_ids)):
        errors.append(f"{label}: ownership record surface_ids must be unique")
    if summary.get("route_family_count") != len(records):
        errors.append(f"{label}: summary.route_family_count must match ownership_records")
    if summary.get("declared_route_count") != sum(
        int(record.get("declared_route_count", 0))
        for record in records
        if isinstance(record, dict)
    ):
        errors.append(f"{label}: summary.declared_route_count must match ownership_records")

    selected_count = 0
    platform_count = 0
    blocked_count = 0
    proof_gap_count = 0
    route_gap_count = 0
    connector_boundary_count = 0
    for record in records:
        if not isinstance(record, dict):
            errors.append(f"{label}: ownership record entries must be objects")
            continue
        surface_id = str(record.get("surface_id", "<missing>"))
        readiness_state = str(record.get("readiness_state", ""))
        binding_level = str(record.get("binding_level", ""))
        blockers = set(_string_list(record.get("promotion_blockers")))
        selected_bound_components = _string_list(record.get("selected_bound_component_ids"))
        candidate_proof_components = _string_list(record.get("candidate_proof_bound_component_ids"))
        blocked_actions = set(_string_list(record.get("blocked_actions")))
        if record.get("ownership_is_not_execution_authority") is not True:
            errors.append(f"{label}: {surface_id} ownership must not be execution authority")
        if record.get("can_enable_live_action") is not False:
            errors.append(f"{label}: {surface_id} cannot enable live action")
        if "route_execution" not in blocked_actions:
            errors.append(f"{label}: {surface_id} must block route_execution")
        if "terminal_closure" not in blocked_actions:
            errors.append(f"{label}: {surface_id} must block terminal_closure")
        if readiness_state == "selected_component_bound":
            selected_count += 1
            if binding_level != "selected_component_bound":
                errors.append(f"{label}: {surface_id} selected readiness requires selected binding level")
            if not selected_bound_components:
                errors.append(f"{label}: {surface_id} selected readiness requires selected bound components")
            if blockers:
                errors.append(f"{label}: {surface_id} selected readiness must not list promotion blockers")
        elif readiness_state.startswith("blocked_"):
            blocked_count += 1
            if not blockers:
                errors.append(f"{label}: {surface_id} blocked readiness must list promotion blockers")
            if "missing_selected_component_route_binding" not in blockers:
                errors.append(f"{label}: {surface_id} blocked readiness must require route binding evidence")
            if "missing_lifecycle_transition_receipt" not in blockers:
                errors.append(f"{label}: {surface_id} blocked readiness must require lifecycle evidence")
            if "missing_authority_upgrade_witness" not in blockers:
                errors.append(f"{label}: {surface_id} blocked readiness must require authority evidence")
            if readiness_state == "blocked_needs_proof_binding" and candidate_proof_components:
                errors.append(f"{label}: {surface_id} proof-binding blocker contradicts candidate proof evidence")
            if readiness_state == "blocked_needs_route_binding_witness" and not candidate_proof_components:
                errors.append(f"{label}: {surface_id} route-binding blocker requires candidate proof evidence")
        else:
            errors.append(f"{label}: {surface_id} readiness_state is not governed")

        if binding_level == "platform_family_classified":
            platform_count += 1
        if "missing_component_proof_surface_binding" in blockers:
            proof_gap_count += 1
        if "missing_selected_component_route_binding" in blockers:
            route_gap_count += 1
        if "generic_connector_surface_not_product_specific_authority" in blockers:
            connector_boundary_count += 1

    expected_counts = {
        "selected_component_bound_count": selected_count,
        "platform_family_classified_count": platform_count,
        "promotion_blocked_count": blocked_count,
        "proof_binding_gap_count": proof_gap_count,
        "route_binding_gap_count": route_gap_count,
        "generic_connector_boundary_count": connector_boundary_count,
        "live_action_enabled_count": 0,
        "terminal_closure_claim_count": 0,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match ownership_records")

    expected_receipts = set(_string_list(report.get("expected_receipts")))
    if "component_route_family_ownership_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include component_route_family_ownership_receipt")
    if "authority_denial_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include authority_denial_receipt")
    if "component_authority_envelope_witness" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include component_authority_envelope_witness")
    if "authority_upgrade_witness" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include authority_upgrade_witness")
    if report.get("outcome") not in {"AwaitingEvidence", "SolvedUnverified"}:
        errors.append(f"{label}: outcome is not a governed solver outcome")


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
    """Parse route-family ownership validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness route-family ownership readiness.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for route-family ownership validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_ownership(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_ownership_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY OWNERSHIP VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
