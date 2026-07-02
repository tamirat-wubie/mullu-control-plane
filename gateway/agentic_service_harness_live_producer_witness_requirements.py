"""Agentic Service Harness live producer witness requirements.

Purpose: project the blocked live producer admission gate into explicit
missing witness requirements before any live producer implementation exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_producer_admission.
Invariants:
  - Requirements output is read-only, non-terminal, and `AwaitingEvidence`.
  - Witness records never grant live execution authority.
  - UI, mutation, adapter, branch, pull-request, deployment, DNS, secret,
    runtime write, and destructive-operation authority remain denied.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from gateway.agentic_service_harness_live_producer_admission import (
    ADMISSION_GATE_ID,
    AgenticServiceHarnessLiveProducerAdmissionGate,
)


WITNESS_REQUIREMENTS_ID = "agentic-service-harness-live-producer-witness-requirements"
WITNESS_REQUIREMENTS_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-witness-requirements",
    "command": "python scripts/validate_agentic_service_harness_live_producer_witness_requirements.py",
    "required_for_closure": True,
}
FALSE_AUTHORITY_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "runtime_state_written",
)
REQUIRED_WITNESS_KINDS = (
    "operator_approval",
    "effect_receipt",
    "external_adapter_evidence",
    "secret_handoff",
    "rollback_proof",
)
GOVERNED_WITNESS_COLLECTION = (
    {
        "witness_kind": "operator_approval",
        "requirements_evidence_ref": "approval://operator-live-producer-approval-required",
        "governed_artifact_ref": "examples/agentic_service_harness_live_producer_operator_approval_request.local.json",
        "validator_id": "agentic-service-harness-live-producer-operator-approval-request",
        "validator_command": "python scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py",
    },
    {
        "witness_kind": "effect_receipt",
        "requirements_evidence_ref": "receipt://agentic-service-harness/live-producer-effect-receipt-required",
        "governed_artifact_ref": "examples/agentic_service_harness_live_producer_effect_receipt_preflight.local.json",
        "validator_id": "agentic-service-harness-live-producer-effect-receipt-preflight",
        "validator_command": "python scripts/validate_agentic_service_harness_live_producer_effect_receipt_preflight.py",
    },
    {
        "witness_kind": "external_adapter_evidence",
        "requirements_evidence_ref": "evidence://agentic-service-harness/external-adapter-live-evidence-required",
        "governed_artifact_ref": "examples/agentic_service_harness_live_producer_external_adapter_evidence_preflight.local.json",
        "validator_id": "agentic-service-harness-live-producer-external-adapter-evidence-preflight",
        "validator_command": "python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight.py",
    },
    {
        "witness_kind": "secret_handoff",
        "requirements_evidence_ref": "secret-handoff://agentic-service-harness/live-producer-required",
        "governed_artifact_ref": "examples/agentic_service_harness_live_producer_secret_handoff_preflight.local.json",
        "validator_id": "agentic-service-harness-live-producer-secret-handoff-preflight",
        "validator_command": "python scripts/validate_agentic_service_harness_live_producer_secret_handoff_preflight.py",
    },
    {
        "witness_kind": "rollback_proof",
        "requirements_evidence_ref": "rollback://agentic-service-harness/live-producer-required",
        "governed_artifact_ref": "examples/agentic_service_harness_live_producer_rollback_proof_preflight.local.json",
        "validator_id": "agentic-service-harness-live-producer-rollback-proof-preflight",
        "validator_command": "python scripts/validate_agentic_service_harness_live_producer_rollback_proof_preflight.py",
    },
)


class AgenticServiceHarnessLiveProducerWitnessRequirements:
    """Produce missing witness requirements from the blocked admission gate."""

    def __init__(
        self,
        *,
        admission_gate_source: AgenticServiceHarnessLiveProducerAdmissionGate | None = None,
    ) -> None:
        self._admission_gate_source = admission_gate_source or AgenticServiceHarnessLiveProducerAdmissionGate()

    def produce(self) -> dict[str, Any] | None:
        """Return witness requirements or None when admission gate is unavailable."""
        admission_gate = self._admission_gate_source.produce()
        if not isinstance(admission_gate, Mapping):
            return None
        return project_admission_gate_to_witness_requirements(admission_gate)


def project_admission_gate_to_witness_requirements(
    admission_gate: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one blocked admission gate into missing witness requirements."""
    gate = deepcopy(dict(admission_gate))
    scope = _mapping(gate.get("scope"))
    required_evidence = _mapping(gate.get("required_evidence"))
    return {
        "requirements_id": WITNESS_REQUIREMENTS_ID,
        "schema_version": 1,
        "generated_at": str(gate.get("generated_at", "")),
        "solver_outcome": "AwaitingEvidence",
        "source_admission_gate_ref": f"admission-gate://{ADMISSION_GATE_ID}",
        "admission_decision": "blocked",
        "planning_only": True,
        "read_only": True,
        "live_producer_implemented": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure": False,
        "scope": {
            "tenant_id": str(scope.get("tenant_id", "")),
            "organization_id": str(scope.get("organization_id", "")),
            "project_id": str(scope.get("project_id", "")),
            "repository_connection_id": str(scope.get("repository_connection_id", "")),
            "read_only": True,
        },
        "witnesses": _witnesses(required_evidence),
        "governed_witness_collection": _governed_witness_collection(),
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": "none",
        },
        "validators": [dict(WITNESS_REQUIREMENTS_VALIDATOR)],
        "next_action": (
            "Collect these five witnesses as separate governed evidence before "
            "revisiting live producer implementation."
        ),
    }


def _witnesses(required_evidence: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        _witness(
            witness_kind="operator_approval",
            evidence_ref=str(required_evidence.get("approval_gate_ref", "")),
            next_action="Obtain explicit operator approval for live producer implementation.",
        ),
        _witness(
            witness_kind="effect_receipt",
            evidence_ref=str(required_evidence.get("effect_receipt_ref", "")),
            next_action="Produce an effect receipt proving admitted live-producer side effects.",
        ),
        _witness(
            witness_kind="external_adapter_evidence",
            evidence_ref=str(required_evidence.get("external_adapter_evidence_ref", "")),
            next_action="Validate external adapter evidence before any adapter execution.",
        ),
        _witness(
            witness_kind="secret_handoff",
            evidence_ref=str(required_evidence.get("secret_handoff_ref", "")),
            next_action="Prepare a redacted secret handoff without serializing secret values.",
        ),
        _witness(
            witness_kind="rollback_proof",
            evidence_ref=str(required_evidence.get("rollback_plan_ref", "")),
            next_action="Produce rollback proof before live producer admission.",
        ),
    ]


def _governed_witness_collection() -> list[dict[str, Any]]:
    return [
        {
            "collection_id": f"collection.{entry['witness_kind']}",
            "witness_kind": entry["witness_kind"],
            "requirements_evidence_ref": entry["requirements_evidence_ref"],
            "governed_artifact_ref": entry["governed_artifact_ref"],
            "validator_id": entry["validator_id"],
            "validator_command": entry["validator_command"],
            "status": "AwaitingEvidence",
            "authority_granted": False,
            "blocks_live_producer": True,
        }
        for entry in GOVERNED_WITNESS_COLLECTION
    ]


def _witness(*, witness_kind: str, evidence_ref: str, next_action: str) -> dict[str, Any]:
    return {
        "witness_id": f"witness.{witness_kind}",
        "witness_kind": witness_kind,
        "required": True,
        "status": "AwaitingEvidence",
        "evidence_ref": evidence_ref,
        "admission_effect": "blocks_live_producer",
        "authority_granted": False,
        "next_action": next_action,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}
