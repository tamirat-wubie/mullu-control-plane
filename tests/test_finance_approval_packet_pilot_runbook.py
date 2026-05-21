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

from scripts.validate_protocol_manifest import load_manifest

ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "63_finance_approval_packet_pilot.md"


def test_finance_runbook_documents_strict_promotion_boundary() -> None:
    content = RUNBOOK.read_text(encoding="utf-8")
    manifest = load_manifest()
    expected_manifest_result = f"protocol manifest ok: {len(manifest['schemas'])} schemas"

    assert "python scripts\\validate_finance_approval_email_calendar_live_receipt.py --require-ready --json" in content
    assert "python scripts\\produce_finance_approval_handoff_packet.py --live-receipt .change_assurance\\email_calendar_live_receipt.json" in content
    assert "python scripts\\validate_finance_approval_live_handoff_chain.py --strict --json" in content
    assert "python scripts\\validate_finance_approval_live_handoff_chain.py --strict --require-ready --json" in content
    assert "python scripts\\produce_finance_approval_operator_summary.py --output .change_assurance\\finance_approval_operator_summary.json --strict --json" in content
    assert "python scripts\\validate_finance_approval_operator_summary_schema.py --strict --json" in content
    assert "python scripts\\validate_finance_email_calendar_recovery_env_example.py --template examples\\finance_email_calendar_recovery.env.example --strict --json" in content
    assert "`promotion_boundary.ok` separately from `promotion_boundary.ready`" in content
    assert "operator summary is a redacted read-only artifact" in content
    assert "`ok=true` means the packet artifacts are structurally usable" in content
    assert "`ready=false` means live handoff promotion remains blocked" in content
    assert "packet must include the `email_calendar_live_receipt` artifact" in content
    assert "passed, read-only, worker-bound, and effect-free" in content
    assert "17-command dry-run artifact" in content
    assert "validates the redacted recovery env template before binding receipt emission" in content
    assert "only live connector touchpoint" in content
    assert "validates the aggregate handoff chain" in content
    assert "validates the operator summary schema" in content
    assert "Email/calendar recovery requires three operator bindings" in content
    assert "finance_email_calendar_binding_receipt_not_ready" in content
    assert "examples\\finance_email_calendar_recovery.env.example" in content
    assert "validate it before replacing secret placeholders" in content
    assert "binding-name presence for the email/calendar worker endpoint" in content
    assert "scope witness classification as read-only or invalid by binding name" in content
    assert "never serializes worker URLs, token values, secrets, or scope values" in content
    assert "MULLU_EMAIL_CALENDAR_WORKER_URL and MULLU_EMAIL_CALENDAR_WORKER_SECRET" in content
    assert "EMAIL_CALENDAR_CONNECTOR_SCOPE_ID=gmail.readonly" in content
    assert "GOOGLE_CALENDAR_SCOPE_ID=calendar.events.readonly" in content
    assert "Do not use write-capable scope witnesses" in content
    assert "Payment-provider binding receipt" in content
    assert "python scripts\\emit_finance_approval_payment_provider_binding_receipt.py --provider stripe" in content
    assert "python scripts\\validate_finance_approval_payment_provider_binding_receipt.py --receipt .change_assurance\\finance_approval_payment_provider_binding_receipt.json --require-ready --json" in content
    assert "python scripts\\produce_finance_approval_payment_closure_receipt.py --provider stripe --provider-binding-receipt .change_assurance\\finance_approval_payment_provider_binding_receipt.json" in content
    assert "python scripts\\validate_finance_approval_payment_closure_receipt.py --receipt .change_assurance\\finance_approval_payment_closure_receipt.json --provider-binding-receipt .change_assurance\\finance_approval_payment_provider_binding_receipt.json --require-ready --json" in content
    assert "provider-binding:{provider}:..." in content
    assert "Reviewer fixtures" in content
    assert "examples\\finance_payment_provider_binding_receipt_stripe.json" in content
    assert "examples\\finance_payment_closure_receipt_stripe_bound.json" in content
    assert "These fixtures are deterministic Stripe-scoped evidence examples" in content
    assert "not a production payment claim" in content
    assert expected_manifest_result in content
