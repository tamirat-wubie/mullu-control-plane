#!/usr/bin/env python3
"""Validate Mullu SDLC route fixtures and routing contract.

Purpose: verify repository-owned SDLC route examples and deterministic routing.
Governance scope: OCE route fixture completeness, RAG request-to-skill linkage,
CDCV route causality, CQTE decidable checks, UWMA validation receipt, and PRS closure.
Dependencies: Python standard library and scripts/route_sdlc.py.
Invariants:
  - Every route fixture is a JSON object.
  - Expected skills are retained in observed route output.
  - Short signal matching does not admit substring false positives.
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

from scripts.route_sdlc import build_route_payload, route_request  # noqa: E402


EXAMPLE_DIR = WORKSPACE_ROOT / "examples" / "sdlc_route"
REQUIRED_EXAMPLES: tuple[str, ...] = (
    "ci_failure_route.json",
    "new_validator_route.json",
    "release_witness_route.json",
    "documentation_drift_route.json",
    "fallback_route.json",
)
REQUIRED_PR_TERMS: tuple[str, ...] = (
    "SDLC route used",
    "python scripts/route_sdlc.py",
    "python scripts/validate_sdlc_route.py",
)


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one route fixture JSON object."""

    if not path.exists():
        raise FileNotFoundError(f"missing SDLC route fixture: {_label_path(path)}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"SDLC route fixture must be an object: {_label_path(path)}")
    return payload


def validate_route_fixture(path: Path) -> list[str]:
    """Validate one route fixture."""

    errors: list[str] = []
    payload = load_json_object(path)
    route_id = payload.get("route_id")
    request = payload.get("request")
    expected_skills = payload.get("expected_skills")
    expected_sequence = payload.get("expected_sequence")
    expected_fallback = payload.get("expected_fallback_used")
    if not isinstance(route_id, str) or not route_id:
        errors.append(f"{_label_path(path)}: route_id must be a non-empty string")
    if not isinstance(request, str) or not request.strip():
        errors.append(f"{_label_path(path)}: request must be a non-empty string")
        return errors
    if not isinstance(expected_skills, list) or not expected_skills:
        errors.append(f"{_label_path(path)}: expected_skills must be a non-empty list")
        return errors

    receipt = route_request(request)
    observed_skills = set(receipt.skills)
    missing_skills = [skill for skill in expected_skills if skill not in observed_skills]
    unexpected_skills = [skill for skill in receipt.skills if skill not in expected_skills and receipt.fallback_used]
    if missing_skills:
        errors.append(f"{_label_path(path)}: route missing expected skills: {missing_skills}")
    if unexpected_skills:
        errors.append(f"{_label_path(path)}: fallback route emitted unexpected skills: {unexpected_skills}")
    if isinstance(expected_sequence, str) and receipt.sequence_name != expected_sequence:
        errors.append(
            f"{_label_path(path)}: expected sequence {expected_sequence}, observed {receipt.sequence_name}"
        )
    if isinstance(expected_fallback, bool) and receipt.fallback_used is not expected_fallback:
        errors.append(f"{_label_path(path)}: fallback_used mismatch")
    return errors


def validate_route_contract() -> list[str]:
    """Validate all route fixtures and route evidence surfaces."""

    errors: list[str] = []
    for example_name in REQUIRED_EXAMPLES:
        errors.extend(validate_route_fixture(EXAMPLE_DIR / example_name))
    prepare_receipt = route_request("Prepare release deployment witness and rollback")
    if "sdlc-pr-readiness-closure" in prepare_receipt.skills:
        errors.append("route_contract: Prepare must not trigger the short PR signal")
    pr_template_text = (WORKSPACE_ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
    sdlc_doc_text = (WORKSPACE_ROOT / "docs" / "SDLC.md").read_text(encoding="utf-8")
    for term in REQUIRED_PR_TERMS:
        if term not in pr_template_text:
            errors.append(f"pull_request_template missing SDLC route term: {term}")
        if term not in sdlc_doc_text:
            errors.append(f"SDLC.md missing SDLC route term: {term}")
    return errors


def build_validation_report() -> dict[str, object]:
    """Build a machine-readable SDLC route validation receipt."""

    try:
        errors = validate_route_contract()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors = [f"load-sdlc-route-contract: {_sanitize_error(exc)}"]
    valid = not errors
    checks = (
        "sdlc_route_fixtures",
        "sdlc_route_short_signal_boundary",
        "sdlc_route_pr_template_evidence",
        "sdlc_route_documentation_evidence",
    )
    return {
        "receipt_id": "sdlc_route_validation_receipt",
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "valid": valid,
        "status": "passed" if valid else "failed",
        "example_paths": [f"examples/sdlc_route/{example_name}" for example_name in REQUIRED_EXAMPLES],
        "checks": [{"name": check_name, "passed": valid} for check_name in checks],
        "check_count": len(checks),
        "error_count": len(errors),
        "errors": errors,
    }


def _label_path(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(WORKSPACE_ROOT).as_posix()
    except ValueError:
        return path.name


def _sanitize_error(exc: BaseException) -> str:
    message = str(exc)
    return message.replace(str(WORKSPACE_ROOT), ".")


def main(argv: list[str] | None = None) -> int:
    """Validate SDLC route fixtures and contract."""

    parser = argparse.ArgumentParser(description="Validate governed SDLC route fixtures.")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    parser.add_argument("--route", help="emit the observed route for one request")
    args = parser.parse_args(argv)

    if args.route:
        receipt = build_route_payload(route_request(args.route))
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return 0

    report = build_validation_report()
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0 if report["valid"] else 1
    if not report["valid"]:
        for error in report["errors"]:
            sys.stderr.write(f"[FAIL] sdlc-route: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1
    for check in report["checks"]:
        sys.stdout.write(f"[PASS] {check['name']}\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
