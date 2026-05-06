"""Purpose: verify MIL terminal learning admission and memory anchoring.
Governance scope: only terminally certified MIL closures may enter episodic memory.
Dependencies: MIL learning admission, terminal certificate adapter, memory, and terminal closure certifier.
Invariants: committed closures admit; review closures defer; mismatched certificates fail closed.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory, MemoryTier
from mcoi_runtime.core.mil_learning_admission import admit_mil_terminal_learning
from mcoi_runtime.core.mil_terminal_certificate import certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier


def clock() -> str:
    return "2026-05-06T12:00:00+00:00"


def _program() -> MILProgram:
    decision = PolicyDecision(
        "whqr:goal:allow",
        "operator",
        "goal",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "whqr_allow"),),
        "2026-05-06T11:59:00Z",
    )
    instructions = (
        MILInstruction("check", MILOpcode.CHECK_POLICY, "goal"),
        MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
        MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "goal", depends_on=("call",)),
        MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal", depends_on=("verify",)),
    )
    return MILProgram("mil:goal", "goal", decision, instructions, "2026-05-06T11:59:01Z")


def _execution(status: ExecutionOutcome = ExecutionOutcome.SUCCEEDED) -> ExecutionResult:
    return ExecutionResult(
        "exec-1",
        "goal",
        status,
        (EffectRecord("process_completed", {"evidence_ref": "provider:exec-1"}),),
        (),
        "2026-05-06T11:59:02+00:00",
        "2026-05-06T11:59:03+00:00",
    )


def _bundle(status: ExecutionOutcome = ExecutionOutcome.SUCCEEDED):
    return certify_mil_dispatch_result(
        _program(),
        GovernedDispatchResult(execution_result=_execution(status), blocked=False, ledger_hash="abc123"),
        TerminalClosureCertifier(clock=clock),
        case_id="case-1",
    )


def test_committed_mil_terminal_closure_admits_to_episodic_memory() -> None:
    episodic = EpisodicMemory()
    result = admit_mil_terminal_learning(_bundle(), episodic, issued_at="2026-05-06T12:00:01Z")

    assert result.decision.status is LearningAdmissionStatus.ADMIT
    assert result.memory_entry is not None
    assert result.memory_entry.tier is MemoryTier.EPISODIC
    assert episodic.size == 1
    assert result.memory_entry.content["certificate_id"] == result.decision.extensions["certificate_id"]


def test_review_mil_terminal_closure_defers_learning_without_memory() -> None:
    episodic = EpisodicMemory()
    result = admit_mil_terminal_learning(
        _bundle(ExecutionOutcome.FAILED),
        episodic,
        issued_at="2026-05-06T12:00:01Z",
    )

    assert result.decision.status is LearningAdmissionStatus.DEFER
    assert result.memory_entry is None
    assert episodic.size == 0
    assert result.decision.metadata["disposition"] == "requires_review"


def test_mismatched_certificate_bundle_fails_closed() -> None:
    bundle = _bundle()
    bad_certificate = replace(bundle.certificate, command_id="mil:other")
    bad_bundle = replace(bundle, certificate=bad_certificate)

    with pytest.raises(RuntimeCoreInvariantError, match="command mismatch"):
        admit_mil_terminal_learning(bad_bundle, EpisodicMemory(), issued_at="2026-05-06T12:00:01Z")
