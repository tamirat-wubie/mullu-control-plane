"""Phase 207D — Execution Replay Contracts.

Purpose: Deterministic re-execution of governed operations.
    Records execution traces that can be replayed for debugging,
    auditing, and regression testing.
Governance scope: replay recording and execution only.
Dependencies: none (pure data structures).
Invariants:
  - Replay traces are immutable once recorded.
  - Replay produces identical results for identical inputs.
  - Trace recording adds no observable side effects.
  - Traces are bounded (max entries per trace).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Callable
import json


def _classify_replay_exception(exc: Exception) -> str:
    """Return a bounded replay failure reason."""
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"replay operation timeout ({exc_type})"
    return f"replay operation error ({exc_type})"


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    """Single frame in a replay trace."""

    frame_id: str
    sequence: int
    operation: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    duration_ms: float
    frame_hash: str


@dataclass(frozen=True, slots=True)
class ReplayTrace:
    """Complete replay trace for an execution."""

    trace_id: str
    frames: tuple[ReplayFrame, ...]
    total_duration_ms: float
    trace_hash: str
    recorded_at: str


class ReplayRecorder:
    """Records execution traces for replay."""

    def __init__(self, *, clock: Callable[[], str], max_frames: int = 1000) -> None:
        self._clock = clock
        self._max_frames = max_frames
        self._traces: dict[str, list[ReplayFrame]] = {}
        self._completed: list[ReplayTrace] = []
        self._frame_counter = 0

    def start_trace(self, trace_id: str) -> None:
        """Start recording a new trace."""
        if trace_id in self._traces:
            raise ValueError("trace already started")
        self._traces[trace_id] = []

    def record_frame(
        self,
        trace_id: str,
        operation: str,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        duration_ms: float = 0.0,
    ) -> ReplayFrame:
        """Record a single frame in a trace."""
        frames = self._traces.get(trace_id)
        if frames is None:
            raise ValueError("trace not started")
        if len(frames) >= self._max_frames:
            raise ValueError("trace exceeded max frames")

        self._frame_counter += 1
        content = json.dumps(
            {"op": operation, "in": input_data, "out": output_data},
            sort_keys=True, default=str,
        ).encode()
        frame_hash = sha256(content).hexdigest()

        frame = ReplayFrame(
            frame_id=f"frame-{self._frame_counter}",
            sequence=len(frames) + 1,
            operation=operation,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
            frame_hash=frame_hash,
        )
        frames.append(frame)
        return frame

    def complete_trace(self, trace_id: str) -> ReplayTrace:
        """Finalize a trace — makes it immutable."""
        frames = self._traces.pop(trace_id, None)
        if frames is None:
            raise ValueError("trace not found")

        total_duration = sum(f.duration_ms for f in frames)
        all_hashes = "".join(f.frame_hash for f in frames)
        trace_hash = sha256(all_hashes.encode()).hexdigest()

        trace = ReplayTrace(
            trace_id=trace_id,
            frames=tuple(frames),
            total_duration_ms=total_duration,
            trace_hash=trace_hash,
            recorded_at=self._clock(),
        )
        self._completed.append(trace)
        return trace

    def get_trace(self, trace_id: str) -> ReplayTrace | None:
        """Get a completed trace by ID."""
        for trace in self._completed:
            if trace.trace_id == trace_id:
                return trace
        return None

    def list_traces(self, limit: int = 50) -> list[ReplayTrace]:
        return self._completed[-limit:]

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def active_count(self) -> int:
        return len(self._traces)

    def summary(self) -> dict[str, Any]:
        return {
            "completed": self.completed_count,
            "active": self.active_count,
            "total_frames": self._frame_counter,
        }


class ReplayExecutor:
    """Replays a trace by calling operations in sequence.

    Compares outputs against recorded outputs for verification.
    """

    def __init__(self, *, operations: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self._operations = operations

    def replay(self, trace: ReplayTrace) -> list[dict[str, Any]]:
        """Replay a trace. Returns comparison results for each frame."""
        results: list[dict[str, Any]] = []
        for frame in trace.frames:
            op_fn = self._operations.get(frame.operation)
            if op_fn is None:
                results.append({
                    "frame_id": frame.frame_id,
                    "matched": False,
                    "reason": "unknown operation",
                })
                continue

            try:
                actual_output = op_fn(frame.input_data)
                expected_hash = frame.frame_hash
                actual_hash = sha256(
                    json.dumps(
                        {"op": frame.operation, "in": frame.input_data, "out": actual_output},
                        sort_keys=True, default=str,
                    ).encode()
                ).hexdigest()

                results.append({
                    "frame_id": frame.frame_id,
                    "matched": actual_hash == expected_hash,
                    "expected_hash": expected_hash[:16],
                    "actual_hash": actual_hash[:16],
                })
            except Exception as exc:
                results.append({
                    "frame_id": frame.frame_id,
                    "matched": False,
                    "reason": _classify_replay_exception(exc),
                })

        return results

    def verify(self, trace: ReplayTrace) -> tuple[bool, int, int]:
        """Verify a trace. Returns (all_matched, matched_count, total_count)."""
        results = self.replay(trace)
        matched = sum(1 for r in results if r.get("matched"))
        return all(r.get("matched") for r in results), matched, len(results)
