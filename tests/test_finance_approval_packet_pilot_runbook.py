"""Tests for the finance approval packet pilot runbook.

Purpose: prove the operator runbook preserves the live handoff promotion
boundary and strict readiness commands.
Governance scope: finance handoff documentation, live receipt validation,
promotion-boundary language, and strict promotion command visibility.
Dependencies: docs/63_finance_approval_packet_pilot.md.
Invariants:
  - The runbook documents live receipt readiness validation.
  - The runbook separates promotion_boundary.ok from promotion_boundary.ready.
  - The runbook exposes the strict --require-ready promotion chain.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "63_finance_approval_packet_pilot.md"


def test_finance_runbook_documents_strict_promotion_boundary() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")

    assert "python scripts\\validate_finance_approval_email_calendar_live_receipt.py --require-ready --json" in content
    assert "python scripts\\validate_finance_approval_live_handoff_chain.py --strict --json" in content
    assert "python scripts\\validate_finance_approval_live_handoff_chain.py --strict --require-ready --json" in content
    assert "python scripts\\produce_finance_approval_operator_summary.py --output .change_assurance\\finance_approval_operator_summary.json --strict --json" in content
    assert "python scripts\\validate_finance_approval_operator_summary_schema.py --strict --json" in content
    assert "`promotion_boundary.ok` separately from `promotion_boundary.ready`" in content
    assert "operator summary is a redacted read-only artifact" in content
    assert "`ok=true` means the packet artifacts are structurally usable" in content
    assert "`ready=false` means live handoff promotion remains blocked" in content
    assert "16-command dry-run artifact" in content
    assert "only live connector touchpoint" in content
    assert "validates the aggregate handoff chain" in content
    assert "validates the operator summary schema" in content
    assert "protocol manifest ok: 88 schemas" in content
