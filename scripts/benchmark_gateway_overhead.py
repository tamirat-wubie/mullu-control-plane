"""Emit deterministic gateway overhead benchmark reports.

Purpose: provide a CI-safe benchmark harness for Mullusi, LiteLLM, and Portkey comparisons.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: argparse, json, pathlib, gateway benchmark harness.
Invariants: default execution performs no live network calls and emits a stable report hash.
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
    from mcoi_runtime.core.gateway_benchmark_harness import GatewayBenchmarkHarness

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for writing the JSON benchmark report.",
    )
    args = parser.parse_args()

    report = GatewayBenchmarkHarness().run()
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{encoded}\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
