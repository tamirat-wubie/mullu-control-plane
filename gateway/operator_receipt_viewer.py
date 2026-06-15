"""Operator receipt and current-task read models.

Purpose: Build bounded operator visibility for command receipts and active
    task state without exposing raw command payload text.
Governance scope: gateway command receipt visibility, task-state projection,
    and read-only operator evidence review.
Dependencies: gateway command spine and universal action proof reconstruction.
Invariants:
  - Raw command payload text is never exposed.
  - Read models never mutate the command ledger.
  - Receipt rows expose identifiers, hashes, states, and evidence references.
  - Limit and offset inputs are bounded before ledger scans.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from html import escape
import json
from typing import Any, Mapping

from gateway.command_spine import CommandEnvelope, CommandEvent, CommandState
from mcoi_runtime.app.governed_execution import universal_command_proof_view


RECEIPT_VIEWER_SCHEMA_REF = "urn:mullusi:schema:operator-receipt-viewer-read-model:1"
CURRENT_TASK_SCHEMA_REF = "urn:mullusi:schema:current-task-read-model:1"

_MAX_SCAN_LIMIT = 1000
_MAX_PAGE_LIMIT = 500

_INTERPRETATION_RECEIPT_FIELDS = (
    "receipt_id",
    "schema_ref",
    "request_id",
    "adapter",
    "tenant_id",
    "actor_id",
    "raw_message_hash",
    "normalized_text_hash",
    "interpreted_intent",
    "confidence",
    "created_at",
)

_WAITING_STATES = frozenset(
    {
        CommandState.APPROVAL_CHAIN_PENDING,
        CommandState.PENDING_APPROVAL,
        CommandState.PENDING_EFFECT_APPROVAL,
    }
)
_BLOCKED_STATES = frozenset({CommandState.DENIED, CommandState.SIMULATION_BLOCKED})
_REVIEW_STATES = frozenset(
    {
        CommandState.REQUIRES_REVIEW,
        CommandState.OBLIGATIONS_OPENED,
        CommandState.OBLIGATIONS_ESCALATED,
    }
)
_COMPLETED_STATES = frozenset(
    {
        CommandState.TERMINALLY_CERTIFIED,
        CommandState.OBLIGATIONS_SATISFIED,
        CommandState.RESPONSE_EVIDENCE_CLOSED,
        CommandState.MEMORY_PROMOTED,
        CommandState.LEARNING_DECIDED,
        CommandState.WITNESSED,
        CommandState.RESPONDED,
        CommandState.ANCHORED,
    }
)
_ACTIVE_STATES = frozenset(
    {
        CommandState.APPROVAL_CHAIN_SATISFIED,
        CommandState.ALLOWED,
        CommandState.APPROVED,
        CommandState.BUDGET_RESERVED,
        CommandState.EFFECT_PLANNED,
        CommandState.FRACTURE_TESTED,
        CommandState.SIMULATED,
        CommandState.DISPATCHED,
        CommandState.EFFECT_OBSERVED,
        CommandState.OBSERVED,
        CommandState.VERIFIED,
        CommandState.RECONCILED,
        CommandState.COMMITTED,
    }
)
_TASK_STATUSES = (
    "received",
    "active",
    "waiting_for_approval",
    "requires_review",
    "blocked",
    "completed",
)


def valid_task_statuses() -> tuple[str, ...]:
    """Return accepted current-task status filter values."""
    return _TASK_STATUSES


def task_status_for_state(
    state: CommandState,
    *,
    terminal_certificate_present: bool = False,
) -> str:
    """Map a command lifecycle state to an operator task status."""
    if terminal_certificate_present or state in _COMPLETED_STATES:
        return "completed"
    if state in _BLOCKED_STATES:
        return "blocked"
    if state in _WAITING_STATES:
        return "waiting_for_approval"
    if state in _REVIEW_STATES:
        return "requires_review"
    if state in _ACTIVE_STATES:
        return "active"
    return "received"


def build_operator_receipt_viewer_read_model(
    command_ledger: Any,
    *,
    tenant_id: str = "",
    command_id: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Build a bounded command receipt read model for operator review."""
    bounded_limit = _bounded_limit(limit)
    bounded_offset = _bounded_offset(offset)
    commands = _filtered_commands(
        command_ledger,
        tenant_id=tenant_id,
        command_id=command_id,
        limit=bounded_limit,
        offset=bounded_offset,
    )
    rows = [
        _command_receipt_group(command_ledger, command)
        for command in commands["page"]
    ]
    total_receipts = sum(int(row["receipt_count"]) for row in rows)
    return {
        "schema_ref": RECEIPT_VIEWER_SCHEMA_REF,
        "tenant_id_filter": tenant_id,
        "command_id_filter": command_id,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "next_offset": commands["next_offset"],
        "total": commands["total"],
        "count": len(rows),
        "total_receipts": total_receipts,
        "receipt_groups": rows,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def build_current_task_read_model(
    command_ledger: Any,
    *,
    tenant_id: str = "",
    status: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Build a bounded current-task state read model for operator review."""
    normalized_status = status.strip()
    bounded_limit = _bounded_limit(limit)
    bounded_offset = _bounded_offset(offset)
    commands = _filtered_commands(
        command_ledger,
        tenant_id=tenant_id,
        command_id="",
        limit=bounded_limit,
        offset=bounded_offset,
        pre_filter=lambda command: (
            not normalized_status
            or _command_task_status(command_ledger, command) == normalized_status
        ),
    )
    tasks = [
        _current_task_row(command_ledger, command)
        for command in commands["page"]
    ]
    status_counts = _task_status_counts(command_ledger, commands["all"])
    current_task_id = next(
        (
            task["command_id"]
            for task in tasks
            if task["task_status"] != "completed"
        ),
        "",
    )
    return {
        "schema_ref": CURRENT_TASK_SCHEMA_REF,
        "tenant_id_filter": tenant_id,
        "status_filter": normalized_status,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "next_offset": commands["next_offset"],
        "total": commands["total"],
        "count": len(tasks),
        "current_task_id": current_task_id,
        "status_counts": status_counts,
        "tasks": tasks,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def render_operator_receipt_viewer_html(read_model: Mapping[str, Any]) -> str:
    """Render the operator receipt read model as a read-only HTML table."""
    records = _mapping_list(read_model.get("receipt_groups"))
    columns = (
        "command_id",
        "tenant_id",
        "actor_id",
        "source",
        "intent",
        "command_state",
        "task_status",
        "payload_hash",
        "latest_event_hash",
        "event_count",
        "receipt_count",
    )
    rows = _html_rows(records, columns, empty_label="No command receipts")
    metrics = (
        ("Visible", read_model.get("count", 0)),
        ("Total", read_model.get("total", 0)),
        ("Receipts", read_model.get("total_receipts", 0)),
        ("Tenant Filter", read_model.get("tenant_id_filter", "")),
        ("Command Filter", read_model.get("command_id_filter", "")),
    )
    return _operator_table_html(
        title="Mullu Operator Receipt Viewer",
        description="Read-only command receipt groups with bounded evidence references.",
        json_href="/operator/receipts/read-model",
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/current-task", "current task"),
            ("/operator/universal-actions", "universal actions"),
            ("/gateway/status", "gateway status"),
        ),
    )


def render_current_task_html(read_model: Mapping[str, Any]) -> str:
    """Render the current-task read model as a read-only HTML table."""
    records = _mapping_list(read_model.get("tasks"))
    columns = (
        "command_id",
        "tenant_id",
        "actor_id",
        "source",
        "intent",
        "command_state",
        "task_status",
        "waiting_for",
        "next_action",
        "created_at",
        "latest_event_hash",
        "event_count",
        "receipt_count",
    )
    rows = _html_rows(records, columns, empty_label="No current tasks")
    status_counts = read_model.get("status_counts")
    if not isinstance(status_counts, Mapping):
        status_counts = {}
    metrics = (
        ("Visible", read_model.get("count", 0)),
        ("Total", read_model.get("total", 0)),
        ("Current Task", read_model.get("current_task_id", "")),
        ("Active", status_counts.get("active", 0)),
        ("Waiting", status_counts.get("waiting_for_approval", 0)),
        ("Blocked", status_counts.get("blocked", 0)),
    )
    return _operator_table_html(
        title="Mullu Current Task State",
        description="Read-only command task states and next governed operator actions.",
        json_href="/operator/current-task/read-model",
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/receipts", "receipt viewer"),
            ("/operator/universal-actions", "universal actions"),
            ("/gateway/status", "gateway status"),
        ),
    )


def _filtered_commands(
    command_ledger: Any,
    *,
    tenant_id: str,
    command_id: str,
    limit: int,
    offset: int,
    pre_filter: Any | None = None,
) -> dict[str, Any]:
    if command_id:
        command = command_ledger.get(command_id)
        all_commands = [command] if _command_matches(command, tenant_id=tenant_id) else []
    else:
        scan_limit = _bounded_limit(limit + offset, maximum=_MAX_SCAN_LIMIT)
        all_commands = [
            command
            for command in command_ledger.list_commands(
                tenant_id=tenant_id,
                limit=scan_limit,
            )
            if isinstance(command, CommandEnvelope)
        ]
    if pre_filter is not None:
        all_commands = [command for command in all_commands if pre_filter(command)]
    page = all_commands[offset:offset + limit]
    next_offset = offset + len(page)
    return {
        "all": tuple(all_commands),
        "page": tuple(page),
        "total": len(all_commands),
        "next_offset": next_offset if next_offset < len(all_commands) else None,
    }


def _command_matches(command: Any, *, tenant_id: str) -> bool:
    return isinstance(command, CommandEnvelope) and (
        not tenant_id or command.tenant_id == tenant_id
    )


def _command_receipt_group(command_ledger: Any, command: CommandEnvelope) -> dict[str, Any]:
    events = [
        event
        for event in command_ledger.events_for(command.command_id)
        if isinstance(event, CommandEvent)
    ]
    terminal_certificate = command_ledger.terminal_certificate_for(command.command_id)
    receipts = _receipts_for_command(
        command_ledger,
        command,
        events=events,
        terminal_certificate=terminal_certificate,
    )
    latest_event_hash = events[-1].event_hash if events else ""
    task_status = task_status_for_state(
        command.state,
        terminal_certificate_present=terminal_certificate is not None,
    )
    return {
        "command_id": command.command_id,
        "tenant_id": command.tenant_id,
        "actor_id": command.actor_id,
        "source": command.source,
        "intent": command.intent,
        "command_state": command.state.value,
        "task_status": task_status,
        "payload_hash": command.payload_hash,
        "trace_id": command.trace_id,
        "created_at": command.created_at,
        "latest_event_hash": latest_event_hash,
        "event_count": len(events),
        "receipt_count": len(receipts),
        "receipts": receipts,
    }


def _receipts_for_command(
    command_ledger: Any,
    command: CommandEnvelope,
    *,
    events: list[CommandEvent],
    terminal_certificate: Any | None,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    interpretation = _interpretation_receipt(command)
    if interpretation is not None:
        receipts.append(interpretation)
    receipts.extend(_event_receipt(event) for event in events)
    proof = universal_command_proof_view(command_ledger, command.command_id)
    if proof is not None:
        receipts.append(_universal_action_proof_receipt(proof))
    if terminal_certificate is not None:
        receipts.append(_terminal_certificate_receipt(terminal_certificate))
    return receipts


def _interpretation_receipt(command: CommandEnvelope) -> dict[str, Any] | None:
    raw_receipt = command.redacted_payload.get("interpretation_receipt")
    if not isinstance(raw_receipt, Mapping):
        return None
    details = {
        key: _json_safe_value(raw_receipt[key])
        for key in _INTERPRETATION_RECEIPT_FIELDS
        if key in raw_receipt
    }
    receipt_id = str(
        details.get("receipt_id")
        or command.redacted_payload.get("interpretation_receipt_id")
        or f"interpretation:{command.command_id}"
    )
    evidence_refs = {
        "raw_message_hash": str(details.get("raw_message_hash", "")),
        "normalized_text_hash": str(details.get("normalized_text_hash", "")),
        "request_id": str(details.get("request_id", "")),
        "interpreted_intent": str(details.get("interpreted_intent", "")),
    }
    return {
        "receipt_type": "interpretation_receipt",
        "receipt_id": receipt_id,
        "receipt_hash": _stable_hash(details),
        "status": "recorded",
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _event_receipt(event: CommandEvent) -> dict[str, Any]:
    detail = event.detail if isinstance(event.detail, Mapping) else {}
    details = {
        "event_id": event.event_id,
        "previous_state": event.previous_state.value,
        "next_state": event.next_state.value,
        "timestamp": event.timestamp,
        "cause": str(detail.get("cause", "")),
    }
    evidence_refs = {
        "event_hash": event.event_hash,
        "previous_event_hash": event.prev_event_hash,
        "input_hash": event.input_hash,
        "output_hash": event.output_hash,
        "trace_id": event.trace_id,
    }
    return {
        "receipt_type": "command_event",
        "receipt_id": event.event_id,
        "receipt_hash": event.event_hash,
        "status": event.next_state.value,
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _universal_action_proof_receipt(proof: Any) -> dict[str, Any]:
    details = _dataclass_mapping(proof)
    evidence_refs = {
        "proof_hash": str(details.get("proof_hash", "")),
        "trace_ref": str(details.get("trace_ref", "")),
        "admission_receipt_ref": str(details.get("admission_receipt_ref", "")),
        "execution_receipt_ref": str(details.get("execution_receipt_ref", "")),
        "reconciliation_ref": str(details.get("reconciliation_ref", "")),
        "memory_ref": str(details.get("memory_ref", "")),
        "dispatch_ledger_hash": str(details.get("dispatch_ledger_hash", "")),
        "terminal_certificate_id": str(details.get("terminal_certificate_id", "")),
        "learning_admission_id": str(details.get("learning_admission_id", "")),
    }
    status = "blocked" if bool(details.get("blocked", False)) else str(
        details.get("closure_state", "recorded")
    )
    return {
        "receipt_type": "universal_action_proof",
        "receipt_id": str(details.get("proof_hash", "")),
        "receipt_hash": str(details.get("proof_hash", "")),
        "status": status or "recorded",
        "details": _json_safe_value(details),
        "evidence_refs": evidence_refs,
    }


def _terminal_certificate_receipt(certificate: Any) -> dict[str, Any]:
    details = _dataclass_mapping(certificate)
    evidence_refs = {
        "certificate_id": str(details.get("certificate_id", "")),
        "evidence_refs": tuple(details.get("evidence_refs", ())),
        "response_evidence_closure_id": str(
            details.get("response_evidence_closure_id", "")
        ),
        "certificate_hash": str(details.get("certificate_hash", "")),
    }
    return {
        "receipt_type": "terminal_closure_certificate",
        "receipt_id": str(details.get("certificate_id", "")),
        "receipt_hash": str(details.get("certificate_hash", "")),
        "status": str(details.get("disposition", "recorded")),
        "details": _json_safe_value(details),
        "evidence_refs": evidence_refs,
    }


def _current_task_row(command_ledger: Any, command: CommandEnvelope) -> dict[str, Any]:
    events = [
        event
        for event in command_ledger.events_for(command.command_id)
        if isinstance(event, CommandEvent)
    ]
    terminal_certificate = command_ledger.terminal_certificate_for(command.command_id)
    receipts = _receipts_for_command(
        command_ledger,
        command,
        events=events,
        terminal_certificate=terminal_certificate,
    )
    task_status = task_status_for_state(
        command.state,
        terminal_certificate_present=terminal_certificate is not None,
    )
    return {
        "command_id": command.command_id,
        "tenant_id": command.tenant_id,
        "actor_id": command.actor_id,
        "source": command.source,
        "intent": command.intent,
        "command_state": command.state.value,
        "task_status": task_status,
        "task_terminal": task_status == "completed",
        "task_blocked": task_status == "blocked",
        "waiting_for": _waiting_for(command.state),
        "next_action": _next_action(task_status),
        "created_at": command.created_at,
        "trace_id": command.trace_id,
        "latest_event_hash": events[-1].event_hash if events else "",
        "event_count": len(events),
        "receipt_count": len(receipts),
        "evidence_ref_count": _evidence_ref_count(receipts),
    }


def _command_task_status(command_ledger: Any, command: CommandEnvelope) -> str:
    return task_status_for_state(
        command.state,
        terminal_certificate_present=command_ledger.terminal_certificate_for(command.command_id)
        is not None,
    )


def _task_status_counts(
    command_ledger: Any,
    commands: tuple[CommandEnvelope, ...],
) -> dict[str, int]:
    counts = {status: 0 for status in _TASK_STATUSES}
    for command in commands:
        counts[_command_task_status(command_ledger, command)] += 1
    return counts


def _waiting_for(state: CommandState) -> str:
    if state is CommandState.APPROVAL_CHAIN_PENDING:
        return "approval_chain"
    if state is CommandState.PENDING_APPROVAL:
        return "operator_approval"
    if state is CommandState.PENDING_EFFECT_APPROVAL:
        return "effect_approval"
    if state in _REVIEW_STATES:
        return "operator_review"
    return ""


def _next_action(task_status: str) -> str:
    return {
        "completed": "review_receipts",
        "blocked": "inspect_denial_or_block_receipts",
        "waiting_for_approval": "resolve_approval",
        "requires_review": "operator_review",
        "active": "monitor_execution_receipts",
        "received": "continue_governed_admission",
    }[task_status]


def _evidence_ref_count(receipts: list[dict[str, Any]]) -> int:
    count = 0
    for receipt in receipts:
        refs = receipt.get("evidence_refs")
        if not isinstance(refs, Mapping):
            continue
        count += sum(1 for value in refs.values() if _has_evidence_ref(value))
    return count


def _has_evidence_ref(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return any(_has_evidence_ref(item) for item in value)
    return value is not None


def _bounded_limit(limit: int, *, maximum: int = _MAX_PAGE_LIMIT) -> int:
    return max(1, min(int(limit), maximum))


def _bounded_offset(offset: int) -> int:
    return max(0, int(offset))


def _dataclass_mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, tuple):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_json_safe_value(item) for item in value]
    try:
        json.dumps(value, ensure_ascii=True, allow_nan=False)
    except (TypeError, ValueError):
        return str(value)
    return value


def _stable_hash(value: Any) -> str:
    return str(
        sha256(
            json.dumps(
                _json_safe_value(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()
    )


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _html_rows(
    records: list[Mapping[str, Any]],
    columns: tuple[str, ...],
    *,
    empty_label: str,
) -> str:
    if not records:
        return f'<tr><td colspan="{len(columns)}">{escape(empty_label)}</td></tr>'
    rendered: list[str] = []
    for record in records:
        rendered.append(
            "<tr>"
            + "".join(
                f"<td>{escape(_display_value(record.get(column, '')))}</td>"
                for column in columns
            )
            + "</tr>"
        )
    return "\n".join(rendered)


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _operator_table_html(
    *,
    title: str,
    description: str,
    json_href: str,
    columns: tuple[str, ...],
    rows: str,
    metrics: tuple[tuple[str, Any], ...],
    nav_links: tuple[tuple[str, str], ...],
) -> str:
    metric_items = "".join(
        "<li>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(_display_value(value))}</strong>"
        "</li>"
        for label, value in metrics
    )
    nav_items = "".join(
        f'<a href="{escape(href)}">{escape(label)}</a>'
        for href, label in ((json_href, "read model json"), *nav_links)
    )
    heading_cells = "".join(f"<th>{escape(column)}</th>" for column in columns)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; }}
    body {{ margin: 0; background: #f7f8fa; color: #1b1f24; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 32px 24px 48px; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    p {{ margin: 0 0 20px; color: #57606a; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 24px; }}
    a {{ color: #0969da; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; padding: 0; margin: 0 0 24px; }}
    .metrics li {{ display: flex; justify-content: space-between; gap: 16px; list-style: none; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8dee4; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; font-size: 13px; overflow-wrap: anywhere; }}
    th {{ background: #eef1f4; font-weight: 700; }}
  </style>
</head>
<body>
<main>
  <h1>{escape(title)}</h1>
  <p>{escape(description)}</p>
  <nav>{nav_items}</nav>
  <ul class="metrics">{metric_items}</ul>
  <table>
    <thead><tr>{heading_cells}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
</main>
</body>
</html>"""
