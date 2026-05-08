"""Per-tenant construct registry shims and lifecycle helpers."""
from __future__ import annotations

from uuid import UUID

from mcoi_runtime.substrate.constructs import ConstructBase
from mcoi_runtime.substrate.phi_gov import Authority, PhiAgentFilter
from mcoi_runtime.substrate.registry_store import (
    DEFAULT_TENANT,
    STORE,
)


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
