#!/usr/bin/env python3
"""Validate Component Harness promotion operator-submitted evidence records.

Purpose: prove submitted-for-review promotion evidence records apply acceptance
rules as record-only evidence while remaining blocked from promotion,
execution, connector, router-inventory, mutation, and terminal-closure
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: operator-submitted evidence records schema/example, runtime
builder, and submitted-evidence payload examples validation.
Invariants:
  - Accepted records are not promotion authority.
  - Applied acceptance rules are not execution authority.
  - Record acceptance does not satisfy promotion requirements.
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

from mcoi_runtime.app.component_route_family_promotion_operator_submitted_evidence_records import (  # noqa: E402
    build_component_route_family_promotion_operator_submitted_evidence_records,
)
from scripts.validate_component_route_family_promotion_submitted_evidence_payload_examples import (  # noqa: E402
    validate_component_route_family_promotion_submitted_evidence_payload_examples,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "component_route_family_promotion_operator_submitted_evidence_records.schema.json"
)
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_operator_submitted_evidence_records.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "component_route_family_promotion_operator_submitted_evidence_records_validation.json"
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
class ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsValidation:
    """Schema and semantic validation report for operator-submitted evidence records."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    submitted_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    accepted_evidence_count: int
    acceptance_rule_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_operator_submitted_evidence_records(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsValidation:
    """Validate operator-submitted evidence record schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(
        schema_path,
        "component route-family promotion operator-submitted evidence records schema",
        errors,
    )
    example = _load_json_object(
        example_path,
        "component route-family promotion operator-submitted evidence records example",
        errors,
    )

    payload_examples_validation = validate_component_route_family_promotion_submitted_evidence_payload_examples()
    if not payload_examples_validation.ok:
        errors.extend(
            f"component route-family promotion submitted-evidence payload examples validation failed: {error}"
            for error in payload_examples_validation.errors
        )

    runtime_report = build_component_route_family_promotion_operator_submitted_evidence_records()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_operator_submitted_records_semantics(example, errors, _path_label(example_path))
    _validate_operator_submitted_records_semantics(
        runtime_report,
        errors,
        "runtime component route-family promotion operator-submitted records",
    )

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        submitted_record_count=int(summary.get("submitted_record_count", 0)) if isinstance(summary, dict) else 0,
        accepted_record_count=int(summary.get("accepted_record_count", 0)) if isinstance(summary, dict) else 0,
        rejected_record_count=int(summary.get("rejected_record_count", 0)) if isinstance(summary, dict) else 0,
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        acceptance_rule_count=int(summary.get("acceptance_rule_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_operator_submitted_evidence_records_validation(
    validation: ComponentRouteFamilyPromotionOperatorSubmittedEvidenceRecordsValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic operator-submitted evidence record validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_operator_submitted_records_semantics(
    report: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("record_decision") != "submitted_for_review":
        errors.append(f"{label}: record_decision must be submitted_for_review")
    if report.get("acceptance_decision") != "rules_applied_record_only":
        errors.append(f"{label}: acceptance_decision must be rules_applied_record_only")
    if report.get("submission_source") != "local_foundation_fixture":
        errors.append(f"{label}: submission_source must be local_foundation_fixture")
    if report.get("operator_submitted_evidence_records_are_not_execution_authority") is not True:
        errors.append(f"{label}: operator-submitted records must not be execution authority")
    if report.get("accepted_records_are_not_promotion_authority") is not True:
        errors.append(f"{label}: accepted records must not be promotion authority")
    if report.get("foundation_fixture_records_are_not_live_operator_evidence") is not True:
        errors.append(f"{label}: foundation fixture records must not be live operator evidence")
    if report.get("acceptance_rules_are_not_execution_authority") is not True:
        errors.append(f"{label}: acceptance rules must not be execution authority")
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
            errors.append(f"{label}: {field_name} must remain empty until gate satisfaction exists")

    records = report.get("operator_submitted_evidence_records")
    summary = report.get("summary")
    if not isinstance(records, list) or not records:
        errors.append(f"{label}: operator_submitted_evidence_records must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    record_ids = [
        str(record.get("operator_submitted_record_id"))
        for record in records
        if isinstance(record, dict)
    ]
    if len(record_ids) != len(set(record_ids)):
        errors.append(f"{label}: operator_submitted_record_ids must be unique")
    if set(_string_list(report.get("submitted_record_refs"))) != set(record_ids):
        errors.append(f"{label}: submitted_record_refs must match operator_submitted_record_ids")
    if set(_string_list(report.get("accepted_record_refs"))) != set(record_ids):
        errors.append(f"{label}: accepted_record_refs must match operator_submitted_record_ids")
    if _string_list(report.get("rejected_record_refs")):
        errors.append(f"{label}: rejected_record_refs must be empty")

    observed_gates: set[str] = set()
    reviewed_count = 0
    accepted_record_count = 0
    rejected_record_count = 0
    submitted_payload_count = 0
    accepted_evidence_count = 0
    rejected_evidence_count = 0
    acceptance_rule_count = 0
    applied_rule_count = 0
    passing_rule_count = 0
    failing_rule_count = 0
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
    for record in records:
        if not isinstance(record, dict):
            errors.append(f"{label}: operator_submitted_evidence_records entries must be objects")
            continue
        gate_id = str(record.get("gate_id", ""))
        observed_gates.add(gate_id)
        collected_required.update(_string_list(record.get("required_artifacts")))
        _validate_operator_submitted_record(record, errors, label, gate_id)

        submitted_payload = record.get("submitted_payload")
        required_payload_fields = set(_string_list(record.get("required_payload_fields")))
        if not isinstance(submitted_payload, dict):
            errors.append(f"{label}: record {gate_id} submitted_payload must be an object")
            submitted_payload_fields: set[str] = set()
        else:
            submitted_payload_fields = set(str(field_name) for field_name in submitted_payload)
            if submitted_payload_fields != required_payload_fields:
                errors.append(f"{label}: record {gate_id} submitted_payload keys must match required_payload_fields")
            _validate_submitted_payload_values(record, submitted_payload, errors, label, gate_id)

        rules = record.get("applied_acceptance_rules")
        if not isinstance(rules, list) or not rules:
            errors.append(f"{label}: record {gate_id} applied_acceptance_rules must be non-empty")
        else:
            for rule in rules:
                if not isinstance(rule, dict):
                    errors.append(f"{label}: record {gate_id} applied_acceptance_rules entries must be objects")
                    continue
                _validate_applied_acceptance_rule(
                    rule,
                    record,
                    submitted_payload_fields,
                    errors,
                    label,
                    gate_id,
                )
                acceptance_rule_count += 1
                if rule.get("rule_state") == "applied":
                    applied_rule_count += 1
                if rule.get("proof_state") == "Pass" and rule.get("rule_result") == "pass":
                    passing_rule_count += 1
                if isinstance(rule.get("proof_state"), str) and str(rule.get("proof_state")).startswith("Fail"):
                    failing_rule_count += 1

        submitted_payload_count += 1 if isinstance(submitted_payload, dict) else 0
        accepted_evidence_count += len(_string_list(record.get("accepted_evidence_refs")))
        rejected_evidence_count += len(_string_list(record.get("rejected_evidence_refs")))
        if record.get("verification_state") == "reviewed":
            reviewed_count += 1
        if record.get("acceptance_state") == "accepted_record_only":
            accepted_record_count += 1
        else:
            rejected_record_count += 1
        if record.get("satisfies_requirement") is True:
            satisfied_count += 1
        if record.get("blocks_promotion") is True:
            blocking_count += 1
        if (
            record.get("grants_execution_authority") is True
            or record.get("grants_connector_authority") is True
            or record.get("grants_terminal_closure") is True
        ):
            authority_grant_count += 1

    if observed_gates != TARGET_RECORD_GATES:
        errors.append(f"{label}: operator_submitted_evidence_records must cover exactly {sorted(TARGET_RECORD_GATES)}")
    if reported_required != collected_required:
        errors.append(f"{label}: approval_evidence_required must match record required_artifacts")

    expected_counts = {
        "submitted_record_count": len(records),
        "reviewed_record_count": reviewed_count,
        "accepted_record_count": accepted_record_count,
        "rejected_record_count": rejected_record_count,
        "submitted_payload_count": submitted_payload_count,
        "accepted_evidence_count": accepted_evidence_count,
        "rejected_evidence_count": rejected_evidence_count,
        "acceptance_rule_count": acceptance_rule_count,
        "applied_acceptance_rule_count": applied_rule_count,
        "passing_acceptance_rule_count": passing_rule_count,
        "failing_acceptance_rule_count": failing_rule_count,
        "satisfied_requirement_count": satisfied_count,
        "blocking_record_count": blocking_count,
        "approval_artifact_requirement_count": len(reported_required),
        "authority_grant_count": authority_grant_count,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match operator-submitted evidence records")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_submitted_evidence_records_receipt",
        "component_route_family_promotion_submitted_evidence_verifier_receipt",
        "component_route_family_promotion_approval_intake_receipt",
        "component_lifecycle_transition_receipt",
        "authority_upgrade_witness",
        "product_specific_ownership_decision",
        "operator_approval_required_receipt",
    ):
        if expected_receipt not in expected_receipts:
            errors.append(f"{label}: expected_receipts must include {expected_receipt}")


def _validate_operator_submitted_record(
    record: dict[str, Any],
    errors: list[str],
    label: str,
    gate_id: str,
) -> None:
    if record.get("record_state") != "submitted_for_review":
        errors.append(f"{label}: record {gate_id} record_state must be submitted_for_review")
    if record.get("submission_state") != "submitted":
        errors.append(f"{label}: record {gate_id} submission_state must be submitted")
    if record.get("verification_state") != "reviewed":
        errors.append(f"{label}: record {gate_id} verification_state must be reviewed")
    if record.get("acceptance_state") != "accepted_record_only":
        errors.append(f"{label}: record {gate_id} acceptance_state must be accepted_record_only")
    if record.get("proof_state") != "Pass":
        errors.append(f"{label}: record {gate_id} proof_state must be Pass")
    if record.get("submission_source") != "local_foundation_fixture":
        errors.append(f"{label}: record {gate_id} submission_source must be local_foundation_fixture")
    if record.get("payload_source_state") != "foundation_fixture_from_payload_example":
        errors.append(f"{label}: record {gate_id} payload_source_state must be foundation_fixture_from_payload_example")
    if record.get("blocks_promotion") is not True:
        errors.append(f"{label}: record {gate_id} must block promotion")
    if record.get("satisfies_requirement") is not False:
        errors.append(f"{label}: record {gate_id} must not satisfy requirement")
    if record.get("accepted_record_is_not_execution_authority") is not True:
        errors.append(f"{label}: record {gate_id} accepted_record_is_not_execution_authority must be true")
    if record.get("accepted_record_is_not_promotion_authority") is not True:
        errors.append(f"{label}: record {gate_id} accepted_record_is_not_promotion_authority must be true")
    if record.get("foundation_fixture_record_is_not_live_operator_evidence") is not True:
        errors.append(f"{label}: record {gate_id} foundation fixture marker must be true")
    for field_name in (
        "mutates_router_inventory",
        "grants_execution_authority",
        "grants_connector_authority",
        "grants_terminal_closure",
    ):
        if record.get(field_name) is not False:
            errors.append(f"{label}: record {gate_id} {field_name} must be false")
    if record.get("payload_values_present") is not True:
        errors.append(f"{label}: record {gate_id} payload_values_present must be true")
    if record.get("payload_values_are_foundation_fixture") is not True:
        errors.append(f"{label}: record {gate_id} payload_values_are_foundation_fixture must be true")
    for field_name in ("required_artifacts", "required_payload_fields", "rejection_conditions"):
        if not record.get(field_name):
            errors.append(f"{label}: record {gate_id} must carry {field_name}")
    required_payload_fields = set(_string_list(record.get("required_payload_fields")))
    if not REQUIRED_PAYLOAD_FIELDS <= required_payload_fields:
        errors.append(f"{label}: record {gate_id} required_payload_fields omits required fields")
    for field_name in (
        "submitted_evidence_refs",
        "accepted_evidence_refs",
        "rejected_evidence_refs",
        "promotion_approval_refs",
    ):
        if _string_list(record.get(field_name)):
            errors.append(f"{label}: record {gate_id} {field_name} must remain empty until gate satisfaction exists")
    if not record.get("blocking_reason"):
        errors.append(f"{label}: record {gate_id} must carry blocking_reason")


def _validate_submitted_payload_values(
    record: dict[str, Any],
    submitted_payload: dict[str, Any],
    errors: list[str],
    label: str,
    gate_id: str,
) -> None:
    expected_pairs = {
        "source_verifier_request_id": record.get("source_verifier_request_id"),
        "source_intake_request_id": record.get("source_intake_request_id"),
        "gate_id": gate_id,
    }
    for field_name, expected_value in expected_pairs.items():
        if submitted_payload.get(field_name) != expected_value:
            errors.append(f"{label}: record {gate_id} submitted_payload.{field_name} must match source")
    if not isinstance(submitted_payload.get("artifact_refs"), list) or not submitted_payload.get("artifact_refs"):
        errors.append(f"{label}: record {gate_id} submitted_payload.artifact_refs must be non-empty")
    if not isinstance(submitted_payload.get("witness_refs"), list) or not submitted_payload.get("witness_refs"):
        errors.append(f"{label}: record {gate_id} submitted_payload.witness_refs must be non-empty")
    authority_claims = submitted_payload.get("authority_claims")
    if not isinstance(authority_claims, dict):
        errors.append(f"{label}: record {gate_id} submitted_payload.authority_claims must be an object")
    else:
        for field_name in ("can_execute", "can_mutate", "can_call_connector", "can_claim_terminal_closure"):
            if authority_claims.get(field_name) is not False:
                errors.append(f"{label}: record {gate_id} authority_claims.{field_name} must be false")
    if submitted_payload.get("terminal_closure_claim") is not False:
        errors.append(f"{label}: record {gate_id} terminal_closure_claim must be false")
    if submitted_payload.get("no_router_mutation_claim") is not True:
        errors.append(f"{label}: record {gate_id} no_router_mutation_claim must be true")
    required_artifacts = set(_string_list(record.get("required_artifacts")))
    if any(artifact.startswith("operator_approval") or artifact.endswith("operator_approval") for artifact in required_artifacts):
        if not isinstance(submitted_payload.get("operator_approval_refs"), list) or not submitted_payload.get("operator_approval_refs"):
            errors.append(f"{label}: record {gate_id} operator_approval_refs must be present when approval is required")


def _validate_applied_acceptance_rule(
    rule: dict[str, Any],
    record: dict[str, Any],
    submitted_payload_fields: set[str],
    errors: list[str],
    label: str,
    gate_id: str,
) -> None:
    if rule.get("source_record_envelope_id") != record.get("source_record_envelope_id"):
        errors.append(f"{label}: record {gate_id} applied rule source_record_envelope_id must match record")
    if rule.get("source_payload_example_id") != record.get("source_payload_example_id"):
        errors.append(f"{label}: record {gate_id} applied rule source_payload_example_id must match record")
    if rule.get("gate_id") != gate_id:
        errors.append(f"{label}: record {gate_id} applied rule gate_id must match record")
    if rule.get("rule_state") != "applied":
        errors.append(f"{label}: record {gate_id} applied rule state must be applied")
    if rule.get("proof_state") != "Pass":
        errors.append(f"{label}: record {gate_id} applied rule proof_state must be Pass")
    if rule.get("rule_result") != "pass":
        errors.append(f"{label}: record {gate_id} applied rule result must be pass")
    if rule.get("required_for_submission") is not True:
        errors.append(f"{label}: record {gate_id} applied rule required_for_submission must be true")
    if rule.get("blocks_submission_until_pass") is not True:
        errors.append(f"{label}: record {gate_id} applied rule blocks_submission_until_pass must be true")
    if rule.get("rule_is_not_execution_authority") is not True:
        errors.append(f"{label}: record {gate_id} applied rule must not be execution authority")
    if rule.get("record_acceptance_only") is not True:
        errors.append(f"{label}: record {gate_id} applied rule record_acceptance_only must be true")
    for field_name in (
        "mutates_router_inventory",
        "grants_execution_authority",
        "grants_connector_authority",
        "grants_terminal_closure",
    ):
        if rule.get(field_name) is not False:
            errors.append(f"{label}: record {gate_id} applied rule {field_name} must be false")
    source_payload_fields = set(_string_list(rule.get("source_payload_fields")))
    if not source_payload_fields:
        errors.append(f"{label}: record {gate_id} applied rule source_payload_fields must be non-empty")
    if not source_payload_fields <= submitted_payload_fields:
        errors.append(f"{label}: record {gate_id} applied rule source_payload_fields must exist on submitted_payload")
    if not rule.get("failure_condition"):
        errors.append(f"{label}: record {gate_id} applied rule must carry failure_condition")
    if not rule.get("evaluation_detail"):
        errors.append(f"{label}: record {gate_id} applied rule must carry evaluation_detail")


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
    """Parse operator-submitted evidence record validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness operator-submitted evidence records.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for operator-submitted evidence record validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_operator_submitted_evidence_records(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_operator_submitted_evidence_records_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION OPERATOR SUBMITTED EVIDENCE RECORDS VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
