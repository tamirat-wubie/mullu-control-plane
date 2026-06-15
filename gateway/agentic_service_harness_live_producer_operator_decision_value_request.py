"""Agentic Service Harness explicit operator decision value request.

Purpose: request the exact future operator approval or rejection value after
generic continuation has been rejected as a non-decision input.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.
Invariants:
  - The request is read-only and planning-only.
  - The request records no operator value.
  - The request grants no live producer authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection import (
    GENERIC_CONTINUATION_REJECTION_WITNESS_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionGenericContinuationRejection,
)
from gateway.agentic_service_harness_live_producer_operator_decision_record import (
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight import (
    FORBIDDEN_DECISION_VALUE_FIELDS,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_REQUEST_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-request"
)
OPERATOR_DECISION_VALUE_REQUEST_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-request",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_request.py",
    "required_for_closure": True,
}


class AgenticServiceHarnessLiveProducerOperatorDecisionValueRequest:
    """Produce an explicit operator decision value request packet."""

    def __init__(
        self,
        *,
        rejection_source: AgenticServiceHarnessLiveProducerOperatorDecisionGenericContinuationRejection | None = None,
    ) -> None:
        self._rejection_source = (
            rejection_source or AgenticServiceHarnessLiveProducerOperatorDecisionGenericContinuationRejection()
        )

    def produce(self) -> dict[str, Any] | None:
        """Return an explicit value request or None when unavailable."""
        rejection_witness = self._rejection_source.produce()
        if not isinstance(rejection_witness, Mapping):
            return None
        return project_generic_continuation_rejection_to_value_request(rejection_witness)


def project_generic_continuation_rejection_to_value_request(
    rejection_witness: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a generic continuation rejection into an explicit value request."""
    witness = deepcopy(dict(rejection_witness))
    scope = _mapping(witness.get("scope"))
    return {
        "request_id": OPERATOR_DECISION_VALUE_REQUEST_ID,
        "schema_version": 1,
        "generated_at": str(witness.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_rejection_witness_ref": f"rejection-witness://{GENERIC_CONTINUATION_REJECTION_WITNESS_ID}",
        "request_status": "awaiting_explicit_operator_decision_value",
        "requested_input_kind": "explicit_operator_decision_value",
        "rejected_input_kind": "generic_continuation",
        "generic_continuation_rejected": True,
        "operator_value_collected": False,
        "explicit_operator_value_present": False,
        "authority_granted": False,
        "planning_only": True,
        "read_only": True,
        "live_producer_implemented": False,
        "terminal_closure": False,
        "scope": {
            "tenant_id": str(scope.get("tenant_id", "")),
            "organization_id": str(scope.get("organization_id", "")),
            "project_id": str(scope.get("project_id", "")),
            "repository_connection_id": str(scope.get("repository_connection_id", "")),
            "read_only": True,
        },
        "decision_value_requirements": [
            {
                "decision_kind": decision_kind,
                "required": True,
                "status": "AwaitingEvidence",
                "required_fields": list(REQUIRED_DECISION_RECORD_FIELDS),
                "forbidden_fields": list(FORBIDDEN_DECISION_VALUE_FIELDS),
                "scope_must_match_request": True,
                "witness_ref_required": True,
                "records_operator_intent_only": True,
                "grants_live_authority": False,
            }
            for decision_kind in ACCEPTED_RECORD_KINDS
        ],
        "request_controls": {
            "freeform_continuation_allowed": False,
            "credential_values_allowed": False,
            "mutation_route_allowed": False,
            "self_authorization_allowed": False,
            "live_authority_on_request": False,
        },
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_VALUE_REQUEST_VALIDATOR)],
        "next_action": (
            "Provide an explicit operator approval or rejection value matching the "
            "required fields; this request records no value and grants no live authority."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
