"""Optional governed swarm router integration for the control-plane app.

Purpose: mount the governed invoice swarm router only when explicitly enabled
by environment configuration.
Governance scope: feature flag boundary, audit-store requirement, and fail-
closed optional dependency loading.
Dependencies: app router mounting and optional mcoi_runtime.swarm package path.
Invariants: disabled means no route mount; enabled requires an audit store path
and a loadable governed swarm runtime/router factory. External runtime package
paths must be explicit and must contain mcoi_runtime/swarm.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class GovernedSwarmBootstrap:
    """Startup posture for the governed swarm router integration."""

    enabled: bool
    mounted: bool
    audit_store_path: str
    reason: str


def env_flag(value: str | None) -> bool:
    """Return whether an environment flag is enabled."""

    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def mount_governed_swarm_router_from_env(
    *,
    app: Any,
    runtime_env: Mapping[str, str],
    include_router_fn: Callable[[Any], Any] | None = None,
    runtime_factory: Callable[[str | Path], Any] | None = None,
    router_factory: Callable[[Any], Any] | None = None,
) -> GovernedSwarmBootstrap:
    """Mount the governed swarm router when the explicit flag is enabled."""

    if not env_flag(runtime_env.get("MULLU_GOVERNED_SWARM_ENABLED")):
        return GovernedSwarmBootstrap(
            enabled=False,
            mounted=False,
            audit_store_path="",
            reason="disabled",
        )

    audit_store_path = str(runtime_env.get("MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH", "")).strip()
    if not audit_store_path:
        raise RuntimeError("MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH is required when governed swarm is enabled")

    if runtime_factory is None or router_factory is None:
        runtime_package_path = str(runtime_env.get("MULLU_GOVERNED_SWARM_RUNTIME_PATH", "")).strip()
        if runtime_package_path:
            extend_runtime_package_path(runtime_package_path)
        try:
            from mcoi_runtime.swarm import InvoiceSwarmRuntime, create_fastapi_router
        except ImportError as exc:
            raise RuntimeError("governed swarm package is required when MULLU_GOVERNED_SWARM_ENABLED is true") from exc
        runtime_factory = runtime_factory or InvoiceSwarmRuntime.from_path
        router_factory = router_factory or create_fastapi_router

    runtime = runtime_factory(Path(audit_store_path))
    router = router_factory(runtime)
    if include_router_fn is None:
        app.include_router(router)
    else:
        include_router_fn(router)
    return GovernedSwarmBootstrap(
        enabled=True,
        mounted=True,
        audit_store_path=audit_store_path,
        reason="mounted",
    )


def extend_runtime_package_path(runtime_path: str | Path) -> Path:
    """Extend mcoi_runtime package lookup with an explicit external path."""

    root = Path(runtime_path).resolve()
    package_path = root / "mcoi_runtime"
    swarm_path = package_path / "swarm"
    if not swarm_path.is_dir():
        raise RuntimeError("MULLU_GOVERNED_SWARM_RUNTIME_PATH must contain mcoi_runtime/swarm")
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    import mcoi_runtime

    package_path_text = str(package_path)
    if package_path_text not in mcoi_runtime.__path__:
        mcoi_runtime.__path__.append(package_path_text)
    return package_path
