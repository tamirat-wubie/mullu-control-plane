"""Operator goal intake preview UI.

Purpose: Render a bounded operator-facing goal intake form and redacted plan
    preview without echoing raw goal text or granting execution authority.
Governance scope: user-surface goal admission, plan preview review, and
    explicit preview approval or denial handoff.
Dependencies: standard-library HTML escaping, thread locking, and capability
    plan preview dictionaries produced by gateway.plan.
Invariants:
  - Raw goal text is never echoed after submission.
  - The UI never grants execution authority.
  - Preview fields are rendered from the redacted CapabilityPlanPreview shape.
  - Approval and denial handoffs consume server-side preview records by id.
  - Blocked intake states remain explicit and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from html import escape
from threading import Lock
from typing import Any, Mapping


GOAL_INTAKE_SCHEMA_REF = "urn:mullusi:schema:operator-goal-intake-preview-ui:1"
DEFAULT_GOAL_INTAKE_CHANNEL = "operator_goal_intake"
DEFAULT_GOAL_INTAKE_SENDER_ID = "operator"


@dataclass(frozen=True, slots=True)
class GoalIntakePreviewRecord:
    """Server-side pending preview record.

    Input contract: ``goal`` is the raw submitted goal and must never be
    rendered directly. ``preview`` is the redacted CapabilityPlanPreview dict.
    Output contract: store consumers can reconstruct the governed router
    message only after an explicit approval decision.
    Error contract: construction is pure; validation is performed by callers.
    """

    preview_id: str
    plan_id: str
    tenant_id: str
    identity_id: str
    channel: str
    sender_id: str
    sender_id_hash: str
    goal: str
    goal_hash: str
    preview: dict[str, Any]
    status: str
    created_at: str
    decided_at: str = ""
    decision: str = ""
    decision_reason: str = ""
    handoff_message_id: str = ""
    handoff_response_body: str = ""
    handoff_response_metadata: dict[str, Any] = field(default_factory=dict)


class GoalIntakePreviewStore:
    """Bounded in-memory store for preview approval handoff records."""

    def __init__(self, *, max_records: int = 200) -> None:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        self._max_records = max_records
        self._records: dict[str, GoalIntakePreviewRecord] = {}
        self._order: list[str] = []
        self._lock = Lock()

    def save(self, record: GoalIntakePreviewRecord) -> None:
        """Persist or replace one pending preview record."""
        if not record.preview_id:
            raise ValueError("preview_id is required")
        with self._lock:
            if record.preview_id not in self._records:
                self._order.append(record.preview_id)
            self._records[record.preview_id] = record
            self._evict_excess_locked()

    def get(self, preview_id: str) -> GoalIntakePreviewRecord | None:
        """Return a preview record by id, if present."""
        normalized_preview_id = str(preview_id).strip()
        if not normalized_preview_id:
            return None
        with self._lock:
            return self._records.get(normalized_preview_id)

    def list_records(self) -> tuple[GoalIntakePreviewRecord, ...]:
        """Return preview records in insertion order without raw rendering authority."""
        with self._lock:
            return tuple(
                self._records[preview_id]
                for preview_id in self._order
                if preview_id in self._records
            )

    def decide(
        self,
        preview_id: str,
        *,
        status: str,
        decision: str,
        decided_at: str,
        decision_reason: str = "",
        handoff_message_id: str = "",
        handoff_response_body: str = "",
        handoff_response_metadata: Mapping[str, Any] | None = None,
    ) -> GoalIntakePreviewRecord:
        """Mark one preview decision exactly through this store."""
        normalized_preview_id = str(preview_id).strip()
        if not normalized_preview_id:
            raise KeyError("preview_id is required")
        with self._lock:
            record = self._records.get(normalized_preview_id)
            if record is None:
                raise KeyError(normalized_preview_id)
            updated = replace(
                record,
                status=str(status),
                decision=str(decision),
                decided_at=str(decided_at),
                decision_reason=str(decision_reason),
                handoff_message_id=str(handoff_message_id),
                handoff_response_body=str(handoff_response_body),
                handoff_response_metadata=dict(handoff_response_metadata or {}),
            )
            self._records[normalized_preview_id] = updated
            return updated

    def _evict_excess_locked(self) -> None:
        while len(self._order) > self._max_records:
            evicted = self._order.pop(0)
            self._records.pop(evicted, None)


def build_goal_intake_read_model(
    *,
    preview_id: str = "",
    tenant_id: str = "",
    identity_id: str = "",
    channel: str = DEFAULT_GOAL_INTAKE_CHANNEL,
    sender_id_present: bool = False,
    sender_id_hash: str = "",
    status: str = "idle",
    goal_hash: str = "",
    preview: Mapping[str, Any] | None = None,
    decision: str = "",
    decision_reason: str = "",
    handoff_message_id: str = "",
    handoff_response_body: str = "",
    handoff_response_metadata: Mapping[str, Any] | None = None,
    error_code: str = "",
    error_message: str = "",
) -> dict[str, Any]:
    """Build a bounded goal-intake UI read model.

    Input contract: caller provides already-normalized identifiers and an
    optional redacted capability plan preview.
    Output contract: the returned model is JSON-safe and contains no raw goal.
    Error contract: total for string-like values and mapping previews.
    """
    preview_mapping = dict(preview) if isinstance(preview, Mapping) else {}
    handoff_mapping = (
        dict(handoff_response_metadata)
        if isinstance(handoff_response_metadata, Mapping)
        else {}
    )
    normalized_preview_id = str(preview_id or preview_mapping.get("preview_id", ""))
    return {
        "schema_ref": GOAL_INTAKE_SCHEMA_REF,
        "preview_id": normalized_preview_id,
        "tenant_id": str(tenant_id),
        "identity_id": str(identity_id),
        "channel": str(channel or DEFAULT_GOAL_INTAKE_CHANNEL),
        "sender_id_present": bool(sender_id_present),
        "sender_id_hash": str(sender_id_hash),
        "status": str(status),
        "goal_hash": str(goal_hash or preview_mapping.get("goal_hash", "")),
        "preview_generated": bool(preview_mapping),
        "preview": preview_mapping,
        "decision": str(decision),
        "decision_reason": str(decision_reason),
        "handoff_message_id": str(handoff_message_id),
        "handoff_response_body": str(handoff_response_body),
        "handoff_response_metadata": handoff_mapping,
        "error_code": str(error_code),
        "error_message": str(error_message),
        "raw_goal_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def render_goal_intake_html(read_model: Mapping[str, Any]) -> str:
    """Render the goal-intake read model as preview-only HTML."""
    preview = read_model.get("preview")
    if not isinstance(preview, Mapping):
        preview = {}
    status_panel = _status_panel(read_model)
    preview_panel = _preview_panel(read_model, preview)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Goal Intake</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f7f8fa; color: #1b1f24; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    p {{ margin: 0 0 20px; color: #57606a; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 24px; }}
    a {{ color: #0969da; }}
    form {{ display: grid; gap: 14px; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 18px; margin: 0 0 24px; }}
    label {{ display: grid; gap: 6px; font-weight: 700; font-size: 13px; }}
    input, textarea {{ box-sizing: border-box; width: 100%; border: 1px solid #d0d7de; border-radius: 6px; padding: 10px 12px; font: inherit; background: #fff; color: #1b1f24; }}
    textarea {{ min-height: 132px; resize: vertical; }}
    button {{ width: fit-content; border: 1px solid #1f883d; border-radius: 6px; background: #1f883d; color: #fff; font-weight: 700; padding: 10px 14px; cursor: pointer; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 0 0 24px; }}
    .metric {{ display: flex; justify-content: space-between; gap: 16px; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }}
    .metric span {{ color: #57606a; }}
    .panel {{ background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 18px; margin: 0 0 24px; }}
    .blocked {{ border-color: #cf222e; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; margin: 0 0 18px; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; }}
    th {{ background: #eef1f4; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>Mullu Goal Intake</h1>
  <p>Preview-only governed goal admission for plan review.</p>
  <nav>
    <a href="/operator/current-task">current task</a>
    <a href="/operator/receipts">receipt viewer</a>
    <a href="/operator/universal-actions">universal actions</a>
    <a href="/gateway/status">gateway status</a>
  </nav>
  <form method="post" action="/operator/goal-intake/preview">
    <label>Tenant ID
      <input name="tenant_id" value="{escape(_display_value(read_model.get("tenant_id", "")))}" required>
    </label>
    <label>Identity ID
      <input name="identity_id" value="{escape(_display_value(read_model.get("identity_id", "")))}" required>
    </label>
    <label>Channel
      <input name="channel" value="{escape(_display_value(read_model.get("channel", DEFAULT_GOAL_INTAKE_CHANNEL)))}" required>
    </label>
    <label>Sender ID
      <input name="sender_id" value="">
    </label>
    <label>Goal
      <textarea name="goal" required maxlength="8000"></textarea>
    </label>
    <button type="submit">Preview Plan</button>
  </form>
  {status_panel}
  {preview_panel}
</main>
</body>
</html>"""


def _status_panel(read_model: Mapping[str, Any]) -> str:
    metrics = (
        ("Status", read_model.get("status", "idle")),
        ("Goal Hash", read_model.get("goal_hash", "")),
        ("Sender Present", read_model.get("sender_id_present", False)),
        ("Raw Goal Exposed", read_model.get("raw_goal_exposed", False)),
        ("Execution Allowed", read_model.get("execution_allowed", False)),
        ("Write Allowed", read_model.get("write_allowed", False)),
        ("Decision", read_model.get("decision", "")),
        ("Decision Reason", read_model.get("decision_reason", "")),
    )
    metric_items = "".join(
        "<div class=\"metric\">"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(_display_value(value))}</strong>"
        "</div>"
        for label, value in metrics
    )
    error_code = _display_value(read_model.get("error_code", ""))
    if not error_code:
        return f'<section class="grid">{metric_items}</section>'
    error_message = _display_value(read_model.get("error_message", ""))
    return (
        '<section class="panel blocked">'
        "<h2>Intake Blocked</h2>"
        f"<p>{escape(error_code)}: {escape(error_message)}</p>"
        "</section>"
        f'<section class="grid">{metric_items}</section>'
    )


def _preview_panel(read_model: Mapping[str, Any], preview: Mapping[str, Any]) -> str:
    if not preview:
        return '<section class="panel"><h2>Plan Preview</h2><p>No preview generated.</p></section>'
    budget = preview.get("budget")
    if not isinstance(budget, Mapping):
        budget = {}
    steps = _mapping_list(preview.get("steps"))
    tools = _mapping_list(preview.get("tools"))
    metrics = (
        ("Preview ID", preview.get("preview_id", "")),
        ("Plan ID", preview.get("plan_id", "")),
        ("Risk", preview.get("risk_tier", "")),
        ("Steps", preview.get("step_count", 0)),
        ("Approval Required", preview.get("approval_required", False)),
        ("Execution Allowed", preview.get("execution_allowed", False)),
        ("Budget Gate", budget.get("budget_gate", "")),
        ("Budget Required", budget.get("budget_required", False)),
    )
    metric_items = "".join(
        "<div class=\"metric\">"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(_display_value(value))}</strong>"
        "</div>"
        for label, value in metrics
    )
    step_rows = _html_rows(
        steps,
        ("step_id", "capability_id", "depends_on", "param_names", "params_hash"),
        empty_label="No plan steps",
    )
    tool_rows = _html_rows(
        tools,
        (
            "step_id",
            "capability_id",
            "tool_name",
            "tool_type",
            "permission_state",
            "budget_required",
            "execution_allowed",
        ),
        empty_label="No tools",
    )
    controls = _decision_controls(read_model)
    handoff = _handoff_panel(read_model)
    return (
        '<section class="grid">'
        f"{metric_items}"
        "</section>"
        '<section class="panel">'
        "<h2>Plan Steps</h2>"
        "<table><thead><tr>"
        "<th>step_id</th><th>capability_id</th><th>depends_on</th>"
        "<th>param_names</th><th>params_hash</th>"
        f"</tr></thead><tbody>{step_rows}</tbody></table>"
        "<h2>Tools</h2>"
        "<table><thead><tr>"
        "<th>step_id</th><th>capability_id</th><th>tool_name</th>"
        "<th>tool_type</th><th>permission_state</th>"
        "<th>budget_required</th><th>execution_allowed</th>"
        f"</tr></thead><tbody>{tool_rows}</tbody></table>"
        f"{controls}"
        f"{handoff}"
        "</section>"
    )


def _decision_controls(read_model: Mapping[str, Any]) -> str:
    if read_model.get("status") != "preview_ready":
        return ""
    preview_id = _display_value(read_model.get("preview_id", ""))
    if not preview_id:
        return ""
    return (
        '<div class="grid">'
        '<form method="post" action="/operator/goal-intake/approve">'
        f'<input type="hidden" name="preview_id" value="{escape(preview_id)}">'
        '<button type="submit">Approve Handoff</button>'
        "</form>"
        '<form method="post" action="/operator/goal-intake/deny">'
        f'<input type="hidden" name="preview_id" value="{escape(preview_id)}">'
        '<button type="submit">Deny Preview</button>'
        "</form>"
        "</div>"
    )


def _handoff_panel(read_model: Mapping[str, Any]) -> str:
    metadata = read_model.get("handoff_response_metadata")
    if not isinstance(metadata, Mapping) or not metadata:
        return ""
    rows = _html_rows(
        [
            {"field": key, "value": value}
            for key, value in sorted(metadata.items())
            if key in {
                "error",
                "plan_id",
                "plan_error",
                "plan_failure_witness_id",
                "approval_required",
                "request_id",
                "command_id",
                "risk_tier",
                "delivery_status",
            }
        ],
        ("field", "value"),
        empty_label="No handoff metadata",
    )
    body = _display_value(read_model.get("handoff_response_body", ""))
    return (
        "<h2>Handoff Result</h2>"
        f"<p>{escape(body)}</p>"
        "<table><thead><tr><th>field</th><th>value</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _html_rows(
    records: list[Mapping[str, Any]],
    columns: tuple[str, ...],
    *,
    empty_label: str,
) -> str:
    if not records:
        return f'<tr><td colspan="{len(columns)}">{escape(empty_label)}</td></tr>'
    return "\n".join(
        "<tr>"
        + "".join(
            f"<td>{escape(_display_value(record.get(column, '')))}</td>"
            for column in columns
        )
        + "</tr>"
        for record in records
    )


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)
