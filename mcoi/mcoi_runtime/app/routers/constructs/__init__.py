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

Originally a single 821-line module. Split into:
- ``_registry``: ``_REGISTRY`` proxy, ``reset_registry``, ``install_phi_agent_filter``
- ``_governance``: Φ_gov-mediated write path (quota → rate limit → governance)
- ``_models``: 8 pydantic request/response models
- ``_helpers``: payload conversion + UUID resolution
- ``_pagination``: offset (v4.14) and cursor (v4.23) pagination helpers
- ``_routes``: the 11 FastAPI endpoints

Public import surface preserved via the re-exports below.
"""
from __future__ import annotations

from mcoi_runtime.app.routers.constructs._pagination import (
    PAGE_SIZE_MAX,
    _decode_cursor,
    _encode_cursor,
    _paginate_cursor,
)
from mcoi_runtime.app.routers.constructs._registry import (
    _REGISTRY,
    install_phi_agent_filter,
    reset_registry,
)
from mcoi_runtime.app.routers.constructs._routes import router

__all__ = [
    "PAGE_SIZE_MAX",
    "_REGISTRY",
    "_decode_cursor",
    "_encode_cursor",
    "_paginate_cursor",
    "install_phi_agent_filter",
    "reset_registry",
    "router",
]
