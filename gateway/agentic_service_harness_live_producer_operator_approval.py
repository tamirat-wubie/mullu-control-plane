"""Agentic Service Harness live producer operator approval request.

Purpose: project missing live producer witness requirements into the first
operator approval request packet without collecting approval or authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_witness_requirements.
Invariants:
  - Request output is read-only, non-terminal, and `AwaitingEvidence`.
  - Approval is not collected by this packet.
  - Live execution, runtime writes, mutation routes, and external effects
    remain denied until all required witnesses are separately verified.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_witness_requirements import (
    FALSE_AUTHORITY_FLAGS,
    GOVERNED_WITNESS_COLLECTION,
    REQUIRED_WITNESS_KINDS,
    WITNESS_REQUIREMENTS_ID,
    AgenticServiceHarnessLiveProducerWitnessRequirements,
)


OPERATOR_APPROVAL_REQUEST_ID = "agentic-service-harness-live-producer-operator-approval-request"
OPERATOR_APPROVAL_REQUEST_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-approval-request",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py",
    "required_for_closure": True,
}
OPERATOR_APPROVAL_WITNESS_KIND = "operator_approval"
REMAINING_WITNESS_KINDS = tuple(
    witness_kind for witness_kind in REQUIRED_WITNESS_KINDS if witness_kind != OPERATOR_APPROVAL_WITNESS_KIND
)
ALLOWED_RESPONSE_KINDS = (
    "record_operator_approval_witness",
    "record_operator_rejection_witness",
)


class AgenticServiceHarnessLiveProducerOperatorApprovalRequest:
    """Produce an operator approval request from witness requirements."""

    def __init__(
        self,
        *,
        witness_requirements_source: AgenticServiceHarnessLiveProducerWitnessRequirements | None = None,
    ) -> None:
        self._witness_requirements_source = (
            witness_requirements_source or AgenticServiceHarnessLiveProducerWitnessRequirements()
        )

    def produce(self) -> dict[str, Any] | None:
        """Return an operator approval request or None when requirements are unavailable."""
        witness_requirements = self._witness_requirements_source.produce()
        if not isinstance(witness_requirements, Mapping):
            return None
        return project_witness_requirements_to_operator_approval_request(witness_requirements)


def project_witness_requirements_to_operator_approval_request(
    witness_requirements: Mapping[str, Any],
) -> dict[str, Any]:
    """Project missing witness requirements into a non-authorizing approval request."""
    requirements = deepcopy(dict(witness_requirements))
    operator_witness = _find_witness(requirements, OPERATOR_APPROVAL_WITNESS_KIND)
    scope = _mapping(requirements.get("scope"))
    return {
        "request_id": OPERATOR_APPROVAL_REQUEST_ID,
        "schema_version": 1,
        "generated_at": str(requirements.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_requirements_ref": f"requirements://{WITNESS_REQUIREMENTS_ID}",
        "source_admission_gate_ref": str(requirements.get("source_admission_gate_ref", "")),
        "witness_kind": OPERATOR_APPROVAL_WITNESS_KIND,
        "requested_evidence_ref": str(operator_witness.get("evidence_ref", "")),
        "governed_collection_binding": _governed_collection_binding(requirements),
        "approval_status": "AwaitingEvidence",
        "approval_collected": False,
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
        "approval_request": {
            "approval_request_id": "approval-request.operator-live-producer",
            "approver_role": "operator",
            "question": (
                "Record whether the operator permits creating future planning artifacts "
                "for live task/run producer implementation after all remaining witnesses exist."
            ),
            "decision_required": "operator_response_required",
            "allowed_response_kinds": list(ALLOWED_RESPONSE_KINDS),
            "default_response_kind": "record_operator_rejection_witness",
            "response_record_required": True,
            "response_record_collected": False,
            "approval_effect": "satisfies_operator_approval_witness_only",
            "live_execution_authorized_after_response": False,
        },
        "remaining_witnesses": _remaining_witnesses(requirements),
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_APPROVAL_REQUEST_VALIDATOR)],
        "next_action": (
            "Record an operator response as a separate witness before effect receipt, "
            "adapter evidence, secret handoff, rollback proof, or live producer implementation."
        ),
    }


def _remaining_witnesses(requirements: Mapping[str, Any]) -> list[dict[str, Any]]:
    witnesses = requirements.get("witnesses")
    if not isinstance(witnesses, list):
        return []
    remaining: list[dict[str, Any]] = []
    for witness_kind in REMAINING_WITNESS_KINDS:
        witness = _find_witness(requirements, witness_kind)
        remaining.append(
            {
                "witness_kind": witness_kind,
                "status": "AwaitingEvidence",
                "evidence_ref": str(witness.get("evidence_ref", "")),
                "blocks_live_producer": True,
            }
        )
    return remaining


def _governed_collection_binding(requirements: Mapping[str, Any]) -> dict[str, Any]:
    collection_entry = _find_collection_entry(requirements, OPERATOR_APPROVAL_WITNESS_KIND)
    expected_entry = _expected_collection_entry(OPERATOR_APPROVAL_WITNESS_KIND)
    artifact_ref = str(collection_entry.get("governed_artifact_ref", expected_entry.get("governed_artifact_ref", "")))
    validator_id = str(collection_entry.get("validator_id", expected_entry.get("validator_id", "")))
    validator_command = str(collection_entry.get("validator_command", expected_entry.get("validator_command", "")))
    return {
        "binding_id": "binding.operator_approval.governed_witness_collection",
        "collection_id": str(collection_entry.get("collection_id", "collection.operator_approval")),
        "witness_kind": OPERATOR_APPROVAL_WITNESS_KIND,
        "requirements_evidence_ref": str(
            collection_entry.get(
                "requirements_evidence_ref",
                expected_entry.get("requirements_evidence_ref", ""),
            )
        ),
        "governed_artifact_ref": artifact_ref,
        "validator_id": validator_id,
        "validator_command": validator_command,
        "source_requirements_ref": f"requirements://{WITNESS_REQUIREMENTS_ID}",
        "request_id": OPERATOR_APPROVAL_REQUEST_ID,
        "request_artifact_ref": "examples/agentic_service_harness_live_producer_operator_approval_request.local.json",
        "request_validator_id": OPERATOR_APPROVAL_REQUEST_VALIDATOR["validator_id"],
        "request_validator_command": OPERATOR_APPROVAL_REQUEST_VALIDATOR["command"],
        "binding_status": "AwaitingEvidence",
        "collection_status": "AwaitingEvidence",
        "authority_granted": False,
        "blocks_live_producer": True,
        "approval_collected": False,
        "live_execution_authorized": False,
    }


def _find_collection_entry(requirements: Mapping[str, Any], witness_kind: str) -> Mapping[str, Any]:
    collection = requirements.get("governed_witness_collection")
    if not isinstance(collection, list):
        return {}
    for entry in collection:
        if isinstance(entry, Mapping) and entry.get("witness_kind") == witness_kind:
            return entry
    return {}


def _expected_collection_entry(witness_kind: str) -> Mapping[str, Any]:
    for entry in GOVERNED_WITNESS_COLLECTION:
        if entry.get("witness_kind") == witness_kind:
            return entry
    return {}


def _find_witness(requirements: Mapping[str, Any], witness_kind: str) -> Mapping[str, Any]:
    witnesses = requirements.get("witnesses")
    if not isinstance(witnesses, list):
        return {}
    for witness in witnesses:
        if isinstance(witness, Mapping) and witness.get("witness_kind") == witness_kind:
            return witness
    return {}


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
