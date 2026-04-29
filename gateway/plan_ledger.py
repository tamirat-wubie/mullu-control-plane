"""Gateway capability plan ledger.

Purpose: Record governed multi-step plan closure and issue plan-level
    terminal certificates after all step commands have terminal closure.
Governance scope: plan execution proof, terminal certificate aggregation, and
    append-only plan witness records.
Dependencies: gateway capability plan contracts, plan executor, canonical
    command spine hashing.
Invariants:
  - A plan certificate is issued only for a successful execution result.
  - Every plan step must have a terminal certificate id.
  - Certificate identity is derived from canonical plan and execution evidence.
  - Plan witness records are append-only and addressable by plan id.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from gateway.command_spine import canonical_hash
from gateway.plan import CapabilityPlan
from gateway.plan_executor import CapabilityPlanExecutionResult


@dataclass(frozen=True, slots=True)
class CapabilityPlanTerminalCertificate:
    """Terminal proof envelope for a completed capability plan."""

    certificate_id: str
    plan_id: str
    tenant_id: str
    identity_id: str
    disposition: str
    step_count: int
    step_command_ids: tuple[str, ...]
    step_terminal_certificate_ids: tuple[str, ...]
    evidence_hash: str
    issued_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CapabilityPlanWitnessRecord:
    """Append-only witness for one plan certification decision."""

    witness_id: str
    plan_id: str
    certificate_id: str
    succeeded: bool
    evidence_hash: str
    witnessed_at: str
    detail: dict[str, Any] = field(default_factory=dict)


class CapabilityPlanLedger:
    """In-memory append-only ledger for plan-level terminal closure."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._certificates: dict[str, CapabilityPlanTerminalCertificate] = {}
        self._witnesses: list[CapabilityPlanWitnessRecord] = []

    def certify(
        self,
        *,
        plan: CapabilityPlan,
        execution: CapabilityPlanExecutionResult,
    ) -> CapabilityPlanTerminalCertificate:
        """Issue and record a plan-level terminal certificate."""
        _validate_certifiable_execution(plan=plan, execution=execution)
        issued_at = self._clock()
        step_command_ids = tuple(result.command_id for result in execution.step_results)
        certificate_payload = {
            "plan_id": plan.plan_id,
            "tenant_id": plan.tenant_id,
            "identity_id": plan.identity_id,
            "goal_hash": canonical_hash({"goal": plan.goal}),
            "step_count": len(plan.steps),
            "step_command_ids": step_command_ids,
            "step_terminal_certificate_ids": execution.terminal_certificate_ids,
            "evidence_hash": execution.evidence_hash,
            "issued_at": issued_at,
        }
        certificate_id = f"plan-cert-{canonical_hash(certificate_payload)[:16]}"
        certificate = CapabilityPlanTerminalCertificate(
            certificate_id=certificate_id,
            plan_id=plan.plan_id,
            tenant_id=plan.tenant_id,
            identity_id=plan.identity_id,
            disposition="committed",
            step_count=len(plan.steps),
            step_command_ids=step_command_ids,
            step_terminal_certificate_ids=execution.terminal_certificate_ids,
            evidence_hash=execution.evidence_hash,
            issued_at=issued_at,
            metadata={
                "risk_tier": plan.risk_tier,
                "approval_required": plan.approval_required,
                "evidence_required": plan.evidence_required,
            },
        )
        self._certificates[plan.plan_id] = certificate
        self._witnesses.append(_witness_for_certificate(certificate, execution=execution, witnessed_at=issued_at))
        return certificate

    def record_failure(
        self,
        *,
        plan: CapabilityPlan,
        execution: CapabilityPlanExecutionResult,
    ) -> CapabilityPlanWitnessRecord:
        """Record a non-terminal plan failure witness without issuing a certificate."""
        if execution.plan_id != plan.plan_id:
            raise ValueError("plan execution result does not match plan_id")
        witnessed_at = self._clock()
        detail = {
            "cause": "plan_execution_failed",
            "error": execution.error or "execution_failed",
            "step_results": [asdict(result) for result in execution.step_results],
        }
        witness_payload = {
            "plan_id": plan.plan_id,
            "succeeded": False,
            "evidence_hash": execution.evidence_hash,
            "witnessed_at": witnessed_at,
            "detail": detail,
        }
        witness = CapabilityPlanWitnessRecord(
            witness_id=f"plan-witness-{canonical_hash(witness_payload)[:16]}",
            plan_id=plan.plan_id,
            certificate_id="",
            succeeded=False,
            evidence_hash=execution.evidence_hash,
            witnessed_at=witnessed_at,
            detail=detail,
        )
        self._witnesses.append(witness)
        return witness

    def certificate_for(self, plan_id: str) -> CapabilityPlanTerminalCertificate | None:
        """Return the terminal certificate for one plan id, if present."""
        return self._certificates.get(plan_id)

    def witnesses_for(self, plan_id: str) -> tuple[CapabilityPlanWitnessRecord, ...]:
        """Return append-only witness records for one plan id."""
        return tuple(witness for witness in self._witnesses if witness.plan_id == plan_id)

    def read_model(self) -> dict[str, Any]:
        """Return an operator read model for plan closure."""
        return {
            "plan_certificate_count": len(self._certificates),
            "plan_witness_count": len(self._witnesses),
            "failed_plan_witness_count": sum(1 for witness in self._witnesses if not witness.succeeded),
            "certificates": [asdict(certificate) for certificate in self._certificates.values()],
        }


def _validate_certifiable_execution(
    *,
    plan: CapabilityPlan,
    execution: CapabilityPlanExecutionResult,
) -> None:
    if execution.plan_id != plan.plan_id:
        raise ValueError("plan execution result does not match plan_id")
    if not execution.succeeded:
        raise ValueError(f"plan execution is not certifiable: {execution.error or 'execution_failed'}")
    if len(execution.step_results) != len(plan.steps):
        raise ValueError("plan execution result must include every plan step")
    expected_step_ids = tuple(step.step_id for step in plan.steps)
    observed_step_ids = tuple(result.step_id for result in execution.step_results)
    if observed_step_ids != expected_step_ids:
        raise ValueError("plan execution step order does not match plan")
    missing_certificates = [
        result.step_id
        for result in execution.step_results
        if not result.terminal_certificate_id
    ]
    if missing_certificates:
        raise ValueError(f"plan step missing terminal certificate: {missing_certificates[0]}")
    missing_command_ids = [result.step_id for result in execution.step_results if not result.command_id]
    if missing_command_ids:
        raise ValueError(f"plan step missing command id: {missing_command_ids[0]}")
    if not execution.evidence_hash:
        raise ValueError("plan execution evidence_hash is required")


def _witness_for_certificate(
    certificate: CapabilityPlanTerminalCertificate,
    *,
    execution: CapabilityPlanExecutionResult,
    witnessed_at: str,
) -> CapabilityPlanWitnessRecord:
    detail = {
        "cause": "plan_terminal_certificate_issued",
        "terminal_certificate_ids": certificate.step_terminal_certificate_ids,
        "execution_error": execution.error,
    }
    witness_payload = {
        "plan_id": certificate.plan_id,
        "certificate_id": certificate.certificate_id,
        "succeeded": execution.succeeded,
        "evidence_hash": certificate.evidence_hash,
        "witnessed_at": witnessed_at,
        "detail": detail,
    }
    return CapabilityPlanWitnessRecord(
        witness_id=f"plan-witness-{canonical_hash(witness_payload)[:16]}",
        plan_id=certificate.plan_id,
        certificate_id=certificate.certificate_id,
        succeeded=execution.succeeded,
        evidence_hash=certificate.evidence_hash,
        witnessed_at=witnessed_at,
        detail=detail,
    )
