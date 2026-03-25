"""Purpose: named configuration profiles for deterministic runtime startup.
Governance scope: config profile loading and merging only.
Dependencies: AppConfig, deployment profile inventory.
Invariants:
  - Config profiles derive from the canonical deployment profile inventory.
  - No profile silently widens permissions.
  - Profile merging is deterministic — later values override earlier ones.
  - Unknown profile names fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .config import AppConfig
from .deployment_profiles import BUILTIN_PROFILES


class ProfileName(StrEnum):
    """Canonical profile names."""

    LOCAL_DEV = "local-dev"
    SAFE_READONLY = "safe-readonly"
    OPERATOR_APPROVED = "operator-approved"
    SANDBOXED = "sandboxed"
    PILOT_PROD = "pilot-prod"


@dataclass(frozen=True, slots=True)
class ProfileLoadResult:
    """Result of loading a profile."""

    profile_name: str
    config: AppConfig
    overrides_applied: int


class ProfileLoadError(ValueError):
    """Raised when a profile cannot be loaded."""


def load_profile(
    name: str,
    *,
    overrides: Mapping[str, Any] | None = None,
) -> ProfileLoadResult:
    """Load a named profile, optionally with overrides.

    Overrides are applied on top of the profile defaults.
    Unknown profile names fail closed.
    """
    deployment_profile = BUILTIN_PROFILES.get(name)
    if deployment_profile is None:
        raise ProfileLoadError(f"unknown profile: {name}")

    base = deployment_profile.to_config_dict()
    override_count = 0

    if overrides:
        for key, value in overrides.items():
            if key in base:
                base[key] = value
                override_count += 1
            else:
                raise ProfileLoadError(f"unknown config key in overrides: {key}")

    config = AppConfig.from_mapping(base)

    return ProfileLoadResult(
        profile_name=deployment_profile.profile_id,
        config=config,
        overrides_applied=override_count,
    )


def list_profiles() -> tuple[str, ...]:
    """List all available profile names."""
    return tuple(sorted(BUILTIN_PROFILES.keys()))
