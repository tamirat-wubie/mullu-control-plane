#!/usr/bin/env python3
"""Validate personal-assistant operator decision receipt value binding guards.

Purpose: prove value binding guards record future operator-submitted value
requirements without binding values or admitting execution.
Governance scope: value-template refs, value-binding controls, shared receipt
conformance, private-payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant value-binding guard runtime helper, schema
validators, and receipt validator.
Invariants:
  - Binding guards never accept operator-submitted values.
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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_binding_guard.schema.json"
)
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_BINDING_GUARD_GENERATED_AT
EXPECTED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_binding_guard_allowed",
        "value_template_ref_binding_allowed",
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
        "binding_guard_accepted_as_value",
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
        "value_template_projection",
        "decision_value_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingGuardValidation:
    """Validation result for no-effect operator decision value binding guards."""

    valid: bool
    runtime_validated: bool
    binding_guard_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingGuardValidation:
    """Validate the runtime operator reapproval decision value-binding guard."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator reapproval decision value-binding guard schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard(
        generated_at=RUNTIME_GENERATED_AT,
    )
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_operator_reapproval_decision_receipt_value_binding_guard_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueBindingGuardValidation(
        valid=not errors,
        runtime_validated=not errors,
        binding_guard_count=int(envelope.get("binding_guard_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_operator_reapproval_decision_receipt_value_binding_guard_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    guards = envelope.get("binding_guards")
    if not isinstance(guards, list):
        errors.append("binding_guards must be a list")
        return tuple(errors)
    if envelope.get("binding_guard_count") != len(guards):
        errors.append("binding_guard_count must equal binding_guards length")
    guard_ids: list[str] = []
    source_template_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, guard in enumerate(guards):
        if not isinstance(guard, dict):
            errors.append(f"binding_guards[{index}] must be an object")
            continue
        guard_ids.append(str(guard.get("binding_guard_id", "")))
        source_template_ids.append(str(guard.get("source_template_id", "")))
        _require_value_template_ref(index, _mapping(guard.get("value_template_ref")), errors)
        _require_admissible_value_binding(index, _mapping(guard.get("admissible_value_binding")), errors)
        _require_execution_block(index, _mapping(guard.get("execution_admission_block")), errors)
        receipt = _mapping(guard.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"binding_guards[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"binding_guards[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "deferred":
            errors.append(f"binding_guards[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != guard.get("approval_id"):
            errors.append(f"binding_guards[{index}].receipt.approval_ref must match approval_id")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_binding_guard_is_execution") is not False:
            errors.append(
                "binding_guards["
                f"{index}].receipt.metadata.operator_reapproval_decision_receipt_value_binding_guard_is_execution must be false"
            )
        if metadata.get("value_template_ref_bound") is not True:
            errors.append(f"binding_guards[{index}].receipt.metadata.value_template_ref_bound must be true")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "operator_value_collected",
                    "explicit_operator_value_present",
                    "operator_value_bound",
                    "binding_guard_accepted_as_value",
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
            f"binding_guards[{index}].receipt.metadata",
            errors,
        )
        receipt_ids.append(str(receipt.get("receipt_id", "")))
    if envelope.get("binding_guard_ids") != guard_ids:
        errors.append("binding_guard_ids must match binding guard order")
    if envelope.get("source_template_ids") != source_template_ids:
        errors.append("source_template_ids must match binding guard order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match binding guard receipts")
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("outcome") != "AwaitingEvidence":
        errors.append("assurance.outcome must remain AwaitingEvidence")
    metadata = _mapping(envelope.get("metadata"))
    _require_false_fields(metadata, FALSE_EFFECT_BOUNDARY_FIELDS - {"dispatch_lease_active", "live_connector_receipt_present"}, "metadata", errors)
    return tuple(errors)


def _require_value_template_ref(index: int, value_template_ref: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in (
        "operator_submitted_value_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    ):
        if value_template_ref.get(field_name) is not True:
            errors.append(f"binding_guards[{index}].value_template_ref.{field_name} must be true")
    for field_name in ("operator_value_bound", "execution_worker_admission_allowed"):
        if value_template_ref.get(field_name) is not False:
            errors.append(f"binding_guards[{index}].value_template_ref.{field_name} must be false")


def _require_admissible_value_binding(index: int, admissible_value_binding: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in (
        "requires_explicit_operator_value",
        "requires_operator_identity_ref",
        "requires_operator_signature_ref",
        "requires_decision_receipt_ref",
        "requires_value_request_ref",
        "requires_value_template_ref",
    ):
        if admissible_value_binding.get(field_name) is not True:
            errors.append(f"binding_guards[{index}].admissible_value_binding.{field_name} must be true")
    if tuple(admissible_value_binding.get("allowed_decision_values", ())) != EXPECTED_DECISION_VALUES:
        errors.append(f"binding_guards[{index}].admissible_value_binding.allowed_decision_values must match policy")
    for field_name in (
        "accepted_value_present",
        "placeholder_value_present",
        "template_value_present",
        "raw_private_payload_allowed",
        "secret_value_allowed",
        "grants_execution_authority",
    ):
        if admissible_value_binding.get(field_name) is not False:
            errors.append(f"binding_guards[{index}].admissible_value_binding.{field_name} must be false")


def _require_execution_block(index: int, execution_block: Mapping[str, Any], errors: list[str]) -> None:
    if execution_block.get("execution_worker_admission_state") != "blocked_pending_governed_operator_value_binding":
        errors.append(f"binding_guards[{index}].execution_admission_block.execution_worker_admission_state must remain blocked")
    _require_false_fields(
        execution_block,
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
        f"binding_guards[{index}].execution_admission_block",
        errors,
    )


def _require_private_payload_policy(private_payload_policy: Mapping[str, Any], errors: list[str]) -> None:
    expected = {
        "raw_private_payload_serialized": False,
        "secret_values_serialized": False,
        "value_template_projection": "ref_only",
        "decision_value_projection": "absent",
        "operator_identity_ref_projection": "absent",
        "operator_signature_projection": "absent",
        "decision_receipt_projection": "absent",
    }
    for field_name, expected_value in expected.items():
        if private_payload_policy.get(field_name) != expected_value:
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

    validation = validate_personal_assistant_operator_reapproval_decision_receipt_value_binding_guard(
        schema_path=args.schema,
        receipt_schema_path=args.receipt_schema,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.valid:
        print("PERSONAL ASSISTANT OPERATOR REAPPROVAL DECISION RECEIPT VALUE BINDING GUARD VALID")
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}", file=sys.stderr)
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
