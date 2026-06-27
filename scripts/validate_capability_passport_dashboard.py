#!/usr/bin/env python3
"""Validate the capability passport dashboard read model.

Purpose: prove the operator dashboard is a read-only projection of capability
passports and gate templates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/capability_passport_dashboard.schema.json,
examples/capability_passport_dashboard.foundation.json, capability passports,
and gate template registry.
Invariants:
  - Dashboard state is not execution authority.
  - Every passport appears in exactly one simple operator status lane.
  - Operator cards do not expose raw gate IDs or schema refs.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.capability_passport_dashboard import (  # noqa: E402
    STATUS_ORDER,
    build_capability_passport_dashboard,
)
from mcoi_runtime.app.capability_passports import build_capability_passports  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "capability_passport_dashboard.schema.json"
DEFAULT_DASHBOARD = REPO_ROOT / "examples" / "capability_passport_dashboard.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "capability_passport_dashboard_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "capability_passport_dashboard_validator": "python scripts/validate_capability_passport_dashboard.py",
    "capability_passport_dashboard_tests": "python -m pytest tests/test_validate_capability_passport_dashboard.py -q",
}
FORBIDDEN_OPERATOR_CARD_FIELDS = {
    "required_gates",
    "source_ref",
    "input_schema_ref",
    "output_schema_ref",
    "schema_ref",
    "gate_id",
    "passport_id",
}


@dataclass(frozen=True, slots=True)
class CapabilityPassportDashboardValidation:
    """Validation report for the capability passport dashboard."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    dashboard_path: str
    capability_count: int
    family_count: int
    unresolved_gate_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_capability_passport_dashboard(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    dashboard_path: Path = DEFAULT_DASHBOARD,
) -> CapabilityPassportDashboardValidation:
    """Validate the dashboard against schema and runtime projections."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "capability passport dashboard schema", errors)
    dashboard = _load_json_object(dashboard_path, "capability passport dashboard example", errors)
    runtime_dashboard = build_capability_passport_dashboard() if not errors else {}
    runtime_passports = build_capability_passports() if not errors else {}

    if schema and dashboard:
        errors.extend(f"{_path_label(dashboard_path)}: {error}" for error in _validate_schema_instance(schema, dashboard))
        if dashboard != runtime_dashboard:
            errors.append(f"{_path_label(dashboard_path)}: example does not match runtime projection")
    if dashboard:
        _validate_dashboard(dashboard, runtime_dashboard, runtime_passports, errors, _path_label(dashboard_path))

    summary = dashboard.get("summary", {}) if isinstance(dashboard, dict) else {}
    governance_health = dashboard.get("governance_health", {}) if isinstance(dashboard, dict) else {}
    return CapabilityPassportDashboardValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        dashboard_path=_path_label(dashboard_path),
        capability_count=int(summary.get("capability_count", 0)) if isinstance(summary, dict) else 0,
        family_count=int(summary.get("family_count", 0)) if isinstance(summary, dict) else 0,
        unresolved_gate_count=int(governance_health.get("unresolved_gate_count", 0))
        if isinstance(governance_health, dict)
        else 0,
    )


def write_capability_passport_dashboard_validation(
    validation: CapabilityPassportDashboardValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic dashboard validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_dashboard(
    dashboard: dict[str, Any],
    runtime_dashboard: dict[str, Any],
    runtime_passports: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if dashboard.get("dashboard_is_not_execution_authority") is not True:
        errors.append(f"{label}: dashboard_is_not_execution_authority must be true")
    if dashboard.get("live_execution_enabled") is not False:
        errors.append(f"{label}: live_execution_enabled must be false")
    _validate_validators(dashboard, errors, label)

    passport_entries = _list_of_objects(runtime_passports.get("passports"))
    operator_view = dashboard.get("operator_view")
    if not isinstance(operator_view, dict):
        errors.append(f"{label}: operator_view must be an object")
        return
    _validate_status_tiles(dashboard, passport_entries, errors, label)
    _validate_status_lanes(operator_view, passport_entries, errors, label)
    _validate_family_rows(dashboard, passport_entries, errors, label)
    _validate_governance_health(dashboard, runtime_dashboard, passport_entries, errors, label)


def _validate_status_tiles(
    dashboard: Mapping[str, Any],
    passport_entries: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    summary = dashboard.get("summary")
    operator_view = dashboard.get("operator_view")
    if not isinstance(summary, dict) or not isinstance(operator_view, dict):
        errors.append(f"{label}: summary and operator_view must be objects")
        return
    status_counts = summary.get("status_counts")
    tiles = operator_view.get("status_tiles")
    if not isinstance(status_counts, dict) or not isinstance(tiles, list):
        errors.append(f"{label}: status_counts and status_tiles must be present")
        return
    expected_counts = _status_counts(passport_entries)
    if status_counts != expected_counts:
        errors.append(f"{label}: summary.status_counts must match passport statuses")
    if summary.get("capability_count") != len(passport_entries):
        errors.append(f"{label}: summary.capability_count must match passport count")
    if summary.get("ready_count") != expected_counts["Ready"]:
        errors.append(f"{label}: summary.ready_count must match Ready count")
    expected_attention = sum(expected_counts[status] for status in STATUS_ORDER if status != "Ready")
    if summary.get("attention_required_count") != expected_attention:
        errors.append(f"{label}: summary.attention_required_count must match non-ready count")
    tile_labels = [tile.get("label") for tile in tiles if isinstance(tile, dict)]
    if tuple(tile_labels) != STATUS_ORDER:
        errors.append(f"{label}: status_tiles must use canonical status order")
    for tile in tiles:
        if not isinstance(tile, dict):
            errors.append(f"{label}: status_tiles entries must be objects")
            continue
        status = str(tile.get("label", ""))
        if status in expected_counts and tile.get("count") != expected_counts[status]:
            errors.append(f"{label}: status tile {status} count must match passports")


def _validate_status_lanes(
    operator_view: Mapping[str, Any],
    passport_entries: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    lanes = operator_view.get("status_lanes")
    if not isinstance(lanes, list):
        errors.append(f"{label}: status_lanes must be a list")
        return
    lane_labels = [lane.get("label") for lane in lanes if isinstance(lane, dict)]
    if tuple(lane_labels) != STATUS_ORDER:
        errors.append(f"{label}: status_lanes must use canonical status order")

    seen_capability_ids: list[str] = []
    for lane in lanes:
        if not isinstance(lane, dict):
            errors.append(f"{label}: status_lanes entries must be objects")
            continue
        lane_label = str(lane.get("label", ""))
        cards = lane.get("capabilities")
        if not isinstance(cards, list):
            errors.append(f"{label}: lane {lane_label} capabilities must be a list")
            continue
        if lane.get("count") != len(cards):
            errors.append(f"{label}: lane {lane_label} count must match card count")
        for card in cards:
            if not isinstance(card, dict):
                errors.append(f"{label}: lane {lane_label} cards must be objects")
                continue
            _validate_operator_card(card, lane_label, errors, label)
            seen_capability_ids.append(str(card.get("capability_id", "")))

    expected_capability_ids = sorted(str(passport["capability_id"]) for passport in passport_entries)
    if sorted(seen_capability_ids) != expected_capability_ids:
        errors.append(f"{label}: status_lanes must contain every passport exactly once")


def _validate_operator_card(
    card: Mapping[str, Any],
    lane_label: str,
    errors: list[str],
    label: str,
) -> None:
    capability_id = str(card.get("capability_id", "<missing>"))
    if card.get("status") != lane_label:
        errors.append(f"{label}: {capability_id} card status must match lane {lane_label}")
    forbidden = sorted(FORBIDDEN_OPERATOR_CARD_FIELDS & set(card))
    if forbidden:
        errors.append(f"{label}: {capability_id} operator card exposes internal fields {forbidden}")
    if not isinstance(card.get("blocked_action_count"), int):
        errors.append(f"{label}: {capability_id} blocked_action_count must be an integer")
    if not isinstance(card.get("required_receipt_count"), int):
        errors.append(f"{label}: {capability_id} required_receipt_count must be an integer")


def _validate_family_rows(
    dashboard: Mapping[str, Any],
    passport_entries: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    operator_view = dashboard.get("operator_view")
    summary = dashboard.get("summary")
    if not isinstance(operator_view, dict) or not isinstance(summary, dict):
        return
    rows = operator_view.get("family_rows")
    if not isinstance(rows, list):
        errors.append(f"{label}: family_rows must be a list")
        return
    expected_families = sorted({str(passport["family"]) for passport in passport_entries})
    row_families = sorted(str(row.get("family", "")) for row in rows if isinstance(row, dict))
    if row_families != expected_families:
        errors.append(f"{label}: family_rows must cover every passport family")
    if summary.get("family_count") != len(expected_families):
        errors.append(f"{label}: summary.family_count must match family rows")
    for row in rows:
        if not isinstance(row, dict):
            errors.append(f"{label}: family_rows entries must be objects")
            continue
        family = str(row.get("family", ""))
        family_passports = [passport for passport in passport_entries if passport["family"] == family]
        if row.get("capability_count") != len(family_passports):
            errors.append(f"{label}: family {family} capability_count must match passports")
        if row.get("status_counts") != _status_counts(family_passports):
            errors.append(f"{label}: family {family} status_counts must match passports")


def _validate_governance_health(
    dashboard: Mapping[str, Any],
    runtime_dashboard: Mapping[str, Any],
    passport_entries: list[dict[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    governance_health = dashboard.get("governance_health")
    runtime_health = runtime_dashboard.get("governance_health") if isinstance(runtime_dashboard, dict) else {}
    if not isinstance(governance_health, dict) or not isinstance(runtime_health, dict):
        errors.append(f"{label}: governance_health must be an object")
        return
    required_gate_ids = sorted(
        {
            str(gate_id)
            for passport in passport_entries
            for gate_id in passport.get("required_gates", [])
        }
    )
    if governance_health.get("passport_count") != len(passport_entries):
        errors.append(f"{label}: governance_health.passport_count must match passports")
    if governance_health.get("required_gate_template_count") != len(required_gate_ids):
        errors.append(f"{label}: governance_health.required_gate_template_count must match passport gates")
    if governance_health.get("unresolved_gate_count") != 0:
        errors.append(f"{label}: governance_health.unresolved_gate_count must be zero")
    if governance_health.get("unresolved_gate_ids") != []:
        errors.append(f"{label}: governance_health.unresolved_gate_ids must be empty")
    if governance_health.get("resolved_gate_template_count") != runtime_health.get("resolved_gate_template_count"):
        errors.append(f"{label}: governance_health.resolved_gate_template_count must match runtime projection")
    if governance_health.get("operator_view_hides_internal_gate_ids") is not True:
        errors.append(f"{label}: operator_view_hides_internal_gate_ids must be true")
    if governance_health.get("operator_view_hides_schema_refs") is not True:
        errors.append(f"{label}: operator_view_hides_schema_refs must be true")


def _validate_validators(dashboard: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = dashboard.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, dict)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _status_counts(passports: list[dict[str, Any]]) -> dict[str, int]:
    return {
        status: sum(1 for passport in passports if passport.get("operator_status") == status)
        for status in STATUS_ORDER
    }


def _list_of_objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse capability passport dashboard validation arguments."""

    parser = argparse.ArgumentParser(description="Validate capability passport dashboard.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--dashboard", default=str(DEFAULT_DASHBOARD))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for dashboard validation."""

    args = parse_args(argv)
    validation = validate_capability_passport_dashboard(
        schema_path=Path(args.schema),
        dashboard_path=Path(args.dashboard),
    )
    write_capability_passport_dashboard_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("CAPABILITY PASSPORT DASHBOARD VALID")
    else:
        print(f"CAPABILITY PASSPORT DASHBOARD INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
