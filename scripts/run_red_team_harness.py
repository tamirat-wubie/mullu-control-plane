"""Run the deterministic Mullusi red-team release harness.

Purpose: emit prompt-injection, budget-evasion, audit-tampering, and policy-bypass pass rates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: red-team harness core module.
Invariants: default execution performs no network calls and fails when the minimum pass rate is not met.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))


def main() -> int:
    from mcoi_runtime.core.red_team_harness import RedTeamHarness

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional path for writing the JSON report.")
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=1.0,
        help="Minimum acceptable pass rate. Defaults to 1.0 for release gating.",
    )
    args = parser.parse_args()
    if args.min_pass_rate < 0 or args.min_pass_rate > 1:
        print("--min-pass-rate must be between 0 and 1")
        return 2

    report = RedTeamHarness().run()
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n", encoding="utf-8")
    print(encoded)
    if report["pass_rate"] < args.min_pass_rate:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
