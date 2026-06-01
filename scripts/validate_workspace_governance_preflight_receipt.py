#!/usr/bin/env python3
"""Validate a saved workspace governance preflight receipt.

Purpose: verify a persisted preflight receipt JSON file before it is used as
governance evidence.
Governance scope: [OCE, RAG, CDCV, UWMA, PRS]
Dependencies: Python standard library and receipt contract validator.
Invariants:
  - Validation is read-only and deterministic.
  - Receipt status must match observed check metadata.
  - Saved replay witness receipts must have status passed.
  - Malformed receipt evidence is rejected with explicit errors.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from validate_workspace_governance_preflight_receipt_contract import validate_receipt
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.validate_workspace_governance_preflight_receipt_contract import validate_receipt


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "docs" / "workspace-governance-preflight-receipt-example.json"


class PreflightReceiptValidationError(ValueError):
    """Raised when a saved preflight receipt cannot be admitted."""


def load_receipt(receipt_path: Path) -> dict[str, Any]:
    """Load a saved preflight receipt JSON object."""

    if not receipt_path.exists():
        raise FileNotFoundError(f"missing preflight receipt: {receipt_path}")
    if not receipt_path.is_file():
        raise IsADirectoryError(f"preflight receipt path is not a file: {receipt_path}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise PreflightReceiptValidationError("preflight receipt must be a JSON object")
    return receipt


def validate_receipt_file(receipt_path: Path) -> list[str]:
    """Validate one saved preflight receipt file."""

    receipt = load_receipt(receipt_path)
    errors = validate_receipt(receipt)
    if not errors and receipt.get("status") != "passed":
        errors.append("receipt status must be passed for replay witness")
    return errors


def validate_receipt_freshness(
    receipt: dict[str, Any],
    max_age_seconds: float,
    now_epoch: float | None = None,
) -> list[str]:
    """Validate that a receipt was generated within an explicit freshness window."""

    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    generated_at_epoch = receipt.get("generated_at_epoch")
    if isinstance(generated_at_epoch, bool) or not isinstance(generated_at_epoch, (int, float)):
        return ["generated_at_epoch must be a positive epoch timestamp"]
    observed_now = time.time() if now_epoch is None else now_epoch
    if observed_now < generated_at_epoch:
        return ["receipt generated_at_epoch is in the future"]
    age_seconds = observed_now - generated_at_epoch
    if age_seconds > max_age_seconds:
        return [
            "receipt generated_at_epoch is older than freshness window: "
            f"{age_seconds:.3f}s > {max_age_seconds:.3f}s"
        ]
    return []


def main(argv: list[str] | None = None) -> int:
    """Validate a saved workspace governance preflight receipt."""

    parser = argparse.ArgumentParser(description="Validate a saved workspace governance preflight receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument(
        "--max-age-seconds",
        type=float,
        help="reject receipts older than this many seconds using generated_at_epoch",
    )
    args = parser.parse_args(argv)

    try:
        receipt = load_receipt(args.receipt)
        errors = validate_receipt(receipt)
        if not errors and receipt.get("status") != "passed":
            errors.append("receipt status must be passed for replay witness")
        if not errors and args.max_age_seconds is not None:
            errors.extend(validate_receipt_freshness(receipt, args.max_age_seconds))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-receipt: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] preflight-receipt: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] workspace_governance_preflight_receipt_file\n")
    sys.stdout.write("[PASS] workspace_governance_preflight_receipt_status\n")
    sys.stdout.write("[PASS] workspace_governance_preflight_receipt_checks\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
