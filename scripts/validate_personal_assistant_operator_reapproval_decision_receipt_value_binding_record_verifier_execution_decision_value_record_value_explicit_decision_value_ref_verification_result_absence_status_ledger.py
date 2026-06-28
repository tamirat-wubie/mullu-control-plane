#!/usr/bin/env python3
"""Validate operator value-binding explicit decision value-ref result absence ledger."""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_VERIFICATION_RESULT_ABSENCE_STATUS_LEDGER_GENERATED_AT
EXPECTED_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
FALSE_FIELDS = frozenset(
    {
        "explicit_decision_value_ref_verification_result_absence_status_ledger_satisfied",
        "explicit_decision_value_ref_verification_result_absence_satisfied",
        "explicit_decision_value_ref_verification_result_request_satisfied",
        "explicit_decision_value_refs_verified",
        "explicit_decision_value_refs_accepted",
        "explicit_decision_value_refs_bound",
        "explicit_decision_value_refs_validated",
        "explicit_decision_value_refs_stored",
        "verification_result_present",
        "verification_result_accepted",
        "verification_result_bound",
        "verification_result_stored",
        "operator_value_record_created",
        "operator_decision_value_stored",
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "operator_decision_value_admitted",
        "operator_approval_granted",
        "operator_approval_rejected",
        "ready_for_verifier_execution",
        "verifier_execution_allowed",
        "verifier_execution_started",
        "verifier_execution_completed",
        "verifier_result_present",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
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


@dataclass(frozen=True, slots=True)
class PersonalAssistantExplicitDecisionValueRefVerificationResultAbsenceStatusLedgerValidation:
    """Validation result for explicit decision value-ref result absence ledger."""

    valid: bool
    runtime_validated: bool
    absence_status_count: int
    verification_result_requested_count: int
    verification_result_absence_recorded_count: int
    verification_result_absence_status_ledgered_count: int
    verification_result_present_count: int
    submitted_ref_only_count: int
    verified_ref_count: int
    accepted_ref_count: int
    bound_ref_count: int
    validated_ref_count: int
    stored_ref_count: int
    raw_result_payload_count: int
    raw_operator_value_count: int
    operator_value_record_creation_count: int
    verifier_execution_allowed_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantExplicitDecisionValueRefVerificationResultAbsenceStatusLedgerValidation:
    """Validate runtime verifier execution explicit decision value-ref absence ledger."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "explicit decision value-ref verification result absence status ledger schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_explicit_decision_value_ref_verification_result_absence_status_ledger_semantics(envelope, receipt_schema))
    _scan_secret_values(envelope, errors, path="$runtime")
    return PersonalAssistantExplicitDecisionValueRefVerificationResultAbsenceStatusLedgerValidation(
        valid=not errors,
        runtime_validated=not errors,
        absence_status_count=int(summary.get("absence_status_count", 0)),
        verification_result_requested_count=int(summary.get("verification_result_requested_count", 0)),
        verification_result_absence_recorded_count=int(summary.get("verification_result_absence_recorded_count", 0)),
        verification_result_absence_status_ledgered_count=int(summary.get("verification_result_absence_status_ledgered_count", 0)),
        verification_result_present_count=int(summary.get("verification_result_present_count", 0)),
        submitted_ref_only_count=int(summary.get("submitted_ref_only_count", 0)),
        verified_ref_count=int(summary.get("verified_ref_count", 0)),
        accepted_ref_count=int(summary.get("accepted_ref_count", 0)),
        bound_ref_count=int(summary.get("bound_ref_count", 0)),
        validated_ref_count=int(summary.get("validated_ref_count", 0)),
        stored_ref_count=int(summary.get("stored_ref_count", 0)),
        raw_result_payload_count=int(summary.get("raw_result_payload_count", 0)),
        raw_operator_value_count=int(summary.get("raw_operator_value_count", 0)),
        operator_value_record_creation_count=int(summary.get("operator_value_record_creation_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_explicit_decision_value_ref_verification_result_absence_status_ledger_semantics(envelope: Mapping[str, Any], receipt_schema: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "explicit_decision_value_ref_verification_result_absence_status_ledger_state": "verification_result_absence_status_ledgered",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")

    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "required_value_refs_submitted",
        "submitted_ref_only",
        "verification_preflight_checked",
        "verification_result_requested",
        "verification_result_absence_recorded",
        "verification_result_absence_status_ledgered",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(effect_boundary, FALSE_FIELDS, "effect_boundary", errors)

    statuses = envelope.get("absence_statuses")
    if not isinstance(statuses, list):
        errors.append("absence_statuses must be a list")
        return tuple(errors)
    if envelope.get("absence_status_count") != len(EXPECTED_REQUIRED_VALUE_REFS):
        errors.append("absence_status_count must equal four canonical required refs")
    status_ids: list[str] = []
    source_absence_record_ids: list[str] = []
    submitted_ref_uris: list[str] = []
    names: list[str] = []
    for index, status in enumerate(statuses):
        if not isinstance(status, dict):
            errors.append(f"absence_statuses[{index}] must be an object")
            continue
        status_ids.append(str(status.get("absence_status_id", "")))
        source_absence_record_ids.append(str(status.get("source_absence_record_id", "")))
        submitted_ref_uris.append(str(status.get("submitted_ref_uri", "")))
        names.append(str(status.get("ref_name", "")))
        _require_status(index, status, errors)
    if tuple(names) != EXPECTED_REQUIRED_VALUE_REFS:
        errors.append("absence_statuses must match canonical required ref order")
    if envelope.get("absence_status_ids") != status_ids:
        errors.append("absence_status_ids must match status order")
    if envelope.get("source_absence_record_ids") != source_absence_record_ids:
        errors.append("source_absence_record_ids must match status order")
    if envelope.get("submitted_ref_uris") != submitted_ref_uris:
        errors.append("submitted_ref_uris must match status order")

    receipt = _mapping(envelope.get("receipt"))
    if receipt_schema:
        errors.extend(f"receipt {message}" for message in _validate_schema_instance(dict(receipt_schema), receipt))
    errors.extend(f"receipt {message}" for message in validate_personal_assistant_receipt_payload(dict(receipt)))
    metadata = _mapping(receipt.get("metadata"))
    if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger_is_execution") is not False:
        errors.append("receipt.metadata execution flag must be false")
    if metadata.get("verification_result_absence_status_ledgered") is not True:
        errors.append("receipt.metadata verification_result_absence_status_ledgered must be true")
    if metadata.get("verification_result_present") is not False:
        errors.append("receipt.metadata verification_result_present must be false")
    if metadata.get("submitted_ref_only") is not True:
        errors.append("receipt.metadata submitted_ref_only must be true")
    _require_false_fields(metadata, FALSE_FIELDS | {"external_write_allowed"}, "receipt.metadata", errors)
    _require_summary(envelope, statuses, errors)
    return tuple(errors)


def _require_status(index: int, status: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "status": "verification_result_absent_after_request",
        "verification_result_requested": True,
        "verification_result_absence_recorded": True,
        "verification_result_absence_status_ledgered": True,
        "verification_result_present": False,
        "submitted_ref_only": True,
        "raw_result_payload_present": False,
        "raw_operator_value_present": False,
        "verified": False,
        "accepted": False,
        "bound": False,
        "validated": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if status.get(field_name) != expected_value:
            errors.append(f"absence_statuses[{index}].{field_name} must be {expected_value}")
    ref_name = str(status.get("ref_name", ""))
    expected_uri = (
        "evidence://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-submitted/"
        f"{ref_name}"
    )
    if status.get("submitted_ref_uri") != expected_uri:
        errors.append(f"absence_statuses[{index}].submitted_ref_uri must match ref_name")
    if status.get("blocking_reason") != f"{ref_name}_verification_result_absent":
        errors.append(f"absence_statuses[{index}].blocking_reason must match ref_name")


def _require_summary(envelope: Mapping[str, Any], statuses: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "absence_status_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "verification_result_requested_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "verification_result_absence_recorded_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "verification_result_absence_status_ledgered_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "verification_result_present_count": 0,
        "submitted_ref_only_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "verified_ref_count": 0,
        "accepted_ref_count": 0,
        "bound_ref_count": 0,
        "validated_ref_count": 0,
        "stored_ref_count": 0,
        "raw_result_payload_count": 0,
        "raw_operator_value_count": 0,
        "operator_value_record_creation_count": 0,
        "verifier_execution_allowed_count": 0,
        "authority_grant_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")
    if len(statuses) != len(EXPECTED_REQUIRED_VALUE_REFS):
        errors.append("summary source absence status count must stay canonical")


def _require_false_fields(payload: Mapping[str, Any], field_names: set[str] | frozenset[str], path: str, errors: list[str]) -> None:
    for field_name in sorted(field_names):
        if field_name in payload and payload.get(field_name) is not False:
            errors.append(f"{path}.{field_name} must be false")


def _scan_secret_values(value: Any, errors: list[str], *, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _scan_secret_values(child, errors, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _scan_secret_values(child, errors, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                errors.append(f"{path} must not contain secret-like values")


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
        errors.append(f"{label} must be an object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def main(argv: list[str] | None = None) -> int:
    """Run the explicit decision value-ref verification result absence status ledger validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_verification_result_absence_status_ledger(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("personal assistant verifier execution explicit decision value-ref verification result absence status ledger: valid")
    else:
        print("personal assistant verifier execution explicit decision value-ref verification result absence status ledger: invalid")
        for error in validation.errors:
            print(f"  - {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
