"""
/musia/tenants/* — multi-tenant registry administration.

Distinct from the existing platform /tenants router (which manages full
tenant runtime: budgets, quotas, isolation auditing). This router is
narrower: it observes and manages MUSIA construct registry state per
tenant.

Naming chosen to avoid collision with /tenants and to make the substrate
scope explicit.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import require_admin, require_read
from mcoi_runtime.substrate.registry_store import STORE


router = APIRouter(prefix="/musia/tenants", tags=["musia-tenants"])


class TenantSummary(BaseModel):
    tenant_id: str
    construct_count: int


class StoreSummary(BaseModel):
    tenant_count: int
    tenants: list[TenantSummary]


@router.get("", response_model=StoreSummary)
def list_tenants(
    _: str = Depends(require_admin),
) -> StoreSummary:
    raw = STORE.summary()
    return StoreSummary(
        tenant_count=raw["tenant_count"],
        tenants=[TenantSummary(**t) for t in raw["tenants"]],
    )


@router.get("/{tenant_id}", response_model=TenantSummary)
def get_tenant(
    tenant_id: str,
    _: str = Depends(require_admin),
) -> TenantSummary:
    state = STORE.get(tenant_id)
    if state is None:
        raise HTTPException(
            status_code=404, detail=f"tenant {tenant_id} has no MUSIA state"
        )
    return TenantSummary(
        tenant_id=tenant_id,
        construct_count=len(state.graph.constructs),
    )


@router.delete("/{tenant_id}", status_code=204)
def reset_tenant(
    tenant_id: str,
    _: str = Depends(require_admin),
) -> None:
    """Drop one tenant's MUSIA construct state. Other tenants unaffected.

    Persistence files are NOT deleted; on restart, the tenant will reload
    unless `DELETE /musia/tenants/{id}/snapshot` is also called.
    """
    if STORE.get(tenant_id) is None:
        raise HTTPException(
            status_code=404, detail=f"tenant {tenant_id} has no MUSIA state"
        )
    STORE.reset_tenant(tenant_id)


# ---- Persistence endpoints (v4.4.0) ----


class SnapshotResult(BaseModel):
    tenant_id: str
    construct_count: int
    path: str


class LoadResult(BaseModel):
    tenant_id: str
    loaded: bool
    construct_count: int


def _require_persistence() -> Any:
    backend = STORE.persistence
    if backend is None:
        raise HTTPException(
            status_code=409,
            detail="persistence not configured; call configure_persistence(dir) at startup",
        )
    return backend


@router.post("/{tenant_id}/snapshot", response_model=SnapshotResult)
def snapshot_tenant(
    tenant_id: str,
    _: str = Depends(require_admin),
) -> SnapshotResult:
    """Persist one tenant's current registry graph to disk."""
    _require_persistence()
    state = STORE.get(tenant_id)
    if state is None:
        raise HTTPException(
            status_code=404, detail=f"tenant {tenant_id} has no MUSIA state"
        )
    path = STORE.snapshot_tenant(tenant_id)
    return SnapshotResult(
        tenant_id=tenant_id,
        construct_count=len(state.graph.constructs),
        path=str(path),
    )


@router.post("/{tenant_id}/load", response_model=LoadResult)
def load_tenant(
    tenant_id: str,
    _: str = Depends(require_admin),
) -> LoadResult:
    """Reload one tenant's registry graph from disk.

    Replaces in-memory state with the persisted snapshot. The Φ_agent
    filter on the tenant is preserved (it is not part of the snapshot).
    Returns `loaded=False` when no file exists for this tenant.
    """
    _require_persistence()
    loaded = STORE.load_tenant(tenant_id)
    state = STORE.get(tenant_id)
    return LoadResult(
        tenant_id=tenant_id,
        loaded=loaded,
        construct_count=(
            len(state.graph.constructs) if state is not None else 0
        ),
    )


# ---- Run listing (v4.12.0) ----


class RunSummary(BaseModel):
    run_id: str
    domain: str | None
    summary: str | None
    timestamp: str | None
    construct_count: int


class RunsListResponse(BaseModel):
    tenant_id: str
    total_runs: int
    runs: list[RunSummary]
    # v4.14.0 pagination (None when not paginated)
    page: int | None = None
    page_size: int | None = None
    total_pages: int | None = None
    has_more: bool | None = None


_RUNS_PAGE_SIZE_MAX = 1000


@router.get("/{tenant_id}/runs", response_model=RunsListResponse)
def list_runs(
    tenant_id: str,
    page: int | None = None,
    page_size: int | None = None,
    _: str = Depends(require_admin),
) -> RunsListResponse:
    """List domain runs persisted for this tenant.

    Returned in newest-first timestamp order. Each run summary carries
    its domain, request summary, ISO timestamp, and the count of
    constructs persisted for that run.

    A run shows up here only if its constructs have ``run_id`` in their
    metadata — i.e., they came from a ``persist_run=true`` domain call.

    v4.14.0+: optional pagination via ``page`` + ``page_size``. Default
    behavior (omit both) returns all runs.
    """
    state = STORE.get(tenant_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"tenant {tenant_id} has no MUSIA state",
        )
    # Validate pagination params inline (the constructs router has its own
    # helper; duplicating the few lines keeps musia_tenants free of a
    # cross-router import).
    if page_size is not None:
        if page_size < 1 or page_size > _RUNS_PAGE_SIZE_MAX:
            raise HTTPException(
                status_code=400,
                detail=f"page_size must be in [1, {_RUNS_PAGE_SIZE_MAX}]",
            )
        if page is None:
            page = 1
        if page < 1:
            raise HTTPException(status_code=400, detail="page must be >= 1")

    raw = state.list_runs()
    total = len(raw)
    if page_size is not None:
        total_pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        end = start + page_size
        items = raw[start:end]
        has_more = end < total
    else:
        total_pages = None
        has_more = None
        items = raw

    return RunsListResponse(
        tenant_id=tenant_id,
        total_runs=total,
        runs=[RunSummary(**r) for r in items],
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_more=has_more,
    )


@router.delete("/{tenant_id}/snapshot", status_code=204)
def delete_snapshot(
    tenant_id: str,
    _: str = Depends(require_admin),
) -> None:
    """Delete the persisted snapshot file. In-memory state untouched."""
    backend = _require_persistence()
    if not backend.delete(tenant_id):
        raise HTTPException(
            status_code=404,
            detail=f"no persisted snapshot for tenant {tenant_id}",
        )


# ---- Quota endpoints (v4.9.0) ----


class QuotaPayload(BaseModel):
    max_constructs: int | None = Field(default=None, ge=0)
    max_writes_per_window: int | None = Field(default=None, ge=0)
    window_seconds: int = Field(default=3600, gt=0)


class QuotaSnapshot(BaseModel):
    tenant_id: str
    max_constructs: int | None
    current_constructs: int
    headroom: int | None  # max - current, None if unlimited
    max_writes_per_window: int | None
    window_seconds: int
    writes_in_current_window: int


def _build_snapshot(tenant_id: str, state: Any) -> QuotaSnapshot:
    current = len(state.graph.constructs)
    headroom = (
        state.quota.max_constructs - current
        if state.quota.max_constructs is not None
        else None
    )
    # Run a stale-eviction pass to make the count accurate. The check
    # method is idempotent; calling it for read-only purposes is safe.
    state.check_rate_limit_for_write()
    return QuotaSnapshot(
        tenant_id=tenant_id,
        max_constructs=state.quota.max_constructs,
        current_constructs=current,
        headroom=headroom,
        max_writes_per_window=state.quota.max_writes_per_window,
        window_seconds=state.quota.window_seconds,
        writes_in_current_window=len(state._recent_writes),
    )


@router.get("/{tenant_id}/quota", response_model=QuotaSnapshot)
def get_quota(
    tenant_id: str,
    _: str = Depends(require_admin),
) -> QuotaSnapshot:
    state = STORE.get(tenant_id)
    if state is None:
        raise HTTPException(
            status_code=404,
            detail=f"tenant {tenant_id} has no MUSIA state",
        )
    return _build_snapshot(tenant_id, state)


@router.put("/{tenant_id}/quota", response_model=QuotaSnapshot)
def set_quota(
    tenant_id: str,
    payload: QuotaPayload,
    _: str = Depends(require_admin),
) -> QuotaSnapshot:
    """Install or update a tenant's quota. Creates the tenant state if absent.

    Setting max_constructs below the current construct count is allowed —
    no eviction happens, but the next write attempt will return 429 until
    the count drops below the new limit.

    v4.10.0+: also accepts ``max_writes_per_window`` + ``window_seconds``.
    """
    from mcoi_runtime.substrate.registry_store import TenantQuota

    state = STORE.get_or_create(tenant_id)
    state.quota = TenantQuota(
        max_constructs=payload.max_constructs,
        max_writes_per_window=payload.max_writes_per_window,
        window_seconds=payload.window_seconds,
    )
    return _build_snapshot(tenant_id, state)
