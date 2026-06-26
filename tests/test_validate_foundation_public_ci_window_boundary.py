"""Tests for the Foundation Mode public CI window boundary validator.

Purpose: prove temporary repository-public windows remain bounded to CI
execution, evidence capture, proprietary boundary validation, and receipt
closure.
Governance scope: source-control visibility, GitHub Actions execution,
public-readiness separation, secret exposure prevention, and Foundation Mode.
Dependencies: scripts.validate_foundation_public_ci_window_boundary.
Invariants: public visibility is not public readiness; no raw secrets,
customer exposure, public launch, or production deployment is authorized.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_public_ci_window_boundary import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_RECEIPT_PATH,
    DEFAULT_WITNESS_PATH,
    EXPECTED_WITNESS_ID,
    REQUIRED_FRAGMENTS,
    load_json_object,
    validate_document_text,
    validate_foundation_public_ci_window_boundary,
    validate_window_receipt,
    validate_witness,
    main,
)


def test_foundation_public_ci_window_boundary_artifact_passes() -> None:
    findings = validate_foundation_public_ci_window_boundary()
    content = DEFAULT_DOC_PATH.read_text(encoding="utf-8")

    assert findings == []
    assert "temporary CI execution surface" in content
    assert "public visibility is not public readiness" in content
    assert "post-window receipt" in content


def test_public_ci_window_boundary_rejects_missing_required_fragment() -> None:
    content = "\n".join(fragment for fragment in REQUIRED_FRAGMENTS if fragment != "post-window receipt")

    findings = validate_document_text(content)

    assert findings
    assert any(finding.rule_id == "public_ci_window_required_fragment_missing" for finding in findings)
    assert any("post-window receipt" in finding.message for finding in findings)


def test_public_ci_window_boundary_rejects_public_readiness_equivalence() -> None:
    content = DEFAULT_DOC_PATH.read_text(encoding="utf-8") + "\npublic visibility equals public readiness\n"

    findings = validate_document_text(content)

    assert findings
    assert any(finding.rule_id == "public_ci_window_forbidden_fragment_present" for finding in findings)
    assert any("public visibility equals public readiness" in finding.message for finding in findings)


def test_public_ci_window_witness_blocks_public_claims_and_secret_exposure() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "public CI window boundary witness")

    assert validate_witness(payload) == []
    assert payload["witness_id"] == EXPECTED_WITNESS_ID
    assert payload["status"] == "AwaitingEvidence"
    assert payload["public_readiness_claimed"] is False
    assert payload["public_launch_claimed"] is False
    assert payload["customer_access_claimed"] is False
    assert payload["production_deployment_claimed"] is False
    assert payload["raw_secrets_committed"] is False


def test_public_ci_window_witness_rejects_launch_claim() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "public CI window boundary witness")
    payload["public_launch_claimed"] = True

    findings = validate_witness(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_witness_value_invalid" for finding in findings)
    assert any("public_launch_claimed" in finding.message for finding in findings)


def test_public_ci_window_closed_receipt_example_passes() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")

    assert validate_window_receipt(payload) == []
    assert payload["status"] == "closed"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["public_readiness_claimed"] is False
    assert payload["raw_secrets_committed"] is False
    assert payload["workflow_run_urls"]


def test_public_ci_window_receipt_rejects_missing_closure_for_closed_window() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["closed_at"] = None

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_closed_at_invalid" for finding in findings)
    assert any("closed receipts require closed_at" in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_secret_shaped_text() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["exposure_decision"] = "accidentally included client_secret value"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(
        finding.rule_id == "public_ci_window_receipt_secret_shaped_text_present"
        for finding in findings
    )
    assert all("client_secret value" not in finding.message for finding in findings)


def test_public_ci_window_receipt_allows_bounded_public_awaiting_evidence() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["status"] = "bounded_public_awaiting_evidence"
    payload["solver_outcome"] = "AwaitingEvidence"
    payload["closed_at"] = None
    for validator in payload["validators"]:
        validator["state"] = "AwaitingEvidence"

    findings = validate_window_receipt(payload)

    assert findings == []
    assert payload["status"] == "bounded_public_awaiting_evidence"
    assert payload["closed_at"] is None
    assert all(validator["state"] == "AwaitingEvidence" for validator in payload["validators"])


def test_public_ci_window_boundary_cli_passes(capsys) -> None:
    exit_code = main([])
    streams = capsys.readouterr()

    assert exit_code == 0
    assert "[PASS] foundation_public_ci_window_boundary" in streams.out
    assert "STATUS: passed" in streams.out
