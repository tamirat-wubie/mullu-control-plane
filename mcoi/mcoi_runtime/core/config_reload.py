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

from dataclasses import dataclass, field
from typing import Any, Callable
from hashlib import sha256
import json


@dataclass(frozen=True, slots=True)
class ConfigVersion:
    """A versioned configuration snapshot."""

    version: int
    config: dict[str, Any]
    config_hash: str
    applied_at: str
    applied_by: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class ConfigChangeResult:
    """Result of a configuration change attempt."""

    success: bool
    version: int
    previous_version: int
    changes: dict[str, Any]
    error: str = ""


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

    def __init__(self, *, clock: Callable[[], str], initial: dict[str, Any] | None = None) -> None:
        self._clock = clock
        self._current: dict[str, Any] = initial or {}
        self._version: int = 0
        self._history: list[ConfigVersion] = []
        self._validators: dict[str, Callable[[Any], bool]] = {}

        # Record initial version
        if self._current:
            self._record_version("system", "initial configuration")

    def register_validator(self, section: str, validator: Callable[[Any], bool]) -> None:
        """Register a validation function for a config section."""
        self._validators[section] = validator

    def get(self, section: str, default: Any = None) -> Any:
        """Get a configuration section."""
        return self._current.get(section, default)

    def get_all(self) -> dict[str, Any]:
        """Get the entire current configuration."""
        return dict(self._current)

    def update(
        self,
        changes: dict[str, Any],
        *,
        applied_by: str = "system",
        description: str = "",
    ) -> ConfigChangeResult:
        """Apply configuration changes atomically.

        Validates all sections before applying. If any validation
        fails, no changes are applied.
        """
        # Validate all changes
        for section, value in changes.items():
            validator = self._validators.get(section)
            if validator is not None and not validator(value):
                return ConfigChangeResult(
                    success=False,
                    version=self._version,
                    previous_version=self._version,
                    changes=changes,
                    error=f"validation failed for section: {section}",
                )

        # Apply atomically
        previous_version = self._version
        self._current.update(changes)
        self._record_version(applied_by, description or f"updated: {', '.join(changes.keys())}")

        return ConfigChangeResult(
            success=True,
            version=self._version,
            previous_version=previous_version,
            changes=changes,
        )

    def rollback(self, to_version: int, *, applied_by: str = "system") -> ConfigChangeResult:
        """Rollback to a previous configuration version."""
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
                error=f"version not found: {to_version}",
            )

        previous_version = self._version
        self._current = dict(target.config)
        self._record_version(applied_by, f"rollback to version {to_version}")

        return ConfigChangeResult(
            success=True,
            version=self._version,
            previous_version=previous_version,
            changes=target.config,
        )

    def _record_version(self, applied_by: str, description: str) -> None:
        self._version += 1
        config_bytes = json.dumps(self._current, sort_keys=True, default=str).encode()
        config_hash = sha256(config_bytes).hexdigest()

        self._history.append(ConfigVersion(
            version=self._version,
            config=dict(self._current),
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

    def history(self, limit: int = 10) -> list[ConfigVersion]:
        return self._history[-limit:]

    def diff(self, from_version: int, to_version: int) -> dict[str, Any]:
        """Compute diff between two config versions."""
        from_config: dict[str, Any] = {}
        to_config: dict[str, Any] = {}
        for v in self._history:
            if v.version == from_version:
                from_config = v.config
            if v.version == to_version:
                to_config = v.config

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
            "sections": list(self._current.keys()),
            "history_size": len(self._history),
        }
