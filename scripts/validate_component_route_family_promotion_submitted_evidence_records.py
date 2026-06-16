#!/usr/bin/env python3
"""Validate Component Harness promotion submitted-evidence record envelopes.

Purpose: prove submitted-evidence records remain template-only envelopes without
accepting evidence, approving promotion, mutating router inventory, or granting
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: submitted-evidence records schema/example, runtime builder, and
submitted-evidence verifier validation.
Invariants:
  - Submitted-evidence record envelopes remain template-only and not submitted.
  - Template-only envelopes do not satisfy promotion requirements.
  - Record envelopes cannot grant execution, connector, mutation, or terminal
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

from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_records import (  # noqa: E402
    build_component_route_family_promotion_submitted_evidence_records,
)
from scripts.validate_component_route_family_promotion_submitted_evidence_verifier import (  # noqa: E402
    validate_component_route_family_promotion_submitted_evidence_verifier,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_submitted_evidence_records.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_submitted_evidence_records.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "component_route_family_promotion_submitted_evidence_records_validation.json"
)
TARGET_RECORD_GATES = {
    "route_binding_gate",
    "lifecycle_gate",
    "authority_upgrade_gate",
    "product_specific_boundary_gate",
}
REQUIRED_APPROVAL_EVIDENCE = {
    "authority_upgrade_witness",
    "component_lifecycle_transition_receipt",
    "component_route_binding_receipt",
    "gmail_account_binding_evidence_receipt",
    "operator_approval_if_connector_action_requested",
    "operator_approval_if_external_effect",
    "product_specific_ownership_decision",
    "selected_component_bound_router_inventory_delta",
}
REQUIRED_PAYLOAD_FIELDS = {
    "submitted_evidence_id",
    "source_verifier_request_id",
    "source_intake_request_id",
    "gate_id",
    "submitted_by",
    "submitted_at_epoch",
    "artifact_refs",
    "operator_approval_refs",
    "witness_refs",
    "authority_claims",
    "terminal_closure_claim",
    "no_router_mutation_claim",
}


@dataclass(frozen=True, slots=True)
class ComponentRouteFamilyPromotionSubmittedEvidenceRecordsValidation:
    """Schema and semantic validation report for submitted-evidence record envelopes."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    record_envelope_count: int
    submitted_record_count: int
    accepted_evidence_count: int
    rejected_evidence_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_submitted_evidence_records(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionSubmittedEvidenceRecordsValidation:
    """Validate submitted-evidence record envelope schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component route-family promotion submitted-evidence records schema", errors)
    example = _load_json_object(
        example_path,
        "component route-family promotion submitted-evidence records example",
        errors,
    )

    verifier_validation = validate_component_route_family_promotion_submitted_evidence_verifier()
    if not verifier_validation.ok:
        errors.extend(
            f"component route-family promotion submitted-evidence verifier validation failed: {error}"
            for error in verifier_validation.errors
        )

    runtime_report = build_component_route_family_promotion_submitted_evidence_records()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_records_semantics(example, errors, _path_label(example_path))
    _validate_records_semantics(runtime_report, errors, "runtime component route-family promotion records")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionSubmittedEvidenceRecordsValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        record_envelope_count=int(summary.get("record_envelope_count", 0)) if isinstance(summary, dict) else 0,
        submitted_record_count=int(summary.get("submitted_record_count", 0)) if isinstance(summary, dict) else 0,
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        rejected_evidence_count=int(summary.get("rejected_evidence_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_submitted_evidence_records_validation(
    validation: ComponentRouteFamilyPromotionSubmittedEvidenceRecordsValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic submitted-evidence record envelope validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_records_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("record_decision") != "template_only":
        errors.append(f"{label}: record_decision must be template_only")
    if report.get("submitted_evidence_records_are_not_execution_authority") is not True:
        errors.append(f"{label}: submitted-evidence records must not be execution authority")
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
    for field_name in ("submitted_evidence_refs", "accepted_evidence_refs", "rejected_evidence_refs"):
        if _string_list(report.get(field_name)):
            errors.append(f"{label}: {field_name} must be empty until submitted payloads exist")

    record_envelopes = report.get("record_envelopes")
    summary = report.get("summary")
    if not isinstance(record_envelopes, list) or not record_envelopes:
        errors.append(f"{label}: record_envelopes must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    envelope_ids = [
        str(envelope.get("record_envelope_id"))
        for envelope in record_envelopes
        if isinstance(envelope, dict)
    ]
    if len(envelope_ids) != len(set(envelope_ids)):
        errors.append(f"{label}: record_envelope_ids must be unique")

    observed_gates: set[str] = set()
    template_count = 0
    not_submitted_count = 0
    submitted_count = 0
    accepted_count = 0
    rejected_count = 0
    satisfied_count = 0
    blocking_count = 0
    authority_grant_count = 0
    reported_required = set(_string_list(report.get("approval_evidence_required")))
    submission_channels = set(_string_list(report.get("operator_submission_channels")))
    if not REQUIRED_APPROVAL_EVIDENCE <= reported_required:
        errors.append(f"{label}: approval_evidence_required omits required approval artifacts")
    if reported_required != submission_channels:
        errors.append(f"{label}: operator_submission_channels must match approval_evidence_required")
    collected_required = set(reported_required)
    for envelope in record_envelopes:
        if not isinstance(envelope, dict):
            errors.append(f"{label}: record_envelopes entries must be objects")
            continue
        gate_id = str(envelope.get("gate_id", ""))
        observed_gates.add(gate_id)
        collected_required.update(_string_list(envelope.get("required_artifacts")))
        if envelope.get("envelope_state") != "template_only":
            errors.append(f"{label}: envelope {gate_id} envelope_state must be template_only")
        if envelope.get("submission_state") != "not_submitted":
            errors.append(f"{label}: envelope {gate_id} submission_state must be not_submitted")
        if envelope.get("verification_state") != "not_verified":
            errors.append(f"{label}: envelope {gate_id} verification_state must be not_verified")
        if envelope.get("proof_state") != "Unknown":
            errors.append(f"{label}: envelope {gate_id} proof_state must be Unknown")
        if envelope.get("blocks_promotion") is not True:
            errors.append(f"{label}: envelope {gate_id} must block promotion")
        if envelope.get("satisfies_requirement") is not False:
            errors.append(f"{label}: envelope {gate_id} must not satisfy requirement")
        if envelope.get("record_envelope_is_not_execution_authority") is not True:
            errors.append(f"{label}: envelope {gate_id} record_envelope_is_not_execution_authority must be true")
        for field_name in (
            "mutates_router_inventory",
            "grants_execution_authority",
            "grants_connector_authority",
            "grants_terminal_closure",
        ):
            if envelope.get(field_name) is not False:
                errors.append(f"{label}: envelope {gate_id} {field_name} must be false")
        for field_name in ("required_artifacts", "payload_field_names", "validation_rules", "rejection_conditions"):
            if not envelope.get(field_name):
                errors.append(f"{label}: envelope {gate_id} must carry {field_name}")
        payload_field_names = set(_string_list(envelope.get("payload_field_names")))
        if not REQUIRED_PAYLOAD_FIELDS <= payload_field_names:
            errors.append(f"{label}: envelope {gate_id} payload_field_names omits required fields")
        refs_by_field = {
            "submitted_evidence_refs": _string_list(envelope.get("submitted_evidence_refs")),
            "accepted_evidence_refs": _string_list(envelope.get("accepted_evidence_refs")),
            "rejected_evidence_refs": _string_list(envelope.get("rejected_evidence_refs")),
        }
        for field_name, refs in refs_by_field.items():
            if refs:
                errors.append(f"{label}: envelope {gate_id} {field_name} must be empty until submitted payloads exist")
        if envelope.get("payload_values_present") is not False:
            errors.append(f"{label}: envelope {gate_id} payload_values_present must be false")
        if envelope.get("operator_submission_state") != "awaiting_operator":
            errors.append(f"{label}: envelope {gate_id} operator_submission_state must be awaiting_operator")
        if not envelope.get("missing_submission_reason"):
            errors.append(f"{label}: envelope {gate_id} must carry missing_submission_reason")
        submitted_count += len(refs_by_field["submitted_evidence_refs"])
        accepted_count += len(refs_by_field["accepted_evidence_refs"])
        rejected_count += len(refs_by_field["rejected_evidence_refs"])
        if envelope.get("envelope_state") == "template_only":
            template_count += 1
        if envelope.get("submission_state") == "not_submitted":
            not_submitted_count += 1
        if envelope.get("satisfies_requirement") is True:
            satisfied_count += 1
        if envelope.get("blocks_promotion") is True:
            blocking_count += 1
        if (
            envelope.get("grants_execution_authority") is True
            or envelope.get("grants_connector_authority") is True
            or envelope.get("grants_terminal_closure") is True
        ):
            authority_grant_count += 1

    if observed_gates != TARGET_RECORD_GATES:
        errors.append(f"{label}: record_envelopes must cover exactly {sorted(TARGET_RECORD_GATES)}")
    if reported_required != collected_required:
        errors.append(f"{label}: approval_evidence_required must match envelope required_artifacts")

    expected_counts = {
        "record_envelope_count": len(record_envelopes),
        "template_only_envelope_count": template_count,
        "not_submitted_envelope_count": not_submitted_count,
        "submitted_record_count": submitted_count,
        "valid_record_count": 0,
        "accepted_evidence_count": accepted_count,
        "rejected_evidence_count": rejected_count,
        "satisfied_requirement_count": satisfied_count,
        "blocking_envelope_count": blocking_count,
        "approval_artifact_requirement_count": len(reported_required),
        "authority_grant_count": authority_grant_count,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match submitted-evidence records")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_approval_intake_receipt",
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
    """Parse submitted-evidence record envelope validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness submitted-evidence record envelopes.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for submitted-evidence record envelope validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_submitted_evidence_records(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_submitted_evidence_records_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION SUBMITTED EVIDENCE RECORDS VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
