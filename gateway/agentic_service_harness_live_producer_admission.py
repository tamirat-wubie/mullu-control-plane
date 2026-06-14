"""Agentic Service Harness live producer admission gate.

Purpose: project the local task/run producer rehearsal into a blocked live
producer admission gate before any live producer implementation exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_task_run_producer.
Invariants:
  - Admission output is read-only, local-only, and non-terminal.
  - Live producer execution remains blocked by default.
  - UI, mutation, adapter, branch, pull-request, deployment, DNS, secret,
    runtime write, and destructive-operation authority remain denied.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from gateway.agentic_service_harness_live_task_run_producer import (
    AgenticServiceHarnessLocalTaskRunProducerRehearsal,
    REHEARSAL_REPORT_ID,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
ADMISSION_GATE_ID = "agentic-service-harness-live-producer-admission-gate"
ADMISSION_GATE_FIXTURE_REF = "examples/agentic_service_harness_live_producer_admission_gate.local.json"
ADMISSION_GATE_VALIDATOR = {
    "validator_id": "agentic-service-harness-live-producer-admission-gate",
    "command": "python scripts/validate_agentic_service_harness_live_producer_admission_gate.py",
    "required_for_closure": True,
}
DEFAULT_BLOCKED_REASONS = (
    "live_producer_authority_not_granted",
    "operator_approval_missing",
    "effect_receipt_missing",
    "external_adapter_evidence_missing",
    "mutation_route_not_admitted",
    "secret_handoff_missing",
    "terminal_closure_not_allowed",
)
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


class AgenticServiceHarnessLiveProducerAdmissionGate:
    """Produce a blocked live producer admission gate from local rehearsal."""

    def __init__(
        self,
        *,
        rehearsal_source: AgenticServiceHarnessLocalTaskRunProducerRehearsal | None = None,
    ) -> None:
        self._rehearsal_source = rehearsal_source or AgenticServiceHarnessLocalTaskRunProducerRehearsal()

    def produce(self) -> dict[str, Any] | None:
        """Return a blocked admission gate or None when rehearsal is unavailable."""
        rehearsal_report = self._rehearsal_source.produce()
        if not isinstance(rehearsal_report, Mapping):
            return None
        return project_rehearsal_to_live_producer_admission_gate(rehearsal_report)


def project_rehearsal_to_live_producer_admission_gate(
    rehearsal_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Project one local rehearsal report into a blocked admission gate."""
    report = deepcopy(dict(rehearsal_report))
    invalid_rehearsal = tuple(_rehearsal_blockers(report))
    scope = _mapping(report.get("scope"))
    effect_boundary = _mapping(report.get("effect_boundary"))
    run_projection = _mapping(report.get("run_projection"))

    blocked_reasons = list(DEFAULT_BLOCKED_REASONS)
    if invalid_rehearsal:
        blocked_reasons.append("invalid_local_rehearsal")

    return {
        "gate_id": ADMISSION_GATE_ID,
        "schema_version": 1,
        "generated_at": str(report.get("generated_at", "")),
        "gate_state": "blocked_invalid_rehearsal" if invalid_rehearsal else "blocked_pending_live_authority",
        "solver_outcome": "GovernanceBlocked" if invalid_rehearsal else "AwaitingEvidence",
        "source_rehearsal_report_id": str(report.get("report_id", "")),
        "source_fixture_ref": str(report.get("source_fixture_ref", "")),
        "planning_only": True,
        "local_rehearsal_only": True,
        "live_producer_implemented": False,
        "read_only": True,
        "report_is_not_terminal_closure": True,
        "terminal_closure": False,
        "admission_decision": "blocked",
        "scope": {
            "tenant_id": str(scope.get("tenant_id", "")),
            "organization_id": str(scope.get("organization_id", "")),
            "project_id": str(scope.get("project_id", "")),
            "repository_connection_id": str(scope.get("repository_connection_id", "")),
            "read_only": True,
        },
        "required_evidence": {
            "local_rehearsal_report_ref": f"rehearsal://{REHEARSAL_REPORT_ID}",
            "live_task_run_producer_evidence_ref": _first_string(
                _first_list_value(run_projection.get("evidence_bundle_refs")),
                "evidence://agentic-service-harness/live-producer-local-evidence",
            ),
            "read_only_status_route_ref": "GET:/api/v1/harness/status",
            "approval_gate_ref": "approval://operator-live-producer-approval-required",
            "effect_receipt_ref": "receipt://agentic-service-harness/live-producer-effect-receipt-required",
            "external_adapter_evidence_ref": (
                "evidence://agentic-service-harness/external-adapter-live-evidence-required"
            ),
            "secret_handoff_ref": "secret-handoff://agentic-service-harness/live-producer-required",
            "rollback_plan_ref": "rollback://agentic-service-harness/live-producer-required",
        },
        "authority_denials": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "live_execution_authorized": False,
        },
        "effect_boundary": {
            **{flag_name: False for flag_name in FALSE_AUTHORITY_FLAGS},
            "network_policy": str(effect_boundary.get("network_policy", "none")),
        },
        "blocked_reasons": list(dict.fromkeys(blocked_reasons)),
        "validators": [dict(ADMISSION_GATE_VALIDATOR)],
        "next_action": (
            "Keep live producer admission blocked until explicit approval, effect "
            "receipt, adapter evidence, secret handoff, and rollback proof exist."
        ),
    }


def _rehearsal_blockers(report: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    if report.get("report_id") != REHEARSAL_REPORT_ID:
        blockers.append("invalid_local_rehearsal")
    if report.get("producer_state") != "local_dry_run_ready":
        blockers.append("invalid_local_rehearsal")
    if report.get("planning_only") is not True:
        blockers.append("invalid_local_rehearsal")
    if report.get("local_rehearsal_only") is not True:
        blockers.append("invalid_local_rehearsal")
    if report.get("live_producer_implemented") is not False:
        blockers.append("invalid_local_rehearsal")
    if report.get("report_is_not_terminal_closure") is not True:
        blockers.append("invalid_local_rehearsal")
    if report.get("terminal_closure") is not False:
        blockers.append("invalid_local_rehearsal")
    effect_boundary = _mapping(report.get("effect_boundary"))
    if effect_boundary.get("network_policy") != "none":
        blockers.append("invalid_local_rehearsal")
    for flag_name in FALSE_AUTHORITY_FLAGS:
        if effect_boundary.get(flag_name) is not False:
            blockers.append("invalid_local_rehearsal")
    return tuple(dict.fromkeys(blockers))


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _first_string(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _first_list_value(value: Any) -> str:
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return ""
