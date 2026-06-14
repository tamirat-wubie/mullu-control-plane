"""Agentic Service Harness runtime read-model producer.

Purpose: project the local harness contract fixture into the read-only status
source consumed by the gateway route.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness.read_only.json.
Invariants:
  - Producer is read-only and performs no HTTP, branch, PR, adapter, deploy,
    DNS, secret, or destructive-operation effects.
  - Secret values and high-risk authority are not introduced by projection.
  - Output remains non-terminal and tenant/project scoped.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT_PATH = REPO_ROOT / "examples" / "agentic_service_harness.read_only.json"
DEFAULT_CONTRACT_REF = "examples/agentic_service_harness.read_only.json"


class AgenticServiceHarnessRuntimeReadModelProducer:
    """Produce one local read-only harness read model from a contract fixture."""

    def __init__(
        self,
        *,
        contract_path: Path = DEFAULT_CONTRACT_PATH,
        contract_ref: str = DEFAULT_CONTRACT_REF,
    ) -> None:
        self._contract_path = contract_path
        self._contract_ref = contract_ref

    @property
    def contract_path(self) -> Path:
        """Return the source contract path used by this producer."""
        return self._contract_path

    def produce(self) -> dict[str, Any] | None:
        """Return a projected runtime read model or None when unavailable."""
        contract = _load_contract(self._contract_path)
        if contract is None:
            return None
        return project_contract_to_read_model(contract, self._contract_ref)


def project_contract_to_read_model(
    contract: Mapping[str, Any],
    contract_ref: str,
) -> dict[str, Any]:
    """Project one harness contract object into a read-only read-model envelope."""
    organization_by_id = {
        organization["organization_id"]: organization
        for organization in _objects(contract.get("organizations"))
    }
    task_by_id = {
        task["task_id"]: task
        for task in _objects(contract.get("agent_tasks"))
    }
    project = _objects(contract.get("projects"))[0]
    scenario = str(contract.get("scenario"))

    return {
        "report_id": "agentic_service_harness_read_models",
        "schema_version": 1,
        "contract_ref": contract_ref,
        "generated_at": str(contract.get("generated_at")),
        "projection_scope": {
            "tenant_id": project["tenant_id"],
            "organization_id": project["organization_id"],
            "project_id": project["project_id"],
            "read_only": True,
            "ui_created": False,
            "mutation_endpoints_admitted": False,
            "external_adapter_integrated": False,
            "default_high_risk_authority": False,
            "secret_values_serialized": False,
        },
        "accounts": [
            _project_user(user, organization_by_id)
            for user in _objects(contract.get("users"))
        ],
        "projects": [
            {
                "project_id": item["project_id"],
                "organization_id": item["organization_id"],
                "tenant_id": item["tenant_id"],
                "name": item["name"],
                "repository_connection_ids": list(item["repository_connection_ids"]),
                "agent_run_ids": list(item["agent_run_ids"]),
                "receipt_refs": list(item["receipt_refs"]),
                "loop_status_ref": item["loop_status_ref"],
                "read_only": True,
                "mutation_route": False,
            }
            for item in _objects(contract.get("projects"))
        ],
        "repositories": [
            {
                "connection_id": repository["connection_id"],
                "project_id": repository["project_id"],
                "provider": repository["provider"],
                "repository_slug": repository["repository_slug"],
                "default_branch": repository["default_branch"],
                "permission_scope": repository["permission_scope"],
                "credential_binding_ref": repository["credential_binding_ref"],
                "secret_values_serialized": False,
                "write_authority_enabled": False,
                "read_only": True,
            }
            for repository in _objects(contract.get("repository_connections"))
        ],
        "runs": [
            _project_run(run, task_by_id)
            for run in _objects(contract.get("agent_runs"))
        ],
        "approvals": [
            _project_approval(gate)
            for gate in _objects(contract.get("approval_gates"))
        ],
        "receipts": [
            _project_receipt(receipt)
            for receipt in _objects(contract.get("receipts"))
        ],
        "evidence": [
            _project_evidence(bundle)
            for bundle in _objects(contract.get("evidence_bundles"))
        ],
        "result_summaries": [
            _project_summary(summary)
            for summary in _objects(contract.get("result_summaries"))
        ],
        "permission_snapshot": _project_permission_snapshot(
            _required_mapping(contract.get("permission_model"), "permission_model")
        ),
        "validators": [
            {
                "validator_id": f"runtime-producer.{scenario}",
                "command": "python scripts/validate_agentic_service_harness_read_only_status_route.py",
                "required_for_closure": True,
            }
        ],
        "next_action": "Runtime read-model producer is bound; keep route read-only.",
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
    }


def _project_user(
    user: Mapping[str, Any],
    organization_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    memberships = list(user["organization_memberships"])
    tenant_id = organization_by_id[memberships[0]]["tenant_id"]
    return {
        "user_id": user["user_id"],
        "tenant_id": tenant_id,
        "organization_memberships": memberships,
        "display_name": user["display_name"],
        "default_role": user["default_role"],
        "identity_provider_ref": user["identity_provider_ref"],
        "read_only": True,
        "secret_values_serialized": False,
    }


def _project_run(
    run: Mapping[str, Any],
    task_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    task = task_by_id[run["task_id"]]
    return {
        "run_id": run["run_id"],
        "project_id": task["project_id"],
        "task_request_ref": f"task://{run['task_id']}",
        "adapter_id": run["adapter_id"],
        "sandbox_id": run["sandbox_id"],
        "mode": run["mode"],
        "status": run["status"],
        "approval_gate_ids": list(run["approval_gate_ids"]),
        "receipt_id": run["receipt_id"],
        "evidence_bundle_id": run["evidence_bundle_id"],
        "result_summary_id": run["result_summary_id"],
        "risk_level": task["risk_level"],
        "blocked_actions": list(run["blocked_actions"]),
        "read_only": True,
        "executes_adapter": False,
        "creates_branch": False,
        "opens_pull_request": False,
        "permits_external_effect": False,
    }


def _project_approval(gate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gate_id": gate["gate_id"],
        "run_id": gate["run_id"],
        "action_class": gate["action_class"],
        "risk_level": gate["risk_level"],
        "status": gate["status"],
        "approver_role_required": gate["approver_role_required"],
        "approval_required": gate["approval_required"],
        "self_approval_allowed": False,
        "permits_external_effect": False,
        "evidence_refs": list(gate["evidence_refs"]),
        "read_only": True,
    }


def _project_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "receipt_id": receipt["receipt_id"],
        "run_id": receipt["run_id"],
        "task_request_ref": receipt["task_request_ref"],
        "selected_agent_ref": receipt["selected_agent_ref"],
        "files_changed": dict(receipt["files_changed"]),
        "commands_run_refs": [
            command["command_ref"]
            for command in _objects(receipt.get("commands_run"))
        ],
        "tests_run_refs": [
            test.get("log_ref") or test["command_ref"]
            for test in _objects(receipt.get("tests_run"))
        ],
        "policy_result": receipt["policy_result"],
        "risk_level": receipt["risk_level"],
        "evidence_refs": list(receipt["evidence_refs"]),
        "next_action": receipt["next_action"],
        "read_only": True,
        "receipt_is_not_terminal_closure": True,
        "terminal_closure": False,
        "secret_values_serialized": False,
    }


def _project_evidence(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle["bundle_id"],
        "run_id": bundle["run_id"],
        "evidence_refs": list(bundle["evidence_refs"]),
        "command_log_refs": list(bundle["command_log_refs"]),
        "test_log_refs": list(bundle["test_log_refs"]),
        "diff_refs": list(bundle["diff_refs"]),
        "policy_refs": list(bundle["policy_refs"]),
        "redaction_policy": "hash_or_reference_only",
        "contains_secret_values": False,
        "inline_diff_allowed": False,
        "read_only": True,
    }


def _project_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "summary_id": summary["summary_id"],
        "run_id": summary["run_id"],
        "outcome": summary["outcome"],
        "user_visible_status": summary["user_visible_status"],
        "changed_file_count": summary["changed_file_count"],
        "tests_status": summary["tests_status"],
        "blockers": list(summary["blockers"]),
        "next_action": summary["next_action"],
        "read_only": True,
        "terminal_closure": False,
    }


def _project_permission_snapshot(permission_model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "roles": list(permission_model["roles"]),
        "action_classes": list(permission_model["action_classes"]),
        "blocked_high_risk_actions": list(permission_model["blocked_high_risk_actions"]),
        "can_merge": False,
        "can_deploy": False,
        "can_mutate_dns": False,
        "can_mutate_secrets": False,
        "can_run_destructive_operations": False,
        "read_only": True,
    }


def _load_contract(contract_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(contract_path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constant is not permitted: {raw_constant}")


def _required_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(deepcopy(item) for item in collection if isinstance(item, dict))
