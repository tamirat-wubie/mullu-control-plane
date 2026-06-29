"""Tests for capability debt report validation.

Purpose: prove capability gaps are projected into a clear operator next-action
debt report without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capability_debt_report, capability passports,
evidence passports, and sandbox-to-live promotion paths.
Invariants: every capability has one debt row; summary counters match rows;
live action remains disabled.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.capability_debt_report import (
    CapabilityDebtReportError,
    build_capability_debt_report,
)
from scripts.validate_capability_debt_report import (
    DEFAULT_DEBT_REPORT,
    DEFAULT_OUTPUT,
    validate_capability_debt_report,
    write_capability_debt_report_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_DEBT_REPORT.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    debt_path = tmp_path / "capability_debt_report.json"
    debt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return debt_path


def _debt_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = payload["debt_rows"]
    assert isinstance(rows, list)
    return rows


def _row_by_capability(payload: dict[str, object], capability_id: str) -> dict[str, object]:
    for row in _debt_rows(payload):
        if row.get("capability_id") == capability_id:
            return row
    raise AssertionError(f"missing debt row {capability_id}")


def test_capability_debt_report_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_capability_debt_report()
    output_path = tmp_path / "capability-debt-report-validation.json"

    written_path = write_capability_debt_report_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.debt_row_count == validation.capability_count
    assert validation.debt_row_count > 20
    assert validation.total_debt_item_count > validation.debt_row_count
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "capability_debt_report_validation.json"


def test_capability_debt_report_projects_expected_debt_categories() -> None:
    report = build_capability_debt_report()
    payment = _row_by_capability(report, "financial.send_payment")
    categories = {item["category"] for item in payment["debt_items"]}

    assert payment["debt_item_count"] >= 3
    assert payment["debt_severity"] == "high"
    assert "approval" in categories
    assert "promotion" in categories
    assert "live_action" in categories
    assert payment["live_action_enabled"] is False
    approval_item = next(item for item in payment["debt_items"] if item["category"] == "approval")
    assert approval_item["missing_refs"] == [
        "gate.approval.required",
        "approval_decision_receipt",
        "approval_chain",
        "approval_refs",
        "actor_id",
        "separation_of_duty",
    ]
    assert "approval_decision_receipt" in payment["next_action"]
    assert "separation_of_duty" in approval_item["fix"]


def test_capability_debt_report_projects_missing_evidence_for_draft() -> None:
    report = build_capability_debt_report()
    draft = _row_by_capability(report, "email.draft")
    categories = {item["category"] for item in draft["debt_items"]}

    assert "evidence" in categories
    assert "replay" in categories
    assert "promotion" in categories
    assert draft["debt_row_is_not_execution_authority"] is True
    assert draft["live_action_enabled"] is False
    replay_item = next(item for item in draft["debt_items"] if item["category"] == "replay")
    assert replay_item["missing_refs"] == [
        "replay_record",
        "replay_input_digest",
        "replay_output_digest",
        "connector_id",
        "recipient_hashes",
        "draft_receipt",
        "terminal_closure_certificate",
        "effect_reconciliation_receipt",
    ]
    assert "replay_output_digest" in replay_item["fix"]
    rollback_item = next(item for item in draft["debt_items"] if item["category"] == "rollback")
    assert rollback_item["missing_refs"] == [
        "recovery_evidence_missing",
        "rollback_capability",
        "compensation_capability",
        "failure_review_receipt",
        "rollback_or_recovery_evidence",
    ]
    assert "failure_review_receipt" in rollback_item["fix"]
    assert "collect" in draft["next_action"] or "bind" in draft["next_action"] or "keep" in draft["next_action"]


def test_capability_debt_report_rejects_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["debt_report_is_not_execution_authority"] = False
    payload["live_execution_enabled"] = True
    row = _row_by_capability(payload, "email.draft")
    row["debt_row_is_not_execution_authority"] = False
    row["live_action_enabled"] = True

    validation = validate_capability_debt_report(debt_report_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "debt_report_is_not_execution_authority must be true" in serialized_errors
    assert "live_execution_enabled must be false" in serialized_errors
    assert "debt_row_is_not_execution_authority must be true" in serialized_errors
    assert "live_action_enabled must be false" in serialized_errors


def test_capability_debt_report_rejects_missing_debt_row(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["debt_rows"] = [
        row for row in _debt_rows(payload) if row.get("capability_id") != "financial.send_payment"
    ]
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["debt_row_count"] = int(summary["debt_row_count"]) - 1

    validation = validate_capability_debt_report(debt_report_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "registered capabilities missing debt rows ['financial.send_payment']" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_debt_report_rejects_bad_summary_counts(tmp_path: Path) -> None:
    payload = _default_payload()
    summary = payload["summary"]
    assert isinstance(summary, dict)
    summary["total_debt_item_count"] = 1

    validation = validate_capability_debt_report(debt_report_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "summary.total_debt_item_count must match debt rows" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_capability_debt_report_rejects_empty_source_rows() -> None:
    passport_set = {"passport_set_id": "demo.passports", "passports": []}

    with pytest.raises(CapabilityDebtReportError, match="non-empty passports list"):
        build_capability_debt_report(passports=passport_set)
