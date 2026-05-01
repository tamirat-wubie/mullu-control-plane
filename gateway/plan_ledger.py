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

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
import threading
from typing import Any, Callable

from gateway.command_spine import canonical_hash, capability_passport_for
from gateway.plan import CapabilityPlan, CapabilityPlanStep
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


@dataclass(frozen=True, slots=True)
class CapabilityPlanRecoveryDecision:
    """Deterministic recovery classification for a failed plan."""

    plan_id: str
    recovery_action: str
    reason: str
    failed_step_id: str
    failed_capability_id: str
    approval_required: bool
    compensation_required: bool
    review_required: bool
    retry_allowed: bool
    completed_mutating_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityPlanRecoveryAttempt:
    """Append-only witness for one plan recovery attempt."""

    attempt_id: str
    plan_id: str
    recovery_action: str
    status: str
    reason: str
    attempted_at: str
    witness_id: str = ""
    terminal_certificate_id: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CapabilityPlanEvidenceBundle:
    """Operator-exportable proof bundle for one completed capability plan."""

    bundle_id: str
    bundle_hash: str
    plan_id: str
    certificate_id: str
    disposition: str
    step_count: int
    step_command_ids: tuple[str, ...]
    step_terminal_certificate_ids: tuple[str, ...]
    plan_evidence_hash: str
    witness_ids: tuple[str, ...]
    recovery_attempt_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    exported_at: str


class CapabilityPlanLedgerStore:
    """Persistence contract for plan certificates and witness records."""

    def save_certificate(self, certificate: CapabilityPlanTerminalCertificate) -> None:
        """Persist or replace the certificate for one plan id."""
        raise NotImplementedError

    def load_certificate(self, plan_id: str) -> CapabilityPlanTerminalCertificate | None:
        """Load a plan certificate by plan id."""
        raise NotImplementedError

    def list_certificates(self) -> tuple[CapabilityPlanTerminalCertificate, ...]:
        """Return stored plan certificates."""
        return ()

    def append_witness(self, witness: CapabilityPlanWitnessRecord) -> None:
        """Append one plan witness record."""
        raise NotImplementedError

    def list_witnesses(self, plan_id: str = "") -> tuple[CapabilityPlanWitnessRecord, ...]:
        """Return witness records, optionally filtered by plan id."""
        return ()

    def append_recovery_attempt(self, attempt: CapabilityPlanRecoveryAttempt) -> None:
        """Append one recovery-attempt witness."""
        raise NotImplementedError

    def list_recovery_attempts(self, plan_id: str = "") -> tuple[CapabilityPlanRecoveryAttempt, ...]:
        """Return recovery attempts, optionally filtered by plan id."""
        return ()

    def status(self) -> dict[str, Any]:
        """Return storage health details."""
        return {"backend": "unknown", "available": False}


class InMemoryCapabilityPlanLedgerStore(CapabilityPlanLedgerStore):
    """In-memory store for local development and tests."""

    def __init__(self) -> None:
        self._certificates: dict[str, CapabilityPlanTerminalCertificate] = {}
        self._witnesses: list[CapabilityPlanWitnessRecord] = []
        self._recovery_attempts: list[CapabilityPlanRecoveryAttempt] = []

    def save_certificate(self, certificate: CapabilityPlanTerminalCertificate) -> None:
        self._certificates[certificate.plan_id] = certificate

    def load_certificate(self, plan_id: str) -> CapabilityPlanTerminalCertificate | None:
        return self._certificates.get(plan_id)

    def list_certificates(self) -> tuple[CapabilityPlanTerminalCertificate, ...]:
        return tuple(self._certificates.values())

    def append_witness(self, witness: CapabilityPlanWitnessRecord) -> None:
        self._witnesses.append(witness)

    def list_witnesses(self, plan_id: str = "") -> tuple[CapabilityPlanWitnessRecord, ...]:
        if not plan_id:
            return tuple(self._witnesses)
        return tuple(witness for witness in self._witnesses if witness.plan_id == plan_id)

    def append_recovery_attempt(self, attempt: CapabilityPlanRecoveryAttempt) -> None:
        self._recovery_attempts.append(attempt)

    def list_recovery_attempts(self, plan_id: str = "") -> tuple[CapabilityPlanRecoveryAttempt, ...]:
        if not plan_id:
            return tuple(self._recovery_attempts)
        return tuple(attempt for attempt in self._recovery_attempts if attempt.plan_id == plan_id)

    def status(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "available": True,
            "certificates": len(self._certificates),
            "witnesses": len(self._witnesses),
            "recovery_attempts": len(self._recovery_attempts),
        }


class JsonFileCapabilityPlanLedgerStore(CapabilityPlanLedgerStore):
    """JSON-file durable store for plan certificates and witness records."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write_payload({"certificates": {}, "witnesses": [], "recovery_attempts": []})

    def save_certificate(self, certificate: CapabilityPlanTerminalCertificate) -> None:
        with self._lock:
            payload = self._read_payload()
            certificates = payload.setdefault("certificates", {})
            if not isinstance(certificates, dict):
                raise ValueError("plan ledger certificates root must be an object")
            certificates[certificate.plan_id] = asdict(certificate)
            self._write_payload(payload)

    def load_certificate(self, plan_id: str) -> CapabilityPlanTerminalCertificate | None:
        payload = self._read_payload()
        raw_certificates = payload.get("certificates", {})
        if not isinstance(raw_certificates, dict):
            raise ValueError("plan ledger certificates root must be an object")
        raw_certificate = raw_certificates.get(plan_id)
        if raw_certificate is None:
            return None
        if not isinstance(raw_certificate, dict):
            raise ValueError("plan ledger certificate entry must be an object")
        return _certificate_from_mapping(raw_certificate)

    def list_certificates(self) -> tuple[CapabilityPlanTerminalCertificate, ...]:
        payload = self._read_payload()
        raw_certificates = payload.get("certificates", {})
        if not isinstance(raw_certificates, dict):
            raise ValueError("plan ledger certificates root must be an object")
        return tuple(
            _certificate_from_mapping(raw_certificate)
            for raw_certificate in raw_certificates.values()
            if isinstance(raw_certificate, dict)
        )

    def append_witness(self, witness: CapabilityPlanWitnessRecord) -> None:
        with self._lock:
            payload = self._read_payload()
            witnesses = payload.setdefault("witnesses", [])
            if not isinstance(witnesses, list):
                raise ValueError("plan ledger witnesses root must be an array")
            witnesses.append(asdict(witness))
            self._write_payload(payload)

    def list_witnesses(self, plan_id: str = "") -> tuple[CapabilityPlanWitnessRecord, ...]:
        payload = self._read_payload()
        raw_witnesses = payload.get("witnesses", [])
        if not isinstance(raw_witnesses, list):
            raise ValueError("plan ledger witnesses root must be an array")
        witnesses = tuple(
            _witness_from_mapping(raw_witness)
            for raw_witness in raw_witnesses
            if isinstance(raw_witness, dict)
        )
        if not plan_id:
            return witnesses
        return tuple(witness for witness in witnesses if witness.plan_id == plan_id)

    def append_recovery_attempt(self, attempt: CapabilityPlanRecoveryAttempt) -> None:
        with self._lock:
            payload = self._read_payload()
            attempts = payload.setdefault("recovery_attempts", [])
            if not isinstance(attempts, list):
                raise ValueError("plan ledger recovery_attempts root must be an array")
            attempts.append(asdict(attempt))
            self._write_payload(payload)

    def list_recovery_attempts(self, plan_id: str = "") -> tuple[CapabilityPlanRecoveryAttempt, ...]:
        payload = self._read_payload()
        raw_attempts = payload.get("recovery_attempts", [])
        if not isinstance(raw_attempts, list):
            raise ValueError("plan ledger recovery_attempts root must be an array")
        attempts = tuple(
            _recovery_attempt_from_mapping(raw_attempt)
            for raw_attempt in raw_attempts
            if isinstance(raw_attempt, dict)
        )
        if not plan_id:
            return attempts
        return tuple(attempt for attempt in attempts if attempt.plan_id == plan_id)

    def status(self) -> dict[str, Any]:
        payload = self._read_payload()
        certificates = payload.get("certificates", {})
        witnesses = payload.get("witnesses", [])
        recovery_attempts = payload.get("recovery_attempts", [])
        return {
            "backend": "json_file",
            "available": True,
            "path": str(self._path),
            "certificates": len(certificates) if isinstance(certificates, dict) else 0,
            "witnesses": len(witnesses) if isinstance(witnesses, list) else 0,
            "recovery_attempts": len(recovery_attempts) if isinstance(recovery_attempts, list) else 0,
        }

    def _read_payload(self) -> dict[str, Any]:
        with open(self._path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("plan ledger JSON root must be an object")
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
        temporary_path.replace(self._path)


class CapabilityPlanLedger:
    """Append-only ledger for plan-level terminal closure."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        store: CapabilityPlanLedgerStore | None = None,
    ) -> None:
        self._clock = clock
        self._store = store or InMemoryCapabilityPlanLedgerStore()

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
        self._store.save_certificate(certificate)
        self._store.append_witness(_witness_for_certificate(certificate, execution=execution, witnessed_at=issued_at))
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
            "plan_snapshot": _plan_snapshot(plan),
            "step_results": [asdict(result) for result in execution.step_results],
        }
        recovery_decision = _recovery_decision_for_failure(plan=plan, execution=execution)
        detail["recovery_decision"] = asdict(recovery_decision)
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
        self._store.append_witness(witness)
        return witness

    def certificate_for(self, plan_id: str) -> CapabilityPlanTerminalCertificate | None:
        """Return the terminal certificate for one plan id, if present."""
        return self._store.load_certificate(plan_id)

    def witnesses_for(self, plan_id: str = "") -> tuple[CapabilityPlanWitnessRecord, ...]:
        """Return append-only witness records for one plan id."""
        return self._store.list_witnesses(plan_id)

    def record_recovery_attempt(
        self,
        *,
        plan_id: str,
        recovery_action: str,
        status: str,
        reason: str,
        witness_id: str = "",
        terminal_certificate_id: str = "",
        detail: dict[str, Any] | None = None,
    ) -> CapabilityPlanRecoveryAttempt:
        """Record an append-only recovery attempt witness."""
        normalized_plan_id = plan_id.strip()
        normalized_action = recovery_action.strip()
        normalized_status = status.strip()
        normalized_reason = reason.strip()
        if not normalized_plan_id:
            raise ValueError("recovery attempt plan_id is required")
        if not normalized_action:
            raise ValueError("recovery attempt recovery_action is required")
        if not normalized_status:
            raise ValueError("recovery attempt status is required")
        if not normalized_reason:
            raise ValueError("recovery attempt reason is required")
        attempted_at = self._clock()
        attempt_detail = dict(detail or {})
        attempt_payload = {
            "plan_id": normalized_plan_id,
            "recovery_action": normalized_action,
            "status": normalized_status,
            "reason": normalized_reason,
            "witness_id": witness_id,
            "terminal_certificate_id": terminal_certificate_id,
            "attempted_at": attempted_at,
            "detail": attempt_detail,
        }
        attempt = CapabilityPlanRecoveryAttempt(
            attempt_id=f"plan-recovery-attempt-{canonical_hash(attempt_payload)[:16]}",
            plan_id=normalized_plan_id,
            recovery_action=normalized_action,
            status=normalized_status,
            reason=normalized_reason,
            attempted_at=attempted_at,
            witness_id=witness_id,
            terminal_certificate_id=terminal_certificate_id,
            detail=attempt_detail,
        )
        self._store.append_recovery_attempt(attempt)
        return attempt

    def recovery_attempts_for(self, plan_id: str = "") -> tuple[CapabilityPlanRecoveryAttempt, ...]:
        """Return recovery-attempt witness records for one plan id."""
        return self._store.list_recovery_attempts(plan_id)

    def export_evidence_bundle(self, *, plan_id: str) -> CapabilityPlanEvidenceBundle:
        """Export a deterministic operator proof bundle for a certified plan."""
        normalized_plan_id = plan_id.strip()
        if not normalized_plan_id:
            raise ValueError("plan_id is required")
        certificate = self.certificate_for(normalized_plan_id)
        if certificate is None:
            raise KeyError("plan terminal certificate not found")
        witnesses = self.witnesses_for(normalized_plan_id)
        recovery_attempts = self.recovery_attempts_for(normalized_plan_id)
        exported_at = self._clock()
        evidence_refs = _plan_bundle_evidence_refs(
            certificate=certificate,
            witnesses=witnesses,
            recovery_attempts=recovery_attempts,
        )
        witness_ids = tuple(witness.witness_id for witness in witnesses)
        recovery_attempt_ids = tuple(attempt.attempt_id for attempt in recovery_attempts)
        bundle_payload = {
            "plan_id": certificate.plan_id,
            "certificate_id": certificate.certificate_id,
            "disposition": certificate.disposition,
            "step_count": certificate.step_count,
            "step_command_ids": certificate.step_command_ids,
            "step_terminal_certificate_ids": certificate.step_terminal_certificate_ids,
            "plan_evidence_hash": certificate.evidence_hash,
            "witness_ids": witness_ids,
            "recovery_attempt_ids": recovery_attempt_ids,
            "evidence_refs": evidence_refs,
            "exported_at": exported_at,
            "bundle_type": "capability_plan_evidence_bundle_v1",
        }
        bundle_hash = canonical_hash(bundle_payload)
        return CapabilityPlanEvidenceBundle(
            bundle_id=f"plan-evidence-bundle-{bundle_hash[:16]}",
            bundle_hash=bundle_hash,
            plan_id=certificate.plan_id,
            certificate_id=certificate.certificate_id,
            disposition=certificate.disposition,
            step_count=certificate.step_count,
            step_command_ids=certificate.step_command_ids,
            step_terminal_certificate_ids=certificate.step_terminal_certificate_ids,
            plan_evidence_hash=certificate.evidence_hash,
            witness_ids=witness_ids,
            recovery_attempt_ids=recovery_attempt_ids,
            evidence_refs=evidence_refs,
            exported_at=exported_at,
        )

    def read_model(
        self,
        *,
        recovery_action: str = "",
        failed_witness_limit: int | None = None,
        failed_witness_offset: int = 0,
        recovery_attempt_status: str = "",
        recovery_attempt_limit: int | None = None,
        recovery_attempt_offset: int = 0,
    ) -> dict[str, Any]:
        """Return an operator read model for plan closure."""
        certificates = self._store.list_certificates()
        witnesses = self._store.list_witnesses()
        recovery_attempts = self._store.list_recovery_attempts()
        filtered_recovery_attempts = recovery_attempts
        failed_witnesses = tuple(witness for witness in witnesses if not witness.succeeded)
        requested_recovery_action = recovery_action.strip()
        requested_attempt_status = recovery_attempt_status.strip()
        if requested_recovery_action:
            failed_witnesses = tuple(
                witness
                for witness in failed_witnesses
                if _witness_recovery_action(witness) == requested_recovery_action
            )
        paged_failed_witnesses, failed_witness_page = _read_model_page(
            failed_witnesses,
            limit=failed_witness_limit,
            offset=failed_witness_offset,
        )
        if requested_attempt_status:
            filtered_recovery_attempts = tuple(
                attempt
                for attempt in recovery_attempts
                if attempt.status == requested_attempt_status
            )
        paged_recovery_attempts, recovery_attempt_page = _read_model_page(
            filtered_recovery_attempts,
            limit=recovery_attempt_limit,
            offset=recovery_attempt_offset,
        )
        return {
            "plan_certificate_count": len(certificates),
            "plan_witness_count": len(witnesses),
            "failed_plan_witness_count": sum(1 for witness in witnesses if not witness.succeeded),
            "recovery_action_counts": _recovery_action_counts(witnesses),
            "recovery_action_filter": requested_recovery_action,
            "failed_plan_witness_page": failed_witness_page,
            "recovery_attempt_count": len(recovery_attempts),
            "recovery_attempt_status_counts": _recovery_attempt_status_counts(recovery_attempts),
            "recovery_attempt_status_filter": requested_attempt_status,
            "recovery_attempt_page": recovery_attempt_page,
            "certificates": [asdict(certificate) for certificate in certificates],
            "failed_plan_witnesses": [asdict(witness) for witness in paged_failed_witnesses],
            "recovery_attempts": [asdict(attempt) for attempt in paged_recovery_attempts],
            "store": self._store.status(),
        }


def _validate_certifiable_execution(
    *,
    plan: CapabilityPlan,
    execution: CapabilityPlanExecutionResult,
) -> None:
    if execution.plan_id != plan.plan_id:
        raise ValueError("plan execution result does not match plan_id")
    if not execution.succeeded:
        raise ValueError("plan execution is not certifiable")
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
        raise ValueError("plan step missing terminal certificate")
    missing_command_ids = [result.step_id for result in execution.step_results if not result.command_id]
    if missing_command_ids:
        raise ValueError("plan step missing command id")
    if not execution.evidence_hash:
        raise ValueError("plan execution evidence_hash is required")


def _certificate_from_mapping(raw: dict[str, Any]) -> CapabilityPlanTerminalCertificate:
    metadata = dict(raw.get("metadata", {}))
    if isinstance(metadata.get("evidence_required"), list):
        metadata["evidence_required"] = tuple(str(item) for item in metadata["evidence_required"])
    return CapabilityPlanTerminalCertificate(
        certificate_id=str(raw["certificate_id"]),
        plan_id=str(raw["plan_id"]),
        tenant_id=str(raw["tenant_id"]),
        identity_id=str(raw["identity_id"]),
        disposition=str(raw["disposition"]),
        step_count=int(raw["step_count"]),
        step_command_ids=tuple(str(item) for item in raw["step_command_ids"]),
        step_terminal_certificate_ids=tuple(str(item) for item in raw["step_terminal_certificate_ids"]),
        evidence_hash=str(raw["evidence_hash"]),
        issued_at=str(raw["issued_at"]),
        metadata=metadata,
    )


def _plan_snapshot(plan: CapabilityPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "tenant_id": plan.tenant_id,
        "identity_id": plan.identity_id,
        "goal": plan.goal,
        "risk_tier": plan.risk_tier,
        "approval_required": plan.approval_required,
        "evidence_required": tuple(plan.evidence_required),
        "metadata": dict(plan.metadata),
        "steps": [
            {
                "step_id": step.step_id,
                "capability_id": step.capability_id,
                "params": dict(step.params),
                "depends_on": tuple(step.depends_on),
            }
            for step in plan.steps
        ],
    }


def _witness_from_mapping(raw: dict[str, Any]) -> CapabilityPlanWitnessRecord:
    return CapabilityPlanWitnessRecord(
        witness_id=str(raw["witness_id"]),
        plan_id=str(raw["plan_id"]),
        certificate_id=str(raw.get("certificate_id", "")),
        succeeded=bool(raw["succeeded"]),
        evidence_hash=str(raw["evidence_hash"]),
        witnessed_at=str(raw["witnessed_at"]),
        detail=dict(raw.get("detail", {})),
    )


def _recovery_attempt_from_mapping(raw: dict[str, Any]) -> CapabilityPlanRecoveryAttempt:
    return CapabilityPlanRecoveryAttempt(
        attempt_id=str(raw["attempt_id"]),
        plan_id=str(raw["plan_id"]),
        recovery_action=str(raw["recovery_action"]),
        status=str(raw["status"]),
        reason=str(raw["reason"]),
        attempted_at=str(raw["attempted_at"]),
        witness_id=str(raw.get("witness_id", "")),
        terminal_certificate_id=str(raw.get("terminal_certificate_id", "")),
        detail=dict(raw.get("detail", {})),
    )


def _recovery_decision_for_failure(
    *,
    plan: CapabilityPlan,
    execution: CapabilityPlanExecutionResult,
) -> CapabilityPlanRecoveryDecision:
    failed_result = next((result for result in execution.step_results if not result.succeeded), None)
    failed_step = _step_for_result(plan.steps, failed_result.step_id if failed_result is not None else "")
    failed_capability_id = failed_result.capability_id if failed_result is not None else ""
    error = failed_result.error if failed_result is not None else execution.error or "execution_failed"
    completed_mutating_capabilities = tuple(
        result.capability_id
        for result in execution.step_results
        if result.succeeded and _capability_mutates_world(result.capability_id)
    )
    if error.startswith("approval_required:"):
        return CapabilityPlanRecoveryDecision(
            plan_id=plan.plan_id,
            recovery_action="wait_for_approval",
            reason=error,
            failed_step_id=failed_step.step_id if failed_step is not None else "",
            failed_capability_id=failed_capability_id,
            approval_required=True,
            compensation_required=False,
            review_required=False,
            retry_allowed=True,
            completed_mutating_capabilities=completed_mutating_capabilities,
        )
    if completed_mutating_capabilities:
        return CapabilityPlanRecoveryDecision(
            plan_id=plan.plan_id,
            recovery_action="compensate_or_review",
            reason=error,
            failed_step_id=failed_step.step_id if failed_step is not None else "",
            failed_capability_id=failed_capability_id,
            approval_required=False,
            compensation_required=True,
            review_required=True,
            retry_allowed=False,
            completed_mutating_capabilities=completed_mutating_capabilities,
        )
    if error.startswith(("plan_step_capability_admission_rejected:", "plan_step_command_binding_rejected:")):
        return CapabilityPlanRecoveryDecision(
            plan_id=plan.plan_id,
            recovery_action="operator_review",
            reason=error,
            failed_step_id=failed_step.step_id if failed_step is not None else "",
            failed_capability_id=failed_capability_id,
            approval_required=False,
            compensation_required=False,
            review_required=True,
            retry_allowed=False,
            completed_mutating_capabilities=completed_mutating_capabilities,
        )
    return CapabilityPlanRecoveryDecision(
        plan_id=plan.plan_id,
        recovery_action="retry_or_review",
        reason=error,
        failed_step_id=failed_step.step_id if failed_step is not None else "",
        failed_capability_id=failed_capability_id,
        approval_required=False,
        compensation_required=False,
        review_required=True,
        retry_allowed=True,
        completed_mutating_capabilities=completed_mutating_capabilities,
    )


def _step_for_result(
    steps: tuple[CapabilityPlanStep, ...],
    step_id: str,
) -> CapabilityPlanStep | None:
    return next((step for step in steps if step.step_id == step_id), None)


def _capability_mutates_world(capability_id: str) -> bool:
    try:
        return capability_passport_for(capability_id).mutates_world
    except ValueError:
        return False


def _recovery_action_counts(witnesses: tuple[CapabilityPlanWitnessRecord, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for witness in witnesses:
        decision = witness.detail.get("recovery_decision")
        if not isinstance(decision, dict):
            continue
        action = str(decision.get("recovery_action", "")).strip()
        if action:
            counts[action] = counts.get(action, 0) + 1
    return dict(sorted(counts.items()))


def _recovery_attempt_status_counts(attempts: tuple[CapabilityPlanRecoveryAttempt, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attempt in attempts:
        status = attempt.status.strip()
        if status:
            counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _read_model_page(
    items: tuple[Any, ...],
    *,
    limit: int | None,
    offset: int,
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    normalized_offset = max(0, int(offset))
    total = len(items)
    if limit is None:
        normalized_limit = total
    else:
        normalized_limit = max(1, int(limit))
    page = items[normalized_offset:normalized_offset + normalized_limit]
    next_offset = normalized_offset + len(page)
    return page, {
        "total": total,
        "limit": normalized_limit,
        "offset": normalized_offset,
        "next_offset": next_offset if next_offset < total else None,
    }


def _witness_recovery_action(witness: CapabilityPlanWitnessRecord) -> str:
    decision = witness.detail.get("recovery_decision")
    if not isinstance(decision, dict):
        return ""
    return str(decision.get("recovery_action", "")).strip()


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


def _plan_bundle_evidence_refs(
    *,
    certificate: CapabilityPlanTerminalCertificate,
    witnesses: tuple[CapabilityPlanWitnessRecord, ...],
    recovery_attempts: tuple[CapabilityPlanRecoveryAttempt, ...],
) -> tuple[str, ...]:
    refs: list[str] = [
        f"plan_terminal_certificate:{certificate.certificate_id}",
        f"plan_evidence_hash:{certificate.evidence_hash}",
    ]
    refs.extend(f"step_command:{command_id}" for command_id in certificate.step_command_ids)
    refs.extend(
        f"step_terminal_certificate:{certificate_id}"
        for certificate_id in certificate.step_terminal_certificate_ids
    )
    refs.extend(f"plan_witness:{witness.witness_id}" for witness in witnesses)
    refs.extend(f"plan_recovery_attempt:{attempt.attempt_id}" for attempt in recovery_attempts)
    deduped: list[str] = []
    for ref in refs:
        if ref not in deduped:
            deduped.append(ref)
    return tuple(deduped)


def build_capability_plan_ledger_from_env(
    *,
    clock: Callable[[], str],
) -> CapabilityPlanLedger:
    """Create a plan ledger using gateway persistence environment variables."""
    backend = os.environ.get("MULLU_PLAN_LEDGER_BACKEND", "").strip().lower()
    path = os.environ.get("MULLU_PLAN_LEDGER_PATH", "").strip()
    if not backend:
        backend = "json_file" if path else "memory"
    if backend in {"memory", "in_memory"}:
        store: CapabilityPlanLedgerStore = InMemoryCapabilityPlanLedgerStore()
    elif backend in {"json", "json_file"}:
        if not path:
            raise ValueError("MULLU_PLAN_LEDGER_PATH is required for json_file plan ledger backend")
        store = JsonFileCapabilityPlanLedgerStore(path)
    else:
        raise ValueError("unsupported plan ledger backend")
    return CapabilityPlanLedger(clock=clock, store=store)
