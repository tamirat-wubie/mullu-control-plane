#!/usr/bin/env python3
"""Validate the Phi2-GPS v3 platform overlay in the canonical Phi spec.

Purpose: keep the accepted v3 platform overlay attached to the canonical Phi
specification without claiming completed external effect-bearing runtime.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and docs/PHI_CANONICAL_SPEC.md.
Invariants:
  - Validation is read-only and deterministic.
  - The v3 overlay remains additive over the v2.2 kernel.
  - Runtime, deployment, and adapter completion claims stay bounded.
  - Ledgers, gates, receipts, failure taxonomy, and acceptance tests remain explicit.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC_PATH = WORKSPACE_ROOT / "docs" / "PHI_CANONICAL_SPEC.md"


@dataclass(frozen=True, slots=True)
class SpecFinding:
    """One deterministic validation finding for the v3 overlay."""

    rule_id: str
    message: str


REQUIRED_PHRASES: tuple[tuple[str, str], ...] = (
    ("schema-banner", "platform overlay: phi2-gps-v3"),
    ("additive-wrapper", "Phi2-GPS v3 is accepted as an additive engineering platform around the v2.2 kernel."),
    ("local-runtime-contracts", "Repository-local v3 runtime contracts:    SolvedVerified"),
    ("external-adapter-bound", "Effect-bearing external adapter execution: AwaitingEvidence"),
    ("platform-law", "Phi2_GPS_v3(Praw)"),
    ("compile-route-certify", "Compile(Praw -> P*)"),
    ("layers", "L0 | Intake Layer"),
    ("compiler", "ProblemCompiler(raw) -> CompiledProblem"),
    ("contradiction-ledger", "`ContradictionLedger` is append-only."),
    ("belief-ledger", "`BeliefLedger` is append-only."),
    ("action-gate", "`ActionGate` classifies every proposed action as epistemic, world-changing, or hybrid."),
    ("counterfactual-lab", "`CounterfactualLab` runs before irreversible or high-risk action."),
    ("representation-lab", "`RepresentationLab` may split, merge, reparameterize"),
    ("shape-engine", "irreversibility_score"),
    ("failure-taxonomy", "FailureKind :="),
    ("adapter-contract", "rollback_or_compensate(action, result) -> RollbackResult"),
    ("uao-no-bypass", "No adapter action may bypass Universal Action Orchestration"),
    ("acceptance-tests", "A v3 repository-local implementation is runtime-closed only when it passes these deterministic tests:"),
    ("milestone-1-runtime-contracts", "Status: implemented as immutable runtime data contracts"),
    ("milestone-2-problem-compiler", "Status: implemented as deterministic `ProblemCompiler.compile(...)` data-path"),
    ("milestone-3-registries", "Status: implemented as deterministic `PlatformRegistry`, `RegistryRecord`, `ContradictionLedger`, and `BeliefLedger` contracts."),
    ("milestone-4-router", "Status: implemented as `route_solver(...)` and `SolverRoute`."),
    ("milestone-5-execution-loop", "Status: implemented as local `run_platform_cycle(...)` with world-changing actions blocked unless explicitly authorized."),
    ("milestone-6-verification", "Status: implemented as `PlatformVerificationCertificate`, `verify_platform_result(...)`, and proof receipt emission."),
    ("milestone-7-labs", "Status: implemented as deterministic `CounterfactualLab` and generic `RepresentationLab` operator acceptance records; specialized domain transforms remain adapter evidence."),
    ("milestone-8-adapter-harness", "Status: implemented as `DeterministicPlatformAdapter` contract harness for local simulation; effect-bearing external adapters remain AwaitingEvidence."),
    ("roadmap", "Phi2-GPS v3 acceptance-test harness"),
    ("status", "Phi2-GPS v3 overlay     ACCEPTED SPEC"),
    ("footer", "Platform overlay: `phi2-gps-v3`"),
)


ORDERED_SECTIONS: tuple[str, ...] = (
    "## PART V",
    "## PART V-A - Phi2-GPS v3: ENGINEERING PLATFORM OVERLAY",
    "## PART VI",
)


def load_spec(spec_path: Path) -> str:
    """Load the canonical spec with explicit read errors."""

    if not spec_path.exists():
        raise FileNotFoundError(f"missing canonical Phi spec: {spec_path}")
    if not spec_path.is_file():
        raise IsADirectoryError(f"canonical Phi spec path is not a file: {spec_path}")
    return spec_path.read_text(encoding="utf-8")


def validate_spec(spec_text: str) -> list[SpecFinding]:
    """Return deterministic findings for the v3 platform overlay."""

    findings: list[SpecFinding] = []
    findings.extend(_validate_required_phrases(spec_text))
    findings.extend(_validate_section_order(spec_text))
    findings.extend(_validate_runtime_claim_bounds(spec_text))
    return findings


def _validate_required_phrases(spec_text: str) -> list[SpecFinding]:
    return [
        SpecFinding(rule_id, f"required v3 overlay phrase is absent: {phrase}")
        for rule_id, phrase in REQUIRED_PHRASES
        if phrase not in spec_text
    ]


def _validate_section_order(spec_text: str) -> list[SpecFinding]:
    indexes: list[int] = []
    findings: list[SpecFinding] = []
    for section in ORDERED_SECTIONS:
        index = spec_text.find(section)
        if index < 0:
            findings.append(SpecFinding("missing-section", f"section is absent: {section}"))
        indexes.append(index)

    if findings:
        return findings
    if indexes != sorted(indexes):
        return [SpecFinding("section-order", "v3 overlay must sit between Part V and Part VI")]
    return []


def _validate_runtime_claim_bounds(spec_text: str) -> list[SpecFinding]:
    findings: list[SpecFinding] = []
    blocked_claims = (
        "Effect-bearing external adapter execution: SolvedVerified",
        "External deployment:      SolvedVerified",
        "OPEN-WORLD AUTONOMY:     YES",
    )
    for claim in blocked_claims:
        if claim in spec_text:
            findings.append(SpecFinding("unbounded-v3-claim", f"blocked claim appears: {claim}"))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate the canonical Phi2-GPS v3 platform overlay."""

    parser = argparse.ArgumentParser(description="Validate canonical Phi2-GPS v3 platform overlay.")
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC_PATH)
    args = parser.parse_args(argv)

    try:
        spec_text = load_spec(args.spec)
    except OSError as exc:
        sys.stderr.write(f"[FAIL] load-spec: {exc}\nSTATUS: failed\n")
        return 1

    findings = validate_spec(spec_text)
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] phi_gps_v3_overlay_present\n")
    sys.stdout.write("[PASS] phi_gps_v3_runtime_claims_bounded\n")
    sys.stdout.write("[PASS] phi_gps_v3_governance_contract\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
