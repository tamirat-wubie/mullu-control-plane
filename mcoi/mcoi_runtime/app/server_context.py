"""Environment and governance context bootstrap helpers for the server.

Purpose: isolate env-derived surface, store, field-encryption, foundation,
and governance setup from the main server module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: production surface manifests, primary store bootstrap,
foundation bootstrap, and governance bootstrap helpers.
Invariants:
  - Environment posture remains deterministic and env-driven.
  - Store and foundation bootstrap share the same persisted store instance.
  - Governance bootstrap preserves shell-policy and tenant-gating posture.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.production_surface import (
    DEPLOYMENT_MANIFESTS,
    ProductionSurface,
)
from mcoi_runtime.app.server_foundation import bootstrap_foundation_services
from mcoi_runtime.app.server_platform import (
    bootstrap_governance_runtime,
    bootstrap_primary_store,
)


@dataclass(frozen=True)
class ServerContextBootstrap:
    """Server context bootstrap result."""

    env: str
    surface: Any
    tenant_allow_unknown: bool
    db_backend: str
    db_backend_warning: Any
    store: Any
    foundation_bootstrap: Any
    field_encryptor: Any | None
    field_encryption_bootstrap: dict[str, Any]
    governance_bootstrap: Any
    shell_policy: Any


def bootstrap_server_context(
    *,
    runtime_env: Mapping[str, str],
    clock: Callable[[], str],
    env_flag_fn: Callable[[str, Mapping[str, str]], bool | None],
    validate_db_backend_for_env: Callable[[str, str], Any],
    init_field_encryption_from_env_fn: Callable[[], tuple[Any | None, dict[str, Any]]],
    deployment_manifests: Mapping[str, Any] = DEPLOYMENT_MANIFESTS,
    production_surface_cls: type[Any] = ProductionSurface,
    bootstrap_primary_store_fn: Callable[..., Any] = bootstrap_primary_store,
    bootstrap_foundation_services_fn: Callable[..., Any] = bootstrap_foundation_services,
    bootstrap_governance_runtime_fn: Callable[..., Any] = bootstrap_governance_runtime,
) -> ServerContextBootstrap:
    """Build env-derived context for the governed server."""
    env = runtime_env.get("MULLU_ENV", "local_dev")
    surface = production_surface_cls(
        deployment_manifests.get(env, deployment_manifests["local_dev"])
    )

    tenant_allow_unknown = env_flag_fn("MULLU_ALLOW_UNKNOWN_TENANTS", runtime_env)
    if tenant_allow_unknown is None:
        tenant_allow_unknown = env in ("local_dev", "test")

    primary_store_bootstrap = bootstrap_primary_store_fn(
        env=env,
        runtime_env=runtime_env,
        clock=clock,
        validate_db_backend_for_env=validate_db_backend_for_env,
    )
    db_backend = primary_store_bootstrap.db_backend
    db_backend_warning = primary_store_bootstrap.warning
    store = primary_store_bootstrap.store

    field_encryptor, field_encryption_bootstrap = init_field_encryption_from_env_fn()
    foundation_bootstrap = bootstrap_foundation_services_fn(
        clock=clock,
        runtime_env=runtime_env,
        store=store,
    )
    governance_bootstrap = bootstrap_governance_runtime_fn(
        env=env,
        runtime_env=runtime_env,
        db_backend=db_backend,
        clock=clock,
        field_encryptor=field_encryptor,
        allow_unknown_tenants=tenant_allow_unknown,
    )

    return ServerContextBootstrap(
        env=env,
        surface=surface,
        tenant_allow_unknown=tenant_allow_unknown,
        db_backend=db_backend,
        db_backend_warning=db_backend_warning,
        store=store,
        foundation_bootstrap=foundation_bootstrap,
        field_encryptor=field_encryptor,
        field_encryption_bootstrap=field_encryption_bootstrap,
        governance_bootstrap=governance_bootstrap,
        shell_policy=governance_bootstrap.shell_policy,
    )
