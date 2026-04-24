"""Purpose: deployment profile definitions for controlled runtime environments.
Governance scope: profile definition and selection only.
Dependencies: app config, autonomy contracts.
Invariants:
  - Profiles are immutable once defined.
  - No profile silently widens permissions beyond its declared autonomy mode.
  - Profile selection is explicit, not inferred.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from mcoi_runtime.contracts._base import freeze_value

if TYPE_CHECKING:
    from mcoi_runtime.contracts.deployment import DeploymentBinding


@dataclass(frozen=True, slots=True)
class DeploymentProfile:
    """A named deployment configuration binding autonomy, policy, providers, and retention."""

    profile_id: str
    name: str
    description: str
    autonomy_mode: str
    policy_pack_id: str | None = None
    policy_pack_version: str | None = None
    allowed_planning_classes: tuple[str, ...] = ("constraint",)
    enabled_executor_routes: tuple[str, ...] = ("shell_command",)
    enabled_observer_routes: tuple[str, ...] = ("filesystem", "process")
    max_retention_days: int = 90
    export_enabled: bool = True
    import_enabled: bool = False
    telemetry_enabled: bool = True
    effect_assurance_required: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profile_id or not self.profile_id.strip():
            raise ValueError("profile_id must be non-empty")
        if not self.name or not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.autonomy_mode or not self.autonomy_mode.strip():
            raise ValueError("autonomy_mode must be non-empty")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))

    def to_config_dict(self) -> dict[str, Any]:
        """Convert to AppConfig-compatible dict."""
        return {
            "allowed_planning_classes": list(self.allowed_planning_classes),
            "enabled_executor_routes": list(self.enabled_executor_routes),
            "enabled_observer_routes": list(self.enabled_observer_routes),
            "autonomy_mode": self.autonomy_mode,
            "policy_pack_id": self.policy_pack_id,
            "policy_pack_version": self.policy_pack_version,
            "effect_assurance_required": self.effect_assurance_required,
        }


# --- Built-in profiles ---

LOCAL_DEV = DeploymentProfile(
    profile_id="local-dev",
    name="Local Development",
    description="Full capability for local development and testing",
    autonomy_mode="bounded_autonomous",
    enabled_executor_routes=("shell_command",),
    enabled_observer_routes=("filesystem", "process"),
    max_retention_days=7,
    export_enabled=True,
    import_enabled=True,
    telemetry_enabled=True,
)

SAFE_READONLY = DeploymentProfile(
    profile_id="safe-readonly",
    name="Safe Read-Only",
    description="Observe and analyze only — no execution or mutation",
    autonomy_mode="observe_only",
    enabled_executor_routes=("shell_command",),
    enabled_observer_routes=("filesystem", "process"),
    max_retention_days=30,
    export_enabled=True,
    import_enabled=False,
)

OPERATOR_APPROVED = DeploymentProfile(
    profile_id="operator-approved",
    name="Operator Approved",
    description="All actions require explicit operator approval",
    autonomy_mode="approval_required",
    enabled_executor_routes=("shell_command",),
    enabled_observer_routes=("filesystem", "process"),
    max_retention_days=90,
    export_enabled=True,
    import_enabled=False,
    effect_assurance_required=True,
)

SANDBOXED = DeploymentProfile(
    profile_id="sandboxed",
    name="Sandboxed",
    description="Suggest-only mode — no live execution",
    autonomy_mode="suggest_only",
    enabled_executor_routes=("shell_command",),
    enabled_observer_routes=("filesystem",),
    max_retention_days=14,
    export_enabled=True,
    import_enabled=False,
)

PILOT_PROD = DeploymentProfile(
    profile_id="pilot-prod",
    name="Pilot Production",
    description="Production-like with approval required and full telemetry",
    autonomy_mode="approval_required",
    policy_pack_id="default-safe",
    policy_pack_version="v0.1",
    enabled_executor_routes=("shell_command",),
    enabled_observer_routes=("filesystem", "process"),
    max_retention_days=180,
    export_enabled=True,
    import_enabled=False,
    telemetry_enabled=True,
    effect_assurance_required=True,
)


BUILTIN_PROFILES: dict[str, DeploymentProfile] = {
    p.profile_id: p
    for p in (LOCAL_DEV, SAFE_READONLY, OPERATOR_APPROVED, SANDBOXED, PILOT_PROD)
}


def get_profile(profile_id: str) -> DeploymentProfile | None:
    """Look up a built-in deployment profile by ID."""
    return BUILTIN_PROFILES.get(profile_id)


def list_profiles() -> tuple[DeploymentProfile, ...]:
    """List all built-in deployment profiles."""
    return tuple(sorted(BUILTIN_PROFILES.values(), key=lambda p: p.profile_id))


def bind_profile(profile: DeploymentProfile) -> "DeploymentBinding":
    """Create a DeploymentBinding from a profile (app-layer convenience)."""
    from mcoi_runtime.contracts.deployment import DeploymentBinding
    return DeploymentBinding(
        profile_id=profile.profile_id,
        autonomy_mode=profile.autonomy_mode,
        policy_pack_id=profile.policy_pack_id,
        policy_pack_version=profile.policy_pack_version,
        allowed_executor_routes=profile.enabled_executor_routes,
        allowed_observer_routes=profile.enabled_observer_routes,
        export_enabled=profile.export_enabled,
        import_enabled=profile.import_enabled,
        max_retention_days=profile.max_retention_days,
        telemetry_enabled=profile.telemetry_enabled,
    )
