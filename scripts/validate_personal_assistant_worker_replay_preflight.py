#!/usr/bin/env python3
"""Validate personal-assistant worker/replay preflight evidence.

Purpose: prove execution-gate evidence can be projected into a no-effect
worker/replay preflight before any live personal-assistant dispatch.
Governance scope: execution-worker binding controls, replay prerequisites,
receipt conformance, private payload redaction, and Foundation Mode no-effect
boundaries.
Dependencies: personal-assistant worker/replay preflight runtime helper,
worker/replay preflight schema, receipt schema, and schema validators.
Invariants:
  - Worker/replay preflight does not bind an execution worker.
  - Replay and rollback plans are required but not executed.
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
    DEFAULT_WORKER_REPLAY_PREFLIGHT_GENERATED_AT,
    build_default_personal_assistant_worker_replay_preflight,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_worker_replay_preflight.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_WORKER_REPLAY_PREFLIGHT_GENERATED_AT
FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "worker_binding_allowed",
        "replay_execution_allowed",
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
        "gate_payload_projection",
        "payload_digest_only",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantWorkerReplayPreflightValidation:
    """Validation result for a no-effect worker/replay preflight envelope."""

    valid: bool
    runtime_validated: bool
    preflight_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_worker_replay_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantWorkerReplayPreflightValidation:
    """Validate the runtime worker/replay preflight envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "worker/replay preflight schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    envelope = build_default_personal_assistant_worker_replay_preflight(generated_at=RUNTIME_GENERATED_AT)
    assurance = _mapping(envelope.get("assurance"))
    if schema:
        errors.extend(_validate_schema_instance(schema, envelope))
    errors.extend(_validate_worker_replay_preflight_semantics(envelope, receipt_schema))
    _scan_private_or_secret_payload(envelope, errors, path="$runtime")
    return PersonalAssistantWorkerReplayPreflightValidation(
        valid=not errors,
        runtime_validated=not errors,
        preflight_count=int(envelope.get("preflight_count", 0)),
        receipt_count=len(envelope.get("receipt_ids", ())),
        assurance_outcome=str(assurance.get("outcome", "")),
        errors=tuple(errors),
    )


def _validate_worker_replay_preflight_semantics(
    envelope: Mapping[str, Any],
    receipt_schema: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    effect_boundary = _mapping(envelope.get("effect_boundary"))
    if effect_boundary.get("worker_replay_preflight_allowed") is not True:
        errors.append("effect_boundary.worker_replay_preflight_allowed must be true")
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

    preflights = envelope.get("preflights")
    if not isinstance(preflights, list):
        errors.append("preflights must be a list")
        return tuple(errors)
    if envelope.get("preflight_count") != len(preflights):
        errors.append("preflight_count must equal preflights length")
    preflight_ids: list[str] = []
    gate_ids: list[str] = []
    receipt_ids: list[str] = []
    for index, preflight in enumerate(preflights):
        if not isinstance(preflight, dict):
            errors.append(f"preflights[{index}] must be an object")
            continue
        preflight_ids.append(str(preflight.get("preflight_id", "")))
        gate_ids.append(str(preflight.get("gate_id", "")))
        gate_ref = _mapping(preflight.get("execution_gate_ref"))
        worker_preflight = _mapping(preflight.get("worker_preflight"))
        replay_preflight = _mapping(preflight.get("replay_preflight"))
        receipt = _mapping(preflight.get("receipt"))
        if gate_ref.get("gate_receipt_state") != "deferred":
            errors.append(f"preflights[{index}].execution_gate_ref.gate_receipt_state must be deferred")
        for field_name in ("execution_allowed",):
            if gate_ref.get(field_name) is not False:
                errors.append(f"preflights[{index}].execution_gate_ref.{field_name} must be false")
        for field_name in ("execution_gate_evaluated", "payload_digest_only"):
            if gate_ref.get(field_name) is not True:
                errors.append(f"preflights[{index}].execution_gate_ref.{field_name} must be true")
        _require_worker_preflight(index, worker_preflight, errors)
        _require_replay_preflight(index, replay_preflight, errors)
        if receipt_schema:
            errors.extend(
                f"preflights[{index}].receipt {message}"
                for message in _validate_schema_instance(dict(receipt_schema), receipt)
            )
        errors.extend(
            f"preflights[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("decision") != "deferred":
            errors.append(f"preflights[{index}].receipt.decision must be deferred")
        if receipt.get("approval_ref") != preflight.get("approval_id"):
            errors.append(f"preflights[{index}].receipt.approval_ref must match approval_id")
        receipt_metadata = _mapping(receipt.get("metadata"))
        for field_name in (
            "worker_binding_allowed",
            "replay_execution_allowed",
            "execution_allowed",
            "live_connector_execution_allowed",
            "connector_mutation_allowed",
            "external_write_allowed",
            "system_of_record_write_allowed",
            "memory_write_allowed",
        ):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"preflights[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
    if envelope.get("preflight_ids") != preflight_ids:
        errors.append("preflight_ids must match preflights order")
    if envelope.get("gate_ids") != gate_ids:
        errors.append("gate_ids must match preflights order")
    if envelope.get("receipt_ids") != receipt_ids:
        errors.append("receipt_ids must match embedded receipts")
    return tuple(errors)


def _require_worker_preflight(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("worker_family") != "personal_assistant_execution_worker":
        errors.append(f"preflights[{index}].worker_preflight.worker_family must be personal_assistant_execution_worker")
    if payload.get("worker_binding_state") != "unbound":
        errors.append(f"preflights[{index}].worker_preflight.worker_binding_state must be unbound")
    for field_name in ("worker_binding_allowed", "execution_worker_bound", "live_connector_witness_present", "dispatch_lease_present"):
        if payload.get(field_name) is not False:
            errors.append(f"preflights[{index}].worker_preflight.{field_name} must be false")
    for field_name in ("live_connector_witness_required", "dispatch_lease_required", "operator_reapproval_required"):
        if payload.get(field_name) is not True:
            errors.append(f"preflights[{index}].worker_preflight.{field_name} must be true")


def _require_replay_preflight(index: int, payload: Mapping[str, Any], errors: list[str]) -> None:
    if payload.get("replay_plan_state") != "required_not_recorded":
        errors.append(f"preflights[{index}].replay_preflight.replay_plan_state must be required_not_recorded")
    for field_name in ("replay_plan_required", "rollback_plan_required", "idempotency_key_required"):
        if payload.get(field_name) is not True:
            errors.append(f"preflights[{index}].replay_preflight.{field_name} must be true")
    for field_name in (
        "replay_plan_validated",
        "rollback_plan_validated",
        "idempotency_key_present",
        "replay_execution_allowed",
    ):
        if payload.get(field_name) is not False:
            errors.append(f"preflights[{index}].replay_preflight.{field_name} must be false")


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
    """Parse worker/replay preflight validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant worker/replay preflight evidence.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for worker/replay preflight validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_worker_replay_preflight(
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant worker replay preflight ok "
            f"preflights={result.preflight_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
