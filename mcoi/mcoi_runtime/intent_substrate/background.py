"""BackgroundTicker — drives IntentResolver.tick() while the substrate is idle.

Without ambient event traffic, ReplayEngine.tick() only runs when an
event arrives or evaluate() is called explicitly. In genuinely idle
windows a pending fulfillment would sit indefinitely after its
confirm_window has elapsed.

The ticker is a daemon thread that calls resolver.tick() every
`interval_s` seconds. Pick interval_s smaller than confirm_window_s
(typically 1/4) so confirms fire within ~1.25 * confirm_window even
on idle systems.

Usage:
    with BackgroundTicker(resolver, interval_s=0.05):
        ...
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from .resolver import IntentResolver

logger = logging.getLogger(__name__)


def _bounded_ticker_error(exc: BaseException) -> str:
    return f"intent substrate ticker error ({type(exc).__name__})"


class BackgroundTicker:
    def __init__(
        self, resolver: IntentResolver, *, interval_s: float = 0.1
    ) -> None:
        if interval_s <= 0:
            raise ValueError(f"interval_s must be > 0, got {interval_s!r}")
        self._resolver = resolver
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._tick_count = 0
        self._error_count = 0
        self._last_error = ""

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("BackgroundTicker already running")
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="intent-substrate-ticker",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float | None = 2.0) -> None:
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is None:
            return
        self._stop.set()
        thread.join(timeout=timeout)

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def summary(self) -> dict[str, object]:
        """Return bounded ticker state for diagnostics and shutdown receipts."""
        with self._lock:
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                "interval_s": self._interval_s,
                "tick_count": self._tick_count,
                "error_count": self._error_count,
                "last_error": self._last_error,
                "governed": True,
            }

    def __enter__(self) -> "BackgroundTicker":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.stop()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval_s):
            try:
                with self._lock:
                    self._tick_count += 1
                self._resolver.tick()
                with self._lock:
                    self._last_error = ""
            except Exception as exc:
                error = _bounded_ticker_error(exc)
                with self._lock:
                    self._error_count += 1
                    self._last_error = error
                logger.exception("intent_substrate ticker raised")
