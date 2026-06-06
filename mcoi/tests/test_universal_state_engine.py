"""Tests for Universal State Engine contracts.

Purpose: prove universal state envelopes preserve governed lifecycle invariants.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS state closure validation.
Dependencies: mcoi_runtime.contracts.universal_state_engine and state-machine contracts.
Invariants: subjects, guards, transitions, closures, receipts, and machines remain linked.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.state import StateCategory, StateReference
from mcoi_runtime.contracts.state_machine import StateMachineSpec, TransitionRule
from mcoi_runtime.contracts.universal_state_engine import (
    UniversalStateClosure,
    UniversalStateClosureKind,
    UniversalStateEngine,
    UniversalStateGuard,
    UniversalStateGuardKind,
    UniversalStateSubject,
    UniversalStateSubjectKind,
    UniversalStateTransition,
)


TS = "2026-06-06T11:00:00+00:00"


def _machine(**overrides: object) -> StateMachineSpec:
    values = {
        "machine_id": "machine://workflow-closure-v1",
        "name": "Workflow Closure Lifecycle",
        "version": "1.0.0",
        "states": ("opened", "verified", "closed", "rolled_back"),
        "initial_state": "opened",
        "terminal_states": ("closed", "rolled_back"),
        "transitions": (
            TransitionRule(
                from_state="opened",
                to_state="verified",
                action="verify",
                guard_label="evidence_required",
                emits="workflow_verified",
            ),
            TransitionRule(
                from_state="verified",
                to_state="closed",
                action="close",
                guard_label="receipt_required",
                emits="workflow_closed",
            ),
            TransitionRule(
                from_state="verified",
                to_state="rolled_back",
                action="rollback",
                guard_label="authority_required",
                emits="workflow_rolled_back",
            ),
        ),
    }
    values.update(overrides)
    return StateMachineSpec(**values)


def _subject(**overrides: object) -> UniversalStateSubject:
    values = {
        "subject_id": "workflow://foundation-proof-thread-001",
        "subject_kind": UniversalStateSubjectKind.WORKFLOW,
        "machine_id": "machine://workflow-closure-v1",
        "current_state": "closed",
        "state_ref": StateReference(
            state_id="state://workflow/foundation-proof-thread-001/closed",
            category=StateCategory.RUNTIME,
            state_hash="sha256:use-foundation-proof-thread-001",
            captured_at=TS,
            metadata={"source": "universal-state-engine-test"},
            extensions={},
        ),
        "evidence_refs": ("evidence://state/workflow-closure-verified",),
        "updated_at": TS,
        "metadata": {"domain": "foundation_mode"},
    }
    values.update(overrides)
    return UniversalStateSubject(**values)


def _guard(**overrides: object) -> UniversalStateGuard:
    values = {
        "guard_id": "guard://workflow-close-receipt",
        "guard_kind": UniversalStateGuardKind.RECEIPT_REQUIRED,
        "machine_id": "machine://workflow-closure-v1",
        "from_state": "verified",
        "to_state": "closed",
        "required_refs": ("receipt://workflow/closure-proof-001",),
        "confidence": 1.0,
        "metadata": {"guard_label": "receipt_required"},
    }
    values.update(overrides)
    return UniversalStateGuard(**values)


def _transition(**overrides: object) -> UniversalStateTransition:
    values = {
        "transition_id": "transition://workflow/foundation-proof-thread-001/close",
        "subject_id": "workflow://foundation-proof-thread-001",
        "machine_id": "machine://workflow-closure-v1",
        "from_state": "verified",
        "to_state": "closed",
        "action": "close",
        "guard_ids": ("guard://workflow-close-receipt",),
        "receipt_refs": ("receipt://workflow/closure-proof-001",),
        "evidence_refs": ("evidence://state/workflow-closure-verified",),
        "transitioned_at": TS,
        "metadata": {"cause": "verified proof thread reached terminal closure"},
    }
    values.update(overrides)
    return UniversalStateTransition(**values)


def _closure(**overrides: object) -> UniversalStateClosure:
    values = {
        "closure_id": "closure://workflow/foundation-proof-thread-001",
        "subject_id": "workflow://foundation-proof-thread-001",
        "closure_kind": UniversalStateClosureKind.COMPLETED,
        "terminal_state": "closed",
        "receipt_refs": ("receipt://workflow/closure-proof-001",),
        "closed_at": TS,
        "metadata": {"solver_outcome": "SolvedVerified"},
    }
    values.update(overrides)
    return UniversalStateClosure(**values)


def _engine(**overrides: object) -> UniversalStateEngine:
    values = {
        "engine_id": "use-foundation-thread-001",
        "version": "use.v1",
        "generated_at": TS,
        "subjects": (_subject(),),
        "state_machines": (_machine(),),
        "guards": (_guard(),),
        "transitions": (_transition(),),
        "closures": (_closure(),),
        "receipt_refs": ("receipt://workflow/closure-proof-001", "receipt://use/engine-001"),
        "metadata": {
            "sequence": "state_transition_guard_receipt_closure",
            "foundation_mode": True,
        },
    }
    values.update(overrides)
    return UniversalStateEngine(**values)


def test_universal_state_engine_round_trips_to_json_dict() -> None:
    engine = _engine()
    payload = engine.to_json_dict()

    assert payload["engine_id"] == "use-foundation-thread-001"
    assert payload["subjects"][0]["subject_kind"] == "workflow"
    assert payload["state_machines"][0]["transitions"][1]["action"] == "close"
    assert payload["closures"][0]["terminal_state"] == "closed"


def test_universal_state_engine_rejects_subject_dangling_machine() -> None:
    dangling_subject = _subject(machine_id="machine://missing")

    with pytest.raises(ValueError, match="machine_id"):
        _engine(subjects=(dangling_subject,))


def test_universal_state_engine_rejects_illegal_transition_edge() -> None:
    illegal_transition = _transition(from_state="opened", to_state="closed", action="close")

    with pytest.raises(ValueError, match="legal state machine edge"):
        _engine(transitions=(illegal_transition,))


def test_universal_state_engine_rejects_guard_state_mismatch() -> None:
    mismatched_guard = _guard(to_state="rolled_back")

    with pytest.raises(ValueError, match="guard must match"):
        _engine(guards=(mismatched_guard,))


def test_universal_state_engine_rejects_nonterminal_closure() -> None:
    bad_closure = _closure(terminal_state="verified")

    with pytest.raises(ValueError, match="terminal_state"):
        _engine(closures=(bad_closure,))
