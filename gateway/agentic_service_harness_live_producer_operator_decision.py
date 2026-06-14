"""Agentic Service Harness live producer operator decision evidence boundary.

Purpose: project the missing operator response witness into an explicit
decision evidence boundary that rejects generic continuation as approval.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_response.
Invariants:
  - Generic continuation never satisfies operator approval.
  - Decision evidence remains `AwaitingEvidence` until explicit approval or
    rejection evidence is separately recorded.
  - No live producer authority is granted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_response import (
    OPERATOR_RESPONSE_WITNESS_ID,
    AgenticServiceHarnessLiveProducerOperatorResponseWitness,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_EVIDENCE_ID = "agentic-service-harness-live-producer-operator-decision-evidence"
OPERATOR_DECISION_EVIDENCE_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-evidence",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py",
    "required_for_closure": True,
}
ACCEPTED_DECISION_KINDS = ("explicit_operator_approval", "explicit_operator_rejection")


class AgenticServiceHarnessLiveProducerOperatorDecisionEvidence:
    """Produce a decision evidence boundary from the missing response witness."""

    def __init__(
        self,
        *,
        response_witness_source: AgenticServiceHarnessLiveProducerOperatorResponseWitness | None = None,
    ) -> None:
        self._response_witness_source = response_witness_source or AgenticServiceHarnessLiveProducerOperatorResponseWitness()

    def produce(self) -> dict[str, Any] | None:
        """Return an operator decision evidence boundary or None when unavailable."""
        response_witness = self._response_witness_source.produce()
        if not isinstance(response_witness, Mapping):
            return None
        return project_operator_response_witness_to_decision_evidence(response_witness)


def project_operator_response_witness_to_decision_evidence(
    response_witness: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a missing response witness into an explicit decision boundary."""
    witness = deepcopy(dict(response_witness))
    scope = _mapping(witness.get("scope"))
    return {
        "evidence_boundary_id": OPERATOR_DECISION_EVIDENCE_ID,
        "schema_version": 1,
        "generated_at": str(witness.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_response_witness_ref": f"response-witness://{OPERATOR_RESPONSE_WITNESS_ID}",
        "decision_status": "AwaitingEvidence",
        "observed_input_kind": "generic_continuation",
        "generic_continuation_satisfies_approval": False,
        "approval_satisfied": False,
        "rejection_recorded": False,
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
        "accepted_decision_evidence": [
            {
                "decision_kind": decision_kind,
                "required": True,
                "status": "AwaitingEvidence",
                "authority_effect": "no_live_authority_without_all_witnesses",
            }
            for decision_kind in ACCEPTED_DECISION_KINDS
        ],
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_EVIDENCE_VALIDATOR)],
        "next_action": (
            "Collect an explicit operator approval or rejection record; generic continuation "
            "does not satisfy operator approval."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
