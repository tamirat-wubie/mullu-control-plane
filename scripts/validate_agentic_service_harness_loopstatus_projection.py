#!/usr/bin/env python3
"""Validate Agentic Service Harness LoopStatus projection.

Purpose: prove the harness LoopStatus projection binds to the holistic loop
read model while remaining read-only, projection-only, blocked, and
non-terminal.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_loopstatus_projection.schema.json,
examples/agentic_service_harness_loopstatus_projection.foundation.json,
scripts/report_holistic_loop_read_model.py, and scripts.validate_schemas.
Invariants:
  - LoopStatus projection identity matches the project scope.
  - Missing loop evidence and authority stay modeled as AwaitingEvidence.
  - Loop registration, status transition, runtime execution, dashboard UI,
    task creation routes, mutation endpoints, receipt append, secrets, and
    terminal closure are denied.
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


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_loopstatus_projection.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_loopstatus_projection.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_loopstatus_projection_validation.json"
REQUIRED_SOURCE_REFS = (
    "schemas/holistic_loop_read_model.schema.json",
    "scripts/report_holistic_loop_read_model.py",
    "scripts/validate_holistic_loop_read_model.py",
    "schemas/agentic_service_harness_read_models.schema.json",
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "examples/agentic_service_harness_receipt_evidence_read_models.foundation.json",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_FALSE_FLAGS = (
    "loop_registration_admitted",
    "status_transition_admitted",
    "runtime_execution_admitted",
    "secret_values_serialized",
    "terminal_closure_granted",
    "status_transition",
    "loop_registration",
    "runtime_execution",
    "terminal_closure",
    "dashboard_ui_admitted",
    "task_creation_route_admitted",
    "dashboard_ui",
    "task_creation_route",
    "mutation_endpoint",
    "receipt_store_append",
    "external_adapter_execution",
    "secret_serialization",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "projection_only",
    "dashboard_data_contract_closed",
    "receipt_evidence_read_models_closed",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
REQUIRED_BLOCKERS = (
    "blocked://holistic-loop-read-model/status-blocked",
    "blocked://loopstatus/source-loop-evidence-missing",
    "blocked://loopstatus/source-loop-authority-missing",
    "blocked://task-creation-route/not-admitted",
)
REQUIRED_TASK_PREFLIGHT_REFS = (
    "evidence://task-creation-admission-preflight",
    "approval://task-creation-route/not-collected",
    "policy://harness/task-creation-read-only-boundary",
)
ALLOWED_SECRET_KEYS = {
    "secret_values_serialized",
    "secret_serialization",
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
class LoopStatusProjectionValidation:
    """Schema and semantic validation report for LoopStatus projection."""

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


def validate_agentic_service_harness_loopstatus_projection(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> LoopStatusProjectionValidation:
    """Validate LoopStatus projection examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "LoopStatus projection schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"LoopStatus projection example {_path_label(example_path)}",
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
    return LoopStatusProjectionValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
    )


def write_loopstatus_projection_validation(
    validation: LoopStatusProjectionValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic LoopStatus projection validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _validate_required_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_loop_status(payload, errors, label)
    _validate_readiness_gates(payload, errors, label)
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
    projection = payload.get("loop_status_projection")
    if not isinstance(scope, Mapping) or not isinstance(projection, Mapping):
        errors.append(f"{label}: scope and loop_status_projection must be objects")
        return
    if scope.get("project_id") != projection.get("project_id"):
        errors.append(f"{label}: scope.project_id must match loop_status_projection.project_id")
    if scope.get("loop_status_ref") != projection.get("loop_status_ref"):
        errors.append(f"{label}: scope.loop_status_ref must match loop_status_projection.loop_status_ref")


def _validate_loop_status(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    projection = payload.get("loop_status_projection")
    if not isinstance(projection, Mapping):
        return
    if projection.get("source_report_id") != "holistic_loop_read_model":
        errors.append(f"{label}: source_report_id must be holistic_loop_read_model")
    if projection.get("source_report_status") == "blocked":
        if projection.get("projected_outcome") != "AwaitingEvidence":
            errors.append(f"{label}: blocked source report must project AwaitingEvidence")
        if projection.get("proof_state") != "Unknown":
            errors.append(f"{label}: blocked source report must keep proof_state Unknown")
    if projection.get("source_returned_count", 0) > projection.get("source_loop_count", 0):
        errors.append(f"{label}: source_returned_count cannot exceed source_loop_count")
    blockers = set(str(ref) for ref in projection.get("blocker_refs", []))
    missing_blockers = sorted(set(REQUIRED_BLOCKERS[:3]) - blockers)
    if missing_blockers:
        errors.append(f"{label}: missing loop blocker refs: {', '.join(missing_blockers)}")
    if not projection.get("evidence_refs"):
        errors.append(f"{label}: evidence_refs must not be empty")
    if not projection.get("authority_gap_refs"):
        errors.append(f"{label}: authority_gap_refs must not be empty")


def _validate_readiness_gates(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = payload.get("readiness_gates")
    if not isinstance(gates, Mapping):
        errors.append(f"{label}: readiness_gates must be an object")
        return
    if gates.get("missing_evidence_policy") != "AwaitingEvidence":
        errors.append(f"{label}: missing_evidence_policy must be AwaitingEvidence")
    missing_preflight = sorted(
        set(REQUIRED_TASK_PREFLIGHT_REFS)
        - {str(ref) for ref in gates.get("required_before_task_creation_refs", [])}
    )
    if missing_preflight:
        errors.append(f"{label}: missing required_before_task_creation_refs: {', '.join(missing_preflight)}")
    missing_blockers = sorted(
        set(REQUIRED_BLOCKERS[3:])
        - {str(ref) for ref in gates.get("blocked_reason_refs", [])}
    )
    if missing_blockers:
        errors.append(f"{label}: missing readiness blocked_reason_refs: {', '.join(missing_blockers)}")


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
    for phrase in ("task creation admission preflight", "LoopStatus", "Receipt", "EvidenceBundle", "non-terminal"):
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
    """Run the LoopStatus projection validator."""

    args = build_arg_parser().parse_args(argv)
    validation = validate_agentic_service_harness_loopstatus_projection(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    write_loopstatus_projection_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LOOPSTATUS PROJECTION VALID")
    else:
        print("AGENTIC SERVICE HARNESS LOOPSTATUS PROJECTION INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
