"""Tests for nested-mind operator documentation.

Purpose: keep the documented live-observation flow aligned with safe CLI gates.
Governance scope: documentation contract only; no nested-mind network calls.
Dependencies: docs/design/nested-mind-integration-seam.md and operator scripts.
Invariants: evidence reporting happens before P3 validation and blocked
automation cannot silently advance.
"""

from __future__ import annotations

from pathlib import Path


DOC_PATH = Path(__file__).resolve().parents[1] / "docs" / "design" / "nested-mind-integration-seam.md"


def test_operator_doc_lists_read_only_report_before_p3_validation() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")
    report_command = "python scripts\\report_nested_mind_evidence.py"
    validate_command = "python scripts\\validate_nested_mind_p3_readiness.py"

    assert report_command in text
    assert validate_command in text
    assert text.index(report_command) < text.index(validate_command)


def test_operator_doc_states_blocked_report_exit_contract() -> None:
    text = " ".join(DOC_PATH.read_text(encoding="utf-8").split())

    assert "It exits with `0` only when the readiness validator reports `ready`" in text
    assert "blocked reports exit with `1`" in text
    assert "automation cannot silently advance P3" in text


def test_operator_doc_states_corrupted_evidence_is_not_blocked_json() -> None:
    text = " ".join(DOC_PATH.read_text(encoding="utf-8").split())

    assert "Malformed or corrupted evidence stores raise a typed persistence error" in text
    assert "do not emit a normal blocked readiness JSON object" in text


def test_operator_doc_aligns_phase2_projection_import_status() -> None:
    text = " ".join(DOC_PATH.read_text(encoding="utf-8").split())

    assert "Phase 2 typed projection import is implemented" in text
    assert "runtime-only read-model contract" in text
    assert "does not admit content into semantic or procedural memory" in text
    assert "does not create a public Mullu Governance Protocol schema" in text
    assert "Phase 2 may import" not in text
    assert "A later Phase 2 can add" not in text
    assert "does not yet import nested-mind projection" not in text


def test_operator_doc_keeps_symbol_flow_ascii_stable() -> None:
    text = DOC_PATH.read_text(encoding="utf-8")

    assert "Nested-mind Gamma response" in text
    assert "Mullu Phi_gov" in text
    assert "-> NestedMindProjectionEnvelope" in text
    assert "\u2192" not in text
    assert "\u2193" not in text
    assert "\u2014" not in text
