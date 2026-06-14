#!/usr/bin/env python3
"""Validate a personal-assistant memory observation read-model fixture.

Purpose: ensure memory observation projections remain candidate-only,
schema-backed, redacted, and unable to imply live memory writes or Nested Mind
activation.
Governance scope: memory read-model schema conformance, observation schema
conformance, receipt conformance, no secret serialization, no raw private
payload storage, and no live memory authority.
Dependencies: personal-assistant memory read-model, observation, and receipt
schemas plus the example read-model fixture.
Invariants:
  - Memory read models never grant live memory write authority.
  - Nested Mind live activation remains blocked and staging-only.
  - Raw chat logs, raw connector payloads, and secret-like values are rejected.
  - Every candidate carries an observation and a receipt.
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_READ_MODEL = REPO_ROOT / "examples" / "personal_assistant_memory_read_model.json"
DEFAULT_READ_MODEL_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_memory_read_model.schema.json"
DEFAULT_OBSERVATION_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_memory_observation.schema.json"
DEFAULT_RECEIPT_SCHEMA = REPO_ROOT / "schemas" / "personal_assistant_receipt.schema.json"

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
REQUIRED_ACTIONS_NOT_TAKEN = frozenset(
    {
        "live_memory_not_written",
        "nested_mind_not_activated",
        "raw_chat_log_not_stored",
        "raw_connector_payload_not_stored",
        "system_of_record_not_mutated",
    }
)


@dataclass(frozen=True, slots=True)
class PersonalAssistantMemoryObservationValidation:
    """Validation result for one personal-assistant memory read model."""

    valid: bool
    read_model_path: str
    candidate_count: int
    receipt_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_personal_assistant_memory_observation(
    *,
    read_model_path: Path = DEFAULT_READ_MODEL,
    read_model_schema_path: Path = DEFAULT_READ_MODEL_SCHEMA,
    observation_schema_path: Path = DEFAULT_OBSERVATION_SCHEMA,
    receipt_schema_path: Path = DEFAULT_RECEIPT_SCHEMA,
) -> PersonalAssistantMemoryObservationValidation:
    """Validate one personal-assistant memory observation read model."""
    errors: list[str] = []
    read_model_schema = _load_json_object(read_model_schema_path, "memory read-model schema", errors)
    observation_schema = _load_json_object(observation_schema_path, "memory observation schema", errors)
    receipt_schema = _load_json_object(receipt_schema_path, "personal-assistant receipt schema", errors)
    read_model = _load_json_object(read_model_path, "memory read model", errors)
    if read_model_schema and read_model:
        errors.extend(_validate_schema_instance(read_model_schema, read_model))
    if read_model:
        errors.extend(_validate_read_model_semantics(read_model, observation_schema, receipt_schema))
        _scan_private_or_secret_payload(read_model, errors, path="$")
    return PersonalAssistantMemoryObservationValidation(
        valid=not errors,
        read_model_path=_path_label(read_model_path),
        candidate_count=int(read_model.get("candidate_count", 0)) if isinstance(read_model, dict) else 0,
        receipt_count=_receipt_count(read_model),
        errors=tuple(errors),
    )


def _validate_read_model_semantics(
    read_model: dict[str, Any],
    observation_schema: dict[str, Any],
    receipt_schema: dict[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    for field_name in (
        "live_memory_write_allowed",
        "nested_mind_live_activation_allowed",
        "raw_private_payload_storage_allowed",
        "secret_value_storage_allowed",
    ):
        if read_model.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if read_model.get("candidate_only") is not True:
        errors.append("candidate_only must be true")

    metadata = read_model.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object")
    else:
        if metadata.get("foundation_only") is not True:
            errors.append("metadata.foundation_only must be true")
        for field_name in (
            "live_memory_write_allowed",
            "nested_mind_live_activation_allowed",
            "raw_private_payload_storage_allowed",
            "secret_value_storage_allowed",
        ):
            if metadata.get(field_name) is not False:
                errors.append(f"metadata.{field_name} must be false")

    candidates = read_model.get("candidates", ())
    if not isinstance(candidates, list):
        errors.append("candidates must be a list")
        return tuple(errors)
    if read_model.get("candidate_count") != len(candidates):
        errors.append("candidate_count must equal candidates length")

    observation_ids: list[str] = []
    memory_types: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"candidates[{index}] must be an object")
            continue
        observation = candidate.get("observation")
        receipt = candidate.get("receipt")
        if not isinstance(observation, dict):
            errors.append(f"candidates[{index}].observation must be an object")
            continue
        if not isinstance(receipt, dict):
            errors.append(f"candidates[{index}].receipt must be an object")
            continue

        errors.extend(
            f"candidates[{index}].observation {message}"
            for message in _validate_schema_instance(observation_schema, observation)
        )
        errors.extend(
            f"candidates[{index}].receipt {message}"
            for message in _validate_schema_instance(receipt_schema, receipt)
        )
        errors.extend(
            f"candidates[{index}].receipt {message}"
            for message in validate_personal_assistant_receipt_payload(receipt)
        )
        errors.extend(_validate_candidate_boundary(candidate, observation, receipt, index))
        observation_id = observation.get("memory_observation_id")
        if isinstance(observation_id, str):
            observation_ids.append(observation_id)
        memory_type = observation.get("memory_type")
        if isinstance(memory_type, str):
            memory_types.add(memory_type)

    if sorted(read_model.get("memory_observation_ids", ())) != sorted(observation_ids):
        errors.append("memory_observation_ids must match embedded observations")
    if sorted(read_model.get("memory_types", ())) != sorted(memory_types):
        errors.append("memory_types must match embedded observations")
    return tuple(errors)


def _validate_candidate_boundary(
    candidate: dict[str, Any],
    observation: dict[str, Any],
    receipt: dict[str, Any],
    index: int,
) -> tuple[str, ...]:
    errors: list[str] = []
    observation_id = observation.get("memory_observation_id")
    if candidate.get("memory_observation_id") != observation_id:
        errors.append(f"candidates[{index}].memory_observation_id must match observation")
    if observation.get("nested_mind_status") != "staging_only":
        errors.append(f"candidates[{index}].observation.nested_mind_status must be staging_only")
    if observation.get("sensitivity") == "secret_forbidden":
        errors.append(f"candidates[{index}].observation.sensitivity must not be secret_forbidden")
    if observation.get("retention_policy") == "do_not_store":
        errors.append(f"candidates[{index}].observation.retention_policy must not be do_not_store")

    receipt_memory_refs = receipt.get("memory_observation_refs")
    if receipt_memory_refs != [observation_id]:
        errors.append(f"candidates[{index}].receipt.memory_observation_refs must bind observation id")
    missing_actions = sorted(REQUIRED_ACTIONS_NOT_TAKEN.difference(_string_set(receipt, "actions_not_taken")))
    if missing_actions:
        errors.append(f"candidates[{index}].receipt.actions_not_taken missing {missing_actions}")
    private_policy = receipt.get("private_payload_policy", {})
    if not isinstance(private_policy, dict):
        errors.append(f"candidates[{index}].receipt.private_payload_policy must be an object")
    else:
        if private_policy.get("raw_private_payload_serialized") is not False:
            errors.append(f"candidates[{index}].receipt raw_private_payload_serialized must be false")
        if private_policy.get("secret_values_serialized") is not False:
            errors.append(f"candidates[{index}].receipt secret_values_serialized must be false")
    metadata = receipt.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append(f"candidates[{index}].receipt.metadata must be an object")
    else:
        if metadata.get("candidate_only") is not True:
            errors.append(f"candidates[{index}].receipt.metadata.candidate_only must be true")
        if metadata.get("live_memory_write_allowed") is not False:
            errors.append(f"candidates[{index}].receipt.metadata.live_memory_write_allowed must be false")
        if metadata.get("nested_mind_live_activation_allowed") is not False:
            errors.append(f"candidates[{index}].receipt.metadata.nested_mind_live_activation_allowed must be false")
    return tuple(errors)


def _scan_private_or_secret_payload(payload: Any, errors: list[str], *, path: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key in RAW_PRIVATE_FIELD_NAMES:
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


def _receipt_count(read_model: dict[str, Any]) -> int:
    candidates = read_model.get("candidates", ()) if isinstance(read_model, dict) else ()
    return sum(1 for candidate in candidates if isinstance(candidate, dict) and isinstance(candidate.get("receipt"), dict))


def _string_set(payload: dict[str, Any], field_name: str) -> set[str]:
    values = payload.get(field_name, ())
    return {value for value in values if isinstance(value, str)} if isinstance(values, list) else set()


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
    """Parse personal-assistant memory observation validation arguments."""
    parser = argparse.ArgumentParser(description="Validate personal-assistant memory observation read model.")
    parser.add_argument("--read-model", default=str(DEFAULT_READ_MODEL))
    parser.add_argument("--schema", default=str(DEFAULT_READ_MODEL_SCHEMA))
    parser.add_argument("--observation-schema", default=str(DEFAULT_OBSERVATION_SCHEMA))
    parser.add_argument("--receipt-schema", default=str(DEFAULT_RECEIPT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for personal-assistant memory observation validation."""
    args = parse_args(argv)
    result = validate_personal_assistant_memory_observation(
        read_model_path=Path(args.read_model),
        read_model_schema_path=Path(args.schema),
        observation_schema_path=Path(args.observation_schema),
        receipt_schema_path=Path(args.receipt_schema),
    )
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(
            "personal-assistant memory observation ok "
            f"candidates={result.candidate_count} receipts={result.receipt_count}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
