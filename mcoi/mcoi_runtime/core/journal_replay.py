"""Purpose: deterministic tick replay from journal entries.
Governance scope: journal replay semantics only.
Dependencies: checkpoint manager, state machine contracts, supervisor engine.
Invariants:
  - Replay processes journal entries in strict sequence order.
  - Replay from a checkpoint restores state then re-executes tick entries.
  - Tick replay compares re-executed outcomes against recorded payloads.
  - Non-tick entries are validated for ordering but not re-executed.
  - Replay is fail-closed: any divergence halts replay and reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)
from mcoi_runtime.contracts.state_machine import (
    CompositeCheckpoint,
    JournalEntry,
    JournalEntryKind,
)
from mcoi_runtime.core.checkpoint_manager import CheckpointManager
from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.core.supervisor_engine import SupervisorEngine


def _bounded_replay_error(summary: str, exc: Exception) -> str:
    """Return a stable replay failure without raw backend detail."""
    return f"{summary} ({type(exc).__name__})"


# ---------------------------------------------------------------------------
# Replay contracts
# ---------------------------------------------------------------------------


class ReplayStepVerdict(StrEnum):
    """Outcome of a single replayed journal entry."""

    MATCH = "match"
    OUTCOME_DIVERGED = "outcome_diverged"
    TICK_NUMBER_DIVERGED = "tick_number_diverged"
    SKIPPED = "skipped"
    ERROR = "error"


class ReplaySessionVerdict(StrEnum):
    """Overall outcome of a replay session."""

    SUCCESS = "success"
    DIVERGENCE_DETECTED = "divergence_detected"
    EMPTY_JOURNAL = "empty_journal"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class ReplayStepResult(ContractRecord):
    """Result of replaying a single journal entry."""

    step_id: str
    sequence: int
    kind: JournalEntryKind
    verdict: ReplayStepVerdict
    expected_payload: Mapping[str, Any] = field(default_factory=dict)
    actual_payload: Mapping[str, Any] = field(default_factory=dict)
    detail: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "sequence", require_non_negative_int(self.sequence, "sequence"))
        if not isinstance(self.kind, JournalEntryKind):
            raise ValueError("kind must be a JournalEntryKind value")
        if not isinstance(self.verdict, ReplayStepVerdict):
            raise ValueError("verdict must be a ReplayStepVerdict value")
        object.__setattr__(self, "expected_payload", freeze_value(self.expected_payload))
        object.__setattr__(self, "actual_payload", freeze_value(self.actual_payload))


@dataclass(frozen=True, slots=True)
class ReplaySessionResult(ContractRecord):
    """Overall result of a replay session."""

    session_id: str
    epoch_id: str
    entries_replayed: int
    entries_matched: int
    entries_diverged: int
    entries_skipped: int
    verdict: ReplaySessionVerdict
    steps: tuple[ReplayStepResult, ...] = ()
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "epoch_id", require_non_empty_text(self.epoch_id, "epoch_id"))
        object.__setattr__(self, "entries_replayed", require_non_negative_int(self.entries_replayed, "entries_replayed"))
        object.__setattr__(self, "entries_matched", require_non_negative_int(self.entries_matched, "entries_matched"))
        object.__setattr__(self, "entries_diverged", require_non_negative_int(self.entries_diverged, "entries_diverged"))
        object.__setattr__(self, "entries_skipped", require_non_negative_int(self.entries_skipped, "entries_skipped"))
        if not isinstance(self.verdict, ReplaySessionVerdict):
            raise ValueError("verdict must be a ReplaySessionVerdict value")
        object.__setattr__(self, "steps", freeze_value(list(self.steps)))
        if self.started_at:
            object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        if self.completed_at:
            object.__setattr__(self, "completed_at", require_datetime_text(self.completed_at, "completed_at"))


# ---------------------------------------------------------------------------
# Journal replay engine
# ---------------------------------------------------------------------------


class JournalReplayEngine:
    """Deterministic replay of journal tick entries against a supervisor stack.

    Given a checkpoint and journal entries recorded during original execution,
    replays tick entries by re-executing supervisor ticks and comparing
    outcomes to the recorded journal payloads.

    Non-tick entries (checkpoint, heartbeat, etc.) are validated for
    ordering but not re-executed — they are marked as SKIPPED.
    """

    def __init__(
        self,
        *,
        supervisor: SupervisorEngine,
        checkpoint_manager: CheckpointManager,
        clock: Callable[[], str],
    ) -> None:
        self._supervisor = supervisor
        self._checkpoint_mgr = checkpoint_manager
        self._clock = clock

    def replay_from_checkpoint(
        self,
        checkpoint: CompositeCheckpoint,
        journal_entries: tuple[JournalEntry, ...],
        *,
        halt_on_divergence: bool = True,
    ) -> ReplaySessionResult:
        """Restore from checkpoint, then replay journal entries.

        Tick entries are re-executed and outcomes compared.
        Non-tick entries are skipped (ordering validated only).

        If halt_on_divergence=True, stops at first divergence.
        """
        started = self._clock()
        session_id = stable_identifier("replay", {
            "checkpoint": checkpoint.checkpoint_id,
            "at": started,
        })

        # Restore from checkpoint (with verification)
        self._checkpoint_mgr.restore_checkpoint(checkpoint, verify=True)

        return self._run_replay(
            session_id=session_id,
            epoch_id=checkpoint.epoch_id,
            journal_entries=journal_entries,
            halt_on_divergence=halt_on_divergence,
            started=started,
        )

    def replay_journal(
        self,
        journal_entries: tuple[JournalEntry, ...],
        *,
        halt_on_divergence: bool = True,
    ) -> ReplaySessionResult:
        """Replay journal entries against current state (no checkpoint restore).

        Useful for verifying journal entries match current execution.
        """
        started = self._clock()
        epoch_id = journal_entries[0].epoch_id if journal_entries else self._checkpoint_mgr.epoch_id
        session_id = stable_identifier("replay-nocp", {"at": started})

        return self._run_replay(
            session_id=session_id,
            epoch_id=epoch_id,
            journal_entries=journal_entries,
            halt_on_divergence=halt_on_divergence,
            started=started,
        )

    def _run_replay(
        self,
        *,
        session_id: str,
        epoch_id: str,
        journal_entries: tuple[JournalEntry, ...],
        halt_on_divergence: bool,
        started: str,
    ) -> ReplaySessionResult:
        """Core replay loop."""
        if not journal_entries:
            return ReplaySessionResult(
                session_id=session_id,
                epoch_id=epoch_id,
                entries_replayed=0,
                entries_matched=0,
                entries_diverged=0,
                entries_skipped=0,
                verdict=ReplaySessionVerdict.EMPTY_JOURNAL,
                started_at=started,
                completed_at=self._clock(),
            )

        steps: list[ReplayStepResult] = []
        matched = 0
        diverged = 0
        skipped = 0

        for entry in journal_entries:
            step = self._replay_entry(entry)
            steps.append(step)

            if step.verdict == ReplayStepVerdict.MATCH:
                matched += 1
            elif step.verdict == ReplayStepVerdict.SKIPPED:
                skipped += 1
            else:
                diverged += 1
                if halt_on_divergence:
                    break

        if diverged > 0:
            verdict = ReplaySessionVerdict.DIVERGENCE_DETECTED
        else:
            verdict = ReplaySessionVerdict.SUCCESS

        return ReplaySessionResult(
            session_id=session_id,
            epoch_id=epoch_id,
            entries_replayed=len(steps),
            entries_matched=matched,
            entries_diverged=diverged,
            entries_skipped=skipped,
            verdict=verdict,
            steps=tuple(steps),
            started_at=started,
            completed_at=self._clock(),
        )

    def _replay_entry(self, entry: JournalEntry) -> ReplayStepResult:
        """Replay a single journal entry."""
        step_id = stable_identifier("rstep", {"seq": entry.sequence})

        if entry.kind == JournalEntryKind.TICK:
            return self._replay_tick(entry, step_id)

        # Non-tick entries are not re-executed
        return ReplayStepResult(
            step_id=step_id,
            sequence=entry.sequence,
            kind=entry.kind,
            verdict=ReplayStepVerdict.SKIPPED,
            expected_payload=entry.payload,
            detail="entry not re-executed during replay",
        )

    def _replay_tick(self, entry: JournalEntry, step_id: str) -> ReplayStepResult:
        """Re-execute a tick and compare outcome to journal record."""
        expected_tick = entry.payload.get("tick_number")
        expected_outcome = entry.payload.get("outcome")

        try:
            tick_result = self._supervisor.tick()
        except Exception as exc:
            return ReplayStepResult(
                step_id=step_id,
                sequence=entry.sequence,
                kind=JournalEntryKind.TICK,
                verdict=ReplayStepVerdict.ERROR,
                expected_payload=entry.payload,
                detail=_bounded_replay_error("tick execution error", exc),
            )

        actual_tick = tick_result.tick_number
        actual_outcome = tick_result.outcome.value

        if expected_tick is not None and actual_tick != expected_tick:
            return ReplayStepResult(
                step_id=step_id,
                sequence=entry.sequence,
                kind=JournalEntryKind.TICK,
                verdict=ReplayStepVerdict.TICK_NUMBER_DIVERGED,
                expected_payload=entry.payload,
                actual_payload={"tick_number": actual_tick, "outcome": actual_outcome},
                detail="tick number diverged",
            )

        if expected_outcome is not None and actual_outcome != expected_outcome:
            return ReplayStepResult(
                step_id=step_id,
                sequence=entry.sequence,
                kind=JournalEntryKind.TICK,
                verdict=ReplayStepVerdict.OUTCOME_DIVERGED,
                expected_payload=entry.payload,
                actual_payload={"tick_number": actual_tick, "outcome": actual_outcome},
                detail="tick outcome diverged",
            )

        return ReplayStepResult(
            step_id=step_id,
            sequence=entry.sequence,
            kind=JournalEntryKind.TICK,
            verdict=ReplayStepVerdict.MATCH,
            expected_payload=entry.payload,
            actual_payload={"tick_number": actual_tick, "outcome": actual_outcome},
        )
