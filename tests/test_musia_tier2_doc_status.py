"""Tests for MUSIA Tier 2 implementation-reference status.

Purpose: prevent implemented Tier 2 docs from regressing to future/stub wording.
Governance scope: documentation drift for structural constructs and the
software-dev adapter integration reference.
Dependencies: docs/MUSIA_TIER_2_INTERFACES_DRAFT.md and implemented Tier 2
runtime/test files.
Invariants: implementation references exist, status is implemented, deferred
soak risk stays explicit, and stale placeholder language is absent.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "MUSIA_TIER_2_INTERFACES_DRAFT.md"
IMPLEMENTATION_PATH = REPO_ROOT / "mcoi" / "mcoi_runtime" / "substrate" / "constructs" / "tier2_structural.py"
TEST_PATH = REPO_ROOT / "mcoi" / "tests" / "test_tier2_structural.py"


def test_musia_tier2_reference_declares_implemented_surface() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    assert DOC_PATH.exists()
    assert IMPLEMENTATION_PATH.exists()
    assert TEST_PATH.exists()
    assert "**Status:** IMPLEMENTED" in content
    assert "## Status: IMPLEMENTED" in content
    assert "mcoi/mcoi_runtime/substrate/constructs/tier2_structural.py" in content
    assert "mcoi/tests/test_tier2_structural.py" in content


def test_musia_tier2_reference_rejects_stale_stub_language() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    stale_phrases = (
        "stub into a real consumer",
        "stub-shaped placeholder",
        "Once Tier 2 ships",
        "no change needed at draft time",
    )

    assert all(phrase not in content for phrase in stale_phrases)
    assert "SCCCECycle.to_universal_result_kwargs()" in content
    assert "mcoi/tests/test_cognition.py" in content
    assert "Production soak remains deferred by user direction" in content

