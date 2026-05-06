"""Purpose: verify replayable audit reconstruction from admitted MIL terminal memory.
Governance scope: WHQR-to-learning trace reconstruction is observation-only and certificate anchored.
Dependencies: MIL terminal certificate, MIL learning admission, WHQR document, replay, and trace contracts.
Invariants: admitted episodic memory is required; trace parent-child causality is explicit; replay cannot re-execute effects.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.learning import LearningAdmissionStatus
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.replay import ReplayMode
from mcoi_runtime.contracts.whqr import Connector, ConnectorExpr, WHQRDocument, WHQRNode, WHRole
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.mil_audit_reconstruction import reconstruct_mil_audit
from mcoi_runtime.core.mil_learning_admission import admit_mil_terminal_learning
from mcoi_runtime.core.mil_terminal_certificate import certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier


def clock() -> str:
    return "2026-05-06T12:00:00+00:00"


def _whqr_doc() -> WHQRDocument:
    return WHQRDocument(
        root=ConnectorExpr(
            Connector.BECAUSE,
            WHQRNode(WHRole.WHAT, "payment_request"),
            WHQRNode(WHRole.WHY, "invoice_due"),
        )
    )


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


def _admitted():
    memory = EpisodicMemory()
    bundle = _bundle()
    admission = admit_mil_terminal_learning(bundle, memory, issued_at="2026-05-06T12:00:01Z")

    assert admission.decision.status is LearningAdmissionStatus.ADMIT
    return bundle, admission


def test_reconstructs_parent_linked_mil_audit_chain() -> None:
    bundle, admission = _admitted()
    reconstruction = reconstruct_mil_audit(
        bundle,
        admission,
        whqr_document=_whqr_doc(),
        recorded_at="2026-05-06T12:00:02Z",
    )
    event_types = tuple(entry.event_type for entry in reconstruction.trace_entries)

    assert event_types == (
        "whqr_semantic_tree",
        "policy_decision",
        "mil_program",
        "dispatch_execution",
        "terminal_certificate",
        "learning_admission",
    )
    assert reconstruction.trace_entries[0].parent_trace_id is None
    assert reconstruction.trace_entries[-1].parent_trace_id == reconstruction.trace_entries[-2].trace_id
    assert reconstruction.chain_hash.startswith("mil-audit-chain-")


def test_reconstruction_emits_observation_only_replay_record() -> None:
    bundle, admission = _admitted()
    reconstruction = reconstruct_mil_audit(
        bundle,
        admission,
        whqr_document=_whqr_doc(),
        recorded_at="2026-05-06T12:00:02Z",
    )

    assert reconstruction.replay_record.mode is ReplayMode.OBSERVATION_ONLY
    assert reconstruction.replay_record.source_hash == reconstruction.chain_hash
    assert reconstruction.replay_record.approved_effects[0].effect_id == bundle.certificate.certificate_id
    assert reconstruction.replay_record.blocked_effects == ()


def test_deferred_learning_cannot_be_reconstructed() -> None:
    memory = EpisodicMemory()
    bundle = _bundle(ExecutionOutcome.FAILED)
    admission = admit_mil_terminal_learning(bundle, memory, issued_at="2026-05-06T12:00:01Z")

    assert admission.decision.status is LearningAdmissionStatus.DEFER
    with pytest.raises(RuntimeCoreInvariantError, match="admitted learning memory"):
        reconstruct_mil_audit(bundle, admission, recorded_at="2026-05-06T12:00:02Z")
