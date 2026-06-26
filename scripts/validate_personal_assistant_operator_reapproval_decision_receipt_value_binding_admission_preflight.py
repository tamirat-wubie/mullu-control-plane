#!/usr/bin/env python3
"""Validate personal-assistant operator decision value-binding admission preflight.

Purpose: prove value-binding admission remains blocked while governed operator
decision value binding is absent.
Governance scope: value-binding absence refs, admission denial, receipt
conformance, private-payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant value-binding admission preflight runtime
helper, schema validators, and receipt validator.
Invariants:
  - Admission preflight never admits execution without governed value binding.
  - Operator decision values, identity refs, signatures, and decision receipts
    remain unbound.
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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_ADMISSION_PREFLIGHT_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_ADMISSION_PREFLIGHT_GENERATED_AT
EXPECTED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_binding_admission_preflight_allowed",
        "value_binding_absence_ref_binding_allowed",
        "admission_decision_allowed",
        "operator_submitted_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_value_collected",
        "explicit_operator_value_present",
        "operator_value_bound",
        "accepted_value_present",
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
        "value_binding_absence_projection",
        "value_binding_guard_projection",
        "decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingAdmissionPreflightValidation:
    """Validation result for blocked value-binding admission preflight."""

    valid: bool
    runtime_validated: bool
    admission_preflight_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingAdmissionPreflightValidation:
    """Validate the runtime value-binding admission preflight envelope."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator reapproval decision value-binding admission preflight schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight(
        generated_at=RUNTIME_GENERATED_AT,
    )
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_value_binding_admission_preflight_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingAdmissionPreflightValidation(
        valid=not errors,
        runtime_validated=not errors,
        admission_preflight_count=int(envelope.get("admission_preflight_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_value_binding_admission_preflight_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    preflights = envelope.get("admission_preflights")
    if not isinstance(preflights, list):
        errors.append("admission_preflights must be a list")
        return tuple(errors)
    if envelope.get("admission_preflight_count") != len(preflights):
        errors.append("admission_preflight_count must equal admission_preflights length")
    preflight_ids: list[str] = []
    source_binding_absence_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, preflight in enumerate(preflights):
        if not isinstance(preflight, dict):
            errors.append(f"admission_preflights[{index}] must be an object")
            continue
        preflight_ids.append(str(preflight.get("admission_preflight_id", "")))
        source_binding_absence_ids.append(str(preflight.get("source_binding_absence_id", "")))
        _require_value_binding_absence_ref(index, _mapping(preflight.get("value_binding_absence_ref")), errors)
        _require_admission_decision(index, _mapping(preflight.get("admission_decision")), errors)
        _require_execution_block(index, _mapping(preflight.get("execution_admission_block")), errors)
        receipt = _mapping(preflight.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"admission_preflights[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"admission_preflights[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "blocked":
            errors.append(f"admission_preflights[{index}].receipt.decision must be blocked")
        if receipt.get("approval_ref") != preflight.get("approval_id"):
            errors.append(f"admission_preflights[{index}].receipt.approval_ref must match approval_id")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_admission_preflight_is_execution") is not False:
            errors.append(
                "admission_preflights["
                f"{index}].receipt.metadata.operator_reapproval_decision_receipt_value_binding_admission_preflight_is_execution must be false"
            )
        if metadata.get("value_binding_absence_ref_bound") is not True:
            errors.append(f"admission_preflights[{index}].receipt.metadata.value_binding_absence_ref_bound must be true")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "operator_value_collected",
                    "explicit_operator_value_present",
                    "operator_value_bound",
                    "accepted_value_present",
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
            f"admission_preflights[{index}].receipt.metadata",
            errors,
        )
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if envelope.get("admission_preflight_ids") != preflight_ids:
        errors.append("admission_preflight_ids must match preflight order")
    if envelope.get("source_binding_absence_ids") != source_binding_absence_ids:
        errors.append("source_binding_absence_ids must match preflight order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match preflight receipts")
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "GovernanceBlocked":
        errors.append("assurance.outcome must remain GovernanceBlocked")
    metadata = _mapping(envelope.get("metadata"))
    _require_false_fields(
        metadata,
        FALSE_EFFECT_BOUNDARY_FIELDS - {"dispatch_lease_active", "live_connector_receipt_present"},
        "metadata",
        errors,
    )
    return tuple(errors)


def _require_value_binding_absence_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("operator_submitted_value_required") is not True:
        errors.append(f"admission_preflights[{index}].value_binding_absence_ref.operator_submitted_value_required must be true")
    if tuple(payload.get("allowed_decision_values", ())) != EXPECTED_DECISION_VALUES:
        errors.append(f"admission_preflights[{index}].value_binding_absence_ref.allowed_decision_values must match policy")
    for field_name in ("operator_value_bound", "accepted_value_present", "execution_worker_admission_allowed"):
        if payload.get(field_name) is not False:
            errors.append(f"admission_preflights[{index}].value_binding_absence_ref.{field_name} must be false")


def _require_admission_decision(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "decision": "blocked",
        "admission_state": "blocked_missing_governed_operator_value_binding",
        "outcome": "GovernanceBlocked",
        "required_next_evidence": "governed_operator_reapproval_decision_receipt_value_binding",
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            errors.append(f"admission_preflights[{index}].admission_decision.{field_name} must be {expected_value}")
    if payload.get("operator_submitted_value_required") is not True:
        errors.append(f"admission_preflights[{index}].admission_decision.operator_submitted_value_required must be true")
    for field_name in (
        "operator_value_bound",
        "accepted_value_present",
        "authority_granted",
        "execution_worker_admission_allowed",
        "dispatch_allowed",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"admission_preflights[{index}].admission_decision.{field_name} must be false")
    if not payload.get("blocking_reasons"):
        errors.append(f"admission_preflights[{index}].admission_decision.blocking_reasons must be non-empty")


def _require_execution_block(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("execution_worker_admission_state") != "blocked_missing_governed_operator_value_binding":
        errors.append(f"admission_preflights[{index}].execution_admission_block.execution_worker_admission_state must remain blocked")
    _require_false_fields(
        payload,
        frozenset(
            {
                "execution_worker_admission_allowed",
                "dispatch_allowed",
                "live_connector_execution_allowed",
                "connector_mutation_allowed",
                "external_send_allowed",
                "system_of_record_write_allowed",
                "memory_write_allowed",
            }
        ),
        f"admission_preflights[{index}].execution_admission_block",
        errors,
    )


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "raw_private_payload_serialized": False,
        "secret_values_serialized": False,
        "value_binding_absence_projection": "ref_only",
        "decision_value_projection": "absent",
        "operator_identity_ref_projection": "absent",
        "operator_signature_projection": "absent",
        "decision_receipt_projection": "absent",
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

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_admission_preflight(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING ADMISSION PREFLIGHT VALID")
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}", file=sys.stderr)
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
