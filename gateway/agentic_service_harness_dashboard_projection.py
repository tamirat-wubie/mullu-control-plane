"""Read-only Agentic Service Harness dashboard projection.

Purpose: turn the checked-in dashboard data contract into a compact operator
projection and static HTML without admitting routes, controls, adapters, writes,
or terminal closure.
Governance scope: observation and presentation only.
Invariants:
  - Source contract must remain read-only and Foundation Mode.
  - Dashboard implementation, route admission, mutation endpoints, adapter
    execution, runtime writes, and receipt append remain false.
  - Only the ``read_only`` action class is accepted.
  - HTML contains no forms, buttons, action links, or mutation controls.
  - All untrusted text is HTML-escaped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_CONTRACT_PATH = (
    REPO_ROOT / "examples" / "agentic_service_harness_dashboard_data_contract.foundation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_dashboard_data_contract"
EXPECTED_DECISION = "READ_ONLY_DASHBOARD_DATA_CONTRACT_ACCEPTED"

_REQUIRED_FALSE_SCOPE_FLAGS = (
    "dashboard_implemented",
    "ui_created",
    "route_admitted",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "adapter_executed",
    "runtime_state_write_enabled",
    "receipt_store_append_enabled",
    "secret_values_serialized",
)
_REQUIRED_FALSE_CONTRACT_FLAGS = (
    "polling_enabled",
    "subscription_enabled",
    "route_registered",
    "mutation_controls_allowed",
)
_REQUIRED_FALSE_WIDGET_FLAGS = (
    "ui_component_created",
    "action_links_allowed",
    "mutation_controls_allowed",
    "route_admitted",
)


class DashboardProjectionError(ValueError):
    """Raised when a dashboard contract attempts to cross the read-only boundary."""


def load_foundation_dashboard_contract(
    path: Path = DEFAULT_DASHBOARD_CONTRACT_PATH,
) -> dict[str, Any]:
    """Load one checked-in dashboard contract as a JSON object."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DashboardProjectionError(f"dashboard contract not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DashboardProjectionError(f"dashboard contract is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DashboardProjectionError("dashboard contract must be a JSON object")
    return payload


def build_agentic_service_harness_dashboard_projection(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a bounded operator projection from a validated dashboard contract."""
    _require_equal(contract, "report_id", EXPECTED_REPORT_ID)

    scope = _require_mapping(contract, "scope")
    data_contract = _require_mapping(contract, "data_contract")
    _require_equal(data_contract, "decision", EXPECTED_DECISION, prefix="data_contract.")
    _require_true(scope, "read_only", prefix="scope.")
    for field_name in _REQUIRED_FALSE_SCOPE_FLAGS:
        _require_false(scope, field_name, prefix="scope.")
    for field_name in _REQUIRED_FALSE_CONTRACT_FLAGS:
        _require_false(data_contract, field_name, prefix="data_contract.")
    _require_true(data_contract, "read_only", prefix="data_contract.")
    _require_true(
        data_contract,
        "approval_required_for_effects",
        prefix="data_contract.",
    )

    allowed_action_classes = _string_sequence(
        data_contract.get("allowed_action_classes"),
        field_name="data_contract.allowed_action_classes",
    )
    if allowed_action_classes != ("read_only",):
        raise DashboardProjectionError("allowed action classes must be exactly read_only")

    blocked_effects = _string_sequence(
        data_contract.get("forbidden_action_classes"),
        field_name="data_contract.forbidden_action_classes",
    )
    blocked_reasons = _string_sequence(
        data_contract.get("blocked_reason_refs"),
        field_name="data_contract.blocked_reason_refs",
    )
    required_gates = _string_sequence(
        data_contract.get("required_gate_refs"),
        field_name="data_contract.required_gate_refs",
    )
    if not blocked_effects or not blocked_reasons or not required_gates:
        raise DashboardProjectionError("blocked effects, reasons, and gates must be present")

    widgets_value = contract.get("widgets")
    if not isinstance(widgets_value, list) or not widgets_value:
        raise DashboardProjectionError("widgets must be a non-empty list")

    widgets: list[dict[str, Any]] = []
    seen_widget_ids: set[str] = set()
    for index, raw_widget in enumerate(widgets_value):
        if not isinstance(raw_widget, Mapping):
            raise DashboardProjectionError(f"widgets[{index}] must be an object")
        widget_id = _non_empty_text(
            raw_widget.get("widget_id"),
            f"widgets[{index}].widget_id",
        )
        if widget_id in seen_widget_ids:
            raise DashboardProjectionError(f"duplicate widget_id: {widget_id}")
        seen_widget_ids.add(widget_id)
        _require_true(raw_widget, "read_only", prefix=f"widgets[{index}].")
        for field_name in _REQUIRED_FALSE_WIDGET_FLAGS:
            _require_false(raw_widget, field_name, prefix=f"widgets[{index}].")
        widgets.append(
            {
                "widget_id": widget_id,
                "title": _non_empty_text(
                    raw_widget.get("title"),
                    f"widgets[{index}].title",
                ),
                "source_collection": _non_empty_text(
                    raw_widget.get("source_collection"),
                    f"widgets[{index}].source_collection",
                ),
                "required_fields": list(
                    _string_sequence(
                        raw_widget.get("required_fields"),
                        field_name=f"widgets[{index}].required_fields",
                    )
                ),
                "empty_state": _non_empty_text(
                    raw_widget.get("empty_state"),
                    f"widgets[{index}].empty_state",
                ),
                "evidence_refs": list(
                    _string_sequence(
                        raw_widget.get("evidence_refs"),
                        field_name=f"widgets[{index}].evidence_refs",
                    )
                ),
                "status": "read_only_ready",
                "read_only": True,
                "action_controls_present": False,
            }
        )

    return {
        "projection_id": "agentic-service-harness-dashboard-projection-v0",
        "title": "Mullu Governed Operator Dashboard",
        "lifecycle_stage": "internal_alpha_foundation_mode",
        "source_report_id": EXPECTED_REPORT_ID,
        "source_decision": EXPECTED_DECISION,
        "read_only": True,
        "no_effect": True,
        "action_controls_present": False,
        "route_registration_requested": False,
        "runtime_authority_granted": False,
        "approval_required_for_effects": True,
        "widget_count": len(widgets),
        "widgets": widgets,
        "blocked_effects": list(blocked_effects),
        "blocked_reason_refs": list(blocked_reasons),
        "required_gate_refs": list(required_gates),
        "next_action": (
            "Review readiness, approval, receipt, and workspace evidence; "
            "do not treat preview or CI success as execution authority."
        ),
    }


def render_agentic_service_harness_dashboard_html(projection: Mapping[str, Any]) -> str:
    """Render static, escaped HTML for the read-only operator projection."""
    if projection.get("read_only") is not True or projection.get("no_effect") is not True:
        raise DashboardProjectionError(
            "dashboard projection must remain read-only and no-effect"
        )
    if projection.get("action_controls_present") is not False:
        raise DashboardProjectionError(
            "dashboard projection must not contain action controls"
        )

    widgets_value = projection.get("widgets")
    if not isinstance(widgets_value, list):
        raise DashboardProjectionError("projection widgets must be a list")

    cards: list[str] = []
    for index, widget in enumerate(widgets_value):
        if not isinstance(widget, Mapping):
            raise DashboardProjectionError(
                f"projection widgets[{index}] must be an object"
            )
        if widget.get("read_only") is not True:
            raise DashboardProjectionError(
                f"projection widgets[{index}].read_only must be true"
            )
        if widget.get("action_controls_present") is not False:
            raise DashboardProjectionError(
                f"projection widgets[{index}].action_controls_present must be false"
            )
        evidence_refs = widget.get("evidence_refs", ())
        required_fields = widget.get("required_fields", ())
        if not isinstance(evidence_refs, Sequence) or isinstance(
            evidence_refs,
            (str, bytes),
        ):
            raise DashboardProjectionError(
                f"projection widgets[{index}].evidence_refs invalid"
            )
        if not isinstance(required_fields, Sequence) or isinstance(
            required_fields,
            (str, bytes),
        ):
            raise DashboardProjectionError(
                f"projection widgets[{index}].required_fields invalid"
            )
        cards.append(
            "<article class=\"card\">"
            f"<h2>{escape(str(widget.get('title', '')))}</h2>"
            f"<p class=\"status\">{escape(str(widget.get('status', 'blocked')))}</p>"
            f"<p>{escape(str(widget.get('empty_state', '')))}</p>"
            f"<p><strong>Source:</strong> {escape(str(widget.get('source_collection', '')))}</p>"
            f"<p><strong>Required fields:</strong> {escape(', '.join(str(item) for item in required_fields))}</p>"
            f"<p><strong>Evidence:</strong> {escape(', '.join(str(item) for item in evidence_refs))}</p>"
            "</article>"
        )

    blocked_effects = projection.get("blocked_effects", ())
    blocked_reasons = projection.get("blocked_reason_refs", ())
    if not isinstance(blocked_effects, Sequence) or isinstance(
        blocked_effects,
        (str, bytes),
    ):
        raise DashboardProjectionError("blocked_effects must be a sequence")
    if not isinstance(blocked_reasons, Sequence) or isinstance(
        blocked_reasons,
        (str, bytes),
    ):
        raise DashboardProjectionError("blocked_reason_refs must be a sequence")

    blocked_items = "".join(
        f"<li>{escape(str(item))}</li>" for item in blocked_effects
    )
    reason_items = "".join(
        f"<li>{escape(str(item))}</li>" for item in blocked_reasons
    )
    cards_html = "\n".join(cards)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(str(projection.get('title', 'Mullu Operator Dashboard')))}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; background: #f7f8fa; }}
    header, section {{ max-width: 1200px; margin: 0 auto 24px; }}
    .banner {{ border: 1px solid #9aa4b2; background: #fff; padding: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }}
    .card {{ background: #fff; border: 1px solid #d8dee4; padding: 16px; }}
    .status {{ font-weight: 700; }}
    code {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header class="banner">
    <h1>{escape(str(projection.get('title', 'Mullu Operator Dashboard')))}</h1>
    <p>Foundation Mode · Internal Alpha · Read-only · No effect</p>
    <p>{escape(str(projection.get('next_action', '')))}</p>
  </header>
  <section>
    <h2>Read-only evidence panels</h2>
    <div class="grid">{cards_html}</div>
  </section>
  <section class="banner">
    <h2>Blocked effects</h2>
    <ul>{blocked_items}</ul>
    <h2>Why they remain blocked</h2>
    <ul>{reason_items}</ul>
  </section>
</body>
</html>"""


def _require_mapping(container: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = container.get(field_name)
    if not isinstance(value, Mapping):
        raise DashboardProjectionError(f"{field_name} must be an object")
    return value


def _require_equal(
    container: Mapping[str, Any],
    field_name: str,
    expected: Any,
    *,
    prefix: str = "",
) -> None:
    if container.get(field_name) != expected:
        raise DashboardProjectionError(
            f"{prefix}{field_name} must equal {expected!r}"
        )


def _require_true(
    container: Mapping[str, Any],
    field_name: str,
    *,
    prefix: str = "",
) -> None:
    if container.get(field_name) is not True:
        raise DashboardProjectionError(f"{prefix}{field_name} must be true")


def _require_false(
    container: Mapping[str, Any],
    field_name: str,
    *,
    prefix: str = "",
) -> None:
    if container.get(field_name) is not False:
        raise DashboardProjectionError(f"{prefix}{field_name} must be false")


def _non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DashboardProjectionError(
            f"{field_name} must be exact non-empty text"
        )
    return value


def _string_sequence(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DashboardProjectionError(f"{field_name} must be a sequence")
    output: list[str] = []
    for index, item in enumerate(value):
        output.append(_non_empty_text(item, f"{field_name}[{index}]"))
    return tuple(output)
