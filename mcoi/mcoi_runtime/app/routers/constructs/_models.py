"""Pydantic request/response models for /constructs/*."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from mcoi_runtime.substrate.registry_store import DEFAULT_TENANT


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
