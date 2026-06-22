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
    rows = (
        ("Walkthrough", walkthrough.get("walkthrough_id", "")),
        ("Draft Status", walkthrough.get("draft_status", "")),
        ("Draft Type", walkthrough.get("draft_type", "")),
        ("Approval Required Before Send", walkthrough.get("approval_required_before_send", False)),
        ("Approval Is Execution", walkthrough.get("approval_is_execution", False)),
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
    <table>
      <thead><tr><th>Signal</th><th>Status</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </section>"""


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
