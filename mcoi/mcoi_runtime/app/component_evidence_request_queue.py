"""Build Component Harness evidence request queues.

Purpose: derive request-only evidence slots from foundation component bundle
compilations and claim firewall blockers.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: component bundle compiler and component claim firewall.
Invariants:
  - Evidence request queues are not execution, evidence submission, evidence
    acceptance, authority grant, promotion approval, or terminal closure.
  - Live execution, connector calls, mutation, and terminal closure stay false.
  - Unsafe source authority drift fails closed with explicit causal context.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.app.component_bundle_compiler import compile_foundation_component_bundles
from mcoi_runtime.app.component_claim_firewall import build_component_claim_firewall


SCHEMA_VERSION = 1
QUEUE_ID = "component_evidence_request_queue.foundation.v1"
REQUIRED_VALIDATOR_REFS = (
    "component_bundle_compiler_validator",
    "component_claim_firewall_validator",
    "component_evidence_request_queue_validator",
)


class ComponentEvidenceRequestQueueError(ValueError):
    """Raised when evidence request queues cannot be projected safely."""


def build_component_evidence_request_queue(
    *,
    bundle_compilations: list[dict[str, Any]] | None = None,
    claim_firewall: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic request-only component evidence queue.

    Input contract: optional precomputed bundle compilations and claim firewall.
    Output contract: JSON-serializable evidence request queue.
    Error contract: raises ComponentEvidenceRequestQueueError for malformed or
    authority-unsafe source state.
    """

    compilations = bundle_compilations or compile_foundation_component_bundles()
    firewall = claim_firewall or build_component_claim_firewall()
    _require_claim_firewall_safe(firewall)

    request_slots: list[dict[str, Any]] = []
    blocked_claim_ids = _blocked_claim_ids(firewall)
    for compilation in compilations:
        _require_bundle_compilation_safe(compilation)
        request_slots.extend(_request_slots_for_bundle(compilation, blocked_claim_ids))

    return {
        "schema_version": SCHEMA_VERSION,
        "queue_id": QUEUE_ID,
        "mode": "foundation",
        "source_refs": {
            "component_bundle_compilations": "mcoi_runtime.app.component_bundle_compiler.compile_foundation_component_bundles",
            "component_claim_firewall": "examples/component_claim_firewall.foundation.json",
        },
        "queue_is_not_execution_authority": True,
        "queue_is_not_evidence_submission": True,
        "queue_is_not_evidence_acceptance": True,
        "queue_is_not_authority_grant": True,
        "queue_is_not_promotion_approval": True,
        "queue_is_not_terminal_closure": True,
        "live_execution_enabled": False,
        "live_connector_send_enabled": False,
        "can_execute": False,
        "can_mutate": False,
        "can_call_connector": False,
        "can_claim_terminal_closure": False,
        "evidence_submitted": False,
        "evidence_accepted": False,
        "authority_granted": False,
        "promotion_approved": False,
        "terminal_closure_allowed": False,
        "summary": {
            "bundle_count": len(compilations),
            "request_slot_count": len(request_slots),
            "operator_input_required_count": sum(1 for slot in request_slots if slot["operator_input_required"]),
            "unknown_proof_state_count": sum(1 for slot in request_slots if slot["proof_state"] == "Unknown"),
            "submitted_evidence_count": sum(1 for slot in request_slots if slot["evidence_submitted"]),
            "accepted_evidence_count": sum(1 for slot in request_slots if slot["evidence_accepted"]),
            "authority_grant_count": sum(1 for slot in request_slots if slot["authority_granted"]),
            "terminal_closure_allowed_count": sum(1 for slot in request_slots if slot["terminal_closure_allowed"]),
        },
        "request_slots": request_slots,
        "validators": [
            {
                "validator_id": "component_evidence_request_queue_validator",
                "command": "python scripts/validate_component_evidence_request_queue.py",
                "required_for_closure": True,
            },
            {
                "validator_id": "component_evidence_request_queue_tests",
                "command": "python -m pytest tests/test_validate_component_evidence_request_queue.py -q",
                "required_for_closure": True,
            },
        ],
        "next_action": "Submit separate governed evidence packets for queued slots; this queue does not accept them.",
    }


def _request_slots_for_bundle(
    compilation: dict[str, Any],
    blocked_claim_ids: list[str],
) -> list[dict[str, Any]]:
    bundle_id = _required_text(compilation, "bundle_id", "bundle compilation")
    compilation_id = _required_text(compilation, "compilation_id", "bundle compilation")
    source_outcome = _required_text(compilation, "outcome", "bundle compilation")
    blocked_actions = _required_string_list(compilation, "blocked_actions", "bundle compilation")
    missing_evidence = _required_string_list(compilation, "missing_evidence", "bundle compilation", allow_empty=True)
    slots: list[dict[str, Any]] = []
    for evidence_ref in missing_evidence:
        slots.append(
            {
                "request_id": f"component_evidence_request_queue.{bundle_id}.{evidence_ref}.v1",
                "bundle_id": bundle_id,
                "source_compilation_id": compilation_id,
                "source_outcome": source_outcome,
                "missing_evidence_ref": evidence_ref,
                "request_state": "requested_not_submitted",
                "proof_state": "Unknown",
                "outcome": "AwaitingEvidence",
                "operator_input_required": True,
                "request_only": True,
                "requirement_satisfied": False,
                "evidence_submitted": False,
                "evidence_accepted": False,
                "authority_granted": False,
                "promotion_approved": False,
                "terminal_closure_allowed": False,
                "blocked_actions": blocked_actions,
                "claim_firewall_blocking_claim_ids": blocked_claim_ids,
                "required_validator_refs": list(REQUIRED_VALIDATOR_REFS),
            }
        )
    return slots


def _require_bundle_compilation_safe(compilation: dict[str, Any]) -> None:
    if compilation.get("compiler_is_not_execution_authority") is not True:
        raise ComponentEvidenceRequestQueueError("bundle compilation must not be execution authority")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
    ):
        if compilation.get(flag_name) is not False:
            bundle_id = str(compilation.get("bundle_id", "<missing>"))
            raise ComponentEvidenceRequestQueueError(f"bundle {bundle_id} {flag_name} must be false")
    if "terminal_closure" not in _required_string_list(compilation, "blocked_actions", "bundle compilation"):
        raise ComponentEvidenceRequestQueueError("bundle compilation blocked_actions must include terminal_closure")


def _require_claim_firewall_safe(claim_firewall: dict[str, Any]) -> None:
    if claim_firewall.get("firewall_is_not_execution_authority") is not True:
        raise ComponentEvidenceRequestQueueError("claim firewall must not be execution authority")
    if claim_firewall.get("live_execution_enabled") is not False:
        raise ComponentEvidenceRequestQueueError("claim firewall live_execution_enabled must be false")
    if claim_firewall.get("live_connector_send_enabled") is not False:
        raise ComponentEvidenceRequestQueueError("claim firewall live_connector_send_enabled must be false")
    if _blocked_claim_ids(claim_firewall) == []:
        raise ComponentEvidenceRequestQueueError("claim firewall must carry blocked claim ids")


def _blocked_claim_ids(claim_firewall: dict[str, Any]) -> list[str]:
    checks = claim_firewall.get("claim_checks")
    if not isinstance(checks, list):
        raise ComponentEvidenceRequestQueueError("claim firewall claim_checks must be a list")
    return [
        _required_text(claim_check, "claim_id", "claim firewall check")
        for claim_check in checks
        if isinstance(claim_check, dict) and claim_check.get("decision") == "blocked"
    ]


def _required_text(payload: dict[str, Any], field_name: str, label: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ComponentEvidenceRequestQueueError(f"{label} must carry text field {field_name}")
    return value


def _required_string_list(
    payload: dict[str, Any],
    field_name: str,
    label: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ComponentEvidenceRequestQueueError(f"{label} must carry list field {field_name}")
    if not allow_empty and not value:
        raise ComponentEvidenceRequestQueueError(f"{label} list field {field_name} must not be empty")
    output: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ComponentEvidenceRequestQueueError(
                f"{label} list field {field_name}[{index}] must be non-empty text"
            )
        output.append(item)
    return output
