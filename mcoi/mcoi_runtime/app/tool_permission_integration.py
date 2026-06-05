"""Tool permission registry integration for the control-plane app.

Purpose: select tool permission registry storage from runtime environment and
validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: shared integration path validation and tool permission primitive
contracts.
Invariants: no env path means a non-persistent in-memory registry; an env path
must be absolute, must use a .json extension, must not point to a directory,
and the parent directory must already exist and be writable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from mcoi_runtime.app._integration_paths import validate_hosted_store_path
from mcoi_runtime.core.tool_permission_primitives import (
    FileToolPermissionRegistry,
    ToolPermissionRegistry,
)


TOOL_PERMISSION_REGISTRY_PATH_ENV = "MULLU_TOOL_PERMISSION_REGISTRY_PATH"


@dataclass(frozen=True)
class ToolPermissionRegistryBootstrap:
    """Startup posture for the tool permission registry."""

    registry: ToolPermissionRegistry
    path: str
    persistent: bool


def select_tool_permission_registry(
    runtime_env: Mapping[str, str],
) -> ToolPermissionRegistryBootstrap:
    """Return the tool permission registry matching runtime configuration."""

    raw_value = runtime_env.get(TOOL_PERMISSION_REGISTRY_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return ToolPermissionRegistryBootstrap(
            registry=ToolPermissionRegistry(),
            path="",
            persistent=False,
        )

    path = validate_tool_permission_registry_path(str(raw_value).strip())
    return ToolPermissionRegistryBootstrap(
        registry=FileToolPermissionRegistry(path),
        path=str(path),
        persistent=True,
    )


def validate_tool_permission_registry_path(store_path: str | Path) -> Path:
    """Validate the hosted tool permission registry path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=TOOL_PERMISSION_REGISTRY_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
