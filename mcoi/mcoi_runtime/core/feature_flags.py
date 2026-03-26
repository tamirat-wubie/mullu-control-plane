"""Phase 220 — Feature Flags.

Purpose: Runtime feature toggles for gradual rollout and A/B testing.
Governance scope: flag evaluation only.
Invariants:
  - Flag evaluation is deterministic for same inputs.
  - Disabled flags never execute gated code paths.
  - Tenant-scoped overrides take precedence over defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class FeatureFlag:
    """A named feature flag."""
    flag_id: str
    name: str
    enabled: bool = False
    tenant_overrides: dict[str, bool] | None = None
    description: str = ""


class FeatureFlagEngine:
    """Evaluates feature flags with tenant-scoped overrides."""

    def __init__(self) -> None:
        self._flags: dict[str, FeatureFlag] = {}

    def register(self, flag: FeatureFlag) -> None:
        self._flags[flag.flag_id] = flag

    def is_enabled(self, flag_id: str, tenant_id: str = "") -> bool:
        flag = self._flags.get(flag_id)
        if flag is None:
            return False
        if tenant_id and flag.tenant_overrides and tenant_id in flag.tenant_overrides:
            return flag.tenant_overrides[tenant_id]
        return flag.enabled

    def set_enabled(self, flag_id: str, enabled: bool) -> bool:
        flag = self._flags.get(flag_id)
        if flag is None:
            return False
        self._flags[flag_id] = FeatureFlag(
            flag_id=flag.flag_id, name=flag.name, enabled=enabled,
            tenant_overrides=flag.tenant_overrides, description=flag.description,
        )
        return True

    def list_flags(self) -> list[FeatureFlag]:
        return sorted(self._flags.values(), key=lambda f: f.flag_id)

    @property
    def count(self) -> int:
        return len(self._flags)

    def summary(self) -> dict[str, Any]:
        enabled = sum(1 for f in self._flags.values() if f.enabled)
        return {"total": self.count, "enabled": enabled, "disabled": self.count - enabled}
