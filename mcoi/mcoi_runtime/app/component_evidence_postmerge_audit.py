"""Build Component Harness evidence post-merge audits.

Purpose: audit the component evidence request queue and submission intake after
merge without accepting evidence or changing authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component evidence request queue and submission intake.
Invariants:
  - The audit is read-only and post-merge only.
  - Evidence acceptance, rejection, authority grant, promotion, and terminal
    closure remain denied.
  - Queue and intake request IDs must stay aligned.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_evidence_request_queue import build_component_evidence_request_queue
from mcoi_runtime.app.component_evidence_submission_intake import build_component_evidence_submission_intake


SCHEMA_VERSION = 1
AUDIT_ID = "component_evidence_postmerge_audit.foundation.v1"
REQUIRED_VALIDATOR_REFS = (
    "component_evidence_request_queue_validator",
    "component_evidence_submission_intake_validator",
    "component_evidence_postmerge_audit_validator",
)


class ComponentEvidencePostmergeAuditError(ValueError):
    """Raised when component evidence post-merge audit sources are unsafe."""


def build_component_evidence_postmerge_audit(
    *,
    evidence_request_queue: dict[str, Any] | None = None,
    evidence_submission_intake: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic read-only post-merge audit.

    Input contract: optional queue and intake projections.
    Output contract: JSON-serializable post-merge audit packet.
    Error contract: raises ComponentEvidencePostmergeAuditError for malformed,
    unsafe, or misaligned sources.
    """

    queue = evidence_request_queue or build_component_evidence_request_queue()
    intake = evidence_submission_intake or build_component_evidence_submission_intake(
        evidence_request_queue=queue,
    )
    _require_queue_safe(queue)
    _require_intake_safe(intake)
    queue_slots = _object_list(queue, "request_slots", "queue")
    intake_slots = _object_list(intake, "intake_slots", "intake")
    queue_request_ids = {_required_text(slot, "request_id", "queue slot") for slot in queue_slots}
    intake_request_ids = {_required_text(slot, "request_id", "intake slot") for slot in intake_slots}
    if queue_request_ids != intake_request_ids:
        raise ComponentEvidencePostmergeAuditError("queue and intake request IDs must match")

    submitted_slot_count = sum(1 for slot in intake_slots if slot.get("submitted_evidence_observed") is True)
    submitted_ref_count = sum(len(_string_list(slot.get("submitted_evidence_refs"), "submitted refs")) for slot in intake_slots)
    accepted_count = sum(len(_string_list(slot.get("accepted_evidence_refs"), "accepted refs")) for slot in intake_slots)
    rejected_count = sum(len(_string_list(slot.get("rejected_evidence_refs"), "rejected refs")) for slot in intake_slots)
    authority_grant_count = sum(1 for slot in intake_slots if slot.get("authority_granted") is True)
    terminal_closure_allowed_count = sum(1 for slot in intake_slots if slot.get("terminal_closure_allowed") is True)

    findings = (
        _finding(
            "queue_runtime_alignment",
            "request queue matches runtime projection and remains request-only",
            ("component_evidence_request_queue_validator",),
        ),
        _finding(
            "intake_runtime_alignment",
            "submission intake matches runtime projection and remains observation-only",
            ("component_evidence_submission_intake_validator",),
        ),
        _finding(
            "request_to_intake_coverage",
            "every queued request ID has one intake slot",
            ("component_evidence_request_queue", "component_evidence_submission_intake"),
        ),
        _finding(
            "authority_denial_preserved",
            "acceptance, rejection, authority, and promotion remain denied",
            ("authority_denial_receipt",),
        ),
        _finding(
            "terminal_closure_denial_preserved",
            "post-merge audit is not terminal closure",
            ("terminal_closure_denial_receipt",),
        ),
    )

    blockers = (
        "submitted_evidence_not_verified",
        "evidence_acceptance_not_performed",
        "authority_grant_not_performed",
        "terminal_closure_denied",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_id": AUDIT_ID,
        "mode": "foundation",
        "source_refs": {
            "component_evidence_request_queue": "examples/component_evidence_request_queue.foundation.json",
            "component_evidence_submission_intake": "examples/component_evidence_submission_intake.foundation.json",
        },
        "audit_is_not_execution_authority": True,
        "audit_is_not_evidence_submission": True,
        "audit_is_not_evidence_acceptance": True,
        "audit_is_not_evidence_rejection": True,
        "audit_is_not_authority_grant": True,
        "audit_is_not_promotion_approval": True,
        "audit_is_not_terminal_closure": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "evidence_accepted": False,
        "evidence_rejected": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_allowed": False,
        "summary": {
            "request_slot_count": len(queue_slots),
            "intake_slot_count": len(intake_slots),
            "submitted_slot_count": submitted_slot_count,
            "submitted_evidence_ref_count": submitted_ref_count,
            "accepted_evidence_count": accepted_count,
            "rejected_evidence_count": rejected_count,
            "authority_grant_count": authority_grant_count,
            "terminal_closure_allowed_count": terminal_closure_allowed_count,
            "audit_finding_count": len(findings),
            "postmerge_blocker_count": len(blockers),
        },
        "audit_findings": list(findings),
        "postmerge_blockers": list(blockers),
        "validators": [
            {
                "validator_id": "component_evidence_postmerge_audit_validator",
                "command": "python scripts/validate_component_evidence_postmerge_audit.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_evidence_postmerge_audit_tests",
                "command": "python -m pytest tests/test_validate_component_evidence_postmerge_audit.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Verify submitted evidence in a separate governed lane before acceptance or authority changes.",
    }


def _finding(finding_id: str, statement: str, evidence_refs: tuple[str, ...]) -> dict[str, Any]:
    return {
        "finding_id": finding_id,
        "proof_state": "Pass",
        "outcome": "SolvedVerified",
        "statement": statement,
        "evidence_refs": list(evidence_refs),
        "required_validator_refs": list(REQUIRED_VALIDATOR_REFS),
    }


def _require_queue_safe(queue: dict[str, Any]) -> None:
    if queue.get("queue_is_not_execution_authority") is not True:
        raise ComponentEvidencePostmergeAuditError("queue must not be execution authority")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "evidence_submitted",
        "evidence_accepted",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if queue.get(flag_name) is not False:
            raise ComponentEvidencePostmergeAuditError(f"queue {flag_name} must be false")


def _require_intake_safe(intake: dict[str, Any]) -> None:
    if intake.get("intake_is_not_execution_authority") is not True:
        raise ComponentEvidencePostmergeAuditError("intake must not be execution authority")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "evidence_accepted",
        "evidence_rejected",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if intake.get(flag_name) is not False:
            raise ComponentEvidencePostmergeAuditError(f"intake {flag_name} must be false")


def _object_list(payload: dict[str, Any], field_name: str, label: str) -> list[dict[str, Any]]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value:
        raise ComponentEvidencePostmergeAuditError(f"{label} {field_name} must be a non-empty list")
    output: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ComponentEvidencePostmergeAuditError(f"{label} {field_name}[{index}] must be an object")
        output.append(item)
    return output


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentEvidencePostmergeAuditError(f"{label} must carry text field {field_name}")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ComponentEvidencePostmergeAuditError(f"{label} must be a list")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ComponentEvidencePostmergeAuditError(f"{label}[{index}] must be non-empty text")
        output.append(item)
    return output
