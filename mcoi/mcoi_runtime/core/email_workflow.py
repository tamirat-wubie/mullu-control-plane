"""Purpose: email workflow core — parse, extract, correlate, generate.
Governance scope: email workflow processing logic only.
Dependencies: email contracts, invariant helpers.
Invariants:
  - Approval parsing is explicit — ambiguous responses fail closed.
  - Correlation IDs must be present for workflow linkage.
  - Outbound messages carry explicit attribution and correlation.
  - No action is triggered from ambiguous email content.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from mcoi_runtime.contracts.email import (
    ActionExtractionStatus,
    ApprovalDecision,
    ApprovalResponse,
    EmailActionExtraction,
    EmailDirection,
    EmailEnvelope,
    EmailMessage,
    EmailParseResult,
    EmailParseStatus,
    EmailPurpose,
    EmailThreadRef,
    EmailWorkflowLink,
)
from .invariants import ensure_non_empty_text, stable_identifier


# --- Approval keywords for deterministic parsing ---

_APPROVE_PATTERNS = re.compile(
    r"\b(approved|approve|yes|accept|confirmed|lgtm|go ahead)\b",
    re.IGNORECASE,
)
_REJECT_PATTERNS = re.compile(
    r"\b(rejected|reject|no|deny|denied|declined|block|stop)\b",
    re.IGNORECASE,
)


def parse_approval_response(
    message: EmailMessage,
    expected_correlation_id: str,
) -> EmailParseResult:
    """Parse an inbound email as an approval response.

    Rules:
    - Both approve AND reject signals -> AMBIGUOUS (fail closed)
    - Only approve signals -> APPROVED
    - Only reject signals -> REJECTED
    - No signals -> AMBIGUOUS
    """
    ensure_non_empty_text("expected_correlation_id", expected_correlation_id)

    if message.direction is not EmailDirection.INBOUND:
        return EmailParseResult(
            parse_id=stable_identifier("parse", {"message_id": message.message_id}),
            message_id=message.message_id,
            status=EmailParseStatus.UNSUPPORTED,
            error_message="only inbound messages can be parsed as approval responses",
        )

    # Check correlation
    actual_correlation = (
        message.workflow_link.correlation_id
        if message.workflow_link else None
    )
    if actual_correlation != expected_correlation_id:
        return EmailParseResult(
            parse_id=stable_identifier("parse", {"message_id": message.message_id}),
            message_id=message.message_id,
            status=EmailParseStatus.MALFORMED,
            error_message=f"correlation mismatch: expected {expected_correlation_id}, got {actual_correlation}",
        )

    body = message.body
    has_approve = bool(_APPROVE_PATTERNS.search(body))
    has_reject = bool(_REJECT_PATTERNS.search(body))

    if has_approve and has_reject:
        decision = ApprovalDecision.AMBIGUOUS
    elif has_approve:
        decision = ApprovalDecision.APPROVED
    elif has_reject:
        decision = ApprovalDecision.REJECTED
    else:
        decision = ApprovalDecision.AMBIGUOUS

    response = ApprovalResponse(
        response_id=stable_identifier("approval", {"message_id": message.message_id}),
        message_id=message.message_id,
        correlation_id=expected_correlation_id,
        decision=decision,
        responder=message.envelope.sender,
    )

    return EmailParseResult(
        parse_id=stable_identifier("parse", {"message_id": message.message_id}),
        message_id=message.message_id,
        status=EmailParseStatus.PARSED,
        detected_purpose=EmailPurpose.APPROVAL_RESPONSE,
        approval_response=response,
    )


def extract_email_action(
    message: EmailMessage,
    known_action_keywords: Mapping[str, str] | None = None,
) -> EmailActionExtraction:
    """Extract actionable signal from an email.

    Uses simple keyword matching against known action types.
    Ambiguous or missing signals are reported explicitly.
    """
    keywords = known_action_keywords or {}
    body_lower = message.body.lower()
    subject_lower = message.envelope.subject.lower()
    combined = f"{subject_lower} {body_lower}"

    matches: list[tuple[str, str]] = []
    for keyword, action_type in sorted(keywords.items()):
        if keyword.lower() in combined:
            matches.append((keyword, action_type))

    extraction_id = stable_identifier("email-action", {"message_id": message.message_id})

    if len(matches) == 0:
        return EmailActionExtraction(
            extraction_id=extraction_id,
            message_id=message.message_id,
            status=ActionExtractionStatus.NO_ACTION,
        )

    if len(matches) > 1:
        return EmailActionExtraction(
            extraction_id=extraction_id,
            message_id=message.message_id,
            status=ActionExtractionStatus.AMBIGUOUS,
            action_parameters={"matched_keywords": [m[0] for m in matches]},
        )

    keyword, action_type = matches[0]
    return EmailActionExtraction(
        extraction_id=extraction_id,
        message_id=message.message_id,
        status=ActionExtractionStatus.ACTION_FOUND,
        action_type=action_type,
        action_parameters={"matched_keyword": keyword},
    )


def generate_approval_request(
    *,
    message_id: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    correlation_id: str,
    skill_id: str | None = None,
    goal_id: str | None = None,
) -> EmailMessage:
    """Generate an outbound approval request email with workflow linkage."""
    ensure_non_empty_text("message_id", message_id)
    ensure_non_empty_text("sender", sender)
    ensure_non_empty_text("recipient", recipient)

    return EmailMessage(
        message_id=message_id,
        direction=EmailDirection.OUTBOUND,
        purpose=EmailPurpose.APPROVAL_REQUEST,
        envelope=EmailEnvelope(
            sender=sender,
            recipients=(recipient,),
            subject=subject,
        ),
        body=body,
        workflow_link=EmailWorkflowLink(
            correlation_id=correlation_id,
            skill_id=skill_id,
            goal_id=goal_id,
        ),
    )


def generate_completion_notice(
    *,
    message_id: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    correlation_id: str,
    execution_id: str | None = None,
    skill_id: str | None = None,
) -> EmailMessage:
    """Generate an outbound completion notification with workflow linkage."""
    ensure_non_empty_text("message_id", message_id)

    return EmailMessage(
        message_id=message_id,
        direction=EmailDirection.OUTBOUND,
        purpose=EmailPurpose.COMPLETION,
        envelope=EmailEnvelope(
            sender=sender,
            recipients=(recipient,),
            subject=subject,
        ),
        body=body,
        workflow_link=EmailWorkflowLink(
            correlation_id=correlation_id,
            skill_id=skill_id,
            execution_id=execution_id,
        ),
    )


def generate_escalation(
    *,
    message_id: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    correlation_id: str,
    goal_id: str | None = None,
) -> EmailMessage:
    """Generate an outbound escalation email."""
    ensure_non_empty_text("message_id", message_id)

    return EmailMessage(
        message_id=message_id,
        direction=EmailDirection.OUTBOUND,
        purpose=EmailPurpose.ESCALATION,
        envelope=EmailEnvelope(
            sender=sender,
            recipients=(recipient,),
            subject=subject,
        ),
        body=body,
        workflow_link=EmailWorkflowLink(
            correlation_id=correlation_id,
            goal_id=goal_id,
        ),
    )
