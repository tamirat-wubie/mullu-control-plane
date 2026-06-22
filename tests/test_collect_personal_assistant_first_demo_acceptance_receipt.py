"""Tests for the first demo acceptance receipt collector.

Purpose: prove the JSON console route and HTML console view expose the first
usable demo and invoice/email walkthrough while preserving the no-effect boundary.
Governance scope: fixture-backed TestClient route projection only.
"""

from __future__ import annotations

import json

from scripts.collect_personal_assistant_first_demo_acceptance_receipt import (
    collect_first_demo_acceptance_receipt,
    main,
)


def test_collect_first_demo_acceptance_receipt_passes_and_preserves_no_effect_boundary() -> None:
    receipt = collect_first_demo_acceptance_receipt(generated_at="2026-06-22T00:00:00Z")

    assert receipt["receipt_id"] == "personal_assistant_first_demo_acceptance_receipt_v1"
    assert receipt["status"] == "passed"
    assert receipt["governed"] is True
    assert receipt["fixture_backed"] is True
    assert receipt["read_only"] is True
    assert receipt["checks"]["json_route_status_ok"] is True
    assert receipt["checks"]["html_route_status_ok"] is True
    assert receipt["checks"]["json_route_read_only"] is True
    assert receipt["checks"]["html_route_read_only"] is True
    assert receipt["checks"]["first_demo_visible"] is True
    assert receipt["checks"]["invoice_walkthrough_visible"] is True
    assert receipt["checks"]["html_panel_visible"] is True
    assert receipt["checks"]["first_demo_effects_false"] is True
    assert receipt["checks"]["invoice_walkthrough_effects_false"] is True
    assert receipt["checks"]["approval_required_before_send"] is True
    assert receipt["checks"]["approval_is_not_execution"] is True
    assert receipt["checks"]["draft_preview_not_send_authority"] is True
    assert receipt["checks"]["actions_not_taken_recorded"] is True
    assert receipt["checks"]["secret_or_private_leak_absent"] is True
    assert receipt["checks"]["customer_readiness_claim_absent"] is True
    assert receipt["missing"] == {
        "actions_not_taken": [],
        "false_first_demo_effect_fields": [],
        "false_invoice_walkthrough_effect_fields": [],
        "html_markers": [],
    }
    assert receipt["effect_boundary"]["execution_allowed"] is False
    assert receipt["effect_boundary"]["external_send_allowed"] is False
    assert receipt["effect_boundary"]["provider_draft_creation_allowed"] is False
    assert receipt["effect_boundary"]["invoice_payment_allowed"] is False
    assert receipt["effect_boundary"]["money_movement_allowed"] is False
    assert receipt["effect_boundary"]["memory_write_allowed"] is False
    assert receipt["effect_boundary"]["deployment_mutation_allowed"] is False
    assert receipt["effect_boundary"]["customer_readiness_claim_allowed"] is False
    assert "email_not_sent" in receipt["actions_not_taken"]
    assert "provider_draft_not_created" in receipt["actions_not_taken"]
    assert "invoice_not_paid" in receipt["actions_not_taken"]
    assert "mcoi/mcoi_runtime/personal_assistant/console_first_demo_html.py" in receipt["source_refs"]


def test_collect_first_demo_acceptance_receipt_cli_writes_output(tmp_path, monkeypatch) -> None:  # noqa: ANN001
    output = tmp_path / "first_demo_acceptance_receipt.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "collect_personal_assistant_first_demo_acceptance_receipt.py",
            "--output",
            str(output),
        ],
    )

    assert main() == 0
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert output.exists()
    assert saved["status"] == "passed"
    assert saved["observed"]["html_panel_title"] == "Invoice Email Draft Walkthrough"
    assert saved["effect_boundary"]["external_send_allowed"] is False
