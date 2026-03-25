"""Purpose: shared base protocol for all MCOI runtime engines.
Governance scope: defines the standard interface that every engine must
    implement for checkpoint, replay, persistence, and audit compatibility.
Dependencies: Python standard library only.
Invariants:
  - Every engine must be deterministically hashable.
  - Every engine must support snapshot/restore for persistence.
  - Every engine must support injected clock for replay determinism.
  - Constructor must validate event_spine type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Clock protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """Protocol for injectable clock sources."""

    def now_iso(self) -> str:
        """Return current time as ISO 8601 string."""
        ...


class WallClock:
    """Default wall-clock implementation."""

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()


class FixedClock:
    """Fixed clock for deterministic testing and replay."""

    def __init__(self, fixed_time: str = "2026-01-01T00:00:00+00:00") -> None:
        self._time = fixed_time
        self._tick = 0

    def now_iso(self) -> str:
        self._tick += 1
        return self._time

    def advance(self, new_time: str) -> None:
        self._time = new_time


class MonotonicClock:
    """Monotonically incrementing clock for replay-safe operations."""

    def __init__(self, base: str = "2026-01-01T00:00:00+00:00") -> None:
        self._base = datetime.fromisoformat(base)
        self._tick = 0

    def now_iso(self) -> str:
        from datetime import timedelta
        self._tick += 1
        t = self._base + timedelta(seconds=self._tick)
        return t.isoformat()


# ---------------------------------------------------------------------------
# Engine base protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EngineProtocol(Protocol):
    """Protocol that all MCOI engines should implement."""

    def state_hash(self) -> str:
        """Deterministic SHA-256 hash of all engine state."""
        ...

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        ...

    def restore(self, data: dict[str, Any]) -> None:
        """Restore engine state from a snapshot dict."""
        ...


# ---------------------------------------------------------------------------
# Engine base class (optional mixin)
# ---------------------------------------------------------------------------


class EngineBase(ABC):
    """Optional base class providing standard engine infrastructure.

    Subclasses get:
    - Clock injection (self._clock, self._now())
    - Standard state_hash infrastructure
    - Default snapshot/restore via collection enumeration
    - Constructor validation pattern

    Usage:
        class MyEngine(EngineBase):
            def __init__(self, event_spine, clock=None):
                super().__init__(event_spine, clock)
                self._items = {}

            def _collections(self):
                return {"items": self._items}

            def state_hash(self):
                return self._hash_collections()
    """

    def __init__(self, event_spine: Any, clock: Clock | None = None) -> None:
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock or WallClock()

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    @abstractmethod
    def _collections(self) -> dict[str, dict[str, Any]]:
        """Return all internal collections as {name: dict}."""
        ...

    def _hash_collections(self) -> str:
        """Compute SHA-256 hash over all sorted collection keys."""
        parts: list[str] = []
        for name, collection in sorted(self._collections().items()):
            if isinstance(collection, dict):
                for k in sorted(collection):
                    v = collection[k]
                    # Try to get a status/disposition value for richer hashing
                    status = ""
                    for attr in ("status", "disposition", "verdict", "kind", "level"):
                        val = getattr(v, attr, None)
                        if val is not None:
                            status = f":{val.value}" if hasattr(val, "value") else f":{val}"
                            break
                    parts.append(f"{name}:{k}{status}")
            elif isinstance(collection, list):
                parts.append(f"{name}:len={len(collection)}")
        return sha256("|".join(parts).encode()).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        """Capture all collections as serializable state."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Default implementation using _hash_collections."""
        return self._hash_collections()

    @property
    def event_spine(self) -> Any:
        """Access the event spine."""
        return self._events


# ---------------------------------------------------------------------------
# Integration base class (optional mixin)
# ---------------------------------------------------------------------------


class IntegrationBase:
    """Optional base class providing standard integration infrastructure.

    Subclasses get:
    - Constructor validation for (engine, event_spine, memory_engine)
    - Clock access via engine
    - Standard _emit helper
    """

    def __init__(
        self,
        engine: Any,
        engine_type: type,
        event_spine: Any,
        memory_engine: Any,
    ) -> None:
        from mcoi_runtime.core.event_spine import EventSpineEngine
        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
        from mcoi_runtime.core.memory_mesh import MemoryMeshEngine

        if not isinstance(engine, engine_type):
            raise RuntimeCoreInvariantError(
                f"engine must be a {engine_type.__name__}"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")

        self._engine = engine
        self._events = event_spine
        self._memory = memory_engine
