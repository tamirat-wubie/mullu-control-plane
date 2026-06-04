"""Purpose: verify repository-local workspace governance preflight orchestration.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: scripts.run_workspace_governance_checks.
Invariants:
  - Check names are stable and map to repository-local scripts.
  - Result receipts derive status from return codes.
  - Saved canonical receipts require a full unsharded preflight.
  - Receipt writes cannot escape the workspace root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scripts import run_workspace_governance_checks as runner


def test_build_check_commands_are_ordered_and_repo_local() -> None:
    commands = runner.build_check_commands("python-test")
    names = [command.name for command in commands]
    args_by_name = {command.name: command.args for command in commands}

    assert names[:61] == [
        "local_assurance_plan",
        "agents_policy",
        "foundation_mode",
        "foundation_source_control_boundary",
        "foundation_operator_readiness_boundary",
        "foundation_solo_daily_loop_boundary",
        "foundation_learning_path_boundary",
        "foundation_architecture_map_boundary",
        "foundation_system_boundary_inventory_boundary",
        "foundation_module_inventory_boundary",
        "foundation_component_contract_boundary",
        "foundation_interface_map_boundary",
        "foundation_dependency_graph_boundary",
        "foundation_invariant_map_boundary",
        "foundation_hazard_map_boundary",
        "foundation_proof_reference_boundary",
        "foundation_gap_register_boundary",
        "foundation_diff_review_boundary",
        "foundation_change_handoff_boundary",
        "foundation_local_workstation_boundary",
        "foundation_documentation_boundary",
        "foundation_plain_language_status_boundary",
        "foundation_accessibility_language_boundary",
        "foundation_claim_boundary",
        "foundation_website_posture_boundary",
        "foundation_research_notebook_boundary",
        "foundation_evidence_ledger_boundary",
        "foundation_decision_journal_boundary",
        "foundation_next_action_boundary",
        "foundation_test_evidence_boundary",
        "foundation_local_proof_thread",
        "foundation_private_recovery_boundary",
        "foundation_private_recovery_rehearsal_boundary",
        "foundation_secrets_credentials_boundary",
        "foundation_security_baseline_boundary",
        "foundation_cost_budget_boundary",
        "foundation_payment_provider_boundary",
        "foundation_runtime_environment_boundary",
        "foundation_backup_export_boundary",
        "foundation_deployment_deferral_boundary",
        "foundation_external_infrastructure_boundary",
        "foundation_domain_email_boundary",
        "foundation_legal_business_boundary",
        "foundation_product_scope_boundary",
        "foundation_capability_roadmap_boundary",
        "foundation_agentic_management_boundary",
        "foundation_operations_runbook_boundary",
        "foundation_market_research_boundary",
        "foundation_pilot_deferral_boundary",
        "foundation_support_readiness_boundary",
        "foundation_support_triage_rehearsal_boundary",
        "foundation_intake_onboarding_boundary",
        "foundation_intake_questionnaire_rehearsal_boundary",
        "foundation_customer_access_boundary",
        "foundation_customer_access_policy_rehearsal_boundary",
        "foundation_github_app_token_format_boundary",
        "foundation_privacy_data_boundary",
        "foundation_privacy_minimization_rehearsal_boundary",
        "foundation_funding_team_boundary",
        "foundation_community_network_boundary",
        "protocol_manifest",
    ]
    assert names[65:73] == [
        "workspace_governance_preflight_receipt_contract",
        "workspace_governance_preflight_receipt_example",
        "workspace_governance_witness_contract",
        "workspace_governance_inventory_report",
        "workspace_governance_inventory_report_contract",
        "workspace_governance_integrity_report",
        "workspace_governance_integrity_report_contract",
        "universal_action_orchestration_contract",
    ]
    assert len(names) == 81
    assert names[-9:] == [
        "universal_action_orchestration_contract",
        "universal_action_orchestration_validation_receipt_contract",
        "universal_action_orchestration_validation_receipt_example",
        "sdlc_artifact_validation",
        "sdlc_route_validation",
        "sdlc_state_machine_validation",
        "sdlc_release_readiness_validation",
        "sdlc_security_review_validation",
        "sdlc_pr_enforcement_validation",
    ]
    assert args_by_name["local_assurance_plan"][1:] == (
        "scripts/refresh_local_assurance.py",
        "--dry-run",
        "--json",
    )
    assert args_by_name["agents_policy"][1:] == ("scripts/validate_agents_governance.py",)
    assert args_by_name["foundation_mode"][1:] == ("scripts/validate_foundation_mode.py",)
    assert args_by_name["foundation_source_control_boundary"][1:] == (
        "scripts/validate_foundation_source_control_boundary.py",
    )
    assert args_by_name["foundation_operator_readiness_boundary"][1:] == (
        "scripts/validate_foundation_operator_readiness_boundary.py",
    )
    assert args_by_name["foundation_solo_daily_loop_boundary"][1:] == (
        "scripts/validate_foundation_solo_daily_loop_boundary.py",
    )
    assert args_by_name["foundation_learning_path_boundary"][1:] == (
        "scripts/validate_foundation_learning_path_boundary.py",
    )
    assert args_by_name["foundation_architecture_map_boundary"][1:] == (
        "scripts/validate_foundation_architecture_map_boundary.py",
    )
    assert args_by_name["foundation_system_boundary_inventory_boundary"][1:] == (
        "scripts/validate_foundation_system_boundary_inventory_boundary.py",
    )
    assert args_by_name["foundation_module_inventory_boundary"][1:] == (
        "scripts/validate_foundation_module_inventory_boundary.py",
    )
    assert args_by_name["foundation_component_contract_boundary"][1:] == (
        "scripts/validate_foundation_component_contract_boundary.py",
    )
    assert args_by_name["foundation_interface_map_boundary"][1:] == (
        "scripts/validate_foundation_interface_map_boundary.py",
    )
    assert args_by_name["foundation_dependency_graph_boundary"][1:] == (
        "scripts/validate_foundation_dependency_graph_boundary.py",
    )
    assert args_by_name["foundation_invariant_map_boundary"][1:] == (
        "scripts/validate_foundation_invariant_map_boundary.py",
    )
    assert args_by_name["foundation_hazard_map_boundary"][1:] == (
        "scripts/validate_foundation_hazard_map_boundary.py",
    )
    assert args_by_name["foundation_proof_reference_boundary"][1:] == (
        "scripts/validate_foundation_proof_reference_boundary.py",
    )
    assert args_by_name["foundation_gap_register_boundary"][1:] == (
        "scripts/validate_foundation_gap_register_boundary.py",
    )
    assert args_by_name["foundation_diff_review_boundary"][1:] == (
        "scripts/validate_foundation_diff_review_boundary.py",
    )
    assert args_by_name["foundation_change_handoff_boundary"][1:] == (
        "scripts/validate_foundation_change_handoff_boundary.py",
    )
    assert args_by_name["foundation_local_workstation_boundary"][1:] == (
        "scripts/validate_foundation_local_workstation_boundary.py",
    )
    assert args_by_name["foundation_documentation_boundary"][1:] == (
        "scripts/validate_foundation_documentation_boundary.py",
    )
    assert args_by_name["foundation_plain_language_status_boundary"][1:] == (
        "scripts/validate_foundation_plain_language_status_boundary.py",
    )
    assert args_by_name["foundation_accessibility_language_boundary"][1:] == (
        "scripts/validate_foundation_accessibility_language_boundary.py",
    )
    assert args_by_name["foundation_claim_boundary"][1:] == (
        "scripts/validate_foundation_claim_boundary.py",
    )
    assert args_by_name["foundation_website_posture_boundary"][1:] == (
        "scripts/validate_foundation_website_posture_boundary.py",
    )
    assert args_by_name["foundation_research_notebook_boundary"][1:] == (
        "scripts/validate_foundation_research_notebook_boundary.py",
    )
    assert args_by_name["foundation_evidence_ledger_boundary"][1:] == (
        "scripts/validate_foundation_evidence_ledger_boundary.py",
    )
    assert args_by_name["foundation_decision_journal_boundary"][1:] == (
        "scripts/validate_foundation_decision_journal_boundary.py",
    )
    assert args_by_name["foundation_next_action_boundary"][1:] == (
        "scripts/validate_foundation_next_action_boundary.py",
    )
    assert args_by_name["foundation_test_evidence_boundary"][1:] == (
        "scripts/validate_foundation_test_evidence_boundary.py",
    )
    assert args_by_name["foundation_local_proof_thread"][1:] == (
        "scripts/validate_foundation_local_proof_thread.py",
    )
    assert args_by_name["foundation_private_recovery_boundary"][1:] == (
        "scripts/validate_foundation_private_recovery_boundary.py",
    )
    assert args_by_name["foundation_private_recovery_rehearsal_boundary"][1:] == (
        "scripts/validate_foundation_private_recovery_rehearsal_boundary.py",
    )
    assert args_by_name["foundation_secrets_credentials_boundary"][1:] == (
        "scripts/validate_foundation_secrets_credentials_boundary.py",
    )
    assert args_by_name["foundation_security_baseline_boundary"][1:] == (
        "scripts/validate_foundation_security_baseline_boundary.py",
    )
    assert args_by_name["foundation_cost_budget_boundary"][1:] == (
        "scripts/validate_foundation_cost_budget_boundary.py",
    )
    assert args_by_name["foundation_payment_provider_boundary"][1:] == (
        "scripts/validate_foundation_payment_provider_boundary.py",
    )
    assert args_by_name["foundation_runtime_environment_boundary"][1:] == (
        "scripts/validate_foundation_runtime_environment_boundary.py",
    )
    assert args_by_name["foundation_backup_export_boundary"][1:] == (
        "scripts/validate_foundation_backup_export_boundary.py",
    )
    assert args_by_name["foundation_deployment_deferral_boundary"][1:] == (
        "scripts/validate_foundation_deployment_deferral_boundary.py",
    )
    assert args_by_name["foundation_external_infrastructure_boundary"][1:] == (
        "scripts/validate_foundation_external_infrastructure_boundary.py",
    )
    assert args_by_name["foundation_domain_email_boundary"][1:] == (
        "scripts/validate_foundation_domain_email_boundary.py",
    )
    assert args_by_name["foundation_legal_business_boundary"][1:] == (
        "scripts/validate_foundation_legal_business_boundary.py",
    )
    assert args_by_name["foundation_product_scope_boundary"][1:] == (
        "scripts/validate_foundation_product_scope_boundary.py",
    )
    assert args_by_name["foundation_capability_roadmap_boundary"][1:] == (
        "scripts/validate_foundation_capability_roadmap_boundary.py",
    )
    assert args_by_name["foundation_agentic_management_boundary"][1:] == (
        "scripts/validate_foundation_agentic_management_boundary.py",
    )
    assert args_by_name["foundation_operations_runbook_boundary"][1:] == (
        "scripts/validate_foundation_operations_runbook_boundary.py",
    )
    assert args_by_name["foundation_market_research_boundary"][1:] == (
        "scripts/validate_foundation_market_research_boundary.py",
    )
    assert args_by_name["foundation_pilot_deferral_boundary"][1:] == (
        "scripts/validate_foundation_pilot_deferral_boundary.py",
    )
    assert args_by_name["foundation_support_readiness_boundary"][1:] == (
        "scripts/validate_foundation_support_readiness_boundary.py",
    )
    assert args_by_name["foundation_support_triage_rehearsal_boundary"][1:] == (
        "scripts/validate_foundation_support_triage_rehearsal_boundary.py",
    )
    assert args_by_name["foundation_intake_onboarding_boundary"][1:] == (
        "scripts/validate_foundation_intake_onboarding_boundary.py",
    )
    assert args_by_name["foundation_intake_questionnaire_rehearsal_boundary"][1:] == (
        "scripts/validate_foundation_intake_questionnaire_rehearsal_boundary.py",
    )
    assert args_by_name["foundation_customer_access_boundary"][1:] == (
        "scripts/validate_foundation_customer_access_boundary.py",
    )
    assert args_by_name["foundation_customer_access_policy_rehearsal_boundary"][1:] == (
        "scripts/validate_foundation_customer_access_policy_rehearsal_boundary.py",
    )
    assert args_by_name["foundation_github_app_token_format_boundary"][1:] == (
        "scripts/validate_foundation_github_app_token_format_boundary.py",
    )
    assert args_by_name["foundation_privacy_data_boundary"][1:] == (
        "scripts/validate_foundation_privacy_data_boundary.py",
    )
    assert args_by_name["foundation_privacy_minimization_rehearsal_boundary"][1:] == (
        "scripts/validate_foundation_privacy_minimization_rehearsal_boundary.py",
    )
    assert args_by_name["foundation_funding_team_boundary"][1:] == (
        "scripts/validate_foundation_funding_team_boundary.py",
    )
    assert args_by_name["foundation_community_network_boundary"][1:] == (
        "scripts/validate_foundation_community_network_boundary.py",
    )
    assert args_by_name["workspace_governance_inventory_report"][1:] == (
        "scripts/report_workspace_governance_inventory.py",
    )
    assert args_by_name["workspace_governance_inventory_report_contract"][1:] == (
        "scripts/validate_workspace_governance_inventory_report_contract.py",
    )
    assert args_by_name["workspace_governance_witness_contract"][1:] == (
        "scripts/validate_workspace_governance_witness.py",
    )
    assert args_by_name["workspace_governance_integrity_report"][1:] == (
        "scripts/report_workspace_governance_integrity.py",
    )
    assert args_by_name["workspace_governance_integrity_report_contract"][1:] == (
        "scripts/validate_workspace_governance_integrity_report_contract.py",
    )
    assert args_by_name["sdlc_release_readiness_validation"][1:] == (
        "scripts/validate_sdlc_release_readiness.py",
        "--strict",
    )
    assert args_by_name["sdlc_route_validation"][1:] == (
        "scripts/validate_sdlc_route.py",
    )
    assert args_by_name["sdlc_security_review_validation"][1:] == (
        "scripts/validate_sdlc_security_review.py",
        "--strict",
    )
    assert args_by_name["sdlc_pr_enforcement_validation"][1:] == (
        "scripts/validate_sdlc_pr_enforcement.py",
    )


def test_run_check_preserves_failure_evidence() -> None:
    command = runner.CheckCommand(
        "intentional_failure",
        (sys.executable, "-c", "import sys; print('observed failure'); sys.exit(7)"),
    )

    result = runner.run_check(command, runner.WORKSPACE_ROOT)

    assert result.passed is False
    assert result.return_code == 7
    assert "observed failure" in result.stdout


def test_select_check_commands_filters_and_shards() -> None:
    commands = (
        runner.CheckCommand("a", ("python", "a")),
        runner.CheckCommand("b", ("python", "b")),
        runner.CheckCommand("c", ("python", "c")),
        runner.CheckCommand("d", ("python", "d")),
    )

    selected = runner.select_check_commands(commands, selected_names=("d", "b"))
    shard_zero = runner.select_check_commands(commands, shard_count=2, shard_index=0)

    assert [command.name for command in selected] == ["b", "d"]
    assert [command.name for command in shard_zero] == ["a", "c"]
    with pytest.raises(ValueError):
        runner.select_check_commands(commands, selected_names=("missing",))


def test_build_receipt_records_pass_and_failure() -> None:
    pass_result = runner.CheckResult("pass_check", ("python", "--version"), 0, "ok\n", "")
    fail_result = runner.CheckResult("fail_check", ("python", "-c", "fail"), 1, "", "bad\n")

    receipt = runner.build_receipt((pass_result, fail_result), generated_at_epoch=12345.5)

    assert receipt["receipt_id"] == "workspace_governance_preflight_receipt"
    assert receipt["terminal_closure_required"] is True
    assert receipt["receipt_is_not_terminal_closure"] is True
    assert receipt["status"] == "failed"
    assert receipt["generated_at_epoch"] == 12345.5
    assert receipt["check_count"] == 2
    assert receipt["checks"][1]["passed"] is False


def test_write_receipt_rejects_escape_and_non_json(tmp_path: Path) -> None:
    receipt = runner.build_receipt((runner.CheckResult("pass_check", ("python", "--version"), 0, "ok\n", ""),))

    receipt_path = runner.write_receipt(receipt, Path("receipt.json"), tmp_path)
    loaded = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert loaded["status"] == "passed"
    assert receipt_path.name == "receipt.json"
    with pytest.raises(ValueError):
        runner.resolve_receipt_path(Path("../receipt.json"), tmp_path)
    with pytest.raises(ValueError):
        runner.resolve_receipt_path(Path("receipt.txt"), tmp_path)


def test_main_json_emits_machine_readable_receipt() -> None:
    exit_code = runner.main(
        [
            "--json",
            "--check",
            "workspace_governance_preflight_receipt_contract",
            "--check",
            "workspace_governance_preflight_receipt_example",
        ]
    )

    assert exit_code == 0
    assert runner.requires_full_preflight_lock((), 1) is True
    assert runner.requires_full_preflight_lock(("protocol_manifest",), 1) is False
    assert runner.allows_saved_canonical_receipt((), 1) is True
    assert runner.allows_saved_canonical_receipt(("protocol_manifest",), 1) is False


def test_main_rejects_saved_receipt_for_selected_or_sharded_runs(capsys: pytest.CaptureFixture[str]) -> None:
    selected_receipt_path = runner.WORKSPACE_ROOT / ".tmp" / "partial-selected-preflight-receipt.json"
    sharded_receipt_path = runner.WORKSPACE_ROOT / ".tmp" / "partial-sharded-preflight-receipt.json"

    selected_exit_code = runner.main(
        [
            "--check",
            "protocol_manifest",
            "--receipt-path",
            str(selected_receipt_path.relative_to(runner.WORKSPACE_ROOT)),
        ]
    )
    selected_streams = capsys.readouterr()
    sharded_exit_code = runner.main(
        [
            "--shard-count",
            "2",
            "--shard-index",
            "0",
            "--receipt-path",
            str(sharded_receipt_path.relative_to(runner.WORKSPACE_ROOT)),
        ]
    )
    sharded_streams = capsys.readouterr()

    assert selected_exit_code == 1
    assert sharded_exit_code == 1
    assert "full unsharded preflight run" in selected_streams.err
    assert "full unsharded preflight run" in sharded_streams.err
    assert not selected_receipt_path.exists()
    assert not sharded_receipt_path.exists()
