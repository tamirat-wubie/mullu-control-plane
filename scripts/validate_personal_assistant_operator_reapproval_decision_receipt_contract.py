#!/usr/bin/env python3
"""Validate personal-assistant operator reapproval decision receipt contracts.

Purpose: prove decision intake evidence can be projected into a no-effect
future receipt contract before execution-worker admission.
Governance scope: decision intake refs, required receipt shape, receipt
conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant operator reapproval decision receipt contract
runtime helper, schema validators, and receipt validator.
Invariants:
  - Receipt contracts record future decision receipt requirements only.
  - Fresh operator decisions, identity refs, signatures, and reapproval receipts
    are not claimed.
  - Live connector execution, dispatch, execution-worker admission, connector
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
    DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_CONTRACT_GENERATED_AT,
    build_default_personal_assistant_operator_reapproval_decision_receipt_contract,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_operator_reapproval_decision_receipt_contract.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_OPERATOR_REAPPROVAL_DECISION_RECEIPT_CONTRACT_GENERATED_AT
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "operator_reapproval_decision_receipt_contract_allowed",
        "decision_intake_ref_binding_allowed",
        "fresh_operator_decision_required",
        "operator_identity_ref_required",
        "operator_signature_ref_required",
        "decision_receipt_required",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
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
        "raw_reapproval_payload",
        "raw_operator_decision",
        "operator_decision_value",
        "operator_signature",
        "raw_decision_receipt",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "intake_payload_projection",
        "receipt_payload_projection",
        "intake_request_digest",
        "required_receipt_digest",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantOperatorReapprovalDecisionReceiptContractValidation:
    """Validation result for no-effect operator reapproval decision receipt contracts."""

    valid: bool
    runtime_validated: bool
    contract_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_operator_reapproval_decision_receipt_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantOperatorReapprovalDecisionReceiptContractValidation:
    """Validate the runtime operator reapproval decision receipt contract envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "operator reapproval decision receipt contract schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_operator_reapproval_decision_receipt_contract(
        generated_at=RUNTIME_GENERATED_AT,
    )
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_operator_reapproval_decision_receipt_contract_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantOperatorReapprovalDecisionReceiptContractValidation(
        valid=not errors,
        runtime_validated=not errors,
        contract_count=int(envelope.get("contract_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_operator_reapproval_decision_receipt_contract_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    _require_true_fields(effect_boundary, TRUE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(effect_boundary, FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(envelope.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    if private_policy.get("intake_payload_projection") != "ref_only":
        errors.append("private_payload_policy.intake_payload_projection must be ref_only")
    if private_policy.get("receipt_payload_projection") != "absent_until_operator_submits_decision":
        errors.append("private_payload_policy.receipt_payload_projection must remain absent")
    assurance = _mapping(envelope.get("assurance"))
    for field_name in (
        "ready_for_execution_worker_admission",
        "ready_for_live_execution",
        "ready_for_customer_readiness_claim",
    ):
        if assurance.get(field_name) is not False:
            errors.append(f"assurance.{field_name} must be false")

    contracts = envelope.get("contracts")
    if not isinstance(contracts, list):
        errors.append("contracts must be a list")
        return tuple(errors)
    if envelope.get("contract_count") != len(contracts):
        errors.append("contract_count must equal contracts length")
    contract_ids: list[str] = []
    source_intake_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, contract in enumerate(contracts):
        if not isinstance(contract, dict):
            errors.append(f"contracts[{index}] must be an object")
            continue
        contract_ids.append(str(contract.get("contract_id", "")))
        source_intake_ids.append(str(contract.get("source_intake_id", "")))
        approval_id = str(contract.get("approval_id", ""))
        _require_decision_intake_ref(index, approval_id, _mapping(contract.get("decision_intake_ref")), errors)
        _require_required_receipt_contract(
            index,
            approval_id,
            _mapping(contract.get("required_receipt_contract")),
            errors,
        )
        _require_execution_admission_block(index, _mapping(contract.get("execution_admission_block")), errors)
        receipt = _mapping(contract.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"contracts[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(
            f"contracts[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("decision") != "deferred":
            errors.append(f"contracts[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != contract.get("approval_id"):
            errors.append(f"contracts[{index}].receipt.approval_ref must match approval_id")
        receipt_metadata = _mapping(receipt.get("metadata"))
        for field_name in (
            "decision_intake_ref_bound",
            "fresh_operator_decision_required",
            "operator_identity_ref_required",
            "operator_signature_ref_required",
        ):
            if receipt_metadata.get(field_name) is not True:
                errors.append(f"contracts[{index}].receipt.metadata.{field_name} must be true")
        for field_name in (
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
            "connector_mutation_allowed",
            "external_write_allowed",
            "system_of_record_write_allowed",
            "memory_write_allowed",
        ):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"contracts[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if envelope.get("contract_ids") != contract_ids:
        errors.append("contract_ids must match contracts order")
    if envelope.get("source_intake_ids") != source_intake_ids:
        errors.append("source_intake_ids must match contracts order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_decision_intake_ref(index: int, approval_id: str, payload: Mapping[str, Any], errors: list[str]) -> None:
    expected_intake_request_ref = f"approval://personal-assistant/reapproval-decision-intake/{approval_id}"
    if payload.get("intake_request_ref") != expected_intake_request_ref:
        errors.append(f"contracts[{index}].decision_intake_ref.intake_request_ref must match approval_id")
    if payload.get("wait_state") != "awaiting_operator_reapproval":
        errors.append(f"contracts[{index}].decision_intake_ref.wait_state must await reapproval")
    if payload.get("accepted_decision_values") != ["approved", "rejected", "revised", "expired"]:
        errors.append(f"contracts[{index}].decision_intake_ref.accepted_decision_values must be canonical")
    if payload.get("decision_receipt_required") is not True:
        errors.append(f"contracts[{index}].decision_intake_ref.decision_receipt_required must be true")
    for field_name in ("decision_receipt_present", "execution_worker_admission_allowed"):
        if payload.get(field_name) is not False:
            errors.append(f"contracts[{index}].decision_intake_ref.{field_name} must be false")


def _require_required_receipt_contract(
    index: int,
    approval_id: str,
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    expected_required_receipt_ref = f"receipt://personal-assistant/operator-reapproval-decision/{approval_id}"
    if payload.get("required_receipt_ref") != expected_required_receipt_ref:
        errors.append(f"contracts[{index}].required_receipt_contract.required_receipt_ref must match approval_id")
    if payload.get("allowed_decision_values") != ["approved", "rejected", "revised", "expired"]:
        errors.append(f"contracts[{index}].required_receipt_contract.allowed_decision_values must be canonical")
    if payload.get("required_identity_binding") != "operator_identity_ref":
        errors.append(f"contracts[{index}].required_receipt_contract.required_identity_binding must be canonical")
    if payload.get("required_signature_binding") != "operator_signature_ref":
        errors.append(f"contracts[{index}].required_receipt_contract.required_signature_binding must be canonical")
    for required_ref in ("operator_reapproval_gate_ref", "operator_reapproval_decision_intake_ref", "approval_ref"):
        source_refs = payload.get("required_source_refs")
        if not isinstance(source_refs, list) or required_ref not in source_refs:
            errors.append(f"contracts[{index}].required_receipt_contract.required_source_refs missing {required_ref}")
    for required_field in ("receipt_id", "request_id", "skill_id", "decision", "approval_ref", "actions_taken"):
        receipt_fields = payload.get("required_receipt_fields")
        if not isinstance(receipt_fields, list) or required_field not in receipt_fields:
            errors.append(f"contracts[{index}].required_receipt_contract.required_receipt_fields missing {required_field}")
    for field_name in ("raw_operator_decision_serialized", "secret_values_serialized", "decision_receipt_present"):
        if payload.get(field_name) is not False:
            errors.append(f"contracts[{index}].required_receipt_contract.{field_name} must be false")


def _require_execution_admission_block(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("execution_worker_admission_state") != "blocked_pending_operator_reapproval_decision_receipt":
        errors.append(f"contracts[{index}].execution_admission_block.execution_worker_admission_state must be blocked")
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
            errors.append(f"contracts[{index}].execution_admission_block.{field_name} must be false")


def _require_true_fields(payload: Mapping[str, Any], fields: frozenset[str], label: str, errors: list[str]) -> None:
    model = _mapping(payload)
    if not model:
        errors.append(f"{label} must be an object")
        return
    for field_name in sorted(fields):
        if model.get(field_name) is not True:
            errors.append(f"{label}.{field_name} must be true")


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
    """Parse operator reapproval decision receipt contract validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate personal-assistant operator reapproval decision receipt contract evidence.",
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for operator reapproval decision receipt contract validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_operator_reapproval_decision_receipt_contract(
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant operator reapproval decision receipt contract ok "
            f"contracts={result.contract_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
