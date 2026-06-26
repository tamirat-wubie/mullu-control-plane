#!/usr/bin/env python3
"""Validate Component Harness evidence post-merge audits.

Purpose: prove component evidence post-merge audits are schema-valid,
runtime-aligned, source-bound, and non-authorizing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_evidence_postmerge_audit.schema.json,
examples/component_evidence_postmerge_audit.foundation.json, request queue
validation, submission intake validation, and scripts.validate_schemas.
Invariants:
  - The example payload equals the runtime projection.
  - The audit cannot accept or reject evidence.
  - Authority, promotion, execution, mutation, and terminal closure stay false.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for import_root in (REPO_ROOT, MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from mcoi_runtime.app.component_evidence_postmerge_audit import (  # noqa: E402
    REQUIRED_VALIDATOR_REFS,
    build_component_evidence_postmerge_audit,
)
from scripts.validate_component_evidence_request_queue import validate_component_evidence_request_queue  # noqa: E402
from scripts.validate_component_evidence_submission_intake import (  # noqa: E402
    validate_component_evidence_submission_intake,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_evidence_postmerge_audit.schema.json"
DEFAULT_EXAMPLE = REPO_ROOT / "examples" / "component_evidence_postmerge_audit.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_evidence_postmerge_audit_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_evidence_postmerge_audit_validator": "python scripts/validate_component_evidence_postmerge_audit.py",
    "component_evidence_postmerge_audit_tests": (
        "python -m pytest tests/test_validate_component_evidence_postmerge_audit.py -q"
    ),
}


@dataclass(frozen=True, slots=True)
class ComponentEvidencePostmergeAuditValidation:
    """Validation result for component evidence post-merge audits."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_path: str
    request_slot_count: int
    audit_finding_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_evidence_postmerge_audit(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_path: Path = DEFAULT_EXAMPLE,
) -> ComponentEvidencePostmergeAuditValidation:
    """Validate audit schema, example, runtime projection, and invariants."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component evidence post-merge audit schema", errors)
    example = _load_json_object(example_path, "component evidence post-merge audit example", errors)

    for label, validation in (
        ("component evidence request queue", validate_component_evidence_request_queue()),
        ("component evidence submission intake", validate_component_evidence_submission_intake()),
    ):
        if not validation.ok:
            errors.extend(f"{label} validation failed: {error}" for error in validation.errors)

    runtime_projection = build_component_evidence_postmerge_audit()
    if schema and example:
        errors.extend(f"{_path_label(example_path)}: {error}" for error in _validate_schema_instance(schema, example))
        if example != runtime_projection:
            errors.append(f"{_path_label(example_path)}: example does not match runtime projection")
        _validate_audit_semantics(example, errors, _path_label(example_path))

    summary = example.get("summary", {}) if isinstance(example, dict) else {}
    return ComponentEvidencePostmergeAuditValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_path=_path_label(example_path),
        request_slot_count=int(summary.get("request_slot_count", 0)) if isinstance(summary, dict) else 0,
        audit_finding_count=int(summary.get("audit_finding_count", 0)) if isinstance(summary, dict) else 0,
    )


def write_component_evidence_postmerge_audit_validation(
    validation: ComponentEvidencePostmergeAuditValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic post-merge audit validation result."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _validate_audit_semantics(audit: dict[str, Any], errors: list[str], label: str) -> None:
    for flag_name in (
        "audit_is_not_execution_authority",
        "audit_is_not_evidence_submission",
        "audit_is_not_evidence_acceptance",
        "audit_is_not_evidence_rejection",
        "audit_is_not_authority_grant",
        "audit_is_not_promotion_approval",
        "audit_is_not_terminal_closure",
    ):
        if audit.get(flag_name) is not True:
            errors.append(f"{label}: {flag_name} must be true")
    for flag_name in (
        "live_execution_enabled",
        "live_connector_send_enabled",
        "can_execute",
        "can_mutate",
        "can_call_connector",
        "can_claim_terminal_closure",
        "evidence_accepted",
        "evidence_rejected",
        "authority_granted",
        "promotion_approved",
        "terminal_closure_allowed",
    ):
        if audit.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")

    findings = audit.get("audit_findings")
    if not isinstance(findings, list) or not findings:
        errors.append(f"{label}: audit_findings must be a non-empty list")
        return
    _validate_summary(audit, findings, errors, label)
    _validate_blockers(audit, errors, label)
    _validate_validators(audit, errors, label)
    for finding in findings:
        if not isinstance(finding, dict):
            errors.append(f"{label}: audit finding entries must be objects")
            continue
        _validate_finding(finding, errors, label)


def _validate_summary(
    audit: dict[str, Any],
    findings: list[Any],
    errors: list[str],
    label: str,
) -> None:
    summary = audit.get("summary")
    blockers = audit.get("postmerge_blockers")
    if not isinstance(summary, dict):
        errors.append(f"{label}: summary must be an object")
        return
    if not isinstance(blockers, list):
        errors.append(f"{label}: postmerge_blockers must be a list")
        return
    expected_counts = {
        "request_slot_count": 7,
        "intake_slot_count": 7,
        "submitted_slot_count": 0,
        "submitted_evidence_ref_count": 0,
        "accepted_evidence_count": 0,
        "rejected_evidence_count": 0,
        "authority_grant_count": 0,
        "terminal_closure_allowed_count": 0,
        "audit_finding_count": len([finding for finding in findings if isinstance(finding, dict)]),
        "postmerge_blocker_count": len(_string_list(blockers)),
    }
    for field_name, expected_value in expected_counts.items():
        if summary.get(field_name) != expected_value:
            errors.append(f"{label}: summary.{field_name} must be {expected_value}")


def _validate_finding(finding: dict[str, Any], errors: list[str], label: str) -> None:
    finding_id = str(finding.get("finding_id", ""))
    if finding.get("proof_state") != "Pass":
        errors.append(f"{label}: finding {finding_id} proof_state must be Pass")
    if finding.get("outcome") != "SolvedVerified":
        errors.append(f"{label}: finding {finding_id} outcome must be SolvedVerified")
    if not isinstance(finding.get("statement"), str) or not finding["statement"]:
        errors.append(f"{label}: finding {finding_id} statement must be non-empty text")
    if not _string_list(finding.get("evidence_refs")):
        errors.append(f"{label}: finding {finding_id} must carry evidence refs")
    validator_refs = set(_string_list(finding.get("required_validator_refs")))
    for validator_ref in REQUIRED_VALIDATOR_REFS:
        if validator_ref not in validator_refs:
            errors.append(f"{label}: finding {finding_id} must require {validator_ref}")


def _validate_blockers(audit: dict[str, Any], errors: list[str], label: str) -> None:
    blockers = set(_string_list(audit.get("postmerge_blockers")))
    for blocker in (
        "submitted_evidence_not_verified",
        "evidence_acceptance_not_performed",
        "authority_grant_not_performed",
        "terminal_closure_denied",
    ):
        if blocker not in blockers:
            errors.append(f"{label}: postmerge_blockers must include {blocker}")


def _validate_validators(audit: dict[str, Any], errors: list[str], label: str) -> None:
    validators = audit.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id = {
        str(validator.get("validator_id", "")): validator
        for validator in validators
        if isinstance(validator, dict)
    }
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    if not all(isinstance(item, str) and item for item in value):
        return []
    return value


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse component evidence post-merge audit validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness evidence post-merge audit.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", default=str(DEFAULT_EXAMPLE))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for component evidence post-merge audit validation."""

    args = parse_args(argv)
    validation = validate_component_evidence_postmerge_audit(
        schema_path=Path(args.schema),
        example_path=Path(args.example),
    )
    write_component_evidence_postmerge_audit_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT EVIDENCE POSTMERGE AUDIT VALID")
    else:
        print(f"COMPONENT EVIDENCE POSTMERGE AUDIT INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
