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
from mcoi_runtime.contracts.whqr import (
    Connector,
    ConnectorExpr,
    EvidenceGate,
    GateResult,
    TruthGate,
    WHQRDocument,
    WHQRNode,
    WHRole,
)
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory import EpisodicMemory
from mcoi_runtime.core.mil_audit_reconstruction import reconstruct_mil_audit
from mcoi_runtime.core.mil_learning_admission import admit_mil_terminal_learning
from mcoi_runtime.core.mil_terminal_certificate import certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.whqr.governance import build_policy_decision


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


def _legacy_decision() -> PolicyDecision:
    return PolicyDecision(
        "whqr:goal:allow",
        "operator",
        "goal",
        PolicyDecisionStatus.ALLOW,
        (DecisionReason("allowed", "whqr_allow"),),
        "2026-05-06T11:59:00Z",
    )


def _replay_decision() -> PolicyDecision:
    return build_policy_decision(
        _whqr_doc().root,
        subject_id="operator",
        issued_at="2026-05-06T11:59:00Z",
        goal_id="goal",
        context=WHQREvaluationContext(
            node_results={
                "payment_request": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
                "invoice_due": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
            }
        ),
    )


def _program(decision: PolicyDecision | None = None) -> MILProgram:
    decision = decision if decision is not None else _legacy_decision()
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


def _admitted(decision: PolicyDecision | None = None):
    memory = EpisodicMemory()
    bundle = (
        certify_mil_dispatch_result(
            _program(decision),
            GovernedDispatchResult(execution_result=_execution(), blocked=False, ledger_hash="abc123"),
            TerminalClosureCertifier(clock=clock),
            case_id="case-1",
        )
        if decision is not None
        else _bundle()
    )
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


def test_reconstruction_imports_embedded_whqr_replay_document() -> None:
    decision = _replay_decision()
    bundle, admission = _admitted(decision)
    reconstruction = reconstruct_mil_audit(
        bundle,
        admission,
        recorded_at="2026-05-06T12:00:02Z",
    )
    semantic_entry = reconstruction.trace_entries[0]

    assert semantic_entry.event_type == "whqr_semantic_tree"
    assert semantic_entry.metadata["anchor"] == decision.metadata["whqr_canonical_hash"]
    assert semantic_entry.metadata["whqr_version"] == decision.metadata["whqr_version"]
    assert semantic_entry.metadata["whqr_semantics_hash"] == decision.metadata["whqr_semantics_hash"]


def test_reconstruction_rejects_tampered_embedded_whqr_replay_document() -> None:
    decision = _replay_decision()
    metadata = dict(decision.metadata)
    metadata["whqr_canonical_json"] = metadata["whqr_canonical_json"].replace("payment_request", "delete_file")
    tampered_decision = PolicyDecision(
        decision.decision_id,
        decision.subject_id,
        decision.goal_id,
        decision.status,
        decision.reasons,
        decision.issued_at,
        metadata=metadata,
    )
    with pytest.raises(RuntimeCoreInvariantError, match="WHQR replay document is invalid"):
        _admitted(tampered_decision)


def test_reconstruction_rejects_explicit_whqr_document_metadata_mismatch() -> None:
    decision = _replay_decision()
    bundle, admission = _admitted(decision)
    mismatched_document = WHQRDocument(root=WHQRNode(WHRole.WHAT, "other_request"))

    with pytest.raises(RuntimeCoreInvariantError, match="does not match policy metadata"):
        reconstruct_mil_audit(
            bundle,
            admission,
            whqr_document=mismatched_document,
            recorded_at="2026-05-06T12:00:02Z",
        )


def test_reconstruction_requires_replay_metadata_without_explicit_document() -> None:
    bundle, admission = _admitted()

    with pytest.raises(RuntimeCoreInvariantError, match="whqr_canonical_hash"):
        reconstruct_mil_audit(bundle, admission, recorded_at="2026-05-06T12:00:02Z")


def test_deferred_learning_cannot_be_reconstructed() -> None:
    memory = EpisodicMemory()
    bundle = _bundle(ExecutionOutcome.FAILED)
    admission = admit_mil_terminal_learning(bundle, memory, issued_at="2026-05-06T12:00:01Z")

    assert admission.decision.status is LearningAdmissionStatus.DEFER
    with pytest.raises(RuntimeCoreInvariantError, match="admitted learning memory"):
        reconstruct_mil_audit(bundle, admission, recorded_at="2026-05-06T12:00:02Z")
