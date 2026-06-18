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
        "raw_private_payload_storage_allowed",
        "secret_value_storage_allowed",
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
_FOUNDATION_LANES = (
    {
        "lane_id": "request_intake_whqr",
        "display_name": "Request Intake and WHQR",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/requests/preview"],
        "schema_refs": [
            "schemas/personal_assistant_request.schema.json",
            "schemas/personal_assistant_plan.schema.json",
            "schemas/personal_assistant_receipt.schema.json",
        ],
        "validator_refs": [
            "scripts/validate_personal_assistant_receipt.py",
            "tests/test_personal_assistant_intake.py",
        ],
    },
    {
        "lane_id": "skill_registry",
        "display_name": "Skill Registry",
        "stage": "runtime_read_model",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/skills"],
        "schema_refs": ["schemas/personal_assistant_skill.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_skill_registry.py",
            "tests/test_personal_assistant_skill_registry.py",
            "tests/test_personal_assistant_runtime_skill_registry.py",
        ],
    },
    {
        "lane_id": "approval_queue",
        "display_name": "Approval Queue",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": [
            "/api/v1/personal-assistant/approval-queue",
            "/api/v1/personal-assistant/approval-queue/preview",
        ],
        "schema_refs": [
            "schemas/personal_assistant_approval.schema.json",
            "schemas/personal_assistant_approval_queue.schema.json",
            "schemas/personal_assistant_approval_decision.schema.json",
        ],
        "validator_refs": [
            "scripts/validate_personal_assistant_approval_queue.py",
            "scripts/validate_personal_assistant_approval_decision.py",
            "tests/test_personal_assistant_approval_queue.py",
        ],
    },
    {
        "lane_id": "memory_observation",
        "display_name": "Memory Observation",
        "stage": "candidate_only",
        "state": "SolvedVerified",
        "route_refs": [
            "/api/v1/personal-assistant/memory-observations",
            "/api/v1/personal-assistant/memory-observations/preview",
            "/api/v1/personal-assistant/memory-observations/review/preview",
        ],
        "schema_refs": [
            "schemas/personal_assistant_memory_observation.schema.json",
            "schemas/personal_assistant_memory_review.schema.json",
        ],
        "validator_refs": [
            "scripts/validate_personal_assistant_memory_observation.py",
            "scripts/validate_personal_assistant_memory_review.py",
            "tests/test_personal_assistant_memory_runtime.py",
        ],
    },
    {
        "lane_id": "read_only_projection",
        "display_name": "Read-Only Inbox and Calendar",
        "stage": "projection_only",
        "state": "SolvedVerified",
        "route_refs": [],
        "schema_refs": ["schemas/personal_assistant_read_only_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_read_only_projection.py",
            "tests/test_validate_personal_assistant_read_only_projection.py",
        ],
    },
    {
        "lane_id": "draft_projection",
        "display_name": "Draft-Only Assistant",
        "stage": "projection_only",
        "state": "SolvedVerified",
        "route_refs": [],
        "schema_refs": ["schemas/personal_assistant_draft_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_draft_projection.py",
            "tests/test_validate_personal_assistant_draft_projection.py",
        ],
    },
    {
        "lane_id": "teamops_shared_inbox",
        "display_name": "TeamOps Shared Inbox",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/teamops/shared-inbox/plan/preview"],
        "schema_refs": ["schemas/personal_assistant_teamops_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_teamops_projection.py",
            "tests/test_validate_personal_assistant_teamops_projection.py",
        ],
    },
    {
        "lane_id": "github_codex_review",
        "display_name": "GitHub and Codex Review",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/github-codex/review/preview"],
        "schema_refs": ["schemas/personal_assistant_github_codex_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_github_codex_projection.py",
            "tests/test_validate_personal_assistant_github_codex_projection.py",
        ],
    },
    {
        "lane_id": "research_source_compare",
        "display_name": "Research Source Compare",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/research/source-compare/preview"],
        "schema_refs": ["schemas/personal_assistant_research_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_research_projection.py",
            "tests/test_validate_personal_assistant_research_projection.py",
        ],
    },
    {
        "lane_id": "math_reasoning",
        "display_name": "Math Reasoning",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/math/reasoning/preview"],
        "schema_refs": ["schemas/personal_assistant_math_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_math_projection.py",
            "tests/test_validate_personal_assistant_math_projection.py",
        ],
    },
    {
        "lane_id": "schedule_planning",
        "display_name": "Schedule Planning",
        "stage": "runtime_preview",
        "state": "SolvedVerified",
        "route_refs": ["/api/v1/personal-assistant/planning/schedule/preview"],
        "schema_refs": ["schemas/personal_assistant_planning_projection.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_planning_projection.py",
            "tests/test_validate_personal_assistant_planning_projection.py",
        ],
    },
    {
        "lane_id": "operator_console",
        "display_name": "Operator Console",
        "stage": "read_model",
        "state": "SolvedVerified",
        "route_refs": [
            "/api/v1/console/personal-assistant",
            "/api/v1/console/personal-assistant/view",
            "/api/v1/console/personal-assistant/readiness",
        ],
        "schema_refs": ["schemas/personal_assistant_console_read_model.schema.json"],
        "validator_refs": [
            "scripts/validate_personal_assistant_console_read_model.py",
            "tests/test_validate_personal_assistant_console_read_model.py",
            "tests/test_personal_assistant_console.py",
        ],
    },
)
_APPROVAL_FALSE_CONTROLS = (
    "execution_allowed",
    "live_connector_execution_allowed",
    "external_send_allowed",
    "connector_mutation_allowed",
    "system_of_record_write_allowed",
    "approval_is_execution",
)
_APPROVAL_METADATA_FALSE_CONTROLS = (
    "live_connector_execution_allowed",
    "approval_decision_executes_action",
)
_MEMORY_FALSE_CONTROLS = (
    "live_memory_write_allowed",
    "nested_mind_live_activation_allowed",
    "raw_private_payload_storage_allowed",
    "secret_value_storage_allowed",
)
_MEMORY_METADATA_FALSE_CONTROLS = _MEMORY_FALSE_CONTROLS
_READ_ONLY_WORKER_REHEARSAL_RECEIPT_KIND = "read_only_worker_rehearsal_receipt"


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
    approval_model, approval_blockers = _normalize_false_controls(
        approval_queue.read_model() if approval_queue else _empty_approval_model(),
        label="approval_queue",
        controls=_APPROVAL_FALSE_CONTROLS,
        metadata_controls=_APPROVAL_METADATA_FALSE_CONTROLS,
    )
    memory_model, memory_blockers = _normalize_false_controls(
        memory_ledger.read_model() if memory_ledger else _empty_memory_model(),
        label="memory",
        controls=_MEMORY_FALSE_CONTROLS,
        metadata_controls=_MEMORY_METADATA_FALSE_CONTROLS,
    )
    request_rows = _panel_items(recent_requests, "recent_requests")
    task_rows = _panel_items(task_items, "task_items")
    receipt_rows = _panel_items(receipts, "receipts")
    teamops_rows = _panel_items(teamops_plans, "teamops_plans")
    lane_status = _build_lane_status()
    assurance = _build_foundation_assurance(
        approval_blockers=approval_blockers,
        memory_blockers=memory_blockers,
        teamops_rows=teamops_rows,
        lane_status=lane_status,
    )
    return {
        "console_id": "personal_assistant_console_foundation",
        "status": "foundation_read_only",
        "solver_outcome": assurance["outcome"],
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
            "lane_status": {
                "item_count": lane_status["lane_count"],
                "execution_allowed": False,
            },
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
            "viewer_binding": _receipt_viewer_binding(receipt_rows),
        },
        "skills": skill_model,
        "memory": memory_model,
        "teamops": {
            "plans": teamops_rows,
            "live_probe_allowed": False,
            "mailbox_mutation_allowed": False,
            "provider_call_allowed": False,
        },
        "lane_status": lane_status,
        "assurance": assurance,
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


def build_personal_assistant_readiness_demo(
    *,
    generated_at: str,
    console_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the read-only "Show my assistant readiness" demo payload.

    Input contract: callers pass a generation timestamp and may pass an already
    built console payload.
    Output contract: returns a compact read-only readiness projection.
    Error contract: raises PersonalAssistantInvariantError for malformed
    timestamps, private payload drift, or secret-like values.
    """

    timestamp = _require_text(generated_at, "generated_at")
    if isinstance(console_payload, Mapping):
        payload = dict(console_payload)
    else:
        payload = build_personal_assistant_console_read_model(generated_at=timestamp)
    _scan_private_or_secret_payload(payload, path="console_payload")
    skills = _mapping_value(payload, "skills")
    receipts = _mapping_value(payload, "receipts")
    approval_queue = _mapping_value(payload, "approval_queue")
    effect_boundary = _mapping_value(payload, "effect_boundary")
    skill_ids = list(skills.get("skill_ids", ())) if isinstance(skills.get("skill_ids"), list) else []
    return {
        "demo_id": "personal_assistant_readiness_read_only_demo",
        "user_ask": "Show my assistant readiness.",
        "status": "foundation_read_only",
        "solver_outcome": payload.get("solver_outcome", "SolvedVerified"),
        "generated_at": timestamp,
        "governed": True,
        "inbox_projection_status": {
            "status": "projection_contract_ready",
            "skill_id": "email.inbox.summarize",
            "source_projection": "operator_supplied_redacted_projection",
            "required_connector_proof": "gmail.readonly",
            "live_connector_execution_allowed": False,
            "mailbox_read_allowed": False,
            "mailbox_mutation_allowed": False,
            "external_send_allowed": False,
        },
        "calendar_projection_status": {
            "status": "projection_contract_ready",
            "skill_id": "calendar.day.brief",
            "source_projection": "operator_supplied_redacted_projection",
            "required_connector_proof": "calendar.readonly",
            "live_connector_execution_allowed": False,
            "calendar_read_allowed": False,
            "calendar_write_allowed": False,
            "invite_allowed": False,
        },
        "available_skills": {
            "skill_count": skills.get("skill_count", 0),
            "skill_ids": skill_ids,
            "read_only_skill_ids": [
                skill_id
                for skill_id in ("email.inbox.summarize", "calendar.day.brief")
                if skill_id in skill_ids
            ],
        },
        "blocked_actions": list(payload.get("blocked_actions", ())),
        "required_approvals": {
            "approval_count": approval_queue.get("approval_count", 0),
            "state_counts": dict(approval_queue.get("state_counts", {}))
            if isinstance(approval_queue.get("state_counts"), Mapping)
            else {},
            "records": list(approval_queue.get("records", ()))
            if isinstance(approval_queue.get("records"), list)
            else [],
            "approval_before_send_required": True,
            "approval_is_execution": False,
        },
        "receipts": {
            "receipt_count": receipts.get("receipt_count", 0),
            "items": list(receipts.get("items", ())) if isinstance(receipts.get("items"), list) else [],
            "receipt_refs": (
                list(payload.get("receipt_refs", ()))
                if isinstance(payload.get("receipt_refs"), list)
                else []
            ),
            "viewer_binding": dict(receipts.get("viewer_binding", {}))
            if isinstance(receipts.get("viewer_binding"), Mapping)
            else {},
        },
        "effect_boundary": {
            **dict(effect_boundary),
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "external_send_allowed": False,
            "mailbox_mutation_allowed": False,
            "calendar_write_allowed": False,
        },
        "private_payload_policy": dict(payload.get("private_payload_policy", {}))
        if isinstance(payload.get("private_payload_policy"), Mapping)
        else {},
        "assurance": dict(payload.get("assurance", {})) if isinstance(payload.get("assurance"), Mapping) else {},
        "next_action": "continue read-only demo hardening before approval-gated execution",
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
    lane_status = _mapping_value(payload, "lane_status")
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
        ("Foundation Lanes", lane_status.get("lane_count", 0)),
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
  {_panel_table("Foundation Lanes", lane_status.get("lanes", ()), ("lane_id", "stage", "state"))}
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
        "raw_private_payload_storage_allowed": False,
        "secret_value_storage_allowed": False,
        "candidate_only": True,
        "candidates": [],
        "metadata": {
            "foundation_only": True,
            "ledger_projection": "read_model",
            "persistence_boundary": "stateless_unless_hosted_store_is_explicitly_bound",
            "live_memory_write_allowed": False,
            "nested_mind_live_activation_allowed": False,
            "raw_private_payload_storage_allowed": False,
            "secret_value_storage_allowed": False,
        },
    }


def _normalize_false_controls(
    model: Mapping[str, Any],
    *,
    label: str,
    controls: Sequence[str],
    metadata_controls: Sequence[str],
) -> tuple[dict[str, Any], list[str]]:
    normalized = _json_ready(model)
    if not isinstance(normalized, dict):
        raise PersonalAssistantInvariantError(f"{label} read model must be a mapping")
    blockers: list[str] = []
    for control in controls:
        if normalized.get(control) is not False:
            blockers.append(f"{label}.{control}")
        normalized[control] = False
    metadata = normalized.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    metadata_dict = dict(metadata)
    for control in metadata_controls:
        if metadata_dict.get(control) is not False:
            blockers.append(f"{label}.metadata.{control}")
        metadata_dict[control] = False
    normalized["metadata"] = metadata_dict
    return normalized, sorted(set(blockers))


def _build_foundation_assurance(
    *,
    approval_blockers: Sequence[str],
    memory_blockers: Sequence[str],
    teamops_rows: Sequence[Mapping[str, Any]],
    lane_status: Mapping[str, Any],
) -> dict[str, Any]:
    blockers = list(approval_blockers) + list(memory_blockers)
    for index, plan in enumerate(teamops_rows):
        for control in ("live_probe_allowed", "mailbox_mutation_allowed", "provider_call_allowed"):
            if plan.get(control) is not False and control in plan:
                blockers.append(f"teamops_plans[{index}].{control}")
    for index, lane in enumerate(_sequence_of_mappings(lane_status.get("lanes", ()))):
        for control in (
            "execution_allowed",
            "live_connector_execution_allowed",
            "connector_mutation_allowed",
            "external_effect_allowed",
            "customer_readiness_claim_allowed",
            "nested_mind_live_activation_allowed",
        ):
            if lane.get(control) is not False:
                blockers.append(f"lane_status.lanes[{index}].{control}")
        if not lane.get("schema_refs"):
            blockers.append(f"lane_status.lanes[{index}].schema_refs")
        if not lane.get("validator_refs"):
            blockers.append(f"lane_status.lanes[{index}].validator_refs")
    unique_blockers = sorted(set(blockers))
    return {
        "assurance_id": "personal_assistant_foundation_no_effect_assurance",
        "outcome": "GovernanceBlocked" if unique_blockers else "SolvedVerified",
        "foundation_only": True,
        "ready_for_live_execution": False,
        "ready_for_customer_readiness_claim": False,
        "authority_drift_detected": bool(unique_blockers),
        "blocking_reasons": unique_blockers,
        "checked_controls": [
            "approval_queue_no_execution",
            "approval_decision_is_not_execution",
            "memory_candidate_only",
            "nested_mind_staging_only",
            "teamops_no_live_probe",
            "no_raw_private_payload_serialization",
            "no_secret_value_serialization",
            "receipt_viewer_read_only_projection",
            "foundation_lane_status_no_effect",
        ],
        "next_action": (
            "repair authority-drift controls before any further assistant promotion"
            if unique_blockers
            else "continue foundation-stage assistant hardening without enabling live execution"
        ),
    }


def _build_lane_status() -> dict[str, Any]:
    lanes = []
    for lane in _FOUNDATION_LANES:
        lanes.append(
            {
                **_json_ready(lane),
                "foundation_only": True,
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "connector_mutation_allowed": False,
                "external_effect_allowed": False,
                "customer_readiness_claim_allowed": False,
                "nested_mind_live_activation_allowed": False,
                "receipt_required": True,
            }
        )
    runtime_preview_count = sum(1 for lane in lanes if lane["stage"] == "runtime_preview")
    return {
        "status_id": "personal_assistant_foundation_lane_status",
        "foundation_only": True,
        "lane_count": len(lanes),
        "runtime_preview_lane_count": runtime_preview_count,
        "read_model_lane_count": sum(1 for lane in lanes if lane["stage"] in {"runtime_read_model", "read_model"}),
        "projection_only_lane_count": sum(1 for lane in lanes if lane["stage"] in {"projection_only", "candidate_only"}),
        "governed": True,
        "execution_allowed": False,
        "live_connector_execution_allowed": False,
        "connector_mutation_allowed": False,
        "external_effect_allowed": False,
        "customer_readiness_claim_allowed": False,
        "nested_mind_live_activation_allowed": False,
        "lanes": lanes,
    }


def _sequence_of_mappings(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


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


def _receipt_viewer_binding(receipt_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    projected_receipt_ids = sorted(
        {
            str(row["receipt_id"])
            for row in receipt_rows
            if isinstance(row.get("receipt_id"), str) and str(row.get("receipt_id"))
        }
    )
    source_receipt_refs = sorted(
        {
            str(row["source_receipt_ref"])
            for row in receipt_rows
            if isinstance(row.get("source_receipt_ref"), str) and str(row.get("source_receipt_ref"))
        }
    )
    return {
        "viewer_id": "foundation_receipt_viewer_binding",
        "viewer_state": "foundation_read_only",
        "foundation_only": True,
        "projection_count": len(projected_receipt_ids),
        "projected_receipt_ids": projected_receipt_ids,
        "source_receipt_refs": source_receipt_refs,
        "read_only_worker_rehearsal_bound": any(
            row.get("receipt_kind") == _READ_ONLY_WORKER_REHEARSAL_RECEIPT_KIND for row in receipt_rows
        ),
        "runtime_dispatch_allowed": False,
        "filesystem_write_allowed": False,
        "external_effect_allowed": False,
        "connector_call_allowed": False,
        "terminal_closure_allowed": False,
        "success_claim_allowed": False,
    }


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
