"""HTTP endpoints for /constructs/*."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mcoi_runtime.app.routers.constructs._governance import _governed_write
from mcoi_runtime.app.routers.constructs._helpers import (
    _construct_to_payload,
    _resolve_uuid,
)
from mcoi_runtime.app.routers.constructs._models import (
    BoundaryCreatePayload,
    CausationCreatePayload,
    ChangeCreatePayload,
    ConstraintCreatePayload,
    ConstructListResponse,
    ConstructPayload,
    RunDeleteResponse,
    RunExport,
    StateCreatePayload,
)
from mcoi_runtime.app.routers.constructs._pagination import (
    PAGE_SIZE_MAX,
    _paginate_cursor,
    _paginate_slice,
    _validate_cursor_limit,
    _validate_pagination,
)
from mcoi_runtime.app.routers.musia_auth import (
    require_admin,
    require_read,
    require_write,
)
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    ConstructBase,
    Constraint,
    State,
)
from mcoi_runtime.substrate.registry_store import STORE


router = APIRouter(prefix="/constructs", tags=["constructs"])


def _construct_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


# ---- Reads ----


@router.get("", response_model=ConstructListResponse)
def list_constructs(
    tier: int | None = None,
    type_filter: str | None = None,
    run_id: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
    tenant_id: str = Depends(require_read),
) -> ConstructListResponse:
    """List constructs in a tenant's registry.

    Three pagination modes (mutually exclusive):
    1. None of (page/page_size/cursor/limit) → full unfiltered list (v4.13.x default).
    2. ``page_size=N`` (with optional ``page=K``) → offset pagination (v4.14.0+).
    3. ``limit=N`` (with optional ``cursor=...``) → cursor pagination (v4.23.0+).
       Stable under inserts/deletes between requests; sorted by UUID.

    If both offset and cursor params are passed, cursor takes precedence and
    offset params are ignored. ``total`` is always the unfiltered count of
    matches across all modes.
    """
    page, page_size = _validate_pagination(page, page_size)
    limit_validated = _validate_cursor_limit(limit)
    state = STORE.get_or_create(tenant_id)
    if run_id is not None:
        items: list[ConstructBase] = state.constructs_in_run(run_id)
    else:
        items = list(state.graph.constructs.values())
    if tier is not None:
        if not (1 <= tier <= 5):
            raise HTTPException(status_code=400, detail="tier must be in [1,5]")
        items = [c for c in items if c.tier.value == tier]
    if type_filter is not None:
        items = [c for c in items if c.type.value == type_filter]

    # by_type is computed across ALL matches (not just the page)
    by_type: dict[str, int] = {}
    for c in items:
        by_type[c.type.value] = by_type.get(c.type.value, 0) + 1

    # Cursor mode takes precedence when limit is provided. Offset mode
    # otherwise. Unpaginated when neither.
    next_cursor: str | None = None
    if limit_validated is not None or cursor is not None:
        effective_limit = limit_validated if limit_validated is not None else PAGE_SIZE_MAX
        page_items, next_cursor = _paginate_cursor(items, cursor, effective_limit)
        page = None
        page_size = None
        total_pages = None
        has_more = next_cursor is not None
    else:
        page_items, total_pages, has_more = _paginate_slice(items, page, page_size)

    return ConstructListResponse(
        total=len(items),
        by_type=by_type,
        constructs=[_construct_to_payload(c, state.tenant_id) for c in page_items],
        tenant_id=state.tenant_id,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
        next_cursor=next_cursor,
    )


@router.get("/{construct_id}", response_model=ConstructPayload)
def get_construct(
    construct_id: str,
    tenant_id: str = Depends(require_read),
) -> ConstructPayload:
    state = STORE.get_or_create(tenant_id)
    cid = _resolve_uuid(construct_id, "construct_id")
    c = state.graph.constructs.get(cid)
    if c is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "construct_not_found",
                "construct_id": str(cid),
                "tenant_id": state.tenant_id,
            },
        )
    return _construct_to_payload(c, state.tenant_id)


@router.get("/{construct_id}/dependents", response_model=list[str])
def get_dependents(
    construct_id: str,
    tenant_id: str = Depends(require_read),
) -> list[str]:
    state = STORE.get_or_create(tenant_id)
    cid = _resolve_uuid(construct_id, "construct_id")
    if cid not in state.graph.constructs:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "construct_not_found",
                "construct_id": str(cid),
                "tenant_id": state.tenant_id,
            },
        )
    return [str(i) for i in state.graph.direct_dependents_of(cid)]


# ---- Tier 1 writes ----


@router.post("/state", response_model=ConstructPayload, status_code=201)
def create_state(
    payload: StateCreatePayload,
    tenant_id: str = Depends(require_write),
) -> ConstructPayload:
    state = STORE.get_or_create(tenant_id)
    s = State(configuration=payload.configuration)
    _governed_write(s, "create", depends_on=(), state=state)
    return _construct_to_payload(s, state.tenant_id)


@router.post("/change", response_model=ConstructPayload, status_code=201)
def create_change(
    payload: ChangeCreatePayload,
    tenant_id: str = Depends(require_write),
) -> ConstructPayload:
    state = STORE.get_or_create(tenant_id)
    before = _resolve_uuid(payload.state_before_id, "state_before_id")
    after = _resolve_uuid(payload.state_after_id, "state_after_id")
    deps: list[UUID] = [u for u in (before, after) if u is not None]
    for u in deps:
        if u not in state.graph.constructs:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "referenced_state_not_found",
                    "state_id": str(u),
                    "tenant_id": state.tenant_id,
                },
            )
    chg = Change(
        state_before_id=before,
        state_after_id=after,
        delta_vector=payload.delta_vector,
    )
    _governed_write(chg, "create", depends_on=tuple(deps), state=state)
    return _construct_to_payload(chg, state.tenant_id)


@router.post("/causation", response_model=ConstructPayload, status_code=201)
def create_causation(
    payload: CausationCreatePayload,
    tenant_id: str = Depends(require_write),
) -> ConstructPayload:
    state = STORE.get_or_create(tenant_id)
    cause = _resolve_uuid(payload.cause_id, "cause_id")
    effect = _resolve_uuid(payload.effect_id, "effect_id")
    deps: list[UUID] = [u for u in (cause, effect) if u is not None]
    for u in deps:
        if u not in state.graph.constructs:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "referenced_construct_not_found",
                    "construct_id": str(u),
                    "tenant_id": state.tenant_id,
                },
            )
    try:
        c = Causation(
            cause_id=cause,
            effect_id=effect,
            mechanism=payload.mechanism,
            strength=payload.strength,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_construct_error_detail("invalid causation construct", "invalid_causation_construct"),
        ) from exc
    _governed_write(c, "create", depends_on=tuple(deps), state=state)
    return _construct_to_payload(c, state.tenant_id)


@router.post("/constraint", response_model=ConstructPayload, status_code=201)
def create_constraint(
    payload: ConstraintCreatePayload,
    tenant_id: str = Depends(require_write),
) -> ConstructPayload:
    state = STORE.get_or_create(tenant_id)
    try:
        c = Constraint(
            domain=payload.domain,
            restriction=payload.restriction,
            violation_response=payload.violation_response,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_construct_error_detail("invalid constraint construct", "invalid_constraint_construct"),
        ) from exc
    _governed_write(c, "create", depends_on=(), state=state)
    return _construct_to_payload(c, state.tenant_id)


@router.post("/boundary", response_model=ConstructPayload, status_code=201)
def create_boundary(
    payload: BoundaryCreatePayload,
    tenant_id: str = Depends(require_write),
) -> ConstructPayload:
    state = STORE.get_or_create(tenant_id)
    try:
        b = Boundary(
            inside_predicate=payload.inside_predicate,
            interface_points=tuple(payload.interface_points),
            permeability=payload.permeability,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=_construct_error_detail("invalid boundary construct", "invalid_boundary_construct"),
        ) from exc
    _governed_write(b, "create", depends_on=(), state=state)
    return _construct_to_payload(b, state.tenant_id)


# ---- Run-scoped admin ops ----


@router.get("/by-run/{run_id}", response_model=RunExport)
def export_run(
    run_id: str,
    page: int | None = None,
    page_size: int | None = None,
    tenant_id: str = Depends(require_admin),
) -> RunExport:
    """Return every construct in a single run as a self-describing export.

    Admin scope. Includes the run's metadata (domain, summary, timestamp)
    in the envelope, plus full construct payloads (matching the shape of
    GET /constructs/{id}).

    v4.14.0+: optional pagination via ``page`` + ``page_size``. Without
    them, returns the full bundle (current behavior). With ``page_size=N``,
    returns at most N constructs per page; ``construct_count`` always
    reflects the FULL count.

    For a lighter-weight read-scoped query, use ``GET /constructs?run_id=X``.
    """
    page, page_size = _validate_pagination(page, page_size)
    state = STORE.get_or_create(tenant_id)
    constructs = state.constructs_in_run(run_id)
    if not constructs:
        return RunExport(
            tenant_id=tenant_id,
            run_id=run_id,
            domain=None,
            summary=None,
            timestamp=None,
            construct_count=0,
            constructs=[],
            page=page,
            page_size=page_size,
            total_pages=0 if page_size is not None else None,
            has_more=False if page_size is not None else None,
        )
    sample = constructs[0]
    page_items, total_pages, has_more = _paginate_slice(
        constructs, page, page_size,
    )
    return RunExport(
        tenant_id=tenant_id,
        run_id=run_id,
        domain=sample.metadata.get("run_domain"),
        summary=sample.metadata.get("run_summary"),
        timestamp=sample.metadata.get("run_timestamp"),
        construct_count=len(constructs),
        constructs=[_construct_to_payload(c, tenant_id) for c in page_items],
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
    )


@router.delete("/by-run/{run_id}", response_model=RunDeleteResponse)
def delete_run(
    run_id: str,
    tenant_id: str = Depends(require_admin),
) -> RunDeleteResponse:
    """Bulk delete every construct stamped with `run_id` for this tenant.

    Admin scope required (bulk operations have larger blast radius than
    individual deletes). Constructs that have live dependents (other
    constructs reference them) are skipped — their ids appear in
    ``skipped_ids``.

    Returns 200 with a count summary even when nothing matched (use
    ``deleted == 0 and skipped == 0`` to detect "no such run").

    v4.12.0+.
    """
    state = STORE.get_or_create(tenant_id)
    result = state.delete_run(run_id)
    STORE.maybe_snapshot(tenant_id)
    return RunDeleteResponse(
        tenant_id=tenant_id,
        run_id=run_id,
        deleted=result["deleted"],
        skipped=result["skipped"],
        skipped_ids=result["skipped_ids"],
    )


@router.delete("/{construct_id}", status_code=204)
def delete_construct(
    construct_id: str,
    tenant_id: str = Depends(require_write),
) -> None:
    state = STORE.get_or_create(tenant_id)
    cid = _resolve_uuid(construct_id, "construct_id")
    if cid not in state.graph.constructs:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "construct_not_found",
                "construct_id": str(cid),
                "tenant_id": state.tenant_id,
            },
        )
    try:
        state.graph.unregister(cid)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=_construct_error_detail("construct has dependents", "construct_has_dependents"),
        ) from exc
    STORE.maybe_snapshot(state.tenant_id)
