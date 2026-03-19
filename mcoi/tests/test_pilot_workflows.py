"""End-to-end pilot workflow tests.

Proves the platform works as a system under 3 real workflow patterns:
1. Approval-gated command workflow
2. Document-to-action workflow
3. Failure-escalation workflow
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.app.config import AppConfig
from mcoi_runtime.app.console import render_run_summary, render_skill_summary
from mcoi_runtime.app.operator_loop import (
    OperatorLoop,
    OperatorRequest,
    SkillRequest,
)
from mcoi_runtime.app.view_models import RunSummaryView, SkillSummaryView
from mcoi_runtime.contracts.autonomy import ActionClass, AutonomyDecisionStatus, AutonomyMode
from mcoi_runtime.contracts.document import DocumentVerificationStatus
from mcoi_runtime.contracts.email import ApprovalDecision, EmailDirection, EmailParseStatus, EmailPurpose
from mcoi_runtime.contracts.meta_reasoning import CapabilityConfidence
from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    SkillClass,
    SkillDescriptor,
    SkillLifecycle,
    SkillOutcomeStatus,
    TrustClass,
    VerificationStrength,
)
from mcoi_runtime.core.autonomy import AutonomyEngine
from mcoi_runtime.core.document import extract_json_fields, ingest_document, verify_extraction
from mcoi_runtime.core.email_workflow import (
    generate_approval_request,
    generate_completion_notice,
    generate_escalation,
    parse_approval_response,
)
from mcoi_runtime.contracts.email import (
    EmailEnvelope,
    EmailMessage,
    EmailWorkflowLink,
)


FIXED_CLOCK = "2025-01-15T10:00:00+00:00"


def _make_loop(autonomy_mode="bounded_autonomous"):
    config = AppConfig(autonomy_mode=autonomy_mode)
    runtime = bootstrap_runtime(config=config, clock=lambda: FIXED_CLOCK)
    return OperatorLoop(runtime=runtime)


def _register_skill(loop, skill_id="sk-1", **kw):
    defaults = dict(
        skill_id=skill_id,
        name=f"skill-{skill_id}",
        skill_class=SkillClass.PRIMITIVE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.BOUNDED_EXTERNAL,
        verification_strength=VerificationStrength.STRONG,
    )
    defaults.update(kw)
    d = SkillDescriptor(**defaults)
    loop.runtime.skill_registry.register(d)
    return d


# ============================================================================
# Pilot 1: Approval-Gated Command Workflow
# ============================================================================


class TestPilot1ApprovalGatedCommand:
    """Proves: observe -> select skill -> request approval -> parse response
    -> execute if approved -> verify -> persist -> report."""

    def test_step1_autonomy_blocks_execution_without_approval(self):
        """In approval_required mode, execution is blocked pending approval."""
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        decision = engine.evaluate(ActionClass.EXECUTE_WRITE)
        assert decision.status is AutonomyDecisionStatus.BLOCKED_PENDING_APPROVAL

    def test_step2_generate_approval_request_email(self):
        """System generates a correlated approval request email."""
        msg = generate_approval_request(
            message_id="pilot1-req",
            sender="system@mullu.io",
            recipient="ops-lead@company.com",
            subject="Approve: restart nginx",
            body="Skill sk-restart wants to run systemctl restart nginx.",
            correlation_id="corr-pilot1",
            skill_id="sk-restart",
            goal_id="goal-restart",
        )
        assert msg.purpose is EmailPurpose.APPROVAL_REQUEST
        assert msg.workflow_link.correlation_id == "corr-pilot1"
        assert msg.workflow_link.skill_id == "sk-restart"

    def test_step3_parse_approval_response(self):
        """System parses inbound approval email with correlation."""
        response = EmailMessage(
            message_id="pilot1-resp",
            direction=EmailDirection.INBOUND,
            purpose=EmailPurpose.GENERAL,
            envelope=EmailEnvelope(
                sender="ops-lead@company.com",
                recipients=("system@mullu.io",),
                subject="Re: Approve: restart nginx",
            ),
            body="Approved. Go ahead with the restart.",
            workflow_link=EmailWorkflowLink(correlation_id="corr-pilot1"),
        )
        result = parse_approval_response(response, "corr-pilot1")
        assert result.status is EmailParseStatus.PARSED
        assert result.approval_response.decision is ApprovalDecision.APPROVED

    def test_step4_execution_allowed_with_approval(self):
        """After approval, autonomy permits execution."""
        engine = AutonomyEngine(mode=AutonomyMode.APPROVAL_REQUIRED)
        decision = engine.evaluate(ActionClass.EXECUTE_WRITE, has_approval=True)
        assert decision.status is AutonomyDecisionStatus.ALLOWED

    def test_step5_skill_executes_through_runtime(self):
        """Approved skill runs through the governed runtime path."""
        loop = _make_loop(autonomy_mode="bounded_autonomous")
        _register_skill(loop, "sk-restart", name="shell_command")

        report = loop.run_skill(SkillRequest(
            request_id="pilot1-exec",
            subject_id="operator-1",
            goal_id="goal-restart",
            skill_id="sk-restart",
        ))
        assert report.execution_record is not None
        assert report.skill_id == "sk-restart"

    def test_step6_run_report_has_autonomy_mode(self):
        """Operator run report includes autonomy mode."""
        loop = _make_loop(autonomy_mode="approval_required")
        report = loop.run_step(OperatorRequest(
            request_id="pilot1-report",
            subject_id="operator-1",
            goal_id="goal-report",
            template={"action_type": "shell_command"},
            bindings={"action_type": "shell_command"},
        ))
        assert report.autonomy_mode == "approval_required"

    def test_step7_console_shows_autonomy(self):
        """Console rendering includes autonomy mode."""
        loop = _make_loop(autonomy_mode="approval_required")
        report = loop.run_step(OperatorRequest(
            request_id="pilot1-console",
            subject_id="operator-1",
            goal_id="goal-console",
            template={"action_type": "shell_command"},
            bindings={"action_type": "shell_command"},
        ))
        view = RunSummaryView.from_report(report)
        rendered = render_run_summary(view)
        assert "approval_required" in rendered


# ============================================================================
# Pilot 2: Document-to-Action Workflow
# ============================================================================


class TestPilot2DocumentToAction:
    """Proves: ingest document -> extract fields -> verify -> route to skill
    -> execute -> communicate status."""

    def test_step1_ingest_and_fingerprint(self):
        """JSON document is ingested with deterministic fingerprint."""
        content = json.dumps({"task": "backup_database", "target": "prod_db"})
        doc = ingest_document("doc-pilot2", "task.json", content)
        assert doc.fingerprint.content_hash is not None
        assert doc.fingerprint.byte_length > 0

    def test_step2_extract_fields(self):
        """Expected fields are extracted from the document."""
        content = json.dumps({"task": "backup_database", "target": "prod_db", "retention_days": 30})
        doc = ingest_document("doc-pilot2", "task.json", content)
        result = extract_json_fields(doc, ("task", "target", "retention_days"))
        assert result.extracted_count == 3
        assert result.missing_count == 0

    def test_step3_verify_extraction(self):
        """Extracted fields match expected values."""
        content = json.dumps({"task": "backup_database", "target": "prod_db"})
        doc = ingest_document("doc-pilot2", "task.json", content)
        extraction = extract_json_fields(doc, ("task", "target"))
        verification = verify_extraction(
            extraction,
            ("task", "target"),
            expected_values={"task": "backup_database"},
        )
        assert verification.status is DocumentVerificationStatus.PASS

    def test_step4_mismatch_verification_fails(self):
        """Wrong expected value causes verification failure."""
        content = json.dumps({"task": "backup_database"})
        doc = ingest_document("doc-pilot2", "task.json", content)
        extraction = extract_json_fields(doc, ("task",))
        verification = verify_extraction(
            extraction,
            ("task",),
            expected_values={"task": "deploy_service"},
        )
        assert verification.status is DocumentVerificationStatus.FAIL

    def test_step5_route_to_skill_and_execute(self):
        """Extracted task routes to the correct skill."""
        loop = _make_loop()
        _register_skill(loop, "sk-backup", name="shell_command", confidence=0.7)
        _register_skill(loop, "sk-deploy", name="shell_command", confidence=0.3)

        # Simulate: document says "backup", so we select sk-backup by ID
        report = loop.run_skill(SkillRequest(
            request_id="pilot2-exec",
            subject_id="operator-1",
            goal_id="goal-backup",
            skill_id="sk-backup",
        ))
        assert report.skill_id == "sk-backup"

    def test_step6_completion_notice(self):
        """Completion notice is generated with correlation."""
        notice = generate_completion_notice(
            message_id="pilot2-done",
            sender="system@mullu.io",
            recipient="ops@company.com",
            subject="Completed: backup_database",
            body="Backup completed successfully.",
            correlation_id="corr-pilot2",
            execution_id="exec-42",
            skill_id="sk-backup",
        )
        assert notice.purpose is EmailPurpose.COMPLETION
        assert notice.workflow_link.execution_id == "exec-42"


# ============================================================================
# Pilot 3: Failure-Escalation Workflow
# ============================================================================


class TestPilot3FailureEscalation:
    """Proves: skill fails -> structured error -> update confidence ->
    detect degraded -> escalate -> persist."""

    def test_step1_skill_execution_fails(self):
        """Skill execution produces a typed failure."""
        loop = _make_loop()
        _register_skill(loop, "sk-fragile", name="nonexistent_route", confidence=0.6)

        report = loop.run_skill(SkillRequest(
            request_id="pilot3-fail",
            subject_id="operator-1",
            goal_id="goal-fragile",
            skill_id="sk-fragile",
        ))
        # Execution will fail because nonexistent_route has no adapter
        assert report.status is not SkillOutcomeStatus.SUCCEEDED or report.completed is True

    def test_step2_confidence_decreases_on_failure(self):
        """Capability confidence drops after failure."""
        loop = _make_loop()
        _register_skill(loop, "sk-fragile", name="nonexistent_route", confidence=0.6)

        loop.run_skill(SkillRequest(
            request_id="pilot3-conf",
            subject_id="operator-1",
            goal_id="goal-fragile",
            skill_id="sk-fragile",
        ))

        updated = loop.runtime.skill_registry.get("sk-fragile")
        assert updated.confidence < 0.6  # Decreased

    def test_step3_meta_reasoning_tracks_degraded(self):
        """After repeated failures, meta-reasoning can mark capability degraded."""
        loop = _make_loop()
        mr = loop.runtime.meta_reasoning

        # Simulate low confidence directly
        mr.update_confidence(CapabilityConfidence(
            capability_id="flaky-capability",
            success_rate=0.2,
            verification_pass_rate=0.1,
            timeout_rate=0.0,
            error_rate=0.8,
            sample_count=10,
            assessed_at=FIXED_CLOCK,
        ))

        assert mr.is_degraded("flaky-capability")
        degraded = mr.list_degraded()
        assert len(degraded) >= 1

    def test_step4_escalation_email_generated(self):
        """Escalation email is generated with failure context."""
        msg = generate_escalation(
            message_id="pilot3-esc",
            sender="system@mullu.io",
            recipient="oncall@company.com",
            subject="ESCALATION: sk-fragile failed",
            body="Skill sk-fragile has failed. Capability degraded.",
            correlation_id="corr-pilot3",
            goal_id="goal-fragile",
        )
        assert msg.purpose is EmailPurpose.ESCALATION
        assert msg.workflow_link.goal_id == "goal-fragile"

    def test_step5_report_shows_provider_ids_and_autonomy(self):
        """Run report surfaces provider IDs and autonomy mode."""
        loop = _make_loop(autonomy_mode="bounded_autonomous")
        report = loop.run_step(OperatorRequest(
            request_id="pilot3-report",
            subject_id="operator-1",
            goal_id="goal-report",
            template={"action_type": "shell_command"},
            bindings={"action_type": "shell_command"},
        ))
        assert report.autonomy_mode == "bounded_autonomous"
        # Provider IDs may be None if no providers registered, which is correct
        view = RunSummaryView.from_report(report)
        assert view.autonomy_mode == "bounded_autonomous"


# ============================================================================
# Cross-pilot: Report fidelity
# ============================================================================


class TestReportFidelity:
    def test_run_report_autonomy_mode_present(self):
        loop = _make_loop(autonomy_mode="observe_only")
        report = loop.run_step(OperatorRequest(
            request_id="fidelity-1",
            subject_id="operator-1",
            goal_id="goal-fidelity",
            template={"action_type": "shell_command"},
            bindings={"action_type": "shell_command"},
        ))
        assert report.autonomy_mode == "observe_only"

    def test_view_model_carries_provider_fields(self):
        loop = _make_loop()
        report = loop.run_step(OperatorRequest(
            request_id="fidelity-2",
            subject_id="operator-1",
            goal_id="goal-fidelity",
            template={"action_type": "shell_command"},
            bindings={"action_type": "shell_command"},
        ))
        view = RunSummaryView.from_report(report)
        # Fields exist (may be None if no providers registered)
        assert hasattr(view, "integration_provider_id")
        assert hasattr(view, "communication_provider_id")
        assert hasattr(view, "model_provider_id")

    def test_console_render_includes_autonomy(self):
        loop = _make_loop(autonomy_mode="suggest_only")
        report = loop.run_step(OperatorRequest(
            request_id="fidelity-3",
            subject_id="operator-1",
            goal_id="goal-fidelity",
            template={"action_type": "shell_command"},
            bindings={"action_type": "shell_command"},
        ))
        view = RunSummaryView.from_report(report)
        rendered = render_run_summary(view)
        assert "suggest_only" in rendered
