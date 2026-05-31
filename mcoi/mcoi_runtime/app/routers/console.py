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
"""
from __future__ import annotations

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


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
    tenant_id: str | None = None,
    outcome: str | None = None,
    limit: int = 50,
):
    """Operator runs view — recent governed actions with status."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(
        tenant_id=tenant_id,
        outcome=outcome,
        limit=limit,
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
    tenant_id: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
):
    """Operator audit view — searchable event history."""
    deps.metrics.inc("requests_governed")
    entries = deps.audit_trail.query(
        tenant_id=tenant_id,
        action=action,
        outcome=outcome,
        limit=limit,
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
            "retrieval_influence_count": 0,
            "index_proof_state": "Unknown",
        },
        "filters": {
            "retrieval_receipt_ref": "",
        },
        "recent_notes": [],
        "rejected_deltas": [],
        "expiring_notes": [],
        "pending_promotions": [],
        "memory_anchors": [],
        "episode_capsules": [],
        "contradictions": [],
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
def console_note_memory(limit: int = 25, retrieval_receipt_ref: str = ""):
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
def console_note_memory_view(limit: int = 25, retrieval_receipt_ref: str = ""):
    """Browser-facing read-only note-memory operator view."""

    payload = console_note_memory(limit=limit, retrieval_receipt_ref=retrieval_receipt_ref)
    return HTMLResponse(_render_note_memory_console_html(payload))


def _render_note_memory_console_html(payload: dict[str, object]) -> str:
    """Render the note-memory read model as a compact escaped HTML console."""

    summary = _mapping_value(payload, "summary")
    extension = _mapping_value(payload, "extension")
    status = escape(str(payload.get("status", "")))
    extension_state = escape(str(extension.get("state", "")))
    error = escape(str(payload.get("error", "")))
    filters = _mapping_value(payload, "filters")
    retrieval_receipt_filter = escape(str(filters.get("retrieval_receipt_ref", "")))
    filter_block = f"<p>Filter: <code>{retrieval_receipt_filter}</code></p>" if retrieval_receipt_filter else ""
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
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


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
        "governed": True,
    }
