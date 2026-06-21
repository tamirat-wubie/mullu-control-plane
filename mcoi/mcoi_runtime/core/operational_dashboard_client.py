"""Normal-user dashboard client projection.

Purpose: turn the Level 1 dashboard payload into a deterministic UI-ready
client view.
Governance scope: normal-user display only; proof, witness, gate-decision,
operator, and auditor details remain hidden.
Dependencies: dataclasses, typing, and runtime invariant helpers.
Invariants: no execution authority, no internal governance refs, no raw checks,
and no operator/auditor fields are exposed in the client view.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape, unescape
from typing import Any, Mapping, Sequence

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


HIDDEN_NORMAL_USER_DASHBOARD_FIELDS = {
    "auditor_details",
    "blocked_reasons",
    "boundary_witness_ref",
    "checks",
    "decision_ref",
    "operator_details",
    "proof_stamp_ref",
    "raw_decision",
    "review_reasons",
}

HIDDEN_NORMAL_USER_REF_PREFIXES = ("gate-decision-", "proof-", "witness-")
NORMAL_USER_SAFETY_LABEL = "Safety status"
NORMAL_USER_ACTION_LOCK_LABEL = "Actions locked"
NORMAL_USER_EVIDENCE_LABELS = frozenset({"Evidence saved", "No evidence yet", "Evidence unavailable"})
ACTIVE_CONTENT_ATTRIBUTE_PATTERN = re.compile(r"[\s/]+on[a-z][a-z0-9_-]*\s*=", re.IGNORECASE)
ACTIVE_CONTENT_TAG_PATTERN = re.compile(
    r"<\s*(?:iframe|object|embed|form|meta|base|link)\b",
    re.IGNORECASE,
)
ACTIVE_RESOURCE_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+(?:href|src|srcdoc|action|formaction|poster|xlink:href)\s*=",
    re.IGNORECASE,
)
ACTIVE_STYLE_PATTERN = re.compile(
    r"<\s*style\b|[\s/]+style\s*=|@import\b|url\s*\(",
    re.IGNORECASE,
)
UNSUPPORTED_BODY_TAG_PATTERN = re.compile(
    r"<\s*/?\s*(?:a|area|audio|canvas|details|dialog|img|input|map|math|menu|option|picture|select|slot|source|summary|svg|template|textarea|track|video)\b",
    re.IGNORECASE,
)
BUTTON_TAG_PATTERN = re.compile(r"<\s*button\b(?P<attributes>[^>]*)>", re.IGNORECASE)
BUTTON_DISABLED_ATTRIBUTE_PATTERN = re.compile(r"(?:^|[\s/])disabled(?:\s|=|$)", re.IGNORECASE)
BUTTON_ARIA_DISABLED_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+aria-disabled\s*=\s*([\"']?)true\1",
    re.IGNORECASE,
)
BUTTON_TYPE_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+type\s*=\s*([\"']?)button\1",
    re.IGNORECASE,
)
INTERACTIVE_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+(?:accesskey|autofocus|contenteditable|popover|popovertarget|tabindex)(?:\s*=|(?=[\s>/]))",
    re.IGNORECASE,
)
INTERACTIVE_ROLE_PATTERN = re.compile(
    r"[\s/]+role\s*=\s*(?:[\"'][^\"'>]*\b(?:alertdialog|button|checkbox|combobox|dialog|link|listbox|menu|menuitem|option|radio|searchbox|slider|spinbutton|switch|tab|textbox|tree|treeitem)\b[^\"'>]*[\"']|[^\s>]*\b(?:alertdialog|button|checkbox|combobox|dialog|link|listbox|menu|menuitem|option|radio|searchbox|slider|spinbutton|switch|tab|textbox|tree|treeitem)\b[^\s>]*)",
    re.IGNORECASE,
)
INTERACTIVE_ARIA_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+aria-(?:activedescendant|checked|controls|expanded|haspopup|modal|pressed|selected)\s*=",
    re.IGNORECASE,
)
PROTECTED_SHELL_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+data-(?:execution-allowed|proof-hidden|visibility)\s*=",
    re.IGNORECASE,
)
HTML_COMMENT_PATTERN = re.compile(r"<!--|-->")
HIDDEN_CONTENT_ATTRIBUTE_PATTERN = re.compile(
    r"[\s/]+(?:aria-hidden|hidden|inert)(?:\s*=|(?=[\s>/]))",
    re.IGNORECASE,
)
BODY_TAG_NAME_PATTERN = re.compile(r"<\s*/?\s*([a-z][a-z0-9:-]*)\b", re.IGNORECASE)
ALLOWED_BODY_TAG_NAMES = frozenset(
    {
        "article",
        "button",
        "div",
        "h1",
        "h2",
        "h3",
        "li",
        "p",
        "section",
        "span",
        "strong",
        "ul",
    }
)


@dataclass(frozen=True)
class NormalUserDashboardActionCard:
    """UI-ready card for one normal-user action summary."""

    action_ref: str
    title: str
    status_label: str
    message: str
    risk: str
    approval_needed: bool
    evidence_saved: bool
    next_step: str
    primary_action: str
    secondary_actions: tuple[str, ...]
    audit_details_available: bool
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        _reject_internal_ref(self.action_ref, "action_ref")
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("normal user action card cannot allow execution")
        if self.status_label not in {"Ready", "Needs approval", "Blocked"}:
            raise RuntimeCoreInvariantError("normal user action card status is unsupported")
        for field_name, field_value in {
            "action_ref": self.action_ref,
            "title": self.title,
            "status_label": self.status_label,
            "message": self.message,
            "risk": self.risk,
            "next_step": self.next_step,
            "primary_action": self.primary_action,
        }.items():
            _require_trimmed_text(field_value, field_name)
        for action in self.secondary_actions:
            _require_trimmed_text(action, "secondary_action")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible action card."""

        return {
            "action_ref": self.action_ref,
            "title": self.title,
            "status_label": self.status_label,
            "message": self.message,
            "risk": self.risk,
            "approval_needed": self.approval_needed,
            "evidence_saved": self.evidence_saved,
            "next_step": self.next_step,
            "primary_action": self.primary_action,
            "secondary_actions": list(self.secondary_actions),
            "audit_details_available": self.audit_details_available,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class NormalUserDashboardWorkflowCard:
    """UI-ready card for one normal-user workflow summary."""

    workflow_ref: str
    workflow: str
    label: str
    title: str
    status_label: str
    message: str
    next_step: str
    ready_count: int
    review_count: int
    blocked_count: int
    action_refs: tuple[str, ...]
    primary_action: str
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        _reject_internal_ref(self.workflow_ref, "workflow_ref")
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("normal user workflow card cannot allow execution")
        if self.status_label not in {"Ready", "Needs approval", "Blocked"}:
            raise RuntimeCoreInvariantError("normal user workflow card status is unsupported")
        if min(self.ready_count, self.review_count, self.blocked_count) < 0:
            raise RuntimeCoreInvariantError("normal user workflow counts cannot be negative")
        if self.ready_count + self.review_count + self.blocked_count != len(self.action_refs):
            raise RuntimeCoreInvariantError("normal user workflow counts must match action refs")
        for field_name, field_value in {
            "workflow_ref": self.workflow_ref,
            "workflow": self.workflow,
            "label": self.label,
            "title": self.title,
            "status_label": self.status_label,
            "message": self.message,
            "next_step": self.next_step,
            "primary_action": self.primary_action,
        }.items():
            _require_trimmed_text(field_value, field_name)
        for action_ref in self.action_refs:
            _reject_internal_ref(action_ref, "workflow action_ref")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible workflow card."""

        return {
            "workflow_ref": self.workflow_ref,
            "workflow": self.workflow,
            "label": self.label,
            "title": self.title,
            "status_label": self.status_label,
            "message": self.message,
            "next_step": self.next_step,
            "ready_count": self.ready_count,
            "review_count": self.review_count,
            "blocked_count": self.blocked_count,
            "action_refs": list(self.action_refs),
            "primary_action": self.primary_action,
            "execution_allowed": self.execution_allowed,
        }


@dataclass(frozen=True)
class NormalUserDashboardClientView:
    """UI-ready normal-user dashboard view."""

    view_ref: str
    visibility_level: str
    title: str
    status_label: str
    message: str
    count_summary: str
    next_action: str
    command_guidance: tuple[str, ...]
    action_cards: tuple[NormalUserDashboardActionCard, ...]
    workflow_cards: tuple[NormalUserDashboardWorkflowCard, ...]
    audit_details_visible: bool
    receipts_visible: bool
    proof_details_hidden: bool
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.visibility_level != "normal_user":
            raise RuntimeCoreInvariantError("normal user dashboard client view must stay normal_user")
        if self.audit_details_visible or self.receipts_visible or not self.proof_details_hidden:
            raise RuntimeCoreInvariantError("normal user dashboard client view cannot expose proof details")
        if self.execution_allowed:
            raise RuntimeCoreInvariantError("normal user dashboard client view cannot allow execution")
        if self.status_label not in {"Ready", "Needs approval", "Blocked"}:
            raise RuntimeCoreInvariantError("normal user dashboard client view status is unsupported")
        for field_name, field_value in {
            "view_ref": self.view_ref,
            "visibility_level": self.visibility_level,
            "title": self.title,
            "status_label": self.status_label,
            "message": self.message,
            "count_summary": self.count_summary,
            "next_action": self.next_action,
        }.items():
            _require_trimmed_text(field_value, field_name)
        for command in self.command_guidance:
            _require_trimmed_text(command, "command_guidance")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible client view."""

        return {
            "view_ref": self.view_ref,
            "visibility_level": self.visibility_level,
            "title": self.title,
            "status_label": self.status_label,
            "message": self.message,
            "count_summary": self.count_summary,
            "next_action": self.next_action,
            "command_guidance": list(self.command_guidance),
            "action_cards": [card.to_dict() for card in self.action_cards],
            "workflow_cards": [card.to_dict() for card in self.workflow_cards],
            "audit_details_visible": self.audit_details_visible,
            "receipts_visible": self.receipts_visible,
            "proof_details_hidden": self.proof_details_hidden,
            "execution_allowed": self.execution_allowed,
        }


def build_normal_user_dashboard_client_view(
    dashboard_payload: Mapping[str, Any],
    *,
    contract: Mapping[str, Any] | None = None,
) -> NormalUserDashboardClientView:
    """Build a UI-ready view from a normal-user dashboard payload."""

    _validate_contract(contract)
    _reject_normal_user_payload_leaks(dashboard_payload)
    if _required_text(dashboard_payload, "visibility_level") != "normal_user":
        raise RuntimeCoreInvariantError("normal user dashboard payload must be normal_user")
    if _required_bool(dashboard_payload, "execution_allowed"):
        raise RuntimeCoreInvariantError("normal user dashboard payload cannot allow execution")
    audit_details_visible = _required_bool(dashboard_payload, "audit_details_visible")
    receipts_visible = _required_bool(dashboard_payload, "receipts_visible")
    proof_details_hidden = _required_bool(dashboard_payload, "proof_details_hidden")
    if audit_details_visible or receipts_visible or not proof_details_hidden:
        raise RuntimeCoreInvariantError("normal user dashboard payload cannot expose proof details")

    home = _required_mapping(dashboard_payload, "home")
    action_cards = tuple(
        _action_card(summary)
        for summary in _mapping_sequence(dashboard_payload.get("simple_action_summaries"), "simple_action_summaries")
    )
    workflow_cards = tuple(
        _workflow_card(summary)
        for summary in _mapping_sequence(
            dashboard_payload.get("simple_workflow_summaries"),
            "simple_workflow_summaries",
        )
    )
    return NormalUserDashboardClientView(
        view_ref=f"normal-user-dashboard-client:{_required_text(home, 'status_label')}",
        visibility_level="normal_user",
        title=_required_text(home, "title"),
        status_label=_required_text(home, "status_label"),
        message=_required_text(home, "message"),
        count_summary=_required_text(home, "count_summary"),
        next_action=_required_text(home, "next_action"),
        command_guidance=_text_tuple(home.get("command_guidance"), "command_guidance"),
        action_cards=action_cards,
        workflow_cards=workflow_cards,
        audit_details_visible=audit_details_visible,
        receipts_visible=receipts_visible,
        proof_details_hidden=proof_details_hidden,
    )


def render_normal_user_dashboard_html(view: NormalUserDashboardClientView) -> str:
    """Render a read-only HTML page for the normal-user dashboard view."""

    _reject_normal_user_payload_leaks(view.to_dict())
    action_cards = "\n".join(_render_action_card(card) for card in view.action_cards)
    workflow_cards = "\n".join(_render_workflow_card(card) for card in view.workflow_cards)
    command_items = "\n".join(f"<li>{escape(command)}</li>" for command in view.command_guidance)
    empty_action_cards = '<p class="empty">No actions waiting.</p>'
    empty_workflow_cards = '<p class="empty">No workflows waiting.</p>'
    return render_normal_user_dashboard_shell(
        document_title=f"Mullu Dashboard - {view.status_label}",
        body_lines=(
            '    <section class="summary" aria-labelledby="dashboard-title">',
            f'      <p class="status">{escape(view.status_label)}</p>',
            f'      <h1 id="dashboard-title">{escape(view.title)}</h1>',
            f'      <p class="message">{escape(view.message)}</p>',
            '      <div class="metrics" aria-label="Workflow counts">',
            f'        <span>{escape(view.count_summary)}</span>',
            "      </div>",
            f'      <p class="next">{escape(view.next_action)}</p>',
            "    </section>",
            '    <section class="grid" aria-label="Dashboard cards">',
            '      <section class="panel" aria-labelledby="actions-title">',
            '        <h2 id="actions-title">Actions</h2>',
            f"        {action_cards or empty_action_cards}",
            "      </section>",
            '      <section class="panel" aria-labelledby="workflows-title">',
            '        <h2 id="workflows-title">Workflows</h2>',
            f"        {workflow_cards or empty_workflow_cards}",
            "      </section>",
            '      <section class="panel compact" aria-labelledby="commands-title">',
            '        <h2 id="commands-title">Commands</h2>',
            f"        <ul>{command_items}</ul>",
            "      </section>",
            "    </section>",
        ),
        evidence_label="Evidence saved",
        include_dashboard_css=True,
    )


def render_normal_user_dashboard_shell(
    *,
    document_title: str,
    body_lines: Sequence[str],
    evidence_label: str,
    include_dashboard_css: bool = False,
) -> str:
    """Render the shared Level 1 dashboard page shell."""

    title = _require_trimmed_text(document_title, "document_title")
    _reject_normal_user_html_fragment_leaks(title, "document_title")
    evidence = _require_trimmed_text(evidence_label, "evidence_label")
    if evidence not in NORMAL_USER_EVIDENCE_LABELS:
        raise RuntimeCoreInvariantError("normal user dashboard evidence label is unsupported")
    for line in body_lines:
        body_fragment = _require_html_body_fragment(line)
        _reject_normal_user_html_fragment_leaks(body_fragment, "body fragment")

    head_lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f"  <title>{escape(title)}</title>",
    ]
    if include_dashboard_css:
        head_lines.extend(("  <style>", _dashboard_css(), "  </style>"))
    head_lines.extend(
        (
            "</head>",
            "<body>",
            '  <main class="shell" data-visibility="normal_user">',
        )
    )
    return "\n".join(
        (
            *head_lines,
            *body_lines,
            _normal_user_safety_footer(evidence),
            "  </main>",
            "</body>",
            "</html>",
        )
    )


def _normal_user_safety_footer(evidence_label: str) -> str:
    return "\n".join(
        (
            f'    <footer class="guard" aria-label="{NORMAL_USER_SAFETY_LABEL}">',
            f'      <span data-proof-hidden="true">{escape(evidence_label)}</span>',
            f'      <span data-execution-allowed="false">{NORMAL_USER_ACTION_LOCK_LABEL}</span>',
            "    </footer>",
        )
    )


def _require_html_body_fragment(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError("body fragment must be non-empty text")
    return value


def _reject_normal_user_html_fragment_leaks(value: str, field_name: str) -> None:
    for scan_value in _normal_user_html_scan_values(value):
        lowered_value = scan_value.lower()
        if HTML_COMMENT_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose hidden content")
        if "<script" in lowered_value or "</script" in lowered_value:
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if "javascript:" in lowered_value:
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if ACTIVE_CONTENT_ATTRIBUTE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if ACTIVE_CONTENT_TAG_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if ACTIVE_RESOURCE_ATTRIBUTE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if ACTIVE_STYLE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if UNSUPPORTED_BODY_TAG_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if INTERACTIVE_ATTRIBUTE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if INTERACTIVE_ROLE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if INTERACTIVE_ARIA_ATTRIBUTE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        if PROTECTED_SHELL_ATTRIBUTE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot override shell markers")
        if HIDDEN_CONTENT_ATTRIBUTE_PATTERN.search(scan_value):
            raise RuntimeCoreInvariantError(f"{field_name} cannot expose hidden content")
        if field_name == "body fragment":
            unsupported_tag_names = sorted(
                {
                    match.group(1).lower()
                    for match in BODY_TAG_NAME_PATTERN.finditer(scan_value)
                    if match.group(1).lower() not in ALLOWED_BODY_TAG_NAMES
                }
            )
            if unsupported_tag_names:
                raise RuntimeCoreInvariantError(
                    f"{field_name} cannot expose unsupported markup: {', '.join(unsupported_tag_names)}"
                )
        for match in BUTTON_TAG_PATTERN.finditer(scan_value):
            attributes = match.group("attributes")
            if (
                not BUTTON_DISABLED_ATTRIBUTE_PATTERN.search(attributes)
                or not BUTTON_ARIA_DISABLED_ATTRIBUTE_PATTERN.search(attributes)
                or not BUTTON_TYPE_ATTRIBUTE_PATTERN.search(attributes)
            ):
                raise RuntimeCoreInvariantError(f"{field_name} cannot expose active content")
        leaked_fields = sorted(field for field in HIDDEN_NORMAL_USER_DASHBOARD_FIELDS if field in lowered_value)
        if leaked_fields:
            raise RuntimeCoreInvariantError(
                f"{field_name} cannot expose internal fields: {', '.join(leaked_fields)}"
            )
        for prefix in HIDDEN_NORMAL_USER_REF_PREFIXES:
            if prefix in lowered_value:
                raise RuntimeCoreInvariantError(f"{field_name} cannot expose internal governance refs")


def _normal_user_html_scan_values(value: str) -> tuple[str, ...]:
    decoded_value = unescape(value)
    if decoded_value == value:
        return (value,)
    return (value, decoded_value)


def _action_card(summary: Mapping[str, Any]) -> NormalUserDashboardActionCard:
    choices = _text_tuple(summary.get("choices"), "choices")
    primary_action = _primary_action(_required_text(summary, "status_label"))
    secondary_actions = tuple(choice for choice in choices if choice != primary_action)
    return NormalUserDashboardActionCard(
        action_ref=_required_text(summary, "action_ref"),
        title=_required_text(summary, "title"),
        status_label=_required_text(summary, "status_label"),
        message=_required_text(summary, "message"),
        risk=_required_text(summary, "risk"),
        approval_needed=_required_bool(summary, "approval_needed"),
        evidence_saved=_required_bool(summary, "evidence_saved"),
        next_step=_required_text(summary, "next_step"),
        primary_action=primary_action,
        secondary_actions=secondary_actions,
        audit_details_available=_required_bool(summary, "audit_details_available"),
        execution_allowed=_required_bool(summary, "execution_allowed"),
    )


def _render_action_card(card: NormalUserDashboardActionCard) -> str:
    secondary_buttons = "\n".join(
        _disabled_button(action, class_name="secondary")
        for action in card.secondary_actions
        if action != "View audit details"
    )
    audit_button = (
        _disabled_button("Audit details", class_name="ghost")
        if card.audit_details_available
        else ""
    )
    return "\n".join(
        (
            f'<article class="card {escape(_status_class(card.status_label))}" data-ref="{escape(card.action_ref)}">',
            f'  <div class="card-head"><span>{escape(card.status_label)}</span><strong>{escape(card.risk)}</strong></div>',
            f"  <h3>{escape(card.title)}</h3>",
            f"  <p>{escape(card.message)}</p>",
            f'  <p class="step">{escape(card.next_step)}</p>',
            '  <div class="actions">',
            f"    {_disabled_button(card.primary_action, class_name='primary')}",
            f"    {secondary_buttons}",
            f"    {audit_button}",
            "  </div>",
            "</article>",
        )
    )


def _render_workflow_card(card: NormalUserDashboardWorkflowCard) -> str:
    return "\n".join(
        (
            f'<article class="card {escape(_status_class(card.status_label))}" data-ref="{escape(card.workflow_ref)}">',
            f'  <div class="card-head"><span>{escape(card.status_label)}</span><strong>{escape(card.label)}</strong></div>',
            f"  <h3>{escape(card.title)}</h3>",
            f"  <p>{escape(card.message)}</p>",
            '  <div class="counts">',
            f"    <span>{card.ready_count} ready</span>",
            f"    <span>{card.review_count} review</span>",
            f"    <span>{card.blocked_count} blocked</span>",
            "  </div>",
            f'  <p class="step">{escape(card.next_step)}</p>',
            '  <div class="actions">',
            f"    {_disabled_button(card.primary_action, class_name='primary')}",
            "  </div>",
            "</article>",
        )
    )


def _disabled_button(label: str, *, class_name: str) -> str:
    return (
        f'<button class="{escape(class_name)}" type="button" disabled '
        f'aria-disabled="true">{escape(label)}</button>'
    )


def _status_class(status_label: str) -> str:
    if status_label == "Blocked":
        return "blocked"
    if status_label == "Needs approval":
        return "review"
    return "ready"


def _dashboard_css() -> str:
    return """
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --ink: #17202a;
      --muted: #5d6673;
      --line: #d9dee6;
      --panel: #ffffff;
      --ready: #13795b;
      --review: #8a5a00;
      --blocked: #b42318;
      --accent: #2457a6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 15px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell {
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0;
    }
    .summary {
      padding: 24px 0 22px;
      border-bottom: 1px solid var(--line);
    }
    .status {
      margin: 0 0 8px;
      color: var(--accent);
      font-weight: 700;
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 0;
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 { margin-bottom: 8px; font-size: 32px; line-height: 1.15; letter-spacing: 0; }
    h2 { margin-bottom: 14px; font-size: 18px; letter-spacing: 0; }
    h3 { margin-bottom: 8px; font-size: 17px; letter-spacing: 0; }
    .message, .next, .step, .empty { color: var(--muted); }
    .metrics {
      display: inline-flex;
      min-height: 34px;
      align-items: center;
      margin: 8px 0 14px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      font-weight: 650;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 18px;
      padding: 22px 0;
    }
    .panel {
      min-width: 0;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    .panel.compact { grid-column: 1 / -1; }
    .panel ul {
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
    }
    .card {
      padding: 14px 0;
      border-top: 1px solid var(--line);
    }
    .card:first-of-type { border-top: 0; padding-top: 0; }
    .card-head, .counts, .actions, .guard {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }
    .card-head {
      justify-content: space-between;
      margin-bottom: 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .card.ready .card-head span { color: var(--ready); }
    .card.review .card-head span { color: var(--review); }
    .card.blocked .card-head span { color: var(--blocked); }
    .counts span, .guard span {
      min-height: 28px;
      padding: 4px 8px;
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--muted);
      background: #fbfcfd;
    }
    button {
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 12px;
      font: inherit;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.secondary { background: #eef2f7; color: var(--ink); }
    button.ghost { background: #fff; color: var(--muted); }
    button:disabled { opacity: .72; cursor: not-allowed; }
    .guard {
      justify-content: flex-end;
      padding-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    @media (max-width: 760px) {
      .shell { width: min(100% - 20px, 1120px); padding: 18px 0; }
      h1 { font-size: 26px; }
      .grid { grid-template-columns: 1fr; }
      .panel.compact { grid-column: auto; }
      .actions button { flex: 1 1 120px; }
    }
    """


def _workflow_card(summary: Mapping[str, Any]) -> NormalUserDashboardWorkflowCard:
    title = _required_text(summary, "title")
    return NormalUserDashboardWorkflowCard(
        workflow_ref=_required_text(summary, "workflow_ref"),
        workflow=_required_text(summary, "workflow"),
        label=_required_text(summary, "label"),
        title=title,
        status_label=title,
        message=_required_text(summary, "message"),
        next_step=_required_text(summary, "next_step"),
        ready_count=_required_int(summary, "ready_count"),
        review_count=_required_int(summary, "review_count"),
        blocked_count=_required_int(summary, "blocked_count"),
        action_refs=_text_tuple(summary.get("action_refs"), "action_refs"),
        primary_action=_primary_action(title),
        execution_allowed=_required_bool(summary, "execution_allowed"),
    )


def _primary_action(status_label: str) -> str:
    if status_label == "Blocked":
        return "Fix"
    if status_label == "Needs approval":
        return "Review"
    if status_label == "Ready":
        return "Start"
    raise RuntimeCoreInvariantError("normal user status label is unsupported")


def _validate_contract(contract: Mapping[str, Any] | None) -> None:
    if contract is None:
        return
    if _required_text(contract, "contract_ref") != "operational_dashboard.normal_user_dashboard.v1":
        raise RuntimeCoreInvariantError("normal user dashboard contract_ref is unsupported")
    if _required_text(contract, "visibility_level") != "normal_user":
        raise RuntimeCoreInvariantError("normal user dashboard contract visibility is unsupported")
    route = _required_mapping(contract, "route")
    if (
        _required_text(route, "method") != "GET"
        or _required_text(route, "path") != "/api/v1/dashboard/simple"
        or _required_text(route, "payload_key") != "dashboard"
    ):
        raise RuntimeCoreInvariantError("normal user dashboard contract route is unsupported")
    page_route = _required_mapping(contract, "page_route")
    if (
        _required_text(page_route, "method") != "GET"
        or _required_text(page_route, "path") != "/api/v1/dashboard/simple/page"
        or _required_text(page_route, "content_type") != "text/html"
    ):
        raise RuntimeCoreInvariantError("normal user dashboard contract page_route is unsupported")
    hidden_fields = set(_text_tuple(contract.get("hidden_fields"), "hidden_fields"))
    missing_fields = HIDDEN_NORMAL_USER_DASHBOARD_FIELDS.difference(hidden_fields)
    if missing_fields:
        raise RuntimeCoreInvariantError("normal user dashboard contract is missing hidden fields")
    hidden_ref_prefixes = _text_tuple(contract.get("hidden_ref_prefixes"), "hidden_ref_prefixes")
    for prefix in HIDDEN_NORMAL_USER_REF_PREFIXES:
        if prefix not in hidden_ref_prefixes:
            raise RuntimeCoreInvariantError("normal user dashboard contract is missing hidden ref prefixes")


def _reject_normal_user_payload_leaks(value: Any) -> None:
    if isinstance(value, Mapping):
        leaked_fields = sorted(str(key) for key in value if key in HIDDEN_NORMAL_USER_DASHBOARD_FIELDS)
        if leaked_fields:
            raise RuntimeCoreInvariantError(
                f"normal user dashboard client cannot expose internal fields: {', '.join(leaked_fields)}"
            )
        for nested_value in value.values():
            _reject_normal_user_payload_leaks(nested_value)
        return
    if isinstance(value, list | tuple):
        for nested_value in value:
            _reject_normal_user_payload_leaks(nested_value)
        return
    if isinstance(value, str):
        _reject_internal_ref(value, "normal user dashboard value")


def _reject_internal_ref(value: str, field_name: str) -> None:
    if value.startswith(HIDDEN_NORMAL_USER_REF_PREFIXES):
        raise RuntimeCoreInvariantError(f"{field_name} cannot expose internal governance refs")


def _required_mapping(record: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    value = record.get(field_name)
    if not isinstance(value, Mapping):
        raise RuntimeCoreInvariantError(f"{field_name} must be a mapping")
    return value


def _mapping_sequence(value: Any, field_name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeCoreInvariantError(f"{field_name} must be a sequence")
    summaries: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise RuntimeCoreInvariantError(f"{field_name} entries must be mappings")
        summaries.append(item)
    return tuple(summaries)


def _text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise RuntimeCoreInvariantError(f"{field_name} must be a text sequence")
    return tuple(_require_trimmed_text(item, field_name) for item in value)


def _required_text(record: Mapping[str, Any], field_name: str) -> str:
    return _require_trimmed_text(record.get(field_name), field_name)


def _require_trimmed_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeCoreInvariantError(f"{field_name} must be non-empty text")
    if value.strip() != value:
        raise RuntimeCoreInvariantError(f"{field_name} must be trimmed")
    return value


def _required_bool(record: Mapping[str, Any], field_name: str) -> bool:
    value = record.get(field_name)
    if not isinstance(value, bool):
        raise RuntimeCoreInvariantError(f"{field_name} must be a boolean")
    return value


def _required_int(record: Mapping[str, Any], field_name: str) -> int:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeCoreInvariantError(f"{field_name} must be an integer")
    return value
