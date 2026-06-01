#!/usr/bin/env python3
"""Emit an SDLC closure receipt from the canonical example chain.

Purpose: provide a deterministic non-runtime closure receipt emitter for the
SDLC contract foundation.
Governance scope: OCE closure fields, RAG receipt references, CDCV example
chain causality, CQTE terminal-state checks, UWMA closure witness, and PRS
receipt emission.
Dependencies: Python standard library and scripts/validate_sdlc_artifact.py.
Invariants:
  - The emitter does not execute, deploy, publish, or merge anything.
  - The emitted closure must pass the same SDLC artifact validator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_sdlc_artifact import (  # noqa: E402
    ARTIFACT_SPEC_BY_KIND,
    load_json_object,
    validate_artifact_record,
)


def emit_closure_receipt(closure_path: Path | None = None) -> dict[str, object]:
    """Load and validate one closure receipt before emission."""

    resolved_path = ARTIFACT_SPEC_BY_KIND["closure_receipt"].example_path if closure_path is None else closure_path
    closure = load_json_object(resolved_path, "SDLC closure receipt")
    errors = validate_artifact_record("closure_receipt", closure)
    if errors:
        raise ValueError(f"invalid SDLC closure receipt: {len(errors)} error(s)")
    return closure


def write_closure_receipt(receipt: dict[str, object], output_path: Path) -> Path:
    """Write the closure receipt to a JSON file."""

    resolved_path = output_path if output_path.is_absolute() else WORKSPACE_ROOT / output_path
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved_path


def main(argv: list[str] | None = None) -> int:
    """Emit an SDLC closure receipt."""

    parser = argparse.ArgumentParser(description="Emit SDLC closure receipt.")
    parser.add_argument("--closure", type=Path, help="optional closure receipt source JSON path")
    parser.add_argument("--output", type=Path, help="optional output JSON path")
    args = parser.parse_args(argv)

    try:
        receipt = emit_closure_receipt(args.closure)
        if args.output is not None:
            write_closure_receipt(receipt, args.output)
        sys.stdout.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"[FAIL] sdlc-closure-receipt: {exc}\nSTATUS: failed\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
