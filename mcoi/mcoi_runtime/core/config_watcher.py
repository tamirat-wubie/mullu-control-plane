"""Phase 223C — Config Hot-Reload File Watcher.

Purpose: Watch configuration files for changes and trigger governed
    reload callbacks. Uses file modification time polling (no OS-specific
    watchers needed).
Dependencies: None (stdlib only).
Invariants:
  - Reload only triggers when file mtime changes.
  - Callbacks receive parsed config dict.
  - Failed reloads are logged, not propagated.
  - Thread-safe via simple locking.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _require_non_negative_number(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    number = float(value)
    if number < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


@dataclass(frozen=True)
class WatchedFile:
    """A configuration file being monitored for changes."""

    path: str
    parser: Callable[[str], dict[str, Any]]  # fn(content) -> config dict
    on_change: Callable[[dict[str, Any]], None]  # fn(new_config)
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _require_non_empty_text(self.path, "path"))
        if not callable(self.parser):
            raise ValueError("parser must be callable")
        if not callable(self.on_change):
            raise ValueError("on_change must be callable")
        object.__setattr__(self, "description", _require_text(self.description, "description"))


@dataclass
class FileState:
    """Tracked state for a watched file."""

    path: str
    last_mtime: float = 0.0
    last_hash: str = ""
    reload_count: int = 0
    last_error: str = ""
    last_reload_at: float = 0.0

    def __post_init__(self) -> None:
        self.path = _require_non_empty_text(self.path, "path")
        self.last_mtime = _require_non_negative_number(self.last_mtime, "last_mtime")
        self.last_hash = _require_text(self.last_hash, "last_hash")
        if not isinstance(self.reload_count, int) or isinstance(self.reload_count, bool):
            raise ValueError("reload_count must be an integer")
        if self.reload_count < 0:
            raise ValueError("reload_count must be non-negative")
        self.last_error = _require_text(self.last_error, "last_error")
        self.last_reload_at = _require_non_negative_number(self.last_reload_at, "last_reload_at")


def _bounded_watch_error(exc: Exception) -> str:
    return f"watch error ({type(exc).__name__})"


class ConfigFileWatcher:
    """Polls config files for changes and triggers reload callbacks."""

    def __init__(self, poll_interval: float = 5.0,
                 clock: Callable[[], str] | None = None):
        self._poll_interval = _require_non_negative_number(poll_interval, "poll_interval")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        self._clock = clock
        self._watched: dict[str, WatchedFile] = {}
        self._states: dict[str, FileState] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._total_reloads = 0
        self._total_errors = 0

    def watch(self, watched: WatchedFile) -> None:
        if not isinstance(watched, WatchedFile):
            raise ValueError("watched must be a WatchedFile instance")
        with self._lock:
            self._watched[watched.path] = watched
            self._states[watched.path] = FileState(path=watched.path)

    def unwatch(self, path: str) -> None:
        path = _require_non_empty_text(path, "path")
        with self._lock:
            self._watched.pop(path, None)
            self._states.pop(path, None)

    @property
    def watched_count(self) -> int:
        return len(self._watched)

    def check_once(self) -> list[str]:
        """Check all files once and trigger callbacks for changed ones.
        Returns list of paths that were reloaded."""
        reloaded = []
        with self._lock:
            items = list(self._watched.items())

        for path, watched in items:
            state: FileState | None = None
            try:
                if not os.path.exists(path):
                    continue
                state = self._states.get(path)
                if not state:
                    continue
                mtime = os.path.getmtime(path)
                if mtime == state.last_mtime:
                    continue

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                config = watched.parser(content)
                if not isinstance(config, Mapping):
                    raise ValueError("parser must return a mapping")
                watched.on_change(config)

                with self._lock:
                    state.last_mtime = mtime
                    state.reload_count += 1
                    state.last_reload_at = time.time()
                    state.last_error = ""
                    self._total_reloads += 1

                reloaded.append(path)
            except Exception as exc:
                with self._lock:
                    if state:
                        state.last_error = _bounded_watch_error(exc)
                    self._total_errors += 1

        return reloaded

    def start(self) -> None:
        """Start background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._poll_interval + 1)
            self._thread = None

    def _poll_loop(self) -> None:
        while self._running:
            self.check_once()
            time.sleep(self._poll_interval)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "watched_files": self.watched_count,
                "total_reloads": self._total_reloads,
                "total_errors": self._total_errors,
                "running": self._running,
                "poll_interval": self._poll_interval,
                "files": {
                    path: {
                        "reload_count": state.reload_count,
                        "last_error": state.last_error,
                    }
                    for path, state in self._states.items()
                },
            }


def json_parser(content: str) -> dict[str, Any]:
    """Default JSON config parser."""
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("json config must be an object")
    return parsed
