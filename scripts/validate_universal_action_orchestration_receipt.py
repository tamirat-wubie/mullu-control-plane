#!/usr/bin/env python3
"""Validate a saved Universal Action Orchestration validation receipt.

Purpose: replay-validate one persisted UAO validation receipt before it is
used as governance evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: Python standard library and the UAO validation receipt contract validator.
Invariants:
  - Validation is read-only and deterministic.
  - Saved receipts remain non-terminal closure evidence.
  - Malformed or contradictory receipt evidence is rejected explicitly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from validate_universal_action_orchestration_receipt_contract import validate_receipt
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as package.
    from scripts.validate_universal_action_orchestration_receipt_contract import validate_receipt


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "docs" / "universal-action-orchestration-validation-receipt-example.json"


class UaoValidationReceiptFileError(ValueError):
    """Raised when a saved UAO validation receipt cannot be admitted."""


def load_receipt(receipt_path: Path) -> dict[str, Any]:
    """Load a saved UAO validation receipt JSON object."""

    if not receipt_path.exists():
        raise FileNotFoundError(f"missing UAO validation receipt: {receipt_path}")
    if not receipt_path.is_file():
        raise IsADirectoryError(f"UAO validation receipt path is not a file: {receipt_path}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise UaoValidationReceiptFileError("UAO validation receipt must be a JSON object")
    return receipt


def validate_receipt_file(receipt_path: Path = DEFAULT_RECEIPT_PATH) -> list[str]:
    """Validate one saved UAO validation receipt file."""

    receipt = load_receipt(receipt_path)
    errors = validate_receipt(receipt)
    if not errors and receipt.get("status") != "passed":
        errors.append("receipt status must be passed for replay witness")
    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate a saved Universal Action Orchestration validation receipt."""

    parser = argparse.ArgumentParser(description="Validate a saved UAO validation receipt.")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    args = parser.parse_args(argv)

    try:
        errors = validate_receipt_file(args.receipt)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"[FAIL] load-receipt: {exc}\nSTATUS: failed\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"[FAIL] universal-action-orchestration-validation-receipt: {error}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] universal_action_orchestration_validation_receipt_file\n")
    sys.stdout.write("[PASS] universal_action_orchestration_validation_receipt_status\n")
    sys.stdout.write("[PASS] universal_action_orchestration_validation_receipt_checks\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
