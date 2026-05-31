"""Outcome learning bridge for governed memory projections.

Purpose: convert observed action outcomes into candidate learning records that
can be written back through governed note-memory paths.
Governance scope: outcome traceability, expected-versus-actual comparison,
future precondition recommendations, and no direct memory mutation.
Dependencies: dataclasses, compiled memory actions, note-memory mesh proof
states, and runtime invariant helpers.
Invariants: outcome learning emits records only; appending notes or changing
workflow rules requires a separate governed write path.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.memory_action_compiler import CompiledMemoryAction
from mcoi_runtime.core.note_memory_mesh import ProofState


@dataclass(frozen=True)
class OutcomeLearningRecord:
    """Projection-only learning record for one action outcome."""

    learning_record_id: str
    compiled_action_id: str
    expected_outcome: str
    actual_outcome: str
    proof_state: ProofState
    future_precondition: str
    write_back_required: bool

    def __post_init__(self) -> None:
        if not self.expected_outcome.strip() or not self.actual_outcome.strip():
            raise RuntimeCoreInvariantError("outcome learning requires expected and actual outcomes")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible learning record."""

        return {
            "learning_record_id": self.learning_record_id,
            "compiled_action_id": self.compiled_action_id,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "proof_state": self.proof_state.value,
            "future_precondition": self.future_precondition,
            "write_back_required": self.write_back_required,
            "execution_approval": False,
        }


def build_outcome_learning_record(
    *,
    compiled_action: CompiledMemoryAction,
    expected_outcome: str,
    actual_outcome: str,
) -> OutcomeLearningRecord:
    """Build a candidate learning record from an observed outcome."""

    matched = expected_outcome.strip().lower() == actual_outcome.strip().lower()
    future_precondition = "" if matched else f"Verify stronger precondition before {compiled_action.action_type}"
    learning_record_id = stable_identifier(
        "outcome-learning",
        {
            "compiled_action_id": compiled_action.compiled_action_id,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
        },
    )
    return OutcomeLearningRecord(
        learning_record_id=learning_record_id,
        compiled_action_id=compiled_action.compiled_action_id,
        expected_outcome=expected_outcome,
        actual_outcome=actual_outcome,
        proof_state=ProofState.PASS if matched else ProofState.UNKNOWN,
        future_precondition=future_precondition,
        write_back_required=not matched,
    )
