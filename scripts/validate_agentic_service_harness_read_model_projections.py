#!/usr/bin/env python3
"""Validate read-only projections from harness contract fixtures.

Purpose: derive display-only Agentic Service Harness read models from the
existing contract fixtures and prove that fixture projection does not admit
UI, mutation endpoints, persistence adapters, external adapter execution,
branch writes, pull-request creation, secret serialization, or terminal
closure claims.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: examples/agentic_service_harness.*.json,
schemas/agentic_service_harness_read_models.schema.json,
scripts.validate_agentic_service_harness_contract, and
scripts.validate_agentic_service_harness_read_models.
Invariants:
  - Every contract scenario has one derived read-model projection.
  - Source fixtures remain contract-valid and effect-denied.
  - Derived projections are read-only, reference-consistent, redacted, and
    non-terminal.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_contract import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_CONTRACT_EXAMPLES,
    EXPECTED_SCENARIOS,
    validate_agentic_service_harness_contract,
)
from scripts.validate_agentic_service_harness_read_models import (  # noqa: E402
    DEFAULT_SCHEMA as DEFAULT_READ_MODEL_SCHEMA,
    HIGH_RISK_ACTIONS,
    _validate_read_model_semantics,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_read_model_projection_validation.json"
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b")
SOURCE_DENIAL_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "default_high_risk_authority",
)


@dataclass(frozen=True, slots=True)
class AgenticServiceHarnessReadModelProjectionValidation:
    """Validation result for generated harness read-model projections."""

    ok: bool
    errors: tuple[str, ...]
    source_paths: tuple[str, ...]
    schema_path: str
    source_count: int
    projection_count: int
    scenario_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["source_paths"] = list(self.source_paths)
        return payload


def validate_agentic_service_harness_read_model_projections(
    *,
    source_paths: Sequence[Path] = DEFAULT_CONTRACT_EXAMPLES,
    schema_path: Path = DEFAULT_READ_MODEL_SCHEMA,
) -> AgenticServiceHarnessReadModelProjectionValidation:
    """Validate read-model projections derived from contract fixtures."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "harness read-model schema", errors)
    source_validation = validate_agentic_service_harness_contract(
        example_paths=tuple(source_paths)
    )
    errors.extend(f"source contract: {error}" for error in source_validation.errors)

    projections: list[dict[str, Any]] = []
    observed_scenarios: set[str] = set()
    for source_path in source_paths:
        source = _load_json_object(
            source_path,
            f"harness contract source {_path_label(source_path)}",
            errors,
        )
        if not source:
            continue
        label = _path_label(source_path)
        scenario = str(source.get("scenario", ""))
        observed_scenarios.add(scenario)
        _validate_source_projection_boundary(source, errors, label)
        projection = project_contract_to_read_model(source, label)
        projections.append(projection)
        if schema:
            errors.extend(
                f"{label}: projection schema: {error}"
                for error in _validate_schema_instance(schema, projection)
            )
        _validate_read_model_semantics(projection, errors, f"{label}: projection")
        _validate_projection_matches_source(source, projection, errors, label)

    missing = sorted(set(EXPECTED_SCENARIOS) - observed_scenarios)
    extra = sorted(observed_scenarios - set(EXPECTED_SCENARIOS))
    if missing:
        errors.append(f"source scenarios missing {missing}")
    if extra:
        errors.append(f"source scenarios unknown {extra}")

    return AgenticServiceHarnessReadModelProjectionValidation(
        ok=not errors,
        errors=tuple(errors),
        source_paths=tuple(_path_label(path) for path in source_paths),
        schema_path=_path_label(schema_path),
        source_count=len(source_paths),
        projection_count=len(projections),
        scenario_count=len(observed_scenarios),
    )


def project_contract_to_read_model(
    contract: dict[str, Any],
    contract_ref: str,
) -> dict[str, Any]:
    """Project one harness contract fixture into a read-only read-model envelope."""
    organization_by_id = {
        organization["organization_id"]: organization
        for organization in _objects(contract.get("organizations"))
    }
    task_by_id = {
        task["task_id"]: task
        for task in _objects(contract.get("agent_tasks"))
    }
    run_ids_by_sandbox = _run_ids_by_sandbox(contract)
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
                "provider_repository_ref": repository["provider_repository_ref"],
                "repository_owner": repository["repository_owner"],
                "repository_name": repository["repository_name"],
                "repository_slug": repository["repository_slug"],
                "default_branch": repository["default_branch"],
                "installation_ref": repository["installation_ref"],
                "installation_state": repository["installation_state"],
                "permission_scope": repository["permission_scope"],
                "permission_scopes": list(repository["permission_scopes"]),
                "credential_binding_ref": repository["credential_binding_ref"],
                "revocation_state": repository["revocation_state"],
                "revocation_evidence_ref": repository["revocation_evidence_ref"],
                "last_verified_at": repository["last_verified_at"],
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
        "workspace_allocations": [
            _project_workspace_allocation(sandbox, run_ids_by_sandbox)
            for sandbox in _objects(contract.get("workspace_sandboxes"))
        ],
        "durable_entity_bindings": _project_durable_entity_bindings(contract_ref),
        "permission_snapshot": _project_permission_snapshot(contract["permission_model"]),
        "validators": [
            {
                "validator_id": f"projection.{scenario}",
                "command": (
                    "python scripts/validate_agentic_service_harness_read_model_projections.py "
                    "--strict"
                ),
                "required_for_closure": True,
            }
        ],
        "next_action": "Use this projection as a read-only fixture witness only.",
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
    }


def write_projection_validation(
    validation: AgenticServiceHarnessReadModelProjectionValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic projection validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _project_user(
    user: dict[str, Any],
    organization_by_id: dict[str, dict[str, Any]],
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
    run: dict[str, Any],
    task_by_id: dict[str, dict[str, Any]],
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
        "lifecycle_state": run["lifecycle_state"],
        "created_at": run["created_at"],
        "lifecycle_updated_at": run["lifecycle_updated_at"],
        "approval_gate_ids": list(run["approval_gate_ids"]),
        "receipt_id": run["receipt_id"],
        "evidence_bundle_id": run["evidence_bundle_id"],
        "result_summary_id": run["result_summary_id"],
        "risk_level": task["risk_level"],
        "blocked_actions": list(run["blocked_actions"]),
        "transition_receipt_refs": list(run["transition_receipt_refs"]),
        "terminal_state": run["terminal_state"],
        "read_only_query_ref": f"agent-run://{run['run_id']}/read-only-query",
        "read_only": True,
        "executes_adapter": False,
        "creates_branch": False,
        "opens_pull_request": False,
        "permits_external_effect": False,
    }


def _project_approval(gate: dict[str, Any]) -> dict[str, Any]:
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


def _project_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
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


def _project_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
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


def _project_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary_id": summary["summary_id"],
        "run_id": summary["run_id"],
        "outcome": summary["outcome"],
        "user_visible_status": summary["user_visible_status"],
        "changed_file_count": summary["changed_file_count"],
        "tests_status": summary["tests_status"],
        "blockers": list(summary["blockers"]) or ["none"],
        "next_action": summary["next_action"],
        "read_only": True,
        "terminal_closure": False,
    }


def _project_workspace_allocation(
    sandbox: dict[str, Any],
    run_ids_by_sandbox: dict[str, list[str]],
) -> dict[str, Any]:
    sandbox_id = sandbox["sandbox_id"]
    return {
        "allocation_id": f"workspace-allocation.{sandbox_id}",
        "sandbox_id": sandbox_id,
        "project_id": sandbox["project_id"],
        "run_ids": run_ids_by_sandbox.get(sandbox_id, []),
        "branch_workspace_ref": f"workspace://harness/{sandbox_id}/contract-only",
        "base_branch": "main",
        "working_branch_ref": f"branch://pending/{sandbox_id}",
        "command_allowlist": list(sandbox["command_allowlist"]),
        "path_allowlist": list(sandbox["path_allowlist"]),
        "timeout_seconds": sandbox["timeout_seconds"],
        "network_policy": sandbox["network_policy"],
        "cleanup_receipt_ref": sandbox["cleanup_receipt_ref"],
        "command_log_collection_ref": f"logs://harness/{sandbox_id}/commands",
        "test_log_collection_ref": f"logs://harness/{sandbox_id}/tests",
        "diff_collection_ref": f"diff://harness/{sandbox_id}",
        "redaction_policy": "hash_or_reference_only",
        "read_only": True,
        "workspace_created": False,
        "commands_executed": False,
        "files_written": False,
        "cleanup_executed": False,
        "production_mutation_allowed": False,
        "secret_values_serialized": False,
    }


def _project_durable_entity_bindings(contract_ref: str) -> dict[str, Any]:
    return {
        "store_contract_ref": "scripts/validate_agentic_service_harness_read_model_persistence.py",
        "store_mode": "append_only_jsonl_rehearsal",
        "read_only": True,
        "append_enabled": False,
        "mutation_routes_admitted": False,
        "secret_values_serialized": False,
        "entity_bindings": [
            _durable_entity_binding(
                entity_kind="User",
                record_kind="account",
                collection_ref="read-model://accounts",
                primary_key="user_id",
                tenant_key="tenant_id",
                owner_ref_fields=("organization_memberships",),
                identity_source_ref="schemas/agentic_service_harness.schema.json#/$defs/user",
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="Organization",
                record_kind="organization",
                collection_ref="contract://organizations",
                primary_key="organization_id",
                tenant_key="tenant_id",
                owner_ref_fields=("owner_user_ids", "admin_user_ids", "project_ids"),
                identity_source_ref="schemas/agentic_service_harness.schema.json#/$defs/organization",
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="Project",
                record_kind="project",
                collection_ref="read-model://projects",
                primary_key="project_id",
                tenant_key="tenant_id",
                owner_ref_fields=(
                    "organization_id",
                    "repository_connection_ids",
                    "agent_run_ids",
                    "receipt_refs",
                    "loop_status_ref",
                ),
                identity_source_ref="schemas/agentic_service_harness.schema.json#/$defs/project",
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="RepositoryConnection",
                record_kind="repository",
                collection_ref="read-model://repositories",
                primary_key="connection_id",
                tenant_key="project_id",
                owner_ref_fields=(
                    "project_id",
                    "provider_repository_ref",
                    "installation_ref",
                    "credential_binding_ref",
                    "revocation_evidence_ref",
                ),
                identity_source_ref=(
                    "schemas/agentic_service_harness.schema.json#/$defs/repository_connection"
                ),
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="AgentRun",
                record_kind="run",
                collection_ref="read-model://runs",
                primary_key="run_id",
                tenant_key="project_id",
                owner_ref_fields=(
                    "project_id",
                    "approval_gate_ids",
                    "receipt_id",
                    "evidence_bundle_id",
                    "result_summary_id",
                ),
                identity_source_ref="schemas/agentic_service_harness.schema.json#/$defs/agent_run",
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="ApprovalRequest",
                record_kind="approval",
                collection_ref="read-model://approvals",
                primary_key="gate_id",
                tenant_key="run_id",
                owner_ref_fields=("run_id", "evidence_refs"),
                identity_source_ref="schemas/agentic_service_harness.schema.json#/$defs/approval_gate",
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="Receipt",
                record_kind="receipt",
                collection_ref="read-model://receipts",
                primary_key="receipt_id",
                tenant_key="run_id",
                owner_ref_fields=("run_id", "task_request_ref", "evidence_refs"),
                identity_source_ref=(
                    "schemas/agentic_service_harness.schema.json#/$defs/agent_run_receipt"
                ),
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="WorkspaceAllocation",
                record_kind="workspace_allocation",
                collection_ref="read-model://workspace_allocations",
                primary_key="allocation_id",
                tenant_key="project_id",
                owner_ref_fields=(
                    "project_id",
                    "sandbox_id",
                    "run_ids",
                    "cleanup_receipt_ref",
                ),
                identity_source_ref=(
                    "schemas/agentic_service_harness_read_models.schema.json#/$defs/"
                    "harness_workspace_allocation_read_model"
                ),
                contract_ref=contract_ref,
            ),
            _durable_entity_binding(
                entity_kind="LoopStatus",
                record_kind="loop_status",
                collection_ref="read-model://projects/loop_status_ref",
                primary_key="loop_status_ref",
                tenant_key="project_id",
                owner_ref_fields=("project_id", "loop_status_ref"),
                identity_source_ref="MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md#public-api-foundation",
                contract_ref=contract_ref,
            ),
        ],
    }


def _durable_entity_binding(
    *,
    entity_kind: str,
    record_kind: str,
    collection_ref: str,
    primary_key: str,
    tenant_key: str,
    owner_ref_fields: tuple[str, ...],
    identity_source_ref: str,
    contract_ref: str,
) -> dict[str, Any]:
    return {
        "entity_kind": entity_kind,
        "record_kind": record_kind,
        "collection_ref": collection_ref,
        "primary_key": primary_key,
        "tenant_key": tenant_key,
        "owner_ref_fields": list(owner_ref_fields),
        "identity_source_ref": identity_source_ref,
        "read_model_source": "fixture_projection",
        "write_authority_enabled": False,
        "append_enabled": False,
        "mutation_route": False,
        "secret_values_serialized": False,
        "evidence_refs": [contract_ref],
    }


def _project_permission_snapshot(permission_model: dict[str, Any]) -> dict[str, Any]:
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


def _validate_source_projection_boundary(
    contract: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for flag_name in SOURCE_DENIAL_FLAGS:
        if contract.get(flag_name) is not False:
            errors.append(f"{label}: source {flag_name} must remain false")
    for repository in _objects(contract.get("repository_connections")):
        if repository.get("write_authority_enabled") is not False:
            errors.append(f"{label}: source repository write authority must remain false")
        _validate_repository_connection_fields(repository, errors, label)
    for adapter in _objects(contract.get("agent_adapters")):
        if adapter.get("external_adapter_integrated") is not False:
            errors.append(f"{label}: source adapter integration must remain false")
    for sandbox in _objects(contract.get("workspace_sandboxes")):
        if sandbox.get("production_mutation_allowed") is not False:
            errors.append(f"{label}: source sandbox production mutation must remain false")
    for path, value in _walk_strings(contract):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: source mutation route string at {path}")


def _validate_repository_connection_fields(
    repository: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    connection_id = repository.get("connection_id")
    repository_label = f"{label}: source repository {connection_id}"
    if repository.get("provider") != "github":
        errors.append(f"{repository_label} provider must be github")
    for ref_name in (
        "provider_repository_ref",
        "installation_ref",
        "credential_binding_ref",
        "revocation_evidence_ref",
    ):
        if not isinstance(repository.get(ref_name), str) or not repository.get(ref_name):
            errors.append(f"{repository_label} {ref_name} must be a non-empty ref")
    if repository.get("installation_state") not in {
        "presence_only",
        "active",
        "revoked",
        "requires_reauth",
    }:
        errors.append(f"{repository_label} installation_state is invalid")
    if repository.get("revocation_state") not in {
        "not_revoked",
        "revoked",
        "pending_revalidation",
    }:
        errors.append(f"{repository_label} revocation_state is invalid")
    if repository.get("secret_values_serialized") is not False:
        errors.append(f"{repository_label} secret_values_serialized must remain false")
    permission_scopes = repository.get("permission_scopes")
    if not isinstance(permission_scopes, list) or not permission_scopes:
        errors.append(f"{repository_label} permission_scopes must be a non-empty list")
    elif any(str(scope).endswith("_write") for scope in permission_scopes):
        errors.append(f"{repository_label} permission_scopes must not include write scopes")


def _validate_projection_matches_source(
    contract: dict[str, Any],
    projection: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if projection["contract_ref"] != label:
        errors.append(f"{label}: projection contract_ref mismatch")
    if projection["generated_at"] != contract.get("generated_at"):
        errors.append(f"{label}: projection generated_at mismatch")
    if projection["projection_scope"]["ui_created"] is not False:
        errors.append(f"{label}: projection created UI")
    source_runs = _ids(contract.get("agent_runs"), "run_id")
    projected_runs = _ids(projection.get("runs"), "run_id")
    if source_runs != projected_runs:
        errors.append(f"{label}: projected run ids mismatch")
    source_receipts = _ids(contract.get("receipts"), "receipt_id")
    projected_receipts = _ids(projection.get("receipts"), "receipt_id")
    if source_receipts != projected_receipts:
        errors.append(f"{label}: projected receipt ids mismatch")
    source_policy_results = {
        receipt["policy_result"]
        for receipt in _objects(contract.get("receipts"))
    }
    projected_policy_results = {
        receipt["policy_result"]
        for receipt in _objects(projection.get("receipts"))
    }
    if source_policy_results != projected_policy_results:
        errors.append(f"{label}: projected policy results mismatch")
    blocked_actions = set(projection["permission_snapshot"]["blocked_high_risk_actions"])
    if blocked_actions != set(HIGH_RISK_ACTIONS):
        errors.append(f"{label}: projected high-risk action set mismatch")


def _ids(collection: Any, key: str) -> set[str]:
    return {str(item.get(key)) for item in _objects(collection) if item.get(key)}


def _run_ids_by_sandbox(contract: dict[str, Any]) -> dict[str, list[str]]:
    run_ids_by_sandbox: dict[str, list[str]] = {}
    for run in _objects(contract.get("agent_runs")):
        run_ids_by_sandbox.setdefault(str(run["sandbox_id"]), []).append(str(run["run_id"]))
    return run_ids_by_sandbox


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield path, payload


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse harness read-model projection validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate read-only projections from harness contract fixtures."
    )
    parser.add_argument("--source", action="append", default=None)
    parser.add_argument("--schema", default=str(DEFAULT_READ_MODEL_SCHEMA))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for harness read-model projection validation."""
    args = parse_args(argv)
    source_paths = (
        tuple(Path(source) for source in args.source)
        if args.source
        else DEFAULT_CONTRACT_EXAMPLES
    )
    validation = validate_agentic_service_harness_read_model_projections(
        source_paths=source_paths,
        schema_path=Path(args.schema),
    )
    write_projection_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ MODEL PROJECTIONS VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ MODEL PROJECTIONS INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
