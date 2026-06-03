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
            raise RuntimeError("dependency not registered")
        return v

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return self.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        # Private attributes (e.g. ``_store``) are real instance state. Public
        # names route into the dependency dict so ``deps.x = v``,
        # ``deps.set("x", v)`` and ``monkeypatch.setattr(deps, "x", v)`` are all
        # equivalent. Without this, ``setattr`` creates a real instance attribute
        # that permanently shadows ``__getattr__`` — and monkeypatch's teardown
        # (which *re-setattrs* the saved value) leaves that shadow in place,
        # silently breaking ``set()`` for that key for the rest of the process.
        # That was a cross-test pollution source: a tenant-scope test patching
        # ``deps.temporal_scheduler_store`` poisoned later temporal router tests.
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._store[name] = value

    def __delattr__(self, name: str) -> None:
        # Symmetric with __setattr__: deleting a public name (as monkeypatch may
        # do on teardown when the attribute was previously absent) clears the
        # dict entry rather than failing on a missing instance attribute.
        if name.startswith("_"):
            object.__delattr__(self, name)
        else:
            self._store.pop(name, None)


deps = _Deps()
