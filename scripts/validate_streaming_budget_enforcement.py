#!/usr/bin/env python3
"""Validate streaming budget enforcement events.

Purpose: prove predictive debit events obey the public streaming budget
enforcement protocol beyond JSON shape.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: schemas/streaming_budget_enforcement.schema.json.
Invariants:
  - Event payloads match the published schema.
  - Reservation totals equal estimated input plus reserved output tokens.
  - Emitted output tokens never exceed the reserved output reservation.
  - Cutoff retry flags match the declared cutoff semantic.
  - Settlement token deltas match actual usage minus reserved total tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schemas" / "streaming_budget_enforcement.schema.json"


@dataclass(frozen=True, slots=True)
class StreamingBudgetValidation:
    """Structured validation result for one streaming budget event."""

    valid: bool
    errors: tuple[str, ...]


def validate_streaming_budget_event(payload: dict[str, Any]) -> StreamingBudgetValidation:
    """Validate one streaming budget enforcement event."""
    schema_errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    errors = [_bounded_schema_error(error) for error in schema_errors]
    errors.extend(_validate_protocol_invariants(payload))
    return StreamingBudgetValidation(valid=not errors, errors=tuple(errors))


def _validate_protocol_invariants(payload: dict[str, Any]) -> list[str]:
    """Validate cross-field protocol invariants that schema shape cannot express."""
    errors: list[str] = []
    event_type = payload.get("event_type")
    estimated_input_tokens = _integer_field(payload, "estimated_input_tokens")
    reserved_output_tokens = _integer_field(payload, "reserved_output_tokens")
    reserved_total_tokens = _integer_field(payload, "reserved_total_tokens")
    emitted_output_tokens = _integer_field(payload, "emitted_output_tokens")
    actual_input_tokens = _integer_field(payload, "actual_input_tokens")
    actual_output_tokens = _integer_field(payload, "actual_output_tokens")
    delta_tokens = _integer_field(payload, "delta_tokens")

    if (
        estimated_input_tokens is not None
        and reserved_output_tokens is not None
        and reserved_total_tokens is not None
        and reserved_total_tokens != estimated_input_tokens + reserved_output_tokens
    ):
        errors.append("reserved_total_tokens must equal estimated_input_tokens plus reserved_output_tokens")

    if (
        emitted_output_tokens is not None
        and reserved_output_tokens is not None
        and emitted_output_tokens > reserved_output_tokens
    ):
        errors.append("emitted_output_tokens must not exceed reserved_output_tokens")

    if event_type == "cutoff_emitted":
        cutoff_semantic = payload.get("cutoff_semantic")
        retry_eligible = payload.get("retry_eligible")
        if cutoff_semantic == "retry_eligible" and retry_eligible is not True:
            errors.append("retry_eligible cutoff_semantic requires retry_eligible true")
        if cutoff_semantic in {"graceful", "abrupt"} and retry_eligible is not False:
            errors.append("non-retry cutoff_semantic requires retry_eligible false")
        if (
            emitted_output_tokens is not None
            and reserved_output_tokens is not None
            and emitted_output_tokens != reserved_output_tokens
        ):
            errors.append("cutoff_emitted requires emitted_output_tokens to equal reserved_output_tokens")

    if (
        event_type == "settled"
        and actual_input_tokens is not None
        and actual_output_tokens is not None
        and reserved_total_tokens is not None
        and delta_tokens is not None
        and delta_tokens != actual_input_tokens + actual_output_tokens - reserved_total_tokens
    ):
        errors.append("delta_tokens must equal actual total tokens minus reserved_total_tokens")

    return errors


def _integer_field(payload: dict[str, Any], field_name: str) -> int | None:
    value = payload.get(field_name)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _bounded_schema_error(error: str) -> str:
    if "missing required fields" in error:
        return "schema contract missing required fields"
    if "unexpected property" in error:
        return "schema contract unexpected property"
    if "expected" in error:
        return "schema contract type or value mismatch"
    return "schema contract validation failed"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for streaming budget event validation."""
    parser = argparse.ArgumentParser(
        description="Validate one streaming budget enforcement event JSON payload.",
    )
    parser.add_argument("event", help="Path to a streaming budget event JSON payload.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for streaming budget event validation."""
    args = parse_args(argv)
    event_path = Path(args.event)
    try:
        payload = json.loads(event_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("FAILED - event JSON parse failed")
        return 1
    if not isinstance(payload, dict):
        print("FAILED - event JSON root must be an object")
        return 1

    validation = validate_streaming_budget_event(payload)
    if not validation.valid:
        print(f"FAILED - {len(validation.errors)} error(s):")
        for error in validation.errors:
            print(f"  X {error}")
        return 1
    print("STREAMING BUDGET EVENT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
