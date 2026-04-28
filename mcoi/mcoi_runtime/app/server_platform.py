"""Platform bootstrap helpers for the governed HTTP server.

Purpose: isolate persistence, governance, and environment-selected platform
services from the main HTTP bootstrap module.
Governance scope: [OCE, CDCV, CQTE, UWMA]
Dependencies: persistence backends, governance stores, tenant gating, shell
policies, and optional JWT authentication.
Invariants:
  - Primary store backend selection stays deterministic.
  - SQLite migrations run only when a SQLite-backed connection is present.
  - Governance services remain wired to stable store keys.
  - Optional JWT bootstrap remains disabled when no signing secret is set.
  - Shell policy selection remains environment-bounded and deterministic.
"""
from __future__ import annotations

import base64
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.shell_policies import (
    LOCAL_DEV,
    PILOT_PROD,
    PILOT_PROD_DISABLED,
    SANDBOXED,
)
from mcoi_runtime.core.audit_trail import AuditTrail
from mcoi_runtime.core.governance_metrics import GovernanceMetricsEngine
from mcoi_runtime.core.rate_limiter import RateLimitConfig, RateLimiter
from mcoi_runtime.core.tenant_budget import TenantBudgetManager
from mcoi_runtime.core.tenant_gating import TenantGatingRegistry
from mcoi_runtime.persistence.migrations import create_platform_migration_engine
from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores
from mcoi_runtime.persistence.postgres_store import create_store


@dataclass(frozen=True)
class PrimaryStoreBootstrap:
    """Primary persistence bootstrap result."""

    db_backend: str
    store: Any
    warning: str | None
    migrations_applied: tuple[str, ...]


@dataclass(frozen=True)
class GovernanceBootstrap:
    """Governance service bootstrap result."""

    governance_stores: Any
    tenant_budget_mgr: Any
    metrics: Any
    rate_limiter: Any
    audit_trail: Any
    jwt_authenticator: Any | None
    tenant_gating: Any
    shell_policy: Any


def _shell_execution_enabled(runtime_env: Mapping[str, str]) -> bool:
    """Return whether governed shell execution is explicitly enabled."""
    value = runtime_env.get("MULLU_SHELL_EXECUTION_ENABLED", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def bootstrap_primary_store(
    *,
    env: str,
    runtime_env: Mapping[str, str],
    clock: Callable[[], str],
    validate_db_backend_for_env: Callable[[str, str], str | None],
    create_store_fn: Callable[..., Any] = create_store,
    create_platform_migration_engine_fn: Callable[..., Any] = create_platform_migration_engine,
    warnings_module: Any = warnings,
) -> PrimaryStoreBootstrap:
    """Create the primary persistence store and apply SQLite migrations when needed."""
    db_backend = runtime_env.get("MULLU_DB_BACKEND", "memory")
    warning = validate_db_backend_for_env(db_backend, env)
    if warning:
        warnings_module.warn(warning, stacklevel=1)

    store = create_store_fn(
        backend=db_backend,
        connection_string=runtime_env.get("MULLU_DB_URL", ""),
    )

    migrations_applied: tuple[str, ...] = ()
    if db_backend == "sqlite" and hasattr(store, "_conn"):
        migration_engine = create_platform_migration_engine_fn(clock=clock)
        migration_results = migration_engine.apply_all(store._conn)
        if migration_results:
            migrations_applied = tuple(
                result.name
                for result in migration_results
                if getattr(result, "success", False)
            )

    return PrimaryStoreBootstrap(
        db_backend=db_backend,
        store=store,
        warning=warning,
        migrations_applied=migrations_applied,
    )


def bootstrap_governance_runtime(
    *,
    env: str,
    runtime_env: Mapping[str, str],
    db_backend: str,
    clock: Callable[[], str],
    field_encryptor: Any | None,
    allow_unknown_tenants: bool,
    create_governance_stores_fn: Callable[..., Any] = create_governance_stores,
    tenant_budget_manager_cls: type[Any] = TenantBudgetManager,
    governance_metrics_engine_cls: type[Any] = GovernanceMetricsEngine,
    rate_limiter_cls: type[Any] = RateLimiter,
    rate_limit_config_cls: type[Any] = RateLimitConfig,
    audit_trail_cls: type[Any] = AuditTrail,
    tenant_gating_registry_cls: type[Any] = TenantGatingRegistry,
    sandboxed_policy: Any = SANDBOXED,
    local_dev_policy: Any = LOCAL_DEV,
    pilot_prod_policy: Any = PILOT_PROD,
    pilot_prod_disabled_policy: Any = PILOT_PROD_DISABLED,
    jwt_authenticator_cls: type[Any] | None = None,
    oidc_config_cls: type[Any] | None = None,
) -> GovernanceBootstrap:
    """Create governance stores and the platform services bound to them."""
    # v4.36.0 (audit F12): connection-pool sizing.
    # MULLU_DB_POOL_SIZE controls per-store pool cap. Default 1 keeps
    # the legacy single-connection behavior. Production deployments
    # should set this to a value tuned to expected concurrent writers
    # (typical 5-20). Note: total pg connections = 4 stores × pool_size.
    try:
        pool_size = max(1, int(runtime_env.get("MULLU_DB_POOL_SIZE", "1")))
    except (TypeError, ValueError):
        pool_size = 1
    governance_stores = create_governance_stores_fn(
        backend=db_backend,
        connection_string=runtime_env.get("MULLU_DB_URL", ""),
        field_encryptor=field_encryptor,
        pool_size=pool_size,
    )

    tenant_budget_mgr = tenant_budget_manager_cls(
        clock=clock,
        store=governance_stores["budget"],
    )
    metrics = governance_metrics_engine_cls(clock=clock)
    rate_limiter = rate_limiter_cls(
        default_config=rate_limit_config_cls(max_tokens=60, refill_rate=1.0),
        store=governance_stores["rate_limit"],
    )
    audit_trail = audit_trail_cls(
        clock=clock,
        store=governance_stores["audit"],
    )

    jwt_authenticator = None
    jwt_secret = runtime_env.get("MULLU_JWT_SECRET", "")
    if jwt_secret:
        auth_cls = jwt_authenticator_cls
        config_cls = oidc_config_cls
        if auth_cls is None or config_cls is None:
            from mcoi_runtime.core.jwt_auth import JWTAuthenticator, OIDCConfig

            auth_cls = JWTAuthenticator
            config_cls = OIDCConfig
        jwt_authenticator = auth_cls(
            config_cls(
                issuer=runtime_env.get("MULLU_JWT_ISSUER", "mullu"),
                audience=runtime_env.get("MULLU_JWT_AUDIENCE", "mullu-api"),
                signing_key=base64.b64decode(jwt_secret),
                tenant_claim=runtime_env.get("MULLU_JWT_TENANT_CLAIM", "tenant_id"),
            )
        )

    tenant_gating = tenant_gating_registry_cls(
        clock=clock,
        store=governance_stores["tenant_gating"],
        allow_unknown_tenants=allow_unknown_tenants,
    )
    if env == "local_dev":
        shell_policy = local_dev_policy
    elif env in {"pilot", "production"}:
        shell_policy = (
            pilot_prod_policy
            if _shell_execution_enabled(runtime_env)
            else pilot_prod_disabled_policy
        )
    else:
        shell_policy = sandboxed_policy

    return GovernanceBootstrap(
        governance_stores=governance_stores,
        tenant_budget_mgr=tenant_budget_mgr,
        metrics=metrics,
        rate_limiter=rate_limiter,
        audit_trail=audit_trail,
        jwt_authenticator=jwt_authenticator,
        tenant_gating=tenant_gating,
        shell_policy=shell_policy,
    )
