#!/usr/bin/env python3
"""Validate Agentic Service Harness task creation admission preflight.

Purpose: prove task creation admission remains read-only, blocked, and
non-terminal while recording prerequisite evidence for a later user-facing
task route.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies:
schemas/agentic_service_harness_task_creation_admission_preflight.schema.json,
examples/agentic_service_harness_task_creation_admission_preflight.foundation.json,
scripts.validate_schemas.
Invariants:
  - Admission scope matches the project and repository connection request.
  - Task creation route, runtime writes, task persistence, adapter execution,
    branch workspace creation, receipt append, dashboard UI, secrets, and
    terminal closure remain denied.
  - Missing approval and UAO evidence force AwaitingEvidence.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_task_creation_admission_preflight.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_task_creation_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_task_creation_admission_preflight_validation.json"
REQUIRED_SOURCE_REFS = (
    "schemas/agentic_service_harness.schema.json",
    "schemas/agentic_service_harness_read_models.schema.json",
    "schemas/agentic_service_harness_github_repo_task_intake.schema.json",
    "examples/agentic_service_harness_github_repo_task_intake.foundation.json",
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "examples/agentic_service_harness_receipt_evidence_read_models.foundation.json",
    "examples/agentic_service_harness_loopstatus_projection.foundation.json",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_EVIDENCE_REFS = (
    "examples/agentic_service_harness_github_repo_task_intake.foundation.json",
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "examples/agentic_service_harness_receipt_evidence_read_models.foundation.json",
    "examples/agentic_service_harness_loopstatus_projection.foundation.json",
    "approval://task-creation-route/not-collected",
    "evidence://uao-task-creation-admission/not-verified",
    "policy://harness/task-creation-read-only-boundary",
    "receipt://task-creation-admission-preflight/not-emitted",
)
REQUIRED_MISSING_EVIDENCE_REFS = (
    "approval://task-creation-route/not-collected",
    "evidence://uao-task-creation-admission/not-verified",
    "receipt://task-creation-admission-preflight/not-emitted",
)
REQUIRED_BLOCKED_REFS = (
    "blocked://task-creation-route/not-admitted",
    "blocked://task-creation-approval/not-collected",
    "blocked://uao-task-creation-admission/not-verified",
    "blocked://runtime-state-write/not-admitted",
    "blocked://receipt-store-append/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_FALSE_FLAGS = (
    "task_creation_route_admitted",
    "dashboard_ui_admitted",
    "runtime_state_write_enabled",
    "receipt_store_append_enabled",
    "adapter_execution_enabled",
    "branch_workspace_creation_enabled",
    "secret_values_serialized",
    "terminal_closure_granted",
    "approval_collected",
    "uao_admission_verified",
    "runtime_state_write_admitted",
    "task_record_persisted",
    "adapter_execution_admitted",
    "branch_workspace_creation_admitted",
    "receipt_emission_admitted",
    "terminal_closure_allowed",
    "task_creation_route_enabled",
    "task_record_persistence_enabled",
    "live_adapter_execution_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "repository_write_enabled",
    "mutation_route_enabled",
    "dashboard_ui_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "preflight_only",
    "github_repo_task_intake_closed",
    "dashboard_data_contract_closed",
    "receipt_evidence_read_models_closed",
    "loopstatus_projection_closed",
    "approval_required_for_effects",
    "task_scope_valid",
    "repository_connection_valid",
    "required_for_closure",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_values_serialized",
    "secret_mutation_enabled",
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
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TaskCreationAdmissionPreflightValidation:
    """Schema and semantic validation report for task creation admission."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_task_creation_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> TaskCreationAdmissionPreflightValidation:
    """Validate task creation admission preflight examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "task creation admission preflight schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"task creation admission preflight example {_path_label(example_path)}",
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
    return TaskCreationAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
    )


def write_task_creation_admission_preflight_validation(
    validation: TaskCreationAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic task creation admission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _validate_required_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_prerequisite_evidence(payload, errors, label)
    _validate_admission_decision(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_required_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_reference_integrity(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = payload.get("scope")
    request = payload.get("admission_request")
    if not isinstance(scope, Mapping) or not isinstance(request, Mapping):
        errors.append(f"{label}: scope and admission_request must be objects")
        return
    if scope.get("project_id") != request.get("project_id"):
        errors.append(f"{label}: scope.project_id must match admission_request.project_id")
    if scope.get("repository_connection_id") != request.get("repository_connection_id"):
        errors.append(
            f"{label}: scope.repository_connection_id must match admission_request.repository_connection_id"
        )


def _validate_prerequisite_evidence(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence = payload.get("prerequisite_evidence")
    if not isinstance(evidence, Mapping):
        errors.append(f"{label}: prerequisite_evidence must be an object")
        return
    required_refs = {str(ref) for ref in evidence.get("required_evidence_refs", [])}
    missing_required_refs = sorted(set(REQUIRED_EVIDENCE_REFS) - required_refs)
    if missing_required_refs:
        errors.append(f"{label}: missing required_evidence_refs: {', '.join(missing_required_refs)}")
    missing_refs = {str(ref) for ref in evidence.get("missing_evidence_refs", [])}
    absent_missing_refs = sorted(set(REQUIRED_MISSING_EVIDENCE_REFS) - missing_refs)
    if absent_missing_refs:
        errors.append(f"{label}: missing missing_evidence_refs: {', '.join(absent_missing_refs)}")
    if evidence.get("approval_collected") is not False:
        errors.append(f"{label}: approval_collected must remain false")
    if evidence.get("uao_admission_verified") is not False:
        errors.append(f"{label}: uao_admission_verified must remain false")


def _validate_admission_decision(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    decision = payload.get("admission_decision")
    if not isinstance(decision, Mapping):
        errors.append(f"{label}: admission_decision must be an object")
        return
    if decision.get("decision") != "TASK_CREATION_ROUTE_BLOCKED_AWAITING_EVIDENCE":
        errors.append(f"{label}: decision must block task creation route awaiting evidence")
    if decision.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: decision solver_outcome must be AwaitingEvidence")
    if decision.get("proof_state") != "Unknown":
        errors.append(f"{label}: decision proof_state must be Unknown")
    blocked_refs = {str(ref) for ref in decision.get("blocked_reason_refs", [])}
    missing_blockers = sorted(set(REQUIRED_BLOCKED_REFS) - blocked_refs)
    if missing_blockers:
        errors.append(f"{label}: missing blocked_reason_refs: {', '.join(missing_blockers)}")
    next_refs = {str(ref) for ref in decision.get("next_required_evidence_refs", [])}
    missing_next_refs = sorted(set(REQUIRED_MISSING_EVIDENCE_REFS) - next_refs)
    if missing_next_refs:
        errors.append(f"{label}: missing next_required_evidence_refs: {', '.join(missing_next_refs)}")


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
    for phrase in (
        "approved branch workspace creation preflight",
        "task creation admission",
        "mutation endpoints",
        "runtime writes",
        "receipt append",
        "terminal closure",
    ):
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, (*path, str(index)))


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
    write_task_creation_admission_preflight_validation(validation, args.output)
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
