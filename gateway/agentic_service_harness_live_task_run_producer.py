"""Agentic Service Harness local task/run producer rehearsal.

Purpose: project the validated live task/run producer evidence fixture into a
local dry-run report before any live producer execution path exists.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness_live_task_run_producer_evidence.local.json.
Invariants:
  - Rehearsal is local-only and performs no UI, HTTP mutation, adapter, branch,
    pull-request, deployment, DNS, secret, or destructive-operation effects.
  - Secret values are represented only by refs or denial flags.
  - Output remains read-only, non-terminal, and tenant/project scoped.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_FIXTURE_PATH = (
    REPO_ROOT / "examples" / "agentic_service_harness_live_task_run_producer_evidence.local.json"
)
DEFAULT_EVIDENCE_FIXTURE_REF = "examples/agentic_service_harness_live_task_run_producer_evidence.local.json"
REHEARSAL_REPORT_ID = "agentic_service_harness_live_task_run_producer_rehearsal"


class AgenticServiceHarnessLocalTaskRunProducerRehearsal:
    """Produce a local-only task/run rehearsal report from the evidence fixture."""

    def __init__(
        self,
        *,
        fixture_path: Path = DEFAULT_EVIDENCE_FIXTURE_PATH,
        fixture_ref: str = DEFAULT_EVIDENCE_FIXTURE_REF,
    ) -> None:
        self._fixture_path = fixture_path
        self._fixture_ref = fixture_ref

    @property
    def fixture_path(self) -> Path:
        """Return the source fixture path used by this rehearsal."""
        return self._fixture_path

    def produce(self) -> dict[str, Any] | None:
        """Return a local dry-run report or None when the fixture is unavailable."""
        fixture = _load_fixture(self._fixture_path)
        if fixture is None:
            return None
        return project_evidence_fixture_to_rehearsal(fixture, self._fixture_ref)


def project_evidence_fixture_to_rehearsal(
    fixture: Mapping[str, Any],
    fixture_ref: str,
) -> dict[str, Any]:
    """Project one validated evidence fixture into a local dry-run report."""
    scope = _required_mapping(fixture.get("scope"), "scope")
    task = _required_mapping(fixture.get("task_intake_evidence"), "task_intake_evidence")
    run = _required_mapping(fixture.get("run_projection_evidence"), "run_projection_evidence")
    approval = _required_mapping(fixture.get("approval_evidence"), "approval_evidence")
    receipt = _required_mapping(fixture.get("receipt_evidence"), "receipt_evidence")
    sandbox = _required_mapping(fixture.get("sandbox_evidence"), "sandbox_evidence")
    rollback = _required_mapping(fixture.get("rollback_evidence"), "rollback_evidence")
    status_publication = _required_mapping(
        fixture.get("status_publication_evidence"),
        "status_publication_evidence",
    )
    authority_denials = _required_mapping(fixture.get("authority_denials"), "authority_denials")

    return {
        "report_id": REHEARSAL_REPORT_ID,
        "schema_version": 1,
        "source_fixture_ref": fixture_ref,
        "source_fixture_id": fixture["fixture_id"],
        "generated_at": fixture["generated_at"],
        "producer_state": "local_dry_run_ready",
        "solver_outcome": "AwaitingEvidence",
        "planning_only": True,
        "local_rehearsal_only": True,
        "live_producer_implemented": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure": False,
        "scope": {
            "tenant_id": scope["tenant_id"],
            "organization_id": scope["organization_id"],
            "project_id": scope["project_id"],
            "repository_connection_id": scope["repository_connection_id"],
            "read_only": True,
        },
        "task_projection": {
            "task_id": task["task_id"],
            "requester_ref": task["requester_ref"],
            "tenant_id": task["tenant_id"],
            "project_id": task["project_id"],
            "requested_mode": task["requested_mode"],
            "risk_level": task["risk_level"],
            "policy_refs": list(task["policy_refs"]),
            "append_only": True,
            "read_only": True,
        },
        "run_projection": {
            "run_id": run["run_id"],
            "task_ref": run["task_ref"],
            "sandbox_ref": run["sandbox_ref"],
            "adapter_ref": run["adapter_ref"],
            "approval_refs": list(run["approval_refs"]),
            "receipt_refs": list(run["receipt_refs"]),
            "evidence_bundle_refs": list(run["evidence_bundle_refs"]),
            "status_route_publication_ready": run["status_route_publication_ready"],
            "executes_adapter": False,
            "creates_branch": False,
            "opens_pull_request": False,
            "permits_external_effect": False,
            "read_only": True,
        },
        "approval_projection": {
            "gate_id": approval["gate_id"],
            "approver_role_required": approval["approver_role_required"],
            "approval_required": approval["approval_required"],
            "self_approval_allowed": False,
            "permits_external_effect": False,
            "read_only": True,
        },
        "receipt_projection": {
            "receipt_id": receipt["receipt_id"],
            "command_refs": list(receipt["command_refs"]),
            "test_refs": list(receipt["test_refs"]),
            "changed_file_refs": list(receipt["changed_file_refs"]),
            "policy_result": receipt["policy_result"],
            "receipt_is_not_terminal_closure": True,
            "terminal_closure": False,
            "secret_values_serialized": False,
            "read_only": True,
            "next_action": receipt["next_action"],
        },
        "sandbox_projection": {
            "sandbox_id": sandbox["sandbox_id"],
            "path_allowlist": list(sandbox["path_allowlist"]),
            "command_allowlist": list(sandbox["command_allowlist"]),
            "timeout_seconds": sandbox["timeout_seconds"],
            "network_policy": "none",
            "cleanup_ref": sandbox["cleanup_ref"],
            "secret_redaction_required": True,
            "read_only": True,
        },
        "rollback_projection": {
            "rollback_boundary": rollback["rollback_boundary"],
            "replay_refs": list(rollback["replay_refs"]),
            "cleanup_refs": list(rollback["cleanup_refs"]),
            "denied_effect_refs": list(rollback["denied_effect_refs"]),
            "read_only": True,
        },
        "status_publication_projection": {
            "status_route_ref": status_publication["status_route_ref"],
            "source_update_ref": status_publication["source_update_ref"],
            "validator_refs": list(status_publication["validator_refs"]),
            "read_only": True,
            "no_terminal_closure_claim": True,
        },
        "authority_denials": dict(authority_denials),
        "effect_boundary": {
            "ui_created": False,
            "mutation_endpoints_admitted": False,
            "external_adapter_integrated": False,
            "branch_write_enabled": False,
            "pull_request_creation_enabled": False,
            "deployment_enabled": False,
            "dns_mutation_enabled": False,
            "secret_mutation_enabled": False,
            "destructive_operation_enabled": False,
            "runtime_state_written": False,
            "network_policy": "none",
        },
        "validators": [
            {
                "validator_id": "agentic-service-harness-live-task-run-producer-rehearsal",
                "command": "python scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py",
                "required_for_closure": True,
            }
        ],
        "next_action": (
            "Keep the producer rehearsal local; require separate approval and "
            "effect gates before any live producer implementation."
        ),
    }


def _load_fixture(fixture_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return deepcopy(payload)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _required_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value
