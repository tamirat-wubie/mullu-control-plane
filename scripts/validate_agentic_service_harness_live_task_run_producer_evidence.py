#!/usr/bin/env python3
"""Validate Agentic Service Harness live task/run producer evidence contract.

Purpose: prove the future live producer evidence boundary is explicit before
any producer implementation, UI, mutation endpoint, external adapter, branch
write, pull-request creation, deployment, DNS, secret, or destructive authority
is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_LIVE_TASK_RUN_PRODUCER_EVIDENCE.md,
schemas/agentic_service_harness_live_task_run_producer_evidence.schema.json,
and examples/agentic_service_harness_live_task_run_producer_evidence.local.json.
Invariants:
  - Evidence surfaces and guards are explicit.
  - Hard false flags deny effect-bearing authority.
  - Mutation routes, route decorators, and implementation claims fail closed.
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


DEFAULT_EVIDENCE_DOC = REPO_ROOT / "MULLUSI_AGENTIC_SERVICE_HARNESS_LIVE_TASK_RUN_PRODUCER_EVIDENCE.md"
DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_live_task_run_producer_evidence.schema.json"
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "agentic_service_harness_live_task_run_producer_evidence.local.json"

REQUIRED_SECTIONS = (
    "# Mullusi Agentic Service Harness Live Task/Run Producer Evidence",
    "## Objective",
    "## Scope",
    "## Producer State Boundary",
    "## Required Guards",
    "## Forbidden Authority",
    "## Acceptance Gates",
    "## Next Implementation Boundary",
)
REQUIRED_EVIDENCE_SURFACES = (
    "TaskIntakeEvidence",
    "RunProjectionEvidence",
    "ApprovalEvidence",
    "ReceiptEvidence",
    "SandboxEvidence",
    "RollbackEvidence",
    "StatusPublicationEvidence",
)
REQUIRED_FALSE_FLAGS = (
    "planning_only=true",
    "live_producer_implemented=false",
    "ui_created=false",
    "mutation_endpoints_admitted=false",
    "external_adapter_integrated=false",
    "branch_write_enabled=false",
    "pull_request_creation_enabled=false",
    "deployment_enabled=false",
    "dns_mutation_enabled=false",
    "secret_mutation_enabled=false",
    "destructive_operation_enabled=false",
    "terminal_closure=false",
)
REQUIRED_GUARD_TERMS = (
    "Tenant and project scope",
    "append-only",
    "refs or hashes",
    "Secret values are never serialized",
    "External adapter execution remains blocked",
    "approval-gated and disabled by default",
    "High-risk actions remain blocked by default",
    "read-only and non-terminal",
    "Rollback and cleanup refs",
    "AwaitingEvidence",
)
REQUIRED_VALIDATORS = (
    "python scripts/validate_agentic_service_harness_contract.py --strict",
    "python scripts/validate_agentic_service_harness_read_models.py --strict",
    "python scripts/validate_agentic_service_harness_read_only_status_route.py",
    "python scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py",
    "python scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py",
    "python scripts/validate_agentic_service_harness_live_producer_admission_gate.py",
    "python scripts/validate_agentic_service_harness_live_producer_witness_requirements.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_request.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_template.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.py",
    "python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record_path.py",
    "python scripts/validate_agentic_service_harness_live_producer_effect_receipt_preflight.py",
    "python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight.py",
    "python scripts/validate_agentic_service_harness_live_producer_secret_handoff_preflight.py",
    "python scripts/validate_agentic_service_harness_live_producer_rollback_proof_preflight.py",
    "python scripts/validate_agentic_service_harness_live_producer_evidence_packet_intake.py",
    "python scripts/validate_agentic_service_harness_live_producer_effect_receipt_packet.py",
    "python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_packet.py",
    "python scripts/validate_agentic_service_harness_live_producer_secret_handoff_packet.py",
    "python scripts/validate_agentic_service_harness_live_producer_rollback_proof_packet.py",
    "python scripts/validate_agentic_service_harness_authority_transitions.py",
)
REQUIRED_FIXTURE_SURFACES = (
    "task_intake_evidence",
    "run_projection_evidence",
    "approval_evidence",
    "receipt_evidence",
    "sandbox_evidence",
    "rollback_evidence",
    "status_publication_evidence",
)
FIXTURE_AUTHORITY_FALSE_FLAGS = (
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
FORBIDDEN_PATTERNS = (
    ("mutation_route", re.compile(r"\b(?:POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)),
    ("fastapi_mutation_decorator", re.compile(r"@\w+\.(?:post|put|patch|delete)\(", re.IGNORECASE)),
    ("live_producer_implementation_claim", re.compile(r"\blive_producer_implemented=true\b", re.IGNORECASE)),
    ("ui_enablement", re.compile(r"\bui_created=true\b", re.IGNORECASE)),
    ("mutation_enablement", re.compile(r"\bmutation_endpoints_admitted=true\b", re.IGNORECASE)),
    ("adapter_enablement", re.compile(r"\bexternal_adapter_integrated=true\b", re.IGNORECASE)),
    ("branch_write_enablement", re.compile(r"\bbranch_write_enabled=true\b", re.IGNORECASE)),
    ("pull_request_enablement", re.compile(r"\bpull_request_creation_enabled=true\b", re.IGNORECASE)),
    ("deployment_enablement", re.compile(r"\bdeployment_enabled=true\b", re.IGNORECASE)),
    ("dns_enablement", re.compile(r"\bdns_mutation_enabled=true\b", re.IGNORECASE)),
    ("secret_enablement", re.compile(r"\bsecret_mutation_enabled=true\b", re.IGNORECASE)),
    ("destructive_enablement", re.compile(r"\bdestructive_operation_enabled=true\b", re.IGNORECASE)),
)


@dataclass(frozen=True, slots=True)
class LiveTaskRunProducerEvidenceValidation:
    """Deterministic validation result for the live producer evidence contract."""

    ok: bool
    errors: tuple[str, ...]
    evidence_doc_path: str
    schema_path: str
    fixture_path: str
    required_section_count: int
    required_evidence_surface_count: int
    required_false_flag_count: int
    required_validator_count: int

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_live_task_run_producer_evidence(
    evidence_doc_path: Path = DEFAULT_EVIDENCE_DOC,
    schema_path: Path = DEFAULT_SCHEMA,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> LiveTaskRunProducerEvidenceValidation:
    """Validate that the live producer evidence contract is complete and bounded."""
    errors: list[str] = []
    try:
        evidence_text = evidence_doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        return LiveTaskRunProducerEvidenceValidation(
            ok=False,
            errors=(f"evidence doc load failed: {exc}",),
            evidence_doc_path=_path_label(evidence_doc_path),
            schema_path=_path_label(schema_path),
            fixture_path=_path_label(fixture_path),
            required_section_count=0,
            required_evidence_surface_count=0,
            required_false_flag_count=0,
            required_validator_count=0,
        )

    _require_all(evidence_text, REQUIRED_SECTIONS, "section", errors)
    _require_all(evidence_text, REQUIRED_EVIDENCE_SURFACES, "evidence_surface", errors)
    _require_all(evidence_text, REQUIRED_FALSE_FLAGS, "false_flag", errors)
    _require_all(evidence_text, REQUIRED_GUARD_TERMS, "guard_term", errors)
    _require_all(evidence_text, REQUIRED_VALIDATORS, "validator", errors)
    _validate_forbidden_patterns(evidence_text, errors)
    _validate_state_order(evidence_text, errors)

    schema = _load_json_object(schema_path, "live producer evidence schema", errors)
    fixture = _load_json_object(fixture_path, "live producer evidence fixture", errors)
    if schema and fixture:
        errors.extend(
            f"{_path_label(fixture_path)}: {error}"
            for error in _validate_schema_instance(schema, fixture)
        )
        _validate_fixture_semantics(fixture, errors, _path_label(fixture_path))

    return LiveTaskRunProducerEvidenceValidation(
        ok=not errors,
        errors=tuple(errors),
        evidence_doc_path=_path_label(evidence_doc_path),
        schema_path=_path_label(schema_path),
        fixture_path=_path_label(fixture_path),
        required_section_count=len(REQUIRED_SECTIONS),
        required_evidence_surface_count=len(REQUIRED_EVIDENCE_SURFACES),
        required_false_flag_count=len(REQUIRED_FALSE_FLAGS),
        required_validator_count=len(REQUIRED_VALIDATORS),
    )


def _require_all(
    evidence_text: str,
    required_values: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    for required_value in required_values:
        if required_value not in evidence_text:
            errors.append(f"missing {label}: {required_value}")


def _validate_forbidden_patterns(evidence_text: str, errors: list[str]) -> None:
    for pattern_name, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(evidence_text):
            errors.append(f"forbidden {pattern_name}")


def _validate_state_order(evidence_text: str, errors: list[str]) -> None:
    state_markers = (
        "producer_contract_defined",
        "evidence_fixture_ready",
        "local_dry_run_ready",
        "awaiting_approval_for_effects",
        "blocked_high_risk",
    )
    positions: list[int] = []
    for marker in state_markers:
        position = evidence_text.find(marker)
        if position == -1:
            errors.append(f"missing state marker: {marker}")
        else:
            positions.append(position)
    if positions and positions != sorted(positions):
        errors.append("producer state sequence is not ordered")


def _validate_fixture_semantics(
    fixture: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _require_fixture_surfaces(fixture, errors, label)
    _validate_fixture_scope(fixture, errors, label)
    _validate_fixture_authority_denials(fixture, errors, label)
    _validate_fixture_terminal_boundary(fixture, errors, label)
    _validate_fixture_refs(fixture, errors, label)
    _validate_fixture_secret_surface(fixture, errors, label)
    _validate_fixture_no_mutation_routes(fixture, errors, label)


def _require_fixture_surfaces(
    fixture: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for surface in REQUIRED_FIXTURE_SURFACES:
        if not isinstance(fixture.get(surface), Mapping):
            errors.append(f"{label}: missing fixture surface {surface}")


def _validate_fixture_scope(
    fixture: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = fixture.get("scope")
    task = fixture.get("task_intake_evidence")
    if not isinstance(scope, Mapping):
        errors.append(f"{label}: scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append(f"{label}: scope.read_only must be true")
    if isinstance(task, Mapping):
        if task.get("tenant_id") != scope.get("tenant_id"):
            errors.append(f"{label}: task tenant_id must match scope")
        if task.get("project_id") != scope.get("project_id"):
            errors.append(f"{label}: task project_id must match scope")


def _validate_fixture_authority_denials(
    fixture: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if fixture.get("planning_only") is not True:
        errors.append(f"{label}: planning_only must be true")
    if fixture.get("live_producer_implemented") is not False:
        errors.append(f"{label}: live_producer_implemented must be false")
    authority_denials = fixture.get("authority_denials")
    if not isinstance(authority_denials, Mapping):
        errors.append(f"{label}: authority_denials must be an object")
        return
    for flag_name in FIXTURE_AUTHORITY_FALSE_FLAGS:
        if authority_denials.get(flag_name) is not False:
            errors.append(f"{label}: authority_denials.{flag_name} must be false")


def _validate_fixture_terminal_boundary(
    fixture: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if fixture.get("report_is_not_terminal_closure") is not True:
        errors.append(f"{label}: report_is_not_terminal_closure must be true")
    if fixture.get("terminal_closure") is not False:
        errors.append(f"{label}: terminal_closure must be false")
    receipt = fixture.get("receipt_evidence")
    if isinstance(receipt, Mapping):
        if receipt.get("receipt_is_not_terminal_closure") is not True:
            errors.append(f"{label}: receipt must not claim terminal closure")
        if receipt.get("secret_values_serialized") is not False:
            errors.append(f"{label}: receipt secret_values_serialized must be false")


def _validate_fixture_refs(
    fixture: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    task = fixture.get("task_intake_evidence")
    run = fixture.get("run_projection_evidence")
    status_publication = fixture.get("status_publication_evidence")
    sandbox = fixture.get("sandbox_evidence")
    if isinstance(task, Mapping) and not task.get("policy_refs"):
        errors.append(f"{label}: task policy_refs must not be empty")
    if isinstance(run, Mapping):
        for ref_field in ("approval_refs", "receipt_refs", "evidence_bundle_refs"):
            if not run.get(ref_field):
                errors.append(f"{label}: run {ref_field} must not be empty")
    if isinstance(status_publication, Mapping):
        if status_publication.get("read_only") is not True:
            errors.append(f"{label}: status publication must be read-only")
        if status_publication.get("no_terminal_closure_claim") is not True:
            errors.append(f"{label}: status publication must deny terminal closure")
        if not status_publication.get("validator_refs"):
            errors.append(f"{label}: status publication validator_refs must not be empty")
    if isinstance(sandbox, Mapping):
        if sandbox.get("network_policy") != "none":
            errors.append(f"{label}: sandbox network_policy must be none")
        if sandbox.get("secret_redaction_required") is not True:
            errors.append(f"{label}: sandbox must require secret redaction")


def _validate_fixture_secret_surface(
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


def _validate_fixture_no_mutation_routes(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_strings(payload):
        if FORBIDDEN_PATTERNS[0][1].search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (OSError, json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON load failed: {_path_label(path)}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object: {_path_label(path)}")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


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
    parser.add_argument("--evidence-doc", type=Path, default=DEFAULT_EVIDENCE_DOC)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the live task/run producer evidence validator."""
    args = build_arg_parser().parse_args(argv)
    validation = validate_live_task_run_producer_evidence(args.evidence_doc)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS LIVE TASK RUN PRODUCER EVIDENCE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS LIVE TASK RUN PRODUCER EVIDENCE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
