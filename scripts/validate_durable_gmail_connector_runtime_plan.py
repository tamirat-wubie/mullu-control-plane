#!/usr/bin/env python3
"""Validate the durable Gmail connector runtime planning boundary.

Purpose: verify that durable Gmail connector runtime work is requirement-bound,
release-bounded by provider-side witnesses, and free of serialized secret
values.
Governance scope: OAuth authority, least-privilege scope selection, secret
redaction, receipt integrity, audit visibility, and release blocking.
Dependencies: scripts.validate_sdlc_artifact and scripts.validate_sdlc_security_review.
Invariants:
  - This validator is read-only and deterministic.
  - Provider-side credential mutation is not performed or claimed.
  - Read-only live-probe readiness requires provider lifecycle witnesses.
  - Write, calendar, customer, and production readiness remain separately blocked.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_sdlc_artifact import (  # noqa: E402
    load_json_object,
    validate_artifact_record,
    validate_security_review_record,
)
from scripts.validate_sdlc_security_review import validate_required_security_checks  # noqa: E402


PLAN_PATH = WORKSPACE_ROOT / "docs" / "64_durable_gmail_connector_runtime_plan.md"
REQUIREMENT_PATH = (
    WORKSPACE_ROOT / "examples" / "sdlc" / "requirement_durable_gmail_connector_runtime_20260611.json"
)
SECURITY_REVIEW_PATH = (
    WORKSPACE_ROOT / "examples" / "sdlc" / "security_review_durable_gmail_connector_runtime_20260611.json"
)

REQUIRED_PLAN_TERMS = (
    "No Google Cloud credential creation",
    "least-privilege scope decision",
    "refresh-token storage",
    "revocation and failed-refresh",
    "approval-gated",
    "AwaitingEvidence",
    "SolvedVerified",
    "read-only Gmail live-probe boundary",
    "mint_gmail_oauth_access_token.py",
    "produce_durable_gmail_oauth_operator_handoff.py",
    "produce_durable_gmail_oauth_live_receipt.py",
    "validate_durable_gmail_oauth_live_receipt_freshness.py",
    "Evidence freshness",
    "operator handoff packet",
)
REQUIRED_NON_GOALS = (
    "no Google Cloud credential creation in this change",
    "no OAuth consent-screen publication in this change",
    "no production verification submission in this change",
    "no secret value storage in repository artifacts",
)
REQUIRED_CONSTRAINT_TERMS = (
    "narrowest documented scope",
    "Sensitive or restricted Google scopes",
    "never token or refresh-token values",
    "External-account mutations require operator authorization",
    "revocation, rotation, expiration, and failed-refresh paths",
)
REQUIRED_EVIDENCE_REFS = (
    "Google OAuth consent-screen configuration witness",
    "Google OAuth client creation witness without secret serialization",
    "least-privilege Gmail scope decision receipt",
    "refresh-token storage and rotation receipt",
    "revocation and failed-refresh test receipt",
)
BLOCKING_FINDING_ID = "durable_gmail_oauth_runtime_witness_missing"
PROHIBITED_SERIALIZED_SECRET_MARKERS = (
    "ya29.",
    "refresh_token=",
    "client_secret=",
    "-----BEGIN PRIVATE KEY-----",
)


def validate_contract() -> list[str]:
    """Validate the durable Gmail connector runtime plan and evidence packets."""

    errors: list[str] = []
    plan_text = _load_plan_text()
    requirement_record = load_json_object(REQUIREMENT_PATH, "durable Gmail connector runtime requirement")
    security_review_record = load_json_object(
        SECURITY_REVIEW_PATH,
        "durable Gmail connector runtime security review",
    )

    errors.extend(f"requirement: {error}" for error in validate_artifact_record("requirement", requirement_record))
    errors.extend(
        f"security_review: {error}"
        for error in validate_artifact_record("security_review", security_review_record)
    )
    errors.extend(
        f"security_review: {error}"
        for error in validate_security_review_record(security_review_record, strict=True)
    )
    errors.extend(
        f"security_review: {error}"
        for error in validate_required_security_checks(security_review_record, strict=True)
    )

    errors.extend(_validate_plan_terms(plan_text))
    errors.extend(_validate_requirement_boundary(requirement_record))
    errors.extend(_validate_security_boundary(security_review_record))
    errors.extend(_validate_no_secret_markers(plan_text, requirement_record, security_review_record))
    return errors


def build_validation_report() -> dict[str, Any]:
    """Build a machine-readable validation receipt."""

    try:
        errors = validate_contract()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-durable-gmail-connector-runtime-plan: {_sanitize_error(exc)}"]
    valid = not errors
    checks = (
        "durable_gmail_plan_terms",
        "durable_gmail_requirement_schema",
        "durable_gmail_non_goal_boundary",
        "durable_gmail_scope_constraints",
        "durable_gmail_required_evidence",
        "durable_gmail_operator_handoff",
        "durable_gmail_evidence_freshness",
        "durable_gmail_security_review_schema",
        "durable_gmail_release_block",
        "durable_gmail_secret_redaction",
    )
    return {
        "receipt_id": "durable_gmail_connector_runtime_plan_validation",
        "valid": valid,
        "status": "passed" if valid else "failed",
        "plan_path": _path_label(PLAN_PATH),
        "requirement_path": _path_label(REQUIREMENT_PATH),
        "security_review_path": _path_label(SECURITY_REVIEW_PATH),
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def _load_plan_text() -> str:
    if not PLAN_PATH.exists():
        raise FileNotFoundError(f"missing durable Gmail connector runtime plan: {_path_label(PLAN_PATH)}")
    return PLAN_PATH.read_text(encoding="utf-8")


def _validate_plan_terms(plan_text: str) -> list[str]:
    errors: list[str] = []
    for required_term in REQUIRED_PLAN_TERMS:
        if required_term not in plan_text:
            errors.append(f"plan missing required term: {required_term}")
    return errors


def _validate_requirement_boundary(requirement_record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if requirement_record.get("risk_class") != "high":
        errors.append("requirement risk_class must remain high for durable OAuth runtime work")
    for required_non_goal in REQUIRED_NON_GOALS:
        if required_non_goal not in requirement_record.get("non_goals", []):
            errors.append(f"requirement missing non-goal: {required_non_goal}")
    constraint_text = "\n".join(str(item) for item in requirement_record.get("constraints", []))
    for required_constraint_term in REQUIRED_CONSTRAINT_TERMS:
        if required_constraint_term not in constraint_text:
            errors.append(f"requirement missing constraint term: {required_constraint_term}")
    for required_evidence_ref in REQUIRED_EVIDENCE_REFS:
        if required_evidence_ref not in requirement_record.get("evidence_required", []):
            errors.append(f"requirement missing evidence ref: {required_evidence_ref}")
    if not any(
        "Google Cloud OAuth consent and credentials" == surface
        for surface in requirement_record.get("affected_surfaces", [])
    ):
        errors.append("requirement must include Google Cloud OAuth consent and credentials surface")
    return errors


def _validate_security_boundary(security_review_record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if security_review_record.get("release_blocked") is not True:
        errors.append("security review must block release until durable OAuth witnesses exist")
    if security_review_record.get("residual_risk") != "high":
        errors.append("security review residual risk must remain high while provider witnesses are missing")
    open_high_findings = [
        finding
        for finding in security_review_record.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("finding_id") == BLOCKING_FINDING_ID
        and finding.get("severity") == "high"
        and finding.get("status") == "open"
    ]
    if not open_high_findings:
        errors.append(f"security review missing open high finding: {BLOCKING_FINDING_ID}")
    required_impacts = {"auth", "external_api", "secrets", "policy", "receipts", "audit"}
    observed_impacts = set(security_review_record.get("impact_categories", []))
    missing_impacts = sorted(required_impacts - observed_impacts)
    if missing_impacts:
        errors.append(f"security review missing impact categories: {missing_impacts}")
    if security_review_record.get("receipt_ref") not in security_review_record.get("security_receipts", []):
        errors.append("security review receipt_ref must be included in security_receipts")
    return errors


def _validate_no_secret_markers(
    plan_text: str,
    requirement_record: dict[str, Any],
    security_review_record: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    serialized_payload = "\n".join(
        (
            plan_text,
            json.dumps(requirement_record, sort_keys=True),
            json.dumps(security_review_record, sort_keys=True),
        )
    )
    for prohibited_marker in PROHIBITED_SERIALIZED_SECRET_MARKERS:
        if prohibited_marker in serialized_payload:
            errors.append(f"serialized secret marker is prohibited: {prohibited_marker}")
    return errors


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    for governed_path in (PLAN_PATH, REQUIREMENT_PATH, SECURITY_REVIEW_PATH):
        message = message.replace(str(governed_path), _path_label(governed_path))
        message = message.replace(str(governed_path.resolve(strict=False)), _path_label(governed_path))
    return message


def main(argv: list[str] | None = None) -> int:
    """Validate the durable Gmail connector runtime plan."""

    parser = argparse.ArgumentParser(description="Validate durable Gmail connector runtime plan.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)

    report = build_validation_report()
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1

    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] durable-gmail-connector-runtime-plan: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
