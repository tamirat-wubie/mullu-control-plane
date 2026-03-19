"""Golden scenario tests for email workflow automation.

Proves end-to-end email parsing, approval extraction, action extraction,
outbound generation, and correlation linkage.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.email import (
    ActionExtractionStatus,
    ApprovalDecision,
    EmailDirection,
    EmailEnvelope,
    EmailMessage,
    EmailParseStatus,
    EmailPurpose,
    EmailWorkflowLink,
)
from mcoi_runtime.core.email_workflow import (
    extract_email_action,
    generate_approval_request,
    generate_completion_notice,
    generate_escalation,
    parse_approval_response,
)


# --- Helpers ---


def _inbound(
    message_id="msg-1",
    body="",
    subject="Re: Approval Request",
    sender="user@example.com",
    correlation_id="corr-1",
    purpose=EmailPurpose.GENERAL,
):
    return EmailMessage(
        message_id=message_id,
        direction=EmailDirection.INBOUND,
        purpose=purpose,
        envelope=EmailEnvelope(
            sender=sender,
            recipients=("system@mullu.io",),
            subject=subject,
        ),
        body=body,
        workflow_link=EmailWorkflowLink(correlation_id=correlation_id),
    )


# --- Approval parsing ---


class TestApprovalParsing:
    def test_approved_signal(self):
        msg = _inbound(body="Yes, I approve this action. Go ahead.")
        result = parse_approval_response(msg, "corr-1")
        assert result.status is EmailParseStatus.PARSED
        assert result.approval_response is not None
        assert result.approval_response.decision is ApprovalDecision.APPROVED

    def test_rejected_signal(self):
        msg = _inbound(body="No, I reject this. Please stop.")
        result = parse_approval_response(msg, "corr-1")
        assert result.status is EmailParseStatus.PARSED
        assert result.approval_response.decision is ApprovalDecision.REJECTED

    def test_ambiguous_both_signals(self):
        msg = _inbound(body="I approve the first part but reject the second.")
        result = parse_approval_response(msg, "corr-1")
        assert result.status is EmailParseStatus.PARSED
        assert result.approval_response.decision is ApprovalDecision.AMBIGUOUS

    def test_ambiguous_no_signals(self):
        msg = _inbound(body="Thanks for the update, will review later.")
        result = parse_approval_response(msg, "corr-1")
        assert result.status is EmailParseStatus.PARSED
        assert result.approval_response.decision is ApprovalDecision.AMBIGUOUS

    def test_correlation_mismatch(self):
        msg = _inbound(body="Approved", correlation_id="wrong-corr")
        result = parse_approval_response(msg, "corr-1")
        assert result.status is EmailParseStatus.MALFORMED
        assert "correlation mismatch" in result.error_message

    def test_outbound_message_unsupported(self):
        msg = EmailMessage(
            message_id="msg-out",
            direction=EmailDirection.OUTBOUND,
            purpose=EmailPurpose.GENERAL,
            envelope=EmailEnvelope(
                sender="system@mullu.io",
                recipients=("user@example.com",),
                subject="test",
            ),
            body="approved",
        )
        result = parse_approval_response(msg, "corr-1")
        assert result.status is EmailParseStatus.UNSUPPORTED

    def test_lgtm_recognized_as_approval(self):
        msg = _inbound(body="LGTM, ship it!")
        result = parse_approval_response(msg, "corr-1")
        assert result.approval_response.decision is ApprovalDecision.APPROVED

    def test_responder_preserved(self):
        msg = _inbound(body="Approved", sender="boss@company.com")
        result = parse_approval_response(msg, "corr-1")
        assert result.approval_response.responder == "boss@company.com"


# --- Action extraction ---


class TestActionExtraction:
    def test_single_keyword_match(self):
        msg = _inbound(body="Please deploy the service.", subject="Deployment request")
        result = extract_email_action(msg, {"deploy": "deploy_service"})
        assert result.status is ActionExtractionStatus.ACTION_FOUND
        assert result.action_type == "deploy_service"

    def test_no_keyword_match(self):
        msg = _inbound(body="Just checking in.")
        result = extract_email_action(msg, {"deploy": "deploy_service"})
        assert result.status is ActionExtractionStatus.NO_ACTION

    def test_ambiguous_multiple_matches(self):
        msg = _inbound(body="Please deploy and also restart the service.")
        result = extract_email_action(msg, {
            "deploy": "deploy_service",
            "restart": "restart_service",
        })
        assert result.status is ActionExtractionStatus.AMBIGUOUS

    def test_keyword_in_subject(self):
        msg = _inbound(body="See attached.", subject="Deploy request")
        result = extract_email_action(msg, {"deploy": "deploy_service"})
        assert result.status is ActionExtractionStatus.ACTION_FOUND

    def test_empty_keywords(self):
        msg = _inbound(body="Do something")
        result = extract_email_action(msg, {})
        assert result.status is ActionExtractionStatus.NO_ACTION

    def test_no_keywords_provided(self):
        msg = _inbound(body="Do something")
        result = extract_email_action(msg)
        assert result.status is ActionExtractionStatus.NO_ACTION


# --- Outbound generation ---


class TestOutboundGeneration:
    def test_approval_request_generation(self):
        msg = generate_approval_request(
            message_id="msg-out-1",
            sender="system@mullu.io",
            recipient="approver@company.com",
            subject="Approval needed: deploy-v2",
            body="Please approve the deployment of service v2.",
            correlation_id="corr-100",
            skill_id="sk-deploy",
            goal_id="goal-deploy-v2",
        )
        assert msg.direction is EmailDirection.OUTBOUND
        assert msg.purpose is EmailPurpose.APPROVAL_REQUEST
        assert msg.workflow_link.correlation_id == "corr-100"
        assert msg.workflow_link.skill_id == "sk-deploy"
        assert msg.workflow_link.goal_id == "goal-deploy-v2"
        assert msg.envelope.recipients == ("approver@company.com",)

    def test_completion_notice_generation(self):
        msg = generate_completion_notice(
            message_id="msg-out-2",
            sender="system@mullu.io",
            recipient="user@company.com",
            subject="Completed: backup-db",
            body="Database backup completed successfully.",
            correlation_id="corr-200",
            execution_id="exec-42",
            skill_id="sk-backup",
        )
        assert msg.purpose is EmailPurpose.COMPLETION
        assert msg.workflow_link.execution_id == "exec-42"
        assert msg.workflow_link.skill_id == "sk-backup"

    def test_escalation_generation(self):
        msg = generate_escalation(
            message_id="msg-out-3",
            sender="system@mullu.io",
            recipient="oncall@company.com",
            subject="ESCALATION: deploy failed",
            body="The deploy-v2 skill failed after 3 retries.",
            correlation_id="corr-300",
            goal_id="goal-deploy-v2",
        )
        assert msg.purpose is EmailPurpose.ESCALATION
        assert msg.workflow_link.correlation_id == "corr-300"
        assert msg.workflow_link.goal_id == "goal-deploy-v2"


# --- End-to-end golden scenarios ---


class TestEndToEndScenarios:
    def test_approval_request_then_approved_response(self):
        """Golden: send approval request, receive approval, parse it."""
        request = generate_approval_request(
            message_id="msg-req-1",
            sender="system@mullu.io",
            recipient="approver@co.com",
            subject="Approve deploy?",
            body="Please approve deployment.",
            correlation_id="corr-e2e-1",
            skill_id="sk-deploy",
        )

        response = _inbound(
            message_id="msg-resp-1",
            body="Yes, approved. Go ahead.",
            sender="approver@co.com",
            correlation_id="corr-e2e-1",
        )

        parse_result = parse_approval_response(response, "corr-e2e-1")
        assert parse_result.status is EmailParseStatus.PARSED
        assert parse_result.approval_response.decision is ApprovalDecision.APPROVED
        assert parse_result.approval_response.correlation_id == "corr-e2e-1"

    def test_approval_request_then_rejection(self):
        """Golden: send request, receive rejection."""
        response = _inbound(
            body="No, I deny this action.",
            correlation_id="corr-e2e-2",
        )
        parse_result = parse_approval_response(response, "corr-e2e-2")
        assert parse_result.approval_response.decision is ApprovalDecision.REJECTED

    def test_ambiguous_response_blocks_action(self):
        """Golden: ambiguous response must NOT be treated as approval."""
        response = _inbound(
            body="I'm not sure about this yet.",
            correlation_id="corr-e2e-3",
        )
        parse_result = parse_approval_response(response, "corr-e2e-3")
        assert parse_result.approval_response.decision is ApprovalDecision.AMBIGUOUS

    def test_completion_notice_links_to_execution(self):
        """Golden: completion notice carries execution linkage."""
        notice = generate_completion_notice(
            message_id="msg-done-1",
            sender="system@mullu.io",
            recipient="user@co.com",
            subject="Done: backup",
            body="Backup completed.",
            correlation_id="corr-e2e-4",
            execution_id="exec-99",
        )
        assert notice.workflow_link.execution_id == "exec-99"
        assert notice.workflow_link.correlation_id == "corr-e2e-4"

    def test_email_action_routes_to_skill(self):
        """Golden: email with known keyword extracts action deterministically."""
        msg = _inbound(
            body="Please restart the database service.",
            subject="Service restart needed",
            correlation_id="corr-e2e-5",
        )
        result = extract_email_action(msg, {"restart": "restart_service"})
        assert result.status is ActionExtractionStatus.ACTION_FOUND
        assert result.action_type == "restart_service"
