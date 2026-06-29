#!/usr/bin/env python3
"""Build a governed public CI window receipt.

Purpose: convert observed temporary public GitHub Actions window evidence into
the receipt shape enforced by the Foundation public CI window boundary.
Governance scope: Foundation Mode source-control visibility, public CI window
closure, bounded-public AwaitingEvidence, branch cleanup, CI evidence, and
public-readiness separation.
Dependencies: scripts.validate_foundation_public_ci_window_boundary.
Invariants:
  - The builder does not change repository visibility.
  - Public visibility is not public readiness.
  - Closed receipts require merge and private-restoration evidence.
  - Bounded-public receipts remain AwaitingEvidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_public_ci_window_boundary import (  # noqa: E402
    EXPECTED_RECEIPT_ID,
    EXPECTED_REPO,
    validate_window_receipt,
)


DEFAULT_OUTPUT_DIR = REPO_ROOT / ".change_assurance"
REASON = "Foundation Mode budget constraints required a temporary public repository visibility window for GitHub Actions execution."
EXPOSURE_DECISION = (
    "The public window was used only for GitHub Actions evidence and PR verification. "
    "No public launch, customer access, production deployment, legal filing, "
    "fundraising readiness, or raw secret exposure was claimed."
)
CLOSED_DECISION = (
    "Public CI evidence was collected, all observed checks passed, and repository exposure was closed or bounded "
    "without changing public-readiness state."
)
BOUNDED_DECISION = (
    "Public CI evidence remains AwaitingEvidence, checks are not terminal, and public-readiness state remains blocked."
)
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


def _contains_secret_shaped_text(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True).casefold()
    return any(fragment in text for fragment in SECRET_SHAPED_FRAGMENTS)


def _is_hex_sha(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _timestamp(value: str, field_name: str) -> str:
    if not value.endswith("Z"):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field_name} must be an ISO-8601 UTC timestamp ending in Z")
    return value


def _date_token(opened_at: str) -> str:
    parsed = datetime.fromisoformat(f"{opened_at[:-1]}+00:00")
    return parsed.strftime("%Y%m%d")


def _pull_request_number(value: str) -> str:
    match = re.fullmatch(r"https://github\.com/tamirat-wubie/mullu-control-plane/pull/([0-9]+)|([0-9]+)", value)
    if match is None:
        raise ValueError("pull_request must be a repository PR number or URL")
    return match.group(1) or match.group(2)


def _branch(value: str) -> str:
    if not value.strip() or value.startswith("-") or ".." in value or not any(char.isalnum() for char in value):
        raise ValueError("branch must be a non-empty branch name")
    return value


def _workflow_run_urls(values: list[str]) -> list[str]:
    prefix = f"https://github.com/{EXPECTED_REPO}/actions/runs/"
    if len(values) != 2:
        raise ValueError("workflow_run_urls must contain exactly two GitHub Actions run URLs")
    run_ids: list[str] = []
    for value in values:
        if not value.startswith(prefix):
            raise ValueError("workflow_run_urls must be exact repository GitHub Actions run URLs")
        run_id = value.removeprefix(prefix)
        if not run_id.isdigit():
            raise ValueError("workflow_run_urls must be exact repository GitHub Actions run URLs")
        run_ids.append(run_id)
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("workflow_run_urls must not repeat a GitHub Actions run")
    return values


def _validators(pr_number: str, state: str) -> list[dict[str, str]]:
    return [
        {"command": "python scripts/validate_public_repository_surface.py --local-only", "state": state},
        {"command": "python scripts/validate_proprietary_boundary.py", "state": state},
        {"command": "python scripts/validate_release_status.py", "state": state},
        {"command": f"gh pr checks {pr_number}", "state": state},
    ]


def build_public_ci_window_receipt(
    *,
    pull_request: str,
    branch: str,
    head_sha: str,
    opened_at: str,
    workflow_run_urls: list[str],
    status: str,
    closed_at: str | None = None,
    merged_at: str | None = None,
    merge_commit: str | None = None,
    repo_visibility_restored_at: str | None = None,
    branch_deleted: bool | None = None,
) -> dict[str, Any]:
    """Build a public CI window receipt matching the boundary validator."""

    pr_number = _pull_request_number(pull_request)
    branch = _branch(branch)
    opened_at = _timestamp(opened_at, "opened_at")
    workflow_run_urls = _workflow_run_urls(workflow_run_urls)
    if not _is_hex_sha(head_sha):
        raise ValueError("head_sha must be a 40-character lowercase hex SHA")
    if _contains_secret_shaped_text((pull_request, branch, head_sha, opened_at, workflow_run_urls)):
        raise ValueError("receipt inputs must not contain raw secret-shaped text")

    if status == "closed":
        if closed_at is None or merged_at is None or merge_commit is None or repo_visibility_restored_at is None:
            raise ValueError("closed receipts require closed_at, merged_at, merge_commit, and repo_visibility_restored_at")
        if branch_deleted is not True:
            raise ValueError("closed receipts require branch_deleted true")
        closed_at = _timestamp(closed_at, "closed_at")
        merged_at = _timestamp(merged_at, "merged_at")
        repo_visibility_restored_at = _timestamp(repo_visibility_restored_at, "repo_visibility_restored_at")
        if not _is_hex_sha(merge_commit):
            raise ValueError("merge_commit must be a 40-character lowercase hex SHA")
        solver_outcome = "SolvedVerified"
        repo_visibility_after = "private"
        repo_visibility_restored = True
        validator_state = "passed"
        closure_decision = CLOSED_DECISION
    elif status == "bounded_public_awaiting_evidence":
        closed_at = None
        merged_at = None
        merge_commit = None
        repo_visibility_restored_at = None
        branch_deleted = False
        solver_outcome = "AwaitingEvidence"
        repo_visibility_after = "bounded_public"
        repo_visibility_restored = False
        validator_state = "AwaitingEvidence"
        closure_decision = BOUNDED_DECISION
    else:
        raise ValueError("status must be closed or bounded_public_awaiting_evidence")

    receipt = {
        "branch": branch,
        "branch_deleted": branch_deleted,
        "closed_at": closed_at,
        "closure_decision": closure_decision,
        "customer_access_claimed": False,
        "exposure_decision": EXPOSURE_DECISION,
        "head_sha": head_sha,
        "merge_commit": merge_commit,
        "merged_at": merged_at,
        "opened_at": opened_at,
        "production_deployment_claimed": False,
        "public_launch_claimed": False,
        "public_readiness_claimed": False,
        "pull_request": f"https://github.com/{EXPECTED_REPO}/pull/{pr_number}",
        "raw_secrets_committed": False,
        "reason": REASON,
        "receipt_id": EXPECTED_RECEIPT_ID,
        "repo": EXPECTED_REPO,
        "repo_visibility_after": repo_visibility_after,
        "repo_visibility_before": "private",
        "repo_visibility_restored": repo_visibility_restored,
        "repo_visibility_restored_at": repo_visibility_restored_at,
        "schema_version": 1,
        "solver_outcome": solver_outcome,
        "status": status,
        "validators": _validators(pr_number, validator_state),
        "window_id": f"foundation_public_ci_window.{_date_token(opened_at)}.pr{pr_number}",
        "workflow_run_urls": workflow_run_urls,
    }
    findings = validate_window_receipt(receipt)
    if findings:
        rule_ids = ", ".join(finding.rule_id for finding in findings)
        raise ValueError(f"generated receipt failed boundary validation: {rule_ids}")
    return receipt


def write_public_ci_window_receipt(receipt: dict[str, Any], output_path: Path) -> Path:
    """Write a receipt JSON object to a repository-local path."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a public CI window receipt.")
    parser.add_argument("--pull-request", required=True, help="Repository PR number or URL.")
    parser.add_argument("--branch", required=True, help="Branch verified during the CI window.")
    parser.add_argument("--head-sha", required=True, help="40-character lowercase head SHA.")
    parser.add_argument("--opened-at", required=True, help="UTC timestamp ending in Z.")
    parser.add_argument("--workflow-run-url", action="append", required=True, help="GitHub Actions run URL. Provide exactly two.")
    parser.add_argument("--status", choices=("closed", "bounded_public_awaiting_evidence"), required=True)
    parser.add_argument("--closed-at", default=None, help="UTC timestamp ending in Z for closed receipts.")
    parser.add_argument("--merged-at", default=None, help="UTC timestamp ending in Z for closed receipts.")
    parser.add_argument("--merge-commit", default=None, help="40-character lowercase merge commit for closed receipts.")
    parser.add_argument("--repo-visibility-restored-at", default=None, help="UTC timestamp ending in Z for closed receipts.")
    parser.add_argument("--branch-deleted", action="store_true", help="Set true after deleting the topic branch.")
    parser.add_argument("--output", type=Path, default=None, help="Output receipt path.")
    args = parser.parse_args(argv)

    try:
        receipt = build_public_ci_window_receipt(
            pull_request=args.pull_request,
            branch=args.branch,
            head_sha=args.head_sha,
            opened_at=args.opened_at,
            workflow_run_urls=args.workflow_run_url,
            status=args.status,
            closed_at=args.closed_at,
            merged_at=args.merged_at,
            merge_commit=args.merge_commit,
            repo_visibility_restored_at=args.repo_visibility_restored_at,
            branch_deleted=args.branch_deleted,
        )
    except ValueError as exc:
        print(f"[FAIL] public_ci_window_receipt_builder: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if args.output is None:
        pr_number = _pull_request_number(args.pull_request)
        output_path = DEFAULT_OUTPUT_DIR / f"public-ci-window-{pr_number}-receipt.json"
    else:
        output_path = args.output
    write_public_ci_window_receipt(receipt, output_path)
    print(f"[PASS] public_ci_window_receipt_builder: {output_path}")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
