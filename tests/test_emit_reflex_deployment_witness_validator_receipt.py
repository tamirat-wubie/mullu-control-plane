"""Tests for Reflex deployment witness validator receipt emission.

Purpose: prove CI validator receipts bind JUnit evidence, schema evidence, and
validator evidence before release publication.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.emit_reflex_deployment_witness_validator_receipt.
Invariants:
  - Passing JUnit produces a passed JSON receipt.
  - JUnit failures or missing JUnit fail closed.
  - Receipt identity is stable for the same JUnit evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.emit_reflex_deployment_witness_validator_receipt import (
    build_reflex_deployment_witness_validator_receipt,
    main,
)


DT = "2026-05-04T12:00:00+00:00"


def test_reflex_validator_receipt_accepts_passing_junit(tmp_path: Path) -> None:
    junit_path = _write_junit(tmp_path / "passed.xml")

    receipt = build_reflex_deployment_witness_validator_receipt(
        junit_path=junit_path,
        generated_at=DT,
    )

    assert receipt.status == "passed"
    assert receipt.receipt_id.startswith("reflex-witness-validator-receipt-")
    assert receipt.test_count == 8
    assert receipt.failure_count == 0
    assert receipt.error_count == 0
    assert receipt.blockers == ()
    assert "schema:schemas/reflex_deployment_witness_envelope.schema.json" in receipt.evidence_refs


def test_reflex_validator_receipt_rejects_failed_junit(tmp_path: Path) -> None:
    junit_path = _write_junit(tmp_path / "failed.xml", failures=1)

    receipt = build_reflex_deployment_witness_validator_receipt(
        junit_path=junit_path,
        generated_at=DT,
    )

    assert receipt.status == "failed"
    assert receipt.failure_count == 1
    assert "junit_failures_present" in receipt.blockers
    assert receipt.junit_sha256
    assert receipt.junit_path == "provided-reflex-validator-junit"


def test_reflex_validator_receipt_rejects_missing_junit(tmp_path: Path) -> None:
    receipt = build_reflex_deployment_witness_validator_receipt(
        junit_path=tmp_path / "secret-junit-path.xml",
        generated_at=DT,
    )
    serialized = json.dumps(receipt.to_json_dict(), sort_keys=True)

    assert receipt.status == "failed"
    assert receipt.junit_sha256 == ""
    assert "junit_missing" in receipt.blockers
    assert receipt.test_count == 0
    assert "secret-junit-path" not in serialized


def test_reflex_validator_receipt_cli_writes_json(tmp_path: Path, capsys) -> None:
    junit_path = _write_junit(tmp_path / "cli.xml")
    output_path = tmp_path / "receipt.json"

    exit_code = main(
        [
            "--junit",
            str(junit_path),
            "--output",
            str(output_path),
            "--generated-at",
            DT,
            "--json",
        ]
    )
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload == file_payload
    assert file_payload["status"] == "passed"
    assert file_payload["generated_at"] == DT
    assert file_payload["blockers"] == []


def _write_junit(path: Path, *, failures: int = 0, errors: int = 0) -> Path:
    path.write_text(
        (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<testsuite name="pytest" errors="{errors}" failures="{failures}" '
            'skipped="0" tests="8" time="0.1"></testsuite>'
        ),
        encoding="utf-8",
    )
    return path
