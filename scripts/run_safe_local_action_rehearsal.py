#!/usr/bin/env python3
"""Run the safe local action rehearsal capability.

Purpose: emit a proof-only rehearsal receipt for local developer actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi.govern.safe_local_action_rehearsal.runner.
Invariants: this script writes only the requested receipt artifact and performs
no live action, connector call, PR creation, merge, rollback, or deployment.
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
    run_safe_local_action_rehearsal,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run safe local action rehearsal.")
    parser.add_argument("--dashboard", default="", help="Optional operator workflow dashboard read model path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        receipt, validation = run_safe_local_action_rehearsal(
            dashboard_path=Path(args.dashboard) if args.dashboard else None,
            output_path=Path(args.output),
        )
    except ValueError as exc:
        print(f"SAFE LOCAL ACTION REHEARSAL INVALID error={exc}")
        return 2
    if not validation.ok:
        print(f"SAFE LOCAL ACTION REHEARSAL INVALID errors={list(validation.errors)}")
        return 2
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"SAFE LOCAL ACTION REHEARSAL BUILT path={validation.receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
