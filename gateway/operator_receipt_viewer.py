"""Operator receipt, approval-history, plan-review, and current-task read models.

Purpose: Build bounded operator visibility for command receipts and active
    task state without exposing raw command payload text.
Governance scope: gateway command receipt visibility, persisted approval
    history projection, plan-review projection, task-state projection, and
    read-only operator evidence review.
Dependencies: gateway command spine and universal action proof reconstruction.
Invariants:
  - Raw command payload text is never exposed.
  - Read models never mutate the command ledger.
  - Receipt rows expose identifiers, hashes, states, and evidence references.
  - Approval history rows are reconstructed from command transition witnesses.
  - Plan review rows expose redacted plan, budget, and recovery evidence only.
  - Limit and offset inputs are bounded before ledger scans.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from html import escape
import json
from typing import Any, Mapping
from urllib.parse import quote, urlencode

from gateway.command_spine import CommandEnvelope, CommandEvent, CommandState
from mcoi_runtime.app.governed_execution import universal_command_proof_view


RECEIPT_VIEWER_SCHEMA_REF = "urn:mullusi:schema:operator-receipt-viewer-read-model:1"
APPROVAL_HISTORY_SCHEMA_REF = "urn:mullusi:schema:operator-approval-history-read-model:1"
PLAN_REVIEW_SCHEMA_REF = "urn:mullusi:schema:operator-plan-review-read-model:1"
BUDGET_REPORT_SCHEMA_REF = "urn:mullusi:schema:operator-budget-report-read-model:1"
PLAN_RECEIPT_EXPORT_SCHEMA_REF = "urn:mullusi:schema:operator-plan-receipt-export-read-model:1"
PLAN_RECEIPT_BUNDLE_SCHEMA_REF = "urn:mullusi:schema:operator-plan-receipt-bundle-read-model:1"
CURRENT_TASK_SCHEMA_REF = "urn:mullusi:schema:current-task-read-model:1"

_MAX_SCAN_LIMIT = 1000
_MAX_PAGE_LIMIT = 500
_MAX_SEARCH_FILTER_LENGTH = 128

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

_CAPABILITY_INTENT_KEYS = ("capability_intent", "skill_intent")

_RECEIPT_TYPES = (
    "interpretation_receipt",
    "search_decision_receipt",
    "search_receipt",
    "plan_step_receipt",
    "approval_receipt",
    "denial_receipt",
    "worker_receipt",
    "worker_failure_receipt",
    "delivery_receipt",
    "command_event",
    "universal_action_proof",
    "terminal_closure_certificate",
)

_APPROVAL_APPROVED_STATES = frozenset(
    {
        CommandState.APPROVED,
        CommandState.ALLOWED,
        CommandState.APPROVAL_CHAIN_SATISFIED,
    }
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
_RESPONSE_STATES = (
    "received",
    "in_progress",
    "waiting_for_approval",
    "requires_review",
    "blocked",
    "awaiting_terminal_evidence",
    "completed_verified",
)
_RESPONSE_EVIDENCE_STATES = (
    "received",
    "execution_in_progress",
    "approval_pending",
    "operator_review_required",
    "blocked_with_receipt",
    "blocked_receipt_required",
    "terminal_certificate_missing",
    "terminal_verified",
)
_APPROVAL_STATUSES = ("pending", "approved", "denied", "expired", "unknown")
_PLAN_REVIEW_STATUSES = (
    "preview_ready",
    "handoff_submitted",
    "denied",
    "blocked",
    "certified",
    "failed",
    "recovered",
    "recovery_rejected",
    "recovery_pending",
)
_PLAN_BUDGET_GATES = ("budget_reserved", "not_required", "not_recorded")
_APPROVAL_HISTORY_COLUMNS = (
    "approval_request_id",
    "status",
    "tenant_id",
    "command_id",
    "risk_tier",
    "approval_strength_policy",
    "approval_strength_decision",
    "approval_strength",
    "required_approval_strength",
    "actor_id",
    "source",
    "intent",
    "requested_at",
    "resolved_at",
    "resolved_by",
    "command_state",
    "task_status",
    "event_count",
    "latest_event_hash",
    "approval_strength_required_controls",
    "receipt_href",
    "current_task_href",
)
_PLAN_REVIEW_COLUMNS = (
    "plan_id",
    "status",
    "review_type",
    "tenant_id",
    "risk_tier",
    "approval_required",
    "budget_required",
    "budget_gate",
    "budget_evidence_state",
    "estimate_state",
    "used_cost_units",
    "limit_cost_units",
    "remaining_cost_units",
    "budget_report_href",
    "required_by_steps",
    "step_count",
    "certificate_id",
    "witness_id",
    "attempt_id",
    "recovery_action",
    "latest_at",
    "review_href",
    "receipt_export_href",
    "closure_href",
)
_BUDGET_REPORT_COLUMNS = (
    "tenant_id",
    "status",
    "budget_id",
    "spent_cost_units",
    "limit_cost_units",
    "remaining_cost_units",
    "calls_made",
    "max_calls",
    "exhausted",
    "enabled",
    "utilization_percent",
)
_PLAN_RECEIPT_EXPORT_COLUMNS = (
    "command_id",
    "tenant_id",
    "intent",
    "command_state",
    "task_status",
    "receipt_count",
    "receipt_types",
    "latest_event_hash",
    "receipt_href",
)
_PLAN_RECEIPT_BUNDLE_COLUMNS = (
    "plan_id",
    "status",
    "evidence_bundle_available",
    "step_command_count",
    "receipt_group_count",
    "receipt_count",
    "evidence_ref_count",
    "missing_step_command_count",
    "receipt_export_href",
)


def valid_task_statuses() -> tuple[str, ...]:
    """Return accepted current-task status filter values."""
    return _TASK_STATUSES


def valid_receipt_types() -> tuple[str, ...]:
    """Return accepted operator receipt type filter values."""
    return _RECEIPT_TYPES


def valid_approval_statuses() -> tuple[str, ...]:
    """Return accepted operator approval history status filter values."""
    return _APPROVAL_STATUSES


def valid_plan_review_statuses() -> tuple[str, ...]:
    """Return accepted operator plan-review status filter values."""
    return _PLAN_REVIEW_STATUSES


def valid_plan_budget_gates() -> tuple[str, ...]:
    """Return accepted operator plan-review budget gate filter values."""
    return _PLAN_BUDGET_GATES


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
    receipt_type: str = "",
    receipt_status: str = "",
    task_status: str = "",
    search: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Build a bounded command receipt read model for operator review."""
    normalized_receipt_type = receipt_type.strip()
    normalized_receipt_status = receipt_status.strip()
    normalized_task_status = task_status.strip()
    normalized_search = search.strip()[:_MAX_SEARCH_FILTER_LENGTH]
    bounded_limit = _bounded_limit(limit)
    bounded_offset = _bounded_offset(offset)
    filters_active = any(
        (
            normalized_receipt_type,
            normalized_receipt_status,
            normalized_task_status,
            normalized_search,
        )
    )
    commands = _filtered_commands(
        command_ledger,
        tenant_id=tenant_id,
        command_id=command_id,
        limit=_MAX_SCAN_LIMIT if filters_active else bounded_limit,
        offset=0 if filters_active else bounded_offset,
    )
    all_rows = [
        row
        for command in commands["page"]
        if (
            row := _filtered_command_receipt_group(
                command_ledger,
                command,
                receipt_type=normalized_receipt_type,
                receipt_status=normalized_receipt_status,
                task_status=normalized_task_status,
                search=normalized_search,
            )
        )
        is not None
    ]
    if filters_active:
        rows = all_rows[bounded_offset:bounded_offset + bounded_limit]
        total = len(all_rows)
        next_offset = bounded_offset + len(rows)
    else:
        rows = all_rows
        total = commands["total"]
        next_offset = commands["next_offset"]
    total_receipts = sum(int(row["receipt_count"]) for row in rows)
    resolved_next_offset = (
        next_offset
        if isinstance(next_offset, int) and next_offset < total
        else None
    )
    return {
        "schema_ref": RECEIPT_VIEWER_SCHEMA_REF,
        "tenant_id_filter": tenant_id,
        "command_id_filter": command_id,
        "receipt_type_filter": normalized_receipt_type,
        "receipt_status_filter": normalized_receipt_status,
        "task_status_filter": normalized_task_status,
        "search_filter": normalized_search,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "next_offset": resolved_next_offset,
        "total": total,
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
            if task["response_state"] != "completed_verified"
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
        "receipt_types",
        "receipt_count",
    )
    rows = _receipt_group_rows(records, columns)
    metrics = (
        ("Visible", read_model.get("count", 0)),
        ("Total", read_model.get("total", 0)),
        ("Receipts", read_model.get("total_receipts", 0)),
        ("Tenant Filter", read_model.get("tenant_id_filter", "")),
        ("Command Filter", read_model.get("command_id_filter", "")),
        ("Receipt Type", read_model.get("receipt_type_filter", "")),
        ("Receipt Status", read_model.get("receipt_status_filter", "")),
        ("Task Status", read_model.get("task_status_filter", "")),
        ("Search", read_model.get("search_filter", "")),
    )
    filter_query = _receipt_filter_query(read_model)
    return _operator_table_html(
        title="Mullu Operator Receipt Viewer",
        description="Read-only command receipt groups with bounded evidence references.",
        json_href="/operator/receipts/read-model"
        + (f"?{filter_query}" if filter_query else ""),
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/current-task", "current task"),
            ("/operator/plan-review", "plan review"),
            ("/operator/approvals", "approval history"),
            ("/operator/universal-actions", "universal actions"),
            ("/gateway/status", "gateway status"),
        ),
        extra_html=_receipt_filter_controls(read_model),
    )


def render_operator_receipt_detail_html(read_model: Mapping[str, Any]) -> str:
    """Render one command receipt group with bounded receipt details."""
    groups = _mapping_list(read_model.get("receipt_groups"))
    group = groups[0] if groups else {}
    receipts = _mapping_list(group.get("receipts"))
    columns = (
        "receipt_type",
        "status",
        "receipt_id",
        "receipt_hash",
        "details",
        "evidence_refs",
    )
    rows = _html_rows(receipts, columns, empty_label="No receipts for command")
    command_id = str(group.get("command_id", "")).strip()
    tenant_id = str(group.get("tenant_id", "")).strip()
    query = f"?command_id={quote(command_id, safe='')}" if command_id else ""
    metrics = (
        ("Command", command_id),
        ("Tenant", tenant_id),
        ("State", group.get("command_state", "")),
        ("Task", group.get("task_status", "")),
        ("Receipts", group.get("receipt_count", 0)),
        ("Raw Exposed", read_model.get("raw_message_exposed", False)),
    )
    return _operator_table_html(
        title="Mullu Receipt Detail",
        description="Read-only bounded receipt details and evidence references for one command.",
        json_href=f"/operator/receipts/read-model{query}",
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/receipts", "receipt viewer"),
            ("/operator/plan-review", "plan review"),
            ("/operator/current-task", "current task"),
            ("/gateway/status", "gateway status"),
        ),
    )


def build_operator_approval_history_read_model(
    command_ledger: Any,
    *,
    tenant_id: str = "",
    request_id: str = "",
    command_id: str = "",
    status: str = "",
    search: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Build a bounded approval history read model from command witnesses."""
    normalized_request_id = request_id.strip()
    normalized_command_id = command_id.strip()
    normalized_status = status.strip()
    normalized_search = search.strip()[:_MAX_SEARCH_FILTER_LENGTH]
    bounded_limit = _bounded_limit(limit)
    bounded_offset = _bounded_offset(offset)
    commands = _filtered_commands(
        command_ledger,
        tenant_id=tenant_id,
        command_id=normalized_command_id,
        limit=_MAX_SCAN_LIMIT,
        offset=0,
    )
    records = [
        record
        for command in commands["all"]
        for record in _approval_history_records_for_command(command_ledger, command)
        if _approval_history_matches_filters(
            record,
            request_id=normalized_request_id,
            status=normalized_status,
            search=normalized_search,
        )
    ]
    total = len(records)
    rows = records[bounded_offset:bounded_offset + bounded_limit]
    next_offset = bounded_offset + len(rows)
    status_counts = {approval_status: 0 for approval_status in _APPROVAL_STATUSES}
    for record in records:
        approval_status = str(record.get("status", "unknown"))
        if approval_status not in status_counts:
            approval_status = "unknown"
        status_counts[approval_status] += 1
    return {
        "schema_ref": APPROVAL_HISTORY_SCHEMA_REF,
        "tenant_id_filter": tenant_id,
        "request_id_filter": normalized_request_id,
        "command_id_filter": normalized_command_id,
        "status_filter": normalized_status,
        "search_filter": normalized_search,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "next_offset": next_offset if next_offset < total else None,
        "total": total,
        "count": len(rows),
        "status_counts": status_counts,
        "approvals": rows,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def render_operator_approval_history_html(read_model: Mapping[str, Any]) -> str:
    """Render approval history as read-only operator HTML."""
    records = _mapping_list(read_model.get("approvals"))
    columns = _APPROVAL_HISTORY_COLUMNS
    rows = _html_rows(records, columns, empty_label="No approval history")
    status_counts = read_model.get("status_counts")
    if not isinstance(status_counts, Mapping):
        status_counts = {}
    metrics = (
        ("Visible", read_model.get("count", 0)),
        ("Total", read_model.get("total", 0)),
        ("Pending", status_counts.get("pending", 0)),
        ("Approved", status_counts.get("approved", 0)),
        ("Denied", status_counts.get("denied", 0)),
        ("Expired", status_counts.get("expired", 0)),
    )
    query = _approval_filter_query(read_model)
    return _operator_table_html(
        title="Mullu Approval History",
        description="Read-only approval request history reconstructed from command transition witnesses.",
        json_href="/operator/approvals/read-model"
        + (f"?{query}" if query else ""),
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/current-task", "current task"),
            ("/operator/plan-review", "plan review"),
            ("/operator/receipts", "receipt viewer"),
            ("/gateway/status", "gateway status"),
        ),
        extra_html=_approval_filter_controls(read_model),
    )


def render_operator_approval_detail_html(read_model: Mapping[str, Any]) -> str:
    """Render one approval history row as bounded operator HTML."""
    records = _mapping_list(read_model.get("approvals"))
    record = records[0] if records else {}
    columns = _APPROVAL_HISTORY_COLUMNS
    rows = _html_rows(records, columns, empty_label="Approval history not found")
    request_id = str(record.get("approval_request_id", "")).strip()
    tenant_id = str(record.get("tenant_id", "")).strip()
    query = f"?request_id={quote(request_id, safe='')}" if request_id else ""
    metrics = (
        ("Approval", request_id),
        ("Tenant", tenant_id),
        ("Status", record.get("status", "")),
        ("Risk", record.get("risk_tier", "")),
        ("Command", record.get("command_id", "")),
        ("Raw Exposed", read_model.get("raw_message_exposed", False)),
    )
    return _operator_table_html(
        title="Mullu Approval Detail",
        description="Read-only approval request detail and receipt navigation.",
        json_href=f"/operator/approvals/read-model{query}",
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/approvals", "approval history"),
            ("/operator/plan-review", "plan review"),
            ("/operator/current-task", "current task"),
            ("/operator/receipts", "receipt viewer"),
        ),
    )


def build_operator_plan_review_read_model(
    plan_ledger: Any,
    *,
    preview_store: Any | None = None,
    tenant_budget_reporter: Any | None = None,
    tenant_id: str = "",
    plan_id: str = "",
    status: str = "",
    budget_gate: str = "",
    search: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Build a bounded read-only Plan Review model with budget evidence."""
    normalized_plan_id = plan_id.strip()
    normalized_status = status.strip()
    normalized_budget_gate = budget_gate.strip()
    normalized_search = search.strip()[:_MAX_SEARCH_FILTER_LENGTH]
    bounded_limit = _bounded_limit(limit)
    bounded_offset = _bounded_offset(offset)
    preview_records = _preview_records(preview_store)
    preview_by_plan = _preview_by_plan_id(preview_records)
    ledger_model = plan_ledger.read_model()
    all_rows = [
        *_plan_review_preview_rows(preview_records),
        *_plan_review_certificate_rows(ledger_model, preview_by_plan),
        *_plan_review_failed_witness_rows(ledger_model, preview_by_plan),
        *_plan_review_recovery_attempt_rows(ledger_model, preview_by_plan),
    ]
    all_rows = _plan_review_rows_with_tenant_budget_reports(
        all_rows,
        tenant_budget_reporter,
    )
    filtered_rows = [
        row
        for row in all_rows
        if _plan_review_matches_filters(
            row,
            tenant_id=tenant_id,
            plan_id=normalized_plan_id,
            status=normalized_status,
            budget_gate=normalized_budget_gate,
            search=normalized_search,
        )
    ]
    total = len(filtered_rows)
    rows = filtered_rows[bounded_offset:bounded_offset + bounded_limit]
    next_offset = bounded_offset + len(rows)
    return {
        "schema_ref": PLAN_REVIEW_SCHEMA_REF,
        "tenant_id_filter": tenant_id,
        "plan_id_filter": normalized_plan_id,
        "status_filter": normalized_status,
        "budget_gate_filter": normalized_budget_gate,
        "search_filter": normalized_search,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "next_offset": next_offset if next_offset < total else None,
        "total": total,
        "count": len(rows),
        "status_counts": _plan_review_status_counts(filtered_rows),
        "budget_gate_counts": _plan_review_budget_gate_counts(filtered_rows),
        "plans": rows,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def render_operator_plan_review_html(read_model: Mapping[str, Any]) -> str:
    """Render Plan Review history as read-only operator HTML."""
    records = _mapping_list(read_model.get("plans"))
    rows = _html_rows(records, _PLAN_REVIEW_COLUMNS, empty_label="No plan review history")
    status_counts = read_model.get("status_counts")
    if not isinstance(status_counts, Mapping):
        status_counts = {}
    budget_counts = read_model.get("budget_gate_counts")
    if not isinstance(budget_counts, Mapping):
        budget_counts = {}
    query = _plan_review_filter_query(read_model)
    metrics = (
        ("Visible", read_model.get("count", 0)),
        ("Total", read_model.get("total", 0)),
        ("Preview", status_counts.get("preview_ready", 0)),
        ("Certified", status_counts.get("certified", 0)),
        ("Failed", status_counts.get("failed", 0)),
        ("Budget Required", budget_counts.get("budget_reserved", 0)),
    )
    return _operator_table_html(
        title="Mullu Plan Review",
        description="Read-only plan history, recovery state, and bounded budget evidence.",
        json_href="/operator/plan-review/read-model"
        + (f"?{query}" if query else ""),
        columns=_PLAN_REVIEW_COLUMNS,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/goal-intake", "goal intake"),
            ("/operator/current-task", "current task"),
            ("/operator/approvals", "approval history"),
            ("/operator/receipts", "receipt viewer"),
        ),
        extra_html=_plan_review_filter_controls(read_model),
    )


def render_operator_plan_review_detail_html(read_model: Mapping[str, Any]) -> str:
    """Render all Plan Review rows for one plan id."""
    records = _mapping_list(read_model.get("plans"))
    rows = _html_rows(records, _PLAN_REVIEW_COLUMNS, empty_label="Plan review history not found")
    first = records[0] if records else {}
    plan_id = str(first.get("plan_id", read_model.get("plan_id_filter", ""))).strip()
    tenant_id = str(first.get("tenant_id", read_model.get("tenant_id_filter", ""))).strip()
    query = f"?plan_id={quote(plan_id, safe='')}" if plan_id else ""
    metrics = (
        ("Plan", plan_id),
        ("Tenant", tenant_id),
        ("Rows", read_model.get("count", 0)),
        ("Status", first.get("status", "")),
        ("Budget", first.get("budget_gate", "")),
        ("Raw Exposed", read_model.get("raw_message_exposed", False)),
    )
    return _operator_table_html(
        title="Mullu Plan Review Detail",
        description="Read-only plan review history and budget evidence for one plan.",
        json_href=f"/operator/plan-review/read-model{query}",
        columns=_PLAN_REVIEW_COLUMNS,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/plan-review", "plan review"),
            ("/operator/current-task", "current task"),
            ("/operator/receipts", "receipt viewer"),
        ),
    )


def build_operator_plan_receipt_export_read_model(
    *,
    plan_ledger: Any,
    command_ledger: Any,
    preview_store: Any | None = None,
    tenant_budget_reporter: Any | None = None,
    plan_id: str,
) -> dict[str, Any]:
    """Build a read-only Plan Review receipt export for one plan."""
    normalized_plan_id = plan_id.strip()
    plan_review = build_operator_plan_review_read_model(
        plan_ledger,
        preview_store=preview_store,
        tenant_budget_reporter=tenant_budget_reporter,
        plan_id=normalized_plan_id,
        limit=100,
        offset=0,
    )
    certificate = plan_ledger.certificate_for(normalized_plan_id) if normalized_plan_id else None
    evidence_bundle: dict[str, Any] | None = None
    step_receipt_groups: list[dict[str, Any]] = []
    missing_step_command_ids: list[str] = []
    status = "not_found" if plan_review["count"] < 1 else "awaiting_certificate"
    if certificate is not None:
        status = "certified"
        evidence_bundle = _dataclass_mapping(
            plan_ledger.export_evidence_bundle(plan_id=normalized_plan_id)
        )
        for command_id in _text_tuple(evidence_bundle.get("step_command_ids")):
            command = command_ledger.get(command_id)
            if command is None:
                missing_step_command_ids.append(command_id)
                continue
            step_receipt_groups.append(_command_receipt_group(command_ledger, command))
    receipt_count = sum(int(group.get("receipt_count", 0)) for group in step_receipt_groups)
    return {
        "schema_ref": PLAN_RECEIPT_EXPORT_SCHEMA_REF,
        "plan_id": normalized_plan_id,
        "status": status,
        "plan_review": plan_review,
        "plan_evidence_bundle": evidence_bundle,
        "evidence_bundle_available": evidence_bundle is not None,
        "step_command_count": len(step_receipt_groups),
        "missing_step_command_ids": missing_step_command_ids,
        "receipt_group_count": len(step_receipt_groups),
        "receipt_count": receipt_count,
        "step_receipt_groups": step_receipt_groups,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def build_operator_plan_receipt_bundle_read_model(
    *,
    plan_ledger: Any,
    command_ledger: Any,
    preview_store: Any | None = None,
    tenant_budget_reporter: Any | None = None,
    tenant_id: str = "",
    status: str = "",
    budget_gate: str = "",
    search: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Build a read-only receipt bundle across the current Plan Review page."""
    plan_review = build_operator_plan_review_read_model(
        plan_ledger,
        preview_store=preview_store,
        tenant_budget_reporter=tenant_budget_reporter,
        tenant_id=tenant_id,
        status=status,
        budget_gate=budget_gate,
        search=search,
        limit=limit,
        offset=offset,
    )
    plan_exports: list[dict[str, Any]] = []
    plan_export_summaries: list[dict[str, Any]] = []
    missing_step_command_ids: list[str] = []
    receipt_type_counts: dict[str, int] = {}
    receipt_status_counts: dict[str, int] = {}
    for plan_record in _mapping_list(plan_review.get("plans")):
        plan_id = str(plan_record.get("plan_id", "")).strip()
        if not plan_id:
            continue
        export = build_operator_plan_receipt_export_read_model(
            plan_ledger=plan_ledger,
            command_ledger=command_ledger,
            preview_store=preview_store,
            tenant_budget_reporter=tenant_budget_reporter,
            plan_id=plan_id,
        )
        plan_exports.append(export)
        missing = [str(command_id) for command_id in _text_tuple(export.get("missing_step_command_ids"))]
        missing_step_command_ids.extend(missing)
        for group in _mapping_list(export.get("step_receipt_groups")):
            for receipt_type in _text_tuple(group.get("receipt_types")):
                _increment_count(receipt_type_counts, receipt_type)
            for receipt in _mapping_list(group.get("receipts")):
                _increment_count(receipt_status_counts, _receipt_status_key(receipt))
        evidence_bundle = export.get("plan_evidence_bundle")
        evidence_refs = (
            _text_tuple(evidence_bundle.get("evidence_refs"))
            if isinstance(evidence_bundle, Mapping)
            else ()
        )
        plan_export_summaries.append(
            {
                "plan_id": plan_id,
                "status": str(export.get("status", "not_found")),
                "evidence_bundle_available": export.get("evidence_bundle_available") is True,
                "step_command_count": _bounded_int(export.get("step_command_count")),
                "receipt_group_count": _bounded_int(export.get("receipt_group_count")),
                "receipt_count": _bounded_int(export.get("receipt_count")),
                "evidence_ref_count": len(evidence_refs),
                "missing_step_command_count": len(missing),
                "receipt_export_href": _plan_receipt_export_href(plan_id),
            }
        )
    return {
        "schema_ref": PLAN_RECEIPT_BUNDLE_SCHEMA_REF,
        "tenant_id_filter": str(plan_review.get("tenant_id_filter", "")),
        "status_filter": str(plan_review.get("status_filter", "")),
        "budget_gate_filter": str(plan_review.get("budget_gate_filter", "")),
        "search_filter": str(plan_review.get("search_filter", "")),
        "limit": _bounded_int(plan_review.get("limit")),
        "offset": _bounded_int(plan_review.get("offset")),
        "next_offset": plan_review.get("next_offset"),
        "total": _bounded_int(plan_review.get("total")),
        "count": len(plan_exports),
        "plan_review": plan_review,
        "plan_export_count": len(plan_exports),
        "certified_export_count": sum(1 for export in plan_exports if export.get("status") == "certified"),
        "evidence_bundle_count": sum(1 for export in plan_exports if export.get("evidence_bundle_available") is True),
        "step_command_count": sum(_bounded_int(export.get("step_command_count")) for export in plan_exports),
        "receipt_group_count": sum(_bounded_int(export.get("receipt_group_count")) for export in plan_exports),
        "receipt_count": sum(_bounded_int(export.get("receipt_count")) for export in plan_exports),
        "evidence_ref_count": sum(
            _bounded_int(summary.get("evidence_ref_count")) for summary in plan_export_summaries
        ),
        "missing_step_command_ids": missing_step_command_ids,
        "receipt_type_counts": receipt_type_counts,
        "receipt_status_counts": receipt_status_counts,
        "plan_export_summaries": plan_export_summaries,
        "plan_exports": plan_exports,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def render_operator_plan_receipt_bundle_html(read_model: Mapping[str, Any]) -> str:
    """Render the cross-plan receipt bundle as bounded operator HTML."""
    summaries = _mapping_list(read_model.get("plan_export_summaries"))
    rows = _html_rows(
        summaries,
        _PLAN_RECEIPT_BUNDLE_COLUMNS,
        empty_label="No plan receipt exports in the current view",
    )
    metrics = (
        ("Plans", read_model.get("plan_export_count", 0)),
        ("Certified", read_model.get("certified_export_count", 0)),
        ("Evidence Bundles", read_model.get("evidence_bundle_count", 0)),
        ("Receipt Groups", read_model.get("receipt_group_count", 0)),
        ("Receipts", read_model.get("receipt_count", 0)),
        ("Raw Exposed", read_model.get("raw_message_exposed", False)),
    )
    return _operator_table_html(
        title="Mullu Plan Receipt Bundle",
        description="Read-only Plan Review receipt bundle for the current filtered plan page.",
        json_href="/operator/plan-review/receipts/read-model",
        columns=_PLAN_RECEIPT_BUNDLE_COLUMNS,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/plan-review", "plan review"),
            ("/operator/receipts", "receipt viewer"),
            ("/operator/current-task", "current task"),
        ),
    )


def render_operator_plan_receipt_export_html(read_model: Mapping[str, Any]) -> str:
    """Render a Plan Review receipt export as bounded operator HTML."""
    groups = _mapping_list(read_model.get("step_receipt_groups"))
    rows = _html_rows(
        groups,
        _PLAN_RECEIPT_EXPORT_COLUMNS,
        empty_label="No step command receipts exported",
    )
    plan_id = str(read_model.get("plan_id", "")).strip()
    metrics = (
        ("Plan", plan_id),
        ("Status", read_model.get("status", "")),
        ("Bundle", "available" if read_model.get("evidence_bundle_available") else "not available"),
        ("Step Commands", read_model.get("step_command_count", 0)),
        ("Receipt Groups", read_model.get("receipt_group_count", 0)),
        ("Receipts", read_model.get("receipt_count", 0)),
        ("Raw Exposed", read_model.get("raw_message_exposed", False)),
    )
    href = _plan_receipt_export_href(plan_id) if plan_id else "/operator/plan-review"
    return _operator_table_html(
        title="Mullu Plan Receipt Export",
        description="Read-only Plan Review export binding plan evidence and step command receipts.",
        json_href=f"{href}/read-model",
        columns=_PLAN_RECEIPT_EXPORT_COLUMNS,
        rows=rows,
        metrics=metrics,
        nav_links=(
            (_plan_review_detail_href(plan_id), "plan review detail"),
            ("/operator/plan-review", "plan review"),
            ("/operator/receipts", "receipt viewer"),
        ),
    )


def build_operator_budget_report_read_model(
    tenant_budget_reporter: Any | None,
    *,
    tenant_id: str,
) -> dict[str, Any]:
    """Build a read-only operator budget report for one tenant."""
    normalized_tenant_id = tenant_id.strip()
    report: Mapping[str, Any] | None = None
    if tenant_budget_reporter is not None and normalized_tenant_id:
        report = _tenant_budget_report(tenant_budget_reporter, normalized_tenant_id)
    row = _budget_report_row(normalized_tenant_id, report, tenant_budget_reporter)
    return {
        "schema_ref": BUDGET_REPORT_SCHEMA_REF,
        "tenant_id": normalized_tenant_id,
        "status": row["status"],
        "report": row,
        "raw_message_exposed": False,
        "execution_allowed": False,
        "write_allowed": False,
        "governed": True,
    }


def render_operator_budget_report_html(read_model: Mapping[str, Any]) -> str:
    """Render one tenant budget report as read-only operator HTML."""
    row = read_model.get("report")
    records = [row] if isinstance(row, Mapping) else []
    rows = _html_rows(records, _BUDGET_REPORT_COLUMNS, empty_label="No budget report")
    tenant_id = str(read_model.get("tenant_id", "")).strip()
    metrics = (
        ("Tenant", tenant_id),
        ("Status", read_model.get("status", "")),
        ("Spend", row.get("spent_cost_units", "") if isinstance(row, Mapping) else ""),
        ("Limit", row.get("limit_cost_units", "") if isinstance(row, Mapping) else ""),
        ("Remaining", row.get("remaining_cost_units", "") if isinstance(row, Mapping) else ""),
        ("Raw Exposed", read_model.get("raw_message_exposed", False)),
    )
    href = _budget_report_href(tenant_id) if tenant_id else "/operator/plan-review"
    return _operator_table_html(
        title="Mullu Budget Report",
        description="Read-only tenant budget evidence used by Plan Review.",
        json_href=f"{href}/read-model",
        columns=_BUDGET_REPORT_COLUMNS,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/plan-review", "plan review"),
            ("/operator/current-task", "current task"),
            ("/operator/receipts", "receipt viewer"),
        ),
    )


def render_current_task_html(read_model: Mapping[str, Any]) -> str:
    """Render the current-task read model as an operator task table."""
    records = _mapping_list(read_model.get("tasks"))
    columns = (
        "command_id",
        "tenant_id",
        "actor_id",
        "source",
        "intent",
        "goal_intake_preview_id",
        "goal_hash",
        "plan_id",
        "plan_step_id",
        "command_state",
        "task_status",
        "response_state",
        "response_evidence_state",
        "response_claim_allowed",
        "response_terminal_certificate_id",
        "response_evidence_refs",
        "response_blocker",
        "waiting_for",
        "approval_request_id",
        "approval_recovery_available",
        "worker_failure_receipt_id",
        "worker_failure_state",
        "worker_failure_recovery_action",
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
    action_html = _operator_action_status_html(
        str(read_model.get("operator_action_status", ""))
    ) + _approval_recovery_controls(records)
    return _operator_table_html(
        title="Mullu Current Task State",
        description="Read-only command task states and next governed operator actions.",
        json_href="/operator/current-task/read-model",
        columns=columns,
        rows=rows,
        metrics=metrics,
        nav_links=(
            ("/operator/receipts", "receipt viewer"),
            ("/operator/plan-review", "plan review"),
            ("/operator/approvals", "approval history"),
            ("/operator/universal-actions", "universal actions"),
            ("/gateway/status", "gateway status"),
        ),
        extra_html=action_html,
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


def _filtered_command_receipt_group(
    command_ledger: Any,
    command: CommandEnvelope,
    *,
    receipt_type: str,
    receipt_status: str,
    task_status: str,
    search: str,
) -> dict[str, Any] | None:
    row = _command_receipt_group(command_ledger, command)
    if task_status and row["task_status"] != task_status:
        return None
    active_receipt_filters = bool(receipt_type or receipt_status or search)
    if not active_receipt_filters:
        return row
    if (
        search
        and not receipt_type
        and not receipt_status
        and _receipt_group_search_text(row).find(search.lower()) >= 0
    ):
        return row

    filtered_receipts = [
        receipt
        for receipt in _mapping_list(row.get("receipts"))
        if _receipt_matches_filters(
            receipt,
            receipt_type=receipt_type,
            receipt_status=receipt_status,
            search=search,
        )
    ]
    if not filtered_receipts:
        return None
    return {
        **row,
        "receipt_types": _receipt_types(filtered_receipts),
        "receipt_count": len(filtered_receipts),
        "receipts": filtered_receipts,
    }


def _preview_records(preview_store: Any | None) -> tuple[Any, ...]:
    if preview_store is None:
        return ()
    list_records = getattr(preview_store, "list_records", None)
    if not callable(list_records):
        return ()
    records = list_records()
    if isinstance(records, tuple):
        return records
    if isinstance(records, list):
        return tuple(records)
    return ()


def _preview_by_plan_id(preview_records: tuple[Any, ...]) -> dict[str, Mapping[str, Any]]:
    previews: dict[str, Mapping[str, Any]] = {}
    for record in preview_records:
        mapping = _dataclass_mapping(record)
        preview = mapping.get("preview")
        if not isinstance(preview, Mapping):
            preview = {}
        plan_id = str(mapping.get("plan_id") or preview.get("plan_id") or "").strip()
        if plan_id:
            previews[plan_id] = mapping
    return previews


def _plan_review_preview_rows(preview_records: tuple[Any, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in preview_records:
        mapping = _dataclass_mapping(record)
        preview = mapping.get("preview")
        if not isinstance(preview, Mapping):
            preview = {}
        plan_id = str(mapping.get("plan_id") or preview.get("plan_id") or "").strip()
        if not plan_id:
            continue
        budget = _budget_from_mapping(preview.get("budget"), "preview_budget")
        rows.append(
            _plan_review_row(
                review_id=str(mapping.get("preview_id") or preview.get("preview_id") or ""),
                review_type="preview",
                plan_id=plan_id,
                preview_id=str(mapping.get("preview_id") or preview.get("preview_id") or ""),
                tenant_id=str(mapping.get("tenant_id") or preview.get("tenant_id") or ""),
                identity_id=str(mapping.get("identity_id") or preview.get("identity_id") or ""),
                status=_plan_review_preview_status(mapping),
                risk_tier=str(preview.get("risk_tier", "")),
                approval_required=bool(preview.get("approval_required", False)),
                step_count=int(preview.get("step_count", 0) or 0),
                goal_hash=str(mapping.get("goal_hash") or preview.get("goal_hash") or ""),
                evidence_required=_text_tuple(preview.get("evidence_required")),
                budget=budget,
                tools_count=len(_mapping_list(preview.get("tools"))),
                latest_at=str(mapping.get("decided_at") or mapping.get("created_at") or preview.get("created_at") or ""),
            )
        )
    return rows


def _plan_review_certificate_rows(
    ledger_model: Mapping[str, Any],
    preview_by_plan: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for certificate in _mapping_list(ledger_model.get("certificates")):
        plan_id = str(certificate.get("plan_id", "")).strip()
        if not plan_id:
            continue
        metadata = certificate.get("metadata")
        if not isinstance(metadata, Mapping):
            metadata = {}
        preview = preview_by_plan.get(plan_id, {})
        budget = _budget_from_preview_record_or_snapshot(
            preview_record=preview,
            plan_snapshot={},
            fallback_state="certificate_metadata_only",
        )
        rows.append(
            _plan_review_row(
                review_id=str(certificate.get("certificate_id", "")),
                review_type="certificate",
                plan_id=plan_id,
                preview_id=str(preview.get("preview_id", "")),
                tenant_id=str(certificate.get("tenant_id", "")),
                identity_id=str(certificate.get("identity_id", "")),
                status="certified",
                risk_tier=str(metadata.get("risk_tier", "")),
                approval_required=bool(metadata.get("approval_required", False)),
                step_count=int(certificate.get("step_count", 0) or 0),
                goal_hash=str(preview.get("goal_hash", "")),
                evidence_required=_text_tuple(metadata.get("evidence_required")),
                budget=budget,
                tools_count=_preview_tools_count(preview),
                certificate_id=str(certificate.get("certificate_id", "")),
                latest_at=str(certificate.get("issued_at", "")),
            )
        )
    return rows


def _plan_review_failed_witness_rows(
    ledger_model: Mapping[str, Any],
    preview_by_plan: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for witness in _mapping_list(ledger_model.get("failed_plan_witnesses")):
        plan_id = str(witness.get("plan_id", "")).strip()
        if not plan_id:
            continue
        detail = witness.get("detail")
        if not isinstance(detail, Mapping):
            detail = {}
        plan_snapshot = detail.get("plan_snapshot")
        if not isinstance(plan_snapshot, Mapping):
            plan_snapshot = {}
        recovery_decision = detail.get("recovery_decision")
        if not isinstance(recovery_decision, Mapping):
            recovery_decision = {}
        preview = preview_by_plan.get(plan_id, {})
        budget = _budget_from_preview_record_or_snapshot(
            preview_record=preview,
            plan_snapshot=plan_snapshot,
            fallback_state="witness_plan_snapshot",
        )
        rows.append(
            _plan_review_row(
                review_id=str(witness.get("witness_id", "")),
                review_type="failed_witness",
                plan_id=plan_id,
                preview_id=str(preview.get("preview_id", "")),
                tenant_id=str(plan_snapshot.get("tenant_id") or preview.get("tenant_id") or ""),
                identity_id=str(plan_snapshot.get("identity_id") or preview.get("identity_id") or ""),
                status="failed",
                risk_tier=str(plan_snapshot.get("risk_tier", "")),
                approval_required=bool(plan_snapshot.get("approval_required", False)),
                step_count=len(_mapping_list(plan_snapshot.get("steps"))),
                goal_hash=_plan_snapshot_goal_hash(plan_snapshot, preview),
                evidence_required=_text_tuple(plan_snapshot.get("evidence_required")),
                budget=budget,
                tools_count=_plan_snapshot_tools_count(plan_snapshot, preview),
                witness_id=str(witness.get("witness_id", "")),
                recovery_action=str(recovery_decision.get("recovery_action", "")),
                recovery_reason=str(recovery_decision.get("reason", "")),
                latest_at=str(witness.get("witnessed_at", "")),
            )
        )
    return rows


def _plan_review_recovery_attempt_rows(
    ledger_model: Mapping[str, Any],
    preview_by_plan: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failed_by_plan = {
        str(witness.get("plan_id", "")): witness
        for witness in _mapping_list(ledger_model.get("failed_plan_witnesses"))
        if str(witness.get("plan_id", "")).strip()
    }
    rows: list[dict[str, Any]] = []
    for attempt in _mapping_list(ledger_model.get("recovery_attempts")):
        plan_id = str(attempt.get("plan_id", "")).strip()
        if not plan_id:
            continue
        witness = failed_by_plan.get(plan_id, {})
        detail = witness.get("detail") if isinstance(witness, Mapping) else {}
        if not isinstance(detail, Mapping):
            detail = {}
        plan_snapshot = detail.get("plan_snapshot")
        if not isinstance(plan_snapshot, Mapping):
            plan_snapshot = {}
        preview = preview_by_plan.get(plan_id, {})
        budget = _budget_from_preview_record_or_snapshot(
            preview_record=preview,
            plan_snapshot=plan_snapshot,
            fallback_state="witness_plan_snapshot" if plan_snapshot else "not_recorded",
        )
        rows.append(
            _plan_review_row(
                review_id=str(attempt.get("attempt_id", "")),
                review_type="recovery_attempt",
                plan_id=plan_id,
                preview_id=str(preview.get("preview_id", "")),
                tenant_id=str(plan_snapshot.get("tenant_id") or preview.get("tenant_id") or ""),
                identity_id=str(plan_snapshot.get("identity_id") or preview.get("identity_id") or ""),
                status=_plan_review_recovery_status(str(attempt.get("status", ""))),
                risk_tier=str(plan_snapshot.get("risk_tier", "")),
                approval_required=bool(plan_snapshot.get("approval_required", False)),
                step_count=len(_mapping_list(plan_snapshot.get("steps"))),
                goal_hash=_plan_snapshot_goal_hash(plan_snapshot, preview),
                evidence_required=_text_tuple(plan_snapshot.get("evidence_required")),
                budget=budget,
                tools_count=_plan_snapshot_tools_count(plan_snapshot, preview),
                attempt_id=str(attempt.get("attempt_id", "")),
                witness_id=str(attempt.get("witness_id", "")),
                certificate_id=str(attempt.get("terminal_certificate_id", "")),
                recovery_action=str(attempt.get("recovery_action", "")),
                recovery_reason=str(attempt.get("reason", "")),
                latest_at=str(attempt.get("attempted_at", "")),
            )
        )
    return rows


def _plan_review_row(
    *,
    review_id: str,
    review_type: str,
    plan_id: str,
    preview_id: str,
    tenant_id: str,
    identity_id: str,
    status: str,
    risk_tier: str,
    approval_required: bool,
    step_count: int,
    goal_hash: str,
    evidence_required: tuple[str, ...],
    budget: Mapping[str, Any],
    tools_count: int,
    latest_at: str,
    certificate_id: str = "",
    witness_id: str = "",
    attempt_id: str = "",
    recovery_action: str = "",
    recovery_reason: str = "",
) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "review_type": review_type,
        "plan_id": plan_id,
        "preview_id": preview_id,
        "tenant_id": tenant_id,
        "identity_id": identity_id,
        "status": status if status in _PLAN_REVIEW_STATUSES else "blocked",
        "risk_tier": risk_tier,
        "approval_required": approval_required,
        "step_count": max(0, int(step_count)),
        "goal_hash": goal_hash,
        "evidence_required": list(evidence_required),
        "evidence_required_count": len(evidence_required),
        "budget_required": bool(budget.get("budget_required", False)),
        "budget_gate": str(budget.get("budget_gate", "not_recorded")),
        "estimate_state": str(budget.get("estimate_state", "not_recorded")),
        "estimate_source": str(budget.get("estimate_source", "not_recorded")),
        "estimated_cost_units": budget.get("estimated_cost_units"),
        "used_cost_units": float(budget.get("used_cost_units", 0) or 0),
        "used_cost_source": str(budget.get("used_cost_source", "not_recorded")),
        "limit_cost_units": budget.get("limit_cost_units"),
        "remaining_cost_units": budget.get("remaining_cost_units"),
        "budget_report_href": _budget_report_href(tenant_id),
        "currency": str(budget.get("currency", "cost_units")),
        "required_by_steps": list(_text_tuple(budget.get("required_by_steps"))),
        "not_required_by_steps": list(_text_tuple(budget.get("not_required_by_steps"))),
        "execution_spend_allowed": bool(budget.get("execution_spend_allowed", False)),
        "budget_evidence_state": str(budget.get("budget_evidence_state", "not_recorded")),
        "tools_count": max(0, int(tools_count)),
        "certificate_id": certificate_id,
        "witness_id": witness_id,
        "attempt_id": attempt_id,
        "recovery_action": recovery_action,
        "recovery_reason": recovery_reason,
        "latest_at": latest_at,
        "review_href": _plan_review_detail_href(plan_id, tenant_id),
        "receipt_export_href": _plan_receipt_export_href(plan_id),
        "closure_href": _plan_closure_href(plan_id) if certificate_id else "",
    }


def _plan_review_preview_status(record: Mapping[str, Any]) -> str:
    status = str(record.get("status", "")).strip()
    decision = str(record.get("decision", "")).strip()
    if decision == "denied":
        return "denied"
    if status in _PLAN_REVIEW_STATUSES:
        return status
    return "blocked" if status == "blocked" else "preview_ready"


def _plan_review_recovery_status(status: str) -> str:
    if status == "succeeded":
        return "recovered"
    if status == "rejected":
        return "recovery_rejected"
    return "recovery_pending"


def _budget_from_preview_record_or_snapshot(
    *,
    preview_record: Mapping[str, Any],
    plan_snapshot: Mapping[str, Any],
    fallback_state: str,
) -> dict[str, Any]:
    preview = preview_record.get("preview")
    if isinstance(preview, Mapping):
        budget = preview.get("budget")
        if isinstance(budget, Mapping):
            return _budget_from_mapping(budget, "preview_budget")
    if plan_snapshot:
        metadata = plan_snapshot.get("metadata")
        if isinstance(metadata, Mapping):
            contracts = _mapping_list(metadata.get("step_contracts"))
            if contracts:
                return _budget_from_step_contracts(contracts, "witness_plan_snapshot")
    return _budget_not_recorded(fallback_state)


def _budget_from_mapping(value: Any, evidence_state: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return _budget_not_recorded("not_recorded")
    budget = dict(value)
    budget["budget_evidence_state"] = evidence_state
    return _normalized_budget(budget)


def _budget_from_step_contracts(
    step_contracts: list[Mapping[str, Any]],
    evidence_state: str,
) -> dict[str, Any]:
    budget_contracts = tuple(
        contract
        for contract in step_contracts
        if "budget_reserved" in _text_tuple(contract.get("requires"))
    )
    budget_step_ids = tuple(
        str(contract.get("step_id", ""))
        for contract in budget_contracts
    )
    all_step_ids = tuple(str(contract.get("step_id", "")) for contract in step_contracts)
    not_required_step_ids = tuple(step_id for step_id in all_step_ids if step_id not in budget_step_ids)
    budget_required = bool(budget_step_ids)
    cost_estimates = tuple(
        estimate
        for estimate in (
            _nullable_number(contract.get("max_estimated_cost_units"))
            for contract in budget_contracts
        )
        if estimate is not None
    )
    unknown_estimate_count = max(0, len(budget_contracts) - len(cost_estimates))
    estimated_cost_units = sum(cost_estimates) if cost_estimates else None
    estimate_state = "not_required"
    estimate_source = "capability_passport"
    if budget_required and estimated_cost_units is None:
        estimate_state = "not_calculated"
        estimate_source = "runtime_budget_gate_required"
    elif budget_required and unknown_estimate_count:
        estimate_state = "partial"
        estimate_source = "capability_cost_model"
    elif budget_required:
        estimate_state = "estimated"
        estimate_source = "capability_cost_model"
    return _normalized_budget(
        {
            "budget_required": budget_required,
            "budget_gate": "budget_reserved" if budget_required else "not_required",
            "estimate_state": estimate_state,
            "estimate_source": estimate_source,
            "estimated_cost_units": estimated_cost_units,
            "used_cost_units": 0,
            "used_cost_source": "preview_execution_not_started",
            "limit_cost_units": None,
            "remaining_cost_units": None,
            "currency": "cost_units",
            "required_by_steps": list(budget_step_ids),
            "not_required_by_steps": list(not_required_step_ids),
            "execution_spend_allowed": False,
            "budget_evidence_state": evidence_state,
        }
    )


def _budget_not_recorded(evidence_state: str) -> dict[str, Any]:
    return _normalized_budget(
        {
            "budget_required": False,
            "budget_gate": "not_recorded",
            "estimate_state": "not_recorded",
            "estimate_source": "not_recorded",
            "estimated_cost_units": None,
            "used_cost_units": 0,
            "used_cost_source": "not_recorded",
            "limit_cost_units": None,
            "remaining_cost_units": None,
            "currency": "cost_units",
            "required_by_steps": [],
            "not_required_by_steps": [],
            "execution_spend_allowed": False,
            "budget_evidence_state": evidence_state,
        }
    )


def _normalized_budget(budget: Mapping[str, Any]) -> dict[str, Any]:
    budget_gate = str(budget.get("budget_gate", "not_recorded"))
    if budget_gate not in _PLAN_BUDGET_GATES:
        budget_gate = "not_recorded"
    return {
        "budget_required": bool(budget.get("budget_required", False)),
        "budget_gate": budget_gate,
        "estimate_state": str(budget.get("estimate_state", "not_recorded")),
        "estimate_source": str(budget.get("estimate_source", "not_recorded")),
        "estimated_cost_units": _nullable_number(budget.get("estimated_cost_units")),
        "used_cost_units": float(budget.get("used_cost_units", 0) or 0),
        "used_cost_source": str(budget.get("used_cost_source", "not_recorded")),
        "limit_cost_units": _nullable_number(budget.get("limit_cost_units")),
        "remaining_cost_units": _nullable_number(budget.get("remaining_cost_units")),
        "currency": str(budget.get("currency", "cost_units")),
        "required_by_steps": list(_text_tuple(budget.get("required_by_steps"))),
        "not_required_by_steps": list(_text_tuple(budget.get("not_required_by_steps"))),
        "execution_spend_allowed": bool(budget.get("execution_spend_allowed", False)),
        "budget_evidence_state": str(budget.get("budget_evidence_state", "not_recorded")),
    }


def _plan_review_rows_with_tenant_budget_reports(
    rows: list[dict[str, Any]],
    tenant_budget_reporter: Any | None,
) -> list[dict[str, Any]]:
    if tenant_budget_reporter is None:
        return rows
    report_cache: dict[str, Mapping[str, Any] | None] = {}
    enriched_rows: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        tenant_id = str(enriched.get("tenant_id", "")).strip()
        if not tenant_id:
            enriched_rows.append(enriched)
            continue
        if tenant_id not in report_cache:
            report_cache[tenant_id] = _tenant_budget_report(
                tenant_budget_reporter,
                tenant_id,
            )
        report = report_cache[tenant_id]
        if report is None:
            enriched_rows.append(enriched)
            continue
        enriched_rows.append(_plan_review_row_with_tenant_budget_report(enriched, report))
    return enriched_rows


def _tenant_budget_report(
    tenant_budget_reporter: Any,
    tenant_id: str,
) -> Mapping[str, Any] | None:
    try:
        report_func = getattr(tenant_budget_reporter, "report", None)
        if callable(report_func):
            return _dataclass_mapping(report_func(tenant_id))
        if callable(tenant_budget_reporter):
            return _dataclass_mapping(tenant_budget_reporter(tenant_id))
    except Exception as exc:
        return {"_budget_report_error": type(exc).__name__}
    return None


def _budget_report_row(
    tenant_id: str,
    report: Mapping[str, Any] | None,
    tenant_budget_reporter: Any | None,
) -> dict[str, Any]:
    base = {
        "tenant_id": tenant_id,
        "status": "tenant_required" if not tenant_id else "not_configured",
        "budget_id": "",
        "spent_cost_units": None,
        "limit_cost_units": None,
        "remaining_cost_units": None,
        "calls_made": None,
        "max_calls": None,
        "exhausted": False,
        "enabled": False,
        "utilization_percent": None,
    }
    if tenant_budget_reporter is None:
        return base
    if report is None:
        return {**base, "status": "unavailable" if tenant_id else "tenant_required"}
    if report.get("_budget_report_error"):
        return {**base, "status": "report_error"}
    spent = _nullable_number(report.get("spent"))
    limit = _nullable_number(report.get("max_cost"))
    remaining = _nullable_number(report.get("remaining"))
    utilization = None
    if spent is not None and limit is not None and limit > 0:
        utilization = round((spent / limit) * 100, 6)
    return {
        "tenant_id": tenant_id,
        "status": "available",
        "budget_id": str(report.get("tenant_id", tenant_id)),
        "spent_cost_units": spent,
        "limit_cost_units": limit,
        "remaining_cost_units": remaining,
        "calls_made": _nullable_integer(report.get("calls_made")),
        "max_calls": _nullable_integer(report.get("max_calls")),
        "exhausted": bool(report.get("exhausted", False)),
        "enabled": bool(report.get("enabled", True)),
        "utilization_percent": utilization,
    }


def _plan_review_row_with_tenant_budget_report(
    row: dict[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    if report.get("_budget_report_error"):
        return {
            **row,
            "used_cost_source": "tenant_budget_report_error",
            "budget_evidence_state": "tenant_budget_report_error",
        }
    used = _nullable_number(report.get("spent"))
    limit = _nullable_number(report.get("max_cost"))
    remaining = _nullable_number(report.get("remaining"))
    if used is None and limit is None and remaining is None:
        return row
    return {
        **row,
        "used_cost_units": used if used is not None else row.get("used_cost_units", 0),
        "used_cost_source": "tenant_budget_report",
        "limit_cost_units": limit,
        "remaining_cost_units": remaining,
        "budget_evidence_state": "tenant_budget_report",
    }


def _nullable_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nullable_integer(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _plan_snapshot_goal_hash(
    plan_snapshot: Mapping[str, Any],
    preview_record: Mapping[str, Any],
) -> str:
    goal_hash = str(preview_record.get("goal_hash", "")).strip()
    if goal_hash:
        return goal_hash
    goal = str(plan_snapshot.get("goal", "")).strip()
    return _stable_hash({"goal": goal}) if goal else ""


def _preview_tools_count(preview_record: Mapping[str, Any]) -> int:
    preview = preview_record.get("preview")
    if isinstance(preview, Mapping):
        return len(_mapping_list(preview.get("tools")))
    return 0


def _plan_snapshot_tools_count(
    plan_snapshot: Mapping[str, Any],
    preview_record: Mapping[str, Any],
) -> int:
    preview_count = _preview_tools_count(preview_record)
    if preview_count:
        return preview_count
    metadata = plan_snapshot.get("metadata")
    if isinstance(metadata, Mapping):
        contracts = _mapping_list(metadata.get("step_contracts"))
        if contracts:
            return len(contracts)
    return len(_mapping_list(plan_snapshot.get("steps")))


def _plan_review_matches_filters(
    row: Mapping[str, Any],
    *,
    tenant_id: str,
    plan_id: str,
    status: str,
    budget_gate: str,
    search: str,
) -> bool:
    if tenant_id and str(row.get("tenant_id", "")) != tenant_id:
        return False
    if plan_id and str(row.get("plan_id", "")) != plan_id:
        return False
    if status and str(row.get("status", "")) != status:
        return False
    if budget_gate and str(row.get("budget_gate", "")) != budget_gate:
        return False
    if search and _bounded_search_text(row).find(search.lower()) < 0:
        return False
    return True


def _plan_review_status_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {status: 0 for status in _PLAN_REVIEW_STATUSES}
    for row in rows:
        status = str(row.get("status", "blocked"))
        if status not in counts:
            status = "blocked"
        counts[status] += 1
    return counts


def _plan_review_budget_gate_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {gate: 0 for gate in _PLAN_BUDGET_GATES}
    for row in rows:
        gate = str(row.get("budget_gate", "not_recorded"))
        if gate not in counts:
            gate = "not_recorded"
        counts[gate] += 1
    return counts


def _approval_history_records_for_command(
    command_ledger: Any,
    command: CommandEnvelope,
) -> list[dict[str, Any]]:
    events = [
        event
        for event in command_ledger.events_for(command.command_id)
        if isinstance(event, CommandEvent) and str(event.approval_id or "").strip()
    ]
    groups: dict[str, list[CommandEvent]] = {}
    order: list[str] = []
    for event in events:
        approval_id = str(event.approval_id or "").strip()
        if approval_id not in groups:
            groups[approval_id] = []
            order.append(approval_id)
        groups[approval_id].append(event)
    terminal_certificate = command_ledger.terminal_certificate_for(command.command_id)
    task_status = task_status_for_state(
        command.state,
        terminal_certificate_present=terminal_certificate is not None,
    )
    return [
        _approval_history_record(command, approval_id, groups[approval_id], task_status)
        for approval_id in order
    ]


def _approval_history_record(
    command: CommandEnvelope,
    approval_id: str,
    approval_events: list[CommandEvent],
    task_status: str,
) -> dict[str, Any]:
    latest = approval_events[-1]
    status = _approval_history_status(command, approval_events, task_status)
    risk_tier = next(
        (
            str(event.risk_tier)
            for event in reversed(approval_events)
            if str(event.risk_tier).strip()
        ),
        "",
    )
    resolved_at = latest.timestamp if status in {"approved", "denied", "expired"} else ""
    resolved_by = _approval_history_resolved_by(status, latest)
    strength_detail = _approval_strength_detail(approval_events)
    receipt_href = _receipt_detail_href(command.command_id, command.tenant_id)
    current_task_href = _current_task_href(command.tenant_id, task_status)
    return {
        "approval_request_id": approval_id,
        "tenant_id": command.tenant_id,
        "actor_id": command.actor_id,
        "source": command.source,
        "intent": command.intent,
        "command_id": command.command_id,
        "command_state": command.state.value,
        "task_status": task_status,
        "risk_tier": risk_tier,
        "status": status,
        "requested_at": approval_events[0].timestamp,
        "resolved_at": resolved_at,
        "resolved_by": resolved_by,
        **strength_detail,
        "event_count": len(approval_events),
        "latest_event_hash": latest.event_hash,
        "trace_id": command.trace_id,
        "payload_hash": command.payload_hash,
        "receipt_href": receipt_href,
        "current_task_href": current_task_href,
    }


def _approval_strength_detail(approval_events: list[CommandEvent]) -> dict[str, Any]:
    """Return the latest approval-strength witness carried by approval events."""
    defaults: dict[str, Any] = {
        "approval_strength_policy": "",
        "approval_strength_decision": "",
        "approval_strength": "",
        "required_approval_strength": "",
        "request_channel_trust": "",
        "response_channel_trust": "",
        "cross_channel_approval": False,
        "approval_strength_reasons": (),
        "approval_strength_required_controls": (),
    }
    strength_keys = frozenset(defaults)
    for event in reversed(approval_events):
        detail = event.detail if isinstance(event.detail, Mapping) else {}
        if not any(key in detail for key in strength_keys):
            continue
        return {
            "approval_strength_policy": str(
                detail.get("approval_strength_policy", "")
            ).strip(),
            "approval_strength_decision": str(
                detail.get("approval_strength_decision", "")
            ).strip(),
            "approval_strength": str(detail.get("approval_strength", "")).strip(),
            "required_approval_strength": str(
                detail.get("required_approval_strength", "")
            ).strip(),
            "request_channel_trust": str(
                detail.get("request_channel_trust", "")
            ).strip(),
            "response_channel_trust": str(
                detail.get("response_channel_trust", "")
            ).strip(),
            "cross_channel_approval": bool(detail.get("cross_channel_approval", False)),
            "approval_strength_reasons": _text_tuple(
                detail.get("approval_strength_reasons", ()),
            ),
            "approval_strength_required_controls": _text_tuple(
                detail.get("approval_strength_required_controls", ()),
            ),
        }
    return defaults


def _approval_history_status(
    command: CommandEnvelope,
    approval_events: list[CommandEvent],
    task_status: str,
) -> str:
    latest_state = approval_events[-1].next_state
    if latest_state in _BLOCKED_STATES:
        return "denied"
    if latest_state in _WAITING_STATES:
        return "pending"
    if latest_state in _APPROVAL_APPROVED_STATES:
        return "approved"
    if any(event.next_state in _APPROVAL_APPROVED_STATES for event in approval_events):
        return "approved"
    if command.state in _COMPLETED_STATES or task_status == "completed":
        return "approved"
    return "unknown"


def _approval_history_resolved_by(status: str, latest: CommandEvent) -> str:
    if status == "pending":
        return ""
    detail = latest.detail if isinstance(latest.detail, Mapping) else {}
    resolved_by = str(
        detail.get("resolved_by")
        or detail.get("approver_id")
        or detail.get("identity_id")
        or ""
    ).strip()
    if resolved_by:
        return resolved_by
    if status == "approved":
        return "operator_or_policy"
    if status == "denied":
        return "operator_or_policy"
    if status == "expired":
        return "timeout_or_capacity"
    return ""


def _approval_history_matches_filters(
    record: Mapping[str, Any],
    *,
    request_id: str,
    status: str,
    search: str,
) -> bool:
    if request_id and str(record.get("approval_request_id", "")) != request_id:
        return False
    if status and str(record.get("status", "")) != status:
        return False
    if search and _bounded_search_text(record).find(search.lower()) < 0:
        return False
    return True


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
        "receipt_types": _receipt_types(receipts),
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
    search_decision = _search_decision_receipt(command, events)
    if search_decision is not None:
        receipts.append(search_decision)
    search_receipt = _search_receipt(command, events)
    if search_receipt is not None:
        receipts.append(search_receipt)
    plan_step = _plan_step_receipt(command)
    if plan_step is not None:
        receipts.append(plan_step)
    receipts.extend(_approval_receipts(command, events))
    receipts.extend(_denial_receipts(command, events))
    worker = _worker_receipt(
        command_ledger,
        command,
        events=events,
        terminal_certificate=terminal_certificate,
    )
    if worker is not None:
        receipts.append(worker)
    worker_failure = _worker_failure_receipt(command, events)
    if worker_failure is not None:
        receipts.append(worker_failure)
    delivery = _delivery_receipt(
        command,
        events=events,
        terminal_certificate=terminal_certificate,
    )
    if delivery is not None:
        receipts.append(delivery)
    receipts.extend(_event_receipt(event) for event in events)
    proof = universal_command_proof_view(command_ledger, command.command_id)
    if proof is not None:
        receipts.append(_universal_action_proof_receipt(proof))
    if terminal_certificate is not None:
        receipts.append(_terminal_certificate_receipt(terminal_certificate))
    return receipts


def _receipt_types(receipts: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for receipt in receipts:
        receipt_type = str(receipt.get("receipt_type", "")).strip()
        if not receipt_type or receipt_type in seen:
            continue
        ordered.append(receipt_type)
        seen.add(receipt_type)
    return ordered


def _receipt_matches_filters(
    receipt: Mapping[str, Any],
    *,
    receipt_type: str,
    receipt_status: str,
    search: str,
) -> bool:
    if receipt_type and str(receipt.get("receipt_type", "")) != receipt_type:
        return False
    if receipt_status and str(receipt.get("status", "")) != receipt_status:
        return False
    if search and _bounded_search_text(receipt).find(search.lower()) < 0:
        return False
    return True


def _receipt_group_search_text(row: Mapping[str, Any]) -> str:
    fields = {
        "command_id": row.get("command_id", ""),
        "tenant_id": row.get("tenant_id", ""),
        "actor_id": row.get("actor_id", ""),
        "source": row.get("source", ""),
        "intent": row.get("intent", ""),
        "command_state": row.get("command_state", ""),
        "task_status": row.get("task_status", ""),
        "payload_hash": row.get("payload_hash", ""),
        "trace_id": row.get("trace_id", ""),
        "latest_event_hash": row.get("latest_event_hash", ""),
        "receipt_types": row.get("receipt_types", ()),
    }
    return _bounded_search_text(fields)


def _bounded_search_text(value: Any) -> str:
    return json.dumps(
        _json_safe_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).lower()


def _plan_step_receipt(command: CommandEnvelope) -> dict[str, Any] | None:
    metadata = _command_metadata(command)
    plan_id = _metadata_text(metadata, "plan_id", "recovered_plan_id")
    plan_step_id = _metadata_text(metadata, "plan_step_id")
    if not plan_id and not plan_step_id:
        return None
    goal_intake_preview_id = _metadata_text(
        metadata,
        "goal_intake_preview_id",
        "preview_id",
    )
    goal_hash = _metadata_text(metadata, "goal_hash")
    details = {
        "command_id": command.command_id,
        "plan_id": plan_id,
        "plan_step_id": plan_step_id,
        "depends_on": list(_text_tuple(metadata.get("depends_on"))),
        "completed_step_count": len(_text_tuple(metadata.get("completed_steps"))),
        "goal_intake_preview_id": goal_intake_preview_id,
        "goal_hash_present": bool(goal_hash),
    }
    evidence_refs = {
        "plan_id": plan_id,
        "plan_step_id": plan_step_id,
        "command_id": command.command_id,
        "payload_hash": command.payload_hash,
        "trace_id": command.trace_id,
        "goal_intake_preview_id": goal_intake_preview_id,
        "goal_hash": goal_hash,
    }
    receipt_hash = _stable_hash(
        {"details": details, "evidence_refs": evidence_refs}
    )
    return {
        "receipt_type": "plan_step_receipt",
        "receipt_id": f"plan-step:{command.command_id}:{plan_id}:{plan_step_id}",
        "receipt_hash": receipt_hash,
        "status": task_status_for_state(command.state),
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _approval_receipts(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> list[dict[str, Any]]:
    approval_event_groups: dict[str, list[CommandEvent]] = {}
    approval_order: list[str] = []
    for event in events:
        approval_id = str(event.approval_id or "").strip()
        if not approval_id:
            continue
        if approval_id not in approval_event_groups:
            approval_event_groups[approval_id] = []
            approval_order.append(approval_id)
        approval_event_groups[approval_id].append(event)
    return [
        _approval_receipt(command, approval_id, approval_event_groups[approval_id])
        for approval_id in approval_order
    ]


def _approval_receipt(
    command: CommandEnvelope,
    approval_id: str,
    approval_events: list[CommandEvent],
) -> dict[str, Any]:
    latest = approval_events[-1]
    risk_tier = next(
        (
            str(event.risk_tier)
            for event in reversed(approval_events)
            if str(event.risk_tier).strip()
        ),
        "",
    )
    details = {
        "approval_request_id": approval_id,
        "risk_tier": risk_tier,
        "command_id": command.command_id,
        "event_count": len(approval_events),
        "latest_state": latest.next_state.value,
    }
    evidence_refs = {
        "approval_request_id": approval_id,
        "latest_event_hash": latest.event_hash,
        "command_id": command.command_id,
        "payload_hash": command.payload_hash,
        "trace_id": command.trace_id,
    }
    receipt_hash = _stable_hash(
        {"details": details, "evidence_refs": evidence_refs}
    )
    return {
        "receipt_type": "approval_receipt",
        "receipt_id": f"approval:{approval_id}",
        "receipt_hash": receipt_hash,
        "status": _approval_receipt_status(command, approval_events),
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _approval_receipt_status(
    command: CommandEnvelope,
    approval_events: list[CommandEvent],
) -> str:
    latest_state = approval_events[-1].next_state
    if latest_state in _BLOCKED_STATES:
        return "denied"
    if latest_state in _WAITING_STATES:
        return "pending"
    if latest_state in _APPROVAL_APPROVED_STATES:
        return "approved"
    if any(event.next_state in _APPROVAL_APPROVED_STATES for event in approval_events):
        return "approved"
    if command.state in _COMPLETED_STATES:
        return "approved"
    return latest_state.value


def _denial_receipts(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for event in events:
        if event.next_state not in _BLOCKED_STATES:
            continue
        detail = event.detail if isinstance(event.detail, Mapping) else {}
        details = {
            "command_id": command.command_id,
            "previous_state": event.previous_state.value,
            "next_state": event.next_state.value,
            "cause": str(detail.get("cause", "")),
            "risk_tier": str(event.risk_tier or ""),
        }
        evidence_refs = {
            "event_hash": event.event_hash,
            "command_id": command.command_id,
            "approval_request_id": str(event.approval_id or ""),
            "payload_hash": command.payload_hash,
            "trace_id": command.trace_id,
        }
        receipt_hash = _stable_hash(
            {"details": details, "evidence_refs": evidence_refs}
        )
        receipts.append(
            {
                "receipt_type": "denial_receipt",
                "receipt_id": f"denial:{event.event_id}",
                "receipt_hash": receipt_hash,
                "status": event.next_state.value,
                "details": details,
                "evidence_refs": evidence_refs,
            }
        )
    return receipts


def _worker_receipt(
    command_ledger: Any,
    command: CommandEnvelope,
    *,
    events: list[CommandEvent],
    terminal_certificate: Any | None,
) -> dict[str, Any] | None:
    capability_intent = _capability_intent(command)
    governed_action = _governed_action(command_ledger, command.command_id)
    dispatch_event = _latest_event_with_state(
        events,
        {
            CommandState.DISPATCHED,
            CommandState.EFFECT_OBSERVED,
            CommandState.OBSERVED,
            CommandState.VERIFIED,
            CommandState.RECONCILED,
            CommandState.COMMITTED,
            CommandState.RESPONDED,
        },
    )
    tool_names = tuple(
        sorted({str(event.tool_name) for event in events if str(event.tool_name).strip()})
    )
    if capability_intent is None and governed_action is None and not tool_names:
        return None

    params = (
        capability_intent.get("params")
        if isinstance(capability_intent, Mapping)
        else None
    )
    if not isinstance(params, Mapping):
        params = {}
    capability_id = _first_text(
        capability_intent.get("capability_id") if isinstance(capability_intent, Mapping) else "",
        getattr(governed_action, "capability", ""),
        command.intent,
    )
    domain, action_name = _capability_parts(capability_id)
    domain = _first_text(
        capability_intent.get("domain") if isinstance(capability_intent, Mapping) else "",
        domain,
    )
    action_name = _first_text(
        capability_intent.get("action") if isinstance(capability_intent, Mapping) else "",
        action_name,
    )
    terminal_certificate_id = _terminal_certificate_id(terminal_certificate)
    details = {
        "command_id": command.command_id,
        "capability_id": capability_id,
        "domain": domain,
        "action": action_name,
        "param_names": sorted(str(name) for name in params),
        "params_hash": _stable_hash(params) if params else "",
        "risk_tier": str(getattr(governed_action, "risk_tier", "")),
        "authority_required": list(getattr(governed_action, "authority_required", ())),
        "dispatch_state": command.state.value,
        "tool_names": list(tool_names),
        "terminal_certificate_id": terminal_certificate_id,
    }
    evidence_refs = {
        "command_id": command.command_id,
        "trace_id": command.trace_id,
        "payload_hash": command.payload_hash,
        "intent_hash": str(getattr(governed_action, "intent_hash", "")),
        "capability_passport_hash": str(
            getattr(governed_action, "capability_passport_hash", "")
        ),
        "latest_dispatch_event_hash": dispatch_event.event_hash if dispatch_event else "",
        "terminal_certificate_id": terminal_certificate_id,
    }
    receipt_hash = _stable_hash(
        {"details": details, "evidence_refs": evidence_refs}
    )
    return {
        "receipt_type": "worker_receipt",
        "receipt_id": f"worker:{command.command_id}:{capability_id}",
        "receipt_hash": receipt_hash,
        "status": (
            "terminal_certificate_present"
            if terminal_certificate_id
            else "dispatch_not_terminal"
        ),
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _worker_failure_receipt(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> dict[str, Any] | None:
    raw_receipt, source_event = _raw_worker_failure_receipt(command, events)
    if not isinstance(raw_receipt, Mapping):
        return None
    details = {
        key: _json_safe_value(raw_receipt[key])
        for key in (
            "schema_ref",
            "receipt_id",
            "worker_receipt_id",
            "request_id",
            "command_id",
            "capability",
            "operation",
            "tenant_id",
            "lease_id",
            "failure_state",
            "reason",
            "partial_completion",
            "attempted_units",
            "completed_units",
            "recovery_action",
            "recovery_ref",
            "terminal_closure_required",
            "receipt_is_not_terminal_closure",
            "generated_at",
            "metadata",
            "receipt_state",
            "worker_dispatch_ref",
            "failure_class",
            "effect_status",
            "recovery_action_refs",
        )
        if key in raw_receipt
    }
    metadata = raw_receipt.get("metadata") if isinstance(raw_receipt.get("metadata"), Mapping) else {}
    status = _worker_failure_status(raw_receipt)
    receipt_id = str(
        details.get("receipt_id")
        or command.redacted_payload.get("worker_failure_receipt_id")
        or f"worker-failure:{command.command_id}"
    )
    evidence_refs = {
        "command_id": command.command_id,
        "worker_failure_receipt_id": receipt_id,
        "worker_receipt_id": str(details.get("worker_receipt_id", "")),
        "worker_dispatch_ref": str(details.get("worker_dispatch_ref", "")),
        "source_receipt_hash": str(raw_receipt.get("source_receipt_hash") or metadata.get("source_receipt_hash") or ""),
        "failure_hash": str(raw_receipt.get("failure_hash") or metadata.get("failure_hash") or ""),
        "source_event_hash": source_event.event_hash if source_event is not None else "",
        "payload_hash": command.payload_hash,
        "trace_id": command.trace_id,
        "evidence_refs": list(raw_receipt.get("evidence_refs", ()))
        if isinstance(raw_receipt.get("evidence_refs"), list)
        else [],
    }
    receipt_hash = str(evidence_refs["failure_hash"]) or _stable_hash(
        {"details": details, "evidence_refs": evidence_refs}
    )
    return {
        "receipt_type": "worker_failure_receipt",
        "receipt_id": receipt_id,
        "receipt_hash": receipt_hash,
        "status": status,
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _raw_worker_failure_receipt(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> tuple[Mapping[str, Any] | None, CommandEvent | None]:
    raw_payload_receipt = command.redacted_payload.get("worker_failure_receipt")
    if isinstance(raw_payload_receipt, Mapping):
        return raw_payload_receipt, None
    for event in reversed(events):
        raw_detail = event.detail if isinstance(event.detail, Mapping) else {}
        raw_detail_receipt = raw_detail.get("worker_failure_receipt")
        if isinstance(raw_detail_receipt, Mapping):
            return raw_detail_receipt, event
        raw_execution = raw_detail.get("execution_result")
        if isinstance(raw_execution, Mapping):
            raw_execution_output = raw_execution.get("output")
            if isinstance(raw_execution_output, Mapping):
                raw_execution_receipt = raw_execution_output.get("worker_failure_receipt")
                if isinstance(raw_execution_receipt, Mapping):
                    return raw_execution_receipt, event
    return None, None


def _worker_failure_status(raw_receipt: Mapping[str, Any]) -> str:
    if not raw_receipt:
        return ""
    failure_state = str(raw_receipt.get("failure_state") or "").strip()
    if failure_state:
        return failure_state
    receipt_state = str(raw_receipt.get("receipt_state") or "").strip().lower()
    if receipt_state == "partial_execution_recorded":
        return "partial_completion"
    if receipt_state:
        return receipt_state
    return "recorded"


def _worker_failure_recovery_action(raw_receipt: Mapping[str, Any]) -> str:
    recovery_action = str(raw_receipt.get("recovery_action") or "").strip()
    if recovery_action:
        return recovery_action
    recovery_refs = raw_receipt.get("recovery_action_refs")
    if isinstance(recovery_refs, list) and recovery_refs:
        return "safe_halt"
    return ""


def _delivery_receipt(
    command: CommandEnvelope,
    *,
    events: list[CommandEvent],
    terminal_certificate: Any | None,
) -> dict[str, Any] | None:
    delivery_event = _latest_event_with_detail(events, "delivery_status")
    response_event = _latest_event_with_state(events, {CommandState.RESPONDED})
    delivery_status = ""
    if delivery_event is not None:
        delivery_status = str(delivery_event.detail.get("delivery_status", "")).strip()
    metadata = _command_metadata(command)
    if not delivery_status:
        delivery_status = _metadata_text(metadata, "delivery_status")
    if (
        not delivery_status
        and response_event is None
        and terminal_certificate is None
        and command.state not in _COMPLETED_STATES
    ):
        return None

    terminal_certificate_id = _terminal_certificate_id(terminal_certificate)
    delivery_detail = delivery_event.detail if delivery_event is not None else {}
    execution_status = str(delivery_detail.get("execution_status") or "").strip()
    if not execution_status:
        execution_status = (
            "terminal_certified"
            if terminal_certificate_id
            else (
                "response_recorded"
                if response_event is not None or command.state in _COMPLETED_STATES
                else "not_closed"
            )
        )
    delivery_error_type = str(delivery_detail.get("delivery_error_type") or "").strip()
    delivery_succeeded = bool(delivery_detail.get("delivery_succeeded")) if delivery_event is not None else False
    delivery_attempted = bool(delivery_detail.get("delivery_attempted")) if delivery_event is not None else False
    status = delivery_status or "delivery_status_not_recorded"
    latest_event = delivery_event or response_event or (events[-1] if events else None)
    details = {
        "command_id": command.command_id,
        "execution_status": execution_status,
        "delivery_status": delivery_status,
        "delivery_error_type": delivery_error_type,
        "delivery_succeeded": delivery_succeeded,
        "delivery_attempted": delivery_attempted,
        "execution_delivery_separated": bool(
            delivery_detail.get("execution_delivery_separated")
        ),
        "response_recorded": response_event is not None,
        "delivery_status_observed": bool(delivery_status),
        "terminal_certificate_present": terminal_certificate is not None,
        "terminal_certificate_id": terminal_certificate_id,
    }
    evidence_refs = {
        "command_id": command.command_id,
        "latest_event_hash": latest_event.event_hash if latest_event else "",
        "delivery_event_hash": delivery_event.event_hash if delivery_event else "",
        "response_event_hash": response_event.event_hash if response_event else "",
        "terminal_certificate_id": terminal_certificate_id,
    }
    receipt_hash = _stable_hash(
        {"details": details, "evidence_refs": evidence_refs}
    )
    return {
        "receipt_type": "delivery_receipt",
        "receipt_id": f"delivery:{command.command_id}",
        "receipt_hash": receipt_hash,
        "status": status,
        "details": details,
        "evidence_refs": evidence_refs,
    }


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


def _search_decision_receipt(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> dict[str, Any] | None:
    raw_receipt, source_event = _raw_search_decision_receipt(command, events)
    if not isinstance(raw_receipt, Mapping):
        return None
    details = {
        key: _json_safe_value(raw_receipt[key])
        for key in (
            "schema_ref",
            "receipt_id",
            "tenant_id",
            "actor_id",
            "capability_id",
            "query_hash",
            "search_classification",
            "freshness_state",
            "budget_state",
            "retrieval_authority",
            "retrieval_instruction_authority_allowed",
            "decision",
            "blocked_reasons",
            "estimated_cost_units",
            "budget_limit_units",
            "max_result_count",
            "generated_at",
            "metadata",
        )
        if key in raw_receipt
    }
    receipt_id = str(
        details.get("receipt_id")
        or command.redacted_payload.get("search_decision_receipt_id")
        or f"search-decision:{command.command_id}"
    )
    evidence_refs = {
        "command_id": command.command_id,
        "receipt_hash": str(raw_receipt.get("receipt_hash", "")),
        "query_hash": str(details.get("query_hash", "")),
        "capability_id": str(details.get("capability_id", "")),
        "source_event_hash": source_event.event_hash if source_event is not None else "",
        "payload_hash": command.payload_hash,
        "trace_id": command.trace_id,
    }
    receipt_hash = str(raw_receipt.get("receipt_hash", "")) or _stable_hash(
        {"details": details, "evidence_refs": evidence_refs}
    )
    return {
        "receipt_type": "search_decision_receipt",
        "receipt_id": receipt_id,
        "receipt_hash": receipt_hash,
        "status": str(details.get("decision") or "recorded"),
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _raw_search_decision_receipt(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> tuple[Mapping[str, Any] | None, CommandEvent | None]:
    raw_payload_receipt = command.redacted_payload.get("search_decision_receipt")
    if isinstance(raw_payload_receipt, Mapping):
        return raw_payload_receipt, None
    for event in reversed(events):
        raw_detail = event.detail if isinstance(event.detail, Mapping) else {}
        raw_detail_receipt = raw_detail.get("search_decision_receipt")
        if isinstance(raw_detail_receipt, Mapping):
            return raw_detail_receipt, event
        raw_execution = raw_detail.get("execution_result")
        if isinstance(raw_execution, Mapping):
            raw_execution_output = raw_execution.get("output")
            if isinstance(raw_execution_output, Mapping):
                raw_execution_receipt = raw_execution_output.get("search_decision_receipt")
                if isinstance(raw_execution_receipt, Mapping):
                    return raw_execution_receipt, event
    return None, None


def _search_receipt(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> dict[str, Any] | None:
    raw_receipt, source_event, raw_receipt_hash = _raw_search_receipt(command, events)
    if not isinstance(raw_receipt, Mapping):
        return None
    details = _search_receipt_details(raw_receipt)
    receipt_id = str(
        details.get("receipt_id")
        or command.redacted_payload.get("search_receipt_id")
        or f"search-receipt:{command.command_id}"
    )
    receipt_hash = raw_receipt_hash or _stable_hash(
        {"details": details, "command_id": command.command_id}
    )
    evidence_refs = {
        "command_id": command.command_id,
        "receipt_hash": receipt_hash,
        "search_decision_ref": str(details.get("search_decision_ref", "")),
        "request_id": str(details.get("request_id", "")),
        "source_event_hash": source_event.event_hash if source_event is not None else "",
        "payload_hash": command.payload_hash,
        "trace_id": command.trace_id,
        "citation_refs": list(_text_tuple(raw_receipt.get("citation_refs"))),
        "conflict_refs": list(_text_tuple(raw_receipt.get("conflict_refs"))),
        "stale_source_refs": list(_text_tuple(raw_receipt.get("stale_source_refs"))),
        "receipt_evidence_refs": list(_text_tuple(raw_receipt.get("evidence_refs"))),
    }
    return {
        "receipt_type": "search_receipt",
        "receipt_id": receipt_id,
        "receipt_hash": receipt_hash,
        "status": str(
            details.get("receipt_state")
            or details.get("solver_outcome")
            or "recorded"
        ),
        "details": details,
        "evidence_refs": evidence_refs,
    }


def _search_receipt_details(raw_receipt: Mapping[str, Any]) -> dict[str, Any]:
    details = {
        key: _json_safe_value(raw_receipt[key])
        for key in (
            "receipt_id",
            "receipt_version",
            "search_decision_ref",
            "request_id",
            "tenant_id",
            "actor_id",
            "created_at",
            "solver_outcome",
            "receipt_state",
            "search_state",
            "freshness_result",
            "source_plan_result",
            "cache_result",
            "budget_result",
            "evidence_summary",
            "citation_refs",
            "conflict_refs",
            "stale_source_refs",
            "retrieval_errors",
            "retrieval_safety_result",
            "governance_guards",
            "receipt_envelope",
            "metadata",
        )
        if key in raw_receipt
    }
    details["evidence_item_refs"] = _search_receipt_evidence_item_refs(raw_receipt)
    details["raw_query_exposed"] = False
    details["source_content_body_exposed"] = False
    return details


def _search_receipt_evidence_item_refs(
    raw_receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence_items = raw_receipt.get("evidence_items")
    if not isinstance(evidence_items, list):
        return []
    panel_items: list[dict[str, Any]] = []
    for item in evidence_items:
        if not isinstance(item, Mapping):
            continue
        panel_items.append(
            {
                "evidence_ref": str(item.get("evidence_ref", "")),
                "source_type": str(item.get("source_type", "")),
                "source_ref": str(item.get("source_ref", "")),
                "citation_ref": str(item.get("citation_ref", "")),
                "freshness_status": str(item.get("freshness_status", "")),
                "trust_tier": str(item.get("trust_tier", "")),
                "content_hash_ref": str(item.get("content_hash_ref", "")),
                "content_body_included": False,
            }
        )
    return panel_items


def _raw_search_receipt(
    command: CommandEnvelope,
    events: list[CommandEvent],
) -> tuple[Mapping[str, Any] | None, CommandEvent | None, str]:
    raw_payload_receipt = command.redacted_payload.get("search_receipt")
    if isinstance(raw_payload_receipt, Mapping):
        return (
            raw_payload_receipt,
            None,
            str(command.redacted_payload.get("search_receipt_hash", "")),
        )
    for event in reversed(events):
        raw_detail = event.detail if isinstance(event.detail, Mapping) else {}
        raw_detail_receipt = raw_detail.get("search_receipt")
        if isinstance(raw_detail_receipt, Mapping):
            return (
                raw_detail_receipt,
                event,
                str(raw_detail.get("search_receipt_hash", "")),
            )
        raw_execution = raw_detail.get("execution_result")
        if isinstance(raw_execution, Mapping):
            raw_execution_output = raw_execution.get("output")
            if isinstance(raw_execution_output, Mapping):
                raw_execution_receipt = raw_execution_output.get("search_receipt")
                if isinstance(raw_execution_receipt, Mapping):
                    return (
                        raw_execution_receipt,
                        event,
                        str(raw_execution_output.get("search_receipt_hash", "")),
                    )
    return None, None, ""


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
    terminal_certificate_id = _terminal_certificate_id(terminal_certificate)
    blocker_receipt_refs = _blocker_receipt_refs(receipts)
    response_state = _response_state_for_task(
        task_status=task_status,
        terminal_certificate_id=terminal_certificate_id,
    )
    response_evidence_state = _response_evidence_state_for_task(
        task_status=task_status,
        terminal_certificate_id=terminal_certificate_id,
        blocker_receipt_refs=blocker_receipt_refs,
    )
    response_blocker = _response_blocker(
        task_status=task_status,
        terminal_certificate_id=terminal_certificate_id,
    )
    metadata = _command_metadata(command)
    worker_failure = _current_task_worker_failure(events)
    approval_request_id = _latest_approval_request_id(events)
    return {
        "command_id": command.command_id,
        "tenant_id": command.tenant_id,
        "actor_id": command.actor_id,
        "source": command.source,
        "intent": command.intent,
        "goal_intake_preview_id": _metadata_text(
            metadata,
            "goal_intake_preview_id",
            "preview_id",
        ),
        "goal_hash": _metadata_text(metadata, "goal_hash"),
        "plan_id": _metadata_text(metadata, "plan_id", "recovered_plan_id"),
        "plan_step_id": _metadata_text(metadata, "plan_step_id"),
        "approval_request_id": approval_request_id,
        "approval_recovery_available": (
            task_status == "waiting_for_approval" and bool(approval_request_id)
        ),
        "worker_failure_receipt_id": str(worker_failure.get("receipt_id", "")),
        "worker_failure_state": _worker_failure_status(worker_failure),
        "worker_failure_recovery_action": _worker_failure_recovery_action(worker_failure),
        "command_state": command.state.value,
        "task_status": task_status,
        "response_state": response_state,
        "response_evidence_state": response_evidence_state,
        "response_claim_allowed": response_state == "completed_verified",
        "response_terminal_certificate_id": terminal_certificate_id,
        "response_evidence_refs": _response_evidence_refs(
            terminal_certificate_id=terminal_certificate_id,
            blocker_receipt_refs=blocker_receipt_refs,
        ),
        "response_blocker": response_blocker,
        "task_terminal": bool(terminal_certificate_id),
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


def _command_metadata(command: CommandEnvelope) -> Mapping[str, Any]:
    metadata = command.redacted_payload.get("metadata")
    if isinstance(metadata, Mapping):
        return metadata
    return {}


def _metadata_text(
    metadata: Mapping[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    return (text,) if text else ()


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _capability_parts(capability_id: str) -> tuple[str, str]:
    if "." not in capability_id:
        return "", capability_id
    domain, action = capability_id.split(".", 1)
    return domain, action


def _capability_intent(command: CommandEnvelope) -> Mapping[str, Any] | None:
    for key in _CAPABILITY_INTENT_KEYS:
        raw_intent = command.redacted_payload.get(key)
        if isinstance(raw_intent, Mapping):
            return raw_intent
    return None


def _governed_action(command_ledger: Any, command_id: str) -> Any | None:
    lookup = getattr(command_ledger, "governed_action_for", None)
    if not callable(lookup):
        return None
    try:
        return lookup(command_id)
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def _terminal_certificate_id(certificate: Any | None) -> str:
    if certificate is None:
        return ""
    return str(_dataclass_mapping(certificate).get("certificate_id", ""))


def _latest_event_with_state(
    events: list[CommandEvent],
    states: set[CommandState],
) -> CommandEvent | None:
    for event in reversed(events):
        if event.next_state in states:
            return event
    return None


def _latest_event_with_detail(
    events: list[CommandEvent],
    detail_key: str,
) -> CommandEvent | None:
    for event in reversed(events):
        detail = event.detail if isinstance(event.detail, Mapping) else {}
        if str(detail.get(detail_key, "")).strip():
            return event
    return None


def _latest_approval_request_id(events: list[CommandEvent]) -> str:
    for event in reversed(events):
        approval_id = str(event.approval_id or "").strip()
        if approval_id:
            return approval_id
    return ""


def _current_task_worker_failure(events: list[CommandEvent]) -> Mapping[str, Any]:
    for event in reversed(events):
        detail = event.detail if isinstance(event.detail, Mapping) else {}
        receipt = detail.get("worker_failure_receipt")
        if isinstance(receipt, Mapping):
            return receipt
        execution = detail.get("execution_result")
        if isinstance(execution, Mapping):
            output = execution.get("output")
            if isinstance(output, Mapping):
                nested_receipt = output.get("worker_failure_receipt")
                if isinstance(nested_receipt, Mapping):
                    return nested_receipt
    return {}


def _command_task_status(command_ledger: Any, command: CommandEnvelope) -> str:
    return task_status_for_state(
        command.state,
        terminal_certificate_present=command_ledger.terminal_certificate_for(command.command_id)
        is not None,
    )


def _response_state_for_task(
    *,
    task_status: str,
    terminal_certificate_id: str,
) -> str:
    if terminal_certificate_id:
        return "completed_verified"
    if task_status == "completed":
        return "awaiting_terminal_evidence"
    if task_status == "blocked":
        return "blocked"
    if task_status == "waiting_for_approval":
        return "waiting_for_approval"
    if task_status == "requires_review":
        return "requires_review"
    if task_status == "active":
        return "in_progress"
    return "received"


def _response_blocker(
    *,
    task_status: str,
    terminal_certificate_id: str,
) -> str:
    if terminal_certificate_id:
        return ""
    if task_status == "completed":
        return "terminal_certificate_missing"
    if task_status == "blocked":
        return "explicit_blocker_receipt_required"
    if task_status == "waiting_for_approval":
        return "approval_required"
    if task_status == "requires_review":
        return "operator_review_required"
    return ""


def _response_evidence_state_for_task(
    *,
    task_status: str,
    terminal_certificate_id: str,
    blocker_receipt_refs: tuple[str, ...],
) -> str:
    if terminal_certificate_id:
        return "terminal_verified"
    if task_status == "completed":
        return "terminal_certificate_missing"
    if task_status == "blocked":
        if blocker_receipt_refs:
            return "blocked_with_receipt"
        return "blocked_receipt_required"
    if task_status == "waiting_for_approval":
        return "approval_pending"
    if task_status == "requires_review":
        return "operator_review_required"
    if task_status == "active":
        return "execution_in_progress"
    return "received"


def _response_evidence_refs(
    *,
    terminal_certificate_id: str,
    blocker_receipt_refs: tuple[str, ...],
) -> list[str]:
    refs = []
    if terminal_certificate_id:
        refs.append(f"terminal-certificate://{terminal_certificate_id}")
    refs.extend(blocker_receipt_refs)
    return refs


def _blocker_receipt_refs(receipts: list[dict[str, Any]]) -> tuple[str, ...]:
    refs: list[str] = []
    for receipt in receipts:
        receipt_type = str(receipt.get("receipt_type", "")).strip()
        if receipt_type not in {
            "denial_receipt",
            "worker_failure_receipt",
            "delivery_receipt",
        }:
            continue
        status = str(receipt.get("status", "")).strip()
        if receipt_type == "delivery_receipt" and status not in {"failed", "rejected"}:
            continue
        receipt_id = str(receipt.get("receipt_id", "")).strip()
        if receipt_id:
            refs.append(f"receipt://{receipt_type}/{receipt_id}")
    return tuple(refs)


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


def _bounded_int(value: Any) -> int:
    return max(0, int(value)) if isinstance(value, int) and not isinstance(value, bool) else 0


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


def _receipt_group_rows(
    records: list[Mapping[str, Any]],
    columns: tuple[str, ...],
) -> str:
    if not records:
        return f'<tr><td colspan="{len(columns)}">No command receipts</td></tr>'
    rendered: list[str] = []
    for record in records:
        cells: list[str] = []
        for column in columns:
            value = record.get(column, "")
            if column == "command_id":
                cells.append(f"<td>{_receipt_detail_link(record)}</td>")
            else:
                cells.append(f"<td>{escape(_display_value(value))}</td>")
        rendered.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(rendered)


def _receipt_detail_link(record: Mapping[str, Any]) -> str:
    command_id = str(record.get("command_id", "")).strip()
    if not command_id:
        return ""
    tenant_id = str(record.get("tenant_id", "")).strip()
    href = _receipt_detail_href(command_id, tenant_id)
    return f'<a href="{escape(href)}">{escape(command_id)}</a>'


def _receipt_detail_href(command_id: str, tenant_id: str = "") -> str:
    href = f"/operator/receipts/{quote(command_id, safe='')}"
    if tenant_id:
        href += f"?tenant_id={quote(tenant_id, safe='')}"
    return href


def _approval_detail_href(request_id: str, tenant_id: str = "") -> str:
    href = f"/operator/approvals/{quote(request_id, safe='')}"
    if tenant_id:
        href += f"?tenant_id={quote(tenant_id, safe='')}"
    return href


def _current_task_href(tenant_id: str, status: str = "") -> str:
    query = urlencode(
        {
            key: value
            for key, value in {
                "tenant_id": tenant_id,
                "status": status,
            }.items()
            if value
        }
    )
    return "/operator/current-task" + (f"?{query}" if query else "")


def _plan_review_detail_href(plan_id: str, tenant_id: str = "") -> str:
    href = f"/operator/plan-review/{quote(plan_id, safe='')}"
    if tenant_id:
        href += f"?tenant_id={quote(tenant_id, safe='')}"
    return href


def _plan_receipt_export_href(plan_id: str) -> str:
    if not plan_id:
        return ""
    return f"/operator/plan-review/{quote(plan_id, safe='')}/receipts"


def _budget_report_href(tenant_id: str) -> str:
    if not tenant_id:
        return ""
    return f"/operator/plan-review/budget/{quote(tenant_id, safe='')}"


def _plan_closure_href(plan_id: str) -> str:
    return f"/capability-plans/{quote(plan_id, safe='')}/closure"


def _increment_count(counts: dict[str, int], key: str) -> None:
    normalized_key = key.strip() or "unknown"
    counts[normalized_key] = counts.get(normalized_key, 0) + 1


def _receipt_status_key(receipt: Mapping[str, Any]) -> str:
    for key in ("receipt_status", "status", "decision"):
        value = receipt.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown"


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
        tenant_id = str(record.get("tenant_id", "")).strip()
        rendered.append(
            "<tr>"
            + "".join(_html_cell(record, column, tenant_id) for column in columns)
            + "</tr>"
        )
    return "\n".join(rendered)


def _html_cell(
    record: Mapping[str, Any],
    column: str,
    tenant_id: str,
) -> str:
    value = record.get(column, "")
    if column == "approval_request_id":
        request_id = str(value).strip()
        if request_id:
            href = _approval_detail_href(request_id, tenant_id)
            return f'<td><a href="{escape(href)}">{escape(request_id)}</a></td>'
    if column == "plan_id":
        plan_id = str(value).strip()
        href = str(record.get("review_href", "")).strip()
        if plan_id and href:
            return f'<td><a href="{escape(href)}">{escape(plan_id)}</a></td>'
    if column == "receipt_id" and str(record.get("receipt_type", "")) == "approval_receipt":
        request_id = str(value).removeprefix("approval:").strip()
        if request_id:
            href = _approval_detail_href(request_id)
            return f'<td><a href="{escape(href)}">{escape(_display_value(value))}</a></td>'
    if column.endswith("_href"):
        href = str(value).strip()
        if href:
            label = column.removesuffix("_href").replace("_", " ")
            return f'<td><a href="{escape(href)}">{escape(label)}</a></td>'
    return f"<td>{escape(_display_value(value))}</td>"


def _display_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _receipt_filter_query(read_model: Mapping[str, Any]) -> str:
    query = {
        "tenant_id": str(read_model.get("tenant_id_filter", "")).strip(),
        "command_id": str(read_model.get("command_id_filter", "")).strip(),
        "receipt_type": str(read_model.get("receipt_type_filter", "")).strip(),
        "receipt_status": str(read_model.get("receipt_status_filter", "")).strip(),
        "task_status": str(read_model.get("task_status_filter", "")).strip(),
        "search": str(read_model.get("search_filter", "")).strip(),
        "limit": str(read_model.get("limit", "")).strip(),
        "offset": str(read_model.get("offset", "")).strip(),
    }
    return urlencode({key: value for key, value in query.items() if value})


def _approval_filter_query(read_model: Mapping[str, Any]) -> str:
    query = {
        "tenant_id": str(read_model.get("tenant_id_filter", "")).strip(),
        "request_id": str(read_model.get("request_id_filter", "")).strip(),
        "command_id": str(read_model.get("command_id_filter", "")).strip(),
        "status": str(read_model.get("status_filter", "")).strip(),
        "search": str(read_model.get("search_filter", "")).strip(),
        "limit": str(read_model.get("limit", "")).strip(),
        "offset": str(read_model.get("offset", "")).strip(),
    }
    return urlencode({key: value for key, value in query.items() if value})


def _plan_review_filter_query(read_model: Mapping[str, Any]) -> str:
    query = {
        "tenant_id": str(read_model.get("tenant_id_filter", "")).strip(),
        "plan_id": str(read_model.get("plan_id_filter", "")).strip(),
        "status": str(read_model.get("status_filter", "")).strip(),
        "budget_gate": str(read_model.get("budget_gate_filter", "")).strip(),
        "search": str(read_model.get("search_filter", "")).strip(),
        "limit": str(read_model.get("limit", "")).strip(),
        "offset": str(read_model.get("offset", "")).strip(),
    }
    return urlencode({key: value for key, value in query.items() if value})


def _plan_review_filter_controls(read_model: Mapping[str, Any]) -> str:
    selected_status = str(read_model.get("status_filter", "")).strip()
    selected_budget_gate = str(read_model.get("budget_gate_filter", "")).strip()
    values = {
        "tenant_id": str(read_model.get("tenant_id_filter", "")).strip(),
        "plan_id": str(read_model.get("plan_id_filter", "")).strip(),
        "search": str(read_model.get("search_filter", "")).strip(),
        "limit": str(read_model.get("limit", 100)).strip(),
    }
    return (
        '<section class="operator-filters" aria-label="Plan Review filters">'
        "<h2>Plan Review Filters</h2>"
        '<form method="get" action="/operator/plan-review">'
        f'<label>Tenant <input name="tenant_id" value="{escape(values["tenant_id"])}"></label>'
        f'<label>Plan <input name="plan_id" value="{escape(values["plan_id"])}"></label>'
        "<label>Status "
        + _select_html(
            "status",
            _PLAN_REVIEW_STATUSES,
            selected_status,
            empty_label="any",
        )
        + "</label>"
        "<label>Budget Gate "
        + _select_html(
            "budget_gate",
            _PLAN_BUDGET_GATES,
            selected_budget_gate,
            empty_label="any",
        )
        + "</label>"
        f'<label>Search <input name="search" maxlength="{_MAX_SEARCH_FILTER_LENGTH}" value="{escape(values["search"])}"></label>'
        f'<label>Limit <input name="limit" type="number" min="1" max="{_MAX_PAGE_LIMIT}" value="{escape(values["limit"])}"></label>'
        '<button type="submit">Apply</button>'
        '<a href="/operator/plan-review">Clear</a>'
        "</form>"
        "</section>"
    )


def _approval_filter_controls(read_model: Mapping[str, Any]) -> str:
    selected_status = str(read_model.get("status_filter", "")).strip()
    values = {
        "tenant_id": str(read_model.get("tenant_id_filter", "")).strip(),
        "request_id": str(read_model.get("request_id_filter", "")).strip(),
        "command_id": str(read_model.get("command_id_filter", "")).strip(),
        "search": str(read_model.get("search_filter", "")).strip(),
        "limit": str(read_model.get("limit", 100)).strip(),
    }
    return (
        '<section class="operator-filters" aria-label="Approval filters">'
        "<h2>Approval Filters</h2>"
        '<form method="get" action="/operator/approvals">'
        f'<label>Tenant <input name="tenant_id" value="{escape(values["tenant_id"])}"></label>'
        f'<label>Approval <input name="request_id" value="{escape(values["request_id"])}"></label>'
        f'<label>Command <input name="command_id" value="{escape(values["command_id"])}"></label>'
        "<label>Status "
        + _select_html(
            "status",
            _APPROVAL_STATUSES,
            selected_status,
            empty_label="any",
        )
        + "</label>"
        f'<label>Search <input name="search" maxlength="{_MAX_SEARCH_FILTER_LENGTH}" value="{escape(values["search"])}"></label>'
        f'<label>Limit <input name="limit" type="number" min="1" max="{_MAX_PAGE_LIMIT}" value="{escape(values["limit"])}"></label>'
        '<button type="submit">Apply</button>'
        '<a href="/operator/approvals">Clear</a>'
        "</form>"
        "</section>"
    )


def _receipt_filter_controls(read_model: Mapping[str, Any]) -> str:
    selected_receipt_type = str(read_model.get("receipt_type_filter", "")).strip()
    selected_task_status = str(read_model.get("task_status_filter", "")).strip()
    values = {
        "tenant_id": str(read_model.get("tenant_id_filter", "")).strip(),
        "command_id": str(read_model.get("command_id_filter", "")).strip(),
        "receipt_status": str(read_model.get("receipt_status_filter", "")).strip(),
        "search": str(read_model.get("search_filter", "")).strip(),
        "limit": str(read_model.get("limit", 100)).strip(),
    }
    return (
        '<section class="operator-filters" aria-label="Receipt filters">'
        "<h2>Receipt Filters</h2>"
        '<form method="get" action="/operator/receipts">'
        f'<label>Tenant <input name="tenant_id" value="{escape(values["tenant_id"])}"></label>'
        f'<label>Command <input name="command_id" value="{escape(values["command_id"])}"></label>'
        "<label>Receipt Type "
        + _select_html(
            "receipt_type",
            _RECEIPT_TYPES,
            selected_receipt_type,
            empty_label="any",
        )
        + "</label>"
        f'<label>Receipt Status <input name="receipt_status" value="{escape(values["receipt_status"])}"></label>'
        "<label>Task Status "
        + _select_html(
            "task_status",
            _TASK_STATUSES,
            selected_task_status,
            empty_label="any",
        )
        + "</label>"
        f'<label>Search <input name="search" maxlength="{_MAX_SEARCH_FILTER_LENGTH}" value="{escape(values["search"])}"></label>'
        f'<label>Limit <input name="limit" type="number" min="1" max="{_MAX_PAGE_LIMIT}" value="{escape(values["limit"])}"></label>'
        '<button type="submit">Apply</button>'
        '<a href="/operator/receipts">Clear</a>'
        "</form>"
        "</section>"
    )


def _select_html(
    name: str,
    values: tuple[str, ...],
    selected: str,
    *,
    empty_label: str,
) -> str:
    options = [
        f'<option value="">{escape(empty_label)}</option>',
    ]
    for value in values:
        selected_attr = " selected" if value == selected else ""
        options.append(
            f'<option value="{escape(value)}"{selected_attr}>{escape(value)}</option>'
        )
    return f'<select name="{escape(name)}">' + "".join(options) + "</select>"


def _operator_table_html(
    *,
    title: str,
    description: str,
    json_href: str,
    columns: tuple[str, ...],
    rows: str,
    metrics: tuple[tuple[str, Any], ...],
    nav_links: tuple[tuple[str, str], ...],
    extra_html: str = "",
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
    .operator-filters {{ margin: 0 0 24px; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; }}
    .operator-filters h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .operator-filters form {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; align-items: end; }}
    .operator-filters label {{ display: grid; gap: 6px; color: #57606a; font-size: 12px; font-weight: 700; }}
    .operator-filters input, .operator-filters select {{ width: 100%; box-sizing: border-box; border: 1px solid #8c959f; border-radius: 6px; padding: 8px; font: inherit; }}
    .operator-filters button {{ border: 1px solid #1a7f37; border-radius: 6px; background: #1f883d; color: #fff; padding: 9px 12px; cursor: pointer; }}
    .operator-actions {{ margin-top: 24px; background: #fff; border: 1px solid #d8dee4; border-radius: 8px; padding: 16px; }}
    .operator-actions h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .operator-actions ul {{ margin: 0; padding: 0; display: grid; gap: 12px; }}
    .operator-actions li {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; list-style: none; border-top: 1px solid #d8dee4; padding-top: 12px; }}
    .operator-actions li:first-child {{ border-top: 0; padding-top: 0; }}
    .operator-actions form {{ display: flex; gap: 8px; margin: 0; }}
    .operator-actions button {{ border: 1px solid #8c959f; border-radius: 6px; background: #f6f8fa; padding: 8px 12px; cursor: pointer; }}
    .operator-actions button[value="approve"] {{ background: #1f883d; border-color: #1a7f37; color: #fff; }}
    .operator-action-status {{ margin: 0 0 16px; padding: 12px 14px; border: 1px solid #bf8700; border-radius: 8px; background: #fff8c5; color: #3b2300; }}
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
  {extra_html}
</main>
</body>
</html>"""


def _operator_action_status_html(status: str) -> str:
    if not status:
        return ""
    return (
        '<div class="operator-action-status">'
        f"{escape(status)}"
        "</div>"
    )


def _approval_recovery_controls(records: list[Mapping[str, Any]]) -> str:
    recoverable = [
        record
        for record in records
        if bool(record.get("approval_recovery_available"))
        and str(record.get("approval_request_id", "")).strip()
    ]
    if not recoverable:
        return ""
    items: list[str] = []
    for record in recoverable:
        request_id = str(record.get("approval_request_id", "")).strip()
        command_id = str(record.get("command_id", "")).strip()
        plan_id = str(record.get("plan_id", "")).strip()
        plan_step_id = str(record.get("plan_step_id", "")).strip()
        context = " / ".join(
            item
            for item in (
                f"command {command_id}" if command_id else "",
                f"plan {plan_id}" if plan_id else "",
                f"step {plan_step_id}" if plan_step_id else "",
            )
            if item
        )
        items.append(
            "<li>"
            f"<span>{escape(request_id)}"
            + (f"<br><small>{escape(context)}</small>" if context else "")
            + "</span>"
            '<form method="post" action="/operator/current-task/approval">'
            f'<input type="hidden" name="request_id" value="{escape(request_id)}">'
            '<button type="submit" name="decision" value="approve">Approve</button>'
            '<button type="submit" name="decision" value="deny">Deny</button>'
            "</form>"
            "</li>"
        )
    return (
        '<section class="operator-actions" aria-label="Approval recovery controls">'
        "<h2>Approval Recovery</h2>"
        "<ul>"
        + "\n".join(items)
        + "</ul>"
        "</section>"
    )
