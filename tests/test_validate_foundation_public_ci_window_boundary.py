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


def test_public_ci_window_witness_rejects_extra_validator_fields() -> None:
    payload = load_json_object(DEFAULT_WITNESS_PATH, "public CI window boundary witness")
    payload["validators"][0]["raw_log"] = "bounded local detail"

    findings = validate_witness(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_validator_entry_keys_invalid" for finding in findings)
    assert any("validator entries must contain only command and state" in finding.message for finding in findings)
    assert all("bounded local detail" not in finding.message for finding in findings)


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


def test_public_ci_window_receipt_rejects_extra_validator_fields() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["validators"][0]["raw_log"] = "private validator output"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(
        finding.rule_id == "public_ci_window_receipt_validator_entry_keys_invalid"
        for finding in findings
    )
    assert any("validator entries must contain only command and state" in finding.message for finding in findings)
    assert all("private validator output" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_invalid_visibility_before_label() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["repo_visibility_before"] = "public"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_visibility_before_invalid" for finding in findings)
    assert any("repo_visibility_before must be private" in finding.message for finding in findings)
    assert all("public" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_invalid_bounded_visibility_after_label() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["status"] = "bounded_public_awaiting_evidence"
    payload["solver_outcome"] = "AwaitingEvidence"
    payload["closed_at"] = None
    payload["repo_visibility_after"] = "private"
    for validator in payload["validators"]:
        validator["state"] = "AwaitingEvidence"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_visibility_after_invalid" for finding in findings)
    assert any("repo_visibility_after must match the receipt status" in finding.message for finding in findings)
    assert all("private" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_reason_without_budget_actions_boundary() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["reason"] = "Temporary visibility was useful for general repository review."

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_text_contract_invalid" for finding in findings)
    assert any("reason must preserve public CI window boundary wording" in finding.message for finding in findings)
    assert all("general repository review" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_exposure_decision_without_deployment_boundary() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["exposure_decision"] = "The public window was used for GitHub Actions and PR verification."

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_text_contract_invalid" for finding in findings)
    assert any("exposure_decision must preserve public CI window boundary wording" in finding.message for finding in findings)
    assert all("PR verification" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_invalid_opened_at_timestamp() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["opened_at"] = "2026-06-26 10:51:56"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_opened_at_invalid" for finding in findings)
    assert any("opened_at must be an ISO-8601 UTC timestamp ending in Z" in finding.message for finding in findings)
    assert all("2026-06-26 10:51:56" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_closed_at_before_opened_at() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["opened_at"] = "2026-06-26T11:15:28Z"
    payload["closed_at"] = "2026-06-26T10:51:56Z"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_timestamp_order_invalid" for finding in findings)
    assert any("closed_at must be greater than or equal to opened_at" in finding.message for finding in findings)
    assert all("2026-06-26T10:51:56Z" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_window_id_date_mismatch() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["window_id"] = "foundation_public_ci_window.20260625.pr2213"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_window_id_date_mismatch" for finding in findings)
    assert any("window_id date must match opened_at UTC date" in finding.message for finding in findings)
    assert all("20260625" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_malformed_window_id_date_token() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["window_id"] = "foundation_public_ci_window.pr2213"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_window_id_date_mismatch" for finding in findings)
    assert any("window_id date must match opened_at UTC date" in finding.message for finding in findings)
    assert all("foundation_public_ci_window.pr2213" not in finding.message for finding in findings)


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


def test_public_ci_window_receipt_rejects_job_url_as_workflow_run_url() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["workflow_run_urls"] = [
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28233991896/job/83700000000"
    ]

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_workflow_urls_invalid" for finding in findings)
    assert any("exact repository GitHub Actions run URLs" in finding.message for finding in findings)
    assert all("83700000000" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_duplicate_workflow_run_urls() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["workflow_run_urls"] = [
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28233991896",
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28233991896",
    ]

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_workflow_urls_duplicate" for finding in findings)
    assert any("must not repeat a GitHub Actions run" in finding.message for finding in findings)
    assert all("28233991896" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_missing_workflow_run_url() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["workflow_run_urls"] = [
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28233991896"
    ]

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_workflow_url_count_invalid" for finding in findings)
    assert any("workflow_run_urls must contain exactly 2 runs" in finding.message for finding in findings)
    assert all("28233991896" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_extra_workflow_run_url() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["workflow_run_urls"].append(
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28233999999"
    )

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_workflow_url_count_invalid" for finding in findings)
    assert any("workflow_run_urls must contain exactly 2 runs" in finding.message for finding in findings)
    assert all("28233999999" not in finding.message for finding in findings)


def test_public_ci_window_receipt_derives_pr_check_command_from_pull_request() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["pull_request"] = "https://github.com/tamirat-wubie/mullu-control-plane/pull/2230"
    payload["window_id"] = "foundation_public_ci_window.20260626.pr2230"
    payload["head_sha"] = "a67ce0c31871c6f88e098fa16019143e7c04d059"
    payload["branch"] = "codex/public-ci-window-receipt-contract-20260626"
    payload["validators"][-1]["command"] = "gh pr checks 2230"

    findings = validate_window_receipt(payload)

    assert findings == []
    assert payload["pull_request"].endswith("/2230")
    assert payload["validators"][-1]["command"] == "gh pr checks 2230"
    assert payload["head_sha"] == "a67ce0c31871c6f88e098fa16019143e7c04d059"


def test_public_ci_window_receipt_rejects_window_id_pr_mismatch() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["pull_request"] = "https://github.com/tamirat-wubie/mullu-control-plane/pull/2230"
    payload["window_id"] = "foundation_public_ci_window.20260626.pr2213"
    payload["validators"][-1]["command"] = "gh pr checks 2230"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(finding.rule_id == "public_ci_window_receipt_window_id_pr_mismatch" for finding in findings)
    assert any("window_id must end with the pull request identity" in finding.message for finding in findings)
    assert all("2230" not in finding.message for finding in findings)


def test_public_ci_window_receipt_rejects_mismatched_pr_check_command() -> None:
    payload = load_json_object(DEFAULT_RECEIPT_PATH, "public CI window receipt example")
    payload["pull_request"] = "https://github.com/tamirat-wubie/mullu-control-plane/pull/2230"
    payload["validators"][-1]["command"] = "gh pr checks 2213"

    findings = validate_window_receipt(payload)

    assert findings
    assert any(
        finding.rule_id == "public_ci_window_receipt_validator_commands_invalid"
        for finding in findings
    )
    assert all("2230" not in finding.message for finding in findings)


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
