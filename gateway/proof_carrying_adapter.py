"""Gateway Proof-Carrying Capability Adapter - receipt-normalized execution.

Purpose: Wrap every executable gateway capability and normalize its result
    into a proof-carrying receipt before closure logic may inspect it.
Governance scope: skill, LLM, worker, and future MCP/payment/document/shell
    execution boundaries.
Dependencies: gateway command spine contracts and standard-library hashing.
Invariants:
  - Capability execution never returns only text to the closure kernel.
  - Every execution has a command-bound receipt with evidence references.
  - Missing required proof downgrades execution to review-required status.
  - Exceptions become failed receipts with causal evidence, not silent errors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Callable

from gateway.command_spine import CapabilityPassport, CommandEnvelope, GovernedAction, canonical_hash
from mcoi_runtime.contracts.execution import EffectRecord, ExecutionOutcome, ExecutionResult


class CapabilityExecutionStatus(StrEnum):
    """Normalized status for proof-carrying capability execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class ProofCarryingReceipt:
    """Receipt proving one capability execution and its observed effects."""

    execution_id: str
    command_id: str
    tenant_id: str
    actor_id: str
    capability_id: str
    capability_version: str
    idempotency_key: str
    status: CapabilityExecutionStatus
    result_summary: str
    actual_effects: tuple[dict[str, Any], ...]
    evidence_refs: tuple[str, ...]
    cost_amount: str | None = None
    cost_currency: str | None = None
    isolation_plane: str = "control"
    execution_worker_id: str | None = None
    rollback_ref: str | None = None
    compensation_ref: str | None = None
    started_at: str = ""
    completed_at: str = ""


@dataclass(frozen=True, slots=True)
class ProofCarryingExecution:
    """Capability output paired with its mandatory proof-carrying receipt."""

    result: dict[str, Any]
    receipt: ProofCarryingReceipt
    execution_result: ExecutionResult


class ProofCarryingCapabilityAdapter:
    """Execute a capability and return normalized proof evidence."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock

    def execute(
        self,
        *,
        command: CommandEnvelope,
        governed_action: GovernedAction,
        capability_passport: CapabilityPassport,
        executor: Callable[[], Any],
    ) -> ProofCarryingExecution:
        """Run an executor and attach a proof-carrying receipt."""
        started_at = self._clock()
        try:
            raw_result = executor()
        except Exception as exc:
            completed_at = self._clock()
            result = {
                "succeeded": False,
                "error": type(exc).__name__,
                "response": "Capability execution failed before proof closure.",
            }
            receipt = self._build_receipt(
                command=command,
                governed_action=governed_action,
                capability_passport=capability_passport,
                result=result,
                status=CapabilityExecutionStatus.FAILED,
                started_at=started_at,
                completed_at=completed_at,
                result_summary=f"failed:{type(exc).__name__}",
            )
            return ProofCarryingExecution(
                result=self._attach_receipt(result, receipt),
                receipt=receipt,
                execution_result=_execution_result_from_receipt(receipt),
            )

        completed_at = self._clock()
        result = _normalize_result(raw_result)
        missing_proof = _missing_required_proof(result, capability_passport)
        status = _status_from_result(result)
        if missing_proof and status is CapabilityExecutionStatus.SUCCEEDED:
            status = CapabilityExecutionStatus.REQUIRES_REVIEW
            result = {
                **result,
                "error": "missing_required_proof",
                "missing_proof_fields": missing_proof,
            }
        receipt = self._build_receipt(
            command=command,
            governed_action=governed_action,
            capability_passport=capability_passport,
            result=result,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            result_summary=_result_summary(result, status),
        )
        return ProofCarryingExecution(
            result=self._attach_receipt(result, receipt),
            receipt=receipt,
            execution_result=_execution_result_from_receipt(receipt),
        )

    def _build_receipt(
        self,
        *,
        command: CommandEnvelope,
        governed_action: GovernedAction,
        capability_passport: CapabilityPassport,
        result: dict[str, Any],
        status: CapabilityExecutionStatus,
        started_at: str,
        completed_at: str,
        result_summary: str,
    ) -> ProofCarryingReceipt:
        output_hash = canonical_hash(result)
        execution_hash = canonical_hash({
            "command_id": command.command_id,
            "capability_id": governed_action.capability,
            "capability_version": governed_action.capability_version,
            "idempotency_key": command.idempotency_key,
            "started_at": started_at,
            "output_hash": output_hash,
        })
        evidence_refs = _evidence_refs(
            command=command,
            result=result,
            output_hash=output_hash,
            capability_passport=capability_passport,
        )
        isolation_plane, worker_id = _isolation_context(result)
        return ProofCarryingReceipt(
            execution_id=f"capability-execution-{execution_hash[:16]}",
            command_id=command.command_id,
            tenant_id=command.tenant_id,
            actor_id=command.actor_id,
            capability_id=governed_action.capability,
            capability_version=governed_action.capability_version,
            idempotency_key=command.idempotency_key,
            status=status,
            result_summary=result_summary,
            actual_effects=_actual_effects(
                result,
                evidence_refs=evidence_refs,
                governed_action=governed_action,
                capability_passport=capability_passport,
                status=status,
            ),
            evidence_refs=evidence_refs,
            cost_amount=_optional_text(result.get("cost_amount")),
            cost_currency=_optional_text(result.get("cost_currency")),
            isolation_plane=isolation_plane,
            execution_worker_id=worker_id,
            rollback_ref=_optional_text(result.get("rollback_ref")),
            compensation_ref=_optional_text(result.get("compensation_ref")),
            started_at=started_at,
            completed_at=completed_at,
        )

    def _attach_receipt(
        self,
        result: dict[str, Any],
        receipt: ProofCarryingReceipt,
    ) -> dict[str, Any]:
        return {
            **result,
            "proof_carrying_receipt": asdict(receipt),
            "proof_receipt_id": receipt.execution_id,
            "receipt_status": result.get("receipt_status", receipt.status.value),
        }


def _normalize_result(raw_result: Any) -> dict[str, Any]:
    """Convert capability-specific return shapes into a JSON-like object."""
    if raw_result is None:
        return {"succeeded": False, "error": "empty_capability_result"}
    if isinstance(raw_result, dict):
        return dict(raw_result)
    content = getattr(raw_result, "content", None)
    if content is not None:
        return {
            "succeeded": bool(getattr(raw_result, "succeeded", True)),
            "content": str(content),
            "error": str(getattr(raw_result, "error", "") or ""),
        }
    return {"succeeded": True, "value": str(raw_result)}


def _status_from_result(result: dict[str, Any]) -> CapabilityExecutionStatus:
    if result.get("error"):
        return CapabilityExecutionStatus.FAILED
    if result.get("succeeded") is False or result.get("success") is False:
        return CapabilityExecutionStatus.FAILED
    raw_status = str(result.get("receipt_status", "")).strip().lower()
    if raw_status in {"requires_review", "missing_required_proof", "isolation_worker_required"}:
        return CapabilityExecutionStatus.REQUIRES_REVIEW
    return CapabilityExecutionStatus.SUCCEEDED


def _missing_required_proof(
    result: dict[str, Any],
    capability_passport: CapabilityPassport,
) -> tuple[str, ...]:
    required = capability_passport.evidence_required or capability_passport.proof_required_fields
    if not required:
        return ()
    if not (capability_passport.mutates_world or capability_passport.risk_tier == "high"):
        return ()
    return tuple(field for field in required if not result.get(field))


def _evidence_refs(
    *,
    command: CommandEnvelope,
    result: dict[str, Any],
    output_hash: str,
    capability_passport: CapabilityPassport,
) -> tuple[str, ...]:
    refs: list[str] = [
        f"command:{command.command_id}",
        f"trace:{command.trace_id}",
        f"output_hash:{output_hash}",
    ]
    for field in capability_passport.evidence_required or capability_passport.proof_required_fields:
        value = result.get(field)
        if value:
            refs.append(f"{field}:{canonical_hash({'command_id': command.command_id, 'value': str(value)})[:16]}")
    worker_receipt = result.get("capability_execution_receipt")
    if isinstance(worker_receipt, dict):
        refs.extend(str(ref) for ref in worker_receipt.get("evidence_refs", ()) if ref)
    return tuple(dict.fromkeys(refs))


def _actual_effects(
    result: dict[str, Any],
    *,
    evidence_refs: tuple[str, ...],
    governed_action: GovernedAction,
    capability_passport: CapabilityPassport,
    status: CapabilityExecutionStatus,
) -> tuple[dict[str, Any], ...]:
    effects: list[dict[str, Any]] = []
    if status is CapabilityExecutionStatus.SUCCEEDED:
        for effect_name in capability_passport.declared_effects:
            effects.append({
                "effect_id": effect_name,
                "name": effect_name,
                "observed_value": effect_name,
                "evidence_ref": evidence_refs[0] if evidence_refs else effect_name,
            })
        if capability_passport.mutates_world:
            for mutation in (
                f"{governed_action.tenant_id}:ledger_entry",
                f"{governed_action.tenant_id}:capability_effect:{capability_passport.capability}",
            ):
                effects.append({
                    "effect_id": mutation,
                    "name": mutation,
                    "observed_value": mutation,
                    "evidence_ref": evidence_refs[0] if evidence_refs else mutation,
                })
        for proof_field in capability_passport.evidence_required or capability_passport.proof_required_fields:
            observed_value = result.get(proof_field)
            evidence_ref = _evidence_ref_for_field(proof_field, evidence_refs)
            if observed_value or evidence_ref:
                effects.append({
                    "effect_id": proof_field,
                    "name": proof_field,
                    "observed_value": observed_value or proof_field,
                    "evidence_ref": evidence_ref or proof_field,
                })
    for key, value in sorted(result.items()):
        if key in {"proof_carrying_receipt"}:
            continue
        if value in (None, "", (), []):
            continue
        effects.append({
            "effect_id": key,
            "name": key,
            "observed_value": value,
            "evidence_ref": evidence_refs[0] if evidence_refs else key,
        })
    return tuple(_deduplicate_effects(effects))


def _deduplicate_effects(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduplicated: list[dict[str, Any]] = []
    for effect in effects:
        effect_id = str(effect.get("effect_id", ""))
        if effect_id in seen:
            continue
        seen.add(effect_id)
        deduplicated.append(effect)
    return deduplicated


def _evidence_ref_for_field(field: str, evidence_refs: tuple[str, ...]) -> str:
    prefixes = {
        "command_id": "command:",
        "trace_id": "trace:",
        "output_hash": "output_hash:",
    }
    prefix = prefixes.get(field, f"{field}:")
    for evidence_ref in evidence_refs:
        if evidence_ref.startswith(prefix):
            return evidence_ref
    return ""


def _execution_result_from_receipt(receipt: ProofCarryingReceipt) -> ExecutionResult:
    status = (
        ExecutionOutcome.SUCCEEDED
        if receipt.status is CapabilityExecutionStatus.SUCCEEDED
        else ExecutionOutcome.FAILED
    )
    return ExecutionResult(
        execution_id=receipt.execution_id,
        goal_id=receipt.command_id,
        status=status,
        actual_effects=tuple(
            EffectRecord(
                name=str(effect["name"]),
                details={
                    "effect_id": str(effect.get("effect_id", effect["name"])),
                    "observed_value": effect.get("observed_value"),
                    "evidence_ref": str(effect.get("evidence_ref", receipt.execution_id)),
                    "source": receipt.capability_id,
                },
            )
            for effect in receipt.actual_effects
        ),
        assumed_effects=(),
        started_at=receipt.started_at,
        finished_at=receipt.completed_at,
        metadata={
            "command_id": receipt.command_id,
            "tenant_id": receipt.tenant_id,
            "actor_id": receipt.actor_id,
            "capability_id": receipt.capability_id,
            "proof_receipt_id": receipt.execution_id,
            "isolation_plane": receipt.isolation_plane,
        },
    )


def _isolation_context(result: dict[str, Any]) -> tuple[str, str | None]:
    worker_receipt = result.get("capability_execution_receipt")
    if not isinstance(worker_receipt, dict):
        return "control", None
    return (
        str(worker_receipt.get("execution_plane", "isolated_worker")),
        str(worker_receipt.get("worker_id", "")) or None,
    )


def _result_summary(result: dict[str, Any], status: CapabilityExecutionStatus) -> str:
    if "response" in result:
        return str(result["response"])[:160]
    if "content" in result:
        return str(result["content"])[:160]
    if "error" in result and result["error"]:
        return f"{status.value}:{result['error']}"
    return status.value


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
