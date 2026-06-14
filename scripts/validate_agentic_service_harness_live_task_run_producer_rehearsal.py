#!/usr/bin/env python3
"""Validate Agentic Service Harness local task/run producer rehearsal.

Purpose: prove the validated producer evidence fixture can be projected into a
local dry-run report before any live producer execution path, UI, mutation
endpoint, external adapter, branch write, pull-request creation, deployment,
DNS mutation, secret mutation, or destructive authority is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_live_task_run_producer and
scripts.validate_agentic_service_harness_live_task_run_producer_evidence.
Invariants:
  - Rehearsal output is local-only, read-only, and non-terminal.
  - Effect-bearing authority remains explicitly denied.
  - Credential-like values, mutation routes, and live implementation claims
    fail closed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.agentic_service_harness_live_task_run_producer import (  # noqa: E402
    DEFAULT_EVIDENCE_FIXTURE_PATH,
    DEFAULT_EVIDENCE_FIXTURE_REF,
    REHEARSAL_REPORT_ID,
    project_evidence_fixture_to_rehearsal,
)
from scripts.validate_agentic_service_harness_live_task_run_producer_evidence import (  # noqa: E402
    DEFAULT_EVIDENCE_DOC,
    DEFAULT_SCHEMA,
    validate_live_task_run_producer_evidence,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_live_task_run_producer_rehearsal_validation.json"
)
REQUIRED_TOP_LEVEL_FIELDS = (
    "report_id",
    "schema_version",
    "source_fixture_ref",
    "source_fixture_id",
    "generated_at",
    "producer_state",
    "solver_outcome",
    "planning_only",
    "local_rehearsal_only",
    "live_producer_implemented",
    "report_is_not_terminal_closure",
    "terminal_closure",
    "scope",
    "task_projection",
    "run_projection",
    "approval_projection",
    "receipt_projection",
    "sandbox_projection",
    "rollback_projection",
    "status_publication_projection",
    "authority_denials",
    "effect_boundary",
    "validators",
    "next_action",
)
FALSE_EFFECT_FLAGS = (
    "ui_created",
    "mutation_endpoints_admitted",
    "external_adapter_integrated",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
)
FALSE_RUN_FLAGS = (
    "executes_adapter",
    "creates_branch",
    "opens_pull_request",
    "permits_external_effect",
)
ALLOWED_SECRET_KEYS = {
    "secret_mutation_enabled",
    "secret_redaction_required",
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
FORBIDDEN_MUTATION_ROUTE = re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class LiveTaskRunProducerRehearsalValidation:
    """Validation report for the local task/run producer rehearsal."""

    ok: bool
    errors: tuple[str, ...]
    fixture_path: str
    report_id: str
    producer_state: str
    effect_denial_count: int
    validator_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_task_run_producer_rehearsal(
    *,
    fixture_path: Path = DEFAULT_EVIDENCE_FIXTURE_PATH,
    fixture_ref: str = DEFAULT_EVIDENCE_FIXTURE_REF,
) -> tuple[LiveTaskRunProducerRehearsalValidation, dict[str, Any]]:
    """Validate the local dry-run producer report generated from one fixture."""
    errors: list[str] = []
    source_validation = validate_live_task_run_producer_evidence(
        evidence_doc_path=DEFAULT_EVIDENCE_DOC,
        schema_path=DEFAULT_SCHEMA,
        fixture_path=fixture_path,
    )
    errors.extend(f"source evidence: {error}" for error in source_validation.errors)
    fixture = _load_json_object(fixture_path, errors)
    report: dict[str, Any] = {}
    if fixture:
        try:
            report = project_evidence_fixture_to_rehearsal(fixture, fixture_ref)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"rehearsal projection failed: {exc}")
    if report:
        _validate_rehearsal_report(report, fixture, errors)

    validation = LiveTaskRunProducerRehearsalValidation(
        ok=not errors,
        errors=tuple(errors),
        fixture_path=_path_label(fixture_path),
        report_id=str(report.get("report_id", "")),
        producer_state=str(report.get("producer_state", "")),
        effect_denial_count=len(FALSE_EFFECT_FLAGS),
        validator_count=len(report.get("validators", ())) if isinstance(report.get("validators"), list) else 0,
    )
    return validation, report


def write_live_task_run_producer_rehearsal_validation(
    validation: LiveTaskRunProducerRehearsalValidation,
    report: Mapping[str, Any],
    output_path: Path = DEFAULT_OUTPUT,
) -> Path:
    """Write a local validation receipt containing the in-memory rehearsal report."""
    payload = validation.as_dict()
    payload["rehearsal_report"] = dict(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_rehearsal_report(
    report: Mapping[str, Any],
    fixture: Mapping[str, Any],
    errors: list[str],
) -> None:
    for field_name in REQUIRED_TOP_LEVEL_FIELDS:
        if field_name not in report:
            errors.append(f"rehearsal missing field: {field_name}")
    if report.get("report_id") != REHEARSAL_REPORT_ID:
        errors.append("rehearsal report_id mismatch")
    if report.get("source_fixture_id") != fixture.get("fixture_id"):
        errors.append("rehearsal source fixture id mismatch")
    if report.get("producer_state") != "local_dry_run_ready":
        errors.append("rehearsal producer_state must be local_dry_run_ready")
    if report.get("solver_outcome") != "AwaitingEvidence":
        errors.append("rehearsal solver_outcome must be AwaitingEvidence")
    for field_name, expected_value in (
        ("planning_only", True),
        ("local_rehearsal_only", True),
        ("live_producer_implemented", False),
        ("report_is_not_terminal_closure", True),
        ("terminal_closure", False),
    ):
        if report.get(field_name) is not expected_value:
            errors.append(f"rehearsal {field_name} must be {str(expected_value).lower()}")

    _validate_scope(report, fixture, errors)
    _validate_denials(report, errors)
    _validate_projection_surfaces(report, fixture, errors)
    _validate_secret_surface(report, errors)
    _validate_no_mutation_routes(report, errors)


def _validate_scope(
    report: Mapping[str, Any],
    fixture: Mapping[str, Any],
    errors: list[str],
) -> None:
    scope = _mapping(report.get("scope"))
    fixture_scope = _mapping(fixture.get("scope"))
    if not scope:
        errors.append("rehearsal scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append("rehearsal scope.read_only must be true")
    for field_name in ("tenant_id", "organization_id", "project_id", "repository_connection_id"):
        if scope.get(field_name) != fixture_scope.get(field_name):
            errors.append(f"rehearsal scope {field_name} must match fixture")


def _validate_denials(report: Mapping[str, Any], errors: list[str]) -> None:
    authority_denials = _mapping(report.get("authority_denials"))
    effect_boundary = _mapping(report.get("effect_boundary"))
    if not authority_denials:
        errors.append("rehearsal authority_denials must be an object")
    if not effect_boundary:
        errors.append("rehearsal effect_boundary must be an object")
    for flag_name in FALSE_EFFECT_FLAGS:
        if authority_denials and authority_denials.get(flag_name) is not False:
            errors.append(f"rehearsal authority_denials.{flag_name} must be false")
        if effect_boundary and effect_boundary.get(flag_name) is not False:
            errors.append(f"rehearsal effect_boundary.{flag_name} must be false")
    if effect_boundary and effect_boundary.get("runtime_state_written") is not False:
        errors.append("rehearsal effect_boundary.runtime_state_written must be false")
    if effect_boundary and effect_boundary.get("network_policy") != "none":
        errors.append("rehearsal effect_boundary.network_policy must be none")


def _validate_projection_surfaces(
    report: Mapping[str, Any],
    fixture: Mapping[str, Any],
    errors: list[str],
) -> None:
    task = _mapping(report.get("task_projection"))
    run = _mapping(report.get("run_projection"))
    approval = _mapping(report.get("approval_projection"))
    receipt = _mapping(report.get("receipt_projection"))
    sandbox = _mapping(report.get("sandbox_projection"))
    rollback = _mapping(report.get("rollback_projection"))
    status_publication = _mapping(report.get("status_publication_projection"))
    fixture_task = _mapping(fixture.get("task_intake_evidence"))
    fixture_run = _mapping(fixture.get("run_projection_evidence"))

    if task.get("task_id") != fixture_task.get("task_id"):
        errors.append("rehearsal task id must match fixture")
    if task.get("append_only") is not True or task.get("read_only") is not True:
        errors.append("rehearsal task projection must be append-only and read-only")
    if run.get("run_id") != fixture_run.get("run_id"):
        errors.append("rehearsal run id must match fixture")
    for flag_name in FALSE_RUN_FLAGS:
        if run.get(flag_name) is not False:
            errors.append(f"rehearsal run_projection.{flag_name} must be false")
    if approval.get("self_approval_allowed") is not False:
        errors.append("rehearsal approval self_approval_allowed must be false")
    if approval.get("permits_external_effect") is not False:
        errors.append("rehearsal approval permits_external_effect must be false")
    if receipt.get("receipt_is_not_terminal_closure") is not True:
        errors.append("rehearsal receipt must not claim terminal closure")
    if receipt.get("terminal_closure") is not False:
        errors.append("rehearsal receipt terminal_closure must be false")
    if receipt.get("secret_values_serialized") is not False:
        errors.append("rehearsal receipt secret_values_serialized must be false")
    if sandbox.get("network_policy") != "none":
        errors.append("rehearsal sandbox network_policy must be none")
    if sandbox.get("secret_redaction_required") is not True:
        errors.append("rehearsal sandbox secret redaction must be required")
    if rollback.get("rollback_boundary") != "local_fixture_only":
        errors.append("rehearsal rollback boundary must remain local_fixture_only")
    if status_publication.get("read_only") is not True:
        errors.append("rehearsal status publication must be read-only")
    if status_publication.get("no_terminal_closure_claim") is not True:
        errors.append("rehearsal status publication must deny terminal closure")


def _validate_secret_surface(payload: Any, errors: list[str]) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"rehearsal forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"rehearsal credential-like value at {path}")
                    break


def _validate_no_mutation_routes(payload: Any, errors: list[str]) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_MUTATION_ROUTE.search(value):
            errors.append(f"rehearsal mutation route string at {path}")


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"fixture JSON load failed: {_path_label(path)}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"fixture JSON root must be an object: {_path_label(path)}")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            child_path = f"{path}[{index}]"
            yield child_path, f"[{index}]", item
            yield from _walk_json(item, child_path)


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield path, payload


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_EVIDENCE_FIXTURE_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the local task/run producer rehearsal validator."""
    args = build_arg_parser().parse_args(argv)
    fixture_ref = _path_label(args.fixture)
    validation, report = validate_live_task_run_producer_rehearsal(
        fixture_path=args.fixture,
        fixture_ref=fixture_ref,
    )
    if args.output is not None:
        write_live_task_run_producer_rehearsal_validation(validation, report, args.output)
    if args.json:
        payload = validation.as_dict()
        payload["rehearsal_report"] = report
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE TASK RUN PRODUCER REHEARSAL VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE TASK RUN PRODUCER REHEARSAL INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
