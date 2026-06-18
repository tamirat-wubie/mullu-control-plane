"""Agentic Service Harness operator decision value record.

Purpose: record an explicit operator approval or rejection value while keeping
live producer authority blocked until the remaining witnesses exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_operator_decision_value_record_path.
Invariants:
  - An operator approval satisfies only the operator approval witness.
  - Remaining live producer witnesses continue to block live execution.
  - No UI, mutation endpoint, external adapter, secret value, or runtime write
    authority is granted by this record.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_operator_approval import REMAINING_WITNESS_KINDS
from gateway.agentic_service_harness_live_producer_operator_decision_value_record_path import (
    OPERATOR_DECISION_VALUE_RECORD_PATH_ID,
    AgenticServiceHarnessLiveProducerOperatorDecisionValueRecordPath,
)
from gateway.agentic_service_harness_live_producer_witness_requirements import FALSE_AUTHORITY_FLAGS


OPERATOR_DECISION_VALUE_RECORD_ID = (
    "agentic-service-harness-live-producer-operator-decision-value-record"
)
OPERATOR_DECISION_VALUE_RECORD_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-operator-decision-value-record",
    "command": "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record.py",
    "required_for_closure": True,
}
DECISION_VALUE_TO_KIND = {
    "approve": "explicit_operator_approval",
    "reject": "explicit_operator_rejection",
}


class AgenticServiceHarnessLiveProducerOperatorDecisionValueRecord:
    """Produce a bounded operator decision value record from the record path."""

    def __init__(
        self,
        *,
        record_path_source: AgenticServiceHarnessLiveProducerOperatorDecisionValueRecordPath | None = None,
        operator_decision_value: str = "approve",
    ) -> None:
        self._record_path_source = record_path_source or (
            AgenticServiceHarnessLiveProducerOperatorDecisionValueRecordPath()
        )
        self._operator_decision_value = operator_decision_value

    def produce(self) -> dict[str, Any] | None:
        """Return a bounded operator decision value record or None when unavailable."""
        record_path = self._record_path_source.produce()
        if not isinstance(record_path, Mapping):
            return None
        return project_record_path_to_operator_decision_value_record(
            record_path,
            operator_decision_value=self._operator_decision_value,
        )


def project_record_path_to_operator_decision_value_record(
    record_path: Mapping[str, Any],
    *,
    operator_decision_value: str,
) -> dict[str, Any]:
    """Project an explicit operator value into a non-authorizing record."""
    normalized_value = operator_decision_value.strip().lower()
    decision_kind = DECISION_VALUE_TO_KIND.get(normalized_value, "")
    path = deepcopy(dict(record_path))
    scope = _mapping(path.get("scope"))
    approval_satisfied = decision_kind == "explicit_operator_approval"
    rejection_recorded = decision_kind == "explicit_operator_rejection"
    return {
        "record_id": OPERATOR_DECISION_VALUE_RECORD_ID,
        "schema_version": 1,
        "generated_at": str(path.get("generated_at", "")),
        "solver_outcome": "SolvedVerified" if decision_kind else "GovernanceBlocked",
        "source_record_path_ref": f"record-path://{OPERATOR_DECISION_VALUE_RECORD_PATH_ID}",
        "source_record_path_status": str(path.get("path_status", "")),
        "operator_input_ref": "codex-thread://operator-message/2026-06-18/approve",
        "decision_kind": decision_kind or "invalid_operator_decision_value",
        "normalized_decision_value": normalized_value if decision_kind else "",
        "raw_input_serialized": False,
        "operator_value_record_created": bool(decision_kind),
        "actual_operator_decision_value_present": bool(decision_kind),
        "operator_approval_witness_satisfied": approval_satisfied,
        "operator_rejection_recorded": rejection_recorded,
        "approval_status": "Satisfied" if approval_satisfied else "Rejected",
        "remaining_live_witnesses_status": "AwaitingEvidence",
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
        "remaining_witnesses": [
            {
                "witness_kind": witness_kind,
                "status": "AwaitingEvidence",
                "blocks_live_producer": True,
            }
            for witness_kind in REMAINING_WITNESS_KINDS
        ],
        "record_controls": {
            "accepts_generic_continuation": False,
            "accepts_template_packet": False,
            "stores_raw_operator_input": False,
            "stores_secret_values": False,
            "admits_mutation_route": False,
            "grants_live_authority": False,
            "requires_remaining_witnesses": True,
        },
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(OPERATOR_DECISION_VALUE_RECORD_VALIDATOR)],
        "next_action": (
            "Collect effect receipt, external adapter evidence, secret handoff, "
            "and rollback proof before any live producer implementation."
        ),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
