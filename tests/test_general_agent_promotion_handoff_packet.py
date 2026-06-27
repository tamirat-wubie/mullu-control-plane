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
    assert "production-general-agent" in packet_text


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
    assert "scripts/plan_general_agent_promotion_live_evidence_queue.py" in packet_text
    assert "scripts/validate_general_agent_promotion_terminal_approvals.py" in packet_text
    assert "schemas/general_agent_promotion_terminal_approvals.schema.json" in packet_text
    assert "scripts/plan_general_agent_promotion_terminal_certificate_gate.py" in packet_text
    assert "scripts/plan_general_agent_promotion_terminal_certificate_candidates.py" in packet_text
    assert "scripts/produce_capability_improvement_proof_receipt.py" in packet_text
    assert "schemas/capability_improvement_proof_receipt.schema.json" in packet_text
    assert "schemas/general_agent_promotion_terminal_certificate_candidates.schema.json" in packet_text
    assert "scripts/reconcile_general_agent_promotion_terminal_evidence.py" in packet_text
    assert "schemas/general_agent_promotion_terminal_evidence_reconciliation.schema.json" in packet_text
    assert "scripts/gate_general_agent_promotion_terminal_minting.py" in packet_text
    assert "schemas/general_agent_promotion_terminal_minting_gate.schema.json" in packet_text
    assert "scripts/mint_general_agent_promotion_terminal_certificates.py" in packet_text
    assert "schemas/general_agent_promotion_terminal_certificate_minting_run.schema.json" in packet_text
    assert ".change_assurance/general_agent_promotion_closure_plan.json" in packet_text
    assert ".change_assurance/capability_improvement_portfolio.json" in packet_text
    assert ".change_assurance/capability_improvement_proof_receipt*.json" in packet_text
    assert ".change_assurance/general_agent_promotion_live_evidence_queue.json" in packet_text
    assert ".change_assurance/general_agent_promotion_terminal_approvals.json" in packet_text
    assert ".change_assurance/general_agent_promotion_terminal_certificate_gate.json" in packet_text
    assert ".change_assurance/general_agent_promotion_terminal_certificate_candidates.json" in packet_text
    assert ".change_assurance/general_agent_promotion_terminal_evidence_reconciliation.json" in packet_text
    assert ".change_assurance/general_agent_promotion_terminal_minting_gate.json" in packet_text
    assert ".change_assurance/general_agent_promotion_terminal_certificate_minting_run.json" in packet_text
    assert ".change_assurance/general_agent_promotion_closure_plan_schema_validation.json" in packet_text
    assert ".change_assurance/general_agent_promotion_closure_plan_validation.json" in packet_text
    assert ".change_assurance/general_agent_promotion_environment_binding_receipt.json" in packet_text
    assert ".change_assurance/general_agent_promotion_handoff_preflight.json" in packet_text


def test_handoff_packet_preserves_blockers_and_terminal_proof() -> None:
    packet_text = _packet_text()
    packet = json.loads(PACKET_JSON.read_text(encoding="utf-8"))
    aggregate_closure_actions = packet["aggregate_closure_actions"]
    assert packet["open_blockers"] == []
    assert "deployment_dns_not_verified" in packet_text
    assert "deployment_upstream_api_gate_not_ready" not in packet_text
    assert "document_adapter_not_closed" not in packet_text
    assert f"Aggregate closure actions | {aggregate_closure_actions}" in packet_text
    assert f"Approval-required actions | {packet['approval_required_actions']}" in packet_text
    assert "deployment_dns_not_verified" in packet["approval_required_blockers"]
    assert "voice_dependency_missing:OPENAI_API_KEY" not in packet["approval_required_blockers"]
    assert "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN" not in packet["approval_required_blockers"]
    assert "deployment_witness_not_published" not in packet["approval_required_blockers"]
    assert "production_health_not_declared" not in packet["approval_required_blockers"]
    assert "capability_improvement_required:agentic_control.evidence.append" in packet_text
    assert "capability_improvement_required:agentic_control.governance_gate.evaluate" in packet_text
    assert "capability_improvement_required:agentic_control.code_change.plan" in packet_text
    assert "capability_improvement_required:agentic_control.incident_recovery.plan" in packet_text
    assert "Inspect the live-evidence queue before executing any closure command" in packet_text
    assert "Validate the terminal approval receipt when approval refs are supplied" in packet_text
    assert "Inspect the terminal certificate gate before executing any closure command" in packet_text
    assert "Inspect terminal certificate candidates and verify minting remains governed by explicit authority" in packet_text
    assert "Produce capability-improvement proof receipts" in packet_text
    assert "Inspect terminal evidence reconciliation" in packet_text
    assert "Inspect terminal minting gate" in packet_text
    assert "Run the terminal certificate minting executor only after the terminal minting gate is ready" in packet_text
    assert packet["approval_required_actions"] == len(packet["approval_required_blockers"])
    assert "browser-sandbox-evidence-*" in packet_text
    assert "sandbox-receipt-*" in packet_text
    assert "runtime and authority responsibility debt are clear" in packet_text
    assert "debt-clear witness fields" in packet_text
    assert "validate_general_agent_promotion.py --strict" in packet_text
    assert packet["status"] == "ready_for_final_validation"
    assert packet["production_promotion"] == "ready"
    assert packet["approval_required_actions"] == 6
    assert "STATUS:" in packet_text
