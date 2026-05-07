"""Purpose: validate replay from persisted artifacts end-to-end.
Governance scope: replay-persistence integration only.
Dependencies: replay engine, persistence stores.
Invariants:
  - A persisted run can survive process death and still be replay-validated deterministically.
  - Never executes live effects.
  - Fail closed on missing or corrupted artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .invariants import ensure_non_empty_text
from .replay_engine import (
    ReplayContext,
    ReplayEngine,
    ReplayValidationResult,
    ReplayVerdict,
)

from mcoi_runtime.persistence.replay_store import ReplayStore
from mcoi_runtime.persistence.trace_store import TraceStore
from mcoi_runtime.persistence.errors import (
    PersistenceError,
)


@dataclass(frozen=True, slots=True)
class PersistedReplayResult:
    """Full result of a persisted replay validation."""

    replay_id: str
    trace_id: str
    validation: ReplayValidationResult
    trace_found: bool
    trace_hash_matches: bool | None
    trace_lookup_reason: str = ""


class PersistedReplayValidator:
    """Load persisted replay/trace artifacts and validate end-to-end.

    This is the proof that a completed run can survive process death
    and still be reinterpreted deterministically.
    """

    def __init__(
        self,
        *,
        replay_store: ReplayStore,
        trace_store: TraceStore,
        replay_engine: ReplayEngine | None = None,
    ) -> None:
        self._replay_store = replay_store
        self._trace_store = trace_store
        self._replay_engine = replay_engine or ReplayEngine()

    def _bounded_persistence_reason(self, prefix: str, exc: Exception) -> str:
        return f"{prefix}:{type(exc).__name__}"

    def validate(
        self,
        replay_id: str,
        context: ReplayContext | None = None,
    ) -> PersistedReplayResult:
        """Load a persisted replay record and validate it.

        Steps:
        1. Load replay record from persistence (fail closed if missing/corrupted)
        2. Optionally load referenced trace entry for cross-validation
        3. Validate artifact completeness, state hash, environment digest
        4. Return explicit verdict — never guess, never silently succeed
        """
        ensure_non_empty_text("replay_id", replay_id)

        # Step 1: load replay record
        try:
            record = self._replay_store.load(replay_id)
        except PersistenceError as exc:
            return PersistedReplayResult(
                replay_id=replay_id,
                trace_id="",
                validation=ReplayValidationResult(
                    ready=False,
                    reasons=(self._bounded_persistence_reason("persistence_load_failed", exc),),
                    artifacts=(),
                    verdict=ReplayVerdict.INVALID_RECORD,
                ),
                trace_found=False,
                trace_hash_matches=None,
            )

        # Step 2: optionally load referenced trace for cross-validation
        trace_found = False
        trace_hash_matches: bool | None = None
        trace_lookup_reason = ""
        try:
            trace_entry = self._trace_store.load_trace(record.trace_id)
            trace_found = True
            # Cross-validate: the replay record's source_hash should match
            # the trace entry's state_hash for consistency
            if record.source_hash and trace_entry.state_hash:
                trace_hash_matches = record.source_hash == trace_entry.state_hash
        except PersistenceError as exc:
            # Trace not found is not fatal — replay can still validate its own artifacts
            trace_lookup_reason = self._bounded_persistence_reason("trace_lookup_failed", exc)

        # Step 3: validate with or without context
        if context is not None:
            validation = self._replay_engine.validate_with_context(record, context)
        else:
            validation = self._replay_engine.validate(record)

        return PersistedReplayResult(
            replay_id=record.replay_id,
            trace_id=record.trace_id,
            validation=validation,
            trace_found=trace_found,
            trace_hash_matches=trace_hash_matches,
            trace_lookup_reason=trace_lookup_reason,
        )

    def validate_all(
        self,
        context: ReplayContext | None = None,
    ) -> tuple[PersistedReplayResult, ...]:
        """Validate all persisted replay records."""
        replay_ids = self._replay_store.list_replays()
        return tuple(self.validate(rid, context) for rid in replay_ids)
