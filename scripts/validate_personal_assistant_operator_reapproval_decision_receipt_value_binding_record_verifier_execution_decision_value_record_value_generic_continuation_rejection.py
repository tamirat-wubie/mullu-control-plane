#!/usr/bin/env python3
"""Validate operator value-binding verifier execution record value generic continuation rejection."""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_GENERIC_CONTINUATION_REJECTION_GENERATED_AT
EXPECTED_RULE_IDS = (
    "generic-continuation-is-not-explicit-operator-approval",
    "generic-continuation-is-not-explicit-operator-rejection",
    "generic-continuation-is-not-explicit-operator-revision",
    "generic-continuation-is-not-explicit-operator-expiry",
    "generic-continuation-grants-no-verifier-authority",
)
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
FALSE_FIELDS = frozenset(
    {
        "generic_continuation_accepted_as_value",
        "generic_continuation_accepted_as_decision",
        "record_value_generic_continuation_rejection_admitted",
        "record_value_absence_admitted",
        "record_value_collection_gate_satisfied",
        "operator_value_record_created",
        "operator_decision_value_stored",
        "operator_decision_value_present",
        "operator_decision_value_collected",
        "operator_decision_value_admitted",
        "operator_approval_granted",
        "operator_approval_rejected",
        "verifier_execution_allowed",
        "verifier_execution_started",
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
class PersonalAssistantRecordValueGenericContinuationRejectionValidation:
    """Validation result for record value generic continuation rejection."""

    valid: bool
    runtime_validated: bool
    generic_continuation_rejection_count: int
    generic_continuation_rejected_count: int
    actual_operator_decision_value_absent_count: int
    generic_continuation_accepted_as_value_count: int
    operator_decision_value_present_count: int
    operator_value_record_creation_count: int
    verifier_execution_allowed_count: int
    authority_grant_count: int
    rule_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantRecordValueGenericContinuationRejectionValidation:
    """Validate runtime verifier execution record value generic continuation rejection."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "generic continuation rejection schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_generic_continuation_rejection_semantics(envelope, receipt_schema))
    _scan_secret_values(envelope, errors, path="$runtime")
    return PersonalAssistantRecordValueGenericContinuationRejectionValidation(
        valid=not errors,
        runtime_validated=not errors,
        generic_continuation_rejection_count=int(envelope.get("generic_continuation_rejection_count", 0)),
        generic_continuation_rejected_count=int(summary.get("generic_continuation_rejected_count", 0)),
        actual_operator_decision_value_absent_count=int(summary.get("actual_operator_decision_value_absent_count", 0)),
        generic_continuation_accepted_as_value_count=int(summary.get("generic_continuation_accepted_as_value_count", 0)),
        operator_decision_value_present_count=int(summary.get("operator_decision_value_present_count", 0)),
        operator_value_record_creation_count=int(summary.get("operator_value_record_creation_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        rule_count=int(summary.get("rule_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_generic_continuation_rejection_semantics(envelope: Mapping[str, Any], receipt_schema: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "generic_continuation_rejection_state": "generic_continuation_rejected_not_operator_value",
        "decision": "blocked",
        "outcome": "SolvedVerified",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_absence",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "generic_continuation_rejected",
        "actual_operator_decision_value_absent",
        "record_value_absences_present",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(effect_boundary, FALSE_FIELDS, "effect_boundary", errors)

    records = envelope.get("generic_continuation_rejections")
    if not isinstance(records, list):
        errors.append("generic_continuation_rejections must be a list")
        return tuple(errors)
    if envelope.get("generic_continuation_rejection_count") != len(records):
        errors.append("generic_continuation_rejection_count must equal generic_continuation_rejections length")
    item_ids: list[str] = []
    receipt_ids: list[str] = []
    coverage: dict[str, set[str]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"generic_continuation_rejections[{index}] must be an object")
            continue
        item_ids.append(str(record.get("generic_continuation_rejection_item_id", "")))
        evidence_kind = str(record.get("evidence_kind", ""))
        requirement_kind = str(record.get("requirement_kind", ""))
        coverage.setdefault(evidence_kind, set()).add(requirement_kind)
        _require_source_ref(index, _mapping(record.get("record_value_absence_ref")), errors)
        _require_rejection(index, _mapping(record.get("generic_continuation_rejection")), errors)
        _require_false_fields(_mapping(record.get("authority_status")), FALSE_FIELDS | {"operator_value_bound"}, f"generic_continuation_rejections[{index}].authority_status", errors)
        receipt = _mapping(record.get("receipt"))
        if receipt_schema:
            errors.extend(f"generic_continuation_rejections[{index}].receipt {message}" for message in _validate_schema_instance(dict(receipt_schema), receipt))
        errors.extend(f"generic_continuation_rejections[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection_is_execution") is not False:
            errors.append(f"generic_continuation_rejections[{index}].receipt.metadata execution flag must be false")
        if metadata.get("generic_continuation_rejected") is not True:
            errors.append(f"generic_continuation_rejections[{index}].receipt.metadata generic_continuation_rejected must be true")
        _require_false_fields(metadata, FALSE_FIELDS | {"external_write_allowed"}, f"generic_continuation_rejections[{index}].receipt.metadata", errors)
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if set(coverage) != EXPECTED_EVIDENCE_KINDS:
        errors.append("generic_continuation_rejections must cover all governed evidence kinds")
    for evidence_kind, requirement_kinds in coverage.items():
        if requirement_kinds != EXPECTED_REQUIREMENT_KINDS:
            errors.append(f"generic_continuation_rejections for {evidence_kind} must cover all verifier requirement kinds")
    if envelope.get("generic_continuation_rejection_item_ids") != item_ids:
        errors.append("generic_continuation_rejection_item_ids must match item order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match item receipts")
    _require_summary(envelope, records, errors)
    return tuple(errors)


def _require_source_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "source_record_value_absence_state": "operator_decision_value_record_value_absent_not_collected_not_admitted",
        "source_outcome": "AwaitingEvidence",
        "source_record_contract_ready": True,
        "source_actual_operator_decision_value_absent": True,
        "source_operator_decision_value_present": False,
        "source_operator_value_record_created": False,
        "source_verifier_execution_allowed": False,
        "source_authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"generic_continuation_rejections[{index}].record_value_absence_ref.{field_name} must be {expected_value}")


def _require_rejection(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected_true = ("generic_continuation_rejected", "actual_operator_decision_value_absent")
    for field_name in expected_true:
        if payload.get(field_name) is not True:
            errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.{field_name} must be true")
    expected_values = {
        "observed_input_kind": "generic_continuation",
        "rejected_input_kind": "generic_continuation",
        "rejected_reason": "not_explicit_operator_decision_value",
    }
    for field_name, expected_value in expected_values.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.{field_name} must be {expected_value}")
    _require_false_fields(payload, FALSE_FIELDS, f"generic_continuation_rejections[{index}].generic_continuation_rejection", errors)
    rules = payload.get("rejection_rules")
    if not isinstance(rules, list):
        errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.rejection_rules must be a list")
        return
    if tuple(str(rule.get("rule_id", "")) for rule in rules if isinstance(rule, dict)) != EXPECTED_RULE_IDS:
        errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.rejection_rules must match canonical rules")
    for rule_index, rule in enumerate(rules):
        if not isinstance(rule, Mapping):
            errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.rejection_rules[{rule_index}] must be an object")
            continue
        if rule.get("applies") is not True or rule.get("decision") != "reject":
            errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.rejection_rules[{rule_index}] must reject")
        if rule.get("grants_authority") is not False or rule.get("grants_verifier_execution") is not False:
            errors.append(f"generic_continuation_rejections[{index}].generic_continuation_rejection.rejection_rules[{rule_index}] must grant no authority")


def _require_summary(envelope: Mapping[str, Any], records: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "generic_continuation_rejection_count": len(records),
        "generic_continuation_rejected_count": len(records),
        "actual_operator_decision_value_absent_count": len(records),
        "generic_continuation_accepted_as_value_count": 0,
        "generic_continuation_accepted_as_decision_count": 0,
        "operator_decision_value_present_count": 0,
        "operator_value_record_creation_count": 0,
        "verifier_execution_allowed_count": 0,
        "authority_grant_count": 0,
        "rule_count": len(records) * len(EXPECTED_RULE_IDS),
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")


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
    """Run the record value generic continuation rejection validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_generic_continuation_rejection(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("personal assistant verifier execution record value generic continuation rejection: valid")
    else:
        print("personal assistant verifier execution record value generic continuation rejection: invalid")
        for error in validation.errors:
            print(f"  - {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
