"""Agentic Service Harness live producer operator decision pending status.

Purpose: project decision value absence into a read-only platform status that
keeps live producer authority blocked until an explicit operator value exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_absence.
Invariants:
  - Pending status is read-only and planning-only.
  - Generic continuation remains non-authorizing.
  - No live producer authority is granted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_record import (
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_operator_decision_value_absence import (
    OPERATOR_DECISION_VALUE_ABSENCE_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionValueAbsence,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_PENDING_STATUS_ID = (
    "agentic-service-harness-live-producer-operator-decision-pending-status"
)
OPERATOR_DECISION_PENDING_STATUS_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-pending-status",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py",
    "required_for_closure": True,
}


class AgenticServiceHarnessLiveProducerOperatorDecisionPendingStatus:
    """Produce a read-only pending status from the value absence witness."""

    def __init__(
        self,
        *,
        value_absence_source: AgenticServiceHarnessLiveProducerOperatorDecisionValueAbsence | None = None,
    ) -> None:
        self._value_absence_source = value_absence_source or AgenticServiceHarnessLiveProducerOperatorDecisionValueAbsence()

    def produce(self) -> dict[str, Any] | None:
        """Return an operator decision pending status or None when unavailable."""
        value_absence = self._value_absence_source.produce()
        if not isinstance(value_absence, Mapping):
            return None
        return project_value_absence_to_pending_status(value_absence)


def project_value_absence_to_pending_status(value_absence: Mapping[str, Any]) -> dict[str, Any]:
    """Project value absence into a platform-facing blocked pending status."""
    absence = deepcopy(dict(value_absence))
    scope = _mapping(absence.get("scope"))
    return {
        "status_boundary_id": OPERATOR_DECISION_PENDING_STATUS_ID,
        "schema_version": 1,
        "generated_at": str(absence.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_value_absence_ref": f"value-absence://{OPERATOR_DECISION_VALUE_ABSENCE_ID}",
        "pending_status": "blocked_pending_operator_decision_value",
        "decision_gate_state": "blocked",
        "operator_action_required": True,
        "generic_continuation_accepted_as_decision": False,
        "explicit_operator_value_present": False,
        "approval_value_present": False,
        "rejection_value_present": False,
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
        "pending_requirements": [
            {
                "decision_kind": decision_kind,
                "required": True,
                "status": "AwaitingEvidence",
                "required_value_shape": list(REQUIRED_DECISION_RECORD_FIELDS),
                "blocks_live_authority": True,
            }
            for decision_kind in ACCEPTED_RECORD_KINDS
        ],
        "block_reasons": [
            "explicit_operator_approval_missing",
            "explicit_operator_rejection_missing",
            "generic_continuation_not_decision_value",
        ],
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_PENDING_STATUS_VALIDATOR)],
        "next_action": (
            "Record an explicit operator approval or rejection value before any live "
            "producer implementation or authority transition."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
