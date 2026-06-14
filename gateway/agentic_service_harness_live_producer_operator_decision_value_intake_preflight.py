"""Agentic Service Harness live producer operator decision value intake preflight.

Purpose: define the required shape for a future explicit operator approval or
rejection value before any value is recorded or any live authority is granted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_pending_status.
Invariants:
  - The intake preflight is read-only and planning-only.
  - Generic continuation remains non-authorizing.
  - A future explicit value must carry witness evidence and matching scope.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_pending_status import (
    OPERATOR_DECISION_PENDING_STATUS_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionPendingStatus,
)
from gateway.agentic_service_harness_live_producer_operator_decision_record import (
    ACCEPTED_RECORD_KINDS,
    REQUIRED_DECISION_RECORD_FIELDS,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-intake-preflight"
)
OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-intake-preflight",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.py",
    "required_for_closure": True,
}
FORBIDDEN_DECISION_VALUE_FIELDS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)


class AgenticServiceHarnessLiveProducerOperatorDecisionValueIntakePreflight:
    """Produce an intake preflight from the blocked pending status."""

    def __init__(
        self,
        *,
        pending_status_source: AgenticServiceHarnessLiveProducerOperatorDecisionPendingStatus | None = None,
    ) -> None:
        self._pending_status_source = pending_status_source or AgenticServiceHarnessLiveProducerOperatorDecisionPendingStatus()

    def produce(self) -> dict[str, Any] | None:
        """Return an operator decision value intake preflight or None when unavailable."""
        pending_status = self._pending_status_source.produce()
        if not isinstance(pending_status, Mapping):
            return None
        return project_pending_status_to_value_intake_preflight(pending_status)


def project_pending_status_to_value_intake_preflight(
    pending_status: Mapping[str, Any],
) -> dict[str, Any]:
    """Project pending status into a future explicit-value intake contract."""
    status = deepcopy(dict(pending_status))
    scope = _mapping(status.get("scope"))
    return {
        "preflight_boundary_id": OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID,
        "schema_version": 1,
        "generated_at": str(status.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_pending_status_ref": f"pending-status://{OPERATOR_DECISION_PENDING_STATUS_ID}",
        "intake_status": "AwaitingEvidence",
        "current_input_kind": "generic_continuation",
        "schema_ready": True,
        "operator_value_collected": False,
        "generic_continuation_accepted_as_decision": False,
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
        "accepted_value_contracts": [
            {
                "decision_kind": decision_kind,
                "required": True,
                "status": "AwaitingEvidence",
                "required_fields": list(REQUIRED_DECISION_RECORD_FIELDS),
                "forbidden_fields": list(FORBIDDEN_DECISION_VALUE_FIELDS),
                "scope_must_match_pending_status": True,
                "witness_ref_required": True,
                "records_operator_intent_only": True,
                "grants_live_authority": False,
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
        "validators": [dict(OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_VALIDATOR)],
        "next_action": (
            "Provide one explicit operator decision value that satisfies the intake "
            "contract; this preflight itself records no value and grants no live authority."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
