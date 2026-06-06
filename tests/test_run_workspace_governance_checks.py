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

import ast
import json
import re
import sys
from pathlib import Path

import pytest

from scripts import run_workspace_governance_checks as runner


def _foundation_boundary_validator_scripts() -> tuple[Path, ...]:
    return tuple(sorted((runner.WORKSPACE_ROOT / "scripts").glob("validate_foundation_*_boundary.py")))


def _foundation_boundary_docs() -> tuple[Path, ...]:
    return tuple(sorted((runner.WORKSPACE_ROOT / "docs").glob("FOUNDATION_*BOUNDARY.md")))


def _foundation_boundary_test_files() -> tuple[Path, ...]:
    return tuple(sorted((runner.WORKSPACE_ROOT / "tests").glob("test_validate_foundation_*_boundary.py")))


def _ci_workflow_text() -> str:
    return (runner.WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _module_docstring(module_path: Path) -> str:
    return ast.get_docstring(ast.parse(module_path.read_text(encoding="utf-8-sig")), clean=False) or ""


def test_build_check_commands_are_ordered_and_repo_local() -> None:
    commands = runner.build_check_commands("python-test")
    names = [command.name for command in commands]
    args_by_name = {command.name: command.args for command in commands}
    foundation_start = names.index("foundation_mode")
    protocol_index = names.index("protocol_manifest")
    foundation_phase = names[foundation_start:protocol_index]
    expected_foundation_names = {
        "foundation_mode",
        "foundation_local_proof_thread",
        *(
            script_path.stem.removeprefix("validate_")
            for script_path in _foundation_boundary_validator_scripts()
        ),
    }
    repository_governance_phase = [
        "protocol_manifest",
        "logic_governance_application",
        "phi_gps_v3_platform_spec",
        "public_repository_surface",
        "proprietary_boundary",
        "release_status",
    ]
    workspace_evidence_phase = [
        "workspace_governance_preflight_receipt_contract",
        "workspace_governance_preflight_receipt_example",
        "workspace_governance_witness_contract",
        "workspace_governance_inventory_report",
        "workspace_governance_inventory_report_contract",
        "workspace_governance_integrity_report",
        "workspace_governance_integrity_report_contract",
        "governed_code_change_loop_sandbox_probe_example",
        "governed_code_change_loop_sandbox_readiness_runbook",
        "intelligence_coordination_episode_receipt",
        "engineering_puzzle_universality_witness",
        "mil_audit_runbook_operator_checklist",
        "general_agent_promotion_handoff_packet",
        "general_agent_promotion_operator_checklist",
        "general_agent_promotion_environment_bindings",
        "general_agent_promotion_handoff_preflight",
        "route_receipt_coverage",
        "route_guard_chain_coverage",
        "reflective_contract_guard",
        "doc_code_consistency",
        "tenant_scope_coverage",
        "persistence_tenant_guard_coverage",
        "mcp_capability_manifest",
        "mcp_operator_checklist",
        "public_naming_readiness",
        "public_demo_surfaces",
        "strict_schema_validation",
        "strict_artifact_validation",
        "terminal_closure_certificate",
    ]
    terminal_protocol_phase = [
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
    expected_tail = repository_governance_phase + workspace_evidence_phase + terminal_protocol_phase

    def assert_ordered(before: str, after: str) -> None:
        assert names.index(before) < names.index(after)

    assert names[:foundation_start] == ["local_assurance_plan", "agents_policy"]
    assert foundation_phase
    assert set(foundation_phase) == expected_foundation_names
    assert len(foundation_phase) == len(expected_foundation_names)
    assert names[protocol_index:] == expected_tail
    assert len(names) == len(set(names))
    assert names == [command.name for command in runner.build_check_commands("python-test")]

    assert foundation_phase[:2] == ["foundation_mode", "foundation_source_control_boundary"]
    assert_ordered("foundation_source_control_boundary", "foundation_source_control_review_checklist_boundary")
    assert_ordered("foundation_source_control_review_checklist_boundary", "foundation_operator_readiness_boundary")
    assert_ordered("foundation_source_control_boundary", "foundation_operator_readiness_boundary")
    assert_ordered("foundation_external_infrastructure_boundary", "foundation_runtime_secret_handoff_rehearsal_boundary")
    assert_ordered(
        "foundation_runtime_secret_handoff_rehearsal_boundary",
        "foundation_runtime_witness_deferral_boundary",
    )
    assert_ordered(
        "foundation_runtime_witness_deferral_boundary",
        "foundation_production_dependency_evidence_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_production_dependency_evidence_rehearsal_boundary",
        "foundation_external_evidence_acceptance_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_external_evidence_acceptance_rehearsal_boundary",
        "foundation_deployment_upstream_api_gate_rehearsal_boundary",
    )
    assert_ordered("foundation_deployment_upstream_api_gate_rehearsal_boundary", "foundation_gateway_dns_target_binding_rehearsal_boundary")
    assert_ordered("foundation_gateway_dns_target_binding_rehearsal_boundary", "foundation_gateway_dns_publication_rehearsal_boundary")
    assert_ordered(
        "foundation_gateway_dns_publication_rehearsal_boundary",
        "foundation_gateway_dns_resolution_receipt_rehearsal_boundary",
    )
    assert_ordered("foundation_gateway_dns_resolution_receipt_rehearsal_boundary", "foundation_gateway_endpoint_reachability_rehearsal_boundary")
    assert_ordered("foundation_gateway_endpoint_reachability_rehearsal_boundary", "foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary")
    assert_ordered("foundation_gateway_endpoint_evidence_receipt_rehearsal_boundary", "foundation_public_health_declaration_rehearsal_boundary")
    assert_ordered("foundation_public_health_declaration_rehearsal_boundary", "foundation_deployment_witness_input_boundary")
    assert_ordered("foundation_deployment_witness_input_boundary", "foundation_deployment_witness_preflight_rehearsal_boundary")
    assert_ordered(
        "foundation_deployment_witness_preflight_rehearsal_boundary",
        "foundation_deployment_witness_dispatch_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_deployment_witness_dispatch_rehearsal_boundary",
        "foundation_deployment_witness_artifact_validation_rehearsal_boundary",
    )
    assert_ordered(
        "foundation_deployment_witness_artifact_validation_rehearsal_boundary",
        "foundation_deployment_witness_evidence_handoff_boundary",
    )
    assert_ordered("foundation_deployment_witness_evidence_handoff_boundary", "foundation_deployment_witness_evidence_ledger_routing_boundary")
    assert_ordered("foundation_legal_business_boundary", "foundation_legal_business_question_rehearsal_boundary")
    assert_ordered("foundation_pilot_deferral_boundary", "foundation_pilot_deferral_rehearsal_boundary")
    assert_ordered("foundation_pilot_deferral_rehearsal_boundary", "foundation_reassessment_gate_boundary")
    assert_ordered("foundation_support_readiness_boundary", "foundation_support_triage_rehearsal_boundary")
    assert_ordered("foundation_intake_onboarding_boundary", "foundation_intake_questionnaire_rehearsal_boundary")
    assert_ordered("foundation_customer_access_boundary", "foundation_customer_access_policy_rehearsal_boundary")
    assert_ordered("foundation_privacy_data_boundary", "foundation_privacy_minimization_rehearsal_boundary")
    assert_ordered("foundation_funding_team_boundary", "foundation_funding_team_obligation_rehearsal_boundary")
    assert_ordered("foundation_community_network_boundary", "foundation_community_network_no_outreach_rehearsal_boundary")
    assert_ordered("foundation_community_network_no_outreach_rehearsal_boundary", "protocol_manifest")

    assert args_by_name["local_assurance_plan"][1:] == (
        "scripts/refresh_local_assurance.py",
        "--dry-run",
        "--json",
    )
    assert args_by_name["agents_policy"][1:] == ("scripts/validate_agents_governance.py",)
    assert args_by_name["phi_gps_v3_platform_spec"][1:] == (
        "scripts/validate_phi_gps_v3_platform_spec.py",
    )
    for check_name in foundation_phase:
        if check_name == "foundation_mode":
            expected_args = ("scripts/validate_foundation_mode.py",)
        elif check_name == "foundation_local_proof_thread":
            expected_args = ("scripts/validate_foundation_local_proof_thread.py",)
        else:
            expected_args = (f"scripts/validate_{check_name}.py",)

        assert args_by_name[check_name][1:] == expected_args
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
    assert args_by_name["governed_code_change_loop_sandbox_probe_example"][1:] == (
        "scripts/validate_governed_code_change_loop_sandbox_probe.py",
        "--probe",
        "docs/governed-code-change-loop-sandbox-probe-example.json",
    )
    assert args_by_name["governed_code_change_loop_sandbox_readiness_runbook"][1:] == (
        "scripts/validate_governed_code_change_loop_sandbox_readiness_runbook.py",
    )
    assert args_by_name["intelligence_coordination_episode_receipt"][1:] == (
        "scripts/validate_intelligence_coordination_episode_receipt.py",
    )
    assert args_by_name["engineering_puzzle_universality_witness"][1:] == (
        "scripts/validate_engineering_puzzle_universality_witness.py",
        "--output",
        ".tmp/engineering-puzzle-universality-witness.json",
    )
    assert args_by_name["mil_audit_runbook_operator_checklist"][1:] == (
        "scripts/validate_mil_audit_runbook_operator_checklist.py",
        "--checklist",
        "examples/mil_audit_runbook_operator_checklist.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_handoff_packet"][1:] == (
        "scripts/validate_general_agent_promotion_handoff_packet.py",
        "--packet",
        "examples/general_agent_promotion_handoff_packet.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_operator_checklist"][1:] == (
        "scripts/validate_general_agent_promotion_operator_checklist.py",
        "--checklist",
        "examples/general_agent_promotion_operator_checklist.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_environment_bindings"][1:] == (
        "scripts/validate_general_agent_promotion_environment_bindings.py",
        "--contract",
        "examples/general_agent_promotion_environment_bindings.json",
        "--checklist",
        "examples/general_agent_promotion_operator_checklist.json",
        "--json",
    )
    assert args_by_name["general_agent_promotion_handoff_preflight"][1:] == (
        "scripts/preflight_general_agent_promotion_handoff.py",
        "--output",
        ".tmp/general-agent-promotion-handoff-preflight.json",
        "--json",
    )
    assert args_by_name["route_receipt_coverage"][1:] == (
        "scripts/validate_receipt_coverage.py",
        "--strict",
    )
    assert args_by_name["route_guard_chain_coverage"][1:] == (
        "scripts/validate_guard_chain_coverage.py",
        "--strict",
    )
    assert args_by_name["reflective_contract_guard"][1:] == (
        "scripts/validate_reflective_contracts.py",
    )
    assert args_by_name["doc_code_consistency"][1:] == (
        "scripts/validate_doc_code_consistency.py",
    )
    assert args_by_name["tenant_scope_coverage"][1:] == (
        "scripts/validate_tenant_scope_coverage.py",
    )
    assert args_by_name["persistence_tenant_guard_coverage"][1:] == (
        "scripts/validate_persistence_tenant_guard_coverage.py",
    )
    assert args_by_name["mcp_capability_manifest"][1:] == (
        "scripts/validate_mcp_capability_manifest.py",
        "--manifest",
        "examples/mcp_capability_manifest.json",
        "--json",
    )
    assert args_by_name["mcp_operator_checklist"][1:] == (
        "scripts/validate_mcp_operator_checklist.py",
        "--checklist",
        "examples/mcp_operator_handoff_checklist.json",
        "--json",
    )
    assert args_by_name["public_naming_readiness"][1:] == (
        "scripts/validate_public_naming_readiness.py",
    )
    assert args_by_name["public_demo_surfaces"][1:] == (
        "scripts/validate_public_demo_surfaces.py",
        "--output",
        ".tmp/public-demo-surface-validation.json",
    )
    assert args_by_name["strict_schema_validation"][1:] == (
        "scripts/validate_schemas.py",
        "--strict",
    )
    assert args_by_name["strict_artifact_validation"][1:] == (
        "scripts/validate_artifacts.py",
        "--strict",
    )
    assert args_by_name["terminal_closure_certificate"][1:] == (
        "scripts/validate_terminal_closure_certificate.py",
        "--json",
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

def test_foundation_boundary_validators_are_preflight_gated_and_tested() -> None:
    """Every foundation boundary validator must be wired into closure evidence."""

    commands = runner.build_check_commands("python-test")
    args_by_name = {command.name: command.args for command in commands}
    boundary_docs = _foundation_boundary_docs()
    boundary_scripts = _foundation_boundary_validator_scripts()

    assert boundary_scripts
    assert len(boundary_scripts) == len(boundary_docs)
    for script_path in boundary_scripts:
        check_name = script_path.stem.removeprefix("validate_")
        relative_script_path = script_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        paired_test_path = (
            runner.WORKSPACE_ROOT
            / "tests"
            / f"test_{script_path.stem}.py"
        )

        assert check_name in args_by_name, f"{relative_script_path} missing from workspace preflight"
        assert args_by_name[check_name][1:] == (relative_script_path,)
        assert paired_test_path.exists(), f"{relative_script_path} missing paired validator test"


def test_foundation_boundary_docs_have_preflight_validators_and_tests() -> None:
    """Every foundation boundary document must carry executable closure evidence."""

    commands = runner.build_check_commands("python-test")
    args_by_name = {command.name: command.args for command in commands}
    boundary_docs = _foundation_boundary_docs()
    boundary_scripts = _foundation_boundary_validator_scripts()
    boundary_tests = _foundation_boundary_test_files()

    assert boundary_docs
    assert len(boundary_scripts) == len(boundary_docs)
    assert len(boundary_tests) == len(boundary_docs)
    for doc_path in boundary_docs:
        check_name = doc_path.stem.lower()
        validator_path = runner.WORKSPACE_ROOT / "scripts" / f"validate_{check_name}.py"
        paired_test_path = runner.WORKSPACE_ROOT / "tests" / f"test_validate_{check_name}.py"
        relative_doc_path = doc_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        relative_validator_path = validator_path.relative_to(runner.WORKSPACE_ROOT).as_posix()

        assert validator_path.exists(), f"{relative_doc_path} missing paired validator"
        assert paired_test_path.exists(), f"{relative_doc_path} missing paired validator test"
        assert check_name in args_by_name, f"{relative_doc_path} missing from workspace preflight"
        assert args_by_name[check_name][1:] == (relative_validator_path,)


def test_foundation_boundary_example_packets_exist_and_are_validator_referenced() -> None:
    """Every boundary-owned example packet must be validated by its boundary validator."""

    example_link_pattern = re.compile(r"\.\./examples/([A-Za-z0-9_.-]+\.json)")
    boundary_docs = _foundation_boundary_docs()

    assert boundary_docs
    for doc_path in boundary_docs:
        relative_doc_path = doc_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        validator_path = runner.WORKSPACE_ROOT / "scripts" / f"validate_{doc_path.stem.lower()}.py"
        validator_text = validator_path.read_text(encoding="utf-8-sig")
        packet_refs = tuple(dict.fromkeys(example_link_pattern.findall(doc_path.read_text(encoding="utf-8-sig"))))

        assert packet_refs, f"{relative_doc_path} does not link any local example packet"
        for packet_ref in packet_refs:
            packet_path = runner.WORKSPACE_ROOT / "examples" / packet_ref

            assert packet_path.exists(), f"{relative_doc_path} references missing example packet: {packet_ref}"
            assert packet_ref in validator_text, f"{validator_path.name} does not validate linked packet: {packet_ref}"


def test_foundation_boundary_validators_and_tests_keep_governed_headers() -> None:
    """Every foundation boundary validator/test module must explain its contract."""

    required_header_fields = ("Purpose:", "Governance scope:", "Dependencies:", "Invariants:")
    boundary_docs = _foundation_boundary_docs()
    boundary_scripts = _foundation_boundary_validator_scripts()
    boundary_tests = _foundation_boundary_test_files()
    module_paths = boundary_scripts + boundary_tests

    assert boundary_docs
    assert len(boundary_scripts) == len(boundary_docs)
    assert len(boundary_tests) == len(boundary_docs)
    assert len(module_paths) == len(boundary_docs) * 2
    for module_path in module_paths:
        relative_module_path = module_path.relative_to(runner.WORKSPACE_ROOT).as_posix()
        module_docstring = _module_docstring(module_path)

        assert module_docstring, f"{relative_module_path} missing module docstring"
        for header_field in required_header_fields:
            assert header_field in module_docstring, f"{relative_module_path} missing {header_field}"


def test_ci_runs_full_unsharded_workspace_preflight_receipt() -> None:
    workflow_text = _ci_workflow_text()
    preflight_command = (
        "python scripts/run_workspace_governance_checks.py --json "
        "--receipt-path .tmp/workspace-governance-preflight-receipt.json"
    )

    assert preflight_command in workflow_text
    command_line = next(line.strip() for line in workflow_text.splitlines() if preflight_command in line)

    assert command_line == f"run: {preflight_command}"
    assert "--check" not in command_line
    assert "--shard-count" not in command_line
    assert "--shard-index" not in command_line


def test_ci_uploads_workspace_preflight_receipt_artifact() -> None:
    workflow_text = _ci_workflow_text()
    preflight_command = (
        "python scripts/run_workspace_governance_checks.py --json "
        "--receipt-path .tmp/workspace-governance-preflight-receipt.json"
    )
    artifact_name = "name: sdlc-workspace-governance-preflight-receipt"
    artifact_path = "path: .tmp/workspace-governance-preflight-receipt.json"

    assert workflow_text.find(preflight_command) < workflow_text.find("Upload SDLC workspace preflight receipt")
    assert "uses: actions/upload-artifact@v6" in workflow_text
    assert artifact_name in workflow_text
    assert artifact_path in workflow_text
    assert workflow_text.find(artifact_name) < workflow_text.find(artifact_path)


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


def test_preflight_lock_reclaims_stale_dead_pid_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "workspace-governance-preflight.lock"
    stale_payload = {
        "lock_id": runner.PREFLIGHT_LOCK_ID,
        "pid": 0,
        "created_at_epoch": 1,
    }
    lock_path.write_text(json.dumps(stale_payload), encoding="utf-8")

    with runner.PreflightLock(lock_path):
        observed_payload = json.loads(lock_path.read_text(encoding="utf-8"))

        assert observed_payload["lock_id"] == runner.PREFLIGHT_LOCK_ID
        assert observed_payload["pid"] != stale_payload["pid"]
        assert observed_payload["created_at_epoch"] > stale_payload["created_at_epoch"]

    assert not lock_path.exists()
