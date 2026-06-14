#!/usr/bin/env python3
"""Validate the personal-assistant console read-model contract.

Purpose: keep the operator console schema-backed, read-only, and fail-closed
when approval, memory, or TeamOps projections drift toward execution authority.
Governance scope: console read-model schema conformance, no-effect assurance,
private payload redaction, and Foundation Mode readiness boundaries.
Dependencies: personal-assistant console read-model schema, example fixture,
runtime console builder, and schema validation helpers.
Invariants:
  - Console read models never grant live connector execution or external sends.
  - Approval decisions are not execution.
  - Memory remains candidate-only; Nested Mind live activation remains blocked.
  - TeamOps plans cannot grant live probe, provider call, or mailbox mutation.
  - Raw private payloads and secret-like values are not serialized.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for candidate in (REPO_ROOT, MCOI_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from mcoi_runtime.personal_assistant.console import build_personal_assistant_console_read_model  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_READ_MODEL = REPO_ROOT / "examples" / "personal_assistant_console_read_model.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_console_read_model.schema.json"
RUNTIME_GENERATED_AT = "2026-06-14T00:00:00Z"

FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "execution_allowed",
        "live_connector_execution_allowed",
        "mailbox_read_allowed",
        "mailbox_mutation_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "task_write_allowed",
        "memory_write_allowed",
        "nested_mind_live_activation_allowed",
        "deployment_mutation_allowed",
        "public_readiness_claim_allowed",
    }
)
FALSE_APPROVAL_FIELDS = frozenset(
    {
        "execution_allowed",
        "live_connector_execution_allowed",
        "external_send_allowed",
        "connector_mutation_allowed",
        "system_of_record_write_allowed",
        "approval_is_execution",
    }
)
FALSE_MEMORY_FIELDS = frozenset(
    {
        "live_memory_write_allowed",
        "nested_mind_live_activation_allowed",
        "raw_private_payload_storage_allowed",
        "secret_value_storage_allowed",
    }
)
FALSE_TEAMOPS_FIELDS = frozenset(
    {
        "live_probe_allowed",
        "mailbox_mutation_allowed",
        "provider_call_allowed",
    }
)
FALSE_RECEIPT_VIEWER_FIELDS = frozenset(
    {
        "runtime_dispatch_allowed",
        "filesystem_write_allowed",
        "external_effect_allowed",
        "connector_call_allowed",
        "terminal_closure_allowed",
        "success_claim_allowed",
    }
)
FALSE_REHEARSAL_RECEIPT_PROJECTION_FIELDS = frozenset(
    {
        "dispatch_admitted",
        "runtime_dispatch_allowed",
        "filesystem_write_allowed",
        "external_effect_allowed",
        "connector_call_allowed",
        "terminal_closure_allowed",
        "success_claim_allowed",
    }
)
READ_ONLY_WORKER_REHEARSAL_RECEIPT_KIND = "read_only_worker_rehearsal_receipt"
READ_ONLY_WORKER_REHEARSAL_RECEIPT_ID = "read-only-worker-rehearsal-receipt-foundation-repo-inspection-20260614"
READ_ONLY_WORKER_REHEARSAL_RECEIPT_REF = "examples/read_only_worker_rehearsal_receipt.foundation.json"
READ_ONLY_WORKER_REHEARSAL_SCHEMA_REF = "schemas/read_only_worker_rehearsal_receipt.schema.json"
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
        "chat_log_projection",
        "raw_private_payload_storage_allowed",
        "secret_value_storage_allowed",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantConsoleReadModelValidation:
    """Validation result for the personal-assistant console read model."""

    valid: bool
    read_model_path: str
    runtime_validated: bool
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_console_read_model(
    *,
    read_model_path: Path = DEFAULT_READ_MODEL,
    schema_path: Path = DEFAULT_SCHEMA,
    validate_runtime: bool = True,
) -> PersonalAssistantConsoleReadModelValidation:
    """Validate the console read-model example and runtime projection."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "console read-model schema", errors)
    read_model = _load_json_object(read_model_path, "console read model", errors)
    assurance_outcome = ""
    if schema and read_model:
        errors.extend(_validate_schema_instance(schema, read_model))
    if read_model:
        assurance = read_model.get("assurance")
        if isinstance(assurance, dict):
            assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_console_semantics(read_model))
        _scan_private_or_secret_payload(read_model, errors, path="$")

    runtime_validated = False
    if validate_runtime and schema:
        runtime_model = build_personal_assistant_console_read_model(generated_at=RUNTIME_GENERATED_AT)
        runtime_errors = list(_validate_schema_instance(schema, runtime_model))
        runtime_errors.extend(_validate_console_semantics(runtime_model))
        _scan_private_or_secret_payload(runtime_model, runtime_errors, path="$runtime")
        if runtime_errors:
            errors.extend(f"runtime {message}" for message in runtime_errors)
        runtime_validated = not runtime_errors

    return PersonalAssistantConsoleReadModelValidation(
        valid=not errors,
        read_model_path=_path_label(read_model_path),
        runtime_validated=runtime_validated,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def _validate_console_semantics(read_model: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    _require_false_fields(read_model.get("effect_boundary"), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    _require_false_fields(read_model.get("approval_queue"), FALSE_APPROVAL_FIELDS, "approval_queue", errors)
    approval_metadata = _mapping(read_model.get("approval_queue")).get("metadata")
    _require_false_fields(
        approval_metadata,
        frozenset({"live_connector_execution_allowed", "approval_decision_executes_action"}),
        "approval_queue.metadata",
        errors,
    )
    _require_false_fields(read_model.get("memory"), FALSE_MEMORY_FIELDS, "memory", errors)
    memory_metadata = _mapping(read_model.get("memory")).get("metadata")
    _require_false_fields(memory_metadata, FALSE_MEMORY_FIELDS, "memory.metadata", errors)
    _require_false_fields(read_model.get("teamops"), FALSE_TEAMOPS_FIELDS, "teamops", errors)
    _validate_receipt_viewer(read_model, errors)

    memory = _mapping(read_model.get("memory"))
    if memory.get("candidate_only") is not True:
        errors.append("memory.candidate_only must be true")
    assurance = _mapping(read_model.get("assurance"))
    if assurance.get("foundation_only") is not True:
        errors.append("assurance.foundation_only must be true")
    if assurance.get("ready_for_live_execution") is not False:
        errors.append("assurance.ready_for_live_execution must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")
    authority_drift = assurance.get("authority_drift_detected")
    blocking_reasons = assurance.get("blocking_reasons")
    if authority_drift is False and blocking_reasons != []:
        errors.append("assurance.blocking_reasons must be empty when authority_drift_detected is false")
    if authority_drift is True and assurance.get("outcome") != "GovernanceBlocked":
        errors.append("assurance.outcome must be GovernanceBlocked when authority drift is detected")
    if read_model.get("solver_outcome") != assurance.get("outcome"):
        errors.append("solver_outcome must match assurance.outcome")

    private_policy = _mapping(read_model.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    return tuple(errors)


def _validate_receipt_viewer(read_model: dict[str, Any], errors: list[str]) -> None:
    receipts = _mapping(read_model.get("receipts"))
    receipt_items = receipts.get("items")
    if not isinstance(receipt_items, list):
        errors.append("receipts.items must be a list")
        receipt_items = []
    if receipts.get("receipt_count") != len(receipt_items):
        errors.append("receipts.receipt_count must match receipts.items length")

    sections = _mapping(read_model.get("sections"))
    receipt_section = _mapping(sections.get("receipts"))
    if receipt_section.get("item_count") != len(receipt_items):
        errors.append("sections.receipts.item_count must match receipts.items length")

    viewer_binding = _mapping(receipts.get("viewer_binding"))
    if not viewer_binding:
        errors.append("receipts.viewer_binding must be an object")
        return
    _require_false_fields(viewer_binding, FALSE_RECEIPT_VIEWER_FIELDS, "receipts.viewer_binding", errors)
    if viewer_binding.get("viewer_state") != "foundation_read_only":
        errors.append("receipts.viewer_binding.viewer_state must be foundation_read_only")
    if viewer_binding.get("foundation_only") is not True:
        errors.append("receipts.viewer_binding.foundation_only must be true")

    projected_ids = _string_list(viewer_binding.get("projected_receipt_ids"))
    source_refs = _string_list(viewer_binding.get("source_receipt_refs"))
    item_ids = sorted(
        str(item["receipt_id"])
        for item in receipt_items
        if isinstance(item, dict) and isinstance(item.get("receipt_id"), str) and item.get("receipt_id")
    )
    item_source_refs = sorted(
        str(item["source_receipt_ref"])
        for item in receipt_items
        if isinstance(item, dict)
        and isinstance(item.get("source_receipt_ref"), str)
        and item.get("source_receipt_ref")
    )
    if viewer_binding.get("projection_count") != len(item_ids):
        errors.append("receipts.viewer_binding.projection_count must match projected receipt count")
    if projected_ids != item_ids:
        errors.append("receipts.viewer_binding.projected_receipt_ids must match receipt item ids")
    if source_refs != item_source_refs:
        errors.append("receipts.viewer_binding.source_receipt_refs must match receipt item source refs")

    rehearsal_items = [
        item
        for item in receipt_items
        if isinstance(item, dict) and item.get("receipt_kind") == READ_ONLY_WORKER_REHEARSAL_RECEIPT_KIND
    ]
    if bool(rehearsal_items) != bool(viewer_binding.get("read_only_worker_rehearsal_bound")):
        errors.append("receipts.viewer_binding.read_only_worker_rehearsal_bound must reflect receipt items")
    for index, item in enumerate(rehearsal_items):
        _validate_read_only_worker_rehearsal_projection(index, item, errors)


def _validate_read_only_worker_rehearsal_projection(index: int, item: dict[str, Any], errors: list[str]) -> None:
    label = f"receipts.items[{index}]"
    expected_values = {
        "receipt_id": READ_ONLY_WORKER_REHEARSAL_RECEIPT_ID,
        "source_receipt_ref": READ_ONLY_WORKER_REHEARSAL_RECEIPT_REF,
        "source_schema_ref": READ_ONLY_WORKER_REHEARSAL_SCHEMA_REF,
        "binding_ref": "examples/read_only_worker_binding.foundation.json",
        "lease_preflight_ref": "examples/read_only_worker_lease_preflight.foundation.json",
        "selected_worker_path": "read_only_repo_inspection",
        "worker_id": "worker_local_read_only_repo_inspection",
        "rehearsal_mode": "LOCAL_DRY_RUN",
        "solver_outcome": "SolvedVerified",
    }
    for field_name, expected_value in expected_values.items():
        if item.get(field_name) != expected_value:
            errors.append(f"{label}.{field_name} must be {expected_value}")
    _require_false_fields(item, FALSE_REHEARSAL_RECEIPT_PROJECTION_FIELDS, label, errors)
    output_digest = item.get("output_digest")
    if not isinstance(output_digest, str) or not output_digest.startswith("sha256:"):
        errors.append(f"{label}.output_digest must be a sha256 digest reference")
    if item.get("evidence_ref_count") != 8:
        errors.append(f"{label}.evidence_ref_count must be 8")


def _require_false_fields(payload: Any, fields: frozenset[str], label: str, errors: list[str]) -> None:
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


def _string_list(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    return sorted(str(item) for item in payload if isinstance(item, str) and item)


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


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse console read-model validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant console read model.")
    parser.add_argument("--read-model", default=str(DEFAULT_READ_MODEL))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for console read-model validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_console_read_model(
        read_model_path=Path(args.read_model),
        schema_path=Path(args.schema),
        validate_runtime=not args.skip_runtime,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant console read model ok "
            f"outcome={result.assurance_outcome} runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
