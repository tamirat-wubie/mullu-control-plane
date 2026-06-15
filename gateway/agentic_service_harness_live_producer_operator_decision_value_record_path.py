"""Agentic Service Harness operator decision value record path.

Purpose: define the future value-record path while keeping it blocked until an
actual explicit operator decision value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_collection_gate.
Invariants:
  - No operator decision value record is created by this path.
  - No collection gate is satisfied by this path.
  - No live producer authority is granted by this path.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_value_collection_gate import (
    OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionValueCollectionGate,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_RECORD_PATH_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-record-path"
)
OPERATOR_DECISION_VALUE_RECORD_PATH_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-record-path",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record_path.py",
    "required_for_closure": True,
}


class AgenticServiceHarnessLiveProducerOperatorDecisionValueRecordPath:
    """Produce a blocked value-record path from the collection gate."""

    def __init__(
        self,
        *,
        collection_gate_source: AgenticServiceHarnessLiveProducerOperatorDecisionValueCollectionGate | None = None,
    ) -> None:
        self._collection_gate_source = collection_gate_source or (
            AgenticServiceHarnessLiveProducerOperatorDecisionValueCollectionGate()
        )

    def produce(self) -> dict[str, Any] | None:
        """Return a blocked value-record path or None when unavailable."""
        collection_gate = self._collection_gate_source.produce()
        if not isinstance(collection_gate, Mapping):
            return None
        return project_collection_gate_to_value_record_path(collection_gate)


def project_collection_gate_to_value_record_path(collection_gate: Mapping[str, Any]) -> dict[str, Any]:
    """Project a blocked collection gate into a blocked value-record path."""
    gate = deepcopy(dict(collection_gate))
    scope = _mapping(gate.get("scope"))
    return {
        "record_path_id": OPERATOR_DECISION_VALUE_RECORD_PATH_ID,
        "schema_version": 1,
        "generated_at": str(gate.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_collection_gate_ref": f"collection-gate://{OPERATOR_DECISION_VALUE_COLLECTION_GATE_ID}",
        "path_status": "ready_blocked_awaiting_explicit_operator_value",
        "requested_input_kind": "explicit_operator_decision_value",
        "accepted_record_kinds": ["explicit_operator_approval", "explicit_operator_rejection"],
        "rejected_input_kinds": ["generic_continuation", "template_packet"],
        "record_contract_ready": True,
        "record_path_admitted": False,
        "actual_operator_decision_value_present": False,
        "operator_value_record_created": False,
        "collection_gate_satisfied": False,
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
        "record_controls": {
            "requires_collection_gate_satisfied": True,
            "requires_actual_operator_value": True,
            "accepts_generic_continuation": False,
            "accepts_template_packet": False,
            "creates_operator_value_record": False,
            "stores_operator_value": False,
            "admits_mutation_route": False,
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
        "validators": [dict(OPERATOR_DECISION_VALUE_RECORD_PATH_VALIDATOR)],
        "next_action": (
            "Collect an actual explicit operator approval or rejection value before "
            "creating any governed operator decision value record."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
