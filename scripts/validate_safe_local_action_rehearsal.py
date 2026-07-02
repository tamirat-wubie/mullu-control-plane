#!/usr/bin/env python3
"""Validate a safe local action rehearsal receipt.

Purpose: prove a rehearsal receipt remains proof-only and schema-conformant.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi.govern.safe_local_action_rehearsal.runner.
Invariants: validation rejects live execution claims, mutation claims,
approval overclaims, and missing blocked effects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from govern.safe_local_action_rehearsal.runner import (  # noqa: E402
    DEFAULT_OUTPUT,
    validate_safe_local_action_rehearsal_receipt,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate safe local action rehearsal receipt.")
    parser.add_argument("--receipt", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    receipt_path = Path(args.receipt)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SAFE LOCAL ACTION REHEARSAL INVALID error=json_parse_failed:{exc}")
        return 2
    validation = validate_safe_local_action_rehearsal_receipt(
        receipt=receipt,
        receipt_path=receipt_path,
    )
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print(f"SAFE LOCAL ACTION REHEARSAL VALID path={validation.receipt_path}")
    else:
        print(f"SAFE LOCAL ACTION REHEARSAL INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
