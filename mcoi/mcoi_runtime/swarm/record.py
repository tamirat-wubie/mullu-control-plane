"""Serializable audit records for governed swarm runs.

Purpose: convert supervisor, MIL, and invoice results into deterministic
proof-carrying records suitable for append-only persistence.
Governance scope: UWMA and PRS witness material for decisions, receipts,
traces, MIL verification, and closure certificates.
Dependencies: dataclasses, decimal, enum conversion, and swarm result types.
Invariants: every record has a run id, goal id, terminal decision state, and
explicit closure status.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from .contracts import SwarmClosureCertificate, SwarmInvariantViolation, utc_now_iso
from .invoice_workflow import InvoiceSwarmResult
from .supervisor import SwarmRunResult


@dataclass(frozen=True)
class SwarmAuditRecord:
    """Deterministic persisted view of one swarm run."""

    run_id: str
    goal_id: str
    tenant_id: str
    decision_verdict: str
    decision_reason: str
    verification_passed: bool
    verification_reason: str
    mil_verification_passed: bool
    mil_verification_reason: str
    closure_status: str
    closure_certificate_id: str
    proof_stamp: str
    payload: Mapping[str, Any]
    created_at: str

    def __post_init__(self) -> None:
        for field_name in ("run_id", "goal_id", "tenant_id", "decision_verdict", "decision_reason", "created_at"):
            value = getattr(self, field_name)
            if not value or not str(value).strip():
                raise SwarmInvariantViolation(f"{field_name} must be non-empty")
        if self.closure_status not in {"closed", "not_closed"}:
            raise SwarmInvariantViolation("closure_status must be closed or not_closed")
        if self.closure_status == "closed" and not self.proof_stamp:
            raise SwarmInvariantViolation("closed audit records require proof_stamp")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible record."""

        return {
            "run_id": self.run_id,
            "goal_id": self.goal_id,
            "tenant_id": self.tenant_id,
            "decision_verdict": self.decision_verdict,
            "decision_reason": self.decision_reason,
            "verification_passed": self.verification_passed,
            "verification_reason": self.verification_reason,
            "mil_verification_passed": self.mil_verification_passed,
            "mil_verification_reason": self.mil_verification_reason,
            "closure_status": self.closure_status,
            "closure_certificate_id": self.closure_certificate_id,
            "proof_stamp": self.proof_stamp,
            "payload": _json_value(self.payload),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SwarmAuditRecord":
        """Rehydrate an audit record from JSON-compatible data."""

        return cls(
            run_id=_required_text(value, "run_id"),
            goal_id=_required_text(value, "goal_id"),
            tenant_id=_required_text(value, "tenant_id"),
            decision_verdict=_required_text(value, "decision_verdict"),
            decision_reason=_required_text(value, "decision_reason"),
            verification_passed=_required_bool(value, "verification_passed"),
            verification_reason=_required_text(value, "verification_reason"),
            mil_verification_passed=_required_bool(value, "mil_verification_passed"),
            mil_verification_reason=_required_text(value, "mil_verification_reason"),
            closure_status=_required_text(value, "closure_status"),
            closure_certificate_id=_required_text(value, "closure_certificate_id", allow_empty=True),
            proof_stamp=_required_text(value, "proof_stamp", allow_empty=True),
            payload=_required_mapping(value, "payload"),
            created_at=_required_text(value, "created_at"),
        )


def invoice_result_to_audit_record(
    *,
    run_id: str,
    tenant_id: str,
    result: InvoiceSwarmResult,
    created_at: str | None = None,
) -> SwarmAuditRecord:
    """Build a persisted audit record from an invoice swarm result."""

    return _result_to_audit_record(
        run_id=run_id,
        tenant_id=tenant_id,
        swarm=result.swarm,
        mil_verification_passed=result.mil_verification.passed,
        mil_verification_reason=result.mil_verification.reason,
        mil_program=_json_value(result.mil_program),
        closure=result.closure,
        created_at=created_at,
    )


def _result_to_audit_record(
    *,
    run_id: str,
    tenant_id: str,
    swarm: SwarmRunResult,
    mil_verification_passed: bool,
    mil_verification_reason: str,
    mil_program: Mapping[str, Any],
    closure: SwarmClosureCertificate | None,
    created_at: str | None,
) -> SwarmAuditRecord:
    closure_status = "closed" if closure is not None else "not_closed"
    closure_certificate_id = closure.certificate_id if closure is not None else ""
    proof_stamp = closure.proof_stamp if closure is not None else ""
    payload = {
        "plan": _json_value(swarm.plan),
        "decision": _json_value(swarm.decision),
        "conflicts": _json_value(swarm.conflicts),
        "receipts": _json_value(swarm.receipts),
        "verification": _json_value(swarm.verification),
        "mil_program": mil_program,
        "closure": _json_value(closure) if closure is not None else None,
    }
    return SwarmAuditRecord(
        run_id=run_id,
        goal_id=swarm.plan.goal.goal_id,
        tenant_id=tenant_id,
        decision_verdict=swarm.decision.verdict.value,
        decision_reason=swarm.decision.reason,
        verification_passed=swarm.verification.passed,
        verification_reason=swarm.verification.reason,
        mil_verification_passed=mil_verification_passed,
        mil_verification_reason=mil_verification_reason,
        closure_status=closure_status,
        closure_certificate_id=closure_certificate_id,
        proof_stamp=proof_stamp,
        payload=payload,
        created_at=created_at or utc_now_iso(),
    )


def _json_value(value: Any) -> Any:
    """Convert known swarm values to JSON-compatible primitives."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return {
            field_name: _json_value(getattr(value, field_name))
            for field_name in value.__dataclass_fields__
        }
    return value


def _required_text(value: Mapping[str, Any], field_name: str, *, allow_empty: bool = False) -> str:
    """Return a required persisted text field without type coercion."""

    raw_value = value[field_name]
    if not isinstance(raw_value, str):
        raise SwarmInvariantViolation(f"{field_name} must be a string")
    text = raw_value.strip()
    if not allow_empty and not text:
        raise SwarmInvariantViolation(f"{field_name} must be non-empty")
    return text


def _required_bool(value: Mapping[str, Any], field_name: str) -> bool:
    """Return a required persisted boolean field without truthiness coercion."""

    raw_value = value[field_name]
    if not isinstance(raw_value, bool):
        raise SwarmInvariantViolation(f"{field_name} must be boolean")
    return raw_value


def _required_mapping(value: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    """Return a required persisted object field without sequence coercion."""

    raw_value = value[field_name]
    if not isinstance(raw_value, Mapping):
        raise SwarmInvariantViolation(f"{field_name} must be an object")
    return dict(raw_value)
