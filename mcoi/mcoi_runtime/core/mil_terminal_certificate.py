"""Purpose: issue terminal closure certificates for governed MIL dispatch results.
Governance scope: close MIL execution only after governed dispatch, verification synthesis, and effect reconciliation.
Dependencies: MIL contracts, governed dispatcher result, verification, effect assurance, evidence, and terminal closure certifier.
Invariants: blocked or missing execution results fail closed; committed certificates require succeeded execution and MATCH reconciliation.
"""
from __future__ import annotations
from dataclasses import dataclass
from mcoi_runtime.contracts.effect_assurance import EffectReconciliation, ReconciliationStatus
from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.contracts.execution import ExecutionOutcome, ExecutionResult
from mcoi_runtime.contracts.mil import MILProgram
from mcoi_runtime.contracts.terminal_closure import TerminalClosureCertificate
from mcoi_runtime.contracts.verification import VerificationCheck, VerificationResult, VerificationStatus
from mcoi_runtime.core.governed_dispatcher import GovernedDispatchResult
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.terminal_closure import TerminalClosureCertifier

@dataclass(frozen=True, slots=True)
class MILTerminalCertificateBundle:
    program: MILProgram
    execution_result: ExecutionResult
    verification_result: VerificationResult
    reconciliation: EffectReconciliation
    certificate: TerminalClosureCertificate

def certify_mil_dispatch_result(program:MILProgram, dispatch_result:GovernedDispatchResult, certifier:TerminalClosureCertifier, *, case_id:str|None=None)->MILTerminalCertificateBundle:
    if dispatch_result.blocked:
        raise RuntimeCoreInvariantError("blocked MIL dispatch cannot receive terminal closure certificate")
    if dispatch_result.execution_result is None:
        raise RuntimeCoreInvariantError("MIL terminal closure requires execution result")
    execution=dispatch_result.execution_result
    verification=_verification(program, execution, dispatch_result)
    reconciliation=_reconciliation(program, execution, verification, case_id)
    if execution.status is ExecutionOutcome.SUCCEEDED:
        certificate=certifier.certify_committed(execution_result=execution, verification_result=verification, reconciliation=reconciliation, evidence_refs=_evidence_refs(verification), graph_refs=(f"mil:{program.program_id}", f"goal:{program.goal_id}"))
    else:
        certificate=certifier.certify_requires_review(execution_result=execution, verification_result=verification, reconciliation=reconciliation, case_id=case_id or f"case:{program.program_id}", evidence_refs=_evidence_refs(verification), graph_refs=(f"mil:{program.program_id}", f"goal:{program.goal_id}"))
    return MILTerminalCertificateBundle(program, execution, verification, reconciliation, certificate)

def _verification(program:MILProgram, execution:ExecutionResult, dispatch_result:GovernedDispatchResult)->VerificationResult:
    status=VerificationStatus.PASS if execution.status is ExecutionOutcome.SUCCEEDED else VerificationStatus.FAIL
    evidence_uri=f"ledger:{dispatch_result.ledger_hash}" if dispatch_result.ledger_hash else f"execution:{execution.execution_id}"
    return VerificationResult(verification_id=stable_identifier("mil-verification", {"program_id":program.program_id,"execution_id":execution.execution_id,"status":status.value}), execution_id=execution.execution_id, status=status, checks=(VerificationCheck("mil-dispatch-result", status, {"execution_status":execution.status.value}),), evidence=(EvidenceRecord("MIL governed dispatch evidence", evidence_uri),), closed_at=execution.finished_at, metadata={"program_id":program.program_id,"goal_id":program.goal_id})

def _reconciliation(program:MILProgram, execution:ExecutionResult, verification:VerificationResult, case_id:str|None)->EffectReconciliation:
    matched=tuple(effect.name for effect in execution.actual_effects) if execution.status is ExecutionOutcome.SUCCEEDED else ()
    missing=() if execution.status is ExecutionOutcome.SUCCEEDED else ("mil_effect_commit",)
    status=ReconciliationStatus.MATCH if execution.status is ExecutionOutcome.SUCCEEDED else ReconciliationStatus.MISMATCH
    return EffectReconciliation(reconciliation_id=stable_identifier("mil-reconciliation", {"program_id":program.program_id,"execution_id":execution.execution_id,"status":status.value}), command_id=program.program_id, effect_plan_id=f"mil-effect-plan:{program.program_id}", status=status, matched_effects=matched or ("mil_dispatch_completed",), missing_effects=missing, unexpected_effects=(), verification_result_id=verification.verification_id, case_id=None if status is ReconciliationStatus.MATCH else (case_id or f"case:{program.program_id}"), decided_at=execution.finished_at)

def _evidence_refs(verification:VerificationResult)->tuple[str,...]:
    refs=tuple(e.uri for e in verification.evidence if e.uri)
    if not refs:
        raise RuntimeCoreInvariantError("MIL terminal closure requires evidence references")
    return refs
