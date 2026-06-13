"""Tests for durable Gmail OAuth live receipt freshness validation.

Purpose: prove Gmail live evidence cannot be reused after staleness, clock
skew, non-passing status, or secret-marker contamination.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_durable_gmail_oauth_live_receipt_freshness.
Invariants:
  - Freshness supports only the read-only Gmail live-probe boundary.
  - Stale or future-skewed evidence is blocked explicitly.
  - Token-shaped material is never emitted by the validator.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_oauth_live_receipt_freshness as validator


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _durable_receipt(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "receipt_id": "durable_gmail_oauth_live_receipt",
        "adapter_id": "communication.gmail_oauth",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
        "checked_at": "2026-06-12T00:00:00Z",
        "connector_id": "gmail",
        "operation_family": "read_only_search",
        "external_mailbox_write_performed": False,
        "credential_values_disclosed": False,
    }
    payload.update(overrides)
    return payload


def test_fresh_durable_gmail_receipt_is_ready(tmp_path: Path) -> None:
    receipt_path = tmp_path / "durable.json"
    _write_receipt(receipt_path, _durable_receipt())

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
        max_age_days=14,
    )

    assert report["valid"] is True
    assert report["fresh"] is True
    assert report["ready"] is True
    assert report["freshness_status"] == "fresh"
    assert report["age_seconds"] == 86400
    assert report["production_ready_claimed"] is False
    assert report["write_authority_claimed"] is False
    assert report["calendar_authority_claimed"] is False


def test_stale_receipt_blocks_readiness(tmp_path: Path) -> None:
    receipt_path = tmp_path / "durable.json"
    _write_receipt(receipt_path, _durable_receipt(checked_at="2026-05-01T00:00:00Z"))

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
        max_age_days=14,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready"] is False
    assert report["freshness_status"] == "stale"
    assert "receipt_age_exceeds_max_age" in report["blockers"]
    assert report["blocker_count"] >= 1


def test_future_clock_skew_blocks_readiness(tmp_path: Path) -> None:
    receipt_path = tmp_path / "durable.json"
    _write_receipt(receipt_path, _durable_receipt(checked_at="2026-06-13T00:10:01Z"))

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
        max_future_skew_minutes=5,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready"] is False
    assert report["freshness_status"] == "future_clock_skew"
    assert "receipt_checked_at_exceeds_future_skew" in report["blockers"]
    assert report["age_seconds"] < 0


def test_non_passing_durable_receipt_is_not_ready(tmp_path: Path) -> None:
    receipt_path = tmp_path / "durable.json"
    _write_receipt(
        receipt_path,
        _durable_receipt(status="failed", solver_outcome="AwaitingEvidence"),
    )

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready"] is False
    assert "receipt_not_passing_read_only_boundary" in report["blockers"]
    assert report["freshness_status"] == "fresh"


def test_email_calendar_live_receipt_can_be_fresh(tmp_path: Path) -> None:
    receipt_path = tmp_path / "email.json"
    _write_receipt(
        receipt_path,
        {
            "receipt_id": "email_calendar_live_receipt",
            "adapter_id": "communication.email_calendar_worker",
            "status": "passed",
            "verification_status": "passed",
            "checked_at": "2026-06-12T12:00:00Z",
            "external_write": False,
        },
    )

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is True
    assert report["fresh"] is True
    assert report["ready"] is True
    assert report["validated_adapter_id"] == "communication.email_calendar_worker"
    assert report["age_seconds"] == 43200


def test_missing_receipt_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "missing.json"

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready"] is False
    assert "receipt_unavailable" in report["blockers"]
    assert str(tmp_path) not in serialized
    assert "missing.json" in serialized


def test_secret_marker_in_receipt_is_blocked_without_value_disclosure(tmp_path: Path) -> None:
    receipt_path = tmp_path / "durable.json"
    _write_receipt(receipt_path, _durable_receipt(leak="ya29.runtime-secret-value"))

    report = validator.validate_live_receipt_freshness(
        receipt_path,
        now="2026-06-13T00:00:00Z",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready"] is False
    assert "receipt_contains_secret_marker" in report["blockers"]
    assert "ya29.runtime-secret-value" not in serialized
    assert "secret-shaped material" in serialized
