#!/usr/bin/env python3
"""Validate governed runtime promotion readiness.

Purpose: expose a domain-neutral promotion validator while preserving the
existing general-agent promotion readiness contract.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.validate_general_agent_promotion.
Invariants:
  - The compatibility validator remains the single source of readiness truth.
  - Domain-neutral output does not rename or mutate existing evidence schemas.
  - Strict mode fails closed when production promotion blockers remain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_general_agent_promotion import (  # noqa: E402
    GeneralAgentPromotionReadiness,
    validate_general_agent_promotion,
    write_general_agent_promotion_readiness,
)

GovernedRuntimePromotionReadiness = GeneralAgentPromotionReadiness


def validate_governed_runtime_promotion(
    *,
    repo_root: Path = REPO_ROOT,
    deployment_status_path: Path | None = None,
    deployment_witness_path: Path | None = None,
    mcp_manifest_path: Path | None = None,
    adapter_evidence_path: Path | None = None,
) -> GovernedRuntimePromotionReadiness:
    """Validate whether this checkout may claim governed runtime promotion."""
    return validate_general_agent_promotion(
        repo_root=repo_root,
        deployment_status_path=deployment_status_path,
        deployment_witness_path=deployment_witness_path,
        mcp_manifest_path=mcp_manifest_path,
        adapter_evidence_path=adapter_evidence_path,
    )


def write_governed_runtime_promotion_readiness(
    readiness: GovernedRuntimePromotionReadiness,
    output_path: Path,
) -> Path:
    """Write the governed runtime promotion readiness artifact."""
    return write_general_agent_promotion_readiness(readiness, output_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for governed runtime promotion validation."""
    parser = argparse.ArgumentParser(
        description="Validate governed runtime promotion readiness.",
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--deployment-status", default="")
    parser.add_argument("--deployment-witness", default="")
    parser.add_argument("--mcp-manifest", default="")
    parser.add_argument("--adapter-evidence", default="")
    parser.add_argument("--output", default="")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print deterministic JSON readiness output.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when production promotion is blocked.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for governed runtime promotion validation."""
    args = parse_args(argv)
    readiness = validate_governed_runtime_promotion(
        repo_root=Path(args.repo_root),
        deployment_status_path=Path(args.deployment_status) if args.deployment_status else None,
        deployment_witness_path=Path(args.deployment_witness) if args.deployment_witness else None,
        mcp_manifest_path=Path(args.mcp_manifest) if args.mcp_manifest else None,
        adapter_evidence_path=Path(args.adapter_evidence) if args.adapter_evidence else None,
    )
    if args.json:
        print(json.dumps(readiness.as_dict(), indent=2, sort_keys=True))
    elif readiness.ready:
        print(
            "GOVERNED RUNTIME PROMOTION READY "
            f"capabilities={readiness.capability_count} capsules={readiness.capsule_count}"
        )
    else:
        print(
            "GOVERNED RUNTIME PROMOTION BLOCKED "
            f"level={readiness.readiness_level} blockers={list(readiness.blockers)}"
        )
        for check in readiness.checks:
            state = "pass" if check.passed else "block"
            print(f"{state}: {check.name}: {check.detail}")
    if args.output:
        output_path = write_governed_runtime_promotion_readiness(readiness, Path(args.output))
        if not args.json:
            print(f"governed_runtime_promotion_readiness_written: {output_path}")
    return 0 if readiness.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
