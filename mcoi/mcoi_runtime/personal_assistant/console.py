"""Purpose: read-only console model for the governed personal assistant.
Governance scope: user-facing assistant status, task, approval, receipt,
skill, memory, and TeamOps panels without connector or execution authority.
Dependencies: personal-assistant registry, approval queue, and memory ledger.
Invariants:
  - Console construction never executes skills, connectors, memory writes, or
    approval actions.
  - Raw private payloads and secret-like values are rejected before rendering.
  - HTML output escapes all operator-visible values.
"""

from __future__ import annotations

from html import escape
import re
from typing import Any, Mapping, Sequence

from .approval import PersonalAssistantApprovalQueue
from .contracts import PersonalAssistantInvariantError
from .memory import PersonalAssistantMemoryObservationLedger
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


_MAX_PANEL_ITEMS = 25
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_RAW_PRIVATE_FIELD_FRAGMENTS = (
    "raw",
    "body",
    "payload",
    "secret",
    "token",
    "credential",
    "private_key",
    "authorization",
    "cookie",
    "chat_log",
    "transcript",
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "chat_log_projection",
        "body_projection",
    }
)
_BLOCKED_ACTIONS = (
    "send_email",
    "delete_email",
    "archive_email",
    "forward_email",
    "label_large_batch",
    "create_calendar_event",
    "move_calendar_event",
    "cancel_calendar_event",
    "invite_people",
    "message_person",
    "store_contact",
    "export_contact_list",
    "pay_invoice",
    "publish_public_post",
    "deploy_service",
    "mutate_connector_state",
    "write_system_of_record",
    "activate_live_nested_mind",
)
_EFFECT_BOUNDARY = {
    "execution_allowed": False,
    "live_connector_execution_allowed": False,
    "mailbox_read_allowed": False,
    "mailbox_mutation_allowed": False,
    "external_send_allowed": False,
    "calendar_write_allowed": False,
    "task_write_allowed": False,
    "memory_write_allowed": False,
    "nested_mind_live_activation_allowed": False,
    "deployment_mutation_allowed": False,
    "public_readiness_claim_allowed": False,
}


def build_personal_assistant_console_read_model(
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
    approval_queue: PersonalAssistantApprovalQueue | None = None,
    memory_ledger: PersonalAssistantMemoryObservationLedger | None = None,
    recent_requests: Sequence[Mapping[str, Any]] = (),
    task_items: Sequence[Mapping[str, Any]] = (),
    receipts: Sequence[Mapping[str, Any]] = (),
    teamops_plans: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build the personal-assistant console read model.

    Input contract: callers may pass sanitized read-model projections for recent
    requests, tasks, receipts, and TeamOps plans.
    Output contract: returns a JSON-ready read-only console payload.
    Error contract: raises PersonalAssistantInvariantError for missing timestamps,
    malformed panel items, raw private fields, or secret-like values.
    """

    timestamp = _require_text(generated_at, "generated_at")
    skill_registry = registry or load_default_skill_registry()
    skill_model = skill_registry.read_model()
    approval_model = approval_queue.read_model() if approval_queue else _empty_approval_model()
    memory_model = memory_ledger.read_model() if memory_ledger else _empty_memory_model()
    request_rows = _panel_items(recent_requests, "recent_requests")
    task_rows = _panel_items(task_items, "task_items")
    receipt_rows = _panel_items(receipts, "receipts")
    teamops_rows = _panel_items(teamops_plans, "teamops_plans")
    return {
        "console_id": "personal_assistant_console_foundation",
        "status": "foundation_read_only",
        "solver_outcome": "SolvedVerified",
        "generated_at": timestamp,
        "governed": True,
        "sections": {
            "chat": {"item_count": len(request_rows), "execution_allowed": False},
            "tasks": {"item_count": len(task_rows), "task_write_allowed": False},
            "approvals": {
                "item_count": approval_model["approval_count"],
                "execution_allowed": approval_model["execution_allowed"],
            },
            "receipts": {"item_count": len(receipt_rows), "receipt_required": True},
            "skills": {"item_count": skill_model["skill_count"], "registry_loaded": True},
            "memory": {
                "item_count": memory_model["candidate_count"],
                "live_memory_write_allowed": False,
            },
            "teamops": {"item_count": len(teamops_rows), "live_probe_allowed": False},
        },
        "chat": {
            "recent_requests": request_rows,
            "ask_clarification_allowed": True,
            "draft_allowed": True,
            "execution_allowed": False,
            "external_actions_allowed": False,
        },
        "tasks": {
            "items": task_rows,
            "task_write_allowed": False,
            "system_of_record_write_allowed": False,
        },
        "approval_queue": approval_model,
        "receipts": {
            "receipt_count": len(receipt_rows),
            "items": receipt_rows,
            "receipt_required_for_actions": True,
        },
        "skills": skill_model,
        "memory": memory_model,
        "teamops": {
            "plans": teamops_rows,
            "live_probe_allowed": False,
            "mailbox_mutation_allowed": False,
            "provider_call_allowed": False,
        },
        "blocked_actions": list(_BLOCKED_ACTIONS),
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "ref_only",
            "chat_log_projection": "none",
        },
        "evidence_refs": ["examples/personal_assistant_skill_registry.json"],
        "receipt_refs": _receipt_refs(receipt_rows, approval_model, memory_model),
    }


def render_personal_assistant_console_html(payload: Mapping[str, Any]) -> str:
    """Render the console read model as escaped HTML."""

    if not isinstance(payload, Mapping):
        raise PersonalAssistantInvariantError("console payload must be a mapping")
    _scan_private_or_secret_payload(payload, path="payload")
    sections = _mapping_value(payload, "sections")
    boundary = _mapping_value(payload, "effect_boundary")
    skills = _mapping_value(payload, "skills")
    approvals = _mapping_value(payload, "approval_queue")
    memory = _mapping_value(payload, "memory")
    receipts = _mapping_value(payload, "receipts")
    teamops = _mapping_value(payload, "teamops")
    metrics = (
        ("Status", payload.get("status", "")),
        ("Skills", sections.get("skills", {}).get("item_count", 0) if isinstance(sections.get("skills"), Mapping) else 0),
        (
            "Approvals",
            sections.get("approvals", {}).get("item_count", 0)
            if isinstance(sections.get("approvals"), Mapping)
            else 0,
        ),
        ("Receipts", receipts.get("receipt_count", 0)),
        ("Memory Candidates", memory.get("candidate_count", 0)),
        ("Execution Allowed", boundary.get("execution_allowed", False)),
    )
    metric_items = "\n".join(
        "<li>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</li>"
        for label, value in metrics
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Personal Assistant Console</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; background: #fafbfc; }}
    header {{ margin-bottom: 20px; }}
    nav {{ display: flex; gap: 14px; margin: 12px 0 18px; }}
    a {{ color: #0f766e; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; padding: 0; }}
    .metrics li {{ list-style: none; border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #ffffff; }}
    .metrics span {{ display: block; color: #57606a; font-size: 12px; }}
    .metrics strong {{ display: block; margin-top: 4px; font-size: 18px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; background: #ffffff; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; font-size: 14px; vertical-align: top; }}
    th {{ background: #f6f8fa; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu Personal Assistant Console</h1>
    <nav>
      <a href="/api/v1/console/personal-assistant">json read model</a>
      <a href="/api/v1/console">full console json</a>
    </nav>
    <p>Generated: <strong>{escape(str(payload.get("generated_at", "")))}</strong></p>
    <ul class="metrics">
      {metric_items}
    </ul>
  </header>
  {_panel_table("Recent Requests", _mapping_value(payload, "chat").get("recent_requests", ()), ("request_id", "summary", "status"))}
  {_panel_table("Task List", _mapping_value(payload, "tasks").get("items", ()), ("task_id", "summary", "status"))}
  {_panel_table("Approval Queue", approvals.get("records", ()), ("approval_id", "approval_state", "risk_level"))}
  {_panel_table("Receipts", receipts.get("items", ()), ("receipt_id", "skill_id", "decision"))}
  {_panel_table("Skill Status", skills.get("skills", ()), ("skill_id", "mode", "risk_level"))}
  {_panel_table("Memory Candidates", memory.get("candidates", ()), ("memory_observation_id", "memory_type", "confidence"))}
  {_panel_table("TeamOps Plans", teamops.get("plans", ()), ("request_id", "skill_id", "status"))}
  {_sequence_table("Blocked Actions", payload.get("blocked_actions", ()))}
</body>
</html>"""


def _empty_approval_model() -> dict[str, Any]:
    return {
        "approval_count": 0,
        "approval_ids": [],
        "state_counts": {"requested": 0, "approved": 0, "rejected": 0, "revised": 0, "blocked": 0},
        "receipt_ids": [],
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "external_send_allowed": False,
        "connector_mutation_allowed": False,
        "system_of_record_write_allowed": False,
        "approval_is_execution": False,
        "records": [],
        "metadata": {
            "foundation_only": True,
            "queue_projection": "read_model",
            "persistence_boundary": "stateless_unless_hosted_store_is_explicitly_bound",
            "live_connector_execution_allowed": False,
            "approval_decision_executes_action": False,
        },
    }


def _empty_memory_model() -> dict[str, Any]:
    return {
        "candidate_count": 0,
        "memory_observation_ids": [],
        "memory_types": [],
        "live_memory_write_allowed": False,
        "nested_mind_live_activation_allowed": False,
        "candidates": [],
    }


def _panel_items(items: Sequence[Mapping[str, Any]], field_name: str) -> list[dict[str, Any]]:
    if not isinstance(items, (list, tuple)):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items[:_MAX_PANEL_ITEMS]):
        if not isinstance(item, Mapping):
            raise PersonalAssistantInvariantError(f"{field_name}[{index}] must be a mapping")
        _scan_private_or_secret_payload(item, path=f"{field_name}[{index}]")
        normalized.append(_json_ready(item))
    return normalized


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _receipt_refs(
    receipt_rows: Sequence[Mapping[str, Any]],
    approval_model: Mapping[str, Any],
    memory_model: Mapping[str, Any],
) -> list[str]:
    refs: list[str] = []
    for row in receipt_rows:
        receipt_id = row.get("receipt_id")
        if isinstance(receipt_id, str) and receipt_id:
            refs.append(receipt_id)
    for record in approval_model.get("records", ()):
        if isinstance(record, Mapping):
            for receipt in record.get("receipts", ()):
                if isinstance(receipt, Mapping) and isinstance(receipt.get("receipt_id"), str):
                    refs.append(str(receipt["receipt_id"]))
    for candidate in memory_model.get("candidates", ()):
        if isinstance(candidate, Mapping):
            receipt = candidate.get("receipt")
            if isinstance(receipt, Mapping) and isinstance(receipt.get("receipt_id"), str):
                refs.append(str(receipt["receipt_id"]))
    return sorted(set(refs))


def _mapping_value(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    child = value.get(key)
    return dict(child) if isinstance(child, Mapping) else {}


def _panel_table(title: str, raw_rows: object, columns: tuple[str, ...]) -> str:
    rows = [dict(row) for row in raw_rows if isinstance(row, Mapping)] if isinstance(raw_rows, (list, tuple)) else []
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{escape(str(_display_cell(row, column)))}</td>" for column in columns)
        + "</tr>"
        for row in rows
    )
    if not body:
        body = f"<tr><td colspan=\"{len(columns)}\">No records</td></tr>"
    header = "".join(f"<th>{escape(column.replace('_', ' ').title())}</th>" for column in columns)
    return f"""
  <section>
    <h2>{escape(title)}</h2>
    <table>
      <thead><tr>{header}</tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _sequence_table(title: str, raw_values: object) -> str:
    values = [str(value) for value in raw_values] if isinstance(raw_values, (list, tuple)) else []
    body = "\n".join(f"<tr><td>{escape(value)}</td></tr>" for value in values)
    if not body:
        body = "<tr><td>No records</td></tr>"
    return f"""
  <section>
    <h2>{escape(title)}</h2>
    <table>
      <thead><tr><th>Action</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _display_cell(row: Mapping[str, Any], column: str) -> object:
    value = row.get(column, "")
    if value:
        return value
    if column == "approval_state":
        packet = row.get("packet")
        return packet.get("approval_state", "") if isinstance(packet, Mapping) else ""
    if column == "risk_level":
        packet = row.get("packet")
        return packet.get("risk_level", "") if isinstance(packet, Mapping) else ""
    if column == "memory_observation_id":
        observation = row.get("observation")
        return observation.get("memory_observation_id", "") if isinstance(observation, Mapping) else ""
    if column in {"memory_type", "confidence"}:
        observation = row.get("observation")
        return observation.get(column, "") if isinstance(observation, Mapping) else ""
    return ""


def _scan_private_or_secret_payload(value: Any, *, path: str) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            lowered = key.lower()
            if (
                lowered not in _ALLOWED_POLICY_FIELD_NAMES
                and any(fragment in lowered for fragment in _RAW_PRIVATE_FIELD_FRAGMENTS)
            ):
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private field is not allowed")
            _scan_private_or_secret_payload(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _scan_private_or_secret_payload(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in _SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                raise PersonalAssistantInvariantError(f"{path}: secret-like value is not allowed")


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    return value
