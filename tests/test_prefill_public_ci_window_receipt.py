"""Tests for read-only public CI receipt prefill.

Purpose: prove GitHub metadata prefill uses read-only commands, emits the
existing receipt contract, and preserves visibility/manual evidence boundaries.
Governance scope: public CI receipt metadata, GitHub read-only observation,
bounded-public AwaitingEvidence, and public-readiness separation.
Dependencies: scripts.prefill_public_ci_window_receipt.
Invariants: no visibility mutation command is executed; closed receipts require
operator-supplied visibility restoration; secret-shaped data is not echoed.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prefill_public_ci_window_receipt import (  # noqa: E402
    fetch_pull_request_metadata,
    fetch_workflow_run_urls,
    main,
    prefill_public_ci_window_receipt,
)
from scripts.validate_foundation_public_ci_window_boundary import validate_window_receipt  # noqa: E402


def _completed(argv: Sequence[str], payload: object, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(list(argv), returncode, stdout=json.dumps(payload), stderr="")


def _runner(calls: list[list[str]]):
    def run(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        calls.append(command)
        if command[:3] == ["gh", "pr", "view"]:
            return _completed(
                command,
                {
                    "number": 2400,
                    "url": "https://github.com/tamirat-wubie/mullu-control-plane/pull/2400",
                    "headRefName": "codex/public-ci-window-receipt-builder-20260629",
                    "headRefOid": "fdf0e278a19e483f0461a0d251e7365ca69cb3ec",
                    "mergedAt": "2026-06-29T08:07:42Z",
                    "mergeCommit": {"oid": "ba07975fc10c2aa7ec8f1506aa6652245d1be96c"},
                },
            )
        if command[:3] == ["gh", "run", "list"]:
            return _completed(
                command,
                [
                    {
                        "databaseId": 28357014460,
                        "url": "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28357014460",
                        "status": "completed",
                        "conclusion": "success",
                        "createdAt": "2026-06-29T07:46:00Z",
                        "headBranch": "codex/public-ci-window-receipt-builder-20260629",
                        "headSha": "fdf0e278a19e483f0461a0d251e7365ca69cb3ec",
                    },
                    {
                        "databaseId": 28357033319,
                        "url": "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28357033319",
                        "status": "completed",
                        "conclusion": "success",
                        "createdAt": "2026-06-29T07:47:00Z",
                        "headBranch": "codex/public-ci-window-receipt-builder-20260629",
                        "headSha": "fdf0e278a19e483f0461a0d251e7365ca69cb3ec",
                    },
                ],
            )
        return _completed(command, {}, returncode=1)

    return run


def test_prefill_public_ci_window_receipt_builds_closed_receipt() -> None:
    calls: list[list[str]] = []
    observed_at = datetime(2026, 6, 29, 9, 0, 0, tzinfo=timezone.utc)
    receipt = prefill_public_ci_window_receipt(
        pull_request="2400",
        opened_at="2026-06-29T07:46:00Z",
        status="closed",
        repo_visibility_restored_at="2026-06-29T08:06:00Z",
        branch_deleted=True,
        runner=_runner(calls),
        observed_at=observed_at,
    )

    assert validate_window_receipt(receipt, observed_at=observed_at) == []
    assert receipt["status"] == "closed"
    assert receipt["merge_commit"] == "ba07975fc10c2aa7ec8f1506aa6652245d1be96c"
    assert receipt["closed_at"] == "2026-06-29T08:07:42Z"
    assert receipt["window_id"] == "foundation_public_ci_window.20260629.pr2400"
    assert calls[0][:3] == ["gh", "pr", "view"]
    assert calls[1][:3] == ["gh", "run", "list"]
    assert all("--visibility" not in call for call in calls)


def test_prefill_public_ci_window_receipt_builds_bounded_receipt() -> None:
    calls: list[list[str]] = []
    observed_at = datetime(2026, 6, 29, 9, 0, 0, tzinfo=timezone.utc)
    receipt = prefill_public_ci_window_receipt(
        pull_request="2400",
        opened_at="2026-06-29T07:46:00Z",
        status="bounded_public_awaiting_evidence",
        repo_visibility_restored_at="2026-06-29T08:06:00Z",
        branch_deleted=True,
        observed_at=observed_at,
        runner=_runner(calls),
    )

    assert validate_window_receipt(receipt, observed_at=observed_at) == []
    assert receipt["status"] == "bounded_public_awaiting_evidence"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["merge_commit"] is None
    assert receipt["repo_visibility_restored"] is False
    assert receipt["branch_deleted"] is False
    assert all(validator["state"] == "AwaitingEvidence" for validator in receipt["validators"])


def test_prefill_public_ci_window_receipt_requires_restoration_for_closed() -> None:
    try:
        prefill_public_ci_window_receipt(
            pull_request="2400",
            opened_at="2026-06-29T07:46:00Z",
            status="closed",
            branch_deleted=True,
            runner=_runner([]),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "closed receipt prefill requires operator-supplied repo_visibility_restored_at"
    assert "ba07975fc10c2aa7ec8f1506aa6652245d1be96c" not in message


def test_prefill_public_ci_window_receipt_rejects_missing_workflow_runs() -> None:
    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command = list(argv)
        if command[:3] == ["gh", "pr", "view"]:
            return _runner([])(argv)
        if command[:3] == ["gh", "run", "list"]:
            return _completed(command, [])
        return _completed(command, {}, returncode=1)

    try:
        prefill_public_ci_window_receipt(
            pull_request="2400",
            opened_at="2026-06-29T07:46:00Z",
            status="bounded_public_awaiting_evidence",
            runner=runner,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "expected exactly two successful workflow runs for the pull request branch and head SHA"
    assert "2400" not in message
    assert "fdf0e278a19e483f0461a0d251e7365ca69cb3ec" not in message


def test_prefill_public_ci_window_receipt_rejects_failed_gh_query() -> None:
    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(argv), 1, stdout="", stderr="private gh failure")

    try:
        fetch_pull_request_metadata("2400", runner=runner)
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "GitHub metadata query failed"
    assert "private gh failure" not in message
    assert "2400" not in message


def test_prefill_public_ci_window_receipt_rejects_secret_shaped_metadata() -> None:
    def runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return _completed(
            argv,
            {
                "url": "https://github.com/tamirat-wubie/mullu-control-plane/pull/2400",
                "headRefName": "codex/client_secret-branch",
                "headRefOid": "fdf0e278a19e483f0461a0d251e7365ca69cb3ec",
            },
        )

    try:
        fetch_pull_request_metadata("2400", runner=runner)
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "pull request metadata must not contain raw secret-shaped text"
    assert "client_secret-branch" not in message
    assert "fdf0e278a19e483f0461a0d251e7365ca69cb3ec" not in message


def test_fetch_workflow_run_urls_filters_branch_sha_and_success() -> None:
    calls: list[list[str]] = []
    urls = fetch_workflow_run_urls(
        branch="codex/public-ci-window-receipt-builder-20260629",
        head_sha="fdf0e278a19e483f0461a0d251e7365ca69cb3ec",
        runner=_runner(calls),
    )

    assert urls == [
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28357014460",
        "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28357033319",
    ]
    assert calls[0][0:3] == ["gh", "run", "list"]
    assert "--branch" in calls[0]


def test_prefill_public_ci_window_receipt_cli_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "receipt.json"
    monkeypatch.setattr("scripts.prefill_public_ci_window_receipt._run_command", _runner([]))

    exit_code = main(
        [
            "--pull-request",
            "2400",
            "--opened-at",
            "2026-06-29T07:46:00Z",
            "--status",
            "closed",
            "--repo-visibility-restored-at",
            "2026-06-29T08:06:00Z",
            "--branch-deleted",
            "--output",
            str(output_path),
        ]
    )
    streams = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "[PASS] public_ci_window_receipt_prefill" in streams.out
    assert "STATUS: passed" in streams.out
    assert streams.err == ""
    assert validate_window_receipt(payload) == []
