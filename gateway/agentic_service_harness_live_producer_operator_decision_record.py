"""Agentic Service Harness live producer operator decision record boundary.

Purpose: project decision evidence into a pending explicit operator decision
record intake envelope.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision.
Invariants:
  - Generic continuation records no operator approval or rejection.
  - The decision record remains `AwaitingEvidence` until explicit operator
    decision evidence is separately recorded.
  - No live producer authority is granted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_decision import (
    OPERATOR_DECISION_EVIDENCE_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionEvidence,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_RECORD_ID = "agentic-service-harness-live-producer-operator-decision-record"
OPERATOR_DECISION_RECORD_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-record",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py",
    "required_for_closure": True,
}
ACCEPTED_RECORD_KINDS = ("explicit_operator_approval", "explicit_operator_rejection")
REQUIRED_DECISION_RECORD_FIELDS = (
    "decision_kind",
    "operator_id",
    "decision_text",
    "scope",
    "created_at",
    "witness_ref",
)


class AgenticServiceHarnessLiveProducerOperatorDecisionRecord:
    """Produce a pending decision record envelope from decision evidence."""

    def __init__(
        self,
        *,
        decision_evidence_source: AgenticServiceHarnessLiveProducerOperatorDecisionEvidence | None = None,
    ) -> None:
        self._decision_evidence_source = decision_evidence_source or AgenticServiceHarnessLiveProducerOperatorDecisionEvidence()

    def produce(self) -> dict[str, Any] | None:
        """Return a pending operator decision record envelope or None when unavailable."""
        decision_evidence = self._decision_evidence_source.produce()
        if not isinstance(decision_evidence, Mapping):
            return None
        return project_decision_evidence_to_decision_record(decision_evidence)


def project_decision_evidence_to_decision_record(
    decision_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Project decision evidence into a pending explicit decision record envelope."""
    evidence = deepcopy(dict(decision_evidence))
    scope = _mapping(evidence.get("scope"))
    return {
        "record_boundary_id": OPERATOR_DECISION_RECORD_ID,
        "schema_version": 1,
        "generated_at": str(evidence.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_decision_evidence_ref": f"decision-evidence://{OPERATOR_DECISION_EVIDENCE_ID}",
        "record_status": "AwaitingEvidence",
        "current_input_kind": "generic_continuation",
        "current_decision_kind": "none",
        "generic_continuation_records_decision": False,
        "approval_recorded": False,
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
        "accepted_record_shapes": [
            {
                "decision_kind": decision_kind,
                "required": True,
                "status": "AwaitingEvidence",
                "required_fields": list(REQUIRED_DECISION_RECORD_FIELDS),
                "authority_effect": "records_operator_intent_only_no_live_authority",
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
        "validators": [dict(OPERATOR_DECISION_RECORD_VALIDATOR)],
        "next_action": (
            "Record an explicit operator approval or rejection with the required fields; "
            "generic continuation records no decision."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
