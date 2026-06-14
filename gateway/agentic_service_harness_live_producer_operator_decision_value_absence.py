"""Agentic Service Harness live producer operator decision value absence.

Purpose: project the pending operator decision record into a witness that no
explicit approval or rejection value has been provided.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_record.
Invariants:
  - Generic continuation is not an explicit operator decision value.
  - Approval and rejection values remain absent until separately recorded.
  - No live producer authority is granted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_record import (
    ACCEPTED_RECORD_KINDS,
    OPERATOR_DECISION_RECORD_ID,
    REQUIRED_DECISION_RECORD_FIELDS,
    AgenticServiceHarnessLiveProducerOperatorDecisionRecord,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_ABSENCE_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-absence"
)
OPERATOR_DECISION_VALUE_ABSENCE_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-absence",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py",
    "required_for_closure": True,
}


class AgenticServiceHarnessLiveProducerOperatorDecisionValueAbsence:
    """Produce an absence witness from the pending decision record."""

    def __init__(
        self,
        *,
        decision_record_source: AgenticServiceHarnessLiveProducerOperatorDecisionRecord | None = None,
    ) -> None:
        self._decision_record_source = decision_record_source or AgenticServiceHarnessLiveProducerOperatorDecisionRecord()

    def produce(self) -> dict[str, Any] | None:
        """Return an operator decision value absence witness or None when unavailable."""
        decision_record = self._decision_record_source.produce()
        if not isinstance(decision_record, Mapping):
            return None
        return project_decision_record_to_value_absence(decision_record)


def project_decision_record_to_value_absence(
    decision_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Project a pending decision record into an explicit value absence witness."""
    record = deepcopy(dict(decision_record))
    scope = _mapping(record.get("scope"))
    return {
        "absence_boundary_id": OPERATOR_DECISION_VALUE_ABSENCE_ID,
        "schema_version": 1,
        "generated_at": str(record.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_decision_record_ref": f"decision-record://{OPERATOR_DECISION_RECORD_ID}",
        "absence_status": "AwaitingEvidence",
        "observed_input_kind": "generic_continuation",
        "current_decision_kind": "none",
        "explicit_operator_value_present": False,
        "approval_value_present": False,
        "rejection_value_present": False,
        "decision_value_text_present": False,
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
        "missing_value_requirements": [
            {
                "decision_kind": decision_kind,
                "required": True,
                "status": "AwaitingEvidence",
                "required_value_shape": list(REQUIRED_DECISION_RECORD_FIELDS),
                "authority_effect": "missing_value_no_live_authority",
            }
            for decision_kind in ACCEPTED_RECORD_KINDS
        ],
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_VALUE_ABSENCE_VALIDATOR)],
        "next_action": (
            "Provide an explicit operator approval or rejection value with witness_ref; "
            "generic continuation is not a decision value."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
