"""Phase 204D — Plugin System Contracts.

Purpose: Extensible plugin architecture for governed components.
    Plugins can register hooks, add capabilities, and extend
    the runtime without modifying core code.
Governance scope: plugin lifecycle management only.
Dependencies: none (pure contracts).
Invariants:
  - Plugins declare dependencies — loading order is deterministic.
  - Plugin hooks are validated against known hook points.
  - Disabled plugins are never invoked.
  - Plugin errors don't crash the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable


def _classify_plugin_exception(exc: Exception) -> str:
    """Return a bounded plugin hook failure message."""
    return f"plugin hook error ({type(exc).__name__})"


class PluginStatus(StrEnum):
    REGISTERED = "registered"
    LOADED = "loaded"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERRORED = "errored"


class HookPoint(StrEnum):
    """Well-known hook points in the governed runtime."""

    PRE_DISPATCH = "pre_dispatch"
    POST_DISPATCH = "post_dispatch"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    PRE_EXECUTE = "pre_execute"
    POST_EXECUTE = "post_execute"
    ON_SESSION_CREATE = "on_session_create"
    ON_BUDGET_CHECK = "on_budget_check"
    ON_CERTIFICATION = "on_certification"
    ON_ERROR = "on_error"


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """Describes a plugin's identity and capabilities."""

    plugin_id: str
    name: str
    version: str
    description: str = ""
    dependencies: tuple[str, ...] = ()
    hooks: tuple[HookPoint, ...] = ()


@dataclass
class PluginInstance:
    """Runtime state for a loaded plugin."""

    descriptor: PluginDescriptor
    status: PluginStatus = PluginStatus.REGISTERED
    hooks: dict[HookPoint, Callable[..., Any]] = field(default_factory=dict)
    error: str = ""


class PluginRegistry:
    """Manages plugin lifecycle — registration, loading, hook dispatch."""

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInstance] = {}

    def register(self, descriptor: PluginDescriptor) -> PluginInstance:
        """Register a plugin descriptor."""
        if descriptor.plugin_id in self._plugins:
            raise ValueError(f"plugin already registered: {descriptor.plugin_id}")

        instance = PluginInstance(descriptor=descriptor)
        self._plugins[descriptor.plugin_id] = instance
        return instance

    def load(
        self,
        plugin_id: str,
        hooks: dict[HookPoint, Callable[..., Any]] | None = None,
    ) -> PluginInstance:
        """Load a plugin — register its hook implementations."""
        instance = self._plugins.get(plugin_id)
        if instance is None:
            raise ValueError(f"plugin not found: {plugin_id}")

        # Check dependencies
        for dep_id in instance.descriptor.dependencies:
            dep = self._plugins.get(dep_id)
            if dep is None or dep.status not in (PluginStatus.LOADED, PluginStatus.ACTIVE):
                raise ValueError(f"dependency not loaded: {dep_id}")

        if hooks:
            for hook_point, fn in hooks.items():
                if hook_point not in instance.descriptor.hooks:
                    raise ValueError(
                        f"plugin {plugin_id} didn't declare hook {hook_point}"
                    )
                instance.hooks[hook_point] = fn

        instance.status = PluginStatus.LOADED
        return instance

    def activate(self, plugin_id: str) -> PluginInstance:
        """Activate a loaded plugin."""
        instance = self._plugins.get(plugin_id)
        if instance is None:
            raise ValueError(f"plugin not found: {plugin_id}")
        if instance.status != PluginStatus.LOADED:
            raise ValueError(f"plugin not loaded: {plugin_id} (status: {instance.status})")
        instance.status = PluginStatus.ACTIVE
        return instance

    def disable(self, plugin_id: str) -> bool:
        """Disable a plugin."""
        instance = self._plugins.get(plugin_id)
        if instance is None:
            return False
        instance.status = PluginStatus.DISABLED
        return True

    def get(self, plugin_id: str) -> PluginInstance | None:
        return self._plugins.get(plugin_id)

    def dispatch_hook(self, hook_point: HookPoint, **kwargs: Any) -> list[Any]:
        """Dispatch a hook to all active plugins that implement it.

        Returns list of results. Errors are caught and recorded.
        """
        results: list[Any] = []
        for instance in self._plugins.values():
            if instance.status != PluginStatus.ACTIVE:
                continue
            fn = instance.hooks.get(hook_point)
            if fn is None:
                continue
            try:
                result = fn(**kwargs)
                results.append(result)
            except Exception as exc:
                error_message = _classify_plugin_exception(exc)
                instance.error = error_message
                instance.status = PluginStatus.ERRORED
                results.append({"error": error_message, "plugin": instance.descriptor.plugin_id})
        return results

    def list_plugins(self) -> list[PluginInstance]:
        return sorted(self._plugins.values(), key=lambda p: p.descriptor.plugin_id)

    def active_plugins(self) -> list[PluginInstance]:
        return [p for p in self._plugins.values() if p.status == PluginStatus.ACTIVE]

    @property
    def count(self) -> int:
        return len(self._plugins)

    def summary(self) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for p in self._plugins.values():
            status_counts[p.status.value] = status_counts.get(p.status.value, 0) + 1
        return {
            "total": self.count,
            "status_counts": status_counts,
            "active": len(self.active_plugins()),
        }
