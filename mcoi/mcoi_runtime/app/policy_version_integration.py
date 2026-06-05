"""Policy version registry integration for the control-plane app.

Purpose: select policy-version registry storage from runtime environment and
validate any hosted persistence path before construction.
Governance scope: file-vs-in-memory selection boundary, hosted-store path
validation, and fail-closed misconfiguration handling.
Dependencies: shared integration path validation and policy version registry
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
from mcoi_runtime.governance.policy.versioning import (
    FilePolicyVersionRegistry,
    PolicyVersionRegistry,
)


POLICY_VERSION_REGISTRY_PATH_ENV = "MULLU_POLICY_VERSION_REGISTRY_PATH"


@dataclass(frozen=True)
class PolicyVersionRegistryBootstrap:
    """Startup posture for the policy version registry."""

    registry: PolicyVersionRegistry
    path: str
    persistent: bool


def select_policy_version_registry(
    runtime_env: Mapping[str, str],
) -> PolicyVersionRegistryBootstrap:
    """Return the policy version registry matching runtime configuration."""

    raw_value = runtime_env.get(POLICY_VERSION_REGISTRY_PATH_ENV)
    if raw_value is None or not str(raw_value).strip():
        return PolicyVersionRegistryBootstrap(
            registry=PolicyVersionRegistry(),
            path="",
            persistent=False,
        )

    path = validate_policy_version_registry_path(str(raw_value).strip())
    return PolicyVersionRegistryBootstrap(
        registry=FilePolicyVersionRegistry(path),
        path=str(path),
        persistent=True,
    )


def validate_policy_version_registry_path(store_path: str | Path) -> Path:
    """Validate the hosted policy version registry path before use."""

    return validate_hosted_store_path(
        store_path,
        env_name=POLICY_VERSION_REGISTRY_PATH_ENV,
        kind="file",
        required_suffix=".json",
    )
