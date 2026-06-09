#!/usr/bin/env python3
"""Report the holistic governed loop read model.

Purpose: expose Mullu Holistic Loop Engineering Kernel v1 as a read-only
operator report.
Governance scope: loop registry summaries, missing evidence blockers,
non-terminal closure boundary, and bounded JSON output.
Dependencies: Python standard library and mcoi_runtime holistic loop registry.
Invariants:
  - The report is read-only and never executes registered loop behavior.
  - Missing evidence remains a blocker, never an inferred success.
  - Output is bounded by an explicit positive limit.
  - The report is not a terminal closure certificate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.core.holistic_loop_registry import (  # noqa: E402
    DEFAULT_LOOP_UPDATED_AT,
    build_default_loop_read_model,
)


def build_report(
    *,
    observed_evidence_refs: dict[str, tuple[str, ...]] | None = None,
    generated_at: str = DEFAULT_LOOP_UPDATED_AT,
    limit: int = 20,
) -> dict[str, object]:
    """Build a machine-readable holistic loop read-model report."""

    read_model = build_default_loop_read_model(
        observed_evidence_refs=observed_evidence_refs,
        generated_at=generated_at,
        limit=limit,
    )
    blocked_count = sum(1 for loop in read_model.loops if loop.open_blockers)
    verified_count = sum(1 for loop in read_model.loops if loop.status.value == "verified")
    return {
        "report_id": "holistic_loop_read_model",
        "status": "blocked" if blocked_count else "verified",
        "generated_at": read_model.generated_at,
        "loop_count": read_model.total_count,
        "returned_count": read_model.returned_count,
        "blocked_count": blocked_count,
        "verified_count": verified_count,
        "truncated": read_model.truncated,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
        "loops": [loop.to_json_dict() for loop in read_model.loops],
    }


def render_report(report: dict[str, object], output_stream: TextIO) -> None:
    """Render a human-readable read-model summary."""

    output_stream.write(
        "STATUS: {0}; loops={1}; returned={2}; blocked={3}; verified={4}\n".format(
            report["status"],
            report["loop_count"],
            report["returned_count"],
            report["blocked_count"],
            report["verified_count"],
        )
    )
    loops = report["loops"]
    if not isinstance(loops, list):
        return
    for loop in loops:
        if not isinstance(loop, dict):
            continue
        blockers = loop.get("open_blockers", [])
        blocker_count = len(blockers) if isinstance(blockers, list) else 0
        output_stream.write(
            "[{status}] {loop_id}: mode={mode}; step={step}; blockers={blockers}\n".format(
                status=loop.get("status"),
                loop_id=loop.get("loop_id"),
                mode=loop.get("mode"),
                step=loop.get("current_step"),
                blockers=blocker_count,
            )
        )


def parse_evidence_refs(values: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """Parse loop_id=evidence_ref arguments into grouped evidence refs."""

    evidence_by_loop: dict[str, list[str]] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("evidence refs must use loop_id=evidence_ref form")
        loop_id, evidence_ref = value.split("=", 1)
        loop_id = loop_id.strip()
        evidence_ref = evidence_ref.strip()
        if not loop_id or not evidence_ref:
            raise ValueError("loop_id and evidence_ref must be non-empty")
        evidence_by_loop.setdefault(loop_id, []).append(evidence_ref)
    return {loop_id: tuple(refs) for loop_id, refs in evidence_by_loop.items()}


def main(argv: list[str] | None = None) -> int:
    """Report the holistic governed loop read model."""

    parser = argparse.ArgumentParser(description="Report holistic governed loop read model.")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--generated-at",
        default=DEFAULT_LOOP_UPDATED_AT,
        help="ISO 8601 timestamp for the generated report",
    )
    parser.add_argument("--limit", type=int, default=20, help="maximum loop summaries to return")
    parser.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
        help="observed evidence ref in loop_id=evidence_ref form; repeatable",
    )
    args = parser.parse_args(argv)

    try:
        report = build_report(
            observed_evidence_refs=parse_evidence_refs(tuple(args.evidence_ref)),
            generated_at=args.generated_at,
            limit=args.limit,
        )
    except ValueError as exc:
        sys.stderr.write(f"[BLOCKED] holistic-loop-read-model: {exc}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        render_report(report, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
