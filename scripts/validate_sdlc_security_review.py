#!/usr/bin/env python3
"""Validate SDLC security review artifacts.

Purpose: verify security impact classification, required checks, release
blocking behavior, and residual-risk receipts for SDLC changes.
Governance scope: OCE security fields, RAG impact-to-check mapping, CDCV
mitigation evidence, CQTE severity gates, UWMA security receipts, and PRS
residual-risk closure.
Dependencies: Python standard library and scripts/validate_sdlc_artifact.py.
Invariants:
  - Open critical/high findings block release.
  - Failed required checks block release.
  - Strict mode requires receipt-backed review evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_sdlc_artifact import (  # noqa: E402
    ARTIFACT_SPEC_BY_KIND,
    load_json_object,
    validate_artifact_record,
    validate_security_review_record,
)


REQUIRED_CHECK_BY_CATEGORY = {
    "tenant_scope": "IDOR",
    "filesystem": "path traversal",
    "network": "SSRF",
    "secrets": "redaction",
    "budget": "budget ownership",
    "policy": "policy bypass",
    "deployment": "deployment witness",
    "memory": "memory admission",
    "receipts": "receipt integrity",
    "audit": "audit visibility",
}


def validate_required_security_checks(record: dict[str, object], *, strict: bool) -> list[str]:
    """Validate impact categories carry the expected checks."""

    errors: list[str] = []
    checks = record.get("required_checks", [])
    check_text_by_category: dict[str, list[str]] = {}
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict):
                category = str(check.get("category"))
                check_text_by_category.setdefault(category, []).append(str(check.get("check", "")).lower())
    for category, required_text in REQUIRED_CHECK_BY_CATEGORY.items():
        if category not in record.get("impact_categories", []):
            continue
        observed_texts = check_text_by_category.get(category, [])
        if not any(required_text.lower() in observed_text for observed_text in observed_texts):
            errors.append(f"security_review: impact {category} requires {required_text} check")
    if strict and "none" in record.get("impact_categories", []) and len(record.get("impact_categories", [])) > 1:
        errors.append("security_review: none impact category cannot be mixed with concrete impacts")
    return errors


def validate_contract(review_path: Path | None = None, *, strict: bool = False) -> list[str]:
    """Validate the canonical or provided SDLC security review."""

    resolved_review_path = ARTIFACT_SPEC_BY_KIND["security_review"].example_path if review_path is None else review_path
    review_record = load_json_object(resolved_review_path, "SDLC security review")
    errors = validate_artifact_record("security_review", review_record)
    errors.extend(validate_security_review_record(review_record, strict=strict))
    errors.extend(validate_required_security_checks(review_record, strict=strict))
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate SDLC security review."""

    parser = argparse.ArgumentParser(description="Validate SDLC security review.")
    parser.add_argument("--review", type=Path, help="optional security review JSON path")
    parser.add_argument("--strict", action="store_true", help="enforce strict security review controls")
    args = parser.parse_args(argv)

    try:
        errors = validate_contract(args.review, strict=args.strict)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] sdlc-security-review-load: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] sdlc-security-review: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] sdlc_security_review_schema\n")
    sys.stdout.write("[PASS] sdlc_security_review_findings\n")
    sys.stdout.write("[PASS] sdlc_security_review_required_checks\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
