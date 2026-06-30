"""Operator Console — unified operational views for operations teams.

Aggregates runtime state into structured dashboard views that any
frontend can consume. Seven views cover the core operational needs:

- Home: active/blocked/failed runs, provider health, budget burn
- Runs: current state, ledger links, verification, restore eligibility
- Audit: searchable event history by tenant/provider/policy/actor
- Checkpoints: saved coordination state, resumable/expired/blocked
- Providers: Anthropic/OpenAI/Gemini/Ollama status, latency, cost
- Scheduler: jobs, execution history, health
- Note Memory: governed note lifecycle summaries and promotion queues
- Spatial Map: governed runtime, launch, and boundary path panels
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from html import escape
from typing import Mapping

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from mcoi_runtime.app.readiness import production_readiness_checks
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers._tenant_scope import scoped_listing_tenant
from mcoi_runtime.app.view_models import WHQRBindingClarificationStatusView
from mcoi_runtime.contracts.conversation import ConversationThread
from mcoi_runtime.contracts.operator_console_first import (
    ConsoleIntentClass,
    ConsolePlannedAction,
    RecoveryClass,
    SideEffectManifest,
    StateSnapshot,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operator_console_first import OperatorConsoleFirstRuntime
from mcoi_runtime.core.operator_console_first_read_model import build_operator_console_read_model
from mcoi_runtime.core.spatial_governance import build_gateway_spatial_map
from mcoi_runtime.personal_assistant.console import (
    build_personal_assistant_console_read_model,
    render_personal_assistant_console_html,
)

router = APIRouter()
_MAX_CONSOLE_READ_LIMIT = 500


def _coerce_console_read_limit(limit: object) -> int:
    """Return a bounded console read limit."""
    error_detail = {
        "error": "invalid_limit",
        "message": "limit must be a positive integer",
    }
    if isinstance(limit, bool):
        raise HTTPException(status_code=422, detail=error_detail)
    try:
        value = int(limit)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=error_detail) from exc
    if str(limit).strip() != str(value):
        raise HTTPException(status_code=422, detail=error_detail)
    if value < 1 or value > _MAX_CONSOLE_READ_LIMIT:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_limit",
                "message": "limit must be between 1 and 500",
            },
        )
    return value


# ═══ Home Dashboard ═══


@router.get("/api/v1/console/home")
def console_home():
    """Operator home dashboard — key vitals at a glance."""
    deps.metrics.inc("requests_governed")

    # Collect vitals from subsystems
    audit_summary = deps.audit_trail.summary()
    scheduler_summary = deps.scheduler.summary()

    # Count outcomes from recent audit entries
    recent = deps.audit_trail.query(limit=200)
    active = sum(1 for e in recent if e.outcome == "success")
    blocked = sum(1 for e in recent if e.outcome in ("denied", "blocked"))
    failed = sum(1 for e in recent if e.outcome in ("error", "failed"))

    return {
        "active_runs": active,
        "blocked_runs": blocked,
        "failed_runs": failed,
        "total_audit_entries": audit_summary.get("entry_count", 0),
        "chain_intact": deps.audit_trail.verify_chain(),
        "llm_invocations": deps.llm_bridge.invocation_count,
        "llm_total_cost": deps.llm_bridge.total_cost,
        "active_tenants": deps.tenant_budget_mgr.tenant_count(),
        "total_spent": deps.tenant_budget_mgr.total_spent(),
        "scheduler": scheduler_summary,
        "circuit_breaker": deps.llm_circuit.state.value,
        "event_count": deps.event_bus.event_count,
        "health_score": deps.health_agg.compute().overall_score,
        "governed": True,
    }


# ═══ Runs View ═══


@router.get("/api/v1/console/runs")
def console_runs(
    request: Request,
    tenant_id: str | None = None,
    outcome: str | None = None,
    limit: str = "50",
):
    """Operator runs view — recent governed actions with status."""
    deps.metrics.inc("requests_governed")
    tenant_id = scoped_listing_tenant(request, tenant_id)
    read_limit = _coerce_console_read_limit(limit)
    entries = deps.audit_trail.query(
        tenant_id=tenant_id,
        outcome=outcome,
        limit=read_limit,
    )
    return {
        "runs": [
            {
                "entry_id": e.entry_id,
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "timestamp": e.recorded_at,
                "detail": e.detail,
            }
            for e in entries
        ],
        "count": len(entries),
        "filters": {"tenant_id": tenant_id, "outcome": outcome},
        "governed": True,
    }


# ═══ Audit View ═══


@router.get("/api/v1/console/audit")
def console_audit(
    request: Request,
    tenant_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limit: str = "100",
):
    """Operator audit view — searchable event history."""
    deps.metrics.inc("requests_governed")
    tenant_id = scoped_listing_tenant(request, tenant_id)
    read_limit = _coerce_console_read_limit(limit)
    entries = deps.audit_trail.query(
        tenant_id=tenant_id,
        action=action,
        outcome=outcome,
        limit=read_limit,
    )

    # Aggregate by action type
    action_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}
    actor_counts: dict[str, int] = {}
    for e in entries:
        action_counts[e.action] = action_counts.get(e.action, 0) + 1
        outcome_counts[e.outcome or "unknown"] = outcome_counts.get(e.outcome or "unknown", 0) + 1
        actor_counts[e.actor_id] = actor_counts.get(e.actor_id, 0) + 1

    return {
        "entries": [
            {
                "entry_id": e.entry_id,
                "action": e.action,
                "actor_id": e.actor_id,
                "tenant_id": e.tenant_id,
                "target": e.target,
                "outcome": e.outcome,
                "timestamp": e.recorded_at,
                "hash": e.entry_hash[:16],
            }
            for e in entries
        ],
        "count": len(entries),
        "aggregations": {
            "by_action": dict(sorted(action_counts.items(), key=lambda x: -x[1])[:10]),
            "by_outcome": outcome_counts,
            "by_actor": dict(sorted(actor_counts.items(), key=lambda x: -x[1])[:10]),
        },
        "chain_intact": deps.audit_trail.verify_chain(),
        "governed": True,
    }


# ═══ Checkpoints View ═══


@router.get("/api/v1/console/checkpoints")
def console_checkpoints():
    """Operator checkpoint view — coordination state snapshots."""
    deps.metrics.inc("requests_governed")
    coordination = deps.coordination_engine.summary()
    store_states = deps.coordination_store.list_states()
    return {
        "engine_state": coordination,
        "persisted_checkpoints": list(store_states),
        "checkpoint_count": len(store_states),
        "governed": True,
    }


# ═══ Providers View ═══


@router.get("/api/v1/console/providers")
def console_providers():
    """Operator provider view — LLM provider health and cost."""
    deps.metrics.inc("requests_governed")

    budget_summary = deps.llm_bridge.budget_summary()
    budgets = budget_summary.get("budgets", [])

    return {
        "providers": {
            "default_backend": "configured",
            "invocation_count": deps.llm_bridge.invocation_count,
            "total_cost": deps.llm_bridge.total_cost,
            "circuit_breaker": deps.llm_circuit.state.value,
        },
        "budgets": [
            {
                "budget_id": b.get("budget_id", ""),
                "spent": b.get("spent", 0),
                "max_cost": b.get("max_cost", 0),
                "calls_made": b.get("calls_made", 0),
                "exhausted": b.get("exhausted", False),
            }
            for b in budgets
        ] if isinstance(budgets, list) else [],
        "tenant_count": deps.tenant_budget_mgr.tenant_count(),
        "total_tenant_spend": deps.tenant_budget_mgr.total_spent(),
        "governed": True,
    }


# ═══ Scheduler View ═══


@router.get("/api/v1/console/scheduler")
def console_scheduler():
    """Operator scheduler view — jobs, execution history, health."""
    deps.metrics.inc("requests_governed")
    summary = deps.scheduler.summary()
    jobs = deps.scheduler.list_jobs()
    recent = deps.scheduler.recent_executions(limit=20)
    return {
        "summary": summary,
        "jobs": [
            {
                "job_id": j.job_id,
                "name": j.name,
                "schedule_type": j.schedule_type.value,
                "handler_name": j.handler_name,
                "enabled": j.enabled,
                "tenant_id": j.tenant_id,
            }
            for j in jobs
        ],
        "recent_executions": [
            {
                "execution_id": e.execution_id,
                "job_id": e.job_id,
                "status": e.status.value,
                "started_at": e.started_at,
                "error": e.error,
            }
            for e in recent
        ],
        "governed": True,
    }


# ═══ Full Console ═══


# Note Memory View


def _note_memory_extension_read_model() -> dict[str, object]:
    """Return optional note-memory posture without exposing filesystem paths."""

    try:
        bootstrap = deps.get("note_memory_bootstrap")
    except RuntimeError:
        return {
            "registered": False,
            "enabled": False,
            "mounted": False,
            "store_configured": False,
            "state": "unregistered",
            "reason": "dependency_not_registered",
        }
    enabled = bool(getattr(bootstrap, "enabled", False))
    raw_mounted = bool(getattr(bootstrap, "mounted", False))
    store_path = str(getattr(bootstrap, "store_path", "") or "").strip()
    store_configured = bool(store_path)
    mounted = raw_mounted and store_configured
    if mounted:
        state = "mounted"
    elif raw_mounted and not store_configured:
        state = "mounted_unconfigured"
    elif enabled:
        state = "enabled_unmounted"
    else:
        state = "disabled"
    return {
        "registered": True,
        "enabled": enabled,
        "mounted": mounted,
        "store_configured": store_configured,
        "state": state,
        "reason": str(getattr(bootstrap, "reason", "") or "unknown"),
    }


def _empty_note_memory_payload(extension: dict[str, object]) -> dict[str, object]:
    """Return the stable disabled-state note-memory dashboard shape."""

    return {
        "governed": True,
        "status": str(extension["state"]),
        "extension": extension,
        "summary": {
            "event_count": 0,
            "active_note_count": 0,
            "rejected_delta_count": 0,
            "expiring_note_count": 0,
            "pending_promotion_count": 0,
            "memory_anchor_count": 0,
            "episode_capsule_count": 0,
            "contradiction_count": 0,
            "retrieval_filter_active": False,
            "retrieval_filter_mode": "unfiltered",
            "retrieval_influence_count": 0,
            "retrieval_influence_total_count": 0,
            "retrieval_influence_filtered_out_count": 0,
            "retrieval_receipt_count": 0,
            "retrieval_receipt_total_count": 0,
            "retrieval_receipt_filtered_out_count": 0,
            "index_proof_state": "Unknown",
        },
        "filters": {
            "retrieval_receipt_ref": "",
            "retrieval_citing_note_ref": "",
        },
        "recent_notes": [],
        "rejected_deltas": [],
        "expiring_notes": [],
        "pending_promotions": [],
        "memory_anchors": [],
        "episode_capsules": [],
        "contradictions": [],
        "retrieval_receipts": [],
        "retrieval_influence": [],
        "audit_events": [],
        "index": {
            "valid_events": 0,
            "rejected_lines": 0,
            "checksum_failures": 0,
            "proof_state": "Unknown",
        },
        "error": "",
    }


@router.get("/api/v1/console/note-memory")
def console_note_memory(limit: int = 25, retrieval_receipt_ref: str = "", retrieval_citing_note_ref: str = ""):
    """Operator note-memory view with read-only governed lifecycle summaries."""

    deps.metrics.inc("requests_governed")
    extension = _note_memory_extension_read_model()
    if extension["state"] != "mounted":
        return _empty_note_memory_payload(extension)

    try:
        bootstrap = deps.get("note_memory_bootstrap")
        from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime

        bounded_limit = max(1, min(int(limit), 100))
        runtime = NoteMemoryRuntime.from_path(str(getattr(bootstrap, "store_path", "")))
        request_body = {"limit": bounded_limit}
        if retrieval_receipt_ref:
            request_body["retrieval_receipt_ref"] = retrieval_receipt_ref
        if retrieval_citing_note_ref:
            request_body["retrieval_citing_note_ref"] = retrieval_citing_note_ref
        envelope = runtime.dashboard_snapshot(request_body).to_dict()
    except (RuntimeError, TypeError, ValueError) as exc:
        payload = _empty_note_memory_payload(extension)
        payload["status"] = "rejected"
        payload["error"] = str(exc)
        return payload

    if not envelope["ok"]:
        payload = _empty_note_memory_payload(extension)
        payload["status"] = envelope["status"]
        payload["error"] = envelope["error"]
        return payload

    snapshot = dict(envelope["payload"])
    return {
        "governed": True,
        "status": str(snapshot.get("status", "ready")),
        "extension": extension,
        **snapshot,
        "error": "",
    }


@router.get("/api/v1/console/note-memory/view", response_class=HTMLResponse)
def console_note_memory_view(limit: int = 25, retrieval_receipt_ref: str = "", retrieval_citing_note_ref: str = ""):
    """Browser-facing read-only note-memory operator view."""

    payload = console_note_memory(
        limit=limit,
        retrieval_receipt_ref=retrieval_receipt_ref,
        retrieval_citing_note_ref=retrieval_citing_note_ref,
    )
    return HTMLResponse(_render_note_memory_console_html(payload))


@router.get("/api/v1/console/whqr/clarifications")
def console_whqr_binding_clarifications(
    job_id: str | None = None,
    include_empty: bool = False,
    limit: str = "50",
):
    """Operator WHQR binding clarification view for active job-thread replay status."""
    deps.metrics.inc("requests_governed")
    read_limit = _coerce_console_read_limit(limit)
    job_engine = deps.get("job_engine")
    thread_index = _job_conversation_thread_index()
    descriptors = {descriptor.job_id: descriptor for descriptor in job_engine.list_job_descriptors()}
    states = job_engine.list_job_states()
    if job_id is not None:
        states = tuple(state for state in states if state.job_id == job_id)
        if not states:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "job_not_found",
                    "message": "job_id does not identify a known job",
                    "job_id": job_id,
                },
            )

    rows: list[dict[str, object]] = []
    missing_thread_ids: list[str] = []
    selected_states = sorted(states, key=lambda state: state.job_id)[:read_limit]
    for state in selected_states:
        if state.thread_id is None:
            continue
        thread = thread_index.get(state.thread_id)
        if thread is None:
            missing_thread_ids.append(state.thread_id)
            continue
        try:
            view = WHQRBindingClarificationStatusView.from_thread(thread)
        except RuntimeCoreInvariantError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "whqr_clarification_replay_invalid",
                    "message": str(exc),
                    "thread_id": thread.thread_id,
                    "job_id": state.job_id,
                },
            ) from exc
        if not include_empty and view.next_step == "no_whqr_binding_clarification":
            continue
        descriptor = descriptors.get(state.job_id)
        rows.append(
            {
                "job_id": state.job_id,
                "job_name": descriptor.name if descriptor is not None else "",
                "job_status": state.status.value,
                "thread_id": thread.thread_id,
                "whqr_binding": asdict(view),
            }
        )

    next_steps = [
        str(row["whqr_binding"]["next_step"])
        for row in rows
        if isinstance(row.get("whqr_binding"), dict)
    ]
    return {
        "governed": True,
        "filters": {
            "job_id": job_id,
            "include_empty": include_empty,
            "limit": read_limit,
        },
        "summary": {
            "job_count": len(selected_states),
            "registered_thread_count": len(thread_index),
            "status_count": len(rows),
            "pending_response_count": next_steps.count("await_whqr_binding_response"),
            "rejected_response_count": next_steps.count("resolve_whqr_clarification_response"),
            "ready_for_orchestration_count": next_steps.count("ready_for_orchestration"),
            "missing_thread_count": len(missing_thread_ids),
        },
        "missing_thread_ids": missing_thread_ids,
        "statuses": rows,
    }


@router.get("/api/v1/console/spatial-map")
def console_spatial_map():
    """Return the operator spatial-map panel read model."""
    deps.metrics.inc("requests_governed")
    return _spatial_map_console_payload()


@router.get("/api/v1/console/spatial-map/view", response_class=HTMLResponse)
def console_spatial_map_view():
    """Browser-facing read-only spatial-map operator panel."""

    deps.metrics.inc("requests_governed")
    return HTMLResponse(_render_spatial_map_console_html(_spatial_map_console_payload()))


@router.get("/api/v1/console/personal-assistant")
def console_personal_assistant():
    """Personal-assistant foundation console read model."""

    deps.metrics.inc("requests_governed")
    return _personal_assistant_console_payload()


@router.get("/api/v1/console/personal-assistant/view", response_class=HTMLResponse)
def console_personal_assistant_view():
    """Browser-facing read-only personal-assistant console panel."""

    deps.metrics.inc("requests_governed")
    return HTMLResponse(render_personal_assistant_console_html(_personal_assistant_console_payload()))


@router.get("/api/v1/console/operator-console-first")
def console_operator_console_first():
    """Operator Console First foundation panel read model."""

    deps.metrics.inc("requests_governed")
    try:
        return _operator_console_first_console_payload()
    except (RuntimeCoreInvariantError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "operator_console_first_projection_invalid",
                "message": str(exc),
            },
        ) from exc


def _personal_assistant_console_payload() -> dict[str, object]:
    """Build the foundation personal-assistant console payload."""

    return build_personal_assistant_console_read_model(generated_at=_utc_timestamp())


def _operator_console_first_console_payload() -> dict[str, object]:
    """Build the bounded OCF foundation projection without dispatch authority."""

    generated_at = _utc_timestamp()
    runtime = OperatorConsoleFirstRuntime(clock=lambda: generated_at)
    snapshot = StateSnapshot(
        source="console.foundation.operator_console_first",
        captured_at=generated_at,
        expires_at="2999-01-01T00:00:00Z",
        state_hash="foundation-operator-console-first-state",
        trust_level=1.0,
    )
    episode = runtime.capture_episode(
        operator_id="foundation-operator",
        raw_request="Review the proposed Operator Console First execution plan.",
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        governed_goal={
            "objective": "surface_operator_console_first_panels",
            "closure": "read_model_only",
        },
        scope={
            "surface": "operator_console",
            "mode": "foundation_read_only",
        },
        snapshot=snapshot,
    )
    action = ConsolePlannedAction(
        action_id="ocf-foundation-plan-review",
        capability_id="capability.operator_console_first.review",
        intent_class=ConsoleIntentClass.EXTERNAL_IRREVERSIBLE,
        risk_score=60,
        expected_effects=("operator_plan_reviewed",),
        side_effects_declared=True,
        side_effects=SideEffectManifest(reads_data=True),
        recovery_class=RecoveryClass.R0_NONE,
        evidence_required=(
            "operator_approval_receipt",
            "independent_verification_record",
        ),
    )
    planned_episode = runtime.plan_episode(episode, (action,))
    payload = build_operator_console_read_model(planned_episode, generated_at=generated_at)
    payload.update(
        {
            "governed": True,
            "read_only": True,
            "route_boundary": {
                "projection_only": True,
                "execution_allowed": False,
                "dispatch_allowed": False,
                "approval_write_allowed": False,
                "gateway_dispatch_allowed": False,
            },
        }
    )
    return payload


def _utc_timestamp() -> str:
    """Return an ISO UTC timestamp for read-model generation."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _spatial_map_console_payload() -> dict[str, object]:
    """Build panel groupings from the bounded spatial governance map."""

    spatial_map = build_gateway_spatial_map(production_readiness_checks()).to_dict()
    paths = {str(path.get("id", "")): path for path in _sequence_of_mappings(spatial_map.get("paths"))}
    judgments = {
        str(judgment.get("path_id", "")): judgment
        for judgment in _sequence_of_mappings(spatial_map.get("judgments"))
    }
    statuses = [str(judgment.get("status", "unknown")) for judgment in judgments.values()]
    panels = [
        _spatial_path_panel(
            "Runtime Path Panel",
            (
                "dashboard_health_check",
                "governed_request_flow",
                "bounded_exception_response",
                "cache_lookup_path",
                "idempotency_suppression_path",
                "request_deduplication_path",
                "rate_limit_guard_path",
                "backpressure_status_path",
            ),
            paths,
            judgments,
        ),
        _spatial_path_panel(
            "Launch Boundary Panel",
            (
                "readiness_launch_gate",
                "production_health_declaration_path",
                "stateful_command_path",
                "capability_execution_path",
                "finance_approval_path",
                "payment_provider_handoff_path",
                "observability_evidence_path",
                "support_escalation_path",
                "rollback_recovery_path",
                "proof_verification_path",
                "audit_chain_verification_path",
                "runtime_conformance_path",
            ),
            paths,
            judgments,
        ),
        _spatial_path_panel(
            "Fracture Panel",
            ("source_to_secret",),
            paths,
            judgments,
        ),
    ]
    return {
        "spatial_map": spatial_map,
        "summary": {
            "allowed_paths": statuses.count("allowed"),
            "blocked_paths": statuses.count("blocked"),
            "unknown_paths": statuses.count("unknown"),
            "blocker_count": len(spatial_map.get("blockers", ())),
            "panel_path_count": sum(len(panel["paths"]) for panel in panels),
        },
        "panels": panels,
        "governed": True,
    }


def _spatial_path_panel(
    title: str,
    path_ids: tuple[str, ...],
    paths: dict[str, dict[str, object]],
    judgments: dict[str, dict[str, object]],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for path_id in path_ids:
        path = paths.get(path_id, {})
        judgment = judgments.get(path_id, {})
        rows.append(
            {
                "path_id": path_id,
                "source": str(path.get("source", "")),
                "target": str(path.get("target", "")),
                "crosses": _string_sequence(path.get("crosses", ())),
                "status": str(judgment.get("status", "unknown")),
                "reasons": _string_sequence(judgment.get("reasons", ())),
                "witness": _string_sequence(judgment.get("witness", ())),
            }
        )
    return {"title": title, "paths": rows}


def _render_spatial_map_console_html(payload: dict[str, object]) -> str:
    """Render the spatial map panel as escaped operator HTML."""

    spatial_map = _mapping_value(payload, "spatial_map")
    summary = _mapping_value(payload, "summary")
    frame = escape(str(spatial_map.get("frame", "")))
    blockers = [escape(str(blocker)) for blocker in spatial_map.get("blockers", ()) if isinstance(blocker, str)]
    blocker_items = "\n".join(f"<li><code>{blocker}</code></li>" for blocker in blockers)
    if not blocker_items:
        blocker_items = "<li>No blockers</li>"
    metrics = [
        ("Allowed Paths", summary.get("allowed_paths", 0)),
        ("Unknown Paths", summary.get("unknown_paths", 0)),
        ("Blocked Paths", summary.get("blocked_paths", 0)),
        ("Blockers", summary.get("blocker_count", 0)),
    ]
    metric_items = "\n".join(
        "<li>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</li>"
        for label, value in metrics
    )
    panels = "\n".join(_spatial_panel_table(panel) for panel in _sequence_of_mappings(payload.get("panels")))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Spatial Governance Console</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #17202a; background: #fafbfc; overflow-x: hidden; }}
    header {{ margin-bottom: 20px; overflow-wrap: anywhere; }}
    nav {{ display: flex; flex-wrap: wrap; gap: 14px; margin: 12px 0 18px; }}
    a {{ color: #0f766e; }}
    code {{ overflow-wrap: anywhere; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; padding: 0; }}
    .metrics li {{ list-style: none; border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #ffffff; }}
    .metrics span {{ display: block; color: #57606a; font-size: 12px; }}
    .metrics strong {{ display: block; margin-top: 4px; font-size: 18px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; background: #ffffff; }}
    .table-scroll {{ width: 100%; overflow-x: auto; }}
    .table-scroll table {{ min-width: 860px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; text-align: left; font-size: 14px; vertical-align: top; }}
    th {{ background: #f6f8fa; }}
    .status {{ font-weight: 700; }}
    .allowed {{ color: #166534; }}
    .unknown {{ color: #854d0e; }}
    .blocked {{ color: #9f1239; }}
    @media (max-width: 480px) {{
      body {{ margin: 16px; }}
      h1 {{ font-size: 28px; line-height: 1.18; max-width: 320px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu Spatial<br>Governance Console</h1>
    <nav>
      <a href="/api/v1/console/spatial-map">json read model</a>
      <a href="/api/v1/console">full console json</a>
    </nav>
    <p>Frame: <code>{frame}</code></p>
    <ul class="metrics">
      {metric_items}
    </ul>
  </header>
  {panels}
  <section>
    <h2>Blockers</h2>
    <ul>
      {blocker_items}
    </ul>
  </section>
</body>
</html>"""


def _spatial_panel_table(panel: dict[str, object]) -> str:
    title = escape(str(panel.get("title", "")))
    rows = _sequence_of_mappings(panel.get("paths"))
    body = "\n".join(
        "<tr>"
        f"<td><code>{escape(str(row.get('path_id', '')))}</code></td>"
        f"<td>{escape(str(row.get('source', '')))}</td>"
        f"<td>{escape(str(row.get('target', '')))}</td>"
        f"<td>{escape(', '.join(str(item) for item in row.get('crosses', ())))}</td>"
        f"<td class=\"status {escape(str(row.get('status', 'unknown')))}\">{escape(str(row.get('status', 'unknown')))}</td>"
        f"<td>{escape(', '.join(str(item) for item in row.get('reasons', ())))}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"6\">No paths</td></tr>"
    return f"""
  <section>
    <h2>{title}</h2>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Path</th><th>Source</th><th>Target</th><th>Boundaries</th><th>Status</th><th>Reasons</th></tr></thead>
        <tbody>{body}</tbody>
      </table>
    </div>
  </section>"""


def _render_note_memory_console_html(payload: dict[str, object]) -> str:
    """Render the note-memory read model as a compact escaped HTML console."""

    summary = _mapping_value(payload, "summary")
    extension = _mapping_value(payload, "extension")
    status = escape(str(payload.get("status", "")))
    extension_state = escape(str(extension.get("state", "")))
    error = escape(str(payload.get("error", "")))
    filters = _mapping_value(payload, "filters")
    retrieval_receipt_filter = escape(str(filters.get("retrieval_receipt_ref", "")))
    retrieval_citing_note_filter = escape(str(filters.get("retrieval_citing_note_ref", "")))
    filter_parts = []
    if retrieval_receipt_filter:
        filter_parts.append(f"receipt=<code>{retrieval_receipt_filter}</code>")
    if retrieval_citing_note_filter:
        filter_parts.append(f"citing_note=<code>{retrieval_citing_note_filter}</code>")
    filter_block = f"<p>Filter: {' | '.join(filter_parts)}</p>" if filter_parts else ""
    metrics = [
        ("Events", summary.get("event_count", 0)),
        ("Active Notes", summary.get("active_note_count", 0)),
        ("Rejected Deltas", summary.get("rejected_delta_count", 0)),
        ("Expiring Notes", summary.get("expiring_note_count", 0)),
        ("Pending Promotions", summary.get("pending_promotion_count", 0)),
        ("Memory Anchors", summary.get("memory_anchor_count", 0)),
        ("Episode Capsules", summary.get("episode_capsule_count", 0)),
        ("Contradictions", summary.get("contradiction_count", 0)),
        ("Retrieval Influence", summary.get("retrieval_influence_count", 0)),
        ("Retrieval Influence Total", summary.get("retrieval_influence_total_count", 0)),
        ("Retrieval Receipts", summary.get("retrieval_receipt_count", 0)),
        ("Retrieval Receipts Total", summary.get("retrieval_receipt_total_count", 0)),
        ("Index Proof", summary.get("index_proof_state", "Unknown")),
    ]
    metric_items = "\n".join(
        "<li>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</li>"
        for label, value in metrics
    )
    error_block = f"<p class=\"error\">{error}</p>" if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mullu Note Memory Console</title>
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
    .error {{ color: #9f1239; font-weight: 600; }}
  </style>
</head>
<body>
  <header>
    <h1>Mullu Note Memory Console</h1>
    <nav>
      <a href="/api/v1/console/note-memory">json read model</a>
      <a href="/api/v1/console">full console json</a>
    </nav>
    <p>Status: <strong>{status}</strong> | Extension: <strong>{extension_state}</strong></p>
    {filter_block}
    {error_block}
    <ul class="metrics">
      {metric_items}
    </ul>
  </header>
  {_note_memory_event_table("Recent Notes", payload.get("recent_notes", ()))}
  {_note_memory_event_table("Rejected Deltas", payload.get("rejected_deltas", ()))}
  {_note_memory_event_table("Episode Capsules", payload.get("episode_capsules", ()))}
  {_note_memory_retrieval_receipt_table(payload.get("retrieval_receipts", ()))}
  {_note_memory_retrieval_influence_table(payload.get("retrieval_influence", ()))}
  {_note_memory_promotion_table(payload.get("pending_promotions", ()))}
  {_note_memory_event_table("Audit Events", payload.get("audit_events", ()))}
</body>
</html>"""


def _note_memory_event_table(title: str, raw_rows: object) -> str:
    rows = _sequence_of_mappings(raw_rows)
    body = "\n".join(
        "<tr>"
        f"<td>{escape(str(row.get('event_seq', '')))}</td>"
        f"<td>{escape(str(row.get('kind', '')))}</td>"
        f"<td>{escape(str(row.get('action', '')))}</td>"
        f"<td>{escape(str(row.get('scope', '')))}</td>"
        f"<td>{escape(str(row.get('proof_state', '')))}</td>"
        f"<td>{escape(str(row.get('content_summary', '')))}</td>"
        f"<td>{escape(str(row.get('source_ref', '')))}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"7\">No records</td></tr>"
    return f"""
  <section>
    <h2>{escape(title)}</h2>
    <table>
      <thead><tr><th>Seq</th><th>Kind</th><th>Action</th><th>Scope</th><th>Proof</th><th>Summary</th><th>Source</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _note_memory_retrieval_receipt_table(raw_rows: object) -> str:
    rows = _sequence_of_mappings(raw_rows)
    body = "\n".join(
        "<tr>"
        f"<td>{escape(str(row.get('receipt_id', '')))}</td>"
        f"<td>{escape(str(row.get('citation_count', '')))}</td>"
        f"<td>{escape(str(row.get('citing_note_id_count', '')))}</td>"
        f"<td>{escape(', '.join(str(item) for item in row.get('sample_citing_note_ids', ())))}</td>"
        f"<td>{escape(str(row.get('latest_cited_at', '')))}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"5\">No retrieval receipts</td></tr>"
    return f"""
  <section>
    <h2>Retrieval Receipts</h2>
    <table>
      <thead><tr><th>Receipt</th><th>Citations</th><th>Notes</th><th>Sample Notes</th><th>Latest Citation</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _note_memory_retrieval_influence_table(raw_rows: object) -> str:
    rows = _sequence_of_mappings(raw_rows)
    body = "\n".join(
        "<tr>"
        f"<td>{escape(str(row.get('receipt_id', '')))}</td>"
        f"<td>{escape(str(row.get('citing_event_seq', '')))}</td>"
        f"<td>{escape(str(row.get('citing_kind', '')))}</td>"
        f"<td>{escape(str(row.get('citing_action', '')))}</td>"
        f"<td>{escape(str(row.get('citing_note_id', '')))}</td>"
        f"<td>{escape(str(row.get('source_ref', '')))}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"6\">No retrieval influence links</td></tr>"
    return f"""
  <section>
    <h2>Retrieval Influence</h2>
    <table>
      <thead><tr><th>Receipt</th><th>Seq</th><th>Kind</th><th>Action</th><th>Citing Note</th><th>Source</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _note_memory_promotion_table(raw_rows: object) -> str:
    rows = _sequence_of_mappings(raw_rows)
    body = "\n".join(
        "<tr>"
        f"<td>{escape(str(row.get('promotion_id', '')))}</td>"
        f"<td>{escape(str(row.get('source_note_id', '')))}</td>"
        f"<td>{escape(str(row.get('source_event_seq', '')))}</td>"
        f"<td>{escape(str(row.get('queued_at', '')))}</td>"
        "</tr>"
        for row in rows
    )
    if not body:
        body = "<tr><td colspan=\"4\">No pending promotions</td></tr>"
    return f"""
  <section>
    <h2>Pending Promotions</h2>
    <table>
      <thead><tr><th>Promotion</th><th>Source Note</th><th>Source Seq</th><th>Queued</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _mapping_value(value: dict[str, object], key: str) -> dict[str, object]:
    child = value.get(key)
    return dict(child) if isinstance(child, dict) else {}


def _sequence_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value]


def _job_conversation_thread_index() -> Mapping[str, ConversationThread]:
    raw_index = deps.get("job_conversation_threads")
    if not isinstance(raw_index, Mapping):
        raise HTTPException(
            status_code=500,
            detail={
                "error": "job_conversation_thread_index_invalid",
                "message": "job_conversation_threads dependency must be a mapping",
            },
        )
    index: dict[str, ConversationThread] = {}
    for thread_id, thread in raw_index.items():
        if isinstance(thread_id, str) and isinstance(thread, ConversationThread):
            index[thread_id] = thread
    return index


@router.get("/api/v1/console")
def full_console():
    """Complete operator console — all views in one call."""
    deps.metrics.inc("requests_governed")
    return {
        "home": console_home(),
        "checkpoints": console_checkpoints(),
        "providers": console_providers(),
        "scheduler": console_scheduler(),
        "note_memory": console_note_memory(),
        "whqr_clarifications": console_whqr_binding_clarifications(),
        "spatial_map": build_gateway_spatial_map(production_readiness_checks()).to_dict(),
        "personal_assistant": _personal_assistant_console_payload(),
        "operator_console_first": _operator_console_first_console_payload(),
        "governed": True,
    }
