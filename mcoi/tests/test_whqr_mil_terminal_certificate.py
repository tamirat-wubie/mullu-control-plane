"""Purpose: verify terminal closure certificates for governed MIL dispatch results.
Governance scope: MIL dispatch closure must bind execution, verification, reconciliation, and evidence into terminal certificate.
Dependencies: MIL contracts, governed dispatch result, terminal certifier, and MIL terminal certificate adapter.
Invariants: blocked dispatches fail closed; succeeded dispatches certify committed closure with ledger evidence.
"""
from __future__ import annotations
import pytest
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.mil import MILInstruction, MILOpcode, MILProgram
from mcoi_runtime.contracts.policy import DecisionReason, PolicyDecision, PolicyDecisionStatus
from mcoi_runtime.contracts.terminal_closure import TerminalClosureDisposition
from mcoi_runtime.contracts.verification import VerificationStatus
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.mil_terminal_certificate import certify_mil_dispatch_result
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier

def clock(): return "2026-05-06T12:00:00+00:00"
def _program():
    decision=PolicyDecision("whqr:goal:allow","operator","goal",PolicyDecisionStatus.ALLOW,(DecisionReason("allowed","whqr_allow"),),"2026-05-06T11:59:00Z")
    instructions=(MILInstruction("check",MILOpcode.CHECK_POLICY,"goal"),MILInstruction("call",MILOpcode.CALL_CAPABILITY,"shell_command",depends_on=("check",)),MILInstruction("verify",MILOpcode.VERIFY_EFFECT,"goal",depends_on=("call",)),MILInstruction("proof",MILOpcode.EMIT_PROOF,"goal",depends_on=("verify",)))
    return MILProgram("mil:goal","goal",decision,instructions,"2026-05-06T11:59:01Z")
def _execution(status=ExecutionOutcome.SUCCEEDED):
    return ExecutionResult("exec-1","goal",status,(EffectRecord("process_completed",{"evidence_ref":"provider:exec-1"}),),(),"2026-05-06T11:59:02+00:00","2026-05-06T11:59:03+00:00")
def test_certifies_committed_mil_dispatch_result():
    result=GovernedDispatchResult(execution_result=_execution(),blocked=False,ledger_hash="abc123")
    bundle=certify_mil_dispatch_result(_program(),result,TerminalClosureCertifier(clock=clock))
    assert bundle.certificate.disposition is TerminalClosureDisposition.COMMITTED
    assert bundle.verification_result.status is VerificationStatus.PASS
    assert bundle.reconciliation.command_id == "mil:goal"
    assert bundle.certificate.evidence_refs == ("ledger:abc123",)
def test_blocked_mil_dispatch_cannot_receive_terminal_certificate():
    result=GovernedDispatchResult(execution_result=None,blocked=True,block_reason="policy")
    with pytest.raises(RuntimeCoreInvariantError,match="blocked MIL dispatch"):
        certify_mil_dispatch_result(_program(),result,TerminalClosureCertifier(clock=clock))
def test_failed_mil_dispatch_requires_review_certificate():
    result=GovernedDispatchResult(execution_result=_execution(ExecutionOutcome.FAILED),blocked=False,ledger_hash="def456")
    bundle=certify_mil_dispatch_result(_program(),result,TerminalClosureCertifier(clock=clock),case_id="case-1")
    assert bundle.certificate.disposition is TerminalClosureDisposition.REQUIRES_REVIEW
    assert bundle.certificate.case_id == "case-1"
    assert bundle.verification_result.status is VerificationStatus.FAIL
    assert bundle.reconciliation.case_id == "case-1"
