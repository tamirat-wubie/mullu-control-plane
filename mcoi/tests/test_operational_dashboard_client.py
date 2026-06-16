"""Tests for the normal-user operational dashboard client view.

Purpose: verify Level 1 dashboard payloads become UI-ready client cards without
exposing proof, witness, gate-decision, operator, or auditor internals.
Governance scope: normal-user display projection only; no execution authority.
Dependencies: operational dashboard API, client renderer, and dashboard
projection dataclasses.
Invariants: client views hide internal governance refs, reject detail leaks,
and preserve simple status/action affordances.
"""

from __future__ import annotations

import copy

import pytest

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.operational_dashboard_client import (
    build_normal_user_dashboard_client_view,
    render_normal_user_dashboard_html,
    render_normal_user_dashboard_shell,
)
from mcoi_runtime.core.operational_dashboard_intelligence import (
    DashboardSimpleActionSummary,
    DashboardSimpleHomeSummary,
    DashboardSimpleStartGuideSummary,
    DashboardSimpleWorkflowSummary,
    OperationalDashboardState,
    WorkflowHealth,
)


def _dashboard_runtime() -> OperationalDashboardRuntime:
    state = OperationalDashboardState(
        dashboard_id="dashboard-client-test",
        projection_id="projection-client-test",
        active_project_count=1,
        ready_action_ids=(),
        blocked_action_ids=(),
        open_blocker_ids=(),
        open_conflict_ids=(),
        repair_ids=(),
        stale_high_impact_claim_ids=(),
        high_intensity_box_ids=(),
        constructive_delta_ids=(),
        fracture_delta_ids=(),
        memory_confidence_trend=1.0,
        workflow_health=WorkflowHealth.READY,
        execution_readiness="no_action_candidate_ready",
        interrogation_task_ids=(),
        simple_action_summaries=(
            DashboardSimpleActionSummary(
                action_ref="dashboard-simple-action-review",
                outcome="needs_review",
                status_label="Needs approval",
                message="Draft ready.",
                risk="External message",
                approval_needed=True,
                evidence_saved=True,
                next_step="Approve or edit the draft.",
                choices=("Approve", "Edit", "Cancel", "View audit details"),
                audit_details_available=True,
                audit_details_visible=False,
                receipts_visible=False,
                proof_details_hidden=True,
            ),
        ),
        simple_workflow_summaries=(
            DashboardSimpleWorkflowSummary(
                workflow_ref="dashboard-simple-workflow-support-notice",
                workflow="support_notice",
                label="Support notice",
                outcome="needs_review",
                title="Needs approval",
                message="Draft ready.",
                next_step="Approve or edit the draft.",
                ready_count=1,
                review_count=1,
                blocked_count=0,
                action_refs=("dashboard-simple-action-ready", "dashboard-simple-action-review"),
            ),
        ),
        simple_start_guide=DashboardSimpleStartGuideSummary(
            title="Start with simple mode",
            message="Choose a task and review the result.",
            recommended_commands=("mullu menu", "mullu workflows"),
            outcomes=("Ready", "Needs approval", "Blocked"),
        ),
        simple_home_summary=DashboardSimpleHomeSummary(
            title="Needs approval",
            message="Some workflows need approval before users continue.",
            primary_command="mullu menu",
            ready_workflow_count=0,
            review_workflow_count=1,
            blocked_workflow_count=0,
            status_label="Needs approval",
            count_summary="0 ready, 1 need approval, 0 blocked",
            next_action="Review the workflows that need approval before continuing.",
            command_guidance=("mullu menu", "mullu workflows"),
        ),
        simple_review_action_refs=("dashboard-simple-action-review",),
        simple_review_workflow_refs=("dashboard-simple-workflow-support-notice",),
    )
    return OperationalDashboardRuntime.from_state(state)


def _simple_payload_and_contract() -> tuple[dict[str, object], dict[str, object]]:
    runtime = _dashboard_runtime()
    dashboard = runtime.simple_state().to_dict()["payload"]["dashboard"]
    contract = runtime.simple_state_contract().to_dict()["payload"]["contract"]
    assert isinstance(dashboard, dict)
    assert isinstance(contract, dict)
    return dashboard, contract


def test_build_normal_user_dashboard_client_view_projects_ui_cards() -> None:
    dashboard, contract = _simple_payload_and_contract()
    view = build_normal_user_dashboard_client_view(dashboard, contract=contract)
    payload = view.to_dict()

    assert payload["visibility_level"] == "normal_user"
    assert payload["title"] == "Needs approval"
    assert payload["status_label"] == "Needs approval"
    assert payload["count_summary"] == "0 ready, 1 need approval, 0 blocked"
    assert payload["command_guidance"] == ["mullu menu", "mullu workflows"]
    assert payload["audit_details_visible"] is False
    assert payload["receipts_visible"] is False
    assert payload["proof_details_hidden"] is True
    assert payload["execution_allowed"] is False
    assert payload["action_cards"][0]["primary_action"] == "Review"
    assert payload["action_cards"][0]["audit_details_available"] is True
    assert payload["workflow_cards"][0]["primary_action"] == "Review"
    assert payload["workflow_cards"][0]["action_refs"] == [
        "dashboard-simple-action-ready",
        "dashboard-simple-action-review",
    ]
    assert "decision_ref" not in payload["action_cards"][0]
    assert "operator_details" not in payload["action_cards"][0]
    assert "proof_stamp_ref" not in payload["action_cards"][0]


def test_operational_dashboard_runtime_returns_client_view_envelope() -> None:
    envelope = _dashboard_runtime().simple_client_view().to_dict()
    client_view = envelope["payload"]["client_view"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert client_view["visibility_level"] == "normal_user"
    assert client_view["action_cards"][0]["action_ref"] == "dashboard-simple-action-review"
    assert client_view["workflow_cards"][0]["workflow_ref"] == "dashboard-simple-workflow-support-notice"
    assert client_view["execution_allowed"] is False


def test_render_normal_user_dashboard_html_keeps_level_one_boundary() -> None:
    dashboard, contract = _simple_payload_and_contract()
    view = build_normal_user_dashboard_client_view(dashboard, contract=contract)
    html = render_normal_user_dashboard_html(view)

    assert "<!doctype html>" in html
    assert 'data-visibility="normal_user"' in html
    assert "Needs approval" in html
    assert "Draft ready." in html
    assert "Support notice" in html
    assert "mullu menu" in html
    assert 'aria-label="Safety status"' in html
    assert "Actions locked" in html
    assert "disabled aria-disabled=\"true\"" in html
    assert 'data-execution-allowed="false"' in html
    assert 'data-proof-hidden="true"' in html
    assert "Governance status" not in html
    assert "Execution disabled" not in html
    assert "Evidence hidden" not in html
    assert "decision_ref" not in html
    assert "operator_details" not in html
    assert "proof_stamp_ref" not in html
    assert "gate-decision-" not in html
    assert "proof-secret" not in html
    assert "witness-" not in html


def test_operational_dashboard_runtime_returns_client_page_html() -> None:
    envelope = _dashboard_runtime().simple_client_page().to_dict()
    html = envelope["payload"]["html"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert '<main class="shell" data-visibility="normal_user">' in html
    assert "<h1 id=\"dashboard-title\">Needs approval</h1>" in html
    assert 'aria-label="Safety status"' in html
    assert "Evidence saved" in html
    assert "Actions locked" in html
    assert "dashboard-simple-workflow-support-notice" in html
    assert "proof_stamp_ref" not in html


def test_operational_dashboard_runtime_returns_empty_client_page_shell() -> None:
    state = OperationalDashboardState(
        dashboard_id="dashboard-empty-test",
        projection_id="projection-empty-test",
        active_project_count=0,
        ready_action_ids=(),
        blocked_action_ids=(),
        open_blocker_ids=(),
        open_conflict_ids=(),
        repair_ids=(),
        stale_high_impact_claim_ids=(),
        high_intensity_box_ids=(),
        constructive_delta_ids=(),
        fracture_delta_ids=(),
        memory_confidence_trend=1.0,
        workflow_health=WorkflowHealth.READY,
        execution_readiness="no_action_candidate_ready",
        interrogation_task_ids=(),
    )
    envelope = OperationalDashboardRuntime.from_state(state).simple_client_page().to_dict()
    html = envelope["payload"]["html"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "empty"
    assert '<main class="shell" data-visibility="normal_user">' in html
    assert "No dashboard items are waiting." in html
    assert 'aria-label="Safety status"' in html
    assert "No evidence yet" in html
    assert "Actions locked" in html
    assert 'data-proof-hidden="true"' in html
    assert 'data-execution-allowed="false"' in html
    assert "Governance status" not in html
    assert "Execution disabled" not in html
    assert "Evidence hidden" not in html
    assert "proof_stamp_ref" not in html
    assert "gate-decision-" not in html


def test_render_normal_user_dashboard_shell_escapes_title_and_preserves_markers() -> None:
    html = render_normal_user_dashboard_shell(
        document_title="Mullu Dashboard - <Ready>",
        body_lines=("    <h1>Ready</h1>", "    <p>Draft created.</p>"),
        evidence_label="Evidence saved",
    )

    assert "<title>Mullu Dashboard - &lt;Ready&gt;</title>" in html
    assert '<main class="shell" data-visibility="normal_user">' in html
    assert 'aria-label="Safety status"' in html
    assert 'data-proof-hidden="true">Evidence saved</span>' in html
    assert 'data-execution-allowed="false">Actions locked</span>' in html
    assert "Draft created." in html
    assert "Governance status" not in html
    assert "Execution disabled" not in html
    assert "Evidence hidden" not in html


def test_render_normal_user_dashboard_shell_rejects_unknown_evidence_label() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="evidence label is unsupported"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <h1>Ready</h1>",),
            evidence_label="Proof stored",
        )


def test_render_normal_user_dashboard_shell_rejects_empty_body_fragment() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="body fragment"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("   ",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_internal_title_leak() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="internal fields"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - proof_stamp_ref",
            body_lines=("    <h1>Ready</h1>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_internal_body_ref_leak() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="internal governance refs"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <article data-ref="gate-decision-secret">Ready</article>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_entity_encoded_internal_field() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="internal fields"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <p>proof&#95;stamp&#95;ref</p>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_entity_encoded_internal_ref() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="internal governance refs"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <p>gate&#45;decision&#45;secret</p>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_mixed_case_internal_field() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="internal fields"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <p>Proof_Stamp_Ref</p>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_mixed_case_internal_ref() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="internal governance refs"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <p>Gate-Decision-secret</p>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_script_body_fragment() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <script>alert('x')</script>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_entity_encoded_active_tag() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    &lt;script&gt;send()&lt;/script&gt;",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_embedded_content_tag() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <iframe src="https://example.test"></iframe>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_form_tag() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <form action="/send"><button>Send</button></form>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_allows_disabled_display_button() -> None:
    html = render_normal_user_dashboard_shell(
        document_title="Mullu Dashboard - Ready",
        body_lines=('    <button type="button" disabled aria-disabled="true">Approve</button>',),
        evidence_label="Evidence saved",
    )

    assert '<button type="button" disabled aria-disabled="true">Approve</button>' in html
    assert 'data-execution-allowed="false">Actions locked</span>' in html
    assert 'data-proof-hidden="true">Evidence saved</span>' in html


def test_render_normal_user_dashboard_shell_rejects_enabled_button() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <button type="button">Approve</button>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_button_without_aria_disabled() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <button type="button" disabled>Approve</button>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_inline_event_handler() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <button onclick="send()">Send</button>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_unlisted_inline_event_handler() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <input onfocus="send()" value="Ready">',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_contenteditable() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p contenteditable="true">Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_tabindex() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p tabindex="0">Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_interactive_role() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <div role="button">Approve</div>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_interactive_role_token_list() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <div role="presentation button">Approve</div>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_interactive_aria_state() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p aria-expanded="true">Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_shell_marker_override() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="override shell markers"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p data-execution-allowed="true">Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_html_comment() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="hidden content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <!-- hidden operator detail -->",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_hidden_attribute() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="hidden content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p hidden>Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_aria_hidden() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="hidden content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p aria-hidden="true">Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_script_url() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <a href="javascript:send()">Send</a>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_navigation_url() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <a href="https://example.test/audit">Audit details</a>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_srcdoc_payload() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <section srcdoc="<p>external</p>">Ready</section>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_inline_style_attribute() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <p style="position:fixed">Ready</p>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_body_style_block() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <style>@import url('https://example.test/audit.css')</style>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_svg_without_event() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"></circle></svg>',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_input_without_event() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <input value="Approve">',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_template_content() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <template><p>Hidden audit detail</p></template>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_custom_element() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="unsupported markup"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <mullu-proof>Ready</mullu-proof>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_legacy_parser_tag() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="unsupported markup"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=("    <plaintext>Ready</plaintext>",),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_slash_boundary_event_handler() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <svg/onload="send()">',),
            evidence_label="Evidence saved",
        )


def test_render_normal_user_dashboard_shell_rejects_mixed_case_event_handler() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="active content"):
        render_normal_user_dashboard_shell(
            document_title="Mullu Dashboard - Ready",
            body_lines=('    <button OnPointerEnter="send()">Send</button>',),
            evidence_label="Evidence saved",
        )


def test_normal_user_dashboard_client_rejects_internal_field_leak() -> None:
    dashboard, contract = _simple_payload_and_contract()
    leaked_dashboard = copy.deepcopy(dashboard)
    leaked_dashboard["simple_action_summaries"][0]["operator_details"] = {
        "proof_stamp_ref": "proof-secret",
    }

    with pytest.raises(RuntimeCoreInvariantError, match="internal fields"):
        build_normal_user_dashboard_client_view(leaked_dashboard, contract=contract)


def test_normal_user_dashboard_client_rejects_internal_ref_leak() -> None:
    dashboard, contract = _simple_payload_and_contract()
    leaked_dashboard = copy.deepcopy(dashboard)
    leaked_dashboard["simple_workflow_summaries"][0]["action_refs"] = ["proof-secret"]

    with pytest.raises(RuntimeCoreInvariantError, match="internal governance refs"):
        build_normal_user_dashboard_client_view(leaked_dashboard, contract=contract)


def test_normal_user_dashboard_client_rejects_contract_drift() -> None:
    dashboard, contract = _simple_payload_and_contract()
    drifted_contract = copy.deepcopy(contract)
    drifted_contract["hidden_fields"] = ["decision_ref"]

    with pytest.raises(RuntimeCoreInvariantError, match="missing hidden fields"):
        build_normal_user_dashboard_client_view(dashboard, contract=drifted_contract)


def test_normal_user_dashboard_client_rejects_page_route_contract_drift() -> None:
    dashboard, contract = _simple_payload_and_contract()
    drifted_contract = copy.deepcopy(contract)
    drifted_contract["page_route"]["path"] = "/api/v1/dashboard/state"

    with pytest.raises(RuntimeCoreInvariantError, match="page_route is unsupported"):
        build_normal_user_dashboard_client_view(dashboard, contract=drifted_contract)
