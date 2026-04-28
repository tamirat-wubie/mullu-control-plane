"""Purpose: verify operator CLI access to software-change receipts.
Governance scope: read-only local receipt list/get/replay commands.
Dependencies: CLI entrypoint and file-backed software receipt store.
Invariants:
  - CLI reads receipt files without mutating them.
  - List/get/replay emit bounded deterministic envelopes.
  - Replay fails closed when the receipt chain is not terminal.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcoi_runtime.app.cli import main
from mcoi_runtime.contracts.software_dev_loop import (
    SoftwareChangeReceipt,
    SoftwareChangeReceiptStage,
)
from mcoi_runtime.persistence.software_change_receipt_store import (
    FileSoftwareChangeReceiptStore,
)


T0 = "2025-01-15T10:00:00+00:00"
T1 = "2025-01-15T10:00:05+00:00"


def _receipt(
    *,
    receipt_id: str,
    request_id: str = "request-cli-1",
    stage: SoftwareChangeReceiptStage = SoftwareChangeReceiptStage.REQUEST_ADMITTED,
    created_at: str = T0,
) -> SoftwareChangeReceipt:
    return SoftwareChangeReceipt(
        receipt_id=receipt_id,
        request_id=request_id,
        stage=stage,
        cause=f"{stage.value} cause",
        outcome="ok",
        target_refs=(f"target:{stage.value}",),
        constraint_refs=("constraint:software_change_lifecycle_v1",),
        evidence_refs=(f"evidence:{stage.value}",),
        created_at=created_at,
        metadata={"stage": stage.value},
    )


def _store_path(tmp_path: Path) -> Path:
    path = tmp_path / "software_receipts.json"
    store = FileSoftwareChangeReceiptStore(path)
    store.append_many(
        (
            _receipt(receipt_id="receipt-admitted"),
            _receipt(
                receipt_id="receipt-terminal",
                stage=SoftwareChangeReceiptStage.TERMINAL_CLOSED,
                created_at=T1,
            ),
            _receipt(receipt_id="receipt-other", request_id="request-cli-2"),
        )
    )
    return path


def test_cli_lists_receipts_with_stage_filter_json(tmp_path: Path, capsys) -> None:
    path = _store_path(tmp_path)

    rc = main([
        "software-receipts",
        "list",
        "--store",
        str(path),
        "--request-id",
        "request-cli-1",
        "--stage",
        "terminal_closed",
        "--json",
    ])
    body = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert body["operation"] == "list"
    assert body["count"] == 1
    assert body["receipts"][0]["receipt_id"] == "receipt-terminal"
    assert body["stage"] == "terminal_closed"


def test_cli_gets_receipt_and_reports_missing(tmp_path: Path, capsys) -> None:
    path = _store_path(tmp_path)

    found_rc = main([
        "software-receipts",
        "get",
        "receipt-admitted",
        "--store",
        str(path),
    ])
    found_out = capsys.readouterr().out
    missing_rc = main([
        "software-receipts",
        "get",
        "missing-receipt",
        "--store",
        str(path),
    ])
    missing_out = capsys.readouterr().out

    assert found_rc == 0
    assert "operation: get" in found_out
    assert "found: true" in found_out
    assert "receipt-admitted" in found_out
    assert missing_rc == 0
    assert "found: false" in missing_out
    assert "count: 0" in missing_out


def test_cli_replays_terminal_receipt_chain(tmp_path: Path, capsys) -> None:
    path = _store_path(tmp_path)

    rc = main([
        "software-receipts",
        "replay",
        "request-cli-1",
        "--store",
        str(path),
        "--json",
    ])
    body = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert body["operation"] == "replay"
    assert body["terminal_closed"] is True
    assert body["count"] == 2
    assert [receipt["receipt_id"] for receipt in body["receipts"]] == [
        "receipt-admitted",
        "receipt-terminal",
    ]


def test_cli_replay_fails_closed_for_non_terminal_chain(tmp_path: Path, capsys) -> None:
    path = tmp_path / "software_receipts.json"
    FileSoftwareChangeReceiptStore(path).append(
        _receipt(receipt_id="receipt-open", request_id="request-open")
    )

    rc = main([
        "software-receipts",
        "replay",
        "request-open",
        "--store",
        str(path),
    ])
    out = capsys.readouterr().out

    assert rc == 1
    assert "error:" in out
    assert "software receipt store rejected request" in out
    assert "PersistenceError" in out


def test_cli_requires_store_path(capsys) -> None:
    rc = main(["software-receipts", "list"])
    out = capsys.readouterr().out

    assert rc == 1
    assert "error:" in out
    assert "invalid software receipt argument" in out


def test_cli_rejects_missing_store_path(tmp_path: Path, capsys) -> None:
    rc = main([
        "software-receipts",
        "list",
        "--store",
        str(tmp_path / "missing.json"),
    ])
    out = capsys.readouterr().out

    assert rc == 1
    assert "error:" in out
    assert "software receipt store access failed" in out
    assert "FileNotFoundError" in out
