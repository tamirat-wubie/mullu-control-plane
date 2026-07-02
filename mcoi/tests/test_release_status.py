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

from scripts import validate_release_status  # noqa: E402


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
        "integration/contracts_compat/fixtures/mcoi_runtime/concept_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/concept_relation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/schema_mapping.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/entity_alignment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/semantic_conflict.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ontology_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ontology_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ontology_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ontology_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/ontology_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/knowledge_claim.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/evidence_source.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/trust_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/source_reliability_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/claim_conflict.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/epistemic_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/epistemic_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/epistemic_violation.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/epistemic_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/epistemic_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/belief_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/uncertainty_hypothesis.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/evidence_weight_record.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/confidence_interval.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/belief_update.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/competing_hypothesis_set.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/belief_decision.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/uncertainty_assessment.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/uncertainty_snapshot.json"
        in summary.mcoi_runtime_fixtures
    )
    assert (
        "integration/contracts_compat/fixtures/mcoi_runtime/uncertainty_closure_report.json"
        in summary.mcoi_runtime_fixtures
    )


def test_validate_release_status_strictly() -> None:
    summary, errors = validate_release_status.validate_release_status(strict=True)

    assert errors == []
    assert len(summary.release_documents) >= 8
    assert len(summary.schema_files) >= 10
    assert len(summary.config_artifacts) >= 5
    assert len(summary.maf_runtime_fixtures) >= 89
    assert len(summary.mcoi_runtime_fixtures) >= 181
    assert summary.ci_workflow_present is True
    assert summary.release_version == "0.4.3 (v3.13.3)"
    assert summary.release_date == "2026-05-06"


def test_validate_deployment_matrix_requires_scaling_boundary() -> None:
    content = (REPO_ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")

    errors = validate_release_status.validate_deployment_matrix_text(content)

    assert errors == []
    assert "## Scaling Boundary" in content
    assert "ReadWriteOnce state volume must run a single gateway replica" in content
    assert "PostgreSQL audit store with atomic append" in content
    assert "File snapshots are derived recovery artifacts" in content


def test_validate_deployment_matrix_rejects_missing_scaling_boundary() -> None:
    errors = validate_release_status.validate_deployment_matrix_text(
        "# Deployment Matrix\n\n"
        "| Profile | DB Backend |\n"
        "|---|---|\n"
        "| production | PostgreSQL |\n"
    )

    assert len(errors) == 1
    assert "DEPLOYMENT.md missing required scaling-boundary anchors" in errors[0]
    assert "## Scaling Boundary" in errors[0]
    assert "MULLU_STATE_DIR" in errors[0]


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


def test_validate_status_document_text_rejects_missing_public_anchors() -> None:
    errors = validate_release_status.validate_status_document_text(
        "# Repository Status Witness\n\n"
        "## Reflection Summary\n\n"
        "| Branch witness | Reflected |\n"
    )

    assert len(errors) == 1
    assert "Release witness" in errors[0]
    assert "Governance witness" in errors[0]
    assert "python scripts/validate_release_status.py --strict" in errors[0]


def test_validate_public_surface_document_texts_rejects_missing_anchor() -> None:
    errors = validate_release_status.validate_public_surface_document_texts(
        {
            "GITHUB_SURFACE.md": "# GitHub Surface Witness\n",
            "DEPLOYMENT_STATUS.md": "# Deployment Status Witness\n",
        }
    )

    assert len(errors) == 6
    assert any("GITHUB_SURFACE.md missing required public-surface anchors" in error for error in errors)
    assert any("DEPLOYMENT_STATUS.md missing required public-surface anchors" in error for error in errors)
    assert any("DEPLOYMENT_STATUS.md missing deployment witness alignment anchors" in error for error in errors)
    assert any("docs/00_platform_overview.md missing from public-surface documents" in error for error in errors)
    assert any("docs/PRODUCT_BOUNDARY.md missing from public-surface documents" in error for error in errors)
    assert any("No repository topics are required while quiet mode is active." in error for error in errors)


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


def test_scan_source_hygiene_text_rejects_mojibake_marker() -> None:
    path = REPO_ROOT / "sample.py"
    corrupted_dash = "\u00e2\u20ac\u201d"

    errors = validate_release_status.scan_source_hygiene_text(
        path,
        f'"""Broken {corrupted_dash} header."""\n',
    )

    assert len(errors) == 1
    assert "contains mojibake marker utf8_decoded_as_latin1_lead_byte" in errors[0]
    assert "sample.py" in errors[0]


def test_scan_source_hygiene_text_rejects_utf8_bom() -> None:
    path = REPO_ROOT / "sample.py"

    errors = validate_release_status.scan_source_hygiene_text(
        path,
        '\ufeff"""BOM-prefixed source."""\n',
    )

    assert len(errors) == 1
    assert "contains mojibake marker utf8_byte_order_mark" in errors[0]
    assert "sample.py" in errors[0]


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
