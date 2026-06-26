#!/usr/bin/env python3
"""Validate personal-assistant operator reapproval decision receipt value absence.

Purpose: prove a requested operator reapproval decision receipt value is absent
and therefore execution-worker admission remains blocked.
Governance scope: value-request refs, missing decision values, receipt
conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant operator reapproval decision receipt value
absence runtime helper, schema validators, and receipt validator.
Invariants:
  - Absence witnesses must not claim operator decision values, identity refs,
    signatures, or submitted decision receipts.
  - Execution-worker admission, dispatch, live connector execution, connector
    mutation, memory writes, system-of-record writes, and readiness claims
    remain false.
"""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_ABSENCE_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_absence.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_ABSENCE_GENERATED_AT
EXPECTED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_absence_witness_allowed",
        "value_request_ref_binding_allowed",
        "decision_receipt_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "operator_receipt_submission_required",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "decision_value_present",
        "fresh_operator_decision_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "operator_reapproval_receipt_present",
        "decision_receipt_present",
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
        "operator_identity_ref",
        "operator_signature",
        "raw_decision_receipt",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "value_request_projection",
        "decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
        "receipt_intake_digest",
        "value_request_digest",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueAbsenceValidation:
    """Validation result for no-effect operator reapproval decision value absence."""

    valid: bool
    runtime_validated: bool
    absence_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_operator_reapproval_decision_receipt_value_absence(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueAbsenceValidation:
    """Validate the runtime operator reapproval decision receipt value absence envelope."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator reapproval decision receipt value absence schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_absence(
        generated_at=RUNTIME_GENERATED_AT,
    )
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_operator_reapproval_decision_receipt_value_absence_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueAbsenceValidation(
        valid=not errors,
        runtime_validated=not errors,
        absence_count=int(envelope.get("absence_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_operator_reapproval_decision_receipt_value_absence_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    absences = envelope.get("absences")
    if not isinstance(absences, list):
        errors.append("absences must be a list")
        return tuple(errors)
    if envelope.get("absence_count") != len(absences):
        errors.append("absence_count must equal absences length")
    absence_ids: list[str] = []
    source_value_request_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, absence in enumerate(absences):
        if not isinstance(absence, dict):
            errors.append(f"absences[{index}] must be an object")
            continue
        absence_ids.append(str(absence.get("absence_id", "")))
        source_value_request_ids.append(str(absence.get("source_value_request_id", "")))
        approval_id = str(absence.get("approval_id", ""))
        _require_value_request_ref(index, approval_id, _mapping(absence.get("value_request_ref")), errors)
        _require_absence_witness(index, _mapping(absence.get("absence_witness")), errors)
        _require_execution_block(index, _mapping(absence.get("execution_admission_block")), errors)
        receipt = _mapping(absence.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"absences[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"absences[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "deferred":
            errors.append(f"absences[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != absence.get("approval_id"):
            errors.append(f"absences[{index}].receipt.approval_ref must match approval_id")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_absence_is_execution") is not False:
            errors.append(
                "absences["
                f"{index}].receipt.metadata.operator_reapproval_decision_receipt_value_absence_is_execution must be false"
            )
        if metadata.get("value_request_ref_bound") is not True:
            errors.append(f"absences[{index}].receipt.metadata.value_request_ref_bound must be true")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "operator_decision_value_present",
                    "operator_identity_ref_present",
                    "operator_signature_ref_present",
                    "decision_receipt_present",
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
            f"absences[{index}].receipt.metadata",
            errors,
        )
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if envelope.get("absence_ids") != absence_ids:
        errors.append("absence_ids must match absences order")
    if envelope.get("source_value_request_ids") != source_value_request_ids:
        errors.append("source_value_request_ids must match absences order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if payload.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    if payload.get("value_request_projection") != "ref_only":
        errors.append("private_payload_policy.value_request_projection must be ref_only")
    if payload.get("decision_value_projection") != "absent":
        errors.append("private_payload_policy.decision_value_projection must be absent")
    if payload.get("operator_identity_ref_projection") != "absent":
        errors.append("private_payload_policy.operator_identity_ref_projection must be absent")
    if payload.get("operator_signature_projection") != "absent":
        errors.append("private_payload_policy.operator_signature_projection must be absent")
    if payload.get("decision_receipt_projection") != "absent":
        errors.append("private_payload_policy.decision_receipt_projection must be absent")


def _require_value_request_ref(index: int, approval_id: str, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected_ref = f"receipt://personal-assistant/operator-reapproval-decision-value-request/{approval_id}"
    if payload.get("value_request_ref") != expected_ref:
        errors.append(f"absences[{index}].value_request_ref.value_request_ref must match approval_id")
    if tuple(payload.get("accepted_decision_values", ())) != EXPECTED_DECISION_VALUES:
        errors.append(f"absences[{index}].value_request_ref.accepted_decision_values must match canonical values")
    for field_name in (
        "operator_decision_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if payload.get(field_name) is not True:
            errors.append(f"absences[{index}].value_request_ref.{field_name} must be true")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
        "execution_worker_admission_allowed",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"absences[{index}].value_request_ref.{field_name} must be false")


def _require_absence_witness(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("absence_reason") != "operator_reapproval_decision_receipt_value_absent":
        errors.append(f"absences[{index}].absence_witness.absence_reason must be canonical")
    if payload.get("required_next_evidence") != "governed_operator_reapproval_decision_receipt_value":
        errors.append(f"absences[{index}].absence_witness.required_next_evidence must be canonical")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"absences[{index}].absence_witness.{field_name} must be false")


def _require_execution_block(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("execution_worker_admission_state") != "blocked_missing_operator_reapproval_decision_receipt_value":
        errors.append(f"absences[{index}].execution_admission_block.execution_worker_admission_state must be blocked")
    for field_name in (
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "external_send_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"absences[{index}].execution_admission_block.{field_name} must be false")


def _require_true_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(fields):
        if payload.get(field_name) is not True:
            errors.append(f"{label}.{field_name} must be true")


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(fields):
        if payload.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in ALLOWED_POLICY_FIELD_NAMES and normalized_key in RAW_PRIVATE_FIELD_NAMES:
                errors.append(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, errors, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, errors, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(payload):
                errors.append(f"{path}: secret-like value must not be serialized")
                break


def _mapping(payload: Any) -> dict[str, Any]:
    return dict(payload) if isinstance(payload, dict) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append(f"{label} could not be read")
        return {}
    except json.JSONDecodeError:
        errors.append(f"{label} must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label} root must be an object")
        return {}
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse operator reapproval decision receipt value absence validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate personal-assistant operator reapproval decision receipt value absence evidence.",
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator reapproval decision receipt value absence validation."""

    args = parse_args(argv)
    result = validate_personal_assistant_operator_reapproval_decision_receipt_value_absence(
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant operator reapproval decision receipt value absence ok "
            f"absences={result.absence_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
