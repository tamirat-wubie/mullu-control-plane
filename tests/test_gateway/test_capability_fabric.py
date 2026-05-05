"""Purpose: validate gateway capability fabric loader configuration paths.
Governance scope: environment-gated capability fabric admission and checked-in
    default capsule/capability pack installation.
Dependencies: gateway capability fabric loader and governed capability registry.
Invariants:
  - Fabric admission remains disabled unless explicitly enabled.
  - Enabled admission requires explicit sources unless default packs are requested.
  - Checked-in default packs install all certified browser, communication, connector, creative, document, enterprise, financial, computer, and voice entries.
  - Operator read models expose governed capability records, not raw tool handles.
"""

from __future__ import annotations

import os

import pytest

from gateway.capability_fabric import (
    build_capability_admission_gate_from_env,
    build_default_capability_admission_gate,
    load_default_capability_entries,
    load_default_domain_capsules,
)


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
    assert load_default_domain_capsules()[0].capsule_id == "browser.restricted_ops.v0"
    assert load_default_capability_entries()[0].capability_id == "browser.open"


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
    assert read_model["capsule_count"] == 10
    assert read_model["capability_count"] == 52
    assert len(read_model["capability_maturity_assessments"]) == 52
    assert read_model["capability_maturity_counts"]["C3"] == 50
    assert read_model["capability_maturity_counts"]["C6"] == 2
    assert read_model["production_ready_count"] == 2
    assert read_model["autonomy_ready_count"] == 0
    assert {domain["domain"] for domain in read_model["domains"]} == {
        "browser",
        "communication",
        "computer",
        "connector",
        "creative",
        "deployment",
        "document",
        "enterprise",
        "financial",
        "voice",
    }


def test_default_capability_admission_gate_accepts_pack_capabilities() -> None:
    gate = build_default_capability_admission_gate(clock=_clock)

    creative_decision = gate.admit(command_id="command-1", intent_name="creative.translate")
    enterprise_decision = gate.admit(command_id="command-2", intent_name="enterprise.task_schedule")
    payment_decision = gate.admit(command_id="command-4", intent_name="financial.send_payment")
    command_decision = gate.admit(command_id="command-5", intent_name="computer.command.run")
    browser_decision = gate.admit(command_id="command-6", intent_name="browser.submit")
    document_decision = gate.admit(command_id="command-7", intent_name="document.generate_pdf")
    spreadsheet_decision = gate.admit(command_id="command-8", intent_name="spreadsheet.generate")
    voice_decision = gate.admit(command_id="command-9", intent_name="voice.intent_classification")
    voice_confirm_decision = gate.admit(command_id="command-14", intent_name="voice.intent_confirm")
    voice_summary_decision = gate.admit(command_id="command-15", intent_name="voice.meeting_summarize")
    voice_actions_decision = gate.admit(command_id="command-16", intent_name="voice.action_items_extract")
    connector_read_decision = gate.admit(command_id="command-10", intent_name="connector.github.read")
    connector_write_decision = gate.admit(command_id="command-11", intent_name="connector.postgres.write.with_approval")
    email_draft_decision = gate.admit(command_id="command-12", intent_name="email.draft")
    calendar_invite_decision = gate.admit(command_id="command-13", intent_name="calendar.invite")
    deployment_collect_decision = gate.admit(command_id="command-17", intent_name="deployment.witness.collect")
    deployment_publish_decision = gate.admit(
        command_id="command-18",
        intent_name="deployment.witness.publish.with_approval",
    )
    rejected_decision = gate.admit(command_id="command-3", intent_name="gateway.unknown")

    assert creative_decision.status.value == "accepted"
    assert creative_decision.capability_id == "creative.translate"
    assert enterprise_decision.status.value == "accepted"
    assert enterprise_decision.owner_team == "enterprise-ops"
    assert payment_decision.status.value == "accepted"
    assert payment_decision.owner_team == "finance-ops"
    assert command_decision.status.value == "accepted"
    assert command_decision.owner_team == "platform-ops"
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
    assert email_draft_decision.status.value == "accepted"
    assert email_draft_decision.domain == "communication"
    assert calendar_invite_decision.status.value == "accepted"
    assert calendar_invite_decision.owner_team == "platform-ops"
    assert deployment_collect_decision.status.value == "accepted"
    assert deployment_collect_decision.domain == "deployment"
    assert deployment_publish_decision.status.value == "accepted"
    assert deployment_publish_decision.owner_team == "platform-ops"
    assert rejected_decision.status.value == "rejected"
    assert rejected_decision.capability_id == ""


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
    browser_record = records["browser.submit"]
    extract_record = records["document.extract_text"]
    pdf_record = records["document.generate_pdf"]
    spreadsheet_record = records["spreadsheet.generate"]
    voice_record = records["voice.intent_classification"]
    voice_confirm_record = records["voice.intent_confirm"]
    voice_actions_record = records["voice.action_items_extract"]
    github_read_record = records["connector.github.read"]
    github_read_capability = capabilities["connector.github.read"]
    postgres_write_record = records["connector.postgres.write.with_approval"]
    email_send_record = records["email.send.with_approval"]
    calendar_invite_record = records["calendar.invite"]
    deployment_collect_record = records["deployment.witness.collect"]
    deployment_publish_record = records["deployment.witness.publish.with_approval"]

    assert len(records) == 52
    assert payment_capability["maturity_assessment"]["maturity_level"] == "C6"
    assert payment_capability["maturity_assessment"]["production_ready"] is True
    assert payment_capability["maturity_assessment"]["autonomy_ready"] is False
    assert payment_capability["maturity_assessment"]["blockers"] == ["autonomy_controls_missing"]
    assert payment_capability["maturity_assessment"]["metadata"]["assessment_is_not_promotion"] is True
    assert "capability_registry:financial.send_payment" in payment_capability["maturity_assessment"]["evidence_refs"]
    assert "proof://capabilities/financial.send_payment/live-write" in payment_capability["maturity_assessment"]["evidence_refs"]
    assert payment_record["maturity_level"] == "C6"
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
    assert github_read_capability["maturity_assessment"]["production_ready"] is True
    assert github_read_capability["maturity_assessment"]["autonomy_ready"] is False
    assert "proof://capabilities/connector.github.read/live-read" in github_read_capability[
        "maturity_assessment"
    ]["evidence_refs"]
    assert github_read_record["maturity_level"] == "C6"
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
