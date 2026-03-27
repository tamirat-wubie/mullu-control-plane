"""Shared dependency container for router modules.

Subsystem instances are injected here by server.py at startup.
Routers import from this module instead of server.py to avoid circular deps.
"""
from __future__ import annotations

from typing import Any


class _Deps:
    """Holds references to all subsystem instances.

    Populated by server.py at import time via set().
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        self._store[name] = value

    def get(self, name: str) -> Any:
        v = self._store.get(name)
        if v is None:
            raise RuntimeError(f"Dependency '{name}' not registered. Was server.py loaded?")
        return v

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return self.get(name)


deps = _Deps()
