"""Tests for the Observation Evidence Acquisition Architecture validator.

Purpose: prove the observation architecture remains evidence-bound,
Foundation Mode safe, and non-executing.
Governance scope: observation evidence packets, planning-input admission,
world-state projection, live-provider witness blocking, glossary anchoring,
and platform overview discovery.
Dependencies: scripts.validate_observation_evidence_acquisition_architecture.
Invariants: observation is not execution; evidence packets are not truth
commits; hard-constraint planning blocks on Unknown evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_observation_evidence_acquisition_architecture import (  # noqa: E402
    DEFAULT_DOC_PATH,
    DEFAULT_GLOSSARY_PATH,
    DEFAULT_PLATFORM_PATH,
    REQUIRED_PACKET_FIELDS,
    REQUIRED_SOURCE_CLASSES,
    load_text,
    validate_doc_text,
    validate_glossary,
    validate_observation_evidence_acquisition_architecture,
    validate_platform_overview,
)


def test_observation_architecture_artifacts_pass() -> None:
    findings = validate_observation_evidence_acquisition_architecture()
    doc_text = load_text(DEFAULT_DOC_PATH, "observation architecture doc")
    platform_text = load_text(DEFAULT_PLATFORM_PATH, "platform overview")

    assert findings == []
    assert "Observation Evidence Acquisition Architecture" in doc_text
    assert "docs/94_observation_evidence_acquisition_architecture.md" in platform_text


def test_doc_preserves_packet_fields_source_classes_and_hard_block() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "observation architecture doc")

    assert all(field in doc_text for field in REQUIRED_PACKET_FIELDS)
    assert all(source_class in doc_text for source_class in REQUIRED_SOURCE_CLASSES)
    assert "evidence.ProofState in {Unknown, BudgetUnknown}" in doc_text
    assert "-> block planning use and plan sensing" in doc_text


def test_doc_rejects_missing_evidence_packet_anchor() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "observation architecture doc")
    candidate = doc_text.replace("EvidencePacket", "PacketRemoved")
    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "observation_architecture_doc_phrase_missing" for finding in findings)
    assert any("EvidencePacket" in finding.message for finding in findings)


def test_doc_rejects_live_observation_overclaim() -> None:
    doc_text = load_text(DEFAULT_DOC_PATH, "observation architecture doc")
    candidate = f"{doc_text}\nlive provider observation is ready\n"
    findings = validate_doc_text(candidate)

    assert findings
    assert any(finding.rule_id == "live_observation_verified_overclaim" for finding in findings)
    assert all(finding.rule_id != "forbidden_artificial_intelligence_term" for finding in findings)


def test_platform_and_glossary_links_are_required() -> None:
    platform_text = load_text(DEFAULT_PLATFORM_PATH, "platform overview")
    glossary_text = load_text(DEFAULT_GLOSSARY_PATH, "glossary")

    assert validate_platform_overview(platform_text) == []
    assert validate_glossary(glossary_text) == []
    assert validate_platform_overview(platform_text.replace("docs/94_observation_evidence_acquisition_architecture.md", "")) != []
    assert validate_glossary(glossary_text.replace("### Evidence packet", "")) != []
