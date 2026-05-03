"""Conformance tests for the general-agent promotion operator runbook.

Purpose: keep the closure execution procedure aligned with governed artifacts.
Governance scope: aggregate closure validation, approval gates, live receipts, and status mutation.
Dependencies: docs/58_general_agent_promotion_operator_runbook.md.
Invariants: No forbidden terminology, no production claim without witness and health evidence.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "58_general_agent_promotion_operator_runbook.md"
FORBIDDEN_PHRASE = " ".join(("artificial", "intelligence"))


def _runbook_text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_runbook_preserves_symbolic_intelligence_language() -> None:
    runbook_text = _runbook_text()

    assert FORBIDDEN_PHRASE not in runbook_text.lower()
    assert "general-agent promotion" in runbook_text
    assert "pilot-governed-core" in runbook_text


def test_runbook_names_required_closure_artifacts_and_counts() -> None:
    runbook_text = _runbook_text()

    assert ".change_assurance\\general_agent_promotion_closure_plan.json" in runbook_text
    assert ".change_assurance\\general_agent_promotion_closure_plan_schema_validation.json" in runbook_text
    assert ".change_assurance\\general_agent_promotion_closure_plan_validation.json" in runbook_text
    assert "Total closure actions | 13" in runbook_text
    assert "Approval-required actions | 4" in runbook_text
    assert "adapter`, `deployment" in runbook_text


def test_runbook_keeps_status_mutation_evidence_gated() -> None:
    runbook_text = _runbook_text()

    assert "Do not update `DEPLOYMENT_STATUS.md`" in runbook_text
    assert "deployment_claim=published" in runbook_text
    assert "<gateway_url>/health" in runbook_text
    assert "produce_browser_sandbox_evidence.py" in runbook_text
    assert "validate_general_agent_promotion.py --strict" in runbook_text
    assert "validate_general_agent_promotion_closure_plan_schema.py" in runbook_text
    assert "STATUS:" in runbook_text
