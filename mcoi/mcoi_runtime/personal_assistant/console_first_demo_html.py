"""Purpose: render First Usable Demo extension panels in the assistant console HTML.

Governance scope: HTML-only read-model projection for fixture-backed demo panels.
Dependencies: personal_assistant.console base renderer and console_first_demo read model.
Invariants: this module does not execute skills, call connectors, create provider
 drafts, send email, pay invoices, write memory, mutate deployments, or claim
 customer readiness.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping

from .console import render_personal_assistant_console_html as _render_base_console_html


def render_personal_assistant_console_html(payload: Mapping[str, Any]) -> str:
    """Render the console HTML with a compact invoice/email walkthrough panel."""

    html = _render_base_console_html(payload)
    panel = _invoice_email_walkthrough_panel(_mapping(payload.get("first_usable_demo")))
    if not panel:
        return html
    return html.replace("</body>", f"{panel}\n</body>")


def _invoice_email_walkthrough_panel(first_demo: Mapping[str, Any]) -> str:
    walkthrough = _mapping(first_demo.get("invoice_email_walkthrough"))
    if not walkthrough:
        return ""
    effect = _mapping(walkthrough.get("effect_summary"))
    claim = _mapping(walkthrough.get("claim_summary"))
    approval = _mapping(walkthrough.get("approval_review_packet"))
    approval_effect = _mapping(approval.get("effect_summary"))
    state = _automation_state_summary(walkthrough=walkthrough, effect=effect, claim=claim)
    queue = _approval_queue_preview_summary(approval=approval, approval_effect=approval_effect)
    rows = (
        ("Walkthrough", walkthrough.get("walkthrough_id", "")),
        ("Draft Status", walkthrough.get("draft_status", "")),
        ("Draft Type", walkthrough.get("draft_type", "")),
        ("Approval Required Before Send", walkthrough.get("approval_required_before_send", False)),
        ("Approval Is Execution", walkthrough.get("approval_is_execution", False)),
        ("Approval Packet", approval.get("review_packet_id", "")),
        ("Approval Review State", approval.get("review_state", "")),
        ("Approval Risk Level", approval.get("risk_level", "")),
        ("Approval Scope", approval.get("approval_scope", "")),
        ("Approval Proposed Action Count", approval.get("proposed_action_count", 0)),
        ("Approval Enqueued", approval_effect.get("approval_enqueued", False)),
        ("Approval Packet Is Execution", approval_effect.get("approval_is_execution", False)),
        ("Approval Queue Preview", queue["queue_state"]),
        ("Approval Queue Decision", queue["decision_state"]),
        ("Approval Queue Executes Action", queue["executes_action"]),
        ("External Send Allowed", effect.get("external_send_allowed", False)),
        ("Provider Draft Creation Allowed", effect.get("provider_draft_creation_allowed", False)),
        ("Invoice Payment Allowed", effect.get("invoice_payment_allowed", False)),
        ("Memory Write Allowed", effect.get("memory_write_allowed", False)),
        ("Customer Readiness Claim Allowed", effect.get("customer_readiness_claim_allowed", False)),
        ("Draft Preview Is Send Authority", claim.get("draft_preview_is_send_authority", False)),
        ("Approval Review Is Execution", claim.get("approval_review_is_execution", False)),
    )
    body = "\n".join(
        "<tr>"
        f"<td>{escape(str(label))}</td>"
        f"<td>{escape(str(value))}</td>"
        "</tr>"
        for label, value in rows
    )
    return f"""
  <section>
    <h2>Invoice Email Draft Walkthrough</h2>
    <p><strong>User State:</strong> {escape(state["user_state"])}</p>
    <p><strong>Next Safe Step:</strong> {escape(state["next_safe_step"])}</p>
    <p><strong>Approval Prompt:</strong> {escape(state["approval_prompt"])}</p>
    <p><strong>Approval Queue:</strong> {escape(queue["user_state"])}</p>
    <table>
      <thead><tr><th>Signal</th><th>Status</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _automation_state_summary(
    *,
    walkthrough: Mapping[str, Any],
    effect: Mapping[str, Any],
    claim: Mapping[str, Any],
) -> dict[str, str]:
    approval_required = walkthrough.get("approval_required_before_send") is True
    external_effect_blocked = all(
        boundary is False
        for boundary in (
            effect.get("external_send_allowed", False),
            effect.get("provider_draft_creation_allowed", False),
            effect.get("invoice_payment_allowed", False),
            effect.get("memory_write_allowed", False),
            effect.get("customer_readiness_claim_allowed", False),
            claim.get("draft_preview_is_send_authority", False),
            claim.get("approval_review_is_execution", False),
        )
    )
    if approval_required and external_effect_blocked:
        return {
            "user_state": "Drafted for review",
            "next_safe_step": "Approve to send later",
            "approval_prompt": "No email will be sent, no provider draft will be created, and no invoice will be paid until approval is explicitly granted.",
        }
    return {
        "user_state": "Blocked",
        "next_safe_step": "Review effect boundary before continuing",
        "approval_prompt": "The walkthrough could not be compressed into a safe draft-only user state.",
    }


def _approval_queue_preview_summary(
    *,
    approval: Mapping[str, Any],
    approval_effect: Mapping[str, Any],
) -> dict[str, object]:
    if approval and approval_effect.get("approval_is_execution") is False:
        return {
            "user_state": "Waiting for operator approval",
            "queue_state": "requested",
            "decision_state": "pending",
            "executes_action": False,
        }
    return {
        "user_state": "Approval queue unavailable",
        "queue_state": "unavailable",
        "decision_state": "blocked",
        "executes_action": False,
    }


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
