"""Purpose: composite checkpoint creation and restoration across all subsystems.
Governance scope: checkpoint orchestration only.
Dependencies: state machine contracts, supervisor/event/obligation engines.
Invariants:
  - Composite checkpoints capture all subsystem states atomically.
  - Restoration is all-or-nothing — partial restore triggers rollback.
  - State hashes are verified post-restore to detect divergence.
  - Journal entries are append-only and totally ordered within an epoch.
  - Journal validation detects gaps, epoch mismatches, and ordering violations.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.state_machine import (
    CheckpointScope,
    CompositeCheckpoint,
    JournalEntry,
    JournalEntryKind,
    JournalValidationResult,
    JournalValidationVerdict,
    RestoreVerdict,
    RestoreVerification,
    SubsystemSnapshot,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine
from mcoi_runtime.core.supervisor_engine import SupervisorEngine


class CheckpointManager:
    """Orchestrates composite checkpoint creation and restoration.

    Coordinates snapshot/restore across supervisor, event spine,
    and obligation runtime to maintain cross-subsystem consistency.

    Hardened semantics:
    - Restore verifies post-restore hashes against checkpoint hashes.
    - On hash mismatch, pre-restore state is rolled back atomically.
    - Journal validation detects sequence gaps and epoch mismatches.
    """

    def __init__(
        self,
        *,
        supervisor: SupervisorEngine,
        spine: EventSpineEngine,
        obligation_engine: ObligationRuntimeEngine,
        clock: Callable[[], str],
        epoch_id: str = "epoch-1",
    ) -> None:
        self._supervisor = supervisor
        self._spine = spine
        self._obligation_engine = obligation_engine
        self._clock = clock
        self._epoch_id = epoch_id
        self._journal: list[JournalEntry] = []
        self._checkpoints: list[CompositeCheckpoint] = []
        self._verifications: list[RestoreVerification] = []
        self._sequence = 0

    # --- Journal ---

    def append_journal(
        self,
        kind: JournalEntryKind,
        subject_id: str,
        payload: Mapping[str, Any],
    ) -> JournalEntry:
        """Append a journal entry. Returns the entry."""
        now = self._clock()
        entry_id = stable_identifier("journal", {
            "epoch": self._epoch_id,
            "seq": self._sequence,
        })
        entry = JournalEntry(
            entry_id=entry_id,
            epoch_id=self._epoch_id,
            sequence=self._sequence,
            kind=kind,
            subject_id=subject_id,
            payload=payload,
            recorded_at=now,
        )
        self._journal.append(entry)
        self._sequence += 1
        return entry

    @property
    def journal_length(self) -> int:
        return len(self._journal)

    def journal_since(self, sequence: int) -> tuple[JournalEntry, ...]:
        """Return all journal entries with sequence >= the given value."""
        return tuple(e for e in self._journal if e.sequence >= sequence)

    def journal_entries(self) -> tuple[JournalEntry, ...]:
        """Return all journal entries in order."""
        return tuple(self._journal)

    def validate_journal(self) -> JournalValidationResult:
        """Validate journal integrity: monotonic sequence, epoch coherence, gap-freedom.

        Returns a JournalValidationResult with the verdict and any gap positions.
        """
        now = self._clock()
        vid = stable_identifier("jval", {"epoch": self._epoch_id, "at": now})

        if not self._journal:
            return JournalValidationResult(
                validation_id=vid,
                epoch_id=self._epoch_id,
                entry_count=0,
                first_sequence=0,
                last_sequence=0,
                verdict=JournalValidationVerdict.EMPTY_JOURNAL,
                detail="journal contains no entries",
            )

        first_seq = self._journal[0].sequence
        last_seq = self._journal[-1].sequence

        # Check epoch coherence
        mismatched = [e for e in self._journal if e.epoch_id != self._epoch_id]
        if mismatched:
            return JournalValidationResult(
                validation_id=vid,
                epoch_id=self._epoch_id,
                entry_count=len(self._journal),
                first_sequence=first_seq,
                last_sequence=last_seq,
                verdict=JournalValidationVerdict.EPOCH_MISMATCH,
                detail="journal epoch mismatch detected",
            )

        # Check monotonic ordering
        for i in range(1, len(self._journal)):
            if self._journal[i].sequence <= self._journal[i - 1].sequence:
                return JournalValidationResult(
                    validation_id=vid,
                    epoch_id=self._epoch_id,
                    entry_count=len(self._journal),
                    first_sequence=first_seq,
                    last_sequence=last_seq,
                    verdict=JournalValidationVerdict.ORDERING_VIOLATION,
                    detail="journal ordering violation detected",
                )

        # Check for gaps (consecutive sequence numbers with no gaps)
        gaps: list[int] = []
        for i in range(1, len(self._journal)):
            expected = self._journal[i - 1].sequence + 1
            actual = self._journal[i].sequence
            if actual != expected:
                gaps.append(expected)

        if gaps:
            return JournalValidationResult(
                validation_id=vid,
                epoch_id=self._epoch_id,
                entry_count=len(self._journal),
                first_sequence=first_seq,
                last_sequence=last_seq,
                verdict=JournalValidationVerdict.SEQUENCE_GAP,
                gap_positions=tuple(gaps),
                detail="journal sequence gap detected",
            )

        return JournalValidationResult(
            validation_id=vid,
            epoch_id=self._epoch_id,
            entry_count=len(self._journal),
            first_sequence=first_seq,
            last_sequence=last_seq,
            verdict=JournalValidationVerdict.VALID,
        )

    # --- Composite checkpoint ---

    def create_checkpoint(self) -> CompositeCheckpoint:
        """Create a composite checkpoint spanning all subsystems."""
        now = self._clock()
        tick_number = self._supervisor.tick_number

        # Capture subsystem snapshots
        spine_snap_data = self._spine.snapshot()
        obl_snap_data = self._obligation_engine.snapshot()

        spine_snapshot = SubsystemSnapshot(
            snapshot_id=stable_identifier("snap-spine", {"tick": tick_number}),
            scope=CheckpointScope.EVENT_SPINE,
            state_hash=spine_snap_data["state_hash"],
            record_count=self._spine.event_count,
            captured_at=now,
            payload=spine_snap_data,
        )

        obl_snapshot = SubsystemSnapshot(
            snapshot_id=stable_identifier("snap-obl", {"tick": tick_number}),
            scope=CheckpointScope.OBLIGATION_RUNTIME,
            state_hash=obl_snap_data["state_hash"],
            record_count=self._obligation_engine.obligation_count,
            captured_at=now,
            payload=obl_snap_data,
        )

        supervisor_snapshot = SubsystemSnapshot(
            snapshot_id=stable_identifier("snap-sup", {"tick": tick_number}),
            scope=CheckpointScope.SUPERVISOR,
            state_hash=self._supervisor_state_hash(),
            record_count=tick_number,
            captured_at=now,
            payload={
                "tick_number": tick_number,
                "phase": self._supervisor.phase.value,
                "processed_event_ids": sorted(self._supervisor.processed_event_ids),
                "consecutive_errors": self._supervisor._consecutive_errors,
                "consecutive_idle_ticks": self._supervisor._consecutive_idle_ticks,
                "halted": self._supervisor.is_halted,
            },
        )

        # Compute composite hash
        composite_hash = self._compute_composite_hash(
            spine_snap_data["state_hash"],
            obl_snap_data["state_hash"],
            self._supervisor_state_hash(),
        )

        checkpoint = CompositeCheckpoint(
            checkpoint_id=stable_identifier("composite-cp", {
                "epoch": self._epoch_id,
                "tick": tick_number,
            }),
            epoch_id=self._epoch_id,
            tick_number=tick_number,
            snapshots=(supervisor_snapshot, spine_snapshot, obl_snapshot),
            journal_sequence=self._sequence,
            composite_hash=composite_hash,
            created_at=now,
        )
        self._checkpoints.append(checkpoint)

        # Journal the checkpoint
        self.append_journal(
            JournalEntryKind.CHECKPOINT,
            subject_id=checkpoint.checkpoint_id,
            payload={"tick": tick_number, "composite_hash": composite_hash},
        )

        return checkpoint

    def restore_checkpoint(
        self,
        checkpoint: CompositeCheckpoint,
        *,
        verify: bool = True,
    ) -> RestoreVerification | None:
        """Restore all subsystems from a composite checkpoint.

        If verify=True (default), post-restore hashes are compared against
        the checkpoint's recorded hashes. On mismatch, pre-restore state
        is rolled back and RuntimeCoreInvariantError is raised.

        Returns the RestoreVerification record if verify=True, else None.

        Raises RuntimeCoreInvariantError if any snapshot is missing or
        if hash verification fails.
        """
        spine_snap = checkpoint.snapshot_for(CheckpointScope.EVENT_SPINE)
        obl_snap = checkpoint.snapshot_for(CheckpointScope.OBLIGATION_RUNTIME)
        sup_snap = checkpoint.snapshot_for(CheckpointScope.SUPERVISOR)

        if spine_snap is None or obl_snap is None or sup_snap is None:
            raise RuntimeCoreInvariantError(
                "composite checkpoint must contain supervisor, event_spine, "
                "and obligation_runtime snapshots"
            )

        # Capture pre-restore state for rollback (all three subsystems)
        pre_spine = self._spine.snapshot()
        pre_obl = self._obligation_engine.snapshot()
        pre_supervisor = {
            "tick_number": self._supervisor.tick_number,
            "phase": self._supervisor.phase,
            "processed_event_ids": set(self._supervisor.processed_event_ids),
            "consecutive_errors": self._supervisor._consecutive_errors,
            "consecutive_idle_ticks": self._supervisor._consecutive_idle_ticks,
            "recent_tick_outcomes": tuple(self._supervisor._recent_outcomes),
        }

        def _rollback_all() -> None:
            """Rollback all three subsystems to pre-restore state."""
            self._spine.restore(pre_spine)
            self._obligation_engine.restore(pre_obl)
            # Restore supervisor to pre-restore state with actual captured values
            from mcoi_runtime.contracts.supervisor import CheckpointStatus, SupervisorCheckpoint
            rollback_cp = SupervisorCheckpoint(
                checkpoint_id=stable_identifier("rollback", {"tick": pre_supervisor["tick_number"]}),
                tick_number=pre_supervisor["tick_number"],
                phase=pre_supervisor["phase"],
                status=CheckpointStatus.VALID,
                open_obligation_ids=(),
                pending_event_count=0,
                consecutive_errors=pre_supervisor["consecutive_errors"],
                consecutive_idle_ticks=pre_supervisor["consecutive_idle_ticks"],
                recent_tick_outcomes=pre_supervisor["recent_tick_outcomes"],
                state_hash="rollback",
                created_at=self._clock(),
            )
            self._supervisor.resume_from_checkpoint(rollback_cp)
            self._supervisor.restore_processed_event_ids(pre_supervisor["processed_event_ids"])

        try:
            # Restore event spine
            self._spine.restore(spine_snap.payload)

            # Restore obligation runtime
            self._obligation_engine.restore(obl_snap.payload)

            # Restore supervisor
            from mcoi_runtime.contracts.supervisor import CheckpointStatus, SupervisorCheckpoint, SupervisorPhase
            stored_phase = SupervisorPhase(sup_snap.payload["phase"]) if sup_snap.payload.get("phase") else self._supervisor.phase
            sup_checkpoint = SupervisorCheckpoint(
                checkpoint_id=sup_snap.snapshot_id,
                tick_number=checkpoint.tick_number,
                phase=stored_phase,
                status=CheckpointStatus.VALID,
                open_obligation_ids=tuple(
                    o.obligation_id
                    for o in self._obligation_engine.list_obligations()
                    if o.state.value not in ("completed", "expired", "cancelled")
                ),
                pending_event_count=self._spine.event_count,
                consecutive_errors=sup_snap.payload.get("consecutive_errors", 0),
                consecutive_idle_ticks=sup_snap.payload.get("consecutive_idle_ticks", 0),
                recent_tick_outcomes=(),
                state_hash=sup_snap.state_hash,
                created_at=checkpoint.created_at,
            )
            self._supervisor.resume_from_checkpoint(sup_checkpoint)
            stored_ids = sup_snap.payload.get("processed_event_ids", [])
            self._supervisor.restore_processed_event_ids(set(stored_ids))

        except Exception:
            # Rollback all three subsystems
            _rollback_all()
            raise

        # Verify post-restore hashes if requested
        verification = None
        if verify:
            verification = self._verify_restore(checkpoint, spine_snap, obl_snap, sup_snap)
            self._verifications.append(verification)

            if verification.verdict != RestoreVerdict.VERIFIED:
                # Hash mismatch — rollback all three subsystems
                _rollback_all()
                raise RuntimeCoreInvariantError("restore verification failed")

        # Journal the restoration
        self.append_journal(
            JournalEntryKind.RESUME,
            subject_id=checkpoint.checkpoint_id,
            payload={
                "restored_tick": checkpoint.tick_number,
                "verified": verify,
                "verdict": verification.verdict.value if verification else "skipped",
            },
        )

        return verification

    def _verify_restore(
        self,
        checkpoint: CompositeCheckpoint,
        spine_snap: SubsystemSnapshot,
        obl_snap: SubsystemSnapshot,
        sup_snap: SubsystemSnapshot,
    ) -> RestoreVerification:
        """Verify post-restore state hashes match checkpoint hashes."""
        now = self._clock()

        post_spine_hash = self._spine.state_hash()
        post_obl_hash = self._obligation_engine.state_hash()
        post_sup_hash = self._supervisor_state_hash()
        post_composite = self._compute_composite_hash(
            post_spine_hash, post_obl_hash, post_sup_hash,
        )

        subsystem_results: dict[str, dict[str, str]] = {
            "event_spine": {
                "expected": spine_snap.state_hash,
                "actual": post_spine_hash,
                "match": "yes" if spine_snap.state_hash == post_spine_hash else "no",
            },
            "obligation_runtime": {
                "expected": obl_snap.state_hash,
                "actual": post_obl_hash,
                "match": "yes" if obl_snap.state_hash == post_obl_hash else "no",
            },
            "supervisor": {
                "expected": sup_snap.state_hash,
                "actual": post_sup_hash,
                "match": "yes" if sup_snap.state_hash == post_sup_hash else "no",
            },
        }

        if post_composite == checkpoint.composite_hash:
            verdict = RestoreVerdict.VERIFIED
        else:
            verdict = RestoreVerdict.HASH_MISMATCH

        return RestoreVerification(
            verification_id=stable_identifier("rv", {
                "checkpoint": checkpoint.checkpoint_id,
                "at": now,
            }),
            checkpoint_id=checkpoint.checkpoint_id,
            epoch_id=checkpoint.epoch_id,
            tick_number=checkpoint.tick_number,
            verdict=verdict,
            expected_composite_hash=checkpoint.composite_hash,
            actual_composite_hash=post_composite,
            subsystem_results=subsystem_results,
            verified_at=now,
        )

    @property
    def checkpoint_count(self) -> int:
        return len(self._checkpoints)

    @property
    def verification_count(self) -> int:
        return len(self._verifications)

    def latest_checkpoint(self) -> CompositeCheckpoint | None:
        """Return the most recent checkpoint, or None."""
        return self._checkpoints[-1] if self._checkpoints else None

    def latest_verification(self) -> RestoreVerification | None:
        """Return the most recent restore verification, or None."""
        return self._verifications[-1] if self._verifications else None

    def list_verifications(self) -> tuple[RestoreVerification, ...]:
        """Return all restore verifications in order."""
        return tuple(self._verifications)

    # --- Epoch management ---

    def advance_epoch(self, new_epoch_id: str) -> None:
        """Advance to a new epoch. Resets journal sequence to 0.

        This is used after a restore to start a fresh journal epoch.
        The previous journal entries are retained for audit but new
        entries will use the new epoch_id.
        """
        if not new_epoch_id or not new_epoch_id.strip():
            raise RuntimeCoreInvariantError("new_epoch_id must be non-empty")
        self._epoch_id = new_epoch_id
        self._sequence = 0

    @property
    def epoch_id(self) -> str:
        return self._epoch_id

    # --- Internal helpers ---

    def _supervisor_state_hash(self) -> str:
        """Compute a hash of the supervisor's current state.

        Includes tick, phase, error/idle counters, halted flag, and
        processed event count to match the supervisor's own hash scope.
        """
        data = json.dumps({
            "tick": self._supervisor.tick_number,
            "phase": self._supervisor.phase.value,
            "errors": self._supervisor._consecutive_errors,
            "idle": self._supervisor._consecutive_idle_ticks,
            "processed": len(self._supervisor.processed_event_ids),
        }, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _compute_composite_hash(*hashes: str) -> str:
        """Compute a composite hash from subsystem hashes."""
        combined = ":".join(sorted(hashes))
        return hashlib.sha256(combined.encode()).hexdigest()
