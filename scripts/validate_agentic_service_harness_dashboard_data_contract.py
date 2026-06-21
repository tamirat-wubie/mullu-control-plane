#!/usr/bin/env python3
"""Validate Agentic Service Harness dashboard data contract.

Purpose: prove future dashboard data remains a read-only composition contract
before any UI, route, mutation endpoint, provider mutation, task creation,
adapter execution, branch write, pull-request creation, secret serialization,
or terminal closure authority is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_dashboard_data_contract.schema.json,
examples/agentic_service_harness_dashboard_data_contract.foundation.json, and
scripts.validate_schemas.
Invariants:
  - Every expected dashboard section is present exactly once.
  - Sections are display-only, read-only, and have no action controls.
  - UI, route, mutation, adapter, branch, PR, secret, and closure authorities
    remain false.
  - Missing hard evidence remains AwaitingEvidence.
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


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_dashboard_data_contract.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_dashboard_data_contract.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_dashboard_data_contract_validation.json"
)
EXPECTED_SECTIONS = (
    "account_summary",
    "repository_connection",
    "agent_task_intake",
    "run_status",
    "approval_gate",
    "evidence_receipts",
    "loop_readiness",
    "result_summary",
)
REQUIRED_SOURCE_REFS = (
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
    "schemas/agentic_service_harness_read_models.schema.json",
    "examples/agentic_service_harness_read_models.foundation.json",
    "schemas/agentic_service_harness_read_only_repo_task_intake.schema.json",
    "schemas/agentic_service_harness_actual_file_change_summary_receipt.schema.json",
    "docs/FOUNDATION_MODE.md",
)
REQUIRED_FALSE_FLAGS = (
    "ui_created",
    "routes_created",
    "route_created",
    "mutation_endpoints_admitted",
    "mutation_endpoint_admitted",
    "task_creation_route_admitted",
    "provider_connection_mutation",
    "external_adapter_integrated",
    "default_high_risk_authority",
    "secret_values_serialized",
    "terminal_closure_granted",
    "mutation_controls_present",
    "action_buttons_enabled",
    "ui_build_admitted",
    "route_build_admitted",
    "task_creation_admitted",
    "code_execution",
    "external_adapter_execution",
    "filesystem_write",
    "branch_creation",
    "pull_request_creation",
    "merge",
    "deployment",
    "dns_mutation",
    "secret_serialization",
    "destructive_operation",
    "terminal_closure",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "display_only",
    "requires_receipt_read_model",
    "requires_evidence_bundle_read_model",
    "requires_approval_read_model",
    "requires_loop_status_read_model",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {
    "secret_serialization",
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
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)
MUTATION_DECORATOR_PATTERN = re.compile(r"@\w+\.(post|put|patch|delete)\(", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DashboardDataContractValidation:
    """Schema and semantic validation report for dashboard data contracts."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    section_count: int

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
    schema = _load_json_object(schema_path, "dashboard data contract schema", errors)
    examples: list[dict[str, Any]] = []

    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"dashboard data contract example {_path_label(example_path)}",
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

    return DashboardDataContractValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        section_count=len(EXPECTED_SECTIONS),
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


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _validate_required_source_refs(payload, errors, label)
    _validate_sections(payload, errors, label)
    _validate_readiness_gates(payload, errors, label)
    _validate_non_goals(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_required_source_refs(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_sections(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    sections = payload.get("dashboard_sections")
    if not isinstance(sections, list):
        errors.append(f"{label}: dashboard_sections must be a list")
        return
    section_ids = [section.get("section_id") for section in sections if isinstance(section, dict)]
    if tuple(section_ids) != EXPECTED_SECTIONS:
        errors.append(
            f"{label}: dashboard_sections must match ordered sections {', '.join(EXPECTED_SECTIONS)}"
        )
    if len(set(section_ids)) != len(section_ids):
        errors.append(f"{label}: dashboard_sections must not contain duplicate section_id values")
    for section in sections:
        if not isinstance(section, dict):
            errors.append(f"{label}: each dashboard section must be an object")
            continue
        section_id = str(section.get("section_id"))
        if not section.get("source_refs"):
            errors.append(f"{label}: {section_id} must declare source_refs")
        if not section.get("required_fields"):
            errors.append(f"{label}: {section_id} must declare required_fields")
        if section.get("display_only") is not True:
            errors.append(f"{label}: {section_id}.display_only must be true")
        if section.get("read_only") is not True:
            errors.append(f"{label}: {section_id}.read_only must be true")
        if section.get("mutation_controls_present") is not False:
            errors.append(f"{label}: {section_id}.mutation_controls_present must be false")
        if section.get("action_buttons_enabled") is not False:
            errors.append(f"{label}: {section_id}.action_buttons_enabled must be false")


def _validate_readiness_gates(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = payload.get("readiness_gates")
    if not isinstance(gates, dict):
        errors.append(f"{label}: readiness_gates must be an object")
        return
    if gates.get("missing_evidence_policy") != "AwaitingEvidence":
        errors.append(f"{label}: readiness_gates.missing_evidence_policy must be AwaitingEvidence")


def _validate_non_goals(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    non_goals = payload.get("non_goals")
    if not isinstance(non_goals, list):
        errors.append(f"{label}: non_goals must be a list")
        return
    required = {
        "Dashboard UI implementation",
        "Route implementation",
        "Mutation endpoint",
        "Task creation endpoint",
        "Live adapter execution",
        "Terminal closure",
    }
    missing = sorted(required - {str(non_goal) for non_goal in non_goals})
    if missing:
        errors.append(f"{label}: missing non_goals: {', '.join(missing)}")


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
        if not isinstance(value, str):
            continue
        if MUTATION_ROUTE_PATTERN.search(value) or MUTATION_DECORATOR_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    for required_phrase in ("Receipt", "EvidenceBundle", "before any dashboard UI"):
        if required_phrase not in next_action:
            errors.append(f"{label}: next_action must mention {required_phrase}")


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
    """Run the dashboard data contract validator."""

    args = build_arg_parser().parse_args(argv)
    validation = validate_agentic_service_harness_dashboard_data_contract(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    write_dashboard_data_contract_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS DASHBOARD DATA CONTRACT VALID")
    else:
        print("AGENTIC SERVICE HARNESS DASHBOARD DATA CONTRACT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
