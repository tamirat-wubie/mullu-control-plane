"""Purpose: verify terminal closure certificates for governed MIL dispatch results.
Governance scope: MIL dispatch closure must bind execution, verification, reconciliation, evidence, and WHQR replay metadata.
Dependencies: MIL contracts, governed dispatch result, terminal certifier, WHQR governance, and MIL terminal certificate adapter.
Invariants: blocked dispatches fail closed; succeeded dispatches certify committed closure with ledger evidence and verified WHQR replay binding when present.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.contracts.verification import VerificationStatus
from mcoi_runtime.contracts.whqr import EvidenceGate, GateResult, TruthGate, WHQRDocument, WHQRNode, WHRole
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.mil_terminal_certificate import certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext
from mcoi_runtime.whqr.governance import build_policy_decision


def clock() -> str:
    return "2026-05-06T12:00:00+00:00"


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
        WHQRNode(WHRole.WHAT, "payment_request"),
        subject_id="operator",
        issued_at="2026-05-06T11:59:00Z",
        goal_id="goal",
        context=WHQREvaluationContext(
            node_results={"payment_request": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN)}
        ),
    )


def _program(decision: PolicyDecision | None = None) -> MILProgram:
    instructions = (
        MILInstruction("check", MILOpcode.CHECK_POLICY, "goal"),
        MILInstruction("call", MILOpcode.CALL_CAPABILITY, "shell_command", depends_on=("check",)),
        MILInstruction("verify", MILOpcode.VERIFY_EFFECT, "goal", depends_on=("call",)),
        MILInstruction("proof", MILOpcode.EMIT_PROOF, "goal", depends_on=("verify",)),
    )
    return MILProgram("mil:goal", "goal", decision or _legacy_decision(), instructions, "2026-05-06T11:59:01Z")


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


def test_certifies_committed_mil_dispatch_result() -> None:
    result = GovernedDispatchResult(execution_result=_execution(), blocked=False, ledger_hash="abc123")
    bundle = certify_mil_dispatch_result(_program(), result, TerminalClosureCertifier(clock=clock))

    assert bundle.certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert bundle.verification_result.status is VerificationStatus.PASS
    assert bundle.reconciliation.command_id == "mil:goal"
    assert bundle.certificate.evidence_refs == ("ledger:abc123",)


def test_terminal_certificate_preserves_verified_whqr_replay_binding() -> None:
    decision = _replay_decision()
    result = GovernedDispatchResult(execution_result=_execution(), blocked=False, ledger_hash="abc123")
    bundle = certify_mil_dispatch_result(_program(decision), result, TerminalClosureCertifier(clock=clock))
    metadata = bundle.certificate.metadata
    replay_document = WHQRDocument.from_canonical_json(
        metadata["whqr_canonical_json"],
        expected_canonical_hash=metadata["whqr_canonical_hash"],
    )

    assert bundle.certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert metadata["whqr_canonical_hash"] == decision.metadata["whqr_canonical_hash"]
    assert metadata["whqr_semantics_hash"] == decision.metadata["whqr_semantics_hash"]
    assert metadata["whqr_version"] == decision.metadata["whqr_version"]
    assert replay_document.canonical_hash() == decision.metadata["whqr_canonical_hash"]


def test_terminal_certificate_rejects_tampered_whqr_replay_binding() -> None:
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
    result = GovernedDispatchResult(execution_result=_execution(), blocked=False, ledger_hash="abc123")

    with pytest.raises(RuntimeCoreInvariantError, match="WHQR replay document is invalid"):
        certify_mil_dispatch_result(_program(tampered_decision), result, TerminalClosureCertifier(clock=clock))


def test_blocked_mil_dispatch_cannot_receive_terminal_certificate() -> None:
    result = GovernedDispatchResult(execution_result=None, blocked=True, block_reason="policy")

    with pytest.raises(RuntimeCoreInvariantError, match="blocked MIL dispatch"):
        certify_mil_dispatch_result(_program(), result, TerminalClosureCertifier(clock=clock))


def test_failed_mil_dispatch_requires_review_certificate() -> None:
    result = GovernedDispatchResult(
        execution_result=_execution(ExecutionOutcome.FAILED),
        blocked=False,
        ledger_hash="def456",
    )
    bundle = certify_mil_dispatch_result(_program(), result, TerminalClosureCertifier(clock=clock), case_id="case-1")

    assert bundle.certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
    assert bundle.certificate.case_id == "case-1"
    assert bundle.verification_result.status is VerificationStatus.FAIL
    assert bundle.reconciliation.case_id == "case-1"
