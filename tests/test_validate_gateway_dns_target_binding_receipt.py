"""Tests for gateway DNS target binding receipt validation.

Purpose: prove DNS target binding receipts are schema-backed publication gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_gateway_dns_target_binding_receipt.
Invariants:
  - Public schema accepts ready and blocked target-binding receipts.
  - Optional require-ready fails closed when target binding is incomplete.
  - Validation reports carry bounded receipt path, id, state, and step details.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.emit_gateway_dns_target_binding_receipt import (
    emit_gateway_dns_target_binding_receipt,
    write_gateway_dns_target_binding_receipt,
)
from scripts.validate_gateway_dns_target_binding_receipt import (
    GATEWAY_DNS_TARGET_BINDING_SCHEMA_PATH,
    main,
    validate_gateway_dns_target_binding_receipt,
    write_gateway_dns_target_binding_validation_report,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


FIXED_NOW = datetime(2026, 5, 24, 17, 20, tzinfo=UTC)


def test_gateway_dns_target_binding_receipt_matches_public_schema(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="api.mullusi.com",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="CNAME",
        target="gateway-origin.mullusi.net",
        provider="Cloudflare",
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_target_binding_receipt(receipt, receipt_path)
    schema = _load_schema(GATEWAY_DNS_TARGET_BINDING_SCHEMA_PATH)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["ready"] is True
    assert payload["binding_state"] == "bound"
    assert payload["record_type"] == "CNAME"
    assert payload["target_kind"] == "hostname"


def test_gateway_dns_target_binding_validation_report_writes_bounded_result(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    validation_path = tmp_path / "gateway_dns_target_binding_receipt_validation.json"
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="api.mullusi.com",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="A",
        target="203.0.113.10",
        provider="Cloudflare",
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_target_binding_receipt(receipt, receipt_path)

    validation = validate_gateway_dns_target_binding_receipt(
        receipt_path=receipt_path,
        require_ready=True,
        expected_gateway_host="api.mullusi.com",
        expected_gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
    )
    write_gateway_dns_target_binding_validation_report(validation, validation_path)
    payload = json.loads(validation_path.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.ready is True
    assert validation.binding_state == "bound"
    assert payload["receipt_path"] == "provided_receipt"
    assert _step(validation, "require ready").passed is True
    assert _step(validation, "expected gateway_host").detail == "matched"
    assert _step(validation, "schema contract").detail == "valid"


def test_gateway_dns_target_binding_validation_accepts_missing_target_without_ready_gate(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="api.mullusi.com",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="",
        target="",
        provider="",
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_target_binding_receipt(receipt, receipt_path)

    validation = validate_gateway_dns_target_binding_receipt(receipt_path=receipt_path)

    assert validation.valid is True
    assert validation.ready is False
    assert validation.binding_state == "missing-target"
    assert _step(validation, "target binding state").passed is True
    assert _step(validation, "require ready").detail == "not-required"


def test_gateway_dns_target_binding_validation_can_require_ready(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="api.mullusi.com",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="A",
        target="",
        provider="Cloudflare",
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_target_binding_receipt(receipt, receipt_path)

    validation = validate_gateway_dns_target_binding_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )

    assert validation.valid is False
    assert validation.ready is False
    assert validation.binding_state == "missing-target"
    assert _step(validation, "schema contract").passed is True
    assert _step(validation, "require ready").passed is False
    assert _step(validation, "require ready").detail == "not-ready"


def test_gateway_dns_target_binding_validation_rejects_drifted_next_action(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="api.mullusi.com",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="A",
        target="203.0.113.10",
        provider="Cloudflare",
        now_utc=FIXED_NOW,
    )
    payload = receipt.as_dict()
    payload["next_action"] = "publish immediately"
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_gateway_dns_target_binding_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.ready is True
    assert _step(validation, "schema contract").passed is False
    assert _step(validation, "next action").passed is False
    assert _step(validation, "next action").detail == "mismatched"


def test_gateway_dns_target_binding_validation_rejects_cname_ip_literal(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    payload = {
        "binding_state": "bound",
        "checked_at_utc": "2026-05-24T17:20:00Z",
        "expected_environment": "pilot",
        "gateway_host": "api.mullusi.com",
        "gateway_url": "https://api.mullusi.com",
        "next_action": "publish DNS record and rerun gateway DNS resolution receipt",
        "provider": "Cloudflare",
        "ready": True,
        "receipt_id": "gateway-dns-target-binding-0123456789abcdef",
        "record_type": "CNAME",
        "target": "203.0.113.10",
        "target_kind": "hostname",
    }
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_gateway_dns_target_binding_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.ready is True
    assert _step(validation, "schema contract").passed is True
    assert _step(validation, "target binding state").passed is False
    assert _step(validation, "target binding state").detail == "state=bound"


def test_gateway_dns_target_binding_validation_rejects_invalid_gateway_host_shape(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    payload = {
        "binding_state": "bound",
        "checked_at_utc": "2026-05-24T17:20:00Z",
        "expected_environment": "pilot",
        "gateway_host": "api..mullusi.com",
        "gateway_url": "https://api..mullusi.com",
        "next_action": "publish DNS record and rerun gateway DNS resolution receipt",
        "provider": "Cloudflare",
        "ready": True,
        "receipt_id": "gateway-dns-target-binding-0123456789abcdef",
        "record_type": "CNAME",
        "target": "origin.mullusi.net",
        "target_kind": "hostname",
    }
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_gateway_dns_target_binding_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.ready is True
    assert _step(validation, "gateway host shape").passed is False
    assert _step(validation, "gateway host shape").detail == "invalid"
    assert _step(validation, "target binding state").passed is True


def test_gateway_dns_target_binding_validation_cli_writes_json_report(tmp_path: Path, capsys) -> None:
    receipt_path = tmp_path / "gateway_dns_target_binding_receipt.json"
    validation_path = tmp_path / "gateway_dns_target_binding_receipt_validation.json"
    receipt = emit_gateway_dns_target_binding_receipt(
        gateway_host="api.mullusi.com",
        gateway_url="https://api.mullusi.com",
        expected_environment="pilot",
        record_type="A",
        target="203.0.113.10",
        provider="Cloudflare",
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_target_binding_receipt(receipt, receipt_path)

    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--output",
            str(validation_path),
            "--require-ready",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    stdout_report = json.loads(captured.out)

    assert exit_code == 0
    assert report["valid"] is True
    assert report["ready"] is True
    assert stdout_report["receipt_id"] == report["receipt_id"]
    assert stdout_report["steps"] == report["steps"]
    assert captured.err == ""


def _step(validation, name: str):
    return next(step for step in validation.steps if step.name == name)
