"""Conformance tests for the general-agent promotion handoff packet."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs" / "59_general_agent_promotion_handoff_packet.md"
PACKET_JSON = ROOT / "examples" / "general_agent_promotion_handoff_packet.json"
FORBIDDEN_PHRASE = " ".join(("artificial", "intelligence"))


def _packet_text() -> str:
    return PACKET.read_text(encoding="utf-8")


def test_handoff_packet_avoids_forbidden_terminology() -> None:
    packet_text = _packet_text()

    assert FORBIDDEN_PHRASE not in packet_text.lower()
    assert "General-Agent Promotion Handoff Packet" in packet_text
    assert "pilot-governed-core" in packet_text


def test_handoff_packet_links_operator_artifacts() -> None:
    packet_text = _packet_text()

    assert "docs/58_general_agent_promotion_operator_runbook.md" in packet_text
    assert "examples/general_agent_promotion_operator_checklist.json" in packet_text
    assert "examples/general_agent_promotion_handoff_packet.json" in packet_text
    assert "examples/general_agent_promotion_environment_bindings.json" in packet_text
    assert "scripts/validate_general_agent_promotion_handoff_packet.py" in packet_text
    assert "scripts/emit_general_agent_promotion_environment_binding_receipt.py" in packet_text
    assert "scripts/validate_general_agent_promotion_environment_binding_receipt.py" in packet_text
    assert "scripts/preflight_general_agent_promotion_handoff.py" in packet_text
    assert ".change_assurance/general_agent_promotion_closure_plan.json" in packet_text
    assert ".change_assurance/general_agent_promotion_closure_plan_schema_validation.json" in packet_text
    assert ".change_assurance/general_agent_promotion_closure_plan_validation.json" in packet_text
    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in packet_text
    assert ".change_assurance/general_agent_promotion_handoff_preflight.json" in packet_text


def test_handoff_packet_preserves_blockers_and_terminal_proof() -> None:
    packet_text = _packet_text()
    packet = json.loads(PACKET_JSON.read_text(encoding="utf-8"))
    aggregate_closure_actions = packet["aggregate_closure_actions"]
    expected_blockers = {
        "adapter_evidence_not_closed",
        "browser_adapter_not_closed",
        "voice_adapter_not_closed",
        "email_calendar_adapter_not_closed",
        "deployment_witness_not_published",
        "production_health_not_declared",
    }

    assert expected_blockers <= set(packet_text.split())
    assert "document_adapter_not_closed" not in packet_text
    assert f"Aggregate closure actions | {aggregate_closure_actions}" in packet_text
    assert "Approval-required actions | 4" in packet_text
    assert "browser-sandbox-evidence-*" in packet_text
    assert "sandbox-receipt-*" in packet_text
    assert "validate_general_agent_promotion.py --strict" in packet_text
    assert "STATUS:" in packet_text
