#!/usr/bin/env python3
"""Validate the Foundation Mode public CI window boundary.

Purpose: keep temporary repository-public windows bounded to GitHub Actions
execution and evidence capture during Foundation Mode budget constraints.
Governance scope: source-control visibility, CI execution, proprietary
boundary protection, secret exposure prevention, and public-readiness
separation.
Dependencies: docs/FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md.
Invariants:
  - Validation is read-only.
  - Public visibility is not public readiness.
  - Public CI windows do not authorize public launch, customer exposure,
    production deployment, legal filing, fundraising, or raw secret exposure.
  - Window-specific receipts either close exposure or preserve an explicit
    AwaitingEvidence bounded-public state.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "FOUNDATION_PUBLIC_CI_WINDOW_BOUNDARY.md"
DEFAULT_WITNESS_PATH = REPO_ROOT / "examples" / "foundation_public_ci_window_boundary_witness.awaiting_evidence.json"
DEFAULT_RECEIPT_PATH = REPO_ROOT / "examples" / "foundation_public_ci_window_receipt.closed.example.json"

EXPECTED_WITNESS_ID = "foundation_public_ci_window_boundary_witness.awaiting_evidence.v1"
EXPECTED_WINDOW_ID = "foundation_public_ci_window.awaiting_evidence.v1"
EXPECTED_RECEIPT_ID = "foundation_public_ci_window_receipt.closed.example.v1"
EXPECTED_REPO = "tamirat-wubie/mullu-control-plane"
EXPECTED_BLOCKED_CLAIMS = (
    "public readiness",
    "public launch",
    "customer access",
    "production deployment",
    "legal filing",
    "fundraising readiness",
    "raw secret exposure",
)
EXPECTED_VALIDATOR_COMMANDS = (
    "python scripts/validate_public_repository_surface.py --local-only",
    "python scripts/validate_proprietary_boundary.py",
    "python scripts/validate_release_status.py",
    "python scripts/report_ci_health.py --repo tamirat-wubie/mullu-control-plane --branch main --json",
)
EXPECTED_VALIDATOR_KEYS = {"command", "state"}
EXPECTED_RECEIPT_BASE_VALIDATOR_COMMANDS = (
    "python scripts/validate_public_repository_surface.py --local-only",
    "python scripts/validate_proprietary_boundary.py",
    "python scripts/validate_release_status.py",
)
EXPECTED_ROOT_KEYS = {
    "blocked_claims",
    "branch",
    "closed_at",
    "closure_decision",
    "customer_access_claimed",
    "exposure_decision",
    "head_sha",
    "opened_at",
    "production_deployment_claimed",
    "public_launch_claimed",
    "public_readiness_claimed",
    "raw_secrets_committed",
    "reason",
    "repo_visibility_after",
    "repo_visibility_before",
    "schema_version",
    "solver_outcome",
    "status",
    "validators",
    "window_id",
    "witness_id",
    "workflow_run_urls",
}
EXPECTED_RECEIPT_ROOT_KEYS = {
    "branch",
    "branch_deleted",
    "closed_at",
    "closure_decision",
    "customer_access_claimed",
    "exposure_decision",
    "head_sha",
    "merge_commit",
    "merged_at",
    "opened_at",
    "production_deployment_claimed",
    "public_launch_claimed",
    "public_readiness_claimed",
    "pull_request",
    "raw_secrets_committed",
    "reason",
    "receipt_id",
    "repo",
    "repo_visibility_after",
    "repo_visibility_before",
    "repo_visibility_restored",
    "repo_visibility_restored_at",
    "schema_version",
    "solver_outcome",
    "status",
    "validators",
    "window_id",
    "workflow_run_urls",
}
ALLOWED_RECEIPT_STATUSES = {"closed", "bounded_public_awaiting_evidence"}
EXPECTED_VISIBILITY_BEFORE = "private"
ALLOWED_VISIBILITY_AFTER_BY_STATUS = {
    "closed": {"private"},
    "bounded_public_awaiting_evidence": {"bounded_public", "private_or_bounded_public"},
}
EXPECTED_RECEIPT_WORKFLOW_RUN_COUNT = 2
MAX_BOUNDED_PUBLIC_WINDOW_AGE = timedelta(hours=6)
REQUIRED_RECEIPT_TEXT_FRAGMENTS = {
    "reason": (
        "Foundation Mode",
        "budget",
        "GitHub Actions",
    ),
    "exposure_decision": (
        "GitHub Actions",
        "No public launch",
        "customer access",
        "production deployment",
        "raw secret exposure",
    ),
    "closure_decision": (
        "Public CI evidence",
        "checks",
        "public-readiness state",
    ),
}
SECRET_SHAPED_FRAGMENTS = (
    "-----begin",
    "private key",
    "access_token",
    "refresh_token",
    "client_secret",
    "github_token",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
)

REQUIRED_FRAGMENTS = (
    "Foundation Public CI Window Boundary",
    "temporary CI execution surface",
    "public visibility is not public readiness",
    "Foundation Mode",
    "GitHub Actions execution",
    "no raw secrets",
    "pre-window",
    "open-window",
    "execution-window",
    "close-window",
    "post-window receipt",
    "python scripts/validate_public_repository_surface.py --local-only",
    "python scripts/validate_proprietary_boundary.py",
    "python scripts/validate_release_status.py",
    "python scripts/report_ci_health.py --repo tamirat-wubie/mullu-control-plane --branch main --json",
    "repo_visibility_before",
    "repo_visibility_after",
    "workflow_run_urls",
    "exposure_decision",
    "closure_decision",
    "foundation_public_ci_window_receipt.closed.example.json",
    "AwaitingEvidence",
    "../examples/foundation_public_ci_window_boundary_witness.awaiting_evidence.json",
)

FORBIDDEN_FRAGMENTS = (
    "public visibility is public readiness",
    "public visibility equals public readiness",
    "public launch allowed",
    "customer exposure allowed",
    "production deployment allowed",
    "legal filing allowed",
    "fundraising allowed",
    "raw secrets may be printed",
)


@dataclass(frozen=True)
class Finding:
    """A deterministic validation finding for the public CI window boundary."""

    rule_id: str
    message: str


def _normalise(content: str) -> str:
    return " ".join(content.casefold().split())


def _contains_all_fragments(value: Any, fragments: tuple[str, ...]) -> bool:
    if not isinstance(value, str):
        return False
    normalised_value = _normalise(value)
    return all(_normalise(fragment) in normalised_value for fragment in fragments)


def validate_document_text(content: str) -> list[Finding]:
    """Validate the public CI window boundary document content."""

    findings: list[Finding] = []
    normalised = _normalise(content)
    for fragment in REQUIRED_FRAGMENTS:
        if _normalise(fragment) not in normalised:
            findings.append(
                Finding(
                    "public_ci_window_required_fragment_missing",
                    f"missing required fragment: {fragment}",
                )
            )
    for fragment in FORBIDDEN_FRAGMENTS:
        if _normalise(fragment) in normalised:
            findings.append(
                Finding(
                    "public_ci_window_forbidden_fragment_present",
                    f"forbidden fragment present: {fragment}",
                )
            )
    return findings


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with explicit path and type errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def validate_witness(payload: dict[str, Any]) -> list[Finding]:
    """Validate the committed public CI window AwaitingEvidence witness."""

    findings: list[Finding] = []
    if set(payload) != EXPECTED_ROOT_KEYS:
        findings.append(
            Finding(
                "public_ci_window_witness_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_ROOT_KEYS))}",
            )
        )

    expected_values: dict[str, object] = {
        "witness_id": EXPECTED_WITNESS_ID,
        "window_id": EXPECTED_WINDOW_ID,
        "schema_version": 1,
        "status": "AwaitingEvidence",
        "solver_outcome": "AwaitingEvidence",
        "public_readiness_claimed": False,
        "public_launch_claimed": False,
        "customer_access_claimed": False,
        "production_deployment_claimed": False,
        "raw_secrets_committed": False,
    }
    for key, expected_value in expected_values.items():
        if payload.get(key) != expected_value:
            findings.append(
                Finding("public_ci_window_witness_value_invalid", f"{key} must be {expected_value!r}")
            )

    if tuple(payload.get("blocked_claims") or ()) != EXPECTED_BLOCKED_CLAIMS:
        findings.append(
            Finding(
                "public_ci_window_blocked_claims_invalid",
                f"blocked_claims must be: {', '.join(EXPECTED_BLOCKED_CLAIMS)}",
            )
        )

    validators = payload.get("validators")
    if not isinstance(validators, list) or not all(isinstance(item, dict) for item in validators):
        findings.append(Finding("public_ci_window_validators_invalid", "validators must be a list of objects"))
    else:
        if not all(set(item) == EXPECTED_VALIDATOR_KEYS for item in validators):
            findings.append(
                Finding(
                    "public_ci_window_validator_entry_keys_invalid",
                    "validator entries must contain only command and state",
                )
            )
        observed_commands = tuple(item.get("command") for item in validators)
        observed_states = tuple(item.get("state") for item in validators)
        if observed_commands != EXPECTED_VALIDATOR_COMMANDS:
            findings.append(
                Finding("public_ci_window_validator_commands_invalid", "validator command inventory drifted")
            )
        if observed_states != ("AwaitingEvidence",) * len(EXPECTED_VALIDATOR_COMMANDS):
            findings.append(
                Finding("public_ci_window_validator_states_invalid", "validator states must remain AwaitingEvidence")
            )

    if payload.get("opened_at") is not None or payload.get("closed_at") is not None:
        findings.append(
            Finding(
                "public_ci_window_live_timestamps_invalid",
                "committed witness must not claim a live public CI window timestamp",
            )
        )
    if payload.get("workflow_run_urls") != []:
        findings.append(
            Finding(
                "public_ci_window_workflow_urls_invalid",
                "committed witness must not claim observed live workflow runs",
            )
        )
    return findings


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contains_secret_shaped_text(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True).casefold()
    return any(fragment in text for fragment in SECRET_SHAPED_FRAGMENTS)


def _github_actions_run_id(value: Any) -> str | None:
    prefix = f"https://github.com/{EXPECTED_REPO}/actions/runs/"
    if not isinstance(value, str) or not value.startswith(prefix):
        return None
    run_id = value.removeprefix(prefix)
    if not run_id.isdigit():
        return None
    return run_id


def _is_github_actions_url(value: Any) -> bool:
    return _github_actions_run_id(value) is not None


def _is_pull_request_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(f"https://github.com/{EXPECTED_REPO}/pull/")


def _pull_request_number(value: Any) -> str | None:
    if not _is_pull_request_url(value):
        return None
    number = value.rsplit("/", 1)[-1]
    if not number.isdigit():
        return None
    return number


def _window_id_binds_pull_request(window_id: Any, pull_request_number: str) -> bool:
    return isinstance(window_id, str) and window_id.endswith(f".pr{pull_request_number}")


def _window_id_date_token(window_id: Any) -> str | None:
    if not isinstance(window_id, str):
        return None
    parts = window_id.split(".")
    if len(parts) != 3 or parts[0] != "foundation_public_ci_window":
        return None
    date_token = parts[1]
    if len(date_token) != 8 or not date_token.isdigit():
        return None
    return date_token


def _is_hex_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _parse_utc_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return None
    if parsed.tzinfo != timezone.utc:
        return None
    return parsed


def validate_window_receipt(payload: dict[str, Any], observed_at: datetime | None = None) -> list[Finding]:
    """Validate one window-specific public CI receipt."""

    findings: list[Finding] = []
    observed_at = observed_at or datetime.now(timezone.utc)
    if set(payload) != EXPECTED_RECEIPT_ROOT_KEYS:
        findings.append(
            Finding(
                "public_ci_window_receipt_root_keys_invalid",
                f"root keys must be: {', '.join(sorted(EXPECTED_RECEIPT_ROOT_KEYS))}",
            )
        )

    expected_false_flags = (
        "public_readiness_claimed",
        "public_launch_claimed",
        "customer_access_claimed",
        "production_deployment_claimed",
        "raw_secrets_committed",
    )
    for key in expected_false_flags:
        if payload.get(key) is not False:
            findings.append(Finding("public_ci_window_receipt_claim_flag_invalid", f"{key} must be false"))

    if payload.get("receipt_id") != EXPECTED_RECEIPT_ID:
        findings.append(
            Finding("public_ci_window_receipt_id_invalid", f"receipt_id must be {EXPECTED_RECEIPT_ID!r}")
        )
    if payload.get("schema_version") != 1:
        findings.append(Finding("public_ci_window_receipt_schema_version_invalid", "schema_version must be 1"))
    if payload.get("repo") != EXPECTED_REPO:
        findings.append(Finding("public_ci_window_receipt_repo_invalid", f"repo must be {EXPECTED_REPO!r}"))

    status = payload.get("status")
    solver_outcome = payload.get("solver_outcome")
    if status not in ALLOWED_RECEIPT_STATUSES:
        findings.append(
            Finding(
                "public_ci_window_receipt_status_invalid",
                f"status must be one of: {', '.join(sorted(ALLOWED_RECEIPT_STATUSES))}",
            )
        )
    if status == "closed" and solver_outcome != "SolvedVerified":
        findings.append(
            Finding("public_ci_window_receipt_solver_outcome_invalid", "closed receipts must be SolvedVerified")
        )
    if status == "bounded_public_awaiting_evidence" and solver_outcome != "AwaitingEvidence":
        findings.append(
            Finding(
                "public_ci_window_receipt_solver_outcome_invalid",
                "bounded public receipts must remain AwaitingEvidence",
            )
        )
    if status == "closed" and payload.get("branch_deleted") is not True:
        findings.append(
            Finding(
                "public_ci_window_receipt_branch_deleted_invalid",
                "closed receipts must confirm topic branch deletion",
            )
        )
    if status == "bounded_public_awaiting_evidence" and payload.get("branch_deleted") is not False:
        findings.append(
            Finding(
                "public_ci_window_receipt_branch_deleted_invalid",
                "bounded public receipts must keep branch_deleted false",
            )
        )
    if payload.get("repo_visibility_before") != EXPECTED_VISIBILITY_BEFORE:
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_before_invalid",
                "repo_visibility_before must be private",
            )
        )
    allowed_visibility_after = ALLOWED_VISIBILITY_AFTER_BY_STATUS.get(status)
    if allowed_visibility_after is not None and payload.get("repo_visibility_after") not in allowed_visibility_after:
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_after_invalid",
                "repo_visibility_after must match the receipt status",
            )
        )
    if status == "closed" and payload.get("repo_visibility_restored") is not True:
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_restored_invalid",
                "closed receipts must confirm private visibility restoration",
            )
        )
    if status == "bounded_public_awaiting_evidence" and payload.get("repo_visibility_restored") is not False:
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_restored_invalid",
                "bounded public receipts must keep repo_visibility_restored false",
            )
        )

    required_text_fields = (
        "window_id",
        "reason",
        "repo_visibility_before",
        "repo_visibility_after",
        "opened_at",
        "branch",
        "head_sha",
        "exposure_decision",
        "closure_decision",
    )
    for key in required_text_fields:
        if not _is_non_empty_string(payload.get(key)):
            findings.append(Finding("public_ci_window_receipt_required_string_invalid", f"{key} must be non-empty"))
    for key, fragments in REQUIRED_RECEIPT_TEXT_FRAGMENTS.items():
        if not _contains_all_fragments(payload.get(key), fragments):
            findings.append(
                Finding(
                    "public_ci_window_receipt_text_contract_invalid",
                    f"{key} must preserve public CI window boundary wording",
                )
            )
    if not _is_hex_sha(payload.get("head_sha")):
        findings.append(Finding("public_ci_window_receipt_head_sha_invalid", "head_sha must be a 40-character lowercase hex SHA"))
    if status == "closed" and not _is_hex_sha(payload.get("merge_commit")):
        findings.append(
            Finding(
                "public_ci_window_receipt_merge_commit_invalid",
                "closed receipts require a 40-character lowercase hex merge_commit",
            )
        )
    if status == "bounded_public_awaiting_evidence" and payload.get("merge_commit") is not None:
        findings.append(
            Finding(
                "public_ci_window_receipt_merge_commit_invalid",
                "bounded public receipts must keep merge_commit null",
            )
        )
    pull_request_number = _pull_request_number(payload.get("pull_request"))
    if pull_request_number is None:
        findings.append(Finding("public_ci_window_receipt_pull_request_invalid", "pull_request must be a repository PR URL"))
    elif not _window_id_binds_pull_request(payload.get("window_id"), pull_request_number):
        findings.append(
            Finding(
                "public_ci_window_receipt_window_id_pr_mismatch",
                "window_id must end with the pull request identity",
            )
        )

    opened_at = payload.get("opened_at")
    parsed_opened_at = _parse_utc_timestamp(opened_at)
    if parsed_opened_at is None:
        findings.append(
            Finding(
                "public_ci_window_receipt_opened_at_invalid",
                "opened_at must be an ISO-8601 UTC timestamp ending in Z",
            )
        )
    else:
        window_id_date = _window_id_date_token(payload.get("window_id"))
        if window_id_date != parsed_opened_at.strftime("%Y%m%d"):
            findings.append(
                Finding(
                    "public_ci_window_receipt_window_id_date_mismatch",
                    "window_id date must match opened_at UTC date",
                )
            )

    closed_at = payload.get("closed_at")
    if status == "closed" and not _is_non_empty_string(closed_at):
        findings.append(Finding("public_ci_window_receipt_closed_at_invalid", "closed receipts require closed_at"))
    parsed_closed_at = None
    if _is_non_empty_string(closed_at):
        parsed_closed_at = _parse_utc_timestamp(closed_at)
        if parsed_closed_at is None:
            findings.append(
                Finding(
                    "public_ci_window_receipt_closed_at_invalid",
                    "closed_at must be an ISO-8601 UTC timestamp ending in Z",
                )
            )
    if status == "bounded_public_awaiting_evidence" and closed_at is not None:
        findings.append(
            Finding("public_ci_window_receipt_closed_at_invalid", "bounded public receipts must keep closed_at null")
        )
    if parsed_opened_at is not None and parsed_closed_at is not None and parsed_closed_at < parsed_opened_at:
        findings.append(
            Finding(
                "public_ci_window_receipt_timestamp_order_invalid",
                "closed_at must be greater than or equal to opened_at",
            )
        )
    if (
        status == "bounded_public_awaiting_evidence"
        and parsed_opened_at is not None
        and parsed_closed_at is None
        and observed_at - parsed_opened_at > MAX_BOUNDED_PUBLIC_WINDOW_AGE
    ):
        findings.append(
            Finding(
                "public_ci_window_receipt_stale_bounded_public_window",
                "bounded public receipts must close or refresh evidence within six hours",
            )
        )

    merged_at = payload.get("merged_at")
    parsed_merged_at = None
    if status == "closed" and not _is_non_empty_string(merged_at):
        findings.append(Finding("public_ci_window_receipt_merged_at_invalid", "closed receipts require merged_at"))
    if _is_non_empty_string(merged_at):
        parsed_merged_at = _parse_utc_timestamp(merged_at)
        if parsed_merged_at is None:
            findings.append(
                Finding(
                    "public_ci_window_receipt_merged_at_invalid",
                    "merged_at must be an ISO-8601 UTC timestamp ending in Z",
                )
            )
    if status == "bounded_public_awaiting_evidence" and merged_at is not None:
        findings.append(
            Finding("public_ci_window_receipt_merged_at_invalid", "bounded public receipts must keep merged_at null")
        )
    if parsed_opened_at is not None and parsed_merged_at is not None and parsed_merged_at < parsed_opened_at:
        findings.append(
            Finding(
                "public_ci_window_receipt_merge_timestamp_order_invalid",
                "merged_at must be greater than or equal to opened_at",
            )
        )
    if parsed_merged_at is not None and parsed_closed_at is not None and parsed_closed_at < parsed_merged_at:
        findings.append(
            Finding(
                "public_ci_window_receipt_closure_merge_order_invalid",
                "closed_at must be greater than or equal to merged_at",
            )
        )

    repo_visibility_restored_at = payload.get("repo_visibility_restored_at")
    parsed_repo_visibility_restored_at = None
    if status == "closed" and not _is_non_empty_string(repo_visibility_restored_at):
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_restored_at_invalid",
                "closed receipts require repo_visibility_restored_at",
            )
        )
    if _is_non_empty_string(repo_visibility_restored_at):
        parsed_repo_visibility_restored_at = _parse_utc_timestamp(repo_visibility_restored_at)
        if parsed_repo_visibility_restored_at is None:
            findings.append(
                Finding(
                    "public_ci_window_receipt_visibility_restored_at_invalid",
                    "repo_visibility_restored_at must be an ISO-8601 UTC timestamp ending in Z",
                )
            )
    if status == "bounded_public_awaiting_evidence" and repo_visibility_restored_at is not None:
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_restored_at_invalid",
                "bounded public receipts must keep repo_visibility_restored_at null",
            )
        )
    if (
        parsed_opened_at is not None
        and parsed_repo_visibility_restored_at is not None
        and parsed_repo_visibility_restored_at < parsed_opened_at
    ):
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_restoration_order_invalid",
                "repo_visibility_restored_at must be greater than or equal to opened_at",
            )
        )
    if (
        parsed_repo_visibility_restored_at is not None
        and parsed_closed_at is not None
        and parsed_closed_at < parsed_repo_visibility_restored_at
    ):
        findings.append(
            Finding(
                "public_ci_window_receipt_visibility_restoration_closure_order_invalid",
                "closed_at must be greater than or equal to repo_visibility_restored_at",
            )
        )

    workflow_urls = payload.get("workflow_run_urls")
    if not isinstance(workflow_urls, list) or not workflow_urls:
        findings.append(
            Finding("public_ci_window_receipt_workflow_urls_invalid", "workflow_run_urls must be a non-empty list")
        )
    else:
        if len(workflow_urls) != EXPECTED_RECEIPT_WORKFLOW_RUN_COUNT:
            findings.append(
                Finding(
                    "public_ci_window_receipt_workflow_url_count_invalid",
                    f"workflow_run_urls must contain exactly {EXPECTED_RECEIPT_WORKFLOW_RUN_COUNT} runs",
                )
            )
        workflow_run_ids = tuple(_github_actions_run_id(item) for item in workflow_urls)
        if any(run_id is None for run_id in workflow_run_ids):
            findings.append(
                Finding(
                    "public_ci_window_receipt_workflow_urls_invalid",
                    "workflow_run_urls must contain exact repository GitHub Actions run URLs",
                )
            )
        observed_run_ids = tuple(run_id for run_id in workflow_run_ids if run_id is not None)
        if len(set(observed_run_ids)) != len(observed_run_ids):
            findings.append(
                Finding(
                    "public_ci_window_receipt_workflow_urls_duplicate",
                    "workflow_run_urls must not repeat a GitHub Actions run",
                )
            )

    validators = payload.get("validators")
    if not isinstance(validators, list) or not all(isinstance(item, dict) for item in validators):
        findings.append(Finding("public_ci_window_receipt_validators_invalid", "validators must be a list of objects"))
    else:
        if not all(set(item) == EXPECTED_VALIDATOR_KEYS for item in validators):
            findings.append(
                Finding(
                    "public_ci_window_receipt_validator_entry_keys_invalid",
                    "validator entries must contain only command and state",
                )
            )
        expected_validator_commands = EXPECTED_RECEIPT_BASE_VALIDATOR_COMMANDS
        if pull_request_number is not None:
            expected_validator_commands = (
                *EXPECTED_RECEIPT_BASE_VALIDATOR_COMMANDS,
                f"gh pr checks {pull_request_number}",
            )
        observed_commands = tuple(item.get("command") for item in validators)
        if observed_commands != expected_validator_commands:
            findings.append(
                Finding("public_ci_window_receipt_validator_commands_invalid", "validator command inventory drifted")
            )
        observed_states = tuple(item.get("state") for item in validators)
        expected_state = "passed" if status == "closed" else "AwaitingEvidence"
        if observed_states != (expected_state,) * len(expected_validator_commands):
            findings.append(
                Finding(
                    "public_ci_window_receipt_validator_states_invalid",
                    f"validator states must all be {expected_state}",
                )
            )

    if _contains_secret_shaped_text(payload):
        findings.append(
            Finding(
                "public_ci_window_receipt_secret_shaped_text_present",
                "receipt must not contain raw secret-shaped text",
            )
        )
    return findings


def validate_foundation_public_ci_window_boundary(
    doc_path: Path = DEFAULT_DOC_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[Finding]:
    """Validate the repository-local public CI window boundary artifact."""

    if not doc_path.exists():
        return [
            Finding(
                "public_ci_window_document_missing",
                f"missing public CI window boundary document: {doc_path}",
            )
        ]
    findings = validate_document_text(doc_path.read_text(encoding="utf-8"))
    witness_payload = load_json_object(witness_path, "public CI window boundary witness")
    findings.extend(validate_witness(witness_payload))
    receipt_payload = load_json_object(receipt_path, "public CI window receipt example")
    findings.extend(validate_window_receipt(receipt_payload))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the public CI window boundary.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_foundation_public_ci_window_boundary(args.doc, args.witness, args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] public_ci_window_boundary_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    print("[PASS] foundation_public_ci_window_boundary")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
