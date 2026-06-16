#!/usr/bin/env python3
"""Validate router-inventory delta witness remediation evidence request status ledgers."""

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
from mcoi_runtime.app.component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger import (  # noqa: E402
    WITNESS_REQUIREMENTS,
    build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger,
)
from scripts.validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request import (  # noqa: E402
    validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validation.json"
)
REQUIREMENT_SET = set(WITNESS_REQUIREMENTS)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerValidation:
    """Schema and semantic validation report for remediation request status ledger."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    status_record_count: int
    awaiting_operator_evidence_count: int
    submitted_evidence_count: int
    accepted_evidence_count: int
    rejected_evidence_count: int
    witness_mint_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerValidation:
    """Validate remediation request status ledger schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "router-inventory delta witness remediation evidence request status ledger schema", errors)
    example = _load_json_object(example_path, "router-inventory delta witness remediation evidence request status ledger example", errors)

    request_validation = validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request()
    if not request_validation.ok:
        errors.extend(
            f"router-inventory delta witness remediation evidence request validation failed: {error}"
            for error in request_validation.errors
        )

    runtime_report = (
        build_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger()
    )
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_status_ledger_semantics(example, errors, _path_label(example_path))
    _validate_status_ledger_semantics(
        runtime_report,
        errors,
        "runtime router-inventory delta witness remediation evidence request status ledger",
    )

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_report.get("target_product_bundle_id", "")),
        decision=str(runtime_report.get("decision", "")),
        status_record_count=int(summary.get("status_record_count", 0)) if isinstance(summary, dict) else 0,
        awaiting_operator_evidence_count=int(summary.get("awaiting_operator_evidence_count", 0))
        if isinstance(summary, dict)
        else 0,
        submitted_evidence_count=int(summary.get("submitted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        rejected_evidence_count=int(summary.get("rejected_evidence_count", 0)) if isinstance(summary, dict) else 0,
        witness_mint_count=int(summary.get("witness_mint_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validation(
    validation: ComponentRouteFamilyPromotionRouterInventoryDeltaWitnessRemediationEvidenceRequestStatusLedgerValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic remediation request status ledger validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_status_ledger_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "ledger_state": "request_status_only",
        "source_evidence_request_state": "requested_not_submitted",
        "promotion_decision": "blocked_router_inventory_delta_witness_evidence_request_status_pending",
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    for field_name, expected_value in expected_strings.items():
        if report.get(field_name) != expected_value:
            errors.append(f"{label}: {field_name} must be {expected_value}")
    for field_name in (
        "governed",
        "status_ledger_issued",
        "status_ledger_is_not_evidence",
        "status_ledger_is_not_submission",
        "status_ledger_is_not_acceptance",
        "status_ledger_is_not_rejection",
        "status_ledger_is_not_authorization",
        "status_ledger_is_not_witness",
        "status_ledger_is_not_delta",
        "status_ledger_is_not_authority_grant",
        "status_ledger_is_not_promotion_approval",
        "status_ledger_is_not_terminal_closure",
        "source_evidence_request_required",
        "source_evidence_request_present",
        "requirements_unmet",
        "evidence_required",
        "operator_input_required",
        "witness_minting_denied",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "evidence_submitted",
        "evidence_accepted",
        "evidence_rejected",
        "requirements_satisfied",
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "router_inventory_delta_authorized",
        "selected_component_binding_created",
        "route_binding_authorized",
        "lifecycle_transition_authorized",
        "authority_granted",
        "promotion_approved",
        "terminal_certificate_minted",
        "terminal_closure_claimed",
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
        "accepted_evidence_refs",
        "submitted_evidence_refs",
        "rejected_evidence_refs",
        "authorization_refs",
        "router_inventory_delta_witness_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate evidence exists")

    records = report.get("status_records")
    summary = report.get("summary")
    if not isinstance(records, list) or len(records) != len(REQUIREMENT_SET):
        errors.append(f"{label}: status_records must contain six records")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if set(_string_list([record.get("requirement_artifact") for record in records if isinstance(record, dict)])) != REQUIREMENT_SET:
        errors.append(f"{label}: status record artifacts must match required set")
    if _string_list(report.get("status_record_refs")) != [
        str(record.get("status_record_id")) for record in records if isinstance(record, dict)
    ]:
        errors.append(f"{label}: status_record_refs must match status record ids")
    if len(_string_list(report.get("source_evidence_request_refs"))) != 1:
        errors.append(f"{label}: source_evidence_request_refs must contain one source request")
    if len(_string_list(report.get("source_evidence_request_slot_refs"))) != len(REQUIREMENT_SET):
        errors.append(f"{label}: source_evidence_request_slot_refs must contain six source slots")

    for record in records:
        if not isinstance(record, dict):
            errors.append(f"{label}: status_records entries must be objects")
            continue
        _validate_status_record(record, errors, label)

    expected_counts = {
        "source_evidence_request_count": len(_string_list(report.get("source_evidence_request_refs"))),
        "source_evidence_request_slot_count": len(_string_list(report.get("source_evidence_request_slot_refs"))),
        "status_record_count": len(records),
        "awaiting_operator_evidence_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("status") == "awaiting_operator_evidence"
        ),
        "operator_input_required_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("operator_input_required") is True
        ),
        "submitted_evidence_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("evidence_submitted") is True
        ),
        "accepted_evidence_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("evidence_accepted") is True
        ),
        "rejected_evidence_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("evidence_rejected") is True
        ),
        "satisfied_requirement_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("requirement_satisfied") is True
        ),
        "unknown_proof_state_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("proof_state") == "Unknown"
        ),
        "witness_minting_authorization_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("witness_minting_authorized") is True
        ),
        "witness_mint_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("witness_minted") is True
        ),
        "applied_delta_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("delta_applied") is True
        ),
        "router_inventory_mutation_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("router_inventory_mutated") is True
        ),
        "authority_grant_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("authority_granted") is True
        ),
        "promotion_approval_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("promotion_approved") is True
        ),
        "terminal_closure_claim_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("terminal_closure_claimed") is True
        ),
        "blocking_status_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("blocks_witness_minting") is True
        ),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match status records")


def _validate_status_record(record: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "target_surface_id": "governed_connector_framework",
        "target_component_id": "gmail_account_binding_gate",
        "target_product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
        "status": "awaiting_operator_evidence",
        "proof_state": "Unknown",
    }
    for field_name, expected_value in expected_strings.items():
        if record.get(field_name) != expected_value:
            errors.append(f"{label}: status record {field_name} must be {expected_value}")
    if record.get("requirement_artifact") not in REQUIREMENT_SET:
        errors.append(f"{label}: status record requirement_artifact must be in required set")
    for field_name in (
        "required",
        "status_only",
        "evidence_required",
        "operator_input_required",
        "blocks_witness_minting",
        "blocks_promotion",
        "status_is_not_evidence",
        "status_is_not_submission",
        "status_is_not_acceptance",
        "status_is_not_rejection",
        "status_is_not_authorization",
        "status_is_not_witness",
        "status_is_not_delta",
        "status_is_not_authority_grant",
        "status_is_not_promotion_approval",
        "status_is_not_terminal_closure",
    ):
        if record.get(field_name) is not True:
            errors.append(f"{label}: status record {field_name} must be true")
    for field_name in (
        "evidence_submitted",
        "evidence_accepted",
        "evidence_rejected",
        "authorization_present",
        "requirement_satisfied",
        "witness_minting_authorized",
        "witness_minted",
        "delta_applied",
        "router_inventory_mutated",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_claimed",
    ):
        if record.get(field_name) is not False:
            errors.append(f"{label}: status record {field_name} must be false")
    for field_name in (
        "submitted_evidence_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
        "authorization_refs",
        "witness_refs",
        "router_inventory_delta_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(record.get(field_name)):
            errors.append(f"{label}: status record {field_name} must remain empty")
    if _string_list(record.get("source_evidence_request_refs")) != [str(record.get("source_evidence_request_id"))]:
        errors.append(f"{label}: status record source_evidence_request_refs must match source request")
    if _string_list(record.get("source_evidence_request_slot_refs")) != [
        str(record.get("source_evidence_request_slot_id"))
    ]:
        errors.append(f"{label}: status record source_evidence_request_slot_refs must match source slot")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} missing: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, default=DEFAULT_EXAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="write validation receipt")
    parser.add_argument("--strict", action="store_true", help="return non-zero on validation failure")
    args = parser.parse_args(argv)

    validation = (
        validate_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger(
            schema_path=args.schema,
            example_path=args.example,
        )
    )
    if args.write:
        write_component_route_family_promotion_router_inventory_delta_witness_remediation_evidence_request_status_ledger_validation(
            validation,
            args.output,
        )
    if validation.ok:
        print(
            "COMPONENT ROUTE FAMILY PROMOTION ROUTER INVENTORY DELTA WITNESS REMEDIATION EVIDENCE REQUEST STATUS LEDGER VALID"
        )
        return 0
    for error in validation.errors:
        print(f"ERROR: {error}")
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
