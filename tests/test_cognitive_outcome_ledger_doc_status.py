"""Tests for cognitive outcome ledger implementation-status documentation.

Purpose: prevent the cognitive outcome ledger design doc from regressing to
stale in-review or pre-implementation campaign wording.
Governance scope: documentation drift for cognitive loop D1 ledger, Stage E
gate enrichment, and engine thread-safety implementation status.
Dependencies: docs/design/COGNITIVE_OUTCOME_LEDGER.md, cognitive ledger
runtime files, and the Stage E gate enrichment tests.
Invariants: implemented surfaces are marked merged, superseded PR status is
explicit, durable ledger wording is bounded, and stale future language is absent.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "design" / "COGNITIVE_OUTCOME_LEDGER.md"
LEDGER_RUNTIME_PATH = REPO_ROOT / "mcoi" / "mcoi_runtime" / "persistence" / "cognitive_outcome_ledger.py"
REHYDRATE_RUNTIME_PATH = REPO_ROOT / "mcoi" / "mcoi_runtime" / "app" / "cognitive_runtime_integration.py"
GATE_ENRICHMENT_TEST_PATH = REPO_ROOT / "mcoi" / "tests" / "test_cognitive_gate_enriched.py"


def test_cognitive_outcome_ledger_doc_declares_merged_runtime_surfaces() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    assert DOC_PATH.exists()
    assert LEDGER_RUNTIME_PATH.exists()
    assert REHYDRATE_RUNTIME_PATH.exists()
    assert GATE_ENRICHMENT_TEST_PATH.exists()
    assert "Status: **IMPLEMENTED for the first file-backed D1 ledger slice" in content
    assert "| Engine thread-safety (memory.py) | MERGED | #1267 |" in content
    assert "| D1 — file-backed cognitive outcome ledger | MERGED | #1280 |" in content
    assert "| E — gate-enrichment (safety-positive) | MERGED | #1283 (supersedes closed #1274) |" in content
    assert "`FileBackedCognitiveOutcomeLedger`" in content
    assert "`MULLU_COGNITIVE_LOOP_LEDGER`" in content


def test_cognitive_outcome_ledger_doc_rejects_stale_preimplementation_language() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    normalized_content = " ".join(content.split())
    stale_phrases = (
        "no code in this PR",
        "| Engine thread-safety (memory.py) | IN REVIEW | #1267 |",
        "| E — gate-enrichment (safety-positive) | IN REVIEW | #1274 |",
        "**No durable substrate**",
        "Land #1267 first",
        "then implement the selected file-backed",
    )

    assert all(phrase not in content for phrase in stale_phrases)
    assert "**Durable substrate**" in content
    assert "rehydrates `meta_reasoning` and" in content
    assert "The implemented file-backed slice closes the single-host restart-safety gap" in content
    assert "The remaining open gap is shared multi-host coherence" in normalized_content
    assert "Postgres/shared-stream backend" in normalized_content
