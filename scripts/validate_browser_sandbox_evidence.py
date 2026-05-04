#!/usr/bin/env python3
"""Validate governed browser sandbox evidence.

Purpose: fail closed unless browser sandbox evidence proves a rootless,
network-disabled, read-only browser-capability probe.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.produce_capability_adapter_live_receipts.
Invariants:
  - Missing, unreadable, or malformed evidence is invalid.
  - Evidence must be bound to a browser capability receipt.
  - Evidence must preserve sandbox isolation fields before live receipt use.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.produce_capability_adapter_live_receipts import (  # noqa: E402
    _validate_browser_sandbox_evidence,
)
from scripts.produce_browser_sandbox_evidence import DEFAULT_OUTPUT  # noqa: E402


@dataclass(frozen=True, slots=True)
class BrowserSandboxEvidenceValidation:
    """Validation result for one browser sandbox evidence file."""

    valid: bool
    evidence_path: str
    status: str
    detail: str
    evidence_id: str
    receipt_id: str
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        payload = asdict(self)
        payload["blockers"] = list(self.blockers)
        return payload


def validate_browser_sandbox_evidence(
    evidence_path: Path = DEFAULT_OUTPUT,
) -> BrowserSandboxEvidenceValidation:
    """Validate one browser sandbox evidence artifact."""
    result = _validate_browser_sandbox_evidence(str(evidence_path))
    blockers = tuple(str(blocker) for blocker in result["blockers"])
    return BrowserSandboxEvidenceValidation(
        valid=result["passed"] is True and not blockers,
        evidence_path=str(evidence_path),
        status=str(result["status"]),
        detail=str(result["detail"]),
        evidence_id=str(result["evidence_id"]),
        receipt_id=str(result["receipt_id"]),
        blockers=blockers,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse browser sandbox evidence validation arguments."""
    parser = argparse.ArgumentParser(description="Validate governed browser sandbox evidence.")
    parser.add_argument("--evidence", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for browser sandbox evidence validation."""
    args = parse_args(argv)
    result = validate_browser_sandbox_evidence(Path(args.evidence))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"browser sandbox evidence ok: {result.evidence_path}")
    else:
        for blocker in result.blockers:
            print(f"error: {blocker}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
