"""
Substrate path metrics — telemetry for the v3.13.1 → v4.0.0 → v4.0.x soak.

Tracks lookups against the two Mfidel implementations that coexist during the
convergence window:

  - LEGACY_MATRIX_PATH   : mcoi_runtime/core/mfidel_matrix.py   (272-dim dense)
  - CANONICAL_GRID_PATH  : mcoi_runtime/substrate/mfidel/grid.py (269 atoms, 3 known-empty)

Per-request mixing is surfaced as a counter: a request that touches both paths
in the same flow is the exact signal that gates Option 1b convergence safety.
If the convergence GO/NO-GO review at W4 sees zero mixed flows AND zero
legacy-only flows that depend on synthesized col-8 fidels, we proceed.

This module owns its own correlation ContextVar to avoid a substrate→core
dependency. Callers who already manage correlation (e.g. the CorrelationManager
in core/request_correlation.py) bind the active request id via
``bind_correlation(cid)``.

No behavior change to either grid. Telemetry only.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

LEGACY_MATRIX_PATH = "legacy_matrix"
CANONICAL_GRID_PATH = "canonical_grid"

_VALID_PATHS = frozenset({LEGACY_MATRIX_PATH, CANONICAL_GRID_PATH})

_active_correlation: ContextVar[str] = ContextVar("substrate_correlation_id", default="")


def bind_correlation(correlation_id: str) -> None:
    """Bind the active request's correlation id for the current execution context.

    Called by the request entry point before any Mfidel lookup happens. The
    value flows through asyncio tasks naturally because it is a ContextVar.
    """
    _active_correlation.set(correlation_id or "")


def current_correlation() -> str:
    return _active_correlation.get("")


@dataclass
class _PerRequestPaths:
    """Set of grid paths touched within a single request flow."""

    paths: set[str] = field(default_factory=set)
    legacy_lookups: int = 0
    canonical_lookups: int = 0


@dataclass
class SubstratePathSnapshot:
    """Read-only snapshot of substrate path counters."""

    legacy_lookups_total: int
    canonical_lookups_total: int
    requests_legacy_only: int
    requests_canonical_only: int
    requests_mixed: int
    requests_closed_total: int
    open_requests: int
    mode_distribution: dict[str, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "legacy_lookups_total": self.legacy_lookups_total,
            "canonical_lookups_total": self.canonical_lookups_total,
            "requests_legacy_only": self.requests_legacy_only,
            "requests_canonical_only": self.requests_canonical_only,
            "requests_mixed": self.requests_mixed,
            "requests_closed_total": self.requests_closed_total,
            "open_requests": self.open_requests,
            "mode_distribution": dict(self.mode_distribution),
        }


class SubstratePathRegistry:
    """Singleton-style registry. Thread-safe via RLock.

    Counters are monotonically non-decreasing (matches existing telemetry
    invariants in core/telemetry.py).
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._legacy_lookups_total = 0
        self._canonical_lookups_total = 0
        self._requests_legacy_only = 0
        self._requests_canonical_only = 0
        self._requests_mixed = 0
        self._requests_closed_total = 0
        self._per_request: dict[str, _PerRequestPaths] = {}
        self._mode_distribution: dict[str, int] = {}

    def record_lookup(self, path: str) -> None:
        """Increment lookup counters for the active correlation context.

        Lookups outside any correlation (cid == "") are still counted in the
        global totals, but contribute no per-request mixing data. This keeps
        background tasks (warmup, tests) from polluting per-request stats.
        """
        if path not in _VALID_PATHS:
            raise ValueError(f"unknown substrate path: {path!r}")

        cid = current_correlation()
        with self._lock:
            if path == LEGACY_MATRIX_PATH:
                self._legacy_lookups_total += 1
            else:
                self._canonical_lookups_total += 1

            if not cid:
                return

            entry = self._per_request.get(cid)
            if entry is None:
                entry = _PerRequestPaths()
                self._per_request[cid] = entry
            entry.paths.add(path)
            if path == LEGACY_MATRIX_PATH:
                entry.legacy_lookups += 1
            else:
                entry.canonical_lookups += 1

    def close_request(self, correlation_id: str) -> str:
        """Finalize per-request bucket. Returns one of:
        ``legacy_only`` | ``canonical_only`` | ``mixed`` | ``none``.
        """
        if not correlation_id:
            return "none"
        with self._lock:
            entry = self._per_request.pop(correlation_id, None)
            if entry is None or not entry.paths:
                return "none"

            self._requests_closed_total += 1
            if entry.paths == {LEGACY_MATRIX_PATH}:
                self._requests_legacy_only += 1
                return "legacy_only"
            if entry.paths == {CANONICAL_GRID_PATH}:
                self._requests_canonical_only += 1
                return "canonical_only"
            self._requests_mixed += 1
            return "mixed"

    def record_mode(self, mode: str) -> None:
        """Stamp the active MUSIA_MODE distribution. Currently ``unset`` for
        all v3.13.1/v4.0.0 traffic — the flag is reserved for v4.1.0.
        """
        key = mode or "unset"
        with self._lock:
            self._mode_distribution[key] = self._mode_distribution.get(key, 0) + 1

    def snapshot(self) -> SubstratePathSnapshot:
        with self._lock:
            return SubstratePathSnapshot(
                legacy_lookups_total=self._legacy_lookups_total,
                canonical_lookups_total=self._canonical_lookups_total,
                requests_legacy_only=self._requests_legacy_only,
                requests_canonical_only=self._requests_canonical_only,
                requests_mixed=self._requests_mixed,
                requests_closed_total=self._requests_closed_total,
                open_requests=len(self._per_request),
                mode_distribution=dict(self._mode_distribution),
            )

    def reset(self) -> None:
        """Test-only. Resets all counters."""
        with self._lock:
            self._legacy_lookups_total = 0
            self._canonical_lookups_total = 0
            self._requests_legacy_only = 0
            self._requests_canonical_only = 0
            self._requests_mixed = 0
            self._requests_closed_total = 0
            self._per_request.clear()
            self._mode_distribution.clear()


REGISTRY = SubstratePathRegistry()


def export_to_prometheus(exporter: Any) -> None:
    """Push the current snapshot into a PrometheusExporter instance.

    The exporter is duck-typed (has ``register_counter``, ``register_gauge``,
    ``inc_counter``, ``set_gauge``) so this module does not have to import the
    concrete class. Tests can pass a fake.

    Counters are not literally incremented in Prometheus terms; the exporter is
    given the absolute total via a special pattern (set the counter to the
    accumulated value by computing the delta and calling inc_counter with that
    delta). For simplicity here, we use gauges for cumulative totals — this is
    safe for soak observation; v4.1+ will move to true counters with delta
    tracking.
    """
    snap = REGISTRY.snapshot()
    exporter.set_gauge(
        "substrate_mfidel_lookups_total",
        snap.legacy_lookups_total,
        path=LEGACY_MATRIX_PATH,
    )
    exporter.set_gauge(
        "substrate_mfidel_lookups_total",
        snap.canonical_lookups_total,
        path=CANONICAL_GRID_PATH,
    )
    exporter.set_gauge(
        "substrate_requests_total",
        snap.requests_legacy_only,
        bucket="legacy_only",
    )
    exporter.set_gauge(
        "substrate_requests_total",
        snap.requests_canonical_only,
        bucket="canonical_only",
    )
    exporter.set_gauge(
        "substrate_requests_total",
        snap.requests_mixed,
        bucket="mixed",
    )
    exporter.set_gauge("substrate_requests_open", snap.open_requests)
    for mode, count in snap.mode_distribution.items():
        exporter.set_gauge("substrate_musia_mode_total", count, mode=mode)
