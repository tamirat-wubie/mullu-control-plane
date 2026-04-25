"""Purpose: verified runbook library — procedural memory from verified replayable runs.
Governance scope: procedural memory admission per docs/09_memory_hierarchy.md.
Dependencies: learning admission, persisted replay validator,
execution/verification contracts, memory hierarchy.
Invariants:
  - Only runs with successful execution, verification closure, persisted replay integrity,
    and no replay mismatch may be promoted into reusable runbooks.
  - Procedural memory admission requires LearningAdmissionDecision(status=admit).
  - Runbooks carry full provenance: execution_id, verification_id, replay_id, trace_id.
  - Revoked runbooks remain historical but are removed from active selection.
  - Runbook admission is explicit, never implicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Mapping

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus

from .invariants import RuntimeCoreInvariantError, ensure_iso_timestamp, ensure_non_empty_text, stable_identifier
from .persisted_replay import PersistedReplayValidator
from .replay_engine import ReplayContext, ReplayVerdict


class RunbookAdmissionStatus(StrEnum):
    ADMITTED = "admitted"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class RunbookProvenance:
    """Full provenance chain for a runbook."""

    execution_id: str
    verification_id: str
    replay_id: str
    trace_id: str
    learning_admission_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("execution_id", "verification_id", "replay_id", "trace_id"):
            object.__setattr__(self, field_name, ensure_non_empty_text(field_name, getattr(self, field_name)))
        if self.learning_admission_id is not None:
            object.__setattr__(
                self,
                "learning_admission_id",
                ensure_non_empty_text("learning_admission_id", self.learning_admission_id),
            )


@dataclass(frozen=True, slots=True)
class RunbookEntry:
    """A reusable operational procedure derived from a verified run."""

    runbook_id: str
    name: str
    description: str
    template: Mapping[str, Any]
    bindings_schema: Mapping[str, str]
    provenance: RunbookProvenance
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "runbook_id", ensure_non_empty_text("runbook_id", self.runbook_id))
        object.__setattr__(self, "name", ensure_non_empty_text("name", self.name))
        object.__setattr__(self, "description", ensure_non_empty_text("description", self.description))
        if not isinstance(self.template, Mapping):
            raise RuntimeCoreInvariantError("template must be a mapping")
        if not isinstance(self.bindings_schema, Mapping):
            raise RuntimeCoreInvariantError("bindings_schema must be a mapping")


@dataclass(frozen=True, slots=True)
class RunbookRevocation:
    """Append-only revocation record for one procedural memory runbook."""

    revocation_id: str
    runbook_id: str
    reason: str
    revoked_by: str
    evidence_refs: tuple[str, ...]
    revoked_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "revocation_id", ensure_non_empty_text("revocation_id", self.revocation_id))
        object.__setattr__(self, "runbook_id", ensure_non_empty_text("runbook_id", self.runbook_id))
        object.__setattr__(self, "reason", ensure_non_empty_text("reason", self.reason))
        object.__setattr__(self, "revoked_by", ensure_non_empty_text("revoked_by", self.revoked_by))
        object.__setattr__(self, "evidence_refs", _require_evidence_refs(self.evidence_refs))
        object.__setattr__(self, "revoked_at", ensure_iso_timestamp("revoked_at", self.revoked_at))


@dataclass(frozen=True, slots=True)
class RunbookAdmissionResult:
    """Result of attempting to admit a run as a reusable runbook."""

    runbook_id: str
    status: RunbookAdmissionStatus
    reasons: tuple[str, ...]
    entry: RunbookEntry | None = None


class RunbookLibrary:
    """Verified runbook library — procedural memory tier.

    Admission requires:
    1. Replay record exists and loads from persistence
    2. Replay validates as MATCH (no state/environment/artifact mismatches)
    3. Execution succeeded
    4. Verification closed with pass status
    5. All provenance IDs are present
    """

    def __init__(
        self,
        *,
        replay_validator: PersistedReplayValidator,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._replay_validator = replay_validator
        self._clock = clock or _utc_now
        self._entries: dict[str, RunbookEntry] = {}
        self._revocations: dict[str, RunbookRevocation] = {}
        self._revoked_by_runbook: dict[str, str] = {}

    def admit(
        self,
        *,
        runbook_id: str,
        name: str,
        description: str,
        template: Mapping[str, Any],
        bindings_schema: Mapping[str, str],
        replay_id: str,
        execution_id: str,
        verification_id: str,
        execution_succeeded: bool,
        verification_passed: bool,
        learning_admission: LearningAdmissionDecision | None = None,
        context: ReplayContext | None = None,
        preconditions: tuple[str, ...] = (),
        postconditions: tuple[str, ...] = (),
    ) -> RunbookAdmissionResult:
        """Attempt to admit a verified run as a reusable runbook.

        All admission criteria must pass. Failure at any step rejects the runbook.
        """
        ensure_non_empty_text("runbook_id", runbook_id)
        reasons: list[str] = []

        # Gate 1: execution must have succeeded
        if not execution_succeeded:
            reasons.append("execution_did_not_succeed")

        # Gate 2: verification must have passed
        if not verification_passed:
            reasons.append("verification_did_not_pass")

        # Gate 3: learning admission must explicitly admit this procedural candidate
        if learning_admission is None:
            reasons.append("learning_admission_missing")
        else:
            if learning_admission.knowledge_id != runbook_id:
                reasons.append("learning_admission_knowledge_mismatch")
            if learning_admission.status is not LearningAdmissionStatus.ADMIT:
                reasons.append(f"learning_admission_status:{learning_admission.status.value}")

        # Gate 4: replay must validate as MATCH from persistence
        replay_result = self._replay_validator.validate(replay_id, context)

        if not replay_result.validation.ready:
            reasons.append(f"replay_not_ready:{replay_result.validation.verdict.value}")

        if replay_result.validation.verdict is not ReplayVerdict.MATCH:
            if "replay_not_ready" not in reasons[0] if reasons else True:
                reasons.append(f"replay_verdict:{replay_result.validation.verdict.value}")

        # Gate 5: duplicate check
        if runbook_id in self._entries:
            reasons.append("runbook_id_already_exists")

        # Gate 6: revoked runbook ids cannot be silently reused
        if runbook_id in self._revoked_by_runbook:
            reasons.append("runbook_id_revoked")

        if reasons:
            return RunbookAdmissionResult(
                runbook_id=runbook_id,
                status=RunbookAdmissionStatus.REJECTED,
                reasons=tuple(reasons),
            )

        # All gates passed — create the runbook entry
        provenance = RunbookProvenance(
            execution_id=execution_id,
            verification_id=verification_id,
            replay_id=replay_id,
            trace_id=replay_result.trace_id,
            learning_admission_id=learning_admission.admission_id,
        )

        entry = RunbookEntry(
            runbook_id=runbook_id,
            name=name,
            description=description,
            template=template,
            bindings_schema=bindings_schema,
            provenance=provenance,
            preconditions=preconditions,
            postconditions=postconditions,
        )

        self._entries[runbook_id] = entry

        return RunbookAdmissionResult(
            runbook_id=runbook_id,
            status=RunbookAdmissionStatus.ADMITTED,
            reasons=("all_admission_gates_passed",),
            entry=entry,
        )

    def get(self, runbook_id: str) -> RunbookEntry | None:
        ensure_non_empty_text("runbook_id", runbook_id)
        if runbook_id in self._revoked_by_runbook:
            return None
        return self._entries.get(runbook_id)

    def get_historical(self, runbook_id: str) -> RunbookEntry | None:
        """Return a runbook entry even when it has been revoked."""
        ensure_non_empty_text("runbook_id", runbook_id)
        return self._entries.get(runbook_id)

    def list_runbooks(self) -> tuple[RunbookEntry, ...]:
        """Return active, non-revoked runbooks in stable order."""
        return tuple(
            self._entries[rid] for rid in sorted(self._entries) if rid not in self._revoked_by_runbook
        )

    def list_historical_runbooks(self) -> tuple[RunbookEntry, ...]:
        """Return every admitted runbook, including revoked historical entries."""
        return tuple(self._entries[rid] for rid in sorted(self._entries))

    def revoke(
        self,
        runbook_id: str,
        *,
        reason: str,
        revoked_by: str,
        evidence_refs: tuple[str, ...],
    ) -> RunbookRevocation:
        """Revoke a runbook from active selection without deleting its history."""
        runbook_id = ensure_non_empty_text("runbook_id", runbook_id)
        if runbook_id not in self._entries:
            raise RuntimeCoreInvariantError("runbook must exist before revocation")
        if runbook_id in self._revoked_by_runbook:
            raise RuntimeCoreInvariantError("runbook already revoked")
        revoked_at = self._clock()
        revocation = RunbookRevocation(
            revocation_id=stable_identifier(
                "runbook-revocation",
                {
                    "runbook_id": runbook_id,
                    "reason": reason,
                    "revoked_by": revoked_by,
                    "revoked_at": revoked_at,
                },
            ),
            runbook_id=runbook_id,
            reason=reason,
            revoked_by=revoked_by,
            evidence_refs=evidence_refs,
            revoked_at=revoked_at,
        )
        if revocation.revocation_id in self._revocations:
            raise RuntimeCoreInvariantError("runbook revocation already exists")
        self._revocations[revocation.revocation_id] = revocation
        self._revoked_by_runbook[runbook_id] = revocation.revocation_id
        return revocation

    def revocation_for(self, runbook_id: str) -> RunbookRevocation | None:
        """Return the revocation record for a runbook id, when one exists."""
        ensure_non_empty_text("runbook_id", runbook_id)
        revocation_id = self._revoked_by_runbook.get(runbook_id)
        if revocation_id is None:
            return None
        return self._revocations[revocation_id]

    def list_revocations(self) -> tuple[RunbookRevocation, ...]:
        """Return all runbook revocations in stable order."""
        return tuple(self._revocations[rid] for rid in sorted(self._revocations))

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def active_size(self) -> int:
        return len(self.list_runbooks())

    @property
    def revocation_count(self) -> int:
        return len(self._revocations)


def _require_evidence_refs(evidence_refs: tuple[str, ...]) -> tuple[str, ...]:
    refs = tuple(evidence_refs)
    if not refs:
        raise RuntimeCoreInvariantError("runbook revocation requires evidence refs")
    for evidence_ref in refs:
        ensure_non_empty_text("evidence_ref", evidence_ref)
    return refs


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
