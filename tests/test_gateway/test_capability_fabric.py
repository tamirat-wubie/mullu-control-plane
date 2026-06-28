"""Purpose: validate gateway capability fabric loader configuration paths.
Governance scope: environment-gated capability fabric admission and checked-in
    default capsule/capability pack installation.
Dependencies: gateway capability fabric loader and governed capability registry.
Invariants:
  - Fabric admission remains disabled unless explicitly enabled.
  - Enabled admission requires explicit sources unless default packs are requested.
  - Checked-in default packs install all certified agentic_control, browser,
    communication, connector, creative, document, enterprise, financial,
    computer, messaging, phone, and voice entries.
  - Operator read models expose governed capability records, not raw tool handles.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

import pytest

from gateway.capability_dispatch import CapabilityDispatcher, build_capability_dispatcher_from_platform
from gateway.capability_fabric import (
    build_capability_admission_gate,
    build_capability_admission_gate_from_env,
    build_default_capability_admission_gate,
    load_default_capability_entries,
    load_default_domain_capsules,
    load_software_dev_capability_entries,
    load_software_dev_domain_capsule,
)
from mcoi_runtime.core.capability_unlock_ladder import (
    GATE_APPROVAL,
    GATE_CONNECTOR_LEASE,
    GATE_EXECUTION_RECEIPT,
    GATE_ROLLBACK,
    GATE_VERIFIER,
    UNLOCK_LADDER_ID,
    default_capability_unlock_ladder,
)


ROOT = Path(__file__).resolve().parents[2]
SOFTWARE_DEV_CAPSULE_PATH = ROOT / "capsules" / "software_dev.json"
SOFTWARE_DEV_CAPABILITY_PACK_PATH = ROOT / "capabilities" / "software_dev" / "capability_pack.json"


def _clock() -> str:
    return "2026-04-29T12:00:00+00:00"


@pytest.fixture(autouse=True)
def _clear_fabric_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith("MULLU_CAPABILITY_FABRIC_"):
            monkeypatch.delenv(key, raising=False)


def test_capability_fabric_env_loader_stays_disabled_without_enable_flag() -> None:
    gate = build_capability_admission_gate_from_env(clock=_clock)

    assert gate is None
    assert load_default_domain_capsules()[0].capsule_id == "agentic_control.autonomous_ops.v0"
    assert load_default_capability_entries()[0].capability_id == "agentic_control.mission.define"


def test_capability_fabric_env_loader_requires_source_without_default_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")

    with pytest.raises(ValueError, match="requires capsule JSON source and capability JSON source"):
        build_capability_admission_gate_from_env(clock=_clock)

    assert "MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS" not in os.environ
    assert "MULLU_CAPABILITY_FABRIC_CAPSULE_PATH" not in os.environ
    assert "MULLU_CAPABILITY_FABRIC_CAPABILITY_PATH" not in os.environ


def test_capability_fabric_env_loader_installs_checked_in_default_packs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS", "true")

    gate = build_capability_admission_gate_from_env(clock=_clock)

    assert gate is not None
    read_model = gate.read_model()
    assert read_model["capsule_count"] == 13
    assert read_model["capability_count"] == 81
    assert len(read_model["capability_maturity_assessments"]) == 81
    assert read_model["capability_maturity_counts"]["C3"] == 79
    assert read_model["capability_maturity_counts"]["C6"] == 2
    assert read_model["production_ready_count"] == 2
    assert read_model["autonomy_ready_count"] == 0
    assert {domain["domain"] for domain in read_model["domains"]} == {
        "agentic_control",
        "browser",
        "communication",
        "computer",
        "connector",
        "creative",
        "deployment",
        "document",
        "enterprise",
        "financial",
        "messaging",
        "phone",
        "voice",
    }
    assert read_model["general_agent_plane_count"] == 13
    assert read_model["general_agent_execution_order"] == tuple(
        plane["plane_id"] for plane in read_model["general_agent_planes"]
    )
    assert [plane["plane_id"] for plane in read_model["general_agent_planes"]] == [
        "0.governance_core",
        "1.llm_reasoning_plane",
        "2.memory_plane",
        "3.tool_skill_plane",
        "4.computer_control_plane",
        "5.browser_web_plane",
        "6.document_data_plane",
        "7.communication_plane",
        "8.financial_effect_plane",
        "9.mcp_external_tool_plane",
        "10.scheduling_workflow_plane",
        "11.observation_verification_plane",
        "12.deployment_witness_plane",
    ]
    assert read_model["capability_manifest_registry_configured"] is False
    assert read_model["capability_manifest_registry"]["manifest_count"] == 0
    assert read_model["capability_manifest_coverage_status"] == "not_configured"
    assert read_model["capability_manifest_coverage"] == ()


def test_capability_fabric_env_loader_projects_local_manifest_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPSULE_PATH", str(SOFTWARE_DEV_CAPSULE_PATH))
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPABILITY_PACK_PATH", str(SOFTWARE_DEV_CAPABILITY_PACK_PATH))
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_MANIFEST_REGISTRY_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_MANIFEST_ENVIRONMENT", "local")

    gate = build_capability_admission_gate_from_env(clock=_clock)

    assert gate is not None
    read_model = gate.read_model()
    manifest_registry = read_model["capability_manifest_registry"]
    assert read_model["capsule_count"] == 1
    assert read_model["capability_count"] == 8
    assert read_model["capability_manifest_registry_configured"] is True
    assert manifest_registry["manifest_count"] == 8
    assert manifest_registry["admission_count"] == 8
    assert "software_dev.change.run" in manifest_registry["capability_ids"]
    assert read_model["capability_manifest_gated"] is True
    assert read_model["capability_manifest_coverage_status"] == "complete"
    assert read_model["capability_manifest_covered_count"] == 8
    assert read_model["capability_manifest_missing_count"] == 0
    coverage = {record["capability_id"]: record for record in read_model["capability_manifest_coverage"]}
    assert coverage["software_dev.change.run"]["manifest_admitted"] is True
    assert coverage["software_dev.change.run"]["rollback_required"] is True
    assert "tests/test_software_dev_capability_pack.py" in coverage["software_dev.change.run"]["evidence_refs"]
    decision = gate.admit(command_id="cmd-software-dev-change", intent_name="software_dev.change.run")
    assert decision.status.value == "accepted"
    assert decision.capability_id == "software_dev.change.run"


def test_capability_fabric_manifest_gate_rejects_unmanifested_capability() -> None:
    gate = build_capability_admission_gate(
        capsules=(load_software_dev_domain_capsule(),),
        capabilities=load_software_dev_capability_entries(),
        require_certified=True,
        capability_manifest_registry_read_model={
            "manifest_count": 1,
            "admission_count": 1,
            "capability_ids": ("software_dev.repo_map.read",),
            "manifests": (),
            "admissions": (),
        },
        clock=_clock,
    )

    decision = gate.admit(command_id="cmd-software-dev-change", intent_name="software_dev.change.run")
    read_model = gate.read_model()

    assert decision.status.value == "rejected"
    assert decision.capability_id == "software_dev.change.run"
    assert decision.reason == "capability manifest is not admitted for typed intent"
    assert read_model["capability_manifest_gated"] is True
    assert read_model["capability_manifest_coverage_status"] == "partial"
    assert read_model["capability_manifest_covered_count"] == 1
    assert "software_dev.change.run" in read_model["capability_manifest_missing_capability_ids"]
    coverage = {record["capability_id"]: record for record in read_model["capability_manifest_coverage"]}
    assert coverage["software_dev.repo_map.read"]["coverage_status"] == "covered"
    assert coverage["software_dev.change.run"]["coverage_status"] == "missing_manifest"
    assert coverage["software_dev.change.run"]["manifest_admitted"] is False
    assert coverage["software_dev.change.run"]["reason"] == "capability manifest is not admitted for typed intent"


def test_capability_fabric_manifest_coverage_reports_rejected_manifest_as_blocked() -> None:
    gate = build_capability_admission_gate(
        capsules=(load_software_dev_domain_capsule(),),
        capabilities=load_software_dev_capability_entries(),
        require_certified=True,
        capability_manifest_registry_read_model={
            "manifest_count": 0,
            "admission_count": 1,
            "capability_ids": (),
            "manifests": (),
            "admissions": (),
            "capability_abi_coverage": (
                {
                    "capability_id": "software_dev.change.run",
                    "coverage_status": "blocked",
                    "admission_status": "rejected",
                    "reason": "effect_bearing_capability_requires_rollback",
                    "maturity": "unknown",
                    "risk": "unknown",
                    "source_ref": "capabilities/software_dev/manifests/software_dev_change_run.capability.json",
                    "evidence_refs": ("admission-rejected",),
                    "errors": ("effect_bearing_capability_requires_rollback",),
                },
            ),
        },
        clock=_clock,
    )

    read_model = gate.read_model()
    coverage = {
        record["capability_id"]: record for record in read_model["capability_manifest_coverage"]
    }["software_dev.change.run"]

    assert read_model["capability_manifest_coverage_status"] == "blocked"
    assert coverage["capability_id"] == "software_dev.change.run"
    assert coverage["coverage_status"] == "blocked"
    assert coverage["manifest_admitted"] is False
    assert coverage["reason"] == "effect_bearing_capability_requires_rollback"


def test_capability_fabric_env_loader_rejects_production_hot_reload_for_manifest_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPSULE_PATH", str(SOFTWARE_DEV_CAPSULE_PATH))
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_CAPABILITY_PACK_PATH", str(SOFTWARE_DEV_CAPABILITY_PACK_PATH))
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_MANIFEST_REGISTRY_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_MANIFEST_ENVIRONMENT", "production")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_MANIFEST_HOT_RELOAD", "true")

    with pytest.raises(ValueError, match="production_hot_reload_denied_for_effect_bearing_capability"):
        build_capability_admission_gate_from_env(clock=_clock)


def test_default_capability_admission_gate_accepts_pack_capabilities() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    creative_decision = gate.admit(command_id="command-1", intent_name="creative.translate")
    enterprise_decision = gate.admit(command_id="command-2", intent_name="enterprise.task_schedule")
    payment_decision = gate.admit(command_id="command-4", intent_name="financial.send_payment")
    command_decision = gate.admit(command_id="command-5", intent_name="computer.command.run")
    workspace_preflight_decision = gate.admit(
        command_id="command-5b",
        intent_name="computer.workspace_file.preflight",
    )
    browser_decision = gate.admit(command_id="command-6", intent_name="browser.submit")
    document_decision = gate.admit(command_id="command-7", intent_name="document.generate_pdf")
    spreadsheet_decision = gate.admit(command_id="command-8", intent_name="spreadsheet.generate")
    voice_decision = gate.admit(command_id="command-9", intent_name="voice.intent_classification")
    voice_confirm_decision = gate.admit(command_id="command-14", intent_name="voice.intent_confirm")
    voice_summary_decision = gate.admit(command_id="command-15", intent_name="voice.meeting_summarize")
    voice_actions_decision = gate.admit(command_id="command-16", intent_name="voice.action_items_extract")
    connector_read_decision = gate.admit(command_id="command-10", intent_name="connector.github.read")
    connector_write_decision = gate.admit(command_id="command-11", intent_name="connector.postgres.write.with_approval")
    github_pr_decision = gate.admit(command_id="command-19", intent_name="github.open_pull_request")
    email_draft_decision = gate.admit(command_id="command-12", intent_name="email.draft")
    calendar_invite_decision = gate.admit(command_id="command-13", intent_name="calendar.invite")
    deployment_collect_decision = gate.admit(command_id="command-17", intent_name="deployment.witness.collect")
    deployment_publish_decision = gate.admit(
        command_id="command-18",
        intent_name="deployment.witness.publish.with_approval",
    )
    agentic_decision = gate.admit(command_id="command-20", intent_name="agentic_control.mission.define")
    rejected_decision = gate.admit(command_id="command-3", intent_name="gateway.unknown")

    assert creative_decision.status.value == "accepted"
    assert creative_decision.capability_id == "creative.translate"
    assert enterprise_decision.status.value == "accepted"
    assert enterprise_decision.owner_team == "enterprise-ops"
    assert payment_decision.status.value == "accepted"
    assert payment_decision.owner_team == "finance-ops"
    assert command_decision.status.value == "accepted"
    assert command_decision.owner_team == "platform-ops"
    assert workspace_preflight_decision.status.value == "accepted"
    assert workspace_preflight_decision.capability_id == "computer.workspace_file.preflight"
    assert browser_decision.status.value == "accepted"
    assert browser_decision.owner_team == "platform-ops"
    assert document_decision.status.value == "accepted"
    assert document_decision.owner_team == "platform-ops"
    assert spreadsheet_decision.status.value == "accepted"
    assert spreadsheet_decision.domain == "document"
    assert voice_decision.status.value == "accepted"
    assert voice_decision.domain == "voice"
    assert voice_confirm_decision.status.value == "accepted"
    assert voice_summary_decision.status.value == "accepted"
    assert voice_actions_decision.status.value == "accepted"
    assert connector_read_decision.status.value == "accepted"
    assert connector_read_decision.domain == "connector"
    assert connector_write_decision.status.value == "accepted"
    assert connector_write_decision.owner_team == "platform-ops"
    assert github_pr_decision.status.value == "accepted"
    assert github_pr_decision.capability_id == "github.open_pull_request"
    assert github_pr_decision.domain == "connector"
    assert email_draft_decision.status.value == "accepted"
    assert email_draft_decision.domain == "communication"
    assert calendar_invite_decision.status.value == "accepted"
    assert calendar_invite_decision.owner_team == "platform-ops"
    assert deployment_collect_decision.status.value == "accepted"
    assert deployment_collect_decision.domain == "deployment"
    assert deployment_publish_decision.status.value == "accepted"
    assert deployment_publish_decision.owner_team == "platform-ops"
    assert agentic_decision.status.value == "accepted"
    assert agentic_decision.domain == "agentic_control"
    assert rejected_decision.status.value == "rejected"
    assert rejected_decision.capability_id == ""


def test_default_capability_admission_gate_projects_unlock_obligations() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    payment_decision = gate.admit(command_id="command-payment", intent_name="financial.send_payment")
    document_decision = gate.admit(command_id="command-doc", intent_name="document.extract_text")

    assert payment_decision.status.value == "accepted"
    assert payment_decision.unlock_ladder_id == UNLOCK_LADDER_ID
    assert payment_decision.unlock_level == 8
    assert payment_decision.unlock_level_id == "L8"
    assert payment_decision.gate_template_ids == (
        GATE_CONNECTOR_LEASE,
        GATE_APPROVAL,
        GATE_VERIFIER,
        GATE_EXECUTION_RECEIPT,
        GATE_ROLLBACK,
    )
    assert payment_decision.requires_operator_approval is True
    assert payment_decision.requires_receipt is True
    assert payment_decision.requires_rollback is True
    assert payment_decision.requires_live_witness is True
    assert document_decision.status.value == "accepted"
    assert document_decision.unlock_level == 0
    assert document_decision.gate_template_ids == ("evidence_intake_gate",)
    assert document_decision.requires_receipt is False


def test_capability_admission_rejects_malformed_unlock_profile() -> None:
    capabilities = tuple(
        replace(
            entry,
            metadata={
                **entry.metadata,
                "unlock_ladder": {
                    "ladder_id": UNLOCK_LADDER_ID,
                    "level": 8,
                    "level_id": "L8",
                    "gate_template_ids": ("evidence_intake_gate",),
                },
            },
        )
        if entry.capability_id == "financial.send_payment"
        else entry
        for entry in load_default_capability_entries()
    )
    gate = build_capability_admission_gate(
        capsules=load_default_domain_capsules(),
        capabilities=capabilities,
        require_certified=True,
        clock=_clock,
    )

    decision = gate.admit(command_id="command-payment", intent_name="financial.send_payment")

    assert decision.status.value == "rejected"
    assert decision.capability_id == "financial.send_payment"
    assert decision.evidence_required == ()
    assert decision.gate_template_ids == ()
    assert decision.reason == "capability unlock profile invalid"
    assert decision.rejection_codes == ("unlock_ladder_gate_template_ids_mismatch",)


def test_default_runtime_handlers_are_backed_by_capability_contracts() -> None:
    default_dispatcher = build_capability_dispatcher_from_platform(None)
    financial_dispatcher = CapabilityDispatcher(
        financial_provider=object(),
        payment_executor=object(),
    )
    runtime_handler_ids = {
        *default_dispatcher._handlers,
        *financial_dispatcher._handlers,
    }
    contract_ids = {
        entry.capability_id
        for entry in load_default_capability_entries()
    }

    assert "creative.document_generate" in runtime_handler_ids
    assert "enterprise.task_schedule" in runtime_handler_ids
    assert "financial.send_payment" in runtime_handler_ids
    assert runtime_handler_ids <= contract_ids


def test_default_capability_entries_declare_reusable_unlock_profiles() -> None:
    entries = {
        entry.capability_id: entry
        for entry in (*load_default_capability_entries(), *load_software_dev_capability_entries())
    }
    expected_profiles = _expected_unlock_profiles()
    ladder_by_level = {level.level: level for level in default_capability_unlock_ladder()}

    assert expected_profiles.keys() <= entries.keys()
    for capability_id, expected_level in expected_profiles.items():
        profile = entries[capability_id].metadata["unlock_ladder"]
        ladder_level = ladder_by_level[expected_level]

        assert profile["ladder_id"] == UNLOCK_LADDER_ID
        assert profile["level"] == expected_level
        assert profile["level_id"] == ladder_level.level_id
        assert tuple(profile["gate_template_ids"]) == ladder_level.required_gate_ids


def test_default_capability_admission_gate_can_require_production_ready_maturity() -> None:
    gate = build_default_capability_admission_gate(clock=_clock, require_production_ready=True)

    production_decision = gate.admit(command_id="command-1", intent_name="financial.send_payment")
    sandbox_decision = gate.admit(command_id="command-2", intent_name="creative.translate")
    unknown_decision = gate.admit(command_id="command-3", intent_name="gateway.unknown")
    read_model = gate.read_model()

    assert production_decision.status.value == "accepted"
    assert production_decision.capability_id == "financial.send_payment"
    assert production_decision.owner_team == "finance-ops"
    assert sandbox_decision.status.value == "rejected"
    assert sandbox_decision.capability_id == "creative.translate"
    assert "capability is not production-ready" in sandbox_decision.reason
    assert "sandbox_receipt_missing" in sandbox_decision.reason
    assert unknown_decision.status.value == "rejected"
    assert unknown_decision.capability_id == ""
    assert read_model["require_production_ready"] is True
    assert read_model["production_ready_count"] == 2


def test_capability_fabric_env_loader_requires_production_ready_by_default_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS", "true")

    gate = build_capability_admission_gate_from_env(clock=_clock)
    sandbox_decision = gate.admit(command_id="command-1", intent_name="document.extract_text")
    production_decision = gate.admit(command_id="command-2", intent_name="connector.github.read")

    assert gate.read_model()["require_production_ready"] is True
    assert sandbox_decision.status.value == "rejected"
    assert sandbox_decision.domain == "document"
    assert "live_read_receipt_missing" in sandbox_decision.reason
    assert production_decision.status.value == "accepted"
    assert production_decision.capability_id == "connector.github.read"


def test_capability_fabric_env_loader_allows_sandbox_maturity_when_explicitly_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MULLU_ENV", "production")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_USE_DEFAULT_PACKS", "true")
    monkeypatch.setenv("MULLU_CAPABILITY_FABRIC_REQUIRE_PRODUCTION_READY", "false")

    gate = build_capability_admission_gate_from_env(clock=_clock)
    sandbox_decision = gate.admit(command_id="command-1", intent_name="document.extract_text")

    assert gate.read_model()["require_production_ready"] is False
    assert sandbox_decision.status.value == "accepted"
    assert sandbox_decision.capability_id == "document.extract_text"


def test_default_read_model_projects_governed_capability_records() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    records = {
        record["capability_id"]: record
        for record in gate.read_model()["governed_capability_records"]
    }
    capabilities = {
        capability["capability_id"]: capability
        for capability in gate.read_model()["capabilities"]
    }
    payment_record = records["financial.send_payment"]
    payment_capability = capabilities["financial.send_payment"]
    balance_record = records["financial.balance_check"]
    command_record = records["computer.command.run"]
    workspace_preflight_record = records["computer.workspace_file.preflight"]
    browser_record = records["browser.submit"]
    extract_record = records["document.extract_text"]
    pdf_record = records["document.generate_pdf"]
    phone_terminate_record = records["phone.call.terminate"]
    spreadsheet_record = records["spreadsheet.generate"]
    voice_record = records["voice.intent_classification"]
    voice_confirm_record = records["voice.intent_confirm"]
    voice_actions_record = records["voice.action_items_extract"]
    github_read_record = records["connector.github.read"]
    github_read_capability = capabilities["connector.github.read"]
    github_open_record = records["github.open_pull_request"]
    postgres_write_record = records["connector.postgres.write.with_approval"]
    email_send_record = records["email.send.with_approval"]
    calendar_invite_record = records["calendar.invite"]
    deployment_collect_record = records["deployment.witness.collect"]
    deployment_publish_record = records["deployment.witness.publish.with_approval"]
    mission_record = records["agentic_control.mission.define"]
    code_change_record = records["agentic_control.code_change.plan"]
    telemetry_record = records["agentic_control.telemetry_triage.plan"]
    release_handoff_record = records["agentic_control.release_handoff.plan"]
    evidence_record = records["agentic_control.evidence.append"]
    planes = {
        plane["plane_id"]: plane
        for plane in gate.read_model()["general_agent_planes"]
    }

    assert len(records) == 81
    assert payment_capability["maturity_assessment"]["maturity_level"] == "C6"
    assert payment_capability["maturity_assessment"]["maturity_label"] == "Verified"
    assert payment_capability["maturity_assessment"]["production_ready"] is True
    assert payment_capability["maturity_assessment"]["autonomy_ready"] is False
    assert payment_capability["maturity_assessment"]["blockers"] == ["autonomy_controls_missing"]
    assert payment_capability["maturity_assessment"]["metadata"]["assessment_is_not_promotion"] is True
    assert "capability_registry:financial.send_payment" in payment_capability["maturity_assessment"]["evidence_refs"]
    assert "proof://capabilities/financial.send_payment/live-write" in payment_capability["maturity_assessment"]["evidence_refs"]
    assert payment_record["maturity_level"] == "C6"
    assert payment_record["maturity_label"] == "Verified"
    assert payment_record["production_ready"] is True
    assert payment_record["autonomy_ready"] is False
    assert payment_record["maturity_assessment_id"].startswith("capability-maturity-")
    assert payment_record["risk_level"] == "high"
    assert payment_record["read_only"] is False
    assert payment_record["world_mutating"] is True
    assert payment_record["requires_approval"] is True
    assert payment_record["requires_sandbox"] is True
    assert payment_record["allowed_roles"] == ["finance_operator"]
    assert payment_record["allowed_tools"] == ["payment_executor.initiate_payment"]
    assert payment_record["allowed_networks"] == ["api.stripe.com"]
    assert payment_record["receipt_required"] is True
    assert payment_record["rollback_or_compensation_required"] is True
    assert balance_record["risk_level"] == "low"
    assert balance_record["read_only"] is True
    assert balance_record["world_mutating"] is False
    assert balance_record["requires_approval"] is False
    assert command_record["risk_level"] == "high"
    assert command_record["requires_approval"] is True
    assert command_record["requires_sandbox"] is True
    assert command_record["allowed_tools"] == ["sandbox_runner.execute"]
    assert command_record["allowed_paths"] == ["/workspace"]
    assert workspace_preflight_record["risk_level"] == "medium"
    assert workspace_preflight_record["read_only"] is True
    assert workspace_preflight_record["world_mutating"] is False
    assert workspace_preflight_record["requires_approval"] is False
    assert workspace_preflight_record["allowed_tools"] == ["workspace_file.preflight"]
    assert workspace_preflight_record["allowed_paths"] == ["/workspace"]
    assert browser_record["risk_level"] == "high"
    assert browser_record["requires_approval"] is True
    assert browser_record["requires_sandbox"] is True
    assert browser_record["allowed_tools"] == ["browser_worker.submit"]
    assert browser_record["allowed_networks"] == ["docs.mullusi.com", "learn.mullusi.com", "api.mullusi.com"]
    assert extract_record["risk_level"] == "low"
    assert extract_record["read_only"] is True
    assert extract_record["requires_sandbox"] is True
    assert extract_record["allowed_tools"] == ["document_worker.extract_text"]
    assert extract_record["allowed_networks"] == []
    assert pdf_record["risk_level"] == "medium"
    assert pdf_record["world_mutating"] is True
    assert pdf_record["rollback_or_compensation_required"] is True
    assert phone_terminate_record["risk_level"] == "high"
    assert phone_terminate_record["world_mutating"] is True
    assert phone_terminate_record["requires_approval"] is True
    assert phone_terminate_record["requires_sandbox"] is True
    assert phone_terminate_record["allowed_tools"] == ["phone_worker.call_terminate"]
    assert phone_terminate_record["forbidden_effects"] == [
        "phone_call_terminated_without_approval",
        "external_phone_call_placed",
        "credential_scope_exceeded",
    ]
    assert spreadsheet_record["capability_id"] == "spreadsheet.generate"
    assert spreadsheet_record["allowed_tools"] == ["document_worker.spreadsheet_generate"]
    assert voice_record["risk_level"] == "medium"
    assert voice_record["read_only"] is True
    assert voice_record["requires_sandbox"] is True
    assert voice_record["allowed_tools"] == ["voice_worker.intent_classification"]
    assert voice_record["forbidden_effects"] == ["tool_executed", "payment_created", "external_message_sent"]
    assert voice_confirm_record["allowed_tools"] == ["voice_worker.intent_confirm"]
    assert voice_confirm_record["forbidden_effects"] == ["tool_executed", "payment_created", "external_message_sent"]
    assert voice_actions_record["allowed_tools"] == ["voice_worker.action_items_extract"]
    assert voice_actions_record["forbidden_effects"] == ["tool_executed", "external_message_sent", "task_created"]
    assert github_read_record["risk_level"] == "low"
    assert github_read_capability["maturity_assessment"]["maturity_level"] == "C6"
    assert github_read_capability["maturity_assessment"]["maturity_label"] == "Verified"
    assert github_read_capability["maturity_assessment"]["production_ready"] is True
    assert github_read_capability["maturity_assessment"]["autonomy_ready"] is False
    assert "proof://capabilities/connector.github.read/live-read" in github_read_capability[
        "maturity_assessment"
    ]["evidence_refs"]
    assert github_read_record["maturity_level"] == "C6"
    assert github_read_record["maturity_label"] == "Verified"
    assert github_read_record["production_ready"] is True
    assert github_read_record["autonomy_ready"] is False
    assert github_read_record["read_only"] is True
    assert github_read_record["world_mutating"] is False
    assert github_read_record["requires_approval"] is False
    assert github_read_record["allowed_tools"] == ["connector_worker.github_read"]
    assert github_read_record["allowed_networks"] == ["api.github.com"]
    assert postgres_write_record["risk_level"] == "high"
    assert postgres_write_record["read_only"] is False
    assert postgres_write_record["world_mutating"] is True
    assert postgres_write_record["requires_approval"] is True
    assert postgres_write_record["rollback_or_compensation_required"] is True
    assert postgres_write_record["allowed_networks"] == ["postgres.internal"]
    assert github_open_record["risk_level"] == "high"
    assert github_open_record["read_only"] is False
    assert github_open_record["world_mutating"] is True
    assert github_open_record["requires_approval"] is True
    assert github_open_record["requires_sandbox"] is True
    assert github_open_record["allowed_tools"] == ["connector_worker.github_open_pull_request"]
    assert github_open_record["allowed_networks"] == ["api.github.com"]
    assert github_open_record["rollback_or_compensation_required"] is True
    assert github_open_record["forbidden_effects"] == [
        "credential_scope_exceeded",
        "cross_tenant_write",
        "git_push_executed",
        "production_deployment_started",
        "pull_request_opened_without_approval",
        "unreviewed_repository_write",
    ]
    assert email_send_record["risk_level"] == "high"
    assert email_send_record["read_only"] is False
    assert email_send_record["world_mutating"] is True
    assert email_send_record["requires_approval"] is True
    assert email_send_record["requires_sandbox"] is True
    assert email_send_record["allowed_tools"] == ["email_calendar_worker.email_send"]
    assert email_send_record["forbidden_effects"] == [
        "message_sent_without_approval",
        "credential_scope_exceeded",
        "recipient_unapproved",
    ]
    assert calendar_invite_record["risk_level"] == "high"
    assert calendar_invite_record["requires_approval"] is True
    assert calendar_invite_record["allowed_tools"] == ["email_calendar_worker.calendar_invite"]
    assert calendar_invite_record["allowed_networks"] == ["www.googleapis.com", "graph.microsoft.com"]
    assert deployment_collect_record["risk_level"] == "medium"
    assert deployment_collect_record["read_only"] is True
    assert deployment_collect_record["requires_sandbox"] is True
    assert deployment_collect_record["allowed_tools"] == ["deployment_witness.collect"]
    assert deployment_publish_record["risk_level"] == "high"
    assert deployment_publish_record["read_only"] is False
    assert deployment_publish_record["world_mutating"] is True
    assert deployment_publish_record["requires_approval"] is True
    assert deployment_publish_record["allowed_tools"] == ["deployment_witness.publish"]
    assert deployment_publish_record["forbidden_effects"] == [
        "unverified_health_claim_created",
        "unsigned_witness_published",
        "secret_value_exposed",
    ]
    assert mission_record["risk_level"] == "low"
    assert mission_record["read_only"] is True
    assert mission_record["world_mutating"] is False
    assert mission_record["requires_approval"] is False
    assert mission_record["allowed_tools"] == ["agentic_control.mission.define"]
    assert code_change_record["risk_level"] == "medium"
    assert code_change_record["read_only"] is True
    assert code_change_record["world_mutating"] is False
    assert code_change_record["allowed_roles"] == ["developer"]
    assert code_change_record["allowed_tools"] == ["agentic_control.code_change.plan"]
    assert code_change_record["forbidden_effects"] == [
        "workspace_file_written",
        "git_state_mutated",
        "test_result_fabricated",
    ]
    assert telemetry_record["risk_level"] == "medium"
    assert telemetry_record["read_only"] is True
    assert telemetry_record["world_mutating"] is False
    assert telemetry_record["allowed_roles"] == ["operator"]
    assert telemetry_record["allowed_tools"] == ["agentic_control.telemetry_triage.plan"]
    assert telemetry_record["forbidden_effects"] == [
        "threshold_mutated",
        "alert_suppressed",
        "external_message_sent",
    ]
    assert release_handoff_record["risk_level"] == "medium"
    assert release_handoff_record["read_only"] is True
    assert release_handoff_record["world_mutating"] is False
    assert release_handoff_record["allowed_roles"] == ["developer"]
    assert release_handoff_record["allowed_tools"] == ["agentic_control.release_handoff.plan"]
    assert release_handoff_record["forbidden_effects"] == [
        "git_push_executed",
        "pull_request_opened",
        "release_published",
    ]
    assert evidence_record["risk_level"] == "high"
    assert evidence_record["read_only"] is False
    assert evidence_record["world_mutating"] is True
    assert evidence_record["requires_approval"] is True
    assert evidence_record["receipt_required"] is True
    assert evidence_record["rollback_or_compensation_required"] is True
    assert "agentic_control.mission.define" in planes["0.governance_core"]["capability_ids"]
    assert "agentic_control.code_change.plan" in planes["0.governance_core"]["capability_ids"]
    assert "agentic_control.telemetry_triage.plan" in planes["0.governance_core"]["capability_ids"]
    assert "agentic_control.release_handoff.plan" in planes["0.governance_core"]["capability_ids"]
    assert "agentic_control.evidence.append" in planes["0.governance_core"]["capability_ids"]
    assert "financial.send_payment" in planes["8.financial_effect_plane"]["capability_ids"]
    assert "computer.command.run" in planes["4.computer_control_plane"]["capability_ids"]
    assert "browser.submit" in planes["5.browser_web_plane"]["capability_ids"]
    assert "document.extract_text" in planes["6.document_data_plane"]["capability_ids"]
    assert "connector.github.read" in planes["9.mcp_external_tool_plane"]["capability_ids"]
    assert "github.open_pull_request" in planes["9.mcp_external_tool_plane"]["capability_ids"]
    assert "deployment.witness.collect" in planes["12.deployment_witness_plane"]["capability_ids"]
    assert planes["8.financial_effect_plane"]["requires_approval_count"] >= 2
    assert planes["3.tool_skill_plane"]["governed_record_count"] == 61
    for plane in planes.values():
        assert "allowed_tools" not in plane
        assert "input_schema_ref" not in plane
        assert "extensions" not in plane


def _expected_unlock_profiles() -> dict[str, int]:
    return {
        "connector.google_drive.read": 7,
        "connector.google_drive.write.with_approval": 8,
        "connector.github.read": 7,
        "connector.github.write.with_approval": 8,
        "github.open_pull_request": 8,
        "connector.postgres.query": 7,
        "connector.postgres.write.with_approval": 8,
        "document.extract_text": 0,
        "document.extract_tables": 0,
        "document.summarize": 2,
        "document.generate_docx": 2,
        "document.generate_pdf": 2,
        "spreadsheet.analyze": 2,
        "spreadsheet.generate": 2,
        "financial.balance_check": 7,
        "financial.transaction_history": 7,
        "financial.spending_insights": 7,
        "financial.send_payment": 8,
        "financial.refund": 8,
        "browser.open": 1,
        "browser.screenshot": 1,
        "browser.extract_text": 1,
        "browser.click": 4,
        "browser.type": 4,
        "browser.submit": 8,
        "email.read": 7,
        "email.search": 7,
        "email.draft": 2,
        "email.send.with_approval": 8,
        "email.classify": 7,
        "email.reply_suggest": 7,
        "calendar.read": 7,
        "calendar.conflict_check": 7,
        "calendar.schedule": 8,
        "calendar.reschedule": 8,
        "calendar.invite": 8,
        "software_dev.repo_map.read": 0,
        "software_dev.context_bundle.build": 2,
        "software_dev.gate_plan.select": 2,
        "software_dev.change.run": 4,
        "software_dev.app_task_graph.plan": 2,
        "software_dev.pr_candidate.prepare": 5,
    }
