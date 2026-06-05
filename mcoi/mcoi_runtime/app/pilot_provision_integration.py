"""Pilot provision registry integration for the control-plane app.

Purpose: select pilot provision history storage from runtime environment and
validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: shared integration path validation and pilot provision registry
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
from mcoi_runtime.app.pilot_init import (
    FilePilotProvisionRegistry,
    PilotProvisionRegistry,
)


PILOT_PROVISION_REGISTRY_PATH_ENV = "MULLU_PILOT_PROVISION_REGISTRY_PATH"


@dataclass(frozen=True)
class PilotProvisionRegistryBootstrap:
    """Startup posture for the pilot provision registry."""

    registry: PilotProvisionRegistry
    path: str
    persistent: bool


def select_pilot_provision_registry(
    runtime_env: Mapping[str, str],
) -> PilotProvisionRegistryBootstrap:
    """Return the pilot provision registry matching runtime configuration."""

    raw_value = runtime_env.get(PILOT_PROVISION_REGISTRY_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return PilotProvisionRegistryBootstrap(
            registry=PilotProvisionRegistry(),
            path="",
            persistent=False,
        )

    path = validate_pilot_provision_registry_path(str(raw_value).strip())
    return PilotProvisionRegistryBootstrap(
        registry=FilePilotProvisionRegistry(path),
        path=str(path),
        persistent=True,
    )


def validate_pilot_provision_registry_path(store_path: str | Path) -> Path:
    """Validate the hosted pilot provision registry path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=PILOT_PROVISION_REGISTRY_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
