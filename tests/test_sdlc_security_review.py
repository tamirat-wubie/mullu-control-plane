"""Purpose: verify governed SDLC security review validation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_sdlc_security_review.
Invariants:
  - Critical/high open findings block release.
  - Failed required checks are rejected.
  - Impact categories require mapped checks.
"""

from __future__ import annotations

import copy
import io
from contextlib import redirect_stdout
from pathlib import Path

from scripts import validate_sdlc_artifact
from scripts import validate_sdlc_security_review as validator


def test_current_sdlc_security_review_passes_strict() -> None:
    errors = validator.validate_contract(strict=True)

    assert errors == []
    assert validate_sdlc_artifact.ARTIFACT_SPEC_BY_KIND["security_review"].example_path.exists()
    assert "policy" in validate_sdlc_artifact.load_example_records()["security_review"]["impact_categories"]


def test_open_high_finding_blocks_release() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])
    review["findings"] = [
        {
            "finding_id": "finding-high",
            "severity": "high",
            "status": "open",
            "mitigation": "add tenant enforcement",
            "evidence_refs": ["test://tenant-scope"],
            "residual_risk": "high",
        }
    ]
    review["release_blocked"] = false_value = False

    errors = validate_sdlc_artifact.validate_security_review_record(review, strict=True)

    assert "security_review: unresolved critical/high findings must block release" in errors
    assert false_value is False
    assert len(errors) >= 1


def test_failed_required_check_is_rejected() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])
    review["required_checks"][0]["status"] = "failed"

    errors = validate_sdlc_artifact.validate_security_review_record(review, strict=True)

    assert "security_review: failed required checks must be resolved before release" in errors
    assert review["required_checks"][0]["status"] == "failed"
    assert len(errors) >= 1


def test_impact_category_requires_mapped_check() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])
    review["impact_categories"].append("tenant_scope")

    errors = validator.validate_required_security_checks(review, strict=True)

    assert "security_review: impact tenant_scope requires IDOR check" in errors
    assert "tenant_scope" in review["impact_categories"]
    assert len(errors) >= 1


def test_duplicate_category_checks_preserve_required_control() -> None:
    review = copy.deepcopy(validate_sdlc_artifact.load_example_records()["security_review"])

    errors = validator.validate_required_security_checks(review, strict=True)
    audit_checks = [check for check in review["required_checks"] if check["category"] == "audit"]

    assert errors == []
    assert len(audit_checks) >= 2
    assert any("audit visibility" in check["check"] for check in audit_checks)
    assert any("PR enforcement drift" in check["check"] for check in audit_checks)


def test_trusted_identity_header_boundary_security_review_passes_strict() -> None:
    review_path = Path("examples/sdlc/security_review_trusted_identity_header_boundary_20260615.json")
    review = validate_sdlc_artifact.load_json_object(review_path, "trusted identity header boundary security review")

    errors = validator.validate_contract(review_path, strict=True)

    assert errors == []
    assert "auth" in review["impact_categories"]
    assert "tenant_scope" in review["impact_categories"]
    assert review["release_blocked"] is False
    assert review["residual_risk"] == "low"
    assert review["receipt_ref"] in review["security_receipts"]


def test_security_review_cli_reports_passed() -> None:
    stdout_buffer = io.StringIO()

    with redirect_stdout(stdout_buffer):
        exit_code = validator.main(["--strict"])

    output = stdout_buffer.getvalue()
    assert exit_code == 0
    assert "sdlc_security_review_schema" in output
    assert "STATUS: passed" in output
