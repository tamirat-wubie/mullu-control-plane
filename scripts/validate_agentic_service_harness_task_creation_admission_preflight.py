#!/usr/bin/env python3
"""Validate Agentic Service Harness task creation admission preflight.

Purpose: prove user-facing AgentTask creation remains blocked until source
read models, approvals, UAO admission, rollback evidence, and receipt evidence
are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_task_creation_admission_preflight.schema.json,
examples/agentic_service_harness_task_creation_admission_preflight.foundation.json,
and source harness validators for task intake, dashboard data, LoopStatus, and
Receipt projection.
Invariants:
  - Source read-model validators pass first.
  - Task creation route and task record writes are not admitted.
  - Adapter execution, branch workspace creation, receipt append, secrets, and
    terminal closure fail closed.
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
from scripts.validate_agentic_service_harness_loopstatus_projection import (  # noqa: E402
    validate_agentic_service_harness_loopstatus_projection,
)
from scripts.validate_agentic_service_harness_receipt_projection import (  # noqa: E402
    validate_agentic_service_harness_receipt_projection,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_task_creation_admission_preflight.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_task_creation_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_task_creation_admission_preflight_validation.json"
EXPECTED_REPORT_ID = "agentic_service_harness_task_creation_admission_preflight"
EXPECTED_DECISION = "TASK_CREATION_ADMISSION_BLOCKED_PENDING_AUTHORITY"
REQUIRED_SOURCE_REFS = (
    "schemas/agentic_service_harness.schema.json",
    "examples/agentic_service_harness_github_repo_task_intake.foundation.json",
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "examples/agentic_service_harness_loopstatus_projection.foundation.json",
    "examples/agentic_service_harness_receipt_projection.foundation.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BLOCKERS = (
    "blocked://task-creation-route/not-admitted",
    "blocked://task-record-write/no-uao-admission",
    "blocked://approval/task-creation-not-collected",
    "blocked://adapter-execution/not-admitted",
    "blocked://receipt-store/append-not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_FALSE_FLAGS = (
    "task_creation_route_admitted",
    "runtime_state_write_enabled",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "approval_evidence_collected",
    "uao_admission_collected",
    "task_record_write_admitted",
    "adapter_execution_admitted",
    "branch_workspace_creation_admitted",
    "receipt_emission_admitted",
    "terminal_closure_allowed",
    "task_creation_route_enabled",
    "task_record_write_enabled",
    "adapter_execution_enabled",
    "branch_workspace_creation_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "repository_write_enabled",
    "mutation_route_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "preflight_only",
    "read_only_sources",
    "task_scope_valid",
    "source_read_models_valid",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {"secret_values_serialized"}
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
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TaskCreationAdmissionValidation:
    """Validation report for task creation admission preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_validators_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_task_creation_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> TaskCreationAdmissionValidation:
    """Validate task creation admission preflight examples."""

    errors: list[str] = []
    source_errors = _validate_sources()
    errors.extend(source_errors)
    schema = _load_json_object(schema_path, "task creation admission schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"task creation admission example {_path_label(example_path)}",
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
        _validate_semantics(example, errors, _path_label(example_path))
    return TaskCreationAdmissionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
    )


def write_task_creation_admission_validation(
    validation: TaskCreationAdmissionValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic task creation admission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_sources() -> list[str]:
    errors: list[str] = []
    source_results = (
        ("github_repo_task_intake", validate_agentic_service_harness_github_repo_task_intake()),
        ("dashboard_data_contract", validate_agentic_service_harness_dashboard_data_contract()),
        ("loopstatus_projection", validate_agentic_service_harness_loopstatus_projection()),
        ("receipt_projection", validate_agentic_service_harness_receipt_projection()),
    )
    for source_name, validation in source_results:
        if not validation.ok:
            errors.extend(f"source {source_name} invalid: {error}" for error in validation.errors)
    return errors


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    if payload.get("report_id") != EXPECTED_REPORT_ID:
        errors.append(f"{label}: report_id must be {EXPECTED_REPORT_ID}")
    if _mapping(payload.get("admission_decision")).get("decision") != EXPECTED_DECISION:
        errors.append(f"{label}: admission_decision.decision must be {EXPECTED_DECISION}")
    _validate_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_required_evidence(payload, errors, label)
    _validate_blockers(payload, errors, label)
    _validate_validators(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_reference_integrity(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(payload.get("scope"))
    request = _mapping(payload.get("admission_request"))
    if not scope or not request:
        errors.append(f"{label}: scope and admission_request must be objects")
        return
    if scope.get("repository_slug") != "tamirat-wubie/mullu-control-plane":
        errors.append(f"{label}: scope.repository_slug must bind the repository")
    if request.get("requested_action") != "create_agent_task":
        errors.append(f"{label}: requested_action must be create_agent_task")
    if request.get("requested_route_ref") != "route://harness/task-creation/not-admitted":
        errors.append(f"{label}: requested_route_ref must remain not-admitted")
    for key in (
        "source_repository_connection_ref",
        "source_dashboard_ref",
        "source_loopstatus_ref",
        "source_receipt_projection_ref",
    ):
        value = request.get(key)
        if not isinstance(value, str) or not value.startswith("examples/agentic_service_harness_"):
            errors.append(f"{label}: admission_request.{key} must bind a harness source example ref")


def _validate_required_evidence(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    required_evidence = _mapping(payload.get("required_evidence"))
    required_sections = (
        "must_have_before_route_admission",
        "must_have_before_task_record_write",
        "must_have_before_adapter_execution",
        "must_have_before_receipt_append",
    )
    for section in required_sections:
        refs = required_evidence.get(section)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}: required_evidence.{section} must not be empty")
    decision_refs = _mapping(payload.get("admission_decision")).get("next_required_evidence_refs")
    if not isinstance(decision_refs, list) or "evidence://approved-branch-workspace-creation-preflight" not in decision_refs:
        errors.append(f"{label}: next_required_evidence_refs must include approved branch workspace preflight")


def _validate_blockers(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    blockers = _mapping(payload.get("admission_decision")).get("blocked_reason_refs")
    if not isinstance(blockers, list):
        errors.append(f"{label}: blocked_reason_refs must be a list")
        return
    missing = sorted(set(REQUIRED_BLOCKERS) - {str(ref) for ref in blockers})
    if missing:
        errors.append(f"{label}: blocked_reason_refs missing {', '.join(missing)}")


def _validate_validators(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    validators = payload.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append(f"{label}: validators must not be empty")
        return
    commands = {str(item.get("command")) for item in _objects(validators)}
    expected = "python scripts/validate_agentic_service_harness_task_creation_admission_preflight.py --strict"
    if expected not in commands:
        errors.append(f"{label}: validators must include {expected}")


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _validate_secret_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if (
            any(token in key.lower() for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_no_mutation_routes(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    for phrase in ("approved branch workspace creation preflight", "task creation admission", "blocked", "terminal closure"):
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{label} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
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


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the task creation admission preflight validator."""

    args = build_arg_parser().parse_args(argv)
    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    write_task_creation_admission_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS TASK CREATION ADMISSION PREFLIGHT VALID")
    else:
        print("AGENTIC SERVICE HARNESS TASK CREATION ADMISSION PREFLIGHT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
