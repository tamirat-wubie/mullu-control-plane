"""Construction / AEC domain adapter tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.domain_adapters import (
    ConstructionActionKind,
    ConstructionRequest,
    UniversalResult,
    construction_run_with_ucja,
    construction_translate_from_universal,
    construction_translate_to_universal,
)


def _request(**overrides) -> ConstructionRequest:
    base = dict(
        kind=ConstructionActionKind.RFI,
        summary="clarification on beam dimension",
        project_id="PROJ-001",
        project_manager="alice",
        approver_chain=("superintendent",),
        general_contractor="acme-build",
        owner="dev-corp",
        permit_authority="DBI-SF",
        jurisdiction="US-CA-SF",
        trades_involved=("structural",),
        affected_drawings=("S-101",),
        acceptance_criteria=("response_time_within_sla",),
        permit_on_file=True,
        permit_required=True,
        active_safety_incident=False,
        multi_trade_coordinated=True,
        weather_sensitive=False,
        weather_window_open=True,
        is_emergency=False,
        blast_radius="task",
    )
    base.update(overrides)
    return ConstructionRequest(**base)


def test_translate_purpose_for_each_kind():
    for kind in ConstructionActionKind:
        # PERMIT_APPLICATION needs permit_authority; default fixture has it
        uni = construction_translate_to_universal(_request(kind=kind))
        assert ":" in uni.purpose_statement


def test_translate_authority_includes_pm_and_approvers():
    uni = construction_translate_to_universal(
        _request(approver_chain=("super", "engineer")),
    )
    assert "pm:alice" in uni.authority_required
    assert "approver:super" in uni.authority_required
    assert "approver:engineer" in uni.authority_required


def test_translate_observers_include_gc_owner_authority_jurisdiction_trades():
    uni = construction_translate_to_universal(
        _request(trades_involved=("structural", "mep_electrical")),
    )
    assert "project_audit" in uni.observer_required
    assert "gc:acme-build" in uni.observer_required
    assert "owner:dev-corp" in uni.observer_required
    assert "permit_authority:DBI-SF" in uni.observer_required
    assert "jurisdiction:US-CA-SF" in uni.observer_required
    assert "trade:structural" in uni.observer_required
    assert "trade:mep_electrical" in uni.observer_required


def test_translate_safety_officer_always_observer():
    """Safety oversight is continuous, modeled as always-on observer."""
    uni = construction_translate_to_universal(_request())
    assert "safety_officer" in uni.observer_required


def test_translate_incident_command_when_active_incident():
    uni = construction_translate_to_universal(
        _request(active_safety_incident=True),
    )
    assert "incident_command" in uni.observer_required


def test_translate_permit_missing_blocks_routine():
    uni = construction_translate_to_universal(
        _request(permit_on_file=False, is_emergency=False),
    )
    permit = [c for c in uni.constraint_set if c["domain"] == "permit"]
    assert len(permit) == 1
    assert permit[0]["violation_response"] == "block"


def test_translate_permit_missing_escalates_under_emergency():
    """Emergency make-safe is the narrow permit-required exception."""
    uni = construction_translate_to_universal(
        _request(permit_on_file=False, is_emergency=True),
    )
    permit = [c for c in uni.constraint_set if c["domain"] == "permit"]
    assert permit[0]["violation_response"] == "escalate"


def test_translate_permit_application_does_not_require_permit():
    uni = construction_translate_to_universal(
        _request(
            kind=ConstructionActionKind.PERMIT_APPLICATION,
            permit_on_file=False,
        ),
    )
    permit = [c for c in uni.constraint_set if c["domain"] == "permit"]
    assert permit == []


def test_translate_safety_freeze_blocks_routine_work():
    uni = construction_translate_to_universal(
        _request(active_safety_incident=True, is_emergency=False),
    )
    sf = [c for c in uni.constraint_set if c["domain"] == "safety_freeze"]
    assert len(sf) == 1
    assert sf[0]["violation_response"] == "block"


def test_translate_safety_freeze_escalates_under_emergency_repair():
    uni = construction_translate_to_universal(
        _request(active_safety_incident=True, is_emergency=True),
    )
    sf = [c for c in uni.constraint_set if c["domain"] == "safety_freeze"]
    assert sf[0]["violation_response"] == "escalate"


def test_translate_safety_freeze_does_not_block_inspection_kinds():
    """Inspection / punch list ARE the response to a safety incident."""
    for kind in (
        ConstructionActionKind.INSPECTION,
        ConstructionActionKind.PUNCH_LIST,
    ):
        uni = construction_translate_to_universal(
            _request(kind=kind, active_safety_incident=True),
        )
        sf = [c for c in uni.constraint_set if c["domain"] == "safety_freeze"]
        assert sf == [], f"{kind.value} should not be frozen"


def test_translate_multi_trade_uncoordinated_blocks():
    uni = construction_translate_to_universal(
        _request(
            trades_involved=("structural", "mep_mechanical"),
            multi_trade_coordinated=False,
        ),
    )
    tc = [c for c in uni.constraint_set if c["domain"] == "trade_coordination"]
    assert len(tc) == 1
    assert tc[0]["violation_response"] == "block"


def test_translate_single_trade_no_coordination_constraint():
    uni = construction_translate_to_universal(
        _request(trades_involved=("structural",), multi_trade_coordinated=False),
    )
    tc = [c for c in uni.constraint_set if c["domain"] == "trade_coordination"]
    assert tc == []


def test_translate_weather_sensitive_unfavorable_escalates():
    uni = construction_translate_to_universal(
        _request(weather_sensitive=True, weather_window_open=False),
    )
    w = [c for c in uni.constraint_set if c["domain"] == "weather"]
    assert len(w) == 1
    assert w[0]["violation_response"] == "escalate"


def test_translate_invalid_trade_rejected():
    with pytest.raises(ValueError, match="trade"):
        construction_translate_to_universal(_request(trades_involved=("psychic",)))


def test_translate_permit_application_without_authority_rejected():
    with pytest.raises(ValueError, match="permit_authority"):
        construction_translate_to_universal(
            _request(
                kind=ConstructionActionKind.PERMIT_APPLICATION,
                permit_authority="",
            ),
        )


def test_translate_blast_radius_to_permeability():
    cases = {
        "task":              "closed",
        "floor":             "selective",
        "building":          "selective",
        "project_portfolio": "open",
    }
    for blast, expected in cases.items():
        uni = construction_translate_to_universal(_request(blast_radius=blast))
        assert uni.boundary_specification["permeability"] == expected


def _result(state: str = "Pass") -> UniversalResult:
    return UniversalResult(
        job_definition_id=uuid4(),
        construct_graph_summary={
            "observation": 1, "inference": 1, "decision": 1,
            "transformation": 1, "validation": 1, "execution": 1,
        },
        cognitive_cycles_run=1,
        converged=True,
        proof_state=state,
    )


def test_permit_missing_routine_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(permit_on_file=False, is_emergency=False),
    )
    assert any("permit_missing_routine_work" in f for f in out.risk_flags)


def test_permit_missing_emergency_flagged_differently():
    out = construction_translate_from_universal(
        _result(),
        _request(permit_on_file=False, is_emergency=True),
    )
    assert any("permit_missing_under_emergency" in f for f in out.risk_flags)


def test_safety_incident_inspection_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(
            kind=ConstructionActionKind.INSPECTION,
            active_safety_incident=True,
        ),
    )
    assert any(
        "active_safety_incident_during_inspection" in f for f in out.risk_flags
    )


def test_safety_incident_routine_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(
            kind=ConstructionActionKind.MILESTONE,
            active_safety_incident=True,
        ),
    )
    assert any(
        "active_safety_incident_with_milestone" in f for f in out.risk_flags
    )


def test_multi_trade_uncoordinated_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(
            trades_involved=("structural", "mep_mechanical"),
            multi_trade_coordinated=False,
        ),
    )
    assert any("multi_trade_uncoordinated" in f for f in out.risk_flags)


def test_weather_unfavorable_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(weather_sensitive=True, weather_window_open=False),
    )
    assert any("weather_window_unfavorable" in f for f in out.risk_flags)


def test_emergency_mode_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(is_emergency=True),
    )
    assert any("emergency_make_safe_posture" in f for f in out.risk_flags)


def test_irreversible_action_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(kind=ConstructionActionKind.MILESTONE),
    )
    assert any("milestone_irreversible" in f for f in out.risk_flags)


def test_portfolio_blast_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(blast_radius="project_portfolio"),
    )
    assert any("project_portfolio_blast_radius" in f for f in out.risk_flags)


def test_permit_app_without_drawings_flagged():
    out = construction_translate_from_universal(
        _result(),
        _request(
            kind=ConstructionActionKind.PERMIT_APPLICATION,
            affected_drawings=(),
        ),
    )
    assert any(
        "permit_application_without_drawing_set" in f for f in out.risk_flags
    )


def test_protocol_includes_permit_step_when_on_file():
    out = construction_translate_from_universal(
        _result(),
        _request(permit_on_file=True),
    )
    assert any("permit on file" in s.lower() for s in out.project_protocol)


def test_protocol_includes_trade_coordination_step_for_multi_trade():
    out = construction_translate_from_universal(
        _result(),
        _request(
            trades_involved=("structural", "mep_electrical"),
            multi_trade_coordinated=True,
        ),
    )
    assert any(
        "trade coordination signoff" in s for s in out.project_protocol
    )


def test_protocol_milestone_includes_evidence_step():
    out = construction_translate_from_universal(
        _result(),
        _request(kind=ConstructionActionKind.MILESTONE),
    )
    assert any(
        "physical milestone" in s.lower() for s in out.project_protocol
    )


# ---- run_with_ucja ----


def test_run_complete_request_passes():
    out = construction_run_with_ucja(_request())
    assert out.governance_status == "approved"
    assert "pm: alice" in out.required_signoffs


def test_run_no_acceptance_criteria_blocks_at_l9():
    out = construction_run_with_ucja(_request(acceptance_criteria=()))
    assert "Unknown" in out.governance_status


def test_run_emergency_repair_during_safety_incident_passes():
    out = construction_run_with_ucja(
        _request(
            kind=ConstructionActionKind.MILESTONE,
            active_safety_incident=True,
            is_emergency=True,
            acceptance_criteria=("make_safe_documented",),
        ),
    )
    assert out.governance_status == "approved"
    assert out.is_emergency is True
    assert out.active_safety_incident is True


def test_result_carries_permit_and_safety_flags():
    out = construction_run_with_ucja(
        _request(
            permit_on_file=True,
            active_safety_incident=False,
            is_emergency=False,
        ),
    )
    assert out.permit_on_file is True
    assert out.active_safety_incident is False
    assert out.is_emergency is False
