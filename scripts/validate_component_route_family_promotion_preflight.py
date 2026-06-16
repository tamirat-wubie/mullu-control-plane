#!/usr/bin/env python3
"""Validate Component Harness route-family promotion preflight artifacts.

Purpose: prove blocked route-family promotion attempts fail closed with exact
missing evidence and no execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_route_family_promotion_preflight.schema.json,
examples/component_route_family_promotion_preflight.governed_connector_framework.json,
component route-family promotion preflight runtime, and ownership readiness
validation.
Invariants:
  - Promotion preflight cannot approve promotion in foundation mode.
  - Failed hard gates must carry missing evidence keys.
  - Terminal closure stays blocked.
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

from mcoi_runtime.app.component_route_family_promotion_preflight import (  # noqa: E402
    build_component_route_family_promotion_preflight,
)
from scripts.validate_component_route_family_ownership import (  # noqa: E402
    validate_component_route_family_ownership,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_preflight.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT / "examples" / "component_route_family_promotion_preflight.governed_connector_framework.json"
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_route_family_promotion_preflight_validation.json"


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionPreflightValidation:
    """Schema and semantic validation report for promotion preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    failed_gate_count: int
    missing_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionPreflightValidation:
    """Validate promotion preflight schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion preflight schema", errors)
    example = _load_json_object(example_path, "component route-family promotion preflight example", errors)

    ownership_validation = validate_component_route_family_ownership()
    if not ownership_validation.ok:
        errors.extend(
            f"component route-family ownership validation failed: {error}"
            for error in ownership_validation.errors
        )

    runtime_report = build_component_route_family_promotion_preflight()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_preflight_semantics(example, errors, _path_label(example_path))
    _validate_preflight_semantics(runtime_report, errors, "runtime component route-family promotion preflight")

    gate_results = runtime_report.get("gate_results", [])
    missing_evidence = runtime_report.get("missing_evidence", [])
    return ComponentRouteFamilyPromotionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        failed_gate_count=sum(
            1 for gate in gate_results if isinstance(gate, dict) and gate.get("proof_state") == "Fail"
        )
        if isinstance(gate_results, list)
        else 0,
        missing_evidence_count=len(missing_evidence) if isinstance(missing_evidence, list) else 0,
    )


def write_component_route_family_promotion_preflight_validation(
    validation: ComponentRouteFamilyPromotionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic promotion preflight validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_preflight_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("outcome") != "GovernanceBlocked":
        errors.append(f"{label}: outcome must be GovernanceBlocked")
    if report.get("promotion_preflight_is_not_execution_authority") is not True:
        errors.append(f"{label}: promotion preflight must not be execution authority")
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

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")

    snapshot = report.get("route_family_snapshot")
    if not isinstance(snapshot, dict):
        errors.append(f"{label}: route_family_snapshot must be an object")
    else:
        if snapshot.get("surface_id") != report.get("target_surface_id"):
            errors.append(f"{label}: snapshot surface must match target surface")
        if snapshot.get("readiness_state") == "selected_component_bound":
            errors.append(f"{label}: promotion preflight must target a blocked route family")
        if report.get("target_component_id") not in _string_list(snapshot.get("component_ids")):
            errors.append(f"{label}: target component must be a candidate component")
        if not _string_list(snapshot.get("promotion_blockers")):
            errors.append(f"{label}: blocked route family must list promotion blockers")

    gate_results = report.get("gate_results")
    if not isinstance(gate_results, list) or not gate_results:
        errors.append(f"{label}: gate_results must be non-empty")
        return
    failed_evidence = sorted(
        {
            str(gate.get("evidence_key"))
            for gate in gate_results
            if isinstance(gate, dict) and gate.get("proof_state") == "Fail"
        }
    )
    missing_evidence = sorted(_string_list(report.get("missing_evidence")))
    if missing_evidence != failed_evidence:
        errors.append(f"{label}: missing_evidence must match failed gate evidence keys")
    required_failed_evidence = {
        "missing_selected_component_route_binding",
        "missing_lifecycle_transition_receipt",
        "missing_authority_upgrade_witness",
        "generic_connector_surface_not_product_specific_authority",
    }
    missing_required = sorted(required_failed_evidence - set(missing_evidence))
    if missing_required:
        errors.append(f"{label}: missing_evidence omits required blockers {missing_required}")
    gate_ids = [str(gate.get("gate_id")) for gate in gate_results if isinstance(gate, dict)]
    if len(gate_ids) != len(set(gate_ids)):
        errors.append(f"{label}: gate_ids must be unique")
    for gate in gate_results:
        if not isinstance(gate, dict):
            errors.append(f"{label}: gate entries must be objects")
            continue
        if gate.get("gate_is_not_execution_authority") is not True:
            errors.append(f"{label}: gate {gate.get('gate_id')} must not be execution authority")
    if report.get("target_surface_id") != "governed_connector_framework":
        errors.append(f"{label}: target_surface_id must remain governed_connector_framework")
    if report.get("target_component_id") != "gmail_account_binding_gate":
        errors.append(f"{label}: target_component_id must remain gmail_account_binding_gate")

    expected_receipts = set(_string_list(report.get("expected_receipts")))
    if "component_route_family_promotion_preflight_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include promotion preflight receipt")
    if "component_route_family_promotion_witness_requirements_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include promotion witness requirements receipt")
    if "component_route_family_promotion_witness_evidence_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include promotion witness evidence receipt")
    if "component_route_family_promotion_approval_candidates_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include promotion approval candidates receipt")
    if "component_route_family_promotion_approval_intake_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include promotion approval intake receipt")
    if "component_route_family_promotion_submitted_evidence_verifier_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include submitted-evidence verifier receipt")
    if "component_route_family_promotion_submitted_evidence_records_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include submitted-evidence records receipt")
    if "component_route_family_promotion_operator_submitted_evidence_records_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include operator-submitted evidence records receipt")
    if "component_route_family_promotion_gate_satisfaction_evaluator_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include gate-satisfaction evaluator receipt")
    if "component_route_family_promotion_submitted_evidence_payload_examples_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include submitted-evidence payload examples receipt")
    if "authority_denial_receipt" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include authority_denial_receipt")
    if "component_authority_envelope_witness" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include component_authority_envelope_witness")
    if "authority_upgrade_witness" not in expected_receipts:
        errors.append(f"{label}: expected_receipts must include authority_upgrade_witness")


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
    """Parse promotion preflight validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness route-family promotion preflight.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for route-family promotion preflight validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_preflight(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION PREFLIGHT VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
