"""Tests for the Foundation Mode GitHub App token-format boundary validator.

Purpose: prove GitHub App installation tokens remain opaque, long-token-ready,
dot-tolerant, and free of committed live credential assumptions.
Governance scope: token-format compatibility, synthetic fixtures, repository
scanner coverage, external-validation deferral, and deployment blocking.
Dependencies: scripts.validate_foundation_github_app_token_format_boundary.
Invariants: fixed token length, fixed ghs suffix length, JWT parsing, short
storage capacity, real token fixtures, and deployment readiness stay blocked.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_github_app_token_format_boundary import (  # noqa: E402
    DEFAULT_WITNESS_PATH,
    EXPECTED_WITNESS_ID,
    load_json_object,
    validate_foundation_github_app_token_format_boundary,
    validate_repository_scan,
    validate_witness,
)


def test_foundation_github_app_token_format_boundary_artifacts_pass() -> None:
    assert validate_foundation_github_app_token_format_boundary() == []


def test_witness_has_expected_identity_and_opaque_token_contract() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "GitHub App token-format witness")

    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert payload["tokens_are_opaque"] is True
    assert payload["fixed_length_validation_allowed"] is False
    assert payload["jwt_parsing_allowed"] is False
    assert payload["minimum_storage_capacity_chars"] == 520
    assert payload["real_tokens_committed"] is False
    assert payload["deployment_allowed"] is False


def test_witness_rejects_fixed_length_validation_claim() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "GitHub App token-format witness")
    candidate = deepcopy(payload)
    candidate["fixed_length_validation_allowed"] = True

    findings = validate_witness(candidate)

    assert findings
    assert any(finding.rule_id == "github_app_token_format_root_value_invalid" for finding in findings)


def test_witness_rejects_jwt_parsing_claim() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "GitHub App token-format witness")
    candidate = deepcopy(payload)
    candidate["jwt_parsing_allowed"] = True

    findings = validate_witness(candidate)

    assert findings
    assert any(finding.rule_id == "github_app_token_format_root_value_invalid" for finding in findings)


def test_witness_rejects_short_stateless_fixture() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "GitHub App token-format witness")
    candidate = deepcopy(payload)
    candidate["synthetic_fixtures"]["stateless_long_shape"] = "ghs_short.with.dots"

    findings = validate_witness(candidate)

    assert findings
    assert any(finding.rule_id == "github_app_token_format_stateless_fixture_too_short" for finding in findings)


def test_repository_scan_rejects_fixed_ghs_suffix_regex(tmp_path: Path) -> None:
    scanner_file = tmp_path / "scanner.py"
    scanner_file.write_text("pattern = r'github app installation token ghs_[A-Za-z0-9]{36}'\n", encoding="utf-8")

    findings = validate_repository_scan(tmp_path)

    assert findings
    assert any(
        finding.rule_id == "github_app_token_format_forbidden_repository_pattern" for finding in findings
    )


def test_repository_scan_ignores_unrelated_jwt_text(tmp_path: Path) -> None:
    scanner_file = tmp_path / "jwt_notes.md"
    scanner_file.write_text("JWT authentication for normal API users is handled elsewhere.\n", encoding="utf-8")

    findings = validate_repository_scan(tmp_path)

    assert findings == []
