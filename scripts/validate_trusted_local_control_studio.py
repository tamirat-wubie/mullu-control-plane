#!/usr/bin/env python3
"""Validate the trusted local control studio authorization.

Purpose: verify that AGENTS.md and the operator-facing control-studio document
preserve local Codex autonomy without weakening hard external-effect boundaries.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, AGENTS.md, and
docs/TRUSTED_LOCAL_CONTROL_STUDIO.md.
Invariants:
  - Validation is read-only and deterministic.
  - Local autonomy remains scoped to repository-governed work.
  - Secret handling permits task-relevant inspection but blocks disclosure and
    exfiltration.
  - Destructive, legal, financial, public, deployment, external-account,
    platform, connector, and Mullusi hard-law boundaries remain explicit.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = WORKSPACE_ROOT / "AGENTS.md"
DEFAULT_DOC_PATH = WORKSPACE_ROOT / "docs" / "TRUSTED_LOCAL_CONTROL_STUDIO.md"


@dataclass(frozen=True, slots=True)
class StudioFinding:
    """One deterministic trusted-control-studio validation finding."""

    rule_id: str
    message: str


REQUIRED_POLICY_PHRASES = (
    "## Trusted Local Control Studio Authorization",
    "Mullusi control studio",
    "trusted symbolic intelligence operator",
    "Inspect repository files, local configuration, logs, receipts, schemas,",
    "Edit repository-local files, create governed artifacts, run deterministic",
    "Use available network access for documentation lookup, package metadata,",
    "Treat local secrets as operator-owned sensitive inputs, not as hidden state.",
    "must avoid unnecessary disclosure in outputs, and must not exfiltrate them.",
    "Hard boundaries that remain in force:",
    "Do not perform destructive operations outside the intended workspace unless",
    "Do not move money, file legal paperwork, publish production systems, contact",
    "Do not bypass platform-level Codex controls, operating-system permission",
    "connector authentication boundaries, or Mullusi hard governance",
    "Do not print full secret values, private keys, access tokens, or credentials",
    "classify it as",
    "`AwaitingEvidence` until the required witness or task instruction exists.",
)

REQUIRED_DOC_PHRASES = (
    "# Trusted Local Control Studio",
    "Purpose: define the repository-local trusted control studio authorization",
    "Dependencies: AGENTS.md, docs/FOUNDATION_MODE.md, scripts/validate_trusted_local_control_studio.py.",
    "## Authorization Boundary",
    "## Secret Handling",
    "## Hard Stop Rules",
    "## Validation",
    "python scripts/validate_trusted_local_control_studio.py",
    "Inspect secret values only when materially required by the active task.",
    "Do not print full tokens, private keys, passwords, recovery codes, or access",
    "Do not persist raw secret values in Git, docs, fixtures, logs, receipts, or",
    "Bypass platform-level controls, operating-system permission controls, or",
    "STATUS:",
)

FORBIDDEN_POLICY_PHRASES = (
    "no restriction",
    "unlimited authority",
    "may bypass platform",
    "can bypass platform",
    "ignore connector authentication",
    "always print secrets",
    "commit raw credentials",
)


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit filesystem errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def validate_studio_policy(policy_text: str, doc_text: str) -> list[StudioFinding]:
    """Return deterministic findings for trusted local control studio policy."""

    findings: list[StudioFinding] = []
    findings.extend(_require_phrases("missing-policy-phrase", policy_text, REQUIRED_POLICY_PHRASES))
    findings.extend(_require_phrases("missing-doc-phrase", doc_text, REQUIRED_DOC_PHRASES))
    findings.extend(_reject_forbidden_policy_phrases(policy_text))
    return findings


def main(argv: list[str] | None = None) -> int:
    """Validate trusted local control studio artifacts and print an audit result."""

    parser = argparse.ArgumentParser(description="Validate trusted local control studio authorization.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    args = parser.parse_args(argv)

    try:
        policy_text = load_text(args.policy, "AGENTS.md policy")
        doc_text = load_text(args.doc, "trusted local control studio document")
    except OSError as exc:
        sys.stderr.write(f"[FAIL] load-trusted-local-control-studio: {exc}\nSTATUS: failed\n")
        return 1

    findings = validate_studio_policy(policy_text, doc_text)
    if findings:
        for finding in findings:
            sys.stderr.write(f"[FAIL] {finding.rule_id}: {finding.message}\n")
        sys.stderr.write("STATUS: failed\n")
        return 1

    sys.stdout.write("[PASS] trusted_local_control_studio_policy\n")
    sys.stdout.write("[PASS] trusted_local_control_studio_secret_boundary\n")
    sys.stdout.write("[PASS] trusted_local_control_studio_hard_boundaries\n")
    sys.stdout.write("STATUS: passed\n")
    return 0


def _require_phrases(rule_id: str, artifact_text: str, phrases: tuple[str, ...]) -> list[StudioFinding]:
    return [
        StudioFinding(rule_id, f"required phrase is absent: {phrase}")
        for phrase in phrases
        if phrase not in artifact_text
    ]


def _reject_forbidden_policy_phrases(policy_text: str) -> list[StudioFinding]:
    normalized_policy = policy_text.casefold()
    return [
        StudioFinding("forbidden-policy-phrase", f"forbidden phrase appears: {phrase}")
        for phrase in FORBIDDEN_POLICY_PHRASES
        if phrase in normalized_policy
    ]


if __name__ == "__main__":
    raise SystemExit(main())
