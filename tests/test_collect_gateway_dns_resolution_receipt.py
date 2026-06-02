"""Tests for gateway DNS resolution receipt collection.

Purpose: prove gateway DNS evidence is recorded without mutating deployment
state or leaking resolver exception detail.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.collect_gateway_dns_resolution_receipt.
Invariants:
  - Resolved DNS writes address evidence.
  - Unresolved DNS writes an explicit blocked receipt.
  - CLI status is non-zero only when the gateway host remains unresolved.
"""

from __future__ import annotations

import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.collect_gateway_dns_resolution_receipt import (  # noqa: E402
    collect_gateway_dns_resolution_receipt,
    main,
    write_gateway_dns_resolution_receipt,
)


FIXED_NOW = datetime(2026, 5, 24, 16, 30, tzinfo=UTC)


def test_gateway_dns_receipt_records_resolved_addresses(tmp_path: Path) -> None:
    def resolver(host: str) -> tuple[tuple[int, str], ...]:
        assert host == "api.mullusi.com"
        return (
            (socket.AF_INET, "203.0.113.10"),
            (socket.AF_INET6, "2001:db8::10"),
            (socket.AF_INET, "203.0.113.10"),
            (socket.AF_UNSPEC, ""),
        )

    receipt = collect_gateway_dns_resolution_receipt(
        host="API.MULLUSI.COM",
        resolver=resolver,
        now_utc=FIXED_NOW,
    )
    output_path = tmp_path / "dns_receipt.json"
    written = write_gateway_dns_resolution_receipt(receipt, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert receipt.host == "api.mullusi.com"
    assert receipt.resolved is True
    assert receipt.addresses == ("2001:db8::10", "203.0.113.10")
    assert receipt.error is None
    assert receipt.checked_at_utc == "2026-05-24T16:30:00Z"
    assert payload["receipt_id"].startswith("gateway-dns-resolution-")
    assert payload["next_action"] == "rerun deployment witness preflight with endpoint probes enabled"


def test_gateway_dns_receipt_bounds_resolution_errors() -> None:
    def resolver(host: str) -> tuple[tuple[int, str], ...]:
        assert host == "api.mullusi.com"
        raise socket.gaierror("private resolver detail")

    receipt = collect_gateway_dns_resolution_receipt(
        host="api.mullusi.com",
        resolver=resolver,
        now_utc=FIXED_NOW,
    )

    assert receipt.resolved is False
    assert receipt.addresses == ()
    assert receipt.error == "resolution_error"
    assert "private resolver detail" not in json.dumps(receipt.as_dict())
    assert "publish a DNS A, AAAA, or CNAME record" in receipt.next_action


def test_gateway_dns_receipt_cli_writes_unresolved_receipt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def resolver(host: str) -> tuple[tuple[int, str], ...]:
        assert host == "api.mullusi.com"
        raise socket.gaierror("not found")

    output_path = tmp_path / "dns_receipt.json"
    exit_code = main(
        [
            "--gateway-url",
            "https://api.mullusi.com",
            "--output",
            str(output_path),
            "--json",
        ],
        resolver=resolver,
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["resolved"] is False
    assert payload["error"] == "resolution_error"
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def test_gateway_dns_receipt_cli_json_bounds_missing_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "dns_receipt.json"

    exit_code = main(["--output", str(output_path), "--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["resolved"] is False
    assert payload["receipt_written"] is False
    assert payload["status"] == "failed"
    assert payload["error"] == "gateway URL must include http or https scheme and host"
    assert "Traceback" not in captured.out
    assert captured.err == ""
    assert not output_path.exists()


def test_gateway_dns_receipt_cli_human_bounds_invalid_host(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "dns_receipt.json"

    exit_code = main(
        [
            "--host",
            "https://api.mullusi.com",
            "--output",
            str(output_path),
        ],
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == "gateway DNS resolution receipt failed\n"
    assert "Traceback" not in captured.out
    assert captured.err == ""
    assert not output_path.exists()


def test_gateway_dns_receipt_rejects_placeholder_host() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        collect_gateway_dns_resolution_receipt(host="gateway.example.com", now_utc=FIXED_NOW)

    assert "replace gateway.example.com" in str(excinfo.value)
    assert "api.mullusi.com" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).casefold()
