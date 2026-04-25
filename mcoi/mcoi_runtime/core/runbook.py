"""Purpose: verified runbook library — procedural memory from verified replayable runs.
Governance scope: procedural memory admission per docs/09_memory_hierarchy.md.
Dependencies: learning admission, persisted replay validator,
execution/verification contracts, memory hierarchy.
Invariants:
  - Only runs with successful execution, verification closure, persisted replay integrity,
    and no replay mismatch may be promoted into reusable runbooks.
  - Procedural memory admission requires LearningAdmissionDecision(status=admit).
  - Runbooks carry full provenance: execution_id, verification_id, replay_id, trace_id.
  - Runbook admission is explicit, never implicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text
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

    def __init__(self, *, replay_validator: PersistedReplayValidator) -> None:
        self._replay_validator = replay_validator
        self._entries: dict[str, RunbookEntry] = {}

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
        return self._entries.get(runbook_id)

    def list_runbooks(self) -> tuple[RunbookEntry, ...]:
        return tuple(
            self._entries[rid] for rid in sorted(self._entries)
        )

    @property
    def size(self) -> int:
        return len(self._entries)
