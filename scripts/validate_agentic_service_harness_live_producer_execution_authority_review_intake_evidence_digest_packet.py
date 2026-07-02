#!/usr/bin/env python3
"""Compatibility validator for the live producer review intake evidence digest check.

Purpose: expose the workspace governance check name used by preflight receipts
while delegating validation to the canonical review intake digest packet
validator.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_agentic_service_harness_live_producer_execution_authority_review_intake_digest_packet.
Invariants: this wrapper grants no live execution, connector call, receipt
append, runtime write, mutation route, or terminal closure authority.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_live_producer_execution_authority_review_intake_digest_packet import main


if __name__ == "__main__":
    raise SystemExit(main())
