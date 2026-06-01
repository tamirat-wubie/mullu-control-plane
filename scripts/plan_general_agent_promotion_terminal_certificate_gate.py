#!/usr/bin/env python3
"""Plan terminal certificate admission from the promotion live-evidence queue.

Purpose: produce a non-executing gate that admits only queue items already
runnable or explicitly approved for terminal closure candidate generation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: general-agent promotion live-evidence queue, optional approval
receipt, terminal certificate gate schema, and terminal closure certificate
schema identity.
Invariants:
  - This gate does not execute queue actions or mint terminal certificates.
  - Environment-blocked queue items are never admitted by approval alone.
  - Approval-bound queue items require explicit approved refs.
  - Secret values are never read or serialized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.plan_general_agent_promotion_live_evidence_queue import (  # noqa: E402
    DEFAULT_OUTPUT as DEFAULT_LIVE_EVIDENCE_QUEUE,
    validate_general_agent_promotion_live_evidence_queue,
)
from scripts.validate_general_agent_promotion_terminal_approvals import (  # noqa: E402
    validate_general_agent_promotion_terminal_approvals,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402

DEFAULT_APPROVAL_RECEIPT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_approvals.json"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "general_agent_promotion_terminal_certificate_gate.schema.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "general_agent_promotion_terminal_certificate_gate.json"
DEFAULT_GENERATED_AT = "2026-05-01T12:00:00+00:00"
TERMINAL_CERTIFICATE_SCHEMA_ID = "urn:mullusi:schema:terminal-closure-certificate:1"
ADMITTED_STATUSES = frozenset({"admitted_runnable", "admitted_approved"})
APPROVAL_CLASSES = frozenset({"requires_approval", "review_only"})
DEPENDENCY_BLOCKED_CLASSES = frozenset({"requires_dependency_closure"})
ENVIRONMENT_BLOCKED_CLASSES = frozenset(
    {
        "requires_environment_binding",
        "requires_execution_environment",
        "approval_and_environment_blocked",
    }
)


@dataclass(frozen=True, slots=True)
class ApprovalReceiptState:
    """Validated approval-ref projection for terminal certificate admission."""

    present: bool
    valid: bool
    approvals_by_action: dict[str, str]
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TerminalCertificateGateAction:
    """One queue item classified for terminal certificate admission."""

    gate_item_id: str
    source_queue_item_id: str
    source_action_id: str
    source_plan_type: str
    execution_class: str
    terminal_gate_status: str
    approval_required: bool
    approval_ref_present: bool
    approval_ref: str | None
    certificate_candidate_id: str | None
    blocked_reasons: tuple[str, ...]
    evidence_required: tuple[str, ...]
    receipt_validator: str

    @property
    def admitted(self) -> bool:
        """Return whether this action can proceed to terminal certificate candidate work."""
        return self.terminal_gate_status in ADMITTED_STATUSES

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-ready gate item data."""
        return {
            "gate_item_id": self.gate_item_id,
            "source_queue_item_id": self.source_queue_item_id,
            "source_action_id": self.source_action_id,
            "source_plan_type": self.source_plan_type,
            "execution_class": self.execution_class,
            "terminal_gate_status": self.terminal_gate_status,
            "approval_required": self.approval_required,
            "approval_ref_present": self.approval_ref_present,
            "approval_ref": self.approval_ref,
            "certificate_candidate_id": self.certificate_candidate_id,
            "blocked_reasons": list(self.blocked_reasons),
            "evidence_required": list(self.evidence_required),
            "receipt_validator": self.receipt_validator,
        }


@dataclass(frozen=True, slots=True)
class TerminalCertificateGatePlan:
    """Non-executing terminal certificate admission gate."""

    schema_version: int
    gate_id: str
    generated_at: str
    source_queue_path: str
    approval_receipt_path: str
    ready_for_terminal_certificate: bool
    action_count: int
    admitted_action_count: int
    blocked_action_count: int
    approval_bound_admitted_count: int
    missing_approval_count: int
    blocked_reasons: tuple[str, ...]
    actions: tuple[TerminalCertificateGateAction, ...]
    metadata: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready gate output."""
        return {
            "schema_version": self.schema_version,
            "gate_id": self.gate_id,
            "generated_at": self.generated_at,
            "source_queue_path": self.source_queue_path,
            "approval_receipt_path": self.approval_receipt_path,
            "ready_for_terminal_certificate": self.ready_for_terminal_certificate,
            "action_count": self.action_count,
            "admitted_action_count": self.admitted_action_count,
            "blocked_action_count": self.blocked_action_count,
            "approval_bound_admitted_count": self.approval_bound_admitted_count,
            "missing_approval_count": self.missing_approval_count,
            "blocked_reasons": list(self.blocked_reasons),
            "actions": [action.as_dict() for action in self.actions],
            "metadata": dict(self.metadata),
        }


def plan_general_agent_promotion_terminal_certificate_gate(
    *,
    queue_path: Path = DEFAULT_LIVE_EVIDENCE_QUEUE,
    approval_receipt_path: Path = DEFAULT_APPROVAL_RECEIPT,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> TerminalCertificateGatePlan:
    """Classify live-evidence queue items for terminal certificate admission."""
    queue = _load_json_object(queue_path, "live-evidence queue")
    queue_errors = validate_general_agent_promotion_live_evidence_queue(queue)
    if queue_errors:
        approval_state = _approval_receipt_state(approval_receipt_path)
        queue_hash = _stable_hash(queue)
        return _invalid_queue_gate(
            queue_path=queue_path,
            approval_receipt_path=approval_receipt_path,
            generated_at=generated_at,
            queue=queue,
            queue_hash=queue_hash,
            approval_state=approval_state,
            queue_errors=tuple(queue_errors),
        )
    approval_state = _approval_receipt_state(approval_receipt_path)
    actions = tuple(
        _gate_action(index=index, action=action, approval_state=approval_state)
        for index, action in enumerate(_queue_actions(queue), start=1)
    )
    return _gate_plan(
        queue_path=queue_path,
        approval_receipt_path=approval_receipt_path,
        generated_at=generated_at,
        queue=queue,
        actions=actions,
        approval_state=approval_state,
        queue_hash=_stable_hash(queue),
    )


def write_general_agent_promotion_terminal_certificate_gate(
    gate: TerminalCertificateGatePlan,
    output_path: Path,
) -> Path:
    """Write one terminal certificate gate artifact."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(gate.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def validate_general_agent_promotion_terminal_certificate_gate(
    gate: TerminalCertificateGatePlan | dict[str, Any],
    schema_path: Path = DEFAULT_SCHEMA,
) -> tuple[str, ...]:
    """Validate one terminal certificate gate artifact against its schema."""
    schema = _load_schema(schema_path)
    payload = gate.as_dict() if isinstance(gate, TerminalCertificateGatePlan) else gate
    return tuple(_validate_schema_instance(schema, payload))


def _path_label(path: Path) -> str:
    """Return a terminal-gate path label without host-local ancestry."""
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _gate_action(
    *,
    index: int,
    action: dict[str, Any],
    approval_state: ApprovalReceiptState,
) -> TerminalCertificateGateAction:
    source_action_id = _field_text(action, "source_action_id", f"source-action-{index:02d}")
    source_queue_item_id = _field_text(action, "queue_item_id", f"queue-item-{index:02d}")
    execution_class = _field_text(action, "execution_class", "blocked_invalid_queue_item")
    source_plan_type = _source_plan_type(action)
    approval_required = action.get("approval_required") is True
    approval_ref = approval_state.approvals_by_action.get(source_action_id)
    approval_ref_present = approval_ref is not None
    status, blocked_reasons = _terminal_gate_status(
        action=action,
        execution_class=execution_class,
        approval_required=approval_required,
        approval_ref_present=approval_ref_present,
        approval_state=approval_state,
    )
    candidate_id = _certificate_candidate_id(source_action_id, approval_ref) if status in ADMITTED_STATUSES else None
    return TerminalCertificateGateAction(
        gate_item_id=f"terminal-certificate-gate-item-{index:02d}-{_safe_id(source_action_id)}",
        source_queue_item_id=source_queue_item_id,
        source_action_id=source_action_id,
        source_plan_type=source_plan_type,
        execution_class=execution_class,
        terminal_gate_status=status,
        approval_required=approval_required,
        approval_ref_present=approval_ref_present,
        approval_ref=approval_ref,
        certificate_candidate_id=candidate_id,
        blocked_reasons=blocked_reasons,
        evidence_required=_string_tuple(action.get("evidence_required", ())),
        receipt_validator=_field_text(action, "receipt_validator", "not_declared"),
    )


def _terminal_gate_status(
    *,
    action: dict[str, Any],
    execution_class: str,
    approval_required: bool,
    approval_ref_present: bool,
    approval_state: ApprovalReceiptState,
) -> tuple[str, tuple[str, ...]]:
    queue_blockers = _string_tuple(action.get("blocked_reasons", ()))
    if execution_class == "runnable_local":
        return "admitted_runnable", ()
    if execution_class in APPROVAL_CLASSES:
        if approval_ref_present:
            return "admitted_approved", ()
        reasons = ["explicit_approval_ref_missing"]
        if approval_required and not approval_state.present:
            reasons.append("approval_receipt_missing")
        reasons.extend(approval_state.errors)
        return "blocked_approval", tuple(dict.fromkeys(reasons))
    if execution_class in DEPENDENCY_BLOCKED_CLASSES:
        reasons = list(queue_blockers)
        if not reasons:
            reasons.append("dependency_action_requires_closure")
        reasons.extend(approval_state.errors)
        return "blocked_dependency", tuple(dict.fromkeys(reasons))
    if execution_class in ENVIRONMENT_BLOCKED_CLASSES:
        reasons = list(queue_blockers)
        if approval_required and not approval_ref_present:
            reasons.append("explicit_approval_ref_missing")
            if not approval_state.present:
                reasons.append("approval_receipt_missing")
        reasons.extend(approval_state.errors)
        status = "blocked_approval_and_environment" if execution_class == "approval_and_environment_blocked" else "blocked_environment"
        return status, tuple(dict.fromkeys(reasons))
    return "blocked_invalid_queue_item", ("invalid_execution_class",)


def _gate_plan(
    *,
    queue_path: Path,
    approval_receipt_path: Path,
    generated_at: str,
    queue: dict[str, Any],
    actions: tuple[TerminalCertificateGateAction, ...],
    approval_state: ApprovalReceiptState,
    queue_hash: str,
) -> TerminalCertificateGatePlan:
    admitted_count = sum(1 for action in actions if action.admitted)
    blocked_count = len(actions) - admitted_count
    approval_bound_admitted_count = sum(
        1 for action in actions if action.terminal_gate_status == "admitted_approved"
    )
    missing_approval_count = sum(
        1
        for action in actions
        if "explicit_approval_ref_missing" in action.blocked_reasons
    )
    blocked_reasons = tuple(
        sorted(
            {
                reason
                for action in actions
                for reason in action.blocked_reasons
            }
        )
    )
    gate_material = {
        "generated_at": generated_at,
        "queue_hash": queue_hash,
        "approval_receipt_path": _path_label(approval_receipt_path),
        "actions": [action.as_dict() for action in actions],
    }
    gate_digest = _stable_hash(gate_material)
    return TerminalCertificateGatePlan(
        schema_version=1,
        gate_id=f"general-agent-promotion-terminal-certificate-gate-{gate_digest[:16]}",
        generated_at=generated_at,
        source_queue_path=_path_label(queue_path),
        approval_receipt_path=_path_label(approval_receipt_path),
        ready_for_terminal_certificate=blocked_count == 0,
        action_count=len(actions),
        admitted_action_count=admitted_count,
        blocked_action_count=blocked_count,
        approval_bound_admitted_count=approval_bound_admitted_count,
        missing_approval_count=missing_approval_count,
        blocked_reasons=blocked_reasons,
        actions=actions,
        metadata={
            "gate_is_not_execution": True,
            "secret_values_serialized": False,
            "approval_receipt_present": approval_state.present,
            "approval_receipt_valid": approval_state.valid,
            "queue_id": str(queue.get("queue_id", "")),
            "queue_hash": queue_hash,
            "queue_ready_to_execute": queue.get("ready_to_execute") is True,
            "terminal_certificate_schema_id": TERMINAL_CERTIFICATE_SCHEMA_ID,
        },
    )


def _invalid_queue_gate(
    *,
    queue_path: Path,
    approval_receipt_path: Path,
    generated_at: str,
    queue: dict[str, Any],
    queue_hash: str,
    approval_state: ApprovalReceiptState,
    queue_errors: tuple[str, ...],
) -> TerminalCertificateGatePlan:
    action = TerminalCertificateGateAction(
        gate_item_id="terminal-certificate-gate-item-01-invalid-queue",
        source_queue_item_id="invalid-queue",
        source_action_id="invalid-queue",
        source_plan_type="adapter",
        execution_class="runnable_local",
        terminal_gate_status="blocked_invalid_queue_item",
        approval_required=False,
        approval_ref_present=False,
        approval_ref=None,
        certificate_candidate_id=None,
        blocked_reasons=tuple(f"live_evidence_queue_invalid:{error}" for error in queue_errors),
        evidence_required=(),
        receipt_validator="live_evidence_queue_schema",
    )
    return _gate_plan(
        queue_path=queue_path,
        approval_receipt_path=approval_receipt_path,
        generated_at=generated_at,
        queue=queue,
        actions=(action,),
        approval_state=approval_state,
        queue_hash=queue_hash,
    )


def _approval_receipt_state(path: Path) -> ApprovalReceiptState:
    validation = validate_general_agent_promotion_terminal_approvals(
        receipt_path=path,
        allow_missing=True,
    )
    return ApprovalReceiptState(
        present=validation.present,
        valid=validation.valid,
        approvals_by_action=validation.approved_refs_by_action if validation.valid else {},
        errors=validation.errors if validation.present else (),
    )


def _queue_actions(queue: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    actions = queue.get("actions", ())
    if not isinstance(actions, list):
        raise ValueError("live-evidence queue actions must be a list")
    return tuple(action for action in actions if isinstance(action, dict))


def _source_plan_type(action: dict[str, Any]) -> str:
    observed = _field_text(action, "source_plan_type", "adapter")
    if observed in {"adapter", "deployment", "portfolio"}:
        return observed
    return "adapter"


def _field_text(action: dict[str, Any], field_name: str, fallback: str) -> str:
    value = str(action.get(field_name, "")).strip()
    return value or fallback


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _certificate_candidate_id(source_action_id: str, approval_ref: str | None) -> str:
    digest = _stable_hash({"source_action_id": source_action_id, "approval_ref": approval_ref or ""})
    return f"terminal-certificate-candidate-{digest[:16]}"


def _safe_id(value: str) -> str:
    normalized = "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")
    compact = "-".join(part for part in normalized.split("-") if part)
    return (compact or "unknown")[:72]


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON root must be an object")
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse terminal certificate gate planner arguments."""
    parser = argparse.ArgumentParser(description="Plan terminal certificate admission from live-evidence queue.")
    parser.add_argument("--queue", default=str(DEFAULT_LIVE_EVIDENCE_QUEUE))
    parser.add_argument("--approval-receipt", default=str(DEFAULT_APPROVAL_RECEIPT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for terminal certificate gate planning."""
    args = parse_args(argv)
    gate = plan_general_agent_promotion_terminal_certificate_gate(
        queue_path=Path(args.queue),
        approval_receipt_path=Path(args.approval_receipt),
        generated_at=args.generated_at,
    )
    schema_errors = validate_general_agent_promotion_terminal_certificate_gate(gate, Path(args.schema))
    write_general_agent_promotion_terminal_certificate_gate(gate, Path(args.output))
    payload = gate.as_dict() | {"schema_valid": not schema_errors, "schema_errors": list(schema_errors)}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif schema_errors:
        for error in schema_errors:
            print(f"error: {error}")
    else:
        print(
            "GENERAL AGENT PROMOTION TERMINAL CERTIFICATE GATE WRITTEN "
            f"ready={gate.ready_for_terminal_certificate} admitted={gate.admitted_action_count} blocked={gate.blocked_action_count}"
        )
    if schema_errors and args.strict:
        return 2
    if args.require_ready and not gate.ready_for_terminal_certificate:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
