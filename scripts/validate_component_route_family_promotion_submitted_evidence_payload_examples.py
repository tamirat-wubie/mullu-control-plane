#!/usr/bin/env python3
"""Validate Component Harness promotion submitted-evidence payload examples.

Purpose: prove concrete submitted-evidence payload examples and acceptance
rules remain example-only, not submitted, not evaluated, and non-authoritative.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: submitted-evidence payload examples schema/example, runtime
builder, and submitted-evidence records validation.
Invariants:
  - Payload examples are not submitted evidence.
  - Acceptance rules are defined but not applied.
  - Payload examples and acceptance rules cannot grant execution, connector,
    mutation, router-inventory, or terminal-closure authority.
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

from mcoi_runtime.app.component_route_family_promotion_submitted_evidence_payload_examples import (  # noqa: E402
    build_component_route_family_promotion_submitted_evidence_payload_examples,
)
from scripts.validate_component_route_family_promotion_submitted_evidence_records import (  # noqa: E402
    validate_component_route_family_promotion_submitted_evidence_records,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_route_family_promotion_submitted_evidence_payload_examples.schema.json"
DEFAULT_EXAMPLE = (
    REPO_ROOT
    / "examples"
    / "component_route_family_promotion_submitted_evidence_payload_examples.governed_connector_framework.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "component_route_family_promotion_submitted_evidence_payload_examples_validation.json"
)
TARGET_PAYLOAD_GATES = {
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
class ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesValidation:
    """Schema and semantic validation report for submitted-evidence payload examples."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    target_surface_id: str
    target_component_id: str
    decision: str
    payload_example_count: int
    submitted_payload_count: int
    accepted_evidence_count: int
    rejected_evidence_count: int
    acceptance_rule_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_route_family_promotion_submitted_evidence_payload_examples(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesValidation:
    """Validate payload examples schema, example, and runtime projection."""

    errors: list[str] = []
    schema = _load_json_object(
        schema_path,
        "component route-family promotion submitted-evidence payload examples schema",
        errors,
    )
    example = _load_json_object(
        example_path,
        "component route-family promotion submitted-evidence payload examples example",
        errors,
    )

    records_validation = validate_component_route_family_promotion_submitted_evidence_records()
    if not records_validation.ok:
        errors.extend(
            f"component route-family promotion submitted-evidence records validation failed: {error}"
            for error in records_validation.errors
        )

    runtime_report = build_component_route_family_promotion_submitted_evidence_payload_examples()
    if schema and example:
        errors.extend(
            f"{_path_label(example_path)}: {error}"
            for error in _validate_schema_instance(schema, example)
        )
        if example != runtime_report:
            errors.append(f"{_path_label(example_path)}: example does not match runtime report")
        _validate_payload_examples_semantics(example, errors, _path_label(example_path))
    _validate_payload_examples_semantics(runtime_report, errors, "runtime component route-family promotion payload examples")

    summary = runtime_report.get("summary", {})
    return ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        target_surface_id=str(runtime_report.get("target_surface_id", "")),
        target_component_id=str(runtime_report.get("target_component_id", "")),
        decision=str(runtime_report.get("decision", "")),
        payload_example_count=int(summary.get("payload_example_count", 0)) if isinstance(summary, dict) else 0,
        submitted_payload_count=int(summary.get("submitted_payload_count", 0)) if isinstance(summary, dict) else 0,
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)) if isinstance(summary, dict) else 0,
        rejected_evidence_count=int(summary.get("rejected_evidence_count", 0)) if isinstance(summary, dict) else 0,
        acceptance_rule_count=int(summary.get("acceptance_rule_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_route_family_promotion_submitted_evidence_payload_examples_validation(
    validation: ComponentRouteFamilyPromotionSubmittedEvidencePayloadExamplesValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic submitted-evidence payload examples validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_payload_examples_semantics(report: dict[str, Any], errors: list[str], label: str) -> None:
    if report.get("governed") is not True:
        errors.append(f"{label}: governed must be true")
    if report.get("decision") != "blocked":
        errors.append(f"{label}: decision must remain blocked")
    if report.get("preflight_outcome") != "GovernanceBlocked":
        errors.append(f"{label}: preflight_outcome must be GovernanceBlocked")
    if report.get("outcome") != "AwaitingEvidence":
        errors.append(f"{label}: outcome must be AwaitingEvidence")
    if report.get("payload_decision") != "example_only":
        errors.append(f"{label}: payload_decision must be example_only")
    if report.get("acceptance_decision") != "defined_not_applied":
        errors.append(f"{label}: acceptance_decision must be defined_not_applied")
    if report.get("payload_examples_are_not_submitted_evidence") is not True:
        errors.append(f"{label}: payload examples must not be submitted evidence")
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
            errors.append(f"{label}: {field_name} must be empty until actual submitted payloads exist")

    payload_examples = report.get("payload_examples")
    summary = report.get("summary")
    if not isinstance(payload_examples, list) or not payload_examples:
        errors.append(f"{label}: payload_examples must be non-empty")
        return
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return

    payload_example_ids = [
        str(example.get("payload_example_id"))
        for example in payload_examples
        if isinstance(example, dict)
    ]
    if len(payload_example_ids) != len(set(payload_example_ids)):
        errors.append(f"{label}: payload_example_ids must be unique")

    observed_gates: set[str] = set()
    example_only_count = 0
    not_submitted_count = 0
    not_evaluated_count = 0
    submitted_count = 0
    accepted_count = 0
    rejected_count = 0
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
    for payload_example in payload_examples:
        if not isinstance(payload_example, dict):
            errors.append(f"{label}: payload_examples entries must be objects")
            continue
        gate_id = str(payload_example.get("gate_id", ""))
        observed_gates.add(gate_id)
        collected_required.update(_string_list(payload_example.get("required_artifacts")))
        if payload_example.get("payload_state") != "example_only":
            errors.append(f"{label}: payload {gate_id} payload_state must be example_only")
        if payload_example.get("submission_state") != "not_submitted":
            errors.append(f"{label}: payload {gate_id} submission_state must be not_submitted")
        if payload_example.get("verification_state") != "not_verified":
            errors.append(f"{label}: payload {gate_id} verification_state must be not_verified")
        if payload_example.get("acceptance_state") != "not_evaluated":
            errors.append(f"{label}: payload {gate_id} acceptance_state must be not_evaluated")
        if payload_example.get("proof_state") != "Unknown":
            errors.append(f"{label}: payload {gate_id} proof_state must be Unknown")
        if payload_example.get("blocks_promotion") is not True:
            errors.append(f"{label}: payload {gate_id} must block promotion")
        if payload_example.get("satisfies_requirement") is not False:
            errors.append(f"{label}: payload {gate_id} must not satisfy requirement")
        if payload_example.get("payload_values_present") is not True:
            errors.append(f"{label}: payload {gate_id} payload_values_present must be true for examples")
        if payload_example.get("payload_values_are_examples_only") is not True:
            errors.append(f"{label}: payload {gate_id} payload_values_are_examples_only must be true")
        if payload_example.get("payload_example_is_not_submitted_evidence") is not True:
            errors.append(f"{label}: payload {gate_id} payload_example_is_not_submitted_evidence must be true")
        for field_name in (
            "mutates_router_inventory",
            "grants_execution_authority",
            "grants_connector_authority",
            "grants_terminal_closure",
        ):
            if payload_example.get(field_name) is not False:
                errors.append(f"{label}: payload {gate_id} {field_name} must be false")
        for field_name in ("required_artifacts", "required_payload_fields", "rejection_conditions"):
            if not payload_example.get(field_name):
                errors.append(f"{label}: payload {gate_id} must carry {field_name}")
        required_payload_fields = set(_string_list(payload_example.get("required_payload_fields")))
        if not REQUIRED_PAYLOAD_FIELDS <= required_payload_fields:
            errors.append(f"{label}: payload {gate_id} required_payload_fields omits required fields")
        example_payload = payload_example.get("example_payload")
        if not isinstance(example_payload, dict):
            errors.append(f"{label}: payload {gate_id} example_payload must be an object")
            continue
        if set(example_payload) != required_payload_fields:
            errors.append(f"{label}: payload {gate_id} example_payload keys must match required_payload_fields")
        _validate_example_payload_values(payload_example, example_payload, errors, label, gate_id)
        acceptance_rules = payload_example.get("acceptance_rules")
        if not isinstance(acceptance_rules, list) or not acceptance_rules:
            errors.append(f"{label}: payload {gate_id} acceptance_rules must be non-empty")
            continue
        for rule in acceptance_rules:
            if not isinstance(rule, dict):
                errors.append(f"{label}: payload {gate_id} acceptance_rules entries must be objects")
                continue
            _validate_acceptance_rule(rule, payload_example, errors, label, gate_id)
            acceptance_rule_count += 1
            if rule.get("rule_state") != "defined_not_applied":
                applied_rule_count += 1
            if rule.get("proof_state") == "Pass":
                passing_rule_count += 1
            if isinstance(rule.get("proof_state"), str) and rule.get("proof_state", "").startswith("Fail"):
                failing_rule_count += 1
        refs_by_field = {
            "submitted_evidence_refs": _string_list(payload_example.get("submitted_evidence_refs")),
            "accepted_evidence_refs": _string_list(payload_example.get("accepted_evidence_refs")),
            "rejected_evidence_refs": _string_list(payload_example.get("rejected_evidence_refs")),
        }
        for field_name, refs in refs_by_field.items():
            if refs:
                errors.append(f"{label}: payload {gate_id} {field_name} must be empty until actual submission exists")
        if not payload_example.get("missing_submission_reason"):
            errors.append(f"{label}: payload {gate_id} must carry missing_submission_reason")
        submitted_count += len(refs_by_field["submitted_evidence_refs"])
        accepted_count += len(refs_by_field["accepted_evidence_refs"])
        rejected_count += len(refs_by_field["rejected_evidence_refs"])
        if payload_example.get("payload_state") == "example_only":
            example_only_count += 1
        if payload_example.get("submission_state") == "not_submitted":
            not_submitted_count += 1
        if payload_example.get("acceptance_state") == "not_evaluated":
            not_evaluated_count += 1
        if payload_example.get("satisfies_requirement") is True:
            satisfied_count += 1
        if payload_example.get("blocks_promotion") is True:
            blocking_count += 1
        if (
            payload_example.get("grants_execution_authority") is True
            or payload_example.get("grants_connector_authority") is True
            or payload_example.get("grants_terminal_closure") is True
        ):
            authority_grant_count += 1

    if observed_gates != TARGET_PAYLOAD_GATES:
        errors.append(f"{label}: payload_examples must cover exactly {sorted(TARGET_PAYLOAD_GATES)}")
    if reported_required != collected_required:
        errors.append(f"{label}: approval_evidence_required must match payload required_artifacts")

    expected_counts = {
        "payload_example_count": len(payload_examples),
        "example_only_payload_count": example_only_count,
        "not_submitted_payload_count": not_submitted_count,
        "not_evaluated_payload_count": not_evaluated_count,
        "submitted_payload_count": submitted_count,
        "accepted_evidence_count": accepted_count,
        "rejected_evidence_count": rejected_count,
        "acceptance_rule_count": acceptance_rule_count,
        "applied_acceptance_rule_count": applied_rule_count,
        "passing_acceptance_rule_count": passing_rule_count,
        "failing_acceptance_rule_count": failing_rule_count,
        "satisfied_requirement_count": satisfied_count,
        "blocking_payload_count": blocking_count,
        "approval_artifact_requirement_count": len(reported_required),
        "authority_grant_count": authority_grant_count,
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"{label}: summary.{field_name} must match submitted-evidence payload examples")

    blocked_actions = set(_string_list(report.get("blocked_actions")))
    for required_action in ("connector_call", "route_execution", "terminal_closure"):
        if required_action not in blocked_actions:
            errors.append(f"{label}: blocked_actions must include {required_action}")
    expected_receipts = set(_string_list(report.get("expected_receipts")))
    for expected_receipt in (
        "component_route_family_promotion_submitted_evidence_payload_examples_receipt",
        "component_route_family_promotion_operator_submitted_evidence_records_receipt",
        "component_route_family_promotion_gate_satisfaction_evaluator_receipt",
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


def _validate_example_payload_values(
    payload_example: dict[str, Any],
    example_payload: dict[str, Any],
    errors: list[str],
    label: str,
    gate_id: str,
) -> None:
    expected_pairs = {
        "source_verifier_request_id": payload_example.get("source_verifier_request_id"),
        "source_intake_request_id": payload_example.get("source_intake_request_id"),
        "gate_id": gate_id,
    }
    for field_name, expected_value in expected_pairs.items():
        if example_payload.get(field_name) != expected_value:
            errors.append(f"{label}: payload {gate_id} example_payload.{field_name} must match source")
    if not isinstance(example_payload.get("artifact_refs"), list) or not example_payload.get("artifact_refs"):
        errors.append(f"{label}: payload {gate_id} example_payload.artifact_refs must be non-empty")
    if not isinstance(example_payload.get("witness_refs"), list) or not example_payload.get("witness_refs"):
        errors.append(f"{label}: payload {gate_id} example_payload.witness_refs must be non-empty")
    authority_claims = example_payload.get("authority_claims")
    if not isinstance(authority_claims, dict):
        errors.append(f"{label}: payload {gate_id} example_payload.authority_claims must be an object")
    else:
        for field_name in ("can_execute", "can_mutate", "can_call_connector", "can_claim_terminal_closure"):
            if authority_claims.get(field_name) is not False:
                errors.append(f"{label}: payload {gate_id} authority_claims.{field_name} must be false")
    if example_payload.get("terminal_closure_claim") is not False:
        errors.append(f"{label}: payload {gate_id} terminal_closure_claim must be false")
    if example_payload.get("no_router_mutation_claim") is not True:
        errors.append(f"{label}: payload {gate_id} no_router_mutation_claim must be true")
    required_artifacts = set(_string_list(payload_example.get("required_artifacts")))
    if any(artifact.startswith("operator_approval") or artifact.endswith("operator_approval") for artifact in required_artifacts):
        if not isinstance(example_payload.get("operator_approval_refs"), list) or not example_payload.get("operator_approval_refs"):
            errors.append(f"{label}: payload {gate_id} operator_approval_refs must be present when approval is required")


def _validate_acceptance_rule(
    rule: dict[str, Any],
    payload_example: dict[str, Any],
    errors: list[str],
    label: str,
    gate_id: str,
) -> None:
    if rule.get("source_record_envelope_id") != payload_example.get("source_record_envelope_id"):
        errors.append(f"{label}: payload {gate_id} acceptance rule source_record_envelope_id must match payload")
    if rule.get("gate_id") != gate_id:
        errors.append(f"{label}: payload {gate_id} acceptance rule gate_id must match payload")
    if rule.get("rule_state") != "defined_not_applied":
        errors.append(f"{label}: payload {gate_id} acceptance rule state must be defined_not_applied")
    if rule.get("proof_state") != "Unknown":
        errors.append(f"{label}: payload {gate_id} acceptance rule proof_state must be Unknown")
    if rule.get("required_for_submission") is not True:
        errors.append(f"{label}: payload {gate_id} acceptance rule required_for_submission must be true")
    if rule.get("blocks_submission_until_pass") is not True:
        errors.append(f"{label}: payload {gate_id} acceptance rule blocks_submission_until_pass must be true")
    if rule.get("rule_is_not_execution_authority") is not True:
        errors.append(f"{label}: payload {gate_id} acceptance rule must not be execution authority")
    for field_name in (
        "mutates_router_inventory",
        "grants_execution_authority",
        "grants_connector_authority",
        "grants_terminal_closure",
    ):
        if rule.get(field_name) is not False:
            errors.append(f"{label}: payload {gate_id} acceptance rule {field_name} must be false")
    source_payload_fields = set(_string_list(rule.get("source_payload_fields")))
    if not source_payload_fields:
        errors.append(f"{label}: payload {gate_id} acceptance rule source_payload_fields must be non-empty")
    required_payload_fields = set(_string_list(payload_example.get("required_payload_fields")))
    if not source_payload_fields <= required_payload_fields:
        errors.append(f"{label}: payload {gate_id} acceptance rule source_payload_fields must exist on payload")
    if not rule.get("failure_condition"):
        errors.append(f"{label}: payload {gate_id} acceptance rule must carry failure_condition")


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
    """Parse submitted-evidence payload examples validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness submitted-evidence payload examples.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for submitted-evidence payload examples validation."""

    args = parse_args(argv)
    validation = validate_component_route_family_promotion_submitted_evidence_payload_examples(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_route_family_promotion_submitted_evidence_payload_examples_validation(
        validation,
        Path(args.output),
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT ROUTE FAMILY PROMOTION SUBMITTED EVIDENCE PAYLOAD EXAMPLES VALID")
    else:
        for error in validation.errors:
            print(error)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
