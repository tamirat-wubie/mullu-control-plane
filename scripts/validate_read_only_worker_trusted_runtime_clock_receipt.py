#!/usr/bin/env python3
"""Validate read-only worker trusted runtime clock receipts.

Purpose: verify Foundation Mode trusted-clock evidence for future read-only
worker runtime enablement review without granting runtime authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schema validation helpers and the trusted-clock schema/fixture.
Invariants:
  - The clock receipt is evidence only, not authorization.
  - Runtime enablement, dispatch, worker invocation, receipt emission, receipt
    append, terminal closure, network, filesystem writes, and secret
    serialization remain denied.
  - The clock has a bounded validity window and monotonicity requirement.
  - Mfidel atomicity is preserved.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_read_only_worker_runtime_enablement_evidence_request_status_ledger import (  # noqa: E402
    BLOCKED_ACTIONS,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "read_only_worker_trusted_runtime_clock_receipt.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "read_only_worker_trusted_runtime_clock_receipt.foundation.json"
DENIED_FIELDS = (
    "runtime_enablement_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "terminal_closure_allowed",
    "secret_values_serialized",
    "external_network_allowed",
    "filesystem_write_allowed",
)


def validate_trusted_runtime_clock_receipt(
    *,
    receipt_path: Path = DEFAULT_EXAMPLE,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    """Return deterministic validation errors for one clock receipt."""

    schema = _load_schema(schema_path)
    receipt = _load_json_object(receipt_path, "trusted runtime clock receipt")
    return validate_trusted_runtime_clock_receipt_record(receipt, schema)


def validate_trusted_runtime_clock_receipt_record(
    receipt: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one clock receipt record."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA)
    errors = _validate_schema_instance(schema_payload, receipt)
    if not isinstance(receipt, dict):
        errors.append("trusted runtime clock receipt must be a JSON object")
        return errors
    if receipt.get("clock_receipt_is_not_authorization") is not True:
        errors.append("clock_receipt_is_not_authorization must be true")
    if receipt.get("monotonicity_required") is not True:
        errors.append("monotonicity_required must be true")
    if receipt.get("validity_window_seconds") != 300:
        errors.append("validity_window_seconds must be 300")
    _validate_observed_at(str(receipt.get("observed_at", "")), errors)
    for field_name in DENIED_FIELDS:
        if receipt.get(field_name) is not False:
            errors.append(f"{field_name} must be false")
    if set(_string_list(receipt.get("blocked_actions"))) != set(BLOCKED_ACTIONS):
        errors.append("blocked_actions must match runtime enablement blocked actions")
    return errors


def build_mutated_trusted_runtime_clock_receipt(**overrides: Any) -> dict[str, Any]:
    """Return a deep-copied clock fixture with simple overrides."""

    record = _load_json_object(DEFAULT_EXAMPLE, "trusted runtime clock receipt")
    mutated = deepcopy(record)
    for key, value in overrides.items():
        mutated[key] = value
    return mutated


def _validate_observed_at(observed_at: str, errors: list[str]) -> None:
    if not observed_at.endswith("Z"):
        errors.append("observed_at must be UTC with Z suffix")
        return
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError:
        errors.append("observed_at must be a valid ISO date-time")


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except OSError as exc:
        raise RuntimeError(f"{label} file missing: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"{label} JSON parse failed") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} JSON root must be an object")
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _path_label(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description="Validate read-only worker trusted runtime clock receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_trusted_runtime_clock_receipt(
        receipt_path=Path(args.receipt),
        schema_path=Path(args.schema),
    )
    if args.json:
        print(
            json.dumps(
                {
                    "status": "passed" if not errors else "failed",
                    "receipt_path": _path_label(Path(args.receipt)),
                    "schema_path": _path_label(Path(args.schema)),
                    "errors": errors,
                    "runtime_enablement_allowed": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        print(f"trusted runtime clock receipt invalid errors={errors}")
    else:
        print("trusted runtime clock receipt valid")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
