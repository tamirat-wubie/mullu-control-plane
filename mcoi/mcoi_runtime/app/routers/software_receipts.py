"""Purpose: HTTP access to software-change lifecycle receipts and review sync.
Governance scope: MUSIA-gated receipt list/get/replay and review request materialization.
Dependencies: FastAPI, MUSIA auth dependencies, software receipt store, review queue.
Invariants:
  - Receipt query routes require musia.read.
  - Review synchronization requires musia.write.
  - Review decisions append terminal receipt witnesses without mutating workspace state.
  - Replay requires a terminally closed receipt chain.
  - Store errors are bounded at the HTTP boundary.
"""
from __future__ import annotations

from html import escape
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.auth_context import bind_claimed_actor
from mcoi_runtime.app.routers.musia_auth import require_read, require_write
from mcoi_runtime.app.software_receipt_review_queue import SoftwareReceiptReviewQueue
from mcoi_runtime.core.private_pilot_story import (
    DEFAULT_PRIVATE_PILOT_ACTOR_ID,
    DEFAULT_PRIVATE_PILOT_CASE_ID,
    DEFAULT_PRIVATE_PILOT_ORG_ID,
    PrivatePilotStoryError,
    PrivatePilotStoryRequest,
    build_private_pilot_operator_view,
    build_private_pilot_story,
)
from mcoi_runtime.core.sdlc_dashboard import (
    SdlcDashboardError,
    build_sdlc_dashboard_summary,
)
from mcoi_runtime.contracts.review import ReviewDecision, ReviewRequest
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.errors import PersistenceError
from mcoi_runtime.persistence.software_change_receipt_store import (
    SoftwareChangeReceiptStore,
)


router = APIRouter(prefix="/software/receipts", tags=["software-receipts"])
_FALLBACK_STORE = SoftwareChangeReceiptStore()


class SoftwareReceiptEnvelope(BaseModel):
    """HTTP response envelope for software lifecycle receipts."""

    operation: str
    tenant_id: str
    count: int
    receipts: list[dict[str, Any]]
    request_id: str | None = None
    receipt_id: str | None = None
    stage: str | None = None
    found: bool | None = None
    terminal_closed: bool | None = None
    requires_operator_review: bool | None = None
    review_signal_count: int | None = None
    review_signals: list[dict[str, Any]] | None = None
    review_request_count: int | None = None
    review_requests: list[dict[str, Any]] | None = None
    pending_review_count: int | None = None
    review_decision: dict[str, Any] | None = None
    gate_allowed: bool | None = None
    gate_reason: str | None = None
    governed: bool = True


class SoftwareReceiptReviewDecisionBody(BaseModel):
    """HTTP request body for deciding a software receipt review."""

    reviewer_id: str = Field(..., min_length=1)
    approved: bool
    comment: str | None = None


class SoftwareReceiptDashboardEnvelope(BaseModel):
    """HTTP response envelope for live software receipt dashboard counts."""

    operation: str
    tenant_id: str
    dashboard: dict[str, Any]
    total_receipts: int
    request_count: int
    terminal_request_count: int
    open_request_count: int
    requires_operator_review: bool
    review_signal_count: int
    governed: bool = True


class SdlcDashboardEnvelope(BaseModel):
    """HTTP response envelope for the read-only SDLC dashboard summary."""

    operation: str
    tenant_id: str
    dashboard: dict[str, Any]
    stage_count: int
    blocker_count: int
    evidence_count: int
    receipt_count: int
    governed: bool = True


class PrivatePilotStoryEnvelope(BaseModel):
    """HTTP response envelope for the read-only private pilot story."""

    operation: str
    tenant_id: str
    story: dict[str, Any]
    stage_count: int
    uao_branch_count: int
    receipt_count: int
    governed: bool = True


class PrivatePilotOperatorViewEnvelope(BaseModel):
    """HTTP response envelope for the private pilot operator view."""

    operation: str
    tenant_id: str
    operator_view: dict[str, Any]
    timeline_count: int
    receipt_count: int
    operator_ready: bool
    governed: bool = True


def _bounded_http_error(summary: str, exc: Exception) -> dict[str, str]:
    return {"error": summary, "type": type(exc).__name__}


def _receipt_store() -> SoftwareChangeReceiptStore:
    try:
        store = deps.get("software_receipt_store")
    except RuntimeError:
        return _FALLBACK_STORE
    if not isinstance(store, SoftwareChangeReceiptStore):
        raise HTTPException(
            status_code=503,
            detail={"error": "software_receipt_store_invalid"},
        )
    return store


def _review_queue() -> SoftwareReceiptReviewQueue:
    try:
        queue = deps.get("software_receipt_review_queue")
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "software_receipt_review_queue_unavailable"},
        ) from exc
    if not isinstance(queue, SoftwareReceiptReviewQueue):
        raise HTTPException(
            status_code=503,
            detail={"error": "software_receipt_review_queue_invalid"},
        )
    return queue


def _serialize_receipts(
    receipts: tuple[SoftwareChangeReceipt, ...],
) -> list[dict[str, Any]]:
    return [receipt.to_json_dict() for receipt in receipts]


def _serialize_review_requests(
    requests: tuple[ReviewRequest, ...],
) -> list[dict[str, Any]]:
    return [request.to_json_dict() for request in requests]


def _serialize_review_decision(decision: ReviewDecision) -> dict[str, Any]:
    return decision.to_json_dict()


def _review_signals(receipts: tuple[SoftwareChangeReceipt, ...]) -> list[dict[str, str]]:
    return [
        {
            "request_id": receipt.request_id,
            "latest_receipt_id": receipt.receipt_id,
            "latest_stage": receipt.stage.value,
            "latest_outcome": receipt.outcome,
            "reason": "software_change_receipt_chain_open",
        }
        for receipt in receipts
    ]


def _private_pilot_story_read_model(
    *,
    tenant_id: str,
    org_id: str,
    case_id: str,
    actor_id: str,
) -> dict[str, Any]:
    try:
        return build_private_pilot_story(
            PrivatePilotStoryRequest(
                tenant_id=tenant_id,
                org_id=org_id,
                case_id=case_id,
                actor_id=actor_id,
            )
        )
    except PrivatePilotStoryError as exc:
        raise HTTPException(
            status_code=503,
            detail=_bounded_http_error("private pilot story unavailable", exc),
        ) from exc


def _private_pilot_query_string(*, org_id: str, case_id: str, actor_id: str) -> str:
    return urlencode({"org_id": org_id, "case_id": case_id, "actor_id": actor_id})


def _html_cell(value: Any) -> str:
    if isinstance(value, dict):
        text = ", ".join(f"{key}: {item}" for key, item in sorted(value.items()))
    elif isinstance(value, (list, tuple)):
        text = ", ".join(str(item) for item in value)
    else:
        text = str(value)
    return escape(text)


def _html_table(title: str, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"<section><h2>{escape(title)}</h2><p>No records.</p></section>"
    heading = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{_html_cell(row.get(column, ''))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"""<section>
  <h2>{escape(title)}</h2>
  <table>
    <thead><tr>{heading}</tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
</section>"""


def _render_private_pilot_operator_view_html(
    operator_view: dict[str, Any],
    *,
    query_string: str,
) -> str:
    request = operator_view.get("request", {})
    request = request if isinstance(request, dict) else {}
    summary = operator_view.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    authority = operator_view.get("authority_boundary", {})
    authority = authority if isinstance(authority, dict) else {}
    receipt_panel = operator_view.get("receipt_panel", {})
    receipt_panel = receipt_panel if isinstance(receipt_panel, dict) else {}
    timeline_rows: list[dict[str, Any]] = []
    for item in operator_view.get("timeline", []):
        if not isinstance(item, dict):
            continue
        source_panel = item.get("source_refs", {})
        receipt_refs = item.get("receipt_refs", {})
        timeline_rows.append({
            "order": item.get("order", ""),
            "step": item.get("label", ""),
            "status": item.get("status", ""),
            "outcome": item.get("outcome", ""),
            "source_refs": source_panel.get("refs", []) if isinstance(source_panel, dict) else [],
            "receipt_refs": receipt_refs.get("refs", []) if isinstance(receipt_refs, dict) else [],
            "execution_allowed": item.get("execution_allowed", False),
        })
    check_rows = [
        {
            "check": check.get("check_id", ""),
            "passed": check.get("passed", False),
            "proof_state": check.get("proof_state", ""),
            "reason": check.get("reason_code", ""),
        }
        for check in operator_view.get("operator_checks", [])
        if isinstance(check, dict)
    ]
    summary_rows = [
        {"metric": "tenant", "value": request.get("tenant_id", "")},
        {"metric": "organization", "value": request.get("org_id", "")},
        {"metric": "case", "value": request.get("case_id", "")},
        {"metric": "actor", "value": request.get("actor_id", "")},
        {"metric": "composition", "value": summary.get("composition_outcome", "")},
        {"metric": "pilot outcome", "value": summary.get("pilot_execution_outcome", "")},
        {"metric": "operator outcome", "value": summary.get("operator_outcome", "")},
        {"metric": "next action", "value": summary.get("next_action", "")},
    ]
    authority_rows = [
        {"boundary": key, "granted": value}
        for key, value in sorted(authority.items())
    ]
    receipt_rows = [
        {"metric": "receipts", "value": receipt_panel.get("receipt_count", 0)},
        {"metric": "UAO refs", "value": receipt_panel.get("uao_count", 0)},
        {"metric": "causal traces", "value": receipt_panel.get("causal_trace_count", 0)},
    ]
    title = "Mullu Private Pilot Operator View"
    json_url = f"/software/receipts/private-pilot/operator-view?{query_string}"
    story_url = f"/software/receipts/private-pilot/story?{query_string}"
    sdlc_url = "/software/receipts/sdlc/dashboard"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; color: #1f2937; background: #f6f7f8; }}
    header {{ background: #1d3557; color: #ffffff; padding: 24px 28px; }}
    main {{ max-width: 1240px; margin: 0 auto; padding: 22px; }}
    nav {{ display: flex; gap: 14px; margin-top: 12px; flex-wrap: wrap; }}
    nav a {{ color: #d6ecff; }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: 0; }}
    h2 {{ margin: 26px 0 10px; font-size: 18px; letter-spacing: 0; }}
    .status {{ margin-top: 8px; color: #dce8f5; }}
    table {{ border-collapse: collapse; width: 100%; background: #ffffff; }}
    th, td {{ border: 1px solid #d5dbe3; padding: 8px; text-align: left; vertical-align: top; font-size: 14px; overflow-wrap: anywhere; }}
    th {{ background: #edf2f7; color: #243047; }}
    section {{ margin-bottom: 22px; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <div class="status">Case <strong>{escape(str(request.get("case_id", "")))}</strong> | Tenant <strong>{escape(str(request.get("tenant_id", "")))}</strong></div>
    <nav>
      <a href="{escape(json_url)}">json operator view</a>
      <a href="{escape(story_url)}">json story</a>
      <a href="{escape(sdlc_url)}">SDLC dashboard</a>
    </nav>
  </header>
  <main>
    {_html_table("Summary", ("metric", "value"), summary_rows)}
    {_html_table("Chain", ("order", "step", "status", "outcome", "source_refs", "receipt_refs", "execution_allowed"), timeline_rows)}
    {_html_table("Authority Boundary", ("boundary", "granted"), authority_rows)}
    {_html_table("Operator Checks", ("check", "passed", "proof_state", "reason"), check_rows)}
    {_html_table("Receipts", ("metric", "value"), receipt_rows)}
  </main>
</body>
</html>"""


@router.get("", response_model=SoftwareReceiptEnvelope)
def list_software_receipts(
    request_id: str | None = None,
    stage: str | None = None,
    limit: int = Query(default=50, ge=1),
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """List stored lifecycle receipts with optional request/stage filters."""
    stage_filter = None
    try:
        if stage:
            stage_filter = SoftwareChangeReceiptStage(stage)
        receipts = _receipt_store().list_receipts(
            request_id=request_id,
            stage=stage_filter,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("invalid receipt stage", exc),
        ) from exc
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt query rejected", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="list",
        tenant_id=tenant_id,
        request_id=request_id,
        stage=stage_filter.value if stage_filter is not None else None,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
    )


@router.get("/replay/{request_id}", response_model=SoftwareReceiptEnvelope)
def replay_software_receipts(
    request_id: str,
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """Replay a terminally closed receipt chain for one request."""
    try:
        receipts = _receipt_store().replay_request(request_id)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=404,
            detail=_bounded_http_error("receipt replay unavailable", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="replay",
        tenant_id=tenant_id,
        request_id=request_id,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
        terminal_closed=True,
    )


@router.post("/review/sync", response_model=SoftwareReceiptEnvelope)
def sync_software_receipt_reviews(
    limit: int = Query(default=10, ge=1),
    tenant_id: str = Depends(require_write),
) -> SoftwareReceiptEnvelope:
    """Materialize open receipt-chain signals as canonical review requests."""
    try:
        queue = _review_queue()
        submitted = queue.sync(limit=limit)
        pending = queue.pending()
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt review sync rejected", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="review_sync",
        tenant_id=tenant_id,
        count=len(submitted),
        receipts=[],
        review_request_count=len(submitted),
        review_requests=_serialize_review_requests(submitted),
        pending_review_count=len(pending),
        requires_operator_review=bool(pending),
    )


@router.get("/review/requests", response_model=SoftwareReceiptEnvelope)
def list_software_receipt_review_requests(
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """List pending canonical review requests for software receipt chains."""
    queue = _review_queue()
    pending = queue.pending()
    return SoftwareReceiptEnvelope(
        operation="review_requests",
        tenant_id=tenant_id,
        count=len(pending),
        receipts=[],
        review_request_count=len(pending),
        review_requests=_serialize_review_requests(pending),
        pending_review_count=len(pending),
        requires_operator_review=bool(pending),
    )


@router.post("/review/requests/{request_id}/decision", response_model=SoftwareReceiptEnvelope)
def decide_software_receipt_review_request(
    request_id: str,
    body: SoftwareReceiptReviewDecisionBody,
    request: Request,
    tenant_id: str = Depends(require_write),
) -> SoftwareReceiptEnvelope:
    """Approve or reject a software receipt review request."""
    reviewer_id = bind_claimed_actor(request, body.reviewer_id)
    queue = _review_queue()
    try:
        decision = queue.decide(
            request_id=request_id,
            reviewer_id=reviewer_id,
            approved=body.approved,
            comment=body.comment,
        )
        gate_allowed = decision.is_approved
        gate_reason = "review approved" if decision.is_approved else "review not approved"
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=_bounded_http_error("software receipt review decision unavailable", exc),
        ) from exc
    pending = queue.pending()
    return SoftwareReceiptEnvelope(
        operation="review_decision",
        tenant_id=tenant_id,
        request_id=request_id,
        count=1,
        receipts=[],
        review_decision=_serialize_review_decision(decision),
        pending_review_count=len(pending),
        requires_operator_review=bool(pending),
        gate_allowed=gate_allowed,
        gate_reason=gate_reason,
    )


@router.get("/review", response_model=SoftwareReceiptEnvelope)
def review_software_receipts(
    limit: int = Query(default=10, ge=1),
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """List latest receipt for each request chain needing operator review."""
    try:
        receipts = _receipt_store().review_receipts(limit=limit)
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt review query rejected", exc),
        ) from exc
    return SoftwareReceiptEnvelope(
        operation="review",
        tenant_id=tenant_id,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
        requires_operator_review=bool(receipts),
        review_signal_count=len(receipts),
        review_signals=_review_signals(receipts),
    )


@router.get("/dashboard", response_model=SoftwareReceiptDashboardEnvelope)
def software_receipt_dashboard(
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptDashboardEnvelope:
    """Return live software receipt lifecycle counts without mutating state."""

    try:
        dashboard = _receipt_store().summary()
    except PersistenceError as exc:
        raise HTTPException(
            status_code=400,
            detail=_bounded_http_error("receipt dashboard query rejected", exc),
        ) from exc
    return SoftwareReceiptDashboardEnvelope(
        operation="dashboard",
        tenant_id=tenant_id,
        dashboard=dashboard,
        total_receipts=int(dashboard["total_receipts"]),
        request_count=int(dashboard["request_count"]),
        terminal_request_count=int(dashboard["terminal_request_count"]),
        open_request_count=int(dashboard["open_request_count"]),
        requires_operator_review=bool(dashboard["requires_operator_review"]),
        review_signal_count=int(dashboard["review_signal_count"]),
    )


@router.get("/sdlc/dashboard", response_model=SdlcDashboardEnvelope)
def sdlc_dashboard_summary(
    tenant_id: str = Depends(require_read),
) -> SdlcDashboardEnvelope:
    """Return the read-only SDLC change-to-closure dashboard summary."""

    try:
        dashboard = build_sdlc_dashboard_summary()
    except SdlcDashboardError as exc:
        raise HTTPException(
            status_code=503,
            detail=_bounded_http_error("sdlc dashboard unavailable", exc),
        ) from exc
    return SdlcDashboardEnvelope(
        operation="sdlc_dashboard",
        tenant_id=tenant_id,
        dashboard=dashboard,
        stage_count=int(dashboard["stage_count"]),
        blocker_count=int(dashboard["blocker_count"]),
        evidence_count=int(dashboard["evidence_count"]),
        receipt_count=int(dashboard["receipt_count"]),
    )


@router.get("/private-pilot/story", response_model=PrivatePilotStoryEnvelope)
def private_pilot_story_summary(
    org_id: str = Query(default=DEFAULT_PRIVATE_PILOT_ORG_ID, min_length=1),
    case_id: str = Query(default=DEFAULT_PRIVATE_PILOT_CASE_ID, min_length=1),
    actor_id: str = Query(default=DEFAULT_PRIVATE_PILOT_ACTOR_ID, min_length=1),
    tenant_id: str = Depends(require_read),
) -> PrivatePilotStoryEnvelope:
    """Return the read-only OrgOS-to-dashboard private pilot story."""

    story = _private_pilot_story_read_model(
        tenant_id=tenant_id,
        org_id=org_id,
        case_id=case_id,
        actor_id=actor_id,
    )
    return PrivatePilotStoryEnvelope(
        operation="private_pilot_story",
        tenant_id=tenant_id,
        story=story,
        stage_count=int(story["stage_count"]),
        uao_branch_count=int(story["uao_branch_count"]),
        receipt_count=int(story["receipt_count"]),
    )


@router.get("/private-pilot/operator-view", response_model=PrivatePilotOperatorViewEnvelope)
def private_pilot_operator_view(
    org_id: str = Query(default=DEFAULT_PRIVATE_PILOT_ORG_ID, min_length=1),
    case_id: str = Query(default=DEFAULT_PRIVATE_PILOT_CASE_ID, min_length=1),
    actor_id: str = Query(default=DEFAULT_PRIVATE_PILOT_ACTOR_ID, min_length=1),
    tenant_id: str = Depends(require_read),
) -> PrivatePilotOperatorViewEnvelope:
    """Return the read-only private pilot operator chain view."""

    story = _private_pilot_story_read_model(
        tenant_id=tenant_id,
        org_id=org_id,
        case_id=case_id,
        actor_id=actor_id,
    )
    try:
        operator_view = build_private_pilot_operator_view(story)
    except PrivatePilotStoryError as exc:
        raise HTTPException(
            status_code=503,
            detail=_bounded_http_error("private pilot operator view unavailable", exc),
        ) from exc
    receipt_panel = operator_view["receipt_panel"]
    summary = operator_view["summary"]
    return PrivatePilotOperatorViewEnvelope(
        operation="private_pilot_operator_view",
        tenant_id=tenant_id,
        operator_view=operator_view,
        timeline_count=int(operator_view["timeline_count"]),
        receipt_count=int(receipt_panel["receipt_count"]),
        operator_ready=bool(summary["operator_ready"]),
    )


@router.get("/private-pilot/operator-view/view", response_class=HTMLResponse)
def private_pilot_operator_view_html(
    org_id: str = Query(default=DEFAULT_PRIVATE_PILOT_ORG_ID, min_length=1),
    case_id: str = Query(default=DEFAULT_PRIVATE_PILOT_CASE_ID, min_length=1),
    actor_id: str = Query(default=DEFAULT_PRIVATE_PILOT_ACTOR_ID, min_length=1),
    tenant_id: str = Depends(require_read),
) -> HTMLResponse:
    """Return an escaped read-only HTML private pilot operator view."""

    story = _private_pilot_story_read_model(
        tenant_id=tenant_id,
        org_id=org_id,
        case_id=case_id,
        actor_id=actor_id,
    )
    try:
        operator_view = build_private_pilot_operator_view(story)
    except PrivatePilotStoryError as exc:
        raise HTTPException(
            status_code=503,
            detail=_bounded_http_error("private pilot operator view unavailable", exc),
        ) from exc
    query_string = _private_pilot_query_string(
        org_id=org_id,
        case_id=case_id,
        actor_id=actor_id,
    )
    return HTMLResponse(
        _render_private_pilot_operator_view_html(
            operator_view,
            query_string=query_string,
        )
    )


@router.get("/{receipt_id}", response_model=SoftwareReceiptEnvelope)
def get_software_receipt(
    receipt_id: str,
    tenant_id: str = Depends(require_read),
) -> SoftwareReceiptEnvelope:
    """Fetch a single software lifecycle receipt by id."""
    receipt = _receipt_store().get(receipt_id)
    receipts = tuple() if receipt is None else (receipt,)
    return SoftwareReceiptEnvelope(
        operation="get",
        tenant_id=tenant_id,
        receipt_id=receipt_id,
        count=len(receipts),
        receipts=_serialize_receipts(receipts),
        found=receipt is not None,
    )
