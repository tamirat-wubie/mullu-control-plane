"""Purpose: verify replay determinism harness reports.

Governance scope: completed ReplayTrace reconstruction, per-frame comparison,
bounded reason codes, and deterministic report hashing.
Dependencies: execution replay recorder and replay determinism harness.
Invariants: unknown operations fail closed; mismatches are explicit; report
hashes are stable for identical traces and operations.
"""

from __future__ import annotations

from dataclasses import replace

from mcoi_runtime.core.execution_replay import ReplayRecorder
from mcoi_runtime.core.replay_determinism_harness import ReplayDeterminismHarness


def _clock() -> str:
    return "2026-04-25T12:00:00+00:00"


def _trace():
    recorder = ReplayRecorder(clock=_clock)
    recorder.start_trace("trace-replay-1")
    recorder.record_frame("trace-replay-1", "add", {"a": 1, "b": 2}, {"result": 3})
    recorder.record_frame("trace-replay-1", "echo", {"value": "ok"}, {"value": "ok"})
    return recorder.complete_trace("trace-replay-1")


def test_harness_reports_deterministic_match() -> None:
    trace = _trace()
    harness = ReplayDeterminismHarness(
        {
            "add": lambda payload: {"result": payload["a"] + payload["b"]},
            "echo": lambda payload: {"value": payload["value"]},
        }
    )

    report = harness.replay(trace)

    assert report.deterministic is True
    assert report.checked_frames == 2
    assert report.matched_frames == 2
    assert report.reason_codes == ()
    assert report.report_hash.startswith("replay-report-")


def test_harness_report_hash_is_deterministic() -> None:
    trace = _trace()
    harness = ReplayDeterminismHarness(
        {
            "add": lambda payload: {"result": payload["a"] + payload["b"]},
            "echo": lambda payload: {"value": payload["value"]},
        }
    )

    first = harness.replay(trace, replay_id="replay-fixed")
    second = harness.replay(trace, replay_id="replay-fixed")

    assert first.report_hash == second.report_hash
    assert first.to_dict()["report_hash"] == second.to_dict()["report_hash"]
    assert first.to_dict(include_report_hash=False)["trace_id"] == "trace-replay-1"


def test_harness_reports_output_hash_mismatch() -> None:
    trace = _trace()
    harness = ReplayDeterminismHarness(
        {
            "add": lambda _payload: {"result": 999},
            "echo": lambda payload: {"value": payload["value"]},
        }
    )

    report = harness.replay(trace)

    assert report.deterministic is False
    assert report.mismatched_frames == 1
    assert report.reason_codes == ("output_hash_mismatch",)
    assert report.frame_checks[0].reason_code == "output_hash_mismatch"


def test_harness_reports_unknown_operation_without_leaking_name_in_reason() -> None:
    trace = _trace()
    harness = ReplayDeterminismHarness({"add": lambda payload: {"result": payload["a"] + payload["b"]}})

    report = harness.replay(trace)

    assert report.deterministic is False
    assert report.reason_codes == ("unknown_operation",)
    assert report.frame_checks[1].operation == "echo"
    assert report.frame_checks[1].reason_code == "unknown_operation"


def test_harness_reports_sequence_gap_before_replay() -> None:
    trace = _trace()
    broken_frame = replace(trace.frames[1], sequence=4)
    broken_trace = replace(trace, frames=(trace.frames[0], broken_frame))
    harness = ReplayDeterminismHarness(
        {
            "add": lambda payload: {"result": payload["a"] + payload["b"]},
            "echo": lambda payload: {"value": payload["value"]},
        }
    )

    report = harness.replay(broken_trace)

    assert report.deterministic is False
    assert "frame_sequence_gap" in report.reason_codes
    assert report.checked_frames == 2
    assert report.matched_frames == 1


def test_harness_reports_operation_errors_bounded() -> None:
    trace = _trace()
    harness = ReplayDeterminismHarness(
        {
            "add": lambda _payload: (_ for _ in ()).throw(RuntimeError("secret")),
            "echo": lambda payload: {"value": payload["value"]},
        }
    )

    report = harness.replay(trace)

    assert report.deterministic is False
    assert report.reason_codes == ("operation_error",)
    assert "secret" not in report.frame_checks[0].reason_code
