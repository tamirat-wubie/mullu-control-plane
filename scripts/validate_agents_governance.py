#!/usr/bin/env python3
"""Validate the repository AGENTS.md governance policy.

Purpose: verify that the repository instruction file preserves the Mullusi
symbolic intelligence policy surface and local preflight contract.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and AGENTS.md.
Invariants:
  - Validation is read-only and deterministic.
  - Required governance sections remain present.
  - Mfidel atomicity and no-silent-failure constraints remain explicit.
  - Local policy validation commands point to repository-local scripts.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = WORKSPACE_ROOT / "AGENTS.md"
FORBIDDEN_PHRASES = ("artificial " + "intelligence", "A" + "I")


@dataclass(frozen=True, slots=True)
class RequiredSection:
    """One required AGENTS.md section and its proof phrase."""

    heading: str
    proof_phrase: str


@dataclass(frozen=True, slots=True)
class GovernanceFinding:
    """One deterministic governance policy validation finding."""

    rule_id: str
    message: str


REQUIRED_SECTIONS = (
    RequiredSection("Identity", "symbolic intelligence developer agent"),
    RequiredSection("Trusted Local Control Studio Authorization", "trusted symbolic intelligence operator"),
    RequiredSection("Core Governance Laws", "Ontological Completeness Enforcement"),
    RequiredSection("Phi Traversal Spine", "Distinction: boundaries"),
    RequiredSection("Phi Variant Naming", "All governed state writes route through `Phi_gov`."),
    RequiredSection("Phi GPS v3 Platform Overlay", "`Phi_gps` v3 is an additive engineering platform"),
    RequiredSection("Universal Action Orchestration", "Every effect-bearing action must pass through"),
    RequiredSection("ProofState Discipline", "Resource pressure never permits"),
    RequiredSection("Solver Outcome Taxonomy", "SolvedVerified"),
    RequiredSection("Code Generation Rules", "No silent failures"),
    RequiredSection("Mfidel Enforcement", "Each fidel is atomic"),
    RequiredSection("Project Discipline Mesh", "Never silently skip a discipline"),
    RequiredSection("Deterministic Memory Routing System", "Guarantees: deterministic"),
    RequiredSection("SCCE Cognitive Cycle", "Total tension"),
    RequiredSection("Workflow Preferences", "Architecture first"),
    RequiredSection("Output Contract", "STATUS:"),
    RequiredSection("Operating-System Capability Use", "run builds, tests, formatters, and linters"),
    RequiredSection("Policy Validation", "python scripts/run_workspace_governance_checks.py"),
)

REQUIRED_PHRASES = (
    "Use \"symbolic intelligence\" terminology exclusively.",
    "All rejected deltas must be logged. No silent failures.",
    "No-bypass rule:",
    "Do not apply Unicode decomposition, recomposition, or normalization to fidel codepoints.",
    "Overlay and fusion are sound-layer operations only, never structural breakdowns.",
    "If code, a model, or a process would violate fidel atomicity, refuse that path",
    "Use available computer-use capabilities when they materially advance the task:",
    "edit files through auditable patches;",
    "The runner is read-only and must pass before claiming the workspace policy surface is intact.",
    "python scripts/validate_agents_governance.py",
    "python scripts/run_workspace_governance_checks.py --json --max-workers 8 --per-check-timeout-seconds 120",
    "python scripts/run_workspace_governance_checks.py --json --max-workers 8 --per-check-timeout-seconds 120 --receipt-path .tmp/workspace-governance-preflight-receipt.json",
    "python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt.json",
    "python scripts/validate_workspace_governance_preflight_receipt_contract.py",
    "Treat repository-local v3 runtime contracts as claimable only through named validators and receipts;",
    "secret presence, names, scopes, and bounded shape",
    "Raw secret values require explicit task-scoped operator",
    "Do not read or print full secret values, private keys, access tokens, or",
)

STATUS_CONTRACT_LINES = (
    "  Completeness: [percent]",
    "  Invariants verified: [list]",
    "  Open issues: [list or \"none\"]",
    "  Next action: [what follows]",
)


def load_policy(policy_path: Path) -> str:
    """Load a repository policy file with explicit read errors."""

    if not policy_path.exists():
        raise FileNotFoundError(f"missing governance policy: {policy_path}")
    if not policy_path.is_file():
        raise IsADirectoryError(f"governance policy path is not a file: {policy_path}")
    return policy_path.read_text(encoding="utf-8")


def validate_policy(policy_text: str) -> list[GovernanceFinding]:
    """Return deterministic findings for a repository AGENTS.md policy."""

    findings: list[GovernanceFinding] = []
    findings.extend(_validate_required_sections(policy_text))
    findings.extend(_validate_required_phrases(policy_text))
    findings.extend(_validate_forbidden_vocabulary(policy_text))
    findings.extend(_validate_status_contract(policy_text))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate the repository AGENTS.md policy and print an auditable result."""

    parser = argparse.ArgumentParser(description="Validate repository AGENTS.md governance policy.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    args = parser.parse_args(argv)

    try:
        policy_text = load_policy(args.policy)
    except OSError as exc:
        sys.stderr.write(f"[FAIL] load-policy: {exc}\nSTATUS: failed\n")
        return 1

    findings = validate_policy(policy_text)
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] agents_policy_governance_surface\n")
    sys.stdout.write("[PASS] mfidel_atomicity_policy\n")
    sys.stdout.write("[PASS] universal_action_orchestration_policy\n")
    sys.stdout.write("[PASS] status_contract\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


def _validate_required_sections(policy_text: str) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    for section in REQUIRED_SECTIONS:
        heading = f"## {section.heading}"
        if heading not in policy_text:
            findings.append(GovernanceFinding("missing-section", f"{section.heading}: heading is absent"))
        if section.proof_phrase not in policy_text:
            findings.append(
                GovernanceFinding("missing-section-proof", f"{section.heading}: proof phrase is absent")
            )
    return findings


def _validate_required_phrases(policy_text: str) -> list[GovernanceFinding]:
    return [
        GovernanceFinding("missing-policy-phrase", f"required phrase is absent: {phrase}")
        for phrase in REQUIRED_PHRASES
        if phrase not in policy_text
    ]


def _validate_forbidden_vocabulary(policy_text: str) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    for phrase in FORBIDDEN_PHRASES:
        phrase_pattern = rf"(?<![A-Za-z]){re.escape(phrase)}(?![A-Za-z])"
        if re.search(phrase_pattern, policy_text, flags=re.IGNORECASE):
            findings.append(GovernanceFinding("forbidden-vocabulary", "blocked vocabulary appears in AGENTS.md"))
    return findings


def _validate_status_contract(policy_text: str) -> list[GovernanceFinding]:
    return [
        GovernanceFinding("missing-status-contract", f"status contract line is absent: {line.strip()}")
        for line in STATUS_CONTRACT_LINES
        if line not in policy_text
    ]


if __name__ == "__main__":
    raise SystemExit(main())
