"""Purpose: deterministic replay harness for completed execution traces.

Governance scope: reconstructs recorded decision paths from ReplayTrace frames
using local deterministic operations only, then emits a bounded comparison
report for audit and incident response.
Dependencies: execution replay contracts, invariant helpers, and deterministic
JSON hashing.
Invariants: unknown operations fail closed; frame ordering is verified before
execution; report hashes are deterministic; live external effects are excluded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Callable, Literal

from .execution_replay import ReplayFrame, ReplayTrace
from .invariants import ensure_non_empty_text, stable_identifier

ReplayReasonCode = Literal[
    "replay_match",
    "empty_trace",
    "frame_sequence_gap",
    "unknown_operation",
    "output_hash_mismatch",
    "operation_error",
]


@dataclass(frozen=True, slots=True)
class ReplayFrameCheck:
    """Per-frame deterministic replay comparison."""

    frame_id: str
    sequence: int
    operation: str
    matched: bool
    expected_hash: str
    actual_hash: str = ""
    reason_code: ReplayReasonCode = "replay_match"

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "sequence": self.sequence,
            "operation": self.operation,
            "matched": self.matched,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True, slots=True)
class ReplayDeterminismReport:
    """Audit report for one deterministic replay attempt."""

    replay_id: str
    trace_id: str
    trace_hash: str
    deterministic: bool
    checked_frames: int
    matched_frames: int
    mismatched_frames: int
    reason_codes: tuple[ReplayReasonCode, ...]
    frame_checks: tuple[ReplayFrameCheck, ...]
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "replay_id", ensure_non_empty_text("replay_id", self.replay_id))
        object.__setattr__(self, "trace_id", ensure_non_empty_text("trace_id", self.trace_id))
        object.__setattr__(self, "trace_hash", ensure_non_empty_text("trace_hash", self.trace_hash))
        if not self.report_hash:
            object.__setattr__(self, "report_hash", _report_hash(self.to_dict(include_report_hash=False)))

    def to_dict(self, *, include_report_hash: bool = True) -> dict[str, Any]:
        document = {
            "replay_id": self.replay_id,
            "trace_id": self.trace_id,
            "trace_hash": self.trace_hash,
            "deterministic": self.deterministic,
            "checked_frames": self.checked_frames,
            "matched_frames": self.matched_frames,
            "mismatched_frames": self.mismatched_frames,
            "reason_codes": list(self.reason_codes),
            "frame_checks": [check.to_dict() for check in self.frame_checks],
            "metadata": dict(self.metadata),
        }
        if include_report_hash:
            document["report_hash"] = self.report_hash
        return document


class ReplayDeterminismHarness:
    """Replay completed traces with deterministic local operation handlers."""

    def __init__(self, operations: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self._operations = dict(operations)

    def replay(self, trace: ReplayTrace, *, replay_id: str | None = None) -> ReplayDeterminismReport:
        """Replay a trace and emit a deterministic comparison report."""
        checked_frames: list[ReplayFrameCheck] = []
        trace_reason_codes: list[ReplayReasonCode] = []

        if not trace.frames:
            trace_reason_codes.append("empty_trace")

        expected_sequence = 1
        for frame in trace.frames:
            if frame.sequence != expected_sequence:
                trace_reason_codes.append("frame_sequence_gap")
                checked_frames.append(_frame_check(frame, matched=False, reason_code="frame_sequence_gap"))
                expected_sequence = frame.sequence + 1
                continue
            expected_sequence += 1
            checked_frames.append(self._replay_frame(frame))

        for check in checked_frames:
            if check.reason_code != "replay_match" and check.reason_code not in trace_reason_codes:
                trace_reason_codes.append(check.reason_code)

        matched_frames = sum(1 for check in checked_frames if check.matched)
        mismatched_frames = len(checked_frames) - matched_frames
        deterministic = not trace_reason_codes and mismatched_frames == 0
        report = ReplayDeterminismReport(
            replay_id=replay_id or stable_identifier("replay-harness", {"trace_id": trace.trace_id, "trace_hash": trace.trace_hash}),
            trace_id=trace.trace_id,
            trace_hash=trace.trace_hash,
            deterministic=deterministic,
            checked_frames=len(checked_frames),
            matched_frames=matched_frames,
            mismatched_frames=mismatched_frames,
            reason_codes=tuple(trace_reason_codes),
            frame_checks=tuple(checked_frames),
        )
        return report

    def _replay_frame(self, frame: ReplayFrame) -> ReplayFrameCheck:
        operation = self._operations.get(frame.operation)
        if operation is None:
            return _frame_check(frame, matched=False, reason_code="unknown_operation")
        try:
            actual_output = operation(frame.input_data)
        except Exception:
            return _frame_check(frame, matched=False, reason_code="operation_error")
        actual_hash = _frame_hash(frame.operation, frame.input_data, actual_output)
        if actual_hash != frame.frame_hash:
            return _frame_check(
                frame,
                matched=False,
                reason_code="output_hash_mismatch",
                actual_hash=actual_hash,
            )
        return _frame_check(frame, matched=True, reason_code="replay_match", actual_hash=actual_hash)


def _frame_check(
    frame: ReplayFrame,
    *,
    matched: bool,
    reason_code: ReplayReasonCode,
    actual_hash: str = "",
) -> ReplayFrameCheck:
    return ReplayFrameCheck(
        frame_id=frame.frame_id,
        sequence=frame.sequence,
        operation=frame.operation,
        matched=matched,
        expected_hash=frame.frame_hash,
        actual_hash=actual_hash,
        reason_code=reason_code,
    )


def _frame_hash(operation: str, input_data: dict[str, Any], output_data: dict[str, Any]) -> str:
    content = json.dumps(
        {"op": operation, "in": input_data, "out": output_data},
        sort_keys=True,
        default=str,
    ).encode()
    return sha256(content).hexdigest()


def _report_hash(document: dict[str, Any]) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return f"replay-report-{sha256(encoded.encode('utf-8')).hexdigest()[:16]}"
