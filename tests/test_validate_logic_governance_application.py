"""Tests for the logic governance application validator.

Purpose: prove the logic doctrine remains complete enough to govern code,
schema, proof, Phi traversal, and Mfidel substrate changes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_logic_governance_application and
docs/60_logic_governance_application.md.
Invariants:
  - Required logic sections remain present.
  - Mfidel atomicity constraints remain explicit.
  - PRS fields and halt conditions remain auditable.
"""

from __future__ import annotations

from scripts.validate_logic_governance_application import (
    FORBIDDEN_LITERALS,
    LOGIC_GOVERNANCE_DOC,
    REQUIRED_HALT_LITERALS,
    REQUIRED_MFIDEL_LITERALS,
    REQUIRED_PREDICATES,
    REQUIRED_PRS_FIELDS,
    REQUIRED_SECTIONS,
    validate_logic_governance_document,
    validate_logic_governance_text,
    validation_report,
)


def test_logic_governance_document_is_complete() -> None:
    content = LOGIC_GOVERNANCE_DOC.read_text(encoding="utf-8")
    errors = validate_logic_governance_document()

    assert errors == []
    assert "# Logic Governance Application" in content
    assert "Governance Law Mapping" in content
    assert "Proof-of-Resolution Stamp Template" in content


def test_logic_governance_validator_reports_missing_required_section() -> None:
    content = LOGIC_GOVERNANCE_DOC.read_text(encoding="utf-8")
    broken = content.replace("## 5. Governance Law Mapping", "## 5. Removed")

    errors = validate_logic_governance_text(broken)

    assert len(errors) == 1
    assert errors[0] == "missing section: ## 5. Governance Law Mapping"
    assert "Removed" not in errors[0]


def test_logic_governance_validator_reports_mfidel_drift() -> None:
    content = LOGIC_GOVERNANCE_DOC.read_text(encoding="utf-8")
    broken = content.replace(REQUIRED_MFIDEL_LITERALS[1], "No substrate sentence")

    errors = validate_logic_governance_text(broken)

    assert len(errors) == 1
    assert errors[0].startswith("missing Mfidel invariant:")
    assert "Unicode normalization" in errors[0]


def test_logic_governance_validator_reports_forbidden_literal() -> None:
    content = LOGIC_GOVERNANCE_DOC.read_text(encoding="utf-8")
    broken = f"{content}\n{FORBIDDEN_LITERALS[0]}\n"

    errors = validate_logic_governance_text(broken)

    assert len(errors) == 1
    assert errors[0] == f"forbidden literal present: {FORBIDDEN_LITERALS[0]}"
    assert "symbolic intelligence" not in errors[0]


def test_logic_governance_report_is_deterministic() -> None:
    report = validation_report()

    assert report["document"] == "docs/60_logic_governance_application.md"
    assert report["passed"] is True
    assert report["errors"] == []
    assert report["required_sections"] == list(REQUIRED_SECTIONS)
    assert report["required_predicates"] == list(REQUIRED_PREDICATES)
    assert len(report["required_laws"]) == 7


def test_required_logic_contract_lists_are_non_empty_and_bounded() -> None:
    assert len(REQUIRED_SECTIONS) >= 10
    assert len(REQUIRED_PREDICATES) == 10
    assert len(REQUIRED_HALT_LITERALS) == 10
    assert len(REQUIRED_MFIDEL_LITERALS) >= 5
    assert len(REQUIRED_PRS_FIELDS) == 9
