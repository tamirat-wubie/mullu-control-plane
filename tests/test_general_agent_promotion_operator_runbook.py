"""Conformance tests for the general-agent promotion operator runbook.

Purpose: keep the closure execution procedure aligned with governed artifacts.
Governance scope: aggregate closure validation, approval gates, live receipts, and status mutation.
Dependencies: docs/58_general_agent_promotion_operator_runbook.md.
Invariants: No forbidden terminology, no production claim without witness and health evidence.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "58_general_agent_promotion_operator_runbook.md"
HANDOFF_PACKET = ROOT / "examples" / "general_agent_promotion_handoff_packet.json"
FORBIDDEN_PHRASE = " ".join(("artificial", "intelligence"))


def _runbook_text() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_runbook_preserves_symbolic_intelligence_language() -> None:
    runbook_text = _runbook_text()

    assert FORBIDDEN_PHRASE not in runbook_text.lower()
    assert "general-agent promotion" in runbook_text
    assert "production-general-agent" in runbook_text


def test_runbook_names_required_closure_artifacts_and_counts() -> None:
    runbook_text = _runbook_text()
    handoff_packet = json.loads(HANDOFF_PACKET.read_text(encoding="utf-8"))
    aggregate_closure_actions = handoff_packet["aggregate_closure_actions"]

    assert ".change_assurance\\general_agent_promotion_closure_plan.json" in runbook_text
    assert ".change_assurance\\general_agent_promotion_closure_plan_schema_validation.json" in runbook_text
    assert ".change_assurance\\general_agent_promotion_closure_plan_validation.json" in runbook_text
    assert f"Total closure actions | {aggregate_closure_actions}" in runbook_text
    assert f"Approval-required actions | {handoff_packet['approval_required_actions']}" in runbook_text
    assert "`adapter`, `deployment`, and `portfolio`" in runbook_text
    assert "run_general_agent_promotion_closure_chain.py" in runbook_text
    assert "emit_deployment_upstream_blocker_receipt.py" in runbook_text
    assert "collect_deployment_publication_evidence_packet.py" in runbook_text
    assert "validate_deployment_publication_evidence_packet.py" in runbook_text
    assert "emit_deployment_publication_operator_input_request.py" in runbook_text
    assert "validate_deployment_publication_operator_input_request.py" in runbook_text
    assert ".change_assurance\\deployment_publication_evidence_packet\\deployment_publication_evidence_packet.json" in runbook_text
    assert ".change_assurance\\deployment_publication_evidence_packet\\deployment_publication_evidence_packet_validation.json" in runbook_text
    assert ".change_assurance\\deployment_publication_evidence_packet\\deployment_publication_operator_input_request.json" in runbook_text
    assert ".change_assurance\\deployment_publication_evidence_packet\\deployment_publication_operator_input_request_validation.json" in runbook_text
    assert "UPSTREAM_API_READINESS_REPORT" in runbook_text
    assert "--upstream-readiness-report \"$env:UPSTREAM_API_READINESS_REPORT\"" in runbook_text
    assert "validate_deployment_upstream_blocker_receipt.py" in runbook_text
    assert ".change_assurance\\deployment_upstream_blocker_receipt.json" in runbook_text
    assert ".change_assurance\\deployment_upstream_blocker_receipt_validation.json" in runbook_text
    assert "emit_gateway_dns_target_binding_receipt.py" in runbook_text
    assert "validate_gateway_dns_target_binding_receipt.py" in runbook_text
    assert ".change_assurance\\gateway_dns_target_binding_receipt.json" in runbook_text
    assert ".change_assurance\\gateway_dns_target_binding_receipt_validation.json" in runbook_text
    assert "MULLU_GATEWAY_DNS_TARGET" in runbook_text
    assert "MULLU_GATEWAY_DNS_RECORD_TYPE" in runbook_text
    assert "MULLU_DNS_PROVIDER" in runbook_text
    assert "collect_gateway_dns_resolution_receipt.py" in runbook_text
    assert "validate_gateway_dns_resolution_receipt.py" in runbook_text
    assert ".change_assurance\\gateway_dns_resolution_receipt.json" in runbook_text
    assert ".change_assurance\\gateway_dns_resolution_receipt_validation.json" in runbook_text
    assert ".change_assurance\\capability_improvement_portfolio.json" in runbook_text
    assert "produce_capability_improvement_proof_receipt.py" in runbook_text
    assert ".change_assurance\\capability_improvement_proof_receipt.json" in runbook_text
    assert ".change_assurance\\capability_improvement_proof_receipt*.json" in runbook_text
    assert "agentic_control.code_change.plan" in runbook_text
    assert "agentic_control.evidence.append" in runbook_text
    assert "agentic_control.incident_recovery.plan" in runbook_text
    assert "capability improvement proof receipt is non-executing" in runbook_text
    assert "plan_general_agent_promotion_live_evidence_queue.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_live_evidence_queue.json" in runbook_text
    assert "validate_general_agent_promotion_terminal_approvals.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_terminal_approvals.json" in runbook_text
    assert "plan_general_agent_promotion_terminal_certificate_gate.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_terminal_certificate_gate.json" in runbook_text
    assert "plan_general_agent_promotion_terminal_certificate_candidates.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_terminal_certificate_candidates.json" in runbook_text
    assert "reconcile_general_agent_promotion_terminal_evidence.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_terminal_evidence_reconciliation.json" in runbook_text
    assert "gate_general_agent_promotion_terminal_minting.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_terminal_minting_gate.json" in runbook_text
    assert "mint_general_agent_promotion_terminal_certificates.py" in runbook_text
    assert ".change_assurance\\general_agent_promotion_terminal_certificate_minting_run.json" in runbook_text
    assert "ready_for_terminal_certificate_minting=false" in runbook_text
    assert "terminal certificate gate checked before execution" in runbook_text
    assert "terminal certificate candidates are non-minting" in runbook_text
    assert "Capability improvement proof receipt is unsafe" in runbook_text
    assert "terminal evidence reconciliation gates minting readiness" in runbook_text
    assert "terminal minting gate requires explicit authority" in runbook_text
    assert "terminal certificate minting executor requires ready gate" in runbook_text
    assert "`requires_execution_environment`" in runbook_text
    assert "`requires_dependency_closure`" in runbook_text
    assert "`approval_and_environment_blocked`" in runbook_text


def test_runbook_keeps_status_mutation_evidence_gated() -> None:
    runbook_text = _runbook_text()

    assert "Do not update `DEPLOYMENT_STATUS.md`" in runbook_text
    assert "The deployment publication evidence packet validation must report `valid=true`" in runbook_text
    assert "validate_deployment_publication_evidence_packet.py --require-ready" in runbook_text
    assert "deployment publication evidence packet require-ready gate" in runbook_text
    assert "Deployment publication evidence packet is not ready" in runbook_text
    assert "emit `deployment_publication_operator_input_request.json`" in runbook_text
    assert "The upstream blocker" in runbook_text
    assert "validation must report `valid=true` with `--require-ready`" in runbook_text
    assert "validate_deployment_upstream_blocker_receipt.py --require-ready" in runbook_text
    assert "upstream API/DNS validation require-ready gate" in runbook_text
    assert "Upstream API/DNS readiness is not ready" in runbook_text
    assert "The target-binding validation must report `valid=true` with `--require-ready`" in runbook_text
    assert "validate_gateway_dns_target_binding_receipt.py --require-ready" in runbook_text
    assert "gateway DNS target-binding validation require-ready gate" in runbook_text
    assert "Gateway DNS target-binding receipt is not ready" in runbook_text
    assert "The DNS receipt validation must report `valid=true` with `--require-resolved`" in runbook_text
    assert "before publication dispatch" in runbook_text
    assert "validate_gateway_dns_resolution_receipt.py --require-resolved" in runbook_text
    assert "gateway DNS receipt validation require-resolved gate" in runbook_text
    assert "Gateway DNS receipt is unresolved" in runbook_text
    assert "deployment_claim=published" in runbook_text
    assert "runtime_responsibility_debt_clear=true" in runbook_text
    assert "authority_responsibility_debt_clear=true" in runbook_text
    assert "inspect `/authority/responsibility`" in runbook_text
    assert "<gateway_url>/health" in runbook_text
    assert "produce_browser_sandbox_evidence.py" in runbook_text
    assert "run_wsl_browser_sandbox_evidence.py" in runbook_text
    assert "validate_sandbox_execution_receipt.py" in runbook_text
    assert "validate_browser_sandbox_evidence.py" in runbook_text
    assert "The generic sandbox receipt gate must also report `valid=true`" in runbook_text
    assert "browser-sandbox-evidence-*" in runbook_text
    assert "sandbox-receipt-*" in runbook_text
    assert "validate_general_agent_promotion.py --strict" in runbook_text
    assert "validate_general_agent_promotion_closure_plan_schema.py" in runbook_text
    assert "STATUS:" in runbook_text
