"""Temporal bridge for note-memory projections.

Purpose: convert projection-derived blockers and candidate actions into
scheduler-safe checks, reminders, and condition monitors.
Governance scope: no direct high-risk execution from memory, source lineage,
and explicit scheduling intent.
Dependencies: dataclasses, note-memory projection, and runtime invariant
helpers.
Invariants: temporal bridge emits candidates only and never schedules direct
deployment or other high-risk side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.note_memory_projection import CandidateActionStatus, NoteMemoryProjection


class TemporalCandidateType(StrEnum):
    """Allowed scheduler-safe temporal candidate classes."""

    EVIDENCE_CHECK = "evidence_check"
    REPAIR_REVIEW = "repair_review"
    CONDITION_MONITOR = "condition_monitor"
    REMINDER = "reminder"


@dataclass(frozen=True)
class TemporalCandidate:
    """Scheduler-safe temporal candidate."""

    temporal_candidate_id: str
    candidate_type: TemporalCandidateType
    source_ids: tuple[str, ...]
    reason: str
    schedule_direct_execution: bool = False

    def __post_init__(self) -> None:
        if self.schedule_direct_execution:
            raise RuntimeCoreInvariantError("temporal candidates cannot schedule direct execution")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible temporal candidate."""

        return {
            "temporal_candidate_id": self.temporal_candidate_id,
            "candidate_type": self.candidate_type.value,
            "source_ids": list(self.source_ids),
            "reason": self.reason,
            "schedule_direct_execution": self.schedule_direct_execution,
        }


def build_temporal_candidates(projection: NoteMemoryProjection) -> tuple[TemporalCandidate, ...]:
    """Build scheduler-safe checks from projection state."""

    candidates: list[TemporalCandidate] = []
    for blocker in projection.blockers:
        candidates.append(
            _candidate(
                candidate_type=TemporalCandidateType.REPAIR_REVIEW,
                source_ids=blocker.source_ids,
                reason=blocker.reason,
            )
        )
    for action in projection.candidate_actions:
        candidate_type = (
            TemporalCandidateType.EVIDENCE_CHECK
            if action.status == CandidateActionStatus.BLOCKED
            else TemporalCandidateType.CONDITION_MONITOR
        )
        candidates.append(
            _candidate(
                candidate_type=candidate_type,
                source_ids=action.source_note_ids,
                reason=action.reason,
            )
        )
    return tuple(candidates)


def _candidate(
    *,
    candidate_type: TemporalCandidateType,
    source_ids: tuple[str, ...],
    reason: str,
) -> TemporalCandidate:
    temporal_candidate_id = stable_identifier(
        "temporal-candidate",
        {"candidate_type": candidate_type.value, "source_ids": source_ids, "reason": reason},
    )
    return TemporalCandidate(
        temporal_candidate_id=temporal_candidate_id,
        candidate_type=candidate_type,
        source_ids=source_ids,
        reason=reason,
    )
