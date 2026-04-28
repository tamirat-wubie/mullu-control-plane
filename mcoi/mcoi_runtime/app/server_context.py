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

import logging
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.app.production_surface import (
    DEPLOYMENT_MANIFESTS,
    ProductionSurface,
)
from mcoi_runtime.app.server_bootstrap import validate_field_encryption_posture
from mcoi_runtime.app.server_foundation import bootstrap_foundation_services
from mcoi_runtime.app.server_platform import (
    bootstrap_governance_runtime,
    bootstrap_primary_store,
)

_log = logging.getLogger(__name__)


# v4.35.0 (audit F5): env-binding hardening.
#
# Pre-v4.35 every site that read MULLU_ENV used
# ``runtime_env.get("MULLU_ENV", "local_dev")`` directly. An operator
# deploying without setting the env var silently got the most
# permissive policies — local_dev shell, looser tenant validation,
# wildcard CORS, X-Tenant-ID trust. The audit called this out as a
# fail-open path on env binding.
#
# v4.35 routes every read through ``resolve_env``. Behavior:
#
# - MULLU_ENV set to a known value: return it (unchanged).
# - MULLU_ENV unset/empty + MULLU_ENV_REQUIRED=true (or =1/yes/on):
#   raise ``EnvBindingError``. Production deployments set this flag
#   in the manifest so a missing MULLU_ENV is a hard boot failure
#   instead of a silent dev fallback.
# - MULLU_ENV unset/empty + flag not set: log a CRITICAL warning and
#   fall through to "local_dev" (preserves existing behavior for
#   tests and dev workflows).
# - MULLU_ENV set to an unknown value: log an ERROR, return the value
#   as-is (downstream code already falls to ``sandboxed`` shell policy
#   for unknowns).
KNOWN_ENVS = frozenset({"local_dev", "test", "pilot", "production"})

_TRUTHY = frozenset({"true", "1", "yes", "on"})


class EnvBindingError(RuntimeError):
    """Raised when MULLU_ENV is unset and MULLU_ENV_REQUIRED is set."""


def resolve_env(runtime_env: Mapping[str, str]) -> str:
    """Resolve MULLU_ENV with audit-grade fail-closed semantics.

    See module-level docstring for behavior table.
    """
    raw = runtime_env.get("MULLU_ENV", "").strip()
    required = (
        runtime_env.get("MULLU_ENV_REQUIRED", "").strip().lower() in _TRUTHY
    )
    if not raw:
        if required:
            raise EnvBindingError(
                "MULLU_ENV is not set and MULLU_ENV_REQUIRED=true; "
                "refusing to fall back to local_dev defaults"
            )
        _log.critical(
            "MULLU_ENV is not set; falling back to 'local_dev'. "
            "Set MULLU_ENV explicitly (and MULLU_ENV_REQUIRED=true in "
            "production) to silence this warning."
        )
        return "local_dev"
    if raw not in KNOWN_ENVS:
        _log.error(
            "MULLU_ENV=%r is not a known environment %s; downstream "
            "policies will fall to sandboxed defaults",
            raw, sorted(KNOWN_ENVS),
        )
    return raw


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
    validate_field_encryption_posture_fn: Callable[..., None] = validate_field_encryption_posture,
    deployment_manifests: Mapping[str, Any] = DEPLOYMENT_MANIFESTS,
    production_surface_cls: type[Any] = ProductionSurface,
    bootstrap_primary_store_fn: Callable[..., Any] = bootstrap_primary_store,
    bootstrap_foundation_services_fn: Callable[..., Any] = bootstrap_foundation_services,
    bootstrap_governance_runtime_fn: Callable[..., Any] = bootstrap_governance_runtime,
) -> ServerContextBootstrap:
    """Build env-derived context for the governed server."""
    env = resolve_env(runtime_env)
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
    validate_field_encryption_posture_fn(
        env=env,
        db_backend=db_backend,
        field_encryption_bootstrap=field_encryption_bootstrap,
    )
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
