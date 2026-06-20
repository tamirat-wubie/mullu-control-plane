from __future__ import annotations

from copy import deepcopy

import pytest

from gateway.agentic_service_harness_dashboard_projection import (
    DashboardProjectionError,
    build_agentic_service_harness_dashboard_projection,
    load_foundation_dashboard_contract,
    render_agentic_service_harness_dashboard_html,
)


def test_foundation_contract_builds_bounded_projection() -> None:
    projection = build_agentic_service_harness_dashboard_projection(
        load_foundation_dashboard_contract()
    )

    assert projection["read_only"] is True
    assert projection["no_effect"] is True
    assert projection["action_controls_present"] is False
    assert projection["runtime_authority_granted"] is False
    assert projection["approval_required_for_effects"] is True
    assert projection["widget_count"] == 7
    assert {item["widget_id"] for item in projection["widgets"]} == {
        "account_summary",
        "repository_connection",
        "run_status",
        "approval_gate",
        "receipt_evidence",
        "workspace_safety",
        "readiness_next_action",
    }
    assert "write_to_branch" in projection["blocked_effects"]
    assert "terminal_closure" in projection["blocked_effects"]


def test_html_is_static_and_contains_no_effect_controls() -> None:
    projection = build_agentic_service_harness_dashboard_projection(
        load_foundation_dashboard_contract()
    )
    html = render_agentic_service_harness_dashboard_html(projection)
    lowered = html.lower()

    assert "mullu governed operator dashboard" in lowered
    assert "foundation mode" in lowered
    assert "read-only" in lowered
    assert "<form" not in lowered
    assert "<button" not in lowered
    assert "href=" not in lowered
    assert "method=" not in lowered
    assert "write_to_branch" in html


def test_html_escapes_contract_text() -> None:
    contract = load_foundation_dashboard_contract()
    changed = deepcopy(contract)
    changed["widgets"][0]["title"] = "<script>alert(1)</script>"

    projection = build_agentic_service_harness_dashboard_projection(changed)
    html = render_agentic_service_harness_dashboard_html(projection)

    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.parametrize(
    ("section", "field_name", "value", "message"),
    [
        ("scope", "route_admitted", True, "scope.route_admitted must be false"),
        (
            "scope",
            "receipt_store_append_enabled",
            True,
            "scope.receipt_store_append_enabled must be false",
        ),
        (
            "data_contract",
            "mutation_controls_allowed",
            True,
            "mutation_controls_allowed must be false",
        ),
    ],
)
def test_projection_rejects_authority_drift(
    section: str,
    field_name: str,
    value: object,
    message: str,
) -> None:
    contract = load_foundation_dashboard_contract()
    changed = deepcopy(contract)
    changed[section][field_name] = value

    with pytest.raises(DashboardProjectionError, match=message):
        build_agentic_service_harness_dashboard_projection(changed)


def test_projection_rejects_widget_action_controls() -> None:
    contract = load_foundation_dashboard_contract()
    changed = deepcopy(contract)
    changed["widgets"][0]["action_links_allowed"] = True

    with pytest.raises(
        DashboardProjectionError,
        match=r"widgets\[0\]\.action_links_allowed must be false",
    ):
        build_agentic_service_harness_dashboard_projection(changed)


def test_projection_rejects_action_class_expansion() -> None:
    contract = load_foundation_dashboard_contract()
    changed = deepcopy(contract)
    changed["data_contract"]["allowed_action_classes"] = ["read_only", "write"]

    with pytest.raises(
        DashboardProjectionError,
        match="allowed action classes must be exactly read_only",
    ):
        build_agentic_service_harness_dashboard_projection(changed)
