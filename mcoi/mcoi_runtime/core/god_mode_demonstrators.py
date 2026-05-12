"""Purpose: god-mode-gated demonstrator privileged operations.

Governance scope: a small set of intentionally narrow privileged operations
wired through the `@requires_god_ticket` decorator. These exist so the
god-mode subsystem has a working end-to-end example — they are NOT a
general entry point for bypassing platform invariants.

Each demonstrator targets in-memory subsystem state where the blast is
local and easily observable. Subsystems whose state is durable, distributed,
or cross-tenant are intentionally left without demonstrators here; their
god capabilities remain DORMANT until a domain owner wires their own
gated handler.

Dependencies: god_mode_engine (decorator), execution_replay (ReplayRecorder).

Invariants:
  - Every demonstrator is annotated with `@requires_god_ticket(module, name)`.
  - The (module, name) on the decorator must match a registered god capability.
  - Demonstrators accept `ticket_id=` as a keyword argument.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.core.god_mode_engine import requires_god_ticket


@requires_god_ticket(module="replay", name="mutate_recorder")
def truncate_replay_trace(
    *,
    recorder: Any,
    trace_id: str,
    keep_frames: int,
) -> dict[str, Any]:
    """Truncate an in-progress replay trace to ``keep_frames`` frames.

    Bypasses the replay-immutability guarantee for the in-memory recorder.
    Only affects active traces (not completed/finalized ones — those are
    durable and out of scope for this demonstrator).

    Returns a summary dict describing what was kept and what was dropped.
    """
    if keep_frames < 0:
        raise ValueError("keep_frames must be >= 0")
    frames = getattr(recorder, "_traces", {}).get(trace_id)
    if frames is None:
        raise ValueError(f"trace {trace_id!r} not active")
    original_len = len(frames)
    if keep_frames >= original_len:
        return {
            "trace_id": trace_id,
            "original_frames": original_len,
            "kept_frames": original_len,
            "dropped_frames": 0,
        }
    dropped = original_len - keep_frames
    del frames[keep_frames:]
    return {
        "trace_id": trace_id,
        "original_frames": original_len,
        "kept_frames": keep_frames,
        "dropped_frames": dropped,
    }


__all__ = ["truncate_replay_trace"]
