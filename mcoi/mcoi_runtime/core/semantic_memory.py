"""Purpose: versioned semantic memory write gate.
Governance scope: semantic memory admission for generalized knowledge records.
Dependencies: knowledge, evidence, and learning admission contracts.
Invariants:
  - Semantic memory never stores knowledge without LearningAdmissionDecision(status=admit).
  - Every semantic entry references source memory and evidence.
  - Updates create new versions; existing entries are never mutated.
  - Current-version lookup is explicit and deterministic.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mcoi_runtime.contracts.knowledge import KnowledgeRecord
from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus

from .invariants import RuntimeCoreInvariantError, ensure_iso_timestamp, ensure_non_empty_text, stable_identifier


@dataclass(frozen=True, slots=True)
class SemanticMemoryEntry:
    """A versioned semantic memory entry admitted from source evidence."""

    entry_id: str
    knowledge: KnowledgeRecord
    version: int
    learning_admission_id: str
    source_refs: tuple[str, ...]
    admitted_at: str
    supersedes_entry_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", ensure_non_empty_text("entry_id", self.entry_id))
        if not isinstance(self.knowledge, KnowledgeRecord):
            raise RuntimeCoreInvariantError("knowledge must be a KnowledgeRecord")
        if self.version <= 0:
            raise RuntimeCoreInvariantError("semantic memory version must be positive")
        object.__setattr__(
            self,
            "learning_admission_id",
            ensure_non_empty_text("learning_admission_id", self.learning_admission_id),
        )
        object.__setattr__(self, "source_refs", _require_source_refs(self.source_refs))
        object.__setattr__(self, "admitted_at", ensure_iso_timestamp("admitted_at", self.admitted_at))
        if self.supersedes_entry_id is not None:
            object.__setattr__(
                self,
                "supersedes_entry_id",
                ensure_non_empty_text("supersedes_entry_id", self.supersedes_entry_id),
            )


class SemanticMemoryStore:
    """Append-only semantic memory store with admission enforcement."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._entries: dict[str, SemanticMemoryEntry] = {}
        self._versions_by_knowledge: dict[str, list[str]] = {}
        self._current_by_knowledge: dict[str, str] = {}

    @property
    def size(self) -> int:
        """Return total semantic memory entries."""
        return len(self._entries)

    def get(self, entry_id: str) -> SemanticMemoryEntry | None:
        """Return a semantic memory entry by entry id."""
        ensure_non_empty_text("entry_id", entry_id)
        return self._entries.get(entry_id)

    def current(self, knowledge_id: str) -> SemanticMemoryEntry | None:
        """Return the current semantic memory entry for a knowledge id."""
        ensure_non_empty_text("knowledge_id", knowledge_id)
        entry_id = self._current_by_knowledge.get(knowledge_id)
        if entry_id is None:
            return None
        return self._entries[entry_id]

    def list_versions(self, knowledge_id: str) -> tuple[SemanticMemoryEntry, ...]:
        """Return all versions for one knowledge id in version order."""
        ensure_non_empty_text("knowledge_id", knowledge_id)
        return tuple(self._entries[entry_id] for entry_id in self._versions_by_knowledge.get(knowledge_id, ()))

    def admit(
        self,
        *,
        knowledge: KnowledgeRecord,
        learning_admission: LearningAdmissionDecision,
        source_refs: tuple[str, ...],
    ) -> SemanticMemoryEntry:
        """Admit a first semantic memory version."""
        _require_admission(knowledge, learning_admission)
        _require_knowledge_evidence(knowledge)
        if knowledge.knowledge_id in self._current_by_knowledge:
            raise RuntimeCoreInvariantError("semantic knowledge already admitted")
        return self._append(
            knowledge=knowledge,
            learning_admission=learning_admission,
            source_refs=source_refs,
            version=1,
            supersedes_entry_id=None,
        )

    def supersede(
        self,
        *,
        knowledge: KnowledgeRecord,
        learning_admission: LearningAdmissionDecision,
        source_refs: tuple[str, ...],
        supersedes_entry_id: str,
    ) -> SemanticMemoryEntry:
        """Append a new current semantic version for existing knowledge."""
        _require_admission(knowledge, learning_admission)
        _require_knowledge_evidence(knowledge)
        current = self.current(knowledge.knowledge_id)
        if current is None:
            raise RuntimeCoreInvariantError("semantic knowledge must exist before supersede")
        if current.entry_id != ensure_non_empty_text("supersedes_entry_id", supersedes_entry_id):
            raise RuntimeCoreInvariantError("semantic supersede must target current version")
        return self._append(
            knowledge=knowledge,
            learning_admission=learning_admission,
            source_refs=source_refs,
            version=current.version + 1,
            supersedes_entry_id=current.entry_id,
        )

    def _append(
        self,
        *,
        knowledge: KnowledgeRecord,
        learning_admission: LearningAdmissionDecision,
        source_refs: tuple[str, ...],
        version: int,
        supersedes_entry_id: str | None,
    ) -> SemanticMemoryEntry:
        admitted_at = self._clock()
        entry = SemanticMemoryEntry(
            entry_id=stable_identifier(
                "semantic-memory",
                {
                    "knowledge_id": knowledge.knowledge_id,
                    "content_hash": knowledge.content_hash,
                    "version": version,
                    "admission_id": learning_admission.admission_id,
                    "admitted_at": admitted_at,
                },
            ),
            knowledge=knowledge,
            version=version,
            learning_admission_id=learning_admission.admission_id,
            source_refs=_require_source_refs(source_refs),
            admitted_at=admitted_at,
            supersedes_entry_id=supersedes_entry_id,
        )
        if entry.entry_id in self._entries:
            raise RuntimeCoreInvariantError("semantic memory entry already exists")
        self._entries[entry.entry_id] = entry
        self._versions_by_knowledge.setdefault(knowledge.knowledge_id, []).append(entry.entry_id)
        self._current_by_knowledge[knowledge.knowledge_id] = entry.entry_id
        return entry


def _require_admission(
    knowledge: KnowledgeRecord,
    learning_admission: LearningAdmissionDecision,
) -> None:
    if not isinstance(knowledge, KnowledgeRecord):
        raise RuntimeCoreInvariantError("knowledge must be a KnowledgeRecord")
    if learning_admission.knowledge_id != knowledge.knowledge_id:
        raise RuntimeCoreInvariantError("learning admission knowledge mismatch")
    if learning_admission.status is not LearningAdmissionStatus.ADMIT:
        raise RuntimeCoreInvariantError("semantic memory requires admitted learning decision")


def _require_knowledge_evidence(knowledge: KnowledgeRecord) -> None:
    if not knowledge.evidence:
        raise RuntimeCoreInvariantError("semantic memory requires evidence")
    for evidence in knowledge.evidence:
        if evidence.uri is None:
            raise RuntimeCoreInvariantError("semantic memory evidence requires uri")


def _require_source_refs(source_refs: tuple[str, ...]) -> tuple[str, ...]:
    refs = tuple(source_refs)
    if not refs:
        raise RuntimeCoreInvariantError("semantic memory requires source refs")
    for source_ref in refs:
        ensure_non_empty_text("source_ref", source_ref)
    return refs
