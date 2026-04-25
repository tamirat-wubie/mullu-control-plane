"""Tests for gateway publication receipt validation.

Purpose: verify local publication receipts can be used as deterministic gates
for ready-only, blocked-not-ready, and dispatched outcomes.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: scripts.validate_gateway_publication_receipt.
Invariants:
  - Embedded readiness fields must agree with receipt fields.
  - Dispatch policy flags fail closed when receipt state is insufficient.
  - Validation writes a separate local report before returning status.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dispatch_deployment_witness import DEFAULT_REPOSITORY
from scripts.validate_gateway_publication_receipt import (
    main,
    validate_gateway_publication_receipt,
    write_receipt_validation_report,
)


def test_valid_ready_only_receipt_writes_validation_report(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    output_path = tmp_path / "validation.json"
    _write_receipt(receipt_path, resolution_state="ready-only", readiness_ready=True)

    validation = validate_gateway_publication_receipt(
        receipt_path=receipt_path,
        require_ready=True,
        expected_gateway_host="gateway.mullusi.com",
    )
    write_receipt_validation_report(validation, output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert validation.valid is True
    assert validation.resolution_state == "ready-only"
    assert payload["valid"] is True
    assert _step(validation, "require ready").passed is True
    assert _step(validation, "require dispatched").detail == "not-required"


def test_require_dispatched_fails_ready_only_receipt(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, resolution_state="ready-only", readiness_ready=True)

    validation = validate_gateway_publication_receipt(
        receipt_path=receipt_path,
        require_ready=True,
        require_dispatched=True,
    )
    dispatched_step = _step(validation, "require dispatched")

    assert validation.valid is False
    assert dispatched_step.passed is False
    assert dispatched_step.detail == "dispatch_performed=False"
    assert _step(validation, "required fields").passed is True
    assert _step(validation, "resolution state").passed is True


def test_dispatched_success_receipt_satisfies_dispatch_policy(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(
        receipt_path,
        resolution_state="dispatched",
        readiness_ready=True,
        dispatch_requested=True,
        dispatch_performed=True,
        dispatch_conclusion="success",
    )

    validation = validate_gateway_publication_receipt(
        receipt_path=receipt_path,
        require_ready=True,
        require_dispatched=True,
        require_success=True,
        expected_environment="pilot",
    )

    assert validation.valid is True
    assert validation.resolution_state == "dispatched"
    assert _step(validation, "dispatch consistency").detail == "dispatched"
    assert _step(validation, "require success").passed is True
    assert _step(validation, "expected expected_environment").passed is True


def test_blocked_not_ready_receipt_is_valid_but_fails_ready_policy(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(
        receipt_path,
        resolution_state="blocked-not-ready",
        readiness_ready=False,
        dispatch_requested=True,
    )

    validation = validate_gateway_publication_receipt(
        receipt_path=receipt_path,
        require_ready=True,
    )
    ready_step = _step(validation, "require ready")

    assert validation.valid is False
    assert validation.resolution_state == "blocked-not-ready"
    assert _step(validation, "resolution state").passed is True
    assert ready_step.passed is False
    assert ready_step.detail == "readiness_ready=False"


def test_receipt_readiness_mismatch_is_invalid(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    _write_receipt(receipt_path, resolution_state="ready-only", readiness_ready=True)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["readiness"]["gateway_url"] = "https://different.mullusi.com"
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    validation = validate_gateway_publication_receipt(receipt_path=receipt_path)
    consistency_step = _step(validation, "readiness consistency")

    assert validation.valid is False
    assert consistency_step.passed is False
    assert consistency_step.detail == "mismatched=['gateway_url']"
    assert _step(validation, "required fields").passed is True
    assert _step(validation, "dispatch consistency").passed is True


def test_cli_writes_validation_report_and_returns_nonzero_for_failed_success_policy(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    receipt_path = tmp_path / "receipt.json"
    output_path = tmp_path / "validation.json"
    _write_receipt(
        receipt_path,
        resolution_state="dispatched",
        readiness_ready=True,
        dispatch_requested=True,
        dispatch_performed=True,
        dispatch_conclusion="failure",
    )

    exit_code = main(
        [
            "--receipt",
            str(receipt_path),
            "--output",
            str(output_path),
            "--require-dispatched",
            "--require-success",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert output_path.exists()
    assert payload["valid"] is False
    assert "valid: false" in captured.out
    assert "conclusion=failure" in captured.out


def _write_receipt(
    receipt_path: Path,
    *,
    resolution_state: str,
    readiness_ready: bool,
    dispatch_requested: bool = False,
    dispatch_performed: bool = False,
    dispatch_conclusion: str = "",
) -> None:
    readiness = {
        "repository": DEFAULT_REPOSITORY,
        "gateway_host": "gateway.mullusi.com",
        "gateway_url": "https://gateway.mullusi.com",
        "expected_environment": "pilot",
        "ready": readiness_ready,
        "steps": [],
    }
    receipt = {
        "artifact_dir": ".change_assurance/gateway-publication-artifact"
        if dispatch_performed
        else "",
        "dispatch_conclusion": dispatch_conclusion,
        "dispatch_performed": dispatch_performed,
        "dispatch_requested": dispatch_requested,
        "dispatch_run_id": 4567 if dispatch_performed else 0,
        "dispatch_run_url": "https://github.com/run/4567" if dispatch_performed else "",
        "dispatch_status": "completed" if dispatch_performed else "",
        "expected_environment": "pilot",
        "gateway_host": "gateway.mullusi.com",
        "gateway_url": "https://gateway.mullusi.com",
        "readiness": readiness,
        "readiness_ready": readiness_ready,
        "readiness_report": ".change_assurance/gateway_publication_readiness.json",
        "receipt": ".change_assurance/gateway_publication_receipt.json",
        "repository": DEFAULT_REPOSITORY,
        "resolution_state": resolution_state,
    }
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")


def _step(validation, name: str):
    return next(step for step in validation.steps if step.name == name)
