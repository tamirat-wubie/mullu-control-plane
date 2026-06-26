#!/usr/bin/env python3
"""Validate personal-assistant execution-gate evidence.

Purpose: prove approved decisions can be projected into a no-effect dispatch
preflight without executing personal-assistant actions.
Governance scope: PR6 execution gate evidence, approval-decision binding,
receipt conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant execution gate runtime helper, execution gate
schema, receipt schema, and schema validators.
Invariants:
  - Execution gates evaluate future dispatch eligibility only.
  - Approved approval decisions are necessary but not sufficient for execution.
  - Live connector execution, external sends, connector mutation, memory writes,
    system-of-record writes, and readiness claims remain false.
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
    DEFAULT_EXECUTION_GATE_GENERATED_AT,
    build_default_personal_assistant_execution_gate,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_execution_gate.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_EXECUTION_GATE_GENERATED_AT
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "execution_allowed",
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
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "decision_payload_projection",
        "payload_digest_only",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantExecutionGateValidation:
    """Validation result for a no-effect execution-gate envelope."""

    valid: bool
    runtime_validated: bool
    gate_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_execution_gate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantExecutionGateValidation:
    """Validate the runtime execution-gate envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "execution gate schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_execution_gate(generated_at=RUNTIME_GENERATED_AT)
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_execution_gate_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantExecutionGateValidation(
        valid=not errors,
        runtime_validated=not errors,
        gate_count=int(envelope.get("gate_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_execution_gate_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    if effect_boundary.get("execution_gate_evaluation_allowed") is not True:
        errors.append("effect_boundary.execution_gate_evaluation_allowed must be true")
    _require_false_fields(effect_boundary, FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(envelope.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("ready_for_live_execution") is not False:
        errors.append("assurance.ready_for_live_execution must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")

    gates = envelope.get("gates")
    if not isinstance(gates, list):
        errors.append("gates must be a list")
        return tuple(errors)
    if envelope.get("gate_count") != len(gates):
        errors.append("gate_count must equal gates length")
    gate_ids: list[str] = []
    approval_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            errors.append(f"gates[{index}] must be an object")
            continue
        gate_ids.append(str(gate.get("gate_id", "")))
        approval_ids.append(str(gate.get("approval_id", "")))
        decision_ref = _mapping(gate.get("approval_decision_ref"))
        preconditions = _mapping(gate.get("dispatch_preconditions"))
        receipt = _mapping(gate.get("receipt"))
        if decision_ref.get("decision") != "approved":
            errors.append(f"gates[{index}].approval_decision_ref.decision must be approved")
        if decision_ref.get("decision_receipt_state") != "deferred":
            errors.append(f"gates[{index}].approval_decision_ref.decision_receipt_state must be deferred")
        if decision_ref.get("approved_but_not_executed") is not True:
            errors.append(f"gates[{index}].approval_decision_ref.approved_but_not_executed must be true")
        for field_name in ("approval_decision_approved", "decision_receipt_deferred"):
            if preconditions.get(field_name) is not True:
                errors.append(f"gates[{index}].dispatch_preconditions.{field_name} must be true")
        for field_name in ("live_connector_witness_present", "execution_worker_bound", "execution_allowed"):
            if preconditions.get(field_name) is not False:
                errors.append(f"gates[{index}].dispatch_preconditions.{field_name} must be false")
        if receipt_schema:
            errors.extend(
                f"gates[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(
            f"gates[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("decision") != "deferred":
            errors.append(f"gates[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != gate.get("approval_id"):
            errors.append(f"gates[{index}].receipt.approval_ref must match approval_id")
        receipt_metadata = _mapping(receipt.get("metadata"))
        for field_name in (
            "execution_allowed",
            "live_connector_execution_allowed",
            "connector_mutation_allowed",
            "external_write_allowed",
            "system_of_record_write_allowed",
            "memory_write_allowed",
        ):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"gates[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if envelope.get("gate_ids") != gate_ids:
        errors.append("gate_ids must match gates order")
    if envelope.get("approval_ids") != approval_ids:
        errors.append("approval_ids must match gates order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_false_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    model = _mapping(payload)
    if not model:
        errors.append(f"{label} must be an object")
        return
    for field_name in sorted(fields):
        if model.get(field_name) is not False:
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
    """Parse execution-gate validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant execution gate evidence.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for execution-gate validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_execution_gate(
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant execution gate ok "
            f"gates={result.gate_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
