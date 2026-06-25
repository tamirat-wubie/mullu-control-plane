#!/usr/bin/env python3
"""Validate personal-assistant read-only projection evidence.

Purpose: keep redacted inbox and calendar summaries schema-backed, receipt-
anchored, and unable to imply live connector reads, sends, writes, mutation, or
customer readiness.
Governance scope: PR4 read-only projection evidence, private payload redaction,
receipt conformance, and Foundation Mode no-effect boundaries.
Dependencies: personal-assistant read-only runtime helpers, projection schema,
receipt schema, and schema validation helpers.
Invariants:
  - Projections are generated from operator-supplied redacted summaries only.
  - Live connector execution, mailbox mutation, calendar write, external send,
    deployment mutation, and public readiness claims remain false.
  - Embedded receipts validate and record actions taken plus actions not taken.
  - Raw private payloads and secret-like values are rejected.
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
    DEFAULT_READ_ONLY_PROJECTION_GENERATED_AT,
    build_default_personal_assistant_read_only_projection,
    build_personal_assistant_read_only_projection_envelope,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_PROJECTION = REPO_ROOT / "examples" / "personal_assistant_read_only_projection.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_read_only_projection.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"
RUNTIME_GENERATED_AT = DEFAULT_READ_ONLY_PROJECTION_GENERATED_AT

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
        "connector_mutation_allowed",
        "deployment_mutation_allowed",
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
        "body_projection",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantReadOnlyProjectionValidation:
    """Validation result for a read-only projection envelope."""

    valid: bool
    projection_path: str
    runtime_validated: bool
    projection_count: int
    receipt_count: int
    assurance_outcome: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_read_only_projection(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
    validate_runtime: bool = True,
) -> PersonalAssistantReadOnlyProjectionValidation:
    """Validate a projection fixture and optional runtime-generated envelope."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "read-only projection schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "receipt schema", errors)
    projection = _load_json_object(projection_path, "read-only projection", errors)
    assurance_outcome = ""
    if schema and projection:
        errors.extend(_validate_schema_instance(schema, projection))
    if projection:
        assurance = _mapping(projection.get("assurance"))
        assurance_outcome = str(assurance.get("outcome", ""))
        errors.extend(_validate_projection_semantics(projection, receipt_schema))
        _scan_private_or_secret_payload(projection, errors, path="$")

    runtime_validated = False
    if validate_runtime and schema:
        runtime_projection = build_runtime_read_only_projection()
        runtime_errors = list(_validate_schema_instance(schema, runtime_projection))
        runtime_errors.extend(_validate_projection_semantics(runtime_projection, receipt_schema))
        _scan_private_or_secret_payload(runtime_projection, runtime_errors, path="$runtime")
        if runtime_errors:
            errors.extend(f"runtime {message}" for message in runtime_errors)
        runtime_validated = not runtime_errors

    return PersonalAssistantReadOnlyProjectionValidation(
        valid=not errors,
        projection_path=_path_label(projection_path),
        runtime_validated=runtime_validated,
        projection_count=int(projection.get("projection_count", 0)) if isinstance(projection, dict) else 0,
        receipt_count=len(projection.get("receipt_ids", ())) if isinstance(projection, dict) else 0,
        assurance_outcome=assurance_outcome,
        errors=tuple(errors),
    )


def build_runtime_read_only_projection() -> dict[str, Any]:
    """Build a deterministic runtime envelope from redacted fixture inputs."""
    return build_default_personal_assistant_read_only_projection(generated_at=RUNTIME_GENERATED_AT)


def build_read_only_projection_envelope(
    *,
    generated_at: str,
    projections: tuple[tuple[str, Mapping[str, Any]], ...],
) -> dict[str, Any]:
    """Build a schema-shaped no-effect envelope around read-only projections."""
    return build_personal_assistant_read_only_projection_envelope(
        generated_at=generated_at,
        projections=projections,
    )


def _validate_projection_semantics(
    projection: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    _require_false_fields(projection.get("effect_boundary"), FALSE_EFFECT_BOUNDARY_FIELDS, "effect_boundary", errors)
    private_policy = _mapping(projection.get("private_payload_policy"))
    if private_policy.get("raw_private_payload_serialized") is not False:
        errors.append("private_payload_policy.raw_private_payload_serialized must be false")
    if private_policy.get("secret_values_serialized") is not False:
        errors.append("private_payload_policy.secret_values_serialized must be false")
    assurance = _mapping(projection.get("assurance"))
    if assurance.get("foundation_only") is not True:
        errors.append("assurance.foundation_only must be true")
    if assurance.get("ready_for_live_execution") is not False:
        errors.append("assurance.ready_for_live_execution must be false")
    if assurance.get("ready_for_customer_readiness_claim") is not False:
        errors.append("assurance.ready_for_customer_readiness_claim must be false")
    if assurance.get("authority_drift_detected") is False and assurance.get("blocking_reasons") != []:
        errors.append("assurance.blocking_reasons must be empty when authority_drift_detected is false")
    if assurance.get("authority_drift_detected") is True and assurance.get("outcome") != "GovernanceBlocked":
        errors.append("assurance.outcome must be GovernanceBlocked when authority drift is detected")

    items = projection.get("projections")
    if not isinstance(items, list):
        errors.append("projections must be a list")
        return tuple(errors)
    if projection.get("projection_count") != len(items):
        errors.append("projection_count must equal projections length")
    projection_ids: list[str] = []
    receipt_ids: list[str] = []
    connector_names: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"projections[{index}] must be an object")
            continue
        projection_id = item.get("projection_id")
        if isinstance(projection_id, str):
            projection_ids.append(projection_id)
        summary = _mapping(item.get("summary"))
        if item.get("summary_type") != summary.get("summary_type"):
            errors.append(f"projections[{index}].summary_type must match summary.summary_type")
        if item.get("skill_id") == "email.inbox.summarize" and summary.get("effect_boundary") != "read_only_no_mailbox_mutation":
            errors.append(f"projections[{index}].summary.effect_boundary must block mailbox mutation")
        if item.get("skill_id") == "calendar.day.brief" and summary.get("effect_boundary") != "read_only_no_calendar_mutation":
            errors.append(f"projections[{index}].summary.effect_boundary must block calendar mutation")
        receipt = _mapping(item.get("receipt"))
        if receipt_schema:
            errors.extend(
                f"projections[{index}].receipt {message}"
                for message in _validate_schema_instance(receipt_schema, receipt)
            )
        errors.extend(
            f"projections[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        if receipt.get("request_id") != item.get("request_id"):
            errors.append(f"projections[{index}].receipt.request_id must match projection request_id")
        if receipt.get("skill_id") != item.get("skill_id"):
            errors.append(f"projections[{index}].receipt.skill_id must match projection skill_id")
        if receipt.get("approval_required") is not False:
            errors.append(f"projections[{index}].receipt.approval_required must be false")
        receipt_metadata = _mapping(receipt.get("metadata"))
        for field_name in ("live_connector_execution_allowed", "connector_mutation_allowed", "external_write_allowed"):
            if receipt_metadata.get(field_name) is not False:
                errors.append(f"projections[{index}].receipt.metadata.{field_name} must be false")
        receipt_id = receipt.get("receipt_id")
        if isinstance(receipt_id, str):
            receipt_ids.append(receipt_id)
        for connector_name in receipt.get("connectors_used", ()):
            if isinstance(connector_name, str) and connector_name not in connector_names:
                connector_names.append(connector_name)
    if projection.get("projection_ids") != projection_ids:
        errors.append("projection_ids must match projections order")
    if sorted(projection.get("receipt_ids", ())) != sorted(receipt_ids):
        errors.append("receipt_ids must match embedded receipts")
    if sorted(projection.get("connectors_used", ())) != sorted(connector_names):
        errors.append("connectors_used must match embedded receipts")
    return tuple(errors)


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
    """Parse read-only projection validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant read-only projection evidence.")
    parser.add_argument("--projection", default=str(DEFAULT_PROJECTION))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--skip-runtime", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for read-only projection validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_read_only_projection(
        projection_path=Path(args.projection),
        schema_path=Path(args.schema),
        receipt_schema_path=Path(args.receipt_schema),
        validate_runtime=not args.skip_runtime,
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant read-only projection ok "
            f"projections={result.projection_count} receipts={result.receipt_count} "
            f"runtime_validated={result.runtime_validated}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
