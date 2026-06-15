"""Agentic Service Harness operator decision value collection gate.

Purpose: keep the live producer blocked after template publication until an
actual explicit operator decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_template.
Invariants:
  - No collection route is admitted by this gate.
  - No operator value is collected by this gate.
  - No live producer authority is granted by this gate.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_value_template import (
    OPERATOR_DECISION_VALUE_TEMPLATE_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionValueTemplate,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-collection-gate"
)
OPERATOR_DECISION_VALUE_COLLECTION_GATE_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-collection-gate",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.py",
    "required_for_closure": True,
}


class AgenticServiceHarnessLiveProducerOperatorDecisionValueCollectionGate:
    """Produce a blocked collection gate from the template packet."""

    def __init__(
        self,
        *,
        template_source: AgenticServiceHarnessLiveProducerOperatorDecisionValueTemplate | None = None,
    ) -> None:
        self._template_source = template_source or AgenticServiceHarnessLiveProducerOperatorDecisionValueTemplate()

    def produce(self) -> dict[str, Any] | None:
        """Return a blocked collection gate or None when unavailable."""
        template_packet = self._template_source.produce()
        if not isinstance(template_packet, Mapping):
            return None
        return project_value_template_to_collection_gate(template_packet)


def project_value_template_to_collection_gate(template_packet: Mapping[str, Any]) -> dict[str, Any]:
    """Project template packet into a blocked value collection gate."""
    template = deepcopy(dict(template_packet))
    scope = _mapping(template.get("scope"))
    return {
        "collection_gate_id": OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID,
        "schema_version": 1,
        "generated_at": str(template.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_template_ref": f"value-template://{OPERATOR_DECISION_VALUE_TEMPLATE_ID}",
        "gate_status": "blocked_awaiting_explicit_operator_value",
        "requested_input_kind": "explicit_operator_decision_value",
        "accepted_input_kinds": ["explicit_operator_approval", "explicit_operator_rejection"],
        "rejected_input_kinds": ["generic_continuation", "template_packet"],
        "collection_route_admitted": False,
        "template_accepted_as_value": False,
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
        "gate_controls": {
            "requires_actual_operator_value": True,
            "accepts_generic_continuation": False,
            "accepts_template_packet": False,
            "admits_mutation_route": False,
            "stores_operator_value": False,
            "grants_live_authority": False,
        },
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_VALUE_COLLECTION_GATE_VALIDATOR)],
        "next_action": (
            "Provide an actual explicit operator approval or rejection value through "
            "a future governed value-record path; this gate admits no collection route."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
