"""Tests for gateway DNS resolution receipt validation.

Purpose: prove DNS resolution receipts are schema-backed deployment gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_gateway_dns_resolution_receipt.
Invariants:
  - Public schema accepts both resolved and unresolved bounded receipts.
  - Optional require-resolved policy fails closed for unresolved DNS.
  - Validation reports carry bounded path, id, state, and step details.
"""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path

from scripts.collect_gateway_dns_resolution_receipt import (
    collect_gateway_dns_resolution_receipt,
    write_gateway_dns_resolution_receipt,
)
from scripts.validate_gateway_dns_resolution_receipt import (
    GATEWAY_DNS_RECEIPT_SCHEMA_PATH,
    UNRESOLVED_NEXT_ACTION,
    main,
    validate_gateway_dns_resolution_receipt,
    write_gateway_dns_resolution_validation_report,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


FIXED_NOW = datetime(2026, 5, 24, 16, 30, tzinfo=UTC)


def test_gateway_dns_resolution_receipt_matches_public_schema(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    receipt = collect_gateway_dns_resolution_receipt(
        host="api.mullusi.com",
        resolver=lambda host: ((socket.AF_INET, "203.0.113.10"),),
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_resolution_receipt(receipt, receipt_path)
    schema = _load_schema(GATEWAY_DNS_RECEIPT_SCHEMA_PATH)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))

    errors = _validate_schema_instance(schema, payload)

    assert errors == []
    assert payload["resolved"] is True
    assert payload["addresses"] == ["203.0.113.10"]
    assert payload["error"] is None
    assert payload["next_action"] == "rerun deployment witness preflight with endpoint probes enabled"


def test_gateway_dns_receipt_validation_report_writes_bounded_result(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    validation_path = tmp_path / "gateway_dns_resolution_receipt_validation.json"
    receipt = collect_gateway_dns_resolution_receipt(
        host="api.mullusi.com",
        resolver=lambda host: ((socket.AF_INET6, "2001:db8::10"),),
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_resolution_receipt(receipt, receipt_path)

    validation = validate_gateway_dns_resolution_receipt(
        receipt_path=receipt_path,
        require_resolved=True,
    )
    write_gateway_dns_resolution_validation_report(validation, validation_path)
    payload = json.loads(validation_path.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.resolved is True
    assert validation.address_count == 1
    assert payload["receipt_path"] == "provided_receipt"
    assert _step(validation, "require resolved").passed is True
    assert _step(validation, "schema contract").detail == "valid"


def test_gateway_dns_receipt_validation_accepts_unresolved_receipt(tmp_path: Path) -> None:
    def resolver(host: str) -> tuple[tuple[int, str], ...]:
        raise socket.gaierror("private resolver detail")

    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    receipt = collect_gateway_dns_resolution_receipt(
        host="api.mullusi.com",
        resolver=resolver,
        now_utc=FIXED_NOW,
    )
    write_gateway_dns_resolution_receipt(receipt, receipt_path)

    validation = validate_gateway_dns_resolution_receipt(receipt_path=receipt_path)

    assert validation.valid is True
    assert validation.resolved is False
    assert validation.address_count == 0
    assert validation.receipt_id.startswith("gateway-dns-resolution-")
    assert _step(validation, "resolution state").passed is True
    assert _step(validation, "require resolved").detail == "not-required"


def test_gateway_dns_receipt_validation_can_require_resolved_dns(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    payload = _unresolved_payload()
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_gateway_dns_resolution_receipt(
        receipt_path=receipt_path,
        require_resolved=True,
    )

    assert validation.valid is False
    assert validation.resolved is False
    assert validation.address_count == 0
    assert _step(validation, "schema contract").passed is True
    assert _step(validation, "require resolved").passed is False
    assert _step(validation, "require resolved").detail == "unresolved"


def test_gateway_dns_receipt_validation_rejects_drifted_next_action(tmp_path: Path) -> None:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    payload = _unresolved_payload()
    payload["next_action"] = "try again later"
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    validation = validate_gateway_dns_resolution_receipt(receipt_path=receipt_path)

    assert validation.valid is False
    assert validation.resolved is False
    assert _step(validation, "schema contract").passed is False
    assert _step(validation, "next action").passed is False
    assert _step(validation, "next action").detail == "mismatched"


def test_gateway_dns_receipt_validation_cli_writes_json_report(
    tmp_path: Path,
    capsys,
) -> None:
    receipt_path = tmp_path / "gateway_dns_resolution_receipt.json"
    validation_path = tmp_path / "gateway_dns_resolution_receipt_validation.json"
    payload = _unresolved_payload()
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--output",
            str(validation_path),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    stdout_report = json.loads(captured.out)

    assert exit_code == 0
    assert report["valid"] is True
    assert report["resolved"] is False
    assert stdout_report["receipt_id"] == report["receipt_id"]
    assert stdout_report["steps"] == report["steps"]
    assert captured.err == ""


def _step(validation, name: str):
    return next(step for step in validation.steps if step.name == name)


def _unresolved_payload() -> dict[str, object]:
    return {
        "addresses": [],
        "checked_at_utc": "2026-05-24T16:30:00Z",
        "error": "resolution_error",
        "host": "api.mullusi.com",
        "next_action": UNRESOLVED_NEXT_ACTION,
        "receipt_id": "gateway-dns-resolution-0123456789abcdef",
        "resolved": False,
    }
