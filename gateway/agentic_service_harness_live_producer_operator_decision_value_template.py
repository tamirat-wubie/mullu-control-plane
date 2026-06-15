"""Agentic Service Harness explicit operator decision value templates.

Purpose: provide template-only approval and rejection value shapes after the
operator decision value request has been emitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_request.
Invariants:
  - Templates are not accepted as operator values.
  - Templates collect no operator value.
  - Templates grant no live producer authority.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision_record import ACCEPTED_RECORD_KINDS
from gateway.agentic_service_harness_live_producer_operator_decision_value_request import (
    OPERATOR_DECISION_VALUE_REQUEST_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionValueRequest,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_TEMPLATE_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-template"
)
OPERATOR_DECISION_VALUE_TEMPLATE_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-template",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_template.py",
    "required_for_closure": True,
}


class AgenticServiceHarnessLiveProducerOperatorDecisionValueTemplate:
    """Produce template-only explicit operator decision value shapes."""

    def __init__(
        self,
        *,
        request_source: AgenticServiceHarnessLiveProducerOperatorDecisionValueRequest | None = None,
    ) -> None:
        self._request_source = request_source or AgenticServiceHarnessLiveProducerOperatorDecisionValueRequest()

    def produce(self) -> dict[str, Any] | None:
        """Return a template-only value packet or None when unavailable."""
        value_request = self._request_source.produce()
        if not isinstance(value_request, Mapping):
            return None
        return project_value_request_to_value_template(value_request)


def project_value_request_to_value_template(value_request: Mapping[str, Any]) -> dict[str, Any]:
    """Project a value request into approval and rejection value templates."""
    request = deepcopy(dict(value_request))
    scope = _mapping(request.get("scope"))
    return {
        "template_packet_id": OPERATOR_DECISION_VALUE_TEMPLATE_ID,
        "schema_version": 1,
        "generated_at": str(request.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_value_request_ref": f"value-request://{OPERATOR_DECISION_VALUE_REQUEST_ID}",
        "template_status": "template_only_awaiting_operator_value",
        "requested_input_kind": "explicit_operator_decision_value",
        "operator_value_collected": False,
        "explicit_operator_value_present": False,
        "template_accepted_as_value": False,
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
        "decision_value_templates": [
            _template(decision_kind=decision_kind, scope=scope) for decision_kind in ACCEPTED_RECORD_KINDS
        ],
        "template_controls": {
            "template_only": True,
            "stores_operator_value": False,
            "accepts_template_as_value": False,
            "credential_values_allowed": False,
            "mutation_route_allowed": False,
            "live_authority_on_template": False,
        },
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_VALUE_TEMPLATE_VALIDATOR)],
        "next_action": (
            "Fill exactly one template as a separate explicit operator value; "
            "this template packet is not itself a value and grants no live authority."
        ),
    }


def _template(*, decision_kind: str, scope: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "decision_kind": decision_kind,
        "template_only": True,
        "accepted_as_value": False,
        "grants_live_authority": False,
        "field_templates": {
            "decision_kind": decision_kind,
            "operator_id": "operator_id_required",
            "decision_text": "write_explicit_operator_intent_here",
            "scope": {
                "tenant_id": str(scope.get("tenant_id", "")),
                "organization_id": str(scope.get("organization_id", "")),
                "project_id": str(scope.get("project_id", "")),
                "repository_connection_id": str(scope.get("repository_connection_id", "")),
            },
            "created_at": "YYYY-MM-DDTHH:MM:SSZ",
            "witness_ref": "witness_ref_required",
        },
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
