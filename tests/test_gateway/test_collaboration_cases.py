"""Gateway collaboration case tests.

Purpose: verify governed collaboration cases bind requester separation,
approval controls, decider authority, evidence refs, hashes, and non-terminal
case closure.
Governance scope: collaboration admission, approval separation, pending-control
blocking, decider authority, schema compatibility, and terminal-closure
separation.
Dependencies: gateway.collaboration_cases and schemas/collaboration_case.schema.json.
Invariants:
  - A requester cannot approve the same case.
  - Pending controls block case closure.
  - Only the declared decider may close a case.
  - Case closure never claims terminal command closure.
"""

from __future__ import annotations

from pathlib import Path

from gateway.collaboration_cases import (
    CollaborationCase,
    CollaborationCaseManager,
    CollaborationClosure,
    CollaborationControl,
    with_resolved_control,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "collaboration_case.schema.json"


def test_open_case_stamps_hash_and_metadata() -> None:
    case = _case()
    assert case.case_hash
    assert case.metadata["approval_separation_required"] is True
    assert case.metadata["pending_controls_block_case_closure"] is True
    assert case.metadata["decider_authority_required"] is True


def test_self_approval_is_blocked() -> None:
    try:
        _manager().open_case(
            case_id="case-invoice-1",
            tenant_id="tenant-a",
            requester_id="finance-admin",
            subject="vendor invoice review",
            approval_decider_id="finance-admin",
            decider_authority_ref="authority://finance-admin",
            controls=(_control(),),
            evidence_refs=("proof://invoice-extracted",),
        )
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""
    assert error == "approval_separation_required"
    assert error
    assert error.endswith("required")


def test_pending_control_blocks_case_closure() -> None:
    closure = _manager().close_case(_case(), closed_by="finance-admin")
    assert closure.closure_allowed is False
    assert closure.status == "blocked"
    assert "pending_controls_block_case_closure" in closure.blocked_reasons
    assert closure.closure_hash


def test_non_decider_case_closure_is_blocked() -> None:
    closure = _manager().close_case(
        _case_with_resolved_control(), closed_by="user-requester"
    )
    assert closure.closure_allowed is False
    assert closure.status == "blocked"
    assert "decider_authority_required" in closure.blocked_reasons
    assert "proof://invoice-extracted" in closure.evidence_refs


def test_resolved_control_allows_non_terminal_closure_with_combined_evidence() -> None:
    closure = _manager().close_case(
        _case_with_resolved_control(), closed_by="finance-admin"
    )
    assert closure.closure_allowed is True
    assert closure.status == "closed"
    assert closure.closure_is_terminal is False
    assert closure.evidence_refs == (
        "proof://invoice-extracted",
        "proof://manager-approved",
    )
    assert closure.closure_hash


def test_collaboration_case_schema_export_validates() -> None:
    case = _case_with_resolved_control()
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), case.to_json_dict())
    assert errors == []
    assert case.to_json_dict()["closure_is_terminal"] is False
    assert case.to_json_dict()["controls"][0]["status"] == "resolved"
    assert case.to_json_dict()["metadata"]["decider_authority_required"] is True


def test_collaboration_closure_rejects_terminal_claim() -> None:
    try:
        CollaborationClosure(
            case_id="case-invoice-1",
            closed_by="finance-admin",
            closure_allowed=True,
            status="closed",
            blocked_reasons=(),
            evidence_refs=("proof://manager-approved",),
            closure_is_terminal=True,
        )
    except ValueError as exc:
        error = str(exc)
    else:
        error = ""
    assert error == "closure_is_not_terminal_command_closure"
    assert error
    assert "terminal" in error


def _manager() -> CollaborationCaseManager:
    return CollaborationCaseManager()


def _control() -> CollaborationControl:
    return CollaborationControl(
        control_id="control-manager-approval",
        control_type="approval_request",
        owner_id="finance-admin",
    )


def _case() -> CollaborationCase:
    return _manager().open_case(
        case_id="case-invoice-1",
        tenant_id="tenant-a",
        requester_id="user-requester",
        subject="vendor invoice review",
        approval_decider_id="finance-admin",
        decider_authority_ref="authority://finance-admin",
        controls=(_control(),),
        evidence_refs=("proof://invoice-extracted",),
    )


def _case_with_resolved_control() -> CollaborationCase:
    control = with_resolved_control(
        _control(), evidence_refs=("proof://manager-approved",)
    )
    return _manager().open_case(
        case_id="case-invoice-1",
        tenant_id="tenant-a",
        requester_id="user-requester",
        subject="vendor invoice review",
        approval_decider_id="finance-admin",
        decider_authority_ref="authority://finance-admin",
        controls=(control,),
        evidence_refs=("proof://invoice-extracted",),
    )
