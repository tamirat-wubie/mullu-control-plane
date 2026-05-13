"""Phase 203D — Configuration Hot-Reload.

Purpose: Live configuration updates without server restart.
    Supports updating rate limits, budget policies, feature flags,
    and LLM settings at runtime.
Governance scope: configuration management only.
Dependencies: none (pure state management).
Invariants:
  - Config changes are atomic — partial updates never apply.
  - Every change is versioned and auditable.
  - Invalid configs are rejected before application.
  - Rollback to previous version is always available.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping


FrozenConfig = Mapping[str, Any]


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    for key in value:
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-empty strings")
    return value


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return value


def _freeze_config_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({
            _require_non_empty_text(key, "config key"): _freeze_config_value(item)
            for key, item in value.items()
        })
    if isinstance(value, tuple):
        return tuple(_freeze_config_value(item) for item in value)
    if isinstance(value, list):
        return tuple(_freeze_config_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_config_value(item) for item in value)
    return copy.deepcopy(value)


def _freeze_config(value: Mapping[str, Any]) -> FrozenConfig:
    _require_mapping(value, "config")
    return _freeze_config_value(value)


def _thaw_config_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_config_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_config_value(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((_thaw_config_value(item) for item in value), key=str)
    return copy.deepcopy(value)


def _copy_config(value: Mapping[str, Any]) -> dict[str, Any]:
    return _thaw_config_value(value)


@dataclass(frozen=True, slots=True)
class ConfigVersion:
    """A versioned configuration snapshot."""

    version: int
    config: FrozenConfig
    config_hash: str
    applied_at: str
    applied_by: str
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _require_non_negative_int(self.version, "version"))
        object.__setattr__(self, "config", _freeze_config(self.config))
        object.__setattr__(self, "config_hash", _require_non_empty_text(self.config_hash, "config_hash"))
        object.__setattr__(self, "applied_at", _require_non_empty_text(self.applied_at, "applied_at"))
        object.__setattr__(self, "applied_by", _require_non_empty_text(self.applied_by, "applied_by"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class ConfigChangeResult:
    """Result of a configuration change attempt."""

    success: bool
    version: int
    previous_version: int
    changes: FrozenConfig
    error: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean")
        object.__setattr__(self, "version", _require_non_negative_int(self.version, "version"))
        object.__setattr__(
            self,
            "previous_version",
            _require_non_negative_int(self.previous_version, "previous_version"),
        )
        object.__setattr__(self, "changes", _freeze_config(self.changes))
        object.__setattr__(self, "error", _require_text(self.error, "error"))


class ConfigManager:
    """Versioned, auditable configuration with hot-reload support.

    Each config change creates a new version. The full history is
    kept for auditing and rollback.
    """

    # Known configuration sections
    KNOWN_SECTIONS = frozenset({
        "rate_limits",
        "budget_defaults",
        "llm",
        "features",
        "certification",
        "webhook",
    })

    def __init__(self, *, clock: Callable[[], str], initial: Mapping[str, Any] | None = None) -> None:
        if not callable(clock):
            raise ValueError("clock must be callable")
        self._clock = clock
        self._current: dict[str, Any] = _copy_config(_require_mapping(initial, "initial")) if initial is not None else {}
        self._version: int = 0
        self._history: list[ConfigVersion] = []
        self._validators: dict[str, Callable[[Any], bool]] = {}

        # Record initial version
        if self._current:
            self._record_version("system", "initial configuration")

    def register_validator(self, section: str, validator: Callable[[Any], bool]) -> None:
        """Register a validation function for a config section."""
        section = _require_non_empty_text(section, "section")
        if not callable(validator):
            raise ValueError("validator must be callable")
        self._validators[section] = validator

    def get(self, section: str, default: Any = None) -> Any:
        """Get a configuration section."""
        section = _require_non_empty_text(section, "section")
        if section not in self._current:
            return copy.deepcopy(default)
        return _thaw_config_value(self._current[section])

    def get_all(self) -> dict[str, Any]:
        """Get the entire current configuration."""
        return _copy_config(self._current)

    def update(
        self,
        changes: Mapping[str, Any],
        *,
        applied_by: str = "system",
        description: str = "",
    ) -> ConfigChangeResult:
        """Apply configuration changes atomically.

        Validates all sections before applying. If any validation
        fails, no changes are applied.
        """
        changes = _require_mapping(changes, "changes")
        applied_by = _require_non_empty_text(applied_by, "applied_by")
        description = _require_text(description, "description")
        changes_copy = _copy_config(changes)

        # Validate all changes
        for section, value in changes_copy.items():
            validator = self._validators.get(section)
            if validator is not None and not validator(value):
                return ConfigChangeResult(
                    success=False,
                    version=self._version,
                    previous_version=self._version,
                    changes=changes_copy,
                    error=f"validation failed for section: {section}",
                )

        # Apply atomically
        previous_version = self._version
        self._current.update(changes_copy)
        self._record_version(applied_by, description or f"updated: {', '.join(changes_copy.keys())}")

        return ConfigChangeResult(
            success=True,
            version=self._version,
            previous_version=previous_version,
            changes=changes_copy,
        )

    def rollback(self, to_version: int, *, applied_by: str = "system") -> ConfigChangeResult:
        """Rollback to a previous configuration version."""
        to_version = _require_non_negative_int(to_version, "to_version")
        applied_by = _require_non_empty_text(applied_by, "applied_by")
        target = None
        for v in self._history:
            if v.version == to_version:
                target = v
                break

        if target is None:
            return ConfigChangeResult(
                success=False,
                version=self._version,
                previous_version=self._version,
                changes={},
                error="version not found",
            )

        previous_version = self._version
        self._current = _copy_config(target.config)
        self._record_version(applied_by, f"rollback to version {to_version}")

        return ConfigChangeResult(
            success=True,
            version=self._version,
            previous_version=previous_version,
            changes=_copy_config(target.config),
        )

    def _record_version(self, applied_by: str, description: str) -> None:
        self._version += 1
        current_copy = _copy_config(self._current)
        config_bytes = json.dumps(current_copy, sort_keys=True, default=str).encode()
        config_hash = sha256(config_bytes).hexdigest()

        self._history.append(ConfigVersion(
            version=self._version,
            config=current_copy,
            config_hash=config_hash,
            applied_at=self._clock(),
            applied_by=applied_by,
            description=description,
        ))

    @property
    def version(self) -> int:
        return self._version

    @property
    def config_hash(self) -> str:
        if not self._history:
            return ""
        return self._history[-1].config_hash

    def history(self, limit: int = 10) -> tuple[ConfigVersion, ...]:
        limit = _require_non_negative_int(limit, "limit")
        if limit == 0:
            return ()
        return tuple(self._history[-limit:])

    def diff(self, from_version: int, to_version: int) -> dict[str, Any]:
        """Compute diff between two config versions."""
        from_version = _require_non_negative_int(from_version, "from_version")
        to_version = _require_non_negative_int(to_version, "to_version")
        from_config: dict[str, Any] | None = None
        to_config: dict[str, Any] | None = None
        for v in self._history:
            if v.version == from_version:
                from_config = _copy_config(v.config)
            if v.version == to_version:
                to_config = _copy_config(v.config)
        if from_config is None or to_config is None:
            raise ValueError("version not found")

        added = {k: v for k, v in to_config.items() if k not in from_config}
        removed = {k: v for k, v in from_config.items() if k not in to_config}
        changed = {
            k: {"from": from_config[k], "to": to_config[k]}
            for k in from_config
            if k in to_config and from_config[k] != to_config[k]
        }
        return {"added": added, "removed": removed, "changed": changed}

    def summary(self) -> dict[str, Any]:
        return {
            "version": self._version,
            "config_hash": self.config_hash[:16] if self.config_hash else "",
            "sections": sorted(self._current.keys()),
            "history_size": len(self._history),
        }
