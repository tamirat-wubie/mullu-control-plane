"""Small concurrency primitives shared across the in-memory managers.

FastAPI runs sync route handlers in a threadpool, so the in-memory managers are
hit concurrently. A manager that mints ids from a plain integer counter --
``self._counter += 1; id = f"x-{self._counter}"`` -- has a read-modify-write
race: two threads can read the same value and emit DUPLICATE ids, which is an
audit / lookup integrity problem (ids are expected to be unique).

``AtomicCounter`` makes the increment atomic so each minted value is unique,
WITHOUT locking the surrounding (often slow -- LLM calls, tool invocations)
method body. Managers with additional shared mutable state (history lists, dict
iteration) still need their own lock; this only fixes the counter->id race.
"""

from __future__ import annotations

import threading


class AtomicCounter:
    """A thread-safe monotonic counter.

    Drop-in replacement for a plain ``int`` id counter: construct with
    ``AtomicCounter()`` and mint ids with ``f"x-{counter.next()}"`` instead of
    ``self._n += 1; f"x-{self._n}"``. Read the current value with ``.value`` for
    stats / summaries.
    """

    __slots__ = ("_value", "_lock")

    def __init__(self, start: int = 0) -> None:
        self._value = start
        self._lock = threading.Lock()

    def next(self) -> int:
        """Atomically increment and return the new value."""
        with self._lock:
            self._value += 1
            return self._value

    @property
    def value(self) -> int:
        """The current value (no increment). Safe to read for summaries."""
        return self._value
