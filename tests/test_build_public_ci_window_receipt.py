"""Tests for the public CI window receipt builder.

Purpose: prove generated receipts match the Foundation public CI window
boundary contract without mutating repository visibility.
Governance scope: public CI closure, bounded-public AwaitingEvidence, branch
cleanup, workflow run evidence, and public-readiness separation.
Dependencies: scripts.build_public_ci_window_receipt and
scripts.validate_foundation_public_ci_window_boundary.
Invariants: closed receipts require restoration evidence; bounded receipts do
not claim closure; secret-shaped input is rejected without echoing raw values.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_public_ci_window_receipt import (  # noqa: E402
    build_public_ci_window_receipt,
    main,
    write_public_ci_window_receipt,
)
from scripts.validate_foundation_public_ci_window_boundary import validate_window_receipt  # noqa: E402


def _closed_receipt() -> dict[str, object]:
    return build_public_ci_window_receipt(
        pull_request="2391",
        branch="codex/public-ci-window-command-packet-fixture-20260629",
        head_sha="f6daa95ea7d45f8669401120411b191c6372903a",
        opened_at="2026-06-29T06:46:05Z",
        workflow_run_urls=[
            "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355217313",
            "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355219685",
        ],
        status="closed",
        closed_at="2026-06-29T07:32:49Z",
        merged_at="2026-06-29T07:32:49Z",
        merge_commit="a6b99615fc22f861b08369c2045658d5a04564c3",
        repo_visibility_restored_at="2026-06-29T07:31:00Z",
        branch_deleted=True,
    )


def _recent_utc_timestamp() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_public_ci_window_receipt_builder_closed_receipt_passes() -> None:
    receipt = _closed_receipt()

    assert validate_window_receipt(receipt) == []
    assert receipt["status"] == "closed"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert receipt["repo_visibility_restored"] is True
    assert receipt["branch_deleted"] is True
    assert receipt["window_id"] == "foundation_public_ci_window.20260629.pr2391"


def test_public_ci_window_receipt_builder_bounded_receipt_passes() -> None:
    opened_at = _recent_utc_timestamp()

    receipt = build_public_ci_window_receipt(
        pull_request="2391",
        branch="codex/public-ci-window-command-packet-fixture-20260629",
        head_sha="f6daa95ea7d45f8669401120411b191c6372903a",
        opened_at=opened_at,
        workflow_run_urls=[
            "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355217313",
            "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355219685",
        ],
        status="bounded_public_awaiting_evidence",
        closed_at="2026-06-29T07:32:49Z",
        merged_at="2026-06-29T07:32:49Z",
        merge_commit="a6b99615fc22f861b08369c2045658d5a04564c3",
        repo_visibility_restored_at="2026-06-29T07:31:00Z",
        branch_deleted=True,
    )

    assert validate_window_receipt(receipt) == []
    assert receipt["opened_at"] == opened_at
    assert receipt["status"] == "bounded_public_awaiting_evidence"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["repo_visibility_restored"] is False
    assert receipt["branch_deleted"] is False
    assert receipt["closed_at"] is None
    assert all(validator["state"] == "AwaitingEvidence" for validator in receipt["validators"])


def test_public_ci_window_receipt_builder_rejects_closed_without_restoration() -> None:
    try:
        build_public_ci_window_receipt(
            pull_request="2391",
            branch="codex/public-ci-window-command-packet-fixture-20260629",
            head_sha="f6daa95ea7d45f8669401120411b191c6372903a",
            opened_at="2026-06-29T06:46:05Z",
            workflow_run_urls=[
                "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355217313",
                "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355219685",
            ],
            status="closed",
            closed_at="2026-06-29T07:32:49Z",
            merged_at="2026-06-29T07:32:49Z",
            merge_commit="a6b99615fc22f861b08369c2045658d5a04564c3",
            branch_deleted=True,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "closed receipts require closed_at, merged_at, merge_commit, and repo_visibility_restored_at"
    assert "a6b99615fc22f861b08369c2045658d5a04564c3" not in message
    assert "28355217313" not in message


def test_public_ci_window_receipt_builder_rejects_invalid_workflow_url() -> None:
    try:
        build_public_ci_window_receipt(
            pull_request="2391",
            branch="codex/public-ci-window-command-packet-fixture-20260629",
            head_sha="f6daa95ea7d45f8669401120411b191c6372903a",
            opened_at="2026-06-29T06:46:05Z",
            workflow_run_urls=[
                "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355217313/job/83996512775",
                "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355219685",
            ],
            status="bounded_public_awaiting_evidence",
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "workflow_run_urls must be exact repository GitHub Actions run URLs"
    assert "83996512775" not in message
    assert "28355219685" not in message


def test_public_ci_window_receipt_builder_rejects_secret_shaped_input() -> None:
    try:
        build_public_ci_window_receipt(
            pull_request="2391",
            branch="codex/client_secret-branch",
            head_sha="f6daa95ea7d45f8669401120411b191c6372903a",
            opened_at="2026-06-29T06:46:05Z",
            workflow_run_urls=[
                "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355217313",
                "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355219685",
            ],
            status="bounded_public_awaiting_evidence",
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "receipt inputs must not contain raw secret-shaped text"
    assert "client_secret-branch" not in message
    assert "f6daa95ea7d45f8669401120411b191c6372903a" not in message


def test_public_ci_window_receipt_builder_writes_receipt(tmp_path: Path) -> None:
    receipt = _closed_receipt()
    output_path = tmp_path / "public-ci-window-2391-receipt.json"

    written_path = write_public_ci_window_receipt(receipt, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert written_path == output_path
    assert written_payload == receipt
    assert validate_window_receipt(written_payload) == []
    assert written_payload["pull_request"].endswith("/2391")


def test_public_ci_window_receipt_builder_cli_passes(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "receipt.json"

    exit_code = main(
        [
            "--pull-request",
            "2391",
            "--branch",
            "codex/public-ci-window-command-packet-fixture-20260629",
            "--head-sha",
            "f6daa95ea7d45f8669401120411b191c6372903a",
            "--opened-at",
            "2026-06-29T06:46:05Z",
            "--workflow-run-url",
            "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355217313",
            "--workflow-run-url",
            "https://github.com/tamirat-wubie/mullu-control-plane/actions/runs/28355219685",
            "--status",
            "closed",
            "--closed-at",
            "2026-06-29T07:32:49Z",
            "--merged-at",
            "2026-06-29T07:32:49Z",
            "--merge-commit",
            "a6b99615fc22f861b08369c2045658d5a04564c3",
            "--repo-visibility-restored-at",
            "2026-06-29T07:31:00Z",
            "--branch-deleted",
            "--output",
            str(output_path),
        ]
    )
    streams = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "[PASS] public_ci_window_receipt_builder" in streams.out
    assert "STATUS: passed" in streams.out
    assert streams.err == ""
    assert validate_window_receipt(payload) == []
