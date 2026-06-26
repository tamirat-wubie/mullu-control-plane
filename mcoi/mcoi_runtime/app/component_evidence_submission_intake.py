"""Build Component Harness evidence submission intake previews.

Purpose: project submitted-evidence reference observations against the
foundation component evidence request queue without accepting evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component evidence request queue.
Invariants:
  - The intake records submitted refs as observations only.
  - The intake does not submit, verify, accept, reject, grant authority,
    approve promotion, execute, mutate, or claim terminal closure.
  - Unknown request IDs and unsafe queue authority drift fail closed.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.app.component_evidence_request_queue import build_component_evidence_request_queue


SCHEMA_VERSION = 1
INTAKE_ID = "component_evidence_submission_intake.foundation.v1"
REQUIRED_VALIDATOR_REFS = (
    "component_evidence_request_queue_validator",
    "component_evidence_submission_intake_validator",
)


class ComponentEvidenceSubmissionIntakeError(ValueError):
    """Raised when submission intake previews cannot be projected safely."""


def build_component_evidence_submission_intake(
    *,
    evidence_request_queue: dict[str, Any] | None = None,
    submitted_evidence_by_request_id: Mapping[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Return deterministic non-accepting evidence submission intake.

    Input contract: optional evidence request queue and submitted evidence refs
    keyed by request ID.
    Output contract: JSON-serializable intake preview.
    Error contract: raises ComponentEvidenceSubmissionIntakeError for malformed
    queue state, unknown request IDs, or malformed submitted refs.
    """

    queue = evidence_request_queue or build_component_evidence_request_queue()
    submissions = dict(submitted_evidence_by_request_id or {})
    _require_queue_safe(queue)
    request_slots = _request_slots(queue)
    request_ids = {_required_text(slot, "request_id", "queue slot") for slot in request_slots}
    unknown_request_ids = sorted(set(submissions) - request_ids)
    if unknown_request_ids:
        raise ComponentEvidenceSubmissionIntakeError(f"unknown submitted request IDs {unknown_request_ids}")

    intake_slots = [_intake_slot(slot, submissions.get(str(slot["request_id"]), [])) for slot in request_slots]
    return {
        "schema_version": SCHEMA_VERSION,
        "intake_id": INTAKE_ID,
        "mode": "foundation",
        "source_refs": {
            "component_evidence_request_queue": "examples/component_evidence_request_queue.foundation.json",
        },
        "intake_is_not_execution_authority": True,
        "intake_is_not_evidence_submission": True,
        "intake_is_not_evidence_acceptance": True,
        "intake_is_not_evidence_rejection": True,
        "intake_is_not_authority_grant": True,
        "intake_is_not_promotion_approval": True,
        "intake_is_not_terminal_closure": True,
        "submitted_evidence_refs_are_observations_only": True,
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
            "request_slot_count": len(intake_slots),
            "submitted_slot_count": sum(1 for slot in intake_slots if slot["submitted_evidence_observed"]),
            "submitted_evidence_ref_count": sum(len(slot["submitted_evidence_refs"]) for slot in intake_slots),
            "accepted_evidence_count": sum(len(slot["accepted_evidence_refs"]) for slot in intake_slots),
            "rejected_evidence_count": sum(len(slot["rejected_evidence_refs"]) for slot in intake_slots),
            "authority_grant_count": sum(1 for slot in intake_slots if slot["authority_granted"]),
            "terminal_closure_allowed_count": sum(1 for slot in intake_slots if slot["terminal_closure_allowed"]),
        },
        "intake_slots": intake_slots,
        "validators": [
            {
                "validator_id": "component_evidence_submission_intake_validator",
                "command": "python scripts/validate_component_evidence_submission_intake.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_evidence_submission_intake_tests",
                "command": "python -m pytest tests/test_validate_component_evidence_submission_intake.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Run a separate evidence verifier before accepting submitted refs or changing authority state.",
    }


def _intake_slot(queue_slot: dict[str, Any], submitted_refs: list[str]) -> dict[str, Any]:
    request_id = _required_text(queue_slot, "request_id", "queue slot")
    refs = _submitted_refs(submitted_refs, request_id)
    return {
        "intake_slot_id": f"component_evidence_submission_intake.{request_id}.v1",
        "request_id": request_id,
        "bundle_id": _required_text(queue_slot, "bundle_id", "queue slot"),
        "missing_evidence_ref": _required_text(queue_slot, "missing_evidence_ref", "queue slot"),
        "request_state": _required_text(queue_slot, "request_state", "queue slot"),
        "submission_state": "submitted_not_verified" if refs else "awaiting_submission",
        "proof_state": "Unknown",
        "outcome": "AwaitingEvidence",
        "request_bound": True,
        "intake_only": True,
        "submitted_evidence_observed": bool(refs),
        "submitted_evidence_refs": refs,
        "accepted_evidence_refs": [],
        "rejected_evidence_refs": [],
        "evidence_accepted": False,
        "evidence_rejected": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_allowed": False,
        "blocked_actions": _required_string_list(queue_slot, "blocked_actions", "queue slot"),
        "claim_firewall_blocking_claim_ids": _required_string_list(
            queue_slot,
            "claim_firewall_blocking_claim_ids",
            "queue slot",
        ),
        "required_validator_refs": list(REQUIRED_VALIDATOR_REFS),
    }


def _require_queue_safe(queue: dict[str, Any]) -> None:
    if queue.get("queue_is_not_execution_authority") is not True:
        raise ComponentEvidenceSubmissionIntakeError("queue must not be execution authority")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "evidence_accepted",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if queue.get(flag_name) is not False:
            raise ComponentEvidenceSubmissionIntakeError(f"queue {flag_name} must be false")


def _request_slots(queue: dict[str, Any]) -> list[dict[str, Any]]:
    slots = queue.get("request_slots")
    if not isinstance(slots, list) or not slots:
        raise ComponentEvidenceSubmissionIntakeError("queue request_slots must be a non-empty list")
    output: list[dict[str, Any]] = []
    for index, slot in enumerate(slots):
        if not isinstance(slot, dict):
            raise ComponentEvidenceSubmissionIntakeError(f"queue request_slots[{index}] must be an object")
        output.append(slot)
    return output


def _submitted_refs(value: object, request_id: str) -> list[str]:
    if not isinstance(value, list):
        raise ComponentEvidenceSubmissionIntakeError(f"submitted refs for {request_id} must be a list")
    refs: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ComponentEvidenceSubmissionIntakeError(
                f"submitted refs for {request_id}[{index}] must be non-empty text"
            )
        refs.append(item)
    return list(dict.fromkeys(refs))


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentEvidenceSubmissionIntakeError(f"{label} must carry text field {field_name}")
    return value


def _required_string_list(payload: dict[str, Any], field_name: str, label: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list) or not value:
        raise ComponentEvidenceSubmissionIntakeError(f"{label} must carry non-empty list field {field_name}")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ComponentEvidenceSubmissionIntakeError(
                f"{label} list field {field_name}[{index}] must be non-empty text"
            )
        output.append(item)
    return output
