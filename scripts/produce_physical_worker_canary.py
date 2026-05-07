"""Produce the physical worker canary artifact.

Purpose: write a deterministic, hash-bound runtime witness for physical-worker
canary admission.
Governance scope: physical worker sandbox canary production only.
Dependencies: gateway.physical_worker_canary.
Invariants:
  - The producer does not dispatch live physical effects.
  - The written artifact is the canary artifact JSON projection.
  - Strict mode fails closed when the canary fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
MCOI_ROOT = REPO_ROOT / "mcoi"
for path in (REPO_ROOT, MCOI_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gateway.physical_worker_canary import PhysicalWorkerCanaryArtifact, run_physical_worker_canary  # noqa: E402


DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "physical_worker_canary.json"


def produce_physical_worker_canary(*, output_path: Path = DEFAULT_OUTPUT) -> PhysicalWorkerCanaryArtifact:
    """Run the physical worker canary and write its deterministic artifact."""
    if not isinstance(output_path, Path):
        raise TypeError("output_path must be a Path")
    artifact = run_physical_worker_canary()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifact


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the canary producer command-line contract."""
    parser = argparse.ArgumentParser(description="Produce the physical worker canary artifact.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the canary producer CLI."""
    args = parse_args(argv)
    artifact = produce_physical_worker_canary(output_path=args.output)
    if args.emit_json:
        print(json.dumps(artifact.to_json_dict(), sort_keys=True))
    if args.strict and not artifact.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
