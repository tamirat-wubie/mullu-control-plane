"""Purpose: durable persistence for admitted software-learning records.
Governance scope: software learning candidates, learning admission decisions,
    admitted planning projections, deterministic persistence, and replay.
Dependencies: JSON, pathlib, learning contracts, software-learning contracts,
    planning boundary records, and persistence errors.
Invariants:
  - Candidate and decision ids are append-only and idempotent by payload.
  - Planning projections must reference admitted learning decisions.
  - File persistence writes deterministic JSON atomically.
  - Malformed persisted learning records fail closed.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus
from mcoi_runtime.contracts.policy import DecisionReason
from mcoi_runtime.contracts.software_learning import (
    SoftwareLearningKind,
    SoftwareMemoryTarget,
    SoftwareOutcomeLearningCandidate,
)
from mcoi_runtime.core.planning_boundary import KnowledgeLifecycle, PlanningKnowledge

from .errors import CorruptedDataError, PersistenceError, PersistenceWriteError


def _bounded_store_error(summary: str, exc: BaseException) -> str:
    return f"{summary} ({type(exc).__name__})"


def _deterministic_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            fd = -1
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd >= 0:
                os.close(fd)
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except OSError as exc:
        raise PersistenceWriteError(
            _bounded_store_error("software learning store write failed", exc),
        ) from exc


def _candidate_from_json(raw: dict[str, Any]) -> SoftwareOutcomeLearningCandidate:
    if not isinstance(raw, dict):
        raise CorruptedDataError("software learning candidate must be an object")
    try:
        return SoftwareOutcomeLearningCandidate(
            knowledge_id=raw["knowledge_id"],
            kind=SoftwareLearningKind(raw["kind"]),
            memory_target=SoftwareMemoryTarget(raw["memory_target"]),
            request_id=raw["request_id"],
            repository=raw["repository"],
            summary=raw["summary"],
            pattern=raw["pattern"],
            affected_files=tuple(raw["affected_files"]),
            receipt_refs=tuple(raw["receipt_refs"]),
            gate_refs=tuple(raw["gate_refs"]),
            evidence_refs=tuple(raw["evidence_refs"]),
            error_signature=raw.get("error_signature", ""),
            raw_log_included=bool(raw.get("raw_log_included", False)),
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid software learning candidate", exc),
        ) from exc


def _decision_from_json(raw: dict[str, Any]) -> LearningAdmissionDecision:
    if not isinstance(raw, dict):
        raise CorruptedDataError("learning admission decision must be an object")
    try:
        reasons = tuple(_reason_from_json(item) for item in raw["reasons"])
        return LearningAdmissionDecision(
            admission_id=raw["admission_id"],
            knowledge_id=raw["knowledge_id"],
            status=LearningAdmissionStatus(raw["status"]),
            reasons=reasons,
            issued_at=raw["issued_at"],
            metadata=raw.get("metadata", {}),
            extensions=raw.get("extensions", {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid learning admission decision", exc),
        ) from exc


def _reason_from_json(raw: dict[str, Any]) -> DecisionReason:
    if not isinstance(raw, dict):
        raise CorruptedDataError("decision reason must be an object")
    try:
        return DecisionReason(
            message=raw["message"],
            code=raw.get("code"),
            details=raw.get("details"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(_bounded_store_error("invalid decision reason", exc)) from exc


def _planning_from_json(raw: dict[str, Any]) -> PlanningKnowledge:
    if not isinstance(raw, dict):
        raise CorruptedDataError("planning knowledge projection must be an object")
    try:
        return PlanningKnowledge(
            knowledge_id=raw["knowledge_id"],
            knowledge_class=raw["knowledge_class"],
            lifecycle=KnowledgeLifecycle(raw["lifecycle"]),
            admission_id=raw.get("admission_id"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptedDataError(
            _bounded_store_error("invalid planning knowledge projection", exc),
        ) from exc


def _planning_to_json(entry: PlanningKnowledge) -> dict[str, Any]:
    return {
        "knowledge_id": entry.knowledge_id,
        "knowledge_class": entry.knowledge_class,
        "lifecycle": entry.lifecycle.value,
        "admission_id": entry.admission_id,
    }


class SoftwareLearningStore:
    """In-memory append/query store for software-learning records."""

    def __init__(self) -> None:
        self._candidates: list[SoftwareOutcomeLearningCandidate] = []
        self._decisions: list[LearningAdmissionDecision] = []
        self._planning: list[PlanningKnowledge] = []
        self._candidates_by_id: dict[str, SoftwareOutcomeLearningCandidate] = {}
        self._decisions_by_id: dict[str, LearningAdmissionDecision] = {}
        self._planning_by_id: dict[str, PlanningKnowledge] = {}

    def append_candidate(
        self,
        candidate: SoftwareOutcomeLearningCandidate,
    ) -> SoftwareOutcomeLearningCandidate:
        if not isinstance(candidate, SoftwareOutcomeLearningCandidate):
            raise PersistenceError("candidate must be a SoftwareOutcomeLearningCandidate")
        existing = self._candidates_by_id.get(candidate.knowledge_id)
        if existing is not None:
            if existing.to_json_dict() != candidate.to_json_dict():
                raise PersistenceError("software learning candidate id collision")
            return existing
        self._candidates.append(candidate)
        self._candidates_by_id[candidate.knowledge_id] = candidate
        return candidate

    def append_decision(
        self,
        decision: LearningAdmissionDecision,
    ) -> LearningAdmissionDecision:
        if not isinstance(decision, LearningAdmissionDecision):
            raise PersistenceError("decision must be a LearningAdmissionDecision")
        if decision.knowledge_id not in self._candidates_by_id:
            raise PersistenceError("learning decision requires stored candidate")
        existing = self._decisions_by_id.get(decision.admission_id)
        if existing is not None:
            if existing.to_json_dict() != decision.to_json_dict():
                raise PersistenceError("learning admission decision id collision")
            return existing
        self._decisions.append(decision)
        self._decisions_by_id[decision.admission_id] = decision
        return decision

    def append_planning_knowledge(self, entry: PlanningKnowledge) -> PlanningKnowledge:
        if not isinstance(entry, PlanningKnowledge):
            raise PersistenceError("entry must be PlanningKnowledge")
        if entry.admission_id is None:
            raise PersistenceError("planning knowledge requires admission_id")
        decision = self._decisions_by_id.get(entry.admission_id)
        if decision is None:
            raise PersistenceError("planning knowledge requires stored admission decision")
        if decision.status is not LearningAdmissionStatus.ADMIT:
            raise PersistenceError("planning knowledge requires admitted decision")
        if decision.knowledge_id != entry.knowledge_id:
            raise PersistenceError("planning knowledge admission mismatch")
        existing = self._planning_by_id.get(entry.knowledge_id)
        if existing is not None:
            if _planning_to_json(existing) != _planning_to_json(entry):
                raise PersistenceError("planning knowledge id collision")
            return existing
        self._planning.append(entry)
        self._planning_by_id[entry.knowledge_id] = entry
        return entry

    def append_bundle(
        self,
        *,
        candidates: Iterable[SoftwareOutcomeLearningCandidate],
        decisions: Iterable[LearningAdmissionDecision],
        planning_entries: Iterable[PlanningKnowledge] = (),
    ) -> dict[str, int]:
        before = self.summary()
        for candidate in candidates:
            self.append_candidate(candidate)
        for decision in decisions:
            self.append_decision(decision)
        for entry in planning_entries:
            self.append_planning_knowledge(entry)
        after = self.summary()
        return {
            "candidates": after["candidate_count"] - before["candidate_count"],
            "decisions": after["decision_count"] - before["decision_count"],
            "planning_entries": after["planning_entry_count"] - before["planning_entry_count"],
        }

    def list_candidates(self, *, request_id: str | None = None) -> tuple[SoftwareOutcomeLearningCandidate, ...]:
        return tuple(
            candidate
            for candidate in self._candidates
            if request_id is None or candidate.request_id == request_id
        )

    def list_decisions(self, *, knowledge_id: str | None = None) -> tuple[LearningAdmissionDecision, ...]:
        return tuple(
            decision
            for decision in self._decisions
            if knowledge_id is None or decision.knowledge_id == knowledge_id
        )

    def list_planning_knowledge(self) -> tuple[PlanningKnowledge, ...]:
        return tuple(self._planning)

    def summary(self) -> dict[str, Any]:
        by_status = {status.value: 0 for status in LearningAdmissionStatus}
        for decision in self._decisions:
            by_status[decision.status.value] += 1
        return {
            "candidate_count": len(self._candidates),
            "decision_count": len(self._decisions),
            "planning_entry_count": len(self._planning),
            "admitted_decision_count": by_status[LearningAdmissionStatus.ADMIT.value],
            "raw_log_candidate_count": sum(1 for item in self._candidates if item.raw_log_included),
            "by_status": by_status,
            "governed": True,
        }


class FileSoftwareLearningStore(SoftwareLearningStore):
    """JSON-file backed software-learning store."""

    def __init__(self, path: Path) -> None:
        if not isinstance(path, Path):
            raise PersistenceError("path must be a Path instance")
        self._path = path
        super().__init__()
        self._load_if_present()

    def append_candidate(
        self,
        candidate: SoftwareOutcomeLearningCandidate,
    ) -> SoftwareOutcomeLearningCandidate:
        appended = super().append_candidate(candidate)
        self._persist()
        return appended

    def append_decision(self, decision: LearningAdmissionDecision) -> LearningAdmissionDecision:
        appended = super().append_decision(decision)
        self._persist()
        return appended

    def append_planning_knowledge(self, entry: PlanningKnowledge) -> PlanningKnowledge:
        appended = super().append_planning_knowledge(entry)
        self._persist()
        return appended

    def append_bundle(
        self,
        *,
        candidates: Iterable[SoftwareOutcomeLearningCandidate],
        decisions: Iterable[LearningAdmissionDecision],
        planning_entries: Iterable[PlanningKnowledge] = (),
    ) -> dict[str, int]:
        changed = super().append_bundle(
            candidates=candidates,
            decisions=decisions,
            planning_entries=planning_entries,
        )
        if any(changed.values()):
            self._persist()
        return changed

    def _persist(self) -> None:
        payload = {
            "candidates": [candidate.to_json_dict() for candidate in self._candidates],
            "decisions": [decision.to_json_dict() for decision in self._decisions],
            "planning_knowledge": [_planning_to_json(entry) for entry in self._planning],
        }
        _atomic_write(self._path, _deterministic_json(payload))

    def _load_if_present(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise CorruptedDataError(
                _bounded_store_error("malformed software learning store file", exc),
            ) from exc
        if not isinstance(raw, dict):
            raise CorruptedDataError("software learning store payload must be an object")
        candidates_raw = raw.get("candidates")
        decisions_raw = raw.get("decisions")
        planning_raw = raw.get("planning_knowledge", [])
        if not isinstance(candidates_raw, list):
            raise CorruptedDataError("software learning candidates must be a list")
        if not isinstance(decisions_raw, list):
            raise CorruptedDataError("software learning decisions must be a list")
        if not isinstance(planning_raw, list):
            raise CorruptedDataError("software learning planning entries must be a list")
        for item in candidates_raw:
            super().append_candidate(_candidate_from_json(item))
        for item in decisions_raw:
            super().append_decision(_decision_from_json(item))
        for item in planning_raw:
            super().append_planning_knowledge(_planning_from_json(item))
