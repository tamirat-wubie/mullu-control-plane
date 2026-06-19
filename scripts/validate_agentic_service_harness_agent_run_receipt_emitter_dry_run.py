#!/usr/bin/env python3
"""Validate Agentic Service Harness AgentRun receipt-emitter dry-run.

Purpose: prove the AgentRun read-model surface can record a simulated
receipt-emitter dry-run while receipt-store append and all runtime effects
remain denied.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_agent_run_receipt_emitter_dry_run.schema.json,
examples/agentic_service_harness_agent_run_receipt_emitter_dry_run.foundation.json,
scripts.validate_agentic_service_harness_read_models, and
scripts.validate_schemas.
Invariants:
  - The dry-run binds to the validated harness read-model contract.
  - Receipt-store append is explicitly blocked.
  - Live adapter execution, runtime state writes, branch creation, PR creation,
    mutation routes, secret material, and terminal closure fail closed.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_read_models import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_CONTRACT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_CONTRACT_SCHEMA,
    validate_agentic_service_harness_read_models,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_agent_run_receipt_emitter_dry_run.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_agent_run_receipt_emitter_dry_run.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_agent_run_receipt_emitter_dry_run_validation.json"
)
EXPECTED_SOURCE_CONTRACT_REF = "examples/agentic_service_harness_read_models.foundation.json"
EXPECTED_AGENT_RUN_ID = "run-read-model-foundation"
EXPECTED_AGENT_RUN_MODE = "read_only"
EXPECTED_SOURCE_TASK_REF = "task://agentic-service-harness/agent-run-read-model-foundation"
EXPECTED_EMITTER_ID = "agent-run-receipt-emitter-dry-run-foundation"
EXPECTED_EMITTER_MODE = "EMITTER_DRY_RUN_ONLY"
EXPECTED_RESULT_STATE = "DRY_RUN_RECORDED"
EXPECTED_SIMULATED_RECEIPT_KIND = "future_agent_run_receipt"
EXPECTED_APPEND_DECISION = "APPEND_BLOCKED_AWAITING_APPROVAL_AND_STORE_BINDING"
EXPECTED_APPEND_TARGET_REF = "receipt-store://agentic-service-harness/agent-run"
REQUIRED_FORBIDDEN_ACTION_CLASSES = (
    "execute_adapter",
    "write_to_branch",
    "open_pr",
    "append_receipt_store",
    "deploy",
    "dns_mutation",
    "secret_mutation",
    "destructive_operation",
    "terminal_closure",
)
REQUIRED_SOURCE_REFS = (
    EXPECTED_SOURCE_CONTRACT_REF,
    "schemas/agentic_service_harness.schema.json",
    "schemas/agentic_service_harness_read_models.schema.json",
)
REQUIRED_GATE_REFS = (
    "gate://harness/no-live-adapter-execution",
    "gate://harness/no-branch-write",
    "gate://harness/no-pr-creation",
    "gate://harness/no-receipt-store-append",
    "gate://harness/no-secret-serialization",
    "gate://harness/terminal-closure-denied",
)
REQUIRED_EMISSION_OBLIGATIONS = (
    "obligation://record-dry-run-envelope",
    "obligation://deny-runtime-receipt-emission",
    "obligation://deny-receipt-store-append",
    "obligation://deny-runtime-effects",
    "obligation://deny-secret-material",
    "obligation://bind-append-admission-blocker",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_agent_run_receipt_emitter_dry_run.py",
    "scripts/validate_agentic_service_harness_read_models.py",
)
REQUIRED_APPEND_REFS = (
    "evidence://receipt-store-write-path-binding",
    "evidence://uao-append-admission",
    "evidence://operator-approval-for-append",
    "evidence://append-rollback-plan",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_APPEND_BLOCKERS = (
    "blocked://receipt-store/write-path-not-bound",
    "blocked://uao/append-not-admitted",
    "blocked://operator-approval/not-present",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "agent_run_receipt_emitter_dry_run_schema": (
        "schemas/agentic_service_harness_agent_run_receipt_emitter_dry_run.schema.json"
    ),
    "read_models_schema": "schemas/agentic_service_harness_read_models.schema.json",
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "agentic_service_harness_read_models_schema": "schemas/agentic_service_harness_read_models.schema.json",
}
REQUIRED_FALSE_FLAGS = (
    "receipt_store_append_enabled",
    "external_adapter_integrated",
    "secret_values_serialized",
    "runtime_receipt_emitted",
    "receipt_store_appended",
    "adapter_executed",
    "branch_created",
    "pull_request_opened",
    "runtime_state_written",
    "mutation_route_called",
    "external_effects_observed",
    "filesystem_writes_observed",
    "connector_calls_observed",
    "raw_output_included",
    "raw_secret_material_included",
    "terminal_closure",
    "success_claim_allowed",
    "append_admitted",
    "terminal_closure_allowed",
    "live_adapter_execution_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "dry_run_only",
    "dry_run_receipt_recorded",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "raw_secret_material_included",
    "secret_mutation",
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
class AgentRunReceiptEmitterDryRunValidation:
    """Schema and semantic validation report for AgentRun dry-run emitter."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_contract_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_agent_run_receipt_emitter_dry_run(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_contract_schema_path: Path = DEFAULT_SOURCE_CONTRACT_SCHEMA,
    source_contract_example_paths: Sequence[Path] = DEFAULT_SOURCE_CONTRACT_EXAMPLES,
) -> AgentRunReceiptEmitterDryRunValidation:
    """Validate AgentRun receipt-emitter dry-run examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "AgentRun receipt-emitter dry-run schema", errors)
    source_validation = validate_agentic_service_harness_read_models(
        schema_path=source_contract_schema_path,
        example_paths=source_contract_example_paths,
    )
    if not source_validation.ok:
        errors.extend(f"source contract: {error}" for error in source_validation.errors)
    source_contract = _load_json_object(
        source_contract_example_paths[0],
        "harness read-model source contract",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"AgentRun receipt-emitter dry-run example {_path_label(example_path)}",
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
        _validate_dry_run_semantics(example, source_contract, errors, _path_label(example_path))
    return AgentRunReceiptEmitterDryRunValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_contract_ref=EXPECTED_SOURCE_CONTRACT_REF,
    )


def write_agent_run_receipt_emitter_dry_run_validation(
    validation: AgentRunReceiptEmitterDryRunValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic AgentRun receipt-emitter dry-run report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_dry_run(**changes: Any) -> dict[str, Any]:
    """Return a mutated copy of the default dry-run fixture for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default dry-run fixture", [])
    mutated = deepcopy(payload)
    for dotted_path, value in changes.items():
        cursor: dict[str, Any] = mutated
        path_parts = dotted_path.split("__")
        for key in path_parts[:-1]:
            next_cursor = cursor[key]
            if not isinstance(next_cursor, dict):
                raise TypeError(f"cannot mutate non-object path component {key}")
            cursor = next_cursor
        cursor[path_parts[-1]] = value
    return mutated


def _validate_dry_run_semantics(
    example: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _validate_source_binding(example, source_contract, errors, label)
    _validate_contract_sections(example, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_ref_sets(example, errors, label)
    _validate_receipt_refs(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_source_binding(
    example: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if example.get("source_contract_ref") != EXPECTED_SOURCE_CONTRACT_REF:
        errors.append(f"{label}: source_contract_ref must bind the harness read-model fixture")
    scope = example.get("scope")
    source_scope = source_contract.get("projection_scope")
    source_repositories = source_contract.get("repositories")
    source_runs = source_contract.get("runs")
    if not isinstance(scope, Mapping):
        errors.append(f"{label}: scope must be an object")
        return
    if not isinstance(source_scope, Mapping):
        errors.append(f"{label}: source scope must be an object")
        return
    for key in ("tenant_id", "organization_id", "project_id"):
        if scope.get(key) != source_scope.get(key):
            errors.append(f"{label}: scope.{key} must match source contract")
    repository = _first_mapping(source_repositories)
    if not repository:
        errors.append(f"{label}: source repositories must include a repository connection")
    else:
        if scope.get("repository_connection_id") != repository.get("connection_id"):
            errors.append(f"{label}: scope.repository_connection_id must match source repository")
        if scope.get("repository_slug") != repository.get("repository_slug"):
            errors.append(f"{label}: scope.repository_slug must match source repository")
    run = _first_mapping(source_runs)
    if not run:
        errors.append(f"{label}: source runs must include an AgentRun")
    else:
        if scope.get("agent_run_id") != run.get("run_id"):
            errors.append(f"{label}: scope.agent_run_id must match source AgentRun")
        if scope.get("agent_run_mode") != run.get("mode"):
            errors.append(f"{label}: scope.agent_run_mode must match source AgentRun mode")
    if scope.get("agent_run_id") != EXPECTED_AGENT_RUN_ID:
        errors.append(f"{label}: scope.agent_run_id must be {EXPECTED_AGENT_RUN_ID}")
    if scope.get("agent_run_mode") != EXPECTED_AGENT_RUN_MODE:
        errors.append(f"{label}: scope.agent_run_mode must be {EXPECTED_AGENT_RUN_MODE}")


def _validate_contract_sections(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    dry_run_contract = example.get("dry_run_contract")
    emission = example.get("simulated_receipt_emission")
    append_gate = example.get("append_admission_gate")
    if not isinstance(dry_run_contract, Mapping):
        errors.append(f"{label}: dry_run_contract must be an object")
        return
    if not isinstance(emission, Mapping):
        errors.append(f"{label}: simulated_receipt_emission must be an object")
        return
    if not isinstance(append_gate, Mapping):
        errors.append(f"{label}: append_admission_gate must be an object")
        return
    if dry_run_contract.get("emitter_id") != EXPECTED_EMITTER_ID:
        errors.append(f"{label}: dry_run_contract.emitter_id must be {EXPECTED_EMITTER_ID}")
    if dry_run_contract.get("emitter_mode") != EXPECTED_EMITTER_MODE:
        errors.append(f"{label}: dry_run_contract.emitter_mode must be {EXPECTED_EMITTER_MODE}")
    if dry_run_contract.get("source_task_ref") != EXPECTED_SOURCE_TASK_REF:
        errors.append(f"{label}: dry_run_contract.source_task_ref must bind the source task")
    allowed = set(str(item) for item in dry_run_contract.get("allowed_action_classes", ()))
    if allowed != {"dry_run"}:
        errors.append(f"{label}: dry_run_contract.allowed_action_classes must be dry_run only")
    forbidden = set(str(item) for item in dry_run_contract.get("forbidden_action_classes", ()))
    missing_forbidden = sorted(set(REQUIRED_FORBIDDEN_ACTION_CLASSES) - forbidden)
    if missing_forbidden:
        errors.append(f"{label}: dry_run_contract.forbidden_action_classes missing {missing_forbidden}")
    if emission.get("result_state") != EXPECTED_RESULT_STATE:
        errors.append(f"{label}: simulated_receipt_emission.result_state must be {EXPECTED_RESULT_STATE}")
    if emission.get("simulated_receipt_kind") != EXPECTED_SIMULATED_RECEIPT_KIND:
        errors.append(
            f"{label}: simulated_receipt_emission.simulated_receipt_kind must be {EXPECTED_SIMULATED_RECEIPT_KIND}"
        )
    if append_gate.get("decision") != EXPECTED_APPEND_DECISION:
        errors.append(f"{label}: append_admission_gate.decision must be {EXPECTED_APPEND_DECISION}")
    if append_gate.get("append_target_ref") != EXPECTED_APPEND_TARGET_REF:
        errors.append(f"{label}: append_admission_gate.append_target_ref must be {EXPECTED_APPEND_TARGET_REF}")


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


def _validate_ref_sets(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    dry_run_contract = example.get("dry_run_contract")
    append_gate = example.get("append_admission_gate")
    if not isinstance(dry_run_contract, Mapping) or not isinstance(append_gate, Mapping):
        return
    _require_refs(
        dry_run_contract.get("required_source_refs"),
        REQUIRED_SOURCE_REFS,
        f"{label}: dry_run_contract.required_source_refs",
        errors,
    )
    _require_refs(
        dry_run_contract.get("required_gate_refs"),
        REQUIRED_GATE_REFS,
        f"{label}: dry_run_contract.required_gate_refs",
        errors,
    )
    _require_refs(
        dry_run_contract.get("emission_obligations_checked"),
        REQUIRED_EMISSION_OBLIGATIONS,
        f"{label}: dry_run_contract.emission_obligations_checked",
        errors,
    )
    _require_refs(
        dry_run_contract.get("validation_refs"),
        REQUIRED_VALIDATION_REFS,
        f"{label}: dry_run_contract.validation_refs",
        errors,
    )
    _require_refs(
        append_gate.get("required_before_append_refs"),
        REQUIRED_APPEND_REFS,
        f"{label}: append_admission_gate.required_before_append_refs",
        errors,
    )
    _require_refs(
        append_gate.get("blocked_reason_refs"),
        REQUIRED_APPEND_BLOCKERS,
        f"{label}: append_admission_gate.blocked_reason_refs",
        errors,
    )


def _validate_receipt_refs(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    receipt_refs = example.get("receipt_refs")
    if not isinstance(receipt_refs, Mapping):
        errors.append(f"{label}: receipt_refs must be an object")
        return
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _require_refs(
    observed: Any,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_set = set(str(item) for item in observed)
    for required_ref in required:
        if required_ref not in observed_set:
            errors.append(f"{label} missing required ref {required_ref}")


def _first_mapping(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    if not isinstance(first, Mapping):
        return None
    return first


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
    """Parse AgentRun receipt-emitter dry-run validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the harness AgentRun receipt-emitter dry-run contract."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--source-contract-schema", default=str(DEFAULT_SOURCE_CONTRACT_SCHEMA))
    parser.add_argument("--source-contract-example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for AgentRun receipt-emitter dry-run validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    source_contract_example_paths = (
        tuple(Path(example) for example in args.source_contract_example)
        if args.source_contract_example
        else DEFAULT_SOURCE_CONTRACT_EXAMPLES
    )
    validation = validate_agentic_service_harness_agent_run_receipt_emitter_dry_run(
        schema_path=Path(args.schema),
        example_paths=example_paths,
        source_contract_schema_path=Path(args.source_contract_schema),
        source_contract_example_paths=source_contract_example_paths,
    )
    write_agent_run_receipt_emitter_dry_run_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS AgentRun RECEIPT EMITTER DRY-RUN VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS AgentRun RECEIPT EMITTER DRY-RUN INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
