#!/usr/bin/env python3
"""Validate finance approval live handoff preflight schema conformance.

Purpose: reject malformed or internally inconsistent finance live handoff
preflight reports before operator handoff.
Governance scope: preflight schema validation, four-step gate ordering,
blocker derivation, and ready/status consistency.
Dependencies: schemas/finance_approval_live_handoff_preflight.schema.json and
.change_assurance/finance_approval_live_handoff_preflight.json.
Invariants:
  - Preflight shape matches the public protocol schema.
  - The four gate names appear in governed order.
  - Blockers are exactly the failed step names.
  - Ready state is derived from blockers.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.preflight_finance_approval_live_handoff import DEFAULT_OUTPUT as DEFAULT_PREFLIGHT  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_live_handoff_preflight.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_preflight_schema_validation.json"
EXPECTED_STEP_NAMES = (
    "finance handoff plan schema validation",
    "finance email/calendar binding receipt ready",
    "finance live handoff closure run schema validation",
    "finance approval pilot readiness",
)


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffPreflightSchemaValidation:
    """Schema and semantic validation for one finance preflight report."""

    ok: bool
    errors: tuple[str, ...]
    preflight_path: str
    schema_path: str
    step_count: int
    blocker_count: int
    readiness_level: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_live_handoff_preflight_schema(
    *,
    preflight_path: Path = DEFAULT_PREFLIGHT,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceLiveHandoffPreflightSchemaValidation:
    """Validate finance preflight report schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance live handoff preflight schema", errors)
    preflight = _load_json_object(preflight_path, "finance live handoff preflight", errors)
    if not schema or not preflight:
        return _validation_result(
            preflight_path=preflight_path,
            schema_path=schema_path,
            preflight=preflight,
            errors=errors,
        )

    errors.extend(_validate_schema_instance(schema, preflight))
    _validate_step_sequence(preflight, errors)
    _validate_status_consistency(preflight, errors)
    return _validation_result(
        preflight_path=preflight_path,
        schema_path=schema_path,
        preflight=preflight,
        errors=errors,
    )


def write_finance_live_handoff_preflight_schema_validation(
    validation: FinanceLiveHandoffPreflightSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic finance preflight schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_step_sequence(preflight: dict[str, Any], errors: list[str]) -> None:
    steps = preflight.get("steps", [])
    if not isinstance(steps, list):
        errors.append("steps must be a list")
        return
    if preflight.get("step_count") != len(steps):
        errors.append("step_count must match steps length")
    step_names = tuple(str(step.get("name", "")) for step in steps if isinstance(step, dict))
    if step_names != EXPECTED_STEP_NAMES:
        errors.append(f"step names must match expected finance preflight order: observed={list(step_names)}")


def _validate_status_consistency(preflight: dict[str, Any], errors: list[str]) -> None:
    steps = preflight.get("steps", [])
    if not isinstance(steps, list):
        return
    blockers = preflight.get("blockers", [])
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
        return
    expected_blockers = [
        str(step.get("name", ""))
        for step in steps
        if isinstance(step, dict) and step.get("passed") is not True
    ]
    observed_blockers = [str(blocker) for blocker in blockers]
    if observed_blockers != expected_blockers:
        errors.append(
            "blockers must match failed preflight step names: "
            f"observed={observed_blockers} expected={expected_blockers}"
        )
    ready = preflight.get("ready") is True
    if ready and observed_blockers:
        errors.append("ready preflight must not contain blockers")
    if not ready and not observed_blockers:
        errors.append("blocked preflight must contain blockers")
    if ready and preflight.get("readiness_level") != "live-email-handoff-ready":
        errors.append("ready preflight requires readiness_level=live-email-handoff-ready")


def _validation_result(
    *,
    preflight_path: Path,
    schema_path: Path,
    preflight: dict[str, Any],
    errors: list[str],
) -> FinanceLiveHandoffPreflightSchemaValidation:
    steps = preflight.get("steps", ())
    blockers = preflight.get("blockers", ())
    return FinanceLiveHandoffPreflightSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        preflight_path=str(preflight_path),
        schema_path=str(schema_path),
        step_count=len(steps) if isinstance(steps, list) else 0,
        blocker_count=len(blockers) if isinstance(blockers, list) else 0,
        readiness_level=str(preflight.get("readiness_level", "")),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse finance preflight schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval live handoff preflight schema.")
    parser.add_argument("--preflight", default=str(DEFAULT_PREFLIGHT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance preflight schema validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_live_handoff_preflight_schema(
        preflight_path=Path(args.preflight),
        schema_path=Path(args.schema),
    )
    write_finance_live_handoff_preflight_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE LIVE HANDOFF PREFLIGHT SCHEMA VALID")
    else:
        print(f"FINANCE LIVE HANDOFF PREFLIGHT SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
