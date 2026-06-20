#!/usr/bin/env python3
"""Validate Agentic Service Harness dashboard data contract.

Purpose: prove the first dashboard-facing harness data contract is read-only,
contract-only, source-bound, and non-terminal before any UI, route, mutation
endpoint, adapter execution, branch write, pull-request creation, receipt
append, secret serialization, deployment, DNS mutation, destructive operation,
or terminal closure is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_dashboard_data_contract.schema.json,
examples/agentic_service_harness_dashboard_data_contract.foundation.json,
scripts.validate_agentic_service_harness_read_models,
scripts.validate_agentic_service_harness_github_repo_task_intake, and
scripts.validate_schemas.
Invariants:
  - Source read models and GitHub repo task intake validate first.
  - Widget ids, source collections, and binding ids are complete.
  - Dashboard UI creation, route registration, mutation controls, effects,
    receipt append, secrets, and terminal closure fail closed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_github_repo_task_intake import (  # noqa: E402
    validate_agentic_service_harness_github_repo_task_intake,
)
from scripts.validate_agentic_service_harness_read_models import (  # noqa: E402
    validate_agentic_service_harness_read_models,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_dashboard_data_contract.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_dashboard_data_contract.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_dashboard_data_contract_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_dashboard_data_contract"
EXPECTED_SOURCE_READ_MODEL_REF = "examples/agentic_service_harness_read_models.foundation.json"
EXPECTED_SOURCE_TASK_INTAKE_REF = (
    "examples/agentic_service_harness_github_repo_task_intake.foundation.json"
)
EXPECTED_DECISION = "READ_ONLY_DASHBOARD_DATA_CONTRACT_ACCEPTED"
EXPECTED_WIDGET_IDS = frozenset(
    {
        "account_summary",
        "repository_connection",
        "run_status",
        "approval_gate",
        "receipt_evidence",
        "workspace_safety",
        "readiness_next_action",
    }
)
EXPECTED_SOURCE_COLLECTIONS = frozenset(
    {
        "accounts",
        "projects",
        "repositories",
        "runs",
        "approvals",
        "receipts",
        "evidence",
        "result_summaries",
        "workspace_allocations",
        "permission_snapshot",
        "github_repo_task_intake",
    }
)
EXPECTED_FORBIDDEN_ACTION_CLASSES = frozenset(
    {
        "create_ui",
        "register_route",
        "mutation_endpoint",
        "execute_adapter",
        "write_to_branch",
        "open_pr",
        "append_receipt_store",
        "deploy",
        "dns_mutation",
        "secret_mutation",
        "destructive_operation",
        "terminal_closure",
    }
)
EXPECTED_GATE_REFS = frozenset(
    {
        "gate://harness/no-dashboard-ui-creation",
        "gate://harness/no-dashboard-route-registration",
        "gate://harness/no-mutation-endpoints",
        "gate://harness/no-live-adapter-execution",
        "gate://harness/no-branch-write",
        "gate://harness/no-pr-creation",
        "gate://harness/no-receipt-store-append",
        "gate://harness/no-secret-serialization",
        "gate://harness/terminal-closure-denied",
    }
)
EXPECTED_SCREEN_STATUSES = frozenset({"loading", "ready", "empty", "blocked"})
EXPECTED_RECEIPT_REFS = {
    "dashboard_data_contract_schema": (
        "schemas/agentic_service_harness_dashboard_data_contract.schema.json"
    ),
    "dashboard_data_contract_fixture": (
        "examples/agentic_service_harness_dashboard_data_contract.foundation.json"
    ),
    "harness_read_models_schema": "schemas/agentic_service_harness_read_models.schema.json",
    "harness_read_models_fixture": "examples/agentic_service_harness_read_models.foundation.json",
    "github_repo_task_intake_schema": (
        "schemas/agentic_service_harness_github_repo_task_intake.schema.json"
    ),
    "github_repo_task_intake_fixture": (
        "examples/agentic_service_harness_github_repo_task_intake.foundation.json"
    ),
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = frozenset(
    {
        "dashboard_implemented",
        "ui_created",
        "route_admitted",
        "mutation_endpoints_admitted",
        "external_adapter_integrated",
        "adapter_executed",
        "runtime_state_write_enabled",
        "receipt_store_append_enabled",
        "secret_values_serialized",
        "polling_enabled",
        "subscription_enabled",
        "route_registered",
        "mutation_controls_allowed",
        "ui_component_created",
        "action_links_allowed",
        "requires_live_adapter",
        "permits_mutation",
        "action_cta_allowed",
        "dashboard_ui_creation_enabled",
        "route_registration_enabled",
        "mutation_endpoint_enabled",
        "live_adapter_execution_enabled",
        "branch_write_enabled",
        "pull_request_creation_enabled",
        "repository_write_enabled",
        "deployment_enabled",
        "dns_mutation_enabled",
        "secret_mutation_enabled",
        "destructive_operation_enabled",
        "terminal_closure",
        "default_high_risk_authority",
    }
)
REQUIRED_TRUE_FLAGS = frozenset(
    {
        "read_only",
        "approval_required_for_effects",
        "report_is_not_terminal_closure",
        "terminal_closure_required",
        "required_for_closure",
    }
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
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
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DashboardDataContractValidation:
    """Schema and semantic validation report for dashboard data contract."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    widget_count: int
    source_collection_count: int
    read_model_source_ok: bool
    task_intake_source_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_dashboard_data_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> DashboardDataContractValidation:
    """Validate dashboard data contract examples against schema and invariants."""
    errors: list[str] = []
    read_model_validation = validate_agentic_service_harness_read_models()
    task_intake_validation = validate_agentic_service_harness_github_repo_task_intake()
    if not read_model_validation.ok:
        errors.extend(f"source read models invalid: {error}" for error in read_model_validation.errors)
    if not task_intake_validation.ok:
        errors.extend(f"source GitHub repo task intake invalid: {error}" for error in task_intake_validation.errors)

    schema = _load_json_object(schema_path, "dashboard data contract schema", errors)
    examples: list[dict[str, Any]] = []
    observed_widget_ids: set[str] = set()
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"dashboard data contract example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        observed_widget_ids.update(_widget_ids(example.get("widgets")))
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_dashboard_semantics(example, errors, _path_label(example_path))

    return DashboardDataContractValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        widget_count=len(observed_widget_ids),
        source_collection_count=len(EXPECTED_SOURCE_COLLECTIONS),
        read_model_source_ok=read_model_validation.ok,
        task_intake_source_ok=task_intake_validation.ok,
    )


def write_dashboard_data_contract_validation(
    validation: DashboardDataContractValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic dashboard data contract validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_dashboard_semantics(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(example, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(example, ("source_read_model_ref",), EXPECTED_SOURCE_READ_MODEL_REF, errors, label)
    _check_value(example, ("source_task_intake_ref",), EXPECTED_SOURCE_TASK_INTAKE_REF, errors, label)
    _check_value(example, ("data_contract", "decision"), EXPECTED_DECISION, errors, label)
    _validate_scope(example, errors, label)
    _validate_data_contract(example, errors, label)
    _validate_widgets(example, errors, label)
    _validate_data_bindings(example, errors, label)
    _validate_screen_states(example, errors, label)
    _validate_receipt_refs(example, errors, label)
    _validate_validators(example, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_scope(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping_at(example, ("scope",))
    if not scope:
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("foundation_phase") != "foundation_read_only_dashboard_data_contract":
        errors.append(f"{label}: scope.foundation_phase must be foundation_read_only_dashboard_data_contract")
    if scope.get("dashboard_contract_id") != "dashboard-data-contract-foundation":
        errors.append(f"{label}: scope.dashboard_contract_id must be dashboard-data-contract-foundation")


def _validate_data_contract(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    contract = _mapping_at(example, ("data_contract",))
    if not contract:
        errors.append(f"{label}: data_contract must be an object")
        return
    source_collections = set(str(item) for item in contract.get("source_collections", ()))
    forbidden = set(str(item) for item in contract.get("forbidden_action_classes", ()))
    gates = set(str(item) for item in contract.get("required_gate_refs", ()))
    allowed = set(str(item) for item in contract.get("allowed_action_classes", ()))
    missing_sources = sorted(EXPECTED_SOURCE_COLLECTIONS - source_collections)
    missing_forbidden = sorted(EXPECTED_FORBIDDEN_ACTION_CLASSES - forbidden)
    missing_gates = sorted(EXPECTED_GATE_REFS - gates)
    if allowed != {"read_only"}:
        errors.append(f"{label}: allowed_action_classes must be read_only only")
    if missing_sources:
        errors.append(f"{label}: source_collections missing {missing_sources}")
    if missing_forbidden:
        errors.append(f"{label}: forbidden_action_classes missing {missing_forbidden}")
    if missing_gates:
        errors.append(f"{label}: required_gate_refs missing {missing_gates}")
    blocked = contract.get("blocked_reason_refs")
    if not isinstance(blocked, list) or not blocked:
        errors.append(f"{label}: blocked_reason_refs must not be empty")


def _validate_widgets(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    widgets = _objects(example.get("widgets"))
    widget_ids = _widget_ids(widgets)
    missing_widgets = sorted(EXPECTED_WIDGET_IDS - widget_ids)
    if missing_widgets:
        errors.append(f"{label}: widgets missing {missing_widgets}")
    for widget in widgets:
        widget_id = str(widget.get("widget_id"))
        if not widget.get("required_fields"):
            errors.append(f"{label}: widget {widget_id} must list required_fields")
        if not widget.get("evidence_refs"):
            errors.append(f"{label}: widget {widget_id} must list evidence_refs")


def _validate_data_bindings(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    bindings = _objects(example.get("data_bindings"))
    binding_widget_ids = {str(binding.get("widget_id")) for binding in bindings}
    missing_bindings = sorted(EXPECTED_WIDGET_IDS - binding_widget_ids)
    if missing_bindings:
        errors.append(f"{label}: data_bindings missing widget bindings {missing_bindings}")
    binding_ids = [str(binding.get("binding_id")) for binding in bindings]
    if len(binding_ids) != len(set(binding_ids)):
        errors.append(f"{label}: data_binding binding_id values must be unique")
    for binding in bindings:
        binding_id = str(binding.get("binding_id"))
        if not binding.get("identity_keys"):
            errors.append(f"{label}: data_binding {binding_id} must list identity_keys")
        if not binding.get("evidence_refs"):
            errors.append(f"{label}: data_binding {binding_id} must list evidence_refs")


def _validate_screen_states(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    states = _objects(example.get("screen_states"))
    statuses = {str(state.get("status")) for state in states}
    missing_statuses = sorted(EXPECTED_SCREEN_STATUSES - statuses)
    if missing_statuses:
        errors.append(f"{label}: screen_states missing statuses {missing_statuses}")
    for state in states:
        state_id = str(state.get("state_id"))
        if not state.get("display_rule"):
            errors.append(f"{label}: screen_state {state_id} must define display_rule")


def _validate_receipt_refs(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    receipt_refs = _mapping_at(example, ("receipt_refs",))
    if not receipt_refs:
        errors.append(f"{label}: receipt_refs must be an object")
        return
    for key, expected in EXPECTED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected:
            errors.append(f"{label}: receipt_refs.{key} must be {expected}")


def _validate_validators(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    validators = example.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append(f"{label}: validators must not be empty")
        return
    commands = {str(item.get("command")) for item in _objects(validators)}
    expected_command = "python scripts/validate_agentic_service_harness_dashboard_data_contract.py --strict"
    if expected_command not in commands:
        errors.append(f"{label}: validators must include {expected_command}")


def _validate_boolean_flags(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if key_lower in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {path} must be false")
        if key_lower in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {path} must be true")


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


def _check_value(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: Any,
    errors: list[str],
    label: str,
) -> None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            errors.append(f"{label}: {'.'.join(path)} is required")
            return
        current = current[key]
    if current != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


def _mapping_at(payload: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any]:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _widget_ids(collection: Any) -> set[str]:
    if isinstance(collection, tuple):
        objects = collection
    else:
        objects = _objects(collection)
    return {str(item.get("widget_id")) for item in objects if isinstance(item, Mapping)}


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_json(item, f"{path}[{index}]")


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, Mapping):
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
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse dashboard data contract validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the read-only harness dashboard data contract."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for dashboard data contract validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_dashboard_data_contract(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_dashboard_data_contract_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS DASHBOARD DATA CONTRACT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS DASHBOARD DATA CONTRACT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
