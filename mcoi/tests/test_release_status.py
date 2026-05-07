"""Purpose: verify the governed release-status summary remains live and fail-closed.
Governance scope: release inventory and release validation script only.
Dependencies: release status script and governed repo inventories.
Invariants:
  - Release status derives from live inventories, not hardcoded counts.
  - Missing required release docs fail closed.
  - Strict release validation stays aligned with schema and artifact validators.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import validate_release_status


def test_discover_release_status_summary_exposes_live_inventory() -> None:
    summary = validate_release_status.discover_release_status_summary()

    assert "RELEASE_CHECKLIST_v0.1.md" in summary.release_documents
    assert "workflow.schema.json" in summary.schema_files
    assert "pilot-prod" in summary.builtin_profiles
    assert "default-safe" in summary.policy_packs
    assert "mcoi/examples/request-echo.json" in summary.request_artifacts
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/event_envelope.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/event_record.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/event_correlation.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/obligation_closure.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/obligation_transfer.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/obligation_escalation.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/obligation_record.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/function_policy_binding.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/function_metrics_snapshot.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/resource_budget.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/decision_policy.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/operational_node.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/causal_path.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/graph_query_result.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/benchmark_scenario.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/capability_scorecard.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/work_queue_entry.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/workflow_execution_record.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/goal_descriptor.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/goal_execution_state.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/journal_entry.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/composite_checkpoint.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/restore_verification.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/journal_validation_result.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/replay_session_result.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/utility_verdict.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/maf_runtime/supervisor_policy.json"
        in summary.maf_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/incident_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recovery_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recovery_attempt.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recovery_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recovery_plan.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/failover_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recovery_objective.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/delegation_request.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/delegation_result.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/handoff_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/merge_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/conflict_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/case_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/case_assignment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/evidence_collection.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/evidence_item.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/finding_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/review_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/case_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/case_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/case_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/case_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/continuity_plan.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/disruption_event.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recovery_execution.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/verification_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/continuity_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/continuity_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/continuity_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/human_task_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/review_packet.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/approval_board.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/board_member.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/board_vote.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/collaborative_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/handoff_packet.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/human_workflow_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/human_workflow_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/human_workflow_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/attestation_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/certification_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_evidence_binding.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/recertification_window.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_finding.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/assurance_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/governance_contract_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/contract_clause.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/commitment_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/sla_window.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/breach_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/remedy_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/renewal_window.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/contract_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/contract_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/contract_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/configuration_item.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/inventory_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_assignment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_dependency.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/lifecycle_event.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/asset_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/billing_account.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/invoice_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/charge_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/credit_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/penalty_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/dispute_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/revenue_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/billing_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/billing_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/billing_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/payment_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/settlement_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/collection_case.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/dunning_notice.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/cash_application.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/refund_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/writeoff_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/aging_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/settlement_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/settlement_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/customer_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/account_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/product_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/subscription_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/entitlement_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/account_health_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/customer_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/customer_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/customer_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/customer_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_account_link.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ecosystem_agreement.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/revenue_share_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_commitment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_health_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/partner_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/offering_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/package_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/bundle_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/listing_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/eligibility_rule.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/pricing_binding.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/marketplace_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/marketplace_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/marketplace_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/marketplace_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/vendor_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/procurement_request.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/purchase_order.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/vendor_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/vendor_commitment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/procurement_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/procurement_renewal_window.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/vendor_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/procurement_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/procurement_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/budget_envelope.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/spend_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/cost_estimate.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/connector_cost_profile.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/campaign_budget_binding.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/approval_threshold.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/budget_reservation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/spend_forecast.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/budget_conflict.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/budget_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/financial_health_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/budget_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_account.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_transaction.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/settlement_proof.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/anchor_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/wallet_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ledger_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/tenant_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/workspace_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/environment_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/boundary_policy.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/workspace_binding.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/environment_promotion.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/isolation_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/tenant_health.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/tenant_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/tenant_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/record_descriptor.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/retention_schedule.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/legal_hold_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/disposition_review.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/record_link.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/record_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/record_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/preservation_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/disposal_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/records_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_request.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_plan.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_step.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_execution.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_approval_binding.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_evidence.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/rollback_plan.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_outcome.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/change_impact_assessment.json"
        in summary.mcoi_runtime_fixtures
    )


def test_validate_release_status_strictly() -> None:
    summary, errors = validate_release_status.validate_release_status(strict=True)

    assert errors == []
    assert len(summary.release_documents) >= 8
    assert len(summary.schema_files) >= 10
    assert len(summary.config_artifacts) >= 5
    assert len(summary.maf_runtime_fixtures) >= 89
    assert len(summary.mcoi_runtime_fixtures) >= 180
    assert summary.ci_workflow_present is True
    assert summary.release_version == "0.3.0 (v3.10.2)"
    assert summary.release_date == "2026-03-27"


def test_validate_ci_workflow_text_rejects_missing_release_gate() -> None:
    errors = validate_release_status.validate_ci_workflow_text(
        """
name: CI - Build Verification
python -m pytest --tb=short -q -m "not soak"
python scripts/validate_schemas.py --strict
python scripts/validate_artifacts.py --strict
"""
    )

    assert len(errors) == 1
    assert "python scripts/validate_release_status.py --strict" in errors[0]
    assert "cargo test" in errors[0]


def test_validate_release_metadata_texts_rejects_mismatch() -> None:
    (_, _), errors = validate_release_status.validate_release_metadata_texts(
        {
            "RELEASE_NOTES_v0.1.md": "**Version:** 0.1.0 (internal alpha)\n**Date:** 2026-03-19\n",
            "KNOWN_LIMITATIONS_v0.1.md": "**Version:** 0.1.0 (internal alpha)\n**Date:** 2026-03-20\n",
            "SECURITY_MODEL_v0.1.md": "**Version:** 0.2.0 (internal alpha)\n**Date:** 2026-03-19\n",
        }
    )

    assert len(errors) == 2
    assert any("KNOWN_LIMITATIONS_v0.1.md: date metadata mismatch" in error for error in errors)
    assert any("SECURITY_MODEL_v0.1.md: version metadata mismatch" in error for error in errors)


def test_validate_release_limitation_coverage_rejects_missing_anchor() -> None:
    errors = validate_release_status.validate_release_limitation_coverage(
        known_limitations_text="make_dataclass\nHTTP connector\nurllib\n",
        security_model_text="No Authentication or Authorization\n",
    )

    assert len(errors) >= 3
    assert any("coordination_persistence_limitation" in error for error in errors)
    assert any("memory_persistence_limitation" in error for error in errors)
    assert any("encryption_limitation" in error for error in errors)


def test_scan_source_hygiene_text_rejects_bare_except_and_marker() -> None:
    path = REPO_ROOT / "sample.py"
    marker = "TO" + "DO"
    errors = validate_release_status.scan_source_hygiene_text(
        path,
        f"try:\n    pass\nexcept:\n    pass\n# {marker} fix later\n",
    )

    assert len(errors) == 2
    assert any("contains bare except clause" in error for error in errors)
    assert any("contains source hygiene marker TODO" in error for error in errors)


def test_validate_source_hygiene_passes_for_current_repo() -> None:
    errors = validate_release_status.validate_source_hygiene()

    assert errors == []
    assert len(errors) == 0


def test_validate_release_status_rejects_missing_required_docs(monkeypatch) -> None:
    monkeypatch.setattr(
        validate_release_status,
        "REQUIRED_RELEASE_DOCUMENTS",
        ("README.md", "MISSING_RELEASE_SURFACE.md"),
    )

    summary, errors = validate_release_status.validate_release_status(strict=True)

    assert "README.md" in summary.release_documents
    assert len(errors) >= 1
    assert any("MISSING_RELEASE_SURFACE.md" in error for error in errors)
