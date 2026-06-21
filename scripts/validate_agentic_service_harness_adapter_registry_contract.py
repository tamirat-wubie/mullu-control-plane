#!/usr/bin/env python3
"""Validate Agentic Service Harness adapter registry contract.

Purpose: prove the GitHub/Codex-style adapter registry is contract-only,
read-only, source-bound, and non-terminal before subprocess execution,
connector calls, external model execution, live adapter execution, branch
writes, pull-request creation, receipt append, mutation routes, secret
serialization, deployment, DNS mutation, destructive operation, or terminal
closure is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_adapter_registry_contract.schema.json,
examples/agentic_service_harness_adapter_registry_contract.foundation.json,
scripts.validate_agentic_service_harness_dashboard_data_contract,
scripts.validate_agentic_service_harness_github_repo_task_intake, and
scripts.validate_schemas.
Invariants:
  - Source dashboard data contract and GitHub repo task intake validate first.
  - Adapter ids, mode ids, denied action classes, and blocker refs are complete.
  - Subprocess execution, connector calls, external model execution, live
    adapter execution, branch writes, PR creation, receipt append, secrets,
    mutation routes, and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_dashboard_data_contract import (  # noqa: E402
    validate_agentic_service_harness_dashboard_data_contract,
)
from scripts.validate_agentic_service_harness_github_repo_task_intake import (  # noqa: E402
    validate_agentic_service_harness_github_repo_task_intake,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_adapter_registry_contract.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_adapter_registry_contract.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_adapter_registry_contract_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_adapter_registry_contract"
EXPECTED_SOURCE_DASHBOARD_DATA_CONTRACT_REF = (
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json"
)
EXPECTED_SOURCE_TASK_INTAKE_REF = (
    "examples/agentic_service_harness_github_repo_task_intake.foundation.json"
)
EXPECTED_DECISION = "CONTRACT_ONLY_ADAPTER_REGISTRY_ACCEPTED"
EXPECTED_ADAPTER_IDS = frozenset(
    {
        "github_repository_read_adapter",
        "codex_style_planning_adapter",
    }
)
EXPECTED_MODE_IDS = frozenset(
    {
        "read_only",
        "dry_run",
        "branch_write_awaiting_approval",
        "open_pr_awaiting_approval",
    }
)
EXPECTED_FORBIDDEN_ACTION_CLASSES = frozenset(
    {
        "register_route",
        "mutation_endpoint",
        "execute_adapter",
        "spawn_subprocess",
        "connector_call",
        "external_model_execution",
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
        "gate://harness/no-adapter-route-registration",
        "gate://harness/no-mutation-endpoints",
        "gate://harness/no-live-adapter-execution",
        "gate://harness/no-subprocess-execution",
        "gate://harness/no-connector-call",
        "gate://harness/no-external-model-execution",
        "gate://harness/no-branch-write",
        "gate://harness/no-pr-creation",
        "gate://harness/no-receipt-store-append",
        "gate://harness/no-secret-serialization",
        "gate://harness/terminal-closure-denied",
    }
)
EXPECTED_RECEIPT_REFS = {
    "adapter_registry_contract_schema": (
        "schemas/agentic_service_harness_adapter_registry_contract.schema.json"
    ),
    "adapter_registry_contract_fixture": (
        "examples/agentic_service_harness_adapter_registry_contract.foundation.json"
    ),
    "dashboard_data_contract_schema": (
        "schemas/agentic_service_harness_dashboard_data_contract.schema.json"
    ),
    "dashboard_data_contract_fixture": (
        "examples/agentic_service_harness_dashboard_data_contract.foundation.json"
    ),
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
        "registry_route_admitted",
        "mutation_endpoints_admitted",
        "external_adapter_integrated",
        "subprocess_execution_enabled",
        "connector_call_enabled",
        "external_model_execution_enabled",
        "branch_write_enabled",
        "pull_request_creation_enabled",
        "receipt_store_append_enabled",
        "secret_values_serialized",
        "live_integration_enabled",
        "permits_runtime_effects",
        "registry_route_registration_enabled",
        "mutation_endpoint_enabled",
        "live_adapter_execution_enabled",
        "repository_write_enabled",
        "runtime_state_write_enabled",
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
        "contract_only",
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
class AdapterRegistryContractValidation:
    """Schema and semantic validation report for adapter registry contract."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    adapter_count: int
    mode_count: int
    dashboard_source_ok: bool
    task_intake_source_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_adapter_registry_contract(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> AdapterRegistryContractValidation:
    """Validate adapter registry contract examples against schema and invariants."""
    errors: list[str] = []
    dashboard_validation = validate_agentic_service_harness_dashboard_data_contract()
    task_intake_validation = validate_agentic_service_harness_github_repo_task_intake()
    if not dashboard_validation.ok:
        errors.extend(
            f"source dashboard data contract invalid: {error}"
            for error in dashboard_validation.errors
        )
    if not task_intake_validation.ok:
        errors.extend(
            f"source GitHub repo task intake invalid: {error}"
            for error in task_intake_validation.errors
        )

    schema = _load_json_object(schema_path, "adapter registry contract schema", errors)
    examples: list[dict[str, Any]] = []
    observed_adapter_ids: set[str] = set()
    observed_mode_ids: set[str] = set()
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"adapter registry contract example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        observed_adapter_ids.update(_ids(example.get("adapters"), "adapter_id"))
        observed_mode_ids.update(_ids(example.get("mode_bindings"), "mode_id"))
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_adapter_registry_semantics(example, errors, _path_label(example_path))

    return AdapterRegistryContractValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        adapter_count=len(observed_adapter_ids),
        mode_count=len(observed_mode_ids),
        dashboard_source_ok=dashboard_validation.ok,
        task_intake_source_ok=task_intake_validation.ok,
    )


def write_adapter_registry_contract_validation(
    validation: AdapterRegistryContractValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic adapter registry contract validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_adapter_registry_semantics(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(example, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(
        example,
        ("source_dashboard_data_contract_ref",),
        EXPECTED_SOURCE_DASHBOARD_DATA_CONTRACT_REF,
        errors,
        label,
    )
    _check_value(example, ("source_task_intake_ref",), EXPECTED_SOURCE_TASK_INTAKE_REF, errors, label)
    _check_value(example, ("registry", "decision"), EXPECTED_DECISION, errors, label)
    _validate_scope(example, errors, label)
    _validate_registry(example, errors, label)
    _validate_adapters(example, errors, label)
    _validate_mode_bindings(example, errors, label)
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
    if scope.get("foundation_phase") != "foundation_contract_only_adapter_registry":
        errors.append(f"{label}: scope.foundation_phase must be foundation_contract_only_adapter_registry")
    if scope.get("registry_id") != "adapter-registry-contract-foundation":
        errors.append(f"{label}: scope.registry_id must be adapter-registry-contract-foundation")


def _validate_registry(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    registry = _mapping_at(example, ("registry",))
    if not registry:
        errors.append(f"{label}: registry must be an object")
        return
    allowed = set(str(item) for item in registry.get("allowed_action_classes", ()))
    forbidden = set(str(item) for item in registry.get("forbidden_action_classes", ()))
    gates = set(str(item) for item in registry.get("required_gate_refs", ()))
    missing_forbidden = sorted(EXPECTED_FORBIDDEN_ACTION_CLASSES - forbidden)
    missing_gates = sorted(EXPECTED_GATE_REFS - gates)
    if allowed != {"read_only"}:
        errors.append(f"{label}: allowed_action_classes must be read_only only")
    if missing_forbidden:
        errors.append(f"{label}: forbidden_action_classes missing {missing_forbidden}")
    if missing_gates:
        errors.append(f"{label}: required_gate_refs missing {missing_gates}")
    blocked = registry.get("blocked_reason_refs")
    if not isinstance(blocked, list) or not blocked:
        errors.append(f"{label}: blocked_reason_refs must not be empty")
    if registry.get("entry_count") != len(_objects(example.get("adapters"))):
        errors.append(f"{label}: registry.entry_count must equal adapter descriptor count")


def _validate_adapters(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    adapters = _objects(example.get("adapters"))
    adapter_ids = _ids(adapters, "adapter_id")
    missing_adapters = sorted(EXPECTED_ADAPTER_IDS - adapter_ids)
    if missing_adapters:
        errors.append(f"{label}: adapters missing {missing_adapters}")
    for adapter in adapters:
        adapter_id = str(adapter.get("adapter_id"))
        supported_modes = set(str(item) for item in adapter.get("supported_modes", ()))
        if adapter.get("authority_class") != "contract_only_read_model":
            errors.append(f"{label}: adapter {adapter_id} authority_class must be contract_only_read_model")
        if not supported_modes:
            errors.append(f"{label}: adapter {adapter_id} must list supported_modes")
        if not supported_modes <= EXPECTED_MODE_IDS:
            errors.append(f"{label}: adapter {adapter_id} has unknown supported_modes")
        if not adapter.get("required_input_refs"):
            errors.append(f"{label}: adapter {adapter_id} must list required_input_refs")
        if not adapter.get("required_evidence_refs"):
            errors.append(f"{label}: adapter {adapter_id} must list required_evidence_refs")
        if not adapter.get("blocked_reason_refs"):
            errors.append(f"{label}: adapter {adapter_id} must list blocked_reason_refs")


def _validate_mode_bindings(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    modes = _objects(example.get("mode_bindings"))
    mode_ids = _ids(modes, "mode_id")
    missing_modes = sorted(EXPECTED_MODE_IDS - mode_ids)
    if missing_modes:
        errors.append(f"{label}: mode_bindings missing {missing_modes}")
    for mode in modes:
        mode_id = str(mode.get("mode_id"))
        adapter_ids = set(str(item) for item in mode.get("adapter_ids", ()))
        unknown_adapter_ids = sorted(adapter_ids - EXPECTED_ADAPTER_IDS)
        if unknown_adapter_ids:
            errors.append(f"{label}: mode {mode_id} references unknown adapters {unknown_adapter_ids}")
        if not adapter_ids:
            errors.append(f"{label}: mode {mode_id} must list adapter_ids")
        if not mode.get("required_gate_refs"):
            errors.append(f"{label}: mode {mode_id} must list required_gate_refs")
        if not mode.get("blocked_reason_refs"):
            errors.append(f"{label}: mode {mode_id} must list blocked_reason_refs")
        if mode.get("authority_result") not in {"read_only_allowed", "effect_blocked"}:
            errors.append(f"{label}: mode {mode_id} has invalid authority_result")
        if mode_id != "read_only" and mode.get("requires_operator_approval") is not True:
            errors.append(f"{label}: mode {mode_id} must require operator approval")


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
    expected_command = "python scripts/validate_agentic_service_harness_adapter_registry_contract.py --strict"
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
    if not isinstance(collection, (list, tuple)):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _ids(collection: Any, key: str) -> set[str]:
    if isinstance(collection, tuple):
        objects = collection
    else:
        objects = _objects(collection)
    return {str(item.get(key)) for item in objects if isinstance(item, Mapping)}


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
    """Parse adapter registry contract validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the contract-only harness adapter registry."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for adapter registry contract validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_adapter_registry_contract(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_adapter_registry_contract_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS ADAPTER REGISTRY CONTRACT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS ADAPTER REGISTRY CONTRACT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
