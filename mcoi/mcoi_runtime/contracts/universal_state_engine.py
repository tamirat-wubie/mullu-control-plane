"""Purpose: Universal State Engine contract for governed lifecycle meshes.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS state closure.
Dependencies: shared contract base helpers, state references, and state-machine contracts.
Invariants: subjects, guards, transitions, closures, receipts, and machines are explicit and linked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
    require_unit_float,
)
from .state import StateReference
from .state_machine import StateMachineSpec, TransitionVerdict


class UniversalStateSubjectKind(StrEnum):
    """Governed subject classes whose lifecycle can be represented by the engine."""

    NOTE = "note"
    MEMORY = "memory"
    RECEIPT = "receipt"
    WORKFLOW = "workflow"
    DEPLOYMENT = "deployment"
    CASE = "case"
    CAPABILITY = "capability"
    SKILL = "skill"
    POLICY = "policy"
    ACTION = "action"


class UniversalStateGuardKind(StrEnum):
    """Guard classes that must be satisfied before transition execution."""

    EVIDENCE_REQUIRED = "evidence_required"
    AUTHORITY_REQUIRED = "authority_required"
    RECEIPT_REQUIRED = "receipt_required"
    STATE_INVARIANT = "state_invariant"
    TEMPORAL_WINDOW = "temporal_window"
    APPROVAL_REQUIRED = "approval_required"


class UniversalStateClosureKind(StrEnum):
    """Terminal closure classes for governed lifecycle completion."""

    COMPLETED = "completed"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class UniversalStateSubject(ContractRecord):
    """A governed subject bound to one declared state machine and current state."""

    subject_id: str
    subject_kind: UniversalStateSubjectKind
    machine_id: str
    current_state: str
    state_ref: StateReference
    evidence_refs: tuple[str, ...]
    updated_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject_id", require_non_empty_text(self.subject_id, "subject_id"))
        if not isinstance(self.subject_kind, UniversalStateSubjectKind):
            raise ValueError("subject_kind must be a UniversalStateSubjectKind value")
        object.__setattr__(self, "machine_id", require_non_empty_text(self.machine_id, "machine_id"))
        object.__setattr__(self, "current_state", require_non_empty_text(self.current_state, "current_state"))
        if not isinstance(self.state_ref, StateReference):
            raise ValueError("state_ref must be a StateReference")
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniversalStateGuard(ContractRecord):
    """A transition guard with required proof references and confidence."""

    guard_id: str
    guard_kind: UniversalStateGuardKind
    machine_id: str
    from_state: str
    to_state: str
    required_refs: tuple[str, ...]
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "guard_id", require_non_empty_text(self.guard_id, "guard_id"))
        if not isinstance(self.guard_kind, UniversalStateGuardKind):
            raise ValueError("guard_kind must be a UniversalStateGuardKind value")
        object.__setattr__(self, "machine_id", require_non_empty_text(self.machine_id, "machine_id"))
        object.__setattr__(self, "from_state", require_non_empty_text(self.from_state, "from_state"))
        object.__setattr__(self, "to_state", require_non_empty_text(self.to_state, "to_state"))
        object.__setattr__(self, "required_refs", _require_text_tuple(self.required_refs, "required_refs"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniversalStateTransition(ContractRecord):
    """Observed governed transition linking a subject, machine edge, guards, receipts, and evidence."""

    transition_id: str
    subject_id: str
    machine_id: str
    from_state: str
    to_state: str
    action: str
    guard_ids: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    transitioned_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "transition_id", require_non_empty_text(self.transition_id, "transition_id"))
        object.__setattr__(self, "subject_id", require_non_empty_text(self.subject_id, "subject_id"))
        object.__setattr__(self, "machine_id", require_non_empty_text(self.machine_id, "machine_id"))
        object.__setattr__(self, "from_state", require_non_empty_text(self.from_state, "from_state"))
        object.__setattr__(self, "to_state", require_non_empty_text(self.to_state, "to_state"))
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        object.__setattr__(self, "guard_ids", _require_text_tuple(self.guard_ids, "guard_ids"))
        object.__setattr__(self, "receipt_refs", _require_text_tuple(self.receipt_refs, "receipt_refs"))
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "transitioned_at", require_datetime_text(self.transitioned_at, "transitioned_at"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniversalStateClosure(ContractRecord):
    """Terminal closure binding a subject to a terminal state and receipt evidence."""

    closure_id: str
    subject_id: str
    closure_kind: UniversalStateClosureKind
    terminal_state: str
    receipt_refs: tuple[str, ...]
    closed_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "closure_id", require_non_empty_text(self.closure_id, "closure_id"))
        object.__setattr__(self, "subject_id", require_non_empty_text(self.subject_id, "subject_id"))
        if not isinstance(self.closure_kind, UniversalStateClosureKind):
            raise ValueError("closure_kind must be a UniversalStateClosureKind value")
        object.__setattr__(self, "terminal_state", require_non_empty_text(self.terminal_state, "terminal_state"))
        object.__setattr__(self, "receipt_refs", _require_text_tuple(self.receipt_refs, "receipt_refs"))
        object.__setattr__(self, "closed_at", require_datetime_text(self.closed_at, "closed_at"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UniversalStateEngine(ContractRecord):
    """Portable state mesh snapshot for State -> Transition -> Guard -> Receipt -> Closure."""

    engine_id: str
    version: str
    generated_at: str
    subjects: tuple[UniversalStateSubject, ...]
    state_machines: tuple[StateMachineSpec, ...]
    guards: tuple[UniversalStateGuard, ...]
    transitions: tuple[UniversalStateTransition, ...]
    closures: tuple[UniversalStateClosure, ...]
    receipt_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "engine_id", require_non_empty_text(self.engine_id, "engine_id"))
        object.__setattr__(self, "version", require_non_empty_text(self.version, "version"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))
        object.__setattr__(self, "subjects", _require_record_tuple(self.subjects, UniversalStateSubject, "subjects"))
        object.__setattr__(
            self,
            "state_machines",
            _require_record_tuple(self.state_machines, StateMachineSpec, "state_machines"),
        )
        object.__setattr__(self, "guards", _require_record_tuple(self.guards, UniversalStateGuard, "guards"))
        object.__setattr__(
            self,
            "transitions",
            _require_record_tuple(self.transitions, UniversalStateTransition, "transitions"),
        )
        object.__setattr__(self, "closures", _require_record_tuple(self.closures, UniversalStateClosure, "closures"))
        object.__setattr__(self, "receipt_refs", _require_text_tuple(self.receipt_refs, "receipt_refs"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        _validate_engine_references(
            self.subjects,
            self.state_machines,
            self.guards,
            self.transitions,
            self.closures,
        )


def _require_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    items = require_non_empty_tuple(values, field_name)
    for item in items:
        require_non_empty_text(item, f"{field_name} element")
    if len(set(items)) != len(items):
        raise ValueError(f"{field_name} must not contain duplicates")
    return tuple(items)


def _require_record_tuple(values: tuple[Any, ...], record_type: type[Any], field_name: str) -> tuple[Any, ...]:
    items = require_non_empty_tuple(values, field_name)
    for item in items:
        if not isinstance(item, record_type):
            raise ValueError(f"{field_name} must contain {record_type.__name__} records")
    return tuple(items)


def _validate_engine_references(
    subjects: tuple[UniversalStateSubject, ...],
    state_machines: tuple[StateMachineSpec, ...],
    guards: tuple[UniversalStateGuard, ...],
    transitions: tuple[UniversalStateTransition, ...],
    closures: tuple[UniversalStateClosure, ...],
) -> None:
    machines_by_id = _index_unique_records(state_machines, "machine_id", "state_machines")
    subjects_by_id = _index_unique_records(subjects, "subject_id", "subjects")
    guards_by_id = _index_unique_records(guards, "guard_id", "guards")
    _index_unique_records(transitions, "transition_id", "transitions")
    _index_unique_records(closures, "closure_id", "closures")

    for subject in subjects:
        machine = machines_by_id.get(subject.machine_id)
        if machine is None:
            raise ValueError("subjects must reference existing machine_id values")
        if subject.current_state not in machine.states:
            raise ValueError("subject current_state must be declared in its machine states")

    for guard in guards:
        machine = machines_by_id.get(guard.machine_id)
        if machine is None:
            raise ValueError("guards must reference existing machine_id values")
        if guard.from_state not in machine.states or guard.to_state not in machine.states:
            raise ValueError("guard states must be declared in its machine states")

    for transition in transitions:
        subject = subjects_by_id.get(transition.subject_id)
        if subject is None:
            raise ValueError("transitions must reference existing subject_id values")
        if transition.machine_id != subject.machine_id:
            raise ValueError("transition machine_id must match subject machine_id")
        machine = machines_by_id[transition.machine_id]
        verdict = machine.is_legal(transition.from_state, transition.to_state, transition.action)
        if verdict is not TransitionVerdict.ALLOWED:
            raise ValueError("transition must match a legal state machine edge")
        for guard_id in transition.guard_ids:
            guard = guards_by_id.get(guard_id)
            if guard is None:
                raise ValueError("transitions must reference existing guard_id values")
            if (
                guard.machine_id != transition.machine_id
                or guard.from_state != transition.from_state
                or guard.to_state != transition.to_state
            ):
                raise ValueError("transition guard must match transition machine and states")

    for closure in closures:
        subject = subjects_by_id.get(closure.subject_id)
        if subject is None:
            raise ValueError("closures must reference existing subject_id values")
        machine = machines_by_id[subject.machine_id]
        if closure.terminal_state not in machine.terminal_states:
            raise ValueError("closure terminal_state must be terminal in the subject machine")
        if subject.current_state != closure.terminal_state:
            raise ValueError("closure terminal_state must match subject current_state")


def _index_unique_records(records: tuple[Any, ...], id_field: str, field_name: str) -> dict[str, Any]:
    indexed: dict[str, Any] = {}
    for record in records:
        record_id = getattr(record, id_field)
        if record_id in indexed:
            raise ValueError(f"{field_name} must not contain duplicate {id_field} values")
        indexed[record_id] = record
    return indexed
