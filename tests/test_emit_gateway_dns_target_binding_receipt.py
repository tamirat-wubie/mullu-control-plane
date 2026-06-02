"""Tests for gateway DNS target binding receipt emission.

Purpose: prove gateway DNS origin-target evidence is recorded without DNS or
workflow mutation.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.emit_gateway_dns_target_binding_receipt.
Invariants:
  - Ready binding requires record type, target, provider, host, and URL.
  - Missing target produces a bounded blocked receipt.
  - Invalid URL or target shape is rejected before serialization.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.emit_gateway_dns_target_binding_receipt import (  # noqa: E402
    emit_gateway_dns_target_binding_receipt,
    main,
    write_gateway_dns_target_binding_receipt,
)


FIXED_NOW = datetime(2026, 5, 24, 17, 20, tzinfo=UTC)


def test_gateway_dns_target_binding_records_ready_a_record(tmp_path: Path) -> None:
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="API.MULLUSI.COM",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="a",
        target="203.0.113.10",
        provider="Cloudflare",
        now_utc=FIXED_NOW,
    )
    output_path = tmp_path / "target_binding.json"
    written = write_gateway_dns_target_binding_receipt(receipt, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert written == output_path
    assert receipt.gateway_host == "api.mullusi.com"
    assert receipt.gateway_url == "https://api.mullusi.com"
    assert receipt.ready is True
    assert receipt.record_type == "A"
    assert receipt.target_kind == "ipv4"
    assert receipt.binding_state == "bound"
    assert receipt.checked_at_utc == "2026-05-24T17:20:00Z"
    assert payload["receipt_id"].startswith("gateway-dns-target-binding-")


def test_gateway_dns_target_binding_records_missing_target(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_path = tmp_path / "target_binding.json"

    exit_code = main(
        [
            "--gateway-host",
            "api.mullusi.com",
            "--gateway-url",
            "https://api.mullusi.com",
            "--expected-environment",
            "pilot",
            "--output",
            str(output_path),
            "--json",
        ],
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    stdout_payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["ready"] is False
    assert payload["binding_state"] == "missing-target"
    assert payload["target"] == ""
    assert payload["target_kind"] == "missing"
    assert stdout_payload["receipt_id"] == payload["receipt_id"]
    assert captured.err == ""


def test_gateway_dns_target_binding_cli_rejects_invalid_target_without_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "target_binding.json"

    exit_code = main(
        [
            "--gateway-host",
            "api.mullusi.com",
            "--gateway-url",
            "https://api.mullusi.com",
            "--expected-environment",
            "pilot",
            "--record-type",
            "A",
            "--target",
            "not-an-address.example",
            "--provider",
            "Cloudflare",
            "--output",
            str(output_path),
            "--json",
        ],
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)

    assert exit_code == 1
    assert not output_path.exists()
    assert stdout_payload["status"] == "failed"
    assert stdout_payload["ready"] is False
    assert stdout_payload["receipt_written"] is False
    assert stdout_payload["error"] == "A record target must be an IPv4 address"
    assert "not-an-address.example" not in captured.out
    assert "Traceback" not in captured.out
    assert captured.err == ""


def test_gateway_dns_target_binding_cli_json_bounds_missing_target_identity(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["--json"], now_utc=FIXED_NOW)
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)

    assert exit_code == 1
    assert stdout_payload["status"] == "failed"
    assert stdout_payload["ready"] is False
    assert stdout_payload["receipt_written"] is False
    assert stdout_payload["error"] == "gateway host or gateway URL is required"
    assert "Traceback" not in captured.out
    assert captured.err == ""


def test_gateway_dns_target_binding_cli_human_bounds_invalid_host(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_path = tmp_path / "target_binding.json"

    exit_code = main(
        [
            "--gateway-host",
            "https://api.mullusi.com",
            "--gateway-url",
            "https://api.mullusi.com",
            "--expected-environment",
            "pilot",
            "--record-type",
            "A",
            "--target",
            "203.0.113.10",
            "--provider",
            "Cloudflare",
            "--output",
            str(output_path),
        ],
        now_utc=FIXED_NOW,
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert not output_path.exists()
    assert captured.out == ""
    assert "gateway DNS target binding receipt emission failed" in captured.err
    assert "gateway host must not include URL scheme" in captured.err
    assert "https://api.mullusi.com" not in captured.err
    assert "Traceback" not in captured.err


def test_gateway_dns_target_binding_rejects_url_host_mismatch() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        emit_gateway_dns_target_binding_receipt(
            gateway_host="api.mullusi.com",
            gateway_url="https://gateway.mullusi.com",
            expected_environment="pilot",
            record_type="CNAME",
            target="origin.mullusi.net",
            provider="Cloudflare",
            now_utc=FIXED_NOW,
        )

    assert "gateway URL host must match gateway host" in str(excinfo.value)
    assert "origin.mullusi.net" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).casefold()


def test_gateway_dns_target_binding_rejects_wrong_record_target_family() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        emit_gateway_dns_target_binding_receipt(
            gateway_host="api.mullusi.com",
            gateway_url="https://api.mullusi.com",
            expected_environment="pilot",
            record_type="AAAA",
            target="203.0.113.10",
            provider="Cloudflare",
            now_utc=FIXED_NOW,
        )

    assert "AAAA record target must be an IPv6 address" in str(excinfo.value)
    assert "203.0.113.10" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).casefold()


def test_gateway_dns_target_binding_rejects_malformed_a_record_without_echoing_target() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        emit_gateway_dns_target_binding_receipt(
            gateway_host="api.mullusi.com",
            gateway_url="https://api.mullusi.com",
            expected_environment="pilot",
            record_type="A",
            target="not-an-address.example",
            provider="Cloudflare",
            now_utc=FIXED_NOW,
        )

    assert "A record target must be an IPv4 address" in str(excinfo.value)
    assert "not-an-address.example" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).casefold()


def test_gateway_dns_target_binding_rejects_cname_ip_literal() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        emit_gateway_dns_target_binding_receipt(
            gateway_host="api.mullusi.com",
            gateway_url="https://api.mullusi.com",
            expected_environment="pilot",
            record_type="CNAME",
            target="203.0.113.10",
            provider="Cloudflare",
            now_utc=FIXED_NOW,
        )

    assert "CNAME record target must be a hostname" in str(excinfo.value)
    assert "203.0.113.10" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).casefold()


def test_gateway_dns_target_binding_rejects_invalid_dns_label_shape() -> None:
    with pytest.raises(RuntimeError) as excinfo:
        emit_gateway_dns_target_binding_receipt(
            gateway_host="api..mullusi.com",
            gateway_url="https://api..mullusi.com",
            expected_environment="pilot",
            record_type="CNAME",
            target="origin.mullusi.net",
            provider="Cloudflare",
            now_utc=FIXED_NOW,
        )

    assert "gateway host contains invalid DNS characters" in str(excinfo.value)
    assert "api..mullusi.com" not in str(excinfo.value)
    assert "secret" not in str(excinfo.value).casefold()
