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
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class WatchedFile:
    """A configuration file being monitored for changes."""
    path: str
    parser: Callable[[str], dict[str, Any]]  # fn(content) -> config dict
    on_change: Callable[[dict[str, Any]], None]  # fn(new_config)
    description: str = ""


@dataclass
class FileState:
    """Tracked state for a watched file."""
    path: str
    last_mtime: float = 0.0
    last_hash: str = ""
    reload_count: int = 0
    last_error: str = ""
    last_reload_at: float = 0.0


def _bounded_watch_error(exc: Exception) -> str:
    return f"watch error ({type(exc).__name__})"


class ConfigFileWatcher:
    """Polls config files for changes and triggers reload callbacks."""

    def __init__(self, poll_interval: float = 5.0,
                 clock: Callable[[], str] | None = None):
        self._poll_interval = poll_interval
        self._clock = clock
        self._watched: dict[str, WatchedFile] = {}
        self._states: dict[str, FileState] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._total_reloads = 0
        self._total_errors = 0

    def watch(self, watched: WatchedFile) -> None:
        with self._lock:
            self._watched[watched.path] = watched
            self._states[watched.path] = FileState(path=watched.path)

    def unwatch(self, path: str) -> None:
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
    return json.loads(content)
