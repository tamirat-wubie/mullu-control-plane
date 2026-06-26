#!/usr/bin/env python3
"""Validate personal-assistant replay/rollback witness evidence.

Purpose: prove worker/replay preflight can be projected into no-effect replay,
rollback, and idempotency witness evidence before execution-worker admission.
Governance scope: replay refs, rollback refs, idempotency refs, receipt
conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant replay/rollback witness runtime helper,
replay/rollback witness schema, receipt schema, and schema validators.
Invariants:
  - Replay and rollback witness binding records refs and digests only.
  - Replay, rollback, worker binding, and dispatch remain non-executing.
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
    DEFAULT_REPLAY_ROLLBACK_WITNESS_GENERATED_AT,
    build_default_personal_assistant_replay_rollback_witness,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_replay_rollback_witness.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_REPLAY_ROLLBACK_WITNESS_GENERATED_AT
TRUE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "replay_rollback_witness_allowed",
        "replay_plan_binding_allowed",
        "rollback_plan_binding_allowed",
        "idempotency_ref_binding_allowed",
    }
)
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "worker_binding_allowed",
        "dispatch_lease_binding_allowed",
        "replay_execution_allowed",
        "rollback_execution_allowed",
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
        "raw_replay_plan",
        "raw_rollback_plan",
        "idempotency_key",
    }
)
ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "plan_payload_projection",
        "idempotency_key_projection",
        "idempotency_key_digest",
        "idempotency_key_present",
        "idempotency_key_required",
        "idempotency_key_serialized",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantReplayRollbackWitnessValidation:
    """Validation result for a no-effect replay/rollback witness envelope."""

    valid: bool
    runtime_validated: bool
    witness_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_replay_rollback_witness(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantReplayRollbackWitnessValidation:
    """Validate the runtime replay/rollback witness envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "replay/rollback witness schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_replay_rollback_witness(generated_at=RUNTIME_GENERATED_AT)
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_replay_rollback_witness_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantReplayRollbackWitnessValidation(
        valid=not errors,
        runtime_validated=not errors,
        witness_count=int(envelope.get("witness_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_replay_rollback_witness_semantics(
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
    if private_policy.get("plan_payload_projection") != "digest_only":
        errors.append("private_payload_policy.plan_payload_projection must be digest_only")
    if private_policy.get("idempotency_key_projection") != "digest_only":
        errors.append("private_payload_policy.idempotency_key_projection must be digest_only")
    assurance = _mapping(envelope.get("assurance"))
    if assurance.get("ready_for_live_execution") is not False:
        errors.append("assurance.ready_for_live_execution must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")

    witnesses = envelope.get("witnesses")
    if not isinstance(witnesses, list):
        errors.append("witnesses must be a list")
        return tuple(errors)
    if envelope.get("witness_count") != len(witnesses):
        errors.append("witness_count must equal witnesses length")
    witness_ids: list[str] = []
    preflight_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, witness in enumerate(witnesses):
        if not isinstance(witness, dict):
            errors.append(f"witnesses[{index}] must be an object")
            continue
        witness_ids.append(str(witness.get("witness_id", "")))
        preflight_ids.append(str(witness.get("preflight_id", "")))
        _require_preflight_ref(index, _mapping(witness.get("worker_replay_preflight_ref")), errors)
        _require_replay_plan_witness(index, _mapping(witness.get("replay_plan_witness")), errors)
        _require_rollback_plan_witness(index, _mapping(witness.get("rollback_plan_witness")), errors)
        _require_idempotency_witness(index, _mapping(witness.get("idempotency_witness")), errors)
        _require_dispatch_blockers(index, _mapping(witness.get("dispatch_blockers")), errors)
        receipt = _mapping(witness.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"witnesses[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(
            f"witnesses[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("decision") != "deferred":
            errors.append(f"witnesses[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != witness.get("approval_id"):
            errors.append(f"witnesses[{index}].receipt.approval_ref must match approval_id")
        receipt_metadata = _mapping(receipt.get("metadata"))
        for field_name in ("replay_plan_bound", "rollback_plan_bound", "idempotency_ref_bound"):
            if receipt_metadata.get(field_name) is not True:
                errors.append(f"witnesses[{index}].receipt.metadata.{field_name} must be true")
        for field_name in (
            "worker_binding_allowed",
            "dispatch_lease_binding_allowed",
            "replay_execution_allowed",
            "rollback_execution_allowed",
            "execution_allowed",
            "live_connector_execution_allowed",
            "connector_mutation_allowed",
            "external_write_allowed",
            "system_of_record_write_allowed",
            "memory_write_allowed",
        ):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"witnesses[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if envelope.get("witness_ids") != witness_ids:
        errors.append("witness_ids must match witnesses order")
    if envelope.get("preflight_ids") != preflight_ids:
        errors.append("preflight_ids must match witnesses order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_preflight_ref(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("preflight_receipt_state") != "deferred":
        errors.append(f"witnesses[{index}].worker_replay_preflight_ref.preflight_receipt_state must be deferred")
    for field_name in ("worker_binding_allowed", "replay_execution_allowed"):
        if payload.get(field_name) is not False:
            errors.append(f"witnesses[{index}].worker_replay_preflight_ref.{field_name} must be false")
    if payload.get("payload_digest_only") is not True:
        errors.append(f"witnesses[{index}].worker_replay_preflight_ref.payload_digest_only must be true")


def _require_replay_plan_witness(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in ("replay_plan_required", "replay_plan_validated"):
        if payload.get(field_name) is not True:
            errors.append(f"witnesses[{index}].replay_plan_witness.{field_name} must be true")
    if payload.get("replay_plan_state") != "recorded_validated":
        errors.append(f"witnesses[{index}].replay_plan_witness.replay_plan_state must be recorded_validated")
    if payload.get("replay_payload_projection") != "digest_only":
        errors.append(f"witnesses[{index}].replay_plan_witness.replay_payload_projection must be digest_only")
    if payload.get("replay_execution_allowed") is not False:
        errors.append(f"witnesses[{index}].replay_plan_witness.replay_execution_allowed must be false")


def _require_rollback_plan_witness(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in ("rollback_plan_required", "rollback_plan_validated", "compensation_required_after_execution"):
        if payload.get(field_name) is not True:
            errors.append(f"witnesses[{index}].rollback_plan_witness.{field_name} must be true")
    if payload.get("rollback_plan_state") != "recorded_validated":
        errors.append(f"witnesses[{index}].rollback_plan_witness.rollback_plan_state must be recorded_validated")
    if payload.get("rollback_scope") != "no_effect_before_execution":
        errors.append(f"witnesses[{index}].rollback_plan_witness.rollback_scope must be no_effect_before_execution")
    if payload.get("rollback_execution_allowed") is not False:
        errors.append(f"witnesses[{index}].rollback_plan_witness.rollback_execution_allowed must be false")


def _require_idempotency_witness(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in ("idempotency_key_required", "idempotency_key_present", "idempotency_window_validated"):
        if payload.get(field_name) is not True:
            errors.append(f"witnesses[{index}].idempotency_witness.{field_name} must be true")
    if payload.get("idempotency_key_serialized") is not False:
        errors.append(f"witnesses[{index}].idempotency_witness.idempotency_key_serialized must be false")


def _require_dispatch_blockers(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("worker_binding_state") != "unbound":
        errors.append(f"witnesses[{index}].dispatch_blockers.worker_binding_state must be unbound")
    for field_name in ("execution_worker_bound", "live_connector_witness_present", "dispatch_lease_present", "execution_allowed"):
        if payload.get(field_name) is not False:
            errors.append(f"witnesses[{index}].dispatch_blockers.{field_name} must be false")
    if payload.get("operator_reapproval_required") is not True:
        errors.append(f"witnesses[{index}].dispatch_blockers.operator_reapproval_required must be true")


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
    """Parse replay/rollback witness validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant replay/rollback witness evidence.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for replay/rollback witness validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_replay_rollback_witness(
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant replay rollback witness ok "
            f"witnesses={result.witness_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
