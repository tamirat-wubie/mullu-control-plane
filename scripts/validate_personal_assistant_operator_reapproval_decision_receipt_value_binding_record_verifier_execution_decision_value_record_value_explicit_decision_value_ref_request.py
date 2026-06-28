#!/usr/bin/env python3
"""Validate operator value-binding explicit decision value-ref request."""

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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_RECORD_VERIFIER_EXECUTION_DECISION_VALUE_RECORD_VALUE_EXPLICIT_DECISION_VALUE_REF_REQUEST_GENERATED_AT
EXPECTED_REQUIRED_VALUE_REFS = (
    "operator_decision_value_ref",
    "operator_identity_ref",
    "operator_signature_ref",
    "operator_reapproval_decision_receipt_ref",
)
FALSE_FIELDS = frozenset(
    {
        "explicit_decision_value_ref_request_satisfied",
        "explicit_decision_value_ref_status_ledger_satisfied",
        "explicit_decision_value_ref_preflight_satisfied",
        "explicit_decision_value_refs_collected",
        "explicit_decision_value_refs_present",
        "explicit_operator_decision_value_bound",
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
class PersonalAssistantExplicitDecisionValueRefRequestValidation:
    """Validation result for explicit decision value-ref request."""

    valid: bool
    runtime_validated: bool
    required_ref_request_count: int
    required_ref_requested_count: int
    required_ref_collected_count: int
    required_ref_present_count: int
    required_ref_bound_count: int
    required_ref_accepted_count: int
    required_ref_stored_count: int
    operator_value_record_creation_count: int
    verifier_execution_allowed_count: int
    authority_grant_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantExplicitDecisionValueRefRequestValidation:
    """Validate runtime verifier execution explicit decision value-ref request."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "explicit decision value-ref request schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request(
        generated_at=RUNTIME_GENERATED_AT,
    )
    summary = _mapping(envelope.get("summary"))
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_explicit_decision_value_ref_request_semantics(envelope, receipt_schema))
    _scan_secret_values(envelope, errors, path="$runtime")
    return PersonalAssistantExplicitDecisionValueRefRequestValidation(
        valid=not errors,
        runtime_validated=not errors,
        required_ref_request_count=int(summary.get("required_ref_request_count", 0)),
        required_ref_requested_count=int(summary.get("required_ref_requested_count", 0)),
        required_ref_collected_count=int(summary.get("required_ref_collected_count", 0)),
        required_ref_present_count=int(summary.get("required_ref_present_count", 0)),
        required_ref_bound_count=int(summary.get("required_ref_bound_count", 0)),
        required_ref_accepted_count=int(summary.get("required_ref_accepted_count", 0)),
        required_ref_stored_count=int(summary.get("required_ref_stored_count", 0)),
        operator_value_record_creation_count=int(summary.get("operator_value_record_creation_count", 0)),
        verifier_execution_allowed_count=int(summary.get("verifier_execution_allowed_count", 0)),
        authority_grant_count=int(summary.get("authority_grant_count", 0)),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_explicit_decision_value_ref_request_semantics(envelope: Mapping[str, Any], receipt_schema: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    expected_top = {
        "explicit_decision_value_ref_request_state": "required_explicit_decision_value_refs_requested_not_collected",
        "decision": "blocked",
        "outcome": "AwaitingEvidence",
        "source_projection": "operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_status_ledger",
    }
    for field_name, expected_value in expected_top.items():
        if envelope.get(field_name) != expected_value:
            errors.append(f"{field_name} must be {expected_value}")
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    for field_name in (
        "required_value_refs_declared",
        "required_value_refs_requested",
        "required_value_refs_absent",
        "operator_decision_required",
        "operator_decision_value_required",
        "record_contract_ready",
        "verifier_ref_only",
    ):
        if effect_boundary.get(field_name) is not True:
            errors.append(f"effect_boundary.{field_name} must be true")
    _require_false_fields(effect_boundary, FALSE_FIELDS, "effect_boundary", errors)

    requests = envelope.get("required_ref_requests")
    if not isinstance(requests, list):
        errors.append("required_ref_requests must be a list")
        return tuple(errors)
    if envelope.get("required_ref_request_count") != len(EXPECTED_REQUIRED_VALUE_REFS):
        errors.append("required_ref_request_count must equal four canonical required refs")
    ids: list[str] = []
    names: list[str] = []
    for index, request in enumerate(requests):
        if not isinstance(request, dict):
            errors.append(f"required_ref_requests[{index}] must be an object")
            continue
        ids.append(str(request.get("required_ref_request_id", "")))
        names.append(str(request.get("ref_name", "")))
        _require_request(index, request, errors)
    if tuple(names) != EXPECTED_REQUIRED_VALUE_REFS:
        errors.append("required_ref_requests must match canonical required ref order")
    if envelope.get("required_ref_request_ids") != ids:
        errors.append("required_ref_request_ids must match request order")

    receipt = _mapping(envelope.get("receipt"))
    if receipt_schema:
        errors.extend(f"receipt {message}" for message in _validate_schema_instance(dict(receipt_schema), receipt))
    errors.extend(f"receipt {message}" for message in validate_personal_assistant_receipt_payload(dict(receipt)))
    metadata = _mapping(receipt.get("metadata"))
    if metadata.get("operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request_is_execution") is not False:
        errors.append("receipt.metadata execution flag must be false")
    if metadata.get("required_value_refs_requested") is not True:
        errors.append("receipt.metadata required_value_refs_requested must be true")
    if metadata.get("required_value_refs_collected") is not False:
        errors.append("receipt.metadata required_value_refs_collected must be false")
    _require_false_fields(metadata, FALSE_FIELDS | {"external_write_allowed"}, "receipt.metadata", errors)
    _require_summary(envelope, requests, errors)
    return tuple(errors)


def _require_request(index: int, request: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "request_status": "requested_not_collected",
        "request_required": True,
        "missing": True,
        "present": False,
        "bound": False,
        "validated": False,
        "collected": False,
        "accepted": False,
        "stored": False,
        "grants_authority": False,
        "grants_verifier_execution": False,
        "operator_value_record_created": False,
        "verifier_execution_allowed": False,
        "authority_granted": False,
    }
    for field_name, expected_value in expected.items():
        if request.get(field_name) != expected_value:
            errors.append(f"required_ref_requests[{index}].{field_name} must be {expected_value}")
    ref_name = str(request.get("ref_name", ""))
    expected_uri = (
        "proof://personal-assistant/operator-reapproval-decision-receipt-value-binding-record-verifier-execution-decision-value-record-value-explicit-decision-value-ref-request/"
        f"{ref_name}"
    )
    if request.get("requested_evidence_uri") != expected_uri:
        errors.append(f"required_ref_requests[{index}].requested_evidence_uri must match ref_name")
    if request.get("blocking_reason") != f"{ref_name}_requested_not_collected":
        errors.append(f"required_ref_requests[{index}].blocking_reason must match ref_name")


def _require_summary(envelope: Mapping[str, Any], requests: list[Any], errors: list[str]) -> None:
    summary = _mapping(envelope.get("summary"))
    expected = {
        "required_ref_request_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "required_ref_requested_count": len(EXPECTED_REQUIRED_VALUE_REFS),
        "required_ref_collected_count": 0,
        "required_ref_present_count": 0,
        "required_ref_bound_count": 0,
        "required_ref_accepted_count": 0,
        "required_ref_stored_count": 0,
        "operator_value_record_creation_count": 0,
        "verifier_execution_allowed_count": 0,
        "authority_grant_count": 0,
    }
    for field_name, expected_value in expected.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"summary.{field_name} must be {expected_value}")
    if len(requests) != len(EXPECTED_REQUIRED_VALUE_REFS):
        errors.append("summary source request count must stay canonical")


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
    """Run the explicit decision value-ref request validator."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--receipt-schema", type=Path, default=DEFAULT_RECEIPT_SCHEMA)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_record_verifier_execution_decision_value_record_value_explicit_decision_value_ref_request(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("personal assistant verifier execution explicit decision value-ref request: valid")
    else:
        print("personal assistant verifier execution explicit decision value-ref request: invalid")
        for error in validation.errors:
            print(f"  - {error}")
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
