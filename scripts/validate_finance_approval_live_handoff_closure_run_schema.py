#!/usr/bin/env python3
"""Validate finance approval live handoff closure run schema conformance.

Purpose: reject malformed or unsafe finance live handoff closure run records.
Governance scope: closure-run schema validation, dry-run enforcement, command
ordering, live connector touchpoint boundary, and readiness/blocker consistency.
Dependencies: schemas/finance_approval_live_handoff_closure_run.schema.json and
.change_assurance/finance_approval_live_handoff_closure_run.json.
Invariants:
  - Closure run shape matches the public protocol schema.
  - Closure run mode remains dry-run.
  - Binding validation precedes live receipt collection.
  - Exactly one live connector touchpoint is declared.
  - Status, blockers, and ready_to_execute_live remain mutually consistent.
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

from scripts.run_finance_approval_live_handoff_closure import DEFAULT_OUTPUT as DEFAULT_CLOSURE_RUN  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "finance_approval_live_handoff_closure_run.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "finance_approval_live_handoff_closure_run_schema_validation.json"
EXPECTED_STEP_IDS = (
    "01_emit_binding_receipt",
    "02_validate_binding_receipt",
    "03_collect_read_only_live_receipt",
    "04_validate_read_only_live_receipt",
    "05_collect_adapter_evidence",
    "06_validate_pilot_readiness",
    "07_refresh_handoff_plan",
    "08_validate_handoff_plan_schema",
    "09_run_preflight",
    "10_validate_preflight_schema",
    "11_produce_handoff_packet",
    "12_validate_handoff_packet_schema",
    "13_validate_handoff_chain",
    "14_validate_handoff_chain_schema",
)
LIVE_STEP_ID = "03_collect_read_only_live_receipt"


@dataclass(frozen=True, slots=True)
class FinanceLiveHandoffClosureRunSchemaValidation:
    """Schema and semantic validation for one finance closure run."""

    ok: bool
    errors: tuple[str, ...]
    closure_run_path: str
    schema_path: str
    command_count: int
    live_command_count: int
    status: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_finance_approval_live_handoff_closure_run_schema(
    *,
    closure_run_path: Path = DEFAULT_CLOSURE_RUN,
    schema_path: Path = DEFAULT_SCHEMA,
) -> FinanceLiveHandoffClosureRunSchemaValidation:
    """Validate finance closure run schema and semantic consistency."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "finance live handoff closure run schema", errors)
    closure_run = _load_json_object(closure_run_path, "finance live handoff closure run", errors)
    if not schema or not closure_run:
        return _validation_result(
            closure_run_path=closure_run_path,
            schema_path=schema_path,
            closure_run=closure_run,
            errors=errors,
        )

    errors.extend(_validate_schema_instance(schema, closure_run))
    _validate_status_consistency(closure_run, errors)
    _validate_command_sequence(closure_run, errors)
    return _validation_result(
        closure_run_path=closure_run_path,
        schema_path=schema_path,
        closure_run=closure_run,
        errors=errors,
    )


def write_finance_live_handoff_closure_run_schema_validation(
    validation: FinanceLiveHandoffClosureRunSchemaValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic finance closure run schema validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_status_consistency(closure_run: dict[str, Any], errors: list[str]) -> None:
    status = closure_run.get("status")
    ready_to_execute_live = closure_run.get("ready_to_execute_live") is True
    blockers = closure_run.get("blockers", [])
    if closure_run.get("mode") != "dry-run":
        errors.append("mode must remain dry-run")
    if status == "ready" and not ready_to_execute_live:
        errors.append("status=ready requires ready_to_execute_live=true")
    if status == "blocked" and ready_to_execute_live:
        errors.append("status=blocked requires ready_to_execute_live=false")
    if ready_to_execute_live and blockers:
        errors.append("ready_to_execute_live=true requires no blockers")
    if not ready_to_execute_live and not blockers:
        errors.append("blocked closure run must contain blockers")


def _validate_command_sequence(closure_run: dict[str, Any], errors: list[str]) -> None:
    commands = closure_run.get("commands", [])
    if not isinstance(commands, list):
        errors.append("commands must be a list")
        return
    if closure_run.get("command_count") != len(commands):
        errors.append("command_count must match commands length")
    step_ids = tuple(str(command.get("step_id", "")) for command in commands if isinstance(command, dict))
    if step_ids != EXPECTED_STEP_IDS:
        errors.append(f"step_ids must match expected finance closure order: observed={list(step_ids)}")
    live_steps = tuple(
        str(command.get("step_id", ""))
        for command in commands
        if isinstance(command, dict) and command.get("live_effect_possible") is True
    )
    if live_steps != (LIVE_STEP_ID,):
        errors.append(f"live_effect_possible must be true only for {LIVE_STEP_ID}: observed={list(live_steps)}")
    required_steps = tuple(
        str(command.get("step_id", ""))
        for command in commands
        if isinstance(command, dict) and command.get("required_before_next") is True
    )
    if required_steps != EXPECTED_STEP_IDS:
        errors.append("all finance closure commands must be required_before_next=true")
    command_by_step = {str(command.get("step_id", "")): command for command in commands if isinstance(command, dict)}
    live_command = command_by_step.get(LIVE_STEP_ID, {})
    if "produce_capability_adapter_live_receipts.py --target email-calendar" not in str(live_command.get("command", "")):
        errors.append("live receipt command must target email-calendar capability adapter")


def _validation_result(
    *,
    closure_run_path: Path,
    schema_path: Path,
    closure_run: dict[str, Any],
    errors: list[str],
) -> FinanceLiveHandoffClosureRunSchemaValidation:
    commands = closure_run.get("commands", ())
    live_command_count = sum(
        1
        for command in commands
        if isinstance(commands, list) and isinstance(command, dict) and command.get("live_effect_possible") is True
    )
    return FinanceLiveHandoffClosureRunSchemaValidation(
        ok=not errors,
        errors=tuple(errors),
        closure_run_path=str(closure_run_path),
        schema_path=str(schema_path),
        command_count=len(commands) if isinstance(commands, list) else 0,
        live_command_count=live_command_count,
        status=str(closure_run.get("status", "")),
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
    """Parse finance closure run schema validation arguments."""
    parser = argparse.ArgumentParser(description="Validate finance approval live handoff closure run schema.")
    parser.add_argument("--closure-run", default=str(DEFAULT_CLOSURE_RUN))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for finance closure run schema validation."""
    args = parse_args(argv)
    validation = validate_finance_approval_live_handoff_closure_run_schema(
        closure_run_path=Path(args.closure_run),
        schema_path=Path(args.schema),
    )
    write_finance_live_handoff_closure_run_schema_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("FINANCE LIVE HANDOFF CLOSURE RUN SCHEMA VALID")
    else:
        print(f"FINANCE LIVE HANDOFF CLOSURE RUN SCHEMA INVALID errors={list(validation.errors)}")
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
