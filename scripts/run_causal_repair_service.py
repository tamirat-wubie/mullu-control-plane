#!/usr/bin/env python3
"""Run the causal repair service.

Purpose: emit a proof-only repair classification receipt for governed workflow
failure classes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi.causal_repair.service.
Invariants: this script writes only the requested receipt artifact and performs
no repair execution, file mutation, connector call, rollback, deployment, or
external write.
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

from causal_repair.service import (  # noqa: E402
    DEFAULT_FAILURE_IDS,
    DEFAULT_OUTPUT,
    run_causal_repair_service,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run causal repair service.")
    parser.add_argument(
        "--failure-id",
        action="append",
        choices=DEFAULT_FAILURE_IDS,
        help="Failure id to include. Omit to include all default failure cases.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    failure_ids = tuple(args.failure_id or DEFAULT_FAILURE_IDS)
    try:
        receipt, validation = run_causal_repair_service(
            failure_ids=failure_ids,
            output_path=Path(args.output),
        )
    except ValueError as exc:
        print(f"CAUSAL REPAIR SERVICE INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"CAUSAL REPAIR SERVICE INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"CAUSAL REPAIR SERVICE BUILT path={validation.receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
