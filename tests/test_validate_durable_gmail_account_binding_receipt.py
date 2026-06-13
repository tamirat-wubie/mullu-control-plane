"""Tests for durable Gmail account binding receipt validation.

Purpose: prove Gmail account binding evidence is redacted, fresh, tenant-bound,
and hash-matched before it can support a mailbox-binding claim.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_durable_gmail_account_binding_receipt.
Invariants:
  - Raw mailbox addresses are blocked.
  - Matching account hashes are required.
  - Binding does not promote write, Calendar, customer, or production authority.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_durable_gmail_account_binding_receipt as validator


EXPECTED_HASH = "a" * 64
OTHER_HASH = "b" * 64


def _write_receipt(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _binding_receipt(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "receipt_id": "durable_gmail_account_binding_receipt",
        "adapter_id": "communication.gmail_oauth",
        "connector_id": "gmail",
        "tenant_ref": "tenant://mullusi-foundation",
        "expected_account_hash": EXPECTED_HASH,
        "observed_account_hash": EXPECTED_HASH,
        "hash_algorithm": "sha256",
        "hash_salt_ref": "secret:GMAIL_ACCOUNT_BINDING_HASH_SALT",
        "source_receipt_ref": ".change_assurance/durable_gmail_oauth_live_receipt.json",
        "account_profile_probe_performed": True,
        "external_provider_call_performed": True,
        "external_mailbox_write_performed": False,
        "credential_values_disclosed": False,
        "checked_at": "2026-06-12T00:00:00Z",
        "status": "passed",
        "solver_outcome": "SolvedVerified",
    }
    payload.update(overrides)
    return payload


def _source_live_receipt(**overrides: object) -> dict[str, object]:
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


def _write_fresh_source_receipt(tmp_path: Path, **overrides: object) -> Path:
    source_receipt_path = tmp_path / "source-live.json"
    _write_receipt(source_receipt_path, _source_live_receipt(**overrides))
    return source_receipt_path


def test_matching_account_binding_receipt_is_ready(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt())
    source_receipt_path = _write_fresh_source_receipt(tmp_path)

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is True
    assert report["fresh"] is True
    assert report["ready_for_tenant_binding"] is True
    assert report["freshness_status"] == "fresh"
    assert report["write_authority_claimed"] is False
    assert report["calendar_authority_claimed"] is False
    assert report["production_ready_claimed"] is False
    assert report["source_live_receipt_required"] is True
    assert report["source_live_receipt_ready"] is True


def test_hash_mismatch_blocks_account_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt(observed_account_hash=OTHER_HASH))
    source_receipt_path = _write_fresh_source_receipt(tmp_path)

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready_for_tenant_binding"] is False
    assert "account_hash_mismatch" in report["blockers"]
    assert report["freshness_status"] == "fresh"


def test_stale_account_binding_blocks_readiness(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt(checked_at="2026-05-01T00:00:00Z"))
    source_receipt_path = _write_fresh_source_receipt(tmp_path)

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
        max_age_days=14,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready_for_tenant_binding"] is False
    assert report["freshness_status"] == "stale"
    assert "account_binding_age_exceeds_max_age" in report["blockers"]


def test_missing_profile_probe_blocks_account_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(
        receipt_path,
        _binding_receipt(
            account_profile_probe_performed=False,
            external_provider_call_performed=False,
        ),
    )
    source_receipt_path = _write_fresh_source_receipt(tmp_path)

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is False
    assert report["ready_for_tenant_binding"] is False
    assert "account_binding_invalid" in report["blockers"]
    assert any("profile probe" in error for error in report["errors"])


def test_external_mailbox_write_blocks_account_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt(external_mailbox_write_performed=True))
    source_receipt_path = _write_fresh_source_receipt(tmp_path)

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is False
    assert report["ready_for_tenant_binding"] is False
    assert "account_binding_invalid" in report["blockers"]
    assert any("no external mailbox write" in error for error in report["errors"])


def test_raw_mailbox_address_is_blocked_without_disclosure(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt(raw_email="operator@example.com"))
    source_receipt_path = _write_fresh_source_receipt(tmp_path)

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready_for_tenant_binding"] is False
    assert "account_binding_contains_raw_mailbox_address" in report["blockers"]
    assert "operator@example.com" not in serialized
    assert report["raw_mailbox_address_disclosed"] is False


def test_missing_source_live_receipt_blocks_account_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt())

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=tmp_path / "missing-source.json",
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is False
    assert report["fresh"] is False
    assert report["ready_for_tenant_binding"] is False
    assert report["source_live_receipt_ready"] is False
    assert "account_binding_source_live_receipt_not_ready" in report["blockers"]


def test_stale_source_live_receipt_blocks_account_binding(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt())
    source_receipt_path = _write_fresh_source_receipt(tmp_path, checked_at="2026-05-01T00:00:00Z")

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
        max_age_days=14,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready_for_tenant_binding"] is False
    assert report["source_live_receipt_ready"] is False
    assert "account_binding_source_live_receipt_not_ready" in report["blockers"]


def test_source_live_receipt_after_binding_blocks_causal_chain(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt(checked_at="2026-06-12T00:00:00Z"))
    source_receipt_path = _write_fresh_source_receipt(tmp_path, checked_at="2026-06-12T00:10:01Z")

    report = validator.validate_account_binding_receipt(
        receipt_path,
        source_receipt_path=source_receipt_path,
        now="2026-06-13T00:00:00Z",
        max_future_skew_minutes=5,
    )

    assert report["valid"] is True
    assert report["fresh"] is False
    assert report["ready_for_tenant_binding"] is False
    assert report["source_live_receipt_ready"] is True
    assert "source_live_receipt_after_account_binding" in report["blockers"]


def test_source_receipt_ref_parent_traversal_is_blocked(tmp_path: Path) -> None:
    receipt_path = tmp_path / "binding.json"
    _write_receipt(receipt_path, _binding_receipt(source_receipt_ref="../outside.json"))

    report = validator.validate_account_binding_receipt(
        receipt_path,
        now="2026-06-13T00:00:00Z",
    )

    assert report["valid"] is False
    assert report["fresh"] is False
    assert report["ready_for_tenant_binding"] is False
    assert "account_binding_source_receipt_ref_invalid" in report["blockers"]
    assert any("must not traverse parent directories" in error for error in report["errors"])


def test_require_bound_cannot_skip_source_freshness() -> None:
    exit_code = validator.main(["--require-bound", "--skip-source-freshness"])

    assert exit_code == 2


def test_missing_receipt_error_is_bounded(tmp_path: Path) -> None:
    receipt_path = tmp_path / "missing.json"

    report = validator.validate_account_binding_receipt(
        receipt_path,
        now="2026-06-13T00:00:00Z",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["valid"] is False
    assert report["ready_for_tenant_binding"] is False
    assert "account_binding_receipt_unavailable" in report["blockers"]
    assert str(tmp_path) not in serialized
    assert "missing.json" in serialized
