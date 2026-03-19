"""Purpose: named configuration profiles for deterministic runtime startup.
Governance scope: profile loading and merging only.
Dependencies: AppConfig.
Invariants:
  - Profiles are explicit and named.
  - No profile silently widens permissions.
  - Profile merging is deterministic — later values override earlier ones.
  - Unknown profile names fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from .config import AppConfig


class ProfileName(StrEnum):
    """Canonical profile names."""

    LOCAL_DEV = "local-dev"
    SAFE_READONLY = "safe-readonly"
    OPERATOR_APPROVED = "operator-approved"
    SANDBOXED = "sandboxed"


# Built-in profile definitions — frozen to prevent accidental mutation
_BUILTIN_PROFILES: Mapping[str, Mapping[str, Any]] = MappingProxyType({
    ProfileName.LOCAL_DEV: MappingProxyType({
        "allowed_planning_classes": ("constraint",),
        "enabled_executor_routes": ("shell_command",),
        "enabled_observer_routes": ("filesystem", "process"),
    }),
    ProfileName.SAFE_READONLY: MappingProxyType({
        "allowed_planning_classes": ("constraint",),
        "enabled_executor_routes": ("shell_command",),
        "enabled_observer_routes": ("filesystem",),
    }),
    ProfileName.OPERATOR_APPROVED: MappingProxyType({
        "allowed_planning_classes": ("constraint", "learned"),
        "enabled_executor_routes": ("shell_command",),
        "enabled_observer_routes": ("filesystem", "process"),
    }),
    ProfileName.SANDBOXED: MappingProxyType({
        "allowed_planning_classes": ("constraint",),
        "enabled_executor_routes": ("shell_command",),
        "enabled_observer_routes": ("filesystem",),
    }),
})


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
    if name not in _BUILTIN_PROFILES:
        raise ProfileLoadError(f"unknown profile: {name}")

    base = dict(_BUILTIN_PROFILES[name])
    override_count = 0

    if overrides:
        for key, value in overrides.items():
            if key in base:
                base[key] = value
                override_count += 1
            else:
                raise ProfileLoadError(f"unknown config key in overrides: {key}")

    config = AppConfig(
        allowed_planning_classes=tuple(base["allowed_planning_classes"]),
        enabled_executor_routes=tuple(base["enabled_executor_routes"]),
        enabled_observer_routes=tuple(base["enabled_observer_routes"]),
    )

    return ProfileLoadResult(
        profile_name=name,
        config=config,
        overrides_applied=override_count,
    )


def list_profiles() -> tuple[str, ...]:
    """List all available profile names."""
    return tuple(sorted(_BUILTIN_PROFILES.keys()))
