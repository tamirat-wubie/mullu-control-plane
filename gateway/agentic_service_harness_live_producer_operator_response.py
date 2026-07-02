"""Agentic Service Harness live producer operator response witness.

Purpose: project an operator approval request into an explicit missing
operator response witness without collecting approval or granting authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_approval.
Invariants:
  - Response witness output is read-only, non-terminal, and `AwaitingEvidence`.
  - No implicit approval is inferred from generic continuation.
  - Live execution, runtime writes, mutation routes, and external effects
    remain denied until explicit response evidence and all other witnesses pass.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_approval import (
    ALLOWED_RESPONSE_KINDS,
    OPERATOR_APPROVAL_REQUEST_ID,
    OPERATOR_APPROVAL_WITNESS_KIND,
    AgenticServiceHarnessLiveProducerOperatorApprovalRequest,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import (
    FALSE_AUTHORITY_FLAGS,
    REQUIRED_WITNESS_KINDS,
)


OPERATOR_RESPONSE_WITNESS_ID = "agentic-service-harness-live-producer-operator-response-witness"
OPERATOR_RESPONSE_WITNESS_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-response-witness",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py",
    "required_for_closure": True,
}
OPERATOR_RESPONSE_MISSING_KIND = "operator_response_missing"


class AgenticServiceHarnessLiveProducerOperatorResponseWitness:
    """Produce a missing operator response witness from the approval request."""

    def __init__(
        self,
        *,
        approval_request_source: AgenticServiceHarnessLiveProducerOperatorApprovalRequest | None = None,
    ) -> None:
        self._approval_request_source = approval_request_source or AgenticServiceHarnessLiveProducerOperatorApprovalRequest()

    def produce(self) -> dict[str, Any] | None:
        """Return an operator response witness or None when request is unavailable."""
        approval_request = self._approval_request_source.produce()
        if not isinstance(approval_request, Mapping):
            return None
        return project_operator_approval_request_to_operator_response_witness(approval_request)


def project_operator_approval_request_to_operator_response_witness(
    approval_request: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one approval request into a missing response witness packet."""
    request = deepcopy(dict(approval_request))
    scope = _mapping(request.get("scope"))
    approval_request_body = _mapping(request.get("approval_request"))
    requested_evidence_ref = str(request.get("requested_evidence_ref", ""))
    return {
        "response_witness_id": OPERATOR_RESPONSE_WITNESS_ID,
        "schema_version": 1,
        "generated_at": str(request.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_approval_request_ref": f"approval-request://{OPERATOR_APPROVAL_REQUEST_ID}",
        "source_requirements_ref": str(request.get("source_requirements_ref", "")),
        "source_admission_gate_ref": str(request.get("source_admission_gate_ref", "")),
        "witness_kind": OPERATOR_APPROVAL_WITNESS_KIND,
        "requested_evidence_ref": requested_evidence_ref,
        "approval_request_collection_binding": _approval_request_collection_binding(request),
        "response_status": "AwaitingEvidence",
        "response_kind": OPERATOR_RESPONSE_MISSING_KIND,
        "response_record_collected": False,
        "approval_satisfied": False,
        "rejection_recorded": False,
        "authority_granted": False,
        "planning_only": True,
        "read_only": True,
        "live_producer_implemented": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure": False,
        "scope": {
            "tenant_id": str(scope.get("tenant_id", "")),
            "organization_id": str(scope.get("organization_id", "")),
            "project_id": str(scope.get("project_id", "")),
            "repository_connection_id": str(scope.get("repository_connection_id", "")),
            "read_only": True,
        },
        "operator_response": {
            "approval_request_id": str(approval_request_body.get("approval_request_id", "")),
            "approver_role": "operator",
            "required_response_kinds": list(ALLOWED_RESPONSE_KINDS),
            "default_response_kind": "record_operator_rejection_witness",
            "observed_response_kind": OPERATOR_RESPONSE_MISSING_KIND,
            "response_record_ref": requested_evidence_ref,
            "response_record_required": True,
            "response_record_collected": False,
            "approval_effect": "no_approval_effect_without_explicit_response",
            "live_execution_authorized_after_response": False,
        },
        "witnesses_after_response": _witnesses_after_response(request),
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_RESPONSE_WITNESS_VALIDATOR)],
        "next_action": (
            "Collect an explicit operator approval or rejection response as separate "
            "evidence before effect receipt, adapter evidence, secret handoff, "
            "rollback proof, or live producer implementation."
        ),
    }


def _witnesses_after_response(request: Mapping[str, Any]) -> list[dict[str, Any]]:
    remaining_by_kind = {
        str(witness.get("witness_kind", "")): witness
        for witness in request.get("remaining_witnesses", ())
        if isinstance(witness, Mapping)
    }
    witnesses: list[dict[str, Any]] = []
    for witness_kind in REQUIRED_WITNESS_KINDS:
        evidence_ref = str(request.get("requested_evidence_ref", ""))
        if witness_kind != OPERATOR_APPROVAL_WITNESS_KIND:
            evidence_ref = str(_mapping(remaining_by_kind.get(witness_kind)).get("evidence_ref", ""))
        witnesses.append(
            {
                "witness_kind": witness_kind,
                "status": "AwaitingEvidence",
                "evidence_ref": evidence_ref,
                "blocks_live_producer": True,
                "authority_granted": False,
            }
        )
    return witnesses


def _approval_request_collection_binding(request: Mapping[str, Any]) -> dict[str, Any]:
    source_binding = _mapping(request.get("governed_collection_binding"))
    return {
        "binding_id": "binding.operator_response.approval_request_collection",
        "source_binding_id": str(source_binding.get("binding_id", "")),
        "source_collection_id": str(source_binding.get("collection_id", "")),
        "source_witness_kind": str(source_binding.get("witness_kind", "")),
        "source_requirements_evidence_ref": str(source_binding.get("requirements_evidence_ref", "")),
        "source_governed_artifact_ref": str(source_binding.get("governed_artifact_ref", "")),
        "source_validator_id": str(source_binding.get("validator_id", "")),
        "source_validator_command": str(source_binding.get("validator_command", "")),
        "source_approval_request_ref": f"approval-request://{OPERATOR_APPROVAL_REQUEST_ID}",
        "source_approval_request_id": OPERATOR_APPROVAL_REQUEST_ID,
        "source_request_artifact_ref": str(source_binding.get("request_artifact_ref", "")),
        "source_request_validator_id": str(source_binding.get("request_validator_id", "")),
        "source_request_validator_command": str(source_binding.get("request_validator_command", "")),
        "response_witness_id": OPERATOR_RESPONSE_WITNESS_ID,
        "response_witness_ref": "examples/agentic_service_harness_live_producer_operator_response_witness.local.json",
        "response_validator_id": OPERATOR_RESPONSE_WITNESS_VALIDATOR["validator_id"],
        "response_validator_command": OPERATOR_RESPONSE_WITNESS_VALIDATOR["command"],
        "binding_status": "AwaitingEvidence",
        "source_binding_status": str(source_binding.get("binding_status", "")),
        "source_collection_status": str(source_binding.get("collection_status", "")),
        "response_status": "AwaitingEvidence",
        "approval_collected": False,
        "response_record_collected": False,
        "approval_satisfied": False,
        "authority_granted": False,
        "live_execution_authorized": False,
        "blocks_live_producer": True,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
