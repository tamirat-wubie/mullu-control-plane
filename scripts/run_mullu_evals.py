"""Run deterministic Mullu governance eval suites.

Purpose: execute strict promotion-blocking eval suites for governance,
tenant isolation, payments, prompt injection, PII, memory, temporal, and tools.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.evals.
Invariants: default execution performs no network calls, emits a stable
schema-backed EvalRun, and returns non-zero when strict promotion gates fail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MCOI_ROOT = ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.evals import SUITES, MulluEvalRunner  # noqa: E402  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suite",
        action="append",
        choices=SUITES,
        help="Eval suite to run. May be repeated. Defaults to all suites.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail if any critical promotion blocker appears.")
    parser.add_argument("--output", type=Path, help="Optional path for writing the EvalRun JSON.")
    args = parser.parse_args()

    suites = tuple(args.suite or SUITES)
    run = MulluEvalRunner().run(suites=suites, strict=args.strict)
    payload = run.to_json_dict()
    encoded = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n", encoding="utf-8")
    print(encoded)
    if args.strict and run.promotion_blocked:
        return 1
    if not run.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

