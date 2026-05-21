"""Purpose: CLI receipt surface for the operational mathematics loop.
Governance scope: parse bounded local arguments, execute the operational math
    loop, and emit a deterministic JSON receipt with explicit unresolved gaps.
Dependencies: Python argparse/json/pathlib and operational math core engine.
Invariants:
  - The CLI does not mutate runtime state.
  - The loop remains bounded by max_iterations.
  - JSON receipts preserve solver outcome and unresolved principle ids.
  - Receipt file writes are explicit and parent directories must already exist.
  - Receipt store writes use deterministic append-only persistence.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcoi_runtime.contracts.operational_math import (
    OperationalMathLoopResult,
    OperationalMathLoopStatus,
    OperationalMathTarget,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.operational_math_loop import OperationalMathLoopEngine
from mcoi_runtime.app.operational_math_observability import summarize_operational_math_receipt
from mcoi_runtime.persistence.errors import PersistenceError
from mcoi_runtime.persistence.operational_math_receipt_store import (
    FileOperationalMathReceiptStore,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_operational_math_receipt(
    result: OperationalMathLoopResult,
    *,
    event_count: int,
) -> dict[str, Any]:
    """Build one JSON-safe receipt for an operational math loop result."""

    if not isinstance(result, OperationalMathLoopResult):
        raise ValueError("result must be an OperationalMathLoopResult")
    if not isinstance(event_count, int) or event_count < 0:
        raise ValueError("event_count must be a non-negative integer")
    return {
        "receipt_id": f"operational_math_loop_receipt:{result.result_id}",
        "status": "passed" if result.status is OperationalMathLoopStatus.SATURATED else "failed",
        "solver_outcome": result.solver_outcome,
        "target_id": result.target_id,
        "event_count": event_count,
        "iteration_count": len(result.iterations),
        "applied_principle_ids": list(result.applied_principle_ids),
        "unresolved_principle_ids": list(result.unresolved_principle_ids),
        "result": result.to_json_dict(),
    }


def _resolve_receipt_path(receipt_path: Path) -> Path:
    """Resolve a JSON output path without creating hidden parent directories."""

    resolved_path = receipt_path.resolve()
    if resolved_path.suffix.lower() != ".json":
        raise ValueError("output path must use .json suffix")
    if not resolved_path.parent.is_dir():
        raise ValueError("output path parent does not exist")
    return resolved_path


def _write_json_document(document: dict[str, Any], output_path: Path) -> Path:
    """Write one JSON document to an explicit local path."""

    resolved_path = _resolve_receipt_path(output_path)
    resolved_path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return resolved_path


def main(argv: list[str] | None = None) -> int:
    """Run the operational math loop and emit a proof receipt."""

    parser = argparse.ArgumentParser(description="Run the operational math loop.")
    parser.add_argument("--target-id", default="mullu-core-math", help="stable target identifier")
    parser.add_argument("--title", default="Teach Mullu Core Math Principles", help="target title")
    parser.add_argument(
        "--problem-class",
        default="operational mathematical cognition",
        help="target problem class",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=16,
        help="positive bound for loop iterations",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="optional ISO timestamp used for deterministic receipt replay",
    )
    parser.add_argument(
        "--receipt-path",
        type=Path,
        default=None,
        help="optional .json path where the receipt is written",
    )
    parser.add_argument(
        "--store-path",
        type=Path,
        default=None,
        help="optional .json path for the append-only operational math receipt store",
    )
    parser.add_argument(
        "--projection-path",
        type=Path,
        default=None,
        help="optional .json path where the dashboard-safe projection is written",
    )
    args = parser.parse_args(argv)

    try:
        clock = (lambda: args.timestamp) if args.timestamp else None
        event_spine = EventSpineEngine()
        engine = OperationalMathLoopEngine(event_spine=event_spine, clock=clock)
        target = OperationalMathTarget(
            target_id=args.target_id,
            title=args.title,
            problem_class=args.problem_class,
            max_iterations=args.max_iterations,
            created_at=args.timestamp or _now_iso(),
        )
        result = engine.apply_all(target)
        receipt = build_operational_math_receipt(result, event_count=event_spine.event_count)
        if args.store_path is not None:
            FileOperationalMathReceiptStore(args.store_path).append(receipt)
        if args.receipt_path is not None:
            _write_json_document(receipt, args.receipt_path)
        if args.projection_path is not None:
            _write_json_document(summarize_operational_math_receipt(receipt), args.projection_path)
    except (OSError, PersistenceError, ValueError) as exc:
        sys.stderr.write(f"STATUS: failed\nerror: {exc}\n")
        return 1

    sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n")
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
