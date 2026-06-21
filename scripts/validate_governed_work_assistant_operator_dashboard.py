#!/usr/bin/env python3
"""Validate the Governed Work Assistant operator dashboard projection.

Purpose: keep the operator-facing dashboard fixture schema-backed, read-only,
and explicitly no-effect before any route or UI is admitted.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402

DEFAULT_DASHBOARD = REPO_ROOT / "examples" / "governed_work_assistant_operator_dashboard.json"
DEFAULT_SCHEMA = REPO_ROOT / "docs" / "contracts" / "governed_work_assistant_operator_dashboard.schema.json"

FALSE_EFFECT_BOUNDARY_FIELDS = frozenset(
    {
        "live_connector_execution_allowed",
        "mailbox_read_allowed",
        "mailbox_mutation_allowed",
        "external_send_allowed",
        "calendar_write_allowed",
        "repository_write_allowed",
        "worker_dispatch_allowed",
        "live_receipt_append_allowed",
        "production_readiness_claim_allowed",
        "customer_readiness_claim_allowed",
        "autonomous_execution_authority_allowed",
    }
)
REQUIRED_PANEL_IDS = frozenset(
    {
        "product_identity",
        "assistant_readiness",
        "skill_catalog",
        "blocked_actions",
        "draft_preview",
        "approval_preview",
        "receipt_trail",
        "closure_evidence",
        "no_effect_boundary",
    }
)


@dataclass(frozen=True, slots=True)
class GovernedWorkAssistantDashboardValidation:
    valid: bool
    dashboard_path: str
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        rendered = asdict(self)
        rendered["errors"] = list(self.errors)
        return rendered


def validate_dashboard_projection(
    *,
    dashboard_path: Path = DEFAULT_DASHBOARD,
    schema_path: Path = DEFAULT_SCHEMA,
) -> GovernedWorkAssistantDashboardValidation:
    errors: list[str] = []
    schema = _load_json_object(schema_path, "dashboard schema", errors)
    dashboard = _load_json_object(dashboard_path, "dashboard fixture", errors)
    if schema and dashboard:
        errors.extend(_validate_schema_instance(schema, dashboard))
        errors.extend(_validate_semantics(dashboard))
    return GovernedWorkAssistantDashboardValidation(
        valid=not errors,
        dashboard_path=_path_label(dashboard_path),
        errors=tuple(errors),
    )


def _validate_semantics(dashboard: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if dashboard.get("product_name") != "Governed Work Assistant Demo v0":
        errors.append("product_name must be Governed Work Assistant Demo v0")
    if dashboard.get("legacy_internal_pilot_id") != "governed_team_assistant_pilot_v0":
        errors.append("legacy_internal_pilot_id must preserve governed_team_assistant_pilot_v0")
    if dashboard.get("read_only") is not True:
        errors.append("read_only must be true")
    if dashboard.get("fixture_backed") is not True:
        errors.append("fixture_backed must be true")

    effect_boundary = _mapping(dashboard.get("effect_boundary"))
    for field in sorted(FALSE_EFFECT_BOUNDARY_FIELDS):
        if effect_boundary.get(field) is not False:
            errors.append(f"effect_boundary.{field} must be false")

    panels = dashboard.get("panels")
    if not isinstance(panels, list):
        errors.append("panels must be a list")
        return tuple(errors)
    panel_ids: set[str] = set()
    for index, panel in enumerate(panels):
        payload = _mapping(panel)
        panel_id = payload.get("panel_id")
        if isinstance(panel_id, str):
            panel_ids.add(panel_id)
        if payload.get("read_only") is not True:
            errors.append(f"panels[{index}].read_only must be true")
        if payload.get("effect_allowed") is not False:
            errors.append(f"panels[{index}].effect_allowed must be false")
        if payload.get("visible") is not True:
            errors.append(f"panels[{index}].visible must be true")
    missing = sorted(REQUIRED_PANEL_IDS - panel_ids)
    if missing:
        errors.append(f"missing dashboard panels: {', '.join(missing)}")

    blocked_claims = set(_string_list(dashboard.get("blocked_claims")))
    for required in (
        "live_connector_execution",
        "external_send",
        "repository_write",
        "worker_dispatch",
        "live_receipt_append",
        "production_readiness",
        "customer_readiness",
        "autonomous_execution_authority",
    ):
        if required not in blocked_claims:
            errors.append(f"blocked_claims must include {required}")
    return tuple(errors)


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing {label}: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"invalid {label} JSON at {_path_label(path)}: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _path_label(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    args = parser.parse_args()
    result = validate_dashboard_projection(dashboard_path=args.dashboard, schema_path=args.schema)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"OK: {_path_label(args.dashboard)}")
    else:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
