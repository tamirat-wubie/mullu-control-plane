"""
/constructs/* — CRUD for the 25 universal constructs.

Backed by a multi-tenant in-process registry store. Each request scopes
to a tenant via the `X-Tenant-ID` header (defaults to `default` if absent).
Constructs are isolated per tenant: cascade walks never cross the boundary,
and Φ_gov decisions are tenant-local.

Every write goes through Φ_gov. Failed writes return 403 with the judgment
record (cascade summaries, rejected deltas, Φ_agent filter level) so the
caller sees exactly why the write was refused. Deletes that would orphan
dependents return 409.
"""
from __future__ import annotations

import base64
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import (
    require_admin,
    require_read,
    require_write,
    resolve_musia_tenant,
)
from mcoi_runtime.substrate.cascade import CascadeEngine
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    ConstructBase,
    Constraint,
    State,
)
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    PhiAgentFilter,
    PhiGov,
    ProofState,
    ProposedDelta,
)
from mcoi_runtime.substrate.registry_store import (
    DEFAULT_TENANT,
    STORE,
    TenantState,
)


router = APIRouter(prefix="/constructs", tags=["constructs"])


# Default Authority for unauthenticated callers. Production wiring pulls
# this from auth middleware; for now the governance flow is exercised but
# default-permissive.
_DEFAULT_AUTHORITY = Authority(identifier="anonymous", kind="agent")


# ---- Backward-compat shims for code that still references _REGISTRY ----
#
# Some tests and the cognition router still reach into the constructs
# module's `_REGISTRY` global. Keep that name working by routing it
# through the default tenant. New code should use STORE.get_or_create()
# directly.


class _DefaultTenantRegistryProxy:
    """Read-only-ish proxy that exposes the default tenant's graph as if it
    were a module-level DependencyGraph. Used by older callers."""

    @property
    def constructs(self) -> dict[UUID, ConstructBase]:
        return STORE.get_or_create(DEFAULT_TENANT).graph.constructs

    @property
    def dependents(self) -> dict[UUID, set[UUID]]:
        return STORE.get_or_create(DEFAULT_TENANT).graph.dependents

    def register(self, construct: ConstructBase, depends_on=()) -> None:
        STORE.get_or_create(DEFAULT_TENANT).graph.register(
            construct, depends_on=depends_on
        )

    def unregister(self, construct_id: UUID) -> None:
        STORE.get_or_create(DEFAULT_TENANT).graph.unregister(construct_id)

    def direct_dependents_of(self, construct_id: UUID) -> set[UUID]:
        return STORE.get_or_create(DEFAULT_TENANT).graph.direct_dependents_of(
            construct_id
        )


_REGISTRY = _DefaultTenantRegistryProxy()


def reset_registry() -> None:
    """Test-only: reset every tenant's state."""
    STORE.reset_all()


def install_phi_agent_filter(
    filter_obj: PhiAgentFilter,
    tenant_id: str = DEFAULT_TENANT,
) -> None:
    """Install a Φ_agent filter on a tenant (default tenant if not specified)."""
    STORE.install_phi_agent_filter(tenant_id, filter_obj)


def _phi_gov_for(state: TenantState) -> PhiGov:
    """Build Φ_gov for a tenant. v4.15.0: also threads in the existing
    `GovernanceGuardChain` if one was installed via
    ``configure_musia_governance_chain()``.

    The chain's verdict joins Φ_agent's: both must approve. A chain
    rejection lands on the same 403 path Φ_gov uses for any
    external-validator failure.
    """
    from mcoi_runtime.app.routers.musia_governance_bridge import (
        installed_validator_or_none,
    )

    external_validators: tuple = ()
    bridge = installed_validator_or_none()
    if bridge is not None:
        external_validators = (bridge,)

    return PhiGov(
        graph=state.graph,
        cascade_engine=CascadeEngine(state.graph),
        phi_agent=state.phi_agent,
        external_validators=external_validators,
    )


def _governed_write(
    construct: ConstructBase,
    operation: str,
    depends_on: tuple[UUID, ...],
    state: TenantState,
) -> None:
    """Run a write through quota → rate limit → Φ_gov for the given tenant.

    Order of checks (cheapest first):
      1. Lifetime construct quota (HTTP 429, Retry-After: 0)
      2. Sliding-window rate limit (HTTP 429, Retry-After: <seconds>)
      3. Φ_gov / Φ_agent (HTTP 403)
    """
    # 1. Lifetime quota gate
    ok, reason = state.check_quota_for_write()
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "tenant quota exceeded",
                "reason": reason,
                "tenant_id": state.tenant_id,
            },
            # Retry-After: 0 because the lifetime cap doesn't auto-clear;
            # an operator must raise the quota or the tenant must delete.
            headers={"Retry-After": "0"},
        )

    # 2. Sliding-window rate limit gate
    ok, retry_after, reason = state.check_rate_limit_for_write()
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "tenant rate limit exceeded",
                "reason": reason,
                "retry_after_seconds": retry_after,
                "tenant_id": state.tenant_id,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # 3. Φ_gov gate
    delta = ProposedDelta(
        construct_id=construct.id,
        operation=operation,
        payload={"type": construct.type.value, "tier": construct.tier.value},
    )
    ctx = GovernanceContext(
        correlation_id="api-write",
        tenant_id=state.tenant_id,
    )
    phi = _phi_gov_for(state)
    result = phi.evaluate((delta,), ctx, _DEFAULT_AUTHORITY)
    if result.judgment.state == ProofState.PASS:
        state.graph.register(construct, depends_on=depends_on)
        # Consume a rate-limit slot only on successful registration.
        state.record_write()
        # Auto-snapshot if persistence is configured with that mode.
        STORE.maybe_snapshot(state.tenant_id)
        return
    raise HTTPException(
        status_code=403,
        detail={
            "error": "Φ_gov rejected the write",
            "proof_state": result.judgment.state.value,
            "reason": result.judgment.reason,
            "phi_agent_level_passed": (
                result.judgment.phi_agent_level_passed.name
                if result.judgment.phi_agent_level_passed
                else None
            ),
            "rejected_deltas": [
                {
                    "construct_id": str(d.construct_id),
                    "operation": d.operation,
                }
                for d in result.judgment.rejected_deltas
            ],
            "tenant_id": state.tenant_id,
        },
    )


# ---- Pydantic models ----


class ConstructPayload(BaseModel):
    id: str
    type: str
    tier: int
    invariants: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = DEFAULT_TENANT


class StateCreatePayload(BaseModel):
    configuration: dict[str, Any] = Field(default_factory=dict)


class ChangeCreatePayload(BaseModel):
    state_before_id: str | None = None
    state_after_id: str | None = None
    delta_vector: dict[str, Any] = Field(default_factory=dict)


class CausationCreatePayload(BaseModel):
    cause_id: str | None = None
    effect_id: str | None = None
    mechanism: str
    strength: float = 1.0


class ConstraintCreatePayload(BaseModel):
    domain: str
    restriction: str
    violation_response: str = "block"


class BoundaryCreatePayload(BaseModel):
    inside_predicate: str
    interface_points: list[str] = Field(default_factory=list)
    permeability: str = "selective"


class ConstructListResponse(BaseModel):
    total: int
    by_type: dict[str, int]
    constructs: list[ConstructPayload]
    tenant_id: str
    # v4.14.0 offset pagination (None when not paginated)
    page: int | None = None
    page_size: int | None = None
    total_pages: int | None = None
    has_more: bool | None = None
    # v4.23.0 cursor pagination (None when not used). next_cursor is
    # opaque — clients pass it back to the same endpoint to fetch the
    # next page; format is implementation-private and may change.
    next_cursor: str | None = None


class RunDeleteResponse(BaseModel):
    """Result of a bulk run-id-scoped delete (v4.12.0)."""

    tenant_id: str
    run_id: str
    deleted: int
    skipped: int
    skipped_ids: list[str]


class RunExport(BaseModel):
    """Self-describing export of all constructs in a single run (v4.13.0).

    The constructs subarray is the full payload shape — same as a
    GET /constructs/{id} response would yield, just for every member of
    the run. Suitable for archival, replay analysis, or hand-off to a
    downstream audit consumer.

    v4.14.0+: optional pagination via ?page=&page_size= query params.
    construct_count is always the FULL count; constructs may be a slice.
    """

    tenant_id: str
    run_id: str
    domain: str | None
    summary: str | None
    timestamp: str | None
    construct_count: int
    constructs: list[ConstructPayload]
    page: int | None = None
    page_size: int | None = None
    total_pages: int | None = None
    has_more: bool | None = None


# ---- Helpers ----


def _construct_to_payload(c: ConstructBase, tenant_id: str) -> ConstructPayload:
    fields: dict[str, Any] = {}
    for k, v in c.__dict__.items():
        if k in {"id", "tier", "type", "invariants", "metadata", "created_at"}:
            continue
        if isinstance(v, UUID):
            fields[k] = str(v)
        elif isinstance(v, tuple):
            fields[k] = list(v)
        else:
            fields[k] = v
    return ConstructPayload(
        id=str(c.id),
        type=c.type.value,
        tier=c.tier.value,
        invariants=list(c.invariants),
        metadata=dict(c.metadata),
        created_at=c.created_at.isoformat() if c.created_at else None,
        fields=fields,
        tenant_id=tenant_id,
    )


def _resolve_uuid(s: str | None, name: str) -> UUID | None:
    if s is None:
        return None
    try:
        return UUID(s)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_uuid", "field": name, "value": s},
        )


# ---- Pagination (v4.14.0) ----

PAGE_SIZE_MAX = 1000


def _validate_pagination(
    page: int | None,
    page_size: int | None,
) -> tuple[int | None, int | None]:
    """Coerce + validate pagination params. Returns (page, page_size) or (None, None).

    Pagination is "active" iff page_size is not None. page defaults to 1.
    """
    if page_size is None:
        return None, None
    if page_size < 1 or page_size > PAGE_SIZE_MAX:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_page_size", "max": PAGE_SIZE_MAX},
        )
    if page is None:
        page = 1
    if page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    return page, page_size


def _paginate_slice(
    items: list,
    page: int | None,
    page_size: int | None,
) -> tuple[list, int | None, bool | None]:
    """Slice items by page. Returns (slice, total_pages, has_more) or (items, None, None) when not paginated."""
    if page is None or page_size is None:
        return items, None, None
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    sliced = items[start:end]
    has_more = end < total
    return sliced, total_pages, has_more


# ---- Cursor pagination (v4.23.0) ----
#
# Offset pagination drifts when items are inserted/deleted between
# requests: a client iterating page=1, page=2, page=3 may see the same
# item twice (after an insert near the start) or miss items (after a
# delete). Cursor pagination is stable: the cursor is an opaque token
# carrying the boundary item's id, and "next page" means
# "items strictly after this id, sorted by id." Inserts and deletes
# anywhere in the list don't corrupt the iteration.
#
# Trade-off: items are sorted lexicographically by UUID (not by
# insertion order). This is fine because:
#   1. The list endpoint contract doesn't promise insertion order
#   2. Clients using cursor pagination care about consistency, not order
#   3. UUIDs are random, so the order is deterministic per item set


def _encode_cursor(after_id: str) -> str:
    """Encode a boundary id as an opaque cursor string."""
    payload = json.dumps({"after_id": after_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).rstrip(b"=").decode("ascii")


def _decode_cursor(cursor: str) -> str:
    """Decode an opaque cursor. Returns the boundary id.

    Raises HTTPException(400, invalid_cursor) on any decode/parse error.
    Cursor is meant to be opaque to clients — they always pass back
    exactly what the server emitted, so corruption indicates client
    bug or intentional tampering.
    """
    try:
        # Add padding back (urlsafe_b64decode requires correct padding)
        padded = cursor + "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode())
        payload = json.loads(decoded)
        after_id = payload["after_id"]
        if not isinstance(after_id, str) or not after_id:
            raise ValueError("empty after_id")
        return after_id
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_cursor"},
        )


def _validate_cursor_limit(limit: int | None) -> int | None:
    """Coerce + validate the cursor-mode ``limit`` param."""
    if limit is None:
        return None
    if limit < 1 or limit > PAGE_SIZE_MAX:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_limit", "max": PAGE_SIZE_MAX},
        )
    return limit


def _paginate_cursor(
    items: list[ConstructBase],
    cursor: str | None,
    limit: int,
) -> tuple[list[ConstructBase], str | None]:
    """Apply cursor pagination to a list of constructs.

    Items are sorted by UUID lexicographically; the slice is the first
    ``limit`` items strictly greater than the cursor's boundary id.
    Returns (page_items, next_cursor) where next_cursor is None when
    the page is the last one.
    """
    sorted_items = sorted(items, key=lambda c: str(c.id))
    if cursor is not None:
        after_id = _decode_cursor(cursor)
        sorted_items = [c for c in sorted_items if str(c.id) > after_id]
    page = sorted_items[:limit]
    if len(page) < limit:
        next_cursor = None  # no more items
    else:
        # If exactly limit items returned, next page might exist;
        # check by looking past the last one. Cheap because we're
        # already in a sorted list.
        last_id = str(page[-1].id)
        next_cursor = (
            _encode_cursor(last_id)
            if any(str(c.id) > last_id for c in sorted_items)
            else None
        )
    return page, next_cursor


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
        # Cursor mode. Use the validated limit, or default to PAGE_SIZE_MAX
        # when only cursor is given (so the client gets something back).
        effective_limit = limit_validated if limit_validated is not None else PAGE_SIZE_MAX
        page_items, next_cursor = _paginate_cursor(items, cursor, effective_limit)
        # Cursor mode disables offset fields in response (already None default)
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _governed_write(b, "create", depends_on=(), state=state)
    return _construct_to_payload(b, state.tenant_id)


# ---- Delete ----


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
        # Empty-but-valid export — race-tolerant with concurrent delete.
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
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    STORE.maybe_snapshot(state.tenant_id)
