#!/usr/bin/env python3
"""Validate Agentic Service Harness read-model schema examples.

Purpose: keep the first harness read models scoped to displayable, read-only
projections before any dashboard, mutation endpoint, branch write, pull-request
creation, external adapter execution, or high-risk authority is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_read_models.schema.json,
examples/agentic_service_harness_read_models.foundation.json, and
scripts.validate_schemas.
Invariants:
  - Read models are tenant/project scoped and reference-consistent.
  - Projection flags remain read-only and non-mutating.
  - Secret values, mutation route strings, and terminal closure claims are
    rejected.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_read_models.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_read_models.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_read_models_validation.json"

EXPECTED_COLLECTIONS = (
    "accounts",
    "projects",
    "repositories",
    "runs",
    "approvals",
    "receipts",
    "evidence",
    "result_summaries",
    "workspace_allocations",
)
EXPECTED_DURABLE_ENTITY_KINDS = (
    "User",
    "Organization",
    "Project",
    "RepositoryConnection",
    "AgentRun",
    "ApprovalRequest",
    "Receipt",
    "WorkspaceAllocation",
    "LoopStatus",
)
DENIAL_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "default_high_risk_authority",
    "secret_values_serialized",
)
READ_ONLY_FALSE_FLAGS = (
    "append_enabled",
    "mutation_route",
    "mutation_routes_admitted",
    "executes_transition",
    "emits_receipt",
    "terminal_closure",
    "write_authority_enabled",
    "executes_adapter",
    "creates_branch",
    "opens_pull_request",
    "permits_external_effect",
    "contains_secret_values",
    "inline_diff_allowed",
    "can_merge",
    "can_deploy",
    "can_mutate_dns",
    "can_mutate_secrets",
    "can_run_destructive_operations",
    "workspace_created",
    "commands_executed",
    "files_written",
    "cleanup_executed",
    "production_mutation_allowed",
)
HIGH_RISK_ACTIONS = (
    "merge",
    "deploy",
    "dns_mutation",
    "secret_mutation",
    "destructive_operation",
)
VALID_LIFECYCLE_STATES = {
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "blocked",
    "cancelled",
}
TERMINAL_LIFECYCLE_STATES = {"completed", "blocked", "cancelled"}
ALLOWED_SECRET_KEYS = {
    "can_mutate_secrets",
    "contains_secret_values",
    "no_secret_mutation",
    "secret_values_serialized",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b")


@dataclass(frozen=True, slots=True)
class AgenticServiceHarnessReadModelValidation:
    """Schema and semantic validation report for harness read models."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    collection_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_read_models(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> AgenticServiceHarnessReadModelValidation:
    """Validate harness read-model examples against schema and invariants."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "harness read-model schema", errors)
    examples: list[dict[str, Any]] = []

    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"harness read-model example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_read_model_semantics(example, errors, _path_label(example_path))

    return AgenticServiceHarnessReadModelValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        collection_count=len(EXPECTED_COLLECTIONS),
    )


def write_agentic_service_harness_read_model_validation(
    validation: AgenticServiceHarnessReadModelValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic harness read-model validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_read_model_semantics(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _validate_collection_presence(example, errors, label)
    _validate_projection_scope(example, errors, label)
    _validate_reference_integrity(example, errors, label)
    _validate_repository_connections(example, errors, label)
    _validate_agent_runs(example, errors, label)
    _validate_workspace_allocations(example, errors, label)
    _validate_durable_entity_bindings(example, errors, label)
    _validate_complete_high_risk_actions(example, errors, label)
    _validate_read_only_flags(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_collection_presence(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for collection_name in EXPECTED_COLLECTIONS:
        if collection_name not in example:
            errors.append(f"{label}: missing collection {collection_name}")
        elif not isinstance(example[collection_name], list):
            errors.append(f"{label}: collection {collection_name} must be a list")


def _validate_projection_scope(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = example.get("projection_scope")
    if not isinstance(scope, dict):
        errors.append(f"{label}: projection_scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: projection_scope.read_only must be true")
    for flag_name in DENIAL_FLAGS:
        if scope.get(flag_name) is not False:
            errors.append(f"{label}: projection_scope.{flag_name} must remain false")


def _validate_reference_integrity(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    project_ids = _ids(example.get("projects"), "project_id")
    repository_ids = _ids(example.get("repositories"), "connection_id")
    run_ids = _ids(example.get("runs"), "run_id")
    allocation_ids = _ids(example.get("workspace_allocations"), "allocation_id")
    allocation_sandbox_ids = _ids(example.get("workspace_allocations"), "sandbox_id")
    approval_ids = _ids(example.get("approvals"), "gate_id")
    receipt_ids = _ids(example.get("receipts"), "receipt_id")
    evidence_ids = _ids(example.get("evidence"), "bundle_id")
    summary_ids = _ids(example.get("result_summaries"), "summary_id")

    for project in _objects(example.get("projects")):
        _require_refs(
            observed=project.get("repository_connection_ids", ()),
            valid=repository_ids,
            label=f"{label}: project {project.get('project_id')} repository refs",
            errors=errors,
        )
        _require_refs(
            observed=project.get("agent_run_ids", ()),
            valid=run_ids,
            label=f"{label}: project {project.get('project_id')} run refs",
            errors=errors,
        )

    for repository in _objects(example.get("repositories")):
        if repository.get("project_id") not in project_ids:
            errors.append(f"{label}: repository {repository.get('connection_id')} project ref missing")

    for run in _objects(example.get("runs")):
        run_label = f"{label}: run {run.get('run_id')}"
        if run.get("project_id") not in project_ids:
            errors.append(f"{run_label} project ref missing")
        _require_refs(
            observed=run.get("approval_gate_ids", ()),
            valid=approval_ids,
            label=f"{run_label} approval refs",
            errors=errors,
        )
        if run.get("receipt_id") not in receipt_ids:
            errors.append(f"{run_label} receipt ref missing")
        if run.get("evidence_bundle_id") not in evidence_ids:
            errors.append(f"{run_label} evidence ref missing")
        if run.get("result_summary_id") not in summary_ids:
            errors.append(f"{run_label} summary ref missing")
        if run.get("sandbox_id") not in allocation_sandbox_ids:
            errors.append(f"{run_label} sandbox allocation ref missing")

    for collection_name, ref_key in (
        ("approvals", "run_id"),
        ("receipts", "run_id"),
        ("evidence", "run_id"),
        ("result_summaries", "run_id"),
    ):
        for item in _objects(example.get(collection_name)):
            if item.get(ref_key) not in run_ids:
                errors.append(f"{label}: {collection_name} {item.get(ref_key)} run ref missing")

    for allocation in _objects(example.get("workspace_allocations")):
        allocation_label = f"{label}: workspace allocation {allocation.get('allocation_id')}"
        if allocation.get("project_id") not in project_ids:
            errors.append(f"{allocation_label} project ref missing")
        _require_refs(
            observed=allocation.get("run_ids", ()),
            valid=run_ids,
            label=f"{allocation_label} run refs",
            errors=errors,
        )
    if len(allocation_ids) != len(_objects(example.get("workspace_allocations"))):
        errors.append(f"{label}: workspace allocations require unique allocation_id values")


def _validate_repository_connections(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    repositories = example.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        errors.append(f"{label}: repositories must be a non-empty list")
        return
    for repository in _objects(repositories):
        connection_id = repository.get("connection_id")
        repository_label = f"{label}: repository {connection_id}"
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
        if repository.get("write_authority_enabled") is not False:
            errors.append(f"{repository_label} write_authority_enabled must remain false")
        if repository.get("read_only") is not True:
            errors.append(f"{repository_label} read_only must be true")
        permission_scopes = repository.get("permission_scopes")
        if not isinstance(permission_scopes, list) or not permission_scopes:
            errors.append(f"{repository_label} permission_scopes must be a non-empty list")
        elif any(str(scope).endswith("_write") for scope in permission_scopes):
            errors.append(f"{repository_label} permission_scopes must not include write scopes")


def _validate_agent_runs(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    runs = example.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append(f"{label}: runs must be a non-empty list")
        return
    for run in _objects(runs):
        run_label = f"{label}: run {run.get('run_id')}"
        lifecycle_state = run.get("lifecycle_state")
        terminal_state = run.get("terminal_state")
        if lifecycle_state not in VALID_LIFECYCLE_STATES:
            errors.append(f"{run_label} lifecycle_state is invalid")
        for timestamp_name in ("created_at", "lifecycle_updated_at"):
            if not isinstance(run.get(timestamp_name), str) or not run.get(timestamp_name):
                errors.append(f"{run_label} {timestamp_name} must be a non-empty timestamp")
        transition_receipt_refs = run.get("transition_receipt_refs")
        if not isinstance(transition_receipt_refs, list) or not transition_receipt_refs:
            errors.append(f"{run_label} transition_receipt_refs must be a non-empty list")
        if not isinstance(run.get("read_only_query_ref"), str) or not run.get("read_only_query_ref"):
            errors.append(f"{run_label} read_only_query_ref must be a non-empty ref")
        if run.get("status") == "awaiting_approval" and lifecycle_state != "awaiting_approval":
            errors.append(f"{run_label} awaiting approval status must match lifecycle_state")
        if run.get("status") == "blocked" and lifecycle_state != "blocked":
            errors.append(f"{run_label} blocked status must match lifecycle_state")
        if lifecycle_state in TERMINAL_LIFECYCLE_STATES and terminal_state is not True:
            errors.append(f"{run_label} terminal lifecycle state must set terminal_state true")
        if lifecycle_state not in TERMINAL_LIFECYCLE_STATES and terminal_state is not False:
            errors.append(f"{run_label} non-terminal lifecycle state must set terminal_state false")


def _validate_workspace_allocations(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    allocations = example.get("workspace_allocations")
    if not isinstance(allocations, list):
        errors.append(f"{label}: workspace_allocations must be a list")
        return
    if not allocations:
        errors.append(f"{label}: workspace_allocations must not be empty")
    for allocation in _objects(allocations):
        allocation_label = f"{label}: workspace allocation {allocation.get('allocation_id')}"
        if allocation.get("read_only") is not True:
            errors.append(f"{allocation_label} read_only must be true")
        for flag_name in (
            "workspace_created",
            "commands_executed",
            "files_written",
            "cleanup_executed",
            "production_mutation_allowed",
            "secret_values_serialized",
        ):
            if allocation.get(flag_name) is not False:
                errors.append(f"{allocation_label} {flag_name} must remain false")
        for ref_name in (
            "branch_workspace_ref",
            "working_branch_ref",
            "cleanup_receipt_ref",
            "command_log_collection_ref",
            "test_log_collection_ref",
            "diff_collection_ref",
        ):
            if not isinstance(allocation.get(ref_name), str) or not allocation.get(ref_name):
                errors.append(f"{allocation_label} {ref_name} must be a non-empty ref")
        for list_name in ("run_ids", "command_allowlist", "path_allowlist"):
            if not isinstance(allocation.get(list_name), list) or not allocation.get(list_name):
                errors.append(f"{allocation_label} {list_name} must be a non-empty list")


def _validate_durable_entity_bindings(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    bindings = example.get("durable_entity_bindings")
    if not isinstance(bindings, dict):
        errors.append(f"{label}: durable_entity_bindings must be an object")
        return
    if bindings.get("read_only") is not True:
        errors.append(f"{label}: durable_entity_bindings.read_only must be true")
    for flag_name in ("append_enabled", "mutation_routes_admitted", "secret_values_serialized"):
        if bindings.get(flag_name) is not False:
            errors.append(f"{label}: durable_entity_bindings.{flag_name} must remain false")
    entity_bindings = bindings.get("entity_bindings")
    if not isinstance(entity_bindings, list):
        errors.append(f"{label}: durable_entity_bindings.entity_bindings must be a list")
        return
    observed_kinds = [
        str(item.get("entity_kind"))
        for item in entity_bindings
        if isinstance(item, dict)
    ]
    missing = sorted(set(EXPECTED_DURABLE_ENTITY_KINDS) - set(observed_kinds))
    extra = sorted(set(observed_kinds) - set(EXPECTED_DURABLE_ENTITY_KINDS))
    if missing:
        errors.append(f"{label}: durable entity bindings missing {missing}")
    if extra:
        errors.append(f"{label}: durable entity bindings unknown {extra}")
    if len(observed_kinds) != len(set(observed_kinds)):
        errors.append(f"{label}: durable entity bindings must not duplicate entity_kind")

    for item in _objects(entity_bindings):
        entity_kind = item.get("entity_kind")
        item_label = f"{label}: durable entity binding {entity_kind}"
        if item.get("write_authority_enabled") is not False:
            errors.append(f"{item_label} write_authority_enabled must remain false")
        if item.get("append_enabled") is not False:
            errors.append(f"{item_label} append_enabled must remain false")
        if item.get("mutation_route") is not False:
            errors.append(f"{item_label} mutation_route must remain false")
        if item.get("secret_values_serialized") is not False:
            errors.append(f"{item_label} secret_values_serialized must remain false")
        owner_ref_fields = item.get("owner_ref_fields")
        if not isinstance(owner_ref_fields, list) or not owner_ref_fields:
            errors.append(f"{item_label} owner_ref_fields must be a non-empty list")
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"{item_label} evidence_refs must be a non-empty list")


def _validate_complete_high_risk_actions(
    example: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    permission_snapshot = example.get("permission_snapshot")
    if not isinstance(permission_snapshot, dict):
        errors.append(f"{label}: permission_snapshot must be an object")
        return
    observed = set(str(item) for item in permission_snapshot.get("blocked_high_risk_actions", ()))
    missing = sorted(set(HIGH_RISK_ACTIONS) - observed)
    extra = sorted(observed - set(HIGH_RISK_ACTIONS))
    if missing:
        errors.append(f"{label}: blocked_high_risk_actions missing {missing}")
    if extra:
        errors.append(f"{label}: blocked_high_risk_actions unknown {extra}")


def _validate_read_only_flags(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if key_lower == "read_only" and value is not True:
            errors.append(f"{label}: {path} must be true")
        if key_lower in READ_ONLY_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {path} must be false")


def _validate_secret_surface(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_strings(payload):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _ids(collection: Any, key: str) -> set[str]:
    return {str(item.get(key)) for item in _objects(collection) if item.get(key)}


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _require_refs(
    *,
    observed: Any,
    valid: set[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    missing = sorted(str(item) for item in observed if str(item) not in valid)
    if missing:
        errors.append(f"{label} missing {missing}")


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_json(item, f"{path}[{index}]")


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
    """Parse harness read-model validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate read-only Agentic Service Harness read models."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for harness read-model validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_read_models(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_agentic_service_harness_read_model_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ MODELS VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS READ MODELS INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
