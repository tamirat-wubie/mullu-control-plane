"""Offline OrgOS event-log verifier tests.

Purpose: verify signed OrgOS event logs can be checked outside the live gateway.
Governance scope: schema gating, hash-chain replay, receipt-signature checking,
    and optional trust-ledger artifact export.
Dependencies: scripts.verify_orgos_event_log and gateway.orgos_kernel.
Invariants:
  - Valid logs verify and emit a non-terminal trust-ledger artifact.
  - Payload mutation is detected by receipt/event replay.
  - Wrong signing secrets fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gateway.orgos_kernel import JsonlOrgCaseEventLog, OrgCaseEventReceiptConfig
from scripts.validate_schemas import _load_schema, _validate_schema_instance
from scripts.verify_orgos_event_log import main, verify_orgos_event_log_file


NOW = "2026-05-05T12:00:00+00:00"
REPORT_SCHEMA_PATH = Path("schemas/orgos_case_event_log_verification_report.schema.json")


def test_verify_orgos_event_log_file_accepts_valid_log(tmp_path: Path) -> None:
    event_log_path = _write_event_log(tmp_path)

    report = verify_orgos_event_log_file(
        event_log_path=event_log_path,
        signing_secret="orgos-secret",
    )

    assert report["valid"] is True
    assert report["reason"] == "verified"
    assert report["schema_valid"] is True
    assert report["schema_errors"] == []
    assert report["verification_errors"] == []
    assert report["event_count"] == 2
    assert report["first_event_id"] == "orgos-event-1"
    assert report["latest_event_id"] == "orgos-event-2"
    assert report["latest_event_hash"]
    assert report["latest_receipt_id"].startswith("orgos-event-receipt-")
    assert report["signature_key_ids"] == ["orgos-event-test"]
    assert report["anchor_statuses"] == ["not_requested"]
    assert report["trust_ledger_artifact"]["artifact_type"] == "orgos_event_receipt"
    assert report["trust_ledger_artifact"]["required"] is False
    _assert_report_schema(report)


def test_verify_orgos_event_log_file_detects_payload_tamper(tmp_path: Path) -> None:
    event_log_path = _write_event_log(tmp_path)
    lines = event_log_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload"]["status"] = "mutated-after-receipt"
    lines[0] = json.dumps(first, sort_keys=True, separators=(",", ":"))
    event_log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = verify_orgos_event_log_file(
        event_log_path=event_log_path,
        signing_secret="orgos-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "event_log_verification_failed"
    assert report["schema_valid"] is True
    assert report["schema_errors"] == []
    assert report["verification_errors"]
    assert report["trust_ledger_artifact"] is None
    _assert_report_schema(report)


def test_verify_orgos_event_log_file_rejects_wrong_secret(tmp_path: Path) -> None:
    event_log_path = _write_event_log(tmp_path)

    report = verify_orgos_event_log_file(
        event_log_path=event_log_path,
        signing_secret="wrong-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "event_log_verification_failed"
    assert report["schema_valid"] is True
    assert any("receipt signature" in error for error in report["verification_errors"])
    assert report["event_count"] == 0
    _assert_report_schema(report)


def test_verify_orgos_event_log_file_rejects_schema_invalid_event(tmp_path: Path) -> None:
    event_log_path = _write_event_log(tmp_path)
    first = json.loads(event_log_path.read_text(encoding="utf-8").splitlines()[0])
    first.pop("receipt")
    event_log_path.write_text(json.dumps(first), encoding="utf-8")

    report = verify_orgos_event_log_file(
        event_log_path=event_log_path,
        signing_secret="orgos-secret",
    )

    assert report["valid"] is False
    assert report["reason"] == "schema_validation_failed"
    assert report["schema_valid"] is False
    assert any("receipt" in error for error in report["schema_errors"])
    assert report["verification_errors"] == []
    _assert_report_schema(report)


def test_verify_orgos_event_log_cli_reports_valid_json(tmp_path: Path, capsys: Any) -> None:
    event_log_path = _write_event_log(tmp_path)

    exit_code = main([
        "--event-log",
        str(event_log_path),
        "--signing-secret",
        "orgos-secret",
        "--json",
    ])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["valid"] is True
    assert output["latest_event_id"] == "orgos-event-2"
    assert output["trust_ledger_artifact"]["metadata"]["event_receipt_is_not_terminal_closure"] is True
    _assert_report_schema(output)


def _write_event_log(tmp_path: Path) -> Path:
    event_log_path = tmp_path / "orgos-events.jsonl"
    log = JsonlOrgCaseEventLog(
        event_log_path,
        clock=lambda: NOW,
        receipt_config=OrgCaseEventReceiptConfig(
            signing_secret="orgos-secret",
            signature_key_id="orgos-event-test",
            lock_timeout_seconds=1.0,
            stale_lock_seconds=1.0,
        ),
    )
    log.record(
        case_id="case-launch-gateway",
        tenant_id="tenant-a",
        event_type="case_opened",
        actor_id="engineering_owner",
        payload={"status": "open"},
        evidence_refs=("case:intake:launch-gateway",),
    )
    log.record(
        case_id="case-launch-gateway",
        tenant_id="tenant-a",
        event_type="evidence_added",
        actor_id="engineering_owner",
        payload={"evidence_ref": "world:runtime-target-bound"},
        evidence_refs=("world:runtime-target-bound",),
    )
    return event_log_path


def _assert_report_schema(report: dict[str, Any]) -> None:
    errors = _validate_schema_instance(_load_schema(REPORT_SCHEMA_PATH), report)
    assert errors == []
