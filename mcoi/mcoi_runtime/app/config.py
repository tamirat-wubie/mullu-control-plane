"""Purpose: provide deterministic local configuration for the MCOI operator entry path.
Governance scope: operator-loop configuration loading only.
Dependencies: Python standard library dataclasses only.
Invariants: configuration loading is explicit, deterministic, and free of import-time side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_APP_CONFIG_KEYS = frozenset(
    {
        "allowed_planning_classes",
        "enabled_executor_routes",
        "enabled_observer_routes",
        "autonomy_mode",
        "policy_pack_id",
        "policy_pack_version",
        "effect_assurance_required",
        "shell_sandbox_enabled",
        "shell_sandbox_id",
        "shell_allowed_cwd_roots",
        "shell_allowed_environment_keys",
        "shell_allow_inherited_environment",
        "shell_require_cwd",
    }
)


def _require_text(value: Any, _field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("config values must be non-empty strings")
    return value


def _require_text_tuple(value: Any, _field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("config values must be sequences of non-empty strings")
    items = tuple(value)
    if not items:
        raise ValueError("config values must contain at least one item")
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("config values must contain non-empty strings")
    return items


def _optional_text_tuple(value: Any, _field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError("config values must be sequences of non-empty strings")
    items = tuple(value)
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("config values must contain non-empty strings")
    return items


@dataclass(frozen=True, slots=True)
class AppConfig:
    allowed_planning_classes: tuple[str, ...] = ("constraint",)
    enabled_executor_routes: tuple[str, ...] = ("shell_command",)
    enabled_observer_routes: tuple[str, ...] = ("filesystem", "process")
    autonomy_mode: str = "bounded_autonomous"
    policy_pack_id: str | None = None
    policy_pack_version: str | None = None
    effect_assurance_required: bool = False
    shell_sandbox_enabled: bool = False
    shell_sandbox_id: str = "local"
    shell_allowed_cwd_roots: tuple[str, ...] = ()
    shell_allowed_environment_keys: tuple[str, ...] = ()
    shell_allow_inherited_environment: bool = True
    shell_require_cwd: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "allowed_planning_classes",
            _require_text_tuple(self.allowed_planning_classes, "allowed_planning_classes"),
        )
        object.__setattr__(
            self,
            "enabled_executor_routes",
            _require_text_tuple(self.enabled_executor_routes, "enabled_executor_routes"),
        )
        object.__setattr__(
            self,
            "enabled_observer_routes",
            _require_text_tuple(self.enabled_observer_routes, "enabled_observer_routes"),
        )
        object.__setattr__(self, "autonomy_mode", _require_text(self.autonomy_mode, "autonomy_mode"))
        if self.policy_pack_id is not None:
            object.__setattr__(self, "policy_pack_id", _require_text(self.policy_pack_id, "policy_pack_id"))
        if self.policy_pack_version is not None:
            object.__setattr__(
                self,
                "policy_pack_version",
                _require_text(self.policy_pack_version, "policy_pack_version"),
            )
        if not isinstance(self.effect_assurance_required, bool):
            raise ValueError("effect_assurance_required must be a boolean")
        if not isinstance(self.shell_sandbox_enabled, bool):
            raise ValueError("shell_sandbox_enabled must be a boolean")
        object.__setattr__(self, "shell_sandbox_id", _require_text(self.shell_sandbox_id, "shell_sandbox_id"))
        object.__setattr__(
            self,
            "shell_allowed_cwd_roots",
            _optional_text_tuple(self.shell_allowed_cwd_roots, "shell_allowed_cwd_roots"),
        )
        object.__setattr__(
            self,
            "shell_allowed_environment_keys",
            _optional_text_tuple(
                self.shell_allowed_environment_keys,
                "shell_allowed_environment_keys",
            ),
        )
        if not isinstance(self.shell_allow_inherited_environment, bool):
            raise ValueError("shell_allow_inherited_environment must be a boolean")
        if not isinstance(self.shell_require_cwd, bool):
            raise ValueError("shell_require_cwd must be a boolean")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> AppConfig:
        if values is None:
            normalized: dict[str, Any] = {}
        elif not isinstance(values, Mapping):
            raise ValueError("config values must be a mapping")
        else:
            normalized = dict(values)

        unknown_keys = sorted(set(normalized) - _APP_CONFIG_KEYS)
        if unknown_keys:
            raise ValueError("unknown config keys")

        return cls(
            allowed_planning_classes=tuple(
                normalized.get("allowed_planning_classes", ("constraint",))
            ),
            enabled_executor_routes=tuple(
                normalized.get("enabled_executor_routes", ("shell_command",))
            ),
            enabled_observer_routes=tuple(
                normalized.get("enabled_observer_routes", ("filesystem", "process"))
            ),
            autonomy_mode=normalized.get("autonomy_mode", "bounded_autonomous"),
            policy_pack_id=normalized.get("policy_pack_id"),
            policy_pack_version=normalized.get("policy_pack_version"),
            effect_assurance_required=normalized.get("effect_assurance_required", False),
            shell_sandbox_enabled=normalized.get("shell_sandbox_enabled", False),
            shell_sandbox_id=normalized.get("shell_sandbox_id", "local"),
            shell_allowed_cwd_roots=tuple(normalized.get("shell_allowed_cwd_roots", ())),
            shell_allowed_environment_keys=tuple(
                normalized.get("shell_allowed_environment_keys", ())
            ),
            shell_allow_inherited_environment=normalized.get(
                "shell_allow_inherited_environment",
                True,
            ),
            shell_require_cwd=normalized.get("shell_require_cwd", False),
        )
