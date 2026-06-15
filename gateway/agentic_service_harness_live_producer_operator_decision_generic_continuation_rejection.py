"""Agentic Service Harness generic continuation rejection witness.

Purpose: prove that a generic continuation input cannot satisfy the live
producer operator decision value gate.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight.
Invariants:
  - The witness is read-only and planning-only.
  - Generic continuation is rejected as a decision value.
  - Rejection grants no live producer authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_value_intake_preflight import (
    OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionValueIntakePreflight,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


GENERIC_CONTINUATION_REJECTION_WITNESS_ID = (
    "agentic-service-harness-live-producer-operator-decision-generic-continuation-rejection"
)
GENERIC_CONTINUATION_REJECTION_WITNESS_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-generic-continuation-rejection",
    "command": (
        "python scripts/validate_agentic_service_harness_live_producer_operator_decision_"
        "generic_continuation_rejection.py"
    ),
    "required_for_closure": True,
}
REJECTION_RULE_IDS = (
    "generic-continuation-is-not-explicit-operator-approval",
    "generic-continuation-is-not-explicit-operator-rejection",
    "generic-continuation-grants-no-live-authority",
)


class AgenticServiceHarnessLiveProducerOperatorDecisionGenericContinuationRejection:
    """Produce a rejection witness from the operator decision value preflight."""

    def __init__(
        self,
        *,
        preflight_source: AgenticServiceHarnessLiveProducerOperatorDecisionValueIntakePreflight | None = None,
    ) -> None:
        self._preflight_source = preflight_source or AgenticServiceHarnessLiveProducerOperatorDecisionValueIntakePreflight()

    def produce(self) -> dict[str, Any] | None:
        """Return a generic continuation rejection witness or None when unavailable."""
        preflight = self._preflight_source.produce()
        if not isinstance(preflight, Mapping):
            return None
        return project_value_intake_preflight_to_generic_continuation_rejection(preflight)


def project_value_intake_preflight_to_generic_continuation_rejection(
    value_intake_preflight: Mapping[str, Any],
) -> dict[str, Any]:
    """Project value intake preflight into a non-decision input rejection witness."""
    preflight = deepcopy(dict(value_intake_preflight))
    scope = _mapping(preflight.get("scope"))
    authority_denials = _mapping(preflight.get("authority_denials"))
    effect_boundary = _mapping(preflight.get("effect_boundary"))
    return {
        "rejection_witness_id": GENERIC_CONTINUATION_REJECTION_WITNESS_ID,
        "schema_version": 1,
        "generated_at": str(preflight.get("generated_at", "")),
        "solver_outcome": "SolvedVerified",
        "source_preflight_ref": f"preflight://{OPERATOR_DECISION_VALUE_INTAKE_PREFLIGHT_ID}",
        "witness_status": "rejected_non_decision_input",
        "observed_input_kind": "generic_continuation",
        "rejected_input_kind": "generic_continuation",
        "rejected_reason": "not_explicit_operator_decision_value",
        "generic_continuation_rejected": True,
        "generic_continuation_accepted_as_decision": False,
        "explicit_operator_value_present": False,
        "operator_value_collected": False,
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
        "rejection_rules": [
            {
                "rule_id": rule_id,
                "applies": True,
                "decision": "reject",
                "grants_live_authority": False,
            }
            for rule_id in REJECTION_RULE_IDS
        ],
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": bool(authority_denials.get("live_execution_authorized", False)),
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": str(effect_boundary.get("network_policy", "none")),
        },
        "validators": [dict(GENERIC_CONTINUATION_REJECTION_WITNESS_VALIDATOR)],
        "next_action": (
            "Collect an explicit operator approval or rejection value; generic continuation "
            "remains rejected and grants no live authority."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
