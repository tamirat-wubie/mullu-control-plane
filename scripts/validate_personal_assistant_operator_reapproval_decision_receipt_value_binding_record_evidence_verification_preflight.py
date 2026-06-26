#!/usr/bin/env python3
"""Validate operator value-binding evidence verification preflight."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate in (REPO_ROOT, MCOI_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from mcoi_runtime.personal_assistant import (  # noqa: E402
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_VERIFICATION_PREFLIGHT_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_EVIDENCE_VERIFICATION_PREFLIGHT_GENERATED_AT
EXPECTED_EVIDENCE_KINDS = frozenset(
    {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
)
EXPECTED_REQUIREMENT_KINDS = frozenset(
    {
        "verifier_identity_ref",
        "verification_method_ref",
        "evidence_integrity_hash_ref",
        "source_ref_reachability_witness_ref",
        "decision_receipt_crosscheck_ref",
    }
)
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_allowed",
        "evidence_acceptance_preflight_ref_binding_allowed",
        "submitted_evidence_ref_scope_check_allowed",
        "verification_requirement_planning_allowed",
        "evidence_verification_preflight_decision_allowed",
        "submitted_evidence_refs_present",
        "evidence_submitted",
        "evidence_ref_only",
        "evidence_acceptance_preflight_is_source",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "raw_evidence_payload_present",
        "raw_operator_value_present",
        "verifier_identity_bound",
        "verification_method_bound",
        "evidence_integrity_hash_bound",
        "source_ref_reachability_witness_bound",
        "decision_receipt_crosscheck_bound",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
        "operator_value_collected",
        "explicit_operator_value_present",
        "operator_value_bound",
        "operator_identity_ref_bound",
        "operator_signature_ref_bound",
        "decision_receipt_ref_bound",
        "accepted_value_present",
        "binding_record_candidate_accepted",
        "binding_record_created",
        "binding_record_admitted",
        "admission_approved",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "dispatch_lease_active",
        "live_connector_receipt_present",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "task_write_allowed",
        "memory_write_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "deployment_mutation_allowed",
        "nested_mind_live_activation_allowed",
        "public_readiness_claim_allowed",
    }
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
        "raw_calendar_event",
        "raw_task_payload",
        "raw_chat_log",
        "chat_log",
        "transcript",
        "credential",
        "credentials",
        "token",
        "secret",
        "private_key",
        "authorization",
        "cookie",
        "raw_operator_decision",
        "operator_decision_value",
        "operator_identity",
        "operator_signature",
        "raw_decision_receipt",
        "submitted_evidence_payload",
        "raw_submitted_evidence",
        "submitted_value",
        "accepted_value",
        "verified_value",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "acceptance_preflight_projection",
        "submitted_evidence_projection",
        "verification_evidence_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "decision_receipt_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordEvidenceVerificationPreflightValidation:
    """Validation result for evidence verification preflight."""

    valid: bool
    runtime_validated: bool
    verification_preflight_count: int
    submitted_evidence_count: int
    verification_requirement_count: int
    satisfied_verification_requirement_count: int
    verified_evidence_count: int
    accepted_evidence_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordEvidenceVerificationPreflightValidation:
    """Validate runtime evidence verification preflight."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator evidence verification preflight schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_evidence_verification_preflight_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordEvidenceVerificationPreflightValidation(
        valid=not errors,
        runtime_validated=not errors,
        verification_preflight_count=int(envelope.get("verification_preflight_count", 0)),
        submitted_evidence_count=int(summary.get("submitted_evidence_count", 0)),
        verification_requirement_count=int(summary.get("verification_requirement_count", 0)),
        satisfied_verification_requirement_count=int(summary.get("satisfied_verification_requirement_count", 0)),
        verified_evidence_count=int(summary.get("verified_evidence_count", 0)),
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_evidence_verification_preflight_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "verification_state": "submitted_refs_scoped_not_verified",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_evidence_acceptance_preflight",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    records = envelope.get("verification_preflights")
    if not isinstance(records, list):
        errors.append("verification_preflights must be a list")
        return tuple(errors)
    if envelope.get("verification_preflight_count") != len(records):
        errors.append("verification_preflight_count must equal verification_preflights length")
    item_ids: list[str] = []
    source_item_ids: list[str] = []
    submitted_evidence_refs: list[str] = []
    receipt_ids: list[str] = []
    evidence_kinds: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"verification_preflights[{index}] must be an object")
            continue
        item_ids.append(str(record.get("verification_preflight_item_id", "")))
        source_item_ids.append(str(record.get("source_acceptance_preflight_item_id", "")))
        submitted_evidence_refs.append(str(record.get("submitted_evidence_ref", "")))
        evidence_kinds.add(str(record.get("evidence_kind", "")))
        _require_source_ref(index, _mapping(record.get("evidence_acceptance_preflight_ref")), errors)
        _require_verification_preflight(index, _mapping(record.get("verification_preflight")), record, errors)
        _require_authority_status(index, _mapping(record.get("authority_status")), errors)
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"verification_preflights[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"verification_preflights[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "blocked" or receipt.get("outcome") != "AwaitingEvidence":
            errors.append(f"verification_preflights[{index}].receipt must remain blocked AwaitingEvidence")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight_is_execution") is not False:
            errors.append(f"verification_preflights[{index}].receipt.metadata execution flag must be false")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "raw_evidence_payload_present",
                    "raw_operator_value_present",
                    "verifier_identity_bound",
                    "verification_method_bound",
                    "evidence_integrity_hash_bound",
                    "source_ref_reachability_witness_bound",
                    "decision_receipt_crosscheck_bound",
                    "evidence_verified",
                    "evidence_accepted",
                    "evidence_rejected",
                    "operator_value_collected",
                    "explicit_operator_value_present",
                    "operator_value_bound",
                    "accepted_value_present",
                    "binding_record_candidate_accepted",
                    "binding_record_created",
                    "binding_record_admitted",
                    "admission_approved",
                    "authority_granted",
                    "execution_worker_admission_allowed",
                    "dispatch_allowed",
                    "dispatch_lease_active",
                    "live_connector_receipt_present",
                    "live_connector_execution_allowed",
                    "connector_mutation_allowed",
                    "external_write_allowed",
                    "system_of_record_write_allowed",
                    "memory_write_allowed",
                    "money_legal_public_action_allowed",
                }
            ),
            f"verification_preflights[{index}].receipt.metadata",
            errors,
        )
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if evidence_kinds != EXPECTED_EVIDENCE_KINDS:
        errors.append("verification_preflights must cover all governed evidence kinds")
    if envelope.get("verification_preflight_item_ids") != item_ids:
        errors.append("verification_preflight_item_ids must match verification preflight order")
    if envelope.get("source_acceptance_preflight_item_ids") != source_item_ids:
        errors.append("source_acceptance_preflight_item_ids must match verification preflight order")
    if envelope.get("submitted_evidence_refs") != submitted_evidence_refs:
        errors.append("submitted_evidence_refs must match verification preflight order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match verification preflight receipts")
    _require_summary(envelope, records, errors)
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "AwaitingEvidence":
        errors.append("assurance.outcome must remain AwaitingEvidence")
    for field_name in (
        "ready_for_evidence_verification",
        "ready_for_evidence_acceptance",
        "ready_for_binding_record_admission",
        "ready_for_execution_worker_admission",
        "ready_for_live_execution",
        "ready_for_customer_readiness_claim",
        "authority_drift_detected",
    ):
        if assurance.get(field_name) is not False:
            errors.append(f"assurance.{field_name} must be false")
    _require_false_fields(_mapping(envelope.get("metadata")), FALSE_EFFECT_BOUNDARY_FIELDS - {"evidence_rejected"}, "metadata", errors)
    return tuple(errors)


def _require_source_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "source_acceptance_state": "submitted_refs_checked_not_verified_not_accepted",
        "source_outcome": "AwaitingEvidence",
        "source_evidence_submitted": True,
        "source_evidence_verified": False,
        "source_evidence_accepted": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"verification_preflights[{index}].evidence_acceptance_preflight_ref.{field_name} must be {expected_value}")


def _require_verification_preflight(
    index: int,
    payload: Mapping[str, Any],
    record: Mapping[str, Any],
    errors: list[str],
) -> None:
    if payload.get("submitted_evidence_ref") != record.get("submitted_evidence_ref"):
        errors.append(f"verification_preflights[{index}].verification_preflight submitted ref must match record")
    if payload.get("submitted_evidence_ref_kind") != record.get("evidence_kind"):
        errors.append(f"verification_preflights[{index}].verification_preflight evidence kind must match record")
    expected_true = {"submitted_evidence_ref_only", "submitted_evidence_ref_present", "evidence_submitted"}
    expected_false = {
        "raw_evidence_payload_present",
        "raw_operator_value_present",
        "evidence_verified",
        "evidence_accepted",
        "evidence_rejected",
        "requirement_satisfied",
    }
    for field_name in expected_true:
        if payload.get(field_name) is not True:
            errors.append(f"verification_preflights[{index}].verification_preflight.{field_name} must be true")
    for field_name in expected_false:
        if payload.get(field_name) is not False:
            errors.append(f"verification_preflights[{index}].verification_preflight.{field_name} must be false")
    for field_name in ("verified_evidence_refs", "accepted_evidence_refs", "rejected_evidence_refs"):
        if payload.get(field_name) != []:
            errors.append(f"verification_preflights[{index}].verification_preflight.{field_name} must remain empty")
    requirements = payload.get("verification_requirements")
    if not isinstance(requirements, list):
        errors.append(f"verification_preflights[{index}].verification_preflight.verification_requirements must be a list")
        return
    kinds = {str(requirement.get("requirement_kind", "")) for requirement in requirements if isinstance(requirement, Mapping)}
    if kinds != EXPECTED_REQUIREMENT_KINDS:
        errors.append(f"verification_preflights[{index}].verification_preflight must include all verification requirement kinds")
    if payload.get("verification_requirement_count") != len(requirements):
        errors.append(f"verification_preflights[{index}].verification_preflight verification_requirement_count mismatch")
    satisfied_count = 0
    for requirement_index, requirement in enumerate(requirements):
        if not isinstance(requirement, Mapping):
            errors.append(f"verification_preflights[{index}].verification_preflight.verification_requirements[{requirement_index}] must be an object")
            continue
        for field_name, expected_value in {"required": True, "ref_present": False, "satisfied": False}.items():
            if requirement.get(field_name) is not expected_value:
                errors.append(
                    f"verification_preflights[{index}].verification_preflight.verification_requirements[{requirement_index}].{field_name} must be {expected_value}"
                )
        if requirement.get("satisfied") is True:
            satisfied_count += 1
    if payload.get("satisfied_verification_requirement_count") != satisfied_count:
        errors.append(f"verification_preflights[{index}].verification_preflight satisfied_verification_requirement_count mismatch")
    if payload.get("blocking_reason") != "verification_requirements_not_satisfied":
        errors.append(f"verification_preflights[{index}].verification_preflight blocking_reason must remain requirements-not-satisfied")


def _require_authority_status(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    _require_false_fields(
        payload,
        frozenset(
            {
                "verifier_identity_bound",
                "verification_method_bound",
                "evidence_integrity_hash_bound",
                "source_ref_reachability_witness_bound",
                "decision_receipt_crosscheck_bound",
                "operator_value_bound",
                "operator_identity_ref_bound",
                "operator_signature_ref_bound",
                "decision_receipt_ref_bound",
                "binding_record_created",
                "binding_record_admitted",
                "authority_granted",
                "execution_worker_admission_allowed",
                "dispatch_allowed",
                "dispatch_lease_active",
                "live_connector_receipt_present",
                "live_connector_execution_allowed",
                "connector_mutation_allowed",
                "system_of_record_write_allowed",
                "memory_write_allowed",
            }
        ),
        f"verification_preflights[{index}].authority_status",
        errors,
    )


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "verification_preflight_count": len(records),
        "submitted_evidence_ref_count": len(records),
        "raw_evidence_payload_count": 0,
        "raw_operator_value_count": 0,
        "submitted_evidence_count": len(records),
        "verified_evidence_count": 0,
        "accepted_evidence_count": 0,
        "rejected_evidence_count": 0,
        "verification_requirement_count": len(records) * len(EXPECTED_REQUIREMENT_KINDS),
        "satisfied_verification_requirement_count": 0,
        "authority_grant_count": 0,
        "binding_record_creation_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "raw_private_payload_serialized": False,
        "secret_values_serialized": False,
        "acceptance_preflight_projection": "requirements_only",
        "submitted_evidence_projection": "ref_only",
        "verification_evidence_projection": "requirements_only",
        "operator_decision_value_projection": "absent",
        "operator_identity_ref_projection": "absent",
        "operator_signature_ref_projection": "absent",
        "decision_receipt_projection": "absent",
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"private_payload_policy.{field_name} must be {expected_value}")


def _require_true_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(fields):
        if payload.get(field_name) is not True:
            errors.append(f"{label}.{field_name} must be true")


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(fields):
        if payload.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} unreadable: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_POLICY_FIELD_NAMES and normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str) and any(pattern.search(payload) for pattern in SECRET_VALUE_PATTERNS):
        errors.append(f"{path}: secret-like value must not be serialized")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_evidence_verification_preflight(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING RECORD EVIDENCE VERIFICATION PREFLIGHT VALID")
    else:
        for error in result.errors:
            print(f"[ERROR] {error}", file=sys.stderr)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
