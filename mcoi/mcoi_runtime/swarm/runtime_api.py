"""Framework-neutral runtime entry point for governed swarm work.

Purpose: expose invoice swarm execution and audit lookup through JSON-compatible
request and response envelopes.
Governance scope: typed request validation, supervisor execution, MIL static
verification, append-only audit persistence, and proof readback.
Dependencies: decimal parsing, pathlib, invoice workflow, audit records, and
audit store.
Invariants: every accepted run is persisted, lookup is read-only, and invalid
requests return explicit governed errors instead of silent failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from .audit_store import SwarmAuditStore
from .contracts import SwarmInvariantViolation
from .invoice_workflow import InvoiceSwarmRequest, run_invoice_swarm
from .record import SwarmAuditRecord, invoice_result_to_audit_record


@dataclass(frozen=True)
class RuntimeEnvelope:
    """JSON-compatible runtime response envelope."""

    governed: bool
    ok: bool
    status: str
    payload: Mapping[str, Any]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible response."""

        return {
            "governed": self.governed,
            "ok": self.ok,
            "status": self.status,
            "payload": dict(self.payload),
            "error": self.error,
        }


class InvoiceSwarmRuntime:
    """Runtime facade for governed invoice swarm runs."""

    def __init__(self, audit_store: SwarmAuditStore) -> None:
        self.audit_store = audit_store

    @classmethod
    def from_path(cls, path: str | Path) -> "InvoiceSwarmRuntime":
        """Create a runtime facade backed by a JSONL audit path."""

        return cls(SwarmAuditStore(Path(path)))

    def run_invoice(self, request_body: Mapping[str, Any]) -> RuntimeEnvelope:
        """Validate, execute, persist, and return a governed invoice swarm run."""

        try:
            run_id = _required_text(request_body, "run_id")
            request = _invoice_request_from_mapping(request_body)
            result = run_invoice_swarm(request)
            record = invoice_result_to_audit_record(
                run_id=run_id,
                tenant_id=request.tenant_id,
                result=result,
            )
            self.audit_store.append(record)
            return RuntimeEnvelope(
                governed=True,
                ok=True,
                status=record.closure_status,
                payload={"record": record.to_dict()},
            )
        except (KeyError, ValueError, InvalidOperation, SwarmInvariantViolation) as exc:
            return RuntimeEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def get_run(self, run_id: str) -> RuntimeEnvelope:
        """Read one persisted swarm run by id."""

        record = self.audit_store.get(run_id)
        if record is None:
            return RuntimeEnvelope(
                governed=True,
                ok=False,
                status="not_found",
                payload={},
                error=f"unknown run_id: {run_id}",
            )
        return RuntimeEnvelope(
            governed=True,
            ok=True,
            status=record.closure_status,
            payload={"record": record.to_dict()},
        )

    def list_runs(self) -> RuntimeEnvelope:
        """Read all persisted swarm runs in append order."""

        records = [record.to_dict() for record in self.audit_store.list_records()]
        return RuntimeEnvelope(
            governed=True,
            ok=True,
            status="listed",
            payload={"records": records, "count": len(records)},
        )


def _invoice_request_from_mapping(value: Mapping[str, Any]) -> InvoiceSwarmRequest:
    """Build an invoice request from a JSON-like mapping."""

    return InvoiceSwarmRequest(
        goal_id=_required_text(value, "goal_id"),
        tenant_id=_required_text(value, "tenant_id"),
        invoice_ref=_required_text(value, "invoice_ref"),
        invoice_amount_usd=Decimal(str(value["invoice_amount_usd"])),
        vendor_verified=_required_bool(value, "vendor_verified"),
        duplicate_found=_required_bool(value, "duplicate_found"),
        budget_available=_required_bool(value, "budget_available"),
        policy_requires_approval=_required_bool(value, "policy_requires_approval"),
        human_approved=_optional_bool(value, "human_approved", default=False),
    )


def _required_text(value: Mapping[str, Any], field_name: str) -> str:
    """Return a required non-empty text field."""

    if field_name not in value:
        raise KeyError(f"missing field: {field_name}")
    text = str(value[field_name]).strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _required_bool(value: Mapping[str, Any], field_name: str) -> bool:
    """Return a required boolean field."""

    if field_name not in value:
        raise KeyError(f"missing field: {field_name}")
    raw_value = value[field_name]
    if not isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return raw_value


def _optional_bool(value: Mapping[str, Any], field_name: str, *, default: bool) -> bool:
    """Return an optional boolean field."""

    if field_name not in value:
        return default
    raw_value = value[field_name]
    if not isinstance(raw_value, bool):
        raise ValueError(f"{field_name} must be boolean")
    return raw_value
