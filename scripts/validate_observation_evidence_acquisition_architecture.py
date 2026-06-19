#!/usr/bin/env python3
"""Validate the Observation Evidence Acquisition Architecture contract.

Purpose: keep the observation architecture evidence-bound, Foundation Mode
safe, and non-executing while it defines planning-input evidence rules.
Governance scope: OCE required anchors, RAG doc/glossary/platform links, CDCV
observation-to-planning causality, CQTE bounded admission states, UWMA witness
references, SRCA finite validation, and PRS focused closure.
Dependencies: docs/94_observation_evidence_acquisition_architecture.md,
docs/00_platform_overview.md, and docs/GLOSSARY.md.
Invariants:
  - Validation is read-only and deterministic.
  - Observation is not execution.
  - Evidence packets are not truth commits or terminal closure.
  - Hard-constraint planning must block on Unknown or BudgetUnknown evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOC_PATH = REPO_ROOT / "docs" / "94_observation_evidence_acquisition_architecture.md"
DEFAULT_PLATFORM_PATH = REPO_ROOT / "docs" / "00_platform_overview.md"
DEFAULT_GLOSSARY_PATH = REPO_ROOT / "docs" / "GLOSSARY.md"

REQUIRED_DOC_PHRASES = (
    "Observation Evidence Acquisition Architecture",
    "This is a Foundation Mode architecture contract, not a live-provider readiness",
    "What evidence is trusted enough to become planning input right now?",
    "ObservationRequest",
    "source authority preflight",
    "EvidencePacket",
    "EvidenceAdmissionDecision",
    "WorldStateProjection",
    "ProblemStar input",
    "evidence_packet != truth_commit",
    "evidence_packet != execution_authority",
    "evidence_packet != terminal_closure",
    "live provider evidence without live read witness -> AwaitingEvidence",
    "planning_input.requires_hard_constraint",
    "evidence.ProofState in {Unknown, BudgetUnknown}",
    "-> block planning use and plan sensing",
    "No observation failure may silently become a planning assumption.",
    "`freshness_pass_rate`",
    "`missing_evidence_block_rate`",
    "`closure_verification_rate`",
    "Grant live inbox, calendar, CI, provider, browser, deployment, or worker",
    "Treat evidence packets as truth commits.",
    "Mfidel atomicity preserved",
)
REQUIRED_PACKET_FIELDS = (
    "`packet_id`",
    "`observation_request_id`",
    "`source_kind`",
    "`source_ref`",
    "`observed_at`",
    "`fresh_until`",
    "`collector_ref`",
    "`authority_ref`",
    "`consent_scope_ref`",
    "`classification_ref`",
    "`payload_digest_ref`",
    "`planning_admission`",
    "`recovery_actions`",
    "`receipt_refs`",
)
REQUIRED_SOURCE_CLASSES = (
    "Repository",
    "CI",
    "Inbox or calendar",
    "Provider",
    "Worker",
    "Deployment",
    "Approval",
    "Browser or search",
    "Operator-supplied",
)
REQUIRED_PLATFORM_PHRASES = (
    "docs/94_observation_evidence_acquisition_architecture.md",
    "`Observation Evidence Acquisition Architecture` is the cross-platform intake contract",
)
REQUIRED_GLOSSARY_PHRASES = (
    "### Evidence packet",
    "### Observation Evidence Acquisition Architecture",
    "94_observation_evidence_acquisition_architecture.md",
)
FORBIDDEN_DOC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("forbidden_non_mullusi_intelligence_term", re.compile(r"\x61rtificial\s+\x69ntelligence", re.IGNORECASE)),
    ("forbidden_non_mullusi_abbreviation", re.compile(r"\b\x41\x49\b")),
    (
        "live_observation_verified_overclaim",
        re.compile(r"\blive (?:provider )?observation (?:is )?(?:verified|ready|closed)\b", re.IGNORECASE),
    ),
    (
        "execution_authority_granted_overclaim",
        re.compile(r"\bexecution authority (?:is )?granted\b", re.IGNORECASE),
    ),
    (
        "terminal_closure_allowed_overclaim",
        re.compile(r"\bterminal closure (?:is )?(?:allowed|granted|complete)\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True, slots=True)
class ObservationArchitectureFinding:
    """One deterministic observation-architecture validation finding."""

    rule_id: str
    message: str


def load_text(path: Path, label: str) -> str:
    """Load one text artifact with explicit path errors."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    return path.read_text(encoding="utf-8")


def validate_required_phrases(text: str, phrases: tuple[str, ...], rule_id: str, label: str) -> list[ObservationArchitectureFinding]:
    """Return findings for missing required phrases."""

    findings: list[ObservationArchitectureFinding] = []
    for phrase in phrases:
        if phrase not in text:
            findings.append(
                ObservationArchitectureFinding(
                    rule_id,
                    f"{label} missing required phrase: {phrase}",
                )
            )
    return findings


def validate_doc_text(text: str) -> list[ObservationArchitectureFinding]:
    """Return findings for observation architecture contract drift."""

    findings = [
        *validate_required_phrases(text, REQUIRED_DOC_PHRASES, "observation_architecture_doc_phrase_missing", "architecture doc"),
        *validate_required_phrases(text, REQUIRED_PACKET_FIELDS, "observation_architecture_packet_field_missing", "architecture doc"),
        *validate_required_phrases(text, REQUIRED_SOURCE_CLASSES, "observation_architecture_source_class_missing", "architecture doc"),
    ]
    for rule_id, pattern in FORBIDDEN_DOC_PATTERNS:
        if pattern.search(text):
            findings.append(
                ObservationArchitectureFinding(
                    rule_id,
                    f"architecture doc contains forbidden overclaim or term: {rule_id}",
                )
            )
    return findings


def validate_platform_overview(text: str) -> list[ObservationArchitectureFinding]:
    """Return findings for platform overview link drift."""

    return validate_required_phrases(
        text,
        REQUIRED_PLATFORM_PHRASES,
        "observation_architecture_platform_link_missing",
        "platform overview",
    )


def validate_glossary(text: str) -> list[ObservationArchitectureFinding]:
    """Return findings for glossary anchor drift."""

    return validate_required_phrases(
        text,
        REQUIRED_GLOSSARY_PHRASES,
        "observation_architecture_glossary_anchor_missing",
        "glossary",
    )


def validate_observation_evidence_acquisition_architecture(
    doc_path: Path = DEFAULT_DOC_PATH,
    platform_path: Path = DEFAULT_PLATFORM_PATH,
    glossary_path: Path = DEFAULT_GLOSSARY_PATH,
) -> list[ObservationArchitectureFinding]:
    """Validate observation architecture artifacts."""

    doc_text = load_text(doc_path, "observation architecture doc")
    platform_text = load_text(platform_path, "platform overview")
    glossary_text = load_text(glossary_path, "glossary")
    return [
        *validate_doc_text(doc_text),
        *validate_platform_overview(platform_text),
        *validate_glossary(glossary_text),
    ]


def main(argv: list[str] | None = None) -> int:
    """Validate observation architecture artifacts and print deterministic status."""

    parser = argparse.ArgumentParser(description="Validate Observation Evidence Acquisition Architecture artifacts.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC_PATH)
    parser.add_argument("--platform", type=Path, default=DEFAULT_PLATFORM_PATH)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY_PATH)
    args = parser.parse_args(argv)

    try:
        findings = validate_observation_evidence_acquisition_architecture(args.doc, args.platform, args.glossary)
    except OSError as exc:
        print(f"[FAIL] observation_architecture_load: {exc}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"[FAIL] {finding.rule_id}: {finding.message}", file=sys.stderr)
        print("STATUS: failed", file=sys.stderr)
        return 1
    print("[PASS] observation_architecture_doc")
    print("[PASS] observation_architecture_platform_link")
    print("[PASS] observation_architecture_glossary_links")
    print("STATUS: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
