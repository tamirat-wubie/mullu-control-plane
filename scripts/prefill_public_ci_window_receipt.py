#!/usr/bin/env python3
"""Prefill a public CI window receipt from read-only GitHub metadata.

Purpose: collect pull-request and workflow-run metadata with read-only GitHub
CLI commands, then delegate receipt construction to the governed receipt
builder.
Governance scope: Foundation Mode source-control visibility, public CI window
evidence, no-execute visibility boundary, receipt prefill, and public-readiness
separation.
Dependencies: GitHub CLI, scripts.build_public_ci_window_receipt.
Invariants:
  - This script does not change repository visibility.
  - GitHub CLI calls are read-only metadata queries.
  - Closed receipts still require operator-supplied visibility restoration
    evidence.
  - Bounded-public receipts remain AwaitingEvidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_public_ci_window_receipt import (  # noqa: E402
    DEFAULT_OUTPUT_DIR,
    build_public_ci_window_receipt,
    write_public_ci_window_receipt,
)


EXPECTED_REPO = "tamirat-wubie/mullu-control-plane"
PR_FIELDS = "number,url,headRefName,headRefOid,mergedAt,mergeCommit"
RUN_FIELDS = "databaseId,url,status,conclusion,createdAt,headBranch,headSha"
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
CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _contains_secret_shaped_text(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True).casefold()
    return any(fragment in text for fragment in SECRET_SHAPED_FRAGMENTS)


def _run_command(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), check=False, capture_output=True, text=True, timeout=60)


def _gh_json(argv: Sequence[str], *, runner: CommandRunner = _run_command) -> Any:
    completed = runner(argv)
    if completed.returncode != 0:
        raise ValueError("GitHub metadata query failed")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub metadata query returned invalid JSON") from exc


def _pr_number(value: str) -> str:
    value = value.rstrip("/")
    return value.rsplit("/", 1)[-1]


def fetch_pull_request_metadata(pull_request: str, *, runner: CommandRunner = _run_command) -> dict[str, Any]:
    """Fetch read-only pull request metadata from GitHub CLI."""

    payload = _gh_json(
        ("gh", "pr", "view", pull_request, "--repo", EXPECTED_REPO, "--json", PR_FIELDS),
        runner=runner,
    )
    if not isinstance(payload, dict):
        raise ValueError("pull request metadata must be a JSON object")
    required = ("url", "headRefName", "headRefOid")
    if not all(isinstance(payload.get(key), str) and payload[key] for key in required):
        raise ValueError("pull request metadata is missing required fields")
    if _contains_secret_shaped_text(payload):
        raise ValueError("pull request metadata must not contain raw secret-shaped text")
    return payload


def fetch_workflow_run_urls(
    *,
    branch: str,
    head_sha: str,
    limit: int = 20,
    runner: CommandRunner = _run_command,
) -> list[str]:
    """Fetch two read-only GitHub Actions run URLs for a branch and head SHA."""

    payload = _gh_json(
        (
            "gh",
            "run",
            "list",
            "--repo",
            EXPECTED_REPO,
            "--branch",
            branch,
            "--limit",
            str(limit),
            "--json",
            RUN_FIELDS,
        ),
        runner=runner,
    )
    if not isinstance(payload, list):
        raise ValueError("workflow run metadata must be a JSON list")
    urls: list[str] = []
    for run in payload:
        if not isinstance(run, dict):
            continue
        if run.get("headBranch") != branch or run.get("headSha") != head_sha:
            continue
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        url = run.get("url")
        if isinstance(url, str) and url not in urls:
            urls.append(url)
        if len(urls) == 2:
            break
    if len(urls) != 2:
        raise ValueError("expected exactly two successful workflow runs for the pull request branch and head SHA")
    if _contains_secret_shaped_text(urls):
        raise ValueError("workflow run metadata must not contain raw secret-shaped text")
    return urls


def prefill_public_ci_window_receipt(
    *,
    pull_request: str,
    opened_at: str,
    status: str,
    closed_at: str | None = None,
    repo_visibility_restored_at: str | None = None,
    branch_deleted: bool = False,
    run_limit: int = 20,
    runner: CommandRunner = _run_command,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a receipt from read-only GitHub PR and workflow metadata."""

    pr_payload = fetch_pull_request_metadata(pull_request, runner=runner)
    branch = str(pr_payload["headRefName"])
    head_sha = str(pr_payload["headRefOid"])
    workflow_run_urls = fetch_workflow_run_urls(
        branch=branch,
        head_sha=head_sha,
        limit=run_limit,
        runner=runner,
    )
    merged_at = pr_payload.get("mergedAt")
    merge_commit = pr_payload.get("mergeCommit")
    if isinstance(merge_commit, dict):
        merge_commit = merge_commit.get("oid")

    if status == "closed":
        if not isinstance(merged_at, str) or not merged_at:
            raise ValueError("closed receipt prefill requires mergedAt from pull request metadata")
        if not isinstance(merge_commit, str) or not merge_commit:
            raise ValueError("closed receipt prefill requires mergeCommit.oid from pull request metadata")
        if not isinstance(repo_visibility_restored_at, str) or not repo_visibility_restored_at:
            raise ValueError("closed receipt prefill requires operator-supplied repo_visibility_restored_at")
        closed_at = closed_at or merged_at
    else:
        merged_at = None
        merge_commit = None
        closed_at = None
        repo_visibility_restored_at = None
        branch_deleted = False

    return build_public_ci_window_receipt(
        pull_request=str(pr_payload.get("url") or pull_request),
        branch=branch,
        head_sha=head_sha,
        opened_at=opened_at,
        workflow_run_urls=workflow_run_urls,
        status=status,
        closed_at=closed_at,
        merged_at=merged_at,
        merge_commit=merge_commit,
        repo_visibility_restored_at=repo_visibility_restored_at,
        branch_deleted=branch_deleted,
        observed_at=observed_at,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prefill public CI window receipt from read-only GitHub metadata.")
    parser.add_argument("--pull-request", required=True, help="Repository PR number or URL.")
    parser.add_argument("--opened-at", required=True, help="UTC timestamp for public visibility opening.")
    parser.add_argument("--status", choices=("closed", "bounded_public_awaiting_evidence"), required=True)
    parser.add_argument("--closed-at", default=None, help="Optional UTC closure timestamp. Defaults to mergedAt for closed receipts.")
    parser.add_argument("--repo-visibility-restored-at", default=None, help="UTC private-restoration timestamp for closed receipts.")
    parser.add_argument("--branch-deleted", action="store_true", help="Set true after deleting the topic branch.")
    parser.add_argument("--run-limit", type=int, default=20, help="Number of workflow runs to inspect.")
    parser.add_argument("--output", type=Path, default=None, help="Output receipt path.")
    args = parser.parse_args(argv)

    try:
        receipt = prefill_public_ci_window_receipt(
            pull_request=args.pull_request,
            opened_at=args.opened_at,
            status=args.status,
            closed_at=args.closed_at,
            repo_visibility_restored_at=args.repo_visibility_restored_at,
            branch_deleted=args.branch_deleted,
            run_limit=args.run_limit,
            runner=_run_command,
        )
    except ValueError as exc:
        print(f"[FAIL] public_ci_window_receipt_prefill: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if args.output is None:
        output_path = DEFAULT_OUTPUT_DIR / f"public-ci-window-{_pr_number(str(receipt['pull_request']))}-receipt.json"
    else:
        output_path = args.output
    write_public_ci_window_receipt(receipt, output_path)
    print(f"[PASS] public_ci_window_receipt_prefill: {output_path}")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
