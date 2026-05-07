"""Purpose: managed background loop for temporal scheduler worker ticks.
Governance scope: optional periodic execution of due temporal actions.
Dependencies: temporal scheduler worker and standard threading primitives.
Invariants:
  - Background execution is opt-in by caller.
  - Each loop iteration is bounded by run_once(limit=...).
  - Exceptions are counted and bounded, not leaked through the thread.
  - Stop joins the worker thread before shutdown proceeds.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

def _bounded_background_error(exc: BaseException) -> str:
    return f"temporal scheduler background error ({type(exc).__name__})"


@dataclass(frozen=True, slots=True)
class TemporalBackgroundTick:
    """Observable result of a background worker tick."""

    tick_index: int
    processed_count: int
    error: str = ""


class TemporalSchedulerBackgroundLoop:
    """Thread-managed temporal scheduler worker loop."""

    def __init__(
        self,
        *,
        worker: Any,
        interval_seconds: float = 30.0,
        limit: int = 10,
    ) -> None:
        if not callable(getattr(worker, "run_once", None)):
            raise TypeError("worker must provide run_once")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        if limit < 1:
            raise ValueError("limit must be positive")
        self._worker = worker
        self._interval_seconds = interval_seconds
        self._limit = limit
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._tick_count = 0
        self._processed_count = 0
        self._error_count = 0
        self._last_error = ""

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def tick_once(self) -> TemporalBackgroundTick:
        """Run one bounded worker tick synchronously."""
        with self._lock:
            self._tick_count += 1
            tick_index = self._tick_count
        try:
            results = self._worker.run_once(limit=self._limit)
        except Exception as exc:
            error = _bounded_background_error(exc)
            with self._lock:
                self._error_count += 1
                self._last_error = error
            return TemporalBackgroundTick(
                tick_index=tick_index,
                processed_count=0,
                error=error,
            )
        with self._lock:
            self._processed_count += len(results)
            self._last_error = ""
        return TemporalBackgroundTick(
            tick_index=tick_index,
            processed_count=len(results),
        )

    def start(self) -> bool:
        """Start the background loop if it is not already running."""
        if self.running:
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="temporal-scheduler-background",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> dict[str, Any]:
        """Stop the background loop and return bounded shutdown state."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._interval_seconds + 1.0)
        self._thread = None
        return self.summary()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.tick_once()
            self._stop_event.wait(self._interval_seconds)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "interval_seconds": self._interval_seconds,
                "limit": self._limit,
                "tick_count": self._tick_count,
                "processed_count": self._processed_count,
                "error_count": self._error_count,
                "last_error": self._last_error,
                "governed": True,
            }
