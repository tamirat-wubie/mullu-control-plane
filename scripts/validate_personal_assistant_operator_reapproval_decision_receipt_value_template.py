#!/usr/bin/env python3
"""Validate personal-assistant operator reapproval decision receipt value template.

Purpose: prove submitted-value templates define future operator input shape
without collecting values or admitting execution.
Governance scope: value-absence refs, template-only controls, shared receipt
conformance, private-payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant value-template runtime helper, schema
validators, and receipt validator.
Invariants:
  - Templates are never accepted as operator-submitted values.
  - Operator decision values, identity refs, signatures, and decision receipts
    remain uncollected.
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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_value_template,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_value_template.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_VALUE_TEMPLATE_GENERATED_AT
EXPECTED_DECISION_VALUES = ("approved", "rejected", "revised", "expired")
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_value_template_witness_allowed",
        "value_absence_ref_binding_allowed",
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
        "template_accepted_as_value",
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
        "value_absence_projection",
        "decision_value_template_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
        "decision_value_template",
        "operator_identity_ref",
        "operator_signature_ref",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptValueTemplateValidation:
    """Validation result for no-effect operator reapproval decision value template."""

    valid: bool
    runtime_validated: bool
    template_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_operator_reapproval_decision_receipt_value_template(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptValueTemplateValidation:
    """Validate the runtime operator reapproval decision receipt value-template envelope."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator reapproval decision receipt value-template schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_value_template(
        generated_at=RUNTIME_GENERATED_AT,
    )
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_operator_reapproval_decision_receipt_value_template_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptValueTemplateValidation(
        valid=not errors,
        runtime_validated=not errors,
        template_count=int(envelope.get("template_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_operator_reapproval_decision_receipt_value_template_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    _require_true_fields(_mapping(envelope.get("effect_boundary")), TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(_mapping(envelope.get("effect_boundary")), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_private_payload_policy(_mapping(envelope.get("private_payload_policy")), errors)

    templates = envelope.get("templates")
    if not isinstance(templates, list):
        errors.append("templates must be a list")
        return tuple(errors)
    if envelope.get("template_count") != len(templates):
        errors.append("template_count must equal templates length")
    template_ids: list[str] = []
    source_absence_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, template in enumerate(templates):
        if not isinstance(template, dict):
            errors.append(f"templates[{index}] must be an object")
            continue
        template_ids.append(str(template.get("template_id", "")))
        source_absence_ids.append(str(template.get("source_absence_id", "")))
        _require_value_absence_ref(index, _mapping(template.get("value_absence_ref")), errors)
        _require_decision_value_templates(index, str(template.get("approval_id", "")), template.get("decision_value_templates"), errors)
        _require_template_controls(index, _mapping(template.get("template_controls")), errors)
        _require_execution_block(index, _mapping(template.get("execution_admission_block")), errors)
        receipt = _mapping(template.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"templates[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(f"templates[{index}].receipt {message}" for message in validate_personal_assistant_receipt_payload(receipt))
        if receipt.get("decision") != "deferred":
            errors.append(f"templates[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != template.get("approval_id"):
            errors.append(f"templates[{index}].receipt.approval_ref must match approval_id")
        metadata = _mapping(receipt.get("metadata"))
        if metadata.get("operator_reapproval_decision_receipt_value_template_is_execution") is not False:
            errors.append(
                "templates["
                f"{index}].receipt.metadata.operator_reapproval_decision_receipt_value_template_is_execution must be false"
            )
        if metadata.get("value_absence_ref_bound") is not True:
            errors.append(f"templates[{index}].receipt.metadata.value_absence_ref_bound must be true")
        _require_false_fields(
            metadata,
            frozenset(
                {
                    "operator_value_collected",
                    "explicit_operator_value_present",
                    "template_accepted_as_value",
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
            f"templates[{index}].receipt.metadata",
            errors,
        )
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if envelope.get("template_ids") != template_ids:
        errors.append("template_ids must match templates order")
    if envelope.get("source_absence_ids") != source_absence_ids:
        errors.append("source_absence_ids must match templates order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_private_payload_policy(payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if payload.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    if payload.get("value_absence_projection") != "ref_only":
        errors.append("private_payload_policy.value_absence_projection must be ref_only")
    for field_name in (
        "decision_value_template_projection",
        "operator_identity_ref_projection",
        "operator_signature_projection",
        "decision_receipt_projection",
    ):
        if payload.get(field_name) != "placeholder_only":
            errors.append(f"private_payload_policy.{field_name} must be placeholder_only")


def _require_value_absence_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("absence_reason") != "operator_reapproval_decision_receipt_value_absent":
        errors.append(f"templates[{index}].value_absence_ref.absence_reason must record value absence")
    if payload.get("required_next_evidence") != "governed_operator_reapproval_decision_receipt_value":
        errors.append(f"templates[{index}].value_absence_ref.required_next_evidence must request governed value evidence")
    for field_name in (
        "operator_decision_value_present",
        "operator_identity_ref_present",
        "operator_signature_ref_present",
        "decision_receipt_present",
        "execution_worker_admission_allowed",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"templates[{index}].value_absence_ref.{field_name} must be false")


def _require_decision_value_templates(index: int, approval_id: str, payload: Any, errors: list[str]) -> None:
    if not isinstance(payload, list):
        errors.append(f"templates[{index}].decision_value_templates must be a list")
        return
    observed_values: list[str] = []
    for template_index, value_template in enumerate(payload):
        if not isinstance(value_template, dict):
            errors.append(f"templates[{index}].decision_value_templates[{template_index}] must be an object")
            continue
        decision_value = str(value_template.get("decision_value", ""))
        observed_values.append(decision_value)
        if value_template.get("approval_ref") != approval_id:
            errors.append(f"templates[{index}].decision_value_templates[{template_index}].approval_ref must match approval_id")
        if value_template.get("template_only") is not True:
            errors.append(f"templates[{index}].decision_value_templates[{template_index}].template_only must be true")
        if value_template.get("operator_supplied_value_required") is not True:
            errors.append(
                f"templates[{index}].decision_value_templates[{template_index}].operator_supplied_value_required must be true"
            )
        for field_name in ("accepted_as_operator_value", "grants_execution_authority"):
            if value_template.get(field_name) is not False:
                errors.append(f"templates[{index}].decision_value_templates[{template_index}].{field_name} must be false")
        field_templates = _mapping(value_template.get("field_templates"))
        if field_templates.get("decision_value") != f"operator_must_submit_{decision_value}":
            errors.append(f"templates[{index}].decision_value_templates[{template_index}].field_templates.decision_value mismatch")
        for field_name, expected in (
            ("operator_identity_ref_placeholder", "operator_identity_ref_required"),
            ("operator_signature_ref_placeholder", "operator_signature_ref_required"),
            ("decision_receipt_ref_placeholder", "decision_receipt_ref_required"),
            ("submitted_at", "YYYY-MM-DDTHH:MM:SS+00:00"),
        ):
            if field_templates.get(field_name) != expected:
                errors.append(f"templates[{index}].decision_value_templates[{template_index}].field_templates.{field_name} mismatch")
    if tuple(observed_values) != EXPECTED_DECISION_VALUES:
        errors.append(f"templates[{index}].decision_value_templates must use canonical decision order")


def _require_template_controls(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("template_only") is not True:
        errors.append(f"templates[{index}].template_controls.template_only must be true")
    for field_name in (
        "stores_operator_value",
        "accepts_template_as_value",
        "credential_values_allowed",
        "mutation_route_allowed",
        "live_authority_on_template",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"templates[{index}].template_controls.{field_name} must be false")


def _require_execution_block(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("execution_worker_admission_state") != "blocked_template_only_operator_reapproval_decision_receipt_value":
        errors.append(f"templates[{index}].execution_admission_block.execution_worker_admission_state must be blocked")
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
            errors.append(f"templates[{index}].execution_admission_block.{field_name} must be false")


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
    """Parse operator reapproval decision receipt value-template validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate personal-assistant operator reapproval decision receipt value-template evidence.",
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator reapproval decision receipt value-template validation."""

    args = parse_args(argv)
    result = validate_personal_assistant_operator_reapproval_decision_receipt_value_template(
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant operator reapproval decision receipt value template ok "
            f"templates={result.template_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
