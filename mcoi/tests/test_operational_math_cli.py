"""Tests for the operational mathematics CLI receipt surface."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout

from mcoi_runtime.app.operational_math_cli import main


FIXED_TS = "2026-05-18T12:00:00+00:00"


def _run_cli(*args: str) -> tuple[int, str, str]:
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
        exit_code = main(list(args))
    return exit_code, stdout_buffer.getvalue(), stderr_buffer.getvalue()


def test_operational_math_cli_emits_saturated_receipt() -> None:
    exit_code, stdout_text, stderr_text = _run_cli("--timestamp", FIXED_TS)
    receipt = json.loads(stdout_text)

    assert exit_code == 0
    assert stderr_text == ""
    assert receipt["status"] == "passed"
    assert receipt["solver_outcome"] == "SolvedVerified"
    assert receipt["target_id"] == "mullu-core-math"
    assert receipt["iteration_count"] == 10
    assert receipt["event_count"] == 11
    assert receipt["unresolved_principle_ids"] == []
    assert receipt["result"]["started_at"] == FIXED_TS
    assert receipt["result"]["completed_at"] == FIXED_TS


def test_operational_math_cli_reports_bounded_incomplete_receipt() -> None:
    exit_code, stdout_text, stderr_text = _run_cli(
        "--timestamp",
        FIXED_TS,
        "--target-id",
        "bounded-math",
        "--max-iterations",
        "2",
    )
    receipt = json.loads(stdout_text)

    assert exit_code == 1
    assert stderr_text == ""
    assert receipt["status"] == "failed"
    assert receipt["solver_outcome"] == "AwaitingEvidence"
    assert receipt["target_id"] == "bounded-math"
    assert receipt["iteration_count"] == 2
    assert receipt["event_count"] == 3
    assert receipt["applied_principle_ids"] == ["F1", "F2"]
    assert receipt["unresolved_principle_ids"]


def test_operational_math_cli_writes_receipt_file(tmp_path) -> None:
    receipt_path = tmp_path / "operational-math-receipt.json"

    exit_code, stdout_text, stderr_text = _run_cli(
        "--timestamp",
        FIXED_TS,
        "--receipt-path",
        str(receipt_path),
    )
    stdout_receipt = json.loads(stdout_text)
    saved_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stderr_text == ""
    assert receipt_path.is_file()
    assert saved_receipt == stdout_receipt
    assert saved_receipt["receipt_id"].startswith("operational_math_loop_receipt:")
    assert saved_receipt["status"] == "passed"


def test_operational_math_cli_appends_receipt_store(tmp_path) -> None:
    store_path = tmp_path / "operational-math-receipts.json"

    exit_code, stdout_text, stderr_text = _run_cli(
        "--timestamp",
        FIXED_TS,
        "--store-path",
        str(store_path),
    )
    receipt = json.loads(stdout_text)
    store_payload = json.loads(store_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stderr_text == ""
    assert store_path.is_file()
    assert store_payload["receipts"] == [receipt]
    assert store_payload["receipts"][0]["status"] == "passed"
    assert store_payload["receipts"][0]["solver_outcome"] == "SolvedVerified"


def test_operational_math_cli_writes_dashboard_projection(tmp_path) -> None:
    projection_path = tmp_path / "operational-math-projection.json"

    exit_code, stdout_text, stderr_text = _run_cli(
        "--timestamp",
        FIXED_TS,
        "--projection-path",
        str(projection_path),
    )
    receipt = json.loads(stdout_text)
    projection = json.loads(projection_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stderr_text == ""
    assert receipt["status"] == "passed"
    assert projection["source"] == "operational_math"
    assert projection["status"] == "passed"
    assert projection["solver_outcome"] == "SolvedVerified"
    assert projection["requires_operator_review"] is False
    assert projection["unresolved_principle_count"] == 0


def test_operational_math_cli_writes_store_backed_projection(tmp_path) -> None:
    store_path = tmp_path / "operational-math-receipts.json"
    projection_path = tmp_path / "operational-math-store-projection.json"

    exit_code, stdout_text, stderr_text = _run_cli(
        "--timestamp",
        FIXED_TS,
        "--store-path",
        str(store_path),
        "--projection-path",
        str(projection_path),
    )
    receipt = json.loads(stdout_text)
    projection = json.loads(projection_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stderr_text == ""
    assert receipt["status"] == "passed"
    assert projection["source"] == "operational_math"
    assert projection["total_receipts"] == 1
    assert projection["latest_receipt_id"] == receipt["receipt_id"]
    assert projection["passed_receipt_count"] == 1
    assert projection["requires_operator_review"] is False
    assert projection["governed"] is True


def test_operational_math_cli_rejects_invalid_receipt_suffix(tmp_path) -> None:
    exit_code, stdout_text, stderr_text = _run_cli(
        "--timestamp",
        FIXED_TS,
        "--receipt-path",
        str(tmp_path / "receipt.txt"),
    )

    assert exit_code == 1
    assert stdout_text == ""
    assert "STATUS: failed" in stderr_text
    assert "output path must use .json suffix" in stderr_text
