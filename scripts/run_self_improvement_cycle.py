#!/usr/bin/env python3
"""Run one proposal-only self-improvement cycle and report the result.

Crawls the proof-coverage surface index (and, with --include-routes, the HTTP
route-coverage index), runs the diagnose/refine/enhance/engineer/runtime-safe
fixer roles, and prints a human summary plus an optional JSON report. Promotes
nothing: every report is activation- and promotion-blocked.

Usage:
  python scripts/run_self_improvement_cycle.py
  python scripts/run_self_improvement_cycle.py --top-n 8 --include-routes
  python scripts/run_self_improvement_cycle.py --json --out report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateway.self_improvement_driver import run_cycle  # noqa: E402

DEFAULT_MATRIX = REPO_ROOT / "tests" / "fixtures" / "proof_coverage_matrix.json"


def _render_summary(report) -> str:
    lines = [
        f"self-improvement cycle @ {report.generated_at}",
        f"  crawled surfaces : {report.crawled_surface_count}",
        f"  actionable gaps  : {report.actionable_gap_count}",
        f"  activation_blocked={report.activation_blocked} promotion_blocked={report.promotion_blocked}",
        f"  report_hash      : {report.report_hash}",
    ]
    for gap in report.ranked_gaps:
        lines.append(
            f"    gap {gap.surface_id}: unanchored {gap.unanchored_witness_count}/{gap.runtime_witness_count}"
        )
    if report.portfolio is not None:
        lines.append(f"  proposals        : {len(report.portfolio.plans)} (recorded to ledger, all blocked)")
        if report.portfolio.systemic_weakness_codes:
            lines.append(f"  systemic codes   : {', '.join(report.portfolio.systemic_weakness_codes[:5])}")
    if report.route_gaps:
        lines.append(f"  route gaps       : {len(report.route_gaps)} non-proven routes (visibility only)")
    if report.healing_receipts:
        lines.append(f"  healing receipts : {len(report.healing_receipts)} (non-terminal)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--matrix", default=str(DEFAULT_MATRIX), help="Path to the proof-coverage matrix JSON.")
    parser.add_argument("--top-n", type=int, default=5, help="Max number of gaps to turn into proposals.")
    parser.add_argument("--generated-at", default=None, help="ISO-8601 timestamp; defaults to now (UTC).")
    parser.add_argument("--include-routes", action="store_true", help="Also crawl HTTP route coverage.")
    parser.add_argument("--max-route-gaps", type=int, default=50, help="Cap reported route gaps.")
    parser.add_argument("--json", action="store_true", help="Print the JSON report to stdout.")
    parser.add_argument("--out", default=None, help="Write the JSON report to this path.")
    args = parser.parse_args(argv)

    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat()
    report = run_cycle(
        args.matrix,
        generated_at=generated_at,
        top_n=args.top_n,
        include_routes=args.include_routes,
        max_route_gaps=args.max_route_gaps,
    )
    payload = report.to_json_dict()

    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
