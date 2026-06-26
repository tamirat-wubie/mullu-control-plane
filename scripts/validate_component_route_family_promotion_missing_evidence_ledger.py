#!/usr/bin/env python3
"""Validate Component Harness promotion missing-evidence ledgers.

Purpose: prove terminal-closure denial reports can feed one blocked
missing-evidence ledger without creating evidence, witnesses, terminal
certificates, authority grants, router mutations, promotion approvals, or
closure claims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: missing-evidence ledger schema/example, runtime builder, and
promotion terminal-closure denial validation.
Invariants:
  - A missing-evidence ledger is not missing evidence.
  - Unknown required evidence keeps promotion blocked.
  - Ledger records cannot emit witnesses or authorize terminal closure.
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

from mcoi_runtime.app.component_route_family_promotion_missing_evidence_ledger import (  # noqa: E402
    MISSING_EVIDENCE_STAGES,
    build_component_route_family_promotion_missing_evidence_ledger,
)
from mcoi_runtime.app.component_route_family_promotion_product_ownership_decision_report import (  # noqa: E402
    DEFAULT_PRODUCT_BUNDLE_ID,
)
from scripts.validate_component_route_family_promotion_terminal_closure_denial_report import (  # noqa: E402
    validate_component_route_family_promotion_terminal_closure_denial_report,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_missing_evidence_ledger.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_missing_evidence_ledger.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_missing_evidence_ledger_validation.json"
)
MISSING_REQUIRED_ARTIFACTS = set(MISSING_EVIDENCE_STAGES)


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionMissingEvidenceLedgerValidation:
    """Schema and semantic validation report for missing-evidence ledgers."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    target_product_bundle_id: str
    decision: str
    missing_evidence_record_count: int
    present_evidence_count: int
    unknown_proof_state_count: int
    witness_emission_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_missing_evidence_ledger(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionMissingEvidenceLedgerValidation:
    """Validate missing-evidence ledger schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "missing-evidence ledger schema", errors)
    example = _load_json_object(example_path, "missing-evidence ledger example", errors)

    terminal_validation = validate_component_route_family_promotion_terminal_closure_denial_report()
    if not terminal_validation.ok:
        errors.extend(
            f"component route-family promotion terminal-closure denial validation failed: {error}"
            for error in terminal_validation.errors
        )

    runtime_ledger = build_component_route_family_promotion_missing_evidence_ledger()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_ledger:
            errors.append(f"{_path_label(example_path)}: example does not match runtime ledger")
        _validate_missing_evidence_semantics(example, errors, _path_label(example_path))
    _validate_missing_evidence_semantics(
        runtime_ledger,
        errors,
        "runtime component route-family promotion missing-evidence ledger",
    )

    summary = runtime_ledger.get("summary", {})
    return ComponentRouteFamilyPromotionMissingEvidenceLedgerValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_ledger.get("target_surface_id", "")),
        target_component_id=str(runtime_ledger.get("target_component_id", "")),
        target_product_bundle_id=str(runtime_ledger.get("target_product_bundle_id", "")),
        decision=str(runtime_ledger.get("decision", "")),
        missing_evidence_record_count=(
            int(summary.get("missing_evidence_record_count", 0)) if isinstance(summary, dict) else 0
        ),
        present_evidence_count=(
            int(summary.get("present_evidence_count", 0)) if isinstance(summary, dict) else 0
        ),
        unknown_proof_state_count=(
            int(summary.get("unknown_proof_state_count", 0)) if isinstance(summary, dict) else 0
        ),
        witness_emission_count=(
            int(summary.get("witness_emission_count", 0)) if isinstance(summary, dict) else 0
        ),
    )


def write_component_route_family_promotion_missing_evidence_ledger_validation(
    validation: ComponentRouteFamilyPromotionMissingEvidenceLedgerValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic missing-evidence ledger validation receipt."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_missing_evidence_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    expected_strings = {
        "decision": "blocked",
        "preflight_outcome": "GovernanceBlocked",
        "outcome": "AwaitingEvidence",
        "evidence_status": "missing_required_witnesses",
        "promotion_decision": "blocked_missing_required_evidence",
        "terminal_closure_decision_state": "denied_pending_terminal_closure_certificate",
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
        "terminal_closure_denial_issued",
        "evidence_ledger_issued",
        "missing_evidence_ledger_is_not_evidence",
        "missing_evidence_ledger_is_not_witness",
        "missing_evidence_ledger_is_not_terminal_certificate",
        "missing_evidence_ledger_is_not_terminal_closure",
        "missing_evidence_ledger_is_not_promotion_approval",
        "missing_evidence_ledger_is_not_authority_grant",
        "unknown_required_evidence_blocks_promotion",
        "foundation_fixture_decision_is_not_live_operator_evidence",
        "separate_terminal_closure_certificate_required",
        "separate_product_ownership_witness_required",
        "separate_authority_upgrade_witness_required",
        "separate_lifecycle_transition_receipt_required",
        "separate_route_binding_receipt_required",
        "separate_router_inventory_delta_required",
    ):
        if report.get(field_name) is not True:
            errors.append(f"{label}: {field_name} must be true")
    for field_name in (
        "terminal_closure_authorized",
        "terminal_certificate_minted",
        "terminal_closure_witness_emitted",
        "terminal_closure_claimed",
        "promotion_approved",
        "product_ownership_authorized",
        "product_bundle_binding_authorized",
        "product_ownership_witness_emitted",
        "product_route_ownership_bound",
        "route_family_ownership_authorized",
        "authority_upgrade_authorized",
        "authority_level_changed",
        "authority_witness_emitted",
        "authority_envelope_mutated",
        "authority_granted",
        "lifecycle_transition_authorized",
        "route_binding_authorized",
        "router_inventory_delta_authorized",
        "selected_component_binding_authorized",
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
        "terminal_closure_certificate_refs",
        "terminal_closure_witness_refs",
        "terminal_closure_refs",
        "promotion_approval_refs",
        "product_ownership_witness_refs",
        "product_bundle_binding_refs",
        "authority_upgrade_witness_refs",
        "authority_envelope_mutation_refs",
        "authority_grant_refs",
        "lifecycle_transition_receipt_refs",
        "route_binding_receipt_refs",
        "router_inventory_delta_refs",
        "selected_component_binding_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
    ):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must remain empty until separate evidence exists")

    records = report.get("missing_evidence_records")
    summary = report.get("summary")
    if not isinstance(records, list) or len(records) != len(MISSING_REQUIRED_ARTIFACTS):
        errors.append(f"{label}: missing_evidence_records must contain six records")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if set(_string_list(report.get("missing_required_artifacts"))) != MISSING_REQUIRED_ARTIFACTS:
        errors.append(f"{label}: missing_required_artifacts must match required artifact set")
    if _string_list(report.get("missing_evidence_record_refs")) != [
        str(record.get("missing_evidence_id")) for record in records if isinstance(record, dict)
    ]:
        errors.append(f"{label}: missing_evidence_record_refs must match missing_evidence_ids")
    source_terminal_refs = _string_list(report.get("source_terminal_closure_decision_refs"))
    if len(source_terminal_refs) != 1:
        errors.append(f"{label}: source_terminal_closure_decision_refs must contain one terminal decision")
    authority_fuse_refs = _string_list(report.get("authority_fuse_refs"))
    if len(authority_fuse_refs) != 1:
        errors.append(f"{label}: authority_fuse_refs must contain exactly one component authority-fuse ref")
    if _string_list(report.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        errors.append(f"{label}: authority_fuse_blocking_refs must match authority_fuse_refs")

    for record in records:
        if not isinstance(record, dict):
            errors.append(f"{label}: missing_evidence_records entries must be objects")
            continue
        _validate_missing_record(record, source_terminal_refs, authority_fuse_refs, errors, label)

    expected_counts = {
        "missing_evidence_record_count": len(records),
        "required_evidence_count": sum(1 for record in records if isinstance(record, dict) and record.get("required") is True),
        "present_evidence_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("evidence_present") is True
        ),
        "unknown_proof_state_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("proof_state") == "Unknown"
        ),
        "blocking_record_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("blocks_promotion") is True
        ),
        "witness_emission_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("witness_emitted") is True
        ),
        "authority_grant_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("authority_granted") is True
        ),
        "promotion_approval_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("promotion_approved") is True
        ),
        "terminal_certificate_mint_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("terminal_certificate_minted") is True
        ),
        "terminal_closure_authorization_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("terminal_closure_authorized") is True
        ),
        "terminal_closure_claim_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("terminal_closure_claimed") is True
        ),
        "router_inventory_mutation_count": sum(
            1 for record in records if isinstance(record, dict) and record.get("mutates_router_inventory") is True
        ),
        "authority_fuse_blocking_count": sum(
            len(_string_list(record.get("authority_fuse_blocking_refs")))
            for record in records
            if isinstance(record, dict)
        ),
    }
    for stage in MISSING_EVIDENCE_STAGES.values():
        expected_counts[f"{stage}_missing_count"] = sum(
            1 for record in records if isinstance(record, dict) and record.get("required_stage") == stage
        )
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match missing evidence records")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")


def _validate_missing_record(
    record: dict[str, Any],
    source_terminal_refs: list[str],
    authority_fuse_refs: list[str],
    errors: list[str],
    label: str,
) -> None:
    artifact_id = str(record.get("artifact_id", ""))
    expected_stage = MISSING_EVIDENCE_STAGES.get(artifact_id)
    if expected_stage is None:
        errors.append(f"{label}: missing record artifact_id must be a required artifact")
    elif record.get("required_stage") != expected_stage:
        errors.append(f"{label}: missing record required_stage must match artifact_id")
    expected_strings = {
        "evidence_state": "missing",
        "proof_state": "Unknown",
        "product_bundle_id": DEFAULT_PRODUCT_BUNDLE_ID,
    }
    for field_name, expected_value in expected_strings.items():
        if record.get(field_name) != expected_value:
            errors.append(f"{label}: missing record {field_name} must be {expected_value}")
    for field_name in (
        "source_terminal_closure_decision_denied",
        "authority_fuse_blocks_promotion",
        "hard_constraint_unknown_blocks_action",
        "required",
        "blocks_promotion",
        "blocks_terminal_closure",
        "record_is_not_evidence",
        "record_is_not_witness",
        "record_is_not_authority_grant",
        "record_is_not_terminal_certificate",
        "record_is_not_terminal_closure",
        "record_is_not_promotion_approval",
    ):
        if record.get(field_name) is not True:
            errors.append(f"{label}: missing record {field_name} must be true")
    for field_name in (
        "evidence_present",
        "witness_emitted",
        "authority_granted",
        "promotion_approved",
        "terminal_certificate_minted",
        "terminal_closure_authorized",
        "terminal_closure_claimed",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "mutates_router_inventory",
    ):
        if record.get(field_name) is not False:
            errors.append(f"{label}: missing record {field_name} must be false")
    if _string_list(record.get("source_terminal_closure_decision_refs")) != source_terminal_refs:
        errors.append(f"{label}: source_terminal_closure_decision_refs must match ledger source terminal ref")
    if _string_list(record.get("authority_fuse_refs")) != authority_fuse_refs:
        errors.append(f"{label}: missing record authority_fuse_refs must match ledger authority_fuse_refs")
    if _string_list(record.get("authority_fuse_blocking_refs")) != authority_fuse_refs:
        errors.append(f"{label}: missing record authority_fuse_blocking_refs must match ledger authority_fuse_refs")
    for field_name in (
        "accepted_evidence_refs",
        "witness_refs",
        "authority_grant_refs",
        "promotion_approval_refs",
        "terminal_closure_refs",
    ):
        if _string_list(record.get(field_name)):
            errors.append(f"{label}: missing record {field_name} must remain empty")
    if not record.get("decision_reason"):
        errors.append(f"{label}: missing record must carry decision_reason")


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
    """Parse missing-evidence ledger validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness missing-evidence ledger.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for missing-evidence ledger validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_missing_evidence_ledger(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_missing_evidence_ledger_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION MISSING EVIDENCE LEDGER VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
