#!/usr/bin/env python3
"""Validate operator value-binding submitted evidence ref intake."""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_SUBMITTED_EVIDENCE_REF_INTAKE_GENERATED_AT
EXPECTED_EVIDENCE_KINDS = frozenset(
    {
        "operator_decision_value_ref",
        "operator_identity_ref",
        "operator_signature_ref",
        "operator_reapproval_decision_receipt_ref",
    }
)
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_allowed",
        "evidence_request_status_ledger_ref_binding_allowed",
        "submitted_evidence_ref_recording_allowed",
        "submitted_evidence_refs_present",
        "evidence_submitted",
        "evidence_ref_only",
        "status_ledger_is_source",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "raw_evidence_payload_present",
        "raw_operator_value_present",
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
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "status_ledger_projection",
        "submitted_evidence_projection",
        "operator_decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_ref_projection",
        "decision_receipt_projection",
        "evidence_acceptance_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordSubmittedEvidenceRefIntakeValidation:
    """Validation result for submitted evidence ref intake."""

    valid: bool
    runtime_validated: bool
    submission_record_count: int
    submitted_evidence_count: int
    accepted_evidence_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordSubmittedEvidenceRefIntakeValidation:
    """Validate runtime submitted evidence ref intake."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator submitted evidence ref intake schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_submitted_evidence_ref_intake_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingRecordSubmittedEvidenceRefIntakeValidation(
        valid=not errors,
        runtime_validated=not errors,
        submission_record_count=int(envelope.get("submission_record_count", 0)),
        submitted_evidence_count=int(summary.get("submitted_evidence_count", 0)),
        accepted_evidence_count=int(summary.get("accepted_evidence_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_submitted_evidence_ref_intake_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "intake_state": "submitted_refs_recorded_not_accepted",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_evidence_request_status_ledger",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    records = envelope.get("submission_records")
    if not isinstance(records, list):
        errors.append("submission_records must be a list")
        return tuple(errors)
    if envelope.get("submission_record_count") != len(records):
        errors.append("submission_record_count must equal submission_records length")
    submission_record_ids: list[str] = []
    source_status_record_ids: list[str] = []
    submitted_evidence_refs: list[str] = []
    receipt_ids: list[str] = []
    evidence_kinds: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"submission_records[{index}] must be an object")
            continue
        submission_record_ids.append(str(record.get("submission_record_id", "")))
        source_status_record_ids.append(str(record.get("source_status_record_id", "")))
        submitted_evidence_refs.append(str(record.get("submitted_evidence_ref", "")))
        evidence_kinds.add(str(record.get("evidence_kind", "")))
        _require_status_ledger_ref(index, _mapping(record.get("status_ledger_ref")), errors)
        _require_submitted_evidence(index, _mapping(record.get("submitted_evidence")), record, errors)
        _require_authority_status(index, _mapping(record.get("authority_status")), errors)
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"submission_records[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"submission_records[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "blocked" or receipt.get("outcome") != "AwaitingEvidence":
            errors.append(f"submission_records[{index}].receipt must remain blocked AwaitingEvidence")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake_is_execution") is not False:
            errors.append(f"submission_records[{index}].receipt.metadata execution flag must be false")
        if metadata.get("ref_only_submission") is not True:
            errors.append(f"submission_records[{index}].receipt.metadata.ref_only_submission must be true")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "raw_evidence_payload_present",
                    "raw_operator_value_present",
                    "evidence_accepted",
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
            f"submission_records[{index}].receipt.metadata",
            errors,
        )
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if evidence_kinds != EXPECTED_EVIDENCE_KINDS:
        errors.append("submission_records must cover all governed evidence kinds")
    if envelope.get("submission_record_ids") != submission_record_ids:
        errors.append("submission_record_ids must match submission record order")
    if envelope.get("source_status_record_ids") != source_status_record_ids:
        errors.append("source_status_record_ids must match submission record order")
    if envelope.get("submitted_evidence_refs") != submitted_evidence_refs:
        errors.append("submitted_evidence_refs must match submission record order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match submission record receipts")
    _require_summary(envelope, records, errors)
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "AwaitingEvidence":
        errors.append("assurance.outcome must remain AwaitingEvidence")
    for field_name in (
        "ready_for_evidence_acceptance",
        "ready_for_binding_record_admission",
        "ready_for_execution_worker_admission",
        "ready_for_live_execution",
        "ready_for_customer_readiness_claim",
        "authority_drift_detected",
    ):
        if assurance.get(field_name) is not False:
            errors.append(f"assurance.{field_name} must be false")
    metadata = _mapping(envelope.get("metadata"))
    if metadata.get("ref_only_submission") is not True:
        errors.append("metadata.ref_only_submission must be true")
    _require_false_fields(
        metadata,
        FALSE_EFFECT_BOUNDARY_FIELDS - {"evidence_rejected"},
        "metadata",
        errors,
    )
    return tuple(errors)


def _require_status_ledger_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "source_ledger_state": "requested_not_submitted",
        "source_outcome": "AwaitingEvidence",
        "source_evidence_submitted": False,
        "source_evidence_accepted": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"submission_records[{index}].status_ledger_ref.{field_name} must be {expected_value!r}")


def _require_submitted_evidence(index: int, payload: Mapping[str, Any], record: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "submitted_evidence_ref_kind": record.get("evidence_kind"),
        "submitted_evidence_ref_only": True,
        "raw_evidence_payload_present": False,
        "raw_operator_value_present": False,
        "evidence_submitted": True,
        "evidence_accepted": False,
        "evidence_rejected": False,
        "requirement_satisfied": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"submission_records[{index}].submitted_evidence.{field_name} must be {expected_value!r}")
    if payload.get("submitted_evidence_ref") != record.get("submitted_evidence_ref"):
        errors.append(f"submission_records[{index}].submitted_evidence.submitted_evidence_ref must match record")
    for field_name in ("accepted_evidence_refs", "rejected_evidence_refs"):
        if payload.get(field_name) != []:
            errors.append(f"submission_records[{index}].submitted_evidence.{field_name} must remain empty")


def _require_authority_status(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    _require_false_fields(
        payload,
        frozenset(
            {
                "operator_value_bound",
                "operator_identity_ref_bound",
                "operator_signature_ref_bound",
                "decision_receipt_ref_bound",
                "binding_record_created",
                "binding_record_admitted",
                "authority_granted",
                "execution_worker_admission_allowed",
                "dispatch_allowed",
                "live_connector_execution_allowed",
                "connector_mutation_allowed",
                "system_of_record_write_allowed",
                "memory_write_allowed",
            }
        ),
        f"submission_records[{index}].authority_status",
        errors,
    )


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    submitted = [_mapping(record.get("submitted_evidence")) for record in records if isinstance(record, Mapping)]
    authorities = [_mapping(record.get("authority_status")) for record in records if isinstance(record, Mapping)]
    expected_counts = {
        "submission_record_count": len(records),
        "submitted_evidence_ref_count": sum(1 for record in submitted if record.get("submitted_evidence_ref_only") is True),
        "raw_evidence_payload_count": sum(1 for record in submitted if record.get("raw_evidence_payload_present") is True),
        "raw_operator_value_count": sum(1 for record in submitted if record.get("raw_operator_value_present") is True),
        "submitted_evidence_count": sum(1 for record in submitted if record.get("evidence_submitted") is True),
        "accepted_evidence_count": sum(1 for record in submitted if record.get("evidence_accepted") is True),
        "rejected_evidence_count": sum(1 for record in submitted if record.get("evidence_rejected") is True),
        "satisfied_requirement_count": sum(1 for record in submitted if record.get("requirement_satisfied") is True),
        "authority_grant_count": sum(1 for status in authorities if status.get("authority_granted") is True),
        "binding_record_creation_count": sum(1 for status in authorities if status.get("binding_record_created") is True),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"summary.{field_name} must match submission records")


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "raw_private_payload_serialized": False,
        "secret_values_serialized": False,
        "status_ledger_projection": "ref_only",
        "submitted_evidence_projection": "ref_only",
        "operator_decision_value_projection": "absent",
        "operator_identity_ref_projection": "absent",
        "operator_signature_ref_projection": "absent",
        "decision_receipt_projection": "absent",
        "evidence_acceptance_projection": "absent",
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"private_payload_policy.{field_name} must be {expected_value!r}")


def _require_true_fields(payload: Mapping[str, Any], field_names: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(field_names):
        if payload.get(field_name) is not True:
            errors.append(f"{label}.{field_name} must be true")


def _require_false_fields(payload: Mapping[str, Any], field_names: frozenset[str], label: str, errors: list[str]) -> None:
    for field_name in sorted(field_names):
        if payload.get(field_name) is not False:
            errors.append(f"{label}.{field_name} must be false")


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
    elif isinstance(payload, str):
        if any(pattern.search(payload) for pattern in SECRET_VALUE_PATTERNS):
            errors.append(f"{path}: secret-like value must not be serialized")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation result.")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_submitted_evidence_ref_intake(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING RECORD SUBMITTED EVIDENCE REF INTAKE VALID")
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}", file=sys.stderr)
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
