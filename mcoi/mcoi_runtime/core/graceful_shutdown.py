"""Phase 214C — Graceful Shutdown Contracts.

Purpose: Coordinated shutdown of all subsystems with state preservation.
    Ensures in-flight requests complete, state is saved, and connections
    are cleanly closed before the process exits.
Governance scope: shutdown coordination only.
Dependencies: state_persistence (for state saving).
Invariants:
  - Shutdown hooks run by priority, then reverse registration order.
  - Each hook has a timeout — slow hooks don't block indefinitely.
  - Shutdown execution is idempotent after the first completed run.
  - State is saved before connections close.
  - Shutdown status is trackable.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import math
import queue
import threading
import time
from typing import Any, Callable


def _classify_shutdown_exception(exc: Exception) -> str:
    """Return a bounded shutdown hook failure message."""
    return f"shutdown hook error ({type(exc).__name__})"


def _classify_shutdown_timeout() -> str:
    """Return a bounded shutdown hook timeout message."""
    return "shutdown hook timeout"


def _put_hook_result(
    result_queue: queue.Queue[tuple[str, dict[str, Any] | Exception]],
    status: str,
    payload: dict[str, Any] | Exception,
) -> None:
    """Record the first hook result without leaking daemon-thread errors."""
    with suppress(queue.Full):
        result_queue.put_nowait((status, payload))


@dataclass(frozen=True, slots=True)
class ShutdownHook:
    """A named shutdown hook with priority."""

    name: str
    priority: int  # Higher = runs first
    fn: Callable[[], dict[str, Any]]
    timeout_seconds: float = 10.0


@dataclass(frozen=True, slots=True)
class ShutdownResult:
    """Result of running all shutdown hooks."""

    hooks_run: int
    hooks_succeeded: int
    hooks_failed: int
    results: tuple[dict[str, Any], ...]
    total_duration_ms: float


class ShutdownManager:
    """Coordinates graceful shutdown of all subsystems."""

    def __init__(self) -> None:
        self._hooks: list[ShutdownHook] = []
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._shutdown_started = False
        self._shutdown_complete = False
        self._last_result: ShutdownResult | None = None

    def register(
        self,
        name: str,
        fn: Callable[[], dict[str, Any]],
        *,
        priority: int = 0,
        timeout_seconds: float = 10.0,
    ) -> None:
        """Register a shutdown hook."""
        with self._lock:
            if self._shutdown_started:
                raise RuntimeError("shutdown hook registration closed")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("shutdown hook name must be a non-empty string")
            if any(h.name == name.strip() for h in self._hooks):
                raise ValueError("shutdown hook name must be unique")
            if not callable(fn):
                raise ValueError("shutdown hook fn must be callable")
            if isinstance(priority, bool) or not isinstance(priority, int):
                raise ValueError("shutdown hook priority must be an integer")
            if (
                isinstance(timeout_seconds, bool)
                or not isinstance(timeout_seconds, (int, float))
                or not math.isfinite(float(timeout_seconds))
                or float(timeout_seconds) <= 0
            ):
                raise ValueError("shutdown hook timeout_seconds must be positive")
            self._hooks.append(ShutdownHook(
                name=name.strip(),
                priority=priority,
                fn=fn,
                timeout_seconds=float(timeout_seconds),
            ))

    def execute(self) -> ShutdownResult:
        """Run all shutdown hooks in priority order (highest first)."""
        with self._condition:
            if self._last_result is not None:
                return self._last_result
            if self._shutdown_started:
                while self._last_result is None:
                    self._condition.wait()
                return self._last_result
            self._shutdown_started = True
            ordered = self._ordered_hooks_unlocked()

        start = time.monotonic()
        results: list[dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for hook in ordered:
            hook_result = self._execute_hook(hook)
            if hook_result["status"] == "ok":
                results.append(hook_result)
                succeeded += 1
            else:
                results.append(hook_result)
                failed += 1

        total_ms = (time.monotonic() - start) * 1000
        shutdown_result = ShutdownResult(
            hooks_run=len(ordered),
            hooks_succeeded=succeeded,
            hooks_failed=failed,
            results=tuple(results),
            total_duration_ms=round(total_ms, 2),
        )
        with self._condition:
            self._shutdown_complete = True
            self._last_result = shutdown_result
            self._condition.notify_all()
            return self._last_result

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._shutdown_complete

    @property
    def hook_count(self) -> int:
        with self._lock:
            return len(self._hooks)

    def hook_names(self) -> list[str]:
        with self._lock:
            return [h.name for h in self._ordered_hooks_unlocked()]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "hooks": len(self._hooks),
                "hook_names": [h.name for h in self._ordered_hooks_unlocked()],
                "shutdown_started": self._shutdown_started,
                "shutdown_complete": self._shutdown_complete,
            }

    def _ordered_hooks_unlocked(self) -> list[ShutdownHook]:
        """Return hooks by priority, then LIFO for equal priorities."""
        return [
            hook
            for _, hook in sorted(
                enumerate(self._hooks),
                key=lambda item: (item[1].priority, item[0]),
                reverse=True,
            )
        ]

    def _execute_hook(self, hook: ShutdownHook) -> dict[str, Any]:
        """Execute one hook with its configured timeout."""
        result_queue: queue.Queue[tuple[str, dict[str, Any] | Exception]] = queue.Queue(maxsize=1)

        def run_hook() -> None:
            try:
                result = hook.fn()
                if not isinstance(result, dict):
                    raise TypeError("shutdown hook must return a dict")
                _put_hook_result(result_queue, "ok", result)
            except Exception as exc:
                _put_hook_result(result_queue, "error", exc)

        thread = threading.Thread(
            target=run_hook,
            name=f"mullu-shutdown-{hook.name}",
            daemon=True,
        )
        thread.start()
        thread.join(timeout=hook.timeout_seconds)
        if thread.is_alive():
            return {
                "hook": hook.name,
                "status": "error",
                "error": _classify_shutdown_timeout(),
            }

        try:
            status, payload = result_queue.get_nowait()
        except queue.Empty:
            return {
                "hook": hook.name,
                "status": "error",
                "error": _classify_shutdown_exception(RuntimeError()),
            }
        if status == "ok":
            result = dict(payload)
            result["hook"] = hook.name
            result["status"] = "ok"
            return result
        return {
            "hook": hook.name,
            "status": "error",
            "error": _classify_shutdown_exception(payload),
        }
