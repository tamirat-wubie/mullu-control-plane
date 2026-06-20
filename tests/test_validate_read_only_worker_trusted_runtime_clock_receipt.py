"""Tests for read-only worker trusted runtime clock receipts.

Purpose: prove trusted runtime clock receipts stay evidence-only and do not
grant runtime enablement authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_read_only_worker_trusted_runtime_clock_receipt.
Invariants:
  - Runtime enablement and dispatch remain blocked.
  - Clock evidence has a bounded validity window.
  - Clock evidence is not terminal closure or authorization.
"""

from __future__ import annotations

import json
import subprocess
import sys

from scripts.validate_read_only_worker_trusted_runtime_clock_receipt import (
    DEFAULT_SCHEMA,
    build_mutated_trusted_runtime_clock_receipt,
    validate_trusted_runtime_clock_receipt,
    validate_trusted_runtime_clock_receipt_record,
)
from scripts.validate_schemas import _load_schema


def test_trusted_runtime_clock_receipt_fixture_passes() -> None:
    errors = validate_trusted_runtime_clock_receipt()

    assert errors == []
    assert DEFAULT_SCHEMA.exists()
    assert build_mutated_trusted_runtime_clock_receipt()["validity_window_seconds"] == 300


def test_trusted_runtime_clock_receipt_rejects_authority_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA)
    mutated = build_mutated_trusted_runtime_clock_receipt(
        runtime_enablement_allowed=True,
        runtime_dispatch_allowed=True,
        terminal_closure_allowed=True,
    )

    errors = validate_trusted_runtime_clock_receipt_record(mutated, schema)

    assert "runtime_enablement_allowed must be false" in errors
    assert "runtime_dispatch_allowed must be false" in errors
    assert "terminal_closure_allowed must be false" in errors


def test_trusted_runtime_clock_receipt_rejects_clock_boundary_drift() -> None:
    schema = _load_schema(DEFAULT_SCHEMA)
    mutated = build_mutated_trusted_runtime_clock_receipt(
        monotonicity_required=False,
        validity_window_seconds=999,
        observed_at="2026-06-20T00:00:00",
    )

    errors = validate_trusted_runtime_clock_receipt_record(mutated, schema)

    assert "monotonicity_required must be true" in errors
    assert "validity_window_seconds must be 300" in errors
    assert "observed_at must be UTC with Z suffix" in errors


def test_trusted_runtime_clock_receipt_cli_json() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_read_only_worker_trusted_runtime_clock_receipt.py", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["errors"] == []
    assert payload["runtime_enablement_allowed"] is False


def test_trusted_runtime_clock_receipt_rejects_malformed_payload() -> None:
    schema = _load_schema(DEFAULT_SCHEMA)

    errors = validate_trusted_runtime_clock_receipt_record([], schema)

    assert any("must be object" in error or "must be a JSON object" in error for error in errors)
    assert len(errors) >= 1
    assert schema["$id"] == "urn:mullusi:schema:read-only-worker-trusted-runtime-clock-receipt:1"
